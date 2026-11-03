# Auditoría del esquema de datos para el asistente RAG

**Sistema:** FERRE-INVERSIONES PEREZ C.A. — inventario + asistente RAG
**Alcance:** base `ferreteria_rag` (`init.sql`), motor de ingesta
(`app/services/etl_service.py`), acceso a datos (`app/models/inventario.py`) y
búsqueda vectorial (`app/services/vector_search.py`).
**Fecha:** noviembre de 2026.
**Flujo de negocio:** la ferretería recibe catálogos/cotizaciones que sus
proveedores le envían; personal de la ferretería registra cada archivo y
consulta esa información para comparar opciones. Subir un catálogo **no**
significa que la ferretería haya comprado o recibido esos productos.
**Estado:** el esquema y el flujo de ingesta se actualizaron para asociar cada
archivo con su proveedor y vendedor, guardar la moneda, la nota y las ofertas
extraídas. `init.sql` cubre instalaciones nuevas; la migración `7_0` es
idempotente para instalaciones existentes. No se aplicó a la base de desarrollo
durante estos cambios.

---

## 1. Resumen ejecutivo

El uso principal es consultar los **catálogos recibidos de los proveedores**.
Cada archivo debe conservar su proveedor de origen, vigencia y condiciones de
precio. No se debe tratar una cotización como una compra ni como una entrada de
inventario. El esquema actual conserva el archivo, pero el ETL consolida los
productos por un código global y sobrescribe el precio al volver a cargar ese
código; así se pueden mezclar o perder ofertas de distintos proveedores.

| # | Pregunta | ¿Con los catálogos? | Qué dato responde y qué no |
|---|---|---|---|
| 1 | ¿Quién ofrece el precio más bajo y quién entrega más rápido? | **Parcial** | El precio se compara solo después de atribuir cada archivo a un proveedor, identificar que las filas corresponden al mismo producto, y normalizar moneda, unidad e IVA. El plazo solo puede contestarse si el proveedor lo informó o la ferretería lo registró; no se deduce del catálogo. |
| 2 | ¿Qué proveedor ofrece, en promedio, los mejores martillos? | **Depende de “mejores”** | Con cotizaciones se puede promediar el precio comparable de los martillos identificados por proveedor. Calidad, puntualidad y “quién me ha surtido” requieren compras/recepciones y evaluaciones; un catálogo no prueba que se haya comprado ni recibido un artículo. |
| 3 | ¿Qué productos se están acabando? | **No a partir del catálogo** | El catálogo de proveedor informa oferta, no existencias propias. Se necesita el stock operativo actualizado; para calcular cuándo se agotará, también movimientos de salida/consumo. |

Además, la búsqueda vectorial devuelve el *top-k* por similitud de coseno: sirve
para "encuentra productos parecidos a esta frase", no para agregar, comparar ni
ordenar por precio o plazo. Las tres preguntas son **consultas de negocio** y
deben resolverse con SQL sobre datos estructurados; el vector solo debe ayudar a
identificar el producto cuando el usuario lo nombra de forma imprecisa.

**Criterio implementado:** modelar explícitamente cada archivo como cotización
de un proveedor, guardar por separado las ofertas y no tocar el stock propio.
Los productos se concilian todavía por el código global existente; conservar
todas las filas originales no interpretables y revisar equivalencias entre
códigos siguen siendo trabajo pendiente. Compras,
evaluaciones y movimientos de stock son módulos adicionales: solo sirven si la
ferretería realmente registra esos hechos en el sistema o los integra desde
otro sistema.

El RAG puede encontrar el producto por significado; los precios, promedios y
alertas deben calcularse con consultas SQL sobre datos estructurados y
trazables.

---

## 2. Cómo se hizo la revisión

1. Lectura del esquema real (`init.sql`), del modelo de datos
   (`app/models/inventario.py`) y del contrato del chat
   (`app/api/v1/rag_chat.py`).
2. Verificación del contrato ETL antes y después de los cambios: el producto
   interno conserva su contrato actual; la oferta del proveedor guarda además
   IVA informado (0 % cuando no se detecta), moneda, descuento opcional,
   cantidad disponible y política de ventas.
3. Revisión de catálogos de muestra para comprobar formatos y casos de códigos
   repetidos, precios ausentes y monedas/columnas múltiples.
4. Revisión de la migración `7_0`, el endpoint y la persistencia de ofertas.
   Las consultas SQL del chat todavía no están integradas.
5. La base de desarrollo no se modificó. Se requiere aplicar la migración y
   verificar la carga del piloto sobre la copia real de cada catálogo.

---

## 3. Esquema actual y flujo de datos

```
proveedor ──1:N── catálogo recibido (archivo)
                       └── filas originales/revisables
                              └── oferta vigente ── producto interno
productos ── stock operativo (otra fuente; el catálogo no lo actualiza)
productos ── embedding vector(384) ── HNSW
```

Lo que el esquema y el código actuales hacen:

- Buscar un producto por nombre, marca o descripción (`pg_trgm`).
- Ordenar por similitud semántica con una pregunta (`<=>` de pgvector).
- Guardar el original y extraer filas que cumplen las reglas del parser.
- Asociar cada archivo a un proveedor y guardar el vendedor, moneda y nota
  declarados en la confirmación de carga. En una selección de varios archivos,
  cada uno lleva sus propios metadatos.
- Hacer *upsert* en `productos` por `codigo` y guardar la oferta por separado
  en `producto_proveedor`, con historial de precios y condiciones detectadas.
- Mantener `stock` aparte de la ingesta del catálogo: subir una lista de precios
  no debe aumentar ni disminuir existencias.

Lo que aún no demuestra: que una fila pertenece a un proveedor concreto, que
dos códigos distintos son el mismo producto, o qué cantidad de stock hay
realmente. El USD es la moneda inicial en la pantalla, pero el usuario puede
seleccionar VES. El parser toma el porcentaje de IVA solo cuando lo reconoce;
si no, la oferta se guarda como sin IVA (0 %) según la regla solicitada. Esto
no cambia el IVA fijo de 16 % del registro interno `productos`. El chat todavía
no usa las ofertas para comparar precios.

### Caso comprobado: ficha del catálogo GAC

Se verificó el PDF `catalogos_de_prueba/GAC .pdf` con la ficha:

```text
Abrazadera de riego 90mm x 1-1/2"
Precio: $ 10,61
SKU: G0800000197
Política ventas:
Cantidad Disp.: 43
Marca: Imp
```

El lector reconoce el nombre, SKU, precio y marca. La fila que llega al modelo
actual queda como `codigo=G0800000197`, el nombre indicado, `marca=Imp` y
`precio=10.61`; no conserva `Cantidad Disp.: 43` ni el texto de política. En
esta ficha el valor de política está vacío, pero las políticas con contenido
tampoco tienen una columna ni se escriben en la base. El símbolo `$` no basta
para confirmar formalmente la moneda, y la ficha no dice si el precio incluye
IVA.

La cantidad 43 es **disponibilidad declarada por el proveedor**, no
`productos.stock` de la ferretería. El lector de fichas y la oferta ahora pueden
conservarla en `producto_proveedor.cantidad_disponible_proveedor`; la política
detectada se guarda en `politica_ventas`, y la nota general (por ejemplo,
"descuento hasta mañana") queda en `archivos_subidos.nota_proveedor`. La
oferta enlaza el archivo de origen. El campo `descuento` de la oferta es
nullable, para no convertir la ausencia de descuento en un dato inventado.

En una ejecución local previa del extractor combinado sobre el PDF de 178
páginas se obtuvieron 1.575 productos y 4 errores; el cambio de metadatos no
demuestra por sí solo que se procese el 100 %. Como `productos.precio` es
obligatorio, no se inventa el precio de las fichas incompletas. Sigue pendiente
conservar cada fila no importable en una tabla de recepción/revisión y mostrar
su estado y motivo en la vista previa.

---

## 4. Diagnóstico pregunta por pregunta

### 4.1 "¿Cuál es el proveedor más barato y en cuántos días entrega?"

**Veredicto: sí se puede responder usando cotizaciones**, cuando el sistema
conserve la identidad del proveedor, la vigencia, la moneda, la unidad de venta
y la columna de precio elegida. El plazo solo se puede responder si figura en
el catálogo o si la ferretería lo registra; no se debe inferir.

- Hoy la carga no pregunta qué proveedor envió el archivo ni escribe
  `id_proveedor`; el nombre del archivo no es una identidad confiable.
- `productos.precio` guarda un único valor por `codigo`, y la siguiente carga
  puede reemplazarlo. No conserva simultáneamente cotizaciones de proveedores.
- El ETL no registra moneda, IVA incluido/excluido, unidad, vigencia ni plazo
  como atributos de oferta. Un `NUMERIC` por sí solo no permite comparar
  monedas ni precio por pieza frente a precio por paquete.
- `producto_proveedor` y los campos de plazo existen en la propuesta `7_0`,
  pero no están conectados a la carga. Además, su unicidad por
  `(id_producto, id_proveedor)` representa una oferta vigente por pareja; no
  conserva cada fila original del archivo ni resuelve presentaciones distintas.

**Respuesta correcta esperada:** comparar solo ofertas vigentes del mismo
producto y presentación, en la misma moneda (o convertir usando una tasa
fechada) y con el mismo tratamiento de IVA. Mostrar por separado el menor
precio y el menor plazo: pueden corresponder a proveedores distintos.

### 4.2 "¿Cuál es el mejor proveedor en promedio?"

**Veredicto: hay dos preguntas distintas y deben aclararse.**

- Si se refiere a **quién ofrece los martillos con mejor precio promedio**,
  puede calcularse con catálogos comparables, una vez asociadas las ofertas a
  proveedores y homogeneizadas moneda, IVA, unidad y presentación. Debe decirse
  qué período y qué productos entran en el promedio.
- Si se refiere a **quién le ha vendido/surtido mejor históricamente**, un
  catálogo no demuestra una compra ni una entrega. Hace falta registrar órdenes,
  recepciones, cantidades aceptadas y fechas reales.
- “Mejor” no es una métrica única: precio, calidad y puntualidad deben mostrarse
  como indicadores separados o ponderarse con una regla acordada por la
  ferretería. No asignar una calificación que no esté registrada.

Para el primer significado bastan cotizaciones vinculadas a proveedor/producto
y reglas explícitas de comparabilidad. Para el segundo se necesitan
`compras`, `detalle_compra`, fechas de entrega estimadas/reales y, si el negocio
quiere medir calidad percibida, `evaluacion_proveedor`.

### 4.3 "¿Qué se está acabando?"

**Veredicto: no se responde con catálogos de proveedores.** Un catálogo es una
oferta de compra, no el inventario propio de la ferretería.

- `productos.stock` existe, pero el ETL de catálogos lo deja intacto. Es la
  decisión correcta para no confundir disponibilidad del proveedor con
  existencias en depósito.
- Si la ferretería actualiza `stock` desde otro proceso, podría responderse
  “qué está por debajo de un umbral” solo si el dato está vigente y se define el
  umbral. El catálogo no actualiza ese dato.
- Para predecir agotamiento o días de cobertura hacen falta salidas/ventas y
  entradas/ajustes con fecha; para recomendar cuándo reponer, también el plazo
  de reposición del proveedor.

Las tablas `stock_movimientos` y `configuracion_stock` de `7_0` son para una
fase de integración del inventario operativo; no deben poblarse desde una lista
de precios.

---

## 5. Deficiencias transversales encontradas

| # | Hallazgo | Consecuencia | Estado de la propuesta `7_0` |
|---|---|---|---|
| 1 | Históricamente no se guardaba el proveedor que envió cada archivo | No se podía agrupar una cotización por proveedor | Corregido en el flujo nuevo: la carga solicita proveedor y vendedor por archivo, guarda `archivos_subidos.id_proveedor` y conserva los datos de contacto como referencia |
| 2 | `productos.codigo` es `UNIQUE` global y suele venir del proveedor | Los códigos repetidos colisionan y los códigos distintos de un mismo producto no se emparejan solos | `codigo_interno` y `producto_proveedor` ayudan tras una vinculación confirmada, pero `7_0` no implementa la revisión/mapeo entre códigos |
| 3 | El *upsert* por `codigo` reemplaza `id_archivo` y precio del producto interno | El producto interno sigue representando la última ficha recibida | Corregido parcialmente: cada oferta se upsertea separada por producto/proveedor y se registra en `historial_precios`; el producto interno todavía conserva el comportamiento histórico por código |
| 4 | La extracción registra productos válidos, no todas las filas fuente | Una fila sin precio o ambigua queda solo como error agregado; no se puede auditar/reprocesar una a una | `7_0` no incluye staging por fila. Agregar una tabla de filas de catálogo con archivo, número de fila, datos originales y estado de revisión |
| 5 | Moneda, IVA y unidad deben ser comparables | Comparar monedas, tratamiento de IVA o presentaciones distintas puede engañar | Moneda se elige por archivo (USD inicial, VES disponible); IVA de oferta queda en 0 % si no se detecta, según decisión del cliente. El ETL aún no normaliza moneda, unidad ni equivalencia |
| 6 | El plazo del proveedor no siempre es global | El tiempo puede variar por artículo o por cotización | `producto_proveedor.plazo_entrega_dias` y `proveedores.plazo_entrega_dias` permiten el dato, pero hay que capturarlo y distinguir estimado de medido |
| 7 | No existía historial de precios funcional | No se podía reconstruir la evolución de una oferta | El ETL registra nuevas observaciones con precio, moneda, IVA, descuento, disponibilidad, política y archivo de origen |
| 8 | El stock operativo no proviene de catálogos | Una lista de proveedor no puede decir qué hay en depósito | `stock_movimientos`/`configuracion_stock` son integración separada y requieren datos de ventas/almacén |
| 9 | Sin metadatos del vector ni alias | Difícil reconciliar embeddings o vocabulario regional | `modelo_embedding`, `vectorizado_en` y `producto_alias` preparan el esquema; no sustituyen el enrutamiento SQL |

Ninguna de estas deficiencias se corrige "adivinando": todas necesitan datos que
el cliente debe aportar o que el ETL debe empezar a capturar (sección 8).

---

## 6. Esquema de cotizaciones: migración `7_0`

Archivo: `scripts/migracion_7_0.sql`, también reflejada en `init.sql`. La
migración es aditiva e idempotente. El formulario y el ETL ya están preparados
para capturar proveedor/vendedor por archivo y guardar los campos de oferta;
el chat todavía no consulta estas ofertas. La base de desarrollo no se ha
migrado.

Cada archivo seleccionado tiene su propia pareja proveedor/vendedor, moneda y
nota. Si se seleccionan varios archivos, el panel los analiza y confirma de uno
en uno; los datos de contacto anteriores se sugieren para agilizar la carga,
pero se pueden corregir por archivo. Para otro proveedor se cambian esos datos
antes de confirmar.

```powershell
# Después de respaldar la base y antes de usar las nuevas columnas.
venv\Scripts\python.exe scripts\aplicar_migracion.py 7_0
```

### 6.1 Columnas nuevas

La siguiente tabla describe el esquema y el comportamiento de captura. La
selección USD es un valor inicial explícito en el formulario; si el archivo
indica bolívares, el usuario debe elegir VES.

| Tabla | Columnas | Para qué |
|---|---|---|
| `proveedores` | `rif`, `telefono`, `correo`, `vendedor`, `telefono_vendedor`, `correo_vendedor`, `moneda`, `plazo_entrega_dias`, `activo`, `actualizado_en` | Identidad, vendedor/contacto y promesa de entrega |
| `archivos_subidos` | `id_proveedor`, `vendedor_nombre`, `vendedor_telefono`, `vendedor_correo`, `moneda`, `nota_proveedor` | Proveedor y condiciones declaradas para ese archivo |
| `producto_proveedor` | `iva`, `iva_incluido`, `descuento` nullable, `cantidad_disponible_proveedor`, `politica_ventas` | Oferta vigente, separada del stock de la ferretería |
| `historial_precios` | precio, moneda, IVA, descuento, disponibilidad, política, archivo | Observaciones históricas de las ofertas |
| `categoria` | `id_padre`, `sinonimos` | Jerarquía y sinónimos de búsqueda |
| `productos` | `codigo_interno`, `moneda`, `unidad_medida`, `presentacion`, `punto_reorden`, `ubicacion`, `activo`, `actualizado_en`, `modelo_embedding`, `vectorizado_en` | Presentación, política de reorden y trazabilidad del vector |

Para no perder las filas que el parser no puede convertir inmediatamente en
ofertas, se recomienda una tabla de recepción/revisión por fila. Es una pieza
que **no está incluida en `7_0`**:

```sql
CREATE TABLE catalogo_filas (
    id BIGSERIAL PRIMARY KEY,
    id_archivo INT NOT NULL REFERENCES archivos_subidos(id_archivo),
    numero_fila INT NOT NULL,
    datos_originales JSONB NOT NULL,
    estado VARCHAR(24) NOT NULL
        CHECK (estado IN ('pendiente', 'importada', 'duplicada', 'revision', 'error')),
    detalle TEXT,
    id_producto INT REFERENCES productos(id),
    id_oferta INT REFERENCES producto_proveedor(id),
    UNIQUE (id_archivo, numero_fila)
);
```

`datos_originales` conserva la fila extraída y su relación con el documento;
`estado` permite reportar el destino de cada registro. La tabla no convierte
automáticamente una fila inválida en producto ni sustituye el archivo original:
permite auditarla, corregirla y reprocesarla sin ocultar fallos.

### 6.2 Tablas nuevas

| Tabla | Responde a | Clave |
|---|---|---|
| `producto_proveedor` | P1 y promedio de precios ofertados | Oferta vigente por producto interno y proveedor; `codigo_proveedor` se conserva en el lado del proveedor |
| `historial_precios` | Evolución de cotizaciones | Historial de cada oferta, ligado al archivo que la informó |
| `compras` | P2, cuando “surtido” significa compra recibida | Orden/recepción real; no se crea al cargar un catálogo |
| `detalle_compra` | P2: precio pagado y cantidad recibida | Detalle de una compra, vinculado al producto interno |
| `evaluacion_proveedor` | P2: calidad/cumplimiento evaluados | Una evaluación explícita, idealmente por recepción |
| `stock_movimientos` | P3: consumo y cobertura | Operación de almacén; no se alimenta con cotizaciones |
| `configuracion_stock` | P3: umbral y días de cobertura | Regla de inventario, no atributo del proveedor |
| `producto_alias` | Búsqueda sin inventar productos | único `(id_producto, termino)` |
| `tasa_cambio` | Comparar Bs. y USD con fecha | único `(moneda, vigente_desde)` |

El diseño actual de `producto_proveedor` requiere más detalle antes de usarlo con
catálogos heterogéneos:

- La unicidad `(id_producto, id_proveedor)` solo representa una oferta vigente
  por proveedor/producto. El historial y `id_archivo` deben actualizarse sin
  borrar la cotización anterior.
- Artículos con el mismo código pero distinta descripción, tamaño o empaque no
  se deben fusionar automáticamente. La asociación con el producto interno
  requiere confirmación humana o una regla de equivalencia revisada.
- Si un proveedor publica más de una presentación del mismo artículo, la unidad
  y presentación deben formar parte de la identidad comparable; de lo contrario,
  un precio por caja podría compararse erróneamente con uno por pieza.
- El esquema actual de `producto_proveedor.moneda` es `NOT NULL DEFAULT 'USD'`.
  Si la moneda no se reconoce, la solución segura es mantener la fila en
  revisión o cambiar el esquema para permitir “desconocida”; no usar USD por
  defecto como si fuera evidencia.

Reglas de negocio que el borrador de base puede imponer:

- Precios, descuentos y cantidades no negativos; IVA de la oferta entre 0 y 100.
- Cantidad recibida nunca mayor que la solicitada.
- Fecha de entrega real nunca anterior a la compra.
- Calidad y cumplimiento solo de 1 a 5.
- Una sola configuración de stock.
- `plazo_entrega_dias` y `tiempo_reposicion_dias` no negativos.

### 6.3 Lo que aún no está integrado

- Las filas inválidas o no interpretadas no se guardan todavía en una tabla
  `catalogo_filas` para revisión individual; solo quedan el original y el
  detalle agregado del archivo.
- La conciliación de códigos distintos, unidades y presentaciones sigue
  requiriendo confirmación; el código global actual no prueba equivalencia.
- El *backfill* de `7_0` no puede reconstruir el proveedor de catálogos
  históricos cuyo origen nunca se capturó.
- El chat no ejecuta todavía estas consultas de negocio; las tablas por sí
  solas no cambian sus respuestas.
- La eliminación de catálogo debe revisarse junto con la estrategia futura de
  productos compartidos para garantizar que retirar una cotización no borre
  ofertas de otros proveedores.

---

## 7. Ejemplos ilustrativos de consultas

Los nombres, productos y resultados siguientes son **datos sintéticos de
demostración**. No provienen de los catálogos de la ferretería, no prueban que
el ETL ya escriba ofertas y no son respuestas conectadas al chat. Las consultas
muestran cómo responder cuando los datos requeridos ya se capturaron.

### P1 — ofertas comparables y plazo informado (producto `M-001`)

```sql
SELECT pr.nombre AS proveedor,
       o.precio,
       o.moneda,
       ROUND(o.precio * (1 + o.iva / 100), 2) AS precio_con_iva,
       COALESCE(o.plazo_entrega_dias, pr.plazo_entrega_dias) AS dias_entrega,
       o.disponible
  FROM producto_proveedor AS o
  JOIN productos AS p ON p.id = o.id_producto
  JOIN proveedores AS pr ON pr.id_proveedores = o.id_proveedor
 WHERE p.codigo = 'M-001'
   AND o.disponible
   AND (o.vigente_desde IS NULL OR o.vigente_desde <= CURRENT_DATE)
   AND (o.vigente_hasta IS NULL OR o.vigente_hasta >= CURRENT_DATE)
 ORDER BY o.precio ASC;
```

Esta comparación solo es válida si ambas filas representan la misma unidad y
presentación, y usan una moneda y tratamiento de IVA comparables. Si no, el
asistente debe mostrar los valores separados o pedir aclaración, no ordenar
precios incompatibles. El plazo mostrado es el declarado para esa oferta (o el
general del proveedor cuando aplique); no es un plazo de entrega medido.

```text
     proveedor      | precio | moneda | precio_con_iva | dias_entrega | disponible
--------------------+--------+--------+----------------+--------------+------------
 Importadora Norte  |   7.90 | USD    |           9.16 |            7 | t
 Ferreteria Central |   8.50 | USD    |           9.86 |            3 | t
```

La respuesta correcta no es un solo nombre: es **"Importadora Norte ofrece el
precio menor (7,90 USD; 9,16 con IVA), pero Ferretería Central declara 3 días
frente a 7"**. El asistente debe mostrar ambas métricas y dejar que el usuario
decida; la velocidad informada no debe presentarse como puntualidad comprobada.

### P2 — promedio de precios ofertados vs. historial de surtido

La consulta siguiente es un ejemplo de **historial de compras recibidas**, no
de catálogos. Resume el desempeño general del proveedor; para responder
específicamente por martillos, debe filtrarse al conjunto de productos internos
confirmados como martillos. Su promedio de precios no debe mezclar productos,
monedas ni presentaciones, por lo que ese indicador se calcula por separado
sobre cotizaciones vigentes y comparables.

```sql
SELECT pr.nombre,
       (SELECT COUNT(*) FROM compras c
         WHERE c.id_proveedor = pr.id_proveedores
           AND c.estado = 'recibida') AS compras,
       (SELECT ROUND(AVG(dc.precio_unitario), 2)
          FROM detalle_compra dc
          JOIN compras c2 ON c2.id_compra = dc.id_compra
         WHERE c2.id_proveedor = pr.id_proveedores
           AND c2.estado = 'recibida') AS precio_promedio,
       (SELECT ROUND(AVG(e.calidad), 2) FROM evaluacion_proveedor e
         WHERE e.id_proveedor = pr.id_proveedores) AS calidad,
       (SELECT ROUND(AVG(e.cumplimiento), 2) FROM evaluacion_proveedor e
         WHERE e.id_proveedor = pr.id_proveedores) AS cumplimiento,
       (SELECT ROUND(AVG(c3.fecha_entrega_real - c3.fecha_entrega_estimada), 1)
          FROM compras c3
         WHERE c3.id_proveedor = pr.id_proveedores
           AND c3.estado = 'recibida'
           AND c3.fecha_entrega_estimada IS NOT NULL
           AND c3.fecha_entrega_real IS NOT NULL) AS desvio_dias
  FROM proveedores AS pr
 WHERE pr.activo
 ORDER BY calidad DESC NULLS LAST, precio_promedio ASC;
```

```text
       nombre       | compras | precio_promedio | calidad | cumplimiento | desvio_dias
--------------------+---------+-----------------+---------+--------------+-------------
 Ferreteria Central |       2 |            8.50 |    4.50 |         4.50 |         0.5
 Importadora Norte  |       2 |            7.90 |    3.00 |         2.50 |         4.0
```

Aquí se ve por qué "mejor" necesita definición: Importadora Norte es **más
barata**, pero Ferretería Central tiene mejor calidad, mejor cumplimiento y
menor desvío. Los valores son ficticios. Si el usuario solo pregunta por
catálogos, esta consulta no aplica: debe calcularse el promedio de cotizaciones
vigentes y comparables para los productos reconocidos como martillos, indicando
el período y cómo se ponderó cada producto. No debe decir “me ha surtido” sin
compras/recepciones registradas.

### P3 — qué se está acabando

```sql
WITH consumo AS (
    SELECT m.id_producto,
           SUM(ABS(m.cantidad)) FILTER (WHERE m.tipo = 'salida') AS unidades_30d
      FROM stock_movimientos AS m
     WHERE m.ocurrido_en >= NOW() - INTERVAL '30 days'
     GROUP BY m.id_producto
),
regla AS (
    SELECT stock_minimo_global, dias_cobertura_alerta
      FROM configuracion_stock WHERE id = 1
)
SELECT p.codigo,
       p.nombre,
       p.stock,
       COALESCE(p.punto_reorden, r.stock_minimo_global) AS umbral,
       ROUND(COALESCE(c.unidades_30d, 0) / 30.0, 2) AS consumo_diario,
       CASE WHEN COALESCE(c.unidades_30d, 0) = 0 THEN NULL
            ELSE ROUND(p.stock / (c.unidades_30d / 30.0), 1) END AS dias_cobertura,
       (SELECT ROUND(AVG(o.tiempo_reposicion_dias), 1)
          FROM producto_proveedor o
         WHERE o.id_producto = p.id AND o.disponible) AS dias_reposicion,
       r.dias_cobertura_alerta
  FROM productos AS p
 CROSS JOIN regla AS r
  LEFT JOIN consumo AS c ON c.id_producto = p.id
 WHERE p.activo
 ORDER BY (p.stock <= COALESCE(p.punto_reorden, r.stock_minimo_global)) DESC,
          dias_cobertura ASC NULLS LAST;
```

```text
 codigo |         nombre          | stock | umbral | consumo_diario | dias_cobertura | dias_reposicion | dias_cobertura_alerta
--------+-------------------------+-------+--------+----------------+----------------+-----------------+-----------------------
        | Producto sin codigo     |     0 |      5 |           0.00 |                |                 |                    15
 M-001  | Cemento gris 42.5 kg    |     0 |      5 |           0.00 |                |            12.0 |                    15
 M-002  | Alambre galvanizado #18 |    12 |      5 |           2.67 |            4.5 |            12.0 |                    15
```

`M-002` se agotaría en **4,5 días** según los movimientos sintéticos y su
reposición declarada sería de **12**: hay que evaluar reponerlo aunque su stock
(12) supere el umbral (5). Estos resultados solo son válidos si ventas y
movimientos reflejan el inventario real; no se derivan de una cotización.

---

## 8. Cambios necesarios en el flujo de ingesta y en el RAG

La migración sola no responde nada: define parte de dónde guardar los datos.
Falta capturarlos y consultarlos. El flujo recomendado corresponde al trabajo
real de la ferretería: **recibir archivo → identificar proveedor → revisar
extracción → guardar cada fila y su oferta → consultar cotizaciones**. No crear
una compra ni modificar stock en este flujo.

### Fase 1 — Registrar cada catálogo recibido

1. Antes de subir, el usuario selecciona el proveedor existente o registra uno
   nuevo con nombre y, si está disponible, RIF. El nombre del archivo solo se
   conserva como evidencia; no se usa como asociación automática.
2. Guardar `id_proveedor`, fecha de recepción del archivo y metadatos de
   vigencia/moneda que el usuario confirme. Conservar el original.
3. Persistir cada fila fuente y su número de fila en `catalogo_filas`, incluso
   si no se puede convertir en oferta. Estados mínimos: importada, duplicada,
   requiere revisión, error.
4. Mostrar en la vista previa cantidades reconciliables:
   filas leídas = filas importables + duplicadas idénticas + pendientes de
   revisión/error. No llamar "producto guardado" a una fila sin precio, unidad o
   identidad resueltos.

### Fase 2 — Normalizar ofertas y vincular productos

1. Mantener el código original como `codigo_proveedor`, asociado al proveedor;
   no usarlo como identidad global del producto.
2. Encontrar una coincidencia existente por código interno, alias o atributos.
   Si hay más de una posibilidad —o el empaque/unidad difiere— pedir revisión
   humana; no fusionar productos solo por nombre parecido.
3. Guardar en `producto_proveedor` la oferta y el origen `id_archivo`, con
   precio, moneda, IVA, descuento, unidad/presentación, vigencia,
   disponibilidad y plazo solo cuando estén expresamente disponibles.
4. Agregar cada nueva cotización a `historial_precios`; no sobrescribir la
   única evidencia de precio. Marcar oferta anterior como vencida si el archivo
   nuevo sustituye explícitamente esa lista, conservando el historial.
5. Si precio, moneda o IVA no pueden confirmarse, conservar la fila como
   pendiente de revisión; no establecer USD/16 % por defecto como si el
   proveedor lo hubiera afirmado.

### Fase 3 — Consultar catálogos desde el asistente

1. Usar búsqueda vectorial/trigram para identificar el producto interno a
   partir de la pregunta; pedir precisión si existen varias presentaciones.
2. Ejecutar SQL para listar o comparar ofertas vigentes del producto
   seleccionado, con proveedor, precio, moneda, IVA, unidad y fecha de catálogo.
3. En ausencia de moneda/unidad comparables, mostrar la limitación en vez de
   afirmar qué proveedor es más barato.
4. Usar el LLM únicamente para redactar los resultados SQL y abstenerse cuando
   falte evidencia.

### Fase 4 — Integrar compras e inventario, si se requiere

1. Registrar órdenes de compra y recepciones desde el proceso real de la
   ferretería o integrar su sistema de ventas/almacén.
2. Solo entonces registrar fechas prometidas/reales, cantidades recibidas,
   movimientos de stock y evaluaciones de proveedor.
3. No crear datos históricos retroactivos a partir de catálogos.

El endpoint `app/api/v1/rag_chat.py` hoy devuelve una respuesta provisional.
Cuando se conecte el motor, **no debe mandar toda pregunta al *top-k*
vectorial**. Propuesta de enrutamiento:

| Tipo de pregunta | Vía | Ejemplo |
|---|---|---|
| "¿qué producto es…?" / "busco…" | Vector + trigram para identificar el producto | "algo para pegar cerámica" |
| "¿qué proveedor ofrece el martillo más barato?" | Identificación semántica + SQL sobre ofertas vigentes comparables | P1, cotizaciones |
| "¿quién entrega más rápido?" | SQL de plazo cotizado, etiquetado como declarado | P1, cotizaciones |
| "¿cuál tiene el menor precio promedio?" | SQL agregado sobre cotizaciones equivalentes en un período explícito | P2, solo oferta |
| "¿quién me surtió mejor / cumplió más?" | SQL sobre compras, recepciones y evaluaciones reales | P2, solo si se registran hechos |
| "¿qué se está acabando?" | SQL sobre existencias actualizadas y movimientos | P3, integración de almacén |
| "¿cuánto cuesta X?" | SQL de ofertas con proveedor, moneda, unidad y vigencia | cotizaciones |

El modelo de lenguaje recibe **solo** las filas devueltas por SQL y redacta; no
calcula ni completa cifras. Si no hay filas comparables, responde que no hay
datos registrados o que los datos no son comparables; no estima. Cada fuente
mostrada debe incluir proveedor, archivo/fecha del catálogo, código de
proveedor y producto interno si la vinculación fue confirmada.

Contrato mínimo de respuesta:

- **P1/cotización:** producto y presentación, proveedor, precio, moneda,
  tratamiento de IVA, plazo declarado, fecha del archivo y vigencia.
- **P2/precios:** período, productos incluidos, moneda/unidad normalizadas y
  método de promedio. **P2/surtido:** número de compras, cantidades aceptadas,
  calidad/cumplimiento evaluados y fechas reales.
- **P3/inventario:** producto, stock y fecha de actualización; si hay histórico,
  consumo, cobertura, umbral y fuente del dato.

---

## 9. Plan de adopción y compatibilidad

| Paso | Acción | Criterio para avanzar |
|---|---|---|
| 1 | Probar el formulario y la migración en base desechable con catálogos de varios proveedores | Proveedor, vendedor, moneda, nota y ofertas se reconcilian por archivo |
| 2 | Completar filas de revisión y confirmación de códigos/unidades | Ninguna fila fuente queda oculta ante el usuario |
| 3 | Revisar borrado de archivos con productos compartidos | Retirar una cotización no borra ofertas de otros proveedores |
| 4 | Aplicar la migración en desarrollo después de respaldar y verificar la prueba | Respaldo verificado y columnas nuevas consultables |
| 5 | Conectar consultas SQL del chat para cotizaciones | Las respuestas citan fuente, vigencia y unidades y se abstienen si no comparan |
| 6 | Integrar compras/stock desde el proceso operativo, si se requiere P2 histórico o P3 predictiva | Datos de compra/almacén reales disponibles |

La expansión debe ser compatible (expandir, migrar datos, cambiar aplicación y
retirar uso anterior solo después de verificar). No revertir una migración
eliminando tablas que ya recibieron datos; la reversión de aplicación debe
preservar ofertas e historial.

---

## 10. Riesgos y decisiones pendientes con el cliente

1. **Identidad del proveedor al cargar:** se solicita explícitamente por cada
   archivo y no se deduce del nombre del documento. El usuario también registra
   el vendedor que atiende la cuenta; teléfono y correo son opcionales.
2. **Promedio de “mejores martillos”:** confirmar si significa menor precio
   promedio de catálogos o desempeño de compras pasadas. Para precio promedio,
   decidir rango de fechas, presentaciones incluidas y ponderación por SKU.
3. **Moneda y conversión:** USD es el valor inicial del formulario; VES se
   puede seleccionar por archivo. Para comparar monedas distintas hace falta
   una tasa y fecha, no basta con guardar ambas monedas.
4. **IVA y descuentos:** por decisión del cliente, si el lector no encuentra
   el IVA, la oferta se guarda con 0 %. El precio solo se puede comparar con
   seguridad cuando se conoce el tratamiento fiscal. El descuento por producto
   es nullable y la nota del archivo sirve para condiciones como “válido hasta
   mañana”.
5. **Unidades y presentaciones:** establecer qué atributos hacen comparable el
   mismo producto (pieza, caja, medida, marca, modelo).
6. **Plazo de entrega:** distinguir el plazo declarado en una cotización del
   desempeño medido en entregas reales; el primero puede variar por artículo.
7. **Compras e inventario:** decidir si esos datos vivirán en este sistema o se
   leerán desde el ERP/POS de la ferretería. Si no se capturan, P2 histórico y
   P3 de agotamiento deben declararse no disponibles.

---

## 11. Anexo: comandos

La migración `7_0` no se aplicó a la base de desarrollo. Primero ejecute la
prueba en una base desechable y respalde el entorno; el staging por fila y la
normalización de moneda/unidad siguen pendientes:

```powershell
# Aplicar únicamente después de aprobación y pruebas de migración.
venv\Scripts\python.exe scripts\aplicar_migracion.py 7_0

# Comprobar el estado del catálogo
venv\Scripts\python.exe -c "from app.db.session import cursor_rag; c=cursor_rag(); cur=c.__enter__(); cur.execute('SELECT COUNT(*) FROM productos'); print(cur.fetchone())"

# La vectorización es posterior a validar el piloto y distinta de la ingesta.
docker compose exec api python scripts\vectorizar_catalogo.py --lote 10
```

Consultas de estado (solo después de que existan las tablas):

```sql
-- Productos sin oferta asociada (pendientes de conciliación)
SELECT COUNT(*) FROM productos p
 WHERE NOT EXISTS (SELECT 1 FROM producto_proveedor o WHERE o.id_producto = p.id);

-- Productos sin vector; no significa que estén ausentes de la base
SELECT COUNT(*) FROM productos WHERE descripcion_vectorial IS NULL;

-- Stock por debajo del umbral; la confiabilidad depende de la integración del almacén
SELECT p.codigo, p.nombre, p.stock,
       COALESCE(p.punto_reorden, c.stock_minimo_global) AS umbral
  FROM productos p CROSS JOIN configuracion_stock c
 WHERE p.stock <= COALESCE(p.punto_reorden, c.stock_minimo_global);
```

---

## 12. Conclusión

El flujo descrito es **consultar cotizaciones que la ferretería recibe**, no
automatizar compras ni tratar catálogos como inventario. El formulario ahora
guarda por archivo el proveedor, vendedor, moneda y nota; el ETL conserva las
ofertas extraídas, el historial y la disponibilidad informada sin modificar el
stock propio. Para comparar precios todavía hay que confirmar unidades,
equivalencias, impuestos y vigencia; las consultas SQL aún deben conectarse al
chat. “Quién ha surtido mejor” requiere
compras/recepciones reales y no se obtiene de las cotizaciones. “Qué se está
acabando” requiere existencias operativas actualizadas, no archivos de
proveedores.

La migración `7_0` y el ETL cubren proveedor, vendedor, moneda, nota, ofertas e
historial, pero aún faltan el staging por fila, la conciliación humana de
productos y la conexión de consultas SQL al chat. Hasta completar y validar
esas etapas, el asistente debe mostrar solo datos verificables y explicitar
cuándo no puede comparar o responder.
