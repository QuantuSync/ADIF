# Informe de cierre del proyecto ADIF

Fecha: 22/09/2026. Estado del repositorio: commit `a144bbb` (rama `main`).

Sesión de solo lectura: para este informe no se ha cambiado código ni base de
datos, ni se han lanzado reprocesos ni descargas. Las consultas a la base se
hicieron en modo `default_transaction_read_only=on`, y las pruebas corrieron
en un contenedor desechable sin red y con SQLite en memoria.

**Cómo leer las cifras.** Cada cifra lleva su procedencia:

- **(medido)**: sale del repositorio, de la base de datos de producción, del
  Excel entregado o de una ejecución hecha hoy.
- **(doc.)**: la cifra está escrita en un documento de `docs/` o en
  `CONTEXTO.md`, que se cita. No se ha vuelto a medir.
- **(estimado)**: es un cálculo con un criterio que se explica al lado. No es
  una medida.

## Índice

1. Arquitectura
2. Tamaño del sistema
3. Cifras del catálogo y del corpus
4. Historia del trabajo
5. Horas
6. Dificultades del origen de los datos
7. Estado de cierre
