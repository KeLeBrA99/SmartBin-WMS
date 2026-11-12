import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { mensajeError } from '../utils'

const INPUT = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500'
const LABEL = 'block text-xs text-gray-400 uppercase tracking-wider mb-1.5'
const COLOR = {
  ENTRADA: 'bg-emerald-500/15 text-emerald-400',
  SALIDA: 'bg-red-500/15 text-red-400',
  TRANSFERENCIA: 'bg-blue-500/15 text-blue-400',
  AJUSTE: 'bg-yellow-500/15 text-yellow-400',
}
const VACIO = { tipo: 'SALIDA', producto_id: '', ubicacion_id: '', cantidad: 1, referencia: '' }

export default function Movimientos() {
  const [movimientos, setMovimientos] = useState([])
  const [productos, setProductos] = useState([])
  const [ubicaciones, setUbicaciones] = useState([])
  const [bodegas, setBodegas] = useState([])
  const [filtro, setFiltro] = useState({ tipo: '', bodega_id: '' })
  const [form, setForm] = useState(VACIO)
  const [aviso, setAviso] = useState({ texto: '', error: false })
  const [guardando, setGuardando] = useState(false)

  const cargarHistorial = useCallback(() => {
    const params = { limite: 200 }
    if (filtro.tipo) params.tipo = filtro.tipo
    if (filtro.bodega_id) params.bodega_id = filtro.bodega_id
    return api.get('/movimientos', { params }).then(r => setMovimientos(r.data))
      .catch(err => setAviso({ texto: mensajeError(err, 'No se pudo cargar el historial'), error: true }))
  }, [filtro])

  const cargarCatalogos = useCallback(() =>
    Promise.all([api.get('/productos'), api.get('/ubicaciones'), api.get('/bodegas')])
      .then(([p, u, b]) => { setProductos(p.data); setUbicaciones(u.data); setBodegas(b.data) })
      .catch(err => setAviso({ texto: mensajeError(err, 'No se pudieron cargar los datos'), error: true }))
  , [])

  useEffect(() => { cargarCatalogos() }, [cargarCatalogos])
  useEffect(() => { cargarHistorial() }, [cargarHistorial])

  // /ubicaciones devuelve una fila por (ubicacion, producto)
  const productoId = parseInt(form.producto_id)
  const opciones = form.tipo === 'SALIDA'
    ? ubicaciones.filter(u => u.cantidad > 0 && u.producto_id === productoId)
    : [...new Map(ubicaciones.map(u => [u.id, u])).values()]

  async function handleSubmit(e) {
    e.preventDefault(); setGuardando(true); setAviso({ texto: '', error: false })
    try {
      await api.post(form.tipo === 'SALIDA' ? '/salidas' : '/entradas', {
        producto_id: productoId,
        ubicacion_id: parseInt(form.ubicacion_id),
        cantidad: parseInt(form.cantidad),
        referencia: form.referencia.trim() || null,
      })
      setAviso({ texto: form.tipo === 'SALIDA' ? 'Salida registrada' : 'Entrada registrada', error: false })
      setForm({ ...VACIO, tipo: form.tipo })
      await Promise.all([cargarHistorial(), cargarCatalogos()])
    } catch (err) { setAviso({ texto: mensajeError(err, 'No se pudo registrar el movimiento'), error: true }) }
    finally { setGuardando(false) }
  }

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Movimientos</h1>
        <p className="text-gray-400 text-sm mt-1">Entradas, salidas e historial de todo cambio de stock</p>
      </div>

      {aviso.texto && (
        <p className={`text-sm px-4 py-2 rounded-lg border ${aviso.error ? 'text-red-400 bg-red-400/10 border-red-400/20' : 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'}`}>{aviso.texto}</p>
      )}

      <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
        <div>
          <label className={LABEL}>Tipo</label>
          <select value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value, ubicacion_id: '' })} className={INPUT}>
            <option value="SALIDA">Salida</option>
            <option value="ENTRADA">Entrada</option>
          </select>
        </div>
        <div className="lg:col-span-2">
          <label className={LABEL}>Producto</label>
          <select required value={form.producto_id} onChange={e => setForm({ ...form, producto_id: e.target.value, ubicacion_id: '' })} className={INPUT}>
            <option value="">Seleccionar...</option>
            {productos.map(p => <option key={p.id} value={p.id}>{p.nombre} (Stock: {p.stock_total})</option>)}
          </select>
        </div>
        <div className="lg:col-span-2">
          <label className={LABEL}>Ubicacion</label>
          <select required value={form.ubicacion_id} onChange={e => setForm({ ...form, ubicacion_id: e.target.value })} className={INPUT}>
            <option value="">{form.tipo === 'SALIDA' && productoId && opciones.length === 0 ? 'Sin stock de este producto' : 'Seleccionar...'}</option>
            {opciones.map(u => (
              <option key={`${u.id}-${u.producto_id}`} value={u.id}>
                {u.bodega} · {u.codigo}{form.tipo === 'SALIDA' ? ` (${u.cantidad})` : ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={LABEL}>Cantidad</label>
          <input type="number" min="1" step="1" required value={form.cantidad}
            onChange={e => setForm({ ...form, cantidad: e.target.value })} className={INPUT} />
        </div>
        <div className="sm:col-span-2 lg:col-span-4">
          <label className={LABEL}>Referencia (opcional)</label>
          <input maxLength={80} placeholder="Pedido, remision o motivo" value={form.referencia}
            onChange={e => setForm({ ...form, referencia: e.target.value })} className={INPUT} />
        </div>
        <div className="flex items-end lg:col-span-2">
          <button type="submit" disabled={guardando}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold py-2 rounded-lg transition-colors disabled:opacity-50">
            {guardando ? 'Guardando...' : form.tipo === 'SALIDA' ? 'Registrar salida' : 'Registrar entrada'}
          </button>
        </div>
      </form>

      <div className="flex flex-wrap gap-3">
        <select value={filtro.tipo} onChange={e => setFiltro({ ...filtro, tipo: e.target.value })}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500">
          <option value="">Todos los tipos</option>
          {Object.keys(COLOR).map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={filtro.bodega_id} onChange={e => setFiltro({ ...filtro, bodega_id: e.target.value })}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500">
          <option value="">Todas las bodegas</option>
          {bodegas.map(b => <option key={b.id} value={b.id}>{b.codigo}</option>)}
        </select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['Fecha', 'Tipo', 'Producto', 'Bodega', 'Ubicacion', 'Cantidad', 'Saldo', 'Usuario', 'Referencia'].map(h => (
                <th key={h} className="text-left text-xs text-gray-400 uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {movimientos.map(m => (
              <tr key={m.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{new Date(m.created_at).toLocaleString('es-CO')}</td>
                <td className="px-4 py-3"><span className={`text-xs px-2 py-1 rounded-full ${COLOR[m.tipo]}`}>{m.tipo}</span></td>
                <td className="px-4 py-3 text-sm text-white">{m.producto ?? `#${m.producto_id}`}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-300">{m.bodega ?? '-'}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-300">{m.ubicacion ?? '-'}</td>
                <td className={`px-4 py-3 text-sm font-bold ${m.delta < 0 ? 'text-red-400' : 'text-emerald-400'}`}>{m.delta > 0 ? `+${m.delta}` : m.delta}</td>
                <td className="px-4 py-3 text-sm text-gray-300">{m.saldo}</td>
                <td className="px-4 py-3 text-sm text-gray-400 whitespace-nowrap">{m.usuario ?? '-'}</td>
                <td className="px-4 py-3 text-sm text-gray-400">{m.referencia ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {movimientos.length === 0 && <div className="text-center py-8 text-gray-500 text-sm">Aun no hay movimientos registrados</div>}
      </div>
    </div>
  )
}
