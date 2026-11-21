/*
@package IberoLiveOps
@summary Cifrado de contraseñas de usuarios con SHA-256
@author Kilian Ian Pérez García
@date 20 de noviembre de 2026
*/

USE ibero_liveops;

SET @modo_seguro = @@SQL_SAFE_UPDATES;
SET SQL_SAFE_UPDATES = 0;

UPDATE usuarios
SET contrasena = SHA2(CONCAT(nombre_usuario, '$', 'Liveops#2026'), 256)
WHERE id_usuario > 0;

SET SQL_SAFE_UPDATES = @modo_seguro;

SELECT perfil, estado_cuenta, COUNT(*) AS cuentas, MIN(CHAR_LENGTH(contrasena)) AS longitud_hash
FROM usuarios
GROUP BY perfil, estado_cuenta;
