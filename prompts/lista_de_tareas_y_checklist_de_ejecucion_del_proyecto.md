# Lista de tareas y cronograma de ejecución (8 semanas)

**Proyecto:** Sistema Web de Inventario y Buscador Comercial  
**Empresa:** FERRE-INVERSIONES PEREZ C.A.  
**Desarrollador:** Dixon Daniel Bastias Hernandez  
**Punto de replanificación:** día 3  
**Duración total:** 8 semanas, sin extender la fecha final  
**Hito obligatorio:** entregar un MVP funcional al cierre de la semana 4

---

## Criterio de replanificación

La ejecución va por el día 3, pero ya se adelantaron y completaron trabajos que
originalmente estaban previstos para semanas posteriores: infraestructura y
base de datos, autenticación y seguridad, interfaz web e ingesta ETL. Se
conserva el alcance de ocho semanas y el trabajo no se vuelve a programar como
pendiente. Los módulos de **autenticación, roles y usuarios** quedan tal como
fueron planeados y **no se modifican**.

**Cambio de alcance:** el antiguo "Módulo de Asistente IA Conversacional (Chat
RAG)" se sustituye **exclusivamente** por el **Módulo de Buscador Comercial
("Live Search" de Proveedores y Productos)**. En consecuencia:

- El trabajo previo de embeddings, búsqueda vectorial y chat generativo **queda
  fuera del alcance activo y no se continúa**.
- La búsqueda se resuelve con **Full-Text Search nativo de PostgreSQL
  (`tsvector`/`tsquery` o `ILIKE`)**: respuestas en milisegundos sobre los
  ~8.000 productos, a costo cero y **sin IA en tiempo real**.
- El ETL es **100 % local**: los archivos se procesan con **parsers de Python**
  (`pandas`/`openpyxl` para Excel, `pdfplumber`/`PyMuPDF` para PDF,
  `python-docx` para Word y lectura nativa para TXT) y lógica determinista con
  expresiones regulares. **No se usan modelos generativos ni LLM** (OpenRouter,
  Gemini u otros) durante la ingesta.
- Si un archivo no encaja en la estructura esperada, se rechaza ese archivo con
  un mensaje claro al usuario; no se intenta adivinar su contenido con IA.

**Fase 1 (prioritaria y exclusiva):** las semanas 4 y 5 se dedican de lleno al
Buscador de Catálogos de Proveedores —subida de archivos, parsers locales en
Python, persistencia relacional y búsqueda web con AJAX— hasta lograr el MVP de
la semana 4.

**Fase 2 (diferida):** el **Módulo de Conexión con la Base de Datos del Sistema
de Ventas** (reportes de ventas, stock real y métricas comerciales) queda
documentado más abajo como bloque **en pausa**; no se inicia hasta que el
cliente dé la orden explícita.

**MVP al cierre de la semana 4:** un usuario autenticado sube un catálogo de
proveedores, el ETL local extrae y normaliza los registros con los parsers de
Python y los guarda de forma estructurada en PostgreSQL, y desde la interfaz web
puede buscar productos con AJAX obteniendo resultados **instantáneos
(milisegundos)** por Full-Text Search, mostrando producto, precio, proveedor y
número de contacto. El buscador devuelve únicamente productos reales de la base
de datos; si no hay coincidencias lo indica sin inventar productos. El flujo debe
estar probado de extremo a extremo y ser demostrable en el entorno piloto.

---

## Semana 1: Infraestructura y base de datos — completada

- [x] Preparar WSL2/virtualización, VS Code, Git, Python y Docker Desktop. (Dejar listas las herramientas necesarias para desarrollar el sistema.)
- [x] Crear el repositorio, el entorno virtual y las dependencias iniciales. (Organizar el proyecto y preparar los programas que necesita para funcionar.)
- [x] Configurar Docker Compose y PostgreSQL con pgvector. (Preparar la base de datos y los servicios que usa el sistema.)
- [x] Definir el esquema inicial de usuarios, roles, bitácora y catálogo. (Establecer qué información guardará el sistema y quién podrá usarla.)
- [x] Verificar el inicio de la base de datos y la configuración de contenedores. (Comprobar que la base de datos y sus servicios arranquen correctamente.)
- [x] **Entregable:** Acta 1 de infraestructura y base de datos. (Documento que resume el trabajo de preparación.)

---

## Semana 2: Autenticación, seguridad y auditoría — completada

- [x] Implementar usuarios, roles, validación de credenciales y registro inicial. (Permitir crear usuarios y controlar quién puede entrar al sistema.)
- [x] Implementar hashing de contraseñas con scrypt y tokens JWT con expiración. (Proteger las contraseñas y limitar la duración de las sesiones.)
- [x] Añadir middleware de auditoría y controles de acceso. (Registrar acciones importantes y restringir el acceso según los permisos.)
- [x] Cubrir login, expiración de tokens, entradas límite e intentos de SQL
  injection con pruebas. (Comprobar que el acceso y sus protecciones funcionen correctamente.)
- [x] **Entregable:** Acta 2 de seguridad JWT y auditoría. (Documento que resume las medidas de acceso y seguridad realizadas.)

---

## Semana 3: Interfaz e ingesta ETL — completada

La interfaz se adelantó mediante la Adenda 1 y el motor de ingesta base se
terminó antes de la etapa prevista. Se registran aquí como trabajo ejecutado, no
como tareas pendientes. La directriz vigente exige que la extracción y
estructuración se realicen con **parsers locales de Python, sin IA**; la
adaptación y validación de ese motor se controla en la Semana 4.

- [x] Implementar acceso, panel y buscador web. (Crear las pantallas para entrar, recuperar la cuenta y usar el sistema.)
- [x] Añadir temas claro/oscuro, protección CSRF y empaquetado de la API en
  Docker. (Permitir cambiar la apariencia, proteger acciones web y preparar la API para ejecutarse en contenedores.)
- [x] Implementar la carga e historial de catálogos PDF, XLSX, DOCX y TXT. (Permitir cargar catálogos y consultar los archivos enviados.)
- [x] Validar archivos de forma independiente, normalizar productos y hacer
  upsert por código sin sobrescribir el stock. (Revisar cada archivo y actualizar productos sin cambiar las existencias.)
- [x] Añadir una previsualización que permita revisar el catálogo y confirmar
  las columnas de precio antes de guardar productos. (Comprobar los datos antes
  de incorporarlos al inventario.)
- [x] Registrar los datos de cotización y vincular productos con sus ofertas
  por proveedor, conservando el origen conocido en la migración `8_0`.
  (Guardar quién ofrece cada producto y en qué condiciones, sin adivinar
  proveedores para registros históricos.)
- [x] Añadir límites, persistencia segura de originales y migración ETL. (Controlar el tamaño de las cargas y conservar sus archivos de forma segura.)
- [x] Verificar el lote reducido de estrés: 20 archivos / 5000 productos. (Comprobar que el sistema soporte una carga de prueba considerable.)
- [x] **Entregables:** Acta de la Adenda 1 y Acta 3 de ingesta ETL. (Documentos que resumen la interfaz y la carga de catálogos.)

---

## Ajuste de roles y permisos — completado

- [x] Migrar `ferreteria_usuarios` de forma incremental para guardar
  capacidades y su asignación a roles sin perder cuentas. (Actualizar la base
  conservando los datos.)
- [x] Administrar roles y capacidades desde Configuración, solo para
  `admin`, y proteger ese rol y al último administrador activo. (Permitir
  delegar funciones sin perder el acceso de administración.)
- [x] Revalidar permisos desde el servidor en cada petición y cubrir cambios,
  revocaciones y límites con pruebas. (Aplicar de inmediato los cambios de
  acceso y comprobar que nadie pueda evitarlos.)
- [x] Alinear la guía de uso, requisitos, arquitectura y sistema visual con el
  modelo nuevo. (Mantener consistentes los documentos vigentes del proyecto.)

---

## Semana 4: Buscador Comercial (Live Search) y entrega del MVP funcional

**Estado actual.** La búsqueda Full-Text de PostgreSQL, el endpoint y la
interfaz del buscador ya están implementados y operan directamente sobre los
productos guardados, sin exigir archivos cargados. El chat RAG y los embeddings
quedan fuera del alcance activo. La directriz vigente elimina la IA del ETL: las
etapas de conversión a Markdown y estructuración con modelos externos se retiran
del alcance y se sustituyen por **parsers locales de Python con lógica
determinista**. Queda pendiente consolidar y validar ese ETL local, probarlo con
un catálogo representativo, ejecutar el recorrido de extremo a extremo y
demostrar el MVP.

- [x] Implementar y consolidar los **parsers locales** del ETL: `pandas` y
  `openpyxl` para `.xlsx`; `pdfplumber` y `PyMuPDF` (`fitz`) para `.pdf`;
  `python-docx` para `.docx`; lectura nativa para `.txt`. (Extraer códigos,
  descripciones, precios y datos de proveedor sin servicios externos.)
  — Implementado en `etl_service.py`: 91 funciones privadas cubriendo XLSX
  (`_extraer_xlsx`), PDF con 6 estrategias (`_extraer_pdf_espacial`,
  `_extraer_pdf_fichas`, `_extraer_pdf_cuadros`, `_extraer_pdf_columnas`,
  `_extraer_pdf_etiquetas`, `_extraer_pdf_tabla_dolar`), DOCX
  (`_extraer_docx`) y TXT (`_extraer_txt`).
- [x] Definir el mapeo determinista de columnas y cabeceras, junto con
  expresiones regulares para precios, códigos y contactos. (Normalizar los
  datos con reglas reproducibles y auditables.)
  — `SINONIMOS` cubriendo codigo/nombre/precio/marca/descuento/proveedor/telefono,
  `_leer_precio` con regex robustas, `_es_codigo_pdf`, `_es_precio_pdf`,
  `_mapear_cabecera` y `_inferir_columnas`.
- [x] Rechazar los archivos de formato irregular o incompatible con un mensaje
  claro al usuario, sin intentar adivinarlos con IA y sin detener el resto del
  lote. (Aplicar la plantilla estándar o corregir las columnas antes de
  reintentar.)
  — `_validar_paquete` con guardabrisas de ZIP-bomb, `_validar_paginas_docx`,
  `_validar_archivos_limite`, mensajes de error claros por archivo (no afecta
  al lote), límite de errores por detalle 20.
- [x] Guardar los datos extraídos de forma directa y estructurada en las tablas
  relacionales de PostgreSQL (producto, precio, proveedor y número de
  contacto), sin alterar stock, sin inventar proveedores y conservando la
  trazabilidad al archivo de origen.
  — `crear_archivo` (con advisory lock para proveedor), `upsert_producto`
  (upsert por codigo sin tocar stock), `crear_oferta` (vinculacion
  producto-proveedor), migraciones `3_0` y `8_0`.
- [x] Preparar la indexación **Full-Text Search** de PostgreSQL (columna
  `tsvector` + índice) sobre productos y consultar con `tsquery`, con respaldo
  `ILIKE`. (Habilitar búsquedas instantáneas y a costo cero en los ~8.000
  productos.)
- [x] Exponer el endpoint de búsqueda y consumirlo desde la interfaz web con
  Bootstrap + AJAX, agregando la pantalla del **buscador
  comercial**. (Mostrar resultados de productos en tiempo real sin recargar la
  página y sin IA en tiempo real. La consulta puede tener desde un carácter y
  busca directamente en `productos`, aunque no se hayan cargado archivos.)
- [x] Asegurar que los resultados y el detalle de cada coincidencia muestren
  producto, precio, proveedor y **número de contacto** asociado, sin exponer
  datos innecesarios. (Completar la información comercial exigida por el
  buscador.)
  — `inventario.py:344` mapea `telefono_vendedor` del proveedor en la respuesta
  de búsqueda; la tabla de resultados en `buscador.html` muestra columnas de
  producto, precio, proveedor y contacto. Falta validación E2E con catálogo
  real.
- [x] Cubrir con pruebas unitarias los parsers locales y la normalización:
  archivos válidos, columnas faltantes, precios con formatos distintos, valores
  límite y rechazo de formatos incompatibles. (Comprobar que cada formato se
  procese sin IA y que los errores se informen con claridad.)
  — `test_etl_service.py` cubre XLSX/PDF/DOCX/TXT con casos validos, columnas
  faltantes y formatos incompatibles; `test_api_ingesta.py` prueba el flujo
  completo de ingesta; cobertura en expansion.
- [x] Cubrir la búsqueda con pruebas unitarias y de API, incluidos valores
  límite. (En una ejecución focalizada pasaron pruebas de búsqueda y consultas
  límite. Las pruebas de integración que no pudieron preparar la base
  (`relation "productos" does not exist`) deben repetirse antes de aceptar el
  MVP.)
- [x] Redirigir al usuario a `/search` después de iniciar sesión y al abrir
  `/login` con una sesión activa. (Dejar el buscador como destino directo de
  entrada al sistema.)
- [ ] Optimizar ETL para procesamiento por streaming (evitar OOM en archivos grandes).
- [ ] Preparar un catálogo de prueba representativo (~8.000 productos) y
  evaluar consultas concretas con resultados esperados. (Probar con productos
  y búsquedas parecidas a las del uso real.)
- [ ] Ejecutar pruebas de extremo a extremo: autenticación, subida de archivo,
  ETL, búsqueda instantánea, resultados reales y caso sin coincidencias.
  (Verificar el recorrido completo desde el ingreso hasta los resultados.)
- [ ] Corregir bloqueos de uso del piloto y preparar una demostración
  funcional. (Resolver problemas que impidan usar el sistema y dejarlo listo
  para mostrar.)
- [ ] **Criterio de salida del MVP:** flujo completo demostrable desde la web
  sobre productos cargados con los parsers locales; respuestas en milisegundos,
  resultados limitados a productos reales con precio, proveedor y número de
  contacto, sin IA en la ingesta ni en tiempo real, comportamiento honesto sin
  coincidencias y pruebas críticas pasando.
  (Condición para considerar listo el prototipo: que pueda demostrarse y
  encuentre solo productos comprobables.)
- [ ] **Entregable:** MVP funcional del Buscador Comercial y Acta 4 con
  resultados iniciales de búsqueda y aceptación del prototipo. (Prototipo
  utilizable y documento con los resultados iniciales.)

---

## Semana 5: Validación del piloto y calidad del Buscador Comercial

- [ ] Ampliar el conjunto de consultas y productos de prueba con casos
  representativos del catálogo de la ferretería. (Probar más búsquedas y
  productos habituales del negocio.)
- [ ] Medir la relevancia del Full-Text Search: coincidencias exactas,
  parciales, sinónimos, acentos, mayúsculas y casos sin resultados.
  (Comprobar que la búsqueda encuentre lo que la persona busca.)
- [ ] Medir la latencia real de la búsqueda (objetivo por debajo de 100 ms) y
  documentar el entorno y el tamaño de la muestra. (Registrar cuánto tarda la
  consulta en condiciones reales.)
- [ ] Ajustar la indexación según las mediciones: pesos, sinónimos, prefijos en
  `tsquery` o respaldo con `ILIKE`. (Mejorar la precisión y la velocidad sin
  añadir IA en tiempo real.)
- [ ] Verificar que ninguna consulta del usuario ni ninguna etapa del ETL
  invoque un modelo de lenguaje, un servicio de embeddings o una API externa de
  IA. (Confirmar que la búsqueda y la ingesta sean locales en PostgreSQL y
  Python, a costo cero.)
- [ ] Probar fallos del ETL local: archivos corruptos, columnas faltantes,
  formatos incompatibles, precios ilegibles y lotes que superan los límites;
  comprobar que el rechazo sea por archivo, con mensaje claro, sin detener el
  resto del lote.
- [ ] Revisar seguridad del flujo de búsqueda y del ETL, manejo de
  configuración y registros sin exponer credenciales ni datos innecesarios.
  (Confirmar que el ETL no requiere claves de OpenRouter/Gemini y que la
  información sensible no quede expuesta.)
- [ ] **Entregable:** Acta 5 de validación del piloto, relevancia, seguridad y
  rendimiento del Buscador Comercial. (Documento con los resultados de
  precisión, velocidad y seguridad del piloto.)

---

## Semana 6:  Consulta de bitácora

- [ ] Implementar el endpoint y la vista de consulta de bitácora para
  administradores, manteniendo la bitácora inmutable. (Permitir que administradores revisen el historial sin modificarlo.)
- [x] Probar permisos, valores límite y trazabilidad de las acciones. (Comprobar quién puede consultar el historial y que las acciones queden registradas.)
- [x] **Entregable:** Acta 6 de módulo  de bitácora. (Documento que resume el módulo de consulta del historial.)

---

## Semana 7: Preparación de producción y documentación

- [ ] Preparar el entorno VPS y el procedimiento repetible de despliegue con
  Docker. (Preparar el servidor donde se instalará el sistema y los pasos para hacerlo.)
- [ ] Configurar variables y secretos de producción fuera del repositorio. (Guardar claves y ajustes de forma segura, separados del código.)
- [ ] Preparar proxy inverso, HTTPS y dominio, según los datos disponibles del
  cliente. (Configurar una dirección web segura para acceder al sistema.)
- [ ] Definir respaldos, persistencia de base de datos, archivos cargados y
  configuración del ETL local; documentar recuperación básica. (Planificar
  copias de seguridad y cómo restaurar la información; el ETL no requiere
  claves de IA.)
- [ ] Revisar salud, logs, permisos, límites de recursos y configuración de la
  API para el entorno de producción. (Comprobar que el sistema esté preparado para funcionar en el servidor.)
- [ ] Redactar y revisar manual técnico y guía breve de uso para el personal. (Preparar instrucciones para quienes administren y utilicen el sistema.)
- [ ] Preparar un ensayo de despliegue y una lista de verificación para la
  entrega final. (Practicar la instalación y confirmar que no falten pasos.)
- [ ] **Entregable:** Acta 7 de preparación de producción y documentación. (Documento con el estado de preparación del servidor y los manuales.)

---

## Semana 8: Despliegue, pruebas finales y entrega definitiva

- [ ] Desplegar el sistema en el VPS y verificar salud, HTTPS, acceso y
  persistencia después de reinicios. (Instalar el sistema en el servidor y comprobar que siga funcionando al reiniciarlo.)
- [ ] Aplicar o verificar las migraciones necesarias y cargar una muestra
  autorizada del catálogo de producción, confirmando la búsqueda full-text
  sobre esa muestra. (Preparar la base de datos y comprobar que la búsqueda funcione con datos reales.)
- [ ] Ejecutar pruebas finales funcionales, de permisos, seguridad y
  recuperación ante fallos. (Confirmar que las funciones, accesos y recuperación funcionen correctamente.)
- [ ] Ejecutar en el VPS la prueba de carga acordada; reportar resultados y
  límites observados sin extrapolar datos de pruebas menores. (Medir el desempeño del servidor real e informar los resultados obtenidos.)
- [ ] Resolver defectos críticos y verificar nuevamente los flujos principales. (Corregir los problemas más importantes y repetir las comprobaciones.)
- [ ] Entregar manuales y capacitar al personal de la ferretería. (Dar las instrucciones y enseñar al personal a utilizar el sistema.)
- [ ] Obtener conformidad del cliente y registrar pendientes aceptados, si los
  hubiera. (Confirmar que el cliente recibe el sistema y dejar por escrito los pendientes aceptados.)
- [ ] **Entregable:** Acta 8 final de entrega, conformidad y recepción del
  sistema. (Documento que registra la entrega y aceptación final del sistema.)

---

## Fase 2 (EN PAUSA): Conexión con el Sistema de Ventas de la Ferretería

> **No iniciar sin orden explícita del cliente.** Este bloque está documentado
> para dejar constancia del alcance diferido; no consume semanas del
> cronograma y ninguna de sus tareas puede desplazar el Buscador Comercial.
> Al activarse, deberá respetar sin cambios los módulos de autenticación,
> roles y capacidades ya definidos.

- [ ] Conectar el sistema con la base de datos del sistema de ventas de la
  ferretería (solo lectura) y documentar su esquema y credenciales.
  (Preparar la fuente de datos de las ventas sin modificarla.)
- [ ] Implementar reportes de ventas a partir de esa conexión.
  (Mostrar cómo se han vendido los productos.)
- [ ] Mostrar stock real contrastado con el inventario del sistema.
  (Comparar las existencias registradas con las del punto de venta.)
- [ ] Implementar métricas comerciales y tablero de indicadores.
  (Resumir el desempeño del negocio en pantalla.)
- [ ] Probar permisos, latencia y trazabilidad de los reportes.
  (Comprobar que solo las personas autorizadas vean los reportes y que las
  consultas no afecten la velocidad del buscador.)
- [ ] **Entregable:** Acta de la Fase 2 con los reportes operativos y
  aceptación del cliente. (Documento que registra la entrega de este módulo
  cuando se autorice.)

---
