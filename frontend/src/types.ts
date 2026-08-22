export type Role = 'admin' | 'operator' | 'viewer'

export interface User {
  id: string
  username: string
  role: Role
  is_active: boolean
  created_at: string
}

export type ServerStatus = 'created' | 'starting' | 'running' | 'stopping' | 'stopped' | 'failed' | 'deleting'

export interface Server {
  id: string
  name: string
  slug: string
  version: string
  server_type: string
  status: ServerStatus
  port: number
  memory_mb: number
  cpu_limit: number
  max_players: number
  game_mode: string
  difficulty: string
  pvp: boolean
  hardcore: boolean
  view_distance: number
  simulation_distance: number
  motd: string
  level_name: string
  online_mode: boolean
  whitelist: string[]
  operators: string[]
  restart_policy: string
  last_error: string | null
  last_started_at: string | null
  created_at: string
}

export interface MinecraftVersion {
  id: string
  type: 'release' | 'snapshot' | 'old_beta' | 'old_alpha'
  release_time: string
}

export interface MinecraftVersionCatalog {
  latest: string
  source: 'mojang' | 'fallback'
  versions: MinecraftVersion[]
}

export interface HostMetrics {
  total_memory_mb: number
  reserved_host_memory_mb: number
  reserved_servers_memory_mb: number
  current_memory_used_mb: number
  allocatable_memory_mb: number
  cpu_percent: number
  cpu_count: number
  disk_total_bytes: number
  disk_used_bytes: number
  disk_percent: number
  overcommit_enabled: boolean
  servers: Record<ServerStatus, number>
}

export interface AuditEvent {
  id: string
  username: string | null
  action: string
  target: string | null
  ip_address: string | null
  result: string
  details: Record<string, unknown>
  request_id: string | null
  created_at: string
}

export interface MapEntry {
  id: string
  name: string
  description: string
  author: string | null
  minecraft_version: string | null
  file_size: number
  checksum_sha256: string
  source: string
  compatibility_status: string
  created_at: string
}

export interface Backup {
  id: string
  server_id: string
  reason: string
  file_size: number
  checksum_sha256: string
  created_at: string
}

export interface Job {
  id: string
  job_type: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress: number
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
}
