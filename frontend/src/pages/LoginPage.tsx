import { LockKeyhole, ShieldCheck } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { useAuth } from '../auth'

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { await login(username, password) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Sign in failed') } finally { setBusy(false) }
  }
  return <div className="login-page">
    <div className="login-story"><div className="login-brand"><ShieldCheck/> Obsidian Panel</div><div><p className="eyebrow">Self-host with confidence</p><h1>Your worlds.<br/>Under control.</h1><p>Secure operations for every Minecraft Java server on your host—from first boot to the last backup.</p></div><small>Independent community software. Not affiliated with Mojang Studios or Microsoft.</small></div>
    <div className="login-panel"><form className="login-card" onSubmit={submit}><div className="login-icon"><LockKeyhole/></div><p className="eyebrow">Administrator access</p><h2>Welcome back</h2><p>Sign in to manage your server fleet.</p>{error && <div className="form-error" role="alert">{error}</div>}<label>Username<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} minLength={12} required /></label><button className="button primary wide" disabled={busy}>{busy ? 'Signing in…' : 'Sign in securely'}</button><small>Protected by rate limiting and temporary account lockout.</small></form></div>
  </div>
}
