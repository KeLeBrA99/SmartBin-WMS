import { useEffect, useState } from 'react'

function App() {
  const [ubicaciones, setUbicaciones] = useState([])
  
  // 1. Estado para Entrada (Verde)
  const [formEntrada, setFormEntrada] = useState({ producto_id: '', ubicacion_id: '', cantidad: '' })
  
  // 2. Estado para Movimiento (Naranja)
  const [formMover, setFormMover] = useState({ origen_id: '', destino_id: '', producto_id: '', cantidad: '' })

  // 3. NUEVO: Estado para Salida (Rojo)
  const [formSalida, setFormSalida] = useState({ producto_id: '', ubicacion_id: '', cantidad: '' })

  const cargarMapa = () => {
    fetch('http://127.0.0.1:8000/ubicaciones')
      .then(response => response.json())
      .then(data => setUbicaciones(data))
      .catch(error => console.error('Error:', error))
  }

  useEffect(() => { cargarMapa() }, [])

  // --- LÓGICA DE ENTRADA ---
  const manejarEntrada = async (e) => {
    e.preventDefault()
    const response = await fetch('http://127.0.0.1:8000/inventario/entrada', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        producto_id: parseInt(formEntrada.producto_id),
        ubicacion_id: parseInt(formEntrada.ubicacion_id),
        cantidad: parseInt(formEntrada.cantidad)
      })
    })
    if (response.ok) {
      alert("✅ Mercancía Ingresada")
      cargarMapa()
      setFormEntrada({ producto_id: '', ubicacion_id: '', cantidad: '' })
    }
  }

  // --- LÓGICA DE MOVIMIENTO ---
  const manejarMovimiento = async (e) => {
    e.preventDefault()
    const response = await fetch('http://127.0.0.1:8000/inventario/mover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen_id: parseInt(formMover.origen_id),
        destino_id: parseInt(formMover.destino_id),
        producto_id: parseInt(formMover.producto_id),
        cantidad: parseInt(formMover.cantidad)
      })
    })
    const data = await response.json()
    if (response.ok && !data.detail) {
      alert("🚚 Movimiento exitoso")
      cargarMapa()
      setFormMover({ origen_id: '', destino_id: '', producto_id: '', cantidad: '' })
    } else {
      alert("❌ Error: " + (data.detail || data.error))
    }
  }

  // --- NUEVO: LÓGICA DE SALIDA (DESPACHO) ---
  const manejarSalida = async (e) => {
    e.preventDefault()
    const response = await fetch('http://127.0.0.1:8000/inventario/salida', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        producto_id: parseInt(formSalida.producto_id),
        ubicacion_id: parseInt(formSalida.ubicacion_id),
        cantidad: parseInt(formSalida.cantidad)
      })
    })
    const data = await response.json()
    
    if (data.error) {
      alert("⚠️ " + data.error) // Muestra error si falta stock
    } else {
      alert("📤 Despacho Exitoso. " + data.mensaje)
      cargarMapa()
      setFormSalida({ producto_id: '', ubicacion_id: '', cantidad: '' })
    }
  }

  // Manejadores de inputs
  const handleEntradaChange = (e) => setFormEntrada({...formEntrada, [e.target.name]: e.target.value})
  const handleMoverChange = (e) => setFormMover({...formMover, [e.target.name]: e.target.value})
  const handleSalidaChange = (e) => setFormSalida({...formSalida, [e.target.name]: e.target.value})

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif', maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center', color: '#2c3e50' }}>📦 SmartBin WMS <span style={{fontSize:'0.5em', color:'#7f8c8d'}}>v1.0</span></h1>

    
     {/* --- ZONA DE CONTROL (3 COLUMNAS FIJAS) --- */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr 1fr', // <--- CAMBIO AQUÍ: 3 columnas de igual tamaño (fracción 1)
        gap: '20px', 
        marginBottom: '30px' 
      }}>
        
        {/* ... Aquí adentro siguen tus 3 bloques (Verde, Naranja, Rojo) igual que antes ... */}
        {/* ... No necesitas borrar el contenido de adentro, solo cambiar el style del div padre ... */}
        
        {/* 1. ENTRADA (VERDE) */}
        <div style={{ backgroundColor: '#eafaf1', padding: '20px', borderRadius: '10px', border: '1px solid #a9dfbf', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#196f3d' }}>📥 Inbound (Proveedor)</h3>
          <form onSubmit={manejarEntrada} style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
            <input type="number" name="producto_id" placeholder="ID Producto" value={formEntrada.producto_id} onChange={handleEntradaChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <input type="number" name="ubicacion_id" placeholder="ID Ubicación Destino" value={formEntrada.ubicacion_id} onChange={handleEntradaChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <input type="number" name="cantidad" placeholder="Cantidad" value={formEntrada.cantidad} onChange={handleEntradaChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <button type="submit" style={{ marginTop: 'auto', backgroundColor: '#27ae60', color: 'white', padding: '12px', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight:'bold' }}>INGRESAR STOCK</button>
          </form>
        </div>

        {/* 2. MOVER (NARANJA) */}
        <div style={{ backgroundColor: '#fef5e7', padding: '20px', borderRadius: '10px', border: '1px solid #fad7a0', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#d35400' }}>🚚 Transferencia Interna</h3>
          <form onSubmit={manejarMovimiento} style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
            <input type="number" name="producto_id" placeholder="ID Producto" value={formMover.producto_id} onChange={handleMoverChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            
            {/* Fila doble ajustada */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '5px', alignItems: 'center' }}>
              <input type="number" name="origen_id" placeholder="Desde" value={formMover.origen_id} onChange={handleMoverChange} required style={{padding: '10px', width: '100%', border:'1px solid #ccc', borderRadius:'4px', boxSizing: 'border-box'}} />
              <span style={{fontSize: '1.2em', color: '#e67e22'}}>➜</span>
              <input type="number" name="destino_id" placeholder="Hacia" value={formMover.destino_id} onChange={handleMoverChange} required style={{padding: '10px', width: '100%', border:'1px solid #ccc', borderRadius:'4px', boxSizing: 'border-box'}} />
            </div>

            <input type="number" name="cantidad" placeholder="Cantidad" value={formMover.cantidad} onChange={handleMoverChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <button type="submit" style={{ marginTop: 'auto', backgroundColor: '#e67e22', color: 'white', padding: '12px', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight:'bold' }}>MOVER STOCK</button>
          </form>
        </div>

        {/* 3. SALIDA (ROJO) */}
        <div style={{ backgroundColor: '#fadbd8', padding: '20px', borderRadius: '10px', border: '1px solid #f1948a', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#922b21' }}>📤 Outbound (Despacho)</h3>
          <form onSubmit={manejarSalida} style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
            <input type="number" name="producto_id" placeholder="ID Producto" value={formSalida.producto_id} onChange={handleSalidaChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <input type="number" name="ubicacion_id" placeholder="ID Ubicación Origen" value={formSalida.ubicacion_id} onChange={handleSalidaChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <input type="number" name="cantidad" placeholder="Cantidad a Sacar" value={formSalida.cantidad} onChange={handleSalidaChange} required style={{padding: '10px', border:'1px solid #ccc', borderRadius:'4px'}} />
            <button type="submit" style={{ marginTop: 'auto', backgroundColor: '#c0392b', color: 'white', padding: '12px', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight:'bold' }}>DESPACHAR PEDIDO</button>
          </form>
        </div>

      </div>
      {/* --- MAPA --- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '15px' }}>
        {ubicaciones.map((ubi) => (
          <div key={ubi.id} style={{ 
            border: ubi.cantidad ? '2px solid #27ae60' : '2px solid #bdc3c7',
            borderRadius: '10px', padding: '15px',
            backgroundColor: ubi.cantidad ? '#fff' : '#f4f6f7',
            position: 'relative', overflow: 'hidden',
            boxShadow: '0 3px 6px rgba(0,0,0,0.1)'
          }}>
            <div style={{position: 'absolute', top: 0, right: 0, background: '#34495e', color: 'white', fontSize: '0.7em', padding: '2px 6px', borderBottomLeftRadius: '5px'}}>ID: {ubi.id}</div>
            
            <h3 style={{ margin: '0 0 5px 0', color: '#2c3e50' }}>{ubi.codigo}</h3>
            {ubi.cantidad ? (
              <div style={{ color: '#145a32' }}>
                <strong style={{ fontSize: '1.2em' }}>{ubi.cantidad} Unid.</strong>
                <p style={{ margin: '5px 0 0 0', fontSize: '0.9em' }}>📦 {ubi.producto}</p>
              </div>
            ) : ( <p style={{ color: '#95a5a6', fontStyle: 'italic', fontSize: '0.9em' }}>Vacío</p> )}
            
            <div style={{fontSize: '0.7em', color: '#999', marginTop: '10px'}}>Zona: {ubi.tipo}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default App