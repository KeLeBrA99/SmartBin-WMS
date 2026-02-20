import { useState, useEffect } from 'react'
import api from '../api'

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ usuario: '', password: '', nombre: '', rol: 'operario' })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/usuarios').then(r => setUsuarios(r.data))
  }, [])

  async function handleSubmit(e) {
    e.preventDefault(); setSaving(true); setMsg('')
    try {
      await api.post('/usuarios', form)
      const { data } = await api.get('/usuarios')
      setUsuarios(data); setMsg('Usuario creado exitosamente')
      setShowForm(false); setForm({ usuario: '', password: '', nombre: '', rol: 'operario' })
    } catch (err) { setMsg(err.response?.data?.detail || 'Error al crear usuario') }
    finally { setSaving(false) }
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Usuarios</h1>
          <p className="text-gray-400 text-sm mt-1">{usuarios.length} usuarios registrados</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="text-sm bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-4 py-2 rounded-lg transition-colors">
          {showForm ? '✕ Cancelar' : '+ Nuevo Usuario'}
        </button>
      </div>

      {msg && <p className={`text-sm px-4 py-2 rounded-lg border ${msg.includes('Error') ? 'text-red-400 bg-red-400/10 border-red-400/20' : 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'}`}>{msg}</p>}

      {showForm && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Nuevo Usuario</h2>
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { key: 'nombre', label: 'Nombre Completo', placeholder: 'Jose Salamanca' },
              { key: 'usuario', label: 'Usuario', placeholder: 'jsalamanca' },
              { key: 'password', label: 'Contrasena', placeholder: '••••••••', type: 'password' },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">{f.label}</label>
                <input type={f.type || 'text'} placeholder={f.placeholder} value={form[f.key]}
                  onChange={e => setForm({...form, [f.key]: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">Rol</label>
              <select value={form.rol} onChange={e => setForm({...form, rol: e.target.value})}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500">
                <option value="operario">Operario</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="flex items-end sm:col-span-2">
              <button type="submit" disabled={saving}
                className="bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-6 py-2 rounded-lg transition-colors disabled:opacity-50">
                {saving ? 'Guardando...' : 'Crear Usuario'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['Nombre','Usuario','Rol','Creado'].map(h => (
                <th key={h} className="text-left text-xs text-gray-400 uppercase tracking-wider px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {usuarios.map(u => (
              <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 text-sm text-white">{u.nombre}</td>
                <td className="px-4 py-3 font-mono text-sm text-gray-300">{u.usuario}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-1 rounded-full ${u.rol === 'admin' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-blue-500/15 text-blue-400'}`}>
                    {u.rol}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{u.created_at ? new Date(u.created_at).toLocaleDateString('es-CO') : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
