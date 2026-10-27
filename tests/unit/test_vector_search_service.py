from pathlib import Path

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
            "descripcion": "",
        }
    )

    assert texto == "Codigo: SKU-1. Producto: Taladro. Categoria: Herramientas"


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
    assert capturado["textos"] == ["Codigo: SKU-8. Producto: Llave"]
    assert capturado["filas"][0][0] == 8


@pytest.mark.parametrize("limite", [0, 101])
def test_vectorizacion_valida_limite_de_lote(limite):
    with pytest.raises(ValueError, match="limite"):
        vector_search.vectorizar_productos_pendientes(limite)


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
    [("", 5), ("x" * 1001, 5), ("martillo", 0), ("martillo", 21)],
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
