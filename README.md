# 📦 SmartBin WMS
> Sistema de Gestión de Bodegas (Warehouse Management System)

Aplicación web completa para gestionar inventario, productos, ubicaciones y usuarios de bodega. Desarrollada con **FastAPI** en el backend y **React** en el frontend, con autenticación JWT y roles de usuario.

---

## 🖼️ Capturas del Sistema

### Login
![Login](screenshots/login.png)

### Dashboard
![Dashboard](screenshots/dashboard.png)

### Inventario
![Inventario](screenshots/inventario.png)

### Productos
![Productos](screenshots/productos.png)

### Transferencias
![Transferencias](screenshots/transferencias.png)

### Usuarios
![Usuarios](screenshots/usuarios.png)

### Reporte PDF
![Reporte PDF](screenshots/reporte.png)

---

## ✅ Funcionalidades

- 🔐 **Autenticación JWT** con roles (admin / operario)
- 📊 **Dashboard** con gráficas de stock por categoría y alertas en tiempo real
- 📦 **Inventario** — tarjetas por ubicación con estados (Normal / Stock bajo / Vacío)
- 🏷️ **Productos** — crear, editar y ajustar stock desde el panel
- 🔄 **Transferencias** — mover productos entre ubicaciones de bodega, seguras ante peticiones simultáneas (descuento atómico en la base de datos)
- 👥 **Usuarios** — gestión de usuarios con roles (solo admin)
- 📄 **Reportes en PDF** — exportar inventario y catálogo de productos
- 📱 **Responsive** — funciona en mobile con menú hamburguesa

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.13 + FastAPI |
| Base de datos | MySQL 8.0 |
| Autenticación | JWT (PyJWT) + contraseñas con PBKDF2-SHA256 |
| Frontend | React 19 + Vite |
| Estilos | Tailwind CSS |
| HTTP Client | Axios |
| Rutas | React Router DOM |
| Gráficas | Recharts |

---

## 🚀 Instalación Local

### Requisitos previos
- Python 3.10+
- Node.js 18+
- MySQL 8.0

### 1. Clonar el repositorio
```bash
git clone https://github.com/KeLeBrA99/SmartBin-WMS.git
cd SmartBin-WMS
```

### 2. Configurar la base de datos
```bash
mysql -u root -p -e "CREATE DATABASE smartbin_wms CHARACTER SET utf8mb4"
mysql -u root -p smartbin_wms < database/schema.sql
```

> **¿Ya tenías la base creada con una versión anterior?** No uses `schema.sql`: haz un respaldo y ejecuta `database/migracion_001_integridad.sql`. El backend se niega a arrancar si la migración no está aplicada.

### 3. Iniciar el backend
```bash
cd SmartBin_WMS
pip install -r requirements.txt
cp .env.example .env        # en Windows: copy .env.example .env
```

Completa `.env` con tu usuario y contraseña de MySQL y una `SECRET_KEY` propia:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Carga los datos iniciales (categorías, ubicaciones y usuarios por defecto) y arranca:

```bash
python poblar_bd.py
python -m uvicorn main:app --reload
```

El backend queda disponible en `http://localhost:8000`  
Documentación automática en `http://localhost:8000/docs`

### 4. Iniciar el frontend
```bash
cd smartbin-frontend
npm install
npm run dev
```

Abrir `http://localhost:5173`

Si el backend no está en `http://localhost:8000`, crea `smartbin-frontend/.env` con `VITE_API_URL=<url del backend>`.

### 5. Pruebas (opcional)
Pruebas de integración contra una base de datos real, incluida la de transferencias concurrentes. Usan una base **dedicada** cuyo nombre debe terminar en `_test` (las tablas se borran en cada ejecución):

```bash
cd SmartBin_WMS
pip install -r requirements-dev.txt
mysql -u root -p -e "CREATE DATABASE smartbin_wms_test CHARACTER SET utf8mb4"
DB_NAME=smartbin_wms_test python -m pytest
```

---

## 👤 Usuarios por defecto

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| admin | admin123 | Administrador |
| operario1 | operario123 | Operario |

Los crea `poblar_bd.py` y son solo para demostración: cámbialos antes de usar el sistema con datos reales (o define `ADMIN_PASSWORD` y `OPERARIO_PASSWORD` antes de ejecutar el script).

---

## 📁 Estructura del Proyecto

```
SmartBin-WMS/
├── database/
│   ├── schema.sql                       # Tablas para una instalación nueva
│   └── migracion_001_integridad.sql     # Para bases creadas con una versión anterior
├── SmartBin_WMS/                # Backend
│   ├── main.py                  # API FastAPI con todos los endpoints
│   ├── config.py                # Configuración leída de variables de entorno (.env)
│   ├── security.py              # Hash y verificación de contraseñas
│   ├── poblar_bd.py             # Datos iniciales (se puede ejecutar varias veces)
│   ├── .env.example             # Plantilla de configuración
│   ├── requirements.txt
│   ├── tests/test_api.py        # Pruebas de integración y de concurrencia
│   └── multi_bodega/            # Diseño v2 (en desarrollo, aún sin integrar)
│       ├── schema.sql           # Esquema multi-bodega con libro mayor
│       ├── stock_service.py     # Stock sin condiciones de carrera
│       └── reorder.py           # Analítica de puntos de reorden
├── smartbin-frontend/           # Frontend
│   └── src/
│       ├── context/
│       │   └── AuthContext.jsx  # Manejo de sesión JWT
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   ├── Inventario.jsx
│       │   ├── Productos.jsx
│       │   ├── Transferencias.jsx
│       │   └── Usuarios.jsx
│       ├── components/
│       │   ├── Sidebar.jsx
│       │   ├── Layout.jsx
│       │   └── ProtectedRoute.jsx
│       ├── api.js               # Configuración Axios
│       └── utils.js             # Escape de HTML y mensajes de error
└── screenshots/                 # Capturas del sistema
```

---

## 🔌 API Endpoints

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| POST | `/login` | Iniciar sesión | No |
| GET | `/dashboard` | Estadísticas generales | Sí |
| GET | `/productos` | Listar productos | Sí |
| POST | `/productos` | Crear producto | Sí |
| PUT | `/productos/{id}` | Editar producto | Admin |
| PATCH | `/productos/{id}/stock` | Ajustar stock | Admin |
| GET | `/ubicaciones` | Ver inventario por ubicación | Sí |
| POST | `/transferencias` | Transferir stock | Sí |
| GET | `/usuarios` | Listar usuarios | Admin |
| POST | `/usuarios` | Crear usuario | Admin |

---

## 🔒 Seguridad e integridad de datos

- **Sin secretos en el código:** la clave JWT y las credenciales de MySQL se leen de `.env`, que no se sube al repositorio.
- **Contraseñas:** PBKDF2-HMAC-SHA256 con sal por usuario. Las cuentas con el hash anterior se actualizan solas al iniciar sesión.
- **Transferencias sin condiciones de carrera:** comprobar y descontar es una sola sentencia SQL, las filas se bloquean siempre en el mismo orden y los deadlocks se reintentan.
- **La base de datos como última defensa:** una fila única por ubicación y producto, y `CHECK (cantidad >= 0)`.
- **Validación de entradas** en la API (cantidades positivas, roles válidos, contraseñas de 8+ caracteres) y **escape de HTML** en los reportes PDF.

---

## 🚧 En desarrollo: multi-bodega, concurrencia y analítica

Diseño de la siguiente versión, en `SmartBin_WMS/multi_bodega/`. **Todavía no está conectado a la aplicación**: la app actual sigue usando `main.py` y sus tablas (`inventario`, `ubicaciones`, `productos`); este módulo define un esquema nuevo y es la base de la migración.

| Archivo | Qué resuelve |
|---------|--------------|
| `schema.sql` | Esquema multi-bodega: saldo (`stock`) + libro mayor de movimientos de solo inserción, `CHECK` contra stock negativo, índices compuestos e idempotencia por operación |
| `stock_service.py` | Salidas y transferencias sin condiciones de carrera: descuento atómico (bloqueo pesimista), conteos con bloqueo optimista por `version`, orden fijo de bloqueo y reintento ante deadlocks, cabecera `Idempotency-Key` |
| `reorder.py` | Puntos de reorden por bodega y producto a partir de la rotación histórica: demanda diaria ponderada hacia lo reciente, stock de seguridad según nivel de servicio y lead time |

Probar la analítica con datos sintéticos (no necesita base de datos):

```bash
cd SmartBin_WMS/multi_bodega
pip install pandas numpy
python reorder.py --demo
```

**Estado:** `reorder.py` está probado con datos sintéticos. `schema.sql` y `stock_service.py` aún no se han probado contra una instancia real de MySQL.

---

## 💡 Contexto del Proyecto

Este sistema nació de la experiencia trabajando como **Auxiliar de Bodega en Lo Basico SAS**, donde se identificó la necesidad de digitalizar el control de inventario que se manejaba manualmente. SmartBin WMS resuelve ese problema con una interfaz moderna, accesible desde cualquier dispositivo.

---

## 👨‍💻 Autor

**Jose Armando Salamanca**
- 📧 t4hkelebra1@gmail.com
- 🐙 [@KeLeBrA99](https://github.com/KeLeBrA99)
- 💼 Estudiante de Ingeniería de Software — Politécnico Grancolombiano
