"""Configuracion leida del entorno. Ningun secreto vive en el codigo.

Copia `.env.example` a `.env` y completa los valores antes de arrancar.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


def _requerida(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            "Copia SmartBin_WMS/.env.example a SmartBin_WMS/.env y completala."
        )
    return valor


SECRET_KEY = _requerida("SECRET_KEY")
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY debe tener al menos 32 caracteres. Genera una con: "
        'python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )

TOKEN_HORAS = int(os.getenv("TOKEN_HORAS", "8"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": _requerida("DB_USER"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "smartbin_wms"),
}
# Solo hace falta si el servidor no reconoce la intercalacion por defecto
# del conector (p. ej. MariaDB): DB_COLLATION=utf8mb4_general_ci
if os.getenv("DB_COLLATION"):
    DB_CONFIG["charset"] = "utf8mb4"
    DB_CONFIG["collation"] = os.environ["DB_COLLATION"]

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
