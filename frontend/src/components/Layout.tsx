import { Activity, Archive, Boxes, ChevronLeft, ClipboardList, LogOut, Map, Menu, Plus, Server, Settings, Shield, UserRound, Users, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'

const links = [
  { to: '/', label: 'Overview', icon: Activity },
  { to: '/servers', label: 'Servers', icon: Server },
  { to: '/servers/new', label: 'Create server', icon: Plus },
  { to: '/maps', label: 'Map library', icon: Map },
  { to: '/backups', label: 'Backups', icon: Archive },
  { to: '/jobs', label: 'Background jobs', icon: Boxes },
]
const adminLinks = [
  { to: '/users', label: 'Users & roles', icon: Users },
  { to: '/audit', label: 'Audit log', icon: ClipboardList },
  { to: '/settings', label: 'Host settings', icon: Settings },
]

export function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  return <div className={`shell ${collapsed ? 'collapsed' : ''}`}>
    <button className="mobile-menu" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu /></button>
    {open && <button className="backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Shield size={22} /></div><div><b>Obsidian Panel</b><small>Server operations</small></div><button className="mobile-close" aria-label="Close navigation" onClick={() => setOpen(false)}><X /></button></div>
      <nav aria-label="Main navigation">
        <p className="nav-heading">Workspace</p>
        {links.map(({to, label, icon: Icon}) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)}><Icon size={18}/><span>{label}</span></NavLink>)}
        {user?.role === 'admin' && <><p className="nav-heading">Administration</p>{adminLinks.map(({to, label, icon: Icon}) => <NavLink key={to} to={to} onClick={() => setOpen(false)}><Icon size={18}/><span>{label}</span></NavLink>)}</>}
      </nav>
      <div className="sidebar-bottom">
        <NavLink to="/profile"><UserRound size={18}/><span>{user?.username}</span><em>{user?.role}</em></NavLink>
        <button onClick={() => void logout()}><LogOut size={18}/><span>Sign out</span></button>
        <button className="collapse" onClick={() => setCollapsed(!collapsed)}><ChevronLeft size={18}/><span>Collapse</span></button>
      </div>
    </aside>
    <main><Outlet /></main>
  </div>
}
