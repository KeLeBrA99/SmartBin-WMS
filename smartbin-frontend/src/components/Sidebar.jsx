import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const links = [
  { to: '/dashboard',      icon: '📊', label: 'Dashboard' },
  { to: '/inventario',     icon: '📦', label: 'Inventario' },
  { to: '/productos',      icon: '🏷️',  label: 'Productos' },
  { to: '/transferencias', icon: '🔄', label: 'Transferencias' },
]
const adminLinks = [
  { to: '/usuarios', icon: '👥', label: 'Usuarios' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  function handleLogout() { logout(); navigate('/login') }
  function handleNav() { setOpen(false) }

  return (
    <>
      {/* Topbar mobile */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">📦</span>
          <span className="font-bold text-white text-sm">SmartBin WMS</span>
        </div>
        <button onClick={() => setOpen(!open)} className="text-gray-400 hover:text-white p-1">
          {open ? (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Overlay mobile */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50
        w-56 min-h-screen bg-gray-900 border-r border-gray-800 flex flex-col
        transform transition-transform duration-200
        ${open ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>
        {/* Logo — solo desktop */}
        <div className="hidden md:block p-5 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📦</span>
            <div>
              <p className="font-bold text-white text-sm">SmartBin</p>
              <p className="text-xs text-gray-400">WMS v2.0</p>
            </div>
          </div>
        </div>

        {/* Espacio para topbar en mobile */}
        <div className="md:hidden h-14" />

        {/* Usuario */}
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-sm flex-shrink-0">
              {user?.nombre?.[0]?.toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm text-white font-medium truncate">{user?.nombre}</p>
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${user?.rol === 'admin' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'}`}>
                {user?.rol}
              </span>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          {links.map(link => (
            <NavLink key={link.to} to={link.to} onClick={handleNav}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }
            >
              <span>{link.icon}</span>
              <span>{link.label}</span>
            </NavLink>
          ))}

          {user?.rol === 'admin' && (
            <>
              <p className="text-xs text-gray-600 uppercase tracking-wider px-3 pt-3 pb-1">Admin</p>
              {adminLinks.map(link => (
                <NavLink key={link.to} to={link.to} onClick={handleNav}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                        : 'text-gray-400 hover:text-white hover:bg-gray-800'
                    }`
                  }
                >
                  <span>{link.icon}</span>
                  <span>{link.label}</span>
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t border-gray-800">
          <button onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-400/10 transition-colors">
            <span>🚪</span>
            <span>Cerrar Sesion</span>
          </button>
        </div>
      </aside>
    </>
  )
}