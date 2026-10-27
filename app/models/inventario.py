"""Acceso a datos del catalogo y seguimiento de archivos ETL."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Iterable

from psycopg2.extras import execute_values

from app.db.session import consultar_todos, cursor_rag, ejecutar


def _serializar_vector(vector: list[float]) -> str:
    if len(vector) != 384:
        raise ValueError("El embedding debe tener 384 dimensiones")
    valores = [float(valor) for valor in vector]
    if not all(math.isfinite(valor) for valor in valores):
        raise ValueError("El embedding contiene valores no finitos")
    return "[" + ",".join(format(valor, ".9g") for valor in valores) + "]"


def crear_archivo(
    *,
    nombre: str,
    tipo: str,
    ruta: str,
    hash_sha256: str,
    tamano_bytes: int,
    id_usuario: int,
) -> dict[str, Any]:
    """Registra el archivo antes de iniciar su procesamiento."""
    return ejecutar(
        """
        INSERT INTO archivos_subidos
            (nombre, tipo, ruta, hash_sha256, tamano_bytes, estado, id_usuario)
        VALUES (%s, %s, %s, %s, %s, 'pendiente', %s)
        RETURNING id_archivo, nombre, tipo, fecha_de_subida, tamano_bytes,
                  estado, filas_ok, filas_error, detalle
        """,
        (nombre, tipo, ruta, hash_sha256, tamano_bytes, id_usuario),
        rag=True,
    )


def actualizar_estado_archivo(
    id_archivo: int,
    *,
    estado: str,
    filas_ok: int = 0,
    filas_error: int = 0,
    detalle: str | None = None,
) -> dict[str, Any]:
    """Actualiza el resultado del procesamiento y marca su finalizacion."""
    return ejecutar(
        """
        UPDATE archivos_subidos
           SET estado = %s,
               filas_ok = %s,
               filas_error = %s,
               detalle = %s,
               terminado_en = CASE
                   WHEN %s IN ('ok', 'parcial', 'error') THEN CURRENT_TIMESTAMP
                   ELSE NULL
               END
         WHERE id_archivo = %s
        RETURNING id_archivo, nombre, tipo, fecha_de_subida, tamano_bytes,
                  estado, filas_ok, filas_error, detalle
        """,
        (estado, filas_ok, filas_error, detalle, estado, id_archivo),
        rag=True,
    )


def insertar_o_actualizar_productos(
    id_archivo: int, productos: Iterable[dict[str, Any]]
) -> int:
    """Hace upsert por codigo sin modificar existencias ni vectores."""
    filas = [
        (
            id_archivo,
            producto["codigo"],
            producto["nombre"],
            producto.get("marca"),
            producto["precio"],
            Decimal("16.00"),
            producto.get("descuentos", 0),
            producto.get("descripcion"),
        )
        for producto in productos
    ]
    if not filas:
        return 0

    sql = """
        INSERT INTO productos
            (id_archivo, codigo, nombre, marca, precio, iva, descuentos, descripcion)
        VALUES %s
        ON CONFLICT (codigo) DO UPDATE SET
            id_archivo = EXCLUDED.id_archivo,
            nombre = EXCLUDED.nombre,
            marca = EXCLUDED.marca,
            precio = EXCLUDED.precio,
            iva = 16.00,
            descuentos = EXCLUDED.descuentos,
            descripcion = EXCLUDED.descripcion,
            descripcion_vectorial = CASE
                WHEN (productos.nombre, productos.marca, productos.descripcion)
                     IS DISTINCT FROM
                     (EXCLUDED.nombre, EXCLUDED.marca, EXCLUDED.descripcion)
                THEN NULL
                ELSE productos.descripcion_vectorial
            END
    """
    with cursor_rag() as cursor:
        execute_values(cursor, sql, filas, page_size=500)
        return len(filas)


def productos_sin_embedding(limite: int) -> list[dict[str, Any]]:
    """Obtiene productos pendientes con sus campos descriptivos."""
    return consultar_todos(
        """
        SELECT p.id, p.codigo, p.nombre, p.marca, p.descripcion,
               c.nombre AS categoria
          FROM productos AS p
          LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
         WHERE p.descripcion_vectorial IS NULL
         ORDER BY p.id
         LIMIT %s
        """,
        (limite,),
        rag=True,
    )


def guardar_embeddings(filas: Iterable[tuple[int, list[float]]]) -> int:
    """Guarda vectores solo si el producto sigue pendiente de vectorizacion."""
    valores = [
        (id_producto, _serializar_vector(vector))
        for id_producto, vector in filas
    ]
    if not valores:
        return 0

    with cursor_rag() as cursor:
        actualizados = execute_values(
            cursor,
            """
            UPDATE productos AS p
               SET descripcion_vectorial = datos.embedding::vector(384)
              FROM (VALUES %s) AS datos(id, embedding)
             WHERE p.id = datos.id
               AND p.descripcion_vectorial IS NULL
            RETURNING p.id
            """,
            valores,
            template="(%s, %s)",
            page_size=100,
            fetch=True,
        )
        return len(actualizados)


def buscar_productos_por_vector(
    vector: list[float], limite: int
) -> list[dict[str, Any]]:
    """Busca productos por distancia coseno; nunca incluye filas sin vector."""
    vector_texto = _serializar_vector(vector)
    return consultar_todos(
        """
        SELECT p.id, p.codigo, p.nombre, p.marca, p.descripcion, p.precio,
               p.iva, p.stock,
               1 - (p.descripcion_vectorial <=> %s::vector(384)) AS similitud
          FROM productos AS p
         WHERE p.descripcion_vectorial IS NOT NULL
         ORDER BY p.descripcion_vectorial <=> %s::vector(384), p.id
         LIMIT %s
        """,
        (vector_texto, vector_texto, limite),
        rag=True,
    )


def listar_archivos(limite: int = 100) -> list[dict[str, Any]]:
    """Devuelve los lotes mas recientes sin incluir rutas internas ni hashes."""
    return consultar_todos(
        """
        SELECT id_archivo, nombre, tipo, fecha_de_subida, tamano_bytes,
               estado, filas_ok, filas_error, detalle
          FROM archivos_subidos
         ORDER BY fecha_de_subida DESC, id_archivo DESC
         LIMIT %s
        """,
        (limite,),
        rag=True,
    )