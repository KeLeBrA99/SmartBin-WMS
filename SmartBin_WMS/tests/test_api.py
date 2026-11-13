"""Pruebas de integracion contra una base de datos REAL de pruebas.

Requieren un MySQL/MariaDB accesible y un `.env` (o variables de entorno)
que apunte a una base VACIA dedicada a pruebas: las tablas se borran y se
vuelven a crear en cada ejecucion. Por seguridad solo corren si el nombre de
la base termina en `_test`.

    DB_NAME=smartbin_wms_test pytest
"""
import sys
import threading
from pathlib import Path

import mysql.connector
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from config import DB_CONFIG  # noqa: E402

if not DB_CONFIG["database"].endswith("_test"):
    pytest.skip("DB_NAME debe terminar en _test para correr estas pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from security import hash_password, necesita_actualizar, verificar  # noqa: E402

ESQUEMA = (RAIZ.parent / "database" / "schema.sql").read_text(encoding="utf-8")
TABLAS = ["inventario", "movimientos", "productos", "categorias", "ubicaciones", "bodegas", "usuarios"]
SHA256_ADMIN123 = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"


def sql(sentencia, params=()):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sentencia, params)
        filas = cur.fetchall() if cur.with_rows else None
        conn.commit()
        return filas
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def base_limpia():
    for tabla in TABLAS:
        sql(f"DROP TABLE IF EXISTS {tabla}")
    for sentencia in ESQUEMA.split(";"):
        cuerpo = "\n".join(l for l in sentencia.splitlines() if not l.strip().startswith("--")).strip()
        if cuerpo:
            sql(cuerpo)
    # Hash rapido solo para las pruebas (el real usa 600.000 iteraciones)
    sql("INSERT INTO usuarios (usuario,password,nombre,rol) VALUES (%s,%s,'Admin','admin'),(%s,%s,'Op','operario')",
        ("admin", hash_password("admin123", iteraciones=1000), "op", hash_password("operario123", iteraciones=1000)))
    sql("INSERT INTO categorias (id,nombre) VALUES (1,'General')")
    sql("INSERT INTO bodegas (id,codigo,nombre) VALUES (1,'PRINCIPAL','Principal'),(2,'NORTE','Norte')")
    sql("INSERT INTO ubicaciones (id,bodega_id,codigo,tipo) VALUES (1,1,'A-01','Picking'),(2,1,'A-02','Picking'),(3,2,'A-01','Reserva')")
    main._fallos_login.clear()
    sql("INSERT INTO productos (id,sku,nombre,categoria_id,precio_compra,stock_minimo) VALUES (1,'SKU-1','Taladro',1,150.50,5)")
    sql("INSERT INTO inventario (ubicacion_id,producto_id,cantidad) VALUES (1,1,100)")


@pytest.fixture
def api():
    with TestClient(main.app) as cliente:
        yield cliente


def token(api, usuario="admin", clave="admin123"):
    r = api.post("/login", json={"usuario": usuario, "password": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def stock(ubicacion):
    filas = sql("SELECT cantidad FROM inventario WHERE ubicacion_id=%s AND producto_id=1", (ubicacion,))
    return filas[0]["cantidad"] if filas else 0


def transferir(api, h, origen, destino, cantidad):
    return api.post("/transferencias", headers=h,
                    json={"producto_id": 1, "origen_id": origen, "destino_id": destino, "cantidad": cantidad})


# ── Seguridad ────────────────────────────────────────────
def test_hash_y_verificacion():
    h = hash_password("secreta-123", iteraciones=1000)
    assert h != hash_password("secreta-123", iteraciones=1000)  # sal distinta cada vez
    assert verificar("secreta-123", h) and not verificar("otra", h)
    assert verificar("admin123", SHA256_ADMIN123) and necesita_actualizar(SHA256_ADMIN123)
    assert not verificar("x", "") and not verificar("x", "basura$sin$formato")


def test_login_migra_hash_antiguo(api):
    sql("UPDATE usuarios SET password=%s WHERE usuario='admin'", (SHA256_ADMIN123,))
    token(api)
    nuevo = sql("SELECT password FROM usuarios WHERE usuario='admin'")[0]["password"]
    assert nuevo.startswith("pbkdf2_sha256$")
    token(api)  # y sigue entrando con el hash nuevo


def test_login_incorrecto_y_rutas_protegidas(api):
    assert api.post("/login", json={"usuario": "admin", "password": "mala"}).status_code == 401
    assert api.post("/login", json={"usuario": "nadie", "password": "x"}).status_code == 401
    assert api.get("/productos").status_code in (401, 403)
    assert api.get("/productos", headers={"Authorization": "Bearer falso"}).status_code == 401
    assert api.get("/usuarios", headers=token(api, "op", "operario123")).status_code == 403


def test_validacion_de_usuarios(api):
    h = token(api)
    base = {"usuario": "nuevo", "password": "clave-segura", "nombre": "Nuevo", "rol": "operario"}
    assert api.post("/usuarios", headers=h, json={**base, "rol": "superadmin"}).status_code == 422
    assert api.post("/usuarios", headers=h, json={**base, "password": "123"}).status_code == 422
    assert api.post("/usuarios", headers=h, json=base).status_code == 200
    assert api.post("/usuarios", headers=h, json=base).status_code == 409  # repetido
    token(api, "nuevo", "clave-segura")


# ── Productos ────────────────────────────────────────────
def test_productos_devuelve_precio_y_sku_repetido(api):
    h = token(api)
    p = api.get("/productos", headers=h).json()[0]
    assert float(p["precio_compra"]) == 150.5 and int(p["stock_total"]) == 100
    nuevo = {"sku": "SKU-1", "nombre": "Otro", "categoria_id": 1, "precio": 10}
    assert api.post("/productos", headers=h, json=nuevo).status_code == 409
    assert api.post("/productos", headers=h, json={**nuevo, "sku": "SKU-2", "categoria_id": 999}).status_code == 400
    assert api.post("/productos", headers=h, json={**nuevo, "sku": "SKU-2", "precio": -1}).status_code == 422
    assert api.put("/productos/999", headers=h, json={**nuevo, "stock_minimo": 1}).status_code == 404


# ── Transferencias ───────────────────────────────────────
def test_transferencia_basica(api):
    h = token(api)
    assert transferir(api, h, 1, 2, 30).status_code == 200
    assert (stock(1), stock(2)) == (70, 30)
    assert transferir(api, h, 2, 1, 30).status_code == 200  # destino con id menor
    assert (stock(1), stock(2)) == (100, 0)
    assert sql("SELECT COUNT(*) AS n FROM inventario")[0]["n"] == 1  # sin filas en cero


def test_transferencia_rechaza_entradas_invalidas(api):
    h = token(api)
    assert transferir(api, h, 1, 2, -5).status_code == 422   # antes "robaba" stock al reves
    assert transferir(api, h, 1, 2, 0).status_code == 422
    assert transferir(api, h, 1, 1, 5).status_code == 422
    assert transferir(api, h, 1, 2, 101).status_code == 400
    assert transferir(api, h, 3, 2, 1).status_code == 400    # origen sin stock
    assert transferir(api, h, 1, 999, 1).status_code == 404
    assert transferir(api, h, 2, 1, 5).status_code == 400    # falla tras tocar el destino: rollback
    assert (stock(1), stock(2)) == (100, 0)


def test_transferencias_concurrentes_no_sobrevenden(api):
    """40 hilos piden 5 unidades de un saldo de 100: exactamente 20 pasan."""
    h = token(api)
    codigos, barrera = [], threading.Barrier(40)

    def pedir():
        barrera.wait()
        codigos.append(transferir(api, h, 1, 2, 5).status_code)

    hilos = [threading.Thread(target=pedir) for _ in range(40)]
    [t.start() for t in hilos]
    [t.join() for t in hilos]

    assert codigos.count(200) == 20 and codigos.count(400) == 20, codigos
    assert (stock(1), stock(2)) == (0, 100)


def test_transferencias_cruzadas_conservan_el_total(api):
    """A->B y B->A a la vez: sin deadlocks sin resolver y sin perder unidades."""
    h = token(api)
    transferir(api, h, 1, 2, 50)
    codigos, barrera = [], threading.Barrier(30)

    def pedir(i):
        barrera.wait()
        origen, destino = (1, 2) if i % 2 else (2, 1)
        codigos.append(transferir(api, h, origen, destino, 3).status_code)

    hilos = [threading.Thread(target=pedir, args=(i,)) for i in range(30)]
    [t.start() for t in hilos]
    [t.join() for t in hilos]

    assert set(codigos) <= {200, 400}, codigos
    assert stock(1) + stock(2) == 100


# ── Ajuste de stock ──────────────────────────────────────
def test_ajuste_deja_el_total_pedido(api):
    h = token(api)
    transferir(api, h, 1, 2, 40)                      # 60 en A-01, 40 en A-02
    ajustar = lambda n: api.patch("/productos/1/stock", headers=h, json={"cantidad": n})
    assert ajustar(120).status_code == 200 and stock(1) + stock(2) == 120
    assert ajustar(30).status_code == 200 and stock(1) + stock(2) == 30
    assert ajustar(0).status_code == 200 and sql("SELECT COUNT(*) AS n FROM inventario")[0]["n"] == 0
    assert ajustar(7).status_code == 200 and stock(1) == 7   # sin filas: va a la primera ubicacion
    assert ajustar(-1).status_code == 422
    assert api.patch("/productos/999/stock", headers=h, json={"cantidad": 1}).status_code == 404
    assert api.patch("/productos/1/stock", headers=token(api, "op", "operario123"), json={"cantidad": 1}).status_code == 403


# ── Bodegas, entradas, salidas e historial ───────────────
def movimientos(**filtro):
    donde = " AND ".join(f"{k}=%s" for k in filtro) or "1=1"
    return sql(f"SELECT tipo, bodega_id, ubicacion_id, delta, saldo, operacion_id, usuario_id FROM movimientos WHERE {donde} ORDER BY id", tuple(filtro.values()))


def test_bodegas_y_ubicaciones(api):
    h, op = token(api), token(api, "op", "operario123")
    assert api.post("/bodegas", headers=op, json={"codigo": "SUR", "nombre": "Sur"}).status_code == 403
    r = api.post("/bodegas", headers=h, json={"codigo": "sur", "nombre": "Bodega Sur"})
    assert r.status_code == 200
    sur = r.json()["id"]
    assert api.post("/bodegas", headers=h, json={"codigo": "SUR", "nombre": "Otra"}).status_code == 409
    # el mismo codigo de ubicacion puede existir en otra bodega, no en la misma
    nueva = {"bodega_id": sur, "codigo": "A-01", "tipo": "Picking"}
    assert api.post("/ubicaciones", headers=h, json=nueva).status_code == 200
    assert api.post("/ubicaciones", headers=h, json=nueva).status_code == 409
    assert api.post("/ubicaciones", headers=h, json={**nueva, "bodega_id": 999}).status_code == 404
    bodegas = {b["codigo"]: b for b in api.get("/bodegas", headers=h).json()}
    assert int(bodegas["PRINCIPAL"]["unidades"]) == 100 and bodegas["SUR"]["ubicaciones"] == 1
    assert {u["bodega"] for u in api.get("/ubicaciones", headers=h, params={"bodega_id": 2}).json()} == {"NORTE"}


def test_entradas_salidas_y_libro_mayor(api):
    h = token(api)
    mov = lambda ruta, ubi, n: api.post(ruta, headers=h, json={"producto_id": 1, "ubicacion_id": ubi, "cantidad": n, "referencia": "REM-1"})
    assert mov("/entradas", 3, 50).status_code == 200 and stock(3) == 50
    assert mov("/salidas", 3, 20).status_code == 200 and stock(3) == 30
    assert mov("/salidas", 3, 31).status_code == 400 and stock(3) == 30
    assert mov("/salidas", 3, 0).status_code == 422
    assert mov("/entradas", 999, 1).status_code == 404
    assert transferir(api, h, 1, 3, 10).status_code == 200          # entre bodegas
    assert api.patch("/productos/1/stock", headers=h, json={"cantidad": 125}).status_code == 200

    filas = movimientos()
    assert [(f["tipo"], f["bodega_id"], f["delta"], f["saldo"]) for f in filas] == [
        ("ENTRADA", 2, 50, 50), ("SALIDA", 2, -20, 30),
        ("TRANSFERENCIA", 1, -10, 90), ("TRANSFERENCIA", 2, 10, 40),
        ("AJUSTE", 1, -5, 85),
    ]
    assert filas[2]["operacion_id"] == filas[3]["operacion_id"] and filas[0]["usuario_id"] is not None
    # El libro mayor cuadra con el saldo: stock inicial + suma de deltas
    assert 100 + sum(f["delta"] for f in filas) == stock(1) + stock(2) + stock(3) == 125

    historial = api.get("/movimientos", headers=h, params={"tipo": "SALIDA"}).json()
    assert len(historial) == 1 and historial[0]["bodega"] == "NORTE" and historial[0]["usuario"] == "Admin"
    assert len(api.get("/movimientos", headers=h, params={"bodega_id": 1, "limite": 1}).json()) == 1
    assert api.get("/movimientos", headers=h, params={"tipo": "OTRO"}).status_code == 422


def test_salidas_concurrentes_no_sobrevenden(api):
    h = token(api)
    codigos, barrera = [], threading.Barrier(40)

    def pedir():
        barrera.wait()
        codigos.append(api.post("/salidas", headers=h, json={"producto_id": 1, "ubicacion_id": 1, "cantidad": 5}).status_code)

    hilos = [threading.Thread(target=pedir) for _ in range(40)]
    [t.start() for t in hilos]
    [t.join() for t in hilos]
    assert codigos.count(200) == 20 and codigos.count(400) == 20, codigos
    assert stock(1) == 0 and len(movimientos(tipo="SALIDA")) == 20


# ── Reorden ──────────────────────────────────────────────
def test_reorden_desde_salidas_historicas(api):
    import reorden
    # 60 dias vendiendo 10 diarias: demanda 10, sin variabilidad => punto = 10 * 7
    calculo = reorden.calcular([10.0] * 60, lead_time_dias=7, nivel_servicio=0.95, stock=50)
    assert calculo["demanda_diaria"] == 10 and calculo["stock_seguridad"] == 0
    assert calculo["punto_reorden"] == 70 and calculo["requiere_reorden"] and calculo["cantidad_sugerida"] == 90
    assert not reorden.calcular([10.0] * 60, lead_time_dias=7, nivel_servicio=0.95, stock=500)["requiere_reorden"]
    assert reorden.calcular([1.0], lead_time_dias=7, nivel_servicio=0.95)["baja_confianza"]

    h = token(api)
    sql("INSERT INTO movimientos (operacion_id,tipo,bodega_id,ubicacion_id,producto_id,delta,saldo,created_at) "
        "SELECT UUID(),'SALIDA',1,1,1,-10,0, NOW() - INTERVAL n DAY FROM "
        "(SELECT a.n + b.n*10 AS n FROM (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 "
        "UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a, "
        "(SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5) b) dias")
    filas = api.get("/reorden", headers=h).json()
    assert len(filas) == 1
    f = filas[0]
    assert (f["bodega"], f["sku"], f["stock"], f["dias_historia"]) == ("PRINCIPAL", "SKU-1", 100, 60)
    assert f["demanda_diaria"] == 10 and f["punto_reorden"] == 70 and not f["requiere_reorden"]
    assert api.get("/reorden", headers=h, params={"bodega_id": 2}).json() == []


# ── Limite de intentos de login ──────────────────────────
def test_login_se_bloquea_tras_cinco_fallos(api):
    mala = {"usuario": "admin", "password": "incorrecta"}
    assert [api.post("/login", json=mala).status_code for _ in range(5)] == [401] * 5
    r = api.post("/login", json={"usuario": "admin", "password": "admin123"})
    assert r.status_code == 429 and "Retry-After" in r.headers          # ni con la clave correcta
    token(api, "op", "operario123")                                     # otro usuario no se ve afectado
    main._fallos_login.clear()
    token(api)


# ── Editar y eliminar ────────────────────────────────────
def test_editar_y_eliminar_usuarios(api):
    h = token(api)
    op_id = sql("SELECT id FROM usuarios WHERE usuario='op'")[0]["id"]
    admin_id = sql("SELECT id FROM usuarios WHERE usuario='admin'")[0]["id"]
    h_op = token(api, "op", "operario123")

    assert api.put(f"/usuarios/{op_id}", headers=h_op, json={"nombre": "X", "rol": "admin"}).status_code == 403
    # no se puede dejar el sistema sin administrador, ni borrarse a uno mismo
    assert api.put(f"/usuarios/{admin_id}", headers=h, json={"nombre": "Admin", "rol": "operario"}).status_code == 409
    assert api.delete(f"/usuarios/{admin_id}", headers=h).status_code == 400

    assert api.put(f"/usuarios/{op_id}", headers=h, json={"nombre": "Operaria", "rol": "operario", "password": "clave-nueva-1"}).status_code == 200
    assert api.post("/login", json={"usuario": "op", "password": "operario123"}).status_code == 401
    token(api, "op", "clave-nueva-1")
    assert api.put(f"/usuarios/{op_id}", headers=h, json={"nombre": "Operaria", "rol": "operario"}).status_code == 200
    token(api, "op", "clave-nueva-1")                                   # sin password: no cambia

    # el cambio de rol y la eliminacion aplican al token ya emitido
    assert api.get("/usuarios", headers=h_op).status_code == 403
    api.put(f"/usuarios/{op_id}", headers=h, json={"nombre": "Operaria", "rol": "admin"})
    assert api.get("/usuarios", headers=h_op).status_code == 200
    assert api.delete(f"/usuarios/{op_id}", headers=h).status_code == 200
    assert api.get("/productos", headers=h_op).status_code == 401
    assert api.delete(f"/usuarios/{op_id}", headers=h).status_code == 404


def test_editar_y_eliminar_bodegas_ubicaciones_y_productos(api):
    h, op = token(api), token(api, "op", "operario123")
    assert api.delete("/ubicaciones/2", headers=op).status_code == 403

    # con stock no se elimina nada
    assert api.delete("/ubicaciones/1", headers=h).status_code == 409
    assert api.delete("/bodegas/1", headers=h).status_code == 409
    assert api.delete("/productos/1", headers=h).status_code == 409

    assert api.put("/ubicaciones/2", headers=h, json={"codigo": "b-07", "tipo": "Reserva"}).status_code == 200
    assert sql("SELECT codigo, tipo FROM ubicaciones WHERE id=2")[0] == {"codigo": "B-07", "tipo": "Reserva"}
    assert api.put("/ubicaciones/2", headers=h, json={"codigo": "A-01", "tipo": "Reserva"}).status_code == 409  # repetido en la bodega
    assert api.delete("/ubicaciones/2", headers=h).status_code == 200
    assert api.delete("/ubicaciones/2", headers=h).status_code == 404

    assert api.put("/bodegas/2", headers=h, json={"codigo": "sur", "nombre": "Bodega Sur"}).status_code == 200
    assert api.put("/bodegas/2", headers=h, json={"codigo": "PRINCIPAL", "nombre": "x"}).status_code == 409
    assert api.delete("/bodegas/2", headers=h).status_code == 200          # vacia: se va con su ubicacion
    assert sql("SELECT COUNT(*) AS n FROM ubicaciones WHERE bodega_id=2")[0]["n"] == 0

    # producto: se elimina al quedar en 0 y su historial se conserva
    api.patch("/productos/1/stock", headers=h, json={"cantidad": 0})
    assert api.delete("/bodegas/1", headers=h).status_code == 409          # es la unica bodega
    assert api.delete("/productos/1", headers=h).status_code == 200
    assert api.get("/productos", headers=h).json() == []
    assert len(api.get("/movimientos", headers=h).json()) == 1
