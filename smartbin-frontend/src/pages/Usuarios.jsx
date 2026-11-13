import { useState, useEffect } from 'react'
import api from '../api'
import { mensajeError } from '../utils'
import { useAuth } from '../context/AuthContext'

const VACIO = { usuario: '', password: '', nombre: '', rol: 'operario' }

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(VACIO)
  const [editando, setEditando] = useState(null)
  const { user } = useAuth()
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [esError, setEsError] = useState(false)

  useEffect(() => {
    api.get('/usuarios').then(r => setUsuarios(r.data))
      .catch(err => { setEsError(true); setMsg(mensajeError(err, 'No se pudieron cargar los usuarios')) })
  }, [])

  async function handleSubmit(e) {
    e.preventDefault(); setSaving(true); setMsg(''); setEsError(false)
    try {
      if (editando) {
        await api.put(`/usuarios/${editando.id}`, { nombre: form.nombre, rol: form.rol, password: form.password || null })
      } else {
        await api.post('/usuarios', form)
      }
      const { data } = await api.get('/usuarios')
      setUsuarios(data); setMsg(editando ? 'Usuario actualizado' : 'Usuario creado exitosamente')
      cerrarForm()
    } catch (err) { setEsError(true); setMsg(mensajeError(err, 'Error al guardar el usuario')) }
    finally { setSaving(false) }
  }

  function cerrarForm() { setShowForm(false); setEditando(null); setForm(VACIO) }

  function abrirEditar(u) {
    setEditando(u); setForm({ usuario: u.usuario, password: '', nombre: u.nombre, rol: u.rol })
    setShowForm(true); setMsg('')
  }

  async function eliminar(u) {
    if (!window.confirm(`¿Eliminar al usuario ${u.usuario}? Esta accion no se puede deshacer.`)) return
    setMsg(''); setEsError(false)
    try {
      await api.delete(`/usuarios/${u.id}`)
      const { data } = await api.get('/usuarios')
      setUsuarios(data); setMsg('Usuario eliminado')
      if (editando?.id === u.id) cerrarForm()
    } catch (err) { setEsError(true); setMsg(mensajeError(err, 'Error al eliminar el usuario')) }
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Usuarios</h1>
          <p className="text-gray-400 text-sm mt-1">{usuarios.length} usuarios registrados</p>
        </div>
        <button onClick={() => showForm ? cerrarForm() : setShowForm(true)}
          className="text-sm bg-emerald-500 hover:bg-emerald-400 text-gray-950 font-semibold px-4 py-2 rounded-lg transition-colors">
          {showForm ? '✕ Cancelar' : '+ Nuevo Usuario'}
        </button>
      </div>

      {msg && <p className={`text-sm px-4 py-2 rounded-lg border ${esError ? 'text-red-400 bg-red-400/10 border-red-400/20' : 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'}`}>{msg}</p>}

      {showForm && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">{editando ? `Editar usuario ${editando.usuario}` : 'Nuevo Usuario'}</h2>
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { key: 'nombre', label: 'Nombre Completo', placeholder: 'Jose Salamanca' },
              { key: 'usuario', label: 'Usuario', placeholder: 'jsalamanca', disabled: !!editando },
              { key: 'password', label: editando ? 'Nueva contrasena (vacia = no cambiar)' : 'Contrasena (min. 8 caracteres)', placeholder: '••••••••', type: 'password', minLength: 8, opcional: !!editando },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1.5">{f.label}</label>
                <input type={f.type || 'text'} placeholder={f.placeholder} value={form[f.key]} required={!f.opcional} minLength={f.minLength} disabled={f.disabled}
                  onChange={e => setForm({...form, [f.key]: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-emerald-500 disabled:opacity-60"
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
                {saving ? 'Guardando...' : editando ? 'Guardar cambios' : 'Crear Usuario'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              {['Nombre','Usuario','Rol','Creado','Acciones'].map(h => (
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
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => abrirEditar(u)}
                      className="text-xs bg-blue-500/15 hover:bg-blue-500/25 text-blue-400 border border-blue-500/30 px-3 py-1.5 rounded-lg transition-colors">
                      ✏️ Editar
                    </button>
                    {u.usuario !== user?.usuario && (
                      <button onClick={() => eliminar(u)}
                        className="text-xs bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-lg transition-colors">
                        🗑️ Eliminar
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
