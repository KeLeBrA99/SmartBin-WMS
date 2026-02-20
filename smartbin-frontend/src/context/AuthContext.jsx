import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const t = localStorage.getItem('sb_token')
    const u = localStorage.getItem('sb_user')
    if (t && u) { setToken(t); setUser(JSON.parse(u)) }
    setLoading(false)
  }, [])

  function login(userData, tokenData) {
    setUser(userData); setToken(tokenData)
    localStorage.setItem('sb_token', tokenData)
    localStorage.setItem('sb_user', JSON.stringify(userData))
  }

  function logout() {
    setUser(null); setToken(null)
    localStorage.removeItem('sb_token')
    localStorage.removeItem('sb_user')
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() { return useContext(AuthContext) }
