"""
@package IberoLiveOps
@summary Programa principal: conexion, inicio de sesion y menus por perfil
@author Kilian Ian Pérez García
@date 23 de noviembre de 2026
"""
import sys

import db
import ui
import auth
import modCuentas
import modAgenda
import modRecursos
import modIncidencias
import modReportes
from auth import Sesion, PERFIL_COORDINACION, PERFIL_OPERACIONES, PERFIL_PARTICIPANTE
from util import Cancelado, pausar

def consultarAgendaParticipante(conn, sesion):
    modAgenda.mostrarAgenda(conn, sesion, "part")


MENU_COORDINACION = [
    ("Resumen del festival", modReportes.resumenFestival),
    ("Cuentas de usuario", modCuentas.menuCuentas),
    ("Festival, zonas y espacios", modAgenda.menuFestivalZonasEspacios),
    ("Categorias y actividades", modAgenda.menuCategoriasActividades),
    ("Reservaciones", modAgenda.consultaGlobalReservaciones),
    ("Recursos", modRecursos.menuRecursosCoordinacion),
    ("Incidencias", modIncidencias.menuIncidenciasCoordinacion),
    ("Reportes", modReportes.menuReportesCoordinacion),
    ("Mi cuenta", auth.menuMiCuenta),
]
MENU_OPERACIONES = [
    ("Resumen operativo", modReportes.resumenOperativo),
    ("Agenda y listas", modAgenda.menuAgendaOperaciones),
    ("Recursos y movimientos", modRecursos.menuRecursosOperaciones),
    ("Incidencias", modIncidencias.menuIncidenciasOperaciones),
    ("Reportes operativos", modReportes.menuReportesOperaciones),
    ("Mi cuenta", auth.menuMiCuenta),
]
MENU_PARTICIPANTE = [
    ("Consultar agenda", consultarAgendaParticipante),
    ("Crear reservacion", modAgenda.crearReservacion),
    ("Mis reservaciones", modAgenda.misReservaciones),
    ("Registrar incidencia", modIncidencias.registrarIncidencia),
    ("Mis incidencias", modIncidencias.misIncidencias),
    ("Mi cuenta", auth.menuMiCuenta),
]
PAUSAR_AL_TERMINAR = {consultarAgendaParticipante, modAgenda.crearReservacion,
                      modIncidencias.registrarIncidencia, modIncidencias.misIncidencias,
                      modAgenda.consultaGlobalReservaciones}
MENUS = {PERFIL_COORDINACION: MENU_COORDINACION, PERFIL_OPERACIONES: MENU_OPERACIONES,
         PERFIL_PARTICIPANTE: MENU_PARTICIPANTE}


def ejecutar(funcion, conn, sesion):
    try:
        funcion(conn, sesion)
    except Cancelado:
        ui.msgAviso("Operacion cancelada.")
    except db.DBError as e:
        ui.msgError(e.mensaje + ("" if e.negocio else " No se guardaron cambios."))
    except Exception as e:
        ui.msgError(f"Ocurrio un error inesperado ({type(e).__name__}). Se regresa al menu.")


def menuPerfil(conn, sesion):
    opciones = MENUS.get(sesion.perfil)
    if opciones is None:
        ui.msgPermisoDenegado()
        return
    while True:
        eleccion = ui.menu(sesion, f"Menu {sesion.perfil}", [t for t, _ in opciones], cerrar="Cerrar sesion")
        if eleccion == 0:
            return
        funcion = opciones[eleccion - 1][1]
        ejecutar(funcion, conn, sesion)
        if funcion in PAUSAR_AL_TERMINAR:
            pausar()


def main():
    conn = db.conectarInteractivo()
    if conn is None:
        print("Hasta luego.")
        return 1
    sesion = Sesion()
    try:
        while True:
            ui.encabezado(None, "Bienvenido")
            print("  1. Iniciar sesion\n  0. Salir")
            try:
                op = input("\nOpcion: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if op == "0":
                break
            if op != "1":
                ui.msgDatoInvalido("Escriba 1 o 0.")
                continue
            try:
                abierta = auth.login(conn, sesion)
            except Cancelado:
                continue
            except db.DBError as e:
                ui.msgError(e.mensaje)
                continue
            if abierta:
                try:
                    menuPerfil(conn, sesion)
                finally:
                    auth.limpiarSesion(sesion)
                    ui.msgExito("Sesion cerrada.")
    except KeyboardInterrupt:
        print()
    finally:
        db.desconectar(conn)
    print("Conexion cerrada. Hasta luego.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
