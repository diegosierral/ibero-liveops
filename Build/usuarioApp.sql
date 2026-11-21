/*
@package IberoLiveOps
@summary Creación de usuario MySQL con privilegios mínimos para la aplicación
@author Kilian Ian Pérez García
@date 20 de noviembre de 2026
*/

CREATE USER IF NOT EXISTS 'liveops_app'@'localhost' IDENTIFIED BY 'CAMBIAR_ESTA_CLAVE';

GRANT SELECT, INSERT, UPDATE, EXECUTE ON ibero_liveops.* TO 'liveops_app'@'localhost';

FLUSH PRIVILEGES;
