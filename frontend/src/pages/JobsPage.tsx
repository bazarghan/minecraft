import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Loading } from '../components/States'
import { StatusBadge } from '../components/StatusBadge'
import type { Job } from '../types'

export function JobsPage(){const[jobs,setJobs]=useState<Job[]|null>(null);const load=()=>api<Job[]>('/jobs').then(setJobs);useEffect(()=>{void load();const timer=setInterval(()=>void load(),5000);return()=>clearInterval(timer)},[]);return <div className="page"><header className="page-header"><div><p className="eyebrow">Durable work queue</p><h1>Background jobs</h1><p>Imports, backups, restores, and map installations continue outside the request.</p></div><button className="button secondary" onClick={()=>void load()}><RefreshCw size={16}/> Refresh</button></header><section className="panel">{jobs===null?<Loading/>:jobs.length===0?<Empty title="No jobs" detail="Long-running work will appear here."/>:<div className="table"><div className="table-head"><span>Operation</span><span>State</span><span>Progress</span><span>Started</span><span>Result</span></div>{jobs.map(job=><div key={job.id}><strong>{job.job_type.replaceAll('_',' ')}</strong><StatusBadge status={job.status}/><span><span className="progress compact"><i style={{width:`${job.progress}%`}}/></span> {job.progress}%</span><span>{new Date(job.created_at).toLocaleString()}</span><span>{job.error??(job.result?'Complete':'—')}</span></div>)}</div>}</section></div>}
