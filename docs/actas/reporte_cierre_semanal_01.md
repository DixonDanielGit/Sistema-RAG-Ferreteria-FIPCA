# Reporte semana 1

| Campo | Detalle |
|---|---|
| **Proyecto** | Sistema Web de Gestión de Inventario e IA RAG |
| **Empresa** | FERRE-INVERSIONES PEREZ C.A. |
| **Desarrollador** | Dixon Daniel Bastias Hernandez |
| **Período reportado** | Una semana de trabajo |
| **Fecha de cierre** | 27 de octubre de 2026 |
| **Estado** | Tareas reportadas como completadas; alcance restante en curso |
| **Base del reporte** | [Lista de tareas y checklist de ejecución](../../prompts/lista_de_tareas_y_checklist_de_ejecucion_del_proyecto.md) |

## 1. Resumen ejecutivo

Durante una sola semana de trabajo completé un conjunto amplio de actividades
que el cronograma original distribuía entre varias etapas del proyecto. El
avance incluyó la preparación del entorno de desarrollo y de la infraestructura
de ejecución; la configuración de PostgreSQL con pgvector y la definición de
las bases de datos y su esquema inicial; y la implementación de funciones de
autenticación, control de acceso, protección de credenciales y auditoría.

También se construyeron las pantallas web de acceso, panel y chat, junto con
controles para proteger las solicitudes del navegador y opciones de
visualización. Para permitir la incorporación de información del catálogo, se
implementó el flujo de carga e historial de archivos, incluyendo validaciones,
normalización de productos, límites de procesamiento y almacenamiento seguro
de los originales. Se añadieron además herramientas para administrar roles y
permisos, proteger las cuentas administrativas y revalidar las autorizaciones
en cada petición.

Como parte del trabajo adelantado, se integró la base técnica inicial para
representar productos mediante embeddings y buscarlos por similitud vectorial.
En conjunto, estas actividades dejan preparada una plataforma funcional sobre
la cual continuar la integración completa del asistente RAG y las siguientes
etapas del proyecto. Este resumen refleja las tareas registradas como
completadas en el checklist y no declara terminado todo el cronograma ni el MVP
integrado: las actividades que aún aparecen pendientes siguen fuera del alcance
de este cierre.


## 2. Actividades completadas en la semana

### Infraestructura y base de datos

- Preparé las herramientas y el entorno de desarrollo, incluyendo repositorio,
  entorno virtual y dependencias iniciales (dejé listo el espacio de trabajo,
  sus herramientas y los programas necesarios).
- Configuré Docker Compose, PostgreSQL y pgvector (preparé los servicios que
  ejecutan la aplicación, guardan la información y permiten búsquedas por
  similitud).
- Definí el esquema inicial para usuarios, roles, bitácora e inventario
  (organicé cómo se guardan las cuentas, sus permisos, el historial de acciones
  y los productos).
- Verifiqué el arranque de la base de datos y los contenedores (comprobé que los
  servicios necesarios iniciaran correctamente).
- Elaboré el acta de infraestructura y base de datos (documenté la configuración
  inicial del sistema y dónde se guarda la información).

### Autenticación, seguridad y auditoría

- Implementé usuarios, roles, validación de credenciales y registro inicial
  (preparé las cuentas, sus tipos de permiso y la comprobación de identidad al
  ingresar).
- Incorporé hashing de contraseñas con scrypt y tokens JWT con expiración
  (protegí las contraseñas y configuré credenciales temporales que dejan de
  servir después de un tiempo).
- Añadí controles de acceso y middleware de auditoría (limité qué puede hacer
  cada usuario y registré las acciones importantes).
- Preparé pruebas para el inicio de sesión, expiración de tokens, entradas
  límite e intentos de inyección SQL (comprobé el acceso y que el sistema
  rechazara datos extremos o intentos de manipular consultas a la base de
  datos).
- Elaboré el acta de seguridad JWT y auditoría (documenté cómo se protege el
  acceso y cómo se registran las acciones).

### Interfaz web e ingesta de catálogos

- Implementé las pantallas de acceso, panel y chat web (creé las páginas para
  ingresar, consultar el panel principal y usar el chat).
- Añadí temas claro y oscuro, protección CSRF y empaquetado de la API en Docker
  (incorporé dos apariencias, una defensa contra solicitudes no autorizadas y
  preparé el servicio para ejecutarse en Docker).
- Implementé la carga e historial de catálogos PDF, XLSX, DOCX y TXT (permití
  subir catálogos en esos formatos y consultar las cargas anteriores).
- Incorporé validación independiente de archivos, normalización de productos
  y actualización por código sin sobrescribir el stock (revisé cada archivo,
  unifiqué la información de los productos y actualicé sus datos sin cambiar
  las existencias registradas).
- Añadí límites de carga, persistencia segura de los archivos originales y la
  migración correspondiente (controlé el tamaño y la cantidad de archivos,
  guardé sus originales de forma segura y adapté la estructura de la base de
  datos).
- Verifiqué la prueba reducida de estrés de 20 archivos y 5000 productos
  (comprobé que el sistema pudiera procesar ese volumen de datos).
- Registré los entregables de interfaz e ingesta ETL (documenté las pantallas
  creadas y el proceso automático de lectura de catálogos).

### Roles y permisos

- Migré la base de usuarios para guardar capacidades y asignarlas a roles sin
  perder las cuentas existentes (actualicé cómo se guardan los permisos sin
  eliminar usuarios).
- Incorporé la administración de roles y capacidades desde Configuración,
  restringida a administradores (permití que solo los administradores
  gestionen quién puede hacer cada cosa).
- Protegí el rol de administrador y la disponibilidad del último administrador
  activo (impedí quitar o reducir los permisos del último administrador activo).
- Implementé la revalidación de permisos en cada petición y pruebas de cambios,
  revocaciones y límites (volví a comprobar los permisos en cada operación y
  probé que los cambios se respetaran).
- Alineé la documentación funcional y visual con el modelo de permisos
  (actualicé las guías y las pantallas para que coincidan con los permisos
  disponibles).




## 4. Conclusión

En una sola semana completé las actividades indicadas en este reporte, que
abarcan varios bloques del cronograma original. El resultado deja implementada
una base funcional amplia para continuar con la integración y validación del
RAG, y con las demás tareas que siguen pendientes en el checklist.
