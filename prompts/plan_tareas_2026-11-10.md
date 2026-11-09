# Plan de tareas — martes 10 de noviembre de 2026

**Horario:** 8:00 a. m.–5:00 p. m.  
**Meta del día:** desbloquear las pruebas de integración del buscador y dejar
claro qué falta para aceptar el MVP. Mantener OpenRouter pausado y no hacer
llamadas reales al proveedor.

| Hora | Tarea | Resultado esperado |
|---|---|---|
| 8:00–8:30 | Preparar el entorno: revisar cambios sin guardar, estado de Docker/PostgreSQL y configuración de las bases de prueba. | Entorno listo; no tocar ni borrar datos de desarrollo. |
| 8:30–10:00 | Investigar por qué la preparación de pruebas falla con `relation "productos" does not exist`; revisar la creación/clonación de las bases y sus migraciones. | Causa identificada y corrección segura, o bloqueo documentado. |
| 10:00–10:15 | **Pausa** | — |
| 10:15–12:00 | Ejecutar primero una prueba de integración del buscador; si pasa, correr el archivo completo. Corregir fallos atribuibles al buscador. | Pruebas ejecutadas, sin omisiones por configuración de la base. |
| 12:00–1:00 | **Almuerzo** | — |
| 1:00–2:15 | Probar búsquedas con productos de prueba en una base desechable: coincidencia por código/nombre, consulta límite y consulta sin resultados. | Casos esperados comprobados; anotar tiempos y resultados. |
| 2:15–2:30 | **Pausa** | — |
| 2:30–3:45 | Recorrer el flujo web: iniciar sesión, abrir `/search`, buscar productos reales y verificar el estado vacío. Probar carga/ETL solo con un archivo seguro y sin activar llamadas reales a OpenRouter. | Flujo demostrado sin afectar datos del catálogo real. |
| 3:45–4:00 | **Pausa** | — |
| 4:00–4:30 | Repetir las pruebas unitarias/API focalizadas y revisar que sigan pasando. | Resultado de pruebas y cualquier advertencia anotados. |
| 4:30–5:00 | Actualizar el checklist con evidencia y preparar una breve secuencia de demostración; dejar como pendientes las pruebas o aceptación no verificadas. | Estado del MVP documentado con próximos pasos concretos. |

## Prioridad si falta tiempo

1. Resolver el problema de la base de pruebas y ejecutar integración.
2. Validar el buscador con datos de prueba.
3. Completar el recorrido web y las pruebas focalizadas.

El catálogo representativo de aproximadamente 8.000 productos y el Acta 4
pueden quedar para otra jornada si no se completan sin apuro.
