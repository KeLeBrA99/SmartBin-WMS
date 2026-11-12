"""
SmartBin WMS - Puntos de reorden a partir de la rotacion historica.

Modelo (por bodega y producto):

    d   = demanda diaria media, ponderada hacia lo reciente
    s_d = desviacion estandar de la demanda diaria
    L   = lead time medio del proveedor (dias);  s_L = su desviacion
    z   = cuantil normal del nivel de servicio (0.95 -> 1.645)

    stock de seguridad = z * sqrt(L * s_d^2 + d^2 * s_L^2)
    punto de reorden   = d * L + stock de seguridad

Solo cuentan como demanda las SALIDAS (OUTBOUND). Las transferencias
entre ubicaciones no son consumo y los ajustes son correcciones.

Uso como job nocturno:   python reorder.py --days 180
Demo con datos sinteticos (sin base de datos):   python reorder.py --demo

Dependencias: pandas, numpy (y sqlalchemy + pymysql para leer/escribir).
"""
from __future__ import annotations

import argparse
from statistics import NormalDist

import numpy as np
import pandas as pd

MIN_HISTORY_DAYS = 28   # por debajo de esto el resultado se marca poco fiable
HALFLIFE_DAYS = 45      # una venta de hace 45 dias pesa la mitad que una de hoy

DEMAND_SQL = """
SELECT warehouse_id, product_id, DATE(created_at) AS day, -SUM(delta) AS qty
FROM stock_movements
WHERE type = 'OUTBOUND'
  AND created_at >= :since AND created_at < :until
GROUP BY warehouse_id, product_id, DATE(created_at)
"""  # resuelto con el indice ix_mov_demand

PARAMS_SQL = """
SELECT id AS product_id, lead_time_days, lead_time_std_days, service_level
FROM products WHERE is_active = 1
"""

ON_HAND_SQL = """
SELECT warehouse_id, product_id, SUM(quantity - reserved) AS on_hand
FROM stock GROUP BY warehouse_id, product_id
"""  # resuelto con el indice ix_stock_wh_prod


def _weighted_stats(values: np.ndarray, halflife: float) -> tuple[float, float]:
    """Media y desviacion ponderadas; el ultimo elemento es el mas reciente."""
    age = np.arange(len(values) - 1, -1, -1)
    w = 0.5 ** (age / halflife)
    mean = float(np.average(values, weights=w))
    var = float(np.average((values - mean) ** 2, weights=w))
    # Correccion de sesgo por tamano efectivo de muestra.
    n_eff = w.sum() ** 2 / (w**2).sum()
    if n_eff > 1:
        var *= n_eff / (n_eff - 1)
    return mean, float(np.sqrt(var))


def compute_reorder_points(
    demand: pd.DataFrame,
    params: pd.DataFrame,
    as_of: pd.Timestamp,
    on_hand: pd.DataFrame | None = None,
    review_days: int = 7,
    halflife: float = HALFLIFE_DAYS,
) -> pd.DataFrame:
    """
    demand : warehouse_id, product_id, day, qty   (solo dias CON salidas)
    params : product_id, lead_time_days, lead_time_std_days, service_level
    on_hand: warehouse_id, product_id, on_hand    (opcional)
    as_of  : ultimo dia (inclusive) del historico
    """
    demand = demand.copy()
    demand["day"] = pd.to_datetime(demand["day"])
    demand["qty"] = demand["qty"].astype(float)
    params = params.set_index("product_id").astype(float)
    as_of = pd.Timestamp(as_of).normalize()

    rows = []
    for (wh, prod), g in demand.groupby(["warehouse_id", "product_id"]):
        if prod not in params.index:
            continue
        p = params.loc[prod]

        # Clave: los dias sin salidas son demanda CERO, no datos ausentes.
        # Sin esto la media se infla en productos de baja rotacion.
        idx = pd.date_range(g["day"].min(), as_of, freq="D")
        series = g.set_index("day")["qty"].reindex(idx, fill_value=0.0).to_numpy()

        d, s_d = _weighted_stats(series, halflife)
        L, s_L = p["lead_time_days"], p["lead_time_std_days"]
        z = NormalDist().inv_cdf(p["service_level"])

        safety = z * np.sqrt(L * s_d**2 + d**2 * s_L**2)
        rows.append(
            {
                "warehouse_id": wh,
                "product_id": prod,
                "avg_daily_demand": round(d, 4),
                "demand_std": round(s_d, 4),
                "safety_stock": float(np.ceil(safety)),
                "reorder_point": float(np.ceil(d * L + safety)),
                "history_days": len(series),
                "low_confidence": len(series) < MIN_HISTORY_DAYS,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty or on_hand is None:
        return out

    out = out.merge(on_hand, on=["warehouse_id", "product_id"], how="left")
    out["on_hand"] = out["on_hand"].fillna(0).astype(float)
    out["days_of_cover"] = np.where(
        out["avg_daily_demand"] > 0, (out["on_hand"] / out["avg_daily_demand"]).round(1), np.inf
    )
    out["needs_reorder"] = out["on_hand"] <= out["reorder_point"]
    # Pedir hasta cubrir el punto de reorden + el consumo del ciclo de revision.
    target = out["reorder_point"] + out["avg_daily_demand"] * review_days
    out["suggested_qty"] = np.where(
        out["needs_reorder"], np.ceil((target - out["on_hand"]).clip(lower=0)), 0.0
    )
    return out


def run_job(database_url: str, days: int) -> pd.DataFrame:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, isolation_level="READ COMMITTED")
    until = pd.Timestamp.now().normalize()          # hoy 00:00: excluye el dia en curso
    since = until - pd.Timedelta(days=days)

    with engine.connect() as conn:
        demand = pd.read_sql(text(DEMAND_SQL), conn, params={"since": since, "until": until})
        params = pd.read_sql(text(PARAMS_SQL), conn)
        on_hand = pd.read_sql(text(ON_HAND_SQL), conn)

    result = compute_reorder_points(demand, params, as_of=until - pd.Timedelta(days=1), on_hand=on_hand)
    if result.empty:
        return result

    cols = ["warehouse_id", "product_id", "avg_daily_demand", "demand_std",
            "safety_stock", "reorder_point", "history_days", "low_confidence"]
    records = result[cols].astype({"low_confidence": int}).to_dict("records")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO reorder_policies "
                "(warehouse_id, product_id, avg_daily_demand, demand_std, safety_stock, "
                " reorder_point, history_days, low_confidence, calculated_at) "
                "VALUES (:warehouse_id, :product_id, :avg_daily_demand, :demand_std, "
                " :safety_stock, :reorder_point, :history_days, :low_confidence, NOW(6)) "
                "ON DUPLICATE KEY UPDATE avg_daily_demand = VALUES(avg_daily_demand), "
                " demand_std = VALUES(demand_std), safety_stock = VALUES(safety_stock), "
                " reorder_point = VALUES(reorder_point), history_days = VALUES(history_days), "
                " low_confidence = VALUES(low_confidence), calculated_at = NOW(6)"
            ),
            records,
        )
    return result


def _demo() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    as_of = pd.Timestamp("2026-11-11")
    days = pd.date_range(end=as_of, periods=120, freq="D")
    rows = []
    # (bodega, producto, demanda media diaria, prob. de que haya salida ese dia)
    for wh, prod, lam, p_sale in [(1, 101, 20, 1.0), (1, 102, 3, 0.3), (2, 101, 8, 0.9)]:
        for day in days:
            if rng.random() < p_sale:
                qty = rng.poisson(lam)
                if qty:
                    rows.append((wh, prod, day, qty))
    demand = pd.DataFrame(rows, columns=["warehouse_id", "product_id", "day", "qty"])
    params = pd.DataFrame(
        {"product_id": [101, 102], "lead_time_days": [7, 15],
         "lead_time_std_days": [1, 3], "service_level": [0.95, 0.90]}
    )
    on_hand = pd.DataFrame(
        {"warehouse_id": [1, 1, 2], "product_id": [101, 102, 101], "on_hand": [150, 60, 40]}
    )
    return compute_reorder_points(demand, params, as_of=as_of, on_hand=on_hand)


if __name__ == "__main__":
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180, help="ventana de historico")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    df = _demo() if args.demo else run_job(os.environ["DATABASE_URL"], args.days)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
