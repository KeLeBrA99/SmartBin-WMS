import { useState, useEffect } from 'react'
import api from '../api'

export default function Productos() {
  const [productos, setProductos] = useState([])
  const [categorias, setCategorias] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ sku: '', nombre: '', categoria_id: '', precio: '', stock_minimo: 5 })
  const [saving, setSaving] = useState(false)
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    Promise.all([api.get('/productos'), api.get('/categorias')]).then(([p, c]) => {
      setProductos(p.data); setCategorias(c.data); setLoading(false)
    })
  }, [])

  async function handleSubmit(e) {
    e.preventDefault(); setSaving(true)
    try {
      await api.post('/productos', { ...form, categoria_id: parseInt(form.categoria_id), precio: parseFloat(form.precio), stock_minimo: parseInt(form.stock_minimo) })
      const { data } = await api.get('/productos')
      setProductos(data); setShowForm(false)
      setForm({ sku: '', nombre: '', categoria_id: '', precio: '', stock_minimo: 5 })
    } catch (err) { alert(err.response?.data?.detail || 'Error al crear producto') }
    finally { setSaving(false) }
  }

  const filtrados = productos.filter(p =>
    p.nombre.toLowerCase().includes(busqueda.toLowerCase()) ||
    p.sku.toLowerCase().includes(busqueda.toLowerCase())
  )

  if (loading) return <div className="p-8 text-gray-400">Cargando productos...</div>

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Productos</h1>
          <p className="text-gray-400 text-sm mt-1">{productos.length} productos registrados</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="text-sm bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-4 py-2 rounded-lg transition-colors">
          {showForm ? '✕ Cancelar' : '+ Nuevo Producto'}
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Nuevo Producto</h2>
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { key: 'sku', label: 'SKU', type: 'text', placeholder: 'PROD-001' },
              { key: 'nombre', label: 'Nombre', type: 'text', placeholder: 'Nombre del producto' },
              { key: 'precio', label: 'Precio Compra', type: 'number', placeholder: '0.00' },
              { key: 'stock_minimo', label: 'Stock Minimo', type: 'number', placeholder: '5' },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">{f.label}</label>
                <input type={f.type} placeholder={f.placeholder} value={form[f.key]}
                  onChange={e => setForm({...form, [f.key]: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">Categoria</label>
              <select value={form.categoria_id} onChange={e => setForm({...form, categoria_id: e.target.value})}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500">
                <option value="">Seleccionar...</option>
                {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div className="flex items-end">
              <button type="submit" disabled={saving} className="w-full bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold py-2 rounded-lg transition-colors disabled:opacity-50">
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </form>
        </div>
      )}

      <input type="text" placeholder="Buscar productos..." value={busqueda} onChange={e => setBusqueda(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white text-sm outline-none focus:border-emerald-500"
      />

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['SKU','Nombre','Categoria','Stock Total','Stock Min'].map(h => (
                <th key={h} className="text-left text-xs text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtrados.map(p => (
              <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-emerald-400">{p.sku}</td>
                <td className="px-4 py-3 text-sm text-white">{p.nombre}</td>
                <td className="px-4 py-3 text-sm text-gray-400">{p.categoria}</td>
                <td className="px-4 py-3">
                  <span className={`text-sm font-bold ${p.stock_total <= p.stock_minimo ? 'text-red-400' : 'text-white'}`}>{p.stock_total}</span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-400">{p.stock_minimo}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtrados.length === 0 && <div className="text-center py-8 text-gray-500 text-sm">No se encontraron productos</div>}
      </div>
    </div>
  )
}
