"""
@package IberoLiveOps
@summary Modulo 3: catalogos, inventario, asignacion, entrega y devolucion de recursos
@author Kilian Ian Pérez García
@date 22 de noviembre de 2026
"""
import db
import ui
from auth import requierePerfil, PERFIL_COORDINACION, PERFIL_OPERACIONES
from filtros import (Filtro, elegirCategoriaRecurso, elegirZona, elegirTipoIncidencia,
                     pedirBusqueda)
from util import (leerTexto, leerEntero, leerFecha, leerFechaHora, leerOpcionLista,
                  confirmar, pausar)

COORD = (PERFIL_COORDINACION,)
OPER = (PERFIL_OPERACIONES,)

SQL_INVENTARIO = (
    "SELECT r.id_recurso, cr.nombre, r.nombre_recurso, r.cantidad_total, "
    "r.cantidad_total - fn_recurso_disponible(r.id_recurso), fn_recurso_disponible(r.id_recurso), "
    "r.ubicacion, r.estado_recurso, "
    "(SELECT a.nombre_actividad FROM movimientos_recurso m JOIN actividades a ON a.id_actividad = m.id_actividad "
    " WHERE m.id_recurso = r.id_recurso AND m.estado_movimiento IN ('ASIGNADO','ENTREGADO') "
    " ORDER BY m.fecha_entrega LIMIT 1) "
    "FROM recursos r JOIN categorias_recurso cr ON cr.id_categoria_recurso = r.id_categoria_recurso "
)
COLS_INVENTARIO = [("ID", 4, True), ("Categoria", 14, False), ("Recurso", 30, False), ("Total", 5, True),
                   ("Asig", 4, True), ("Disp", 4, True), ("Ubicacion", 18, False), ("Estado", 13, False),
                   ("Proxima actividad", 24, False)]


def pedirFiltrosInventario(conn):
    f = Filtro()
    print("\nFiltros (Enter omite)")
    idc = elegirCategoriaRecurso(conn)
    if idc:
        f.agregar("r.id_categoria_recurso = %s", idc)
    est = leerOpcionLista("Estado", ["DISPONIBLE", "ASIGNADO", "DANADO", "PERDIDO", "MANTENIMIENTO"], opcional=True)
    if est:
        f.agregar("r.estado_recurso = %s", est)
    ubic = pedirBusqueda("Buscar por ubicacion: ")
    if ubic:
        f.agregar("r.ubicacion LIKE %s", ubic)
    disp = leerOpcionLista("Solo con unidades disponibles", ["S", "N"], opcional=True)
    if disp == "S":
        f.agregar("fn_recurso_disponible(r.id_recurso) > 0")
    txt = pedirBusqueda("Buscar recurso: ")
    if txt:
        f.agregar("r.nombre_recurso LIKE %s", txt)
    return f


def consultarInventario(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD, *OPER):
        return
    f = pedirFiltrosInventario(conn)
    filas = db.selectTabla(conn, SQL_INVENTARIO + f.where() + " ORDER BY cr.nombre, r.nombre_recurso", f.params, COLS_INVENTARIO)
    if filas:
        print(f"Totales: unidades {sum(x[3] for x in filas)} | asignadas {sum(x[4] for x in filas)} | disponibles {sum(x[5] for x in filas)}")


def menuRecursosCoordinacion(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    while True:
        opcion = ui.menu(sesion, "Recursos", [
            "Consultar inventario", "Crear categoria de recurso", "Crear recurso",
            "Actualizar recurso", "Historial de movimientos de un recurso"])
        if opcion == 0:
            return
        {1: consultarInventario, 2: crearCategoriaRecurso, 3: crearRecurso,
         4: actualizarRecurso, 5: historialRecurso}[opcion](conn, sesion)
        pausar()


def crearCategoriaRecurso(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    nombre = leerTexto("Nombre de la categoria: ", 2, 80)
    desc = leerTexto("Descripcion: ", 1, 300)
    if db.queryVal(conn, "SELECT COUNT(*) FROM categorias_recurso WHERE nombre=%s", (nombre,)):
        ui.msgError("Nombre duplicado.")
        return
    _, nuevo = db.execute(conn, "INSERT INTO categorias_recurso (nombre, descripcion) VALUES (%s,%s)", (nombre, desc))
    ui.msgExito(f"Recurso guardado. Categoria folio: {nuevo}.")


def crearRecurso(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idc = elegirCategoriaRecurso(conn, opcional=False)
    nombre = leerTexto("Nombre del recurso (3-100): ", 3, 100)
    total = leerEntero("Cantidad total (mayor que cero): ", 1, 100000)
    ubic = leerTexto("Ubicacion (zona, almacen o espacio): ", 1, 120)
    estado = leerOpcionLista("Estado inicial", ["DISPONIBLE", "MANTENIMIENTO", "DANADO", "PERDIDO"])
    obs = leerTexto("Observaciones (obligatorias si no es DISPONIBLE): ", 1 if estado != "DISPONIBLE" else 1, 300,
                     opcional=(estado == "DISPONIBLE"))
    if db.queryVal(conn, "SELECT COUNT(*) FROM recursos WHERE nombre_recurso=%s", (nombre,)):
        ui.msgError("Nombre duplicado: ya existe un recurso con ese nombre.")
        return
    _, nuevo = db.execute(
        conn, "INSERT INTO recursos (id_categoria_recurso,nombre_recurso,cantidad_total,ubicacion,estado_recurso,observaciones) "
              "VALUES (%s,%s,%s,%s,%s,%s)", (idc, nombre, total, ubic, estado, obs))
    ui.msgExito(f"Recurso guardado. Folio: {nuevo}.")


def actualizarRecurso(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idr = leerEntero("ID del recurso (0 = volver): ", 0, 10**9)
    if idr == 0:
        return
    try:
        with db.transaccion(conn):
            r = db.queryOne(conn, "SELECT nombre_recurso, cantidad_total, ubicacion, estado_recurso, observaciones "
                                   "FROM recursos WHERE id_recurso=%s FOR UPDATE", (idr,))
            if r is None:
                raise db.DBError("Recurso no encontrado.", negocio=True)
            fuera = r[1] - db.queryVal(conn, "SELECT fn_recurso_disponible(%s)", (idr,))
            print(f"\n{r[0]} | total {r[1]} | unidades fuera {fuera} | estado {r[3]}")
            print("(Enter conserva el valor actual)")
            total = leerEntero(f"Cantidad total [{r[1]}]: ", 1, 100000, opcional=True) or r[1]
            ubic = leerTexto(f"Ubicacion [{r[2]}]: ", 1, 120, opcional=True) or r[2]
            estado = leerOpcionLista(f"Estado (actual {r[3]})", ["DISPONIBLE", "ASIGNADO", "DANADO", "PERDIDO", "MANTENIMIENTO"], opcional=True) or r[3]
            if total < fuera:
                raise db.DBError(f"Cantidad invalida: hay {fuera} unidades asignadas o entregadas.", negocio=True)
            obs = r[4]
            if estado != r[3]:
                if estado in ("DISPONIBLE", "ASIGNADO") and fuera == 0 and estado == "ASIGNADO":
                    raise db.DBError("Recurso sin asignaciones activas: no puede marcarse ASIGNADO.", negocio=True)
                if estado == "DISPONIBLE" and fuera > 0:
                    raise db.DBError("Recurso con asignacion activa: no puede marcarse DISPONIBLE.", negocio=True)
                obs = leerTexto("Observacion del cambio de estado (obligatoria): ", 3, 300)
                if estado in ("PERDIDO",) and not confirmar("Se registrara la PERDIDA del recurso."):
                    raise db.DBError("Operacion cancelada.", negocio=True)
            db.execute(conn, "UPDATE recursos SET cantidad_total=%s, ubicacion=%s, estado_recurso=%s, observaciones=%s WHERE id_recurso=%s",
                       (total, ubic, estado, obs, idr))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Recurso guardado.")


COLS_MOVS = [("Mov", 4, True), ("Recurso", 26, False), ("Actividad", 24, False), ("Cant", 4, True),
             ("Responsable", 15, False), ("Entrega", 16, False), ("Dev.prevista", 16, False),
             ("Dev.real", 16, False), ("Estado", 12, False), ("Observaciones", 24, False)]
SQL_MOVS = ("SELECT m.id_movimiento, r.nombre_recurso, a.nombre_actividad, m.cantidad_asignada, u.nombre_usuario, "
            "m.fecha_entrega, m.fecha_devolucion_prevista, m.fecha_devolucion_real, m.estado_movimiento, m.observaciones "
            "FROM movimientos_recurso m JOIN recursos r ON r.id_recurso = m.id_recurso "
            "JOIN actividades a ON a.id_actividad = m.id_actividad JOIN usuarios u ON u.id_usuario = m.id_responsable ")


def historialRecurso(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD, *OPER):
        return
    idr = leerEntero("ID del recurso (0 = volver): ", 0, 10**9)
    if idr == 0:
        return
    db.selectTabla(conn, SQL_MOVS + "WHERE m.id_recurso = %s ORDER BY m.fecha_entrega DESC", (idr,), COLS_MOVS)


def menuRecursosOperaciones(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    while True:
        opcion = ui.menu(sesion, "Recursos y movimientos", [
            "Consultar inventario y existencias", "Consultar movimientos", "Asignar recurso a una actividad",
            "Registrar entrega", "Registrar devolucion / dano / perdida / mantenimiento"])
        if opcion == 0:
            return
        {1: consultarInventario, 2: consultarMovimientos, 3: asignarRecurso,
         4: registrarEntrega, 5: registrarDevolucion}[opcion](conn, sesion)
        pausar()


def consultarMovimientos(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER, *COORD):
        return
    f = Filtro()
    print("\nFiltros (Enter omite)")
    fecha = leerFecha("Fecha de entrega", opcional=True)
    if fecha:
        f.agregar("DATE(m.fecha_entrega) = %s", fecha)
    ida = leerEntero("ID de actividad: ", 1, 10**9, opcional=True)
    if ida:
        f.agregar("m.id_actividad = %s", ida)
    idc = elegirCategoriaRecurso(conn)
    if idc:
        f.agregar("r.id_categoria_recurso = %s", idc)
    idr = leerEntero("ID de recurso: ", 1, 10**9, opcional=True)
    if idr:
        f.agregar("m.id_recurso = %s", idr)
    est = leerOpcionLista("Estado", ["ASIGNADO", "ENTREGADO", "DEVUELTO", "DANADO", "PERDIDO", "MANTENIMIENTO"], opcional=True)
    if est:
        f.agregar("m.estado_movimiento = %s", est)
    pend = leerOpcionLista("Solo devoluciones pendientes", ["S", "N"], opcional=True)
    if pend == "S":
        f.agregar("m.estado_movimiento IN ('ASIGNADO','ENTREGADO')")
    db.selectTabla(conn, SQL_MOVS + f.where() + " ORDER BY m.fecha_entrega DESC, m.id_movimiento DESC", f.params, COLS_MOVS)


def asignarRecurso(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    print("\nAsignacion de recurso (/c cancela)")
    ida = leerEntero("ID de la actividad destino: ", 1, 10**9)
    act = db.queryOne(conn, "SELECT nombre_actividad, estado_actividad FROM actividades WHERE id_actividad=%s", (ida,))
    if act is None:
        ui.msgError("Actividad no encontrada.")
        return
    print(f"Actividad: {act[0]} ({act[1]})")
    idr = leerEntero("ID del recurso: ", 1, 10**9)
    rec = db.queryOne(conn, "SELECT nombre_recurso, estado_recurso, fn_recurso_disponible(id_recurso) FROM recursos WHERE id_recurso=%s", (idr,))
    if rec is None:
        ui.msgError("Recurso no encontrado.")
        return
    print(f"Recurso: {rec[0]} | estado {rec[1]} | disponible {rec[2]}")
    cant = leerEntero("Cantidad a asignar: ", 1, 100000)
    entrega = leerFechaHora("Entrega")
    devol = leerFechaHora("Devolucion prevista")
    obs = leerTexto("Observacion (opcional): ", 1, 300, opcional=True)
    if not confirmar(f"Se asignaran {cant} unidad(es) de '{rec[0]}'."):
        ui.msgAviso("Operacion cancelada.")
        return
    try:
        r = db.callSp(conn, "sp_asignar_recurso", (sesion.idUsuario, idr, ida, cant, entrega, devol, obs), ("mov",))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito(f"Asignacion registrada. Movimiento: {r['mov']}.")


def registrarEntrega(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    idm = leerEntero("ID del movimiento a entregar (0 = volver): ", 0, 10**9)
    if idm == 0:
        return
    try:
        with db.transaccion(conn):
            m = db.queryOne(conn, "SELECT estado_movimiento, id_recurso FROM movimientos_recurso WHERE id_movimiento=%s FOR UPDATE", (idm,))
            if m is None:
                raise db.DBError("Movimiento no encontrado.", negocio=True)
            if m[0] != "ASIGNADO":
                raise db.DBError(f"Solo un movimiento ASIGNADO puede entregarse (estado actual: {m[0]}).", negocio=True)
            db.execute(conn, "UPDATE movimientos_recurso SET estado_movimiento='ENTREGADO', fecha_entrega=NOW(), id_responsable=%s "
                             "WHERE id_movimiento=%s", (sesion.idUsuario, idm))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Entrega registrada.")


def registrarDevolucion(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    idm = leerEntero("ID del movimiento (0 = volver): ", 0, 10**9)
    if idm == 0:
        return
    m = db.queryOne(
        conn, "SELECT r.nombre_recurso, m.cantidad_asignada, m.estado_movimiento, a.id_actividad, a.nombre_actividad "
              "FROM movimientos_recurso m JOIN recursos r ON r.id_recurso=m.id_recurso "
              "JOIN actividades a ON a.id_actividad=m.id_actividad WHERE m.id_movimiento=%s", (idm,))
    if m is None:
        ui.msgError("Movimiento no encontrado.")
        return
    print(f"\n{m[0]} | actividad: {m[4]} | asignadas: {m[1]} | estado: {m[2]}")
    if m[2] not in ("ASIGNADO", "ENTREGADO"):
        ui.msgError("El movimiento ya fue cerrado.")
        return
    final = leerOpcionLista("Estado final", ["DEVUELTO", "DANADO", "PERDIDO", "MANTENIMIENTO"])
    recibida = leerEntero(f"Cantidad recibida (0 a {m[1]}): ", 0, m[1])
    obs = leerTexto("Observaciones" + ("" if final == "DEVUELTO" else " (obligatorias)") + ": ", 3 if final != "DEVUELTO" else 1, 300,
                     opcional=(final == "DEVUELTO"))
    if final == "PERDIDO" and not confirmar("Se registrara la PERDIDA del recurso."):
        ui.msgAviso("Operacion cancelada.")
        return
    try:
        db.callSp(conn, "sp_registrar_devolucion", (sesion.idUsuario, idm, recibida, final, obs))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Devolucion registrada.")
    if final != "DEVUELTO" and confirmar("¿Desea registrar tambien una incidencia de recurso?"):
        _incidenciaDeRecurso(conn, sesion, m, final, obs)


def _incidenciaDeRecurso(conn, sesion, mov, final, obs):
    idz = elegirZona(conn, opcional=False)
    tipo = db.queryVal(conn, "SELECT id_tipo_incidencia FROM tipos_incidencia WHERE nombre LIKE 'Recurso%' LIMIT 1") or elegirTipoIncidencia(conn, opcional=False)
    sev = "ALTA" if final in ("PERDIDO", "DANADO") else "MEDIA"
    desc = f"Recurso {mov[0]} reportado como {final}: {obs}"[:500]
    try:
        r = db.callSp(conn, "sp_registrar_incidencia",
                       (sesion.idUsuario, tipo, idz, sev, desc, f"Actividad: {mov[4]}"[:150], mov[3]), ("folio",))
    except db.DBError as e:
        ui.msgError(e.mensaje)
        return
    ui.msgExito(f"Incidencia de recurso registrada. Folio: {r['folio']}.")
