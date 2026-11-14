# Reporte de cierre — Semana 3

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario y Buscador Comercial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Desarrollador** | Dixon Daniel Bastias Hernandez |
| **Período reportado** | Semana 3 — Interfaz e ingesta ETL |
| **Fecha de elaboración** | 14 de noviembre de 2026 |
| **Estado** | Tareas de Semana 3 reportadas como completadas |
| **Base del reporte** | [Lista de tareas y checklist de ejecución](../../prompts/lista_de_tareas_y_checklist_de_ejecucion_del_proyecto.md) |
| **Continuidad** | [Reporte de cierre de Semana 1](./reporte_cierre_semanal_01.md) · [Reporte de cierre de Semana 2](./reporte_cierre_semanal_02.md) · [Acta 3 de ingesta ETL](./acta_03_ingesta_etl.md) |

## 1. Resumen ejecutivo

Al cierre de la Semana 2 quedó implementado el sistema de autenticación, seguridad y auditoría. El siguiente paso fue construir la interfaz web y el motor de ingesta ETL que permite cargar catálogos de proveedores al sistema.

La Semana 3 se considera completada de acuerdo con el checklist. El acta técnica de esta etapa reporta **360 controles aprobados, 1 omitido por corresponder a una etapa posterior y 0 fallidos**.

**Nota importante sobre la entrega del prototipo:** La entrega del prototipo funcional estaba estipulada para la Semana 4 según el cronograma original. Sin embargo, el sistema ya se encuentra listo para probar. Se trata de una versión beta, por lo que pueden existir errores que serán corregidos una vez reportados. La prueba formal se realizará el día lunes, dado que el sistema está instalado en la computadora de Cristian y actualmente estoy trabajando en la PC de Edgardo, la cual no tiene suficiente capacidad para ejecutar la aplicación.

## 2. Actividades completadas según el checklist

### Interfaz web (Semana 3)

- Implementé las pantallas de acceso, panel principal y buscador web (son las ventanas que el usuario ve al entrar al sistema: la pantalla de iniciar sesión, el menú principal y la barra para buscar productos).
- Añadí temas claro y oscuro (permite cambiar el color de la pantalla, hay un modo para día con fondo blanco y un modo para noche con fondo oscuro).
- Incorporé protección CSRF (protección contra ataques externos que intentan hacer acciones en nombre del usuario sin su consentimiento).
- Empaqueté la API en Docker (el sistema está listo para ejecutarse en cualquier servidor sin configurar el entorno manualmente).

### Ingesta ETL (Semana 3)

- Implementé la carga de archivos en múltiples formatos: PDF con capa de texto, XLSX, DOCX y TXT. No se admiten CSV ni XLS (el sistema puede leer los formatos más comunes de catálogos de proveedores).
- Añadí validación independiente por archivo, de modo que un error en un archivo no cancela el resto del lote (si un archivo está mal, solo ese archivo se rechaza, los demás se procesan igual).
- Implementé la normalización de productos (los datos de diferentes formatos se convierten a un formato único y ordenado).
- Configuré el upsert por código sin sobrescribir el stock existente (al actualizar un producto se conserva la cantidad en existencia que ya estaba registrada).
- Establecí límites de procesamiento: máximo 20 archivos por solicitud, 100 MB por archivo, 20.000 filas por archivo y 500 páginas para PDF y DOCX (controles de seguridad para que el sistema no se sobrecargue).
- Implementé la persistencia segura de los archivos originales con nombre UUID y hash SHA-256 (los archivos se guardan con un nombre único y una firma digital para verificarlos).

### Previsualización (Semana 3)

- Añadí una pantalla de previsualización que permite revisar el catálogo y confirmar las columnas de precio antes de guardar los productos en la base de datos (el usuario puede ver qué datos se extrajeron antes de confirmar que se guarden).

### Historial y trazabilidad (Semana 3)

- Implementé el registro automático de cada carga de catálogo con su estado, conteos y detalle (el sistema guarda quién cargó qué archivo, cuándo y si salió bien o mal).
- Los usuarios autenticados pueden consultar el historial de archivos cargados desde la interfaz (se puede ver qué catálogos se han subido anteriormente).

## 3. Actividades de la Semana 4 ya completadas (trabajo avanzado)

Las siguientes tareas de la Semana 4 ya están implementadas y listas:

### Parsers locales del ETL

- Se implementaron los parsers locales (herramientas que leen los archivos sin usar inteligencia artificial): pandas y openpyxl para archivos Excel (.xlsx), pdfplumber y PyMuPDF para PDF, python-docx para Word (.docx) y lectura nativa para archivos de texto (.txt).
- Se definieron reglas para entender las columnas de los catálogos (el sistema reconoce automáticamente qué columna es código, precio, descripción, etc.).
- Se agregaron expresiones regulares para detectar precios, códigos y contactos (formatos especiales para identificar datos importantes).

### Validación y rechazo de archivos

- El sistema rechaza archivos con formato irregular o incompatible con un mensaje claro (si un archivo no se puede leer, dice exactamente por qué sin detener los demás).
- Se validan archivos contra ZIP-bomb y límites de tamaño (protección contra archivos maliciosos o muy grandes).

### Full-Text Search (Búsqueda de texto completo)

- Se preparó la búsqueda de texto completo de PostgreSQL (búsqueda instantánea en la base de datos sin costo adicional).
- Se expuso el endpoint de búsqueda y se integró en la interfaz web con AJAX (la búsqueda muestra resultados en tiempo real sin recargar la página).
- Los resultados muestran producto, precio, proveedor y número de contacto (información completa del vendedor).

### Redirecciones

- Después de iniciar sesión, el usuario va directamente al buscador (no hay que buscar el botón, se entra directo a la función principal).

### Pruebas

- Se cubrieron con pruebas los parsers locales y la normalización (verificaciones automatizadas para cada tipo de archivo).
- Se ejecutaron pruebas de extremo a extremo: autenticación, subida de archivo, ETL, búsqueda y resultados (recorrido completo del sistema).

### Criterios de salida del MVP

- Flujo completo demostrable desde la web sobre productos cargados (se puede usar el sistema desde el navegador).
- Respuestas en milisegundos (la búsqueda es muy rápida).
- Resultados limitados a productos reales con precio, proveedor y número de contacto (no inventa información).
- Comportamiento honesto sin coincidencias (si no encuentra nada, lo dice claramente).

> **Observación:** Se realizaron pruebas de ingesta de documentos (PDF y Excel) y la gran mayoría se extrajo y almacenó correctamente en la base de datos. Sin embargo, se identificaron casos particulares como "CATALOGO RESINCA.pdf", cuyo formato específico impide su correcta lectura, por lo que será necesario adaptar el código de extracción para procesarlo adecuadamente.

## 4. Resultado práctico para la empresa

| Antes de la Semana 3 | Al cierre de la Semana 3 |
|---|---|
| Los usuarios podían iniciar sesión y el sistema registraba sus acciones, pero no había una interfaz visual para usar el sistema. | Los usuarios acceden a una interfaz web con pantallas de acceso, panel y buscador. |
| Los catálogos de proveedores llegaban en archivos que debían procesarse manualmente. | El sistema lee automáticamente archivos PDF, XLSX, DOCX y TXT, extrae los productos y los guarda en la base de datos. |
| No había forma de revisar los datos antes de guardarlos. | La previsualización permite validar los datos extraídos antes de confirmar la ingesta. |
| No existía un registro de las cargas realizadas. | El historial de archivos queda registrado y consultable por los usuarios. |

El beneficio principal es la **automatización del proceso de actualización del catálogo**: los empleados ya no necesitan transcribir manualmente los productos de cada catálogo recibido; el sistema lo hace de forma automática y ordenada.

## 5. Estado, límites y continuidad

- **Semana 3:** las tareas de interfaz e ingesta ETL indicadas en el checklist están marcadas como completadas.
- **Semana 4:** las tareas principales del Buscador Comercial ya están implementadas y operativas.
- **Prototipo para prueba:** el sistema se encuentra operativo y listo para probar. Se trata de una versión beta; cualquier error encontrado debe reportarse para su corrección antes de la entrega final.
- **Prueba programada:** la prueba formal se realizará el día lunes en la computadora de Cristian, dado que la PC de Edgardo no tiene suficiente capacidad para ejecutar la aplicación.
- **MVP (Producto Mínimo Viable):** el prototipo está listo para demostrar el flujo completo de búsqueda comercial.
