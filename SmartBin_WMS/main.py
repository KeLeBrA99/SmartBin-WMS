import datetime
import logging
import random
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from typing import Callable, Literal, Optional, TypeVar

import jwt
import mysql.connector
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

import reorden
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
    la conexion se cierra siempre.
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
    """Se niega a arrancar si la base no esta al dia.

    Sin el indice UNIQUE (ubicacion_id, producto_id) el upsert de inventario
    crearia filas duplicadas y los descuentos se aplicarian varias veces.
    """
    pendiente = "La base de datos no esta al dia ({}). Ejecuta: python preparar_bd.py"
    with transaccion() as cur:
        cur.execute(
            """
            SELECT GROUP_CONCAT(column_name ORDER BY column_name) AS columnas
            FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'inventario' AND non_unique = 0
            GROUP BY index_name
            """
        )
        if not any(f["columnas"] == "producto_id,ubicacion_id" for f in cur.fetchall()):
            raise RuntimeError(pendiente.format("falta el indice unico de inventario"))

        cur.execute(
            """
            SELECT table_name AS tabla, column_name AS columna, character_maximum_length AS largo
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND ((table_name = 'usuarios' AND column_name = 'password')
                OR (table_name = 'ubicaciones' AND column_name = 'bodega_id')
                OR (table_name = 'productos' AND column_name = 'lead_time_dias')
                OR (table_name = 'movimientos' AND column_name = 'operacion_id'))
            """
        )
        columnas = {(f["tabla"].lower(), f["columna"].lower()): f["largo"] for f in cur.fetchall()}
        for tabla, columna in [("ubicaciones", "bodega_id"), ("productos", "lead_time_dias"), ("movimientos", "operacion_id")]:
            if (tabla, columna) not in columnas:
                raise RuntimeError(pendiente.format(f"falta {tabla}.{columna}"))
        if (columnas.get(("usuarios", "password")) or 0) < 128:
            raise RuntimeError(pendiente.format("usuarios.password es muy corta para el hash nuevo"))


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
        return JSONResponse(status_code=409, content={"detail": "Ya existe un registro con ese valor (codigo, SKU o usuario repetido)"})
    if exc.errno in ER_FK:
        return JSONResponse(status_code=400, content={"detail": "Referencia invalida: la categoria, bodega, producto o ubicacion no existe, o esta en uso"})
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


class UsuarioEditar(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    rol: Literal["admin", "operario"]
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)  # None = no cambiarla


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


class MovimientoStock(BaseModel):
    """Entrada (recepcion) o salida (despacho) en una ubicacion."""
    producto_id: int
    ubicacion_id: int
    cantidad: int = Field(gt=0)
    referencia: Optional[str] = Field(default=None, max_length=80)


class BodegaNueva(BaseModel):
    codigo: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    nombre: str = Field(min_length=1, max_length=120)


class UbicacionEditar(BaseModel):
    codigo: str = Field(min_length=1, max_length=40)
    tipo: str = Field(min_length=1, max_length=30)


class UbicacionNueva(BaseModel):
    bodega_id: int
    codigo: str = Field(min_length=1, max_length=40)
    tipo: str = Field(min_length=1, max_length=30)


# ── AUTH HELPERS ─────────────────────────────────────────
def crear_token(uid, usuario, rol):
    return jwt.encode({
        "id": uid, "usuario": usuario, "rol": rol,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_HORAS),
    }, SECRET_KEY, algorithm="HS256")


def get_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        datos = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalido")
    # El rol se lee de la base en cada peticion: si a alguien lo eliminan o le
    # cambian el rol, su token deja de servir de inmediato, no 8 horas despues.
    with transaccion() as cur:
        cur.execute("SELECT usuario, rol FROM usuarios WHERE id=%s", (datos.get("id"),))
        fila = cur.fetchone()
    if not fila:
        raise HTTPException(401, "El usuario ya no existe")
    return {**datos, "usuario": fila["usuario"], "rol": fila["rol"]}


def solo_admin(user=Depends(get_user)):
    if user.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores")
    return user


# Limite de intentos de login contra fuerza bruta: 5 fallos en 15 minutos por
# (IP, usuario). Vive en memoria: sirve para un solo proceso; con varios
# workers habria que moverlo a Redis o a la base de datos.
LOGIN_MAX_FALLOS = 5
LOGIN_VENTANA_SEG = 15 * 60
_fallos_login: dict[tuple[str, str], deque] = defaultdict(deque)
_fallos_lock = threading.Lock()


def _segundos_bloqueado(clave) -> int:
    ahora = time.monotonic()
    with _fallos_lock:
        fallos = _fallos_login[clave]
        while fallos and ahora - fallos[0] > LOGIN_VENTANA_SEG:
            fallos.popleft()
        if len(fallos) >= LOGIN_MAX_FALLOS:
            return int(LOGIN_VENTANA_SEG - (ahora - fallos[0])) + 1
        if not fallos:
            del _fallos_login[clave]
    return 0


# ── MOVIMIENTOS DE STOCK (nucleo) ────────────────────────
def _descontar(cur, producto_id: int, ubicacion_id: int, cantidad: int, mensaje: str):
    """Comprueba y descuenta en UNA sentencia: no hay ventana entre leer el
    saldo y escribirlo en la que otra peticion pueda colarse."""
    cur.execute(
        "UPDATE inventario SET cantidad = cantidad - %s "
        "WHERE producto_id=%s AND ubicacion_id=%s AND cantidad >= %s",
        (cantidad, producto_id, ubicacion_id, cantidad),
    )
    if cur.rowcount == 0:
        raise HTTPException(400, mensaje)


def _sumar(cur, producto_id: int, ubicacion_id: int, cantidad: int):
    cur.execute(
        "INSERT INTO inventario (producto_id, ubicacion_id, cantidad) VALUES (%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE cantidad = cantidad + %s",
        (producto_id, ubicacion_id, cantidad, cantidad),
    )


def _registrar(cur, *, operacion: str, tipo: str, producto_id: int, ubicacion_id: int,
               delta: int, usuario_id: int, referencia: Optional[str] = None):
    """Escribe el movimiento en el libro mayor, en la misma transaccion."""
    cur.execute(
        "SELECT u.bodega_id, COALESCE(i.cantidad, 0) AS saldo FROM ubicaciones u "
        "LEFT JOIN inventario i ON i.ubicacion_id = u.id AND i.producto_id = %s WHERE u.id = %s",
        (producto_id, ubicacion_id),
    )
    fila = cur.fetchone()
    cur.execute(
        "INSERT INTO movimientos (operacion_id, tipo, bodega_id, ubicacion_id, producto_id, delta, saldo, usuario_id, referencia) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (operacion, tipo, fila["bodega_id"], ubicacion_id, producto_id, delta, fila["saldo"], usuario_id, referencia),
    )


def _limpiar_ceros(cur, producto_id: int):
    """No dejar filas en cero: la ubicacion vuelve a mostrarse vacia."""
    cur.execute("DELETE FROM inventario WHERE producto_id=%s AND cantidad=0", (producto_id,))


def _exigir(cur, tabla: str, id_: int, mensaje: str):
    cur.execute(f"SELECT 1 FROM {tabla} WHERE id=%s", (id_,))
    if not cur.fetchone():
        raise HTTPException(404, mensaje)


# ── RUTAS BASE ───────────────────────────────────────────
@app.get("/")
def home():
    return {"mensaje": "SmartBin WMS Activo"}


# ── RUTAS AUTH ───────────────────────────────────────────
@app.post("/login")
def login(data: LoginData, request: Request):
    clave = (request.client.host if request.client else "?", data.usuario.strip().lower())
    espera = _segundos_bloqueado(clave)
    if espera:
        raise HTTPException(
            429, f"Demasiados intentos fallidos. Intenta de nuevo en {espera // 60 + 1} minutos",
            headers={"Retry-After": str(espera)},
        )

    with transaccion() as cur:
        cur.execute("SELECT id, usuario, password, nombre, rol FROM usuarios WHERE usuario=%s", (data.usuario,))
        user = cur.fetchone()
    if not user or not verificar(data.password, user["password"]):
        with _fallos_lock:
            _fallos_login[clave].append(time.monotonic())
        raise HTTPException(401, "Usuario o contrasena incorrectos")
    with _fallos_lock:
        _fallos_login.pop(clave, None)

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


def _exigir_otro_admin(cur, usuario_id: int):
    """Impide dejar el sistema sin ningun administrador."""
    cur.execute("SELECT COUNT(*) AS n FROM usuarios WHERE rol='admin' AND id<>%s", (usuario_id,))
    if cur.fetchone()["n"] == 0:
        raise HTTPException(409, "Debe quedar al menos un administrador")


@app.put("/usuarios/{usuario_id}")
def editar_usuario(usuario_id: int, data: UsuarioEditar, user=Depends(solo_admin)):
    with transaccion() as cur:
        cur.execute("SELECT rol FROM usuarios WHERE id=%s FOR UPDATE", (usuario_id,))
        actual = cur.fetchone()
        if not actual:
            raise HTTPException(404, "Usuario no encontrado")
        if actual["rol"] == "admin" and data.rol != "admin":
            _exigir_otro_admin(cur, usuario_id)
        cur.execute("UPDATE usuarios SET nombre=%s, rol=%s WHERE id=%s", (data.nombre, data.rol, usuario_id))
        if data.password:
            cur.execute("UPDATE usuarios SET password=%s WHERE id=%s", (hash_password(data.password), usuario_id))
    return {"mensaje": "Usuario actualizado"}


@app.delete("/usuarios/{usuario_id}")
def eliminar_usuario(usuario_id: int, user=Depends(solo_admin)):
    if usuario_id == user["id"]:
        raise HTTPException(400, "No puedes eliminar tu propio usuario")
    with transaccion() as cur:
        cur.execute("SELECT rol FROM usuarios WHERE id=%s FOR UPDATE", (usuario_id,))
        actual = cur.fetchone()
        if not actual:
            raise HTTPException(404, "Usuario no encontrado")
        if actual["rol"] == "admin":
            _exigir_otro_admin(cur, usuario_id)
        # El historial conserva sus movimientos (sin nombre de usuario).
        cur.execute("DELETE FROM usuarios WHERE id=%s", (usuario_id,))
    return {"mensaje": "Usuario eliminado"}


# ── BODEGAS Y UBICACIONES ────────────────────────────────
@app.get("/bodegas")
def ver_bodegas(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("""
            SELECT b.id, b.codigo, b.nombre,
                   COUNT(DISTINCT u.id) AS ubicaciones,
                   COALESCE(SUM(i.cantidad), 0) AS unidades
            FROM bodegas b
            LEFT JOIN ubicaciones u ON u.bodega_id = b.id
            LEFT JOIN inventario i ON i.ubicacion_id = u.id
            GROUP BY b.id, b.codigo, b.nombre
            ORDER BY b.id
        """)
        return cur.fetchall()


@app.post("/bodegas")
def crear_bodega(data: BodegaNueva, user=Depends(solo_admin)):
    with transaccion() as cur:
        cur.execute("INSERT INTO bodegas (codigo, nombre) VALUES (%s,%s)", (data.codigo.upper(), data.nombre))
        return {"id": cur.lastrowid, "mensaje": "Bodega creada"}


@app.put("/bodegas/{bodega_id}")
def editar_bodega(bodega_id: int, data: BodegaNueva, user=Depends(solo_admin)):
    with transaccion() as cur:
        _exigir(cur, "bodegas", bodega_id, "La bodega no existe")
        cur.execute("UPDATE bodegas SET codigo=%s, nombre=%s WHERE id=%s", (data.codigo.upper(), data.nombre, bodega_id))
    return {"mensaje": "Bodega actualizada"}


@app.delete("/bodegas/{bodega_id}")
def eliminar_bodega(bodega_id: int, user=Depends(solo_admin)):
    """Elimina la bodega y sus ubicaciones, solo si no queda stock en ella."""
    with transaccion() as cur:
        _exigir(cur, "bodegas", bodega_id, "La bodega no existe")
        cur.execute("SELECT COUNT(*) AS n FROM bodegas")
        if cur.fetchone()["n"] <= 1:
            raise HTTPException(409, "Debe existir al menos una bodega")
        cur.execute(
            "SELECT COALESCE(SUM(i.cantidad), 0) AS unidades FROM ubicaciones u "
            "JOIN inventario i ON i.ubicacion_id = u.id WHERE u.bodega_id=%s FOR UPDATE", (bodega_id,))
        if cur.fetchone()["unidades"] > 0:
            raise HTTPException(409, "La bodega aun tiene stock. Transfierelo o dale salida antes de eliminarla")
        cur.execute("DELETE i FROM inventario i JOIN ubicaciones u ON u.id = i.ubicacion_id WHERE u.bodega_id=%s", (bodega_id,))
        cur.execute("DELETE FROM ubicaciones WHERE bodega_id=%s", (bodega_id,))
        cur.execute("DELETE FROM bodegas WHERE id=%s", (bodega_id,))
    return {"mensaje": "Bodega eliminada"}


@app.get("/ubicaciones")
def ver_ubicaciones(bodega_id: Optional[int] = None, user=Depends(get_user)):
    """Una fila por (ubicacion, producto); las ubicaciones vacias salen una vez."""
    with transaccion() as cur:
        cur.execute("""
            SELECT u.id, u.codigo, u.tipo, u.bodega_id, b.codigo AS bodega,
                   COALESCE(i.cantidad, 0) AS cantidad,
                   COALESCE(p.nombre, 'Vacio') AS producto,
                   p.id AS producto_id,
                   COALESCE(p.stock_minimo, 5) AS stock_minimo
            FROM ubicaciones u
            JOIN bodegas b ON b.id = u.bodega_id
            LEFT JOIN inventario i ON u.id = i.ubicacion_id
            LEFT JOIN productos p ON i.producto_id = p.id
            WHERE (%s IS NULL OR u.bodega_id = %s)
            ORDER BY b.id, u.codigo, p.nombre
        """, (bodega_id, bodega_id))
        return cur.fetchall()


@app.post("/ubicaciones")
def crear_ubicacion(data: UbicacionNueva, user=Depends(solo_admin)):
    with transaccion() as cur:
        _exigir(cur, "bodegas", data.bodega_id, "La bodega no existe")
        cur.execute("INSERT INTO ubicaciones (bodega_id, codigo, tipo) VALUES (%s,%s,%s)",
                    (data.bodega_id, data.codigo.upper(), data.tipo))
        return {"id": cur.lastrowid, "mensaje": "Ubicacion creada"}


@app.put("/ubicaciones/{ubicacion_id}")
def editar_ubicacion(ubicacion_id: int, data: UbicacionEditar, user=Depends(solo_admin)):
    with transaccion() as cur:
        _exigir(cur, "ubicaciones", ubicacion_id, "La ubicacion no existe")
        cur.execute("UPDATE ubicaciones SET codigo=%s, tipo=%s WHERE id=%s", (data.codigo.upper(), data.tipo, ubicacion_id))
    return {"mensaje": "Ubicacion actualizada"}


@app.delete("/ubicaciones/{ubicacion_id}")
def eliminar_ubicacion(ubicacion_id: int, user=Depends(solo_admin)):
    with transaccion() as cur:
        _exigir(cur, "ubicaciones", ubicacion_id, "La ubicacion no existe")
        cur.execute("SELECT COALESCE(SUM(cantidad), 0) AS unidades FROM inventario WHERE ubicacion_id=%s FOR UPDATE", (ubicacion_id,))
        if cur.fetchone()["unidades"] > 0:
            raise HTTPException(409, "La ubicacion aun tiene stock. Transfierelo o dale salida antes de eliminarla")
        cur.execute("DELETE FROM inventario WHERE ubicacion_id=%s", (ubicacion_id,))
        cur.execute("DELETE FROM ubicaciones WHERE id=%s", (ubicacion_id,))
    return {"mensaje": "Ubicacion eliminada"}


# ── PRODUCTOS ────────────────────────────────────────────
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
        _exigir(cur, "productos", producto_id, "Producto no encontrado")
        cur.execute("""
            UPDATE productos SET sku=%s, nombre=%s, categoria_id=%s, precio_compra=%s, stock_minimo=%s
            WHERE id=%s
        """, (producto.sku, producto.nombre, producto.categoria_id, producto.precio, producto.stock_minimo, producto_id))
    return {"mensaje": "Producto actualizado"}


@app.delete("/productos/{producto_id}")
def eliminar_producto(producto_id: int, user=Depends(solo_admin)):
    with transaccion() as cur:
        _exigir(cur, "productos", producto_id, "Producto no encontrado")
        cur.execute("SELECT COALESCE(SUM(cantidad), 0) AS unidades FROM inventario WHERE producto_id=%s FOR UPDATE", (producto_id,))
        if cur.fetchone()["unidades"] > 0:
            raise HTTPException(409, "El producto aun tiene stock. Dale salida o ajustalo a 0 antes de eliminarlo")
        cur.execute("DELETE FROM inventario WHERE producto_id=%s", (producto_id,))
        # Sus movimientos se conservan en el historial.
        cur.execute("DELETE FROM productos WHERE id=%s", (producto_id,))
    return {"mensaje": "Producto eliminado"}


@app.patch("/productos/{producto_id}/stock")
def ajustar_stock(producto_id: int, ajuste: AjusteStock, user=Depends(solo_admin)):
    """Deja el stock TOTAL del producto en `cantidad` (correccion por conteo).

    Se aplica la diferencia: si sobra, se suma a la primera ubicacion; si
    falta, se descuenta ubicacion por ubicacion. Las filas quedan bloqueadas
    (FOR UPDATE) para que una transferencia simultanea no descuadre el calculo.
    """
    def trabajo():
        operacion = str(uuid.uuid4())
        with transaccion() as cur:
            _exigir(cur, "productos", producto_id, "Producto no encontrado")
            cur.execute(
                "SELECT ubicacion_id, cantidad FROM inventario "
                "WHERE producto_id=%s ORDER BY ubicacion_id FOR UPDATE",
                (producto_id,),
            )
            filas = cur.fetchall()
            diferencia = ajuste.cantidad - sum(f["cantidad"] for f in filas)
            cambios = []   # (ubicacion_id, delta)

            if diferencia > 0:
                if filas:
                    destino = filas[0]["ubicacion_id"]
                else:
                    cur.execute("SELECT id FROM ubicaciones ORDER BY id LIMIT 1")
                    ubi = cur.fetchone()
                    if not ubi:
                        raise HTTPException(400, "No hay ubicaciones creadas para guardar el stock")
                    destino = ubi["id"]
                _sumar(cur, producto_id, destino, diferencia)
                cambios.append((destino, diferencia))
            elif diferencia < 0:
                restante = -diferencia
                for f in filas:
                    quitar = min(f["cantidad"], restante)
                    if quitar:
                        cur.execute(
                            "UPDATE inventario SET cantidad = cantidad - %s WHERE producto_id=%s AND ubicacion_id=%s",
                            (quitar, producto_id, f["ubicacion_id"]),
                        )
                        cambios.append((f["ubicacion_id"], -quitar))
                        restante -= quitar

            for ubicacion_id, delta in cambios:
                _registrar(cur, operacion=operacion, tipo="AJUSTE", producto_id=producto_id,
                           ubicacion_id=ubicacion_id, delta=delta, usuario_id=user["id"],
                           referencia="Ajuste de stock total")
            _limpiar_ceros(cur, producto_id)
        return {"mensaje": "Stock actualizado", "stock_total": ajuste.cantidad}

    return con_reintento(trabajo)


@app.get("/categorias")
def ver_categorias(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("SELECT * FROM categorias")
        return cur.fetchall()


# ── ENTRADAS, SALIDAS Y TRANSFERENCIAS ───────────────────
@app.post("/entradas")
def registrar_entrada(mov: MovimientoStock, user=Depends(get_user)):
    """Recepcion de mercancia en una ubicacion."""
    def trabajo():
        with transaccion() as cur:
            _exigir(cur, "productos", mov.producto_id, "Producto no encontrado")
            _exigir(cur, "ubicaciones", mov.ubicacion_id, "La ubicacion no existe")
            _sumar(cur, mov.producto_id, mov.ubicacion_id, mov.cantidad)
            _registrar(cur, operacion=str(uuid.uuid4()), tipo="ENTRADA", producto_id=mov.producto_id,
                       ubicacion_id=mov.ubicacion_id, delta=mov.cantidad, usuario_id=user["id"],
                       referencia=mov.referencia)
        return {"mensaje": "Entrada registrada"}

    return con_reintento(trabajo)


@app.post("/salidas")
def registrar_salida(mov: MovimientoStock, user=Depends(get_user)):
    """Despacho desde una ubicacion. Es la demanda que alimenta el reorden."""
    def trabajo():
        with transaccion() as cur:
            _descontar(cur, mov.producto_id, mov.ubicacion_id, mov.cantidad,
                       "Stock insuficiente en la ubicacion")
            _registrar(cur, operacion=str(uuid.uuid4()), tipo="SALIDA", producto_id=mov.producto_id,
                       ubicacion_id=mov.ubicacion_id, delta=-mov.cantidad, usuario_id=user["id"],
                       referencia=mov.referencia)
            _limpiar_ceros(cur, mov.producto_id)
        return {"mensaje": "Salida registrada"}

    return con_reintento(trabajo)


@app.post("/transferencias")
def transferir(transf: Transferencia, user=Depends(get_user)):
    """Mueve stock entre dos ubicaciones, de la misma bodega o de bodegas distintas.

    El descuento es atomico, el destino se actualiza con un upsert y las dos
    filas se tocan siempre en orden ascendente de ubicacion, para que dos
    transferencias cruzadas (A->B y B->A) no se bloqueen entre si.
    """
    def trabajo():
        operacion = str(uuid.uuid4())
        with transaccion() as cur:
            _exigir(cur, "ubicaciones", transf.destino_id, "La ubicacion de destino no existe")

            pasos = [
                (transf.origen_id, lambda: _descontar(cur, transf.producto_id, transf.origen_id,
                                                      transf.cantidad, "Stock insuficiente en origen")),
                (transf.destino_id, lambda: _sumar(cur, transf.producto_id, transf.destino_id, transf.cantidad)),
            ]
            for _, paso in sorted(pasos, key=lambda p: p[0]):
                paso()   # si el descuento falla, el ROLLBACK deshace la suma

            for ubicacion_id, delta in ((transf.origen_id, -transf.cantidad), (transf.destino_id, transf.cantidad)):
                _registrar(cur, operacion=operacion, tipo="TRANSFERENCIA", producto_id=transf.producto_id,
                           ubicacion_id=ubicacion_id, delta=delta, usuario_id=user["id"])
            _limpiar_ceros(cur, transf.producto_id)
        return {"mensaje": "Transferencia exitosa"}

    return con_reintento(trabajo)


@app.get("/movimientos")
def ver_movimientos(
    tipo: Optional[Literal["ENTRADA", "SALIDA", "TRANSFERENCIA", "AJUSTE"]] = None,
    producto_id: Optional[int] = None,
    bodega_id: Optional[int] = None,
    limite: int = Query(100, ge=1, le=500),
    user=Depends(get_user),
):
    """Historial de movimientos, del mas reciente al mas antiguo."""
    with transaccion() as cur:
        cur.execute("""
            SELECT m.id, m.operacion_id, m.tipo, m.delta, m.saldo, m.referencia, m.created_at,
                   m.producto_id, p.sku, p.nombre AS producto,
                   u.codigo AS ubicacion, m.bodega_id, b.codigo AS bodega,
                   us.nombre AS usuario
            FROM movimientos m
            LEFT JOIN productos p ON p.id = m.producto_id
            LEFT JOIN ubicaciones u ON u.id = m.ubicacion_id
            LEFT JOIN bodegas b ON b.id = m.bodega_id
            LEFT JOIN usuarios us ON us.id = m.usuario_id
            WHERE (%s IS NULL OR m.tipo = %s)
              AND (%s IS NULL OR m.producto_id = %s)
              AND (%s IS NULL OR m.bodega_id = %s)
            ORDER BY m.id DESC
            LIMIT %s
        """, (tipo, tipo, producto_id, producto_id, bodega_id, bodega_id, limite))
        return cur.fetchall()


# ── ANALITICA ────────────────────────────────────────────
@app.get("/reorden")
def puntos_de_reorden(
    bodega_id: Optional[int] = None,
    dias: int = Query(180, ge=7, le=730),
    user=Depends(get_user),
):
    """Punto de reorden por bodega y producto segun las salidas historicas."""
    hoy = datetime.date.today()
    desde = hoy - datetime.timedelta(days=dias)
    with transaccion() as cur:
        cur.execute("""
            SELECT bodega_id, producto_id, DATE(created_at) AS dia, -SUM(delta) AS cantidad
            FROM movimientos
            WHERE tipo = 'SALIDA' AND created_at >= %s
              AND (%s IS NULL OR bodega_id = %s)
            GROUP BY bodega_id, producto_id, DATE(created_at)
        """, (desde, bodega_id, bodega_id))
        ventas: dict[tuple[int, int], dict] = defaultdict(dict)
        for f in cur.fetchall():
            ventas[(f["bodega_id"], f["producto_id"])][f["dia"]] = float(f["cantidad"])

        cur.execute("""
            SELECT u.bodega_id, i.producto_id, SUM(i.cantidad) AS stock
            FROM inventario i JOIN ubicaciones u ON u.id = i.ubicacion_id
            GROUP BY u.bodega_id, i.producto_id
        """)
        stock = {(f["bodega_id"], f["producto_id"]): float(f["stock"]) for f in cur.fetchall()}

        cur.execute("SELECT id, sku, nombre, lead_time_dias, nivel_servicio FROM productos")
        productos = {f["id"]: f for f in cur.fetchall()}
        cur.execute("SELECT id, codigo FROM bodegas")
        bodegas = {f["id"]: f["codigo"] for f in cur.fetchall()}

    resultado = []
    for (b_id, p_id), por_dia in ventas.items():
        p = productos.get(p_id)
        if not p:
            continue
        existencias = stock.get((b_id, p_id), 0.0)
        calculo = reorden.calcular(
            reorden.serie_diaria(por_dia, hoy),
            lead_time_dias=float(p["lead_time_dias"]),
            nivel_servicio=float(p["nivel_servicio"]),
            stock=existencias,
        )
        resultado.append({
            "bodega_id": b_id, "bodega": bodegas.get(b_id, "?"),
            "producto_id": p_id, "sku": p["sku"], "producto": p["nombre"],
            "stock": int(existencias), "lead_time_dias": float(p["lead_time_dias"]),
            **calculo,
        })
    # Primero lo urgente: lo que requiere reorden y menos cobertura tiene.
    resultado.sort(key=lambda r: (not r["requiere_reorden"], r["dias_cobertura"] if r["dias_cobertura"] is not None else 1e9))
    return resultado


@app.get("/dashboard")
def dashboard(user=Depends(get_user)):
    with transaccion() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM productos")
        total_productos = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM ubicaciones")
        total_ubicaciones = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM usuarios")
        total_usuarios = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM bodegas")
        total_bodegas = cur.fetchone()["total"]
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
        "total_bodegas": total_bodegas,
        "alertas_stock": alertas,
        "stock_por_categoria": por_categoria,
    }
