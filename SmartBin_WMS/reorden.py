"""Puntos de reorden a partir de la rotacion historica (solo libreria estandar).

Por cada bodega y producto:

    d   = demanda diaria media, ponderada hacia lo reciente
    s_d = desviacion estandar de la demanda diaria
    L   = lead time del proveedor en dias
    z   = cuantil normal del nivel de servicio (0.95 -> 1.645)

    stock de seguridad = z * s_d * sqrt(L)
    punto de reorden   = d * L + stock de seguridad

Solo cuentan como demanda las SALIDAS. Las transferencias entre ubicaciones
no son consumo y los ajustes son correcciones de conteo.
"""
import datetime
import math
from statistics import NormalDist

VIDA_MEDIA_DIAS = 45       # una salida de hace 45 dias pesa la mitad que una de hoy
MIN_DIAS_HISTORIA = 28     # con menos historia el resultado se marca poco fiable
DIAS_REVISION = 7          # cada cuanto se revisa el inventario para pedir


def estadisticas_ponderadas(serie: list[float], vida_media: float = VIDA_MEDIA_DIAS) -> tuple[float, float]:
    """Media y desviacion ponderadas; el ultimo elemento es el dia mas reciente."""
    n = len(serie)
    pesos = [0.5 ** ((n - 1 - i) / vida_media) for i in range(n)]
    suma = sum(pesos)
    media = sum(p * x for p, x in zip(pesos, serie)) / suma
    varianza = sum(p * (x - media) ** 2 for p, x in zip(pesos, serie)) / suma
    n_efectivo = suma**2 / sum(p * p for p in pesos)
    if n_efectivo > 1:
        varianza *= n_efectivo / (n_efectivo - 1)   # correccion de sesgo
    return media, math.sqrt(varianza)


def serie_diaria(ventas_por_dia: dict[datetime.date, float], hasta: datetime.date) -> list[float]:
    """Rellena con CERO los dias sin salidas, desde la primera salida.

    Sin esto la media se infla en productos de baja rotacion: tres salidas
    de 10 en un mes son 1 unidad/dia, no 10.
    """
    inicio = min(ventas_por_dia)
    dias = (hasta - inicio).days + 1
    return [float(ventas_por_dia.get(inicio + datetime.timedelta(days=i), 0)) for i in range(dias)]


def calcular(serie: list[float], *, lead_time_dias: float, nivel_servicio: float,
             stock: float = 0, dias_revision: int = DIAS_REVISION) -> dict:
    d, s_d = estadisticas_ponderadas(serie)
    z = NormalDist().inv_cdf(nivel_servicio)
    seguridad = math.ceil(z * s_d * math.sqrt(lead_time_dias))
    punto = math.ceil(d * lead_time_dias + z * s_d * math.sqrt(lead_time_dias))
    requiere = stock <= punto
    objetivo = punto + d * dias_revision   # cubrir tambien el consumo hasta la proxima revision
    return {
        "demanda_diaria": round(d, 2),
        "desviacion": round(s_d, 2),
        "stock_seguridad": seguridad,
        "punto_reorden": punto,
        "dias_cobertura": round(stock / d, 1) if d > 0 else None,
        "requiere_reorden": requiere,
        "cantidad_sugerida": max(0, math.ceil(objetivo - stock)) if requiere else 0,
        "dias_historia": len(serie),
        "baja_confianza": len(serie) < MIN_DIAS_HISTORIA,
    }
