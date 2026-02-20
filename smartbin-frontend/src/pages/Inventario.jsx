import { useState, useEffect } from 'react'
import api from '../api'

export default function Inventario() {
  const [ubicaciones, setUbicaciones] = useState([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    api.get('/ubicaciones').then(r => { setUbicaciones(r.data); setLoading(false) })
  }, [])

  const filtradas = ubicaciones.filter(u =>
    u.codigo.toLowerCase().includes(busqueda.toLowerCase()) ||
    u.producto.toLowerCase().includes(busqueda.toLowerCase())
  )

  const getBadge = (cantidad, minimo) => {
    if (cantidad === 0) return 'bg-gray-500/10 text-gray-400 border-gray-500/20'
    if (cantidad <= minimo) return 'bg-red-500/10 text-red-400 border-red-500/20'
    if (cantidad <= minimo * 2) return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
  }

  if (loading) return <div className="p-8 text-gray-400">Cargando inventario...</div>

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Inventario</h1>
          <p className="text-gray-400 text-sm mt-1">{ubicaciones.length} ubicaciones en bodega</p>
        </div>
        <button
          onClick={() => api.get('/ubicaciones').then(r => setUbicaciones(r.data))}
          className="text-sm bg-gray-800 border border-gray-700 text-gray-300 px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors"
        >
          🔄 Actualizar
        </button>
      </div>

      {/* Busqueda */}
      <input
        type="text"
        placeholder="Buscar por ubicacion o producto..."
        value={busqueda}
        onChange={e => setBusqueda(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white text-sm outline-none focus:border-emerald-500 transition-colors"
      />

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtradas.map(u => (
          <div key={u.id} className={`bg-gray-900 border rounded-xl p-4 ${u.cantidad <= (u.stock_minimo || 5) && u.cantidad > 0 ? 'border-red-500/30' : 'border-gray-800'}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-sm font-bold text-white">{u.codigo}</span>
              <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">{u.tipo}</span>
            </div>
            <p className="text-gray-300 text-sm mb-3 truncate">{u.producto}</p>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold text-white">{u.cantidad}</span>
              <span className={`text-xs border px-2 py-0.5 rounded-full ${getBadge(u.cantidad, u.stock_minimo || 5)}`}>
                {u.cantidad === 0 ? 'Vacio' : u.cantidad <= (u.stock_minimo || 5) ? 'Stock bajo' : 'Normal'}
              </span>
            </div>
          </div>
        ))}
      </div>

      {filtradas.length === 0 && (
        <div className="text-center py-12 text-gray-500">No se encontraron ubicaciones</div>
      )}
    </div>
  )
}
