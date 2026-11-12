import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Cargando...</div>
  if (!user) return <Navigate to="/login" />
  if (adminOnly && user.rol !== 'admin') return <Navigate to="/dashboard" />
  return children
}
