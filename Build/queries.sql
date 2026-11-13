/*
@package IberoLiveOps
@summary Consultas y reportes del sistema
@author Nicolás Martínez Viale
@date 12 de noviembre de 2026
*/

USE ibero_liveops;

SET @id_usuario = 11;
SET @id_actividad = 1;
SET @id_incidencia = 1;
SET @fecha_dia = '2026-11-28';

/* Ediciones del festival */
SELECT id_festival, nombre, fecha
FROM festivales
ORDER BY fecha DESC;

/* Fecha de la edicion mas reciente */
SELECT MAX(fecha) AS fecha_festival
FROM festivales;

/* Reporte 8.1 Ocupacion de actividades */
SELECT a.id_actividad, a.nombre_actividad, c.nombre AS categoria, a.fecha,
a.hora_inicio, a.hora_fin, z.nombre AS zona, e.nombre AS espacio, a.cupo,
(SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad = a.id_actividad AND r.estado_reservacion = 'CONFIRMADA') AS confirmadas,
(SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad = a.id_actividad AND r.estado_reservacion = 'ESPERA') AS en_espera,
fn_cupo_disponible(a.id_actividad) AS disponibles,
ROUND((a.cupo - fn_cupo_disponible(a.id_actividad)) * 100 / a.cupo, 1) AS pct_ocupacion,
a.estado_actividad
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
ORDER BY a.fecha, a.hora_inicio, a.id_actividad;

/* Totales del reporte 8.1 por estado de actividad */
SELECT a.estado_actividad, COUNT(*) AS actividades, SUM(a.cupo) AS cupo_total,
SUM(a.cupo - fn_cupo_disponible(a.id_actividad)) AS confirmadas,
SUM((SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad = a.id_actividad AND r.estado_reservacion = 'ESPERA')) AS en_espera
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
GROUP BY a.estado_actividad;

/* Reporte 8.2 Demanda y reservaciones */
SELECT a.id_actividad, a.nombre_actividad, a.fecha, a.hora_inicio,
COUNT(r.id_reservacion) AS solicitudes,
(SELECT COUNT(*) FROM reservaciones r1 WHERE r1.id_actividad = a.id_actividad AND r1.estado_reservacion = 'CONFIRMADA') AS confirmadas,
(SELECT COUNT(*) FROM reservaciones r2 WHERE r2.id_actividad = a.id_actividad AND r2.estado_reservacion = 'ESPERA') AS en_espera,
(SELECT COUNT(*) FROM reservaciones r3 WHERE r3.id_actividad = a.id_actividad AND r3.estado_reservacion = 'CANCELADA') AS canceladas,
MIN(r.fecha_solicitud) AS primera_solicitud,
MAX(r.fecha_solicitud) AS ultima_solicitud
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
LEFT JOIN reservaciones r ON r.id_actividad = a.id_actividad
GROUP BY a.id_actividad, a.nombre_actividad, a.fecha, a.hora_inicio
ORDER BY solicitudes DESC, confirmadas DESC, a.fecha, a.hora_inicio;

/* Totales del reporte 8.2 por estado de reservacion */
SELECT r.estado_reservacion, COUNT(*) AS reservaciones
FROM reservaciones r
JOIN actividades a ON a.id_actividad = r.id_actividad
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
GROUP BY r.estado_reservacion;

/* Reporte 8.3 Inventario y existencia de recursos */
SELECT r.id_recurso, cr.nombre AS categoria, r.nombre_recurso, r.cantidad_total,
fn_recurso_disponible(r.id_recurso) AS en_almacen,
r.cantidad_total - fn_recurso_disponible(r.id_recurso) AS asignadas_o_entregadas,
r.ubicacion, r.estado_recurso
FROM recursos r
JOIN categorias_recurso cr ON cr.id_categoria_recurso = r.id_categoria_recurso
ORDER BY cr.nombre, r.nombre_recurso;

/* Totales del reporte 8.3 por estado de recurso */
SELECT r.estado_recurso, COUNT(*) AS recursos, SUM(r.cantidad_total) AS unidades_total,
SUM(fn_recurso_disponible(r.id_recurso)) AS en_almacen,
SUM(r.cantidad_total - fn_recurso_disponible(r.id_recurso)) AS asignadas_o_entregadas
FROM recursos r
JOIN categorias_recurso cr ON cr.id_categoria_recurso = r.id_categoria_recurso
GROUP BY r.estado_recurso;

/* Reporte 8.3 Asignaciones activas de recursos */
SELECT m.id_movimiento, r.nombre_recurso, cr.nombre AS categoria,
a.nombre_actividad, u.nombre_mostrar AS responsable, m.cantidad_asignada,
m.fecha_entrega, m.fecha_devolucion_prevista, m.estado_movimiento
FROM movimientos_recurso m
JOIN recursos r ON r.id_recurso = m.id_recurso
JOIN categorias_recurso cr ON cr.id_categoria_recurso = r.id_categoria_recurso
JOIN actividades a ON a.id_actividad = m.id_actividad
JOIN usuarios u ON u.id_usuario = m.id_responsable
WHERE m.estado_movimiento IN ('ASIGNADO', 'ENTREGADO')
ORDER BY m.fecha_devolucion_prevista, m.id_movimiento;

/* Totales de asignaciones activas por estado de movimiento */
SELECT m.estado_movimiento, COUNT(*) AS movimientos, SUM(m.cantidad_asignada) AS unidades
FROM movimientos_recurso m
JOIN recursos r ON r.id_recurso = m.id_recurso
WHERE m.estado_movimiento IN ('ASIGNADO', 'ENTREGADO')
GROUP BY m.estado_movimiento;

/* Reporte 8.4 Incidencias y tiempo de atencion */
SELECT i.id_incidencia, ti.nombre AS tipo, i.severidad, i.estado_incidencia,
z.nombre AS zona, i.ubicacion, a.nombre_actividad,
ur.nombre_mostrar AS reportada_por, ua.nombre_mostrar AS responsable,
i.fecha_creacion, i.fecha_resolucion, i.fecha_cierre,
TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion) AS min_atencion
FROM incidencias i
JOIN tipos_incidencia ti ON ti.id_tipo_incidencia = i.id_tipo_incidencia
JOIN zonas z ON z.id_zona = i.id_zona
JOIN usuarios ur ON ur.id_usuario = i.id_reportado_por
LEFT JOIN usuarios ua ON ua.id_usuario = i.id_asignado_a
LEFT JOIN actividades a ON a.id_actividad = i.id_actividad
ORDER BY FIELD(i.severidad, 'CRITICA', 'ALTA', 'MEDIA', 'BAJA'), i.fecha_creacion, i.id_incidencia;

/* Totales del reporte 8.4 por estado */
SELECT i.estado_incidencia, COUNT(*) AS incidencias
FROM incidencias i
JOIN zonas z ON z.id_zona = i.id_zona
GROUP BY i.estado_incidencia;

/* Totales del reporte 8.4 por severidad y promedio de atencion */
SELECT i.severidad, COUNT(*) AS incidencias,
ROUND(AVG(TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion)), 1) AS min_prom_atencion
FROM incidencias i
JOIN zonas z ON z.id_zona = i.id_zona
GROUP BY i.severidad;

/* Tiempo promedio de atencion general */
SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion)), 1) AS min_prom_atencion
FROM incidencias i
JOIN zonas z ON z.id_zona = i.id_zona;

/* Menu 4.6 Consulta global de reservaciones */
SELECT r.id_reservacion, u.nombre_usuario AS participante, a.nombre_actividad,
a.fecha, a.hora_inicio, a.hora_fin, z.nombre AS zona,
r.estado_reservacion, r.posicion_espera, r.fecha_solicitud, r.fecha_cancelacion
FROM reservaciones r
JOIN usuarios u ON u.id_usuario = r.id_participante
JOIN actividades a ON a.id_actividad = r.id_actividad
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
ORDER BY a.fecha, a.hora_inicio, a.id_actividad, r.fecha_solicitud;

/* Totales de consulta global de reservaciones por estado */
SELECT r.estado_reservacion, COUNT(*) AS reservaciones
FROM reservaciones r
JOIN usuarios u ON u.id_usuario = r.id_participante
JOIN actividades a ON a.id_actividad = r.id_actividad
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
GROUP BY r.estado_reservacion;

/* Menu 5.1 Resumen operativo de actividades del dia */
SELECT COUNT(*) AS actividades_del_dia
FROM actividades a
JOIN espacios e ON e.id_espacio = a.id_espacio
WHERE a.estado_actividad = 'PUBLICADA'
AND a.fecha = @fecha_dia;

/* Menu 5.1 Movimientos de recursos pendientes del dia */
SELECT m.estado_movimiento, COUNT(*) AS movimientos
FROM movimientos_recurso m
JOIN actividades a ON a.id_actividad = m.id_actividad
JOIN espacios e ON e.id_espacio = a.id_espacio
WHERE a.estado_actividad = 'PUBLICADA'
AND a.fecha = @fecha_dia
AND m.estado_movimiento IN ('ASIGNADO', 'ENTREGADO')
GROUP BY m.estado_movimiento;

/* Menu 5.1 Incidencias activas asignadas al operador */
SELECT i.estado_incidencia, COUNT(*) AS incidencias
FROM incidencias i
WHERE i.id_asignado_a = @id_usuario
AND i.estado_incidencia IN ('ASIGNADA', 'EN_ATENCION')
GROUP BY i.estado_incidencia;

/* Incidencias criticas asignadas al operador */
SELECT COUNT(*) AS criticas
FROM incidencias i
WHERE i.id_asignado_a = @id_usuario
AND i.estado_incidencia IN ('ASIGNADA', 'EN_ATENCION')
AND i.severidad = 'CRITICA';

/* Incidencias activas vencidas del operador */
SELECT COUNT(*) AS vencidas
FROM incidencias i
WHERE i.id_asignado_a = @id_usuario
AND i.estado_incidencia IN ('ASIGNADA', 'EN_ATENCION')
AND TIMESTAMPDIFF(MINUTE, i.fecha_creacion, NOW()) > 60;

/* Reporte 8.6 Agenda operativa del dia */
SELECT a.id_actividad, a.hora_inicio, a.nombre_actividad, c.nombre AS categoria,
z.nombre AS zona, e.nombre AS espacio, a.cupo,
a.cupo - fn_cupo_disponible(a.id_actividad) AS confirmadas,
fn_cupo_disponible(a.id_actividad) AS disponibles,
(SELECT COUNT(*) FROM movimientos_recurso m WHERE m.id_actividad = a.id_actividad AND m.estado_movimiento IN ('ASIGNADO', 'ENTREGADO')) AS recursos_pendientes,
(SELECT COUNT(*) FROM incidencias i WHERE i.id_actividad = a.id_actividad AND i.estado_incidencia <> 'CERRADA') AS incidencias_abiertas,
a.estado_actividad
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
WHERE a.fecha = @fecha_dia
ORDER BY a.hora_inicio, a.id_actividad;

/* Totales de agenda operativa del dia */
SELECT COUNT(*) AS actividades,
SUM((SELECT COUNT(*) FROM movimientos_recurso m WHERE m.id_actividad = a.id_actividad AND m.estado_movimiento IN ('ASIGNADO', 'ENTREGADO'))) AS recursos_pendientes,
SUM((SELECT COUNT(*) FROM incidencias i WHERE i.id_actividad = a.id_actividad AND i.estado_incidencia <> 'CERRADA')) AS incidencias_abiertas
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
WHERE a.fecha = @fecha_dia;

/* Menu 5.2 Lista de participantes por actividad */
SELECT u.nombre_usuario, u.nombre_mostrar, r.estado_reservacion,
r.posicion_espera, r.fecha_solicitud
FROM reservaciones r
JOIN usuarios u ON u.id_usuario = r.id_participante
WHERE r.id_actividad = @id_actividad
AND r.estado_reservacion IN ('CONFIRMADA', 'ESPERA')
ORDER BY r.estado_reservacion, r.posicion_espera, r.fecha_solicitud;

/* Reporte 8.4 Incidencias asignadas al usuario de Operaciones */
SELECT i.id_incidencia, ti.nombre AS tipo, i.severidad, i.estado_incidencia,
z.nombre AS zona, i.ubicacion, a.nombre_actividad,
ur.nombre_mostrar AS reportada_por,
i.fecha_creacion, i.fecha_resolucion, i.fecha_cierre,
TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion) AS min_atencion
FROM incidencias i
JOIN tipos_incidencia ti ON ti.id_tipo_incidencia = i.id_tipo_incidencia
JOIN zonas z ON z.id_zona = i.id_zona
JOIN usuarios ur ON ur.id_usuario = i.id_reportado_por
LEFT JOIN actividades a ON a.id_actividad = i.id_actividad
WHERE i.id_asignado_a = @id_usuario
ORDER BY FIELD(i.severidad, 'CRITICA', 'ALTA', 'MEDIA', 'BAJA'), i.fecha_creacion, i.id_incidencia;

/* Totales de incidencias de Operaciones por estado */
SELECT i.estado_incidencia, COUNT(*) AS incidencias
FROM incidencias i
WHERE i.id_asignado_a = @id_usuario
GROUP BY i.estado_incidencia;

/* Totales de incidencias de Operaciones por severidad */
SELECT i.severidad, COUNT(*) AS incidencias,
ROUND(AVG(TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion)), 1) AS min_prom_atencion
FROM incidencias i
WHERE i.id_asignado_a = @id_usuario
GROUP BY i.severidad;

/* Historial de cambios de una incidencia */
SELECT h.id_historial, h.fecha_cambio, u.nombre_mostrar AS autor,
h.estado_anterior, h.estado_nuevo, h.accion,
(SELECT MAX(h2.fecha_cambio) FROM historial_incidencias h2 WHERE h2.id_incidencia = h.id_incidencia AND h2.id_historial < h.id_historial) AS cambio_anterior
FROM historial_incidencias h
JOIN usuarios u ON u.id_usuario = h.id_autor
JOIN incidencias i ON i.id_incidencia = h.id_incidencia
WHERE h.id_incidencia = @id_incidencia
ORDER BY h.id_historial;

/* Menu 6.1 Consultar agenda de actividades publicadas */
SELECT a.id_actividad, a.nombre_actividad, c.nombre AS categoria, a.fecha,
a.hora_inicio, a.hora_fin, z.nombre AS zona, e.nombre AS espacio, a.cupo,
fn_cupo_disponible(a.id_actividad) AS lugares_disponibles
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
WHERE a.estado_actividad = 'PUBLICADA'
ORDER BY a.fecha, a.hora_inicio, a.id_actividad;

/* Detalle de una actividad publicada */
SELECT a.id_actividad, a.nombre_actividad, a.descripcion, c.nombre AS categoria,
a.fecha, a.hora_inicio, a.hora_fin, z.nombre AS zona, e.nombre AS espacio,
a.cupo, fn_cupo_disponible(a.id_actividad) AS lugares_disponibles
FROM actividades a
JOIN categorias_actividad c ON c.id_categoria = a.id_categoria
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
WHERE a.id_actividad = @id_actividad
AND a.estado_actividad = 'PUBLICADA';

/* Menu 6.3 y Reporte 8.7 Historial personal de reservaciones */
SELECT r.id_reservacion, a.nombre_actividad, a.fecha, a.hora_inicio, a.hora_fin,
z.nombre AS zona, e.nombre AS espacio, r.estado_reservacion,
r.posicion_espera, r.fecha_solicitud, r.fecha_cancelacion
FROM reservaciones r
JOIN actividades a ON a.id_actividad = r.id_actividad
JOIN espacios e ON e.id_espacio = a.id_espacio
JOIN zonas z ON z.id_zona = e.id_zona
WHERE r.id_participante = @id_usuario
ORDER BY r.fecha_solicitud DESC, r.id_reservacion DESC;

/* Totales del historial personal de reservaciones */
SELECT r.estado_reservacion, COUNT(*) AS reservaciones
FROM reservaciones r
JOIN actividades a ON a.id_actividad = r.id_actividad
WHERE r.id_participante = @id_usuario
GROUP BY r.estado_reservacion;

/* Menu 6.5 y Reporte 8.8 Seguimiento de incidencias propias */
SELECT i.id_incidencia, ti.nombre AS tipo, i.severidad, i.estado_incidencia,
i.ubicacion, a.nombre_actividad, i.fecha_creacion, i.fecha_actualizacion
FROM incidencias i
JOIN tipos_incidencia ti ON ti.id_tipo_incidencia = i.id_tipo_incidencia
LEFT JOIN actividades a ON a.id_actividad = i.id_actividad
WHERE i.id_reportado_por = @id_usuario
ORDER BY i.fecha_creacion DESC, i.id_incidencia DESC;

/* Totales de incidencias propias por estado */
SELECT i.estado_incidencia, COUNT(*) AS incidencias
FROM incidencias i
WHERE i.id_reportado_por = @id_usuario
GROUP BY i.estado_incidencia;

/* Historial cronologico de una incidencia propia */
SELECT h.fecha_cambio, h.estado_anterior, h.estado_nuevo, h.accion
FROM historial_incidencias h
JOIN incidencias i ON i.id_incidencia = h.id_incidencia
WHERE h.id_incidencia = @id_incidencia
AND i.id_reportado_por = @id_usuario
ORDER BY h.fecha_cambio, h.id_historial;