"""Carga los datos iniciales: bodega principal, categorias, ubicaciones y usuarios.

Se puede ejecutar varias veces: solo llena las tablas que esten vacias.
Usa la misma configuracion (.env) que el backend.

    python poblar_bd.py      (lo ejecuta tambien `python preparar_bd.py`)

Las contrasenas iniciales se pueden fijar con ADMIN_PASSWORD y
OPERARIO_PASSWORD; si no, se usan las de demostracion del README.
Cambialas antes de usar el sistema con datos reales.
"""
import os

import mysql.connector

from config import DB_CONFIG
from security import hash_password

CATEGORIAS = [
    ("Tecnología", "Dispositivos electrónicos y periféricos"),
    ("Herramientas", "Herramientas manuales y eléctricas"),
    ("Seguridad", "EPP y dotación industrial"),
]
UBICACIONES = [
    ("A-01-01", "Picking"),
    ("A-01-02", "Picking"),
    ("Z-99-01", "Reserva"),
    ("REC-01", "Recepcion"),
]
USUARIOS = [
    ("admin", os.getenv("ADMIN_PASSWORD", "admin123"), "Administrador", "admin"),
    ("operario1", os.getenv("OPERARIO_PASSWORD", "operario123"), "Operario 1", "operario"),
]


def hay_filas(cursor, tabla):
    cursor.execute(f"SELECT 1 FROM {tabla} LIMIT 1")
    return cursor.fetchone() is not None


def insertar_si_falta(cursor, tabla, columna, valor, columnas, valores):
    cursor.execute(f"SELECT 1 FROM {tabla} WHERE {columna}=%s", (valor,))
    if cursor.fetchone():
        return 0
    marcadores = ",".join(["%s"] * len(valores))
    cursor.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcadores})", valores)
    return 1


def main():
    conexion = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = conexion.cursor()
        print("✅ Conexión exitosa a la Base de Datos")

        n = insertar_si_falta(cursor, "bodegas", "codigo", "PRINCIPAL", "id, codigo, nombre", (1, "PRINCIPAL", "Bodega Principal")) \
            if not hay_filas(cursor, "bodegas") else 0
        print(f"🏭 Bodegas nuevas: {n}")

        # Los datos de ejemplo solo se cargan en tablas vacias: en una base que
        # ya tiene informacion no se agrega nada.
        n = 0 if hay_filas(cursor, "categorias") else \
            sum(insertar_si_falta(cursor, "categorias", "nombre", c[0], "nombre, descripcion", c) for c in CATEGORIAS)
        print(f"📦 Categorías nuevas: {n}")

        n = 0 if hay_filas(cursor, "ubicaciones") else \
            sum(insertar_si_falta(cursor, "ubicaciones", "codigo", u[0], "codigo, tipo", u) for u in UBICACIONES)
        print(f"📍 Ubicaciones nuevas: {n}")

        n = 0 if hay_filas(cursor, "usuarios") else sum(
            insertar_si_falta(cursor, "usuarios", "usuario", usuario,
                              "usuario, password, nombre, rol",
                              (usuario, hash_password(clave), nombre, rol))
            for usuario, clave, nombre, rol in USUARIOS
        )
        print(f"👥 Usuarios nuevos: {n}")

        conexion.commit()
        print("🚀 ¡Todo guardado con éxito!")
    except mysql.connector.Error as err:
        conexion.rollback()
        print(f"❌ Error: {err}")
        raise SystemExit(1)
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
