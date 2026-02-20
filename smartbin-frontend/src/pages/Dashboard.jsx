import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import api from '../api'
import { useAuth } from '../context/AuthContext'

const COLORS = ['#10b981','#3b82f6','#f59e0b','#ef4444','#8b5cf6','#06b6d4']

function StatCard({ icon, label, value, color }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-2xl">{icon}</span>
        <span className={`text-xs px-2 py-1 rounded-full ${color}`}>{label}</span>
      </div>
      <p className="text-3xl font-bold text-white">{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const { user } = useAuth()

  useEffect(() => {
    api.get('/dashboard').then(r => { setData(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-400">Cargando dashboard...</div>

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">Bienvenido, {user?.nombre} — {new Date().toLocaleDateString('es-CO', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="🏷️" label="Productos" value={data?.total_productos ?? 0} color="bg-emerald-500/10 text-emerald-400" />
        <StatCard icon="📍" label="Ubicaciones" value={data?.total_ubicaciones ?? 0} color="bg-blue-500/10 text-blue-400" />
        <StatCard icon="👥" label="Usuarios" value={data?.total_usuarios ?? 0} color="bg-purple-500/10 text-purple-400" />
        <StatCard icon="⚠️" label="Alertas" value={data?.alertas_stock?.length ?? 0} color="bg-red-500/10 text-red-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Grafica de barras */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Stock por Categoria</h2>
          {data?.stock_por_categoria?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.stock_por_categoria}>
                <XAxis dataKey="categoria" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8 }} labelStyle={{ color: '#fff' }} />
                <Bar dataKey="total" fill="#10b981" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-gray-500 text-sm">Sin datos</p>}
        </div>

        {/* Alertas de stock */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <span>⚠️</span> Alertas de Stock Minimo
          </h2>
          {data?.alertas_stock?.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {data.alertas_stock.map((item, i) => (
                <div key={i} className="flex items-center justify-between bg-red-500/5 border border-red-500/20 rounded-lg px-4 py-2">
                  <span className="text-sm text-white">{item.nombre}</span>
                  <div className="text-right">
                    <span className="text-red-400 text-sm font-bold">{item.stock_total}</span>
                    <span className="text-gray-500 text-xs ml-1">/ min {item.stock_minimo}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-emerald-400 text-sm">
              <span>✅</span> Todo el inventario en niveles normales
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
