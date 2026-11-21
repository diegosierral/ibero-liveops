"""
@package IberoLiveOps
@summary Constructor de filtros combinables (WHERE parametrizado) y selectores de catalogo
@author Kilian Ian Pérez García
@date 21 de noviembre de 2026
"""
import db
import ui
from util import leerEntero, leerTexto, leerFecha


class Filtro:
    def __init__(self):
        self.condiciones = []
        self.params = []

    def agregar(self, fragmento, *valores):
        self.condiciones.append(fragmento)
        self.params.extend(valores)

    def where(self, prefijo="WHERE"):
        return (prefijo + " " + " AND ".join(self.condiciones)) if self.condiciones else ""

    def and_(self):
        return (" AND " + " AND ".join(self.condiciones)) if self.condiciones else ""


def _elegir(conn, titulo, sql, params=(), opcional=True):
    filas = db.queryAll(conn, sql, params)
    if not filas:
        ui.msgAviso(f"No hay registros de {titulo}.")
        return None
    print(f"\n{titulo}:")
    for fila in filas:
        print(f"  {fila[0]:>4}  {ui.formatear(fila[1])}")
    ids = {f[0] for f in filas}
    while True:
        v = leerEntero(f"ID de {titulo}" + (" (Enter = todos): " if opcional else ": "), 0, 10**9, opcional=opcional)
        if v is None or v == 0:
            if opcional:
                return None
            ui.msgDatoInvalido("Debe elegir un registro.")
            continue
        if v in ids:
            return v
        ui.msgDatoInvalido("Ese ID no esta en la lista.")


def elegirFestival(conn, opcional=True):
    return _elegir(conn, "festival", "SELECT id_festival, CONCAT(nombre,' (',fecha,')') FROM festivales ORDER BY fecha DESC", opcional=opcional)


def elegirZona(conn, opcional=True):
    return _elegir(conn, "zona", "SELECT id_zona, nombre FROM zonas ORDER BY nombre", opcional=opcional)


def elegirEspacio(conn, opcional=True, soloDisponibles=False):
    sql = ("SELECT e.id_espacio, CONCAT(e.nombre,' | ',z.nombre,' | aforo ',e.aforo,' | ',e.estado_espacio) "
           "FROM espacios e JOIN zonas z ON z.id_zona = e.id_zona ")
    if soloDisponibles:
        sql += "WHERE e.estado_espacio = 'DISPONIBLE' "
    sql += "ORDER BY z.nombre, e.nombre"
    return _elegir(conn, "espacio", sql, opcional=opcional)


def elegirCategoria(conn, opcional=True):
    return _elegir(conn, "categoria de actividad", "SELECT id_categoria, nombre FROM categorias_actividad ORDER BY nombre", opcional=opcional)


def elegirCategoriaRecurso(conn, opcional=True):
    return _elegir(conn, "categoria de recurso", "SELECT id_categoria_recurso, nombre FROM categorias_recurso ORDER BY nombre", opcional=opcional)


def elegirTipoIncidencia(conn, opcional=True):
    return _elegir(conn, "tipo de incidencia", "SELECT id_tipo_incidencia, nombre FROM tipos_incidencia ORDER BY nombre", opcional=opcional)


def elegirOperador(conn, opcional=True):
    return _elegir(conn, "responsable (Operaciones activo)",
                   "SELECT id_usuario, CONCAT(nombre_usuario,' - ',nombre_mostrar) FROM usuarios "
                   "WHERE perfil = 'OPERACIONES' AND estado_cuenta = 'ACTIVA' ORDER BY nombre_usuario",
                   opcional=opcional)


def pedirBusqueda(prompt):
    t = leerTexto(prompt, 1, 60, opcional=True)
    return f"%{t}%" if t else None


def pedirRangoFechas(prompt):
    desde = leerFecha(f"{prompt} desde", opcional=True)
    hasta = leerFecha(f"{prompt} hasta", opcional=True)
    if desde and hasta and hasta < desde:
        ui.msgDatoInvalido("Filtros invalidos: la fecha final es anterior a la inicial.")
        return None, None, False
    return desde, hasta, True
