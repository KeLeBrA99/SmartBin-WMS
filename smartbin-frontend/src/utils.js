// Escapa texto antes de insertarlo en HTML generado a mano (reportes PDF).
// Sin esto, un producto llamado `<img src=x onerror=...>` ejecutaria codigo
// en el navegador de quien abra el reporte (XSS almacenado).
export function escapeHtml(valor) {
  return String(valor ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// Convierte cualquier error de Axios en un texto que React pueda mostrar.
// FastAPI devuelve `detail` como texto en los errores propios y como una
// LISTA de objetos en los errores de validacion (422); pintar esa lista
// directamente hacia fallar el render.
export function mensajeError(err, porDefecto = 'Ocurrio un error') {
  if (!err?.response) return 'No se pudo conectar con el servidor'
  const detail = err.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const textos = detail.map(d => String(d?.msg ?? '').replace(/^Value error, /, '')).filter(Boolean)
    if (textos.length) return textos.join('. ')
  }
  return porDefecto
}

// Abre el reporte en una pestana nueva; avisa si el navegador la bloquea.
export function abrirReporte(html) {
  const ventana = window.open('', '_blank')
  if (!ventana) {
    alert('El navegador bloqueo la ventana del reporte. Permite las ventanas emergentes para este sitio.')
    return
  }
  ventana.document.write(html)
  ventana.document.close()
}
