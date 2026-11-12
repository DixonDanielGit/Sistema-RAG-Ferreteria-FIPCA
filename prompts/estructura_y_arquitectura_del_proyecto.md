# Especificación de Estructura de Carpetas y Arquitectura

**Proyecto:** Sistema Web de Gestión de Inventario y Buscador Comercial
**Empresa:** FERRE-INVERSIONES PEREZ C.A.
**Desarrollador:** Dixon Daniel Bastias Hernandez
**Arquitectura:** Web desacoplada (FastAPI + Jinja2/HTML5/Bootstrap 5/AJAX +
PostgreSQL Full-Text Search + Docker)

---

## 1. Stack Tecnológico Principal

- **Backend:** Python 3.11+ / FastAPI / Uvicorn / Pydantic
- **Base de datos:** PostgreSQL 16 con Full-Text Search nativo
  (`tsvector`/`tsquery`, índices GIN) e `ILIKE` como respaldo para búsquedas
  parciales de código o proveedor
- **Frontend:** HTML5 / Bootstrap 5 / JavaScript vanilla (Fetch API / AJAX) /
  plantillas Jinja2
- **Ingesta (ETL):** 100 % local y determinista con pandas/openpyxl para
  `.xlsx`, pdfplumber para `.pdf`, python-docx para `.docx` y lectura nativa
  para `.txt`; normalización con reglas y expresiones regulares
- **Sin IA en el producto:** no hay modelos generativos, embeddings, búsqueda
  vectorial ni servicios externos de IA en la ingesta ni en las consultas
- **Control de versiones y contenedores:** Git / Docker / Docker Compose

---

## 2. Árbol de Directorios del Proyecto

```text
Sistema-RAG-Ferreteria-FIPCA/
├── .env.example                    # Plantilla de configuración (sin secretos)
├── AGENTS.md                       # Reglas de trabajo para agentes de IA
├── docker-compose.yml              # PostgreSQL + pgAdmin + API
├── Dockerfile                      # Imagen de la API con usuario sin privilegios
├── init.sql                        # Esquema inicial de ferreteria_rag y ferreteria_usuarios
├── requirements.txt                # Dependencias de Python
├── README.md                       # Guía de ejecución, endpoints y pruebas
├── DESIGN.md                       # Sistema de diseño de la interfaz
├── PRODUCT.md                      # Verdad de producto para el diseño
│
├── app/                            # Código fuente del backend (FastAPI)
│   ├── main.py                     # Punto de entrada, middlewares y montaje de rutas
│   ├── config.py                   # Configuración leída de variables de entorno
│   │
│   ├── core/                       # Seguridad, sesión, permisos y auditoría
│   │   ├── security.py             # Hashing scrypt/bcrypt y utilidades criptográficas
│   │   ├── jwt.py                  # Emisión y validación de tokens JWT
│   │   ├── sesion.py               # Cookie HttpOnly y CSRF de doble envío
│   │   ├── permisos.py             # Catálogo cerrado de capacidades
│   │   └── logging.py              # Registro de eventos de auditoría
│   │
│   ├── db/                         # Conexión a PostgreSQL
│   │   ├── session.py              # Pools de conexión (rag y usuarios)
│   │   └── base.py                 # Utilidades de consulta parametrizada
│   │
│   ├── models/                     # Acceso a datos con SQL parametrizado
│   │   ├── usuario.py              # Cuentas, roles y permisos
│   │   ├── inventario.py           # Productos, ofertas, proveedores y búsqueda FTS
│   │   ├── recuperacion.py         # Tokens de restablecimiento de contraseña
│   │   └── bitacora.py             # Bitácora inmutable de auditoría
│   │
│   ├── schemas/                    # DTOs de Pydantic (entrada/salida de la API)
│   │   ├── usuario_schema.py
│   │   ├── inventario_schema.py
│   │   └── bitacora_schema.py
│   │
│   ├── api/                        # Endpoints y páginas
│   │   ├── deps.py                 # Dependencias de autenticación y capacidades
│   │   ├── api_router.py           # Agrupador de rutas /api/v1
│   │   └── v1/
│   │       ├── auth.py             # Autenticación, usuarios, roles y recuperación
│   │       ├── inventario.py       # Ingesta, previsualización, búsqueda y borrado
│   │       ├── bitacora.py         # Consulta del historial de auditoría
│   │       └── web.py              # Páginas HTML (/login, /dashboard, /search…)
│   │
│   ├── services/                   # Lógica de negocio
│   │   ├── etl_service.py          # Parsers locales y orquestación de la ingesta
│   │   ├── email_service.py        # Envío de correo o enlace en consola
│   │   ├── recuperacion_service.py # Tokens y límites de recuperación
│   │   └── perfil_service.py       # Normalización de la imagen de perfil
│   │
│   └── static/                     # Recursos del frontend servidos localmente
│       ├── css/estilos.css         # Estilos y temas claro/oscuro
│       ├── js/                     # Un script por vista (buscador, fuentes, roles…)
│       ├── img/                    # Logotipos y avatares
│       └── vendor/                 # Bootstrap, DataTables, SweetAlert2, jQuery
│
├── templates/                      # Vistas Jinja2
│   ├── base.html                   # Plantilla base con navegación y tema
│   ├── login.html / recuperar.html / restablecer.html
│   ├── dashboard.html              # Panel principal con acceso al buscador
│   ├── buscador.html               # Buscador comercial y panel de fuentes
│   ├── usuarios.html / roles.html / perfil.html / configuracion.html
│   ├── bitacora.html               # Visor de auditoría
│   └── _navbar.html, _marca.html, _panel_fuentes.html
│
├── tests/                          # Suite de pruebas
│   ├── unit/                       # Caja blanca: ETL, esquema, seguridad, utilidades
│   ├── integration/                # Caja negra contra copias desechables de la BD
│   ├── boundary/                   # Valores límite
│   ├── security/                   # CSRF, inyección SQL y endurecimiento
│   └── stress/                     # Carga opcional de catálogos
│
├── scripts/
│   ├── aplicar_migracion.py        # Aplicador idempotente de migraciones
│   └── migracion_*.sql             # Migraciones incrementales sin borrar datos
│
├── docs/actas/                     # Actas de cierre semanal
└── uploads/                        # Originales de catálogos (volumen persistente)
```

---

## 3. Flujo de Ingesta y Búsqueda

1. **Carga:** el administrador sube hasta 20 archivos (`.pdf`, `.xlsx`,
   `.docx` o `.txt`, máximo 100 MB cada uno) desde el panel de fuentes.
2. **Previsualización:** el ETL local extrae filas, valida códigos, nombres,
   precios, moneda, proveedor y contacto; muestra cuántas filas se guardarían
   y cuántas se rechazarían.
3. **Confirmación:** los metadatos comerciales del catálogo (proveedor,
   vendedor, teléfono, correo, moneda y observaciones) se registran junto al
   archivo.
4. **Persistencia:** productos y ofertas se guardan en una transacción en
   `ferreteria_rag`. El upsert conserva el stock existente y no inventa
   proveedores ni precios.
5. **Búsqueda:** `/api/v1/inventario/busqueda` resuelve la consulta con
   `plainto_tsquery` sobre el `tsvector` en español, con `ILIKE` para
   coincidencias parciales. Devuelve producto, precio, proveedor y teléfono de
   contacto; si no hay coincidencias, lo informa sin inventar resultados.

---

## 4. Normas de Desarrollo para el Agente (OpenCode)

1. **Respeto estricto de rutas:** ningún archivo Python nuevo debe crearse
   fuera de `app/` o `tests/`.
2. **Cambios acotados:** modificar solo lo solicitado; no reescribir módulos
   ajenos a la tarea.
3. **Sin IA en la ingesta ni en la búsqueda:** no se agregan modelos
   generativos, embeddings, servicios externos ni claves de API de IA.
4. **Consumo de base de datos:** toda consulta usa SQL parametrizado y el
   esquema de `init.sql` con sus migraciones incrementales.
5. **Frontend:** las vistas de `templates/` consumen la API mediante AJAX desde
   los scripts de `app/static/js/`.
6. **Pruebas:** todo cambio de código se acompaña de pruebas en `tests/`.
