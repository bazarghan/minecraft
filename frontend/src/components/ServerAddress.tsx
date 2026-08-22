import { Check, Copy } from 'lucide-react'
import { useState } from 'react'


export function ServerAddress({ port, compact = false }: { port: number; compact?: boolean }) {
  const [copied, setCopied] = useState(false)
  const address = `${window.location.hostname}:${port}`

  async function copyAddress() {
    await navigator.clipboard.writeText(address)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  return <div className={`server-address ${compact ? 'compact' : ''}`}>
    <code>{address}</code>
    <button type="button" onClick={() => void copyAddress()} aria-label={`Copy ${address}`} title="Copy server address">
      {copied ? <Check size={15}/> : <Copy size={15}/>}
      {!compact && <span>{copied ? 'Copied' : 'Copy address'}</span>}
    </button>
  </div>
}
