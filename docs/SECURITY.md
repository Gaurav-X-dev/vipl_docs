# Security

Passwords use Argon2; JWT access and hashed refresh sessions expire independently. Login attempts, lockout, logout, session termination and heartbeat activity are recorded. RBAC is enforced server-side. Uploads are extension/size validated and stored under generated names. Errors use sanitized structured responses with incident/request IDs. Secrets stay in `.env`, which is ignored. Production must use TLS, a unique `SECRET_KEY`, rotated bootstrap credentials, restricted CORS, database backups and malware scanning for uploads.
