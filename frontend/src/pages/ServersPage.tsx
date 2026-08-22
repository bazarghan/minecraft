import { ArrowUpRight, Plus, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ServerAddress } from '../components/ServerAddress'
import { Empty, ErrorState, Loading } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import type { Server } from '../types'

export function ServersPage() {
  const [servers, setServers] = useState<Server[] | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const load = useCallback(() => api<Server[]>('/servers').then(items => { setServers(items); setError('') }).catch(e => setError(e.message)), [])
  useEffect(() => { void load() }, [load])
  const filtered = useMemo(() => servers?.filter(server => `${server.name} ${server.slug} ${server.server_type} ${server.version}`.toLowerCase().includes(query.toLowerCase())) ?? [], [servers, query])

  return <div className="page servers-page">
    <header className="page-header"><div><p className="eyebrow">Fleet inventory</p><h1>Minecraft servers</h1><p>Every managed instance, reservation, and public endpoint.</p></div><Link className="button primary" to="/servers/new"><Plus size={17}/> New server</Link></header>
    <div className="servers-toolbar"><label className="search"><Search size={17}/><input aria-label="Search servers" placeholder="Search by name, type, version, or slug" value={query} onChange={event => setQuery(event.target.value)}/></label><span>{filtered.length} {filtered.length === 1 ? 'server' : 'servers'}</span></div>
    {error ? <ErrorState message={error} retry={load}/> : servers === null ? <Loading/> : filtered.length === 0 ? <Empty title="No servers found" detail="Create your first server or adjust the search."/> : <div className="server-list">{filtered.map(server => <article className="server-list-card" key={server.id}>
      <div className="server-list-identity"><span className="server-avatar large">{server.name.slice(0, 2).toUpperCase()}</span><div><div className="server-name-line"><Link to={`/servers/${server.id}`}>{server.name}</Link><StatusBadge status={server.status}/></div><p>{server.motd}</p><small>{server.slug}</small></div></div>
      <dl className="server-list-facts"><div><dt>Edition</dt><dd>{server.server_type}</dd></div><div><dt>Version</dt><dd>{server.version}</dd></div><div><dt>Memory</dt><dd>{(server.memory_mb / 1024).toFixed(1)} GB</dd></div><div><dt>Players</dt><dd>0 / {server.max_players}</dd></div></dl>
      <div className="server-list-actions"><ServerAddress port={server.port}/><Link className="button secondary" to={`/servers/${server.id}`}>Manage <ArrowUpRight size={15}/></Link></div>
      {server.last_error && <div className="card-error">{server.last_error}</div>}
    </article>)}</div>}
  </div>
}
