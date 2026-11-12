import { createContext, useContext, useState } from 'react'

const AuthContext = createContext()

function leerSesion() {
  try {
    const token = localStorage.getItem('sb_token')
    const user = JSON.parse(localStorage.getItem('sb_user'))
    if (token && user) return { user, token }
  } catch { /* datos corruptos: se ignoran */ }
  localStorage.removeItem('sb_token')
  localStorage.removeItem('sb_user')
  return { user: null, token: null }
}

export function AuthProvider({ children }) {
  // La sesion se lee una sola vez al montar (inicializador perezoso), sin
  // un efecto ni un render extra. Si lo guardado esta corrupto, se descarta
  // en lugar de romper toda la aplicacion.
  const [sesion, setSesion] = useState(leerSesion)
  const { user, token } = sesion
  const loading = false

  function login(userData, tokenData) {
    setSesion({ user: userData, token: tokenData })
    localStorage.setItem('sb_token', tokenData)
    localStorage.setItem('sb_user', JSON.stringify(userData))
  }

  function logout() {
    setSesion({ user: null, token: null })
    localStorage.removeItem('sb_token')
    localStorage.removeItem('sb_user')
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() { return useContext(AuthContext) }
