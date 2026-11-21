"""
@package IberoLiveOps
@summary Presentacion en consola: encabezados, tablas alineadas y mensajes estandar
@author Kilian Ian Pérez García
@date 21 de noviembre de 2026
"""
import datetime as dt
from decimal import Decimal

from util import _leer, Cancelado

ANCHO = 120
NOMBRE_SISTEMA = "IBERO LiveOps"


def linea(car="-"):
    print(car * ANCHO)


def encabezado(sesion, titulo):
    linea("=")
    if sesion is not None and sesion.activa:
        print(f"{NOMBRE_SISTEMA} | Perfil: {sesion.perfil} | Usuario: {sesion.usuario}")
    else:
        print(NOMBRE_SISTEMA)
    print(titulo.upper())
    linea("=")


def subtitulo(texto):
    print(f"\n--- {texto} ---")


def formatear(valor):
    if valor is None:
        return "-"
    if isinstance(valor, dt.datetime):
        return valor.strftime("%Y-%m-%d %H:%M")
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, dt.timedelta):
        total = int(valor.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    if isinstance(valor, Decimal):
        return f"{valor:.1f}" if valor != valor.to_integral() else str(int(valor))
    if isinstance(valor, float):
        return f"{valor:.1f}"
    return str(valor)


def imprimirTabla(cols, filas):
    def celda(texto, ancho, derecha):
        if len(texto) > ancho:
            texto = texto[: max(ancho - 3, 1)] + "..."
        return texto.rjust(ancho) if derecha else texto.ljust(ancho)

    print(" ".join(celda(t, a, d) for t, a, d in cols))
    print(" ".join("-" * a for _, a, _ in cols))
    for fila in filas:
        print(" ".join(celda(formatear(v), a, d) for v, (_, a, d) in zip(fila, cols)))


def msgExito(detalle):
    print(f"\n[OK] {detalle}")


def msgSinResultados():
    print("\nNo se encontraron registros con los filtros seleccionados.")


def msgDatoInvalido(detalle):
    print(f"\n[DATO INVALIDO] {detalle}")


def msgPermisoDenegado():
    print("\n[PERMISO DENEGADO] La operacion no esta permitida para el perfil activo.")


def msgError(detalle):
    print(f"\n[ERROR] {detalle}")


def msgAviso(detalle):
    print(f"\n[AVISO] {detalle}")


def menu(sesion, titulo, opciones, cerrar="Regresar"):
    while True:
        encabezado(sesion, titulo)
        for i, texto in enumerate(opciones, 1):
            print(f"  {i}. {texto}")
        print(f"  0. {cerrar}")
        try:
            r = _leer("\nOpcion: ")
        except Cancelado:
            return 0
        if r.isdigit() and 0 <= int(r) <= len(opciones):
            return int(r)
        msgDatoInvalido("Escriba el numero de una opcion del menu.")


def elegirOrdenamiento(opciones):
    print("\nOrdenar por:")
    for k, (etq, _) in opciones.items():
        print(f"  {k}. {etq}")
    r = _leer("Opcion (Enter = predeterminado): ")
    return opciones[r][1] if r in opciones else None
