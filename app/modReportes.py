"""
@package IberoLiveOps
@summary Modulo 5: resumenes por perfil y reportes 8.1 a 8.6 con filtros, orden y totales
@author Kilian Ian Pérez García
@date 23 de noviembre de 2026
"""
import db
import ui
import modAgenda
import modRecursos
import modIncidencias
from auth import requierePerfil, PERFIL_COORDINACION, PERFIL_OPERACIONES
from filtros import (Filtro, elegirFestival, elegirZona, elegirEspacio, elegirCategoria,
                     elegirCategoriaRecurso, pedirBusqueda)
from util import (leerEntero, leerFecha, leerOpcionLista, pausar)

COORD = (PERFIL_COORDINACION,)
OPER = (PERFIL_OPERACIONES,)
VENCIDA_MIN = 60


def _fechaFestivalReciente(conn):
    return db.queryVal(conn, "SELECT MAX(fecha) FROM festivales")


def _tablaIndicadores(titulo, pares):
    ui.subtitulo(titulo)
    ui.imprimirTabla([("Indicador", 46, False), ("Valor", 12, True)], pares)


def _unir(*piezas):
    return " ".join(p for p in piezas if p)


def resumenFestival(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idf = elegirFestival(conn, opcional=True)
    if idf is None:
        idf = db.queryVal(conn, "SELECT id_festival FROM festivales ORDER BY fecha DESC LIMIT 1")
    fest = db.queryOne(conn, "SELECT nombre, fecha FROM festivales WHERE id_festival=%s", (idf,)) if idf else None
    if fest is None:
        ui.msgError("Edicion no encontrada.")
        return
    fecha = leerFecha("Filtrar por fecha", opcional=True)
    ffa = Filtro()
    ffa.agregar("z.id_festival = %s", idf)
    if fecha:
        ffa.agregar("a.fecha = %s", fecha)
    baseA = ("FROM actividades a JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona ")
    act = dict(db.queryAll(conn, "SELECT a.estado_actividad, COUNT(*) " + baseA + ffa.where() + " GROUP BY a.estado_actividad", ffa.params))
    res = dict(db.queryAll(
        conn, "SELECT r.estado_reservacion, COUNT(*) FROM reservaciones r JOIN actividades a ON a.id_actividad=r.id_actividad "
              "JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona " + ffa.where() +
              " GROUP BY r.estado_reservacion", ffa.params))
    if not act:
        ui.msgAviso("Sin datos para la edicion seleccionada.")
        return
    rec = dict(db.queryAll(conn, "SELECT IF(estado_recurso IN ('DISPONIBLE','ASIGNADO'),'disp','nodisp'), COUNT(*) FROM recursos GROUP BY 1"))
    fi = Filtro()
    fi.agregar("i.id_zona IN (SELECT id_zona FROM zonas WHERE id_festival = %s)", idf)
    if fecha:
        fi.agregar("DATE(i.fecha_creacion) = %s", fecha)
    inc = db.queryOne(
        conn, "SELECT SUM(i.estado_incidencia IN ('ABIERTA','ASIGNADA','EN_ATENCION')), "
              "SUM(i.estado_incidencia IN ('ABIERTA','ASIGNADA','EN_ATENCION') AND i.severidad='CRITICA'), "
              "SUM(i.estado_incidencia <> 'CERRADA' AND i.id_asignado_a IS NULL) FROM incidencias i " + fi.where(), fi.params)
    ui.encabezado(sesion, "Resumen del festival")
    print(f"Festival: {fest[0]} | Fecha: {fest[1]}" + (f" | Filtro de fecha: {fecha}" if fecha else ""))
    _tablaIndicadores("Actividades", [("Publicadas", act.get("PUBLICADA", 0)), ("Canceladas", act.get("CANCELADA", 0)),
                                        ("Finalizadas", act.get("FINALIZADA", 0))])
    _tablaIndicadores("Reservaciones (las canceladas no cuentan como confirmadas)",
                       [("Confirmadas", res.get("CONFIRMADA", 0)), ("En espera", res.get("ESPERA", 0))])
    _tablaIndicadores("Recursos (disponibles = DISPONIBLE o ASIGNADO; no disponibles = DANADO, PERDIDO o MANTENIMIENTO)",
                       [("Recursos disponibles", rec.get("disp", 0)), ("Recursos no disponibles", rec.get("nodisp", 0))])
    _tablaIndicadores("Incidencias", [("Abiertas (ABIERTA, ASIGNADA o EN_ATENCION)", int(inc[0] or 0)),
                                        ("Criticas abiertas", int(inc[1] or 0)), ("Sin responsable", int(inc[2] or 0))])
    while True:
        v = leerEntero("\nDetalle: 1 Actividades, 2 Recursos, 3 Incidencias, 0 Volver: ", 0, 3)
        if v == 0:
            return
        {1: lambda: modAgenda.mostrarAgenda(conn, sesion, "coord"),
         2: lambda: modRecursos.consultarInventario(conn, sesion),
         3: lambda: modIncidencias.listarIncidencias(conn, sesion)}[v]()


def resumenOperativo(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    fecha = leerFecha("Fecha de trabajo", default=str(_fechaFestivalReciente(conn)))
    idz = elegirZona(conn)
    fa = Filtro()
    fa.agregar("a.fecha = %s", fecha)
    fa.agregar("a.estado_actividad = 'PUBLICADA'")
    if idz:
        fa.agregar("z.id_zona = %s", idz)
    base = "FROM actividades a JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona "
    nAct = db.queryVal(conn, "SELECT COUNT(*) " + base + fa.where(), fa.params)
    movs = dict(db.queryAll(
        conn, "SELECT m.estado_movimiento, COUNT(*) FROM movimientos_recurso m JOIN actividades a ON a.id_actividad=m.id_actividad "
              "JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona " + fa.where() +
              " AND m.estado_movimiento IN ('ASIGNADO','ENTREGADO') GROUP BY m.estado_movimiento", fa.params))
    inc = dict(db.queryAll(conn, "SELECT estado_incidencia, COUNT(*) FROM incidencias WHERE id_asignado_a=%s "
                                  "AND estado_incidencia IN ('ASIGNADA','EN_ATENCION') GROUP BY estado_incidencia", (sesion.idUsuario,)))
    crit = db.queryVal(conn, "SELECT COUNT(*) FROM incidencias WHERE id_asignado_a=%s AND estado_incidencia IN ('ASIGNADA','EN_ATENCION') "
                              "AND severidad='CRITICA'", (sesion.idUsuario,))
    venc = db.queryVal(conn, "SELECT COUNT(*) FROM incidencias WHERE id_asignado_a=%s AND estado_incidencia IN ('ASIGNADA','EN_ATENCION') "
                              "AND TIMESTAMPDIFF(MINUTE, fecha_creacion, NOW()) > %s", (sesion.idUsuario, VENCIDA_MIN))
    ui.encabezado(sesion, "Resumen operativo")
    print(f"Fecha de trabajo: {fecha}" + (" | Zona filtrada" if idz else ""))
    if not (nAct or movs or inc):
        ui.msgAviso("No hay pendientes para la fecha seleccionada.")
    _tablaIndicadores("Pendientes", [
        ("Actividades del dia", nAct), ("Recursos por entregar (ASIGNADO)", movs.get("ASIGNADO", 0)),
        ("Recursos por devolver (ENTREGADO)", movs.get("ENTREGADO", 0)),
        ("Mis incidencias ASIGNADAS", inc.get("ASIGNADA", 0)), ("Mis incidencias EN_ATENCION", inc.get("EN_ATENCION", 0)),
        ("Mis incidencias criticas", crit), (f"Mis incidencias vencidas (> {VENCIDA_MIN} min)", venc)])
    if crit:
        ui.msgAviso("Existen incidencias criticas asignadas a usted.")
    if movs.get("ENTREGADO", 0):
        ui.msgAviso("Hay recursos con devolucion pendiente.")
    while True:
        v = leerEntero("\nAbrir: 1 Agenda, 2 Recursos, 3 Incidencias, 0 Volver: ", 0, 3)
        if v == 0:
            return
        {1: lambda: modAgenda.mostrarAgenda(conn, sesion, "oper"),
         2: lambda: modRecursos.consultarMovimientos(conn, sesion),
         3: lambda: modIncidencias.listarIncidencias(conn, sesion)}[v]()


def menuReportesCoordinacion(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    while True:
        o = ui.menu(sesion, "Reportes de coordinacion", [
            "8.1 Ocupacion de actividades", "8.2 Demanda y reservaciones", "8.3 Disponibilidad y utilizacion de recursos",
            "8.4 Incidencias y tiempo de atencion", "8.5 Resumen ejecutivo del festival"])
        if o == 0:
            return
        {1: reporteOcupacion, 2: reporteDemanda, 3: reporteRecursos, 4: reporteIncidencias, 5: resumenEjecutivo}[o](conn, sesion)
        pausar()


def menuReportesOperaciones(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    while True:
        o = ui.menu(sesion, "Reportes operativos", [
            "8.6 Agenda operativa del dia", "8.1 Ocupacion de actividades", "8.3 Disponibilidad y utilizacion de recursos",
            "8.4 Mis incidencias asignadas"])
        if o == 0:
            return
        {1: agendaOperativa, 2: reporteOcupacion, 3: reporteRecursos, 4: reporteIncidencias}[o](conn, sesion)
        pausar()


INNER_OCUPACION = (
    "SELECT a.id_actividad id, a.nombre_actividad nombre, c.nombre categoria, a.fecha fecha, "
    "CONCAT(LEFT(a.hora_inicio,5),'-',LEFT(a.hora_fin,5)) horario, z.nombre zona, e.nombre espacio, a.cupo cupo, "
    "(SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad=a.id_actividad AND r.estado_reservacion='CONFIRMADA') conf, "
    "(SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad=a.id_actividad AND r.estado_reservacion='ESPERA') espera, "
    "fn_cupo_disponible(a.id_actividad) disp, "
    "ROUND((SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad=a.id_actividad AND r.estado_reservacion='CONFIRMADA')*100/a.cupo,1) pct, "
    "a.estado_actividad estado, z.id_zona idz, c.id_categoria idc, e.id_espacio ide, a.hora_inicio hi "
    "FROM actividades a JOIN categorias_actividad c ON c.id_categoria=a.id_categoria "
    "JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona"
)
ORDEN_OCUP = {"1": ("Fecha y hora (predeterminado)", "fecha, hi, id"), "2": ("Ocupacion de mayor a menor", "pct DESC, fecha, hi"),
              "3": ("Actividad", "nombre"), "4": ("Lugares disponibles", "disp DESC, fecha, hi")}


def reporteOcupacion(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD, *OPER):
        return
    f = Filtro()
    print("\nFiltros (Enter omite)")
    if sesion.perfil == PERFIL_OPERACIONES:
        f.agregar("estado IN ('PUBLICADA','FINALIZADA')")
    fecha = leerFecha("Fecha", opcional=True)
    if fecha:
        f.agregar("fecha = %s", fecha)
    for etq, col, fn in (("zona", "idz", elegirZona), ("categoria", "idc", elegirCategoria), ("espacio", "ide", elegirEspacio)):
        v = fn(conn)
        if v:
            f.agregar(f"{col} = %s", v)
    est = leerOpcionLista("Estado", ["PUBLICADA", "CANCELADA", "FINALIZADA"], opcional=True)
    if est:
        f.agregar("estado = %s", est)
    pmin = leerEntero("Ocupacion minima % (Enter omite): ", 0, 100, opcional=True)
    pmax = leerEntero("Ocupacion maxima % (Enter omite): ", 0, 100, opcional=True)
    if pmin is not None and pmax is not None and pmax < pmin:
        ui.msgDatoInvalido("Filtros invalidos: el rango de ocupacion es incorrecto.")
        return
    if pmin is not None:
        f.agregar("pct >= %s", pmin)
    if pmax is not None:
        f.agregar("pct <= %s", pmax)
    orden = ui.elegirOrdenamiento(ORDEN_OCUP) or ORDEN_OCUP["1"][1]
    sql = ("SELECT id, nombre, categoria, fecha, horario, zona, espacio, cupo, conf, espera, disp, pct, estado FROM ("
           + INNER_OCUPACION + ") t " + f.where() + " ORDER BY " + orden)
    filas = db.selectTabla(conn, sql, f.params, [
        ("ID", 4, True), ("Actividad", 24, False), ("Categoria", 12, False), ("Fecha", 10, False), ("Horario", 11, False),
        ("Zona", 12, False), ("Espacio", 12, False), ("Cupo", 4, True), ("Conf", 4, True), ("Esp", 3, True),
        ("Disp", 4, True), ("%Ocup", 5, True), ("Estado", 10, False)])
    if filas:
        prom = sum(float(x[11]) for x in filas) / len(filas)
        print(f"Totales: cupo {sum(x[7] for x in filas)} | confirmadas {sum(x[8] for x in filas)} | "
              f"en espera {sum(x[9] for x in filas)} | ocupacion promedio {prom:.1f}%")


def reporteDemanda(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    f = Filtro()
    print("\nFiltros (Enter omite)")
    txt = pedirBusqueda("Buscar actividad: ")
    if txt:
        f.agregar("a.nombre_actividad LIKE %s", txt)
    idc = elegirCategoria(conn)
    if idc:
        f.agregar("a.id_categoria = %s", idc)
    fecha = leerFecha("Fecha", opcional=True)
    if fecha:
        f.agregar("a.fecha = %s", fecha)
    idz = elegirZona(conn)
    if idz:
        f.agregar("e.id_zona = %s", idz)
    est = leerOpcionLista("Estado de la actividad", ["PUBLICADA", "CANCELADA", "FINALIZADA"], opcional=True)
    if est:
        f.agregar("a.estado_actividad = %s", est)
    sql = ("SELECT a.id_actividad, a.nombre_actividad, COUNT(r.id_reservacion) sol, "
           "COALESCE(SUM(r.estado_reservacion='CONFIRMADA'),0), COALESCE(SUM(r.estado_reservacion='ESPERA'),0), "
           "COALESCE(SUM(r.estado_reservacion='CANCELADA'),0), MIN(r.fecha_solicitud), MAX(r.fecha_solicitud), "
           "ROUND(COALESCE(SUM(r.estado_reservacion='CANCELADA'),0)*100/NULLIF(COUNT(r.id_reservacion),0),1) "
           "FROM actividades a JOIN espacios e ON e.id_espacio=a.id_espacio "
           "LEFT JOIN reservaciones r ON r.id_actividad=a.id_actividad " + f.where() +
           " GROUP BY a.id_actividad, a.nombre_actividad ORDER BY sol DESC, a.id_actividad")
    filas = db.selectTabla(conn, sql, f.params, [
        ("ID", 4, True), ("Actividad", 28, False), ("Solic", 5, True), ("Conf", 4, True), ("Esp", 4, True), ("Canc", 4, True),
        ("Primera solicitud", 16, False), ("Ultima solicitud", 16, False), ("%Canc", 6, True)])
    if filas:
        print(f"Total general: solicitudes {sum(x[2] for x in filas)} | CONFIRMADA {sum(int(x[3]) for x in filas)} | "
              f"ESPERA {sum(int(x[4]) for x in filas)} | CANCELADA {sum(int(x[5]) for x in filas)}")


def reporteRecursos(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD, *OPER):
        return
    f = Filtro()
    print("\nFiltros (Enter omite)")
    idc = elegirCategoriaRecurso(conn)
    if idc:
        f.agregar("r.id_categoria_recurso = %s", idc)
    ub = pedirBusqueda("Buscar por ubicacion: ")
    if ub:
        f.agregar("r.ubicacion LIKE %s", ub)
    est = leerOpcionLista("Estado", ["DISPONIBLE", "ASIGNADO", "DANADO", "PERDIDO", "MANTENIMIENTO"], opcional=True)
    if est:
        f.agregar("r.estado_recurso = %s", est)
    ida = leerEntero("ID de actividad actual: ", 1, 10**9, opcional=True)
    if ida:
        f.agregar("mm.id_actividad = %s", ida)
    if leerOpcionLista("Solo no disponibles", ["S", "N"], opcional=True) == "S":
        f.agregar("r.estado_recurso IN ('DANADO','PERDIDO','MANTENIMIENTO')")
    if leerOpcionLista("Solo con devolucion pendiente", ["S", "N"], opcional=True) == "S":
        f.agregar("mm.id_movimiento IS NOT NULL")
    sql = ("SELECT r.id_recurso, cr.nombre, r.nombre_recurso, r.cantidad_total, r.cantidad_total - fn_recurso_disponible(r.id_recurso), "
           "fn_recurso_disponible(r.id_recurso), r.ubicacion, r.estado_recurso, a.nombre_actividad, mm.fecha_devolucion_prevista, u.nombre_usuario "
           "FROM recursos r JOIN categorias_recurso cr ON cr.id_categoria_recurso=r.id_categoria_recurso "
           "LEFT JOIN movimientos_recurso mm ON mm.id_movimiento = (SELECT m2.id_movimiento FROM movimientos_recurso m2 "
           " WHERE m2.id_recurso=r.id_recurso AND m2.estado_movimiento IN ('ASIGNADO','ENTREGADO') "
           " ORDER BY m2.fecha_devolucion_prevista, m2.id_movimiento LIMIT 1) "
           "LEFT JOIN actividades a ON a.id_actividad=mm.id_actividad LEFT JOIN usuarios u ON u.id_usuario=mm.id_responsable "
           + f.where() + " ORDER BY cr.nombre, r.nombre_recurso")
    filas = db.selectTabla(conn, sql, f.params, [
        ("ID", 3, True), ("Categoria", 12, False), ("Recurso", 24, False), ("Tot", 4, True), ("Asig", 4, True), ("Disp", 4, True),
        ("Ubicacion", 14, False), ("Estado", 13, False), ("Actividad actual", 18, False), ("Dev. prevista", 16, False), ("Resp.", 10, False)])
    if filas:
        porEstado = {}
        for x in filas:
            if x[7] in ("DANADO", "PERDIDO", "MANTENIMIENTO"):
                porEstado[x[7]] = porEstado.get(x[7], 0) + x[3]
        extra = "".join(f" | {k}: {v} u." for k, v in porEstado.items())
        print(f"Totales: disponibles {sum(x[5] for x in filas)} u. | asignadas {sum(x[4] for x in filas)} u.{extra}")


def reporteIncidencias(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD, *OPER):
        return
    f = modIncidencias._filtrosGestion(conn, sesion)
    if f is None:
        return
    if sesion.perfil == PERFIL_OPERACIONES:
        f.agregar("i.id_asignado_a = %s", sesion.idUsuario)
    filas = modIncidencias._mostrar(conn, modIncidencias.SQL_INC + f.where() + " " + modIncidencias.ORDEN_SEVERIDAD, f.params)
    if not filas:
        return
    sev = {}
    for x in filas:
        sev[x[2]] = sev.get(x[2], 0) + 1
    print("Por severidad: " + " | ".join(f"{k}: {sev[k]}" for k in ("CRITICA", "ALTA", "MEDIA", "BAJA") if k in sev))
    prom = db.queryVal(
        conn, "SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion)),1) FROM incidencias i JOIN zonas z ON z.id_zona=i.id_zona "
              "JOIN tipos_incidencia ti ON ti.id_tipo_incidencia=i.id_tipo_incidencia JOIN usuarios ur ON ur.id_usuario=i.id_reportado_por "
              "LEFT JOIN usuarios ua ON ua.id_usuario=i.id_asignado_a LEFT JOIN actividades a ON a.id_actividad=i.id_actividad "
              + f.where() + (" AND " if f.condiciones else " WHERE ") + "i.fecha_resolucion IS NOT NULL", f.params)
    print("Tiempo promedio de atencion (resueltas o cerradas): " + (f"{prom} min" if prom is not None else "sin incidencias resueltas"))


def resumenEjecutivo(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idf = elegirFestival(conn, opcional=True) or db.queryVal(conn, "SELECT id_festival FROM festivales ORDER BY fecha DESC LIMIT 1")
    fecha = leerFecha("Filtrar por fecha", opcional=True)
    idz = elegirZona(conn)
    fa = Filtro()
    fa.agregar("z.id_festival = %s", idf)
    if fecha:
        fa.agregar("a.fecha = %s", fecha)
    if idz:
        fa.agregar("z.id_zona = %s", idz)
    base = "FROM actividades a JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona "
    porEstado = dict(db.queryAll(conn, "SELECT a.estado_actividad, COUNT(*) " + base + fa.where() + " GROUP BY a.estado_actividad", fa.params))
    if not porEstado:
        ui.msgAviso("Sin datos para la edicion seleccionada.")
        return
    cupo = db.queryVal(conn, "SELECT COALESCE(SUM(a.cupo),0) " + base + fa.where() + " AND a.estado_actividad <> 'CANCELADA'", fa.params)
    conf, espera = db.queryOne(
        conn, "SELECT COALESCE(SUM(r.estado_reservacion='CONFIRMADA'),0), COALESCE(SUM(r.estado_reservacion='ESPERA'),0) "
              "FROM reservaciones r JOIN actividades a ON a.id_actividad=r.id_actividad JOIN espacios e ON e.id_espacio=a.id_espacio "
              "JOIN zonas z ON z.id_zona=e.id_zona " + fa.where() + " AND a.estado_actividad <> 'CANCELADA'", fa.params)
    rec = dict(db.queryAll(conn, "SELECT IF(estado_recurso IN ('DISPONIBLE','ASIGNADO'),'disp','nodisp'), COUNT(*) FROM recursos GROUP BY 1"))
    fi = Filtro()
    fi.agregar("i.id_zona IN (SELECT id_zona FROM zonas WHERE id_festival = %s)", idf)
    if idz:
        fi.agregar("i.id_zona = %s", idz)
    if fecha:
        fi.agregar("DATE(i.fecha_creacion) = %s", fecha)
    inc = db.queryOne(
        conn, "SELECT COALESCE(SUM(i.estado_incidencia IN ('ABIERTA','ASIGNADA','EN_ATENCION')),0), "
              "COALESCE(SUM(i.estado_incidencia IN ('ABIERTA','ASIGNADA','EN_ATENCION') AND i.severidad='CRITICA'),0), "
              "ROUND(AVG(TIMESTAMPDIFF(MINUTE, i.fecha_creacion, i.fecha_resolucion)),1) FROM incidencias i " + fi.where(), fi.params)
    ocup = (float(conf) * 100 / float(cupo)) if cupo else 0.0
    ui.encabezado(sesion, "Resumen ejecutivo del festival")
    pares = [("Actividades PUBLICADAS", porEstado.get("PUBLICADA", 0)), ("Actividades CANCELADAS", porEstado.get("CANCELADA", 0)),
             ("Actividades FINALIZADAS", porEstado.get("FINALIZADA", 0)), ("Cupo total (sin canceladas)", cupo),
             ("Reservaciones confirmadas", int(conf)), ("Personas en espera", int(espera)), ("Ocupacion global %", f"{ocup:.1f}"),
             ("Recursos disponibles", rec.get("disp", 0)), ("Recursos no disponibles", rec.get("nodisp", 0)),
             ("Incidencias abiertas", int(inc[0])), ("Incidencias criticas abiertas", int(inc[1])),
             ("Tiempo promedio de atencion (min)", inc[2] if inc[2] is not None else "-")]
    ui.imprimirTabla([("Indicador", 46, False), ("Valor", 12, True)], pares)


def agendaOperativa(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    f = Filtro()
    fecha = leerFecha("Fecha", default=str(_fechaFestivalReciente(conn)))
    f.agregar("a.fecha = %s", fecha)
    print("\nFiltros (Enter omite)")
    for col, fn in (("z.id_zona", elegirZona), ("e.id_espacio", elegirEspacio), ("c.id_categoria", elegirCategoria)):
        v = fn(conn)
        if v:
            f.agregar(f"{col} = %s", v)
    est = leerOpcionLista("Estado", ["PUBLICADA", "CANCELADA", "FINALIZADA"], opcional=True)
    if est:
        f.agregar("a.estado_actividad = %s", est)
    sql = ("SELECT LEFT(a.hora_inicio,5), a.nombre_actividad, c.nombre, z.nombre, e.nombre, a.cupo, "
           "(SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad=a.id_actividad AND r.estado_reservacion='CONFIRMADA'), "
           "fn_cupo_disponible(a.id_actividad), "
           "(SELECT COUNT(*) FROM movimientos_recurso m WHERE m.id_actividad=a.id_actividad), "
           "(SELECT COUNT(*) FROM movimientos_recurso m WHERE m.id_actividad=a.id_actividad AND m.estado_movimiento IN ('ASIGNADO','ENTREGADO')), "
           "(SELECT COUNT(*) FROM incidencias i WHERE i.id_actividad=a.id_actividad AND i.estado_incidencia IN ('ABIERTA','ASIGNADA','EN_ATENCION')), "
           "a.estado_actividad "
           "FROM actividades a JOIN categorias_actividad c ON c.id_categoria=a.id_categoria "
           "JOIN espacios e ON e.id_espacio=a.id_espacio JOIN zonas z ON z.id_zona=e.id_zona " + f.where() +
           " ORDER BY a.hora_inicio, a.id_actividad")
    filas = db.selectTabla(conn, sql, f.params, [
        ("Hora", 5, False), ("Actividad", 24, False), ("Categoria", 12, False), ("Zona", 12, False), ("Espacio", 12, False),
        ("Cupo", 4, True), ("Conf", 4, True), ("Disp", 4, True), ("RecAs", 5, True), ("RecPend", 7, True), ("IncAb", 5, True),
        ("Estado", 10, False)])
    if filas:
        print(f"Totales: actividades {len(filas)} | alertas: recursos pendientes {sum(x[9] for x in filas)}, "
              f"incidencias abiertas {sum(x[10] for x in filas)}")
