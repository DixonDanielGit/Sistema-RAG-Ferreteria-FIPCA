from pathlib import Path
import threading
import time

import pytest

from app.models import inventario as inventario_model
from app.services import vector_search


def test_crear_texto_producto_solo_incluye_datos_presentes():
    texto = vector_search.crear_texto_producto(
        {
            "codigo": "SKU-1",
            "nombre": "Taladro",
            "marca": None,
            "categoria": "Herramientas",
            "descripcion": "Taladro percutor de 750 W",
        }
    )

    assert texto == (
        "Codigo: SKU-1. Producto: Taladro. Categoria: Herramientas. "
        "Descripcion: Taladro percutor de 750 W"
    )


def test_sin_descripcion_se_indexa_con_ficha_de_plantilla():
    """El proveedor no describio el producto: la ficha arma con datos reales."""
    texto = vector_search.crear_texto_producto(
        {
            "codigo": "SKU-9",
            "nombre": "Manguera de riego",
            "marca": "Tigre",
            "categoria": "Riego",
            "descripcion": "",
        }
    )

    assert texto == "Ficha de producto: Manguera de riego, marca Tigre, categoria Riego, codigo SKU-9."
    # La plantilla no agrega datos: ni precio, ni stock, ni textos inventados.
    assert "precio" not in texto
    assert "stock" not in texto


def test_la_ficha_de_plantilla_no_repite_campos_ausentes():
    texto = vector_search.crear_texto_producto(
        {"codigo": None, "nombre": "Clavo", "marca": "", "categoria": None}
    )

    assert texto == "Ficha de producto: Clavo."


def test_ficha_dinamica_incluye_proveedor_y_presentacion_reales():
    texto = vector_search.crear_texto_producto(
        {
            "codigo": "SKU-10",
            "nombre": "Tubo PVC",
            "marca": "Tigre",
            "categoria": "Plomeria",
            "presentacion": "3 metros",
            "unidad_medida": "unidad",
            "proveedor": "Distribuidora Central",
        }
    )

    assert texto == (
        "Ficha de producto: Tubo PVC, marca Tigre, categoria Plomeria, "
        "presentacion 3 metros, unidad unidad, proveedor Distribuidora Central, "
        "codigo SKU-10."
    )


def test_descripcion_explicita_se_complementa_con_el_proveedor():
    texto = vector_search.crear_texto_producto(
        {
            "codigo": "SKU-11",
            "nombre": "Pega PVC",
            "descripcion": "Adhesivo para tuberias",
            "proveedor": "Distribuidora Central",
        }
    )

    assert texto == (
        "Codigo: SKU-11. Producto: Pega PVC. "
        "Proveedor: Distribuidora Central. "
        "Descripcion: Adhesivo para tuberias"
    )


def test_el_texto_de_indexacion_no_incluye_campos_volatiles():
    texto = vector_search.crear_texto_producto(
        {
            "codigo": "SKU-2",
            "nombre": "Martillo",
            "precio": 4.5,
            "stock": 12,
            "descuentos": 10,
            "descripcion": "Mango de fibra",
        }
    )

    assert "4.5" not in texto
    assert "12" not in texto
    assert "10" not in texto
    assert texto == "Codigo: SKU-2. Producto: Martillo. Descripcion: Mango de fibra"


def test_vectoriza_lote_pendiente(monkeypatch):
    productos = [
        {"id": 8, "codigo": "SKU-8", "nombre": "Llave", "marca": None},
    ]
    capturado = {}
    monkeypatch.setattr(
        vector_search.inventario_model, "productos_sin_embedding", lambda limite: productos
    )

    def generar(textos, *, tipo):
        capturado["textos"] = textos
        capturado["tipo"] = tipo
        return [[0.0] * 384]

    monkeypatch.setattr(vector_search, "generar_embeddings", generar)

    def guardar(filas):
        capturado["filas"] = list(filas)
        return 1

    monkeypatch.setattr(
        vector_search.inventario_model,
        "guardar_embeddings",
        guardar,
    )

    resultado = vector_search.vectorizar_productos_pendientes(limite=1)

    assert resultado == {"encontrados": 1, "actualizados": 1}
    assert capturado["tipo"] == "passage"
    assert capturado["textos"] == ["Ficha de producto: Llave, codigo SKU-8."]
    assert capturado["filas"][0][0] == 8


def test_vectorizacion_fallback_incluye_proveedor_obtenido_de_la_base(monkeypatch):
    productos = [
        {
            "id": 18,
            "codigo": "SKU-18",
            "nombre": "Tubo PVC",
            "proveedor": "Distribuidora Central",
        }
    ]
    capturado = {}
    monkeypatch.setattr(
        vector_search.inventario_model, "productos_sin_embedding", lambda limite: productos
    )

    def generar(textos, *, tipo):
        capturado["textos"] = textos
        return [[0.0] * 384]

    monkeypatch.setattr(vector_search, "generar_embeddings", generar)
    monkeypatch.setattr(
        vector_search.inventario_model,
        "guardar_embeddings",
        lambda filas: len(list(filas)),
    )

    resultado = vector_search.vectorizar_productos_pendientes(limite=1)

    assert resultado == {"encontrados": 1, "actualizados": 1}
    assert capturado["textos"] == [
        "Ficha de producto: Tubo PVC, proveedor Distribuidora Central, codigo SKU-18."
    ]


def test_consulta_de_pendientes_carga_el_proveedor_y_campos_de_presentacion(
    monkeypatch,
):
    capturado = {}

    def consultar(consulta, parametros, *, rag):
        capturado.update(consulta=consulta.lower(), parametros=parametros, rag=rag)
        return []

    monkeypatch.setattr(inventario_model, "consultar_todos", consultar)

    assert inventario_model.productos_sin_embedding(7) == []
    assert "left join proveedores as pr" in capturado["consulta"]
    assert "pr.nombre as proveedor" in capturado["consulta"]
    assert "p.unidad_medida" in capturado["consulta"]
    assert "p.presentacion" in capturado["consulta"]
    assert capturado["parametros"] == (7,)
    assert capturado["rag"] is True


def test_un_producto_sin_campos_no_interrumpe_el_lote(monkeypatch):
    """Un registro vacio no impide vectorizar el resto del lote."""
    productos = [
        {"id": 1, "codigo": None, "nombre": "", "marca": None},
        {"id": 2, "codigo": "SKU-2", "nombre": "Llave", "marca": None},
    ]
    capturado = {}
    monkeypatch.setattr(
        vector_search.inventario_model,
        "productos_sin_embedding",
        lambda limite: productos,
    )

    def generar(textos, *, tipo):
        capturado["textos"] = textos
        return [[0.0] * 384]

    monkeypatch.setattr(vector_search, "generar_embeddings", generar)
    monkeypatch.setattr(
        vector_search.inventario_model,
        "guardar_embeddings",
        lambda filas: len(list(filas)),
    )

    resultado = vector_search.vectorizar_productos_pendientes(limite=2)

    assert resultado == {"encontrados": 2, "actualizados": 1}
    assert capturado["textos"] == ["Ficha de producto: Llave, codigo SKU-2."]


@pytest.mark.parametrize("limite", [0, 101])
def test_vectorizacion_valida_limite_de_lote(limite):
    with pytest.raises(ValueError, match="limite"):
        vector_search.vectorizar_productos_pendientes(limite)


def _configuracion(*, automatica: bool):
    """Configuracion de prueba con la vectorizacion automatica decidida."""
    from dataclasses import replace

    from app.config import get_settings

    return replace(get_settings(), vectorizacion_automatica=automatica)


def test_lanzar_vectorizacion_automatica_arranca_un_hilo(monkeypatch):
    """Tras una ingesta exitosa el catalogo se indexa sin paso manual."""
    conteo = {"consultas": 0}

    def lote(limite):
        conteo["consultas"] += 1
        return {"encontrados": 0, "actualizados": 0}

    monkeypatch.setattr(vector_search, "vectorizar_productos_pendientes", lote)
    monkeypatch.setattr(
        vector_search, "get_settings", lambda: _configuracion(automatica=True)
    )

    assert vector_search.lanzar_vectorizacion_automatica() is True

    # El hilo termina solo: al salir libera la cerradura y baja la bandera.
    para = time.time() + 5
    while vector_search.vectorizacion_en_curso() and time.time() < para:
        time.sleep(0.01)
    assert not vector_search.vectorizacion_en_curso()
    assert conteo["consultas"] == 1


def test_vectorizacion_automatica_desactivada_no_arranca(monkeypatch):
    monkeypatch.setattr(
        vector_search, "get_settings", lambda: _configuracion(automatica=False)
    )

    assert vector_search.lanzar_vectorizacion_automatica() is False
    assert not vector_search.vectorizacion_en_curso()


def test_no_se_admiten_dos_lotes_automaticos_a_la_vez(monkeypatch):
    """La subida envia varios archivos en secuencia: un solo bucle indexa
    todos, para no duplicar trabajo ni pelear por el modelo."""
    liberar = threading.Event()
    consultas = {"n": 0}

    def lote(limite):
        consultas["n"] += 1
        liberar.wait(timeout=5)
        return {"encontrados": 0, "actualizados": 0}

    monkeypatch.setattr(vector_search, "vectorizar_productos_pendientes", lote)
    monkeypatch.setattr(
        vector_search,
        "get_settings",
        lambda: _configuracion(automatica=True),
    )

    assert vector_search.lanzar_vectorizacion_automatica() is True
    try:
        assert vector_search.lanzar_vectorizacion_automatica() is False
    finally:
        liberar.set()

    para = time.time() + 5
    while vector_search.vectorizacion_en_curso() and time.time() < para:
        time.sleep(0.01)
    assert consultas["n"] == 1


def test_el_bucle_se_detiene_si_no_hay_avance(monkeypatch):
    """Dos paginas sin guardar nada significan estancamiento: el bucle no
    debe girar para siempre sobre los mismos productos."""
    consultas = {"n": 0}

    def lote(limite):
        consultas["n"] += 1
        return {"encontrados": 3, "actualizados": 0}

    monkeypatch.setattr(vector_search, "vectorizar_productos_pendientes", lote)

    # Como en produccion: la cerradura la toma lanzar_vectorizacion_automatica.
    assert vector_search._candado_automatica.acquire(blocking=False)
    try:
        vector_search._bucle_vectorizacion()
    finally:
        if vector_search._candado_automatica.locked():
            vector_search._candado_automatica.release()

    assert consultas["n"] == vector_search.MAX_SIN_AVANCE


def test_un_fallo_de_embeddings_no_deja_el_bucle_marcado_en_curso(monkeypatch):
    """Sin FastEmbed el hilo muere limpio: la bandera no puede quedarse
    en True o el panel sondearia para siempre un lote que ya no corre."""
    monkeypatch.setattr(
        vector_search,
        "vectorizar_productos_pendientes",
        lambda limite: (_ for _ in ()).throw(
            vector_search.ErrorEmbedding("Falta FastEmbed")
        ),
    )

    assert vector_search._candado_automatica.acquire(blocking=False)
    vector_search._estado_automatica["en_curso"] = True
    try:
        vector_search._bucle_vectorizacion()
    finally:
        pass

    assert not vector_search.vectorizacion_en_curso()
    # La cerradura quedo libre: otro lote puede arrancar despues.
    assert not vector_search._candado_automatica.locked()


def test_busqueda_vectorial_generada_como_query(monkeypatch):
    capturado = {}

    def generar(textos, *, tipo):
        capturado["textos"] = textos
        capturado["tipo"] = tipo
        return [[0.0] * 384]

    monkeypatch.setattr(vector_search, "generar_embeddings", generar)
    monkeypatch.setattr(
        vector_search.inventario_model,
        "buscar_productos_por_vector",
        lambda vector, limite: [{"codigo": "SKU-1", "similitud": 1.0}],
    )

    resultados = vector_search.buscar_productos(" taladro ", limite=3)

    assert resultados[0]["codigo"] == "SKU-1"
    assert capturado == {"textos": ["taladro"], "tipo": "query"}


@pytest.mark.parametrize(
    ("pregunta", "limite"),
    [("", 5), ("x" * 2001, 5), ("martillo", 0), ("martillo", 21)],
)
def test_busqueda_valida_pregunta_y_limite(pregunta, limite):
    with pytest.raises(ValueError):
        vector_search.buscar_productos(pregunta, limite)


def test_esquema_y_migracion_4_0_coinciden_con_el_modelo():
    raiz = Path(__file__).resolve().parents[2]
    esquema = (raiz / "init.sql").read_text(encoding="utf-8").lower()
    migracion = (raiz / "scripts" / "migracion_4_0.sql").read_text(
        encoding="utf-8"
    ).lower()

    assert "descripcion_vectorial vector(384)" in esquema
    assert "alter column descripcion_vectorial type vector(384)" in migracion
    assert "hay embeddings existentes" in migracion
    assert "using null::vector(384)" in migracion


def test_serializacion_vectorial_valida_dimension_y_valores():
    vector = [0.0] * 384
    texto = inventario_model._serializar_vector(vector)

    assert texto.startswith("[0,0,0")
    assert texto.endswith("]")
    with pytest.raises(ValueError, match="384 dimensiones"):
        inventario_model._serializar_vector(vector[:-1])

    vector[0] = float("inf")
    with pytest.raises(ValueError, match="no finitos"):
        inventario_model._serializar_vector(vector)
