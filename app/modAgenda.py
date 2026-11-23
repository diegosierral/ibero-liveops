"""
@package IberoLiveOps
@summary Modulo 2: festival, zonas, espacios, actividades, agenda y reservaciones
@author Kilian Ian Pérez García
@date 22 de noviembre de 2026
"""
import db
import ui
from auth import (requierePerfil, PERFIL_COORDINACION, PERFIL_OPERACIONES, PERFIL_PARTICIPANTE)
from filtros import (Filtro, elegirFestival, elegirZona, elegirEspacio, elegirCategoria,
                     pedirBusqueda)
from util import (leerTexto, leerEntero, leerFecha, leerHora, leerOpcionLista, confirmar,
                  pausar)

COORD = (PERFIL_COORDINACION,)
OPER = (PERFIL_OPERACIONES,)
PART = (PERFIL_PARTICIPANTE,)

SQL_AGENDA = (
    "SELECT a.id_actividad, a.nombre_actividad, c.nombre, a.fecha, "
    "CONCAT(LEFT(a.hora_inicio,5),'-',LEFT(a.hora_fin,5)), z.nombre, e.nombre, a.cupo, "
    "(SELECT COUNT(*) FROM reservaciones r WHERE r.id_actividad = a.id_actividad AND r.estado_reservacion = 'CONFIRMADA'), "
    "fn_cupo_disponible(a.id_actividad), a.estado_actividad "
    "FROM actividades a "
    "JOIN categorias_actividad c ON c.id_categoria = a.id_categoria "
    "JOIN espacios e ON e.id_espacio = a.id_espacio "
    "JOIN zonas z ON z.id_zona = e.id_zona "
)
COLS_AGENDA = [("ID", 4, True), ("Actividad", 26, False), ("Categoria", 14, False), ("Fecha", 10, False),
               ("Horario", 11, False), ("Zona", 14, False), ("Espacio", 14, False), ("Cupo", 4, True),
               ("Conf", 4, True), ("Disp", 4, True), ("Estado", 10, False)]

ORDEN_AGENDA = "ORDER BY a.fecha, a.hora_inicio, a.id_actividad"


def pedirFiltrosAgenda(conn, modo):
    f = Filtro()
    print("\nFiltros (Enter omite el filtro; /c cancela)")
    if modo == "part":
        f.agregar("a.estado_actividad = 'PUBLICADA'")
    fecha = leerFecha("Fecha", opcional=True)
    if fecha:
        f.agregar("a.fecha = %s", fecha)
    if modo == "part":
        desde = leerHora("Hora de inicio desde", opcional=True)
        hasta = leerHora("Hora de inicio hasta", opcional=True)
        if desde and hasta and hasta < desde:
            ui.msgDatoInvalido("Filtros invalidos: la hora final es anterior a la inicial.")
            return None
        if desde:
            f.agregar("a.hora_inicio >= %s", desde)
        if hasta:
            f.agregar("a.hora_inicio <= %s", hasta)
    idz = elegirZona(conn)
    if idz:
        f.agregar("z.id_zona = %s", idz)
    if modo in ("coord", "oper"):
        ide = elegirEspacio(conn)
        if ide:
            f.agregar("e.id_espacio = %s", ide)
    idc = elegirCategoria(conn)
    if idc:
        f.agregar("c.id_categoria = %s", idc)
    if modo in ("coord", "oper"):
        est = leerOpcionLista("Estado", ["PUBLICADA", "CANCELADA", "FINALIZADA"], opcional=True)
        if est:
            f.agregar("a.estado_actividad = %s", est)
    if modo in ("coord", "part"):
        disp = leerOpcionLista("Solo con lugares disponibles", ["S", "N"], opcional=True)
        if disp == "S":
            f.agregar("fn_cupo_disponible(a.id_actividad) > 0")
    txt = pedirBusqueda("Buscar por nombre: ")
    if txt:
        f.agregar("a.nombre_actividad LIKE %s", txt)
    return f


def mostrarAgenda(conn, sesion, modo):
    f = pedirFiltrosAgenda(conn, modo)
    if f is None:
        return
    sql = SQL_AGENDA + f.where() + " " + ORDEN_AGENDA
    filas = db.selectTabla(conn, sql, f.params, COLS_AGENDA)
    if not filas:
        return
    while True:
        acc = "0 = volver"
        if modo == "part":
            acc = "0 = volver, -1 = reservar una actividad"
        v = leerEntero(f"\nID para ver detalle ({acc}): ", -1 if modo == "part" else 0, 10**9)
        if v == 0:
            return
        if v == -1:
            crearReservacion(conn, sesion)
            return
        detalleActividad(conn, v, soloPublicada=(modo == "part"))


def detalleActividad(conn, idActividad, soloPublicada=False):
    sql = ("SELECT a.id_actividad, a.nombre_actividad, a.descripcion, c.nombre, a.fecha, "
           "CONCAT(LEFT(a.hora_inicio,5),'-',LEFT(a.hora_fin,5)), z.nombre, e.nombre, a.cupo, "
           "fn_cupo_disponible(a.id_actividad), a.estado_actividad "
           "FROM actividades a JOIN categorias_actividad c ON c.id_categoria = a.id_categoria "
           "JOIN espacios e ON e.id_espacio = a.id_espacio JOIN zonas z ON z.id_zona = e.id_zona "
           "WHERE a.id_actividad = %s")
    params = [idActividad]
    if soloPublicada:
        sql += " AND a.estado_actividad = 'PUBLICADA'"
    fila = db.queryOne(conn, sql, params)
    if fila is None:
        ui.msgError("Actividad no encontrada o no disponible.")
        return None
    etiquetas = ["ID", "Actividad", "Descripcion", "Categoria", "Fecha", "Horario", "Zona", "Espacio",
                 "Cupo", "Lugares disponibles", "Estado"]
    print()
    for e, v in zip(etiquetas, fila):
        print(f"  {e:<20}: {ui.formatear(v)}")
    return fila


def crearReservacion(conn, sesion):
    if not requierePerfil(conn, sesion, *PART):
        return
    ui.encabezado(sesion, "Crear reservacion")
    ida = leerEntero("ID de la actividad a reservar (0 = volver): ", 0, 10**9)
    if ida == 0:
        return
    fila = detalleActividad(conn, ida, soloPublicada=True)
    if fila is None:
        return
    if fila[9] == 0:
        ui.msgAviso("Cupo agotado: la solicitud quedara en lista de espera.")
    if not confirmar("Se registrara su solicitud para esta actividad."):
        ui.msgAviso("Operacion cancelada.")
        return
    try:
        r = db.callSp(conn, "sp_crear_reservacion", (sesion.idUsuario, ida), ("folio", "estado", "posicion"))
    except db.DBError as e:
        ui.msgError(e.mensaje if e.negocio else e.mensaje + " No se guardaron cambios.")
        return
    if r["estado"] == "CONFIRMADA":
        ui.msgExito(f"Reservacion confirmada. Folio: {r['folio']}.")
    else:
        ui.msgExito(f"No hay lugares disponibles. La solicitud quedo en lista de espera, posicion {r['posicion']}. Folio: {r['folio']}.")


SQL_MIS_RESERVAS = (
    "SELECT r.id_reservacion, a.nombre_actividad, a.fecha, CONCAT(LEFT(a.hora_inicio,5),'-',LEFT(a.hora_fin,5)), "
    "z.nombre, e.nombre, r.estado_reservacion, r.posicion_espera, r.fecha_solicitud, r.fecha_cancelacion "
    "FROM reservaciones r JOIN actividades a ON a.id_actividad = r.id_actividad "
    "JOIN espacios e ON e.id_espacio = a.id_espacio JOIN zonas z ON z.id_zona = e.id_zona "
)
COLS_MIS_RESERVAS = [("Folio", 5, True), ("Actividad", 26, False), ("Fecha", 10, False), ("Horario", 11, False),
                     ("Zona", 14, False), ("Espacio", 14, False), ("Estado", 10, False), ("Pos", 3, True),
                     ("Solicitud", 16, False), ("Cancelacion", 16, False)]


def misReservaciones(conn, sesion):
    if not requierePerfil(conn, sesion, *PART):
        return
    while True:
        opcion = ui.menu(sesion, "Mis reservaciones", ["Consultar historial", "Cancelar una reservacion"])
        if opcion == 0:
            return
        if opcion == 1:
            historialReservaciones(conn, sesion)
            pausar()
        else:
            cancelarReservacion(conn, sesion)
            pausar()


def historialReservaciones(conn, sesion):
    f = Filtro()
    f.agregar("r.id_participante = %s", sesion.idUsuario)
    print("\nFiltros (Enter omite)")
    est = leerOpcionLista("Estado", ["CONFIRMADA", "ESPERA", "CANCELADA"], opcional=True)
    if est:
        f.agregar("r.estado_reservacion = %s", est)
    desde = leerFecha("Fecha de la actividad desde", opcional=True)
    hasta = leerFecha("Fecha de la actividad hasta", opcional=True)
    if desde and hasta and hasta < desde:
        ui.msgDatoInvalido("Filtros invalidos: la fecha final es anterior a la inicial.")
        return
    if desde:
        f.agregar("a.fecha >= %s", desde)
    if hasta:
        f.agregar("a.fecha <= %s", hasta)
    txt = pedirBusqueda("Buscar actividad: ")
    if txt:
        f.agregar("a.nombre_actividad LIKE %s", txt)
    sql = SQL_MIS_RESERVAS + f.where() + " ORDER BY r.fecha_solicitud DESC, r.id_reservacion DESC"
    filas = db.selectTabla(conn, sql, f.params, COLS_MIS_RESERVAS)
    if filas:
        totales = db.queryAll(
            conn,
            "SELECT r.estado_reservacion, COUNT(*) FROM reservaciones r JOIN actividades a ON a.id_actividad = r.id_actividad "
            + f.where() + " GROUP BY r.estado_reservacion", f.params)
        print("Totales: " + " | ".join(f"{e}: {n}" for e, n in totales))


def cancelarReservacion(conn, sesion):
    if not requierePerfil(conn, sesion, *PART):
        return
    idr = leerEntero("Folio de la reservacion a cancelar (0 = volver): ", 0, 10**9)
    if idr == 0:
        return
    fila = db.queryOne(
        conn,
        "SELECT a.nombre_actividad, r.estado_reservacion FROM reservaciones r "
        "JOIN actividades a ON a.id_actividad = r.id_actividad "
        "WHERE r.id_reservacion = %s AND r.id_participante = %s",
        (idr, sesion.idUsuario),
    )
    if fila is None:
        ui.msgPermisoDenegado()
        print("La reservacion no existe o no le pertenece.")
        return
    if fila[1] == "CANCELADA":
        ui.msgAviso("La reservacion ya estaba cancelada.")
        return
    if not confirmar(f"Esta accion cambiara el estado de '{fila[0]}' a CANCELADA."):
        ui.msgAviso("Operacion cancelada.")
        return
    try:
        r = db.callSp(conn, "sp_cancelar_reservacion", (sesion.idUsuario, idr), ("promovida",))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Reservacion cancelada.")
    if r["promovida"]:
        print(f"Se libero un lugar: la siguiente persona en espera fue promovida (folio {r['promovida']}).")


def menuAgendaOperaciones(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER):
        return
    while True:
        opcion = ui.menu(sesion, "Agenda y listas", ["Ver agenda", "Lista de participantes de una actividad"])
        if opcion == 0:
            return
        if opcion == 1:
            mostrarAgenda(conn, sesion, "oper")
        else:
            listaParticipantes(conn, sesion)
        pausar()


def listaParticipantes(conn, sesion):
    if not requierePerfil(conn, sesion, *OPER, *COORD):
        return
    ida = leerEntero("ID de la actividad (0 = volver): ", 0, 10**9)
    if ida == 0:
        return
    act = db.queryOne(conn, "SELECT nombre_actividad, estado_actividad, cupo FROM actividades WHERE id_actividad = %s", (ida,))
    if act is None:
        ui.msgError("Actividad no encontrada.")
        return
    print(f"\nActividad: {act[0]} | Estado: {act[1]} | Cupo: {act[2]}")
    if act[1] == "CANCELADA":
        ui.msgAviso("Actividad CANCELADA: las reservaciones aparecen canceladas.")
    est = leerOpcionLista("Estado de la reservacion", ["CONFIRMADA", "ESPERA", "CANCELADA"], opcional=True)
    f = Filtro()
    f.agregar("r.id_actividad = %s", ida)
    if est:
        f.agregar("r.estado_reservacion = %s", est)
    else:
        f.agregar("r.estado_reservacion IN ('CONFIRMADA','ESPERA')")
    sql = ("SELECT u.nombre_usuario, u.nombre_mostrar, r.estado_reservacion, r.posicion_espera, r.fecha_solicitud "
           "FROM reservaciones r JOIN usuarios u ON u.id_usuario = r.id_participante " + f.where() +
           " ORDER BY r.estado_reservacion, r.posicion_espera, r.fecha_solicitud")
    filas = db.selectTabla(conn, sql, f.params,
                            [("Usuario", 18, False), ("Nombre", 24, False), ("Estado", 10, False),
                             ("Posicion", 8, True), ("Solicitud", 16, False)])
    if not filas:
        print("Actividad sin reservaciones para ese filtro.")


def menuFestivalZonasEspacios(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    while True:
        opcion = ui.menu(sesion, "Festival, zonas y espacios", [
            "Consultar festivales", "Crear festival", "Actualizar festival",
            "Consultar zonas", "Crear zona", "Actualizar zona",
            "Consultar espacios", "Crear espacio", "Actualizar espacio"])
        if opcion == 0:
            return
        acciones = {1: listarFestivales, 2: crearFestival, 3: actualizarFestival,
                    4: listarZonas, 5: crearZona, 6: actualizarZona,
                    7: listarEspacios, 8: crearEspacio, 9: actualizarEspacio}
        acciones[opcion](conn, sesion)
        pausar()


def listarFestivales(conn, sesion):
    db.selectTabla(
        conn,
        "SELECT f.id_festival, f.nombre, f.fecha, LEFT(f.hora_inicio,5), LEFT(f.hora_fin,5), "
        "(SELECT COUNT(*) FROM zonas z WHERE z.id_festival = f.id_festival), "
        "(SELECT COUNT(*) FROM actividades a JOIN espacios e ON e.id_espacio = a.id_espacio "
        " JOIN zonas z ON z.id_zona = e.id_zona WHERE z.id_festival = f.id_festival) "
        "FROM festivales f ORDER BY f.fecha DESC", (),
        [("ID", 4, True), ("Festival", 34, False), ("Fecha", 10, False), ("Inicio", 6, False),
         ("Fin", 6, False), ("Zonas", 6, True), ("Actividades", 11, True)])


def crearFestival(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    nombre = leerTexto("Nombre del festival: ", 3, 120)
    fecha = leerFecha("Fecha")
    ini = leerHora("Hora inicial")
    fin = leerHora("Hora final")
    if fin <= ini:
        ui.msgDatoInvalido("La hora final debe ser mayor que la hora inicial.")
        return
    if db.queryVal(conn, "SELECT COUNT(*) FROM festivales WHERE nombre = %s", (nombre,)):
        ui.msgError("Nombre duplicado: ya existe un festival con ese nombre.")
        return
    _, nuevo = db.execute(conn, "INSERT INTO festivales (nombre, fecha, hora_inicio, hora_fin) VALUES (%s,%s,%s,%s)",
                          (nombre, fecha, ini, fin))
    ui.msgExito(f"Registro guardado. Folio: {nuevo}.")


def actualizarFestival(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idf = elegirFestival(conn, opcional=False)
    fila = db.queryOne(conn, "SELECT nombre, fecha, LEFT(hora_inicio,5), LEFT(hora_fin,5) FROM festivales WHERE id_festival = %s", (idf,))
    if fila is None:
        ui.msgError("Edicion no encontrada.")
        return
    print("(Enter conserva el valor actual)")
    nombre = leerTexto(f"Nombre [{fila[0]}]: ", 3, 120, opcional=True) or fila[0]
    fecha = leerFecha("Fecha", default=ui.formatear(fila[1]))
    ini = leerHora(f"Hora inicial [{fila[2]}]", opcional=True) or fila[2]
    fin = leerHora(f"Hora final [{fila[3]}]", opcional=True) or fila[3]
    if fin <= ini:
        ui.msgDatoInvalido("La hora final debe ser mayor que la hora inicial.")
        return
    nAct = db.queryVal(
        conn, "SELECT COUNT(*) FROM actividades a JOIN espacios e ON e.id_espacio = a.id_espacio "
              "JOIN zonas z ON z.id_zona = e.id_zona WHERE z.id_festival = %s", (idf,))
    if fecha != ui.formatear(fila[1]) and nAct:
        ui.msgError(f"No se puede cambiar la fecha: la edicion tiene {nAct} actividad(es) programadas en la fecha actual.")
        return
    if db.queryVal(conn, "SELECT COUNT(*) FROM festivales WHERE nombre = %s AND id_festival <> %s", (nombre, idf)):
        ui.msgError("Nombre duplicado.")
        return
    db.execute(conn, "UPDATE festivales SET nombre=%s, fecha=%s, hora_inicio=%s, hora_fin=%s WHERE id_festival=%s",
               (nombre, fecha, ini, fin, idf))
    ui.msgExito("Registro guardado.")


def listarZonas(conn, sesion):
    db.selectTabla(
        conn,
        "SELECT z.id_zona, z.nombre, z.descripcion, f.nombre, "
        "(SELECT COUNT(*) FROM espacios e WHERE e.id_zona = z.id_zona) "
        "FROM zonas z JOIN festivales f ON f.id_festival = z.id_festival ORDER BY f.fecha DESC, z.nombre", (),
        [("ID", 4, True), ("Zona", 24, False), ("Descripcion", 44, False), ("Festival", 26, False), ("Espacios", 8, True)])


def crearZona(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idf = elegirFestival(conn, opcional=False)
    nombre = leerTexto("Nombre de la zona: ", 2, 100)
    desc = leerTexto("Descripcion: ", 1, 300)
    if db.queryVal(conn, "SELECT COUNT(*) FROM zonas WHERE id_festival = %s AND nombre = %s", (idf, nombre)):
        ui.msgError("Nombre duplicado: ya existe una zona con ese nombre en el festival.")
        return
    _, nuevo = db.execute(conn, "INSERT INTO zonas (id_festival, nombre, descripcion) VALUES (%s,%s,%s)", (idf, nombre, desc))
    ui.msgExito(f"Registro guardado. Folio: {nuevo}.")


def actualizarZona(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idz = elegirZona(conn, opcional=False)
    fila = db.queryOne(conn, "SELECT id_festival, nombre, descripcion FROM zonas WHERE id_zona = %s", (idz,))
    nombre = leerTexto(f"Nombre [{fila[1]}]: ", 2, 100, opcional=True) or fila[1]
    desc = leerTexto(f"Descripcion [{fila[2][:40]}]: ", 1, 300, opcional=True) or fila[2]
    if db.queryVal(conn, "SELECT COUNT(*) FROM zonas WHERE id_festival=%s AND nombre=%s AND id_zona<>%s", (fila[0], nombre, idz)):
        ui.msgError("Nombre duplicado en el festival.")
        return
    db.execute(conn, "UPDATE zonas SET nombre=%s, descripcion=%s WHERE id_zona=%s", (nombre, desc, idz))
    ui.msgExito("Registro guardado.")


def listarEspacios(conn, sesion):
    f = Filtro()
    print("\nFiltros (Enter omite)")
    idz = elegirZona(conn)
    if idz:
        f.agregar("z.id_zona = %s", idz)
    est = leerOpcionLista("Estado", ["DISPONIBLE", "NO_DISPONIBLE"], opcional=True)
    if est:
        f.agregar("e.estado_espacio = %s", est)
    txt = pedirBusqueda("Buscar espacio: ")
    if txt:
        f.agregar("e.nombre LIKE %s", txt)
    db.selectTabla(
        conn,
        "SELECT e.id_espacio, e.nombre, z.nombre, e.ubicacion, e.aforo, e.estado_espacio, "
        "(SELECT COUNT(*) FROM actividades a WHERE a.id_espacio = e.id_espacio AND a.estado_actividad <> 'CANCELADA') "
        "FROM espacios e JOIN zonas z ON z.id_zona = e.id_zona " + f.where() + " ORDER BY z.nombre, e.nombre",
        f.params,
        [("ID", 4, True), ("Espacio", 26, False), ("Zona", 22, False), ("Ubicacion", 28, False),
         ("Aforo", 5, True), ("Estado", 13, False), ("Actividades", 11, True)])


def crearEspacio(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idz = elegirZona(conn, opcional=False)
    nombre = leerTexto("Nombre del espacio: ", 2, 100)
    ubic = leerTexto("Ubicacion: ", 1, 150)
    aforo = leerEntero("Aforo (entero mayor que cero): ", 1, 100000)
    est = leerOpcionLista("Estado", ["DISPONIBLE", "NO_DISPONIBLE"])
    if db.queryVal(conn, "SELECT COUNT(*) FROM espacios WHERE id_zona=%s AND nombre=%s", (idz, nombre)):
        ui.msgError("Nombre duplicado: ya existe un espacio con ese nombre en la zona.")
        return
    _, nuevo = db.execute(
        conn, "INSERT INTO espacios (id_zona, nombre, ubicacion, aforo, estado_espacio) VALUES (%s,%s,%s,%s,%s)",
        (idz, nombre, ubic, aforo, est))
    ui.msgExito(f"Registro guardado. Folio: {nuevo}.")


def actualizarEspacio(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    ide = elegirEspacio(conn, opcional=False)
    try:
        with db.transaccion(conn):
            fila = db.queryOne(conn, "SELECT id_zona, nombre, ubicacion, aforo, estado_espacio FROM espacios WHERE id_espacio = %s FOR UPDATE", (ide,))
            nombre = leerTexto(f"Nombre [{fila[1]}]: ", 2, 100, opcional=True) or fila[1]
            ubic = leerTexto(f"Ubicacion [{fila[2]}]: ", 1, 150, opcional=True) or fila[2]
            aforo = leerEntero(f"Aforo [{fila[3]}]: ", 1, 100000, opcional=True) or fila[3]
            est = leerOpcionLista(f"Estado (actual {fila[4]})", ["DISPONIBLE", "NO_DISPONIBLE"], opcional=True) or fila[4]
            maxCupo = db.queryVal(conn, "SELECT COALESCE(MAX(cupo),0) FROM actividades WHERE id_espacio=%s AND estado_actividad <> 'CANCELADA'", (ide,))
            if aforo < maxCupo:
                raise db.DBError(f"Espacio con actividades incompatibles: hay una actividad con cupo {maxCupo} y el nuevo aforo es {aforo}.", negocio=True)
            if db.queryVal(conn, "SELECT COUNT(*) FROM espacios WHERE id_zona=%s AND nombre=%s AND id_espacio<>%s", (fila[0], nombre, ide)):
                raise db.DBError("Nombre duplicado en la zona.", negocio=True)
            if est == "NO_DISPONIBLE" and fila[4] == "DISPONIBLE":
                n = db.queryVal(conn, "SELECT COUNT(*) FROM actividades WHERE id_espacio=%s AND estado_actividad='PUBLICADA'", (ide,))
                if n and not confirmar(f"El espacio tiene {n} actividad(es) PUBLICADA(S)."):
                    raise db.DBError("Cambio cancelado.", negocio=True)
            db.execute(conn, "UPDATE espacios SET nombre=%s, ubicacion=%s, aforo=%s, estado_espacio=%s WHERE id_espacio=%s",
                       (nombre, ubic, aforo, est, ide))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Registro guardado.")


def menuCategoriasActividades(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    while True:
        opcion = ui.menu(sesion, "Categorias y actividades", [
            "Consultar actividades (filtros)", "Detalle de una actividad", "Crear actividad",
            "Actualizar actividad", "Publicar / cancelar / finalizar actividad", "Cambiar cupo",
            "Consultar categorias", "Crear categoria"])
        if opcion == 0:
            return
        acciones = {1: lambda c, s: mostrarAgenda(c, s, "coord"), 2: detalleActividadMenu,
                    3: crearActividad, 4: actualizarActividad, 5: cambiarEstadoActividad,
                    6: cambiarCupo, 7: listarCategorias, 8: crearCategoria}
        acciones[opcion](conn, sesion)
        pausar()


def detalleActividadMenu(conn, sesion):
    ida = leerEntero("ID de la actividad (0 = volver): ", 0, 10**9)
    if ida:
        detalleActividad(conn, ida)


def listarCategorias(conn, sesion):
    db.selectTabla(conn, "SELECT id_categoria, nombre, descripcion FROM categorias_actividad ORDER BY nombre", (),
                    [("ID", 4, True), ("Categoria", 26, False), ("Descripcion", 70, False)])


def crearCategoria(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    nombre = leerTexto("Nombre de la categoria: ", 2, 80)
    desc = leerTexto("Descripcion: ", 1, 300)
    if db.queryVal(conn, "SELECT COUNT(*) FROM categorias_actividad WHERE nombre = %s", (nombre,)):
        ui.msgError("Nombre duplicado.")
        return
    _, nuevo = db.execute(conn, "INSERT INTO categorias_actividad (nombre, descripcion) VALUES (%s,%s)", (nombre, desc))
    ui.msgExito(f"Categoria guardada. Folio: {nuevo}.")


def _validarActividad(conn, idActividad, idEspacio, fecha, ini, fin, cupo, nombre):
    esp = db.queryOne(
        conn,
        "SELECT e.aforo, e.estado_espacio, f.fecha FROM espacios e JOIN zonas z ON z.id_zona = e.id_zona "
        "JOIN festivales f ON f.id_festival = z.id_festival WHERE e.id_espacio = %s FOR UPDATE", (idEspacio,))
    if esp is None:
        raise db.DBError("Espacio no encontrado.", negocio=True)
    aforo, estadoEsp, fechaFest = esp
    if estadoEsp != "DISPONIBLE":
        raise db.DBError("Conflicto de espacio: el espacio esta NO_DISPONIBLE.", negocio=True)
    if str(fecha) != fechaFest.isoformat():
        raise db.DBError(f"La fecha debe corresponder a la edicion del festival ({fechaFest.isoformat()}).", negocio=True)
    if fin <= ini:
        raise db.DBError("La hora final debe ser posterior a la inicial.", negocio=True)
    if cupo < 1:
        raise db.DBError("El cupo debe ser un numero entero mayor que cero.", negocio=True)
    if cupo > aforo:
        raise db.DBError(f"El cupo ({cupo}) supera el aforo del espacio ({aforo}).", negocio=True)
    choque = db.queryOne(
        conn,
        "SELECT id_actividad, nombre_actividad FROM actividades WHERE id_espacio = %s AND fecha = %s "
        "AND estado_actividad <> 'CANCELADA' AND hora_inicio < %s AND hora_fin > %s AND id_actividad <> %s LIMIT 1",
        (idEspacio, fecha, fin, ini, idActividad))
    if choque:
        raise db.DBError(f"Conflicto de espacio: se traslapa con la actividad {choque[0]} '{choque[1]}'.", negocio=True)
    dup = db.queryVal(
        conn, "SELECT COUNT(*) FROM actividades WHERE nombre_actividad = %s AND fecha = %s AND hora_inicio = %s "
              "AND id_actividad <> %s AND estado_actividad <> 'CANCELADA'", (nombre, fecha, ini, idActividad))
    if dup:
        raise db.DBError("Registro duplicado: ya existe una actividad con ese nombre y horario.", negocio=True)


def crearActividad(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    print("\nNueva actividad (/c cancela)")
    idc = elegirCategoria(conn, opcional=False)
    ide = elegirEspacio(conn, opcional=False, soloDisponibles=True)
    nombre = leerTexto("Nombre de la actividad (3-120): ", 3, 120)
    desc = leerTexto("Descripcion (hasta 500): ", 1, 500)
    fecha = leerFecha("Fecha")
    ini = leerHora("Hora inicial")
    fin = leerHora("Hora final")
    cupo = leerEntero("Cupo (entero mayor que cero): ", 1, 100000)
    estado = leerOpcionLista("Estado inicial", ["PUBLICADA", "CANCELADA", "FINALIZADA"])
    try:
        with db.transaccion(conn):
            _validarActividad(conn, 0, ide, fecha, ini, fin, cupo, nombre)
            _, nuevo = db.execute(
                conn,
                "INSERT INTO actividades (id_categoria,id_espacio,nombre_actividad,descripcion,fecha,hora_inicio,hora_fin,cupo,estado_actividad) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (idc, ide, nombre, desc, fecha, ini, fin, cupo, estado))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito(f"Actividad creada. Folio: {nuevo}.")


def _horasTxt(valor):
    return ui.formatear(valor)


def actualizarActividad(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    ida = leerEntero("ID de la actividad a actualizar (0 = volver): ", 0, 10**9)
    if ida == 0:
        return
    try:
        with db.transaccion(conn):
            a = db.queryOne(
                conn, "SELECT id_categoria,id_espacio,nombre_actividad,descripcion,fecha,hora_inicio,hora_fin,cupo,estado_actividad "
                      "FROM actividades WHERE id_actividad = %s FOR UPDATE", (ida,))
            if a is None:
                raise db.DBError("Actividad no encontrada.", negocio=True)
            if a[8] != "PUBLICADA":
                raise db.DBError(f"La actividad esta {a[8]}: use 'Publicar / cancelar / finalizar' antes de editarla.", negocio=True)
            print("(Enter conserva el valor actual)")
            nombre = leerTexto(f"Nombre [{a[2]}]: ", 3, 120, opcional=True) or a[2]
            desc = leerTexto("Descripcion (Enter conserva): ", 1, 500, opcional=True) or a[3]
            fecha = leerFecha("Fecha", default=ui.formatear(a[4]))
            ini = leerHora(f"Hora inicial [{_horasTxt(a[5])}]", opcional=True) or _horasTxt(a[5])
            fin = leerHora(f"Hora final [{_horasTxt(a[6])}]", opcional=True) or _horasTxt(a[6])
            cambiarEsp = leerOpcionLista("¿Cambiar espacio?", ["S", "N"], opcional=True)
            ide = elegirEspacio(conn, opcional=False, soloDisponibles=True) if cambiarEsp == "S" else a[1]
            cupo = leerEntero(f"Cupo [{a[7]}]: ", 1, 100000, opcional=True) or a[7]
            confirmadas = db.queryVal(conn, "SELECT COUNT(*) FROM reservaciones WHERE id_actividad=%s AND estado_reservacion='CONFIRMADA'", (ida,))
            activas = db.queryVal(conn, "SELECT COUNT(*) FROM reservaciones WHERE id_actividad=%s AND estado_reservacion IN ('CONFIRMADA','ESPERA')", (ida,))
            if cupo < confirmadas:
                raise db.DBError(f"Actividad con reservaciones afectadas: hay {confirmadas} confirmadas y el nuevo cupo es {cupo}.", negocio=True)
            _validarActividad(conn, ida, ide, fecha, ini, fin, cupo, nombre)
            cambioHorario = (fecha != ui.formatear(a[4]) or ini != _horasTxt(a[5]) or fin != _horasTxt(a[6]) or ide != a[1])
            if cambioHorario and activas and not confirmar(
                    f"La actividad tiene {activas} reservacion(es) activas que cambiaran de fecha, horario o espacio."):
                raise db.DBError("Cambio cancelado.", negocio=True)
            db.execute(
                conn, "UPDATE actividades SET id_espacio=%s, nombre_actividad=%s, descripcion=%s, fecha=%s, hora_inicio=%s, hora_fin=%s, cupo=%s "
                      "WHERE id_actividad=%s", (ide, nombre, desc, fecha, ini, fin, cupo, ida))
            promovidas = _promoverEspera(conn, ida) if cupo > a[7] else 0
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Actividad actualizada.")
    if promovidas:
        print(f"Con el nuevo cupo se promovieron {promovidas} persona(s) de la lista de espera.")


def cambiarCupo(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    ida = leerEntero("ID de la actividad (0 = volver): ", 0, 10**9)
    if ida == 0:
        return
    try:
        with db.transaccion(conn):
            a = db.queryOne(
                conn, "SELECT a.nombre_actividad, a.cupo, a.estado_actividad, e.aforo FROM actividades a "
                      "JOIN espacios e ON e.id_espacio = a.id_espacio WHERE a.id_actividad = %s FOR UPDATE", (ida,))
            if a is None:
                raise db.DBError("Actividad no encontrada.", negocio=True)
            if a[2] != "PUBLICADA":
                raise db.DBError(f"La actividad esta {a[2]} y no admite cambios de cupo.", negocio=True)
            confirmadas = db.queryVal(conn, "SELECT COUNT(*) FROM reservaciones WHERE id_actividad=%s AND estado_reservacion='CONFIRMADA'", (ida,))
            enEspera = db.queryVal(conn, "SELECT COUNT(*) FROM reservaciones WHERE id_actividad=%s AND estado_reservacion='ESPERA'", (ida,))
            print(f"\n{a[0]} | cupo actual {a[1]} | aforo {a[3]} | confirmadas {confirmadas} | en espera {enEspera}")
            nuevo = leerEntero("Nuevo cupo: ", 1, 100000)
            if nuevo > a[3]:
                raise db.DBError(f"El cupo ({nuevo}) supera el aforo del espacio ({a[3]}).", negocio=True)
            if nuevo < confirmadas:
                raise db.DBError(f"Actividad con reservaciones afectadas: hay {confirmadas} confirmadas; el cupo no puede ser menor.", negocio=True)
            if nuevo == a[1]:
                raise db.DBError("El cupo es el mismo; no hay cambios.", negocio=True)
            if not confirmar(f"El cupo cambiara de {a[1]} a {nuevo}."):
                raise db.DBError("Cambio cancelado.", negocio=True)
            db.execute(conn, "UPDATE actividades SET cupo = %s WHERE id_actividad = %s", (nuevo, ida))
            promovidas = _promoverEspera(conn, ida) if nuevo > a[1] else 0
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Cupo actualizado; las reservaciones existentes se conservaron.")
    if promovidas:
        print(f"Se promovieron {promovidas} persona(s) de la lista de espera.")


def _promoverEspera(conn, idActividad):
    act = db.queryOne(conn, "SELECT cupo, fecha, hora_inicio, hora_fin FROM actividades WHERE id_actividad=%s", (idActividad,))
    cupo, fecha, ini, fin = act
    promovidas = 0
    while True:
        confirmadas = db.queryVal(conn, "SELECT COUNT(*) FROM reservaciones WHERE id_actividad=%s AND estado_reservacion='CONFIRMADA'", (idActividad,))
        if confirmadas >= cupo:
            break
        sig = db.queryOne(
            conn,
            "SELECT r.id_reservacion FROM reservaciones r WHERE r.id_actividad = %s AND r.estado_reservacion = 'ESPERA' "
            "AND NOT EXISTS (SELECT 1 FROM reservaciones r2 JOIN actividades a2 ON a2.id_actividad = r2.id_actividad "
            " WHERE r2.id_participante = r.id_participante AND r2.estado_reservacion = 'CONFIRMADA' "
            " AND a2.fecha = %s AND a2.hora_inicio < %s AND a2.hora_fin > %s) "
            "ORDER BY r.posicion_espera, r.fecha_solicitud LIMIT 1", (idActividad, fecha, fin, ini))
        if sig is None:
            break
        db.execute(conn, "UPDATE reservaciones SET estado_reservacion='CONFIRMADA', posicion_espera=NULL WHERE id_reservacion=%s", (sig[0],))
        promovidas += 1
    restantes = db.queryAll(
        conn, "SELECT id_reservacion FROM reservaciones WHERE id_actividad=%s AND estado_reservacion='ESPERA' "
              "ORDER BY posicion_espera, fecha_solicitud, id_reservacion", (idActividad,))
    for pos, (idr,) in enumerate(restantes, 1):
        db.execute(conn, "UPDATE reservaciones SET posicion_espera=%s WHERE id_reservacion=%s", (pos, idr))
    return promovidas


def cambiarEstadoActividad(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    ida = leerEntero("ID de la actividad (0 = volver): ", 0, 10**9)
    if ida == 0:
        return
    nuevo = leerOpcionLista("Nuevo estado", ["PUBLICADA", "CANCELADA", "FINALIZADA"])
    try:
        with db.transaccion(conn):
            a = db.queryOne(conn, "SELECT nombre_actividad, estado_actividad FROM actividades WHERE id_actividad=%s FOR UPDATE", (ida,))
            if a is None:
                raise db.DBError("Actividad no encontrada.", negocio=True)
            if a[1] == nuevo:
                raise db.DBError(f"La actividad ya esta {nuevo}.", negocio=True)
            if a[1] == "FINALIZADA":
                raise db.DBError("Una actividad FINALIZADA no puede cambiar de estado.", negocio=True)
            activas = db.queryVal(conn, "SELECT COUNT(*) FROM reservaciones WHERE id_actividad=%s AND estado_reservacion IN ('CONFIRMADA','ESPERA')", (ida,))
            movs = db.queryVal(conn, "SELECT COUNT(*) FROM movimientos_recurso WHERE id_actividad=%s AND estado_movimiento IN ('ASIGNADO','ENTREGADO')", (ida,))
            if nuevo == "CANCELADA":
                msg = f"Esta accion cambiara '{a[0]}' a CANCELADA y cancelara {activas} reservacion(es) activa(s)."
                if movs:
                    msg += f" Hay {movs} movimiento(s) de recursos pendientes de devolucion."
                if not confirmar(msg):
                    raise db.DBError("Operacion cancelada.", negocio=True)
                db.execute(conn, "UPDATE reservaciones SET estado_reservacion='CANCELADA', posicion_espera=NULL, fecha_cancelacion=NOW() "
                                 "WHERE id_actividad=%s AND estado_reservacion IN ('CONFIRMADA','ESPERA')", (ida,))
            elif not confirmar(f"Esta accion cambiara '{a[0]}' a {nuevo}."):
                raise db.DBError("Operacion cancelada.", negocio=True)
            db.execute(conn, "UPDATE actividades SET estado_actividad=%s WHERE id_actividad=%s", (nuevo, ida))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito(f"Actividad {nuevo}.")


ORDEN_RESERVAS = {
    "1": ("Fecha y hora de la actividad", "a.fecha, a.hora_inicio, r.id_reservacion"),
    "2": ("Participante", "u.nombre_usuario, r.id_reservacion"),
    "3": ("Estado", "r.estado_reservacion, r.id_reservacion"),
    "4": ("Fecha de solicitud (reciente primero)", "r.fecha_solicitud DESC, r.id_reservacion DESC"),
}


def consultaGlobalReservaciones(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    f = Filtro()
    print("\nFiltros (Enter omite)")
    u = pedirBusqueda("Buscar participante: ")
    if u:
        f.agregar("u.nombre_usuario LIKE %s", u)
    ida = leerEntero("ID de actividad: ", 1, 10**9, opcional=True)
    if ida:
        f.agregar("a.id_actividad = %s", ida)
    fecha = leerFecha("Fecha de la actividad", opcional=True)
    if fecha:
        f.agregar("a.fecha = %s", fecha)
    idz = elegirZona(conn)
    if idz:
        f.agregar("z.id_zona = %s", idz)
    est = leerOpcionLista("Estado", ["CONFIRMADA", "ESPERA", "CANCELADA"], opcional=True)
    if est:
        f.agregar("r.estado_reservacion = %s", est)
    desde = leerFecha("Solicitud desde", opcional=True)
    hasta = leerFecha("Solicitud hasta", opcional=True)
    if desde and hasta and hasta < desde:
        ui.msgDatoInvalido("Filtros invalidos: la fecha final es anterior a la inicial.")
        return
    if desde:
        f.agregar("DATE(r.fecha_solicitud) >= %s", desde)
    if hasta:
        f.agregar("DATE(r.fecha_solicitud) <= %s", hasta)
    orden = ui.elegirOrdenamiento(ORDEN_RESERVAS) or ORDEN_RESERVAS["1"][1]
    base = ("FROM reservaciones r JOIN usuarios u ON u.id_usuario = r.id_participante "
            "JOIN actividades a ON a.id_actividad = r.id_actividad JOIN espacios e ON e.id_espacio = a.id_espacio "
            "JOIN zonas z ON z.id_zona = e.id_zona ")
    sql = ("SELECT r.id_reservacion, u.nombre_usuario, a.nombre_actividad, a.fecha, "
           "CONCAT(LEFT(a.hora_inicio,5),'-',LEFT(a.hora_fin,5)), z.nombre, r.estado_reservacion, "
           "r.posicion_espera, r.fecha_solicitud, r.fecha_cancelacion " + base + f.where() + " ORDER BY " + orden)
    filas = db.selectTabla(conn, sql, f.params,
                            [("Folio", 5, True), ("Participante", 16, False), ("Actividad", 24, False), ("Fecha", 10, False),
                             ("Horario", 11, False), ("Zona", 14, False), ("Estado", 10, False), ("Pos", 3, True),
                             ("Solicitud", 16, False), ("Cancelacion", 16, False)])
    if filas:
        tot = db.queryAll(conn, "SELECT r.estado_reservacion, COUNT(*) " + base + f.where() + " GROUP BY r.estado_reservacion", f.params)
        print("Totales: " + " | ".join(f"{e}: {n}" for e, n in tot))
        while True:
            v = leerEntero("\nFolio para ver detalle (0 = volver): ", 0, 10**9)
            if v == 0:
                return
            fila = next((x for x in filas if x[0] == v), None)
            if fila is None:
                ui.msgError("Ese folio no esta en el resultado mostrado.")
                continue
            etiquetas = ["Folio", "Participante", "Actividad", "Fecha", "Horario", "Zona", "Estado", "Posicion espera", "Solicitud", "Cancelacion"]
            for e, val in zip(etiquetas, fila):
                print(f"  {e:<16}: {ui.formatear(val)}")
