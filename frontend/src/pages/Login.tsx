import { useState, type FormEvent } from "react";
import { Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { errorMessage, hasToken } from "../api";
import { useAuth } from "../auth";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  // Empty, not the development seed account: a pre-filled address is a
  // credential hint on a public sign-in page, and it sent real users to
  // an account that does not exist on the production database.
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (hasToken()) return <Navigate to="/" replace />;
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password, remember);
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-art">
        <div className="art-content">
          <div className="brand large">
            <div className="brand-mark">V</div>
            <div>
              <b>VIPL</b>
              <span>Virtual Investigation Services</span>
            </div>
          </div>
          <h1>
            Investigation intelligence.
            <br />
            Built for every case.
          </h1>
          <p>
            From bank file to verified report—with complete traceability, secure
            collaboration, and company-ready documents.
          </p>
          <div className="trust">
            <ShieldCheck />
            <span>
              <b>Enterprise-grade controls</b>
              <small>Role-based access · Audit trail · Secure documents</small>
            </span>
          </div>
        </div>
      </div>
      <div className="login-panel">
        <form onSubmit={submit}>
          <div className="mobile-brand">VIPL</div>
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h2>Welcome back</h2>
          <p>Sign in to continue to the case management portal.</p>
          {error && <div className="form-error">{error}</div>}
          <label>
            Work email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              // The field is empty on load, so put the caret in it and keep a
              // phone keyboard from capitalising the first letter.
              autoFocus
              autoCapitalize="none"
              spellCheck={false}
              placeholder="you@company.com"
              required
            />
          </label>
          <label>
            Password
            <div className="password">
              <LockKeyhole />
              <input
                type={show ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                placeholder="Enter your password"
              />
              <button type="button" onClick={() => setShow(!show)}>
                {show ? <EyeOff /> : <Eye />}
              </button>
            </div>
          </label>
          <div className="form-row">
            <label className="check">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              Keep me signed in
            </label>
            <a href="#forgot">Forgot password?</a>
          </div>
          <button className="primary submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in securely"}
          </button>
          <small className="legal">
            Access is restricted to authorised VIPL personnel. All activity is
            logged.
          </small>
        </form>
      </div>
    </div>
  );
}
