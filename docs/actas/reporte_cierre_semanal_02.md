# Reporte de cierre — Semana 2

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario y Buscador Comercial |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Desarrollador** | Dixon Daniel Bastias Hernandez |
| **Período reportado** | Semana 2 — Autenticación, seguridad y auditoría |
| **Fecha de elaboración** | 7 de noviembre de 2026 |
| **Estado** | Tareas de Semana 2 reportadas como completadas |
| **Base del reporte** | [Lista de tareas y checklist de ejecución](../../prompts/lista_de_tareas_y_checklist_de_ejecucion_del_proyecto.md) |
| **Continuidad** | [Reporte de cierre de Semana 1](./reporte_cierre_semanal_01.md) · [Acta 2 de seguridad, JWT y auditoría](./acta_02_seguridad_jwt_auditoria.md) |

## 1. Resumen ejecutivo

Al cierre de la Semana 1 quedó preparada la base de datos y el entorno donde
funcionaría el sistema. El siguiente paso fue proteger esa base: en la Semana 2
se implementaron el inicio de sesión, las cuentas y roles, la protección de
contraseñas, las sesiones con vencimiento y el registro de actividad.

En palabras sencillas, el sistema pasó de tener un almacén preparado a contar
con una puerta de acceso y controles para determinar quién puede entrar y qué
puede hacer. Las acciones relevantes dejan evidencia para su revisión, mientras
que las contraseñas no se almacenan en texto legible.

La Semana 2 se considera completada de acuerdo con el checklist. El acta
técnica de esta etapa reporta **230 controles aprobados, 1 omitido por
corresponder a una etapa posterior y 0 fallidos**. Este resultado corresponde a
las verificaciones descritas en dicha acta; no significa que el MVP comercial
completo esté terminado.

## 2. Actividades completadas según el checklist

### Acceso, usuarios y roles

- Implementé el inicio de sesión y la validación de credenciales para que cada
  usuario acceda con su propia cuenta.
- Preparé el registro inicial y los roles para diferenciar las funciones de
  administración y consulta.
- Añadí controles de autorización para que una persona no pueda obtener
  permisos que no le corresponden.

### Protección de contraseñas y sesiones

- Incorporé el algoritmo scrypt para almacenar una huella protegida de cada
  contraseña, en lugar de guardar la contraseña legible.
- Implementé tokens JWT firmados con vencimiento para identificar la sesión.
- Añadí el cierre de sesión y la verificación de la vigencia de las
  credenciales en las peticiones protegidas.

### Auditoría y controles de seguridad

- Incorporé el registro automático de eventos relevantes, como accesos y
  peticiones a la API.
- Protegí la bitácora contra modificaciones y eliminaciones.
- Configuré una cuenta de base de datos para la aplicación con privilegios
  limitados, separada de la cuenta administrativa.
- Cubrí el acceso, la expiración de tokens, los datos inválidos y los intentos
  de inyección SQL con pruebas.

## 3. Resultado práctico para la empresa

| Antes de la Semana 2 | Al cierre de la Semana 2 |
|---|---|
| La infraestructura y las tablas estaban preparadas, pero aún faltaba completar el control de acceso de la aplicación. | El personal puede autenticarse con cuentas individuales. |
| No había una sesión firmada por la aplicación para identificar cada petición protegida. | Las peticiones protegidas requieren una sesión válida con vencimiento. |
| Hacía falta reforzar la separación entre las tareas de la aplicación y las de administración de la base. | La aplicación usa una cuenta con privilegios limitados. |
| La trazabilidad de actividad todavía debía integrarse en el flujo de la aplicación. | Los eventos relevantes quedan registrados y la bitácora está protegida contra cambios. |

El beneficio principal es la **responsabilidad individual**: las operaciones
dejan de depender de una cuenta compartida y pueden relacionarse con una sesión
y un usuario. También se reduce el impacto potencial de errores de acceso o de
una cuenta de aplicación comprometida.


## 4. Cambio de enfoque del producto y sus beneficios

### Cómo se trabajaba en el enfoque anterior

La dirección inicial del proyecto contemplaba un asistente conversacional RAG.
En ese enfoque, se preparaban representaciones vectoriales de los productos
(*embeddings*) para recuperar elementos por similitud semántica y construir
respuestas en lenguaje natural. El usuario habría formulado preguntas como si
conversara con un asistente.

Ese trabajo dejó componentes técnicos en el repositorio, pero el alcance
vigente los reemplazó como camino principal del producto. No se eliminan ni se
extienden sin autorización: quedan fuera de la ruta activa del buscador.

### Enfoque vigente: Buscador Comercial

• Redefinición de la Consulta: Se sustituye el chat generativo por una pantalla de búsqueda directa de productos y proveedores. Las consultas se resolverán internamente en PostgreSQL, mostrando los datos extraídos de los catálogos enviados por los proveedores. En caso de no encontrar coincidencias, el sistema lo notificará explícitamente; no se generará ninguna respuesta con IA durante la búsqueda.

• Procesamiento y Estructuración de Catálogos (ETL): Este proceso se mantiene independiente de la consulta. MarkItDown convierte los archivos a formato Markdown; es una herramienta de conversión, no un modelo de IA. Para la ingesta se contempla **un solo modelo de IA**: ese modelo recibe el Markdown, estructura los registros y, cuando haga falta, sugiere el nombre comercial. No se requieren dos modelos de IA. El modelo operará de forma asíncrona y su respuesta se validará estrictamente antes de guardar los datos. Esta conexión permanece pausada por solicitud del cliente.

El flujo previsto es, por tanto, **archivo → MarkItDown → Markdown → un modelo de IA → validación → PostgreSQL**. MarkItDown prepara el contenido; no se cuenta como una segunda IA ni se plantea añadir otro modelo para convertir o volver a analizar el archivo.

| Aspecto | Asistente RAG planteado inicialmente | Buscador Comercial vigente |
|---|---|---|
| Forma de uso | Preguntas conversacionales y respuesta generada | Consulta y listado de productos del catálogo |
| Cómo encuentra datos | Similitud entre vectores y texto | Índices de texto de PostgreSQL y respaldo  |
| IA durante la consulta | Podía formar parte del flujo de respuesta | No se invoca ningún modelo al buscar |
| Origen de la respuesta | Recuperación y generación con contexto | Filas existentes en la base de datos |
| Costos y dependencias por consulta | Dependía de la infraestructura de embeddings y del diseño generativo | No requiere llamadas a proveedores externos; la consulta se ejecuta en PostgreSQL |

### Por qué se cambió y qué se gana

El cambio responde a los requisitos funcionales actualizados y prioriza un
buscador comercial verificable sobre un asistente generativo. Para el uso de
consulta de catálogos, el objetivo es encontrar productos concretos con rapidez
y mostrar sus datos reales, no producir explicaciones abiertas.

Los beneficios esperados del enfoque vigente son:

- **Resultados comprobables:** cada resultado corresponde a un producto
  almacenado; el buscador no inventa productos ni precios.
- **Menor latencia en consulta:** PostgreSQL realiza la búsqueda localmente y
  utiliza índices, sin esperar una respuesta de un modelo remoto.
- **Sin costo de IA por búsqueda:** las consultas web no consumen tokens ni
  requieren enviar la consulta a un proveedor externo.
- **Más control y trazabilidad:** el criterio de búsqueda y los resultados se
  apoyan en datos relacionales que la empresa puede revisar.
- **Menos complejidad operativa en el camino de consulta:** el buscador no
  depende de que un modelo o servicio de embeddings esté disponible para
  responder.

El cambio también implica una diferencia funcional: un buscador de texto no
interpreta una conversación del mismo modo que un asistente generativo. Por eso
la calidad del catálogo, la normalización, los sinónimos y las pruebas de
relevancia siguen siendo importantes; no se afirma que toda consulta semántica
quede resuelta automáticamente.

## 5. Estado, límites y continuidad

- **Semana 2:** las tareas de autenticación, seguridad y auditoría indicadas en
  el checklist están marcadas como completadas.
- **Autenticación y roles:** se conservan como base estable; el cambio de
  enfoque del buscador no requiere rehacerlos.
- **Buscador Comercial:** corresponde a una etapa posterior y se desarrolla
  conforme al alcance vigente, separado del chat RAG.
- **Ingesta con Gemini:** permanece pausada por solicitud del cliente. No se
  presenta como verificada ni como habilitada en esta etapa.
- **MVP:** este reporte no declara completo el flujo integral de catálogo,
  ingesta y búsqueda ni sustituye las validaciones pendientes de las semanas
  posteriores.
