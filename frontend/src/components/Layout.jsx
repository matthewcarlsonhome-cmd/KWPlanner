import React, { useState, useEffect } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { auth } from '../lib/api'

export default function Layout() {
  const location = useLocation()
  const [user, setUser] = useState(null)

  useEffect(() => {
    auth.me().then(setUser).catch(() => setUser(null))
  }, [])

  const nav = [
    { path: '/', label: 'Dashboard' },
    { path: '/settings', label: 'Settings' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top navbar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="text-xl font-bold text-blue-600">
              KW Planner
            </Link>
            <div className="flex gap-4">
              {nav.map(n => (
                <Link
                  key={n.path}
                  to={n.path}
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    location.pathname === n.path
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  {n.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-gray-500">
                {user.name || user.email}
              </span>
            )}
            {!user?.is_authenticated ? (
              <a
                href="/api/auth/login"
                className="text-sm bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
              >
                Sign in with Google
              </a>
            ) : (
              <button
                onClick={() => auth.logout().then(() => setUser(null))}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Sign out
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  )
}
