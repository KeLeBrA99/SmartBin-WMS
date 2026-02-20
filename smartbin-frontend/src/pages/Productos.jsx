import { useState, useEffect } from 'react'
import api from '../api'

function generarPDFProductos(productos) {
  const fecha = new Date().toLocaleDateString('es-CO', { year: 'numeric', month: 'long', day: 'numeric' })
  const hora  = new Date().toLocaleTimeString('es-CO')

  const filas = productos.map(p => {
    const alerta = p.stock_total <= p.stock_minimo
    return `
      <tr style="border-bottom:1px solid #f3f4f6">
        <td style="padding:10px 12px;font-family:monospace;font-size:0.85em;color:#059669">${p.sku}</td>
        <td style="padding:10px 12px;color:#111827;font-weight:500">${p.nombre}</td>
        <td style="padding:10px 12px;color:#6b7280">${p.categoria || '-'}</td>
        <td style="padding:10px 12px;font-weight:700;color:${alerta ? '#ef4444' : '#111827'}">${p.stock_total}</td>
        <td style="padding:10px 12px;color:#6b7280">${p.stock_minimo}</td>
        <td style="padding:10px 12px">
          <span style="background:${alerta ? '#fee2e2' : '#d1fae5'};color:${alerta ? '#dc2626' : '#059669'};padding:2px 10px;border-radius:20px;font-size:0.78em;font-weight:600">
            ${alerta ? 'Stock bajo' : 'Normal'}
          </span>
        </td>
      </tr>`
  }).join('')

  const total   = productos.length
  const alertas = productos.filter(p => p.stock_total <= p.stock_minimo).length

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Reporte Productos - SmartBin WMS</title>
      <style>
        * { margin:0;padding:0;box-sizing:border-box }
        body { font-family:system-ui,sans-serif;color:#111827 }
        @media print { .no-print{display:none} body{-webkit-print-color-adjust:exact;print-color-adjust:exact} }
      </style>
    </head>
    <body>
      <div style="background:#0d1117;color:white;padding:24px 32px;display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-size:2em">📦</span>
          <div>
            <div style="font-size:1.4em;font-weight:800">SmartBin WMS</div>
            <div style="color:#10b981;font-size:0.85em">Sistema de Gestion de Bodegas</div>
          </div>
        </div>
        <div style="text-align:right;font-size:0.8em;color:#9ca3af">
          <div style="font-size:1.1em;color:white;font-weight:600">Reporte de Productos</div>
          <div>${fecha}</div><div>${hora}</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:24px 32px;background:#f9fafb;border-bottom:1px solid #e5e7eb">
        ${[
          ['Total Productos', total, '#6366f1'],
          ['Con Stock Normal', total - alertas, '#10b981'],
          ['Alertas de Stock', alertas, '#ef4444'],
        ].map(([label, val, color]) => `
          <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center">
            <div style="font-size:2em;font-weight:800;color:${color}">${val}</div>
            <div style="font-size:0.8em;color:#6b7280;margin-top:4px">${label}</div>
          </div>`).join('')}
      </div>

      <div style="padding:24px 32px">
        <h2 style="font-size:1em;font-weight:700;color:#374151;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.05em">Catalogo de Productos</h2>
        <table style="width:100%;border-collapse:collapse;background:white;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
          <thead>
            <tr style="background:#f3f4f6">
              ${['SKU','Nombre','Categoria','Stock','Min','Estado'].map(h =>
                `<th style="padding:10px 12px;text-align:left;font-size:0.75em;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em">${h}</th>`
              ).join('')}
            </tr>
          </thead>
          <tbody>${filas}</tbody>
        </table>
      </div>

      <div style="padding:16px 32px;border-top:1px solid #e5e7eb;display:flex;justify-content:space-between;font-size:0.75em;color:#9ca3af">
        <span>SmartBin WMS — Reporte generado automaticamente</span>
        <span>Total: ${total} productos</span>
      </div>

      <div class="no-print" style="position:fixed;bottom:24px;right:24px">
        <button onclick="window.print()" style="background:#10b981;color:white;border:none;padding:12px 24px;border-radius:8px;font-size:1em;font-weight:600;cursor:pointer">
          🖨️ Imprimir / Guardar PDF
        </button>
      </div>
    </body>
    </html>`

  const ventana = window.open('', '_blank')
  ventana.document.write(html)
  ventana.document.close()
}

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
    <div className="p-4 md:p-6 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Productos</h1>
          <p className="text-gray-400 text-sm mt-1">{productos.length} productos registrados</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => generarPDFProductos(productos)}
            className="text-sm bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-4 py-2 rounded-lg transition-colors flex items-center gap-2">
            📄 <span className="hidden sm:inline">Exportar PDF</span>
          </button>
          <button onClick={() => setShowForm(!showForm)}
            className="text-sm bg-gray-800 border border-gray-700 text-gray-300 px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors">
            {showForm ? '✕' : '+ Nuevo'}
          </button>
        </div>
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
              <button type="submit" disabled={saving}
                className="w-full bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold py-2 rounded-lg transition-colors disabled:opacity-50">
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </form>
        </div>
      )}

      <input type="text" placeholder="Buscar productos..." value={busqueda} onChange={e => setBusqueda(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white text-sm outline-none focus:border-emerald-500"
      />

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['SKU','Nombre','Categoria','Stock','Min'].map(h => (
                <th key={h} className="text-left text-xs text-gray-400 uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtrados.map(p => (
              <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-emerald-400 whitespace-nowrap">{p.sku}</td>
                <td className="px-4 py-3 text-sm text-white">{p.nombre}</td>
                <td className="px-4 py-3 text-sm text-gray-400 whitespace-nowrap">{p.categoria}</td>
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