from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import rag_chat
from app.schemas.rag_schema import PreguntaChat
from app.services.embedding_service import ErrorEmbedding
from app.services.llm_service import ErrorLLM, RespuestaLLM


@pytest.fixture
def dependencias_auditadas(monkeypatch):
    monkeypatch.setattr(rag_chat, "registrar_evento", lambda *args, **kwargs: None)
    return SimpleNamespace(
        request=object(),
        usuario={"id": 7},
    )


def test_chat_conecta_busqueda_generacion_y_fuentes(
    monkeypatch, dependencias_auditadas
):
    producto = {
        "codigo": "M-1",
        "nombre": "Martillo",
        "marca": "FIPCA",
        "categoria": "Herramientas",
        "precio": 12.5,
        "stock": 4,
    }
    llamadas = {}

    def buscar(pregunta):
        llamadas["pregunta_busqueda"] = pregunta
        return [producto]

    def generar(pregunta, productos):
        llamadas["pregunta_generacion"] = pregunta
        llamadas["productos"] = productos
        return RespuestaLLM("Hay 4 unidades.", "modelo-prueba")

    monkeypatch.setattr(rag_chat.vector_search, "buscar_productos", buscar)
    monkeypatch.setattr(rag_chat.llm_service, "generar_respuesta", generar)

    respuesta = rag_chat.chat(
        PreguntaChat(pregunta="¿Cuántos martillos hay?"),
        dependencias_auditadas.request,
        dependencias_auditadas.usuario,
    )

    assert llamadas["pregunta_busqueda"] == "¿Cuántos martillos hay?"
    assert llamadas["pregunta_generacion"] == "¿Cuántos martillos hay?"
    assert llamadas["productos"] == [producto]
    assert respuesta.respuesta == "Hay 4 unidades."
    assert respuesta.modelo == "modelo-prueba"
    assert [fuente.model_dump() for fuente in respuesta.fuentes] == [
        {
            "codigo": "M-1",
            "nombre": "Martillo",
            "marca": "FIPCA",
            "precio": 12.5,
            "stock": 4,
            "categoria": "Herramientas",
        }
    ]


@pytest.mark.parametrize(
    ("dependencia", "excepcion", "estado"),
    [
        ("buscar_productos", ErrorEmbedding("sin modelo"), 503),
        ("generar_respuesta", ErrorLLM("sin proveedor"), 502),
    ],
)
def test_chat_expone_fallos_de_servicios(
    monkeypatch, dependencias_auditadas, dependencia, excepcion, estado
):
    def fallar(*args):
        raise excepcion

    if dependencia == "buscar_productos":
        monkeypatch.setattr(
            rag_chat.vector_search,
            dependencia,
            fallar,
        )
    else:
        monkeypatch.setattr(
            rag_chat.vector_search, "buscar_productos", lambda pregunta: []
        )
        monkeypatch.setattr(
            rag_chat.llm_service,
            dependencia,
            fallar,
        )

    with pytest.raises(HTTPException) as captura:
        rag_chat.chat(
            PreguntaChat(pregunta="Consulta"),
            dependencias_auditadas.request,
            dependencias_auditadas.usuario,
        )

    assert captura.value.status_code == estado


def test_estado_indica_si_el_proveedor_esta_configurado(monkeypatch):
    monkeypatch.setattr(
        rag_chat,
        "get_settings",
        lambda: SimpleNamespace(llm_configurado=True, llm_modelo="modelo-prueba"),
    )

    assert rag_chat.estado({"id": 7}) == {
        "disponible": True,
        "modelo": "modelo-prueba",
        "semana": 4,
        "detalle": (
            "Proveedor configurado; la disponibilidad se confirma al consultar"
        ),
    }
