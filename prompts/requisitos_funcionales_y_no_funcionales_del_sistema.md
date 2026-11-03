# Especificación de Requisitos del Sistema (SRS)

**Proyecto:** Sistema Web de Gestión de Inventario e Inteligencia Artificial RAG  
**Empresa:** FERRE-INVERSIONES PEREZ C.A.  
**Desarrollador:** Dixon Daniel Bastias Hernandez  
**Arquitectura:** Web Desacoplada (FastAPI + PostgreSQL pgvector + HTML5/Bootstrap 5/AJAX)

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
- **RF-02.2:** Normalización automática de datos de productos (precios, marcas, descripciones, equivalencias).
- **RF-02.3:** Tolerancia a fallos durante la ingesta masiva sin detener el servicio.

### RF-03: Vectorización y Asistencia Inteligente (Motor RAG)
- **RF-03.1:** Generación de embeddings vectoriales a partir del contenido de los catálogos de productos.
- **RF-03.2:** Búsqueda por similitud coseno/vectorial utilizando la extensión `pgvector` en PostgreSQL.
- **RF-03.3:** Chat web interactivo con respuesta en lenguaje natural impulsado por LLM, acotado estrictamente a los productos almacenados en la base de datos (sin alucinaciones).

### RF-04: Gestión Administrativa de Inventario
- **RF-04.1:** Módulo CRUD (Crear, Leer, Actualizar, Eliminar) para productos en inventario.
- **RF-04.2:** Gestión de campos técnicos: SKU/Código, Nombre, Marca, Precio Base, Descuentos, Aplicación de IVA (16%) y Stock Actual. No existe una columna `stock_minimo`.
- **RF-04.3:** Filtros de búsqueda rápida y alertas visuales de bajo stock mediante un umbral global.

### RF-05: Bitácora inmutable de Auditoría
- **RF-05.1:** Registro automático e inmutable de toda acción realizada (login, inserción, modificación de precios, consultas RAG, errores).
- **RF-05.2:** Visor de auditoría para el administrador con filtros por fecha, usuario, módulo e IP de origen.

---

## 2. Requisitos No Funcionales (RNF)

### RNF-01: Rendimiento y Latencia
- **RNF-01.1:** Tiempo de respuesta del servidor FastAPI en peticiones AJAX no debe superar los 300 ms.
- **RNF-01.2:** Tiempos de búsqueda vectorial con `pgvector` menores a 1.5 segundos para consultas complejas.
- **RNF-01.3:** Interfaz ligera sin recargas completas de página (construida en Bootstrap 5 + JavaScript vanilla/AJAX).

### RNF-02: Seguridad y Protección de Datos
- **RNF-02.1:** Contraseñas encriptadas mediante algoritmos de hashing seguros (`scrypt` o `bcrypt`).
- **RNF-02.2:** Sanitización de todas las entradas para prevenir Inyecciones SQL y Cross-Site Scripting (XSS).
- **RNF-02.3:** Mecanismos de protección Anti-Prompt Injection en el canal de interacción con el modelo de lenguaje (LLM).

### RNF-03: Arquitectura, Despliegue y Portabilidad
- **RNF-03.1:** Despliegue en contenedores aislados mediante Docker y Docker Compose.
- **RNF-03.2:** Portabilidad probada tanto en entorno local (Windows 10/Linux) como en Servidor Privado Virtual (VPS).

### RNF-04: Calidad y Suite de Pruebas
- **RNF-04.1 (Caja Blanca):** Pruebas unitarias para cobertura de algoritmos críticos (ETL y utilidades de base de datos).
- **RNF-04.2 (Caja Negra):** Validación funcional punto a punto de flujos de usuario.
- **RNF-04.3 (Valores Límite):** Resistencia comprobada ante datos bordes (precios $0.00, stock 0, valores negativos, desbordamiento de caracteres).
- **RNF-04.4 (Estrés / Huracán):** Capacidad de soportar cargas simultáneas masivas (procesamiento de 100+ catálogos pesados de 3MB a 10MB sin caídas del contenedor).