import type { ServerStatus } from '../types'

export function StatusBadge({ status }: { status: ServerStatus | string }) {
  return <span className={`status status-${status}`}>{status}</span>
}
