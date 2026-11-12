-- SmartBin WMS - Esquema de la aplicacion (MySQL 8.0.16+)
-- No hace falta ejecutarlo a mano: `python preparar_bd.py` crea la base,
-- aplica este archivo y actualiza las bases creadas con versiones anteriores.

CREATE TABLE IF NOT EXISTS usuarios (
    id          INT NOT NULL AUTO_INCREMENT,
    usuario     VARCHAR(50)  NOT NULL,
    password    VARCHAR(255) NOT NULL,          -- hash PBKDF2, nunca texto plano
    nombre      VARCHAR(120) NOT NULL,
    rol         ENUM('admin','operario') NOT NULL DEFAULT 'operario',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuarios_usuario (usuario)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categorias (
    id           INT NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(80)  NOT NULL,
    descripcion  VARCHAR(255) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_categorias_nombre (nombre)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS productos (
    id              INT NOT NULL AUTO_INCREMENT,
    sku             VARCHAR(60)  NOT NULL,
    nombre          VARCHAR(200) NOT NULL,
    categoria_id    INT NULL,
    precio_compra   DECIMAL(12,2) NOT NULL DEFAULT 0,
    stock_minimo    INT NOT NULL DEFAULT 5,
    -- Parametros de reabastecimiento que usa el calculo de reorden
    lead_time_dias  DECIMAL(6,2) NOT NULL DEFAULT 7.00,
    nivel_servicio  DECIMAL(4,3) NOT NULL DEFAULT 0.950,
    PRIMARY KEY (id),
    UNIQUE KEY uq_productos_sku (sku),
    KEY ix_productos_categoria (categoria_id),
    CONSTRAINT fk_productos_categoria FOREIGN KEY (categoria_id) REFERENCES categorias (id),
    CONSTRAINT chk_productos_precio CHECK (precio_compra >= 0),
    CONSTRAINT chk_productos_minimo CHECK (stock_minimo >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bodegas (
    id          INT NOT NULL AUTO_INCREMENT,
    codigo      VARCHAR(20)  NOT NULL,
    nombre      VARCHAR(120) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bodegas_codigo (codigo)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ubicaciones (
    id         INT NOT NULL AUTO_INCREMENT,
    bodega_id  INT NOT NULL DEFAULT 1,
    codigo     VARCHAR(40) NOT NULL,
    tipo       VARCHAR(30) NOT NULL,
    PRIMARY KEY (id),
    -- El mismo codigo (A-01-01) puede repetirse en bodegas distintas
    UNIQUE KEY uq_ubicaciones_bodega_codigo (bodega_id, codigo),
    CONSTRAINT fk_ubicaciones_bodega FOREIGN KEY (bodega_id) REFERENCES bodegas (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventario (
    ubicacion_id  INT NOT NULL,
    producto_id   INT NOT NULL,
    cantidad      INT NOT NULL DEFAULT 0,
    -- Una sola fila por (ubicacion, producto): de esto dependen el upsert y
    -- el descuento atomico de salidas y transferencias.
    PRIMARY KEY (ubicacion_id, producto_id),
    -- Stock total por producto resuelto solo con el indice.
    KEY ix_inventario_producto (producto_id, cantidad),
    CONSTRAINT fk_inventario_ubicacion FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones (id),
    CONSTRAINT fk_inventario_producto  FOREIGN KEY (producto_id)  REFERENCES productos (id),
    -- Ultima linea de defensa: la base rechaza stock negativo.
    CONSTRAINT chk_inventario_cantidad CHECK (cantidad >= 0)
) ENGINE=InnoDB;

-- Libro mayor: una fila por cada cambio de saldo, escrita en la MISMA
-- transaccion que modifica `inventario`. Solo se inserta, nunca se edita.
-- Una transferencia genera dos filas (delta negativo y positivo) con el
-- mismo operacion_id. Sin llaves foraneas a proposito: el historial se
-- conserva aunque despues se elimine un producto o una ubicacion.
CREATE TABLE IF NOT EXISTS movimientos (
    id            BIGINT NOT NULL AUTO_INCREMENT,
    operacion_id  CHAR(36) NOT NULL,
    tipo          ENUM('ENTRADA','SALIDA','TRANSFERENCIA','AJUSTE') NOT NULL,
    bodega_id     INT NOT NULL,
    ubicacion_id  INT NOT NULL,
    producto_id   INT NOT NULL,
    delta         INT NOT NULL,                 -- con signo
    saldo         INT NOT NULL,                 -- saldo de la ubicacion tras el movimiento
    usuario_id    INT NULL,
    referencia    VARCHAR(80) NULL,             -- pedido, remision, motivo
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_mov_operacion (operacion_id),
    -- Demanda para el calculo de reorden: filtra tipo y fecha, agrupa por
    -- bodega y producto, y lee `delta` sin tocar la tabla (covering).
    KEY ix_mov_demanda (tipo, created_at, bodega_id, producto_id, delta),
    -- Kardex de un producto en una bodega.
    KEY ix_mov_kardex (bodega_id, producto_id, created_at)
) ENGINE=InnoDB;
