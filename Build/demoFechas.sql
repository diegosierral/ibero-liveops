/*
@package IberoLiveOps
@summary Ajuste de fechas del festival y actividades para demostración
@author Kilian Ian Pérez García
@date 20 de noviembre de 2026
*/

USE ibero_liveops;

SET @modo_seguro = @@SQL_SAFE_UPDATES;
SET SQL_SAFE_UPDATES = 0;

UPDATE festivales
SET fecha = '2026-12-05'
WHERE fecha = '2026-11-28';

UPDATE actividades
SET fecha = '2026-12-05'
WHERE fecha = '2026-11-28';

UPDATE movimientos_recurso
SET fecha_entrega = DATE_ADD(fecha_entrega, INTERVAL 7 DAY),
    fecha_devolucion_prevista = DATE_ADD(fecha_devolucion_prevista, INTERVAL 7 DAY)
WHERE estado_movimiento IN ('ASIGNADO', 'ENTREGADO');

SET SQL_SAFE_UPDATES = @modo_seguro;

SELECT nombre, fecha FROM festivales ORDER BY fecha DESC;
SELECT fecha, COUNT(*) AS actividades FROM actividades GROUP BY fecha;
