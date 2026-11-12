-- =====================================================================
-- DISENO DE REFERENCIA (no lo usa la aplicacion; ver database/schema.sql)
-- SmartBin WMS - Esquema multi-bodega (MySQL 8.0.16+, InnoDB, utf8mb4)
-- Principios:
--   1. `stock` es el saldo actual; `stock_movements` es el libro mayor
--      (append-only). Ambos se escriben SIEMPRE en la misma transaccion.
--   2. La base de datos es la ultima linea de defensa: CHECK impide stock
--      negativo aunque la aplicacion tenga un bug.
--   3. Idempotencia por `stock_operations.idempotency_key`: un reintento
--      del cliente nunca descuenta dos veces.
-- Aislamiento recomendado: READ COMMITTED (menos gap locks = menos
-- deadlocks entre bodegas). Se configura en la conexion, no aqui.
-- =====================================================================

CREATE TABLE warehouses (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)  NOT NULL,
    name        VARCHAR(120) NOT NULL,
    is_active   TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_wh_code (code)
) ENGINE=InnoDB;

CREATE TABLE locations (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    warehouse_id  INT UNSIGNED    NOT NULL,
    code          VARCHAR(40)     NOT NULL,          -- p. ej. A-01-03-B
    type          ENUM('RECEIVING','RESERVE','PICKING','DISPATCH','QUARANTINE')
                  NOT NULL DEFAULT 'RESERVE',
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_loc_wh_code (warehouse_id, code),
    -- Necesario para la FK compuesta de `stock` (garantiza que
    -- stock.warehouse_id siempre coincide con la bodega de la ubicacion).
    UNIQUE KEY uq_loc_id_wh (id, warehouse_id),
    CONSTRAINT fk_loc_wh FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
) ENGINE=InnoDB;

CREATE TABLE products (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sku                 VARCHAR(60)     NOT NULL,
    name                VARCHAR(200)    NOT NULL,
    -- Parametros de reabastecimiento (los usa el modulo de analitica)
    lead_time_days      DECIMAL(6,2)    NOT NULL DEFAULT 7.00,
    lead_time_std_days  DECIMAL(6,2)    NOT NULL DEFAULT 0.00,
    service_level       DECIMAL(4,3)    NOT NULL DEFAULT 0.950,
    is_active           TINYINT(1)      NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_prod_sku (sku),
    CONSTRAINT chk_prod_sl CHECK (service_level > 0.5 AND service_level < 1)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Saldo actual: una fila por (ubicacion, producto).
-- ---------------------------------------------------------------------
CREATE TABLE stock (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    warehouse_id  INT UNSIGNED    NOT NULL,   -- desnormalizado para consultas por bodega
    location_id   BIGINT UNSIGNED NOT NULL,
    product_id    BIGINT UNSIGNED NOT NULL,
    quantity      DECIMAL(14,3)   NOT NULL DEFAULT 0,
    reserved      DECIMAL(14,3)   NOT NULL DEFAULT 0,  -- apartado por pedidos
    version       INT UNSIGNED    NOT NULL DEFAULT 0,  -- bloqueo optimista
    updated_at    DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                  ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),

    -- Clave de negocio. Es el indice que usan TODOS los UPDATE de stock:
    -- el bloqueo cae sobre una sola fila, no sobre un rango.
    UNIQUE KEY uq_stock_loc_prod (location_id, product_id),

    -- "Cuanto hay del producto X en la bodega Y" resuelto solo con el
    -- indice (covering): no toca la tabla.
    KEY ix_stock_wh_prod (warehouse_id, product_id, quantity, reserved),

    -- "Donde hay disponible del producto X" (sugerencia de picking).
    KEY ix_stock_prod_qty (product_id, quantity),

    CONSTRAINT fk_stock_loc  FOREIGN KEY (location_id, warehouse_id)
        REFERENCES locations (id, warehouse_id),
    CONSTRAINT fk_stock_prod FOREIGN KEY (product_id) REFERENCES products (id),
    CONSTRAINT chk_stock_qty CHECK (quantity >= 0),
    CONSTRAINT chk_stock_res CHECK (reserved >= 0 AND reserved <= quantity)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Cabecera de operacion: una por peticion de negocio (una salida, una
-- transferencia, un conteo). Da idempotencia y trazabilidad.
-- ---------------------------------------------------------------------
CREATE TABLE stock_operations (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    idempotency_key  CHAR(36)        NOT NULL,   -- UUID generado por el cliente
    type             ENUM('INBOUND','OUTBOUND','TRANSFER','ADJUSTMENT') NOT NULL,
    reference        VARCHAR(80)     NULL,       -- pedido, remision, etc.
    created_by       BIGINT UNSIGNED NOT NULL,
    created_at       DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_op_idem (idempotency_key),
    KEY ix_op_type_date (type, created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Libro mayor: una fila por cada cambio de saldo. Nunca UPDATE/DELETE.
-- Una transferencia genera dos filas (delta negativo y positivo).
-- ---------------------------------------------------------------------
CREATE TABLE stock_movements (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    operation_id   BIGINT UNSIGNED NOT NULL,
    type           ENUM('INBOUND','OUTBOUND','TRANSFER','ADJUSTMENT') NOT NULL,
    warehouse_id   INT UNSIGNED    NOT NULL,
    location_id    BIGINT UNSIGNED NOT NULL,
    product_id     BIGINT UNSIGNED NOT NULL,
    delta          DECIMAL(14,3)   NOT NULL,     -- con signo
    balance_after  DECIMAL(14,3)   NOT NULL,     -- saldo de la ubicacion tras el movimiento
    created_at     DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_mov_op (operation_id),

    -- Analitica de demanda: filtra por tipo y rango de fechas, agrupa por
    -- bodega/producto. Incluye `delta` para ser covering.
    KEY ix_mov_demand (type, created_at, warehouse_id, product_id, delta),

    -- Kardex de un producto en una bodega, ordenado por fecha.
    KEY ix_mov_kardex (warehouse_id, product_id, created_at),

    -- Historial de una ubicacion concreta.
    KEY ix_mov_loc (location_id, product_id, created_at),

    CONSTRAINT fk_mov_op   FOREIGN KEY (operation_id) REFERENCES stock_operations (id),
    CONSTRAINT fk_mov_loc  FOREIGN KEY (location_id, warehouse_id)
        REFERENCES locations (id, warehouse_id),
    CONSTRAINT fk_mov_prod FOREIGN KEY (product_id) REFERENCES products (id),
    CONSTRAINT chk_mov_delta CHECK (delta <> 0)
) ENGINE=InnoDB;
-- Cuando la tabla pase de decenas de millones de filas: particionar por
-- RANGE sobre created_at (exige quitar las FK e incluir created_at en la PK).

-- ---------------------------------------------------------------------
-- Resultado de la analitica de reorden, si se quisiera guardar (hoy la
-- aplicacion lo calcula al vuelo en GET /reorden).
-- ---------------------------------------------------------------------
CREATE TABLE reorder_policies (
    warehouse_id      INT UNSIGNED    NOT NULL,
    product_id        BIGINT UNSIGNED NOT NULL,
    avg_daily_demand  DECIMAL(14,4)   NOT NULL,
    demand_std        DECIMAL(14,4)   NOT NULL,
    safety_stock      DECIMAL(14,3)   NOT NULL,
    reorder_point     DECIMAL(14,3)   NOT NULL,
    history_days      INT UNSIGNED    NOT NULL,
    low_confidence    TINYINT(1)      NOT NULL DEFAULT 0,
    calculated_at     DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (warehouse_id, product_id),
    CONSTRAINT fk_rp_wh   FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
    CONSTRAINT fk_rp_prod FOREIGN KEY (product_id)   REFERENCES products (id)
) ENGINE=InnoDB;

-- =====================================================================
-- Patron transaccional de referencia (lo implementa stock_service.py)
-- Transferir 5 uds del producto 42 de la ubicacion 10 a la 20:
-- =====================================================================
-- SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
-- START TRANSACTION;
--   INSERT INTO stock_operations (idempotency_key, type, created_by)
--   VALUES ('<uuid>', 'TRANSFER', 7);            -- duplicado => ya se proceso
--
--   -- Las filas se tocan SIEMPRE en orden ascendente de location_id
--   -- (10 antes que 20), sin importar cual es origen y cual destino.
--   UPDATE stock
--      SET quantity = quantity - 5, version = version + 1
--    WHERE location_id = 10 AND product_id = 42
--      AND quantity - reserved >= 5;             -- 0 filas => ROLLBACK (sin stock)
--
--   INSERT INTO stock (warehouse_id, location_id, product_id, quantity)
--   SELECT l.warehouse_id, l.id, 42, 5 FROM locations l
--    WHERE l.id = 20 AND l.is_active = 1
--   ON DUPLICATE KEY UPDATE quantity = stock.quantity + 5,
--                           version  = stock.version + 1;
--
--   INSERT INTO stock_movements (...) VALUES (... -5 ...), (... +5 ...);
-- COMMIT;
