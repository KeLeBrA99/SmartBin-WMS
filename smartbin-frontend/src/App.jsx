import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Inventario from './pages/Inventario'
import Productos from './pages/Productos'
import Transferencias from './pages/Transferencias'
import Usuarios from './pages/Usuarios'
import Movimientos from './pages/Movimientos'
import Reorden from './pages/Reorden'
import Bodegas from './pages/Bodegas'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/dashboard" />} />
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <Layout><Dashboard /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/inventario" element={
            <ProtectedRoute>
              <Layout><Inventario /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/productos" element={
            <ProtectedRoute>
              <Layout><Productos /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/transferencias" element={
            <ProtectedRoute>
              <Layout><Transferencias /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/movimientos" element={
            <ProtectedRoute>
              <Layout><Movimientos /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/reorden" element={
            <ProtectedRoute>
              <Layout><Reorden /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/bodegas" element={
            <ProtectedRoute adminOnly>
              <Layout><Bodegas /></Layout>
            </ProtectedRoute>
          } />
          <Route path="/usuarios" element={
            <ProtectedRoute adminOnly>
              <Layout><Usuarios /></Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
