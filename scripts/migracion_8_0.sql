-- Migracion 8.0 - Asociar productos existentes con el proveedor de su archivo.
--
-- Se aplica sobre ferreteria_rag sin borrar datos y puede repetirse. Solo
-- completa relaciones ausentes cuando el archivo de origen ya conserva
-- id_proveedor; no intenta adivinar proveedores para archivos historicos
-- cuyo origen nunca fue registrado.
--
-- Aplicar con:
--     venv\Scripts\python.exe scripts\aplicar_migracion.py 8_0

UPDATE productos AS producto
   SET id_proveedor = archivo.id_proveedor,
       descripcion_vectorial = NULL,
       modelo_embedding = NULL,
       vectorizado_en = NULL
  FROM archivos_subidos AS archivo
 WHERE producto.id_archivo = archivo.id_archivo
   AND producto.id_proveedor IS NULL
   AND archivo.id_proveedor IS NOT NULL;
