# Lista de tareas y cronograma de ejecución (8 semanas)

**Proyecto:** Sistema Web de Inventario e IA RAG  
**Empresa:** FERRE-INVERSIONES PEREZ C.A.  
**Desarrollador:** Dixon Daniel Bastias Hernandez  
**Punto de replanificación:** día 3  
**Duración total:** 8 semanas, sin extender la fecha final  
**Hito obligatorio:** entregar un MVP funcional al cierre de la semana 4

---

## Criterio de replanificación

La ejecución va por el día 3, pero ya se adelantaron y completaron trabajos que
originalmente estaban previstos para semanas posteriores: infraestructura y
base de datos, autenticación y seguridad, interfaz web, ingesta ETL y la
implementación inicial de embeddings y búsqueda vectorial. Se conserva el
alcance de ocho semanas; el trabajo no se vuelve a programar como pendiente.

El cambio principal es adelantar a la semana 4 lo que hace que el prototipo sea
realmente funcional: conectar la búsqueda vectorial con el modelo generativo,
el endpoint existente y el chat web. La interfaz base ya existe, así que en
esta etapa se integra y prueba; no se vuelve a construir. La validación de
relevancia con un catálogo representativo se completa antes de aceptar el MVP.

**MVP al cierre de la semana 4:** un usuario autenticado puede consultar desde
la interfaz un catálogo cargado y vectorizado; el sistema busca productos
reales, genera una respuesta basada únicamente en esos resultados y muestra
las fuentes. Si no hay evidencia suficiente, debe indicarlo sin inventar
productos. El flujo debe estar probado de extremo a extremo y ser demostrable
en el entorno piloto. 

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

## Semana 4: Integración RAG y entrega del MVP funcional

**Estado actual.** La generación de embeddings, la búsqueda vectorial, el
servicio LLM con defensas y la interfaz de chat ya están implementados. El
endpoint todavía devuelve una respuesta provisional; falta conectarlo con la
recuperación y la generación reales antes de considerar entregado el MVP.

- [x] Integrar `intfloat/multilingual-e5-small` con FastEmbed/ONNX y vectores
  de 384 dimensiones. (Preparar el sistema para interpretar consultas y productos en varios idiomas.)
- [x] Implementar la búsqueda de productos por similitud coseno en pgvector y
  preparar la migración `4_0`. (Habilitar la búsqueda de productos parecidos a lo que pregunta la persona.)
- [x] Aplicar `4_0` en el catálogo de desarrollo y confirmar una vectorización
  y búsqueda técnica inicial. (Actualizar la base de prueba y comprobar que la búsqueda funcione.)
- [x] Completar `app/services/llm_service.py` para generar respuestas a partir
  de los productos recuperados y configuración segura del proveedor elegido. (Hacer que el sistema responda usando los productos encontrados y una conexión protegida.)
- [x] Conectar recuperación, generación y validación de respuesta desde
  `POST /api/v1/rag/chat`; conservar el contrato ya publicado. (Unir la búsqueda y la respuesta automática sin cambiar el funcionamiento esperado por otras partes.)
- [x] Limitar las respuestas al contexto del catálogo: no inventar productos,
  precios, stock ni características; reconocer cuando no hay evidencia. (Asegurar que las respuestas usen solo información real del catálogo.)
- [x] Aplicar y probar las defensas contra prompt injection en la consulta y
  en el contexto recuperado. (Evitar que instrucciones maliciosas alteren las respuestas.)
- [x] Conectar el chat con el contrato del endpoint y mostrar la respuesta y
  las fuentes que este devuelve. (La interfaz ya envía preguntas y presenta
  respuestas y fuentes del flujo RAG experimental.)
- [ ] Preparar un catálogo de prueba representativo, vectorizar una muestra
  pequeña y evaluar consultas concretas con resultados esperados. (Probar con productos y preguntas parecidos a los del uso real.)
- [ ] Ejecutar pruebas de extremo a extremo: autenticación, pregunta, búsqueda,
  respuesta fundamentada, fuentes y caso sin resultados. (Verificar el recorrido completo desde el ingreso hasta la respuesta.)
- [ ] Corregir bloqueos de uso del piloto y preparar una demostración funcional. (Resolver problemas que impidan usar el sistema y dejarlo listo para mostrar.)
- [ ] **Criterio de salida del MVP:** flujo completo demostrable desde la web
  sobre productos cargados; respuesta sustentada en resultados reales, fuentes
  visibles, comportamiento honesto sin resultados y pruebas críticas pasando.
  (Condición para considerar listo el prototipo: que pueda demostrarse y responda con información comprobable.)
- [ ] **Entregable:** MVP funcional y Acta 4 con resultados iniciales de
  búsqueda y aceptación del prototipo. (Prototipo utilizable y documento con los resultados iniciales.)

---

## Semana 5: Validación del piloto y calidad del RAG

- [ ] Ampliar el conjunto de consultas y productos de prueba con casos
  representativos del catálogo de la ferretería. (Probar más preguntas y productos habituales del negocio.)
- [ ] Medir relevancia de recuperación, respuestas fundamentadas y casos en
  los que el sistema debe abstenerse. (Comprobar si encuentra productos adecuados y si evita responder cuando no tiene datos.)
- [ ] Medir por separado latencia de búsqueda, generación y respuesta total;
  documentar el entorno y el tamaño de la muestra. (Registrar cuánto tarda cada etapa y en qué condiciones se midió.)
- [ ] Ajustar instrucciones, umbrales de recuperación o presentación si las
  mediciones muestran problemas, sin relajar la regla de no inventar. (Mejorar los resultados sin permitir respuestas inventadas.)
- [ ] Probar errores del proveedor generativo, tiempos de espera y mensajes de
  recuperación para el usuario. (Comprobar que el sistema informe claramente si un servicio falla o tarda.)
- [ ] Revisar seguridad del flujo RAG, manejo de configuración y registros sin
  exponer credenciales ni datos innecesarios. (Verificar que la información sensible no quede expuesta.)
- [ ] **Entregable:** Acta 5 de validación del piloto, calidad, seguridad y
  rendimiento del RAG. (Documento con los resultados de calidad, seguridad y velocidad del piloto.)

---

## Semana 6:  Consulta de bitácora

- [ ] Implementar el endpoint y la vista de consulta de bitácora para
  administradores, manteniendo la bitácora inmutable. (Permitir que administradores revisen el historial sin modificarlo.)
- [ ] Probar permisos, valores límite y trazabilidad de las acciones. (Comprobar quién puede consultar el historial y que las acciones queden registradas.)
- [ ] **Entregable:** Acta 6 de módulo  de bitácora. (Documento que resume el módulo de consulta del historial.)

---

## Semana 7: Preparación de producción y documentación

- [ ] Preparar el entorno VPS y el procedimiento repetible de despliegue con
  Docker. (Preparar el servidor donde se instalará el sistema y los pasos para hacerlo.)
- [ ] Configurar variables y secretos de producción fuera del repositorio. (Guardar claves y ajustes de forma segura, separados del código.)
- [ ] Preparar proxy inverso, HTTPS y dominio, según los datos disponibles del
  cliente. (Configurar una dirección web segura para acceder al sistema.)
- [ ] Definir respaldos, persistencia de base de datos, archivos cargados y
  caché del modelo; documentar recuperación básica. (Planificar copias de seguridad y cómo restaurar la información.)
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
- [ ] Aplicar o verificar las migraciones necesarias y cargar/vectorizar una
  muestra autorizada del catálogo de producción. (Preparar la base de datos y cargar productos aprobados para el uso real.)
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

## Hitos de control

| Hito | Fecha objetivo | Condición de aceptación |
|---|---|---|
| Replanificación | Día 3 | Semanas 1–3 registradas como completadas; trabajo restante priorizado |
| MVP funcional | Cierre de semana 4 | Consulta web real, recuperación vectorial, respuesta fundamentada, fuentes y pruebas de flujo |
| Validación del piloto | Cierre de semana 5 | Relevancia, latencia, seguridad y abstención documentadas |
| Módulos administrativos | Cierre de semana 6 | Inventario y bitácora operables con permisos y reglas de negocio |
| Preparación de producción | Cierre de semana 7 | Despliegue ensayado, secretos, respaldos y documentación listos |
| Entrega definitiva | Cierre de semana 8 | VPS verificado, pruebas finales y conformidad del cliente |

**Regla de alcance:** si una validación del MVP revela un defecto que impide
responder de forma fundamentada o segura, se prioriza corregirlo sobre
funcionalidades administrativas no esenciales. No se elimina ninguna de las
ocho semanas ni se desplaza la entrega del MVP más allá de la semana 4.
