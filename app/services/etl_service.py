"""Extraccion, normalizacion y carga de catalogos de proveedores."""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import logging
import os
import re
import time
import shutil
import subprocess
import tempfile
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from xml.etree.ElementTree import ParseError

import pymupdf
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import get_settings
from app.db.session import BaseDeDatosNoDisponible
from app.models import inventario as inventario_model
from psycopg2 import Error as ErrorPostgres

logger = logging.getLogger("ferreteria.etl")

EXTENSIONES_PERMITIDAS = frozenset({".pdf", ".xlsx", ".docx", ".txt"})
MAX_ARCHIVO_MB = 100
MAX_ARCHIVO_BYTES = MAX_ARCHIVO_MB * 1024 * 1024
MAX_ARCHIVOS_INGESTA = 20


def _limite_positivo(nombre: str, defecto: int) -> int:
    """Lee un limite entero del entorno, ignorando valores invalidos."""
    valor = os.getenv(nombre, "").strip()
    if not valor:
        return defecto
    try:
        numero = int(valor)
    except ValueError:
        return defecto
    return numero if numero > 0 else defecto


# Filas de catalogo (productos u ofertas) por archivo. Se puede ampliar por
# entorno para proveedores con listados muy extensos.
MAX_FILAS_ARCHIVO = _limite_positivo("ETL_MAX_FILAS_ARCHIVO", 20_000)
# Techo de lineas de texto que se recorren al parsear un PDF o un TXT. Un PDF
# grande produce muchas mas lineas que productos, asi que este guardavias es
# mucho mas alto que MAX_FILAS_ARCHIVO y evita rechazar catalogos validos.
MAX_LINEAS_TEXTO_ARCHIVO = _limite_positivo("ETL_MAX_LINEAS_TEXTO", 1_000_000)
MAX_PAGINAS_PDF = _limite_positivo("ETL_MAX_PAGINAS_PDF", 500)
MAX_PAGINAS_DOCX = _limite_positivo("ETL_MAX_PAGINAS_DOCX", 500)
TIEMPO_MAXIMO_PAGINACION_DOCX_SEGUNDOS = 120
MAX_ENTRADAS_ZIP = 500
MAX_DESCOMPRIMIDO_ZIP = 100 * 1024 * 1024
MAX_RAZON_COMPRESION = 100
MAX_DETALLE = 4000
MAX_ERRORES_DETALLE = 20

# La cabecera de PDF/XLSX/DOCX es obligatoria. TXT puede usar el orden indicado
# en la documentacion cuando no contiene una cabecera reconocible.
TXT_COLUMNAS_POSICIONALES = ("codigo", "nombre", "precio", "descripcion", "marca")

# Campos que todo catalogo deberia traer. La extraccion en memoria siempre
# devuelve esta forma, con ``None`` donde el archivo no trajo el dato, para que
# se pueda revisar columna por columna sin adivinar el origen de cada ficha.
CAMPOS_PRODUCTO_EXTRAIBLE = (
    "codigo",
    "nombre",
    "marca",
    "precio",
    "descuentos",
    "descripcion",
    "descuento_oferta",
    "cantidad_disponible_proveedor",
    "politica_ventas",
    "proveedor",
    "telefono",
    "correo",
    "moneda",
    "iva_oferta",
    "iva_incluido",
)

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
    "proveedor": {"proveedor", "supplier", "vendor", "distribuidor"},
    "telefono": {"telefono", "telefono_proveedor", "phone", "contacto"},
    "correo": {"correo", "correo_proveedor", "email", "e_mail", "mail"},
    "moneda": {"moneda", "currency", "divisa"},
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


class SeleccionPrecioRequerida(ErrorIngesta):
    """El catalogo tiene varias columnas de precio y requiere confirmacion."""

    def __init__(self, opciones: list[dict[str, Any]]) -> None:
        self.opciones = opciones
        super().__init__("Seleccione la columna de precio que desea importar")


@dataclass
class _PaginaPlana:
    """Datos pre-extraidos de una pagina de PDF, sin depender de pdfplumber.

    Se obtienen abriendo el PDF una sola vez con PyMuPDF (fitz). Todas las
    estrategias de extraccion consumen esta estructura, evitando las 5-7
    aperturas del archivo que ocurrian al usar pdfplumber + pypdf.
    """
    texto: str = ""
    palabras: list[dict[str, Any]] = field(default_factory=list)
    rects: list[dict[str, Any]] = field(default_factory=list)
    lines: list[dict[str, Any]] = field(default_factory=list)


def _palabras_a_texto(palabras_list: list[dict[str, Any]]) -> str:
    """Reconstruye texto plano desde palabras con posicion, agrupando por fila.

    pdfplumber hace esto internamente en ``extract_text()``: agrupa palabras
    por su posicion vertical (``top``) para formar lineas completas, y
    conserva los espacios entre columnas (multiples espacios) para que las
    estrategias de tabla (``_filas_pdf``, ``_extraer_pdf_tabla``) puedan
    detectar la separacion entre codigo, descripcion y precio.

    La heuristica de separacion: si el hueco entre dos palabras consecutivas
    supera 8 puntos tipograficos, se considera un salto de columna y se
    insertan al menos 3 espacios (``\\s{3,}``) para que los detectores de
    tabla puedan identificar las columnas.
    """
    if not palabras_list:
        return ""
    agrupadas: list[list[dict[str, Any]]] = []
    ordenadas = sorted(palabras_list, key=lambda p: (round(p["top"]), p["x0"]))
    for palabra in ordenadas:
        if agrupadas and abs(round(agrupadas[-1][0]["top"]) - round(palabra["top"])) <= 2:
            agrupadas[-1].append(palabra)
        else:
            agrupadas.append([palabra])
    SALTO_COLUMNA_PTS = 8.0
    lineas: list[str] = []
    for grupo in agrupadas:
        ordenadas_x = sorted(grupo, key=lambda x: x["x0"])
        partes: list[str] = []
        for i, palabra in enumerate(ordenadas_x):
            if i > 0:
                hueco = palabra["x0"] - ordenadas_x[i - 1]["x1"]
                if hueco > SALTO_COLUMNA_PTS:
                    partes.append("   ")  # 3+ espacios = salto de columna
                else:
                    partes.append(" ")
            partes.append(palabra["text"])
        lineas.append("".join(partes))
    return "\n".join(lineas)


def _cargar_pdf_en_paginas_planas(contenido: bytes) -> tuple[str, list[_PaginaPlana]]:
    """Abre el PDF una sola vez con PyMuPDF y extrae datos de cada pagina.

    Devuelve ``(texto_completo, lista_de_paginas)``. ``texto_completo`` se
    reconstruye agrupando palabras por posicion vertical (igual que pdfplumber),
    para que las estrategias basadas en texto (tabla, generica) funcionen
    correctamente. Cada ``_PaginaPlana`` contiene el texto, las palabras
    (formato ``{x0, top, x1, bottom, text}``) y los dibujos (rects y lines)
    de esa pagina.
    """
    try:
        doc = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception as exc:
        raise ErrorIngesta("No se pudo abrir el PDF") from exc

    if len(doc) > MAX_PAGINAS_PDF:
        doc.close()
        raise ErrorIngesta(
            f"El PDF supera el maximo de {MAX_PAGINAS_PDF} paginas"
        )

    textos_pagina: list[str] = []
    paginas: list[_PaginaPlana] = []

    for pagina_num in range(len(doc)):
        pagina = doc[pagina_num]

        # Palabras con posicion: (x0, y0, x1, y1, palabra, ...)
        palabras_raw = pagina.get_text("words") or []
        palabras_list: list[dict[str, Any]] = []
        for palabra in palabras_raw:
            x0, y0, x1, y1 = float(palabra[0]), float(palabra[1]), float(palabra[2]), float(palabra[3])
            word = str(palabra[4])
            palabras_list.append({
                "x0": x0, "top": y0, "x1": x1, "bottom": y1,
                "text": word, "width": x1 - x0, "height": y1 - y0,
            })

        # Texto plano reconstruido desde palabras (como pdfplumber)
        texto = _palabras_a_texto(palabras_list)
        textos_pagina.append(texto)

        # Dibujos: rects y lines
        rects_list: list[dict[str, Any]] = []
        lines_list: list[dict[str, Any]] = []
        for dibujo in pagina.get_drawings() or []:
            if dibujo.get("type") == "rect":
                r = dibujo["rect"]
                rects_list.append({
                    "x0": r.x0, "top": r.y0, "x1": r.x1, "bottom": r.y1,
                    "width": r.width, "height": r.height,
                })
            elif dibujo.get("type") == "line":
                puntos = dibujo.get("points")
                if puntos and len(puntos) >= 2:
                    lines_list.append({
                        "x0": puntos[0][0], "top": puntos[0][1],
                        "x1": puntos[1][0], "bottom": puntos[1][1],
                    })

        paginas.append(_PaginaPlana(
            texto=texto,
            palabras=palabras_list,
            rects=rects_list,
            lines=lines_list,
        ))

    doc.close()
    texto_completo = "\n".join(textos_pagina)
    return texto_completo, paginas


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
        if numero > MAX_LINEAS_TEXTO_ARCHIVO:
            raise ErrorIngesta(
                f"El archivo supera el maximo de {MAX_LINEAS_TEXTO_ARCHIVO} lineas de texto"
            )
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

    proveedor = _normalizar_texto(obtener("proveedor"))
    if proveedor:
        if len(proveedor) > 255:
            raise ErrorIngesta(f"Fila {numero_fila}: proveedor excede 255 caracteres")
        producto["proveedor"] = proveedor

    telefono = _normalizar_texto(obtener("telefono"))
    if telefono:
        if len(telefono) > 40:
            raise ErrorIngesta(f"Fila {numero_fila}: telefono excede 40 caracteres")
        producto["telefono"] = telefono

    correo = _normalizar_texto(obtener("correo"))
    if correo:
        if len(correo) > 255:
            raise ErrorIngesta(f"Fila {numero_fila}: correo excede 255 caracteres")
        producto["correo"] = correo

    moneda = _normalizar_texto(obtener("moneda")).upper()
    if moneda:
        if moneda not in {"USD", "VES"}:
            raise ErrorIngesta(
                f"Fila {numero_fila}: moneda invalida; use USD o VES"
            )
        producto["moneda"] = moneda

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
        if cantidad_filas_leidas > MAX_LINEAS_TEXTO_ARCHIVO:
            raise ErrorIngesta(
                f"El archivo supera el maximo de {MAX_LINEAS_TEXTO_ARCHIVO} lineas de texto"
            )
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


def _extraer_docx(
    contenido: bytes, paginas: int | None = None
) -> tuple[list[dict[str, Any]], int, list[str]]:
    _validar_paquete(contenido)
    paginas = _contar_paginas_docx(contenido) if paginas is None else paginas
    _validar_paginas_docx(paginas)
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


def _validar_paginas_docx(paginas: int) -> None:
    if paginas > MAX_PAGINAS_DOCX:
        raise ErrorIngesta(
            f"El documento Word supera el maximo de {MAX_PAGINAS_DOCX} paginas"
        )


def _contar_paginas_docx(contenido: bytes) -> int:
    """Renderiza el DOCX aislado y cuenta sus páginas PDF resultantes."""
    ejecutable = shutil.which("libreoffice") or shutil.which("soffice")
    if not ejecutable:
        raise ErrorIngesta(
            "No esta disponible el conversor de documentos Word para validar sus paginas"
        )

    try:
        with tempfile.TemporaryDirectory(prefix="fipca-docx-") as temporal:
            directorio = Path(temporal)
            entrada = directorio / "documento.docx"
            salida = directorio / "convertido"
            perfil = directorio / "perfil-libreoffice"
            salida.mkdir()
            entrada.write_bytes(contenido)
            cache = directorio / "cache"
            configuracion = directorio / "config"
            cache.mkdir()
            configuracion.mkdir()
            entorno = os.environ.copy()
            entorno.update(
                {
                    "HOME": str(directorio),
                    "XDG_CACHE_HOME": str(cache),
                    "XDG_CONFIG_HOME": str(configuracion),
                }
            )
            conversion = subprocess.run(
                [
                    ejecutable,
                    "--headless",
                    f"-env:UserInstallation={perfil.as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(salida),
                    str(entrada),
                ],
                capture_output=True,
                text=True,
                env=entorno,
                timeout=TIEMPO_MAXIMO_PAGINACION_DOCX_SEGUNDOS,
                check=False,
            )
            archivo_pdf = salida / "documento.pdf"
            if conversion.returncode != 0 or not archivo_pdf.is_file():
                logger.warning(
                    "No se pudo paginar el documento Word con LibreOffice: %s",
                    conversion.stderr.strip() or conversion.stdout.strip(),
                )
                raise ErrorIngesta(
                    "No se pudo determinar la cantidad de paginas del documento Word"
                )
            with archivo_pdf.open("rb") as archivo:
                paginas = len(PdfReader(archivo, strict=True).pages)
    except ErrorIngesta:
        raise
    except subprocess.TimeoutExpired as exc:
        raise ErrorIngesta(
            "La paginacion del documento Word excedio el tiempo permitido"
        ) from exc
    except (OSError, PdfReadError, ValueError) as exc:
        raise ErrorIngesta(
            "No se pudo determinar la cantidad de paginas del documento Word"
        ) from exc

    if paginas < 1:
        raise ErrorIngesta(
            "No se pudo determinar la cantidad de paginas del documento Word"
        )
    return paginas


def _filas_pdf(texto: str) -> list[list[str]]:
    resultado: list[list[str]] = []
    for numero, linea in enumerate(io.StringIO(texto), start=1):
        if numero > MAX_LINEAS_TEXTO_ARCHIVO:
            raise ErrorIngesta(
                f"El archivo supera el maximo de {MAX_LINEAS_TEXTO_ARCHIVO} lineas de texto"
            )
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
# Patrones de textos que claramente NO son codigos de producto sino fechas,
# telefonos o medidas que se confunden con codigos.
PATRON_NO_CODIGO_TEXTO = re.compile(
    r"^(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"   # fechas: 04-5-2026
    r"|\d{7,}$"                               # solo numeros largos: 2373580
    r"|\d+[Xx]\d+(?:[/]\d+)?$"               # medidas: 14X1/2, 7.5MX25MM
    r"|\d+[/]\d+[Xx]\d+)"                     # medidas: 1/2X14
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

# --- Catalogos en cuadros ----------------------------------------------------
# Algunos proveedores arman el catalogo como una rejilla de tarjetas dibujadas:
# cada producto es un recuadro con su descripcion, "CODIGO X", "MIN. EMP. N" y
# "Ref. precio". La rejilla real se reconstruye con los bordes verticales de la
# pagina, que a diferencia del texto no se desalinean: cada tarjeta queda
# delimitada por el borde vertical de su izquierda y el de su derecha. Leerla
# como filas de texto mezcla descripciones de tarjetas vecinas, y leerla como
# tabla con pdfplumber mezcla celdas de varias tarjetas en una sola columna.
PATRON_ETIQUETA_CODIGO = re.compile(r"^C[OÓ]DIGO$", re.IGNORECASE)
PATRON_ETIQUETA_PRECIO = re.compile(r"^Ref\.?$", re.IGNORECASE)
# Marcas de que la pagina usa el formato de cuadros. Se buscan sobre el texto
# ya extraido para no abrir el PDF con pdfplumber por segunda vez cuando el
# catalogo trae tablas o fichas normales.
PATRON_MARCA_CODIGO = re.compile(r"C[OÓ]DIGO", re.IGNORECASE)
PATRON_MARCA_CODIGO_COLUMNA = re.compile(r"C[OÓ]DIGO\s*:", re.IGNORECASE)
PATRON_MARCA_REF = re.compile(r"\bRef\s*:", re.IGNORECASE)
PATRON_MARCA_PRECIO = re.compile(r"Ref\.", re.IGNORECASE)
MINIMO_MARCAS_CUADROS = 5
LADO_MINIMO_BORDE = 20.0
ANCHO_MINIMO_TARJETA = 60.0
TOLERANCIA_BORDE_PDF = 2.0
TOLERANCIA_RENGLON_TARJETA = 3.0

# --- Catalogos de columnas sin bordes ---------------------------------------
# Muchos proveedores no dibujan la rejilla: la pagina trae bloques de texto
# alineados en columnas separadas por espacios en blanco. Dos familias:
#   * etiquetas por producto ("Ref:", "Marca:", "Precio:") en cada renglon;
#   * etiquetas de columna ("CODIGO:", "MARCA:", "MEDIDA:") bajo un titulo.
# En ambos casos la celda se reconstruye cortando el renglon por el hueco
# horizontal, porque dos productos vecinos comparten la misma linea base y
# separarlos por palabra mezcla el nombre de uno con el precio del otro.
SALTO_CELDA_PDF = 40.0
AGRUPE_RENGLON_PDF = 3
ANCHO_MAXIMO_COLUMNA_PDF = 80.0
PATRON_ETIQUETA_REF = re.compile(r"^Ref\s*:?\s*(\S+)$", re.IGNORECASE)
PATRON_ETIQUETA_PRECIO_COLUMNA = re.compile(
    r"^Precio\s*:\s*\$?\s*([\d.,]+)$", re.IGNORECASE
)
PATRON_MARCA_PRECIO_COLUMNA = re.compile(
    r"Precio\s*:\s*\$?\s*\d", re.IGNORECASE
)
PATRON_ETIQUETA_MARCA_COLUMNA = re.compile(r"^Marca\s*:\s*(.+)$", re.IGNORECASE)
PATRON_ETIQUETA_EXISTENCIA = re.compile(
    r"^Existencia\s*:?\s*(\d+)", re.IGNORECASE
)
PATRON_ETIQUETA_CODIGO_COLUMNA = re.compile(
    r"^C[oó]digo\s*:?\s*(\S*)$", re.IGNORECASE
)
PATRON_PRECIO_DOLAR = re.compile(r"^\$\s*([\d.,]+)$")
PATRON_MARCA_PRECIO_DOLAR = re.compile(r"\$\s*\d")

# --- Catalogos de tabla con precio en dolares -------------------------------
# Otro formato muy comun: cada renglon de cabecera de producto trae "COD." mas
# el codigo, debajo la descripcion repartida en varios renglones y al final una
# fila de tabla con "EMPAQUE PRECIO/UND MARCA", por ejemplo "$ 8,56 MAKITA".
# El precio y la marca se leen de esa fila; la descripcion es lo que queda
# entre el codigo y la seccion de origen/empaque.
# "COD." puede venir solo o pegado a su codigo ("COD. A-84109"); el ancla de
# columna es la palabra COD. y el inicio de bloque acepta las dos formas.
PATRON_ETIQUETA_COD_PUNTO = re.compile(r"^COD\.?$", re.IGNORECASE)
PATRON_INICIO_BLOQUE_COD = re.compile(r"^COD\.", re.IGNORECASE)
PATRON_MARCA_COD_PUNTO = re.compile(r"\bCOD\.", re.IGNORECASE)
PATRON_FIN_DESCRIPCION = re.compile(
    r"^(?:origen|importado|nacional|empaque|marca|precio)$", re.IGNORECASE
)
PATRON_PRECIO_EN_LINEA = re.compile(r"\$\s*([\d.,]+)")
PATRON_CODIGO_SUELTO = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{2,}$", re.IGNORECASE)
# Renglones que forman parte de la ficha pero no son el nombre del producto.
PATRON_RUIDO_FICHA_PDF = re.compile(
    r"^(?:ref\.?$|precio\b|marca\s*:|min\.?|cant\.?|grupo\b|existencia\b|"
    r"bulto\b|sub\s*empaque|empaque\b|medida\s*:|origen\b)",
    re.IGNORECASE,
)


def _es_codigo_pdf(valor: str) -> bool:
    """Un codigo de catalogo real: alfanumerico, con digito y sin medidas."""
    texto = valor.strip()
    if not PATRON_CODIGO_PDF.fullmatch(texto):
        return False
    # Rechazar textos que claramente no son codigos (fechas, telefonos,
    # medidas con formato 14X1/2, etc.)
    if PATRON_NO_CODIGO_TEXTO.fullmatch(texto):
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


def _es_catalogo_de_cuadros(texto: str) -> bool:
    """Decide si el PDF usa el formato de tarjetas dibujadas.

    Se cuenta sobre el texto ya extraido. Abrir el documento otra vez para
    decidirlo cuesta decenas de segundos en catalogos de cientos de paginas
    que no usan cuadros, y no aporta nada: los catalogos de tarjetas repiten
    las etiquetas "CODIGO" y "Ref." cientos de veces.
    """
    if len(PATRON_MARCA_CODIGO.findall(texto)) < MINIMO_MARCAS_CUADROS:
        return False
    return len(PATRON_MARCA_PRECIO.findall(texto)) >= MINIMO_MARCAS_CUADROS


def _es_catalogo_de_columnas(texto: str) -> bool:
    """Decide si el PDF usa columnas con etiquetas por producto (Ref:/Precio:)."""
    if len(PATRON_MARCA_REF.findall(texto)) < MINIMO_MARCAS_CUADROS:
        return False
    return (
        len(PATRON_MARCA_PRECIO_COLUMNA.findall(texto)) >= MINIMO_MARCAS_CUADROS
    )


def _es_catalogo_de_etiquetas(texto: str) -> bool:
    """Decide si el PDF usa etiquetas de columna (CODIGO:/MARCA:/MEDIDA:)."""
    if len(PATRON_MARCA_CODIGO_COLUMNA.findall(texto)) < MINIMO_MARCAS_CUADROS:
        return False
    return len(PATRON_MARCA_PRECIO_DOLAR.findall(texto)) >= MINIMO_MARCAS_CUADROS


def _pagina_en_cuadros(palabras: list[dict[str, Any]]) -> bool:
    """True si la pagina trae etiquetas de codigo y de precio."""
    etiquetas = {palabra["text"] for palabra in palabras}
    return any(PATRON_ETIQUETA_CODIGO.match(texto) for texto in etiquetas) and any(
        PATRON_ETIQUETA_PRECIO.match(texto) for texto in etiquetas
    )


def _bordes_verticales_pdf(pagina: _PaginaPlana) -> list[tuple[float, float, float]]:
    """Bordes verticales dibujados de la pagina, como (x, arriba, abajo).

    Son las lineas del recuadro de cada tarjeta. El texto se desalinea de un
    producto a otro, pero el dibujo no: por eso la rejilla se arma con ellos.

    Si no se detectan bordes dibujados (PyMuPDF puede no detectar las mismas
    lineas que pdfplumber), se intenta inferir las columnas a partir de la
    posicion de las etiquetas "C[OÓ]DIGO" en la pagina. Esto permite extraer
    catalogos como TAMBOTORCA que usan tarjetas sin bordes explicitos.
    """
    bordes: list[tuple[float, float, float]] = []
    for rect in pagina.rects:
        if rect.get("width", 0) <= 2 and rect.get("height", 0) >= LADO_MINIMO_BORDE:
            bordes.append(
                (
                    (float(rect["x0"]) + float(rect["x1"])) / 2,
                    float(rect["top"]),
                    float(rect["bottom"]),
                )
            )
    for linea in pagina.lines:
        x0, x1 = sorted((float(linea["x0"]), float(linea["x1"])))
        arriba, abajo = sorted((float(linea["top"]), float(linea["bottom"])))
        if x1 - x0 <= 2 and abajo - arriba >= LADO_MINIMO_BORDE:
            bordes.append(((x0 + x1) / 2, arriba, abajo))

    # Fallback: inferir columnas desde la posicion de etiquetas "CODIGO"
    if not bordes:
        COLUMNA_BUCKET_PTS = 20.0
        anchos_columna: dict[float, int] = {}
        for palabra in pagina.palabras:
            if PATRON_ETIQUETA_CODIGO.match(palabra["text"]):
                bucket = round(float(palabra["x0"]) / COLUMNA_BUCKET_PTS) * COLUMNA_BUCKET_PTS
                anchos_columna[bucket] = anchos_columna.get(bucket, 0) + 1
        # Filtrar por buckets con al menos 2 ocurrencias (descarta ruido)
        buckets_ordenados = sorted(
            x for x, count in anchos_columna.items() if count >= 2
        )
        if buckets_ordenados:
            # Crear bordes virtuales: borde izq al primer bucket - delta,
            # borde der al ultimo bucket + delta, y bordes entre columnas
            x_min = buckets_ordenados[0] - 10.0
            x_max = buckets_ordenados[-1] + 10.0
            bordes.append((x_min, 0.0, 900.0))
            for i in range(len(buckets_ordenados) - 1):
                x_medio = (buckets_ordenados[i] + buckets_ordenados[i + 1]) / 2
                bordes.append((x_medio, 0.0, 900.0))
            bordes.append((x_max, 0.0, 900.0))

    return bordes


def _caja_tarjeta_pdf(
    x0: float,
    x1: float,
    centro: float,
    bordes: list[tuple[float, float, float]],
) -> tuple[float, float, float, float] | None:
    """Delimita la tarjeta que contiene la etiqueta, con sus bordes vecinos."""
    izquierda = [
        borde
        for borde in bordes
        if borde[0] <= x0 + TOLERANCIA_BORDE_PDF
        and borde[1] - TOLERANCIA_BORDE_PDF
        <= centro
        <= borde[2] + TOLERANCIA_BORDE_PDF
    ]
    derecha = [
        borde
        for borde in bordes
        if borde[0] >= x1 - TOLERANCIA_BORDE_PDF
        and borde[1] - TOLERANCIA_BORDE_PDF
        <= centro
        <= borde[2] + TOLERANCIA_BORDE_PDF
    ]
    if not izquierda or not derecha:
        return None
    inicio = max(izquierda, key=lambda borde: borde[0])
    fin = min(derecha, key=lambda borde: borde[0])
    if fin[0] - inicio[0] < ANCHO_MINIMO_TARJETA:
        return None
    return (inicio[0], min(inicio[1], fin[1]), fin[0], max(inicio[2], fin[2]))


def _lineas_de_caja_pdf(
    palabras: list[dict[str, Any]],
    caja: tuple[float, float, float, float],
) -> list[list[str]]:
    """Agrupa en renglones las palabras que caen dentro de la tarjeta."""
    izquierda, arriba, derecha, abajo = caja
    dentro = [
        palabra
        for palabra in palabras
        if izquierda
        <= (float(palabra["x0"]) + float(palabra["x1"])) / 2
        <= derecha
        and arriba <= (float(palabra["top"]) + float(palabra["bottom"])) / 2 <= abajo
    ]
    dentro.sort(key=lambda palabra: (float(palabra["top"]), float(palabra["x0"])))
    renglones: list[list[Any]] = []
    for palabra in dentro:
        tope = float(palabra["top"])
        if renglones and abs(renglones[-1][0] - tope) <= TOLERANCIA_RENGLON_TARJETA:
            renglones[-1][1].append(palabra)
        else:
            renglones.append([tope, [palabra]])
    return [
        [
            str(palabra["text"])
            for palabra in sorted(grupo[1], key=lambda parte: float(parte["x0"]))
        ]
        for grupo in renglones
    ]


def _ficha_tarjeta_pdf(
    renglones: list[list[str]],
) -> tuple[str, str, str] | None:
    """Extrae (codigo, nombre, precio) de los renglones de una tarjeta.

    La descripcion es todo lo que esta antes de la etiqueta del codigo: asi el
    "MIN. EMP." de la misma tarjeta no se cuela en el nombre ni se mezcla con
    la descripcion del producto vecino.
    """
    codigo: str | None = None
    precio: str | None = None
    nombre: list[str] = []
    for tokens in renglones:
        primero = tokens[0]
        if PATRON_ETIQUETA_CODIGO.match(primero):
            if codigo is None and len(tokens) > 1:
                unido = "".join(tokens[1:])
                if _es_codigo_pdf(unido):
                    codigo = unido
                elif _es_codigo_pdf(tokens[1]):
                    codigo = tokens[1]
            continue
        if PATRON_ETIQUETA_PRECIO.match(primero):
            # El precio llega partido en dos fragmentos en muchas tarjetas
            # ("9 " + ".19"), por eso se unen sin espacios.
            if precio is None:
                precio = "".join(tokens[1:]).strip()
            continue
        if codigo is None:
            nombre.extend(tokens)
    if not codigo or not precio:
        return None
    return codigo, " ".join(nombre), precio


def _extraer_pdf_cuadros(
    paginas: list[_PaginaPlana],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae catalogos armados como tarjetas dibujadas, una ficha por recuadro.

    Cada tarjeta es un rectangulo con la descripcion arriba, "CODIGO X",
    "MIN. EMP. N" y "Ref. precio". Leerlo como texto plano mezcla los nombres
    de las tarjetas vecinas (vienen en el mismo renglon) y leerlo como tabla
    apila celdas de varias tarjetas en una columna. Aqui cada ficha se arma
    dentro de los bordes de su propio recuadro.
    """
    if not paginas:
        return [], 0, []
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    for numero_pagina, pagina in enumerate(paginas, start=1):
        try:
            fichas = _fichas_cuadros_pagina(pagina)
        except Exception as exc:
            logger.info(
                "No se pudo leer la pagina %s del PDF: %s", numero_pagina, exc
            )
            continue
        for codigo, nombre, precio in fichas:
            numero_fila = len(productos) + len(errores) + 1
            if numero_fila > MAX_FILAS_ARCHIVO:
                raise ErrorIngesta(
                    f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas"
                )
            if not nombre.strip():
                errores.append(
                    f"Fila {numero_fila}: la ficha {codigo} de la pagina "
                    f"{numero_pagina} no trae descripcion"
                )
                continue
            try:
                productos.append(
                    _producto_desde_fila(
                        [codigo, nombre, precio],
                        {"codigo": 0, "nombre": 1, "precio": 2},
                        numero_fila,
                    )
                )
            except ErrorIngesta as exc:
                errores.append(str(exc))
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _fichas_cuadros_pagina(pagina: _PaginaPlana) -> list[tuple[str, str, str]]:
    """Devuelve las fichas (codigo, nombre, precio) de una pagina de tarjetas."""
    palabras = pagina.palabras
    if not palabras or not _pagina_en_cuadros(palabras):
        return []
    bordes = _bordes_verticales_pdf(pagina)

    if bordes:
        # Ruta con bordes: delimita tarjetas por los bordes verticales
        fichas: list[tuple[str, str, str]] = []
        vistas: set[tuple[float, float, float, float]] = set()
        for palabra in palabras:
            if not PATRON_ETIQUETA_CODIGO.match(palabra["text"]):
                continue
            caja = _caja_tarjeta_pdf(
                float(palabra["x0"]),
                float(palabra["x1"]),
                (float(palabra["top"]) + float(palabra["bottom"])) / 2,
                bordes,
            )
            if caja is None or caja in vistas:
                continue
            vistas.add(caja)
            ficha = _ficha_tarjeta_pdf(_lineas_de_caja_pdf(palabras, caja))
            if ficha is not None:
                fichas.append(ficha)
        return fichas

    # Ruta sin bordes: busca CODIGO y REF en la pagina y los empareja
    # por orden de aparicion (cada CODIGO con el REF de la misma fila).
    fichas: list[tuple[str, str, str]] = []
    ordenadas = sorted(palabras, key=lambda w: (w["top"], w["x0"]))

    # Encontrar CODIGO → code, nombre
    codigo_items: list[tuple[float, str, str]] = []
    i = 0
    while i < len(ordenadas):
        w = ordenadas[i]
        if not PATRON_ETIQUETA_CODIGO.match(w["text"]):
            i += 1
            continue
        # Codigo: palabra con digitos a la derecha en la misma linea
        codigo = None
        for j in range(i + 1, min(i + 5, len(ordenadas))):
            sig = ordenadas[j]
            if abs(sig["top"] - w["top"]) > 10:
                break
            if PATRON_CODIGO_PDF.fullmatch(sig["text"]) and any(c.isdigit() for c in sig["text"]):
                codigo = sig["text"]
                break
        if not codigo:
            i += 1
            continue
        # Nombre: palabras arriba del CODIGO (misma zona x)
        nombre_parts: list[str] = []
        for j in range(i - 1, max(i - 15, -1), -1):
            ant = ordenadas[j]
            if abs(ant["x0"] - w["x0"]) > 50 or abs(ant["top"] - w["top"]) > 25:
                continue
            if PATRON_ETIQUETA_CODIGO.match(ant["text"]):
                break
            nombre_parts.insert(0, ant["text"])
        codigo_items.append((w["top"], codigo, " ".join(nombre_parts).strip()))
        i += 1

    # Encontrar REF → price
    ref_items: list[tuple[float, str]] = []
    i = 0
    while i < len(ordenadas):
        w = ordenadas[i]
        if not PATRON_ETIQUETA_PRECIO.match(w["text"]):
            i += 1
            continue
        precio = None
        for j in range(i + 1, min(i + 5, len(ordenadas))):
            sig = ordenadas[j]
            if abs(sig["top"] - w["top"]) > 10:
                break
            try:
                val = sig["text"].replace(",", ".").replace("$", "")
                float(val)
                if any(c.isdigit() for c in val) and len(val.replace(".", "")) >= 2:
                    precio = val
                    break
            except ValueError:
                continue
        if precio:
            ref_items.append((w["top"], precio))
        i += 1

    if not codigo_items or not ref_items:
        return fichas

    # Emparejar CODIGO y REF por orden: cada fila tiene N CODIGOS (uno por
    # columna) seguidos por N REF (uno por columna).
    # Agrupar por fila (top cercano)
    grupos_c = []
    for item in codigo_items:
        if not grupos_c or abs(item[0] - grupos_c[-1][0][0]) > 25:
            grupos_c.append([item])
        else:
            grupos_c[-1].append(item)

    grupos_r = []
    for item in ref_items:
        if not grupos_r or abs(item[0] - grupos_r[-1][0][0]) > 25:
            grupos_r.append([item])
        else:
            grupos_r[-1].append(item)

    for gc in grupos_c:
        # Buscar grupo REF mas cercano debajo
        c_top = gc[0][0]
        mejor_gr = None
        for gr in grupos_r:
            if gr[0][0] > c_top - 10:
                mejor_gr = gr
                break
        if not mejor_gr:
            continue
        # Emparejar dentro del grupo: 1er CODIGO con 1er REF, etc.
        gc_ord = sorted(gc, key=lambda x: x[1])
        gr_ord = sorted(mejor_gr, key=lambda x: x[1])
        for ci, (_, codigo, nombre) in enumerate(gc_ord):
            if ci < len(gr_ord):
                precio = gr_ord[ci][1]
                if codigo and precio and nombre:
                    fichas.append((codigo, nombre, precio))

    return fichas


def _agrupar_tarjetas_en_columna(
    palabras: list[dict[str, Any]],
    fichas: list[tuple[str, str, str]],
) -> None:
    """Agrupa palabras de una columna en tarjetas individuales.

    Cada tarjeta tiene esta estructura:
        [nombre del producto]  ← una o mas lineas
        CÓDIGO <codigo>       ← linea con etiqueta CODIGO
        MIN. EMP. <n>         ← opcional
        Ref. <precio>         ← linea con etiqueta Ref.

    El nombre va ANTES del CODIGO. La tarjeta se delimita desde el
    CODIGO actual hasta el siguiente CODIGO de la misma columna.
    """
    renglones_agrupados: list[list[dict[str, Any]]] = []
    for w in palabras:
        if renglones_agrupados and abs(renglones_agrupados[-1][0]["top"] - w["top"]) <= 3:
            renglones_agrupados[-1].append(w)
        else:
            renglones_agrupados.append([w])

    lineas = [
        " ".join(str(p["text"]) for p in sorted(g, key=lambda x: x["x0"]))
        for g in renglones_agrupados
    ]

    # Identificar tarjetas: buscar CODIGO -> atras para nombre, adelante para precio
    indices_codigo = [
        i for i, linea in enumerate(lineas)
        if PATRON_ETIQUETA_CODIGO.match(linea.split()[0] if linea.split() else "")
    ]

    for idx, i in enumerate(indices_codigo):
        # Codigo
        codigo_texto = _extraer_codigo_desde_renglon(lineas[i])
        # Nombre: lineas entre el CODIGO anterior y este CODIGO
        inicio_nombre = (indices_codigo[idx - 1] + 1) if idx > 0 else 0
        nombre = " ".join(lineas[inicio_nombre:i]).strip()
        # Precio: buscar "Ref." en lineas despues del CODIGO
        fin_bloque = indices_codigo[idx + 1] if idx + 1 < len(indices_codigo) else len(lineas)
        precio = None
        for j in range(i + 1, fin_bloque):
            if "Ref." in lineas[j]:
                precio = lineas[j].split("Ref.")[-1].strip().replace(",", ".")
                break
        if codigo_texto and precio and nombre:
            fichas.append((codigo_texto, nombre, precio))


def _extraer_codigo_desde_renglon(linea: str) -> str:
    """Extrae el codigo de una linea tipo 'CÓDIGO 1100029009A3'."""
    partes = linea.split()
    if len(partes) >= 2:
        return partes[-1]
    return partes[0] if partes else ""


def _agregar_tarjeta(
    codigo: str,
    renglones: list[str],
    fichas: list[tuple[str, str, str]],
) -> None:
    """Extrae nombre y precio de los renglones entre CODIGO y Ref."""
    precio: str | None = None
    nombre: list[str] = []
    for linea in renglones:
        if linea.startswith("MIN.") or linea.startswith("CANT."):
            continue
        if "Ref." in linea:
            precio = linea.split("Ref.")[-1].strip().replace(",", ".")
            continue
        nombre.append(linea.strip())
    if codigo and precio:
        nombre_str = " ".join(nombre).strip()
        if nombre_str:
            fichas.append((codigo, nombre_str, precio))


def _celdas_pagina_pdf(pagina: _PaginaPlana) -> list[tuple[float, float, str]]:
    """Divide la pagina en celdas (tope, izquierda, texto) por huecos.

    Se conserva para los formatos donde cada renglon es una sola ficha. Los
    catalogos en columnas usan ``_columnas_de_palabras_pdf``, que reparte por
    la posicion de cada palabra y no depende del ancho del hueco.
    """
    palabras = pagina.palabras
    if not palabras:
        return []
    renglones: dict[int, list[dict[str, Any]]] = {}
    for palabra in palabras:
        indice = round(float(palabra["top"]) / AGRUPE_RENGLON_PDF)
        renglones.setdefault(indice, []).append(palabra)
    celdas: list[tuple[float, float, str]] = []
    for indice in sorted(renglones):
        grupo = sorted(renglones[indice], key=lambda parte: float(parte["x0"]))
        actual = [grupo[0]]
        for palabra in grupo[1:]:
            if float(palabra["x0"]) - float(actual[-1]["x1"]) >= SALTO_CELDA_PDF:
                celdas.append(_celda_de(actual))
                actual = [palabra]
            else:
                actual.append(palabra)
        celdas.append(_celda_de(actual))
    return celdas


def _columnas_de_palabras_pdf(
    palabras: list[dict[str, Any]],
    patron_ancla: re.Pattern[str],
) -> list[list[tuple[float, float, str]]]:
    """Reparte las palabras en columnas usando la x de la etiqueta ancla.

    La etiqueta ("Ref:" o "CODIGO:") aparece en todas las columnas a la misma
    altura horizontal, asi que su x marca el inicio de cada una. Entre dos
    anclas vecinas la frontera es su punto medio, y cada palabra cae en la
    columna donde esta su centro. Asi el nombre de una tarjeta nunca se mezcla
    con el precio de la vecina, aunque el hueco entre ellas sea pequeno.
    """
    anclas = sorted(
        {
            round(float(palabra["x0"]), 1)
            for palabra in palabras
            if patron_ancla.match(str(palabra["text"]))
        }
    )
    if not anclas:
        return []
    cortes = _cortes_de_columnas_pdf(anclas)
    columnas: dict[int, list[tuple[float, float, str]]] = {}
    for palabra in palabras:
        # Se usa el borde izquierdo, no el centro: un titulo largo puede
        # invadir la columna vecina y quedaria asignado a la tarjeta equivocada.
        columnas.setdefault(_banda_de_pdf(float(palabra["x0"]), cortes), []).append(
            (float(palabra["top"]), float(palabra["x0"]), str(palabra["text"]))
        )
    return [
        sorted(columnas[banda], key=lambda parte: (parte[0], parte[1]))
        for banda in sorted(columnas)
    ]


def _renglones_de_columna_pdf(
    columna: list[tuple[float, float, str]],
) -> list[str]:
    """Agrupa la columna en renglones de texto, de arriba abajo."""
    renglones: list[list[tuple[float, float, str]]] = []
    for palabra in columna:
        if renglones and abs(renglones[-1][0][0] - palabra[0]) <= AGRUPE_RENGLON_PDF:
            renglones[-1].append(palabra)
        else:
            renglones.append([palabra])
    return [
        " ".join(parte[2] for parte in sorted(grupo, key=lambda p: p[1]))
        for grupo in renglones
    ]


def _celda_de(palabras: list[dict[str, Any]]) -> tuple[float, float, str]:
    return (
        round(float(palabras[0]["top"]), 1),
        round(float(palabras[0]["x0"]), 1),
        " ".join(str(palabra["text"]) for palabra in palabras),
    )


def _agrupar_anclas_pdf(anclas: Iterable[float]) -> list[float]:
    """Agrupa anclas casi iguales: la misma columna puede tener x con pequenas
    diferencias entre productos (238.8 y 241.1), y tomarlas como dos columnas
    partiria la tarjeta por la mitad."""
    grupos: list[list[float]] = []
    for x in sorted(set(anclas)):
        if grupos and x - grupos[-1][-1] < ANCHO_MAXIMO_COLUMNA_PDF:
            grupos[-1].append(x)
        else:
            grupos.append([x])
    return [grupo[0] for grupo in grupos]


def _cortes_de_columnas_pdf(anclas: Iterable[float]) -> list[float]:
    """Punto medio entre anclas vecinas: la frontera real de cada columna."""
    ordenadas = _agrupar_anclas_pdf(anclas)
    return [
        (izquierda + derecha) / 2
        for izquierda, derecha in zip(ordenadas, ordenadas[1:])
    ]


def _banda_de_pdf(x: float, cortes: list[float]) -> int:
    for indice, corte in enumerate(cortes):
        if x < corte:
            return indice
    return len(cortes)


def _repartir_en_columnas_pdf(
    celdas: list[tuple[float, float, str]], anclas: Iterable[float]
) -> dict[int, list[tuple[float, float, str]]]:
    """Asigna cada celda a la columna de su ancla mas cercana."""
    cortes = _cortes_de_columnas_pdf(anclas)
    columnas: dict[int, list[tuple[float, float, str]]] = {}
    for celda in sorted(celdas):
        columnas.setdefault(_banda_de_pdf(celda[1], cortes), []).append(celda)
    return columnas


def _es_ruido_ficha_pdf(texto: str) -> bool:
    return PATRON_RUIDO_FICHA_PDF.match(texto.strip()) is not None


def _fichas_columnas_pagina(pagina: _PaginaPlana) -> list[tuple[str, str, str, str | None]]:
    """Fichas de catalogos con etiquetas por producto (Ref:/Marca:/Precio:).

    Cada producto ocupa un bloque vertical de renglones dentro de su columna;
    la columna se detecta por la x del propio "Ref:", que se repite en todas.
    """
    palabras = pagina.palabras
    if not palabras:
        return []
    fichas: list[tuple[str, str, str, str | None]] = []
    for columna in _columnas_de_palabras_pdf(palabras, PATRON_ETIQUETA_REF):
        actual: dict[str, Any] | None = None
        for texto in _renglones_de_columna_pdf(columna):
            referencia = PATRON_ETIQUETA_REF.match(texto)
            if referencia:
                if actual and actual["precio"]:
                    fichas.append(_ficha_desde_bloque_pdf(actual))
                actual = {
                    "codigo": referencia.group(1),
                    "nombre": [],
                    "precio": None,
                    "marca": None,
                }
                continue
            if actual is None:
                continue
            precio = PATRON_ETIQUETA_PRECIO_COLUMNA.match(texto)
            if precio:
                if actual["precio"] is None:
                    actual["precio"] = precio.group(1)
                continue
            marca = PATRON_ETIQUETA_MARCA_COLUMNA.match(texto)
            if marca:
                if actual["marca"] is None:
                    actual["marca"] = marca.group(1).strip()
                continue
            if _es_ruido_ficha_pdf(texto):
                continue
            if actual["precio"] is None and actual["nombre"] is not None:
                actual["nombre"].append(texto)
        if actual and actual["precio"]:
            fichas.append(_ficha_desde_bloque_pdf(actual))
    return fichas


def _ficha_desde_bloque_pdf(bloque: dict[str, Any]) -> tuple[str, str, str, str | None]:
    nombre = " ".join(bloque["nombre"] or []).strip()
    return (bloque["codigo"], nombre, bloque["precio"], bloque["marca"])


def _fichas_etiquetas_pagina(
    pagina: _PaginaPlana,
) -> list[tuple[str, str, str, str | None, int | None]]:
    """Fichas de catalogos con etiquetas de columna (CODIGO:/MARCA:/MEDIDA:).

    En cada columna el bloque de un producto se arma asi: arriba el nombre y el
    precio en dolares, despues su "CODIGO:", y debajo marca, medida y
    existencia. Por eso el nombre y el precio que vienen antes de un codigo son
    los de ESE codigo, y la marca y la existencia que vienen despues tambien.
    """
    palabras = pagina.palabras
    if not palabras:
        return []
    fichas: list[tuple[str, str, str, str | None, int | None]] = []
    for columna in _columnas_de_palabras_pdf(palabras, PATRON_ETIQUETA_CODIGO_COLUMNA):
        bloque: dict[str, Any] | None = None
        nombre: list[str] = []
        precio: str | None = None
        codigo_pendiente: str | None = None
        for texto in _renglones_de_columna_pdf(columna):
            encontrado = PATRON_ETIQUETA_CODIGO_COLUMNA.match(texto)
            if encontrado:
                if bloque and bloque["precio"]:
                    fichas.append(_ficha_etiquetas_desde_bloque(bloque))
                codigo_valor = encontrado.group(1) or ""
                if codigo_valor:
                    if precio:
                        bloque = {
                            "codigo": codigo_valor,
                            "nombre": " ".join(nombre).strip(),
                            "precio": precio,
                            "marca": None,
                            "existencia": None,
                        }
                    else:
                        bloque = None
                    codigo_pendiente = None
                else:
                    # "CODIGO:" sin el codigo adjunto: viene en la sgte linea
                    codigo_pendiente = True
                    bloque = None
                nombre = []
                precio = None
                continue
            if codigo_pendiente and any(c.isdigit() for c in texto):
                codigo_pendiente = None
                if precio:
                    bloque = {
                        "codigo": texto.strip(),
                        "nombre": " ".join(nombre).strip(),
                        "precio": precio,
                        "marca": None,
                        "existencia": None,
                    }
                nombre = []
                precio = None
                continue
            dolar = PATRON_PRECIO_DOLAR.match(texto)
            if dolar:
                if precio is None:
                    precio = dolar.group(1)
                continue
            encontrada_marca = PATRON_ETIQUETA_MARCA_COLUMNA.match(texto)
            if encontrada_marca:
                if bloque and bloque["marca"] is None:
                    bloque["marca"] = encontrada_marca.group(1).strip()
                continue
            encontrada_existencia = PATRON_ETIQUETA_EXISTENCIA.match(texto)
            if encontrada_existencia:
                if bloque and bloque["existencia"] is None:
                    bloque["existencia"] = int(encontrada_existencia.group(1))
                continue
            if _es_ruido_ficha_pdf(texto):
                continue
            if precio is None:
                nombre.append(texto)
        if bloque and bloque["precio"]:
            fichas.append(_ficha_etiquetas_desde_bloque(bloque))
    return fichas


def _ficha_etiquetas_desde_bloque(
    bloque: dict[str, Any],
) -> tuple[str, str, str, str | None, int | None]:
    return (
        bloque["codigo"],
        bloque["nombre"],
        bloque["precio"],
        bloque["marca"],
        bloque["existencia"],
    )


def _fichas_tabla_dolar_pagina(pagina: _PaginaPlana) -> list[tuple[str, str, str, str | None]]:
    """Fichas de catalogos con "COD." y una fila "PRECIO / UND" en dolares.

    La descripcion va entre el codigo y la seccion de origen; el precio y la
    marca salen de la fila de la tabla ("1 UND $ 8,56 MAKITA"). La marca se
    toma como las palabras que siguen al precio, nunca como el nombre.
    """
    palabras = pagina.palabras
    if not palabras:
        return []
    fichas: list[tuple[str, str, str, str | None]] = []
    for columna in _columnas_de_palabras_pdf(palabras, PATRON_ETIQUETA_COD_PUNTO):
        bloques: list[list[str]] = []
        actual: list[str] | None = None
        for texto in _renglones_de_columna_pdf(columna):
            if PATRON_INICIO_BLOQUE_COD.match(texto):
                if actual:
                    bloques.append(actual)
                actual = [texto]
                continue
            if actual is not None:
                actual.append(texto)
        if actual:
            bloques.append(actual)
        for bloque in bloques:
            ficha = _ficha_tabla_dolar_desde_bloque(bloque)
            if ficha is not None:
                fichas.append(ficha)
    return fichas


def _ficha_tabla_dolar_desde_bloque(bloque: list[str]) -> tuple[str, str, str, str | None] | None:
    """Arma una ficha desde el bloque de renglones de un producto."""
    cabecera = bloque[0]
    # "COD. A-84109" trae el codigo en el mismo renglon. Aqui solo se cuenta
    # hasta el final de la etiqueta, para no incluir la descripcion que
    # pdfplumber pega en el mismo renglon.
    codigo = cabecera[PATRON_INICIO_BLOQUE_COD.match(cabecera).end() :].strip()
    codigo = codigo.strip(":") or None
    resto = bloque[1:]
    if codigo is None:
        # El proveedor dejo el codigo suelto en el renglon siguiente
        # ("COD." y luego "DDU115"): se toma la primera palabra con digito.
        for indice, linea in enumerate(resto):
            primera = linea.split()[0] if linea.split() else ""
            if (
                PATRON_CODIGO_SUELTO.match(primera)
                and not PATRON_FIN_DESCRIPCION.match(primera)
                and any(caracter.isdigit() for caracter in primera)
            ):
                codigo = primera
                resto = resto[:indice] + resto[indice + 1 :]
                break
    if not codigo:
        return None
    nombre: list[str] = []
    precio: str | None = None
    marca: str | None = None
    for texto in resto:
        encontrado = PATRON_PRECIO_EN_LINEA.search(texto)
        if encontrado and precio is None:
            precio = encontrado.group(1)
            sobrante = texto[encontrado.end() :].strip()
            if sobrante and not sobrante.replace(" ", "").isdigit():
                marca = sobrante
            continue
        if precio is not None:
            continue
        if PATRON_FIN_DESCRIPCION.match(texto.split()[0] if texto.split() else ""):
            continue
        if "EMPAQUE" in texto.upper() or "PRECIO / UND" in texto.upper():
            # Encabezado de la fila de tabla, no es parte del nombre.
            continue
        nombre.append(texto)
    if not precio:
        return None
    return (codigo, " ".join(nombre).strip(), precio, marca)


def _es_catalogo_de_tabla_dolar(texto: str) -> bool:
    """Decide si el PDF usa "COD." con una fila de precio en dolares."""
    if len(PATRON_MARCA_COD_PUNTO.findall(texto)) < MINIMO_MARCAS_CUADROS:
        return False
    return len(PATRON_MARCA_PRECIO_DOLAR.findall(texto)) >= MINIMO_MARCAS_CUADROS


def _extraer_pdf_tabla_dolar(
    paginas: list[_PaginaPlana],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae catalogos con "COD." y una fila "PRECIO / UND" en dolares."""
    if not paginas:
        return [], 0, []
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    for pagina in paginas:
        try:
            fichas = _fichas_tabla_dolar_pagina(pagina)
        except Exception as exc:
            logger.info("No se pudo leer una pagina del PDF: %s", exc)
            continue
        for codigo, nombre, precio, marca in fichas:
            _agregar_ficha_pdf(productos, errores, codigo, nombre, precio, marca)
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _extraer_pdf_columnas(
    paginas: list[_PaginaPlana],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae catalogos de columnas sin bordes, con etiquetas por producto."""
    if not paginas:
        return [], 0, []
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    for pagina in paginas:
        try:
            fichas = _fichas_columnas_pagina(pagina)
        except Exception as exc:
            logger.info("No se pudo leer una pagina del PDF: %s", exc)
            continue
        for codigo, nombre, precio, marca in fichas:
            _agregar_ficha_pdf(productos, errores, codigo, nombre, precio, marca)
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _extraer_pdf_etiquetas(
    paginas: list[_PaginaPlana],
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae catalogos de columnas con etiquetas CODIGO:/MARCA:/MEDIDA:."""
    if not paginas:
        return [], 0, []
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    for pagina in paginas:
        try:
            fichas = _fichas_etiquetas_pagina(pagina)
        except Exception as exc:
            logger.info("No se pudo leer una pagina del PDF: %s", exc)
            continue
        for codigo, nombre, precio, marca, existencia in fichas:
            _agregar_ficha_pdf(
                productos,
                errores,
                codigo,
                nombre,
                precio,
                marca,
                existencia=existencia,
            )
    return productos, len(errores), errores[:MAX_ERRORES_DETALLE]


def _agregar_ficha_pdf(
    productos: list[dict[str, Any]],
    errores: list[str],
    codigo: str,
    nombre: str,
    precio: str,
    marca: str | None,
    existencia: int | None = None,
) -> None:
    """Valida y agrega una ficha leida por columnas; nunca inventa el nombre."""
    numero_fila = len(productos) + len(errores) + 1
    if numero_fila > MAX_FILAS_ARCHIVO:
        raise ErrorIngesta(
            f"El archivo supera el maximo de {MAX_FILAS_ARCHIVO} filas"
        )
    if not nombre.strip():
        errores.append(
            f"Fila {numero_fila}: la ficha {codigo} no trae descripcion"
        )
        return
    fila = [codigo, nombre, precio]
    columnas = {"codigo": 0, "nombre": 1, "precio": 2}
    if marca:
        fila.append(marca)
        columnas["marca"] = 3
    if existencia is not None:
        fila.append(str(existencia))
        columnas["cantidad_disponible_proveedor"] = len(fila) - 1
    try:
        productos.append(_producto_desde_fila(fila, columnas, numero_fila))
    except ErrorIngesta as exc:
        errores.append(str(exc))


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


def _extraer_pdf_espacial(paginas: list[_PaginaPlana]) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae productos por coordenadas, admitiendo varias columnas por pagina.

    Versión adaptada a los datos planos pre-extraidos (PyMuPDF). Los fragmentos
    de cada pagina se construyen desde las palabras con posicion.
    """
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    numero_fila = 0

    for pagina in paginas:
        fragmentos: list[tuple[float, float, str]] = [
            (float(p["x0"]), float(p["top"]), str(p["text"]))
            for p in pagina.palabras
            if str(p["text"]).strip()
        ]
        if not fragmentos:
            continue
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


def _extraer_pdf_fichas(paginas: list[_PaginaPlana]) -> tuple[list[dict[str, Any]], int, list[str]]:
    productos: list[dict[str, Any]] = []
    errores: list[str] = []
    patron_codigo = re.compile(
        r"\b(?:sku|codigo|c[oó]digo|referencia)\s*:\s*([A-Z0-9][A-Z0-9._/-]{3,})",
        re.IGNORECASE,
    )
    patron_precio = re.compile(r"\bprecio\s*:\s*(.+)$", re.IGNORECASE)
    # Algunos catalogos (como CASAVEZLARA.pdf) ponen el precio como "$7.50"
    # sin la etiqueta "PRECIO:". Este patron detecta esos precios sueltos.
    patron_precio_dolar = re.compile(r"^\s*\$\s*([\d.,]+)\s*$")
    metadatos = ("politica", "cantidad", "marca", "unidad")

    for pagina in paginas:
        lineas = [
            linea.strip()
            for linea in (pagina.texto or "").splitlines()
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
                # Fallback: buscar precios con "$" ("$7.50") sin etiqueta
                precios = [
                    (pos, patron_precio_dolar.match(linea))
                    for pos, linea in enumerate(segmento)
                    if patron_precio_dolar.match(linea)
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
        # Si la estrategia no aporta ningun codigo nuevo, es una lectura
        # alternativa de las mismas filas (por ejemplo, la tabla generica sobre
        # un PDF que ya se leyo por coordenadas). Sus errores no deben marcar
        # el archivo como parcial si otra estrategia ya obtuvo esos productos.
        codigos_estrategia = {producto["codigo"] for producto in validos}
        if fichas and not (codigos_estrategia - set(fichas)):
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


def _texto_pdf_pymupdf(contenido: bytes) -> str:
    """Extrae texto plano del PDF con PyMuPDF (fitz), una sola apertura."""
    try:
        doc = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception as exc:
        raise ErrorIngesta("No se pudo leer el PDF") from exc
    if len(doc) > MAX_PAGINAS_PDF:
        doc.close()
        raise ErrorIngesta(
            f"El PDF supera el maximo de {MAX_PAGINAS_PDF} paginas"
        )
    try:
        return "\n".join(
            (pagina.get_text("text") or "") for pagina in doc
        )
    finally:
        doc.close()


def _extraer_pdf(contenido: bytes) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Extrae productos de un PDF abriendolo UNA SOLA VEZ con PyMuPDF.

    Todas las estrategias reciben los datos pre-extraidos de cada pagina
    (texto, palabras y dibujos), eliminando las 5-7 aperturas del archivo
    que ocurrian con la implementacion anterior (pdfplumber + pypdf).
    """
    texto_completo, paginas = _cargar_pdf_en_paginas_planas(contenido)
    texto = texto_completo.strip()
    if not texto:
        raise ErrorIngesta("El PDF no contiene texto legible; no se admite OCR")

    resultados: list[tuple[str, list[dict[str, Any]], int, list[str]]] = []

    # Estrategias basadas en PdfReader (ahora sobre datos planos)
    try:
        resultados.append(("espacial", *_extraer_pdf_espacial(paginas)))
    except Exception as exc:
        logger.info("La estrategia espacial no aplica a este PDF: %s", exc)
    try:
        resultados.append(("fichas", *_extraer_pdf_fichas(paginas)))
    except Exception as exc:
        logger.info("La estrategia fichas no aplica a este PDF: %s", exc)

    # Estrategia tabla (solo texto, no necesita paginas)
    resultados.append(("tabla", *_extraer_pdf_tabla(texto)))

    # Estrategias condicionales sobre datos planos
    if _es_catalogo_de_cuadros(texto):
        try:
            resultados.append(("cuadros", *_extraer_pdf_cuadros(paginas)))
        except ErrorIngesta:
            raise
        except Exception as exc:
            logger.info("La estrategia cuadros no aplica a este PDF: %s", exc)

    if _es_catalogo_de_columnas(texto):
        try:
            resultados.append(("columnas", *_extraer_pdf_columnas(paginas)))
        except ErrorIngesta:
            raise
        except Exception as exc:
            logger.info("La estrategia columnas no aplica a este PDF: %s", exc)

    if _es_catalogo_de_etiquetas(texto):
        try:
            resultados.append(("etiquetas", *_extraer_pdf_etiquetas(paginas)))
        except ErrorIngesta:
            raise
        except Exception as exc:
            logger.info("La estrategia etiquetas no aplica a este PDF: %s", exc)

    if _es_catalogo_de_tabla_dolar(texto):
        try:
            resultados.append(("tabla_dolar", *_extraer_pdf_tabla_dolar(paginas)))
        except ErrorIngesta:
            raise
        except Exception as exc:
            logger.info("La estrategia tabla_dolar no aplica a este PDF: %s", exc)

    # Estrategia generica (filas de texto)
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
            "No se encontro una tabla, fichas ni cuadros con codigo, descripcion y precio"
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


def _nombre_seguro(nombre: str) -> str:
    nombre = nombre.replace("\\", "/").rsplit("/", 1)[-1]
    nombre = "".join(caracter for caracter in nombre if caracter.isprintable())
    nombre = nombre.strip()
    if not nombre or len(nombre) > 255:
        raise ErrorIngesta("El nombre del archivo esta vacio o supera 255 caracteres")
    return nombre


def nombre_proveedor_desde_archivo(nombre_archivo: str) -> str:
    """Deriva el proveedor del nombre base del archivo, sin su extension."""
    nombre = nombre_archivo.replace("\\", "/").rsplit("/", 1)[-1]
    punto = nombre.rfind(".")
    return nombre[:punto] if punto > 0 else nombre


def _directorio_cargas_seguro() -> Path:
    """Devuelve ``UPLOADS_DIR`` resuelto y fuera del directorio de estaticos."""
    directorio = get_settings().uploads_dir.resolve()
    estaticos = (Path(__file__).resolve().parents[1] / "static").resolve()
    if directorio == estaticos or estaticos in directorio.parents:
        raise RuntimeError("UPLOADS_DIR no puede estar dentro del directorio de estaticos")
    return directorio


def _ruta_json_por_token(token: str) -> Path:
    """Devuelve la ruta del JSON de productos pre-extraidos para un token."""
    directorio = _directorio_cargas_seguro()
    return directorio / f"{token}.productos.json"


def _escribir_productos_json(ruta: Path, productos: list[dict[str, Any]]) -> None:
    """Guarda la lista de productos extraidos en un archivo JSON."""
    directorio = ruta.parent
    directorio.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(productos, archivo, ensure_ascii=False, default=str)
    except OSError:
        ruta.unlink(missing_ok=True)
        raise


def _leer_productos_json(ruta: Path) -> list[dict[str, Any]]:
    """Lee la lista de productos guardada durante la previsualizacion."""
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def _ruta_original(nombre: str) -> tuple[Path, str]:
    directorio = _directorio_cargas_seguro()
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

    No es un error de fila: el producto se guarda igual. Es un aviso de
    cobertura para que el operador sepa que esos articulos quedaran indexados
    con codigo, nombre, marca y categoria, y que la busqueda depende solo de
    esos campos.
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
    paginas_docx: int | None = None,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    extension = Path(nombre).suffix.lower()
    extractores = {
        ".pdf": _extraer_pdf,
        ".xlsx": _extraer_xlsx,
        ".docx": _extraer_docx,
        ".txt": _extraer_txt,
    }
    if extension == ".xlsx":
        return _extraer_xlsx(contenido, selecciones_precio)
    if extension == ".docx":
        return _extraer_docx(contenido, paginas_docx)
    return extractores[extension](contenido)


def previsualizar_archivo(
    nombre: str,
    contenido: bytes,
    selecciones_precio: dict[int, int] | None = None,
    ruta_json: str | None = None,
) -> dict[str, Any]:
    """Analiza un catalogo sin persistirlo y devuelve una muestra verificable.

    Si ``ruta_json`` se proporciona, la lista completa de productos (ya
    consolidada) se escribe en ese archivo para que la ingesta posterior
    no tenga que re-extraer el catalogo.
    """
    t0 = time.perf_counter()
    try:
        nombre = _nombre_seguro(nombre)
    except ErrorIngesta as exc:
        raise ErrorIngesta(str(exc)) from exc
    extension = Path(nombre).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ErrorIngesta("Formato no permitido; use PDF, XLSX, DOCX o TXT")
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise ErrorIngesta(f"El archivo supera el limite de {MAX_ARCHIVO_MB} MB")
    if not contenido:
        raise ErrorIngesta("El archivo esta vacio")
    paginas_docx = None
    if extension == ".docx":
        _validar_paquete(contenido)
        paginas_docx = _contar_paginas_docx(contenido)
        _validar_paginas_docx(paginas_docx)
    t1 = time.perf_counter()
    try:
        productos, filas_error, detalles = _extraer(
            nombre,
            contenido,
            selecciones_precio,
            paginas_docx,
        )
    except SeleccionPrecioRequerida as exc:
        t2 = time.perf_counter()
        logger.info(
            "FASE0 previsualizar nombre=%s tamano=%d validacion=%.3fs extraccion=%.3fs resultado=seleccion_pendiente",
            nombre, len(contenido), t1 - t0, t2 - t1,
        )
        return {
            "productos_detectados": 0,
            "filas_error": 0,
            "filas_duplicadas": 0,
            "muestra": [],
            "detalle": str(exc),
            "seleccion_pendiente": True,
            "opciones_precio": exc.opciones,
        }
    t2 = time.perf_counter()
    productos, filas_duplicadas, errores_duplicados, detalles_duplicados = (
        _consolidar_codigos(productos)
    )
    t3 = time.perf_counter()
    detalles = detalles_duplicados + detalles
    aviso_descripcion = _aviso_sin_descripcion(productos)
    if aviso_descripcion:
        detalles.append(aviso_descripcion)
    if ruta_json:
        try:
            _escribir_productos_json(Path(ruta_json), productos)
        except OSError as exc:
            logger.warning("No se pudo guardar JSON de previsualizacion %s: %s", ruta_json, exc)
    logger.info(
        "FASE0 previsualizar nombre=%s tamano=%d validacion=%.3fs extraccion=%.3fs consolidacion=%.3fs productos=%d",
        nombre, len(contenido), t1 - t0, t2 - t1, t3 - t2, len(productos),
    )
    return {
        "productos_detectados": len(productos),
        "filas_error": filas_error + errores_duplicados,
        "filas_duplicadas": filas_duplicadas,
        "muestra": productos[:20],
        "detalle": _detalle(detalles),
        "seleccion_pendiente": False,
        "opciones_precio": [],
    }


def extraer_catalogo_en_memoria(
    nombre: str,
    contenido: bytes,
    selecciones_precio: dict[int, int] | None = None,
) -> dict[str, Any]:
    """Extrae los productos de un archivo sin escribir en la base ni en disco.

    Es la verificacion del buscador local: sirve para comprobar que las
    librerias de Python (pypdf, pdfplumber, openpyxl y python-docx) leen bien
    el catalogo del proveedor antes de guardar nada. A diferencia de
    ``procesar_archivo`` no guarda el original en ``UPLOADS_DIR``, no crea el
    registro en ``archivos_subidos`` ni inserta productos u ofertas.

    Tampoco pagina los DOCX con LibreOffice: ese paso existe para rechazar
    documentos enormes antes de persistirlos, y aqui nada se persiste. El
    limite de filas por archivo si se sigue aplicando.
    """
    try:
        nombre = _nombre_seguro(nombre)
    except ErrorIngesta as exc:
        visible = str(nombre).replace("\\", "/").rsplit("/", 1)[-1]
        return _resultado_extraccion(
            visible[:255] or "archivo",
            Path(visible).suffix.lower().lstrip(".") or "desconocido",
            len(contenido),
            "rechazado",
            detalle=str(exc),
        )

    extension = Path(nombre).suffix.lower()
    tipo = extension.lstrip(".") or "desconocido"
    if extension not in EXTENSIONES_PERMITIDAS:
        return _resultado_extraccion(
            nombre,
            tipo,
            len(contenido),
            "rechazado",
            detalle="Formato no permitido; use PDF, XLSX, DOCX o TXT",
        )
    if len(contenido) > MAX_ARCHIVO_BYTES:
        return _resultado_extraccion(
            nombre,
            tipo,
            len(contenido),
            "rechazado",
            detalle=f"El archivo supera el limite de {MAX_ARCHIVO_MB} MB",
        )
    if not contenido:
        return _resultado_extraccion(
            nombre, tipo, 0, "error", detalle="El archivo esta vacio"
        )

    paginas_docx = None
    if extension == ".docx":
        try:
            _validar_paquete(contenido)
        except ErrorIngesta as exc:
            return _resultado_extraccion(
                nombre, tipo, len(contenido), "error", detalle=str(exc)
            )
        paginas_docx = 0

    try:
        productos, filas_error, errores = _extraer(
            nombre,
            contenido,
            selecciones_precio,
            paginas_docx,
        )
    except SeleccionPrecioRequerida as exc:
        return _resultado_extraccion(
            nombre,
            tipo,
            len(contenido),
            "pendiente",
            detalle=str(exc),
            seleccion_pendiente=True,
            opciones_precio=exc.opciones,
        )
    except ArchivoSinFilasValidas as exc:
        return _resultado_extraccion(
            nombre,
            tipo,
            len(contenido),
            "error",
            filas_error=exc.filas_error,
            detalle=str(exc),
            errores=[str(exc)],
        )
    except ErrorIngesta as exc:
        return _resultado_extraccion(
            nombre, tipo, len(contenido), "error", detalle=str(exc)
        )
    except (
        InvalidFileException,
        PackageNotFoundError,
        ParseError,
        PdfReadError,
        zipfile.BadZipFile,
        OSError,
        ValueError,
    ) as exc:
        logger.warning("No se pudo extraer archivo de prueba %s: %s", nombre, exc)
        return _resultado_extraccion(
            nombre,
            tipo,
            len(contenido),
            "error",
            detalle="El archivo esta danado o no tiene un formato valido",
        )

    productos, filas_duplicadas, errores_duplicados, detalles_duplicados = (
        _consolidar_codigos(productos)
    )
    filas_error += errores_duplicados
    errores = detalles_duplicados + errores
    aviso_descripcion = _aviso_sin_descripcion(productos)
    if aviso_descripcion:
        errores.append(aviso_descripcion)

    return _resultado_extraccion(
        nombre,
        tipo,
        len(contenido),
        "ok" if not filas_error else "parcial",
        productos=productos,
        filas_ok=len(productos),
        filas_error=filas_error,
        filas_duplicadas=filas_duplicadas,
        errores=errores,
    )


def _resultado_extraccion(
    nombre: str,
    tipo: str,
    tamano_bytes: int,
    estado: str,
    *,
    productos: Iterable[dict[str, Any]] = (),
    filas_ok: int = 0,
    filas_error: int = 0,
    filas_duplicadas: int = 0,
    detalle: str | None = None,
    errores: Iterable[str] = (),
    seleccion_pendiente: bool = False,
    opciones_precio: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Arma la respuesta de ``extraer_catalogo_en_memoria``.

    Los campos que el archivo no traia se dejan en ``None`` para que el JSON
    conserve siempre la misma forma y se pueda revisar columna por columna.
    """
    lista_errores = list(errores)
    return {
        "nombre": nombre,
        "tipo": tipo,
        "tamano_bytes": tamano_bytes,
        "estado": estado,
        "productos": [
            {campo: producto.get(campo) for campo in CAMPOS_PRODUCTO_EXTRAIBLE}
            for producto in productos
        ],
        "filas_ok": filas_ok,
        "filas_error": filas_error,
        "filas_duplicadas": filas_duplicadas,
        "detalle": _detalle(lista_errores) if lista_errores else detalle,
        "seleccion_pendiente": seleccion_pendiente,
        "opciones_precio": opciones_precio or [],
    }


def procesar_archivo(
    nombre: str,
    contenido: bytes,
    id_usuario: int,
    selecciones_precio: dict[int, int] | None = None,
    metadatos: dict[str, Any] | None = None,
    productos_pre_extraidos: list[dict[str, Any]] | None = None,
    id_archivo_existente: int | None = None,
) -> dict[str, Any]:
    """Procesa un archivo y devuelve un resultado aislado del resto del lote.

    Cuando ``productos_pre_extraidos`` se pasa (desde una previsualizacion
    guardada), se salta toda la fase de extraccion y consolidacion y se
    va directo a la insercion. En ese caso ``id_archivo_existente`` debe
    proporcionarse y ``contenido`` puede ser vacio.
    """
    t0 = time.perf_counter()

    # ── Rama productos pre-extraidos (ingesta diferida) ──────────────
    if productos_pre_extraidos is not None:
        assert id_archivo_existente is not None
        id_archivo = id_archivo_existente
        t_ahora = time.perf_counter()
        productos = productos_pre_extraidos
        filas_error = 0
        errores: list[str] = []
        logger.info(
            "FASE1 procesar_archivo pre-extraido id_archivo=%d productos=%d",
            id_archivo, len(productos),
        )
        return _insertar_y_verificar(
            id_archivo, "(pre-extraido)", productos, filas_error, errores,
            metadatos, t0, t_ahora, t_ahora, t_ahora,
        )

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
            "detalle": "Formato no permitido; use PDF, XLSX, DOCX o TXT",
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

    paginas_docx = None
    error_paginas_docx = None
    if extension == ".docx" and contenido:
        try:
            _validar_paquete(contenido)
            paginas_docx = _contar_paginas_docx(contenido)
            _validar_paginas_docx(paginas_docx)
        except ErrorIngesta as exc:
            error_paginas_docx = exc

    digest = hashlib.sha256(contenido).hexdigest()
    ruta, ruta_relativa = _ruta_original(nombre)
    _escribir_original(ruta, contenido)
    t1 = time.perf_counter()
    try:
        archivo = inventario_model.crear_archivo(
            nombre=nombre,
            tipo=tipo,
            ruta=ruta_relativa,
            hash_sha256=digest,
            tamano_bytes=len(contenido),
            id_usuario=id_usuario,
            metadatos=metadatos,
        )
    except (ErrorPostgres, BaseDeDatosNoDisponible, OSError, ValueError):
        ruta.unlink(missing_ok=True)
        raise

    id_archivo = archivo["id_archivo"]
    if error_paginas_docx:
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle=str(error_paginas_docx)[:MAX_DETALLE],
        )
        return dict(resultado)

    inventario_model.actualizar_estado_archivo(id_archivo, estado="procesando")

    if not contenido:
        detalle = "El archivo esta vacio"
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo, estado="error", filas_error=1, detalle=detalle
        )
        return dict(resultado)

    t2 = time.perf_counter()
    try:
        productos, filas_error, errores = _extraer(
            nombre,
            contenido,
            selecciones_precio,
            paginas_docx,
        )
    except ArchivoSinFilasValidas as exc:
        t3 = time.perf_counter()
        logger.info(
            "FASE0 procesar nombre=%s tamano=%d setup=%.3fs extraccion=%.3fs resultado=sin_filas",
            nombre, len(contenido), t2 - t0, t3 - t2,
        )
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=exc.filas_error,
            detalle=str(exc)[:MAX_DETALLE],
        )
        return dict(resultado)
    except ErrorIngesta as exc:
        t3 = time.perf_counter()
        logger.info(
            "FASE0 procesar nombre=%s tamano=%d setup=%.3fs extraccion=%.3fs resultado=error_ingesta",
            nombre, len(contenido), t2 - t0, t3 - t2,
        )
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle=str(exc)[:MAX_DETALLE],
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
        t3 = time.perf_counter()
        logger.info(
            "FASE0 procesar nombre=%s tamano=%d setup=%.3fs extraccion=%.3fs resultado=error_formato",
            nombre, len(contenido), t2 - t0, t3 - t2,
        )
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle="El archivo esta danado o no tiene un formato valido",
        )
        return dict(resultado)

    t3 = time.perf_counter()
    if not productos:
        t3 = time.perf_counter()
        logger.info(
            "FASE0 procesar nombre=%s tamano=%d setup=%.3fs extraccion=%.3fs resultado=sin_productos",
            nombre, len(contenido), t2 - t0, t3 - t2,
        )
        resultado = inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=1,
            detalle=(
                "El archivo no contiene productos verificables; revise las "
                "columnas o use la plantilla estandar"
            )[:MAX_DETALLE],
        )
        return dict(resultado)

    productos, _, errores_duplicados, detalles_duplicados = (
        _consolidar_codigos(productos)
    )
    t4 = time.perf_counter()
    filas_error += errores_duplicados
    errores = detalles_duplicados + errores
    aviso_descripcion = _aviso_sin_descripcion(productos)
    if aviso_descripcion:
        errores.append(aviso_descripcion)

    return _insertar_y_verificar(
        id_archivo, nombre, productos, filas_error, errores, metadatos,
        t0, t2, t3, t4,
    )


def _insertar_y_verificar(
    id_archivo: int,
    nombre: str,
    productos: list[dict[str, Any]],
    filas_error: int,
    errores: list[str],
    metadatos: dict[str, Any] | None,
    t0: float,
    t2: float,
    t3: float,
    t4: float,
) -> dict[str, Any]:
    """Inserta productos en DB, verifica el conteo y actualiza estado.

    Es la etapa comun entre el flujo normal (extraccion + consolidacion) y
    el flujo de ingesta diferida (productos pre-extraidos desde JSON).
    """
    t_nombre = nombre or "(pre-extraido)"
    t5 = time.perf_counter()
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
        t6 = time.perf_counter()
        logger.info(
            "FASE1 insertar nombre=%s extraccion=%.3fs consolidacion=%.3fs insercion=%.3fs resultado=error_db",
            t_nombre, t3 - t2, t4 - t3, t6 - t5,
        )
        inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=max(filas_error, 1),
            detalle="No se pudieron guardar los productos y ofertas del archivo",
        )
        raise
    except ValueError as exc:
        t6 = time.perf_counter()
        logger.info(
            "FASE1 insertar nombre=%s extraccion=%.3fs consolidacion=%.3fs insercion=%.3fs resultado=error_ofertas",
            t_nombre, t3 - t2, t4 - t3, t6 - t5,
        )
        inventario_model.actualizar_estado_archivo(
            id_archivo,
            estado="error",
            filas_error=max(filas_error, 1),
            detalle=str(exc)[:MAX_DETALLE],
        )
        raise

    t6 = time.perf_counter()
    guardados = inventario_model.contar_productos_de_archivo(id_archivo)
    t7 = time.perf_counter()
    if guardados != len(productos):
        logger.info(
            "FASE1 insertar nombre=%s extraccion=%.3fs consolidacion=%.3fs insercion=%.3fs verificacion=%.3fs resultado=conteo_erroneo esperados=%d guardados=%d",
            t_nombre, t3 - t2, t4 - t3, t6 - t5, t7 - t6,
            len(productos), guardados,
        )
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
    resultado = inventario_model.actualizar_estado_archivo(
        id_archivo,
        estado=estado,
        filas_ok=filas_ok,
        filas_error=filas_error,
        detalle=_detalle(errores),
    )
    logger.info(
        "FASE1 insertar nombre=%s tamano=%d extraccion=%.3fs consolidacion=%.3fs insercion=%.3fs verificacion=%.3fs total=%.3fs productos=%d estado=%s",
        t_nombre, len(productos), t3 - t2, t4 - t3, t6 - t5, t7 - t6,
        t7 - t0, len(productos), estado,
    )
    return dict(resultado)


def _eliminar_archivo_original(ruta_relativa: str | None) -> bool:
    """Quita el original del disco; el nombre nunca proviene del cliente.

    La ruta guardada en la base es un nombre generado con UUID. Se resuelve
    y se exige que siga siendo hijo directo de ``UPLOADS_DIR`` antes de
    borrar; cualquier otra ruta se ignora.
    """
    if not ruta_relativa or not ruta_relativa.strip():
        return False

    try:
        directorio = _directorio_cargas_seguro()
    except RuntimeError as exc:
        logger.warning("No se elimina el original: %s", exc)
        return False

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
    archivo_original_eliminado = _eliminar_archivo_original(ruta_original)
    return {
        "id_archivo": resultado_base["id_archivo"],
        "nombre": resultado_base["nombre"],
        "productos_eliminados": resultado_base["productos_eliminados"],
        "archivo_original_eliminado": archivo_original_eliminado,
    }


def eliminar_catalogos_completos(ids_archivos: list[int]) -> dict[str, Any]:
    """Elimina catalogos existentes del lote y reporta los IDs ausentes."""
    resultado_base = inventario_model.eliminar_catalogos(ids_archivos)
    eliminados = []
    for catalogo in resultado_base["catalogos"]:
        ruta_original = catalogo.pop("ruta_original")
        archivo_original_eliminado = _eliminar_archivo_original(ruta_original)
        eliminados.append(
            {
                **catalogo,
                "archivo_original_eliminado": archivo_original_eliminado,
            }
        )
    return {
        "eliminados": eliminados,
        "ids_no_encontrados": resultado_base["ids_no_encontrados"],
    }
