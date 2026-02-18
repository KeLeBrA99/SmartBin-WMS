from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # <--- 1. IMPORTAR ESTO
from pydantic import BaseModel
import mysql.connector

app = FastAPI()

# <--- 2. AGREGAR ESTE BLOQUE DE PERMISOS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" significa que permite conexiones de cualquier lado (útil para desarrollo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de BD
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "1234",
    "database": "smartbin_wms"
}

# --- MODELOS DE DATOS (Las reglas) ---
# Esto define qué datos necesitamos para crear un producto
class ProductoNuevo(BaseModel):
    sku: str
    nombre: str
    categoria_id: int
    precio: float

# --- RUTAS ---

@app.get("/")
def home():
    return {"mensaje": "Sistema WMS Activo 🟢"}

@app.get("/ubicaciones")
def ver_ubicaciones():
    try:
        conexion = mysql.connector.connect(**db_config)
        cursor = conexion.cursor(dictionary=True)
        
        # SQL AVANZADO: Unimos Ubicaciones + Inventario + Productos
        sql = """
            SELECT u.id, u.codigo, u.tipo, 
                   i.cantidad, 
                   p.nombre as producto
            FROM ubicaciones u
            LEFT JOIN inventario i ON u.id = i.ubicacion_id
            LEFT JOIN productos p ON i.producto_id = p.id
        """
        
        cursor.execute(sql)
        datos = cursor.fetchall()
        
        cursor.close()
        conexion.close()
        return datos
    except Exception as e:
        return {"error": str(e)}

# NUEVA RUTA: Crear Producto (POST)
@app.post("/productos")
def crear_producto(producto: ProductoNuevo):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # SQL para insertar
        sql = "INSERT INTO productos (sku, nombre, categoria_id, precio_compra) VALUES (%s, %s, %s, %s)"
        valores = (producto.sku, producto.nombre, producto.categoria_id, producto.precio)
        
        cursor.execute(sql, valores)
        conn.commit()
        
        nuevo_id = cursor.lastrowid # Recuperamos el ID generado
        conn.close()
        
        return {"mensaje": "Producto creado ✅", "id": nuevo_id, "producto": producto}
        
    except Exception as e:
        return {"error": str(e)}
    # --- MODELO PARA MOVER INVENTARIO ---
class MovimientoStock(BaseModel):
    producto_id: int
    ubicacion_id: int  # ¿En qué estante lo vas a poner?
    cantidad: int

# --- RUTA: Ingresar Mercancía (Inbound) ---
@app.post("/inventario/entrada")
def entrada_mercancia(movimiento: MovimientoStock):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 1. Verificar si ya existe ese producto en esa ubicación
        check_sql = "SELECT cantidad FROM inventario WHERE producto_id = %s AND ubicacion_id = %s"
        cursor.execute(check_sql, (movimiento.producto_id, movimiento.ubicacion_id))
        resultado = cursor.fetchone()

        if resultado:
            # Si ya existe, SUMAMOS la cantidad (Update)
            nueva_cantidad = resultado[0] + movimiento.cantidad
            update_sql = "UPDATE inventario SET cantidad = %s WHERE producto_id = %s AND ubicacion_id = %s"
            cursor.execute(update_sql, (nueva_cantidad, movimiento.producto_id, movimiento.ubicacion_id))
            mensaje = "Stock actualizado (sumado) 🔄"
        else:
            # Si no existe, CREAMOS el registro (Insert)
            insert_sql = "INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s, %s, %s)"
            cursor.execute(insert_sql, (movimiento.producto_id, movimiento.ubicacion_id, movimiento.cantidad))
            mensaje = "Nuevo stock registrado en ubicación 📦"

        conn.commit()
        conn.close()
        
        return {"mensaje": mensaje, "datos": movimiento}

    except Exception as e:
        return {"error": str(e)}
    # --- RUTA: Sacar Mercancía (Picking / Outbound) ---
@app.post("/inventario/salida")
def salida_mercancia(movimiento: MovimientoStock):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 1. Consultar cuánto hay ACTUALMENTE
        check_sql = "SELECT cantidad FROM inventario WHERE producto_id = %s AND ubicacion_id = %s"
        cursor.execute(check_sql, (movimiento.producto_id, movimiento.ubicacion_id))
        resultado = cursor.fetchone()

        # Validación 1: ¿Existe el producto ahí?
        if not resultado:
            conn.close()
            return {"error": "❌ No se encontró ese producto en esa ubicación."}
        
        stock_actual = resultado[0]

        # Validación 2: ¿Hay suficiente cantidad?
        if stock_actual < movimiento.cantidad:
            conn.close()
            return {
                "error": "⚠️ Stock insuficiente", 
                "disponible": stock_actual, 
                "solicitado": movimiento.cantidad
            }

        # 2. Si pasa las pruebas, restamos
        nuevo_stock = stock_actual - movimiento.cantidad
        
        if nuevo_stock == 0:
            # Opción A: Si queda en 0, borramos el registro para que no ocupe espacio
            update_sql = "DELETE FROM inventario WHERE producto_id = %s AND ubicacion_id = %s"
            cursor.execute(update_sql, (movimiento.producto_id, movimiento.ubicacion_id))
            mensaje = "Producto agotado en esta ubicación (Fila eliminada) 🗑️"
        else:
            # Opción B: Actualizamos la resta
            update_sql = "UPDATE inventario SET cantidad = %s WHERE producto_id = %s AND ubicacion_id = %s"
            cursor.execute(update_sql, (nuevo_stock, movimiento.producto_id, movimiento.ubicacion_id))
            mensaje = f"Salida exitosa. Quedan {nuevo_stock} unidades 📉"

        conn.commit()
        conn.close()
        
        return {"mensaje": mensaje, "datos": movimiento}

    except Exception as e:
        return {"error": str(e)}
    # --- MODELO PARA MOVER ENTRE UBICACIONES ---
class Transferencia(BaseModel):
    origen_id: int    # Desde dónde sale (ej: A-01)
    destino_id: int   # A dónde va (ej: Z-99)
    producto_id: int
    cantidad: int

# --- RUTA: Reubicación (Transferencia Interna) ---
@app.post("/inventario/mover")
def mover_interno(transf: Transferencia):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 1. VERIFICAR SI HAY STOCK EN EL ORIGEN
        check_sql = "SELECT cantidad FROM inventario WHERE producto_id = %s AND ubicacion_id = %s"
        cursor.execute(check_sql, (transf.producto_id, transf.origen_id))
        origen = cursor.fetchone()

        if not origen or origen[0] < transf.cantidad:
            conn.close()
            # Retornamos error 400 (Bad Request)
            raise HTTPException(status_code=400, detail="❌ Stock insuficiente en el origen")

        # 2. RESTAR DEL ORIGEN (Outbound interno)
        nuevo_stock_origen = origen[0] - transf.cantidad
        if nuevo_stock_origen == 0:
            cursor.execute("DELETE FROM inventario WHERE producto_id = %s AND ubicacion_id = %s", 
                           (transf.producto_id, transf.origen_id))
        else:
            cursor.execute("UPDATE inventario SET cantidad = %s WHERE producto_id = %s AND ubicacion_id = %s", 
                           (nuevo_stock_origen, transf.producto_id, transf.origen_id))

        # 3. SUMAR AL DESTINO (Inbound interno)
        # Revisamos si ya existe en el destino
        cursor.execute(check_sql, (transf.producto_id, transf.destino_id))
        destino = cursor.fetchone()

        if destino:
            # Si ya existe, sumamos
            cursor.execute("UPDATE inventario SET cantidad = cantidad + %s WHERE producto_id = %s AND ubicacion_id = %s", 
                           (transf.cantidad, transf.producto_id, transf.destino_id))
        else:
            # Si no existe, creamos
            cursor.execute("INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s, %s, %s)", 
                           (transf.producto_id, transf.destino_id, transf.cantidad))

        conn.commit()
        conn.close()
        
        return {"mensaje": "Reubicación exitosa 🚚💨"}

    except Exception as e:
        return {"error": str(e)}