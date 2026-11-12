"""Hash de contrasenas con PBKDF2-HMAC-SHA256 (libreria estandar).

Formato guardado:  pbkdf2_sha256$<iteraciones>$<sal hex>$<hash hex>

Las cuentas creadas con el esquema anterior (SHA-256 sin sal, 64 caracteres
hex) siguen pudiendo iniciar sesion: `verificar` las reconoce y
`necesita_actualizar` indica que hay que re-hashearlas en ese login.
"""
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 600_000


def hash_password(password: str, *, iteraciones: int = ITERACIONES) -> str:
    sal = secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, iteraciones)
    return f"{ALGORITMO}${iteraciones}${sal.hex()}${derivado.hex()}"


def _es_legado(guardado: str) -> bool:
    return "$" not in guardado and len(guardado) == 64


def verificar(password: str, guardado: str) -> bool:
    if not guardado:
        return False
    if _es_legado(guardado):
        candidato = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(candidato, guardado.lower())
    try:
        algoritmo, iteraciones, sal_hex, hash_hex = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        derivado = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(sal_hex), int(iteraciones)
        )
        return hmac.compare_digest(derivado.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def necesita_actualizar(guardado: str) -> bool:
    if _es_legado(guardado):
        return True
    try:
        return int(guardado.split("$")[1]) < ITERACIONES
    except (IndexError, ValueError):
        return True
