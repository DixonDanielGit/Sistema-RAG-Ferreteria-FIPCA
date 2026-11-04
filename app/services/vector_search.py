"""Vectorizacion controlada y busqueda semantica de productos."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import get_settings
from app.models import inventario as inventario_model
from app.services.embedding_service import ErrorEmbedding, generar_embeddings

logger = logging.getLogger("ferreteria.vectorizacion")

MAX_PRODUCTOS_POR_LOTE = 100
MAX_RESULTADOS_BUSQUEDA = 20
MAX_LONGITUD_PREGUNTA = 2000
# Sin avance en dos paginas seguidas se detiene el bucle: otra sesion ya
# vectorizo esas filas o ninguna fila del lote tenia campos indexables.
MAX_SIN_AVANCE = 2


def _dato(valor: Any) -> str:
    """Normaliza un campo del producto para componer el texto de indexacion."""
    if valor is None:
        return ""
    return " ".join(str(valor).split()).strip()


def crear_texto_producto(producto: dict[str, Any]) -> str:
    """Construye el texto del catalogo usado para indexar el producto.

    Solo se indexan datos reales de la fila: el texto nunca inventa campos ni
    precios. Varios catalogos de proveedores no traen descripcion del producto
    y, sin descripcion, el fragmento quedaba como una lista de etiquetas
    dificil de relacionar con una pregunta. En ese caso se arma una *ficha de
    plantilla* con datos reales (nombre, marca, categoria, presentacion, unidad,
    proveedor y codigo) para que el asistente pueda encontrarlo.

    La plantilla se usa unicamente para la busqueda: no se guarda en
    ``productos.descripcion`` ni aparenta ser texto escrito por el proveedor.
    Campos volatiles (precio, stock, descuentos) se excluyen a proposito:
    cambian en cada carga y el precio llega al modelo desde la base en vivo.
    """
    codigo = _dato(producto.get("codigo"))
    nombre = _dato(producto.get("nombre"))
    marca = _dato(producto.get("marca"))
    categoria = _dato(producto.get("categoria"))
    descripcion = _dato(producto.get("descripcion"))
    unidad = _dato(producto.get("unidad_medida"))
    presentacion = _dato(producto.get("presentacion"))
    proveedor = _dato(producto.get("proveedor"))

    campos = [
        ("Codigo", codigo),
        ("Producto", nombre),
        ("Marca", marca),
        ("Categoria", categoria),
        ("Presentacion", presentacion),
        ("Unidad", unidad),
        ("Proveedor", proveedor),
        ("Descripcion", descripcion),
    ]
    texto = ". ".join(
        f"{etiqueta}: {valor}" for etiqueta, valor in campos if valor
    ).strip()
    if descripcion or not nombre:
        return texto

    ficha = [nombre]
    if marca:
        ficha.append(f"marca {marca}")
    if categoria:
        ficha.append(f"categoria {categoria}")
    if presentacion:
        ficha.append(f"presentacion {presentacion}")
    if unidad:
        ficha.append(f"unidad {unidad}")
    if proveedor:
        ficha.append(f"proveedor {proveedor}")
    if codigo:
        ficha.append(f"codigo {codigo}")
    return f"Ficha de producto: {', '.join(ficha)}."


def vectorizar_productos_pendientes(limite: int = 25) -> dict[str, int]:
    """Vectoriza una pagina de productos sin embedding y guarda solo filas vigentes."""
    if not 1 <= limite <= MAX_PRODUCTOS_POR_LOTE:
        raise ValueError(
            f"El limite debe estar entre 1 y {MAX_PRODUCTOS_POR_LOTE}"
        )

    productos = inventario_model.productos_sin_embedding(limite)
    if not productos:
        return {"encontrados": 0, "actualizados": 0}

    # Un producto sin ningun campo indexable no puede vectorizarse: se deja
    # fuera del lote en lugar de romper la vectorizacion de todos los demas.
    seleccionados: list[dict[str, Any]] = []
    textos: list[str] = []
    for producto in productos:
        texto = crear_texto_producto(producto)
        if texto:
            seleccionados.append(producto)
            textos.append(texto)
    if not seleccionados:
        return {"encontrados": len(productos), "actualizados": 0}

    vectores = generar_embeddings(textos, tipo="passage")
    filas = [
        (producto["id"], vector)
        for producto, vector in zip(seleccionados, vectores, strict=True)
    ]
    actualizados = inventario_model.guardar_embeddings(filas)
    return {"encontrados": len(productos), "actualizados": actualizados}


# Un solo hilo de vectorizacion automatica a la vez: la subida del cliente
# envia varios archivos en secuencia y cada uno lanzaria su propio bucle.
_candado_automatica = threading.Lock()
_estado_automatica = {"en_curso": False}


def vectorizacion_en_curso() -> bool:
    """True mientras un lote automatico este indexando productos."""
    return _estado_automatica["en_curso"]


def _bucle_vectorizacion() -> None:
    """Pagina los pendientes hasta dejar el catalogo cubierto."""
    sin_avance = 0
    try:
        while True:
            resultado = vectorizar_productos_pendientes(MAX_PRODUCTOS_POR_LOTE)
            if resultado["encontrados"] == 0:
                return
            if resultado["actualizados"] == 0:
                sin_avance += 1
                if sin_avance >= MAX_SIN_AVANCE:
                    logger.warning(
                        "Vectorizacion automatica detenida: %d producto(s) "
                        "pendientes sin avance en dos paginas",
                        resultado["encontrados"],
                    )
                    return
            else:
                sin_avance = 0
    except ErrorEmbedding as exc:
        # Sin FastEmbed (venv de Python 3.15) la ingesta no puede indexar:
        # se avisa y los productos quedan pendientes para el script manual.
        logger.warning("Vectorizacion automatica no disponible: %s", exc)
    except Exception:
        logger.exception("Fallo la vectorizacion automatica del catalogo")
    finally:
        _estado_automatica["en_curso"] = False
        _candado_automatica.release()


def lanzar_vectorizacion_automatica() -> bool:
    """Indexa los productos pendientes en un hilo de fondo.

    Se invoca al terminar una ingesta exitosa para que el panel de fuentes
    no quede marcando pendientes hasta que alguien recuerde correr el
    script manual. Devuelve False si ya hay un lote en curso o si la
    vectorizacion automatica esta desactivada en la configuracion.
    """
    if not get_settings().vectorizacion_automatica:
        return False
    if not _candado_automatica.acquire(blocking=False):
        return False
    _estado_automatica["en_curso"] = True
    try:
        threading.Thread(
            target=_bucle_vectorizacion,
            name="vectorizacion-catalogo",
            daemon=True,
        ).start()
    except BaseException:
        _estado_automatica["en_curso"] = False
        _candado_automatica.release()
        raise
    return True


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