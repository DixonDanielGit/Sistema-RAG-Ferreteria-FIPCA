"""Generacion local de embeddings con multilingual-e5-small."""

from __future__ import annotations

import math
import os
import threading
from typing import Literal

from app.config import get_settings

MODELO_EMBEDDING = "intfloat/multilingual-e5-small"
DIMENSION_EMBEDDING = 384
TAMANO_LOTE_EMBEDDING = 32

_modelo: object | None = None
_candado_modelo = threading.Lock()


class ErrorEmbedding(RuntimeError):
    """Error al cargar o ejecutar el modelo de embeddings."""


def _crear_modelo():
    try:
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType
    except ImportError as exc:
        raise ErrorEmbedding(
            "Falta FastEmbed. Instale requirements-embeddings.txt con Python 3.12 "
            "o use la imagen Docker de la aplicacion."
        ) from exc

    modelos = TextEmbedding.list_supported_models()
    if not any(modelo["model"] == MODELO_EMBEDDING for modelo in modelos):
        TextEmbedding.add_custom_model(
            model=MODELO_EMBEDDING,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=MODELO_EMBEDDING),
            dim=DIMENSION_EMBEDDING,
            model_file="onnx/model.onnx",
            description="Embedding multilingue E5 pequeno para busqueda semantica",
            license="mit",
            additional_files=[
                "config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "sentencepiece.bpe.model",
            ],
            output_name="last_hidden_state",
        )

    cache_dir = get_settings().embedding_cache_dir.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))
    return TextEmbedding(
        model_name=MODELO_EMBEDDING,
        cache_dir=str(cache_dir),
        threads=1,
    )


def _obtener_modelo():
    global _modelo
    if _modelo is None:
        with _candado_modelo:
            if _modelo is None:
                _modelo = _crear_modelo()
    return _modelo


def generar_embeddings(
    textos: list[str], *, tipo: Literal["passage", "query"]
) -> list[list[float]]:
    """Vectoriza textos con prefijos E5 y valida forma y valores del resultado."""
    if tipo not in {"passage", "query"}:
        raise ValueError("El tipo de embedding debe ser 'passage' o 'query'")
    if any(not isinstance(texto, str) or not texto.strip() for texto in textos):
        raise ValueError("Los textos a vectorizar no pueden estar vacios")
    if not textos:
        return []

    entradas = [f"{tipo}: {texto.strip()}" for texto in textos]
    resultado = _obtener_modelo().embed(
        entradas,
        batch_size=TAMANO_LOTE_EMBEDDING,
    )

    vectores: list[list[float]] = []
    for vector in resultado:
        valores = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        if len(valores) != DIMENSION_EMBEDDING:
            raise ErrorEmbedding(
                f"Se esperaban {DIMENSION_EMBEDDING} dimensiones; "
                f"el modelo devolvio {len(valores)}"
            )
        vector_normalizado = [float(valor) for valor in valores]
        if not all(math.isfinite(valor) for valor in vector_normalizado):
            raise ErrorEmbedding("El modelo devolvio valores no finitos")
        vectores.append(vector_normalizado)

    if len(vectores) != len(textos):
        raise ErrorEmbedding(
            f"El modelo devolvio {len(vectores)} vectores para {len(textos)} textos"
        )
    return vectores