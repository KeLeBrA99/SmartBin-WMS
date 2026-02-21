from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import mysql.connector
import hashlib
import jwt
import datetime

app = FastAPI(title="SmartBin WMS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "smartbin_secret_2025"
security = HTTPBearer()

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "1234",
    "database": "smartbin_wms"
}

# ── MODELOS ──────────────────────────────────────────────
class LoginData(BaseModel):
    usuario: str
    password: str

class UsuarioNuevo(BaseModel):
    usuario: str
    password: str
    nombre: str
    rol: str

class ProductoNuevo(BaseModel):
    sku: str
    nombre: str
    categoria_id: int
    precio: float
    stock_minimo: int = 5

class Transferencia(BaseModel):
    producto_id: int
    origen_id: int
    destino_id: int
    cantidad: int

# ── AUTH HELPERS ─────────────────────────────────────────
def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

def crear_token(uid, usuario, rol):
    return jwt.encode({
        "id": uid, "usuario": usuario, "rol": rol,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }, SECRET_KEY, algorithm="HS256")

def get_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except:
        raise HTTPException(401, "Token invalido")

def solo_admin(user=Depends(get_user)):
    if user.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores")
    return user

def get_conn(): return mysql.connector.connect(**db_config)

# ── RUTAS AUTH ───────────────────────────────────────────
@app.get("/")
def home(): return {"mensaje": "SmartBin WMS Activo"}

@app.post("/login")
def login(data: LoginData):
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE usuario=%s AND password=%s",
                    (data.usuario, hash_pw(data.password)))
        user = cur.fetchone()
        conn.close()
        if not user:
            raise HTTPException(401, "Usuario o contrasena incorrectos")
        return {
            "token": crear_token(user["id"], user["usuario"], user["rol"]),
            "usuario": user["usuario"],
            "nombre": user["nombre"],
            "rol": user["rol"]
        }
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/me")
def get_me(user=Depends(get_user)): return user

@app.get("/usuarios")
def listar_usuarios(user=Depends(solo_admin)):
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, usuario, nombre, rol, created_at FROM usuarios")
    result = cur.fetchall(); conn.close(); return result

@app.post("/usuarios")
def crear_usuario(data: UsuarioNuevo, user=Depends(solo_admin)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO usuarios (usuario, password, nombre, rol) VALUES (%s,%s,%s,%s)",
                    (data.usuario, hash_pw(data.password), data.nombre, data.rol))
        conn.commit(); conn.close()
        return {"mensaje": "Usuario creado"}
    except Exception as e: raise HTTPException(500, str(e))

# ── RUTAS INVENTARIO ─────────────────────────────────────
@app.get("/ubicaciones")
def ver_ubicaciones(user=Depends(get_user)):
    try:
        conn = get_conn(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id, u.codigo, u.tipo,
                   COALESCE(i.cantidad, 0) as cantidad,
                   COALESCE(p.nombre, 'Vacio') as producto,
                   COALESCE(p.id, null) as producto_id,
                   COALESCE(pr.stock_minimo, 5) as stock_minimo
            FROM ubicaciones u
            LEFT JOIN inventario i ON u.id = i.ubicacion_id
            LEFT JOIN productos p ON i.producto_id = p.id
            LEFT JOIN productos pr ON i.producto_id = pr.id
        """)
        datos = cur.fetchall(); conn.close(); return datos
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/productos")
def ver_productos(user=Depends(get_user)):
    try:
        conn = get_conn(); cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT p.id, p.sku, p.nombre, c.nombre as categoria,
                   COALESCE(SUM(i.cantidad), 0) as stock_total,
                   p.stock_minimo
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            LEFT JOIN inventario i ON p.id = i.producto_id
            GROUP BY p.id, p.sku, p.nombre, c.nombre, p.stock_minimo
        """)
        datos = cur.fetchall(); conn.close(); return datos
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/productos")
def crear_producto(producto: ProductoNuevo, user=Depends(get_user)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO productos (sku, nombre, categoria_id, precio_compra, stock_minimo) VALUES (%s,%s,%s,%s,%s)",
            (producto.sku, producto.nombre, producto.categoria_id, producto.precio, producto.stock_minimo)
        )
        conn.commit()
        nuevo_id = cur.lastrowid
        conn.close()
        return {"id": nuevo_id, "mensaje": "Producto creado"}
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/categorias")
def ver_categorias(user=Depends(get_user)):
    conn = get_conn(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM categorias")
    datos = cur.fetchall(); conn.close(); return datos

@app.get("/dashboard")
def dashboard(user=Depends(get_user)):
    try:
        conn = get_conn(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) as total FROM productos")
        total_productos = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) as total FROM ubicaciones")
        total_ubicaciones = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) as total FROM usuarios")
        total_usuarios = cur.fetchone()["total"]
        cur.execute("""
            SELECT p.nombre, p.stock_minimo, COALESCE(SUM(i.cantidad),0) as stock_total
            FROM productos p
            LEFT JOIN inventario i ON p.id = i.producto_id
            GROUP BY p.id, p.nombre, p.stock_minimo
            HAVING stock_total <= p.stock_minimo
        """)
        alertas = cur.fetchall()
        cur.execute("""
            SELECT c.nombre as categoria, COALESCE(SUM(i.cantidad),0) as total
            FROM categorias c
            LEFT JOIN productos p ON c.id = p.categoria_id
            LEFT JOIN inventario i ON p.id = i.producto_id
            GROUP BY c.id, c.nombre
        """)
        por_categoria = cur.fetchall()
        conn.close()
        return {
            "total_productos": total_productos,
            "total_ubicaciones": total_ubicaciones,
            "total_usuarios": total_usuarios,
            "alertas_stock": alertas,
            "stock_por_categoria": por_categoria
        }
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/transferencias")
def transferir(transf: Transferencia, user=Depends(get_user)):
    try:
        conn = get_conn(); cur = conn.cursor(dictionary=True)
        check = "SELECT cantidad FROM inventario WHERE producto_id=%s AND ubicacion_id=%s"
        cur.execute(check, (transf.producto_id, transf.origen_id))
        origen = cur.fetchone()
        if not origen or origen["cantidad"] < transf.cantidad:
            raise HTTPException(400, "Stock insuficiente en origen")
        nuevo_stock = origen["cantidad"] - transf.cantidad
        cur.execute("UPDATE inventario SET cantidad=%s WHERE producto_id=%s AND ubicacion_id=%s",
                    (nuevo_stock, transf.producto_id, transf.origen_id))
        cur.execute(check, (transf.producto_id, transf.destino_id))
        destino = cur.fetchone()
        if destino:
            cur.execute("UPDATE inventario SET cantidad=cantidad+%s WHERE producto_id=%s AND ubicacion_id=%s",
                        (transf.cantidad, transf.producto_id, transf.destino_id))
        else:
            cur.execute("INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s,%s,%s)",
                        (transf.producto_id, transf.destino_id, transf.cantidad))
        conn.commit(); conn.close()
        return {"mensaje": "Transferencia exitosa"}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))
    # Agregar estas rutas al main.py despues de POST /productos

class ProductoEditar(BaseModel):
    sku: str
    nombre: str
    categoria_id: int
    precio: float
    stock_minimo: int

class AjusteStock(BaseModel):
    cantidad: int

@app.put("/productos/{producto_id}")
def editar_producto(producto_id: int, producto: ProductoEditar, user=Depends(solo_admin)):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            UPDATE productos SET sku=%s, nombre=%s, categoria_id=%s, precio_compra=%s, stock_minimo=%s
            WHERE id=%s
        """, (producto.sku, producto.nombre, producto.categoria_id, producto.precio, producto.stock_minimo, producto_id))
        conn.commit(); conn.close()
        return {"mensaje": "Producto actualizado"}
    except Exception as e: raise HTTPException(500, str(e))

@app.patch("/productos/{producto_id}/stock")
def ajustar_stock(producto_id: int, ajuste: AjusteStock, user=Depends(solo_admin)):
    try:
        conn = get_conn(); cur = conn.cursor(dictionary=True)
        # Obtener ubicacion principal del producto
        cur.execute("SELECT ubicacion_id FROM inventario WHERE producto_id=%s LIMIT 1", (producto_id,))
        inv = cur.fetchone()
        if inv:
            cur.execute("UPDATE inventario SET cantidad=%s WHERE producto_id=%s AND ubicacion_id=%s",
                        (ajuste.cantidad, producto_id, inv["ubicacion_id"]))
        else:
            # Si no tiene ubicacion, ponerlo en la primera disponible
            cur.execute("SELECT id FROM ubicaciones LIMIT 1")
            ubi = cur.fetchone()
            if ubi:
                cur.execute("INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s,%s,%s)",
                            (producto_id, ubi["id"], ajuste.cantidad))
        conn.commit(); conn.close()
        return {"mensaje": "Stock actualizado"}
    except Exception as e: raise HTTPException(500, str(e))