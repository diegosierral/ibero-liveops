/*
@package IberoLiveOps
@summary Creación de funciones, procedimientos almacenados y triggers
@author Karen Arumil Lima Uranga
@date 9 de noviembre de 2026
*/

USE ibero_liveops;

DROP FUNCTION IF EXISTS fn_cupo_disponible;
DROP FUNCTION IF EXISTS fn_recurso_disponible;
DROP PROCEDURE IF EXISTS sp_crear_reservacion;
DROP PROCEDURE IF EXISTS sp_cancelar_reservacion;
DROP PROCEDURE IF EXISTS sp_asignar_recurso;
DROP PROCEDURE IF EXISTS sp_registrar_devolucion;
DROP PROCEDURE IF EXISTS sp_registrar_incidencia;
DROP PROCEDURE IF EXISTS sp_cambiar_estado_incidencia;
DROP TRIGGER IF EXISTS trg_historial_no_update;
DROP TRIGGER IF EXISTS trg_historial_no_delete;
DROP TRIGGER IF EXISTS trg_reservacion_no_delete;

DELIMITER //

CREATE FUNCTION fn_cupo_disponible(p_id_actividad INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE v_cupo INT;
    DECLARE v_confirmadas INT;

    SELECT cupo INTO v_cupo
    FROM actividades
    WHERE id_actividad = p_id_actividad;

    IF v_cupo IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT COUNT(*) INTO v_confirmadas
    FROM reservaciones
    WHERE id_actividad = p_id_actividad
      AND estado_reservacion = 'CONFIRMADA';

    RETURN GREATEST(v_cupo - v_confirmadas, 0);
END //

CREATE FUNCTION fn_recurso_disponible(p_id_recurso INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE v_total INT;
    DECLARE v_fuera INT;

    SELECT cantidad_total INTO v_total
    FROM recursos
    WHERE id_recurso = p_id_recurso;

    IF v_total IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT COALESCE(SUM(cantidad_asignada), 0) INTO v_fuera
    FROM movimientos_recurso
    WHERE id_recurso = p_id_recurso
      AND estado_movimiento IN ('ASIGNADO', 'ENTREGADO');

    RETURN GREATEST(v_total - v_fuera, 0);
END //

CREATE PROCEDURE sp_crear_reservacion(
    IN  p_id_participante INT,
    IN  p_id_actividad    INT,
    OUT p_id_reservacion  INT,
    OUT p_estado          VARCHAR(20),
    OUT p_posicion        INT
)
BEGIN
    DECLARE v_perfil VARCHAR(20);
    DECLARE v_estado_cuenta VARCHAR(15);
    DECLARE v_cupo INT;
    DECLARE v_estado_act VARCHAR(20);
    DECLARE v_fecha DATE;
    DECLARE v_inicio TIME;
    DECLARE v_fin TIME;
    DECLARE v_confirmadas INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT perfil, estado_cuenta INTO v_perfil, v_estado_cuenta
    FROM usuarios
    WHERE id_usuario = p_id_participante;

    IF v_perfil IS NULL OR v_perfil <> 'PARTICIPANTE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: solo un participante puede reservar';
    END IF;
    IF v_estado_cuenta <> 'ACTIVA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cuenta del participante esta inactiva';
    END IF;

    SELECT cupo, estado_actividad, fecha, hora_inicio, hora_fin
    INTO v_cupo, v_estado_act, v_fecha, v_inicio, v_fin
    FROM actividades
    WHERE id_actividad = p_id_actividad
    FOR UPDATE;

    IF v_cupo IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Actividad no encontrada';
    END IF;
    IF v_estado_act <> 'PUBLICADA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La actividad esta cancelada o finalizada y no acepta reservaciones';
    END IF;
    IF TIMESTAMP(v_fecha, v_inicio) <= NOW() THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La actividad ya comenzo o ya paso';
    END IF;

    IF EXISTS (SELECT 1 FROM reservaciones
               WHERE id_participante = p_id_participante
                 AND id_actividad = p_id_actividad
                 AND estado_reservacion IN ('CONFIRMADA', 'ESPERA')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Registro duplicado: ya tienes una reservacion activa en esta actividad';
    END IF;

    IF EXISTS (SELECT 1
               FROM reservaciones r
               JOIN actividades a ON a.id_actividad = r.id_actividad
               WHERE r.id_participante = p_id_participante
                 AND r.estado_reservacion = 'CONFIRMADA'
                 AND a.fecha = v_fecha
                 AND a.hora_inicio < v_fin
                 AND a.hora_fin > v_inicio) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Conflicto de horario con otra reservacion confirmada';
    END IF;

    SELECT COUNT(*) INTO v_confirmadas
    FROM reservaciones
    WHERE id_actividad = p_id_actividad
      AND estado_reservacion = 'CONFIRMADA';

    IF v_confirmadas < v_cupo THEN
        SET p_estado = 'CONFIRMADA';
        SET p_posicion = NULL;
    ELSE
        SET p_estado = 'ESPERA';
        SELECT COALESCE(MAX(posicion_espera), 0) + 1 INTO p_posicion
        FROM reservaciones
        WHERE id_actividad = p_id_actividad
          AND estado_reservacion = 'ESPERA';
    END IF;

    INSERT INTO reservaciones (id_participante, id_actividad, fecha_solicitud,
                               estado_reservacion, posicion_espera, fecha_cancelacion)
    VALUES (p_id_participante, p_id_actividad, NOW(), p_estado, p_posicion, NULL);

    SET p_id_reservacion = LAST_INSERT_ID();

    COMMIT;
END //

CREATE PROCEDURE sp_cancelar_reservacion(
    IN  p_id_participante INT,
    IN  p_id_reservacion  INT,
    OUT p_id_promovida    INT
)
BEGIN
    DECLARE v_dueno INT;
    DECLARE v_id_actividad INT;
    DECLARE v_estado VARCHAR(20);
    DECLARE v_posicion INT;
    DECLARE v_cupo INT;
    DECLARE v_fecha DATE;
    DECLARE v_inicio TIME;
    DECLARE v_fin TIME;
    DECLARE v_confirmadas INT;
    DECLARE v_pos_promovida INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_id_promovida = NULL;

    START TRANSACTION;

    SELECT id_actividad INTO v_id_actividad
    FROM reservaciones
    WHERE id_reservacion = p_id_reservacion;

    IF v_id_actividad IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reservacion no encontrada';
    END IF;

    SELECT cupo, fecha, hora_inicio, hora_fin
    INTO v_cupo, v_fecha, v_inicio, v_fin
    FROM actividades
    WHERE id_actividad = v_id_actividad
    FOR UPDATE;

    SELECT id_participante, estado_reservacion, posicion_espera
    INTO v_dueno, v_estado, v_posicion
    FROM reservaciones
    WHERE id_reservacion = p_id_reservacion
    FOR UPDATE;

    IF v_dueno <> p_id_participante THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: la reservacion no te pertenece';
    END IF;
    IF v_estado = 'CANCELADA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La reservacion ya estaba cancelada';
    END IF;

    UPDATE reservaciones
    SET estado_reservacion = 'CANCELADA',
        posicion_espera = NULL,
        fecha_cancelacion = NOW()
    WHERE id_reservacion = p_id_reservacion;

    IF v_estado = 'ESPERA' THEN
        UPDATE reservaciones
        SET posicion_espera = posicion_espera - 1
        WHERE id_actividad = v_id_actividad
          AND estado_reservacion = 'ESPERA'
          AND posicion_espera > v_posicion;
    ELSE
        SELECT COUNT(*) INTO v_confirmadas
        FROM reservaciones
        WHERE id_actividad = v_id_actividad
          AND estado_reservacion = 'CONFIRMADA';

        IF v_confirmadas < v_cupo THEN
            SELECT r.id_reservacion, r.posicion_espera
            INTO p_id_promovida, v_pos_promovida
            FROM reservaciones r
            WHERE r.id_actividad = v_id_actividad
              AND r.estado_reservacion = 'ESPERA'
              AND NOT EXISTS (
                  SELECT 1
                  FROM reservaciones r2
                  JOIN actividades a2 ON a2.id_actividad = r2.id_actividad
                  WHERE r2.id_participante = r.id_participante
                    AND r2.estado_reservacion = 'CONFIRMADA'
                    AND a2.fecha = v_fecha
                    AND a2.hora_inicio < v_fin
                    AND a2.hora_fin > v_inicio)
            ORDER BY r.posicion_espera, r.fecha_solicitud
            LIMIT 1;

            IF p_id_promovida IS NOT NULL THEN
                UPDATE reservaciones
                SET estado_reservacion = 'CONFIRMADA',
                    posicion_espera = NULL
                WHERE id_reservacion = p_id_promovida;

                UPDATE reservaciones
                SET posicion_espera = posicion_espera - 1
                WHERE id_actividad = v_id_actividad
                  AND estado_reservacion = 'ESPERA'
                  AND posicion_espera > v_pos_promovida;
            END IF;
        END IF;
    END IF;

    COMMIT;
END //

CREATE PROCEDURE sp_asignar_recurso(
    IN  p_id_responsable            INT,
    IN  p_id_recurso                INT,
    IN  p_id_actividad              INT,
    IN  p_cantidad                  INT,
    IN  p_fecha_entrega             DATETIME,
    IN  p_fecha_devolucion_prevista DATETIME,
    IN  p_observaciones             VARCHAR(300),
    OUT p_id_movimiento             INT
)
BEGIN
    DECLARE v_perfil VARCHAR(20);
    DECLARE v_estado_cuenta VARCHAR(15);
    DECLARE v_estado_recurso VARCHAR(20);
    DECLARE v_estado_act VARCHAR(20);
    DECLARE v_disponible INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT perfil, estado_cuenta INTO v_perfil, v_estado_cuenta
    FROM usuarios
    WHERE id_usuario = p_id_responsable;

    IF v_perfil IS NULL OR v_perfil <> 'OPERACIONES' OR v_estado_cuenta <> 'ACTIVA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: solo Operaciones activa puede asignar recursos';
    END IF;
    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cantidad invalida: debe ser mayor que cero';
    END IF;
    IF p_fecha_devolucion_prevista <= p_fecha_entrega THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La devolucion prevista debe ser posterior a la entrega';
    END IF;

    SELECT estado_recurso INTO v_estado_recurso
    FROM recursos
    WHERE id_recurso = p_id_recurso
    FOR UPDATE;

    IF v_estado_recurso IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Recurso no encontrado';
    END IF;
    IF v_estado_recurso NOT IN ('DISPONIBLE', 'ASIGNADO') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Recurso no disponible: esta danado, perdido o en mantenimiento';
    END IF;

    SELECT estado_actividad INTO v_estado_act
    FROM actividades
    WHERE id_actividad = p_id_actividad;

    IF v_estado_act IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Actividad no encontrada';
    END IF;
    IF v_estado_act <> 'PUBLICADA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No se asignan recursos a actividades canceladas o finalizadas';
    END IF;

    IF EXISTS (SELECT 1 FROM movimientos_recurso
               WHERE id_recurso = p_id_recurso
                 AND id_actividad = p_id_actividad
                 AND estado_movimiento IN ('ASIGNADO', 'ENTREGADO')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Doble asignacion: el recurso ya tiene un movimiento activo en esta actividad';
    END IF;

    SET v_disponible = fn_recurso_disponible(p_id_recurso);
    IF p_cantidad > v_disponible THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Recurso no disponible: cantidad insuficiente';
    END IF;

    INSERT INTO movimientos_recurso (id_recurso, id_actividad, id_responsable, cantidad_asignada,
                                     cantidad_recibida, fecha_entrega, fecha_devolucion_prevista,
                                     fecha_devolucion_real, estado_movimiento, observaciones)
    VALUES (p_id_recurso, p_id_actividad, p_id_responsable, p_cantidad,
            NULL, p_fecha_entrega, p_fecha_devolucion_prevista,
            NULL, 'ASIGNADO', p_observaciones);

    SET p_id_movimiento = LAST_INSERT_ID();

    UPDATE recursos
    SET estado_recurso = 'ASIGNADO'
    WHERE id_recurso = p_id_recurso;

    COMMIT;
END //

CREATE PROCEDURE sp_registrar_devolucion(
    IN p_id_responsable    INT,
    IN p_id_movimiento     INT,
    IN p_cantidad_recibida INT,
    IN p_estado_final      VARCHAR(20),
    IN p_observaciones     VARCHAR(300)
)
BEGIN
    DECLARE v_perfil VARCHAR(20);
    DECLARE v_estado_cuenta VARCHAR(15);
    DECLARE v_id_recurso INT;
    DECLARE v_asignada INT;
    DECLARE v_estado_mov VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT perfil, estado_cuenta INTO v_perfil, v_estado_cuenta
    FROM usuarios
    WHERE id_usuario = p_id_responsable;

    IF v_perfil IS NULL OR v_perfil <> 'OPERACIONES' OR v_estado_cuenta <> 'ACTIVA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: solo Operaciones activa registra devoluciones';
    END IF;
    IF p_estado_final NOT IN ('DEVUELTO', 'DANADO', 'PERDIDO', 'MANTENIMIENTO') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Estado final invalido';
    END IF;
    IF p_estado_final <> 'DEVUELTO' AND (p_observaciones IS NULL OR TRIM(p_observaciones) = '') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Las observaciones son obligatorias para dano, perdida o mantenimiento';
    END IF;

    SELECT id_recurso, cantidad_asignada, estado_movimiento
    INTO v_id_recurso, v_asignada, v_estado_mov
    FROM movimientos_recurso
    WHERE id_movimiento = p_id_movimiento
    FOR UPDATE;

    IF v_id_recurso IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Movimiento no encontrado';
    END IF;
    IF v_estado_mov NOT IN ('ASIGNADO', 'ENTREGADO') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El movimiento ya fue cerrado';
    END IF;
    IF p_cantidad_recibida IS NULL OR p_cantidad_recibida < 0 OR p_cantidad_recibida > v_asignada THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cantidad recibida invalida';
    END IF;

    UPDATE movimientos_recurso
    SET cantidad_recibida = p_cantidad_recibida,
        fecha_devolucion_real = NOW(),
        estado_movimiento = p_estado_final,
        observaciones = COALESCE(p_observaciones, observaciones)
    WHERE id_movimiento = p_id_movimiento;

    IF p_estado_final = 'DEVUELTO' THEN
        IF NOT EXISTS (SELECT 1 FROM movimientos_recurso
                       WHERE id_recurso = v_id_recurso
                         AND estado_movimiento IN ('ASIGNADO', 'ENTREGADO')) THEN
            UPDATE recursos
            SET estado_recurso = 'DISPONIBLE'
            WHERE id_recurso = v_id_recurso
              AND estado_recurso = 'ASIGNADO';
        END IF;
    ELSE
        UPDATE recursos
        SET estado_recurso = p_estado_final,
            observaciones = p_observaciones
        WHERE id_recurso = v_id_recurso;
    END IF;

    COMMIT;
END //

CREATE PROCEDURE sp_registrar_incidencia(
    IN  p_id_usuario         INT,
    IN  p_id_tipo_incidencia INT,
    IN  p_id_zona            INT,
    IN  p_severidad          VARCHAR(15),
    IN  p_descripcion        VARCHAR(500),
    IN  p_ubicacion          VARCHAR(150),
    IN  p_id_actividad       INT,
    OUT p_id_incidencia      INT
)
BEGIN
    DECLARE v_estado_cuenta VARCHAR(15);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT estado_cuenta INTO v_estado_cuenta
    FROM usuarios
    WHERE id_usuario = p_id_usuario;

    IF v_estado_cuenta IS NULL OR v_estado_cuenta <> 'ACTIVA' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: cuenta inexistente o inactiva';
    END IF;
    IF p_descripcion IS NULL OR CHAR_LENGTH(TRIM(p_descripcion)) < 10 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La descripcion debe tener al menos 10 caracteres';
    END IF;
    IF p_ubicacion IS NULL OR TRIM(p_ubicacion) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La ubicacion es obligatoria';
    END IF;

    INSERT INTO incidencias (id_tipo_incidencia, id_zona, severidad, descripcion, ubicacion,
                             id_actividad, id_reportado_por, id_asignado_a, estado_incidencia,
                             accion_realizada, fecha_creacion, fecha_actualizacion,
                             fecha_resolucion, fecha_cierre)
    VALUES (p_id_tipo_incidencia, p_id_zona, p_severidad, TRIM(p_descripcion), TRIM(p_ubicacion),
            p_id_actividad, p_id_usuario, NULL, 'ABIERTA',
            NULL, NOW(), NOW(), NULL, NULL);

    SET p_id_incidencia = LAST_INSERT_ID();

    INSERT INTO historial_incidencias (id_incidencia, id_autor, estado_anterior, estado_nuevo, accion, fecha_cambio)
    VALUES (p_id_incidencia, p_id_usuario, NULL, 'ABIERTA', 'Registro inicial de incidencia', NOW());

    COMMIT;
END //

CREATE PROCEDURE sp_cambiar_estado_incidencia(
    IN p_id_usuario     INT,
    IN p_id_incidencia  INT,
    IN p_estado_nuevo   VARCHAR(20),
    IN p_id_asignado_a  INT,
    IN p_accion         VARCHAR(500)
)
BEGIN
    DECLARE v_perfil VARCHAR(20);
    DECLARE v_estado_cuenta VARCHAR(15);
    DECLARE v_estado_actual VARCHAR(20);
    DECLARE v_asignado INT;
    DECLARE v_accion_actual VARCHAR(500);
    DECLARE v_fecha_resolucion DATETIME;
    DECLARE v_perfil_resp VARCHAR(20);
    DECLARE v_estado_resp VARCHAR(15);
    DECLARE v_texto_historial VARCHAR(500);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT perfil, estado_cuenta INTO v_perfil, v_estado_cuenta
    FROM usuarios
    WHERE id_usuario = p_id_usuario;

    IF v_perfil IS NULL OR v_estado_cuenta <> 'ACTIVA' OR v_perfil = 'PARTICIPANTE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado';
    END IF;

    SELECT estado_incidencia, id_asignado_a, accion_realizada, fecha_resolucion
    INTO v_estado_actual, v_asignado, v_accion_actual, v_fecha_resolucion
    FROM incidencias
    WHERE id_incidencia = p_id_incidencia
    FOR UPDATE;

    IF v_estado_actual IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Incidencia no encontrada';
    END IF;

    IF v_perfil = 'OPERACIONES' AND (v_asignado IS NULL OR v_asignado <> p_id_usuario) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: la incidencia no esta asignada a ti';
    END IF;

    IF p_estado_nuevo = 'ASIGNADA' THEN
        IF v_perfil <> 'COORDINACION' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: solo Coordinacion asigna responsables';
        END IF;
        IF v_estado_actual NOT IN ('ABIERTA', 'ASIGNADA', 'EN_ATENCION') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No se puede asignar una incidencia resuelta o cerrada';
        END IF;

        SELECT perfil, estado_cuenta INTO v_perfil_resp, v_estado_resp
        FROM usuarios
        WHERE id_usuario = p_id_asignado_a;

        IF v_perfil_resp IS NULL OR v_perfil_resp <> 'OPERACIONES' OR v_estado_resp <> 'ACTIVA' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El responsable debe ser una cuenta de Operaciones activa';
        END IF;

        UPDATE incidencias
        SET id_asignado_a = p_id_asignado_a,
            estado_incidencia = 'ASIGNADA',
            fecha_actualizacion = NOW()
        WHERE id_incidencia = p_id_incidencia;

        SET v_texto_historial = COALESCE(p_accion, 'Asignacion de responsable');

    ELSEIF p_estado_nuevo = 'EN_ATENCION' THEN
        IF v_estado_actual <> 'ASIGNADA' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo una incidencia ASIGNADA puede pasar a EN_ATENCION';
        END IF;

        UPDATE incidencias
        SET estado_incidencia = 'EN_ATENCION',
            accion_realizada = COALESCE(p_accion, accion_realizada),
            fecha_actualizacion = NOW()
        WHERE id_incidencia = p_id_incidencia;

        SET v_texto_historial = COALESCE(p_accion, 'Inicio de atencion');

    ELSEIF p_estado_nuevo = 'RESUELTA' THEN
        IF v_estado_actual <> 'EN_ATENCION' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo una incidencia EN_ATENCION puede marcarse RESUELTA';
        END IF;
        IF p_accion IS NULL OR CHAR_LENGTH(TRIM(p_accion)) < 5 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Debes documentar la accion realizada (minimo 5 caracteres)';
        END IF;

        UPDATE incidencias
        SET estado_incidencia = 'RESUELTA',
            accion_realizada = TRIM(p_accion),
            fecha_resolucion = NOW(),
            fecha_actualizacion = NOW()
        WHERE id_incidencia = p_id_incidencia;

        SET v_texto_historial = TRIM(p_accion);

    ELSEIF p_estado_nuevo = 'CERRADA' THEN
        IF v_perfil <> 'COORDINACION' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Permiso denegado: solo Coordinacion cierra incidencias';
        END IF;
        IF v_estado_actual <> 'RESUELTA' OR v_asignado IS NULL
           OR v_accion_actual IS NULL OR v_fecha_resolucion IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No puede cerrarse: falta responsable, accion o resolucion';
        END IF;

        UPDATE incidencias
        SET estado_incidencia = 'CERRADA',
            fecha_cierre = NOW(),
            fecha_actualizacion = NOW()
        WHERE id_incidencia = p_id_incidencia;

        SET v_texto_historial = COALESCE(p_accion, 'Cierre autorizado por Coordinacion');

    ELSE
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Estado nuevo invalido';
    END IF;

    INSERT INTO historial_incidencias (id_incidencia, id_autor, estado_anterior, estado_nuevo, accion, fecha_cambio)
    VALUES (p_id_incidencia, p_id_usuario, v_estado_actual, p_estado_nuevo, v_texto_historial, NOW());

    COMMIT;
END //

CREATE TRIGGER trg_historial_no_update
BEFORE UPDATE ON historial_incidencias
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El historial de incidencias no puede modificarse';
END //

CREATE TRIGGER trg_historial_no_delete
BEFORE DELETE ON historial_incidencias
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El historial de incidencias no puede borrarse';
END //

CREATE TRIGGER trg_reservacion_no_delete
BEFORE DELETE ON reservaciones
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Las reservaciones no se borran; usa sp_cancelar_reservacion';
END //

DELIMITER ;