# Listado de expedientes en ejecución de ADIF

Fichero de entrada permanente desde la sesión 2026-09-21 (bloque 2). Mismo
tratamiento que el listado de estados de contratación
(`docs/sesion-2026-09-18-estados-adif-y-acuerdos-marco.md`): **dato de ADIF,
nunca de la Plataforma, y nunca decide si un expediente consta publicado**.

## Procedencia

- **Qué es.** El **listado interno de ADIF** de sus expedientes en ejecución,
  con la **fecha de firma del acta de inicio** de cada uno. No sale de la
  Plataforma de Contratación ni de ningún sistema al que tengamos acceso: es
  su dato.
- **Quién y cuándo.** Lo compartió Isa, de ADIF, en el grupo de trabajo el
  **18/09/2026**, y lo reenvió **ordenado el 21/09/2026**.
- **Dónde está.** `Ejemplo/Input/expedientes_en_ejecucion_adif_20260921.csv`,
  guardado tal cual se recibió: separador `;`, UTF-8, dos columnas,
  `Nº Expediente` y `Firma acta de inicio` (DD/MM/AAAA). `Ejemplo/` no se
  versiona (`.gitignore`), como el resto de ficheros de entrada.

## Qué trae la versión del 21/09/2026

| | Expedientes |
|---|---:|
| Filas | **121** |
| Del departamento 28510 | **112** |
| De otros departamentos (fuera del alcance, no se cargan) | **9** |
| Del 28510 sin fecha de acta de inicio | 4 (`6.25/28510.0265`, `0250`, `0194`, `0143`) |
| Códigos repetidos | 0 |

Los 9 de otros departamentos son `4.25/27520.0191`, `4.24/27520.0090`,
`3.26/20810.0043`, `3.25/27520.0055`, `3.24/28520.0129`, `3.24/20810.0090`,
`2.25/28520.0196`, `2.25/28520.0161` y `2.24/28520.0128`.

## El cruce con el sistema (21/09/2026)

**Los 112 del 28510 existen en el sistema** (la carga no da de alta ninguno).
Contra la hoja "Conciliación":

| | Expedientes |
|---|---:|
| En "Conciliación" | **111** |
| — aportan líneas al catálogo | **85** |
| — no aportan líneas | **26** |
| No están en "Conciliación" | **1**: `6.25/28510.5001/01` |

**Coincide exactamente con el cruce que hizo el cliente contra el Excel del
20/09** (111 de 112, 85 y 26, solo falta `6.25/28510.5001/01`).

`6.25/28510.5001/01` no falta porque el sistema no lo conozca. Está como
`sin_publicar`: se buscó en la Plataforma y no apareció. La hoja solo lista lo
que consta publicado, y este listado no puede cambiar eso. Había además una
segunda ficha, `6.25/28510.5001_01`, también `sin_publicar`: el mismo código
escrito con `_`. **Unificada el 21/09/2026 (segunda parte, bloque 3)** con la
forma de la barra, que es la del listado de ADIF, sin perder nada de ninguna
de las dos (`app.extraccion.identidad_expediente.unificar_ficha_duplicada`).

Situación de los 26 que no aportan líneas: 11 *"Los precios están en un
acuerdo marco que no está publicado"*, 10 *"Publicado sin cuadro de precios"*,
2 *"El acuerdo marco está publicado pero no publica precios unitarios"*, 2
*"Licitación por lotes de la que solo se conocen algunos lotes"* y 1
*"Publicado dentro de la ficha de otro expediente"*.

## Dónde se ve

Una columna propia en la hoja "Conciliación", **"En ejecución según ADIF"**,
la última. Está separada a propósito de "Estado que consta publicado en la
Plataforma" y de "Estado según ADIF": son tres fuentes distintas. Valores
posibles:

- la fecha de firma del acta de inicio (`24/08/2026`);
- *"En el listado, sin fecha de firma del acta de inicio"*, cuando el listado
  la trae en blanco;
- vacía, si el expediente no figura en el listado.

El Resumen del Excel explica de dónde sale, con el nombre del fichero cargado,
y lo mismo la pantalla `/conciliacion` de la web. **No interviene ni en qué
expedientes salen en la hoja ni en su Situación** (lo comprueba
`tests/test_en_ejecucion_adif.py`).

## Cómo se incorpora una versión nueva

1. Dejar el fichero en `Ejemplo/Input` con la fecha en el nombre:
   `expedientes_en_ejecucion_adif_AAAAMMDD.csv`.
2. Ejecutar:

   ```
   curl -X POST http://localhost:8000/mantenimiento/en-ejecucion-adif/cargar
   ```

Se carga la versión de **fecha más reciente** de la carpeta (por el nombre, no
por la fecha del sistema de ficheros) y **sustituye entera a la anterior**: un
expediente que ya no figura deja de mostrarse como en ejecución (`retirados` en
la respuesta). La respuesta dice qué fichero leyó, cuántos cargó, cuántos son de
otros departamentos, cuáles no existen en el sistema y qué fechas no pudo leer.
Una fecha que no se lee se devuelve y la celda se queda sin fecha: **nunca se
inventa**.

La lectura tolera lo que puede cambiar al reenviar el fichero: separador `;`,
`,` o tabulador, UTF-8 o Windows-1252, y columnas reconocidas por su nombre
("expediente"; "acta" o "firma"). Si la procedencia de la versión nueva es
otra, añadirla a este documento y a `_PROCEDENCIA_EN_EJECUCION` en
`app/exportacion.py`, que es lo que el Resumen escribe junto al nombre del
fichero. Sin esa entrada, el Resumen da solo el nombre.

**Montaje.** La API ve `Ejemplo/Input` entera en `/data/entrada`
(`EN_EJECUCION_ADIF_DIR`). Como el resto de montajes de entrada, va en
`docker-compose.override.yml`, que es local y no se versiona:

```yaml
services:
  api:
    volumes:
      - "./Ejemplo/Input:/data/entrada:ro"
    environment:
      EN_EJECUCION_ADIF_DIR: /data/entrada
```

## Qué no hace

- **No decide si un expediente consta publicado** (eso es solo la Plataforma:
  `app.conciliacion.consta_publicado`).
- **No da de alta expedientes**: los códigos que no existen se devuelven.
- **No escribe en "Estado según ADIF" ni en "Estado del contrato (SAP)"**:
  son otras fuentes y cada valor conserva la suya.
- **No carga los expedientes de otros departamentos.**
