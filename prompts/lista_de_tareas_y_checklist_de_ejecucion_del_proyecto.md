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
- El ETL convierte los archivos con **Microsoft MarkItDown** a Markdown y un
  modelo rápido (**Gemini Flash**) estructura los registros (sugiriendo un
  nombre comercial cuando falte) antes de guardarlos en PostgreSQL.

**Fase 1 (prioritaria y exclusiva):** las semanas 4 y 5 se dedican de lleno al
Buscador de Catálogos de Proveedores —subida de archivos, MarkItDown, ETL con
IA, base de datos y búsqueda web con AJAX— hasta lograr el MVP de la semana 4.

**Fase 2 (diferida):** el **Módulo de Conexión con la Base de Datos del Sistema
de Ventas** (reportes de ventas, stock real y métricas comerciales) queda
documentado más abajo como bloque **en pausa**; no se inicia hasta que el
cliente dé la orden explícita.

**MVP al cierre de la semana 4:** un usuario autenticado sube un catálogo de
proveedores, el ETL lo convierte con MarkItDown y lo estructura con Gemini
Flash en tablas relacionales de PostgreSQL, y desde la interfaz web puede
buscar productos con AJAX obteniendo resultados **instantáneos (milisegundos)**
por Full-Text Search. El buscador devuelve únicamente productos reales de la
base de datos; si no hay coincidencias lo indica sin inventar productos. El
flujo debe estar probado de extremo a extremo y ser demostrable en el entorno
piloto. 

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

La interfaz se adelantó mediante la Adenda 1 y el motor de ingesta se terminó
antes de la etapa prevista. Se registran aquí como trabajo ejecutado, no como
tareas pendientes.

- [x] Implementar acceso, panel y chat web. (Crear las pantallas para entrar, recuperar la cuenta y usar el sistema.)
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

**Estado actual.** La interfaz base, la carga de catálogos y el panel de
archivos ya existen y se reutilizan; el chat RAG queda fuera de alcance y no se
termina. Todo lo que hace funcional al buscador —MarkItDown, estructuración con
Gemini Flash, Full-Text Search y la pantalla de resultados— está pendiente y es
el foco exclusivo de esta semana.

- [ ] Integrar **Microsoft MarkItDown** en el pipeline ETL para convertir los
  archivos PDF, Excel y Word a formato Markdown. (Unificar la lectura de los
  documentos en un solo paso de conversión.)
- [ ] Conectar **Gemini Flash** para que tome el Markdown, estructure los
  registros y genere un **nombre comercial sugerido** cuando el producto no
  tenga uno. (Ordenar los datos crudos del archivo en campos de producto
  claros.)
- [ ] Validar la respuesta del modelo y guardar los datos limpios en las tablas
  relacionales de PostgreSQL, sin alterar stock ni inventar proveedores.
  (Persistir solo información válida y trazable al archivo de origen.)
- [ ] Preparar la indexación **Full-Text Search** de PostgreSQL (columna
  `tsvector` + índice) sobre productos y consultar con `tsquery`, con respaldo
  `ILIKE`. (Habilitar búsquedas instantáneas y a costo cero en los ~8.000
  productos.)
- [ ] Exponer el endpoint de búsqueda y consumirlo desde la interfaz web con
  Bootstrap + AJAX, agregando la pantalla del **buscador
  comercial**. (Mostrar resultados de productos en tiempo real sin recargar la
  página y sin IA en tiempo real.)
- [ ] Cubrir el ETL nuevo y la búsqueda con pruebas unitarias y de API,
  incluidos valores límite. (Comprobar que la conversión, la estructuración y
  la búsqueda se comporten correctamente.)
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
  sobre productos cargados; respuestas en milisegundos, resultados limitados a
  productos reales, sin IA en tiempo real, comportamiento honesto sin
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
- [ ] Verificar que ninguna consulta del usuario invoque un modelo de
  lenguaje ni embeddings en tiempo real. (Confirmar que la búsqueda sea local
  en PostgreSQL y a costo cero.)
- [ ] Probar fallos del ETL con modelo (respuesta inválida de Gemini Flash,
  límite de tokens, proveedor caído) y mensajes de recuperación para el
  usuario. (Comprobar que el sistema informe claramente si un servicio falla
  o tarda.)
- [ ] Revisar seguridad del flujo de búsqueda y del ETL, manejo de
  configuración y registros sin exponer credenciales (incluida la clave de
  Gemini) ni datos innecesarios. (Verificar que la información sensible no
  quede expuesta.)
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
  claves del ETL (Gemini Flash); documentar recuperación básica. (Planificar copias de seguridad y cómo restaurar la información.)
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

## Hitos de control

| Hito | Fecha objetivo | Condición de aceptación |
|---|---|---|
| Replanificación | Día 3 | Semanas 1–3 registradas como completadas; alcance del Buscador Comercial priorizado; autenticación y roles intactos |
| MVP funcional | Cierre de semana 4 | Catálogo subido, ETL con MarkItDown + Gemini Flash, búsqueda full-text en milisegundos desde la web, resultados reales y pruebas de flujo |
| Validación del piloto | Cierre de semana 5 | Relevancia, latencia (milisegundos), seguridad y comportamiento sin coincidencias documentados |
| Módulos administrativos | Cierre de semana 6 | Inventario y bitácora operables con permisos y reglas de negocio |
| Preparación de producción | Cierre de semana 7 | Despliegue ensayado, secretos, respaldos y documentación listos |
| Entrega definitiva | Cierre de semana 8 | VPS verificado, pruebas finales y conformidad del cliente |
| Fase 2: sistema de ventas | Por ordenar | **En pausa:** inicia solo con orden explícita del cliente; reportes, stock real y métricas |

**Regla de alcance:** si una validación del MVP revela un defecto que impide
buscar de forma rápida y segura, se prioriza corregirlo sobre
funcionalidades administrativas no esenciales. No se elimina ninguna de las
ocho semanas ni se desplaza la entrega del MVP más allá de la semana 4. El
bloque de reportes de ventas (Fase 2) permanece en pausa hasta la orden
explícita de iniciar su desarrollo, sin alterar la arquitectura de
autenticación y roles ya definida.
