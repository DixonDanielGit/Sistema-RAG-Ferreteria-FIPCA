# Guía de Prompts y Protocolo de Trabajo con OpenCode

Este documento establece la metodología y los prompts estandarizados para interactuar con **OpenCode** (o cualquier agente de código por IA). 

---

## 1. Reglas de Oro para la Interacción

1. **Una Tarea a la Vez:** NUNCA le pidas a OpenCode desarrollar una semana entera o múltiples módulos en un solo mensaje.
2. **Contexto Activo:** Haz referencia explícita a los archivos `.md` del proyecto (`requisitos_sistema.md`, `checklist_proyecto.md`, `ESTRUCTURA_PROYECTO.md`).
3. **Desarrollo Guiado por Pruebas (TDD):** Exige que junto al código desarrollado se incluya la prueba unitaria o de integración correspondiente en la carpeta `tests/`.
4. **Comando de Mantenimiento:** Usa `/compact` cuando completes una semana o un módulo para limpiar la memoria de tokens.

---

## 2. Prompt Inicial de Bienvenida e Inicialización (Copiar y Pegar al iniciar sesión)

> **Prompt de Arranque:**
> ```text
> Hola OpenCode. Estás trabajando en el proyecto "Sistema Web de Gestión de Inventario e IA RAG" para la empresa FERRE-INVERSIONES PEREZ C.A.
> 
> En la raíz del directorio prompts/ dispones de los siguientes archivos de especificación:
> 1. `requisitos_sistema.md`: Especificación de Requisitos Funcionales, No Funcionales y Criterios de Prueba.
> 2. `checklist_proyecto.md`: Lista detallada de tareas semana a semana.
> 3. `ESTRUCTURA_PROYECTO.md`: Arquitectura de carpetas y stack de tecnologías exactas.
> 
> Por favor, lee y analiza estos archivos para comprender las restricciones y el contexto general. No generes código aún. Simplemente confirma que has comprendido las reglas y la arquitectura del proyecto.
> ```

---

## 3. Plantilla Genérica para Solicitar una Tarea del Checklist

Usa este formato adaptando la **Semana** y la **Tarea** según la fase del proyecto en la que te encuentres:

> **Plantilla de Tarea:**
> ```text
> OpenCode, vamos a trabajar exclusivamente en la siguiente tarea:
> 
> - Documento de Referencia: `checklist_proyecto.md`
> - Fase: [Ej: Semana 1]
> - Tarea Específica: [Ej: "Crear archivo docker-compose.yml con la imagen pgvector/pgvector:pg16"]
> 
> Instrucciones estrictas:
> 1. Revisa `ESTRUCTURA_PROYECTO.md` para colocar cada archivo en la ruta exacta.
> 2. Cumple con los requisitos de seguridad y calidad descritos en `requisitos_sistema.md`.
> 3. Genera el código correspondiente.
> 4. Genera el script o suite de prueba correspondiente dentro de la carpeta `tests/`.
> 5. No avance a ninguna otra tarea del checklist hasta que hayamos validado esta.
> ```

---

## 4. Ejemplos Listos para Usar por Semana

### Ejemplo - Semana 1: Inicialización de la Base de Datos
```text
OpenCode, ayuda a ejecutar la siguiente tarea del checklist_proyecto.md:
"Revisa el archivo init.sql con la extensión vector y que todo este adecuado segun el archevo y asegurate que se púeda crear las 2 base de datos".

Luego dime como puedo visualizar las tablas de la base de datos en "http://localhost:8080" 
```

### Ejemplo - Semana 2: Endpoint de Autenticación JWT
```text
OpenCode, procede a implementar la siguiente tarea del checklist_proyecto.md:
"Crear modelos Pydantic y endpoints de FastAPI para /api/v1/auth/login y /api/v1/auth/register".

Requerimientos:
1. Las contraseñas deben encriptarse con scrypt o bcrypt en app/core/security.py.
2. El token JWT debe generarse en app/core/jwt.py.
3. Ubica los esquemas en app/schemas/usuario_schema.py y las rutas en app/api/v1/auth.py.
4. Genera una prueba de integración en tests/integration/test_auth.py.
```

### Ejemplo - Semana 4: Motor de Búsqueda Vectorial (`pgvector`)
```text
OpenCode, vamos a trabajar en la tarea:
"Implementar función de búsqueda vectorial con distancia de coseno (<=>) usando pgvector".

Instrucciones:
1. Crea el servicio en app/services/vector_search.py.
2. La consulta debe conectarse a PostgreSQL mediante app/db/session.py.
3. Asegúrate de incluir el límite de similitud y ordenamiento por menor distancia.
4. Incluye la prueba de Caja Blanca en tests/unit/test_vector_search.py.
```