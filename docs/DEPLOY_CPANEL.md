# Deploying to virtualinvestigation.xyz (cPanel / WHM, AlmaLinux 8)

Server: `vps.onixyindustries.com` · `103.185.75.157` · WHM 136 · root access.

Read section 1 before touching anything, and section 2 before assuming this
drops in like a PHP site. It does not.

---

## 0. Find the exact account name first

The WHM list truncates it. As root:

```bash
whmapi1 listaccts search=virtualinvestigation searchtype=domain \
  | grep -E 'user:|domain:'
```

Everything below writes `$ACCT` for that username. Set it once so a typo
cannot send a command to the wrong account:

```bash
ACCT=virtualinvestiga        # replace with the exact value printed above
HOME_DIR=/home/$ACCT
echo "$ACCT -> $HOME_DIR"; ls -la $HOME_DIR | head
```

---

## 1. Back up what is there now

Do this before anything else, and check the file exists before moving on.

### 1a. Full cPanel account backup — the one that matters

Captures files, databases, email, cron and DNS in one archive that cPanel
itself can restore:

```bash
/usr/local/cpanel/scripts/pkgacct $ACCT
```

It writes `/home/cpmove-$ACCT.tar.gz`. Confirm it:

```bash
ls -lh /home/cpmove-$ACCT.tar.gz
```

### 1b. A plain copy of the web root as well

Belt and braces — a tar you can read without cPanel:

```bash
STAMP=$(date +%Y%m%d-%H%M)
tar -czf /root/vipl-webroot-$STAMP.tar.gz -C $HOME_DIR public_html
ls -lh /root/vipl-webroot-$STAMP.tar.gz
```

### 1c. Databases, listed then dumped

```bash
mysql -e "SHOW DATABASES" | grep "^${ACCT}_"
```

For each one that appears:

```bash
mysqldump --single-transaction --routines --triggers DBNAME \
  > /root/vipl-DBNAME-$STAMP.sql
```

### 1d. Pull the backups off the server

From **your laptop**, not the server:

```powershell
scp root@103.185.75.157:/home/cpmove-*.tar.gz  .
scp root@103.185.75.157:/root/vipl-*.tar.gz    .
scp root@103.185.75.157:/root/vipl-*.sql       .
```

A backup that only exists on the machine you are about to change is not a
backup.

---

## 2. What this application actually needs

The old site was files served by Apache. This one is **two processes and a
database**, so the shape of the deployment is different:

| Piece | What it is | How it runs |
|---|---|---|
| Backend | FastAPI (Python 3.12+) | a long-lived `uvicorn` process on `127.0.0.1:8000` |
| Frontend | React, built to static files | plain files in `public_html` |
| Database | PostgreSQL 16 | a service on the box |
| Web server | Apache (cPanel's) | serves the static files, proxies `/api` to uvicorn |

Two consequences worth knowing before you start:

- **The frontend is built, not uploaded as source.** `npm run build` produces
  `frontend/dist/`; those files go in `public_html`. The `src/` folder never
  goes on the server.
- **The backend must keep running.** Apache cannot "run" it per request the
  way it runs PHP. It is a systemd service, and Apache forwards to it.

---

## 3. Install the runtimes (root, once)

```bash
dnf install -y python3.12 python3.12-pip python3.12-devel gcc \
               postgresql16-server postgresql16-contrib git

# Node for the build step — or build on your laptop and upload dist/ instead
curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
dnf install -y nodejs
```

Start PostgreSQL:

```bash
/usr/pgsql-16/bin/postgresql-16-setup initdb
systemctl enable --now postgresql-16
```

Create the database and a role with a real password:

```bash
DBPASS=$(openssl rand -base64 24)
sudo -u postgres psql <<SQL
CREATE ROLE vipl LOGIN PASSWORD '$DBPASS';
CREATE DATABASE investigation_db OWNER vipl;
SQL
echo "Database password: $DBPASS"     # write this down now
```

---

## 4. Put the code on the server

```bash
mkdir -p /opt/vipl && cd /opt/vipl
git clone https://github.com/Gaurav-X-dev/vipl_docs.git .
```

The application lives in `/opt/vipl`, **not** in `public_html`. Only the built
frontend goes into the web root — application code under a web root is code
someone can fetch.

---

## 5. Backend

```bash
cd /opt/vipl/backend
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

Write `/opt/vipl/backend/.env` — this file is not in the repository, and must
not be:

```bash
cat > /opt/vipl/backend/.env <<ENV
APP_NAME=Virtual Investigation Services
APP_ENV=production
DEBUG=false
APP_TIMEZONE=Asia/Kolkata

DATABASE_URL=postgresql+asyncpg://vipl:PASTE_DB_PASSWORD@localhost:5432/investigation_db
DB_ECHO=false

SECRET_KEY=PASTE_A_NEW_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7

SUPER_ADMIN_NAME=Super Administrator
SUPER_ADMIN_EMAIL=admin@virtualinvestigation.xyz
SUPER_ADMIN_PASSWORD=PASTE_A_STRONG_PASSWORD

FRONTEND_URL=https://virtualinvestigation.xyz
CORS_ORIGINS=https://virtualinvestigation.xyz

MAX_UPLOAD_MB=25
MAX_IMPORT_MB=40
ORGANIZATION_NAME=Virtual Investigation Services
ORGANIZATION_SHORT_NAME=VIPL
DATA_RETENTION_DAYS=90
ENV

chmod 600 /opt/vipl/backend/.env
```

Generate the secret with:

```bash
python3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then build the schema and the seed data:

```bash
cd /opt/vipl/backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/seed.py
.venv/bin/python -m scripts.tag_templates
.venv/bin/python -m scripts.retag_templates --confirm
```

The last two turn the insurers' specimen forms into templates. **Skip them and
the DOCX button fails on the first real case** with "has no tagged copy yet" —
the service still starts, so nothing warns you until a client is watching.

Then check the whole installation in one command:

```bash
.venv/bin/python -m scripts.doctor
```

It verifies the configuration, the storage directories and their ownership,
the migration version, the seed, and — the one that has bitten this project —
that every template has a tagged copy on disk. Each failure prints the command
that fixes it. Do not go further until it reports no failures.

---

## 6. Run the backend as a service

```bash
cat > /etc/systemd/system/vipl.service <<'UNIT'
[Unit]
Description=VIPL case management API
After=network.target postgresql-16.service
Requires=postgresql-16.service

[Service]
Type=simple
User=nobody
Group=nobody
WorkingDirectory=/opt/vipl/backend
ExecStart=/opt/vipl/backend/.venv/bin/uvicorn app.main:app \
          --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
# Bound to localhost only: Apache is the only thing that may reach it.

[Install]
WantedBy=multi-user.target
UNIT

chown -R nobody:nobody /opt/vipl/storage /opt/vipl/backend
systemctl daemon-reload
systemctl enable --now vipl
systemctl status vipl --no-pager
curl -s http://127.0.0.1:8000/health
```

That last command must answer with `"status":"ok"` before you go further.

---

## 7. Frontend

Point the build at the live domain, then build:

```bash
cd /opt/vipl/frontend
echo 'VITE_API_URL=https://virtualinvestigation.xyz/api/v1' > .env.production
npm ci
npm run build
```

Copy the result into the web root, keeping the old one aside:

```bash
mv $HOME_DIR/public_html $HOME_DIR/public_html.old-$(date +%Y%m%d)
mkdir -p $HOME_DIR/public_html
cp -r /opt/vipl/frontend/dist/* $HOME_DIR/public_html/
chown -R $ACCT:$ACCT $HOME_DIR/public_html
```

---

## 8. Apache: serve the app, proxy the API

The React router owns the URLs, so every path that is not a real file has to
return `index.html`. Create `$HOME_DIR/public_html/.htaccess`:

```apache
# The API and health check belong to uvicorn.
RewriteEngine On
RewriteRule ^api/(.*)$   http://127.0.0.1:8000/api/$1  [P,L]
RewriteRule ^health$     http://127.0.0.1:8000/health   [P,L]

# Everything else is the single-page app.
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^ index.html [L]

# The build hashes its filenames, so they can be cached hard.
<IfModule mod_headers.c>
  <FilesMatch "\.(js|css|woff2)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
  <FilesMatch "index\.html$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  Header always set X-Content-Type-Options "nosniff"
  Header always set X-Frame-Options "SAMEORIGIN"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
</IfModule>
```

Proxying needs the modules enabled once, as root:

```bash
grep -E 'proxy_module|proxy_http_module' /etc/apache2/conf/httpd.conf \
  || echo "enable proxy + proxy_http in WHM > EasyApache 4"
systemctl restart httpd
```

---

## 9. HTTPS

WHM ▸ *SSL/TLS* ▸ *Manage AutoSSL*, run it for the account. Or:

```bash
/usr/local/cpanel/bin/autossl_check --user=$ACCT
```

Then force it in `.htaccess`, above the other rules:

```apache
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]
```

The camera in the evidence dialog **requires HTTPS**. Without a certificate the
browser refuses to open it, and investigators cannot take photos.

---

## 10. Check it, in this order

```bash
systemctl is-active vipl                              # active
curl -s http://127.0.0.1:8000/health                  # status ok
curl -s https://virtualinvestigation.xyz/health       # same, through Apache
```

Then in a browser at `https://virtualinvestigation.xyz`:

1. Sign in with the Super Admin from `.env`
2. Clock In — the header should start counting
3. Import `samples/case_import_template.xlsx`
4. Open a case, fill the form, take a photo (HTTPS must be live)
5. Submit to office, assign office staff, approve, generate the DOCX

Or run the whole thing from the server in one go:

```bash
cd /opt/vipl/backend
.venv/bin/python -m scripts.doctor
.venv/bin/python -m scripts.smoke_flow --base https://virtualinvestigation.xyz
```

`0 failed` means the deployment is good.

### Accounts

The seed creates one Super Admin from `.env` and no staff, so a fresh
production database has nobody to assign work to. Add accounts with:

```bash
.venv/bin/python -m scripts.create_super_admin   --email you@virtualinvestigation.xyz --password 'a-strong-one' --name "Your Name"
```

The same command repairs an existing account: it resets the password, restores
the Super Admin role and clears a lockout from failed sign-ins.

---

## 11. Before real client data goes in

- [ ] `SECRET_KEY` is a fresh random string, not the development one
- [ ] Super Admin password changed from `Admin@123456`
- [ ] `DEBUG=false`, `APP_ENV=production`
- [ ] `CORS_ORIGINS` is the live domain only
- [ ] `.env` is `chmod 600` and owned by root
- [ ] PostgreSQL, not SQLite
- [ ] HTTPS enforced and renewing
- [ ] `/opt/vipl` is outside `public_html`
- [ ] A nightly backup of `investigation_db` and `/opt/vipl/storage`
- [ ] `scripts.doctor` reports no failures

Nightly database dump:

```bash
cat > /etc/cron.daily/vipl-backup <<'CRON'
#!/bin/bash
STAMP=$(date +%Y%m%d)
mkdir -p /root/vipl-backups
sudo -u postgres pg_dump investigation_db | gzip \
  > /root/vipl-backups/db-$STAMP.sql.gz
tar -czf /root/vipl-backups/storage-$STAMP.tar.gz -C /opt/vipl storage
find /root/vipl-backups -mtime +30 -delete
CRON
chmod +x /etc/cron.daily/vipl-backup
```

---

## Updating later

```bash
cd /opt/vipl && git pull
cd backend
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m scripts.doctor          # before restarting, not after
systemctl restart vipl
cd ../frontend && npm ci && npm run build
cp -r dist/* /home/$ACCT/public_html/
chown -R $ACCT:$ACCT /home/$ACCT/public_html
```

If an update adds or changes an insurer form, re-run the tagging as well —
`seed.py` registers the template, but only the tagging step produces the copy
that document generation actually reads:

```bash
cd /opt/vipl/backend
.venv/bin/python scripts/seed.py
.venv/bin/python -m scripts.tag_templates
.venv/bin/python -m scripts.retag_templates --confirm
chown -R nobody:nobody /opt/vipl/storage
systemctl restart vipl
.venv/bin/python -m scripts.doctor
```
