import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { mensajeError } from '../utils'

const INPUT = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500'
const LABEL = 'block text-xs text-gray-400 uppercase tracking-wider mb-1.5'
const BTN = 'bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-6 py-2 rounded-lg transition-colors disabled:opacity-50'
const BTN_SEC = 'text-sm text-gray-400 hover:text-white px-4 py-2 rounded-lg border border-gray-700 hover:border-gray-500 transition-colors'
const EDITAR = 'text-xs bg-blue-500/15 hover:bg-blue-500/25 text-blue-400 border border-blue-500/30 px-3 py-1.5 rounded-lg transition-colors'
const ELIMINAR = 'text-xs bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-lg transition-colors'
const TIPOS = ['Picking', 'Reserva', 'Recepcion', 'Despacho']
const BODEGA_VACIA = { id: null, codigo: '', nombre: '' }
const UBICACION_VACIA = { id: null, bodega_id: '', codigo: '', tipo: 'Picking' }

export default function Bodegas() {
  const [bodegas, setBodegas] = useState([])
  const [ubicaciones, setUbicaciones] = useState([])
  const [bodega, setBodega] = useState(BODEGA_VACIA)
  const [ubicacion, setUbicacion] = useState(UBICACION_VACIA)
  const [filtro, setFiltro] = useState('')
  const [aviso, setAviso] = useState({ texto: '', error: false })
  const [guardando, setGuardando] = useState(false)

  const cargar = useCallback(() =>
    Promise.all([api.get('/bodegas'), api.get('/ubicaciones')])
      .then(([b, u]) => {
        setBodegas(b.data)
        // /ubicaciones trae una fila por (ubicacion, producto): se agrupa por ubicacion
        const porId = new Map()
        for (const fila of u.data) {
          const actual = porId.get(fila.id) ?? { ...fila, unidades: 0 }
          actual.unidades += Number(fila.cantidad)
          porId.set(fila.id, actual)
        }
        setUbicaciones([...porId.values()])
      })
      .catch(err => setAviso({ texto: mensajeError(err, 'No se pudieron cargar las bodegas'), error: true }))
  , [])
  useEffect(() => { cargar() }, [cargar])

  async function ejecutar(peticion, exito, despues = () => {}) {
    setGuardando(true); setAviso({ texto: '', error: false })
    try {
      await peticion()
      await cargar(); despues()
      setAviso({ texto: exito, error: false })
    } catch (err) { setAviso({ texto: mensajeError(err, 'No se pudo completar la operacion'), error: true }) }
    finally { setGuardando(false) }
  }

  function guardarBodega(e) {
    e.preventDefault()
    const datos = { codigo: bodega.codigo, nombre: bodega.nombre }
    ejecutar(
      () => bodega.id ? api.put(`/bodegas/${bodega.id}`, datos) : api.post('/bodegas', datos),
      bodega.id ? 'Bodega actualizada' : 'Bodega creada',
      () => setBodega(BODEGA_VACIA),
    )
  }

  function guardarUbicacion(e) {
    e.preventDefault()
    ejecutar(
      () => ubicacion.id
        ? api.put(`/ubicaciones/${ubicacion.id}`, { codigo: ubicacion.codigo, tipo: ubicacion.tipo })
        : api.post('/ubicaciones', { bodega_id: parseInt(ubicacion.bodega_id), codigo: ubicacion.codigo, tipo: ubicacion.tipo }),
      ubicacion.id ? 'Ubicacion actualizada' : 'Ubicacion creada',
      () => setUbicacion(ubicacion.id ? UBICACION_VACIA : { ...ubicacion, codigo: '' }),
    )
  }

  function eliminarBodega(b) {
    if (!window.confirm(`¿Eliminar la bodega ${b.codigo} y sus ${b.ubicaciones} ubicaciones? Esta accion no se puede deshacer.`)) return
    ejecutar(() => api.delete(`/bodegas/${b.id}`), 'Bodega eliminada', () => { if (bodega.id === b.id) setBodega(BODEGA_VACIA) })
  }

  function eliminarUbicacion(u) {
    if (!window.confirm(`¿Eliminar la ubicacion ${u.codigo} de ${u.bodega}? Esta accion no se puede deshacer.`)) return
    ejecutar(() => api.delete(`/ubicaciones/${u.id}`), 'Ubicacion eliminada', () => { if (ubicacion.id === u.id) setUbicacion(UBICACION_VACIA) })
  }

  const visibles = ubicaciones.filter(u => !filtro || u.bodega_id === parseInt(filtro))

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Bodegas</h1>
        <p className="text-gray-400 text-sm mt-1">{bodegas.length} bodegas · {ubicaciones.length} ubicaciones</p>
      </div>

      {aviso.texto && (
        <p className={`text-sm px-4 py-2 rounded-lg border ${aviso.error ? 'text-red-400 bg-red-400/10 border-red-400/20' : 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'}`}>{aviso.texto}</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {bodegas.map(b => (
          <div key={b.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-sm font-bold text-emerald-400">{b.codigo}</span>
              <span className="text-2xl">🏭</span>
            </div>
            <p className="text-white font-medium truncate">{b.nombre}</p>
            <div className="flex gap-6 mt-4">
              <div><p className="text-2xl font-bold text-white">{b.ubicaciones}</p><p className="text-xs text-gray-500">ubicaciones</p></div>
              <div><p className="text-2xl font-bold text-white">{b.unidades}</p><p className="text-xs text-gray-500">unidades</p></div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setBodega({ id: b.id, codigo: b.codigo, nombre: b.nombre })} className={EDITAR}>✏️ Editar</button>
              <button onClick={() => eliminarBodega(b)} disabled={guardando} className={ELIMINAR}>🗑️ Eliminar</button>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={guardarBodega} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-white">{bodega.id ? 'Editar bodega' : 'Nueva bodega'}</h2>
          <div>
            <label className={LABEL}>Codigo</label>
            <input required maxLength={20} pattern="[A-Za-z0-9_\-]+" title="Solo letras, numeros, guion y guion bajo" placeholder="NORTE"
              value={bodega.codigo} onChange={e => setBodega({ ...bodega, codigo: e.target.value })} className={INPUT} />
          </div>
          <div>
            <label className={LABEL}>Nombre</label>
            <input required maxLength={120} placeholder="Bodega Norte" value={bodega.nombre}
              onChange={e => setBodega({ ...bodega, nombre: e.target.value })} className={INPUT} />
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={guardando} className={BTN}>{bodega.id ? 'Guardar cambios' : 'Crear bodega'}</button>
            {bodega.id && <button type="button" onClick={() => setBodega(BODEGA_VACIA)} className={BTN_SEC}>Cancelar</button>}
          </div>
        </form>

        <form onSubmit={guardarUbicacion} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-white">{ubicacion.id ? 'Editar ubicacion' : 'Nueva ubicacion'}</h2>
          <div>
            <label className={LABEL}>Bodega</label>
            <select required disabled={!!ubicacion.id} value={ubicacion.bodega_id}
              onChange={e => setUbicacion({ ...ubicacion, bodega_id: e.target.value })} className={`${INPUT} disabled:opacity-60`}>
              <option value="">Seleccionar...</option>
              {bodegas.map(b => <option key={b.id} value={b.id}>{b.codigo} — {b.nombre}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={LABEL}>Codigo</label>
              <input required maxLength={40} placeholder="A-01-01" value={ubicacion.codigo}
                onChange={e => setUbicacion({ ...ubicacion, codigo: e.target.value })} className={INPUT} />
            </div>
            <div>
              <label className={LABEL}>Tipo</label>
              <select value={ubicacion.tipo} onChange={e => setUbicacion({ ...ubicacion, tipo: e.target.value })} className={INPUT}>
                {[...new Set([...TIPOS, ubicacion.tipo])].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3">
            <button type="submit" disabled={guardando} className={BTN}>{ubicacion.id ? 'Guardar cambios' : 'Crear ubicacion'}</button>
            {ubicacion.id && <button type="button" onClick={() => setUbicacion(UBICACION_VACIA)} className={BTN_SEC}>Cancelar</button>}
          </div>
        </form>
      </div>

      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-white">Ubicaciones</h2>
        <select value={filtro} onChange={e => setFiltro(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500">
          <option value="">Todas las bodegas</option>
          {bodegas.map(b => <option key={b.id} value={b.id}>{b.codigo}</option>)}
        </select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['Bodega', 'Codigo', 'Tipo', 'Unidades', 'Acciones'].map(h => (
                <th key={h} className="text-left text-xs text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibles.map(u => (
              <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-gray-300">{u.bodega}</td>
                <td className="px-4 py-3 font-mono text-sm text-emerald-400">{u.codigo}</td>
                <td className="px-4 py-3 text-sm text-gray-300">{u.tipo}</td>
                <td className="px-4 py-3 text-sm font-bold text-white">{u.unidades}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => setUbicacion({ id: u.id, bodega_id: String(u.bodega_id), codigo: u.codigo, tipo: u.tipo })} className={EDITAR}>✏️ Editar</button>
                    <button onClick={() => eliminarUbicacion(u)} disabled={guardando} className={ELIMINAR}>🗑️ Eliminar</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visibles.length === 0 && <div className="text-center py-8 text-gray-500 text-sm">No hay ubicaciones</div>}
      </div>

      <p className="text-xs text-gray-500">Una bodega o ubicacion solo se puede eliminar cuando no tiene stock.</p>
    </div>
  )
}
