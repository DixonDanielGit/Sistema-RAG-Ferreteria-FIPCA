"""Acceso a datos del catalogo y seguimiento de archivos ETL."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Iterable

from psycopg2.extras import RealDictCursor, execute_values

from app.db.session import consultar_todos, consultar_uno, cursor_rag, ejecutar


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
    metadatos: dict[str, Any] | None = None,
    contenido_markdown: str | None = None,
) -> dict[str, Any]:
    """Registra el archivo y asocia atómicamente su proveedor y vendedor.

    ``contenido_markdown`` guarda el catalogo convertido por MarkItDown junto
    al registro (RF-02.4); si es ``None`` la conversion no estuvo disponible y
    el archivo se procesa igual (tolerancia RF-02.3).
    """
    metadatos = metadatos or {}
    proveedor = metadatos.get("proveedor")
    id_proveedor = None
    nombre_vendedor = metadatos.get("vendedor")
    telefono_vendedor = metadatos.get("telefono_vendedor")
    correo_vendedor = metadatos.get("correo_vendedor")
    moneda = metadatos.get("moneda", "USD")

    with cursor_rag() as cursor:
        if proveedor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(LOWER(%s))::BIGINT)",
                (proveedor,),
            )
            cursor.execute(
                """
                SELECT id_proveedores
                  FROM proveedores
                 WHERE LOWER(nombre) = LOWER(%s)
                 ORDER BY id_proveedores
                 FOR UPDATE
                """,
                (proveedor,),
            )
            existentes = cursor.fetchall()
            if len(existentes) > 1:
                raise ValueError(
                    "Hay proveedores duplicados con ese nombre; un administrador "
                    "debe unificarlos antes de cargar la cotizacion"
                )
            if existentes:
                id_proveedor = existentes[0]["id_proveedores"]
                cursor.execute(
                    """
                    UPDATE proveedores
                       SET vendedor = %s,
                           telefono_vendedor = COALESCE(NULLIF(%s, ''), telefono_vendedor),
                           correo_vendedor = COALESCE(NULLIF(%s, ''), correo_vendedor),
                           moneda = %s,
                           actualizado_en = NOW()
                     WHERE id_proveedores = %s
                    """,
                    (
                        nombre_vendedor,
                        telefono_vendedor,
                        correo_vendedor,
                        moneda,
                        id_proveedor,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO proveedores
                        (nombre, vendedor, telefono_vendedor, correo_vendedor, moneda)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_proveedores
                    """,
                    (
                        proveedor,
                        nombre_vendedor,
                        telefono_vendedor,
                        correo_vendedor,
                        moneda,
                    ),
                )
                id_proveedor = cursor.fetchone()["id_proveedores"]

        cursor.execute(
            """
            INSERT INTO archivos_subidos
                (nombre, tipo, ruta, hash_sha256, tamano_bytes, estado, id_usuario,
                 id_proveedor, vendedor_nombre, vendedor_telefono, vendedor_correo,
                 moneda, nota_proveedor, contenido_markdown)
            VALUES (%s, %s, %s, %s, %s, 'pendiente', %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_archivo, nombre, tipo, fecha_de_subida, tamano_bytes,
                      estado, filas_ok, filas_error, detalle, moneda,
                      vendedor_nombre AS vendedor,
                      (SELECT nombre FROM proveedores
                        WHERE id_proveedores = archivos_subidos.id_proveedor) AS proveedor
            """,
            (
                nombre,
                tipo,
                ruta,
                hash_sha256,
                tamano_bytes,
                id_usuario,
                id_proveedor,
                nombre_vendedor,
                telefono_vendedor,
                correo_vendedor,
                moneda,
                metadatos.get("nota_proveedor"),
                contenido_markdown,
            ),
        )
        return dict(cursor.fetchone())


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
                  estado, filas_ok, filas_error, detalle, moneda,
                  vendedor_nombre AS vendedor,
                  (SELECT nombre FROM proveedores
                    WHERE id_proveedores = archivos_subidos.id_proveedor) AS proveedor
        """,
        (estado, filas_ok, filas_error, detalle, estado, id_archivo),
        rag=True,
    )


def obtener_archivo(id_archivo: int) -> dict[str, Any] | None:
    """Devuelve los datos de un archivo subido, sin exponer su ruta interna."""
    return consultar_uno(
        """
        SELECT id_archivo, nombre, tipo, fecha_de_subida, tamano_bytes,
               estado, filas_ok, filas_error, detalle, moneda,
               vendedor_nombre AS vendedor,
               (SELECT nombre FROM proveedores
                 WHERE id_proveedores = archivos_subidos.id_proveedor) AS proveedor
          FROM archivos_subidos
         WHERE id_archivo = %s
        """,
        (id_archivo,),
        rag=True,
    )


def _retirar_archivos_y_ofertas(
    cursor: Any, ids_archivos: list[int]
) -> dict[int, int]:
    """Retira cotizaciones seleccionadas y conserva las de otros archivos."""
    cursor.execute(
        """
        WITH ultima AS (
            SELECT DISTINCT ON (id_oferta)
                   id_oferta, precio, moneda, iva, iva_incluido, descuento,
                   cantidad_disponible_proveedor, politica_ventas, id_archivo,
                   registrado_en
              FROM historial_precios
             WHERE id_archivo IS NOT NULL
               AND id_archivo <> ALL(%s)
             ORDER BY id_oferta, registrado_en DESC, id DESC
        )
        UPDATE producto_proveedor AS oferta
           SET precio = ultima.precio,
               moneda = ultima.moneda,
               iva = ultima.iva,
               iva_incluido = ultima.iva_incluido,
               descuento = ultima.descuento,
               cantidad_disponible_proveedor =
                   ultima.cantidad_disponible_proveedor,
               politica_ventas = ultima.politica_ventas,
               disponible = CASE
                   WHEN ultima.cantidad_disponible_proveedor IS NULL THEN NULL
                   ELSE ultima.cantidad_disponible_proveedor > 0
               END,
               id_archivo = ultima.id_archivo,
               fecha_cotizacion = ultima.registrado_en,
               actualizado_en = NOW()
          FROM ultima
         WHERE oferta.id = ultima.id_oferta
           AND oferta.id_archivo = ANY(%s)
        """,
        (ids_archivos, ids_archivos),
    )
    cursor.execute(
        "DELETE FROM producto_proveedor WHERE id_archivo = ANY(%s)",
        (ids_archivos,),
    )
    cursor.execute(
        "DELETE FROM historial_precios WHERE id_archivo = ANY(%s)",
        (ids_archivos,),
    )
    cursor.execute(
        """
        WITH fuentes AS (
            SELECT DISTINCT ON (id_producto) id_producto, id_archivo
              FROM producto_proveedor
             WHERE id_archivo IS NOT NULL
               AND id_archivo <> ALL(%s)
             ORDER BY id_producto, fecha_cotizacion DESC, id DESC
        )
        UPDATE productos AS producto
           SET id_archivo = fuentes.id_archivo,
               id_proveedor = archivo_fuente.id_proveedor,
               descripcion_vectorial = CASE
                   WHEN producto.id_proveedor
                        IS DISTINCT FROM archivo_fuente.id_proveedor
                   THEN NULL
                   ELSE producto.descripcion_vectorial
               END,
               modelo_embedding = CASE
                   WHEN producto.id_proveedor
                        IS DISTINCT FROM archivo_fuente.id_proveedor
                   THEN NULL
                   ELSE producto.modelo_embedding
               END,
               vectorizado_en = CASE
                   WHEN producto.id_proveedor
                        IS DISTINCT FROM archivo_fuente.id_proveedor
                   THEN NULL
                   ELSE producto.vectorizado_en
               END
          FROM fuentes
          JOIN archivos_subidos AS archivo_fuente
            ON archivo_fuente.id_archivo = fuentes.id_archivo
         WHERE producto.id_archivo = ANY(%s)
           AND producto.id = fuentes.id_producto
        """,
        (ids_archivos, ids_archivos),
    )
    cursor.execute(
        """
        DELETE FROM productos
         WHERE id_archivo = ANY(%s)
        RETURNING id_archivo
        """,
        (ids_archivos,),
    )
    productos_por_archivo: dict[int, int] = {}
    for fila in cursor.fetchall():
        id_archivo = fila["id_archivo"]
        productos_por_archivo[id_archivo] = (
            productos_por_archivo.get(id_archivo, 0) + 1
        )
    return productos_por_archivo


def eliminar_catalogo(id_archivo: int) -> dict[str, Any] | None:
    """Retira una cotizacion sin borrar productos/ofertas de otros catalogos."""
    with cursor_rag() as cursor:
        cursor.execute(
            """
            SELECT nombre, ruta
              FROM archivos_subidos
             WHERE id_archivo = %s
               FOR UPDATE
            """,
            (id_archivo,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None

        productos_por_archivo = _retirar_archivos_y_ofertas(cursor, [id_archivo])
        cursor.execute(
            "DELETE FROM archivos_subidos WHERE id_archivo = %s",
            (id_archivo,),
        )
        return {
            "id_archivo": id_archivo,
            "nombre": fila["nombre"],
            "ruta_original": fila["ruta"],
            "productos_eliminados": productos_por_archivo.get(id_archivo, 0),
        }


def eliminar_catalogos(ids_archivos: list[int]) -> dict[str, Any]:
    """Elimina en una transaccion todos los catalogos existentes del lote."""
    ids_unicos = list(dict.fromkeys(ids_archivos))
    if not ids_unicos:
        return {"catalogos": [], "ids_no_encontrados": []}

    with cursor_rag() as cursor:
        cursor.execute(
            """
            SELECT id_archivo, nombre, ruta
              FROM archivos_subidos
             WHERE id_archivo = ANY(%s)
             ORDER BY id_archivo
               FOR UPDATE
            """,
            (ids_unicos,),
        )
        filas = cursor.fetchall()
        por_id = {fila["id_archivo"]: fila for fila in filas}
        ids_existentes = [id_archivo for id_archivo in ids_unicos if id_archivo in por_id]
        ids_no_encontrados = [
            id_archivo for id_archivo in ids_unicos if id_archivo not in por_id
        ]
        if not ids_existentes:
            return {"catalogos": [], "ids_no_encontrados": ids_no_encontrados}

        productos_por_archivo = _retirar_archivos_y_ofertas(
            cursor, ids_existentes
        )

        cursor.execute(
            """
            DELETE FROM archivos_subidos
             WHERE id_archivo = ANY(%s)
            RETURNING id_archivo
            """,
            (ids_existentes,),
        )
        eliminados = {fila["id_archivo"] for fila in cursor.fetchall()}
        catalogos = [
            {
                "id_archivo": id_archivo,
                "nombre": por_id[id_archivo]["nombre"],
                "ruta_original": por_id[id_archivo]["ruta"],
                "productos_eliminados": productos_por_archivo.get(id_archivo, 0),
            }
            for id_archivo in ids_existentes
            if id_archivo in eliminados
        ]
        return {
            "catalogos": catalogos,
            "ids_no_encontrados": ids_no_encontrados,
        }


def insertar_o_actualizar_productos(
    id_archivo: int, productos: Iterable[dict[str, Any]]
) -> int:
    """Actualiza el catalogo sin modificar existencias ni conservar vectores obsoletos."""
    productos = list(productos)
    if not productos:
        return 0

    with cursor_rag() as cursor:
        return _insertar_productos_en_cursor(cursor, id_archivo, productos)


def _insertar_productos_en_cursor(
    cursor: RealDictCursor,
    id_archivo: int,
    productos: list[dict[str, Any]],
) -> int:
    cursor.execute(
        "SELECT id_proveedor FROM archivos_subidos WHERE id_archivo = %s",
        (id_archivo,),
    )
    archivo = cursor.fetchone()
    id_proveedor = archivo["id_proveedor"] if archivo else None
    filas = [
        (
            id_archivo,
            id_proveedor,
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
            (id_archivo, id_proveedor, codigo, nombre, marca, precio, iva,
             descuentos, descripcion)
        VALUES %s
        ON CONFLICT (codigo) DO UPDATE SET
            id_archivo = EXCLUDED.id_archivo,
            id_proveedor = COALESCE(EXCLUDED.id_proveedor, productos.id_proveedor),
            nombre = EXCLUDED.nombre,
            marca = EXCLUDED.marca,
            precio = EXCLUDED.precio,
            iva = 16.00,
            descuentos = EXCLUDED.descuentos,
            descripcion = EXCLUDED.descripcion,
            descripcion_vectorial = CASE
                WHEN (productos.id_proveedor, productos.nombre, productos.marca,
                      productos.descripcion)
                     IS DISTINCT FROM
                     (COALESCE(EXCLUDED.id_proveedor, productos.id_proveedor),
                      EXCLUDED.nombre, EXCLUDED.marca, EXCLUDED.descripcion)
                THEN NULL
                ELSE productos.descripcion_vectorial
            END
    """
    execute_values(cursor, sql, filas, page_size=500)
    return len(filas)


def insertar_o_actualizar_ofertas(
    id_archivo: int, productos: Iterable[dict[str, Any]]
) -> int:
    """Guarda la cotizacion del proveedor sin confundirla con stock propio."""
    productos = list(productos)
    if not productos:
                return 0

    with cursor_rag() as cursor:
                return _insertar_ofertas_en_cursor(cursor, id_archivo, productos)


def _insertar_ofertas_en_cursor(
    cursor: RealDictCursor,
    id_archivo: int,
    productos: list[dict[str, Any]],
) -> int:
    cursor.execute(
                """
                SELECT id_proveedor, moneda
                  FROM archivos_subidos
                 WHERE id_archivo = %s
                """,
                (id_archivo,),
    )
    archivo = cursor.fetchone()
    if not archivo or archivo["id_proveedor"] is None:
                return 0

    codigos = [producto["codigo"] for producto in productos]
    cursor.execute(
                "SELECT id, codigo FROM productos WHERE codigo = ANY(%s)",
                (codigos,),
    )
    ids_producto = cursor.fetchall()
    id_por_codigo = {fila["codigo"]: fila["id"] for fila in ids_producto}
    valores = [
        (
            id_por_codigo[producto["codigo"]],
            archivo["id_proveedor"],
            producto["codigo"],
            producto["precio"],
            archivo["moneda"],
            producto.get("iva_oferta", Decimal("0.00")),
            producto.get("iva_incluido"),
            producto.get("descuento_oferta"),
            producto.get("cantidad_disponible_proveedor"),
            producto.get("politica_ventas"),
            (
                None
                if producto.get("cantidad_disponible_proveedor") is None
                else producto["cantidad_disponible_proveedor"] > 0
            ),
            id_archivo,
        )
        for producto in productos
        if producto["codigo"] in id_por_codigo
    ]
    if len(valores) != len(productos):
        raise ValueError(
            "No se pudo asociar cada fila de la cotizacion con su producto guardado"
        )

    sql_ofertas = """
        INSERT INTO producto_proveedor
            (id_producto, id_proveedor, codigo_proveedor, precio, moneda, iva,
             iva_incluido, descuento, cantidad_disponible_proveedor,
             politica_ventas, disponible, id_archivo, fecha_cotizacion)
        VALUES %s
        ON CONFLICT (id_producto, id_proveedor) DO UPDATE SET
            codigo_proveedor = EXCLUDED.codigo_proveedor,
            precio = EXCLUDED.precio,
            moneda = EXCLUDED.moneda,
            iva = EXCLUDED.iva,
            iva_incluido = EXCLUDED.iva_incluido,
            descuento = EXCLUDED.descuento,
            cantidad_disponible_proveedor = EXCLUDED.cantidad_disponible_proveedor,
            politica_ventas = EXCLUDED.politica_ventas,
            disponible = EXCLUDED.disponible,
            id_archivo = EXCLUDED.id_archivo,
            fecha_cotizacion = EXCLUDED.fecha_cotizacion,
            actualizado_en = NOW()
        RETURNING id, precio, moneda, iva, iva_incluido, descuento,
                  cantidad_disponible_proveedor, politica_ventas, id_archivo
    """
    ofertas = execute_values(
        cursor,
        sql_ofertas,
        valores,
        template=(
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)"
        ),
        page_size=500,
        fetch=True,
    )
    historial = [
        (
            oferta["id"],
            oferta["precio"],
            oferta["moneda"],
            oferta["iva"],
            oferta["iva_incluido"],
            oferta["descuento"],
            oferta["cantidad_disponible_proveedor"],
            oferta["politica_ventas"],
            oferta["id_archivo"],
        )
        for oferta in ofertas
    ]
    execute_values(
        cursor,
        """
        INSERT INTO historial_precios
            (id_oferta, precio, moneda, iva, iva_incluido, descuento,
             cantidad_disponible_proveedor, politica_ventas, id_archivo)
        VALUES %s
        """,
        historial,
        page_size=500,
    )
    return len(ofertas)


def insertar_catalogo_completo(
    id_archivo: int,
    productos: Iterable[dict[str, Any]],
    *,
    guardar_ofertas: bool,
) -> tuple[int, int]:
    """Guarda productos y ofertas en una sola transaccion."""
    productos = list(productos)
    if not productos:
        return 0, 0

    with cursor_rag() as cursor:
        filas_guardadas = _insertar_productos_en_cursor(
            cursor, id_archivo, productos
        )
        ofertas_guardadas = (
            _insertar_ofertas_en_cursor(cursor, id_archivo, productos)
            if guardar_ofertas
            else 0
        )
        if guardar_ofertas and ofertas_guardadas != len(productos):
            raise ValueError(
                "No se guardaron todas las ofertas del catalogo del proveedor"
            )
    return filas_guardadas, ofertas_guardadas


def contar_productos_de_archivo(id_archivo: int) -> int:
    """Cuenta los productos que quedaron asociados a un catalogo."""
    fila = consultar_uno(
        "SELECT COUNT(*) AS total FROM productos WHERE id_archivo = %s",
        (id_archivo,),
        rag=True,
    )
    return int(fila["total"]) if fila else 0


def contar_productos_sin_embedding() -> int:
    """Productos del catalogo que aun no tienen vector de busqueda."""
    fila = consultar_uno(
        "SELECT COUNT(*) AS total FROM productos "
        "WHERE descripcion_vectorial IS NULL",
        rag=True,
    )
    return int(fila["total"]) if fila else 0


def contar_productos_catalogo() -> int:
    """Total de productos del catalogo, con o sin vector."""
    fila = consultar_uno("SELECT COUNT(*) AS total FROM productos", rag=True)
    return int(fila["total"]) if fila else 0


_COLUMNAS_ORDEN_BUSCADOR = {
    "codigo": "p.codigo",
    "nombre": "p.nombre",
    "proveedor": "pr.nombre",
    "precio": "p.precio",
    "stock": "p.stock",
}


def _orden_sql_busqueda(
    ordenar_por: str | None,
    direccion: str,
    orden_predeterminado: str,
) -> str:
    if direccion not in ("asc", "desc"):
        raise ValueError("La direccion de orden debe ser 'asc' o 'desc'")
    if ordenar_por is None:
        return orden_predeterminado
    columna = _COLUMNAS_ORDEN_BUSCADOR.get(ordenar_por)
    if columna is None:
        raise ValueError(f"Columna de orden no permitida: {ordenar_por}")
    return f"{columna} {direccion.upper()} NULLS LAST, p.id ASC"


def listar_productos_catalogo(
    limite: int,
    desplazamiento: int,
    ordenar_por: str | None = None,
    direccion: str = "asc",
) -> tuple[list[dict[str, Any]], int]:
    """Lista productos activos en orden estable y devuelve el total exacto."""
    orden_sql = _orden_sql_busqueda(
        ordenar_por, direccion, "p.nombre ASC, p.id ASC"
    )
    with cursor_rag(commit=False) as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM productos WHERE activo")
        fila = cursor.fetchone()
        total = int(fila["total"]) if fila else 0
        if total == 0 or desplazamiento >= total:
            return [], total

        cursor.execute(
            f"""
            SELECT p.id, p.codigo, p.nombre, p.marca,
                   c.nombre AS categoria, pr.nombre AS proveedor,
                   p.descripcion, p.presentacion,
                   p.precio, p.iva, p.descuentos, p.stock, p.moneda
              FROM productos AS p
              LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
              LEFT JOIN proveedores AS pr ON pr.id_proveedores = p.id_proveedor
             WHERE p.activo
              ORDER BY {orden_sql}
             LIMIT %s OFFSET %s
            """,
            (limite, desplazamiento),
        )
        return list(cursor.fetchall()), total


def productos_sin_embedding(limite: int) -> list[dict[str, Any]]:
    """Obtiene productos y datos reales del proveedor para construir su embedding."""
    return consultar_todos(
        """
        SELECT p.id, p.codigo, p.nombre, p.marca, p.descripcion,
               c.nombre AS categoria, p.unidad_medida, p.presentacion,
               pr.nombre AS proveedor
          FROM productos AS p
          LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
          LEFT JOIN proveedores AS pr ON pr.id_proveedores = p.id_proveedor
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
        SELECT p.id, p.codigo, p.nombre, p.marca, c.nombre AS categoria,
               p.descripcion, p.precio, p.iva, p.stock,
               1 - (p.descripcion_vectorial <=> %s::vector(384)) AS similitud
          FROM productos AS p
          LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
         WHERE p.descripcion_vectorial IS NOT NULL
         ORDER BY p.descripcion_vectorial <=> %s::vector(384), p.id
         LIMIT %s
        """,
        (vector_texto, vector_texto, limite),
        rag=True,
    )


def _escapar_ilike(texto: str) -> str:
    """Escapa los comodines de ILIKE para que el texto se compare literal."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _condiciones_busqueda(consulta: str) -> tuple[str, tuple[str, ...]]:
    """Arma el WHERE compartido por el conteo y el listado del buscador.

    El texto del usuario nunca se concatena en la sentencia: viaja siempre
    como parametro ``%s``, asi que comillas, comodines o intentos de inyeccion
    quedan tratados como texto a buscar y no alteran la consulta.
    """
    patron = "%" + _escapar_ilike(consulta) + "%"
    condicion = """
        p.activo
        AND (p.texto_busqueda @@ plainto_tsquery('spanish', %s)
             OR p.nombre ILIKE %s
             OR p.codigo ILIKE %s
             OR p.marca ILIKE %s
             OR p.descripcion ILIKE %s
             OR pr.nombre ILIKE %s
             OR c.nombre ILIKE %s)
    """
    coincidencias = (consulta, patron, patron, patron, patron, patron, patron)
    return condicion, coincidencias


def buscar_productos_fulltext(
    consulta: str,
    limite: int,
    desplazamiento: int = 0,
    ordenar_por: str | None = None,
    direccion: str = "asc",
) -> tuple[list[dict[str, Any]], int]:
    """Busca productos con Full-Text Search nativo de PostgreSQL (RF-03).

    Todo lo hace la base de datos: el ``tsvector`` en espanol de la migracion
    9_0 con ``plainto_tsquery``, mas ``ILIKE`` como respaldo para busquedas
    parciales de codigo o proveedor. Aqui no participa ningun modelo de IA ni
    hay latencia de red hacia un proveedor externo: la respuesta sale de los
    indices GIN en milisegundos.

    Devuelve ``(filas, total)``; ``total`` cuenta todas las coincidencias
    antes de aplicar el orden y la pagina. Sin coincidencias la respuesta es
    ``([], 0)``, que es un resultado valido y no un error.
    """
    orden_predeterminado = """
        CASE WHEN p.codigo ILIKE %s THEN 0 ELSE 1 END,
        CASE WHEN p.nombre ILIKE %s THEN 0 ELSE 1 END,
        relevancia DESC, p.nombre ASC, p.id ASC
    """
    orden_sql = _orden_sql_busqueda(
        ordenar_por, direccion, orden_predeterminado
    )
    condicion, coincidencias = _condiciones_busqueda(consulta)
    exacto = _escapar_ilike(consulta)
    prefijo = exacto + "%"

    with cursor_rag(commit=False) as cursor:
        cursor.execute(
            f"""
            SELECT count(*) AS total
              FROM productos AS p
              LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
              LEFT JOIN proveedores AS pr ON pr.id_proveedores = p.id_proveedor
             WHERE {condicion}
            """,
            coincidencias,
        )
        fila = cursor.fetchone()
        total = int(fila["total"]) if fila else 0
        if total == 0:
            return [], 0

        cursor.execute(
            f"""
            SELECT p.id, p.codigo, p.nombre, p.marca,
                   c.nombre AS categoria, pr.nombre AS proveedor,
                   p.descripcion, p.presentacion,
                   p.precio, p.iva, p.descuentos, p.stock, p.moneda,
                   ts_rank(p.texto_busqueda,
                           plainto_tsquery('spanish', %s)) AS relevancia
              FROM productos AS p
              LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
              LEFT JOIN proveedores AS pr ON pr.id_proveedores = p.id_proveedor
             WHERE {condicion}
             ORDER BY {orden_sql}
             LIMIT %s OFFSET %s
            """,
            (
                consulta,
                *coincidencias,
                *((exacto, prefijo) if ordenar_por is None else ()),
                limite,
                desplazamiento,
            ),
        )
        return list(cursor.fetchall()), total


def obtener_detalle_producto(id_producto: int) -> dict[str, Any] | None:
    """Consulta la ficha, proveedor, catalogo de origen y ofertas activas."""
    fila = consultar_uno(
        """
        SELECT p.id, p.codigo, p.codigo_interno, p.nombre, p.marca,
               c.nombre AS categoria, p.descripcion, p.unidad_medida,
               p.presentacion, p.precio, p.moneda, p.iva, p.descuentos,
               p.stock, p.punto_reorden, p.ubicacion, p.actualizado_en,
               pr.id_proveedores AS proveedor_id,
               pr.nombre AS proveedor_nombre, pr.rif AS proveedor_rif,
               pr.direccion AS proveedor_direccion,
               pr.telefono AS proveedor_telefono, pr.correo AS proveedor_correo,
               COALESCE(pr.vendedor, a.vendedor_nombre) AS proveedor_vendedor,
               COALESCE(pr.telefono_vendedor, a.vendedor_telefono)
                   AS proveedor_telefono_vendedor,
               COALESCE(pr.correo_vendedor, a.vendedor_correo)
                   AS proveedor_correo_vendedor,
               COALESCE(pr.moneda, a.moneda) AS proveedor_moneda,
               a.id_archivo AS catalogo_id, a.nombre AS catalogo_nombre,
               a.tipo AS catalogo_tipo, a.fecha_de_subida AS catalogo_fecha,
               a.estado AS catalogo_estado, a.filas_ok AS catalogo_filas_ok,
               a.filas_error AS catalogo_filas_error,
               a.moneda AS catalogo_moneda,
               a.nota_proveedor AS catalogo_nota_proveedor,
               a.vendedor_nombre AS catalogo_vendedor,
               a.vendedor_telefono AS catalogo_telefono_vendedor,
               a.vendedor_correo AS catalogo_correo_vendedor
          FROM productos AS p
          LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
          LEFT JOIN archivos_subidos AS a ON a.id_archivo = p.id_archivo
          LEFT JOIN proveedores AS pr
            ON pr.id_proveedores = COALESCE(p.id_proveedor, a.id_proveedor)
         WHERE p.id = %s AND p.activo
        """,
        (id_producto,),
        rag=True,
    )
    if not fila:
        return None

    producto = {
        campo: fila[campo]
        for campo in (
            "id", "codigo", "codigo_interno", "nombre", "marca", "categoria",
            "descripcion", "unidad_medida", "presentacion", "precio", "moneda",
            "iva", "descuentos", "stock", "punto_reorden", "ubicacion",
            "actualizado_en",
        )
    }
    proveedor = None
    if fila["proveedor_id"] is not None:
        proveedor = {
            "id": fila["proveedor_id"],
            "nombre": fila["proveedor_nombre"],
            "rif": fila["proveedor_rif"],
            "direccion": fila["proveedor_direccion"],
            "telefono": fila["proveedor_telefono"],
            "correo": fila["proveedor_correo"],
            "vendedor": fila["proveedor_vendedor"],
            "telefono_vendedor": fila["proveedor_telefono_vendedor"],
            "correo_vendedor": fila["proveedor_correo_vendedor"],
            "moneda": fila["proveedor_moneda"],
        }
    catalogo = None
    if fila["catalogo_id"] is not None:
        catalogo = {
            "id": fila["catalogo_id"],
            "nombre": fila["catalogo_nombre"],
            "tipo": fila["catalogo_tipo"],
            "fecha_de_subida": fila["catalogo_fecha"],
            "estado": fila["catalogo_estado"],
            "filas_ok": fila["catalogo_filas_ok"],
            "filas_error": fila["catalogo_filas_error"],
            "moneda": fila["catalogo_moneda"],
            "nota_proveedor": fila["catalogo_nota_proveedor"],
            "vendedor": fila["catalogo_vendedor"],
            "telefono_vendedor": fila["catalogo_telefono_vendedor"],
            "correo_vendedor": fila["catalogo_correo_vendedor"],
        }
    ofertas = consultar_todos(
        """
        SELECT o.id, pr.nombre AS proveedor, o.codigo_proveedor, o.precio,
               o.moneda, o.iva, o.iva_incluido, o.descuento,
               o.cantidad_disponible_proveedor, o.politica_ventas,
               o.plazo_entrega_dias, o.cantidad_minima, o.disponible,
               o.fecha_cotizacion, a.nombre AS catalogo
          FROM producto_proveedor AS o
          JOIN proveedores AS pr ON pr.id_proveedores = o.id_proveedor
          LEFT JOIN archivos_subidos AS a ON a.id_archivo = o.id_archivo
         WHERE o.id_producto = %s
         ORDER BY o.es_preferido DESC, o.precio, pr.nombre
        """,
        (id_producto,),
        rag=True,
    )
    return {
        "producto": producto,
        "proveedor": proveedor,
        "catalogo": catalogo,
        "ofertas": ofertas,
    }


def listar_archivos(limite: int = 100) -> list[dict[str, Any]]:
    """Devuelve los lotes mas recientes sin incluir rutas internas ni hashes."""
    return consultar_todos(
        """
        SELECT a.id_archivo, a.nombre, a.tipo, a.fecha_de_subida, a.tamano_bytes,
               a.estado, a.filas_ok, a.filas_error, a.detalle, a.moneda,
               a.vendedor_nombre AS vendedor, p.nombre AS proveedor
          FROM archivos_subidos AS a
          LEFT JOIN proveedores AS p ON p.id_proveedores = a.id_proveedor
         ORDER BY fecha_de_subida DESC, id_archivo DESC
         LIMIT %s
        """,
        (limite,),
        rag=True,
    )