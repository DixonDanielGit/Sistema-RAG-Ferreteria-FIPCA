import pytest

from app.services import embedding_service


class ModeloFalso:
    def __init__(self, vector=None):
        self.llamadas = []
        self.vector = vector or [0.0] * embedding_service.DIMENSION_EMBEDDING

    def embed(self, textos, batch_size):
        self.llamadas.append(textos)
        assert batch_size == embedding_service.TAMANO_LOTE_EMBEDDING
        return [self.vector for _ in textos]


def test_embedding_e5_prefija_pregunta_y_pasaje(monkeypatch):
    modelo = ModeloFalso()
    monkeypatch.setattr(embedding_service, "_modelo", modelo)

    consulta = embedding_service.generar_embeddings([" taladro "], tipo="query")
    pasaje = embedding_service.generar_embeddings(["Producto: taladro"], tipo="passage")

    assert modelo.llamadas == [["query: taladro"], ["passage: Producto: taladro"]]
    assert len(consulta[0]) == embedding_service.DIMENSION_EMBEDDING
    assert len(pasaje[0]) == embedding_service.DIMENSION_EMBEDDING


def test_embedding_rechaza_dimension_incorrecta(monkeypatch):
    monkeypatch.setattr(embedding_service, "_modelo", ModeloFalso([0.0] * 383))

    with pytest.raises(embedding_service.ErrorEmbedding, match="384 dimensiones"):
        embedding_service.generar_embeddings(["producto"], tipo="passage")


def test_embedding_rechaza_valores_no_finitos(monkeypatch):
    vector = [0.0] * embedding_service.DIMENSION_EMBEDDING
    vector[0] = float("nan")
    monkeypatch.setattr(embedding_service, "_modelo", ModeloFalso(vector))

    with pytest.raises(embedding_service.ErrorEmbedding, match="no finitos"):
        embedding_service.generar_embeddings(["producto"], tipo="passage")


@pytest.mark.parametrize(
    ("textos", "tipo"),
    [
        ([""], "query"),
        (["producto"], "document"),
    ],
)
def test_embedding_valida_entrada(textos, tipo):
    with pytest.raises(ValueError):
        embedding_service.generar_embeddings(textos, tipo=tipo)


def test_embedding_vacio_no_carga_modelo(monkeypatch):
    def modelo_no_debe_cargarse():
        raise AssertionError("No debe cargar el modelo con una lista vacia")

    monkeypatch.setattr(embedding_service, "_obtener_modelo", modelo_no_debe_cargarse)

    assert embedding_service.generar_embeddings([], tipo="query") == []
