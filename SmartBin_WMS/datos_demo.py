"""Carga datos de demostracion realistas: dos bodegas, 17 productos y 60 dias
de historial (entradas, salidas y transferencias) para que Inventario,
Movimientos, Reorden y el Dashboard se vean con contenido.

    python datos_demo.py              # solo si aun no hay productos
    python datos_demo.py --reiniciar  # BORRA bodegas, ubicaciones, productos,
                                      # inventario y movimientos, y carga la demo

Los usuarios nunca se tocan. Los datos son simulados (semilla fija: siempre
sale lo mismo) y solo sirven para mostrar el sistema.
"""
import argparse
import datetime
import math
import random
import uuid

import mysql.connector

from config import DB_CONFIG

DIAS = 60
BODEGAS = [("PRINCIPAL", "Bodega Principal"), ("NORTE", "Bodega Norte")]
UBICACIONES = [
    ("A-01-01", "Picking"), ("A-01-02", "Picking"), ("B-01-01", "Picking"),
    ("Z-99-01", "Reserva"), ("Z-99-02", "Reserva"),
    ("REC-01", "Recepcion"), ("DES-01", "Despacho"),
]
CATEGORIAS = [
    ("Tecnología", "Dispositivos electrónicos y periféricos"),
    ("Herramientas", "Herramientas manuales y eléctricas"),
    ("Seguridad", "EPP y dotación industrial"),
]
# sku, nombre, categoria, precio compra, stock minimo, lead time (dias),
# demanda diaria en PRINCIPAL, demanda diaria en NORTE, se repone a mitad de periodo
PRODUCTOS = [
    ("TEC-001", "Mouse inalámbrico", "Tecnología", 38000, 40, 7, 9, 4, True),
    ("TEC-002", "Teclado mecánico", "Tecnología", 145000, 20, 10, 4, 2, True),
    ("TEC-003", "Monitor 24 pulgadas", "Tecnología", 520000, 10, 15, 2, 1, False),
    ("TEC-004", "Lector de código de barras", "Tecnología", 210000, 8, 12, 1.5, 0.8, True),
    ("TEC-005", "Impresora de etiquetas", "Tecnología", 890000, 4, 20, 0.5, 0.2, True),
    ("TEC-006", "Cable HDMI 2 m", "Tecnología", 18000, 60, 5, 12, 6, True),
    ("HER-001", "Taladro percutor", "Herramientas", 320000, 8, 10, 1.2, 0.6, True),
    ("HER-002", "Juego de destornilladores", "Herramientas", 65000, 15, 7, 3, 1.5, False),
    ("HER-003", "Flexómetro 5 m", "Herramientas", 22000, 30, 5, 6, 3, True),
    ("HER-004", "Cinta de embalaje (rollo)", "Herramientas", 7500, 200, 4, 45, 20, True),
    ("HER-005", "Bisturí industrial", "Herramientas", 9500, 50, 5, 8, 4, True),
    ("HER-006", "Estibador manual", "Herramientas", 1450000, 2, 25, 0.15, 0.1, True),
    ("SEG-001", "Casco de seguridad", "Seguridad", 42000, 25, 8, 5, 2.5, True),
    ("SEG-002", "Guantes de nitrilo (par)", "Seguridad", 6500, 150, 5, 30, 14, False),
    ("SEG-003", "Chaleco reflectivo", "Seguridad", 28000, 30, 7, 6, 3, True),
    ("SEG-004", "Botas punta de acero", "Seguridad", 135000, 15, 12, 2.5, 1.2, True),
    ("SEG-005", "Gafas de protección", "Seguridad", 15000, 40, 6, 7, 3.5, False),
]


def poisson(rng: random.Random, media: float) -> int:
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def hay_productos(cur) -> bool:
    cur.execute("SELECT 1 FROM productos LIMIT 1")
    return cur.fetchone() is not None


def reiniciar(cur):
    for tabla in ("inventario", "movimientos", "productos", "categorias", "ubicaciones", "bodegas"):
        cur.execute(f"DELETE FROM {tabla}")
        cur.execute(f"ALTER TABLE {tabla} AUTO_INCREMENT = 1")


def cargar(cur, usuario_id):
    rng = random.Random(2026)
    hoy = datetime.date.today()

    # Catalogos (reutiliza lo que ya exista con el mismo codigo o nombre)
    def id_de(tabla, columna, valor, insertar_sql, params):
        cur.execute(f"SELECT id FROM {tabla} WHERE {columna}=%s", (valor,))
        fila = cur.fetchone()
        if fila:
            return fila[0]
        cur.execute(insertar_sql, params)
        return cur.lastrowid

    bodegas = {c: id_de("bodegas", "codigo", c, "INSERT INTO bodegas (codigo, nombre) VALUES (%s,%s)", (c, n))
               for c, n in BODEGAS}
    categorias = {n: id_de("categorias", "nombre", n, "INSERT INTO categorias (nombre, descripcion) VALUES (%s,%s)", (n, d))
                  for n, d in CATEGORIAS}
    ubicaciones = {}
    for bodega, bodega_id in bodegas.items():
        for codigo, tipo in UBICACIONES:
            cur.execute("SELECT id FROM ubicaciones WHERE bodega_id=%s AND codigo=%s", (bodega_id, codigo))
            fila = cur.fetchone()
            if fila:
                ubicaciones[(bodega, codigo)] = fila[0]
            else:
                cur.execute("INSERT INTO ubicaciones (bodega_id, codigo, tipo) VALUES (%s,%s,%s)", (bodega_id, codigo, tipo))
                ubicaciones[(bodega, codigo)] = cur.lastrowid

    saldos: dict[tuple[int, int], int] = {}   # (ubicacion_id, producto_id) -> cantidad
    movimientos = []

    def mover(tipo, bodega, ubicacion_id, producto_id, delta, cuando, referencia=None, operacion=None):
        clave = (ubicacion_id, producto_id)
        saldos[clave] = saldos.get(clave, 0) + delta
        movimientos.append((operacion or str(uuid.uuid4()), tipo, bodegas[bodega], ubicacion_id, producto_id,
                            delta, saldos[clave], usuario_id, referencia, cuando))

    def momento(dia: datetime.date, hora_min=8, hora_max=17):
        return datetime.datetime.combine(dia, datetime.time(rng.randint(hora_min, hora_max), rng.randint(0, 59)))

    picking = ["A-01-01", "A-01-02", "B-01-01"]
    reserva = ["Z-99-01", "Z-99-02"]
    remision = 1000

    for i, (sku, nombre, categoria, precio, minimo, lead, d_principal, d_norte, repone) in enumerate(PRODUCTOS):
        cur.execute(
            "INSERT INTO productos (sku, nombre, categoria_id, precio_compra, stock_minimo, lead_time_dias) "
            "VALUES (%s,%s,%s,%s,%s,%s)", (sku, nombre, categorias[categoria], precio, minimo, lead))
        producto_id = cur.lastrowid

        for bodega, demanda in (("PRINCIPAL", d_principal), ("NORTE", d_norte)):
            u_pick = ubicaciones[(bodega, picking[i % 3])]
            u_res = ubicaciones[(bodega, reserva[i % 2])]
            inicio = hoy - datetime.timedelta(days=DIAS)

            # Recepcion inicial, 30 % a picking. Los que no se reponen arrancan con
            # mas stock para terminar bajos (por debajo del reorden) pero no en cero.
            inicial = max(2, round(demanda * (36 if repone else 52)))
            remision += 1
            mover("ENTRADA", bodega, u_pick, producto_id, max(1, round(inicial * 0.3)), momento(inicio, 7, 8), f"REM-{remision}")
            mover("ENTRADA", bodega, u_res, producto_id, inicial - max(1, round(inicial * 0.3)), momento(inicio, 7, 8), f"REM-{remision}")

            for n in range(1, DIAS + 1):
                dia = inicio + datetime.timedelta(days=n)
                if dia.weekday() == 6:      # domingo: bodega cerrada
                    continue

                # Reposicion del proveedor a mitad del periodo (algunos no la reciben
                # y terminan por debajo del punto de reorden)
                if repone and n == 32:
                    remision += 1
                    mover("ENTRADA", bodega, u_res, producto_id, max(2, round(demanda * 34)), momento(dia, 7, 9), f"REM-{remision}")

                # Reabastecer picking desde reserva cuando queda poco
                if saldos.get((u_pick, producto_id), 0) < demanda * 2 and saldos.get((u_res, producto_id), 0) > 0:
                    cantidad = min(saldos[(u_res, producto_id)], max(1, math.ceil(demanda * 7)))
                    operacion, cuando = str(uuid.uuid4()), momento(dia, 7, 8)
                    mover("TRANSFERENCIA", bodega, u_res, producto_id, -cantidad, cuando, operacion=operacion)
                    mover("TRANSFERENCIA", bodega, u_pick, producto_id, cantidad, cuando, operacion=operacion)

                # Despachos del dia (los sabados se mueve la mitad)
                pedidos = poisson(rng, demanda * (0.5 if dia.weekday() == 5 else 1.0))
                pedidos = min(pedidos, saldos.get((u_pick, producto_id), 0))
                if pedidos > 0:
                    mover("SALIDA", bodega, u_pick, producto_id, -pedidos, momento(dia, 9, 17), f"PED-{rng.randint(10000, 99999)}")

    movimientos.sort(key=lambda m: m[9])
    cur.executemany(
        "INSERT INTO movimientos (operacion_id, tipo, bodega_id, ubicacion_id, producto_id, delta, saldo, usuario_id, referencia, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", movimientos)
    cur.executemany(
        "INSERT INTO inventario (ubicacion_id, producto_id, cantidad) VALUES (%s,%s,%s)",
        [(u, p, c) for (u, p), c in saldos.items() if c > 0])
    return len(movimientos), sum(saldos.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reiniciar", action="store_true",
                    help="borra bodegas, ubicaciones, productos, inventario y movimientos antes de cargar")
    args = ap.parse_args()

    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        if args.reiniciar:
            reiniciar(cur)
            print("🧹 Datos anteriores borrados (los usuarios se conservan)")
        elif hay_productos(cur):
            print("Ya hay productos en la base, no se cargo nada.\n"
                  "Para BORRAR los datos actuales y cargar la demo:  python datos_demo.py --reiniciar")
            raise SystemExit(1)

        cur.execute("SELECT id FROM usuarios WHERE rol='admin' ORDER BY id LIMIT 1")
        admin = cur.fetchone()
        n_movimientos, unidades = cargar(cur, admin[0] if admin else None)
        conn.commit()
        print(f"✅ Demo cargada: {len(BODEGAS)} bodegas, {len(PRODUCTOS)} productos, "
              f"{n_movimientos} movimientos en {DIAS} dias, {unidades} unidades en stock")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"❌ Error: {err}")
        raise SystemExit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
