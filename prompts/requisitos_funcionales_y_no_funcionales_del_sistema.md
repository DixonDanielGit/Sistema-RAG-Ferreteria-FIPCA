# Especificación de Requisitos del Sistema (SRS)

**Proyecto:** Sistema Web de Gestión de Inventario y Buscador Comercial de Catálogos  
**Empresa:** FERRE-INVERSIONES PEREZ C.A.  
**Desarrollador:** Dixon Daniel Bastias Hernandez  
**Arquitectura:** Web Desacoplada (FastAPI + PostgreSQL Full-Text Search + HTML5/Bootstrap 5/AJAX)

---

## 0. Alcance vigente y estrategia secuencial

- **Sustitución del asistente RAG:** el antiguo "Módulo de Asistente IA Conversacional
  (Chat RAG)" queda sustituido **exclusivamente** por el **Módulo de Buscador
  Comercial ("Live Search" de Proveedores y Productos)**. No se mantiene un chat
  generativo en tiempo real en la interfaz.
- **Módulos intactos:** los módulos de **Autenticación, Control de Roles y
  Usuarios (RF-01)** y la **Bitácora inmutable de Auditoría (RF-05)** conservan
  su arquitectura y sus esquemas tal como fueron planeados inicialmente; esta
  especificación no los modifica ni los renumera.
- **ETL sin IA generativa:** la ingesta de catálogos es **100 % local**. No se
  envían archivos, fragmentos de texto ni Markdown a OpenRouter, Gemini ni a
  ningún otro modelo de lenguaje (LLM). La extracción se realiza con parsers
  nativos de Python y lógica determinista.
- **Fase 1 (prioritaria y exclusiva):** desarrollar, probar y estabilizar el
  Buscador de Catálogos de Proveedores: subida de archivos, extracción local con
  parsers de Python, normalización determinista, base de datos relacional en
  PostgreSQL y búsqueda web con AJAX.
- **Fase 2 (posterior y condicionada):** el **Módulo de Conexión con la Base de
  Datos del Sistema de Ventas de la Ferretería** (reportes de ventas, stock real
  y métricas comerciales) queda documentado en este SRS como módulo
  **diferido/secundario** y **en pausa** hasta que el cliente dé la orden
  explícita de iniciar su desarrollo.

---

## 1. Requisitos Funcionales (RF)

### RF-01: Autenticación y control de acceso por roles y capacidades
- **RF-01.1:** El sistema debe permitir el inicio de sesión seguro mediante tokens JWT (JSON Web Tokens).
- **RF-01.2:** El rol protegido `admin` conserva acceso total. `ventas` es el perfil inicial de consulta; pueden crearse perfiles adicionales con capacidades seleccionadas de un catálogo fijo. El servidor autoriza cada operación según las capacidades vigentes del usuario.
- **RF-01.3:** Cierre de sesión automático tras período de inactividad.
- **RF-01.4:** Las cuentas con `usuarios:gestionar` pueden crear, consultar,
  cambiar roles y activar/desactivar cuentas. Solo `admin` puede asignar el rol
  protegido `admin`. No se eliminan cuentas físicamente y debe quedar al menos
  un administrador activo.
- **RF-01.5:** Cada usuario puede actualizar su perfil y fotografía, y consultar
  la versión y vigencia de sesión. El diagnóstico técnico requiere
  `configuracion:diagnostico`.
- **RF-01.6:** Solo `admin` puede crear, consultar, editar y eliminar roles
  desde Configuración y asignarles capacidades del catálogo vigente. `admin` no
  se puede editar ni eliminar; tampoco se puede eliminar un rol con cuentas
  asignadas. Los cambios de capacidad se aplican sin esperar a renovar el JWT.

### RF-02: Gestión y Ingesta Masiva de Catálogos (Motor ETL)
- **RF-02.1:** Extracción, transformación y carga (ETL) de archivos de proveedores en formatos PDF, Excel (`.xlsx`), Word (`.docx`) y texto (`.txt`). No se admiten `.xls` ni `.csv`.
- **RF-02.2:** Normalización automática de datos de productos (códigos, precios, marcas, descripciones, equivalencias, proveedor y número de contacto).
- **RF-02.3:** Tolerancia a fallos durante la ingesta masiva sin detener el servicio.
- **RF-02.4:** El contenido se extrae **localmente en Python** según el formato del archivo:
  - `.xlsx`: lectura directa y ultrarrápida con **pandas** y **openpyxl**, a partir de la estructura de columnas y cabeceras.
  - `.pdf`: extracción de texto con **pdfplumber** y **PyMuPDF (`fitz`)**.
  - `.docx`: extracción con **python-docx**.
  - `.txt`: lectura nativa de texto plano.

  No se utiliza conversión a Markdown ni se depende de servicios externos para leer los archivos.
- **RF-02.5:** La estructuración es **determinista**: mapeo de columnas y cabeceras, expresiones regulares (Regex) y reglas de normalización para identificar códigos, descripciones, precios, proveedores y contactos. Queda **prohibido** el uso de modelos generativos o LLM (OpenRouter, Gemini u otros) en cualquier etapa de la ingesta.
- **RF-02.6:** Si un archivo presenta un formato irregular o incompatible que el
  parser local no pueda interpretar de forma limpia, el sistema **no intenta
  adivinarlo con IA**: rechaza únicamente ese archivo y devuelve al usuario un
  mensaje claro (por ejemplo, "Formato de catálogo no compatible, por favor
  verifique las columnas o use la plantilla estándar"). El resto del lote
  continúa procesándose.
- **RF-02.7:** Los datos limpios resultantes se persisten de forma directa y
  estructurada en tablas relacionales de PostgreSQL (productos, precios,
  proveedores, contactos, categorías y archivos subidos), conservando la
  trazabilidad del archivo de origen.

### RF-03: Módulo de Buscador Comercial ("Live Search" de Proveedores y Productos)
- **RF-03.1:** La interfaz web (Bootstrap 5 + AJAX) permite buscar en tiempo
  real sobre los catálogos de proveedores y productos cargados, sin recargas
  completas de página, para un universo de aproximadamente **8.000 productos**.
- **RF-03.2:** Las consultas **no usan IA en tiempo real**: se resuelven con el
  **Full-Text Search nativo de PostgreSQL (`tsvector`/`tsquery`)**, con respaldo
  `ILIKE` cuando corresponda, para garantizar respuestas **instantáneas
  (milisegundos)** y a **costo cero** por consulta.
- **RF-03.3:** Los resultados se limitan estrictamente a los productos existentes
  en la base de datos y muestran, como mínimo, **producto, precio, proveedor y
  número de contacto** (además de código, nombre comercial, marca y categoría
  cuando estén disponibles); el buscador **nunca inventa productos ni precios** y
  debe indicar claramente cuando no hay coincidencias.
- **RF-03.4:** El buscador sustituye al chat conversacional: la pantalla de
  consulta muestra resultados de productos con sus datos comerciales, no
  respuestas generativas en lenguaje natural.

### RF-04: Gestión Administrativa de Inventario
- **RF-04.1:** Módulo CRUD (Crear, Leer, Actualizar, Eliminar) para productos en inventario.
- **RF-04.2:** Gestión de campos técnicos: SKU/Código, Nombre, Marca, Precio Base, Descuentos, Aplicación de IVA (16%) y Stock Actual. No existe una columna `stock_minimo`.
- **RF-04.3:** Filtros de búsqueda rápida y alertas visuales de bajo stock mediante un umbral global.

### RF-05: Bitácora inmutable de Auditoría
- **RF-05.1:** Registro automático e inmutable de toda acción realizada (login, inserción, modificación de precios, consultas del buscador, errores).
- **RF-05.2:** Visor de auditoría para el administrador con filtros por fecha, usuario, módulo e IP de origen.

### RF-06: Conexión con el Sistema de Ventas de la Ferretería (Fase 2 — diferido)
- **RF-06.1:** Módulo **secundario y en pausa**: conexión con la base de datos
  del sistema de ventas existente para consultar reportes de ventas, stock real
  y métricas comerciales.
- **RF-06.2:** Su diseño y cronograma quedan documentados, pero **no se
  desarrolla ni se prueba hasta que el cliente dé la orden explícita** de
  iniciar la Fase 2. Ninguna tarea de este módulo puede desplazar el alcance de
  la Fase 1 (Buscador Comercial).
- **RF-06.3:** Cuando se autorice, deberá respetar los módulos de autenticación,
  roles y capacidades ya definidos (RF-01), sin alterarlos.

---

## 2. Requisitos No Funcionales (RNF)

### RNF-01: Rendimiento y Latencia
- **RNF-01.1:** Tiempo de respuesta del servidor FastAPI en peticiones AJAX no debe superar los 300 ms.
- **RNF-01.2:** Búsquedas resueltas por Full-Text Search de PostgreSQL en
  milisegundos (objetivo por debajo de 100 ms) sobre los ~8.000 productos, sin
  llamadas a modelos de lenguaje en el camino crítico de consulta y a costo
  cero por búsqueda.
- **RNF-01.3:** Interfaz ligera sin recargas completas de página (construida en Bootstrap 5 + JavaScript vanilla/AJAX).

### RNF-02: Seguridad y Protección de Datos
- **RNF-02.1:** Contraseñas encriptadas mediante algoritmos de hashing seguros (`scrypt` o `bcrypt`).
- **RNF-02.2:** Sanitización de todas las entradas para prevenir Inyecciones SQL y Cross-Site Scripting (XSS).
- **RNF-02.3:** El pipeline ETL se ejecuta íntegramente en local: **no se
  transmiten archivos, fragmentos de texto ni Markdown a servicios externos de
  IA**. Se validan estructura, tipos y rangos antes de persistir, se sanean las
  entradas y se rechazan los registros inválidos (defensa contra datos
  malformados y contenido malicioso incrustado en el catálogo). La consulta del
  usuario tampoco se envía a un modelo de lenguaje.
- **RNF-02.4:** El ETL no requiere claves de API de OpenRouter, Gemini ni de
  ningún proveedor de IA. Los registros y mensajes de error no deben exponer
  credenciales ni datos innecesarios.

### RNF-03: Arquitectura, Despliegue y Portabilidad
- **RNF-03.1:** Despliegue en contenedores aislados mediante Docker y Docker Compose.
- **RNF-03.2:** Portabilidad probada tanto en entorno local (Windows 10/Linux) como en Servidor Privado Virtual (VPS).

### RNF-04: Calidad y Suite de Pruebas
- **RNF-04.1 (Caja Blanca):** Pruebas unitarias para cobertura de algoritmos críticos (ETL y utilidades de base de datos).
- **RNF-04.2 (Caja Negra):** Validación funcional punto a punto de flujos de usuario.
- **RNF-04.3 (Valores Límite):** Resistencia comprobada ante datos bordes (precios $0.00, stock 0, valores negativos, desbordamiento de caracteres).
- **RNF-04.4 (Estrés / Huracán):** Capacidad de soportar cargas simultáneas masivas (procesamiento de 100+ catálogos pesados de 3MB a 10MB sin caídas del contenedor).