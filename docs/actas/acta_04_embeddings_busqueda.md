# Semana 4 — Registro preliminar de embeddings y búsqueda

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario con Inteligencia Artificial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Etapa** | Preparación técnica del piloto local |
| **Estado** | Implementación lista; validación con catálogo real pendiente |

> Este registro preliminar no sustituye el Acta 4 final de rendimiento. Luego
> de la prueba técnica inicial, el usuario aplicó la migración `4_0` en su
> desarrollo y vectorizó un producto real. Los resultados se identifican abajo
> como reportados por el usuario; la relevancia general sigue pendiente.

## 1. Implementación preparada

- Modelo gratuito local: `intfloat/multilingual-e5-small`, ejecutado por
  FastEmbed/ONNX. Los textos del catálogo permanecen en el entorno local.
- Vectores normalizados de 384 dimensiones; prefijo `passage:` para productos
  y `query:` para consultas.
- Búsqueda por distancia coseno `<=>` con índice HNSW.
- Migración incremental `4_0`: solo cambia la columna si todos los vectores
  existentes están vacíos; si detecta vectores antiguos de 1536 dimensiones,
  aborta sin convertirlos.
- Comandos manuales para vectorizar una muestra y consultar productos. No hay
  vectorización automática al arrancar la API.
- El usuario confirmó que `4_0` se aplicó correctamente en `ferreteria_rag` y
  que el contenedor `api_ferreteria` quedó saludable en el puerto 8000.

## 2. Prueba técnica local

La prueba se ejecutó en la imagen Python 3.12 con pesos ya descargados y textos
de productos sintéticos, sin conexión a la base del usuario.

| Medición | Resultado |
|---|---|
| Dimensión devuelta | 384 |
| Consultas sintéticas | 4 |
| Producto esperado en posición 1 | 3 de 4 |
| Consultas en lote (4), con modelo cargado | 162,5 ms |
| Carga del modelo y vectorización de 4 pasajes, caché descargada | 16,0 s |

En la consulta «broca para mampostería», el modelo priorizó un taladro percutor;
la broca relacionada quedó más abajo. Por ello, estos datos demuestran que la
inferencia funciona, pero **no bastan para declarar la relevancia aprobada**.
El tiempo incluye la carga de pesos desde la caché local, no es latencia de
búsqueda SQL.

## 3. Prueba reportada en el catálogo de desarrollo

El usuario ejecutó la vectorización de un lote de 10 y la búsqueda desde el
contenedor. La base tenía un solo producto pendiente; por eso el proceso
actualizó una fila.

```text
docker compose exec api python scripts/vectorizar_catalogo.py --lote 10
Encontrados: 1; vectorizados: 1
```

Consulta ejecutada:

```text
docker compose exec api python scripts/buscar_productos_vectorial.py "consulta sobre un producto"
```

Resultado informado:

| Código | Producto | Similitud |
|---|---|---:|
| `PRUEBA-ETL-001` | Producto de prueba | 0.8489258289337158 |

Esto confirma que el embedding se guardó y pgvector devolvió un producto, pero
con un solo candidato y una consulta genérica **no mide relevancia comparativa**.

### Consultas de seguimiento y límites funcionales

Se propusieron consultas más específicas para comprobar con un catálogo de
prueba que contenga esos artículos. No hay confirmación de que estas consultas
se hayan ejecutado todavía:

- «Producto de prueba»
- «taladro para concreto»
- «necesito hacer un agujero en una pared de cemento»
- «quiero pintar una habitación de blanco»
- «herramienta para apretar una tuerca»

La pregunta «¿a qué proveedor puedo comprar los taladros más rápido?» no es
evaluable con el prototipo: no se han cargado plazos de entrega ni relaciones
de proveedor por producto para comparar. La búsqueda vectorial actual recupera
productos parecidos; no calcula disponibilidad ni rapidez de proveedores.

## 4. Pruebas automáticas

- Suite completa: **378 pasaron, 1 omitida**, 200,83 s.
- Integración de pgvector en base desechable: columna `vector(384)`, escritura
  de vectores, protección contra reescritura y orden por similitud coseno.
- Estrés de Semana 3: **20 archivos / 5000 productos** dentro del umbral
  establecido de 4,25 s.
- La suite reportó un aviso de obsolescencia de `starlette.testclient` con
  `httpx`; no afectó los resultados.

## 5. Siguiente paso

La migración `4_0` ya fue aplicada por el usuario al catálogo de desarrollo.
Para continuar el piloto, agregue un TXT con varios productos representativos,
vectorice una muestra pequeña y compare consultas específicas:

```powershell
docker compose exec api python scripts\vectorizar_catalogo.py --lote 10
docker compose exec api python scripts\buscar_productos_vectorial.py "taladro para concreto"
```

La interfaz web permite cargar esos productos, pero el chat sigue provisional;
para buscar se usa por ahora el comando anterior. Revise relevancia y latencia
antes de ejecutar `vectorizar_catalogo.py --todos`. No cambie de modelo sin
regenerar todos los embeddings: vectores de modelos distintos no se pueden
mezclar.

La integración del chat con el buscador, un modelo generativo, respuestas
restringidas al inventario y defensas contra prompt injection corresponden a la
Semana 5.
