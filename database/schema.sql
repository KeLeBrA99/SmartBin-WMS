-- SmartBin WMS - Esquema de la aplicacion actual (MySQL 8.0.16+)
-- Instalacion nueva:
--   mysql -u root -p -e "CREATE DATABASE smartbin_wms CHARACTER SET utf8mb4"
--   mysql -u root -p smartbin_wms < database/schema.sql
-- Si YA tienes la base creada, usa database/migracion_001_integridad.sql

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
    id             INT NOT NULL AUTO_INCREMENT,
    sku            VARCHAR(60)  NOT NULL,
    nombre         VARCHAR(200) NOT NULL,
    categoria_id   INT NULL,
    precio_compra  DECIMAL(12,2) NOT NULL DEFAULT 0,
    stock_minimo   INT NOT NULL DEFAULT 5,
    PRIMARY KEY (id),
    UNIQUE KEY uq_productos_sku (sku),
    KEY ix_productos_categoria (categoria_id),
    CONSTRAINT fk_productos_categoria FOREIGN KEY (categoria_id) REFERENCES categorias (id),
    CONSTRAINT chk_productos_precio CHECK (precio_compra >= 0),
    CONSTRAINT chk_productos_minimo CHECK (stock_minimo >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ubicaciones (
    id      INT NOT NULL AUTO_INCREMENT,
    codigo  VARCHAR(40) NOT NULL,
    tipo    VARCHAR(30) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ubicaciones_codigo (codigo)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventario (
    ubicacion_id  INT NOT NULL,
    producto_id   INT NOT NULL,
    cantidad      INT NOT NULL DEFAULT 0,
    -- Una sola fila por (ubicacion, producto): de esto dependen el upsert y
    -- el descuento atomico de las transferencias.
    PRIMARY KEY (ubicacion_id, producto_id),
    -- Stock total por producto resuelto solo con el indice.
    KEY ix_inventario_producto (producto_id, cantidad),
    CONSTRAINT fk_inventario_ubicacion FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones (id),
    CONSTRAINT fk_inventario_producto  FOREIGN KEY (producto_id)  REFERENCES productos (id),
    -- Ultima linea de defensa: la base rechaza stock negativo.
    CONSTRAINT chk_inventario_cantidad CHECK (cantidad >= 0)
) ENGINE=InnoDB;
