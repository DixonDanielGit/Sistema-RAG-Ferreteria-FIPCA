"""Pruebas unitarias de extraccion, normalizacion y persistencia ETL."""

from __future__ import annotations

import hashlib
import io
import subprocess
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest
from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter

from app.config import get_settings
from app.models import inventario as inventario_model
from app.services import etl_service


def test_limite_de_paginas_pdf_es_de_500():
    assert etl_service.MAX_PAGINAS_PDF == 500


def test_limite_de_paginas_docx_acepta_500():
    assert etl_service.MAX_PAGINAS_DOCX == 500
    etl_service._validar_paginas_docx(500)


@pytest.mark.parametrize(
    ("cantidad_paginas", "mensaje"),
    [
        (500, "no contiene texto legible"),
        (501, "maximo de 500 paginas"),
    ],
)
def test_pdf_aplica_limite_de_500_paginas(cantidad_paginas, mensaje):
    escritor = PdfWriter()
    for _ in range(cantidad_paginas):
        escritor.add_blank_page(width=100, height=100)
    contenido = io.BytesIO()
    escritor.write(contenido)

    with pytest.raises(etl_service.ErrorIngesta, match=mensaje):
        etl_service._extraer_pdf(contenido.getvalue())


def _bytes_excel(filas):
    libro = Workbook()
    hoja = libro.active
    for fila in filas:
        hoja.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _bytes_word(filas):
    documento = Document()
    tabla = documento.add_table(rows=0, cols=len(filas[0]))
    for fila in filas:
        celdas = tabla.add_row().cells
        for celda, valor in zip(celdas, fila):
            celda.text = str(valor)
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()


def test_txt_normaliza_cabecera_y_precio_venezolano():
    contenido = (
        "Código;Nombre;Precio;Marca;Descripción\n"
        "SKU-01;Martillo;1.234,50;FIPCA;Acero\n"
    ).encode()

    productos, errores, detalles = etl_service._extraer_txt(contenido)

    assert errores == 0
    assert detalles == []
    assert productos == [
        {
            "codigo": "SKU-01",
            "nombre": "Martillo",
            "marca": "FIPCA",
            "precio": Decimal("1234.50"),
            "descuentos": Decimal("0.00"),
            "descripcion": "Acero",
        }
    ]


def test_txt_acepta_orden_posicional_documentado():
    productos, errores, _ = etl_service._extraer_txt(
        b"SKU-01;Martillo;12,50;Acero;FIPCA\n"
    )

    assert errores == 0
    assert productos[0]["codigo"] == "SKU-01"
    assert productos[0]["descripcion"] == "Acero"
    assert productos[0]["marca"] == "FIPCA"
    assert productos[0]["precio"] == Decimal("12.50")


def test_txt_posicional_con_comas_ambiguas_se_rechaza():
    with pytest.raises(etl_service.ErrorIngesta, match="punto y coma"):
        etl_service._extraer_txt(b"SKU-1,Martillo,1,25\n")


def test_txt_extrae_proveedor_contacto_y_moneda_de_la_fila():
    contenido = (
        "codigo;nombre;precio;proveedor;telefono;correo;moneda\n"
        "SKU-77;Taladro;99,90;Ferretería Central;0414-1234567;"
        "ventas@central.com;VES\n"
    ).encode("utf-8")

    productos, errores, _ = etl_service._extraer_txt(contenido)

    assert errores == 0
    assert productos[0]["proveedor"] == "Ferretería Central"
    assert productos[0]["telefono"] == "0414-1234567"
    assert productos[0]["correo"] == "ventas@central.com"
    assert productos[0]["moneda"] == "VES"


def test_txt_rechaza_moneda_no_soportada():
    with pytest.raises(etl_service.ErrorIngesta, match="moneda invalida"):
        etl_service._extraer_txt(
            b"codigo;nombre;precio;moneda\nSKU-1;Martillo;1,00;EUR\n"
        )


def test_pdf_usa_pdfplumber_para_extraer_texto_local(monkeypatch):
    class Pagina:
        def extract_text(self):
            return "Código Producto Precio\nSKU-8 Martillo 2,50"

    class Documento:
        pages = [Pagina()]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(
        etl_service.pdfplumber,
        "open",
        lambda *_args, **_kwargs: Documento(),
    )

    productos, errores, _ = etl_service._extraer_pdf(b"%PDF-1.4 local")

    assert errores == 0
    assert productos[0]["codigo"] == "SKU-8"
    assert productos[0]["precio"] == Decimal("2.50")


def test_pdf_corrupto_se_rechaza_sin_intentar_adivinar():
    with pytest.raises(etl_service.ErrorIngesta, match="PDF"):
        etl_service._extraer_pdf(b"no es un pdf")


def test_txt_informa_filas_invalidas_sin_perder_las_validas():
    contenido = b"codigo;nombre;precio\nA1;Martillo;12,50\nA2;Clavo;-1\n"

    productos, errores, detalles = etl_service._extraer_txt(contenido)

    assert len(productos) == 1
    assert errores == 1
    assert "Fila 3" in detalles[0]


def test_normaliza_codigo_y_espacios_de_producto():
    productos, _, _ = etl_service._extraer_txt(
        b"codigo;nombre;precio;descripcion\nsku-01;  Llave   ajustable ;2,50; acero   inoxidable \n"
    )

    assert productos[0]["codigo"] == "SKU-01"
    assert productos[0]["nombre"] == "Llave ajustable"
    assert productos[0]["descripcion"] == "acero inoxidable"


def test_archivo_valido_guarda_original_y_resultado_con_uuid(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "cargas"))
    get_settings.cache_clear()
    contenido = b"codigo;nombre;precio\nSKU-31;Pinza;3.25\n"
    creado = {
        "id_archivo": 31,
        "nombre": "catalogo.txt",
        "tipo": "txt",
        "tamano_bytes": len(contenido),
    }
    estados = []
    productos_insertados = []
    datos_archivo = {}

    def crear(**valores):
        datos_archivo.update(valores)
        return creado

    def actualizar(id_archivo, **campos):
        estados.append((id_archivo, campos))
        return {
            **creado,
            "estado": campos["estado"],
            "filas_ok": campos.get("filas_ok", 0),
            "filas_error": campos.get("filas_error", 0),
            "detalle": campos.get("detalle"),
        }

    monkeypatch.setattr(inventario_model, "crear_archivo", crear)
    monkeypatch.setattr(inventario_model, "actualizar_estado_archivo", actualizar)
    ofertas_insertadas = []

    def guardar_catalogo(id_archivo, productos, *, guardar_ofertas):
        productos_insertados.extend(productos)
        if guardar_ofertas:
            ofertas_insertadas.extend(productos)
        return len(productos), len(productos) if guardar_ofertas else 0

    monkeypatch.setattr(
        inventario_model, "insertar_catalogo_completo", guardar_catalogo
    )
    monkeypatch.setattr(
        inventario_model, "contar_productos_de_archivo", lambda id_archivo: 1
    )
    metadatos = {
        "proveedor": "Proveedor GAC",
        "vendedor": "Vendedora",
        "moneda": "USD",
        "nota_proveedor": "Descuento hasta mañana",
    }
    try:
        resultado = etl_service.procesar_archivo(
            r"C:\proveedores\catalogo.txt", contenido, 7, metadatos=metadatos
        )
    finally:
        get_settings.cache_clear()

    directorio = tmp_path / "cargas"
    original = list(directorio.glob("*.txt"))
    assert resultado["estado"] == "ok"
    assert resultado["filas_ok"] == 1
    assert len(original) == 1
    assert original[0].name != "catalogo.txt"
    assert original[0].read_bytes() == contenido
    assert datos_archivo["ruta"] == original[0].name
    assert datos_archivo["hash_sha256"] == hashlib.sha256(contenido).hexdigest()
    assert datos_archivo["metadatos"] == metadatos
    assert productos_insertados[0]["codigo"] == "SKU-31"
    assert ofertas_insertadas[0]["codigo"] == "SKU-31"
    assert estados[0][1]["estado"] == "procesando"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("$ 1,234.56", Decimal("1234.56")),
        ("Bs. 1.234,56", Decimal("1234.56")),
        ("0", Decimal("0.00")),
    ],
)
def test_normaliza_formatos_de_precio(valor, esperado):
    assert etl_service._leer_precio(valor) == esperado


@pytest.mark.parametrize("valor", ["", "-1", "1.2.3", "(1,00)", "NaN"])
def test_rechaza_precios_invalidos_o_negativos(valor):
    with pytest.raises(etl_service.ErrorIngesta):
        etl_service._leer_precio(valor)


def test_excel_extrae_tabla_con_cabecera():
    contenido = _bytes_excel(
        [
            ["Código", "Producto", "Precio", "Marca"],
            ["SKU-02", "Taladro", 19.95, "FIPCA"],
        ]
    )

    productos, errores, _ = etl_service._extraer_xlsx(contenido)

    assert errores == 0
    assert productos[0]["codigo"] == "SKU-02"
    assert productos[0]["precio"] == Decimal("19.95")


def test_excel_guarda_metadatos_comerciales_de_la_oferta():
    contenido = _bytes_excel(
        [
            [
                "SKU",
                "Nombre",
                "Precio",
                "Cantidad Disp.",
                "Política ventas",
                "IVA",
                "IVA incluido",
                "Descuento",
            ],
            [
                "SKU-IVA-1",
                "Abrazadera",
                10.61,
                43,
                "Descuento hasta mañana",
                "16%",
                "Sí",
                1.25,
            ],
        ]
    )

    productos, errores, _ = etl_service._extraer_xlsx(contenido)

    assert errores == 0
    assert productos[0]["cantidad_disponible_proveedor"] == 43
    assert productos[0]["politica_ventas"] == "Descuento hasta mañana"
    assert productos[0]["iva_oferta"] == Decimal("16.00")
    assert productos[0]["iva_incluido"] is True
    assert productos[0]["descuento_oferta"] == Decimal("1.25")


def test_excel_omite_hoja_sin_catalogo_y_lee_la_hoja_siguiente():
    libro = Workbook()
    libro.active.title = "Instrucciones"
    libro.active.append(["Lista de precios"])
    hoja = libro.create_sheet("Catalogo")
    hoja.append(["SKU", "Nombre", "PVP"])
    hoja.append(["SKU-03", "Llave", 5])
    salida = io.BytesIO()
    libro.save(salida)

    productos, errores, _ = etl_service._extraer_xlsx(salida.getvalue())

    assert errores == 0
    assert [producto["codigo"] for producto in productos] == ["SKU-03"]


def test_excel_exige_elegir_entre_varias_columnas_de_precio():
    contenido = _bytes_excel(
        [
            ["Código", "Descripción", "Precio neto", "PVP"],
            ["SKU-21", "Tubo PVC", 3.5, 4.06],
        ]
    )

    with pytest.raises(etl_service.SeleccionPrecioRequerida) as error:
        etl_service._extraer_xlsx(contenido)

    assert [opcion["columna"] for opcion in error.value.opciones] == [
        "Precio neto",
        "PVP",
    ]
    vista = etl_service.previsualizar_archivo(
        "catalogo.xlsx", contenido, {0: 3}
    )
    assert vista["productos_detectados"] == 1
    assert vista["muestra"][0]["precio"] == Decimal("4.06")


def test_excel_detecta_cabecera_de_precio_en_filas_superiores():
    contenido = _bytes_excel(
        [
            [None, None, None, None, "Precio neto"],
            ["Código", "Descripción", "Unidad", None, None],
            ["SKU-22", "Cinta aislante", "Pieza", None, 2.75],
        ]
    )

    productos, errores, _ = etl_service._extraer_xlsx(contenido)

    assert errores == 0
    assert productos[0]["codigo"] == "SKU-22"
    assert productos[0]["nombre"] == "Cinta aislante"
    assert productos[0]["precio"] == Decimal("2.75")


def test_excel_infiere_codigo_producto_y_precio_de_hoja_posicional():
    contenido = _bytes_excel(
        [
            [None, None, None, "Peso", "Pza/Atado", "Bs. F/Pza."],
            [5, "10102006", "LAMINAS DE H.N. 3.00 x 1200", 69.12, 35, 584],
            [None, "10302008", "ANGULO 50 x 50 x 4.00", 18.36, 54, 220],
        ]
    )

    productos, errores, _ = etl_service._extraer_xlsx(contenido)

    assert errores == 0
    assert [producto["codigo"] for producto in productos] == [
        "10102006",
        "10302008",
    ]
    assert [producto["precio"] for producto in productos] == [
        Decimal("584.00"),
        Decimal("220.00"),
    ]


def test_docx_extrae_tabla_con_cabecera(monkeypatch):
    contenido = _bytes_word(
        [["Referencia", "Artículo", "Precio"], ["SKU-04", "Destornillador", "7,25"]]
    )
    monkeypatch.setattr(etl_service, "_contar_paginas_docx", lambda _: 1)
    productos, errores, _ = etl_service._extraer_docx(contenido)

    assert errores == 0
    assert productos[0]["codigo"] == "SKU-04"
    assert productos[0]["precio"] == Decimal("7.25")


def test_docx_cuenta_paginas_renderizadas_con_libreoffice(monkeypatch):
    escritor = PdfWriter()
    escritor.add_blank_page(width=100, height=100)
    escritor.add_blank_page(width=100, height=100)
    pdf = io.BytesIO()
    escritor.write(pdf)
    monkeypatch.setattr(etl_service.shutil, "which", lambda _: "libreoffice")

    def convertir(comando, **opciones):
        directorio = Path(comando[comando.index("--outdir") + 1])
        (directorio / "documento.pdf").write_bytes(pdf.getvalue())
        assert "--headless" in comando
        assert opciones["timeout"] == (
            etl_service.TIEMPO_MAXIMO_PAGINACION_DOCX_SEGUNDOS
        )
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(etl_service.subprocess, "run", convertir)

    assert etl_service._contar_paginas_docx(b"documento word") == 2


def test_docx_rechaza_mas_de_500_paginas(monkeypatch):
    monkeypatch.setattr(etl_service, "_contar_paginas_docx", lambda _: 501)
    filas = [
        ["Referencia", "Artículo", "Precio"],
        ["SKU-04", "Destornillador", "7,25"],
    ]

    with pytest.raises(etl_service.ErrorIngesta, match="maximo de 500 paginas"):
        etl_service._extraer_docx(_bytes_word(filas))


def test_word_extrae_fichas_con_campos_etiquetados():
    texto = (
        "SKU: MAR-01\nProducto: Llave ajustable\nPrecio: $ 5,25\n"
        "SKU: MAR-02\nDescripción: Martillo de uña\nPrecio: 8,50\nMarca: FIPCA"
    )

    productos, errores, detalles = etl_service._extraer_fichas_etiquetadas(texto)

    assert errores == 0
    assert detalles == []
    assert [producto["codigo"] for producto in productos] == ["MAR-01", "MAR-02"]
    assert [producto["precio"] for producto in productos] == [
        Decimal("5.25"),
        Decimal("8.50"),
    ]


def test_pdf_sin_capa_de_texto_se_rechaza():
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    salida = io.BytesIO()
    escritor.write(salida)

    with pytest.raises(etl_service.ErrorIngesta, match="no contiene texto"):
        etl_service._extraer_pdf(salida.getvalue())


def test_pdf_extrae_filas_con_cabecera_y_nombres_compuestos(monkeypatch):
    class Pagina:
        def extract_text(self):
            return "Código Producto Precio\nSKU-1 Martillo acero 2,50"

    class Lector:
        pages = [Pagina()]

    monkeypatch.setattr(etl_service, "PdfReader", lambda *_args, **_kwargs: Lector())

    productos, errores, _ = etl_service._extraer_pdf(b"pdf de prueba")

    assert errores == 0
    assert productos[0]["codigo"] == "SKU-1"
    assert productos[0]["nombre"] == "Martillo acero"
    assert productos[0]["precio"] == Decimal("2.50")


def test_pdf_extrae_tabla_con_codigo_descripcion_y_precio_al_final():
    productos, errores, _ = etl_service._extraer_pdf_tabla(
        "IMAGEN CODIGO DESCRIPCION PRECIO\n"
        'E0600000035 ABRAZADERA EMT 1/2"                0,12\n'
        'E0600000036 ABRAZADERA EMT 3/4"                0,12'
    )

    assert errores == 0
    assert len(productos) == 2
    assert productos[0]["codigo"] == "E0600000035"
    assert productos[0]["nombre"] == 'ABRAZADERA EMT 1/2"'
    assert productos[0]["precio"] == Decimal("0.12")


def test_pdf_extrae_ficha_de_producto_con_precio_y_sku():
    class Pagina:
        def extract_text(self):
            return (
                "Abrazadera de riego 90mm x 1-1/2\n"
                "Precio: $ 10,61\nSKU: G0800000197\n"
                "Política ventas: descuento especial valido\n"
                "Cantidad Disp.: 43\nDescuento: $ 1,00\n"
                "IVA 16% incluido\nMarca: Imp"
            )

    productos, errores, _ = etl_service._extraer_pdf_fichas(
        type("Lector", (), {"pages": [Pagina()]})()
    )

    assert errores == 0
    assert productos[0]["codigo"] == "G0800000197"
    assert productos[0]["nombre"] == "Abrazadera de riego 90mm x 1-1/2"
    assert productos[0]["precio"] == Decimal("10.61")
    assert productos[0]["cantidad_disponible_proveedor"] == 43
    assert productos[0]["politica_ventas"] == "descuento especial valido"
    assert productos[0]["descuento_oferta"] == Decimal("1.00")
    assert productos[0]["iva_oferta"] == Decimal("16.00")
    assert productos[0]["iva_incluido"] is True


def test_pdf_no_inventa_si_el_iva_esta_incluido():
    class Pagina:
        def extract_text(self):
            return "Martillo\nPrecio: $ 5,00\nSKU: M-01"

    productos, errores, _ = etl_service._extraer_pdf_fichas(
        type("Lector", (), {"pages": [Pagina()]})()
    )

    assert errores == 0
    assert productos[0].get("iva_incluido") is None


def test_pdf_detecta_iva_expresamente_no_incluido():
    class Pagina:
        def extract_text(self):
            return "Martillo\nPrecio: $ 5,00\nSKU: M-02\nIVA no incluido"

    productos, errores, _ = etl_service._extraer_pdf_fichas(
        type("Lector", (), {"pages": [Pagina()]})()
    )

    assert errores == 0
    assert productos[0]["iva_incluido"] is False


def test_pdf_agrupa_codigo_descripcion_y_precio_por_posicion():
    class Caja:
        width = 612

    class Pagina:
        mediabox = Caja()

        def extract_text(self, visitor_text):
            for x, texto in (
                (32, "M1660"),
                (180, 'MANGUERA RIEGO 60 PSI 3/8"'),
                (513, "16,12"),
            ):
                visitor_text(
                    texto, None, [1, 0, 0, 1, x, 431.9], None, 12
                )

    productos, errores, _ = etl_service._extraer_pdf_espacial(
        type("Lector", (), {"pages": [Pagina()]})()
    )

    assert errores == 0
    assert productos[0]["codigo"] == "M1660"
    assert productos[0]["precio"] == Decimal("16.12")


def test_pdf_espacial_lee_dos_columnas_por_linea_sin_mezclarlas():
    class Caja:
        width = 595.2

    class Pagina:
        mediabox = Caja()

        def extract_text(self, visitor_text):
            # Una sola linea visual con dos productos: antes se guardaba uno
            # solo, con el nombre de una columna y el precio de la otra.
            for x, texto in (
                (15.2, "U16"),
                (102.6, "16MM"),
                (149.2, '3/8"'),
                (229.9, "1,02"),
                (302.4, "AM1612"),
                (390.2, "16MM"),
                (438.1, '1/2"'),
                (518.1, "2,55"),
            ):
                visitor_text(texto, None, [1, 0, 0, 1, x, 631.7], None, 12)

    productos, errores, _ = etl_service._extraer_pdf_espacial(
        type("Lector", (), {"pages": [Pagina()]})()
    )

    assert errores == 0
    assert {producto["codigo"] for producto in productos} == {"U16", "AM1612"}
    izquierda = next(p for p in productos if p["codigo"] == "U16")
    derecha = next(p for p in productos if p["codigo"] == "AM1612")
    assert izquierda["precio"] == Decimal("1.02")
    assert derecha["precio"] == Decimal("2.55")
    assert "2,55" not in izquierda["nombre"]
    assert "AM1612" not in izquierda["nombre"]


def test_pdf_combina_estrategias_para_no_perder_paginas(monkeypatch):
    class Pagina:
        def extract_text(self):
            return "CODIGO DESCRIPCION PRECIO\nSKU-01 Martillo 1,00"

    class Lector:
        pages = [Pagina()]

    monkeypatch.setattr(etl_service, "PdfReader", lambda *_args, **_kwargs: Lector())
    monkeypatch.setattr(
        etl_service,
        "_extraer_pdf_fichas",
        lambda _lector: (
            [
                {
                    "codigo": "SKU-02",
                    "nombre": "Pinza",
                    "marca": None,
                    "precio": Decimal("2.00"),
                    "descuentos": Decimal("0.00"),
                    "descripcion": None,
                }
            ],
            0,
            [],
        ),
    )

    productos, errores, _ = etl_service._extraer_pdf(b"pdf de prueba")

    assert errores == 0
    assert {producto["codigo"] for producto in productos} == {"SKU-01", "SKU-02"}


def test_pdf_estrategia_redundante_no_marca_el_archivo_con_errores():
    """Una lectura alternativa de las mismas filas no debe sumar errores."""
    producto = {
        "codigo": "SKU-01",
        "nombre": "Martillo",
        "marca": None,
        "precio": Decimal("1.00"),
        "descuentos": Decimal("0.00"),
        "descripcion": None,
    }

    productos, errores, detalles = etl_service._unir_estrategias_pdf(
        [
            ("espacial", [producto], 0, []),
            (
                "generica",
                [dict(producto)],
                29,
                ["Fila 229: Precio invalido"],
            ),
        ]
    )

    assert errores == 0
    assert detalles == []
    assert [item["codigo"] for item in productos] == ["SKU-01"]


def test_pdf_estrategia_con_codigos_nuevos_conserva_sus_errores():
    base = {
        "codigo": "SKU-01",
        "nombre": "Martillo",
        "marca": None,
        "precio": Decimal("1.00"),
        "descuentos": Decimal("0.00"),
        "descripcion": None,
    }
    nuevo = {**base, "codigo": "SKU-02", "nombre": "Pinza"}

    productos, errores, detalles = etl_service._unir_estrategias_pdf(
        [
            ("espacial", [base], 0, []),
            ("fichas", [nuevo], 1, ["Fila 2: Precio invalido"]),
        ]
    )

    assert {item["codigo"] for item in productos} == {"SKU-01", "SKU-02"}
    assert errores == 1
    assert detalles == ["Fila 2: Precio invalido"]


def _pagina_de_cuadros(tarjetas):
    """Arma una pagina falsa con tarjetas dibujadas: bordes, palabras y renglones.

    ``tarjetas`` es una lista de ``(izquierda, derecha, arriba, renglones)``;
    cada renglon es el texto de una linea dentro de la tarjeta.
    """
    palabras = []
    rects = []
    for izquierda, derecha, arriba, renglones in tarjetas:
        for indice, renglon in enumerate(renglones):
            tope = arriba + 10 + indice * 13
            x = izquierda + 6
            for token in renglon.split():
                ancho = len(token) * 4.5
                palabras.append(
                    {
                        "text": token,
                        "x0": float(x),
                        "x1": float(x + ancho),
                        "top": float(tope),
                        "bottom": float(tope + 7.2),
                    }
                )
                x += ancho + 3
        alto = len(renglones) * 13 + 12
        for borde in (izquierda, derecha):
            rects.append(
                {
                    "x0": float(borde),
                    "x1": float(borde + 0.6),
                    "top": float(arriba),
                    "bottom": float(arriba + alto),
                    "width": 0.6,
                    "height": float(alto),
                }
            )
    return type(
        "Pagina",
        (),
        {
            "extract_words": lambda self: palabras,
            "rects": rects,
            "lines": [],
        },
    )()


def test_pdf_cuadros_arma_cada_ficha_dentro_de_su_tarjeta():
    # Tarjetas como las de TAMBOTORCA: las tres descripciones y los tres
    # codigos comparten renglon, pero cada ficha vive en su propio recuadro.
    pagina = _pagina_de_cuadros(
        [
            (
                30.0,
                205.0,
                130.0,
                [
                    "TORN. AUTO. C/PAN 4 X 3/8",
                    "CÓDIGO 1100029009A3",
                    "MIN. EMP. 1000",
                    "Ref. 12.04",
                ],
            ),
            (
                212.0,
                388.0,
                130.0,
                [
                    "TORN. AUTO. C/PAN 4 X 1/2",
                    "CÓDIGO 1100029013A3",
                    "MIN. EMP. 1000",
                    "Ref. 18.34",
                ],
            ),
        ]
    )

    fichas = etl_service._fichas_cuadros_pagina(pagina)

    assert fichas == [
        ("1100029009A3", "TORN. AUTO. C/PAN 4 X 3/8", "12.04"),
        ("1100029013A3", "TORN. AUTO. C/PAN 4 X 1/2", "18.34"),
    ]


def test_pdf_cuadros_no_mezcla_descripcion_nombre_ni_minimo():
    pagina = _pagina_de_cuadros(
        [
            (
                30.0,
                205.0,
                130.0,
                [
                    "BLIS REMACHE ALUM. AS (N) 42 N 1/8 x 6",
                    "PZA)",
                    "CÓDIGO 611203200642",
                    "MIN. EMP. 10",
                    "Ref. 20.21",
                ],
            ),
            (
                212.0,
                388.0,
                130.0,
                [
                    "BLIS REMACHE ALUM. AS (N) 43 N 1/8 x 8",
                    "CÓDIGO 611203200843",
                    "MIN. EMP. 10",
                    "Ref. 22.54",
                ],
            ),
        ]
    )

    productos = etl_service._fichas_cuadros_pagina(pagina)

    assert productos[0] == (
        "611203200642",
        "BLIS REMACHE ALUM. AS (N) 42 N 1/8 x 6 PZA)",
        "20.21",
    )
    assert productos[1] == (
        "611203200843",
        "BLIS REMACHE ALUM. AS (N) 43 N 1/8 x 8",
        "22.54",
    )
    for _codigo, nombre, _precio in productos:
        assert "MIN." not in nombre
        assert "EMP." not in nombre


def test_pdf_cuadros_une_el_precio_partido_en_dos_fragmentos():
    # El proveedor parte el precio en dos fragmentos ("9 " + ".19").
    pagina = _pagina_de_cuadros(
        [
            (
                30.0,
                205.0,
                130.0,
                ["BOMBILLO DICROICO LED 7W 6500 K", "CÓDIGO 4102DC7WH", "Ref. 9 .19"],
            ),
            (
                212.0,
                388.0,
                130.0,
                ["PINZA MINIATURA ELECTRICISTA 4.5\"", "CÓDIGO 58smp069c", "Ref. 9 .37"],
            ),
        ]
    )

    fichas = etl_service._fichas_cuadros_pagina(pagina)

    assert [ficha[2] for ficha in fichas] == ["9.19", "9.37"]


def test_pdf_cuadros_ignora_las_tarjetas_sin_precio():
    # Sin "Ref." no hay precio: la tarjeta se descarta en vez de inventarlo.
    pagina = _pagina_de_cuadros(
        [
            (
                30.0,
                205.0,
                130.0,
                ["MARTILLO", "CÓDIGO M-01", "MIN. EMP. 10"],
            ),
        ]
    )

    assert etl_service._fichas_cuadros_pagina(pagina) == []


def test_pdf_cuadros_informa_la_tarjeta_que_el_proveedor_dejo_sin_descripcion(
    monkeypatch,
):
    # Hay tarjetas con codigo y precio pero sin nombre: no se inventa uno.
    class Pagina:
        pass

    monkeypatch.setattr(
        etl_service,
        "pdfplumber",
        type(
            "Plumber",
            (),
            {
                "open": staticmethod(
                    lambda _flujo: type(
                        "Documento",
                        (),
                        {
                            "__enter__": lambda self: self,
                            "__exit__": lambda *_args: None,
                            "pages": [Pagina()],
                        },
                    )()
                )
            },
        ),
    )
    monkeypatch.setattr(
        etl_service,
        "_fichas_cuadros_pagina",
        lambda _pagina: [("1120096031A3", "", "48.86")],
    )

    productos, errores, detalle = etl_service._extraer_pdf_cuadros(b"pdf")

    assert productos == []
    assert errores == 1
    assert "1120096031A3" in detalle[0]
    assert "no trae descripcion" in detalle[0]


def test_pdf_solo_activa_la_lectura_por_cuadros_si_el_texto_la_delata():
    assert etl_service._es_catalogo_de_cuadros(
        "CODIGO DESCRIPCION PRECIO\nSKU-01 Martillo 1,00"
    ) is False
    texto_cuadros = "\n".join(
        ["CÓDIGO 1100029009A3 MIN. EMP. 1000 Ref. 12.04"] * 5
    )
    assert etl_service._es_catalogo_de_cuadros(texto_cuadros) is True


def test_pdf_usa_la_estrategia_de_cuadros_cuando_el_catalogo_es_de_tarjetas(
    monkeypatch,
):
    producto = {
        "codigo": "1100029009A3",
        "nombre": "TORN. AUTO. C/PAN 4 X 3/8",
        "marca": None,
        "precio": Decimal("12.04"),
        "descuentos": Decimal("0.00"),
        "descripcion": None,
    }
    texto_tarjetas = "\n".join(
        ["CÓDIGO 1100029009A3 MIN. EMP. 1000 Ref. 12.04"] * 5
    )
    monkeypatch.setattr(
        etl_service, "_texto_pdf_local", lambda _contenido: texto_tarjetas
    )
    monkeypatch.setattr(
        etl_service,
        "_extraer_pdf_cuadros",
        lambda _contenido: ([producto], 0, []),
    )
    monkeypatch.setattr(
        etl_service, "PdfReader", lambda *_args, **_kwargs: type("Lector", (), {"pages": []})()
    )

    productos, errores, _ = etl_service._extraer_pdf(b"pdf de prueba")

    assert errores == 0
    assert [item["codigo"] for item in productos] == ["1100029009A3"]
    assert productos[0]["precio"] == Decimal("12.04")


def test_excel_pregunta_por_todas_las_hojas_con_precios_ambiguos():
    libro = Workbook()
    primera = libro.active
    primera.title = "Catalogo A"
    primera.append(["Código", "Descripción", "Precio neto", "PVP"])
    primera.append(["SKU-01", "Tubo", 3.5, 4.06])
    segunda = libro.create_sheet("Catalogo B")
    segunda.append(["Código", "Descripción", "Costo", "Precio"])
    segunda.append(["SKU-02", "Codo", 1.5, 1.74])
    salida = io.BytesIO()
    libro.save(salida)

    with pytest.raises(etl_service.SeleccionPrecioRequerida) as error:
        etl_service._extraer_xlsx(salida.getvalue())

    assert {opcion["hoja"] for opcion in error.value.opciones} == {
        "Catalogo A",
        "Catalogo B",
    }


def test_previsualizar_archivo_no_persiste_productos(monkeypatch):
    def no_persistir(*_args, **_kwargs):
        raise AssertionError("La vista previa no debe tocar la base de datos")

    monkeypatch.setattr(inventario_model, "crear_archivo", no_persistir)
    monkeypatch.setattr(
        inventario_model, "insertar_o_actualizar_productos", no_persistir
    )

    vista = etl_service.previsualizar_archivo(
        "catalogo.txt", b"codigo;nombre;precio\nSKU-23;Pinza;3,50\n"
    )

    assert vista["productos_detectados"] == 1
    assert vista["muestra"][0]["codigo"] == "SKU-23"


def test_consolida_repeticiones_identicas_sin_contarlas_como_error():
    producto = {
        "codigo": "SKU-24",
        "nombre": "Martillo",
        "marca": None,
        "precio": Decimal("12.50"),
        "descuentos": Decimal("0.00"),
        "descripcion": None,
    }

    productos, duplicadas, errores, detalles = etl_service._consolidar_codigos(
        [producto, producto.copy()]
    )

    assert productos == [producto]
    assert duplicadas == 1
    assert errores == 0
    assert "se guardara una sola ficha" in detalles[0]


def test_conserva_una_variante_si_un_codigo_tiene_datos_distintos():
    primero = {
        "codigo": "SKU-25",
        "nombre": "Martillo",
        "marca": None,
        "precio": Decimal("12.50"),
        "descuentos": Decimal("0.00"),
        "descripcion": None,
    }
    segundo = {**primero, "precio": Decimal("13.00")}

    productos, duplicadas, errores, detalles = etl_service._consolidar_codigos(
        [primero, segundo]
    )

    # Un codigo repetido con datos distintos ya no elimina el producto: se
    # conserva una ficha y el conflicto queda informado para revision.
    assert productos == [primero]
    assert duplicadas == 1
    assert errores == 0
    assert "se conservo" in detalles[0]
    assert "variante" in detalles[0]


def test_previsualizacion_muestra_el_total_que_realmente_se_guardara(monkeypatch):
    producto = {
        "codigo": "SKU-26",
        "nombre": "Martillo",
        "marca": None,
        "precio": Decimal("12.50"),
        "descuentos": Decimal("0.00"),
        "descripcion": None,
    }
    monkeypatch.setattr(
        etl_service,
        "_extraer",
        lambda *_args, **_kwargs: ([producto, producto.copy()], 0, []),
    )

    vista = etl_service.previsualizar_archivo(
        "catalogo.txt", b"contenido"
    )

    assert vista["productos_detectados"] == 1
    assert vista["filas_duplicadas"] == 1
    assert vista["filas_error"] == 0


def test_el_detalle_informa_productos_sin_descripcion_del_proveedor(monkeypatch):
    """El aviso no cuenta como fila con error: el producto se guarda igual."""
    productos = [
        {
            "codigo": "SKU-40",
            "nombre": "Tuerca",
            "precio": Decimal("1.00"),
            "descripcion": None,
        },
        {
            "codigo": "SKU-41",
            "nombre": "Arandela",
            "precio": Decimal("1.50"),
            "descripcion": "Zincada",
        },
    ]
    monkeypatch.setattr(
        etl_service, "_extraer", lambda *_args, **_kwargs: (productos, 0, [])
    )
    vista = etl_service.previsualizar_archivo("catalogo.txt", b"contenido")

    assert vista["productos_detectados"] == 2
    assert vista["filas_error"] == 0
    assert vista["filas_duplicadas"] == 0
    assert "1 producto sin descripcion en el archivo" in vista["detalle"]
    assert "se indexan con el nombre y los demas datos disponibles" in vista["detalle"]


def test_no_avisa_de_descripcion_cuando_el_catalogo_la_incluye(monkeypatch):
    productos = [
        {
            "codigo": "SKU-42",
            "nombre": "Clavo",
            "precio": Decimal("0.50"),
            "descripcion": "Punta Phillips",
        }
    ]
    monkeypatch.setattr(
        etl_service, "_extraer", lambda *_args, **_kwargs: (productos, 0, [])
    )
    vista = etl_service.previsualizar_archivo("catalogo.txt", b"contenido")

    assert vista["productos_detectados"] == 1
    assert vista["detalle"] is None


def test_rechaza_archivo_xlsx_con_zip_danado():
    with pytest.raises(etl_service.ErrorIngesta, match="comprimido"):
        etl_service._validar_paquete(b"no es un zip")


def test_rechaza_zip_bomb_por_razon_de_compresion():
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
        archivo.writestr("xl/workbook.xml", b"0" * (2 * 1024 * 1024))

    with pytest.raises(etl_service.ErrorIngesta, match="compresion seguro"):
        etl_service._validar_paquete(salida.getvalue())


def test_rechaza_mas_de_20000_filas():
    filas = [["codigo", "nombre", "precio"]]
    filas.extend((f"SKU-{i}", "Producto", "1.00") for i in range(20_001))

    with pytest.raises(etl_service.ErrorIngesta, match="20000 filas"):
        etl_service._extraer_filas(filas)


def test_txt_de_5000_productos_se_procesa_completo():
    filas = [["codigo", "nombre", "precio"]]
    filas.extend((f"SKU-{i}", f"Producto {i}", "1,25") for i in range(5_000))

    productos, errores, _ = etl_service._extraer_filas(filas)

    assert len(productos) == 5_000
    assert errores == 0


def test_formatos_no_admitidos_se_rechazan_sin_guardar_archivo():
    resultado = etl_service.procesar_archivo("catalogo.csv", b"a,b,c", 1)

    assert resultado["estado"] == "rechazado"
    assert resultado["id_archivo"] is None


def test_limite_de_100_mb_se_aplica_antes_de_guardar(monkeypatch):
    assert etl_service.MAX_ARCHIVO_MB == 100
    assert etl_service.MAX_ARCHIVO_BYTES == 100 * 1024 * 1024
    monkeypatch.setattr(etl_service, "MAX_ARCHIVO_BYTES", 3)

    resultado = etl_service.procesar_archivo("catalogo.txt", b"1234", 1)

    assert resultado["estado"] == "rechazado"
    assert "100 MB" in resultado["detalle"]


def test_upsert_no_actualiza_stock_y_conserva_proveedor_y_moneda(monkeypatch):
    capturado = {}

    class CursorFalso:
        def execute(self, *_):
            pass

        def fetchone(self):
            return {"id_proveedor": 17, "moneda": "USD"}

    class ContextoCursor:
        def __enter__(self):
            return CursorFalso()

        def __exit__(self, *_):
            return False

    def ejecutar_valores(cursor, consulta, valores, page_size):
        capturado["consulta"] = consulta.lower()
        capturado["valores"] = valores

    monkeypatch.setattr(inventario_model, "cursor_rag", ContextoCursor)
    monkeypatch.setattr(inventario_model, "execute_values", ejecutar_valores)

    total = inventario_model.insertar_o_actualizar_productos(
        5,
        [
            {
                "codigo": "SKU-05",
                "nombre": "Llave",
                "precio": Decimal("2.50"),
            }
        ],
    )

    assert total == 1
    assert "stock" not in capturado["consulta"]
    assert "id_proveedor" in capturado["consulta"]
    assert "descripcion_vectorial" not in capturado["consulta"]
    assert capturado["valores"][0][0] == 5
    assert capturado["valores"][0][1] == 17
    assert capturado["valores"][0][6] == Decimal("16.00")
    assert capturado["valores"][0][9] == "USD"


def test_migracion_etl_es_idempotente_y_sin_dependencia_fk_usuario():
    raiz = etl_service.Path(__file__).resolve().parents[2]
    sql = (raiz / "scripts" / "migracion_3_0.sql").read_text(encoding="utf-8").lower()

    assert "add column if not exists" in sql
    assert "create index if not exists idx_archivos_hash" in sql
    assert "id_usuario int" in sql
    assert "references usuarios" not in sql
