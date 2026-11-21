"""
@package IberoLiveOps
@summary Lectura segura de teclado y validadores de formato
@author Kilian Ian Pérez García
@date 21 de noviembre de 2026
"""
import getpass
import re
from datetime import datetime

CANCELAR = "/c"


class Cancelado(Exception):
    pass


def _leer(prompt):
    try:
        texto = input(prompt)
    except EOFError:
        raise Cancelado()
    texto = texto.strip()
    if texto.lower() == CANCELAR:
        raise Cancelado()
    return texto


def leerTexto(prompt, minLen=1, maxLen=255, opcional=False):
    while True:
        texto = _leer(prompt)
        if texto == "" and opcional:
            return None
        if minLen <= len(texto) <= maxLen:
            return texto
        print(f"  Dato invalido: debe tener entre {minLen} y {maxLen} caracteres.")


def leerEntero(prompt, minVal, maxVal, opcional=False):
    while True:
        texto = _leer(prompt)
        if texto == "" and opcional:
            return None
        try:
            valor = int(texto)
        except ValueError:
            print("  Dato invalido: escriba un numero entero.")
            continue
        if minVal <= valor <= maxVal:
            return valor
        print(f"  Dato invalido: el valor debe estar entre {minVal} y {maxVal}.")


def leerOpcionLista(prompt, validas, opcional=False):
    validasTxt = "/".join(validas)
    while True:
        texto = _leer(f"{prompt} [{validasTxt}]: ").upper()
        if texto == "" and opcional:
            return None
        if texto in validas:
            return texto
        print("  Dato invalido: elija una de las opciones mostradas.")


def leerPassword(prompt):
    try:
        return getpass.getpass(prompt)
    except EOFError:
        raise Cancelado()


def confirmar(mensaje):
    while True:
        r = _leer(f"{mensaje} ¿Desea continuar? S/N: ").upper()
        if r in ("S", "SI"):
            return True
        if r in ("N", "NO"):
            return False
        print("  Responda S o N.")


def validarFecha(texto):
    try:
        datetime.strptime(texto, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validarHora(texto):
    try:
        datetime.strptime(texto, "%H:%M")
        return True
    except ValueError:
        return False


def validarCorreo(texto):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", texto) is not None


def validarUsuario(texto):
    return 4 <= len(texto) <= 30 and texto == texto.strip() and " " not in texto


def leerFecha(prompt, opcional=False, default=None):
    sufijo = f" (Enter = {default})" if default else ""
    while True:
        texto = _leer(f"{prompt} AAAA-MM-DD{sufijo}: ")
        if texto == "":
            if default:
                return default
            if opcional:
                return None
        if validarFecha(texto):
            return texto
        print("  Dato invalido: use el formato AAAA-MM-DD con una fecha real.")


def leerHora(prompt, opcional=False):
    while True:
        texto = _leer(f"{prompt} HH:MM: ")
        if texto == "" and opcional:
            return None
        if validarHora(texto):
            return texto
        print("  Dato invalido: use el formato HH:MM (00:00 a 23:59).")


def leerFechaHora(prompt):
    f = leerFecha(prompt + " (fecha)")
    h = leerHora(prompt + " (hora)")
    return f"{f} {h}:00"


def pausar():
    try:
        input("\nEnter para continuar...")
    except EOFError:
        pass
