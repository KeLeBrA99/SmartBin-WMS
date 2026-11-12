import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('sb_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Sesion vencida o token invalido: limpiar y volver al login en vez de
// dejar la pantalla cargando o fallando en silencio.
api.interceptors.response.use(
  respuesta => respuesta,
  error => {
    const esLogin = error.config?.url?.includes('/login')
    if (error.response?.status === 401 && !esLogin) {
      localStorage.removeItem('sb_token')
      localStorage.removeItem('sb_user')
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    return Promise.reject(error)
  }
)

export default api
