import { useEffect, useState, type ReactNode } from 'react'
import { api, post, setCsrf } from './api'
import { AuthContext } from './auth-context'
import type { User } from './types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    try {
      const current = await api<User>('/auth/me')
      const csrf = await post<{ csrf_token: string }>('/auth/csrf')
      setCsrf(csrf.csrf_token)
      setUser(current)
    } catch {
      setUser(null)
      setCsrf('')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  async function login(username: string, password: string) {
    const result = await post<{ user: User; csrf_token: string }>('/auth/login', { username, password })
    setCsrf(result.csrf_token)
    setUser(result.user)
  }

  async function logout() {
    await post<void>('/auth/logout')
    setCsrf('')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>{children}</AuthContext.Provider>
}
