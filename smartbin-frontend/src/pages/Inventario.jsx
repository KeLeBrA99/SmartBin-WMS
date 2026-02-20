import { useState, useEffect } from 'react'
import api from '../api'

function generarPDF(ubicaciones) {
  const fecha = new Date().toLocaleDateString('es-CO', { year: 'numeric', month: 'long', day: 'numeric' })
  const hora  = new Date().toLocaleTimeString('es-CO')

  const filas = ubicaciones.map(u => {
    const estado = u.cantidad === 0 ? 'Vacio' : u.cantidad <= (u.stock_minimo || 5) ? 'Stock bajo' : 'Normal'
    const color  = u.cantidad === 0 ? '#6b7280' : u.cantidad <= (u.stock_minimo || 5) ? '#ef4444' : '#10b981'
    return `
      <tr style="border-bottom:1px solid #f3f4f6">
        <td style="padding:10px 12px;font-family:monospace;font-weight:bold;color:#059669">${u.codigo}</td>
        <td style="padding:10px 12px;color:#374151">${u.tipo}</td>
        <td style="padding:10px 12px;color:#374151">${u.producto}</td>
        <td style="padding:10px 12px;font-weight:bold;font-size:1.1em">${u.cantidad}</td>
        <td style="padding:10px 12px"><span style="background:${color}20;color:${color};padding:2px 10px;border-radius:20px;font-size:0.8em;font-weight:600">${estado}</span></td>
      </tr>`
  }).join('')

  const total     = ubicaciones.length
  const vacias    = ubicaciones.filter(u => u.cantidad === 0).length
  const stockBajo = ubicaciones.filter(u => u.cantidad > 0 && u.cantidad <= (u.stock_minimo || 5)).length
  const normales  = total - vacias - stockBajo

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Reporte Inventario - SmartBin WMS</title>
      <style>
        * { margin:0; padding:0; box-sizing:border-box }
        body { font-family: system-ui, sans-serif; color:#111827; background:#fff }
        @media print {
          .no-print { display:none }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact }
        }
      </style>
    </head>
    <body>
      <!-- Header -->
      <div style="background:#0d1117;color:white;padding:24px 32px;display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-size:2em">📦</span>
          <div>
            <div style="font-size:1.4em;font-weight:800">SmartBin WMS</div>
            <div style="color:#10b981;font-size:0.85em">Sistema de Gestion de Bodegas</div>
          </div>
        </div>
        <div style="text-align:right;font-size:0.8em;color:#9ca3af">
          <div style="font-size:1.1em;color:white;font-weight:600">Reporte de Inventario</div>
          <div>${fecha}</div>
          <div>${hora}</div>
        </div>
      </div>

      <!-- Stats -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px 32px;background:#f9fafb;border-bottom:1px solid #e5e7eb">
        ${[
          ['Total Ubicaciones', total, '#6366f1'],
          ['Normales', normales, '#10b981'],
          ['Stock Bajo', stockBajo, '#ef4444'],
          ['Vacias', vacias, '#6b7280'],
        ].map(([label, val, color]) => `
          <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center">
            <div style="font-size:2em;font-weight:800;color:${color}">${val}</div>
            <div style="font-size:0.8em;color:#6b7280;margin-top:4px">${label}</div>
          </div>`).join('')}
      </div>

      <!-- Tabla -->
      <div style="padding:24px 32px">
        <h2 style="font-size:1em;font-weight:700;color:#374151;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.05em">Detalle por Ubicacion</h2>
        <table style="width:100%;border-collapse:collapse;background:white;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden">
          <thead>
            <tr style="background:#f3f4f6">
              ${['Codigo','Tipo','Producto','Cantidad','Estado'].map(h =>
                `<th style="padding:10px 12px;text-align:left;font-size:0.75em;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em">${h}</th>`
              ).join('')}
            </tr>
          </thead>
          <tbody>${filas}</tbody>
        </table>
      </div>

      <!-- Footer -->
      <div style="padding:16px 32px;border-top:1px solid #e5e7eb;display:flex;justify-content:space-between;font-size:0.75em;color:#9ca3af">
        <span>SmartBin WMS — Reporte generado automaticamente</span>
        <span>Total: ${total} ubicaciones</span>
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
    <div className="p-4 md:p-6 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Inventario</h1>
          <p className="text-gray-400 text-sm mt-1">{ubicaciones.length} ubicaciones en bodega</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => generarPDF(ubicaciones)}
            className="text-sm bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
          >
            📄 <span className="hidden sm:inline">Exportar PDF</span>
          </button>
          <button
            onClick={() => api.get('/ubicaciones').then(r => setUbicaciones(r.data))}
            className="text-sm bg-gray-800 border border-gray-700 text-gray-300 px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors"
          >
            🔄
          </button>
        </div>
      </div>

      <input
        type="text"
        placeholder="Buscar por ubicacion o producto..."
        value={busqueda}
        onChange={e => setBusqueda(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white text-sm outline-none focus:border-emerald-500 transition-colors"
      />

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