"""
@package IberoLiveOps
@summary Acceso a MySQL: conexion, sentencias preparadas, CALL a procedimientos y transacciones
@author Kilian Ian Pérez García
@date 21 de noviembre de 2026
"""
import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import errors as mysqlErrors

from util import _leer, Cancelado
import ui

ERR_NEGOCIO = 1644


class DBError(Exception):
    def __init__(self, mensaje, negocio=False, errno=0):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.negocio = negocio
        self.errno = errno


def _cargarEnvLocal():
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.isfile(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def conectar():
    _cargarEnvLocal()
    faltan = [v for v in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME") if v not in os.environ]
    if faltan:
        raise DBError("Faltan variables de entorno: " + ", ".join(faltan))
    try:
        conn = mysql.connector.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            charset="utf8mb4",
            use_pure=True,
            autocommit=True,
            connection_timeout=8,
        )
    except mysqlErrors.Error as e:
        raise DBError(f"No fue posible conectar con MySQL ({e.errno}): {e.msg}", errno=e.errno)
    return conn


def conectarInteractivo():
    while True:
        try:
            return conectar()
        except DBError as e:
            ui.msgError(e.mensaje)
            try:
                r = _leer("¿Reintentar? S/N: ").upper()
            except Cancelado:
                r = "N"
            if r != "S":
                return None


def desconectar(conn):
    try:
        if conn is not None and conn.is_connected():
            conn.close()
    except mysqlErrors.Error:
        pass


def _traducir(e):
    errno = getattr(e, "errno", 0) or 0
    msg = getattr(e, "msg", str(e))
    if errno == ERR_NEGOCIO:
        return DBError(msg, negocio=True, errno=errno)
    if errno in (1062,):
        return DBError("Registro duplicado: ya existe un registro con ese valor unico.", errno=errno)
    if errno in (1451, 1452):
        return DBError("La operacion viola una relacion con otros registros.", errno=errno)
    if errno in (2006, 2013, 2055):
        return DBError("Se perdio la conexion con MySQL.", errno=errno)
    return DBError(f"Error de base de datos ({errno}): {msg}", errno=errno)


def _asegurar(conn):
    try:
        conn.ping(reconnect=True, attempts=2, delay=1)
    except mysqlErrors.Error as e:
        raise _traducir(e)


def queryAll(conn, sql, params=()):
    _asegurar(conn)
    cur = conn.cursor(prepared=True)
    try:
        cur.execute(sql, tuple(params))
        return cur.fetchall()
    except mysqlErrors.Error as e:
        raise _traducir(e)
    finally:
        cur.close()


def queryOne(conn, sql, params=()):
    filas = queryAll(conn, sql, params)
    return filas[0] if filas else None


def queryVal(conn, sql, params=()):
    fila = queryOne(conn, sql, params)
    return fila[0] if fila else None


def execute(conn, sql, params=()):
    _asegurar(conn)
    cur = conn.cursor(prepared=True)
    try:
        cur.execute(sql, tuple(params))
        return cur.rowcount, cur.lastrowid
    except mysqlErrors.Error as e:
        raise _traducir(e)
    finally:
        cur.close()


def selectTabla(conn, sql, params, cols):
    filas = queryAll(conn, sql, params)
    if not filas:
        ui.msgSinResultados()
        return filas
    ui.imprimirTabla(cols, filas)
    print(f"\n{len(filas)} registro(s).")
    return filas


def callSp(conn, nombre, params, salidas=()):
    _asegurar(conn)
    marcadores = ",".join(["%s"] * len(params))
    varsOut = [f"@o_{i}" for i in range(len(salidas))]
    lista = ",".join(([marcadores] if params else []) + varsOut)
    sql = f"CALL {nombre}({lista})"
    cur = conn.cursor(prepared=True)
    try:
        cur.execute(sql, tuple(params))
        while True:
            try:
                cur.fetchall()
            except mysqlErrors.InterfaceError:
                pass
            if not cur.nextset():
                break
    except mysqlErrors.Error as e:
        raise _traducir(e)
    finally:
        cur.close()
    if not salidas:
        return {}
    fila = queryOne(conn, "SELECT " + ",".join(varsOut))
    return dict(zip(salidas, fila))


@contextmanager
def transaccion(conn):
    _asegurar(conn)
    conn.start_transaction()
    try:
        yield conn
        conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except mysqlErrors.Error:
            pass
        raise
