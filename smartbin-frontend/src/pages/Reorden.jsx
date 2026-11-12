import { useState, useEffect } from 'react'
import api from '../api'
import { mensajeError } from '../utils'

export default function Reorden() {
  const [filas, setFilas] = useState([])
  const [bodegas, setBodegas] = useState([])
  const [bodegaId, setBodegaId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => { api.get('/bodegas').then(r => setBodegas(r.data)).catch(() => {}) }, [])

  useEffect(() => {
    api.get('/reorden', { params: bodegaId ? { bodega_id: bodegaId } : {} })
      .then(r => { setFilas(r.data); setError('') })
      .catch(err => setError(mensajeError(err, 'No se pudo calcular el reorden')))
      .finally(() => setLoading(false))
  }, [bodegaId])

  const urgentes = filas.filter(f => f.requiere_reorden).length

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Puntos de reorden</h1>
          <p className="text-gray-400 text-sm mt-1">
            {urgentes > 0 ? `${urgentes} producto(s) por reabastecer` : 'Calculado con las salidas de los ultimos 180 dias'}
          </p>
        </div>
        <select value={bodegaId} onChange={e => setBodegaId(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500">
          <option value="">Todas las bodegas</option>
          {bodegas.map(b => <option key={b.id} value={b.id}>{b.codigo}</option>)}
        </select>
      </div>

      {error && <p className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2">{error}</p>}

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['Bodega', 'Producto', 'Stock', 'Demanda / dia', 'Stock seguridad', 'Punto de reorden', 'Cobertura', 'Pedir', 'Estado'].map(h => (
                <th key={h} className="text-left text-xs text-gray-400 uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map(f => (
              <tr key={`${f.bodega_id}-${f.producto_id}`} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-gray-300">{f.bodega}</td>
                <td className="px-4 py-3">
                  <p className="text-sm text-white">{f.producto}</p>
                  <p className="font-mono text-xs text-emerald-400">{f.sku}</p>
                </td>
                <td className={`px-4 py-3 text-sm font-bold ${f.requiere_reorden ? 'text-red-400' : 'text-white'}`}>{f.stock}</td>
                <td className="px-4 py-3 text-sm text-gray-300">{f.demanda_diaria}</td>
                <td className="px-4 py-3 text-sm text-gray-300">{f.stock_seguridad}</td>
                <td className="px-4 py-3 text-sm text-white font-semibold">{f.punto_reorden}</td>
                <td className="px-4 py-3 text-sm text-gray-300 whitespace-nowrap">{f.dias_cobertura === null ? '-' : `${f.dias_cobertura} dias`}</td>
                <td className="px-4 py-3 text-sm font-bold text-white">{f.cantidad_sugerida || '-'}</td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={`text-xs px-2 py-1 rounded-full ${f.requiere_reorden ? 'bg-red-500/15 text-red-400' : 'bg-emerald-500/15 text-emerald-400'}`}>
                    {f.requiere_reorden ? 'Reabastecer' : 'Suficiente'}
                  </span>
                  {f.baja_confianza && (
                    <span className="ml-2 text-xs text-yellow-400" title={`Solo ${f.dias_historia} dias de historia`}>⚠ poca historia</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && filas.length === 0 && (
          <div className="text-center py-8 text-gray-500 text-sm">
            Aun no hay salidas registradas. Registra salidas en Movimientos para calcular el reorden.
          </div>
        )}
      </div>

      <p className="text-xs text-gray-500">
        Punto de reorden = demanda diaria × lead time + stock de seguridad. La demanda pondera mas las salidas recientes
        y cuenta los dias sin salidas como cero. Con menos de 28 dias de historia el resultado es orientativo.
      </p>
    </div>
  )
}
