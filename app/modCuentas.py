"""
@package IberoLiveOps
@summary Modulo 1: administracion de cuentas de usuario (solo Coordinacion)
@author Kilian Ian Pérez García
@date 22 de noviembre de 2026
"""
import db
import ui
from auth import requierePerfil, PERFIL_COORDINACION
from filtros import Filtro, pedirBusqueda
from util import (leerTexto, leerEntero, leerOpcionLista, leerPassword, confirmar, pausar,
                  validarUsuario, validarCorreo)

COORD = (PERFIL_COORDINACION,)
PERFILES = ["COORDINACION", "OPERACIONES", "PARTICIPANTE"]
COLS_CUENTAS = [("ID", 4, True), ("Usuario", 20, False), ("Nombre", 26, False), ("Correo", 34, False),
                ("Perfil", 13, False), ("Estado", 8, False), ("Registro", 16, False)]


def menuCuentas(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    while True:
        opcion = ui.menu(sesion, "Cuentas de usuario", [
            "Consultar cuentas", "Crear cuenta", "Actualizar cuenta", "Restablecer contrasena"])
        if opcion == 0:
            return
        {1: consultarCuentas, 2: crearCuenta, 3: actualizarCuenta, 4: restablecerContrasena}[opcion](conn, sesion)
        pausar()


def consultarCuentas(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    f = Filtro()
    print("\nFiltros (Enter omite)")
    u = pedirBusqueda("Buscar usuario: ")
    if u:
        f.agregar("nombre_usuario LIKE %s", u)
    p = leerOpcionLista("Perfil", PERFILES, opcional=True)
    if p:
        f.agregar("perfil = %s", p)
    e = leerOpcionLista("Estado", ["ACTIVA", "INACTIVA"], opcional=True)
    if e:
        f.agregar("estado_cuenta = %s", e)
    db.selectTabla(conn,
                    "SELECT id_usuario, nombre_usuario, nombre_mostrar, correo_ficticio, perfil, estado_cuenta, fecha_registro "
                    "FROM usuarios " + f.where() + " ORDER BY id_usuario", f.params, COLS_CUENTAS)


def crearCuenta(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    print("\nNueva cuenta (/c cancela)")
    while True:
        usuario = leerTexto("Nombre de usuario (4 a 30, sin espacios): ", 1, 60)
        if validarUsuario(usuario):
            break
        ui.msgDatoInvalido("El usuario debe tener de 4 a 30 caracteres y no contener espacios.")
    nombre = leerTexto("Nombre a mostrar (2 a 80): ", 2, 80)
    while True:
        correo = leerTexto("Correo ficticio (usuario@dominio): ", 3, 120)
        if validarCorreo(correo):
            break
        ui.msgDatoInvalido("El correo debe tener formato usuario@dominio.")
    clave = leerPassword("Contrasena inicial (minimo 8): ")
    if len(clave) < 8:
        ui.msgDatoInvalido("La contrasena debe tener al menos 8 caracteres.")
        return
    if leerPassword("Confirme la contrasena: ") != clave:
        ui.msgError("Las contrasenas no coinciden.")
        return
    perfil = leerOpcionLista("Perfil", PERFILES)
    estado = leerOpcionLista("Estado de la cuenta", ["ACTIVA", "INACTIVA"])
    if db.queryVal(conn, "SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = %s", (usuario,)):
        ui.msgError("El usuario ya existe. No se inserto nada.")
        return
    if db.queryVal(conn, "SELECT COUNT(*) FROM usuarios WHERE correo_ficticio = %s", (correo,)):
        ui.msgError("Correo duplicado: ya lo usa otra cuenta.")
        return
    _, nuevo = db.execute(
        conn,
        "INSERT INTO usuarios (nombre_usuario, nombre_mostrar, correo_ficticio, contrasena, perfil, estado_cuenta, fecha_registro) "
        "VALUES (%s,%s,%s,SHA2(CONCAT(%s,'$',%s),256),%s,%s,NOW())",
        (usuario, nombre, correo, usuario, clave, perfil, estado))
    ui.msgExito("Cuenta creada.")
    db.selectTabla(conn, "SELECT id_usuario, nombre_usuario, nombre_mostrar, correo_ficticio, perfil, estado_cuenta, fecha_registro "
                          "FROM usuarios WHERE id_usuario = %s", (nuevo,), COLS_CUENTAS)


def actualizarCuenta(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idu = leerEntero("ID de la cuenta (0 = volver): ", 0, 10**9)
    if idu == 0:
        return
    try:
        with db.transaccion(conn):
            c = db.queryOne(conn, "SELECT nombre_usuario, nombre_mostrar, correo_ficticio, perfil, estado_cuenta "
                                   "FROM usuarios WHERE id_usuario = %s FOR UPDATE", (idu,))
            if c is None:
                raise db.DBError("No se encontraron coincidencias.", negocio=True)
            ui.imprimirTabla([("Usuario", 20, False), ("Nombre", 26, False), ("Correo", 34, False),
                               ("Perfil", 13, False), ("Estado", 8, False)], [c])
            print("\n(Enter conserva el valor; el ID y el usuario no se pueden cambiar)")
            nombre = leerTexto("Nombre a mostrar: ", 2, 80, opcional=True) or c[1]
            correo = c[2]
            while True:
                nuevoCorreo = leerTexto("Correo ficticio: ", 3, 120, opcional=True)
                if nuevoCorreo is None:
                    break
                if validarCorreo(nuevoCorreo):
                    correo = nuevoCorreo
                    break
                ui.msgDatoInvalido("El correo debe tener formato usuario@dominio.")
            perfil = leerOpcionLista(f"Perfil (actual {c[3]})", PERFILES, opcional=True) or c[3]
            estado = leerOpcionLista(f"Estado (actual {c[4]})", ["ACTIVA", "INACTIVA"], opcional=True) or c[4]
            if idu == sesion.idUsuario and (perfil != c[3] or estado != c[4]):
                raise db.DBError("No puede cambiar su propio perfil ni desactivar su propia cuenta.", negocio=True)
            if correo != c[2] and db.queryVal(conn, "SELECT COUNT(*) FROM usuarios WHERE correo_ficticio=%s AND id_usuario<>%s", (correo, idu)):
                raise db.DBError("Correo duplicado.", negocio=True)
            if (perfil != c[3] or (estado == "INACTIVA" and c[4] == "ACTIVA")):
                if not confirmar(f"Se cambiara el perfil/estado de '{c[0]}' ({c[3]}/{c[4]} -> {perfil}/{estado})."):
                    raise db.DBError("Cambio cancelado.", negocio=True)
            db.execute(conn, "UPDATE usuarios SET nombre_mostrar=%s, correo_ficticio=%s, perfil=%s, estado_cuenta=%s WHERE id_usuario=%s",
                       (nombre, correo, perfil, estado, idu))
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
        return
    ui.msgExito("Cuenta actualizada.")


def restablecerContrasena(conn, sesion):
    if not requierePerfil(conn, sesion, *COORD):
        return
    idu = leerEntero("ID de la cuenta (0 = volver): ", 0, 10**9)
    if idu == 0:
        return
    c = db.queryOne(conn, "SELECT nombre_usuario FROM usuarios WHERE id_usuario=%s", (idu,))
    if c is None:
        ui.msgError("No se encontraron coincidencias.")
        return
    nueva = leerPassword(f"Nueva contrasena para {c[0]} (minimo 8): ")
    if len(nueva) < 8:
        ui.msgDatoInvalido("La contrasena debe tener al menos 8 caracteres.")
        return
    if leerPassword("Confirme: ") != nueva:
        ui.msgError("Las contrasenas no coinciden.")
        return
    db.execute(conn, "UPDATE usuarios SET contrasena = SHA2(CONCAT(nombre_usuario,'$',%s),256) WHERE id_usuario=%s", (nueva, idu))
    ui.msgExito("Contrasena restablecida.")
