import { useState, useEffect } from 'react'
import api from '../api'
import { mensajeError } from '../utils'

const INPUT = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500'
const LABEL = 'block text-xs text-gray-400 uppercase tracking-wider mb-1.5'
const TIPOS = ['Picking', 'Reserva', 'Recepcion', 'Despacho']

export default function Bodegas() {
  const [bodegas, setBodegas] = useState([])
  const [bodega, setBodega] = useState({ codigo: '', nombre: '' })
  const [ubicacion, setUbicacion] = useState({ bodega_id: '', codigo: '', tipo: 'Picking' })
  const [aviso, setAviso] = useState({ texto: '', error: false })
  const [guardando, setGuardando] = useState(false)

  function cargar() {
    return api.get('/bodegas').then(r => setBodegas(r.data))
      .catch(err => setAviso({ texto: mensajeError(err, 'No se pudieron cargar las bodegas'), error: true }))
  }
  useEffect(() => { cargar() }, [])

  async function enviar(e, ruta, datos, exito, limpiar) {
    e.preventDefault(); setGuardando(true); setAviso({ texto: '', error: false })
    try {
      await api.post(ruta, datos)
      await cargar(); limpiar()
      setAviso({ texto: exito, error: false })
    } catch (err) { setAviso({ texto: mensajeError(err, 'No se pudo guardar'), error: true }) }
    finally { setGuardando(false) }
  }

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Bodegas</h1>
        <p className="text-gray-400 text-sm mt-1">{bodegas.length} bodegas registradas</p>
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
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4"
          onSubmit={e => enviar(e, '/bodegas', bodega, 'Bodega creada', () => setBodega({ codigo: '', nombre: '' }))}>
          <h2 className="text-sm font-semibold text-white">Nueva bodega</h2>
          <div>
            <label className={LABEL}>Codigo</label>
            <input required maxLength={20} pattern="[A-Za-z0-9_\-]+" placeholder="NORTE" value={bodega.codigo}
              onChange={e => setBodega({ ...bodega, codigo: e.target.value })} className={INPUT} />
          </div>
          <div>
            <label className={LABEL}>Nombre</label>
            <input required maxLength={120} placeholder="Bodega Norte" value={bodega.nombre}
              onChange={e => setBodega({ ...bodega, nombre: e.target.value })} className={INPUT} />
          </div>
          <button type="submit" disabled={guardando}
            className="bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-6 py-2 rounded-lg transition-colors disabled:opacity-50">
            Crear bodega
          </button>
        </form>

        <form className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4"
          onSubmit={e => enviar(e, '/ubicaciones', { ...ubicacion, bodega_id: parseInt(ubicacion.bodega_id) }, 'Ubicacion creada',
            () => setUbicacion({ ...ubicacion, codigo: '' }))}>
          <h2 className="text-sm font-semibold text-white">Nueva ubicacion</h2>
          <div>
            <label className={LABEL}>Bodega</label>
            <select required value={ubicacion.bodega_id} onChange={e => setUbicacion({ ...ubicacion, bodega_id: e.target.value })} className={INPUT}>
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
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <button type="submit" disabled={guardando}
            className="bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-6 py-2 rounded-lg transition-colors disabled:opacity-50">
            Crear ubicacion
          </button>
        </form>
      </div>
    </div>
  )
}
