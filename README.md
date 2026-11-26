# IBERO LiveOps

Sistema de gestión operativa en consola para la planeación, control de cupos, inventario de recursos y seguimiento de incidencias de un festival universitario, desarrollado como proyecto final de Sistemas de Bases de Datos.

## Características Principales

* **Control de Acceso por Perfiles:** Inicio de sesión con contraseñas cifradas (SHA-256) y permisos diferenciados para Coordinación, Operaciones y Participante.

* **Agenda y Reservaciones:** Administración de zonas, espacios y actividades, con reservaciones atómicas, prevención de conflictos de horario y promoción automática en lista de espera.

* **Inventario y Recursos:** Asignación, entrega y devolución de equipos con validación de disponibilidad en tiempo real y reporte de daños o mantenimiento.

* **Gestión de Incidencias:** Registro y atención de reportes con flujo de estados controlado e historial de cambios inalterable.

* **Reportes Operativos:** Consultas parametrizadas con filtros combinables y resúmenes de ocupación, demanda, recursos y tiempos de atención.

## Tecnologías Utilizadas

* **Lenguaje:** Python 3

* **Base de Datos:** MySQL 8.0

* **Conector:** `mysql-connector-python`

## Estructura del Proyecto

* `Build/`: Scripts SQL para crear la base de datos (`create.sql`), cargar datos (`insert.sql`), instalar procedimientos (`procedures.sql`), configurar seguridad (`usuarioApp.sql`, `seguridad.sql`, `demoFechas.sql`) y probar consultas (`queries.sql`).

* `app/`: Código fuente de la aplicación en Python (`main.py`, `db.py`, `auth.py`, `modCuentas.py`, `modAgenda.py`, `modRecursos.py`, `modIncidencias.py`, `modReportes.py`, `filtros.py`, `ui.py`, `util.py`).

## Cómo Ejecutar

### 1. Instalar dependencias de Python (Windows y Linux)

Ubícate en la carpeta raíz del proyecto e instala el conector oficial de MySQL:

```bash
pip install mysql-connector-python
```

### Opción A: Windows (PowerShell)

#### 1. Inicializar la base de datos en MySQL

Agrega la ruta de MySQL a la sesión actual de PowerShell e inicia sesión como `root` con soporte UTF-8:

```powershell
$env:PATH += ";" + (Get-ChildItem "C:\Program Files\MySQL" -Recurse -Filter "mysql.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).DirectoryName
mysql -u root -p --default-character-set=utf8mb4
```

Ya dentro del cliente `mysql>`, ejecuta los scripts en orden secuencial, asigna tu contraseña al usuario `liveops_app` (reemplazando `tu_contrasena`) y sal al finalizar:

```sql
SOURCE Build/create.sql;
SOURCE Build/insert.sql;
SOURCE Build/procedures.sql;
SOURCE Build/usuarioApp.sql;
ALTER USER 'liveops_app'@'localhost' IDENTIFIED BY 'tu_contrasena';
FLUSH PRIVILEGES;
SOURCE Build/seguridad.sql;
SOURCE Build/demoFechas.sql;
EXIT;
```

#### 2. Configurar variables de entorno e iniciar la aplicación

Define las variables de conexión en tu sesión de PowerShell (usando la misma `tu_contrasena` que definiste arriba) y arranca el programa:

```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="3306"
$env:DB_USER="liveops_app"
$env:DB_PASSWORD="tu_contrasena"
$env:DB_NAME="ibero_liveops"
python app/main.py
```

### Opción B: Linux / macOS (Bash)

#### 1. Inicializar la base de datos en MySQL

Desde la carpeta raíz del proyecto, carga los scripts de `Build/` en orden secuencial y actualiza la contraseña del usuario `liveops_app` (reemplazando `tu_contrasena`):

```bash
mysql -u root -p --default-character-set=utf8mb4 < Build/create.sql
mysql -u root -p --default-character-set=utf8mb4 < Build/insert.sql
mysql -u root -p --default-character-set=utf8mb4 < Build/procedures.sql
mysql -u root -p --default-character-set=utf8mb4 < Build/usuarioApp.sql
mysql -u root -p -e "ALTER USER 'liveops_app'@'localhost' IDENTIFIED BY 'tu_contrasena'; FLUSH PRIVILEGES;"
mysql -u root -p --default-character-set=utf8mb4 < Build/seguridad.sql
mysql -u root -p --default-character-set=utf8mb4 < Build/demoFechas.sql
```

#### 2. Configurar variables de entorno e iniciar la aplicación

Exporta las credenciales de conexión (usando la misma `tu_contrasena` que definiste arriba) y ejecuta el sistema:

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=liveops_app
export DB_PASSWORD=tu_contrasena
export DB_NAME=ibero_liveops
python3 app/main.py
```

## Usuarios de Prueba

Después de ejecutar `Build/seguridad.sql`, todas las cuentas de demostración utilizan la contraseña **`Liveops#2026`**:

| Perfil | Usuario | Nombre | Descripción |
| :--- | :--- | :--- | :--- |
| `COORDINACION` | `coord_admin` | Elena Rostova | Administrador general con historial de asignación y cierre de incidencias |
| `COORDINACION` | `coord_general` | Marco Villalobos | Segundo coordinador activo |
| `OPERACIONES` | `oper_audio` | Hector Beltran | Operador con recursos asignados e incidencias a su cargo |
| `OPERACIONES` | `oper_logistica` | Diana Peralta | Operador con movimientos de equipo e incidencias activas |
| `OPERACIONES` | `oper_seguridad` | Arturo Monroy | Operador de seguridad activo |
| `PARTICIPANTE` | `part_alessandro` | Alessandro Gatti | Participante con reservaciones confirmadas e incidencias reportadas |
| `PARTICIPANTE` | `part_fabiola` | Fabiola Zepeda | Participante en lista de espera dentro de una actividad |
| `PARTICIPANTE` | `part_erick` | Erick Talavera | Participante activo con agenda libre para nuevas reservaciones |
| `INACTIVA` | `coord_inactivo` | Laura Samperio | Cuenta de Coordinación dada de baja (rechaza inicio de sesión) |
| `INACTIVA` | `oper_baja` | Esteban Cedillo | Cuenta de Operaciones dada de baja (rechaza inicio de sesión) |
| `INACTIVA` | `part_inactivo1` | Flavio Suspendido | Cuenta de Participante dada de baja (rechaza inicio de sesión) |

## Autores

* Karen Arumil Lima Uranga

* Nicolás Martínez Viale

* Kilian Ian Pérez García

* Diego Sierra Legorreta