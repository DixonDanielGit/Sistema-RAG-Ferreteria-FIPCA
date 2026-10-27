"""Vectorizacion controlada y busqueda semantica de productos."""

from __future__ import annotations

from typing import Any

from app.models import inventario as inventario_model
from app.services.embedding_service import generar_embeddings

MAX_PRODUCTOS_POR_LOTE = 100
MAX_RESULTADOS_BUSQUEDA = 20
MAX_LONGITUD_PREGUNTA = 1000


def crear_texto_producto(producto: dict[str, Any]) -> str:
    """Construye el texto del catalogo usado para indexar el producto."""
    campos = [
        ("Codigo", producto.get("codigo")),
        ("Producto", producto.get("nombre")),
        ("Marca", producto.get("marca")),
        ("Categoria", producto.get("categoria")),
        ("Descripcion", producto.get("descripcion")),
    ]
    return ". ".join(f"{nombre}: {valor}" for nombre, valor in campos if valor).strip()


def vectorizar_productos_pendientes(limite: int = 25) -> dict[str, int]:
    """Vectoriza una pagina de productos sin embedding y guarda solo filas vigentes."""
    if not 1 <= limite <= MAX_PRODUCTOS_POR_LOTE:
        raise ValueError(
            f"El limite debe estar entre 1 y {MAX_PRODUCTOS_POR_LOTE}"
        )

    productos = inventario_model.productos_sin_embedding(limite)
    if not productos:
        return {"encontrados": 0, "actualizados": 0}

    textos = [crear_texto_producto(producto) for producto in productos]
    vectores = generar_embeddings(textos, tipo="passage")
    filas = [
        (producto["id"], vector)
        for producto, vector in zip(productos, vectores, strict=True)
    ]
    actualizados = inventario_model.guardar_embeddings(filas)
    return {"encontrados": len(productos), "actualizados": actualizados}


def buscar_productos(pregunta: str, limite: int = 5) -> list[dict[str, Any]]:
    """Devuelve productos existentes ordenados por similitud coseno."""
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La consulta no puede estar vacia")
    if len(pregunta) > MAX_LONGITUD_PREGUNTA:
        raise ValueError(
            f"La consulta no puede superar {MAX_LONGITUD_PREGUNTA} caracteres"
        )
    if not 1 <= limite <= MAX_RESULTADOS_BUSQUEDA:
        raise ValueError(
            f"El limite debe estar entre 1 y {MAX_RESULTADOS_BUSQUEDA}"
        )

    vector = generar_embeddings([pregunta.strip()], tipo="query")[0]
    return inventario_model.buscar_productos_por_vector(vector, limite)