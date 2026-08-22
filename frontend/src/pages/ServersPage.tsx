import { Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Empty, ErrorState, Loading } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import type { Server } from '../types'

export function ServersPage() {
  const [servers, setServers] = useState<Server[] | null>(null); const [query, setQuery] = useState(''); const [error, setError] = useState('')
  const load = () => api<Server[]>('/servers').then(setServers).catch(e => setError(e.message))
  useEffect(() => { load() }, [])
  const filtered = useMemo(() => servers?.filter(s => `${s.name} ${s.slug} ${s.server_type}`.toLowerCase().includes(query.toLowerCase())) ?? [], [servers, query])
  return <div className="page"><header className="page-header"><div><p className="eyebrow">Fleet inventory</p><h1>Minecraft servers</h1><p>Every managed instance, reservation, and public endpoint.</p></div><Link className="button primary" to="/servers/new"><Plus size={17}/> New server</Link></header><div className="toolbar"><label className="search"><Search size={17}/><input aria-label="Search servers" placeholder="Search by name, type, or slug" value={query} onChange={e => setQuery(e.target.value)}/></label><span>{filtered.length} servers</span></div>{error ? <ErrorState message={error} retry={load}/> : servers === null ? <Loading/> : filtered.length === 0 ? <Empty title="No servers found" detail="Create your first server or adjust the search."/> : <div className="card-grid">{filtered.map(s => <Link to={`/servers/${s.id}`} className="server-card" key={s.id}><div className="server-card-top"><span className="server-avatar large">{s.name.slice(0,2).toUpperCase()}</span><StatusBadge status={s.status}/></div><h3>{s.name}</h3><p>{s.motd}</p><dl><div><dt>Edition</dt><dd>{s.server_type} {s.version}</dd></div><div><dt>Address</dt><dd>host:{s.port}</dd></div><div><dt>Memory</dt><dd>{(s.memory_mb / 1024).toFixed(1)} GB</dd></div><div><dt>Players</dt><dd>0 / {s.max_players}</dd></div></dl>{s.last_error && <div className="card-error">{s.last_error}</div>}</Link>)}</div>}</div>
}
