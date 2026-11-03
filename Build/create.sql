/*
@package IberoLiveOps
@summary Creación de base de datos
@author Diego Sierra Legorreta
@date 2 de noviembre de 2026
*/

DROP DATABASE IF EXISTS ibero_liveops;
CREATE DATABASE ibero_liveops;
USE ibero_liveops;

CREATE TABLE usuarios (
id_usuario INT AUTO_INCREMENT PRIMARY KEY,
nombre_usuario VARCHAR(30) NOT NULL UNIQUE,
nombre_mostrar VARCHAR(80) NOT NULL,
correo_ficticio VARCHAR(120) NOT NULL UNIQUE,
contrasena VARCHAR(255) NOT NULL,
perfil VARCHAR(20) NOT NULL,
estado_cuenta VARCHAR(15) NOT NULL,
fecha_registro DATETIME NOT NULL,
CHECK (perfil IN ('COORDINACION', 'OPERACIONES', 'PARTICIPANTE')),
CHECK (estado_cuenta IN ('ACTIVA', 'INACTIVA'))
);

CREATE TABLE festivales (
id_festival INT AUTO_INCREMENT PRIMARY KEY,
nombre VARCHAR(120) NOT NULL UNIQUE,
fecha DATE NOT NULL,
hora_inicio TIME NOT NULL,
hora_fin TIME NOT NULL,
CHECK (hora_fin > hora_inicio)
);

CREATE TABLE zonas (
id_zona INT AUTO_INCREMENT PRIMARY KEY,
id_festival INT NOT NULL,
nombre VARCHAR(100) NOT NULL,
descripcion VARCHAR(300) NOT NULL,
FOREIGN KEY (id_festival) REFERENCES festivales(id_festival) ON UPDATE CASCADE ON DELETE RESTRICT,
UNIQUE (id_festival, nombre)
);

CREATE TABLE espacios (
id_espacio INT AUTO_INCREMENT PRIMARY KEY,
id_zona INT NOT NULL,
nombre VARCHAR(100) NOT NULL,
ubicacion VARCHAR(150) NOT NULL,
aforo INT NOT NULL,
estado_espacio VARCHAR(20) NOT NULL,
FOREIGN KEY (id_zona) REFERENCES zonas(id_zona) ON UPDATE CASCADE ON DELETE RESTRICT,
UNIQUE (id_zona, nombre),
CHECK (aforo > 0),
CHECK (estado_espacio IN ('DISPONIBLE', 'NO_DISPONIBLE'))
);

CREATE TABLE categorias_actividad (
id_categoria INT AUTO_INCREMENT PRIMARY KEY,
nombre VARCHAR(80) NOT NULL UNIQUE,
descripcion VARCHAR(300) NOT NULL
);

CREATE TABLE actividades (
id_actividad INT AUTO_INCREMENT PRIMARY KEY,
id_categoria INT NOT NULL,
id_espacio INT NOT NULL,
nombre_actividad VARCHAR(120) NOT NULL,
descripcion VARCHAR(500) NOT NULL,
fecha DATE NOT NULL,
hora_inicio TIME NOT NULL,
hora_fin TIME NOT NULL,
cupo INT NOT NULL,
estado_actividad VARCHAR(20) NOT NULL,
FOREIGN KEY (id_categoria) REFERENCES categorias_actividad(id_categoria) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_espacio) REFERENCES espacios(id_espacio) ON UPDATE CASCADE ON DELETE RESTRICT,
CHECK (hora_fin > hora_inicio),
CHECK (cupo > 0),
CHECK (estado_actividad IN ('PUBLICADA', 'CANCELADA', 'FINALIZADA'))
);

CREATE TABLE reservaciones (
id_reservacion INT AUTO_INCREMENT PRIMARY KEY,
id_participante INT NOT NULL,
id_actividad INT NOT NULL,
fecha_solicitud DATETIME NOT NULL,
estado_reservacion VARCHAR(20) NOT NULL,
posicion_espera INT NULL,
fecha_cancelacion DATETIME NULL,
FOREIGN KEY (id_participante) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_actividad) REFERENCES actividades(id_actividad) ON UPDATE CASCADE ON DELETE RESTRICT,
CHECK (estado_reservacion IN ('CONFIRMADA', 'ESPERA', 'CANCELADA'))
);

CREATE TABLE categorias_recurso (
id_categoria_recurso INT AUTO_INCREMENT PRIMARY KEY,
nombre VARCHAR(80) NOT NULL UNIQUE,
descripcion VARCHAR(300) NOT NULL
);

CREATE TABLE recursos (
id_recurso INT AUTO_INCREMENT PRIMARY KEY,
id_categoria_recurso INT NOT NULL,
nombre_recurso VARCHAR(100) NOT NULL UNIQUE,
cantidad_total INT NOT NULL,
ubicacion VARCHAR(120) NOT NULL,
estado_recurso VARCHAR(20) NOT NULL,
observaciones VARCHAR(300) NULL,
FOREIGN KEY (id_categoria_recurso) REFERENCES categorias_recurso(id_categoria_recurso) ON UPDATE CASCADE ON DELETE RESTRICT,
CHECK (cantidad_total > 0),
CHECK (estado_recurso IN ('DISPONIBLE', 'ASIGNADO', 'DANADO', 'PERDIDO', 'MANTENIMIENTO'))
);

CREATE TABLE movimientos_recurso (
id_movimiento INT AUTO_INCREMENT PRIMARY KEY,
id_recurso INT NOT NULL,
id_actividad INT NOT NULL,
id_responsable INT NOT NULL,
cantidad_asignada INT NOT NULL,
cantidad_recibida INT NULL,
fecha_entrega DATETIME NOT NULL,
fecha_devolucion_prevista DATETIME NOT NULL,
fecha_devolucion_real DATETIME NULL,
estado_movimiento VARCHAR(20) NOT NULL,
observaciones VARCHAR(300) NULL,
FOREIGN KEY (id_recurso) REFERENCES recursos(id_recurso) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_actividad) REFERENCES actividades(id_actividad) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_responsable) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT,
CHECK (cantidad_asignada > 0),
CHECK (estado_movimiento IN ('ASIGNADO', 'ENTREGADO', 'DEVUELTO', 'DANADO', 'PERDIDO', 'MANTENIMIENTO'))
);

CREATE TABLE tipos_incidencia (
id_tipo_incidencia INT AUTO_INCREMENT PRIMARY KEY,
nombre VARCHAR(80) NOT NULL UNIQUE,
descripcion VARCHAR(300) NOT NULL
);

CREATE TABLE incidencias (
id_incidencia INT AUTO_INCREMENT PRIMARY KEY,
id_tipo_incidencia INT NOT NULL,
id_zona INT NOT NULL,
severidad VARCHAR(15) NOT NULL,
descripcion VARCHAR(500) NOT NULL,
ubicacion VARCHAR(150) NOT NULL,
id_actividad INT NULL,
id_reportado_por INT NOT NULL,
id_asignado_a INT NULL,
estado_incidencia VARCHAR(20) NOT NULL,
accion_realizada VARCHAR(500) NULL,
fecha_creacion DATETIME NOT NULL,
fecha_actualizacion DATETIME NOT NULL,
fecha_resolucion DATETIME NULL,
fecha_cierre DATETIME NULL,
FOREIGN KEY (id_tipo_incidencia) REFERENCES tipos_incidencia(id_tipo_incidencia) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_zona) REFERENCES zonas(id_zona) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_actividad) REFERENCES actividades(id_actividad) ON UPDATE CASCADE ON DELETE SET NULL,
FOREIGN KEY (id_reportado_por) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT,
FOREIGN KEY (id_asignado_a) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT,
CHECK (severidad IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')),
CHECK (estado_incidencia IN ('ABIERTA', 'ASIGNADA', 'EN_ATENCION', 'RESUELTA', 'CERRADA'))
);

CREATE TABLE historial_incidencias (
id_historial INT AUTO_INCREMENT PRIMARY KEY,
id_incidencia INT NOT NULL,
id_autor INT NOT NULL,
estado_anterior VARCHAR(20) NULL,
estado_nuevo VARCHAR(20) NOT NULL,
accion VARCHAR(500) NOT NULL,
fecha_cambio DATETIME NOT NULL,
FOREIGN KEY (id_incidencia) REFERENCES incidencias(id_incidencia) ON UPDATE CASCADE ON DELETE CASCADE,
FOREIGN KEY (id_autor) REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT
);