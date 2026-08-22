import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Loading } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import type { AuditEvent } from '../types'

export function AuditPage(){const[items,setItems]=useState<AuditEvent[]|null>(null);const[query,setQuery]=useState('');useEffect(()=>{api<AuditEvent[]>('/audit?limit=100').then(setItems)},[]);const filtered=useMemo(()=>items?.filter(x=>`${x.action} ${x.username} ${x.target} ${x.result}`.toLowerCase().includes(query.toLowerCase()))??[],[items,query]);return <div className="page"><header className="page-header"><div><p className="eyebrow">Accountability</p><h1>Audit log</h1><p>User, target, network origin, result, request ID, and timestamp.</p></div></header><div className="toolbar"><label className="search"><Search size={17}/><input placeholder="Filter audit events" value={query} onChange={e=>setQuery(e.target.value)}/></label></div><section className="panel">{items===null?<Loading/>:<div className="table"><div className="table-head"><span>Event</span><span>Actor</span><span>Result</span><span>IP address</span><span>Time</span><span>Request ID</span></div>{filtered.map(item=><div key={item.id}><strong>{item.action}</strong><span>{item.username??'system'}</span><StatusBadge status={item.result}/><code>{item.ip_address??'—'}</code><span>{new Date(item.created_at).toLocaleString()}</span><code title={item.request_id??''}>{item.request_id?.slice(0,8)??'—'}</code></div>)}</div>}</section></div>}
