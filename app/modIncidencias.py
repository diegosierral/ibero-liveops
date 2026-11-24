"""
@package IberoLiveOps
@summary Modulo 4: registro, atencion, asignacion y cierre de incidencias con historial
@author Kilian Ian Pérez García
@date 23 de noviembre de 2026
"""
import db
import ui
from auth import requierePerfil, PERFIL_COORDINACION, PERFIL_OPERACIONES, PERFIL_PARTICIPANTE
from filtros import (Filtro, elegirZona, elegirTipoIncidencia, elegirOperador, pedirRangoFechas)
from util import (leerTexto, leerEntero, leerOpcionLista, confirmar, pausar)

COORD = (PERFIL_COORDINACION,)
OPER = (PERFIL_OPERACIONES,)
PART = (PERFIL_PARTICIPANTE,)

SEVERIDADES = ["BAJA", "MEDIA", "ALTA", "CRITICA"]
ESTADOS = ["ABIERTA", "ASIGNADA", "EN_ATENCION", "RESUELTA", "CERRADA"]

SQL_INC = (
    "SELECT i.id_incidencia, ti.nombre, i.severidad, i.estado_incidencia, z.nombre, i.ubicacion, "
    "a.nombre_actividad, ur.nombre_usuario, ua.nombre_usuario, i.fecha_creacion, i.fecha_actualizacion, "
    "i.fecha_resolucion, TIMESTAMPDIFF(MINUTE, i.fecha_creacion, COALESCE(i.fecha_cierre, i.fecha_resolucion, NOW())), "
    "i.accion_realizada "
    "FROM incidencias i JOIN tipos_incidencia ti ON ti.id_tipo_incidencia = i.id_tipo_incidencia "
    "JOIN zonas z ON z.id_zona = i.id_zona JOIN usuarios ur ON ur.id_usuario = i.id_reportado_por "
    "LEFT JOIN usuarios ua ON ua.id_usuario = i.id_asignado_a "
    "LEFT JOIN actividades a ON a.id_actividad = i.id_actividad "
)
COLS_INC = [("Folio", 5, True), ("Tipo", 14, False), ("Severidad", 9, False), ("Estado", 11, False),
            ("Zona", 14, False), ("Ubicacion", 16, False), ("Actividad", 16, False), ("Reporta", 12, False),
            ("Responsable", 12, False), ("Apertura", 16, False), ("Min", 5, True)]
ORDEN_SEVERIDAD = "ORDER BY FIELD(i.severidad,'CRITICA','ALTA','MEDIA','BAJA'), i.fecha_creacion, i.id_incidencia"


def _proyectar(filas):
    return [(f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8], f[9], f[12]) for f in filas]


def _mostrar(conn, sql, params):
    filas = db.queryAll(conn, sql, params)
    if not filas:
        ui.msgSinResultados()
        return []
    ui.imprimirTabla(COLS_INC, _proyectar(filas))
    porEstado = {}
    for f in filas:
        porEstado[f[3]] = porEstado.get(f[3], 0) + 1
    print(f"\n{len(filas)} incidencia(s). Por estado: " + " | ".join(f"{k}: {v}" for k, v in porEstado.items()))
    return filas


def _historial(conn, idIncidencia, limitarAutor=None):
    sql = ("SELECT h.fecha_cambio, u.nombre_usuario, h.estado_anterior, h.estado_nuevo, h.accion, "
           "TIMESTAMPDIFF(MINUTE, (SELECT MAX(h2.fecha_cambio) FROM historial_incidencias h2 "
           " WHERE h2.id_incidencia = h.id_incidencia AND h2.id_historial < h.id_historial), h.fecha_cambio) "
           "FROM historial_incidencias h JOIN usuarios u ON u.id_usuario = h.id_autor "
           "WHERE h.id_incidencia = %s ORDER BY h.fecha_cambio, h.id_historial")
    db.selectTabla(conn, sql, (idIncidencia,),
                    [("Fecha", 16, False), ("Autor", 14, False), ("Anterior", 11, False), ("Nuevo", 11, False),
                     ("Accion", 44, False), ("Min desde previo", 16, True)])


def _detalle(conn, fila):
    etiquetas = ["Folio", "Tipo", "Severidad", "Estado", "Zona", "Ubicacion", "Actividad", "Reportada por",
                 "Responsable", "Apertura", "Ultima actualizacion", "Resolucion", "Minutos", "Ultima accion"]
    print()
    for e, v in zip(etiquetas, fila):
        print(f"  {e:<20}: {ui.formatear(v)}")


def registrarIncidencia(conn, sesion):
    if not requierePerfil(conn, sesion, *PART, *OPER):
        return
    print("\nRegistrar incidencia (/c cancela)")
    tipo = elegirTipoIncidencia(conn, opcional=False)
    sev = leerOpcionLista("Severidad" + (" sugerida" if sesion.perfil == PERFIL_PARTICIPANTE else ""), SEVERIDADES)
    desc = leerTexto("Descripcion del problema (10 a 500 caracteres): ", 10, 500)
    ubic = leerTexto("Ubicacion (obligatoria): ", 1, 150)
    idz = elegirZona(conn, opcional=False)
    ida = leerEntero("ID de actividad relacionada (Enter si no aplica): ", 1, 10**9, opcional=True)
    if ida and db.queryVal(conn, "SELECT COUNT(*) FROM actividades WHERE id_actividad=%s", (ida,)) == 0:
        ui.msgError("Actividad inexistente.")
        return
    try:
        r = db.callSp(conn, "sp_registrar_incidencia", (sesion.idUsuario, tipo, idz, sev, desc, ubic, ida), ("folio",))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito(f"Incidencia registrada con folio {r['folio']}. Estado: ABIERTA.")


def misIncidencias(conn, sesion):
    if not requierePerfil(conn, sesion, *PART):
        return
    f = Filtro()
    f.agregar("i.id_reportado_por = %s", sesion.idUsuario)
    print("\nFiltros (Enter omite)")
    est = leerOpcionLista("Estado", ESTADOS, opcional=True)
    if est:
        f.agregar("i.estado_incidencia = %s", est)
    tipo = elegirTipoIncidencia(conn)
    if tipo:
        f.agregar("i.id_tipo_incidencia = %s", tipo)
    desde, hasta, ok = pedirRangoFechas("Fecha de apertura")
    if not ok:
        return
    if desde:
        f.agregar("DATE(i.fecha_creacion) >= %s", desde)
    if hasta:
        f.agregar("DATE(i.fecha_creacion) <= %s", hasta)
    filas = _mostrar(conn, SQL_INC + f.where() + " ORDER BY i.fecha_creacion DESC, i.id_incidencia DESC", f.params)
    while filas:
        v = leerEntero("\nFolio para ver detalle e historial (0 = volver): ", 0, 10**9)
        if v == 0:
            return
        fila = next((x for x in filas if x[0] == v), None)
        if fila is None:
            ui.msgPermisoDenegado()
            print("Esa incidencia no existe entre las suyas.")
            continue
        _detalle(conn, fila)
        print("\nHistorial:")
        _historial(conn, v)


def _filtrosGestion(conn, sesion):
    f = Filtro()
    print("\nFiltros (Enter omite)")
    if sesion.perfil == PERFIL_OPERACIONES:
        mias = leerOpcionLista("Solo asignadas a mi", ["S", "N"], opcional=True)
        if mias == "S":
            f.agregar("i.id_asignado_a = %s", sesion.idUsuario)
        sin = leerOpcionLista("Solo sin asignar", ["S", "N"], opcional=True)
        if sin == "S":
            f.agregar("i.id_asignado_a IS NULL")
    else:
        sin = leerOpcionLista("Solo sin asignar", ["S", "N"], opcional=True)
        if sin == "S":
            f.agregar("i.id_asignado_a IS NULL")
        resp = elegirOperador(conn)
        if resp:
            f.agregar("i.id_asignado_a = %s", resp)
    est = leerOpcionLista("Estado", ESTADOS, opcional=True)
    if est:
        f.agregar("i.estado_incidencia = %s", est)
    sev = leerOpcionLista("Severidad", SEVERIDADES, opcional=True)
    if sev:
        f.agregar("i.severidad = %s", sev)
    tipo = elegirTipoIncidencia(conn)
    if tipo:
        f.agregar("i.id_tipo_incidencia = %s", tipo)
    zona = elegirZona(conn)
    if zona:
        f.agregar("i.id_zona = %s", zona)
    ida = leerEntero("ID de actividad: ", 1, 10**9, opcional=True)
    if ida:
        f.agregar("i.id_actividad = %s", ida)
    desde, hasta, ok = pedirRangoFechas("Fecha de apertura")
    if not ok:
        return None
    if desde:
        f.agregar("DATE(i.fecha_creacion) >= %s", desde)
    if hasta:
        f.agregar("DATE(i.fecha_creacion) <= %s", hasta)
    return f


def listarIncidencias(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER, *COORD):
        return []
    f = _filtrosGestion(conn, sesion)
    if f is None:
        return []
    return _mostrar(conn, SQL_INC + f.where() + " " + ORDEN_SEVERIDAD, f.params)


def verDetalleHistorial(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER, *COORD):
        return
    v = leerEntero("Folio (0 = volver): ", 0, 10**9)
    if v == 0:
        return
    fila = db.queryOne(conn, SQL_INC + "WHERE i.id_incidencia = %s", (v,))
    if fila is None:
        ui.msgError("Incidencia no encontrada.")
        return
    _detalle(conn, fila)
    print("\nHistorial:")
    _historial(conn, v)


def menuIncidenciasOperaciones(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    while True:
        opcion = ui.menu(sesion, "Incidencias", [
            "Consultar incidencias", "Registrar incidencia", "Clasificar severidad (asignadas a mi)",
            "Aceptar asignacion e iniciar atencion", "Registrar accion realizada",
            "Marcar como resuelta", "Ver detalle e historial"])
        if opcion == 0:
            return
        {1: listarIncidencias, 2: registrarIncidencia, 3: clasificarSeveridad, 4: iniciarAtencion,
         5: registrarAccion, 6: resolver, 7: verDetalleHistorial}[opcion](conn, sesion)
        pausar()


def _cambiarEstado(conn, sesion, folio, estadoNuevo, idAsignado, accion):
    try:
        db.callSp(conn, "sp_cambiar_estado_incidencia", (sesion.idUsuario, folio, estadoNuevo, idAsignado, accion))
        return True
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return False


def iniciarAtencion(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    folio = leerEntero("Folio de la incidencia asignada a usted (0 = volver): ", 0, 10**9)
    if folio == 0:
        return
    nota = leerTexto("Nota inicial (opcional): ", 1, 500, opcional=True)
    if _cambiarEstado(conn, sesion, folio, "EN_ATENCION", None, nota):
        ui.msgExito("Incidencia aceptada. Atencion iniciada.")


def resolver(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    folio = leerEntero("Folio de la incidencia (0 = volver): ", 0, 10**9)
    if folio == 0:
        return
    accion = leerTexto("Accion realizada (5 a 500 caracteres, obligatoria): ", 5, 500)
    if not confirmar("La incidencia pasara a RESUELTA."):
        ui.msgAviso("Operacion cancelada.")
        return
    if _cambiarEstado(conn, sesion, folio, "RESUELTA", None, accion):
        ui.msgExito("Incidencia resuelta.")


def _registrarNotaHistorial(conn, sesion, folio, texto, trasCambio=None):
    with db.transaccion(conn):
        inc = db.queryOne(conn, "SELECT estado_incidencia, id_asignado_a, severidad FROM incidencias WHERE id_incidencia=%s FOR UPDATE", (folio,))
        if inc is None:
            raise db.DBError("Incidencia no encontrada.", negocio=True)
        if inc[1] != sesion.idUsuario:
            raise db.DBError("Permiso denegado: la incidencia no esta asignada a ti.", negocio=True)
        if inc[0] in ("RESUELTA", "CERRADA"):
            raise db.DBError("La incidencia ya esta resuelta o cerrada y no admite cambios.", negocio=True)
        accionFinal, sqlUpd, params = trasCambio(inc, texto)
        db.execute(conn, sqlUpd, params)
        db.execute(conn, "INSERT INTO historial_incidencias (id_incidencia,id_autor,estado_anterior,estado_nuevo,accion,fecha_cambio) "
                         "VALUES (%s,%s,%s,%s,%s,NOW())", (folio, sesion.idUsuario, inc[0], inc[0], accionFinal))


def registrarAccion(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    folio = leerEntero("Folio (0 = volver): ", 0, 10**9)
    if folio == 0:
        return
    texto = leerTexto("Accion realizada (5 a 500 caracteres): ", 5, 500)

    def aplicar(inc, t):
        if inc[0] != "EN_ATENCION":
            raise db.DBError("Primero acepte la asignacion e inicie la atencion (estado EN_ATENCION).", negocio=True)
        return t, "UPDATE incidencias SET accion_realizada=%s, fecha_actualizacion=NOW() WHERE id_incidencia=%s", (t, folio)
    try:
        _registrarNotaHistorial(conn, sesion, folio, texto, aplicar)
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Accion guardada.")


def clasificarSeveridad(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    folio = leerEntero("Folio (0 = volver): ", 0, 10**9)
    if folio == 0:
        return
    nueva = leerOpcionLista("Nueva severidad", SEVERIDADES)

    def aplicar(inc, n):
        if inc[2] == n:
            raise db.DBError("La incidencia ya tiene esa severidad.", negocio=True)
        return (f"Severidad clasificada: {inc[2]} -> {n}",
                "UPDATE incidencias SET severidad=%s, fecha_actualizacion=NOW() WHERE id_incidencia=%s", (n, folio))
    try:
        _registrarNotaHistorial(conn, sesion, folio, nueva, aplicar)
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Severidad actualizada.")


def menuIncidenciasCoordinacion(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    while True:
        opcion = ui.menu(sesion, "Incidencias", [
            "Consultar incidencias", "Ver detalle e historial", "Asignar o reasignar responsable",
            "Cerrar incidencia", "Consultar tipos de incidencia", "Crear tipo de incidencia"])
        if opcion == 0:
            return
        {1: listarIncidencias, 2: verDetalleHistorial, 3: asignarResponsable, 4: cerrarIncidencia,
         5: listarTipos, 6: crearTipo}[opcion](conn, sesion)
        pausar()


def asignarResponsable(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    folio = leerEntero("Folio de la incidencia (0 = volver): ", 0, 10**9)
    if folio == 0:
        return
    resp = elegirOperador(conn, opcional=False)
    nota = leerTexto("Nota de la asignacion (opcional): ", 1, 500, opcional=True)
    if _cambiarEstado(conn, sesion, folio, "ASIGNADA", resp, nota):
        ui.msgExito("Responsable asignado.")


def cerrarIncidencia(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    folio = leerEntero("Folio de la incidencia (0 = volver): ", 0, 10**9)
    if folio == 0:
        return
    nota = leerTexto("Resolucion o comentario final: ", 3, 500)
    if not confirmar("La incidencia pasara a CERRADA (definitivo)."):
        ui.msgAviso("Operacion cancelada.")
        return
    if _cambiarEstado(conn, sesion, folio, "CERRADA", None, nota):
        ui.msgExito("Incidencia cerrada.")


def listarTipos(conn, sesion):
    db.selectTabla(conn, "SELECT id_tipo_incidencia, nombre, descripcion FROM tipos_incidencia ORDER BY nombre", (),
                    [("ID", 4, True), ("Tipo", 22, False), ("Descripcion", 80, False)])


def crearTipo(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    nombre = leerTexto("Nombre del tipo: ", 2, 80)
    desc = leerTexto("Descripcion: ", 1, 300)
    if db.queryVal(conn, "SELECT COUNT(*) FROM tipos_incidencia WHERE nombre=%s", (nombre,)):
        ui.msgError("Nombre duplicado.")
        return
    _, nuevo = db.execute(conn, "INSERT INTO tipos_incidencia (nombre, descripcion) VALUES (%s,%s)", (nombre, desc))
    ui.msgExito(f"Tipo guardado. Folio: {nuevo}.")
