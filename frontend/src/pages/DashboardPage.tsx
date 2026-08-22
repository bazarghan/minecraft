import { AlertTriangle, Cpu, HardDrive, MemoryStick, Plus, Server as ServerIcon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorState, Loading } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import type { AuditEvent, HostMetrics, Server } from '../types'

const gb = (mb: number) => `${(mb / 1024).toFixed(1)} GB`

export function DashboardPage() {
  const [metrics, setMetrics] = useState<HostMetrics | null>(null)
  const [servers, setServers] = useState<Server[]>([])
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)
  const load = useCallback(async () => { try { const [m, s] = await Promise.all([api<HostMetrics>('/host/metrics'), api<Server[]>('/servers')]); setMetrics(m); setServers(s); setError('') } catch (e) { setError(e instanceof Error ? e.message : 'Dashboard unavailable') } }, [])
  useEffect(() => { void load(); const stream = new EventSource('/api/v1/events', { withCredentials: true }); stream.onopen = () => setConnected(true); stream.onerror = () => setConnected(false); stream.addEventListener('update', event => { const items = JSON.parse((event as MessageEvent).data) as AuditEvent[]; setEvents(old => [...items, ...old].slice(0, 8)); void load() }); return () => stream.close() }, [load])
  if (error && !metrics) return <Page><ErrorState message={error} retry={() => void load()} /></Page>
  if (!metrics) return <Page><Loading label="Reading host capacity" /></Page>
  return <Page>
    <header className="page-header"><div><p className="eyebrow">Host command center</p><h1>Good to see you.</h1><p>Capacity, health, and recent activity across your fleet.</p></div><div className="header-actions"><span className={`connection ${connected ? 'online' : ''}`}>{connected ? 'Live' : 'Reconnecting'}</span><Link className="button primary" to="/servers/new"><Plus size={17}/> New server</Link></div></header>
    {servers.some(s => s.status === 'failed') && <div className="notice danger"><AlertTriangle/><div><strong>One or more servers need attention</strong><span>Open the affected server to review its last safe error and logs.</span></div></div>}
    <section className="metric-grid">
      <Metric icon={<MemoryStick/>} label="Allocatable memory" value={gb(metrics.allocatable_memory_mb)} detail={`${gb(metrics.reserved_servers_memory_mb)} reserved by servers`} progress={100 - metrics.allocatable_memory_mb / metrics.total_memory_mb * 100}/>
      <Metric icon={<Cpu/>} label="Host CPU" value={`${metrics.cpu_percent.toFixed(0)}%`} detail={`${metrics.cpu_count} logical cores`} progress={metrics.cpu_percent}/>
      <Metric icon={<HardDrive/>} label="Disk usage" value={`${metrics.disk_percent.toFixed(0)}%`} detail={`${(metrics.disk_used_bytes / 1e9).toFixed(0)} of ${(metrics.disk_total_bytes / 1e9).toFixed(0)} GB`} progress={metrics.disk_percent}/>
      <Metric icon={<ServerIcon/>} label="Active servers" value={`${metrics.servers.running ?? 0}`} detail={`${metrics.servers.stopped ?? 0} stopped · ${metrics.servers.starting ?? 0} starting`} progress={servers.length ? (metrics.servers.running / servers.length) * 100 : 0}/>
    </section>
    <div className="dashboard-columns"><section className="panel"><div className="panel-title"><div><p className="eyebrow">Fleet</p><h2>Server pulse</h2></div><Link to="/servers">View all</Link></div><div className="server-rows">{servers.slice(0, 6).map(server => <Link to={`/servers/${server.id}`} className="server-row" key={server.id}><span className="server-avatar">{server.name.slice(0, 2).toUpperCase()}</span><span><strong>{server.name}</strong><small>{server.server_type} · {server.version} · :{server.port}</small></span><span className="server-memory">{gb(server.memory_mb)}</span><StatusBadge status={server.status}/></Link>)}{servers.length === 0 && <p className="muted">No servers yet. Create one when you are ready.</p>}</div></section><section className="panel"><div className="panel-title"><div><p className="eyebrow">Audit trail</p><h2>Recent activity</h2></div><Link to="/audit">View log</Link></div><div className="timeline">{events.map(item => <div key={item.id}><span className={`dot ${item.result}`}/><p><strong>{item.action.replaceAll('.', ' ')}</strong><small>{item.username ?? 'system'} · {new Date(item.created_at).toLocaleString()}</small></p></div>)}{events.length === 0 && <p className="muted">Waiting for new activity…</p>}</div></section></div>
  </Page>
}

function Metric({ icon, label, value, detail, progress }: { icon: React.ReactNode; label: string; value: string; detail: string; progress: number }) { return <article className="metric"><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong><small>{detail}</small><div className="progress"><i style={{width: `${Math.max(2, Math.min(progress, 100))}%`}}/></div></article> }
function Page({ children }: { children: React.ReactNode }) { return <div className="page">{children}</div> }
