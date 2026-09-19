# Pregunta para ADIF — las dos grafías de "contraaguja"

**Estado: redactada y lista para enviar. Decisión del cliente el 2026-09-19:
no se unifica nada hasta que contesten; la columna "Descripción del material"
sigue siendo literal del PDF.**

---

## El texto de la pregunta

> En sus pliegos conviven dos grafías de la misma pieza. En el catálogo que
> les entregamos hay **156 filas que dicen "contraaguja"** (8 expedientes) y
> **120 que dicen "contraguja"** (7 expedientes):
>
> - *contraaguja*: `6.21/28510.0108`, `0109`, `0110`, `0111`, `6.20/28510.0041`
>   y otros.
> - *contraguja*: `6.22/28510.0122`, `0155`, `0156`, `6.21/28510.0108`-`0111`.
>
> La columna **"Código del material" ya agrupa las dos como CONTRAAGUJA**, así
> que quien busque o agrupe por ahí no pierde ninguna de las dos hoy.
>
> Lo que queremos saber es qué prefieren para la columna **"Descripción del
> material"**:
>
> 1. **Que siga diciendo lo que dice cada documento** — que es lo que hace
>    hoy, y lo que permite poner la fila del Excel al lado del PDF y
>    comprobar que coinciden palabra por palabra; o
> 2. **que unifiquemos la grafía en el entregable** y guardemos la original
>    aparte, con lo que el Excel dejaría de ser literal en esas 120 filas.
>
> No hay ninguna prisa: no cambia ningún precio, ninguna matrícula ni ninguna
> cantidad, y en cualquiera de los dos casos el material sigue localizable.

---

## Lo que hay detrás, por si preguntan

| | En la base de datos | En la hoja "Materiales" |
|---|---:|---:|
| Descripción que dice **CONTRAAGUJA** | 1.990 líneas, 18 expedientes | **156 filas**, 8 expedientes |
| Descripción que dice **CONTRAGUJA** | 540 líneas, 9 expedientes | **120 filas**, 7 expedientes |
| Columna "Código del material" = CONTRAGUJA | 264 líneas | **0 filas** |

Las 264 líneas cuyo "Código del material" quedó en CONTRAGUJA son todas
huérfanas de `6.21/28510.0112`/`0113`, así que no salen al Excel: en el
entregable, las **515 filas** con código de material de esta pieza dicen
**CONTRAAGUJA**, las dos grafías juntas.

**La errata solo vive en "Descripción del material"**, que es literal del
documento y tiene que seguir siéndolo mientras no digan lo contrario
(CONTEXTO.md sección 7, y la razón de que esa columna exista: cotejar la fila
contra su renglón del PDF).

Cifras re-medidas el 2026-09-19 contra
`catalogo_adif_2026-09-19-precio-desde-importe.xlsx`.
