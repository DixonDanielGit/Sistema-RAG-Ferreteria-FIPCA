"""Extraccion, normalizacion y carga de catalogos de proveedores."""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import logging
import os
import re
import tempfile
import unicodedata
import uuid
import zipfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from xml.etree.ElementTree import ParseError

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import get_settings
from app.db.session import BaseDeDatosNoDisponible
from app.models import inventario as inventario_model
from app.services import markdown_transform_service
from psycopg2 import Error as ErrorPostgres

logger = logging.getLogger("ferreteria.etl")

EXTENSIONES_PERMITIDAS = frozenset({".pdf", ".xlsx", ".docx", ".txt", ".md"})
MAX_ARCHIVO_MB = 100
MAX_ARCHIVO_BYTES = MAX_ARCHIVO_MB * 1024 * 1024
MAX_ARCHIVOS_INGESTA = 20
MAX_FILAS_ARCHIVO = 20_000
MAX_PAGINAS_PDF = 300
MAX_ENTRADAS_ZIP = 500
MAX_DESCOMPRIMIDO_ZIP = 100 * 1024 * 1024
MAX_RAZON_COMPRESION = 100
MAX_DETALLE = 4000
MAX_ERRORES_DETALLE = 20
# Limite del Markdown que MarkItDown produce y que se guarda en la base
MAX_MARKDOWN_CARACTERES = 10_000_000

# La cabecera de PDF/XLSX/DOCX es obligatoria. TXT puede usar el orden indicado
# en la documentacion cuando no contiene una cabecera reconocible.
TXT_COLUMNAS_POSICIONALES = ("codigo", "nombre", "precio", "descripcion", "marca")

SINONIMOS = {
    "codigo": {
        "codigo", "cod", "sku", "referencia", "ref", "item", "itemnumber",
        "productcode", "code",
    },
    "nombre": {"nombre", "producto", "articulo", "product", "name"},
    "precio": {
        "precio", "preciounitario", "precioventa", "pvp", "costo", "cost",
        "price", "unitprice",
    },
    "marca": {"marca", "fabricante", "brand", "manufacturer"},
    "descripcion": {"descripcion", "description", "detalle", "observacion", "notes"},
    "descuentos": {"descuento", "descuentos", "discount", "discounts"},
    "iva": {"iva", "impuesto", "porcentajeiva", "tasaiva", "tax"},
    "iva_incluido": {"ivaincluido", "incluyeiva", "precioconiva"},
    "cantidad_disponible_proveedor": {
        "cantidaddisponibleproveedor",
        "cantidaddisp",
        "cantidaddisponible",
        "disponibilidadproveedor",
        "qtyavailable",
    },
    "politica_ventas": {"politicaventas", "condicionesventa", "politicacomercial"},
}
_POR_SINONIMO = {
    sinonimo: campo
    for campo, sinonimos in SINONIMOS.items()
    for sinonimo in sinonimos
}


class ErrorIngesta(ValueError):
    """Error de formato o contenido que debe aislarse a un archivo."""


class CabeceraIngestaAusente(ErrorIngesta):
    """La hoja o tabla no contiene una cabecera de productos reconocible."""


class ArchivoSinFilasValidas(ErrorIngesta):
    """Todas las filas del catalogo fallaron la validacion."""

    def __init__(self, cantidad: int, detalle: str) -> None:
        self.filas_error = cantidad
        super().__init__(detalle)


class ErrorRespuestaIA(ErrorIngesta):
    """Error de normalizacion que conserva el JSON validado por el modelo."""

    def __init__(self, detalle: str, respuesta_ia: dict[str, Any]) -> None:
        self.respuesta_ia = respuesta_ia
        super().__init__(detalle)


class SeleccionPrecioRequerida(ErrorIngesta):
    """El catalogo tiene varias columnas de precio y requiere confirmacion."""

    def __init__(self, opciones: list[dict[str, Any]]) -> None:
        self.opciones = opciones
        super().__init__("Seleccione la columna de precio que desea importar")


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _normalizar_texto(valor: Any) -> str:
    texto = _texto(valor)
    if any(ord(caracter) < 32 and caracter not in "\t\r\n" for caracter in texto):
        raise ErrorIngesta("El texto contiene caracteres de control")
    return " ".join(texto.split())


def _clave(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", _texto(valor).casefold())
    sin_tildes = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r"[^a-z0-9]+", "", sin_tildes)


def _mapear_cabecera(fila: Iterable[Any]) -> dict[str, int] | None:
    valores = list(fila)
    columnas: dict[str, int] = {}
    precios: list[int] = []
    for indice, valor in enumerate(valores):
        clave = _clave(valor)
        campo = _POR_SINONIMO.get(clave)
        if campo is None:
            if clave.startswith(("codigo", "cod", "sku", "referencia")):
                campo = "codigo"
            elif clave.startswith(("nombre", "producto", "articulo")):
                campo = "nombre"
            elif clave.startswith(("descripcion", "description", "detalle")):
                campo = "descripcion"
        if campo is None and (
            clave.startswith("precio")
            or clave.startswith("pvp")
            or clave.startswith("bsf")
        ):
            campo = "precio"
        if campo:
            if campo == "precio":
                precios.append(indice)
            elif campo not in columnas:
                columnas[campo] = indice
    if "nombre" not in columnas and "descripcion" in columnas:
        columnas["nombre"] = columnas["descripcion"]
    if precios:
        columnas["precio"] = precios[0]
    if {"codigo", "nombre", "precio"}.issubset(columnas):
        return columnas
    return None


def _separador(texto: str) -> str | None:
    for separador in ("\t", ";", "|"):
        if separador in texto:
            return separador
    return None


def _filas_delimitadas(texto: str) -> list[list[str]]:
    lineas: list[str] = []
    for numero, linea in enumerate(io.StringIO(texto), start=1):
        if numero > MAX_FILAS_ARCHIVO + 101:
            raise ErrorIngesta(f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas")
        if linea.strip():
            lineas.append(linea.rstrip("\r\n"))
    if not lineas:
        return []
    separador = _separador(lineas[0])
    if separador is None:
        separador = max(
            ("\t", ";", "|", ","),
            key=lambda candidato: sum(linea.count(candidato) for linea in lineas[:10]),
        )
        if not any(separador in linea for linea in lineas):
            return [[linea.strip()] for linea in lineas]
    return [next(csv.reader([linea], delimiter=separador, skipinitialspace=True)) for linea in lineas]


def _leer_precio(valor: Any, *, campo: str = "precio") -> Decimal:
    if isinstance(valor, bool):
        raise ErrorIngesta(f"{campo.capitalize()} invalido")
    if isinstance(valor, (int, float, Decimal)):
        texto = str(valor)
    else:
        texto = _texto(valor)
    if "(" in texto or ")" in texto:
        raise ErrorIngesta(f"{campo.capitalize()} no puede usar notacion negativa")
    texto = re.sub(r"(?i)(?:US\$|USD|VES|BS(?:\.F)?\.?)", "", texto)
    texto = texto.replace("$", "").replace(" ", "").replace("\u00a0", "")
    if re.search(r"[^0-9,.\-]", texto):
        raise ErrorIngesta(f"{campo.capitalize()} invalido")
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto or texto.startswith("-") or "-" in texto:
        raise ErrorIngesta(f"{campo.capitalize()} vacio o negativo")

    coma = texto.rfind(",")
    punto = texto.rfind(".")
    if coma >= 0 and punto >= 0:
        decimal_sep = "," if coma > punto else "."
        millares = "." if decimal_sep == "," else ","
        texto = texto.replace(millares, "").replace(decimal_sep, ".")
    elif coma >= 0 or punto >= 0:
        separador = "," if coma >= 0 else "."
        partes = texto.split(separador)
        if len(partes) > 2:
            if all(len(parte) == 3 for parte in partes[1:]):
                texto = "".join(partes)
            else:
                raise ErrorIngesta(f"{campo.capitalize()} tiene separadores invalidos")
        elif len(partes) == 2 and len(partes[1]) == 3 and partes[0]:
            texto = "".join(partes)
        else:
            texto = ".".join(partes)

    try:
        numero = Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ErrorIngesta(f"{campo.capitalize()} invalido") from exc
    if not numero.is_finite() or numero < 0 or numero > Decimal("99999999.99"):
        raise ErrorIngesta(f"{campo.capitalize()} fuera del rango permitido")
    return numero


def _producto_desde_fila(
    fila: Iterable[Any], columnas: dict[str, int], numero_fila: int
) -> dict[str, Any]:
    valores = list(fila)

    def obtener(campo: str) -> Any:
        indice = columnas.get(campo)
        return valores[indice] if indice is not None and indice < len(valores) else None

    try:
        codigo = _normalizar_texto(obtener("codigo")).upper()
        nombre = _normalizar_texto(obtener("nombre"))
        marca = _normalizar_texto(obtener("marca")) or None
        descripcion = _normalizar_texto(obtener("descripcion")) or None
    except ErrorIngesta as exc:
        raise ErrorIngesta(f"Fila {numero_fila}: {exc}") from exc
    if not codigo or not nombre:
        raise ErrorIngesta(f"Fila {numero_fila}: codigo y nombre son obligatorios")
    if len(codigo) > 50 or len(nombre) > 255:
        raise ErrorIngesta(f"Fila {numero_fila}: codigo o nombre excede el limite")

    if marca and len(marca) > 100:
        raise ErrorIngesta(f"Fila {numero_fila}: marca excede 100 caracteres")
    descuento = obtener("descuentos")
    try:
        precio = _leer_precio(obtener("precio"))
        descuentos = (
            _leer_precio(descuento, campo="descuento")
            if _texto(descuento)
            else Decimal("0.00")
        )
    except ErrorIngesta as exc:
        raise ErrorIngesta(f"Fila {numero_fila}: {exc}") from exc

    producto = {
        "codigo": codigo,
        "nombre": nombre,
        "marca": marca,
        "precio": precio,
        "descuentos": descuentos,
        "descripcion": descripcion,
        **(
            {"descuento_oferta": descuentos}
            if _texto(descuento)
            else {}
        ),
    }
    cantidad_disponible = obtener("cantidad_disponible_proveedor")
    if _texto(cantidad_disponible):
        try:
            cantidad = _leer_precio(
                cantidad_disponible, campo="cantidad disponible"
            )
        except ErrorIngesta as exc:
            raise ErrorIngesta(f"Fila {numero_fila}: {exc}") from exc
        if cantidad != cantidad.to_integral_value():
            raise ErrorIngesta(
                f"Fila {numero_fila}: cantidad disponible no entera"
            )
        producto["cantidad_disponible_proveedor"] = int(cantidad)

    politica = _normalizar_texto(obtener("politica_ventas"))
    if politica:
        producto["politica_ventas"] = politica[:4000]

    iva = obtener("iva")
    if _texto(iva):
        try:
            porcentaje_iva = _leer_precio(
                str(iva).replace("%", ""), campo="IVA"
            )
        except ErrorIngesta as exc:
            raise ErrorIngesta(f"Fila {numero_fila}: {exc}") from exc
        if porcentaje_iva > 100:
            raise ErrorIngesta(f"Fila {numero_fila}: porcentaje de IVA invalido")
        producto["iva_oferta"] = porcentaje_iva

    iva_incluido = obtener("iva_incluido")
    if _texto(iva_incluido):
        valor_iva = _clave(iva_incluido)
        if valor_iva in {"si", "yes", "true", "1", "incluido", "incluida"}:
            producto["iva_incluido"] = True
        elif valor_iva in {"no", "false", "0", "noincluido", "noincluida"}:
            producto["iva_incluido"] = False
        else:
            raise ErrorIngesta(
                f"Fila {numero_fila}: indique si el precio incluye IVA"
            )
    return producto


def _extraer_filas(
    filas: Iterable[Iterable[Any]],
    *,
    permitir_posicional: bool = False,
    desplazamiento: int = 0,
    precio_indice: int | None = None,
    columnas_forzadas: dict[str, int] | None = None,
    indice_cabecera_forzado: int | None = None,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    iterador = iter(filas)
    prefijo: list[list[Any]] = []
    indice_cabecera: int | None = indice_cabecera_forzado
    columnas: dict[str, int] | None = columnas_forzadas
    if columnas is not None and indice_cabecera is not None:
        iterador = itertools.islice(iter(filas), indice_cabecera + 1, None)
    else:
        for indice in range(100):
            try:
                fila = list(next(iterador))
            except StopIteration:
                break
            columnas = _mapear_cabecera(fila)
            if columnas is not None:
                indice_cabecera = indice
                break
            prefijo.append(fila)
    if columnas is not None and precio_indice is not None:
        columnas = {**columnas, "precio": precio_indice}

    if columnas is None:
        if not permitir_posicional:
            raise CabeceraIngestaAusente(
                "No se encontro una cabecera reconocible de codigo, nombre y precio"
            )
        columnas = {campo: indice for indice, campo in enumerate(TXT_COLUMNAS_POSICIONALES)}
        indice_cabecera = -1

    filas_datos = iterador if indice_cabecera >= 0 else itertools.chain(prefijo, iterador)
    numero_inicio = indice_cabecera + 2 + desplazamiento
    if indice_cabecera == -1:
        numero_inicio = 1 + desplazamiento

    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    cantidad_errores = 0
    cantidad_con_datos = 0
    cantidad_filas_leidas = 0
    for indice, fila in enumerate(filas_datos, start=numero_inicio):
        cantidad_filas_leidas += 1
        if cantidad_filas_leidas > MAX_FILAS_ARCHIVO + 101:
            raise ErrorIngesta(f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas")
        fila = list(fila)
        if not any(_texto(valor) for valor in fila):
            continue
        cantidad_con_datos += 1
        if cantidad_con_datos > MAX_FILAS_ARCHIVO:
            raise ErrorIngesta(f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas")
        try:
            if indice_cabecera == -1 and len(fila) > len(TXT_COLUMNAS_POSICIONALES):
                raise ErrorIngesta(
                    f"Fila {indice}: el orden posicional admite maximo "
                    f"{len(TXT_COLUMNAS_POSICIONALES)} columnas"
                )
            productos.append(_producto_desde_fila(fila, columnas, indice))
        except ErrorIngesta as exc:
            cantidad_errores += 1
            if len(errores) < MAX_ERRORES_DETALLE:
                errores.append(str(exc))

    if not productos and not cantidad_errores:
        raise ErrorIngesta("El archivo no contiene productos")
    if not productos:
        raise ArchivoSinFilasValidas(
            cantidad_errores,
            "No se encontro ninguna fila valida: " + "; ".join(errores),
        )
    return productos, cantidad_errores, errores


def _validar_paquete(contenido: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
            entradas = archivo.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise ErrorIngesta("El archivo comprimido esta danado") from exc
    if len(entradas) > MAX_ENTRADAS_ZIP:
        raise ErrorIngesta("El archivo contiene demasiados elementos comprimidos")
    total = sum(entrada.file_size for entrada in entradas)
    if total > MAX_DESCOMPRIMIDO_ZIP:
        raise ErrorIngesta("El contenido descomprimido supera el limite permitido")
    for entrada in entradas:
        if (
            entrada.file_size > 1024 * 1024
            and entrada.file_size / max(entrada.compress_size, 1) > MAX_RAZON_COMPRESION
        ):
            raise ErrorIngesta("El archivo excede el limite de compresion seguro")


def _columnas_precio(fila: Iterable[Any]) -> list[int]:
    indices = []
    for indice, valor in enumerate(fila):
        clave = _clave(valor)
        if _POR_SINONIMO.get(clave) == "precio" or (
            clave.startswith("precio")
            or clave.startswith("pvp")
            or clave.startswith("bsf")
        ):
            indices.append(indice)
    return indices


def _cabecera_compuesta(filas: list[Iterable[Any]], indice: int) -> list[str]:
    inicio = max(0, indice - 4)
    ancho = max((len(fila) for fila in filas[inicio : indice + 1]), default=0)
    return [
        " ".join(
            _texto(fila[columna])
            for fila in filas[inicio : indice + 1]
            if columna < len(fila) and _texto(fila[columna])
        )
        for columna in range(ancho)
    ]


def _inferir_columnas(filas: list[Iterable[Any]], inicio: int, indice_precio: int) -> dict[str, int] | None:
    filas_datos = [list(fila) for fila in filas[inicio + 1 : inicio + 31]]
    if not filas_datos:
        return None
    ancho = max(map(len, filas_datos), default=0)
    codigos: list[tuple[int, int]] = []
    nombres: list[tuple[int, int]] = []
    for columna in range(ancho):
        if columna == indice_precio:
            continue
        valores = [
            fila[columna] if columna < len(fila) else None for fila in filas_datos
        ]
        textos = [_texto(valor) for valor in valores]
        codigo = sum(
            bool(
                isinstance(valor, str)
                and re.fullmatch(
                    r"[A-Z0-9][A-Z0-9._/-]{5,}", valor.strip(), re.IGNORECASE
                )
                and any(caracter.isdigit() for caracter in valor)
            )
            for valor in valores
        )
        nombre = sum(
            len(texto) >= 4
            and any(caracter.isalpha() for caracter in texto)
            and not re.fullmatch(r"[A-Z0-9._/-]+", texto, re.IGNORECASE)
            for texto in textos
        )
        codigos.append((codigo, columna))
        nombres.append((nombre, columna))
    indice_codigo = max(codigos)[1]
    posibles_nombres = [par for par in nombres if par[1] != indice_codigo]
    if not codigos or not posibles_nombres or max(codigos)[0] < 2:
        return None
    cantidad_nombre, indice_nombre = max(posibles_nombres)
    if cantidad_nombre < 2:
        return None
    return {"codigo": indice_codigo, "nombre": indice_nombre, "precio": indice_precio}


def _extraer_xlsx(
    contenido: bytes,
    selecciones_precio: dict[int, int] | None = None,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    _validar_paquete(contenido)
    try:
        libro = load_workbook(
            io.BytesIO(contenido), read_only=True, data_only=True, keep_links=False
        )
    except (InvalidFileException, zipfile.BadZipFile, OSError, ValueError, KeyError) as exc:
        raise ErrorIngesta("No se pudo leer el archivo Excel") from exc

    productos: list[dict[str, Any]] = []
    errores = 0
    detalles: list[str] = []
    opciones_pendientes: list[dict[str, Any]] = []
    selecciones_precio = selecciones_precio or {}
    try:
        for indice_hoja, hoja in enumerate(libro.worksheets):
            filas = list(hoja.iter_rows(values_only=True))
            encontrada = next(
                (
                    (indice, _mapear_cabecera(fila), list(fila))
                    for indice, fila in enumerate(filas[:100])
                    if _mapear_cabecera(fila) is not None
                ),
                None,
            )
            if encontrada is None:
                encontrada = next(
                    (
                        (
                            indice,
                            _mapear_cabecera(cabecera),
                            cabecera,
                        )
                        for indice in range(min(100, len(filas)))
                        for cabecera in [_cabecera_compuesta(filas, indice)]
                        if _mapear_cabecera(cabecera) is not None
                    ),
                    None,
                )
            if encontrada is None:
                fila_precio = next(
                    (
                        (indice, precios[0])
                        for indice, fila in enumerate(filas[:100])
                        if (precios := _columnas_precio(fila))
                    ),
                    None,
                )
                if fila_precio is None:
                    continue
                indice_cabecera, indice_precio = fila_precio
                columnas = _inferir_columnas(filas, indice_cabecera, indice_precio)
                if columnas is None:
                    continue
                filas_hoja, errores_hoja, detalle_hoja = _extraer_filas(
                    filas,
                    precio_indice=indice_precio,
                    columnas_forzadas=columnas,
                    indice_cabecera_forzado=indice_cabecera,
                )
                productos.extend(filas_hoja)
                errores += errores_hoja
                detalles.extend(detalle_hoja)
                continue
            indice_cabecera, columnas, cabecera = encontrada
            precios = _columnas_precio(cabecera)
            indice_precio = selecciones_precio.get(indice_hoja)
            if len(precios) > 1 and indice_precio is None:
                # Se acumulan todas las hojas ambiguas para preguntar una sola
                # vez; antes se abortaba en la primera y el usuario tenia que
                # repetir la seleccion hoja por hoja.
                opciones_pendientes.extend(
                    {
                        "hoja": hoja.title,
                        "hoja_indice": indice_hoja,
                        "columna": _texto(cabecera[indice]),
                        "columna_indice": indice,
                    }
                    for indice in precios
                )
                continue
            if indice_precio is not None and indice_precio not in precios:
                raise ErrorIngesta(
                    f"La columna de precio seleccionada no existe en la hoja {hoja.title}"
                )
            if len(precios) == 1:
                indice_precio = precios[0]
            try:
                filas_hoja, errores_hoja, detalle_hoja = _extraer_filas(
                    filas,
                    precio_indice=indice_precio,
                    columnas_forzadas=columnas,
                    indice_cabecera_forzado=indice_cabecera,
                )
            except CabeceraIngestaAusente:
                continue
            productos.extend(filas_hoja)
            errores += errores_hoja
            detalles.extend(detalle_hoja)
            if len(productos) + errores > MAX_FILAS_ARCHIVO:
                raise ErrorIngesta(
                    f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas"
                )
    finally:
        libro.close()
    if opciones_pendientes:
        raise SeleccionPrecioRequerida(opciones_pendientes)
    if not productos:
        raise ErrorIngesta("El libro no contiene una tabla con codigo, nombre y precio")
    return productos, errores, detalles


def _extraer_fichas_etiquetadas(texto: str) -> tuple[list[dict[str, Any]], int, list[str]]:
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    ficha: dict[str, str] = {}
    numero = 0

    def guardar() -> None:
        nonlocal ficha, numero
        if not ficha:
            return
        numero += 1
        codigo = ficha.get("codigo", "")
        nombre = ficha.get("nombre", "")
        precio = ficha.get("precio", "")
        if not (codigo and nombre and precio):
            errores.append(f"Ficha {numero}: faltan codigo, descripcion o precio")
        else:
            try:
                productos.append(
                    _producto_desde_fila(
                        [codigo, nombre, precio, ficha.get("marca", "")],
                        {"codigo": 0, "nombre": 1, "precio": 2, "marca": 3},
                        numero,
                    )
                )
            except ErrorIngesta as exc:
                errores.append(str(exc))
        ficha = {}

    for linea in texto.splitlines():
        coincidencia = re.match(r"\s*([^:]{2,30})\s*:\s*(.*?)\s*$", linea)
        if not coincidencia:
            continue
        etiqueta = _clave(coincidencia.group(1))
        campo = _POR_SINONIMO.get(etiqueta)
        if campo is None:
            if etiqueta.startswith(("sku", "codigo", "cod", "referencia")):
                campo = "codigo"
            elif etiqueta.startswith(
                ("descripcion", "description", "producto", "nombre", "articulo")
            ):
                campo = "nombre"
            elif etiqueta.startswith(("precio", "pvp")):
                campo = "precio"
            elif etiqueta.startswith(("marca", "fabricante")):
                campo = "marca"
        if not campo:
            continue
        if campo == "descripcion":
            campo = "nombre"
        if campo == "codigo" and ficha.get("codigo"):
            guardar()
        ficha[campo] = coincidencia.group(2).strip()
    guardar()
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _extraer_docx(contenido: bytes) -> tuple[list[dict[str, Any]], int, list[str]]:
    _validar_paquete(contenido)
    try:
        documento = Document(io.BytesIO(contenido))
    except (PackageNotFoundError, zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ErrorIngesta("No se pudo leer el documento Word") from exc

    productos: list[dict[str, Any]] = []
    errores = 0
    detalles: list[str] = []
    for tabla in documento.tables:
        try:
            productos_tabla, errores_tabla, detalle_tabla = _extraer_filas(
                ([celda.text for celda in fila.cells] for fila in tabla.rows)
            )
        except CabeceraIngestaAusente:
            continue
        productos.extend(productos_tabla)
        errores += errores_tabla
        detalles.extend(detalle_tabla)
        if len(productos) + errores > MAX_FILAS_ARCHIVO:
            raise ErrorIngesta(
                f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas"
            )
    if not productos:
        texto = "\n".join(
            parrafo.text.strip()
            for parrafo in documento.paragraphs
            if parrafo.text.strip()
        )
        productos, errores, detalles = _extraer_fichas_etiquetadas(texto)
    if not productos:
        if errores:
            raise ArchivoSinFilasValidas(
                errores,
                "No se encontro ninguna ficha valida: " + "; ".join(detalles),
            )
        raise ErrorIngesta(
            "El documento no contiene tablas ni fichas con codigo, descripcion y precio"
        )
    return productos, errores, detalles


def _filas_pdf(texto: str) -> list[list[str]]:
    resultado: list[list[str]] = []
    for numero, linea in enumerate(io.StringIO(texto), start=1):
        if numero > MAX_FILAS_ARCHIVO + 101:
            raise ErrorIngesta(f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas")
        if not linea.strip():
            continue
        separador = _separador(linea)
        if separador:
            resultado.append(next(csv.reader([linea], delimiter=separador, skipinitialspace=True)))
        elif re.search(r"\s{2,}", linea.strip()):
            resultado.append(re.split(r"\s{2,}", linea.strip()))
        else:
            resultado.append(linea.split())
    return resultado


# --- Lectura por coordenadas de PDF -----------------------------------------
# Un mismo PDF puede traer una tabla, varias columnas de productos o fichas.
# El lector por coordenadas reconstruye, por pagina, las lineas visuales y las
# divide en "bandas" (una por columna de codigos) para no perder los productos
# de la segunda columna ni mezclar el precio de una columna con el nombre de la
# otra. Las heuristicas descartan medidas (16MM, 3/8") como posibles codigos.
PATRON_CODIGO_PDF = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{2,}$", re.IGNORECASE)
PATRON_PRECIO_PDF = re.compile(r"^\$?\s*\d[\d.,]*$")
PATRON_MEDIDA_PDF = re.compile(
    r"^\d+(?:[.,]\d+)?\s*(?:MM|CM|MTS?|M|KGS?|GRS?|LTS?|L|PUL|UN|U|X|PULG|\"|''|/)$",
    re.IGNORECASE,
)
ETIQUETAS_PDF = frozenset(
    {
        "cod", "codigo", "codigos", "sku", "referencia", "ref", "item",
        "descripcion", "descripciones", "producto", "articulo", "imagen",
        "precio", "precios", "pvp", "bs", "bsf", "usd", "medida", "medidas",
        "unidad", "unidades", "cantidad", "disponible", "marca",
    }
)
TOLERANCIA_LINEA_PDF = 1.5
SALTO_COLUMNA_PDF = 25.0
DISTANCIA_MAXIMA_PDF = 15.0


def _es_codigo_pdf(valor: str) -> bool:
    """Un codigo de catalogo real: alfanumerico, con digito y sin medidas."""
    texto = valor.strip()
    if not PATRON_CODIGO_PDF.fullmatch(texto):
        return False
    tiene_digito = any(caracter.isdigit() for caracter in texto)
    tiene_letra = any(caracter.isalpha() for caracter in texto)
    if not tiene_digito:
        return False
    # "U16" o "TA20" son codigos validos; "16" o "110" son medidas. Los
    # codigos puramente numericos se aceptan solo si son largos (10102006).
    if not tiene_letra and len(texto) < 5:
        return False
    return PATRON_MEDIDA_PDF.fullmatch(texto) is None


def _es_precio_pdf(valor: str) -> bool:
    return PATRON_PRECIO_PDF.fullmatch(valor.replace(" ", "")) is not None


def _es_etiqueta_pdf(valor: str) -> bool:
    clave = _clave(valor)
    if not clave:
        return True
    if clave in ETIQUETAS_PDF:
        return True
    return clave.startswith(("precio", "medida", "descripcion", "codigo", "imagen"))


PALABRAS_NO_TITULO = (
    "lista", "precio", "valida", "válida", "garantia", "garantía", "producto",
    "resiste", "durabilidad", "elaborado", "politica", "política", "ventas",
    "descuento", "oferta", "telefono", "teléfono", "rif", "pagina", "página",
)


def _es_titulo_pdf(valor: str) -> bool:
    """Un encabezado de seccion: solo palabras, corto y sin datos."""
    texto = valor.strip()
    if not 4 <= len(texto) <= 40:
        return False
    if any(caracter.isdigit() for caracter in texto):
        return False
    if sum(caracter.isalpha() for caracter in texto) < 3:
        return False
    clave = _clave(texto)
    if not clave or clave in ETIQUETAS_PDF:
        return False
    return not any(palabra in clave for palabra in PALABRAS_NO_TITULO)


def _lineas_pdf(fragmentos: list[tuple[float, float, str]]) -> list[list[tuple[float, str]]]:
    """Agrupa fragmentos por linea visual (y) y los ordena de izquierda a derecha."""
    grupos: list[list[tuple[float, float, str]]] = []
    for x, y, texto in sorted(fragmentos, key=lambda parte: (-parte[1], parte[0])):
        grupo = next(
            (actual for actual in grupos if abs(actual[0][1] - y) <= TOLERANCIA_LINEA_PDF),
            None,
        )
        if grupo is None:
            grupos.append([(x, y, texto)])
        else:
            grupo.append((x, y, texto))
    return [
        [(x, texto) for x, _y, texto in sorted(grupo, key=lambda parte: parte[0])]
        for grupo in grupos
    ]


def _bandas_pdf(lineas: list[list[tuple[float, str]]]) -> list[float]:
    """Detecta el borde izquierdo de cada columna de codigos de la pagina."""
    inicios: list[float] = []
    for linea in lineas:
        anterior: tuple[float, str] | None = None
        for x, texto in linea:
            if _es_codigo_pdf(texto) and (
                anterior is None or x - anterior[0] >= SALTO_COLUMNA_PDF
            ):
                inicios.append(x)
            anterior = (x, texto)
    bordes: list[float] = []
    for x in sorted(inicios):
        if not bordes or x - bordes[-1] > SALTO_COLUMNA_PDF * 1.6:
            bordes.append(x)
    return bordes


def _repartir_por_banda(
    linea: list[tuple[float, str]], bordes: list[float]
) -> dict[int, list[tuple[float, str]]]:
    """Asigna cada fragmento a su columna segun el borde izquierdo."""
    grupos: dict[int, list[tuple[float, str]]] = {}
    for x, texto in linea:
        banda = 0
        for indice, borde in enumerate(bordes):
            if x >= borde - TOLERANCIA_LINEA_PDF:
                banda = indice
        grupos.setdefault(banda, []).append((x, texto))
    return grupos


def _ficha_pdf(
    tokens: list[tuple[float, str]],
) -> tuple[str, str | None, str] | None:
    """Separa (codigo, descripcion, precio) dentro de una columna."""
    codes = [indice for indice, (_x, texto) in enumerate(tokens) if _es_codigo_pdf(texto)]
    if not codes:
        return None
    primero = codes[0]
    precio: int | None = None
    for indice in range(len(tokens) - 1, primero, -1):
        if _es_precio_pdf(tokens[indice][1]):
            precio = indice
            break
    if precio is None:
        return None
    descripcion = [
        texto
        for _x, texto in tokens[primero + 1 : precio]
        if not _es_etiqueta_pdf(texto)
    ]
    return (
        tokens[primero][1],
        " ".join(descripcion) or None,
        tokens[precio][1],
    )


def _extraer_pdf_espacial(lector: PdfReader) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae productos por coordenadas, admitiendo varias columnas por pagina."""
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    numero_fila = 0

    for pagina in lector.pages:
        fragmentos: list[tuple[float, float, str]] = []

        def recoger(texto, _matriz, posicion, _fuente, _tamano):
            limpio = texto.strip()
            if limpio:
                fragmentos.append((float(posicion[4]), float(posicion[5]), limpio))

        pagina.extract_text(visitor_text=recoger)
        lineas = _lineas_pdf(fragmentos)
        bordes = _bandas_pdf(lineas)
        if not bordes:
            continue

        pendientes: dict[int, dict[str, Any]] = {}
        descripciones: dict[int, tuple[str, int]] = {}
        secciones: dict[int, str] = {}
        for indice_linea, linea in enumerate(lineas):
            for banda, tokens in _repartir_por_banda(linea, bordes).items():
                tokens.sort()
                ficha = _ficha_pdf(tokens)
                if ficha is not None:
                    codigo, descripcion, precio = ficha
                    if not descripcion:
                        # Hay catalogos con la descripcion en la linea
                        # anterior al codigo (p. ej. ASPERSOR / AS01 / BOQ).
                        anterior = descripciones.pop(banda, None)
                        if anterior and indice_linea - anterior[1] <= 1:
                            descripcion = anterior[0]
                    else:
                        descripciones.pop(banda, None)
                    if not descripcion:
                        continue
                    seccion = secciones.get(banda)
                    if (
                        seccion
                        and len(descripcion) < 25
                        and _clave(seccion) not in _clave(descripcion)
                    ):
                        descripcion = f"{seccion} {descripcion}"
                    numero_fila += 1
                    pendientes.pop(banda, None)
                    try:
                        productos.append(
                            _producto_desde_fila(
                                [codigo, descripcion, precio],
                                {"codigo": 0, "nombre": 1, "precio": 2},
                                numero_fila,
                            )
                        )
                    except ErrorIngesta as exc:
                        errores.append(str(exc))
                    continue

                if len(tokens) == 1:
                    texto = tokens[0][1]
                    if _es_titulo_pdf(texto):
                        # Encabezado de seccion de esa columna (p. ej. "UNION
                        # RAPIDA"): da contexto a las medidas que vienen debajo.
                        secciones[banda] = texto
                    elif not _es_etiqueta_pdf(texto):
                        descripciones[banda] = (texto, indice_linea)
                    continue

                codigos = [texto for _x, texto in tokens if _es_codigo_pdf(texto)]
                precios = [texto for _x, texto in tokens if _es_precio_pdf(texto)]
                if codigos and not precios:
                    # El precio puede estar en la linea siguiente de la misma
                    # columna: se guarda la ficha y se completa al encontrarlo.
                    pendientes[banda] = {
                        "codigo": codigos[0],
                        "descripcion": " ".join(
                            texto for _x, texto in tokens if not _es_etiqueta_pdf(texto)
                            and texto != codigos[0]
                        ),
                    }
                elif precios and not codigos and banda in pendientes:
                    pendiente = pendientes.pop(banda)
                    if pendiente["descripcion"]:
                        numero_fila += 1
                        try:
                            productos.append(
                                _producto_desde_fila(
                                    [
                                        pendiente["codigo"],
                                        pendiente["descripcion"],
                                        precios[-1],
                                    ],
                                    {"codigo": 0, "nombre": 1, "precio": 2},
                                    numero_fila,
                                )
                            )
                        except ErrorIngesta as exc:
                            errores.append(str(exc))
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _extraer_pdf_fichas(lector: PdfReader) -> tuple[list[dict[str, Any]], int, list[str]]:
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    patron_codigo = re.compile(
        r"\b(?:sku|codigo|c[oó]digo|referencia)\s*:\s*([A-Z0-9][A-Z0-9._/-]{3,})",
        re.IGNORECASE,
    )
    patron_precio = re.compile(r"\bprecio\s*:\s*(.+)$", re.IGNORECASE)
    metadatos = ("politica", "cantidad", "marca", "unidad")

    for pagina in lector.pages:
        lineas = [
            linea.strip()
            for linea in (pagina.extract_text() or "").splitlines()
            if linea.strip()
        ]
        posiciones = [
            (indice, patron_codigo.search(linea))
            for indice, linea in enumerate(lineas)
            if patron_codigo.search(linea)
        ]
        for numero, (indice, coincidencia) in enumerate(posiciones, start=1):
            inicio = posiciones[numero - 2][0] + 1 if numero > 1 else 0
            segmento = lineas[inicio:indice]
            fin = posiciones[numero][0] if numero < len(posiciones) else len(lineas)
            metadatos_ficha = lineas[indice + 1 : fin]
            precios = [
                (pos, patron_precio.search(linea))
                for pos, linea in enumerate(segmento)
                if patron_precio.search(linea)
            ]
            if not precios:
                errores.append(f"Ficha {numero}: no se encontro el precio")
                continue
            indice_precio, precio = precios[-1]
            nombre = " ".join(
                linea
                for linea in segmento[:indice_precio]
                if not any(_clave(linea).startswith(clave) for clave in metadatos)
                and _clave(linea) not in {"imp", "politicaventas"}
            ).strip()
            nombre = re.sub(r"(?<=\d)-\s+(?=\d)", "-", nombre)
            marca = next(
                (
                    coincidencia_marca.group(1).strip()
                    for linea in metadatos_ficha
                    if (
                        coincidencia_marca := re.search(
                            r"\bmarca\s*:\s*(.+)$", linea, re.IGNORECASE
                        )
                    )
                ),
                "",
            )
            try:
                producto = _producto_desde_fila(
                    [coincidencia.group(1), nombre, precio.group(1), marca],
                    {"codigo": 0, "nombre": 1, "precio": 2, "marca": 3},
                    numero,
                )
                for linea in metadatos_ficha:
                    cantidad = re.search(
                        r"\bcantidad\s*(?:disp\.?|disponible)\s*:\s*([\d.,]+)",
                        linea,
                        re.IGNORECASE,
                    )
                    if cantidad:
                        numero_cantidad = _leer_precio(
                            cantidad.group(1), campo="cantidad disponible"
                        )
                        if numero_cantidad != numero_cantidad.to_integral_value():
                            raise ErrorIngesta(
                                f"Ficha {numero}: cantidad disponible no entera"
                            )
                        producto["cantidad_disponible_proveedor"] = int(
                            numero_cantidad
                        )
                    politica = re.search(
                        r"\bpol[ií]tica\s+ventas?\s*:\s*(.*)$",
                        linea,
                        re.IGNORECASE,
                    )
                    if politica and politica.group(1).strip():
                        producto["politica_ventas"] = politica.group(1).strip()[:4000]
                    descuento = re.search(
                        r"\bdescuento\s*:\s*(.+)$", linea, re.IGNORECASE
                    )
                    if descuento and descuento.group(1).strip():
                        producto["descuento_oferta"] = _leer_precio(
                            descuento.group(1), campo="descuento"
                        )
                    iva = re.search(
                        r"\biva\s*:?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*%",
                        linea,
                        re.IGNORECASE,
                    )
                    if iva:
                        producto["iva_oferta"] = _leer_precio(
                            iva.group(1), campo="IVA"
                        )
                        if producto["iva_oferta"] > 100:
                            raise ErrorIngesta(
                                f"Ficha {numero}: porcentaje de IVA invalido"
                            )
                    texto_iva = _clave(linea)
                    if re.search(
                        r"iva.*noincluid|noincluid.*iva|masiva",
                        texto_iva,
                    ):
                        producto["iva_incluido"] = False
                    elif re.search(r"iva.*incluid|incluid.*iva", texto_iva):
                        producto["iva_incluido"] = True
                    if "iva_oferta" not in producto and re.search(
                        r"siniva|noiva", texto_iva
                    ):
                        producto["iva_oferta"] = Decimal("0.00")
                productos.append(producto)
            except ErrorIngesta as exc:
                errores.append(str(exc))
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _extraer_pdf_tabla(texto: str) -> tuple[list[dict[str, Any]], int, list[str]]:
    filas = texto.splitlines()
    indice_cabecera = next(
        (
            indice
            for indice, linea in enumerate(filas[:100])
            if {"codigo", "nombre", "precio"}.issubset(
                set(_mapear_cabecera(linea.split()) or {})
            )
        ),
        None,
    )
    if indice_cabecera is None:
        return [], 0, []

    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    fila_producto = re.compile(
        r"^\s*([A-Z0-9][A-Z0-9._/-]{5,})\s+(.+?)\s{2,}\$?\s*(\d[\d.,]*)\s*$",
        re.IGNORECASE,
    )
    for numero, linea in enumerate(filas[indice_cabecera + 1 :], start=1):
        coincidencia = fila_producto.match(linea)
        if not coincidencia:
            continue
        try:
            productos.append(
                _producto_desde_fila(
                    list(coincidencia.groups()),
                    {"codigo": 0, "nombre": 1, "precio": 2},
                    numero,
                )
            )
        except ErrorIngesta as exc:
            errores.append(str(exc))
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _unir_estrategias_pdf(
    resultados: Iterable[tuple[str, list[dict[str, Any]], int, list[str]]],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Combina las estrategias de lectura de PDF sin perder paginas.

    Un catalogo puede mezclar tabla, columnas y fichas. Antes se devolvia la
    primera estrategia que encontraba algo, de modo que las paginas con otro
    formato se descartaban en silencio. Aqui se unen por codigo; se exige que
    el codigo tenga digitos para descartar cortes de nombre sin sentido.
    """
    fichas: dict[str, dict[str, Any]] = {}
    errores_maximos = 0
    detalles: list[str] = []
    conflictos: list[str] = []
    for _nombre, productos, errores, detalle in resultados:
        validos = [
            producto
            for producto in productos
            if any(caracter.isdigit() for caracter in producto.get("codigo", ""))
        ]
        if not validos:
            continue
        # Un lector que falla mas filas de las que entiende esta leyendo mal la
        # pagina: se descarta para no sumar ruido ni marcar el archivo como
        # parcial. Otra estrategia cubre ese formato.
        if errores > len(validos):
            continue
        errores_maximos = max(errores_maximos, errores)
        for texto in detalle:
            if texto not in detalles:
                detalles.append(texto)
        for producto in validos:
            previo = fichas.get(producto["codigo"])
            if previo is None:
                fichas[producto["codigo"]] = producto
                continue
            actual = sum(
                bool(producto.get(campo))
                for campo in ("nombre", "marca", "descripcion")
            ) + len(producto.get("nombre") or "")
            anterior = sum(
                bool(previo.get(campo))
                for campo in ("nombre", "marca", "descripcion")
            ) + len(previo.get("nombre") or "")
            if actual > anterior:
                elegido, complemento = producto, previo
            else:
                elegido, complemento = previo, producto
            for campo in (
                "cantidad_disponible_proveedor",
                "politica_ventas",
                "descuento_oferta",
                "iva_oferta",
                "iva_incluido",
            ):
                if elegido.get(campo) is None and complemento.get(campo) is not None:
                    elegido[campo] = complemento[campo]
            fichas[producto["codigo"]] = elegido
            if (previo.get("nombre"), previo.get("precio")) != (
                producto.get("nombre"),
                producto.get("precio"),
            ):
                conflictos.append(producto["codigo"])
    if conflictos:
        detalles.append(
            f"{len(set(conflictos))} codigo(s) se leyeron con dos formatos "
            "distintos; se conservo la ficha mas completa de cada uno"
        )
    return list(fichas.values()), errores_maximos, detalles[:MAX_ERRORES_DETALLE]


def _extraer_pdf(contenido: bytes) -> tuple[list[dict[str, Any]], int, list[str]]:
    try:
        lector = PdfReader(io.BytesIO(contenido), strict=True)
        if len(lector.pages) > MAX_PAGINAS_PDF:
            raise ErrorIngesta(f"El PDF supera el maximo de {MAX_PAGINAS_PDF} paginas")
        paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    except ErrorIngesta:
        raise
    except (PdfReadError, OSError, ValueError, KeyError) as exc:
        raise ErrorIngesta("No se pudo leer el PDF") from exc

    texto = "\n".join(paginas)
    if not texto.strip():
        raise ErrorIngesta("El PDF no contiene texto legible; no se admite OCR")

    resultados: list[tuple[str, list[dict[str, Any]], int, list[str]]] = []
    estrategias = (
        ("espacial", _extraer_pdf_espacial),
        ("fichas", _extraer_pdf_fichas),
    )
    for nombre_estrategia, estrategia in estrategias:
        try:
            lector = PdfReader(io.BytesIO(contenido), strict=True)
            resultados.append(
                (nombre_estrategia, *estrategia(lector))
            )
        except (PdfReadError, OSError, ValueError, KeyError, TypeError) as exc:
            logger.info(
                "La estrategia %s no aplica a este PDF: %s", nombre_estrategia, exc
            )

    resultados.append(("tabla", *_extraer_pdf_tabla(texto)))

    filas = _filas_pdf(texto)
    for indice, fila in enumerate(filas):
        if fila and _clave(fila[0]) == "imagen":
            filas[indice] = fila[1:]
    for indice, fila in enumerate(filas):
        columnas = _mapear_cabecera(fila)
        if columnas is None:
            continue
        encabezados = len(fila)
        filas_normalizadas = [fila]
        for datos in filas[indice + 1 :]:
            if len(datos) > encabezados and encabezados == 3 and set(columnas) >= {
                "codigo", "nombre", "precio"
            }:
                datos = [datos[0], " ".join(datos[1:-1]), datos[-1]]
            filas_normalizadas.append(datos)
        try:
            resultados.append(("generica", *_extraer_filas(filas_normalizadas)))
        except (CabeceraIngestaAusente, ArchivoSinFilasValidas):
            pass
        break

    productos, errores, detalles = _unir_estrategias_pdf(resultados)
    if productos:
        return productos, errores, detalles
    raise CabeceraIngestaAusente(
        "No se encontro una tabla ni fichas con codigo, descripcion y precio"
    )


def _extraer_txt(contenido: bytes) -> tuple[list[dict[str, Any]], int, list[str]]:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ErrorIngesta("El archivo TXT debe estar codificado en UTF-8") from exc
    filas = _filas_delimitadas(texto)
    primera_linea = texto.partition("\n")[0]
    tiene_separador_no_ambiguo = bool(_separador(primera_linea))
    tiene_cabecera = any(_mapear_cabecera(fila) for fila in filas[:100])
    if not tiene_cabecera and not tiene_separador_no_ambiguo and "," in texto:
        raise ErrorIngesta(
            "El TXT posicional debe separar columnas con punto y coma, barra vertical o tabulador"
        )
    return _extraer_filas(filas, permitir_posicional=True)


def _extraer_markdown(
    contenido: bytes,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    try:
        markdown = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ErrorIngesta("El archivo Markdown debe estar codificado en UTF-8") from exc

    productos, errores, detalles, _ = _extraer_registros_markdown(markdown)
    if not productos:
        raise ErrorIngesta("El archivo Markdown no contiene productos verificables")
    return productos, errores, detalles


def _nombre_seguro(nombre: str) -> str:
    nombre = nombre.replace("\\", "/").rsplit("/", 1)[-1]
    nombre = "".join(caracter for caracter in nombre if caracter.isprintable())
    nombre = nombre.strip()
    if not nombre or len(nombre) > 255:
        raise ErrorIngesta("El nombre del archivo esta vacio o supera 255 caracteres")
    return nombre


def _ruta_original(nombre: str) -> tuple[Path, str]:
    directorio = get_settings().uploads_dir.resolve()
    estaticos = (Path(__file__).resolve().parents[1] / "static").resolve()
    if directorio == estaticos or estaticos in directorio.parents:
        raise RuntimeError("UPLOADS_DIR no puede estar dentro del directorio de estaticos")
    directorio.mkdir(parents=True, exist_ok=True)
    extension = Path(nombre).suffix.lower()
    nombre_archivo = f"{uuid.uuid4().hex}{extension}"
    ruta = directorio / nombre_archivo
    ruta_resuelta = ruta.resolve()
    if ruta_resuelta.parent != directorio:
        raise RuntimeError("La ruta configurada para cargas no es segura")
    return ruta, nombre_archivo


def _escribir_original(ruta: Path, contenido: bytes) -> None:
    try:
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(contenido)
    except OSError:
        ruta.unlink(missing_ok=True)
        raise


def _detalle(errores: list[str]) -> str | None:
    if not errores:
        return None
    detalle = "; ".join(errores[:MAX_ERRORES_DETALLE])
    return detalle[:MAX_DETALLE]


def _aviso_sin_descripcion(productos: Iterable[dict[str, Any]]) -> str | None:
    """Cuenta los productos que el proveedor no describio.

    No es un error de fila: el producto se guarda igual y se vectoriza. Es un
    aviso de cobertura para que el operador sepa que esos articulos quedaran
    indexados con codigo, nombre, marca y categoria, y que la recuperacion
    depende solo de esos campos.
    """
    total = sum(
        1
        for producto in productos
        if not _texto(producto.get("descripcion")).strip()
    )
    if not total:
        return None
    plural = "producto" if total == 1 else "productos"
    return (
        f"{total} {plural} sin descripcion en el archivo; se indexan con "
        "el nombre y los demas datos disponibles"
    )


def _consolidar_codigos(
    productos: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    """Consolida SKU repetidos conservando siempre una ficha por codigo.

    Antes, un codigo repetido con datos distintos descartaba *todas* sus
    variantes: el producto desaparecia del catalogo y el asistente no podia
    responder sobre el. Ahora se conserva la ficha mas completa (a igualdad,
    la primera del documento) y el conflicto se informa para que el operador
    lo revise. Un codigo representa un producto: no se duplica en la base.
    """
    grupos: dict[str, list[dict[str, Any]]] = {}
    for producto in productos:
        grupos.setdefault(producto["codigo"], []).append(producto)

    unicos: list[dict[str, Any]] = []
    filas_duplicadas = 0
    filas_error = 0
    detalles: list[str] = []
    for codigo, grupo in grupos.items():
        if len(grupo) == 1:
            unicos.append(grupo[0])
            continue

        filas_duplicadas += len(grupo) - 1
        if all(producto == grupo[0] for producto in grupo[1:]):
            unicos.append(grupo[0])
            detalles.append(
                f"Codigo {codigo} repetido {len(grupo)} veces con los mismos datos; "
                "se guardara una sola ficha"
            )
            continue

        elegido = max(
            grupo,
            key=lambda producto: (
                sum(
                    bool(producto.get(campo))
                    for campo in ("nombre", "marca", "descripcion")
                ),
                len(producto.get("nombre") or ""),
            ),
        )
        unicos.append(elegido)
        detalles.append(
            f"Codigo {codigo} aparece {len(grupo)} veces con datos diferentes; "
            f"se conservo \"{elegido['nombre'][:60]}\" y se descartaron "
            f"{len(grupo) - 1} variante(s). Revise el catalogo del proveedor"
        )

    return unicos, filas_duplicadas, filas_error, detalles


def _extraer(
    nombre: str,
    contenido: bytes,
    selecciones_precio: dict[int, int] | None = None,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    extension = Path(nombre).suffix.lower()
    extractores = {
        ".pdf": _extraer_pdf,
        ".xlsx": _extraer_xlsx,
        ".docx": _extraer_docx,
        ".txt": _extraer_txt,
        ".md": _extraer_markdown,
    }
    if extension == ".xlsx":
        return _extraer_xlsx(contenido, selecciones_precio)
    return extractores[extension](contenido)


# --- Conversion a Markdown con Microsoft MarkItDown (RF-02.4) ----------------
# MarkItDown convierte PDF, Excel, Word y TXT a Markdown; los archivos .md se
# leen directamente. El texto se guarda en archivos_subidos.contenido_markdown
# y es el insumo documentado del ETL. La conversion no reemplaza la validacion
# ni la extraccion estructurada que carga los productos relacionales.
AVISO_SIN_MARKDOWN = (
    "No se pudo convertir el archivo a Markdown con MarkItDown; el catalogo "
    "se proceso con los lectores de filas"
)


def convertir_a_markdown(ruta: Path) -> tuple[str | None, str | None]:
    """Convierte un catalogo a Markdown; lee directamente los archivos .md.

    Devuelve ``(markdown, aviso)``. Si falla la conversion MarkItDown, los
    lectores de filas de PDF, Excel, Word y TXT siguen operando; los archivos
    .md requieren que el contenido fuente se pueda leer. Se eliminan los
    caracteres ``\\x00`` porque PostgreSQL los rechaza en columnas de texto.
    """
    if ruta.suffix.lower() == ".md":
        try:
            markdown = ruta.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("No se pudo leer el Markdown %s: %s", ruta.name, exc)
            return None, AVISO_SIN_MARKDOWN
        markdown = markdown.replace("\x00", "")
        if not markdown.strip():
            return None, AVISO_SIN_MARKDOWN
        if len(markdown) > MAX_MARKDOWN_CARACTERES:
            return None, (
                f"El Markdown del archivo supera el limite de "
                f"{MAX_MARKDOWN_CARACTERES} caracteres y no se guardo"
            )
        return markdown, None

    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        logger.warning("Microsoft MarkItDown no esta instalado: %s", exc)
        return None, AVISO_SIN_MARKDOWN

    try:
        markdown = MarkItDown().convert(str(ruta)).text_content or ""
    except Exception as exc:  # noqa: BLE001 - una conversion jamas rompe la carga
        logger.warning("MarkItDown no pudo convertir %s: %s", ruta.name, exc)
        return None, AVISO_SIN_MARKDOWN

    markdown = markdown.replace("\x00", "")
    if not markdown.strip():
        logger.warning("MarkItDown no produjo contenido para %s", ruta.name)
        return None, AVISO_SIN_MARKDOWN
    if len(markdown) > MAX_MARKDOWN_CARACTERES:
        logger.warning(
            "El Markdown de %s supera %s caracteres y no se guarda",
            ruta.name,
            MAX_MARKDOWN_CARACTERES,
        )
        return None, (
            f"El Markdown del archivo supera el limite de "
            f"{MAX_MARKDOWN_CARACTERES} caracteres y no se guardo"
        )
    return markdown, None


def _convertir_contenido_a_markdown(
    nombre: str, contenido: bytes
) -> tuple[str | None, str | None]:
    """Convierte bytes a Markdown durante la vista previa sin guardarlos."""
    if Path(nombre).suffix.lower() == ".md":
        try:
            markdown = contenido.decode("utf-8-sig").replace("\x00", "")
        except UnicodeDecodeError:
            return None, AVISO_SIN_MARKDOWN
        return (markdown, None) if markdown.strip() else (None, AVISO_SIN_MARKDOWN)

    try:
        with tempfile.TemporaryDirectory(prefix="fipca-preview-") as temporal:
            ruta = Path(temporal) / f"archivo{Path(nombre).suffix.lower()}"
            ruta.write_bytes(contenido)
            return convertir_a_markdown(ruta)
    except OSError as exc:
        logger.warning("No se pudo preparar %s para la vista previa: %s", nombre, exc)
        return None, AVISO_SIN_MARKDOWN


def _extraer_registros_markdown(
    markdown: str,
) -> tuple[list[dict[str, Any]], int, list[str], dict[str, Any]]:
    try:
        registros = markdown_transform_service.transformar_markdown(markdown)
    except markdown_transform_service.ErrorTransformacionMarkdown as exc:
        raise ErrorIngesta(str(exc)) from exc

    respuesta_ia = {"productos": registros}
    if not registros:
        return [], 0, [], respuesta_ia

    columnas = (
        "codigo",
        "nombre",
        "precio",
        "marca",
        "descripcion",
        "descuentos",
        "iva",
        "iva_incluido",
        "cantidad_disponible_proveedor",
        "politica_ventas",
    )
    filas: list[list[Any]] = [list(columnas)]
    for registro in registros:
        fila = []
        for campo in columnas:
            valor = registro.get(campo)
            if campo == "iva_incluido" and isinstance(valor, bool):
                valor = "si" if valor else "no"
            fila.append("" if valor is None else valor)
        filas.append(fila)
    try:
        productos, errores, detalles = _extraer_filas(
            filas, desplazamiento=0, indice_cabecera_forzado=0
        )
    except ErrorIngesta as exc:
        raise ErrorRespuestaIA(str(exc), respuesta_ia) from exc
    return productos, errores, detalles, respuesta_ia


def _extraer_con_respaldo_ia(
    nombre: str,
    contenido: bytes,
    markdown: str | None,
    selecciones_precio: dict[int, int] | None = None,
) -> tuple[list[dict[str, Any]], int, list[str], dict[str, Any] | None]:
    """Prefiere el JSON validado de IA y conserva el lector como respaldo."""
    extension = Path(nombre).suffix.lower()
    if extension == ".md":
        if markdown is None:
            return (*_extraer(nombre, contenido, selecciones_precio), None)
        return _extraer_registros_markdown(markdown)

    local: tuple[list[dict[str, Any]], int, list[str]] | None = None
    error_local: ErrorIngesta | None = None
    try:
        local = _extraer(
            nombre, contenido, selecciones_precio
        )
    except SeleccionPrecioRequerida:
        raise
    except ErrorIngesta as exc:
        error_local = exc

    if not markdown:
        if local is not None:
            return (*local, None)
        if error_local is not None:
            raise error_local
        raise ErrorIngesta("No se pudo extraer el contenido del archivo")

    # Una seleccion manual de precios en Excel tiene prioridad sobre cualquier
    # interpretacion del modelo para no cambiar la columna confirmada.
    if extension == ".xlsx" and selecciones_precio:
        if local is not None:
            return (*local, None)
        if error_local is not None:
            raise error_local
        raise ErrorIngesta("No se pudo extraer el contenido del archivo")

    try:
        productos_ia = _extraer_registros_markdown(markdown)
    except ErrorRespuestaIA as exc:
        if local is None:
            raise ErrorRespuestaIA(
                f"{error_local}; OpenRouter: {exc}" if error_local else str(exc),
                exc.respuesta_ia,
            ) from exc
        productos, errores, detalles = local
        detalles.append(f"OpenRouter: {exc}; se conservaron los datos del lector local")
        return productos, errores, detalles, exc.respuesta_ia
    except ErrorIngesta as exc:
        if local is None:
            if error_local:
                raise ErrorIngesta(f"{error_local}; OpenRouter: {exc}") from exc
            raise
        productos, errores, detalles = local
        detalles.append(f"OpenRouter: {exc}; se conservaron los datos del lector local")
        return productos, errores, detalles, None

    productos, errores, detalles, respuesta_ia = productos_ia
    if productos:
        return productos, errores, detalles, respuesta_ia
    if local is not None:
        productos_locales, errores_locales, detalles_locales = local
        detalles_locales.append(
            "OpenRouter no detecto productos; se conservaron los datos del lector local"
        )
        return productos_locales, errores_locales, detalles_locales, respuesta_ia
    if error_local:
        detalles.append(str(error_local))
    return productos, errores, detalles, respuesta_ia


def previsualizar_archivo(
    nombre: str,
    contenido: bytes,
    selecciones_precio: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Analiza un catalogo sin persistirlo y devuelve una muestra verificable."""
    try:
        nombre = _nombre_seguro(nombre)
    except ErrorIngesta as exc:
        raise ErrorIngesta(str(exc)) from exc
    extension = Path(nombre).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ErrorIngesta("Formato no permitido; use PDF, XLSX, DOCX, TXT o MD")
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise ErrorIngesta(f"El archivo supera el limite de {MAX_ARCHIVO_MB} MB")
    if not contenido:
        raise ErrorIngesta("El archivo esta vacio")
    markdown, aviso_markdown = _convertir_contenido_a_markdown(
        nombre, contenido
    )
    try:
        productos, filas_error, detalles, respuesta_ia = _extraer_con_respaldo_ia(
            nombre,
            contenido,
            markdown,
            selecciones_precio,
        )
    except SeleccionPrecioRequerida as exc:
        return {
            "productos_detectados": 0,
            "filas_error": 0,
            "filas_duplicadas": 0,
            "muestra": [],
            "detalle": str(exc),
            "seleccion_pendiente": True,
            "opciones_precio": exc.opciones,
        }
    except ErrorIngesta as error_local:
        if not markdown:
            raise ErrorIngesta(
                f"{error_local}; {aviso_markdown or AVISO_SIN_MARKDOWN}"
            ) from error_local
        raise
    productos, filas_duplicadas, errores_duplicados, detalles_duplicados = (
        _consolidar_codigos(productos)
    )
    detalles = detalles_duplicados + detalles
    aviso_descripcion = _aviso_sin_descripcion(productos)
    if aviso_descripcion:
        detalles.append(aviso_descripcion)
    if aviso_markdown and respuesta_ia is None:
        detalles.append(aviso_markdown)
    return {
        "productos_detectados": len(productos),
        "filas_error": filas_error + errores_duplicados,
        "filas_duplicadas": filas_duplicadas,
        "muestra": productos[:20],
        "detalle": _detalle(detalles),
        "seleccion_pendiente": False,
        "opciones_precio": [],
        "respuesta_ia": respuesta_ia,
    }


def procesar_archivo(
    nombre: str,
    contenido: bytes,
    id_usuario: int,
    selecciones_precio: dict[int, int] | None = None,
    metadatos: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Procesa un archivo y devuelve un resultado aislado del resto del lote."""
    try:
        nombre = _nombre_seguro(nombre)
    except ErrorIngesta as exc:
        nombre_visible = str(nombre).replace("\\", "/").rsplit("/", 1)[-1]
        return {
            "id_archivo": None,
            "nombre": nombre_visible[:255] or "archivo",
            "tipo": Path(nombre_visible).suffix.lower().lstrip(".") or "desconocido",
            "tamano_bytes": len(contenido),
            "estado": "rechazado",
            "filas_ok": 0,
            "filas_error": 0,
            "detalle": str(exc),
        }

    extension = Path(nombre).suffix.lower()
    tipo = extension.lstrip(".") or "desconocido"
    if extension not in EXTENSIONES_PERMITIDAS:
        return {
            "id_archivo": None,
            "nombre": nombre,
            "tipo": tipo,
            "tamano_bytes": len(contenido),
            "estado": "rechazado",
            "filas_ok": 0,
            "filas_error": 0,
            "detalle": "Formato no permitido; use PDF, XLSX, DOCX, TXT o MD",
        }
    if len(contenido) > MAX_ARCHIVO_BYTES:
        return {
            "id_archivo": None,
            "nombre": nombre,
            "tipo": tipo,
            "tamano_bytes": len(contenido),
            "estado": "rechazado",
            "filas_ok": 0,
            "filas_error": 0,
            "detalle": f"El archivo supera el limite de {MAX_ARCHIVO_MB} MB",
        }

    digest = hashlib.sha256(contenido).hexdigest()
    ruta, ruta_relativa = _ruta_original(nombre)
    _escribir_original(ruta, contenido)
    # RF-02.4: conserva el Markdown fuente o el texto convertido junto al
    # registro del archivo original.
    markdown, aviso_markdown = convertir_a_markdown(ruta)
    try:
        archivo = inventario_model.crear_archivo(
            nombre=nombre,
            tipo=tipo,
            ruta=ruta_relativa,
            hash_sha256=digest,
            tamano_bytes=len(contenido),
            id_usuario=id_usuario,
            metadatos=metadatos,
            contenido_markdown=markdown,
        )
    except (ErrorPostgres, BaseDeDatosNoDisponible, OSError, ValueError):
        ruta.unlink(missing_ok=True)
        raise

    id_archivo = archivo["id_archivo"]
    inventario_model.actualizar_estado_archivo(id_archivo, estado="procesando")

    if not contenido:
        detalle = "El archivo esta vacio"
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo, estado="error", filas_error=1, detalle=detalle
        )
        return dict(resultado)

    respuesta_ia: dict[str, Any] | None = None
    try:
        productos, filas_error, errores, respuesta_ia = _extraer_con_respaldo_ia(
            nombre,
            contenido,
            markdown,
            selecciones_precio,
        )
    except ErrorRespuestaIA as exc:
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=max(1, getattr(exc, "filas_error", 0)),
            detalle=str(exc)[:MAX_DETALLE],
        )
        return {**dict(resultado), "respuesta_ia": exc.respuesta_ia}
    except ArchivoSinFilasValidas as exc:
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=exc.filas_error,
            detalle=str(exc)[:MAX_DETALLE],
        )
        return dict(resultado)
    except ErrorIngesta as exc:
        detalle = str(exc)
        if aviso_markdown:
            detalle = f"{detalle}; {aviso_markdown}"
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle=detalle[:MAX_DETALLE],
        )
        return dict(resultado)
    except (
        InvalidFileException,
        PackageNotFoundError,
        ParseError,
        PdfReadError,
        zipfile.BadZipFile,
        OSError,
        ValueError,
    ) as exc:
        logger.warning("No se pudo procesar archivo de ingesta %s: %s", nombre, exc)
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle="El archivo esta danado o no tiene un formato valido",
        )
        return dict(resultado)

    if not productos:
        detalle = "OpenRouter no encontro productos verificables en el Markdown"
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle=detalle,
        )
        return {**dict(resultado), "respuesta_ia": respuesta_ia}

    productos, _, errores_duplicados, detalles_duplicados = (
        _consolidar_codigos(productos)
    )
    filas_error += errores_duplicados
    errores = detalles_duplicados + errores
    aviso_descripcion = _aviso_sin_descripcion(productos)
    if aviso_descripcion:
        errores.append(aviso_descripcion)

    try:
        filas_ok, ofertas_guardadas = inventario_model.insertar_catalogo_completo(
            id_archivo, productos, guardar_ofertas=bool(metadatos)
        )
        if metadatos:
            if ofertas_guardadas != len(productos):
                raise ValueError(
                    "No se guardaron todas las ofertas del catalogo del proveedor"
                )
    except (ErrorPostgres, BaseDeDatosNoDisponible):
        inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=max(filas_error, 1),
            detalle="No se pudieron guardar los productos y ofertas del archivo",
        )
        raise
    except ValueError as exc:
        inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=max(filas_error, 1),
            detalle=str(exc)[:MAX_DETALLE],
        )
        raise

    # Verificacion: no se declara exito si la base no contiene exactamente los
    # productos leidos. El reporte anterior contaba filas intentadas, no filas
    # guardadas, y un guardado parcial pasaba desapercibido.
    guardados = inventario_model.contar_productos_de_archivo(id_archivo)
    if guardados != len(productos):
        detalle = (
            f"Se leyeron {len(productos)} productos pero solo {guardados} "
            "quedaron guardados; el catalogo se marco con error para no "
            "trabajar con datos incompletos"
        )
        return dict(
            inventario_model.actualizar_estado_archivo(
                id_archivo,
                estado="error",
                filas_ok=guardados,
                filas_error=max(filas_error, len(productos) - guardados, 1),
                detalle=detalle[:MAX_DETALLE],
            )
        )

    filas_ok = guardados
    estado = "parcial" if filas_error else "ok"
    if aviso_markdown:
        errores.append(aviso_markdown)
    resultado = inventario_model.actualizar_estado_archivo(
        id_archivo,
        estado=estado,
        filas_ok=filas_ok,
        filas_error=filas_error,
        detalle=_detalle(errores),
    )
    return {**dict(resultado), "respuesta_ia": respuesta_ia}


def _eliminar_archivo_original(ruta_relativa: str | None) -> bool:
    """Quita el original del disco; el nombre nunca proviene del cliente.

    La ruta guardada en la base es un nombre generado con UUID. Se resuelve
    y se exige que siga siendo hijo directo de ``UPLOADS_DIR`` antes de
    borrar; cualquier otra ruta se ignora.
    """
    if not ruta_relativa or not ruta_relativa.strip():
        return False

    directorio = get_settings().uploads_dir.resolve()
    estaticos = (Path(__file__).resolve().parents[1] / "static").resolve()
    if directorio == estaticos or estaticos in directorio.parents:
        raise RuntimeError("UPLOADS_DIR no puede estar dentro del directorio de estaticos")

    try:
        ruta = (directorio / ruta_relativa).resolve()
    except (OSError, ValueError):
        logger.warning("Ruta de original invalida: %r", ruta_relativa[:255])
        return False
    if ruta.parent != directorio:
        logger.warning(
            "Ruta de original fuera de %s; no se elimina: %r",
            directorio,
            ruta_relativa[:255],
        )
        return False

    try:
        ruta.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("No se pudo eliminar el original %s: %s", ruta.name, exc)
        return False
    return True


def eliminar_catalogo_completo(id_archivo: int) -> dict[str, Any] | None:
    """Retira un catalogo del sistema, haya sido procesado o no.

    Elimina en una transaccion los productos cargados por ese archivo y su
    registro en ``archivos_subidos``; despues borra el original del disco.
    Devuelve ``None`` cuando el catalogo no existe.
    """
    resultado_base = inventario_model.eliminar_catalogo(id_archivo)
    if resultado_base is None:
        return None

    ruta_original = resultado_base.pop("ruta_original")
    return {
        "id_archivo": resultado_base["id_archivo"],
        "nombre": resultado_base["nombre"],
        "productos_eliminados": resultado_base["productos_eliminados"],
        "archivo_original_eliminado": _eliminar_archivo_original(ruta_original),
    }


def eliminar_catalogos_completos(ids_archivos: list[int]) -> dict[str, Any]:
    """Elimina catalogos existentes del lote y reporta los IDs ausentes."""
    resultado_base = inventario_model.eliminar_catalogos(ids_archivos)
    eliminados = []
    for catalogo in resultado_base["catalogos"]:
        ruta_original = catalogo.pop("ruta_original")
        eliminados.append(
            {
                **catalogo,
                "archivo_original_eliminado": _eliminar_archivo_original(
                    ruta_original
                ),
            }
        )
    return {
        "eliminados": eliminados,
        "ids_no_encontrados": resultado_base["ids_no_encontrados"],
    }
