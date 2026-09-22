# Informe de cierre del proyecto ADIF: cifras clave

Datos a 22/09/2026, código en el commit `a144bbb`, rama `main`. Todas las cifras están medidas en el repositorio, en la base de producción (consultada en solo lectura) o en el Excel entregado, salvo las marcadas como "estimado".

| Concepto | Cifra | De dónde sale |
|---|---|---|
| Horas totales del proyecto (estimado) | **159 h** (entre 146 y 172 h) | 82,7 h medidas en git, más 38 h de arranque de sesión (51 sesiones × 0,75 h) y 38 h de trabajo que no queda en git. Por categoría: diseño 11,4 · investigación 10,7 · desarrollo 76,9 · verificación 26,3 · entorno 10,8 · coordinación 12,7 · documentación 10,3 |
| Horas medidas en git, mínimo del desarrollo | **82,7 h** | Suma de los intervalos entre commits consecutivos de hasta 2 h; los huecos mayores no cuentan |
| Contraste de arriba abajo | **108,9 h** | 15 laborables × 6 h = 90 h, más 18,9 h medidas en git en los 5 días de fin de semana con actividad. Contando esos fines de semana de su primer a su último commit, salen 159,0 h |
| Esfuerzo equivalente con COCOMO II (desarrollo tradicional sin asistencia) | **13.099 h** (entre 10.788 y 13.705 h) | Modelo Post-Architecture: A = 2,94, B = 0,91, factores de escala nominales (E = 1,0997), multiplicadores = 1, 21,58 KSLOC, 152 h por unidad de esfuerzo |
| Días con actividad y commits | **20 días, 205 commits** | Del 02/09/2026 al 22/09/2026: 15 laborables y 5 de fin de semana |
| Líneas de código propias, sin pruebas | **21.580** (más 905 de migraciones) | cloc 1.96: motor Python 16.685, web TypeScript 3.651, CSS 995, JS 4, scripts 245. Solo líneas de código, sin comentarios ni líneas en blanco |
| Líneas de pruebas | **14.461** | cloc 1.96 sobre `engine/tests`, sin contar los 51 PDF de muestra |
| Ficheros | **310 en git** | Motor 95, web 26, pruebas 141, migraciones 45, scripts 3 |
| Pruebas | **1.429, y pasan las 1.429 hoy** | pytest en la imagen construida desde `HEAD`, sin red, en 101 s |
| Migraciones / tablas / endpoints / pantallas web | **43 / 17 / 53 / 7** | Alembic de 0001 a 0043 · `models.py` · decoradores de la API · menú de la web |
| Expedientes publicados / con líneas | **534 / 390** | Hoja "Conciliación" del Excel entregado. Aparte, 55 expedientes confirmados como no publicados |
| Documentos descargados / páginas procesadas | **1.638 / 54.871** | Tabla `documentos` de la base |
| Documentos leídos por reconocimiento óptico | **140** | Suman 5.298 páginas, de las que 1.657 se enviaron al modelo (`cache_ocr_documento`) |
| Filas del catálogo entregado | **19.333** | Hoja "Materiales". La base guarda 40.133 líneas contando las pendientes de revisión y las del anejo de criterios |
| Materiales distintos por matrícula | **5.211** | Matrículas distintas en la hoja "Materiales" |
| Lotes contrastados | **486** | Hoja "Contraste de presupuestos": 271 cuadran al céntimo y 13 con diferencia menor del 0,01 % |

**Cómo se han calculado las horas.**

- **Git es un mínimo del desarrollo, no el total.** Las 82,7 h no cuentan el trabajo anterior al primer commit de cada sesión ni lo que no deja commit. El 14/09, por ejemplo, tiene 3 commits grandes y 0 h medidas.
- **Los 159 h estimados** son lo medido en git más dos partidas:
  - 0,75 h de arranque por cada una de las 51 sesiones. Con 0,5 h o con 1 h salen los extremos de la horquilla, 146 y 172 h.
  - 38 h de trabajo que no queda en git: diseño previo +4, lectura del corpus y de las fuentes +8, revisión de los 20 Excel entregados +10, entorno WSL y Docker +4, incorporar decisiones del cliente +6, documentos de preguntas y diccionario +6.
- **Quedan fuera** reuniones, llamadas y trabajo fuera del repositorio: esas horas tienes que aportarlas tú.
- **COCOMO II** es solo una referencia de lo que costaría un desarrollo tradicional sin asistencia.
