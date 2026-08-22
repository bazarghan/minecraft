import { AlertCircle, CheckCircle2, ExternalLink, Globe, LoaderCircle, Map as MapIcon, Search, Upload } from 'lucide-react'
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { api, post } from '../api'
import { Empty, ErrorState, Loading } from '../components/States'
import type { Job, MapCatalog, MapCatalogEntry, MapEntry, Server } from '../types'

type PendingInstall = {map: MapEntry; server: Server}
type InstallFeedback = {
  mapId: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress: number
  message: string
}

export function MapsPage() {
  const [maps, setMaps] = useState<MapEntry[] | null>(null)
  const [servers, setServers] = useState<Server[]>([])
  const [catalog, setCatalog] = useState<MapCatalog | null>(null)
  const [catalogError, setCatalogError] = useState('')
  const [catalogSearch, setCatalogSearch] = useState('')
  const [catalogFilter, setCatalogFilter] = useState<'all' | 'official' | 'community'>('all')
  const [importing, setImporting] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [serverId, setServerId] = useState('')
  const [pendingInstall, setPendingInstall] = useState<PendingInstall | null>(null)
  const [installing, setInstalling] = useState('')
  const [installFeedback, setInstallFeedback] = useState<InstallFeedback | null>(null)

  const load = useCallback(() =>
    Promise.all([api<MapEntry[]>('/maps'), api<Server[]>('/servers')])
      .then(([loadedMaps, loadedServers]) => {
        setMaps(loadedMaps)
        setServers(loadedServers)
        setServerId(current => current || loadedServers[0]?.id || '')
        setError('')
      })
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Could not load maps')),
  [])

  const loadCatalog = useCallback(() => {
    setCatalogError('')
    return api<MapCatalog>('/maps/catalog')
      .then(setCatalog)
      .catch(reason => setCatalogError(reason instanceof Error ? reason.message : 'Could not load map catalog'))
  }, [])

  useEffect(() => {
    void load()
    void loadCatalog()
  }, [load, loadCatalog])

  async function waitForImport(job: Job, mapName: string) {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      await new Promise(resolve => window.setTimeout(resolve, 1000))
      const current = await api<Job>(`/jobs/${job.id}`)
      if (current.status === 'succeeded') {
        setMessage(`${mapName} was added to your map library.`)
        await load()
        return
      }
      if (current.status === 'failed') {
        throw new Error(current.error || `Could not import ${mapName}.`)
      }
    }
    setMessage(`${mapName} is still importing. You can follow it on the Jobs page.`)
  }

  async function importCatalogMap(entry: MapCatalogEntry) {
    setImporting(entry.id)
    setMessage(`Downloading and checking ${entry.name}…`)
    try {
      const job = await post<Job>('/maps/url', {
        url: entry.download_url,
        name: entry.name,
        description: entry.description,
        author: entry.author,
        minecraft_version: entry.minecraft_version || null,
      })
      await waitForImport(job, entry.name)
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Map import failed')
    } finally {
      setImporting('')
    }
  }

  async function importUrl(event: FormEvent) {
    event.preventDefault()
    try {
      const job = await post<Job>('/maps/url', {
        url,
        name,
        description: '',
        author: null,
        minecraft_version: null,
      })
      setMessage(`Import queued as job ${job.id.slice(0, 8)}.`)
      setUrl('')
      setName('')
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Import failed')
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    try {
      const job = await api<Job>('/maps/upload', { method: 'POST', body: data })
      setMessage(`Upload queued as job ${job.id.slice(0, 8)}.`)
      event.currentTarget.reset()
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Upload failed')
    }
  }

  function requestInstall(map: MapEntry) {
    const server = servers.find(item => item.id === serverId)
    if (!server) {
      setMessage('Choose a target server first.')
      return
    }
    setPendingInstall({map, server})
  }

  async function confirmInstall() {
    if (!pendingInstall) return
    const {map, server} = pendingInstall
    setPendingInstall(null)
    setInstalling(map.id)
    setInstallFeedback({mapId: map.id, status: 'queued', progress: 0, message: 'Waiting for the installation worker…'})
    try {
      const job = await post<Job>(`/maps/${map.id}/install`, {server_id: server.id, restart_after_install: true})
      for (let attempt = 0; attempt < 240; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 1000))
        const current = await api<Job>(`/jobs/${job.id}`)
        setInstallFeedback({
          mapId: map.id,
          status: current.status,
          progress: current.progress,
          message: installPhase(current),
        })
        if (current.status === 'succeeded') {
          setMessage(`${map.name} was installed on ${server.name}.`)
          await load()
          return
        }
        if (current.status === 'failed') {
          throw new Error(current.error || `Could not install ${map.name}.`)
        }
      }
      setInstallFeedback({mapId: map.id, status: 'running', progress: 95, message: 'Installation is still running. Check the Jobs page before trying again.'})
    } catch (reason) {
      const failure = reason instanceof Error ? reason.message : 'Install failed'
      setInstallFeedback({mapId: map.id, status: 'failed', progress: 0, message: failure})
      setMessage(failure)
    } finally {
      setInstalling('')
    }
  }

  const query = catalogSearch.trim().toLowerCase()
  const visibleCatalog = (catalog?.maps || []).filter(entry => {
    const matchesCategory = catalogFilter === 'all' || entry.category === catalogFilter
    const matchesSearch = !query || `${entry.name} ${entry.description} ${entry.minecraft_version}`.toLowerCase().includes(query)
    return matchesCategory && matchesSearch
  })
  const libraryNames = new Set((maps || []).map(map => map.name.toLowerCase()))

  return <div className="page">
    <header className="page-header">
      <div><p className="eyebrow">Curated worlds</p><h1>Map library</h1><p>Choose a parkour map, import your own ZIP, then install it on any server.</p></div>
    </header>

    {message && <div className="notice">{message}</div>}

    <section className="panel catalog-section">
      <div className="panel-title catalog-heading">
        <div><p className="eyebrow">HielkeMaps catalog</p><h2>Choose a parkour map</h2><p className="muted">The list is refreshed from HielkeMaps and includes official and community worlds.</p></div>
        <a className="button secondary" href="https://hielkemaps.com/maps/" target="_blank" rel="noreferrer">Visit website <ExternalLink size={14}/></a>
      </div>
      <div className="catalog-toolbar">
        <div className="search"><Search size={16}/><input value={catalogSearch} onChange={event => setCatalogSearch(event.target.value)} placeholder="Search parkour maps…"/></div>
        <div className="catalog-filters">
          {(['all', 'official', 'community'] as const).map(filter => <button type="button" key={filter} className={catalogFilter === filter ? 'active' : ''} onClick={() => setCatalogFilter(filter)}>{filter}</button>)}
        </div>
        {catalog && <small className={`catalog-source ${catalog.source}`}>{catalog.source === 'live' ? 'Live website list' : 'Saved fallback list'}</small>}
      </div>
      {catalogError ? <ErrorState message={catalogError} retry={loadCatalog}/> : catalog === null ? <Loading/> : visibleCatalog.length === 0 ? <Empty title="No matching maps" detail="Try a different search or category."/> : <div className="catalog-grid">
        {visibleCatalog.map(entry => {
          const inLibrary = libraryNames.has(entry.name.toLowerCase())
          return <article className="catalog-card" key={entry.id}>
            <div className="catalog-thumbnail"><MapIcon/><img src={entry.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer"/></div>
            <div className="catalog-card-body">
              <div className="catalog-meta"><span className={`catalog-category ${entry.category}`}>{entry.category}</span>{entry.minecraft_version && <span>Java {entry.minecraft_version}</span>}</div>
              <h3>{entry.name}</h3>
              <p>{entry.description || 'A parkour world from HielkeMaps.'}</p>
              <div className="catalog-actions">
                <button type="button" className="button primary" disabled={inLibrary || Boolean(importing)} onClick={() => void importCatalogMap(entry)}>{inLibrary ? 'In library' : importing === entry.id ? 'Importing…' : 'Add to library'}</button>
                <a href={entry.page_url} target="_blank" rel="noreferrer" aria-label={`View ${entry.name} on HielkeMaps`}><ExternalLink size={16}/></a>
              </div>
            </div>
          </article>
        })}
      </div>}
    </section>

    <section className="manual-import-section">
      <div className="section-heading"><p className="eyebrow">Other sources</p><h2>Upload or use a direct link</h2></div>
      <div className="dashboard-columns">
        <form className="panel" onSubmit={upload}>
          <div className="panel-title"><div><p className="eyebrow">Local archive</p><h2>Upload a ZIP</h2></div><Upload/></div>
          <label>Map name<input name="name" required maxLength={128}/></label>
          <label>Description<textarea name="description" maxLength={2000}/></label>
          <label>Minecraft version<input name="minecraft_version" placeholder="Optional"/></label>
          <label>ZIP file<input name="file" type="file" accept=".zip,application/zip" required/></label>
          <button className="button primary">Queue upload</button>
        </form>
        <form className="panel" onSubmit={importUrl}>
          <div className="panel-title"><div><p className="eyebrow">Direct source</p><h2>Import from URL</h2></div><Globe/></div>
          <label>Map name<input value={name} onChange={event => setName(event.target.value)} required/></label>
          <label>Direct HTTPS URL<input type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://example.com/world.zip" required/></label>
          <div className="notice danger">Private networks, metadata endpoints, unsafe redirects, and unbounded downloads are blocked.</div>
          <button className="button primary">Queue import</button>
        </form>
      </div>
    </section>

    <section className="panel map-section">
      <div className="panel-title"><div><p className="eyebrow">Validated archives</p><h2>Available maps</h2></div><label className="inline-select">Install target<select value={serverId} onChange={event => setServerId(event.target.value)}><option value="">Choose server</option>{servers.map(server => <option key={server.id} value={server.id}>{server.name}</option>)}</select></label></div>
      {error ? <ErrorState message={error} retry={load}/> : maps === null ? <Loading/> : maps.length === 0 ? <Empty title="No maps yet" detail="Choose a map above or provide your own ZIP."/> : <div className="card-grid">{maps.map(map => {
        const feedback = installFeedback?.mapId === map.id ? installFeedback : null
        const isInstalling = installing === map.id
        return <article className="map-card" key={map.id}>
          <div className="map-visual"><MapIcon/></div>
          <StatusBadge status={map.compatibility_status}/>
          <h3>{map.name}</h3>
          <p>{map.description || 'No description provided.'}</p>
          <small>{map.author || 'Unknown author'} · {(map.file_size / 1e6).toFixed(1)} MB · {map.minecraft_version || 'Version unverified'}</small>
          <button className="button secondary wide" disabled={Boolean(installing)} onClick={() => requestInstall(map)}>{isInstalling && <LoaderCircle className="spin-icon" size={15}/>} {isInstalling ? 'Installing…' : 'Back up & install'}</button>
          {feedback && <div className={`install-feedback ${feedback.status}`}>
            <span>{feedback.status === 'succeeded' ? <CheckCircle2 size={17}/> : feedback.status === 'failed' ? <AlertCircle size={17}/> : <LoaderCircle className="spin-icon" size={17}/>}</span>
            <div><strong>{feedback.status === 'succeeded' ? 'Installation complete' : feedback.status === 'failed' ? 'Installation failed' : `${feedback.progress}% complete`}</strong><small>{feedback.message}</small>{feedback.status !== 'succeeded' && feedback.status !== 'failed' && <span className="install-progress"><i style={{width: `${feedback.progress}%`}}/></span>}</div>
          </div>}
        </article>
      })}</div>}
    </section>

    {pendingInstall && <div className="modal-backdrop" role="presentation">
      <div className="modal install-confirmation" role="dialog" aria-modal="true" aria-labelledby="install-map-title">
        <p className="eyebrow">Confirm map installation</p>
        <h2 id="install-map-title">Install {pendingInstall.map.name}?</h2>
        <p>This will stop <strong>{pendingInstall.server.name}</strong>, create a safety backup of its current world, replace the world with this map, and start the server again.</p>
        <div className="notice danger"><AlertCircle size={18}/><div><strong>Players will be disconnected briefly</strong><span>Do not start, stop, or install another map until this finishes.</span></div></div>
        <div className="modal-actions"><button type="button" className="button secondary" onClick={() => setPendingInstall(null)}>Cancel</button><button type="button" className="button primary" onClick={() => void confirmInstall()}>Confirm & install</button></div>
      </div>
    </div>}
  </div>
}

function installPhase(job: Job) {
  if (job.status === 'queued') return 'Waiting for the installation worker…'
  if (job.status === 'succeeded') return 'Backup created, world installed, and server started successfully.'
  if (job.status === 'failed') return job.error || 'The installation failed.'
  if (job.progress < 20) return 'Preparing the server…'
  if (job.progress < 45) return 'Stopping the server and creating a safety backup…'
  if (job.progress < 65) return 'Finishing the safety backup…'
  if (job.progress < 85) return 'Extracting and installing the new world…'
  return 'Starting the Minecraft server…'
}

function StatusBadge({status}: {status: string}) {
  return <span className={`status status-${status}`}>{status}</span>
}
