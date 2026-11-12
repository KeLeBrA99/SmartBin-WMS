"""Deja la base de datos lista con un solo comando:

    python preparar_bd.py

Sirve igual para una instalacion nueva y para una base creada con una version
anterior, y se puede ejecutar las veces que haga falta: cada paso revisa
primero si ya esta aplicado.

  1. Crea la base de datos si no existe.
  2. Crea las tablas que falten (database/schema.sql).
  3. Actualiza las tablas antiguas: indice unico y CHECK de inventario,
     columna de contrasena, bodegas, parametros de reorden.
  4. Carga los datos iniciales (poblar_bd.py).

Si la base ya tiene datos, haz antes una copia desde MySQL Workbench
(Server > Data Export) o con mysqldump.
"""
from pathlib import Path

import mysql.connector

import poblar_bd
from config import DB_CONFIG

ESQUEMA = Path(__file__).resolve().parents[1] / "database" / "schema.sql"


def sentencias(sql: str):
    for bloque in sql.split(";"):
        cuerpo = "\n".join(l for l in bloque.splitlines() if not l.strip().startswith("--")).strip()
        if cuerpo:
            yield cuerpo


def uno(cur, sql, params=()):
    cur.execute(sql, params)
    fila = cur.fetchone()
    return fila[0] if fila else None


def columna(cur, tabla, nombre):
    """Largo maximo de la columna (0 si no es de texto) o None si no existe."""
    cur.execute(
        "SELECT COALESCE(character_maximum_length, 0) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (tabla, nombre),
    )
    fila = cur.fetchone()
    return fila[0] if fila else None


def indice(cur, tabla, nombre):
    return uno(cur, "SELECT 1 FROM information_schema.statistics WHERE table_schema = DATABASE() "
                    "AND table_name = %s AND index_name = %s LIMIT 1", (tabla, nombre))


def restriccion(cur, tabla, nombre):
    return uno(cur, "SELECT 1 FROM information_schema.table_constraints WHERE table_schema = DATABASE() "
                    "AND table_name = %s AND constraint_name = %s LIMIT 1", (tabla, nombre))


def inventario_tiene_unico(cur):
    cur.execute(
        "SELECT GROUP_CONCAT(column_name ORDER BY column_name) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = 'inventario' AND non_unique = 0 GROUP BY index_name"
    )
    return any(f[0] == "producto_id,ubicacion_id" for f in cur.fetchall())


def actualizar(conn, cur):
    hecho = lambda texto: print(f"   ✔ {texto}")

    if (columna(cur, "usuarios", "password") or 0) < 128:
        cur.execute("ALTER TABLE usuarios MODIFY password VARCHAR(255) NOT NULL")
        hecho("usuarios.password ampliada para el hash nuevo")

    if not inventario_tiene_unico(cur):
        # Unifica filas repetidas (misma ubicacion y producto) sumando cantidades.
        cur.execute("SELECT ubicacion_id, producto_id, SUM(cantidad) FROM inventario "
                    "GROUP BY ubicacion_id, producto_id HAVING COUNT(*) > 1")
        repetidas = cur.fetchall()
        for ubicacion_id, producto_id, total in repetidas:
            cur.execute("DELETE FROM inventario WHERE ubicacion_id=%s AND producto_id=%s", (ubicacion_id, producto_id))
            cur.execute("INSERT INTO inventario (ubicacion_id, producto_id, cantidad) VALUES (%s,%s,%s)",
                        (ubicacion_id, producto_id, total))
        conn.commit()
        if repetidas:
            hecho(f"{len(repetidas)} filas repetidas de inventario unificadas")
        cur.execute("ALTER TABLE inventario ADD UNIQUE KEY uq_inventario_ubi_prod (ubicacion_id, producto_id)")
        hecho("indice unico (ubicacion, producto) en inventario")

    if not restriccion(cur, "inventario", "chk_inventario_cantidad"):
        cur.execute("UPDATE inventario SET cantidad = 0 WHERE cantidad < 0 OR cantidad IS NULL")
        if cur.rowcount:
            hecho(f"{cur.rowcount} cantidades negativas o vacias puestas en 0")
        conn.commit()
        cur.execute("ALTER TABLE inventario MODIFY cantidad INT NOT NULL DEFAULT 0")
        cur.execute("ALTER TABLE inventario ADD CONSTRAINT chk_inventario_cantidad CHECK (cantidad >= 0)")
        hecho("la base ahora rechaza stock negativo")

    if not indice(cur, "inventario", "ix_inventario_producto"):
        cur.execute("ALTER TABLE inventario ADD KEY ix_inventario_producto (producto_id, cantidad)")
        hecho("indice de stock por producto")

    # La bodega principal debe existir antes de enlazar las ubicaciones.
    if not uno(cur, "SELECT 1 FROM bodegas LIMIT 1"):
        cur.execute("INSERT INTO bodegas (id, codigo, nombre) VALUES (1, 'PRINCIPAL', 'Bodega Principal')")
        conn.commit()
        hecho("bodega PRINCIPAL creada")

    if columna(cur, "ubicaciones", "bodega_id") is None:
        principal = uno(cur, "SELECT MIN(id) FROM bodegas")
        cur.execute(f"ALTER TABLE ubicaciones ADD COLUMN bodega_id INT NOT NULL DEFAULT {int(principal)}")
        cur.execute("ALTER TABLE ubicaciones ADD CONSTRAINT fk_ubicaciones_bodega FOREIGN KEY (bodega_id) REFERENCES bodegas (id)")
        hecho("ubicaciones existentes asignadas a la bodega principal")

    if not indice(cur, "ubicaciones", "uq_ubicaciones_bodega_codigo"):
        try:
            cur.execute("ALTER TABLE ubicaciones ADD UNIQUE KEY uq_ubicaciones_bodega_codigo (bodega_id, codigo)")
            hecho("codigo de ubicacion unico por bodega")
        except mysql.connector.Error as err:
            print(f"   ⚠ No se pudo exigir codigo unico por bodega (hay codigos repetidos): {err.msg}")

    # Un indice unico antiguo sobre `codigo` solo impediria repetir el mismo
    # codigo en bodegas distintas.
    cur.execute(
        "SELECT index_name FROM information_schema.statistics WHERE table_schema = DATABASE() "
        "AND table_name = 'ubicaciones' AND non_unique = 0 AND index_name <> 'PRIMARY' "
        "GROUP BY index_name HAVING GROUP_CONCAT(column_name) = 'codigo'"
    )
    for (nombre,) in cur.fetchall():
        if indice(cur, "ubicaciones", "uq_ubicaciones_bodega_codigo"):
            cur.execute(f"ALTER TABLE ubicaciones DROP INDEX `{nombre}`")
            hecho(f"indice antiguo `{nombre}` reemplazado por el de (bodega, codigo)")

    if columna(cur, "productos", "lead_time_dias") is None:
        cur.execute("ALTER TABLE productos ADD COLUMN lead_time_dias DECIMAL(6,2) NOT NULL DEFAULT 7.00, "
                    "ADD COLUMN nivel_servicio DECIMAL(4,3) NOT NULL DEFAULT 0.950")
        hecho("parametros de reorden agregados a productos")
    conn.commit()


def main():
    config = dict(DB_CONFIG)
    base = config.pop("database")
    conn = mysql.connector.connect(**config)
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{base}` CHARACTER SET utf8mb4")
        cur.execute(f"USE `{base}`")
        print(f"1/3 Base de datos `{base}` lista")

        for sentencia in sentencias(ESQUEMA.read_text(encoding="utf-8")):
            cur.execute(sentencia)
        conn.commit()
        print("2/3 Tablas creadas o ya existentes")

        actualizar(conn, cur)
        print("3/3 Estructura al dia")
    finally:
        conn.close()

    poblar_bd.main()
    print("\nListo. Arranca el backend con:  python -m uvicorn main:app --reload")


if __name__ == "__main__":
    main()
