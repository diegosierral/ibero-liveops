"""
@package IberoLiveOps
@summary Sesion, inicio de sesion, autorizacion en dos capas y Mi cuenta
@author Kilian Ian Pérez García
@date 21 de noviembre de 2026
"""
from dataclasses import dataclass

import db
import ui
from util import leerTexto, leerPassword, validarCorreo

PERFIL_COORDINACION = "COORDINACION"
PERFIL_OPERACIONES = "OPERACIONES"
PERFIL_PARTICIPANTE = "PARTICIPANTE"


@dataclass
class Sesion:
    idUsuario: int = 0
    usuario: str = ""
    nombre: str = ""
    correo: str = ""
    perfil: str = ""
    activa: bool = False


def limpiarSesion(sesion):
    sesion.idUsuario = 0
    sesion.usuario = ""
    sesion.nombre = ""
    sesion.correo = ""
    sesion.perfil = ""
    sesion.activa = False


def login(conn, sesion):
    ui.encabezado(None, "Inicio de sesion")
    usuario = leerTexto("Usuario: ", 1, 30)
    clave = leerPassword("Contrasena: ")
    fila = db.queryOne(
        conn,
        "SELECT id_usuario, nombre_usuario, nombre_mostrar, correo_ficticio, perfil "
        "FROM usuarios "
        "WHERE nombre_usuario = %s AND contrasena = SHA2(CONCAT(nombre_usuario,'$',%s),256) "
        "AND estado_cuenta = 'ACTIVA'",
        (usuario, clave),
    )
    if fila is None:
        ui.msgError("Usuario o contrasena incorrectos, o la cuenta no esta activa.")
        return False
    sesion.idUsuario, sesion.usuario, sesion.nombre, sesion.correo, sesion.perfil = fila
    sesion.activa = True
    ui.msgExito(f"Bienvenido(a), {sesion.nombre}.")
    return True


def requierePerfil(conn, sesion, *permitidos):
    if not sesion.activa or sesion.perfil not in permitidos:
        ui.msgPermisoDenegado()
        return False
    fila = db.queryOne(
        conn, "SELECT perfil, estado_cuenta FROM usuarios WHERE id_usuario = %s", (sesion.idUsuario,)
    )
    if fila is None or fila[0] != sesion.perfil or fila[1] != "ACTIVA":
        ui.msgPermisoDenegado()
        return False
    return True


def menuMiCuenta(conn, sesion):
    while True:
        _mostrarDatos(conn, sesion)
        opcion = ui.menu(sesion, "Mi cuenta", ["Actualizar mis datos", "Cambiar mi contrasena"])
        if opcion == 0:
            return
        if opcion == 1:
            actualizarDatos(conn, sesion)
        else:
            cambiarContrasena(conn, sesion)


def _mostrarDatos(conn, sesion):
    fila = db.queryOne(
        conn,
        "SELECT nombre_usuario, nombre_mostrar, correo_ficticio, perfil, estado_cuenta "
        "FROM usuarios WHERE id_usuario = %s",
        (sesion.idUsuario,),
    )
    ui.imprimirTabla(
        [("Usuario", 18, False), ("Nombre", 26, False), ("Correo", 34, False),
         ("Perfil", 13, False), ("Estado", 8, False)],
        [fila],
    )


def actualizarDatos(conn, sesion):
    if not requierePerfil(conn, sesion, PERFIL_COORDINACION, PERFIL_OPERACIONES, PERFIL_PARTICIPANTE):
        return
    _mostrarDatos(conn, sesion)
    print("\n(Enter conserva el valor actual; /c cancela. No se pueden cambiar usuario, perfil ni estado.)")
    nombre = leerTexto("Nuevo nombre a mostrar: ", 2, 80, opcional=True) or sesion.nombre
    while True:
        correo = leerTexto("Nuevo correo ficticio: ", 3, 120, opcional=True) or sesion.correo
        if validarCorreo(correo):
            break
        ui.msgDatoInvalido("El correo debe tener formato usuario@dominio.")
    if nombre == sesion.nombre and correo == sesion.correo:
        ui.msgAviso("No hay cambios que guardar.")
        return
    repetido = db.queryVal(
        conn, "SELECT COUNT(*) FROM usuarios WHERE correo_ficticio = %s AND id_usuario <> %s",
        (correo, sesion.idUsuario),
    )
    if repetido:
        ui.msgError("Correo duplicado: ya lo usa otra cuenta.")
        return
    db.execute(
        conn,
        "UPDATE usuarios SET nombre_mostrar = %s, correo_ficticio = %s WHERE id_usuario = %s",
        (nombre, correo, sesion.idUsuario),
    )
    sesion.nombre, sesion.correo = nombre, correo
    ui.msgExito("Datos actualizados.")


def cambiarContrasena(conn, sesion):
    if not requierePerfil(conn, sesion, PERFIL_COORDINACION, PERFIL_OPERACIONES, PERFIL_PARTICIPANTE):
        return
    actual = leerPassword("Contrasena actual: ")
    ok = db.queryVal(
        conn,
        "SELECT COUNT(*) FROM usuarios WHERE id_usuario = %s "
        "AND contrasena = SHA2(CONCAT(nombre_usuario,'$',%s),256)",
        (sesion.idUsuario, actual),
    )
    if not ok:
        ui.msgError("Contrasena actual incorrecta.")
        return
    nueva = leerPassword("Nueva contrasena (minimo 8 caracteres): ")
    if len(nueva) < 8:
        ui.msgDatoInvalido("La nueva contrasena debe tener al menos 8 caracteres.")
        return
    if leerPassword("Confirme la nueva contrasena: ") != nueva:
        ui.msgError("Las contrasenas no coinciden.")
        return
    db.execute(
        conn,
        "UPDATE usuarios SET contrasena = SHA2(CONCAT(nombre_usuario,'$',%s),256) WHERE id_usuario = %s",
        (nueva, sesion.idUsuario),
    )
    ui.msgExito("Contrasena cambiada.")
