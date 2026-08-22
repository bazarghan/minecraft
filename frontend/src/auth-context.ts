import { createContext } from 'react'
import type { User } from './types'

export interface AuthValue {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

export const AuthContext = createContext<AuthValue | null>(null)
