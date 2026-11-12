import datetime
import logging
import random
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Callable, Literal, TypeVar

import jwt
import mysql.connector
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

from config import CORS_ORIGINS, DB_CONFIG, SECRET_KEY, TOKEN_HORAS
from security import hash_password, necesita_actualizar, verificar

log = logging.getLogger("smartbin")

# Codigos de error de MySQL / MariaDB que se tratan de forma especifica
ER_DUPLICADO = 1062
ER_FK = (1451, 1452)
ER_CHECK = (3819, 4025)          # CHECK violado (MySQL, MariaDB)
ER_REINTENTABLES = (1213, 1205)  # deadlock, timeout esperando un bloqueo
MAX_INTENTOS = 4

T = TypeVar("T")


# ── BASE DE DATOS ────────────────────────────────────────
@contextmanager
def transaccion():
    """Abre una conexion y entrega un cursor dentro de UNA transaccion.

    COMMIT si el bloque termina bien, ROLLBACK si lanza cualquier error, y
    la conexion se cierra siempre (antes se quedaba abierta si algo fallaba).
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        yield cur
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def con_reintento(trabajo: Callable[[], T]) -> T:
    """Reintenta la transaccion completa si la base la aborta por deadlock."""
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            return trabajo()
        except mysql.connector.Error as exc:
            if exc.errno not in ER_REINTENTABLES or intento == MAX_INTENTOS:
                raise
            time.sleep(0.05 * 2**intento * random.uniform(0.5, 1.5))
    raise RuntimeError("inalcanzable")


def verificar_esquema():
    """Se niega a arrancar si faltan las garantias de las que depende el codigo.

    Sin el indice UNIQUE (ubicacion_id, producto_id) el upsert de inventario
    crearia filas duplicadas y los descuentos se aplicarian varias veces.
    """
    with transaccion() as cur:
        cur.execute(
            """
            SELECT index_name AS indice,
                   GROUP_CONCAT(column_name ORDER BY column_name) AS columnas
            FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'inventario'
              AND non_unique = 0
            GROUP BY index_name
            """
        )
        if not any(f["columnas"] == "producto_id,ubicacion_id" for f in cur.fetchall()):
            raise RuntimeError(
                "La tabla `inventario` no tiene un indice UNIQUE sobre "
                "(ubicacion_id, producto_id). Ejecuta database/migracion_001_integridad.sql"
            )
        cur.execute(
            """
            SELECT character_maximum_length AS largo
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'usuarios'
              AND column_name = 'password'
            """
        )
        col = cur.fetchone()
        if col and col["largo"] is not None and col["largo"] < 128:
            raise RuntimeError(
                "La columna usuarios.password es demasiado corta para el nuevo "
                "hash. Ejecuta database/migracion_001_integridad.sql"
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    verificar_esquema()
    yield


app = FastAPI(title="SmartBin WMS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
security = HTTPBearer()


@app.exception_handler(mysql.connector.Error)
def error_bd(request: Request, exc: mysql.connector.Error):
    """Traduce errores de MySQL sin filtrar detalles internos al cliente."""
    if exc.errno == ER_DUPLICADO:
        return JSONResponse(status_code=409, content={"detail": "Ya existe un registro con ese valor (SKU o usuario repetido)"})
    if exc.errno in ER_FK:
        return JSONResponse(status_code=400, content={"detail": "Referencia invalida: la categoria, producto o ubicacion no existe, o esta en uso"})
    if exc.errno in ER_CHECK:
        return JSONResponse(status_code=409, content={"detail": "La operacion dejaria el stock en negativo"})
    if exc.errno in ER_REINTENTABLES:
        return JSONResponse(status_code=503, content={"detail": "Sistema ocupado, intenta de nuevo"})
    log.exception("Error de base de datos en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno de base de datos"})


# ── MODELOS ──────────────────────────────────────────────
class LoginData(BaseModel):
    usuario: str
    password: str


class UsuarioNuevo(BaseModel):
    usuario: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    nombre: str = Field(min_length=1, max_length=120)
    rol: Literal["admin", "operario"]


class ProductoNuevo(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    nombre: str = Field(min_length=1, max_length=200)
    categoria_id: int
    precio: float = Field(ge=0)
    stock_minimo: int = Field(default=5, ge=0)


class ProductoEditar(ProductoNuevo):
    stock_minimo: int = Field(ge=0)


class AjusteStock(BaseModel):
    cantidad: int = Field(ge=0)


class Transferencia(BaseModel):
    producto_id: int
    origen_id: int
    destino_id: int
    cantidad: int = Field(gt=0)

    @model_validator(mode="after")
    def _distintas(self):
        if self.origen_id == self.destino_id:
            raise ValueError("El origen y el destino deben ser distintos")
        return self


# ── AUTH HELPERS ─────────────────────────────────────────
def crear_token(uid, usuario, rol):
    return jwt.encode({
        "id": uid, "usuario": usuario, "rol": rol,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_HORAS),
    }, SECRET_KEY, algorithm="HS256")


def get_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalido")


def solo_admin(user=Depends(get_user)):
    if user.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores")
    return user


# ── RUTAS BASE ───────────────────────────────────────────
@app.get("/")
def home():
    return {"mensaje": "SmartBin WMS Activo"}


# ── RUTAS AUTH ───────────────────────────────────────────
@app.post("/login")
def login(data: LoginData):
    with transaccion() as cur:
        cur.execute("SELECT id, usuario, password, nombre, rol FROM usuarios WHERE usuario=%s", (data.usuario,))
        user = cur.fetchone()
    if not user or not verificar(data.password, user["password"]):
        raise HTTPException(401, "Usuario o contrasena incorrectos")

    if necesita_actualizar(user["password"]):
        # Migra en caliente las cuentas con el hash antiguo (SHA-256 sin sal).
        try:
            with transaccion() as cur:
                cur.execute("UPDATE usuarios SET password=%s WHERE id=%s",
                            (hash_password(data.password), user["id"]))
        except mysql.connector.Error:
            log.exception("No se pudo actualizar el hash del usuario %s", user["id"])

    return {
        "token": crear_token(user["id"], user["usuario"], user["rol"]),
        "usuario": user["usuario"],
        "nombre": user["nombre"],
        "rol": user["rol"],
    }


@app.get("/me")
def get_me(user=Depends(get_user)):
    return user


@app.get("/usuarios")
def listar_usuarios(user=Depends(solo_admin)):
    with transaccion() as cur:
        cur.execute("SELECT id, usuario, nombre, rol, created_at FROM usuarios")
        return cur.fetchall()


@app.post("/usuarios")
def crear_usuario(data: UsuarioNuevo, user=Depends(solo_admin)):
    with transaccion() as cur:
        cur.execute("INSERT INTO usuarios (usuario, password, nombre, rol) VALUES (%s,%s,%s,%s)",
                    (data.usuario, hash_password(data.password), data.nombre, data.rol))
    return {"mensaje": "Usuario creado"}


# ── RUTAS INVENTARIO ─────────────────────────────────────
@app.get("/ubicaciones")
def ver_ubicaciones(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("""
            SELECT u.id, u.codigo, u.tipo,
                   COALESCE(i.cantidad, 0) AS cantidad,
                   COALESCE(p.nombre, 'Vacio') AS producto,
                   p.id AS producto_id,
                   COALESCE(p.stock_minimo, 5) AS stock_minimo
            FROM ubicaciones u
            LEFT JOIN inventario i ON u.id = i.ubicacion_id
            LEFT JOIN productos p ON i.producto_id = p.id
            ORDER BY u.codigo, p.nombre
        """)
        return cur.fetchall()


@app.get("/productos")
def ver_productos(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("""
            SELECT p.id, p.sku, p.nombre, p.categoria_id, c.nombre AS categoria,
                   p.precio_compra,
                   COALESCE(SUM(i.cantidad), 0) AS stock_total,
                   p.stock_minimo
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            LEFT JOIN inventario i ON p.id = i.producto_id
            GROUP BY p.id, p.sku, p.nombre, p.categoria_id, c.nombre, p.precio_compra, p.stock_minimo
            ORDER BY p.nombre
        """)
        return cur.fetchall()


@app.post("/productos")
def crear_producto(producto: ProductoNuevo, user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute(
            "INSERT INTO productos (sku, nombre, categoria_id, precio_compra, stock_minimo) VALUES (%s,%s,%s,%s,%s)",
            (producto.sku, producto.nombre, producto.categoria_id, producto.precio, producto.stock_minimo),
        )
        return {"id": cur.lastrowid, "mensaje": "Producto creado"}


@app.put("/productos/{producto_id}")
def editar_producto(producto_id: int, producto: ProductoEditar, user=Depends(solo_admin)):
    with transaccion() as cur:
        cur.execute("SELECT 1 FROM productos WHERE id=%s", (producto_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Producto no encontrado")
        cur.execute("""
            UPDATE productos SET sku=%s, nombre=%s, categoria_id=%s, precio_compra=%s, stock_minimo=%s
            WHERE id=%s
        """, (producto.sku, producto.nombre, producto.categoria_id, producto.precio, producto.stock_minimo, producto_id))
    return {"mensaje": "Producto actualizado"}


@app.patch("/productos/{producto_id}/stock")
def ajustar_stock(producto_id: int, ajuste: AjusteStock, user=Depends(solo_admin)):
    """Deja el stock TOTAL del producto en `cantidad`.

    Antes se sobreescribia solo la primera ubicacion, asi que con el producto
    repartido en varias el total no coincidia con lo digitado. Ahora se aplica
    la diferencia: si sobra, se suma a la primera ubicacion; si falta, se
    descuenta ubicacion por ubicacion. Las filas quedan bloqueadas (FOR
    UPDATE) para que una transferencia simultanea no descuadre el calculo.
    """
    def trabajo():
        with transaccion() as cur:
            cur.execute("SELECT 1 FROM productos WHERE id=%s", (producto_id,))
            if not cur.fetchone():
                raise HTTPException(404, "Producto no encontrado")

            cur.execute(
                "SELECT ubicacion_id, cantidad FROM inventario "
                "WHERE producto_id=%s ORDER BY ubicacion_id FOR UPDATE",
                (producto_id,),
            )
            filas = cur.fetchall()
            diferencia = ajuste.cantidad - sum(f["cantidad"] for f in filas)

            if diferencia > 0:
                if filas:
                    destino = filas[0]["ubicacion_id"]
                else:
                    cur.execute("SELECT id FROM ubicaciones ORDER BY id LIMIT 1")
                    ubi = cur.fetchone()
                    if not ubi:
                        raise HTTPException(400, "No hay ubicaciones creadas para guardar el stock")
                    destino = ubi["id"]
                cur.execute(
                    "INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE cantidad = cantidad + %s",
                    (producto_id, destino, diferencia, diferencia),
                )
            elif diferencia < 0:
                restante = -diferencia
                for f in filas:
                    if restante == 0:
                        break
                    quitar = min(f["cantidad"], restante)
                    if quitar:
                        cur.execute(
                            "UPDATE inventario SET cantidad = cantidad - %s "
                            "WHERE producto_id=%s AND ubicacion_id=%s",
                            (quitar, producto_id, f["ubicacion_id"]),
                        )
                        restante -= quitar
                cur.execute("DELETE FROM inventario WHERE producto_id=%s AND cantidad=0", (producto_id,))
        return {"mensaje": "Stock actualizado", "stock_total": ajuste.cantidad}

    return con_reintento(trabajo)


@app.get("/categorias")
def ver_categorias(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("SELECT * FROM categorias")
        return cur.fetchall()


@app.get("/dashboard")
def dashboard(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM productos")
        total_productos = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM ubicaciones")
        total_ubicaciones = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM usuarios")
        total_usuarios = cur.fetchone()["total"]
        cur.execute("""
            SELECT p.nombre, p.stock_minimo, COALESCE(SUM(i.cantidad),0) AS stock_total
            FROM productos p
            LEFT JOIN inventario i ON p.id = i.producto_id
            GROUP BY p.id, p.nombre, p.stock_minimo
            HAVING stock_total <= p.stock_minimo
        """)
        alertas = cur.fetchall()
        cur.execute("""
            SELECT c.nombre AS categoria, COALESCE(SUM(i.cantidad),0) AS total
            FROM categorias c
            LEFT JOIN productos p ON c.id = p.categoria_id
            LEFT JOIN inventario i ON p.id = i.producto_id
            GROUP BY c.id, c.nombre
        """)
        por_categoria = cur.fetchall()
    return {
        "total_productos": total_productos,
        "total_ubicaciones": total_ubicaciones,
        "total_usuarios": total_usuarios,
        "alertas_stock": alertas,
        "stock_por_categoria": por_categoria,
    }


@app.post("/transferencias")
def transferir(transf: Transferencia, user=Depends(get_user)):
    """Mueve stock entre dos ubicaciones sin condiciones de carrera.

    Antes: SELECT cantidad -> restar en Python -> UPDATE cantidad = <valor>.
    Dos peticiones simultaneas leian el mismo saldo y ambas descontaban.

    Ahora la comprobacion y el descuento son UNA sentencia atomica
    (`... SET cantidad = cantidad - N WHERE ... AND cantidad >= N`), el
    destino se actualiza con un upsert, y las dos filas se tocan siempre en
    orden ascendente de ubicacion para que dos transferencias cruzadas
    (A->B y B->A) no se bloqueen entre si.
    """
    def descontar(cur):
        cur.execute(
            "UPDATE inventario SET cantidad = cantidad - %s "
            "WHERE producto_id=%s AND ubicacion_id=%s AND cantidad >= %s",
            (transf.cantidad, transf.producto_id, transf.origen_id, transf.cantidad),
        )
        if cur.rowcount == 0:
            raise HTTPException(400, "Stock insuficiente en origen")

    def sumar(cur):
        cur.execute(
            "INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE cantidad = cantidad + %s",
            (transf.producto_id, transf.destino_id, transf.cantidad, transf.cantidad),
        )

    def trabajo():
        with transaccion() as cur:
            cur.execute("SELECT 1 FROM ubicaciones WHERE id=%s", (transf.destino_id,))
            if not cur.fetchone():
                raise HTTPException(404, "La ubicacion de destino no existe")

            pasos = [(transf.origen_id, descontar), (transf.destino_id, sumar)]
            for _, paso in sorted(pasos, key=lambda p: p[0]):
                paso(cur)   # si `descontar` falla, el ROLLBACK deshace `sumar`

            # No dejar filas en cero: la ubicacion vuelve a mostrarse vacia.
            cur.execute(
                "DELETE FROM inventario WHERE producto_id=%s AND ubicacion_id=%s AND cantidad=0",
                (transf.producto_id, transf.origen_id),
            )
        return {"mensaje": "Transferencia exitosa"}

    return con_reintento(trabajo)
