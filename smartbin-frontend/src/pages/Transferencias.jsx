import { useState, useEffect } from 'react'
import api from '../api'

export default function Transferencias() {
  const [productos, setProductos] = useState([])
  const [ubicaciones, setUbicaciones] = useState([])
  const [form, setForm] = useState({ producto_id: '', origen_id: '', destino_id: '', cantidad: 1 })
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get('/productos'), api.get('/ubicaciones')]).then(([p, u]) => {
      setProductos(p.data); setUbicaciones(u.data)
    })
  }, [])

  async function handleSubmit(e) {
    e.preventDefault(); setMsg(''); setError(''); setLoading(true)
    try {
      await api.post('/transferencias', {
        producto_id: parseInt(form.producto_id),
        origen_id: parseInt(form.origen_id),
        destino_id: parseInt(form.destino_id),
        cantidad: parseInt(form.cantidad)
      })
      setMsg('Transferencia realizada exitosamente')
      setForm({ producto_id: '', origen_id: '', destino_id: '', cantidad: 1 })
      const u = await api.get('/ubicaciones')
      setUbicaciones(u.data)
    } catch (err) { setError(err.response?.data?.detail || 'Error en la transferencia') }
    finally { setLoading(false) }
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Transferencias</h1>
        <p className="text-gray-400 text-sm mt-1">Mover productos entre ubicaciones de bodega</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Formulario */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-5">Nueva Transferencia</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">Producto</label>
              <select value={form.producto_id} onChange={e => setForm({...form, producto_id: e.target.value})}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm outline-none focus:border-emerald-500">
                <option value="">Seleccionar producto...</option>
                {productos.map(p => <option key={p.id} value={p.id}>{p.nombre} (Stock: {p.stock_total})</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">Origen</label>
                <select value={form.origen_id} onChange={e => setForm({...form, origen_id: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm outline-none focus:border-emerald-500">
                  <option value="">Origen...</option>
                  {ubicaciones.filter(u => u.cantidad > 0).map(u => <option key={u.id} value={u.id}>{u.codigo} ({u.cantidad})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">Destino</label>
                <select value={form.destino_id} onChange={e => setForm({...form, destino_id: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm outline-none focus:border-emerald-500">
                  <option value="">Destino...</option>
                  {ubicaciones.filter(u => u.id !== parseInt(form.origen_id)).map(u => <option key={u.id} value={u.id}>{u.codigo} - {u.tipo}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">Cantidad</label>
              <input type="number" min="1" value={form.cantidad} onChange={e => setForm({...form, cantidad: e.target.value})}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm outline-none focus:border-emerald-500"
              />
            </div>
            {msg && <p className="text-emerald-400 text-sm bg-emerald-400/10 border border-emerald-400/20 rounded-lg px-4 py-2">{msg}</p>}
            {error && <p className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2">{error}</p>}
            <button type="submit" disabled={loading}
              className="w-full bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold py-3 rounded-lg transition-colors disabled:opacity-50">
              {loading ? 'Procesando...' : '🔄 Transferir'}
            </button>
          </form>
        </div>

        {/* Estado actual */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Estado Actual de Ubicaciones</h2>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {ubicaciones.map(u => (
              <div key={u.id} className="flex items-center justify-between px-4 py-2.5 bg-gray-800 rounded-lg">
                <div>
                  <span className="font-mono text-sm font-bold text-white">{u.codigo}</span>
                  <span className="text-xs text-gray-500 ml-2">{u.tipo}</span>
                </div>
                <div className="text-right">
                  <span className={`text-sm font-bold ${u.cantidad === 0 ? 'text-gray-500' : 'text-white'}`}>{u.cantidad}</span>
                  {u.cantidad > 0 && <p className="text-xs text-gray-500 truncate max-w-24">{u.producto}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
