"""
SmartBin WMS - Servicio de stock sin condiciones de carrera.

DISENO DE REFERENCIA: no lo usa la aplicacion. El descuento atomico, el orden
de bloqueo, el libro mayor y el multi-bodega ya estan integrados en ../main.py;
aqui queda lo pendiente: idempotencia, bloqueo optimista y stock reservado.

Estrategia de concurrencia (una por caso de uso, no "una para todo"):

  * Salidas y transferencias -> bloqueo PESIMISTA implicito:
      UPDATE ... SET quantity = quantity - :q WHERE ... AND quantity - reserved >= :q
    La comprobacion y el descuento son una sola sentencia atomica; InnoDB
    bloquea la fila hasta el COMMIT. No existe la ventana "leo 10, otro lee
    10, ambos descuentan 8" del patron SELECT + UPDATE.

  * Conteos / ajustes manuales -> bloqueo OPTIMISTA con `version`:
    el operario vio una cantidad en pantalla; si alguien la cambio mientras
    contaba, se responde 409 y vuelve a contar. No se retiene ningun bloqueo
    mientras una persona piensa.

  * Deadlocks -> se previenen tocando las filas siempre en el mismo orden
    (location_id, product_id) y, como red de seguridad, se reintenta la
    transaccion completa ante los errores 1213 / 1205 de MySQL.

  * Reintentos del cliente (doble clic, timeout de red) -> cabecera
    Idempotency-Key respaldada por un indice UNIQUE.

Dependencias: fastapi, pydantic>=2, sqlalchemy>=2, pymysql
Endpoints `def` (no async): FastAPI los ejecuta en su threadpool y cada
peticion usa su propia conexion del pool.
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, TypeVar
from uuid import UUID

from fastapi import APIRouter, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

# --------------------------------------------------------------------------
# Infraestructura
# --------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL", "mysql+pymysql://smartbin:smartbin@localhost:3306/smartbin"
)

engine = create_engine(
    DATABASE_URL,
    isolation_level="READ COMMITTED",  # menos gap locks que REPEATABLE READ
    pool_size=20,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    # Fallar rapido en vez de encolar peticiones 50 s (valor por defecto).
    connect_args={"init_command": "SET SESSION innodb_lock_wait_timeout = 5"},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

MYSQL_DEADLOCK = 1213
MYSQL_LOCK_WAIT_TIMEOUT = 1205
MAX_ATTEMPTS = 4

T = TypeVar("T")


# --------------------------------------------------------------------------
# Errores de dominio
# --------------------------------------------------------------------------
class InsufficientStock(Exception):
    def __init__(self, location_id: int, product_id: int):
        self.location_id, self.product_id = location_id, product_id


class LocationNotFound(Exception):
    def __init__(self, location_id: int):
        self.location_id = location_id


class DuplicateOperation(Exception):
    """La Idempotency-Key ya fue procesada."""


class VersionConflict(Exception):
    def __init__(self, current_version: int | None):
        self.current_version = current_version


# --------------------------------------------------------------------------
# Nucleo transaccional
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Leg:
    """Un cambio de saldo en una ubicacion. delta < 0 descuenta, > 0 suma."""
    location_id: int
    product_id: int
    delta: Decimal


def run_in_transaction(work: Callable[[Session], T]) -> T:
    """Ejecuta `work` en UNA transaccion; reintenta si MySQL la aborta por
    deadlock o por timeout de bloqueo. `work` debe ser re-ejecutable: no
    puede tener efectos fuera de la base de datos."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with SessionLocal() as db, db.begin():  # COMMIT / ROLLBACK automatico
                return work(db)
        except OperationalError as exc:
            code = exc.orig.args[0] if exc.orig and exc.orig.args else None
            if code not in (MYSQL_DEADLOCK, MYSQL_LOCK_WAIT_TIMEOUT) or attempt == MAX_ATTEMPTS:
                raise
            # Backoff exponencial con jitter para no volver a chocar.
            time.sleep((0.05 * 2**attempt) * random.uniform(0.5, 1.5))
    raise RuntimeError("inalcanzable")


def _apply_leg(db: Session, leg: Leg) -> tuple[int, Decimal]:
    """Aplica un delta y devuelve (warehouse_id, saldo_resultante)."""
    params = {"loc": leg.location_id, "prod": leg.product_id, "q": abs(leg.delta)}

    if leg.delta < 0:
        # Comprobacion + descuento atomicos. Respeta lo reservado.
        res = db.execute(
            text(
                "UPDATE stock SET quantity = quantity - :q, version = version + 1 "
                "WHERE location_id = :loc AND product_id = :prod "
                "AND quantity - reserved >= :q"
            ),
            params,
        )
        if res.rowcount == 0:
            raise InsufficientStock(leg.location_id, leg.product_id)
    else:
        # Upsert: crea la fila si la ubicacion aun no tenia ese producto.
        res = db.execute(
            text(
                "INSERT INTO stock (warehouse_id, location_id, product_id, quantity) "
                "SELECT l.warehouse_id, l.id, :prod, :q FROM locations l "
                "WHERE l.id = :loc AND l.is_active = 1 "
                "ON DUPLICATE KEY UPDATE quantity = stock.quantity + :q, "
                "version = stock.version + 1"
            ),
            params,
        )
        if res.rowcount == 0:
            raise LocationNotFound(leg.location_id)

    # La fila sigue bloqueada por esta transaccion: la lectura es consistente.
    row = db.execute(
        text(
            "SELECT warehouse_id, quantity FROM stock "
            "WHERE location_id = :loc AND product_id = :prod"
        ),
        params,
    ).one()
    return row.warehouse_id, row.quantity


def _create_operation(db: Session, key: UUID, op_type: str, reference: str | None, user_id: int) -> int:
    try:
        res = db.execute(
            text(
                "INSERT INTO stock_operations (idempotency_key, type, reference, created_by) "
                "VALUES (:key, :type, :ref, :user)"
            ),
            {"key": str(key), "type": op_type, "ref": reference, "user": user_id},
        )
    except IntegrityError as exc:
        # Si otra peticion con la misma clave esta en curso, este INSERT
        # espera a su COMMIT y luego cae aqui: nunca se ejecutan las dos.
        raise DuplicateOperation from exc
    return res.lastrowid


def _record_movement(db: Session, op_id: int, op_type: str, leg: Leg, warehouse_id: int, balance: Decimal) -> None:
    db.execute(
        text(
            "INSERT INTO stock_movements "
            "(operation_id, type, warehouse_id, location_id, product_id, delta, balance_after) "
            "VALUES (:op, :type, :wh, :loc, :prod, :delta, :bal)"
        ),
        {
            "op": op_id, "type": op_type, "wh": warehouse_id,
            "loc": leg.location_id, "prod": leg.product_id,
            "delta": leg.delta, "bal": balance,
        },
    )


def execute_operation(
    *, key: UUID, op_type: str, legs: list[Leg], user_id: int, reference: str | None = None
) -> dict:
    """Aplica todos los `legs` de forma atomica: o se aplican todos, o ninguno."""
    # Orden global de bloqueo: dos transferencias cruzadas (A->B y B->A)
    # piden las filas en el mismo orden y una simplemente espera a la otra.
    ordered = sorted(legs, key=lambda l: (l.location_id, l.product_id))

    def work(db: Session) -> dict:
        op_id = _create_operation(db, key, op_type, reference, user_id)
        balances = []
        for leg in ordered:
            warehouse_id, balance = _apply_leg(db, leg)
            _record_movement(db, op_id, op_type, leg, warehouse_id, balance)
            balances.append(
                {"location_id": leg.location_id, "product_id": leg.product_id, "balance": balance}
            )
        return {"operation_id": op_id, "replayed": False, "balances": balances}

    try:
        return run_in_transaction(work)
    except DuplicateOperation:
        return _replay(key)


def _replay(key: UUID) -> dict:
    """Devuelve el resultado original de una operacion ya procesada."""
    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT o.id, m.location_id, m.product_id, m.balance_after "
                "FROM stock_operations o "
                "JOIN stock_movements m ON m.operation_id = o.id "
                "WHERE o.idempotency_key = :key ORDER BY m.id"
            ),
            {"key": str(key)},
        ).all()
    if not rows:
        raise HTTPException(status.HTTP_409_CONFLICT, "Operacion con esa clave aun en curso")
    return {
        "operation_id": rows[0].id,
        "replayed": True,
        "balances": [
            {"location_id": r.location_id, "product_id": r.product_id, "balance": r.balance_after}
            for r in rows
        ],
    }


def adjust_by_count(
    *, key: UUID, stock_id: int, counted: Decimal, expected_version: int, user_id: int
) -> dict:
    """Conteo fisico con bloqueo OPTIMISTA."""

    def work(db: Session) -> dict:
        row = db.execute(
            text(
                "SELECT warehouse_id, location_id, product_id, quantity, version "
                "FROM stock WHERE id = :id"
            ),
            {"id": stock_id},
        ).one_or_none()
        if row is None or row.version != expected_version:
            raise VersionConflict(row.version if row else None)

        delta = counted - row.quantity
        if delta == 0:
            return {"operation_id": None, "version": row.version, "balance": row.quantity}

        op_id = _create_operation(db, key, "ADJUSTMENT", None, user_id)
        # El WHERE version = :v es el bloqueo optimista: si otra transaccion
        # modifico la fila entre el SELECT y este UPDATE, afecta 0 filas.
        res = db.execute(
            text(
                "UPDATE stock SET quantity = :new, version = version + 1 "
                "WHERE id = :id AND version = :v AND reserved <= :new"
            ),
            {"new": counted, "id": stock_id, "v": expected_version},
        )
        if res.rowcount == 0:
            raise VersionConflict(None)

        leg = Leg(row.location_id, row.product_id, delta)
        _record_movement(db, op_id, "ADJUSTMENT", leg, row.warehouse_id, counted)
        return {"operation_id": op_id, "version": expected_version + 1, "balance": counted}

    return run_in_transaction(work)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
Qty = Decimal


class OutboundIn(BaseModel):
    location_id: int
    product_id: int
    quantity: Qty = Field(gt=0, max_digits=14, decimal_places=3)
    reference: str | None = Field(default=None, max_length=80)


class TransferIn(BaseModel):
    product_id: int
    from_location_id: int
    to_location_id: int
    quantity: Qty = Field(gt=0, max_digits=14, decimal_places=3)
    reference: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _distinct(self) -> "TransferIn":
        if self.from_location_id == self.to_location_id:
            raise ValueError("Origen y destino deben ser distintos")
        return self


class CountIn(BaseModel):
    counted_quantity: Qty = Field(ge=0, max_digits=14, decimal_places=3)
    expected_version: int = Field(ge=0)


router = APIRouter(prefix="/stock", tags=["stock"])


def current_user_id() -> int:
    return 1  # TODO: sustituir por la dependencia real de autenticacion (JWT)


def _handle(fn: Callable[[], dict]) -> dict:
    try:
        return fn()
    except InsufficientStock as e:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "INSUFFICIENT_STOCK", "location_id": e.location_id, "product_id": e.product_id},
        )
    except LocationNotFound as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "LOCATION_NOT_FOUND", "location_id": e.location_id}
        )
    except VersionConflict as e:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "VERSION_CONFLICT", "current_version": e.current_version},
        )
    except OperationalError:
        # Se agotaron los reintentos por contencion: el cliente puede reintentar
        # con la MISMA Idempotency-Key sin riesgo.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, {"code": "BUSY_RETRY"})


@router.post("/outbound")
def outbound(body: OutboundIn, idempotency_key: UUID = Header(...)) -> dict:
    return _handle(lambda: execute_operation(
        key=idempotency_key, op_type="OUTBOUND", user_id=current_user_id(),
        reference=body.reference,
        legs=[Leg(body.location_id, body.product_id, -body.quantity)],
    ))


@router.post("/transfer")
def transfer(body: TransferIn, idempotency_key: UUID = Header(...)) -> dict:
    """Sirve igual dentro de una bodega o entre bodegas: cada ubicacion
    pertenece a una bodega y el movimiento queda registrado en la suya."""
    return _handle(lambda: execute_operation(
        key=idempotency_key, op_type="TRANSFER", user_id=current_user_id(),
        reference=body.reference,
        legs=[
            Leg(body.from_location_id, body.product_id, -body.quantity),
            Leg(body.to_location_id, body.product_id, body.quantity),
        ],
    ))


@router.put("/{stock_id}/count")
def count(stock_id: int, body: CountIn, idempotency_key: UUID = Header(...)) -> dict:
    return _handle(lambda: adjust_by_count(
        key=idempotency_key, stock_id=stock_id, counted=body.counted_quantity,
        expected_version=body.expected_version, user_id=current_user_id(),
    ))


app = FastAPI(title="SmartBin WMS")
app.include_router(router)
