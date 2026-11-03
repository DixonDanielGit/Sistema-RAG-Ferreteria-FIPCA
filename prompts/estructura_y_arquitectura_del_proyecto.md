# Especificación de Estructura de Carpetas y Arquitectura

**Proyecto:** Sistema Web de Gestión de Inventario e Inteligencia Artificial RAG  
**Empresa:** FERRE-INVERSIONES PEREZ C.A.  
**Desarrollador:** Dixon Daniel Bastias Hernandez  
**Arquitectura:** Web Desacoplada (FastAPI + Jinja2/HTML5/Bootstrap 5/AJAX + PostgreSQL pgvector + Docker)

---

## 1. Stack Tecnológico Principal

- **Backend:** Python 3.11+ / FastAPI / Uvicorn / Pydantic
- **Base de Datos:** PostgreSQL 16 + Extensión `pgvector` (Corriendo en Docker)
- **Frontend:** HTML5 / Bootstrap 5 / JavaScript Vanilla (Fetch API / AJAX) / Jinja2 Templates
- **Modelos de IA (Pipeline RAG):**
  - *Modelo 1 (Embedding):* Generación de vectores semánticos (Gemini Embeddings / OpenAI)
  - *Modelo 2 (LLM Generativo):* Síntesis de respuestas en lenguaje natural (Gemini / GPT)
- **Control de Versiones & Contenedores:** Git / Docker / Docker Compose

---

## 2. Árbol de Directorios del Proyecto

```text
FERRE_INVERSIONES_PEREZ/
├── .gitignore                      # Archivos ignorados por Git (.env, venv/, etc.)
├── docker-compose.yml              # Contenedor PostgreSQL 16 + pgvector
├── init.sql                        # Script de inicialización de BD y esquema de tablas
├── requisitos_sistema.md           # Requisitos funcionales, no funcionales y pruebas
├── checklist_proyecto.md          # Cronograma y checklist de tareas semanales
├── ESTRUCTURA_PROYECTO.md          # Estructura del proyecto y arquitectura (este archivo)
├── PROMPTS_OPENCODE.md             # Guía de prompts para interactuar con OpenCode
├── README.md                       # Guía general de ejecución y comandos
├── requirements.txt                # Librerías y dependencias de Python
│
├── app/                            # CÓDIGO FUENTE DEL BACKEND (FastAPI)
│   ├── __init__.py
│   ├── main.py                     # Punto de entrada FastAPI (rutas, CORS, middlewares)
│   ├── config.py                   # Carga de variables de entorno (.env)
│   │
│   ├── core/                       # Seguridad, tokens y utilidades del sistema
│   │   ├── security.py             # Encriptación/Hashing de contraseñas (scrypt/bcrypt)
│   │   ├── jwt.py                  # Generación y validación de tokens JWT
│   │   ├── permisos.py             # Catálogo cerrado de capacidades configurables
│   │   └── logging.py              # Middleware e inyección para Bitácora de Auditoría
│   │
│   ├── db/                         # Configuración y conexión a Base de Datos
│   │   ├── session.py              # Pool de conexiones a PostgreSQL (psycopg2/SQLAlchemy)
│   │   └── base.py                 # Conexión base y utilidades
│   │
│   ├── models/                     # Modelos de BD / Entidades (SQL)
│   │   ├── usuario.py              # Entidad de usuarios, roles y asignaciones de permisos
│   │   ├── inventario.py           # Entidad de Productos e Inventario
│   │   └── bitacora.py             # Entidad de Registros de Auditoría
│   │
│   ├── schemas/                    # Modelos de validación Pydantic (Entradas/Salidas API)
│   │   ├── usuario_schema.py       # DTOs de Login, Registro y Roles
│   │   ├── inventario_schema.py    # DTOs de Productos, Precios y Stock
│   │   └── rag_schema.py           # DTOs de Peticiones del Chat e Historial
│   │
│   ├── api/                        # Endpoints y Rutas API REST
│   │   ├── v1/
│   │   │   ├── auth.py             # Rutas /api/v1/auth (Login, Token Refresh)
│   │   │   ├── inventario.py       # Rutas /api/v1/inventario (CRUD y Búsqueda)
│   │   │   ├── bitacora.py         # Rutas /api/v1/bitacora (Consulta de Logs)
│   │   │   └── rag_chat.py         # Rutas /api/v1/chat (Endpoint AJAX para IA)
│   │   └── api_router.py           # Agrupador de rutas v1
│   │
│   ├── services/                   # LÓGICA DE NEGOCIO Y PIPELINE RAG
│   │   ├── etl_service.py          # Extracción y limpieza de archivos (PDF/Excel/Word)
│   │   ├── embedding_service.py    # Modelo 1: Vectorización de texto (Embeddings)
│   │   ├── vector_search.py        # Búsqueda por similitud con pgvector (Coseno `<=>`)
│   │   └── llm_service.py          # Modelo 2: Generación de respuestas delimitadas
│   │
│   └── static/                     # ARCHIVOS ESTÁTICOS FRONTEND
│       ├── css/
│       │   └── custom.css          # Estilos personalizados Bootstrap 5
│       ├── js/
│       │   ├── main.js             # Lógica global
│       │   ├── auth.js             # Gestión de JWT en localStorage/cookies
│       │   └── rag_chat.js         # Peticiones AJAX asíncronas para el Chat RAG
│       └── img/                    # Asset de imágenes y logotipos
│
├── templates/                      # VISTAS HTML (Jinja2 Templates)
│   ├── base.html                   # Plantilla base (Navbar, Sidebar y Footer)
│   ├── login.html                  # Pantalla de Autenticación
│   ├── dashboard.html              # Panel Principal de Métricas
│   ├── chat_rag.html               # Interfaz del Chat Inteligente
│   └── inventario.html             # Gestión e inspección de productos
│
├── tests/                          # SUITE COMPLETA DE PRUEBAS
│   ├── unit/                       # Pruebas de Caja Blanca (Funciones aisladas)
│   ├── integration/                # Pruebas de integración de la API
│   ├── boundary/                   # Pruebas de Valores Límite (Datos $0, stock negativo)
│   ├── security/                   # Pruebas de Seguridad y Anti-Prompt Injection
│   └── stress/                     # Pruebas de Carga/Huracán (Catálogos pesados)
│
├── scripts/
│   └── migracion_6_0.sql           # Roles configurables y permisos por capacidades
└── uploads/                        # Archivos temporales de catálogos recibidos
```

### Autorización configurable

`ferreteria_usuarios` conserva las cuentas y las relaciona con `rol`; el
catálogo `permiso` define capacidades fijas y `rol_permiso` las asigna a roles.
El rol `admin` está protegido y obtiene todas las capacidades vigentes. Solo
ese rol administra el catálogo de roles desde Configuración. Las dependencias
de `app/api/deps.py` consultan la cuenta y sus permisos actuales en la base para
cada solicitud; el JWT no es la fuente de autorización.

---

## 3. Normas de Desarrollo para el Agente (OpenCode)

1. **Respeto Estricto de Rutas:** Ningún archivo Python nuevo debe crearse fuera de la carpeta `app/` o `tests/`.
2. **Modularidad:** Todo servicio de IA debe colocarse en `app/services/`. Ninguna lógica de vectorización debe ser incrustada directamente en las rutas de la API (`app/api/`).
3. **Consumo de BD:** Todas las operaciones con la base de datos PostgreSQL deben utilizar el esquema definido en `init.sql` y sus migraciones incrementales.
4. **Respuesta Frontend:** Las vistas HTML en `templates/` consumirás la API de FastAPI mediante AJAX desde los scripts en `app/static/js/`.