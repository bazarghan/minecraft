export function Loading({ label = 'Loading' }: { label?: string }) {
  return <div className="state" role="status"><span className="spinner" /> {label}…</div>
}

export function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty"><div className="empty-mark">◇</div><h3>{title}</h3><p>{detail}</p></div>
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="error-state" role="alert"><strong>Something went wrong</strong><p>{message}</p>{retry && <button className="button secondary" onClick={retry}>Try again</button>}</div>
}
