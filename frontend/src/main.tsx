import React from 'react'
import ReactDOM from 'react-dom/client'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { Layout } from './components/Layout'
import { Loading } from './components/States'
import { AuditPage } from './pages/AuditPage'
import { BackupsPage } from './pages/BackupsPage'
import { CreateServerPage } from './pages/CreateServerPage'
import { DashboardPage } from './pages/DashboardPage'
import { JobsPage } from './pages/JobsPage'
import { LoginPage } from './pages/LoginPage'
import { MapsPage } from './pages/MapsPage'
import { ProfilePage } from './pages/ProfilePage'
import { ServerDetailPage } from './pages/ServerDetailPage'
import { ServersPage } from './pages/ServersPage'
import { SettingsPage } from './pages/SettingsPage'
import { UsersPage } from './pages/UsersPage'
import './styles.css'

function Protected() {
  const { user, loading } = useAuth()
  if (loading) return <Loading label="Opening secure workspace" />
  return user ? <Layout /> : <Navigate to="/login" replace />
}

function LoginRoute() {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  return user ? <Navigate to="/" replace /> : <LoginPage />
}

const router = createBrowserRouter([
  { path: '/login', element: <LoginRoute /> },
  { path: '/', element: <Protected />, children: [
    { index: true, element: <DashboardPage /> },
    { path: 'servers', element: <ServersPage /> },
    { path: 'servers/new', element: <CreateServerPage /> },
    { path: 'servers/:id', element: <ServerDetailPage /> },
    { path: 'maps', element: <MapsPage /> },
    { path: 'backups', element: <BackupsPage /> },
    { path: 'jobs', element: <JobsPage /> },
    { path: 'users', element: <UsersPage /> },
    { path: 'audit', element: <AuditPage /> },
    { path: 'settings', element: <SettingsPage /> },
    { path: 'profile', element: <ProfilePage /> },
  ]},
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AuthProvider><RouterProvider router={router} /></AuthProvider></React.StrictMode>,
)
