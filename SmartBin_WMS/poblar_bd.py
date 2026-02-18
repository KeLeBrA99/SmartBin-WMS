import mysql.connector

try:
    # 1. Configuración de la conexión
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",        # Usuario por defecto
        password="1234",        # <--- ¡OJO AQUÍ! Si en Workbench pusiste contraseña, ponla aquí entre las comillas.
        database="smartbin_wms"
    )
    cursor = conexion.cursor()
    print("✅ Conexión exitosa a la Base de Datos")

    # 2. Datos para insertar (Categorías)
    categorias = [
        ("Tecnología", "Dispositivos electrónicos y periféricos"),
        ("Herramientas", "Herramientas manuales y eléctricas"),
        ("Seguridad", "EPP y dotación industrial")
    ]
    
    sql_cat = "INSERT INTO categorias (nombre, descripcion) VALUES (%s, %s)"
    cursor.executemany(sql_cat, categorias)
    print(f"📦 Se insertaron {cursor.rowcount} categorías.")

    # 3. Datos para insertar (Ubicaciones)
    ubicaciones = [
        ("A-01-01", "Picking"),
        ("A-01-02", "Picking"),
        ("Z-99-01", "Reserva"),
        ("REC-01", "Recepcion")
    ]

    sql_ubi = "INSERT INTO ubicaciones (codigo, tipo) VALUES (%s, %s)"
    cursor.executemany(sql_ubi, ubicaciones)
    print(f"📍 Se insertaron {cursor.rowcount} ubicaciones.")

    # 4. Guardar cambios
    conexion.commit()
    print("🚀 ¡Todo guardado con éxito!")

except mysql.connector.Error as err:
    print(f"❌ Error: {err}")

finally:
    if 'conexion' in locals() and conexion.is_connected():
        cursor.close()
        conexion.close()