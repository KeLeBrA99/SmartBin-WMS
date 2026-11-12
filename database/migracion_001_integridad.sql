-- SmartBin WMS - Migracion 001 para una base de datos YA EXISTENTE.
-- Haz una copia antes:  mysqldump -u root -p smartbin_wms > respaldo.sql
-- Ejecuta:              mysql -u root -p smartbin_wms < database/migracion_001_integridad.sql
-- El backend no arranca hasta que los pasos 2 y 3 esten aplicados.

-- 1) Unifica filas repetidas de inventario (misma ubicacion y producto),
--    sumando sus cantidades. Si no hay repetidas, no cambia nada.
--    Una cantidad negativa (dato invalido) queda en 0. Si algo falla a
--    mitad de camino, los datos siguen en la tabla `inventario_unificado`.
CREATE TABLE inventario_unificado AS
    SELECT ubicacion_id, producto_id, SUM(cantidad) AS cantidad
    FROM inventario
    GROUP BY ubicacion_id, producto_id;
DELETE FROM inventario;
INSERT INTO inventario (ubicacion_id, producto_id, cantidad)
    SELECT ubicacion_id, producto_id, GREATEST(cantidad, 0) FROM inventario_unificado;
DROP TABLE inventario_unificado;

-- 2) Una sola fila por (ubicacion, producto).
ALTER TABLE inventario
    ADD UNIQUE KEY uq_inventario_ubi_prod (ubicacion_id, producto_id);

-- 3) Espacio para el nuevo hash de contrasenas (PBKDF2). Las cuentas
--    actuales siguen funcionando y se actualizan solas al iniciar sesion.
ALTER TABLE usuarios MODIFY password VARCHAR(255) NOT NULL;

-- 4) La base rechaza stock negativo.
ALTER TABLE inventario
    ADD CONSTRAINT chk_inventario_cantidad CHECK (cantidad >= 0);

-- 5) Indice para el stock total por producto.
ALTER TABLE inventario ADD KEY ix_inventario_producto (producto_id, cantidad);
