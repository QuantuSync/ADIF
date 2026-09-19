# Las tres entradas que esperamos de ADIF: qué forma esperan y qué hace el sistema

Bloque 2 del encargo de la sesión 2026-09-19 (sexta parte). **Ninguno de los
tres ficheros ha llegado.** Lo que está hecho es la ingesta, el cruce y la
salida de cada uno, probados sobre datos sintéticos
(`engine/tests/test_entradas_pendientes_del_cliente.py`, 17 pruebas), para que
meterlos sea **dejarlos en `Ejemplo/Input` y ejecutar un comando**.

Este documento dice, para cada uno: dónde se deja, qué comando se ejecuta, qué
forma espera el sistema, **qué hace si llega con otra forma**, y qué sale.

Los tres siguen el mismo mecanismo que las cinco fuentes de entrada que ya
existen (CONTEXTO.md sección 7): una variable de entorno con la ruta dentro del
contenedor, montada por bind-mount en `docker-compose.override.yml`, y un
endpoint que se puede repetir tantas veces como haga falta. **Sin la variable,
el endpoint no tiene nada que leer y no rompe nada**: devuelve
`configurado: false` y no toca la base de datos.

---

## Resumen: los tres comandos

```bash
# 1 — la lista de vigentes con remanente
curl -s -X POST "http://localhost:8000/mantenimiento/vigentes-remanente/cruzar"

# 2 — el listado de estados de ADIF, ahora con presupuesto de licitación
curl -s -X POST "http://localhost:8000/mantenimiento/estados-adif/cargar"

# 3 — el catálogo antiguo de ADIF (el informe va aparte del entregable)
curl -s "http://localhost:8000/mantenimiento/catalogo-antiguo/informe.xlsx" -o informe_catalogo_antiguo_adif.xlsx
```

Antes del primer uso de 1 y 3 hay que añadir el bind-mount y la variable al
`docker-compose.override.yml` (se detalla en cada apartado) y recrear los
contenedores: `docker compose up -d api worker`. El 2 no necesita nada nuevo:
reutiliza el montaje que ya existe, solo se sustituye el fichero.

---

## 1 — `EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx`

**Qué es.** La lista de los **83 contratos vigentes con remanente**. El grupo
de trabajo la tiene registrada desde la sesión 2026-09-16 (noche); se comprobó
hoja a hoja que no está escondida en ninguno de los cinco ficheros de entrada
que sí tenemos (sesión 2026-09-19, tercera parte, bloque 2).

**Dónde se deja y cómo se monta.**

```yaml
# docker-compose.override.yml, servicio "api"
    volumes:
      - "./Ejemplo/Input/EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx:/data/vigentes_remanente.xlsx:ro"
    environment:
      VIGENTES_REMANENTE_PATH: /data/vigentes_remanente.xlsx
```

**Qué forma espera.** Un `.xlsx` con una columna de códigos de expediente. Nada
más: el resto de columnas se ignoran, incluida la del propio remanente (el
cruce que pidió el cliente no lo usa).

**Cómo localiza esa columna, en este orden.**

1. **Por encabezado.** La primera columna cuyo encabezado, en minúsculas y sin
   acentos, contenga `expediente` o `contrato`. Cubre "Expediente",
   "Expediente ADIF", "Nº de expediente", "Contrato"...
2. **Por contenido**, si ninguna hoja tiene ese encabezado: la **única**
   columna cuyos valores tengan forma de código de ADIF en al menos el 60 % de
   sus filas, en las dos escrituras del corpus (`6.24/28510.0088` y
   `28510/2023`). Por esta vía **solo entran los valores con esa forma**: el
   título de la hoja no es un expediente.
3. Las hojas se recorren todas, pero **nunca se mezclan dos**: un fichero con
   una hoja de datos y otra de notas no junta las dos listas.

**Qué hace si llega con otra forma.** Si ninguna hoja resuelve una columna de
códigos —o si la resuelve pero está vacía—, el resultado sale con
`formato_reconocido: false`, `columna_localizada_por: "no encontrada"` y
**cero filas**, y no se toca nada: ni se dan de alta expedientes, ni se encolan
búsquedas, ni se escribe en la base de datos. Con **dos o más** columnas de
aspecto de código y sin encabezado que desempate, tampoco se adivina.

**Qué hace el cruce.** Para cada código:

- Si está en la **Conciliación**, devuelve su **Situación** y su motivo, con el
  recuento de líneas que ese expediente aporta al Excel. Es la misma lista que
  escribe la hoja "Conciliación" del entregable, construida con el mismo
  recuento de filas de "Materiales" — nunca una consulta propia.
- Si **no** está, lo **busca en la Plataforma**: encola un
  `descargar_expediente`, que es la vía normal del sistema y encadena la
  extracción si encuentra algo. Para poder encolarlo hace falta que el
  expediente exista, así que se **da de alta** el que no esté.

**Por qué este sí da de alta y el listado de estados no.** El listado de
estados (`app.extraccion.estados_adif`) tiene prohibido crear expedientes
porque hacerlo respondería sola, y en falso, la pregunta "¿cuáles de los suyos
no tenemos?". Aquí la pregunta del cliente es la contraria —"¿qué sabemos de
estos 83?"— y no se puede contestar sin buscarlos.

**Cómo pedirlo sin tocar la red**, para ver qué saldría antes de lanzar 83
búsquedas contra la Plataforma:

```bash
curl -s -X POST "http://localhost:8000/mantenimiento/vigentes-remanente/cruzar?buscar=false"
```

**Qué devuelve.** JSON con el recuento por Situación, cuántos quedan fuera de
la Conciliación, cuántos se han dado de alta, cuántas búsquedas se han
encolado, y la lista fila a fila con la acción tomada en cada una.

---

## 2 — El listado de estados de ADIF con el presupuesto de licitación

**Qué es.** El mismo fichero que ADIF nos envió el 18/09/2026
(`estados_expedientes_28510_20260918.xlsx`, 358 expedientes del 28510) con una
columna más: el **presupuesto de licitación** de cada expediente. Hoy ese
fichero trae solo cuatro columnas —"Título del expediente", "Expediente ADIF",
"Fecha de creación" y "Descripción del estado"— y por eso la validación de
importes que se ofreció en su día no se pudo hacer (CONTEXTO.md sección 7).

**Dónde se deja.** Sustituyendo el fichero actual en `Ejemplo/Input`. **No hace
falta tocar nada más**: el montaje y la variable `ESTADOS_ADIF_PATH` ya
existen. Si el nombre del fichero cambia, hay que actualizar el bind-mount de
`docker-compose.override.yml`.

**Qué forma espera.** Las mismas cuatro columnas de siempre, con sus nombres
exactos (`Expediente ADIF` y `Descripción del estado` son obligatorias; sin
ellas la hoja se salta entera, como hasta hoy), **más una** de presupuesto.

**Cómo localiza la columna de presupuesto.** Por contenido del encabezado, no
por igualdad: vale cualquiera que contenga `presupuesto`, `importe de
licitacion` o `pbl`. Quedan deliberadamente **fuera** las que contengan
`adjudicacion`, `adjudicado` o `iva`: un importe adjudicado no es el
presupuesto de licitación, y contrastarlos daría diferencias en casi todas las
filas. Con **dos o más** candidatas no se adivina y el campo se queda vacío.

**Qué hace si llega con otra forma.** Si no hay columna de presupuesto —que es
lo que pasa hoy—, la carga funciona exactamente igual que siempre y el campo
`presupuesto_licitacion_adif` se queda `NULL`. El resultado de la carga lo dice
(`trae_presupuesto: false`, `presupuestos_leidos: 0`). Un valor que no se pueda
interpretar como número (ni como número de Excel ni como texto en formato
español, "1.234.567,89 €") se deja vacío: nunca se guarda una cifra a medias.

**Qué sale.** Una hoja nueva en el Excel del catálogo, **"Presupuestos ADIF"**,
con una fila por expediente que traiga presupuesto:

| Columna | Qué es |
|---|---|
| Código de expediente | |
| Título expediente | |
| Presupuesto de licitación según ADIF | Lo que dice su listado |
| Importe de licitación leído de los documentos | `expedientes.importe_licitacion`, leído de un documento publicado, con su traza |
| Diferencia (ADIF − documentos) | |
| Diferencia relativa | Sobre el presupuesto de ADIF |
| Resultado | `Coincide` / `Difiere` / `Sin importe leído de los documentos` |

**El orden es el que pidió el cliente**: primero las coincidencias, después las
diferencias **de mayor a menor** (por valor absoluto: −900.000 € importa tanto
como +900.000 €), y al final los expedientes de los que no se pudo leer ningún
importe. Dentro de cada bloque, por código, para que dos exportaciones seguidas
den el mismo fichero.

**Las dos cifras no se mezclan nunca**: `presupuesto_licitacion_adif` es un
campo propio y jamás escribe en `importe_licitacion`, exactamente por lo mismo
que "Estado según ADIF" y "Estado que consta publicado en la Plataforma" son
dos columnas distintas. Una diferencia no dice cuál de las dos está mal: dice
que hay que mirar ese expediente.

**La hoja solo aparece si hay algo que comparar.** Sin ningún presupuesto
cargado —el estado de hoy— no se añade al Excel: una hoja vacía en el
entregable haría pensar que falta un dato que nadie ha mandado.

---

## 3 — El catálogo antiguo de materiales de ADIF

**Qué es.** El catálogo de materiales que ADIF usaba antes, **de formato
desconocido** (así lo dijo el cliente).

**Dónde se deja y cómo se monta.**

```yaml
# docker-compose.override.yml, servicio "api"
    volumes:
      - "./Ejemplo/Input/CATALOGO_ANTIGUO_ADIF.xlsx:/data/catalogo_antiguo.xlsx:ro"
    environment:
      CATALOGO_ANTIGUO_PATH: /data/catalogo_antiguo.xlsx
```

**Qué forma espera.** Un `.xlsx` con, al menos, una columna de **matrícula** o
una de **descripción**. La de **precio** es opcional: sin ella se puede decir
qué materiales están en un catálogo y no en el otro, pero no comparar precios.

**Cómo localiza las columnas.** Formato desconocido significa lectura por
contenido, no adivinación:

- Se miran las **diez primeras filas** de cada hoja (el encabezado puede no ser
  la primera: un catálogo suele traer un título de portada encima) y se elige
  la que resuelva **más** de las tres columnas. A igualdad, la primera. Esto es
  lo que impide que un título como "CATÁLOGO DE MATERIALES ADIF" se lleve el
  puesto por contener la palabra "material".
- Matrícula: encabezado que contenga `matricula`, `material`, `referencia`,
  `codigo adif` o `cod. adif`.
- Descripción: `descripcion`, `denominacion`, `designacion`, `concepto` o
  `texto breve`.
- Precio: `precio`, `importe` o `valor`, **excluyendo** los que contengan
  `total`, `pedido` o `acumulad` — un importe total de pedido no es un precio
  unitario.
- Se leen **todas** las hojas que resuelvan encabezado; las que no, se saltan
  sin ruido.

**Qué hace si llega con otra forma.** Si ninguna hoja resuelve matrícula ni
descripción, el informe sale con `formato_reconocido: false` y **cero filas**.
No se empareja nada a partir de columnas que no se sabe qué son.

**Cómo empareja, que es lo que pidió el cliente.**

1. **Por matrícula exacta**, si el material de su catálogo la trae.
2. **Solo cuando no la trae**, por **descripción normalizada**: minúsculas, sin
   acentos, sin puntuación y espacios colapsados.

**Nunca al revés.** Una matrícula que no casa **no** se reintenta por
descripción: eso sería un cruce por parecido de nombre, justo lo que
CONTEXTO.md sección 7 prohíbe ("el cruce es por clave exacta, no por similitud
de nombre"). La descripción entra solo donde no hay clave que comparar.

**Contra qué se compara.** Contra los materiales del **entregable**: los mismos
filtros y el mismo criterio de inclusión que la hoja "Materiales"
(`app.exportacion.linea_sale_en_materiales`), nunca una consulta propia. Si
contara otra cosa, el informe diría que falta un material que el cliente sí
tiene en su Excel.

**Qué sale, y dónde.** Un `.xlsx` **aparte, nunca dentro del entregable**
(condición explícita del cliente), con cuatro hojas:

| Hoja | Qué lista |
|---|---|
| Solo en el catálogo de ADIF | Materiales suyos que no casan con ninguno nuestro, con la hoja y la fila de origen |
| Solo en el nuestro | Materiales del entregable que no casan con ninguno suyo, con su expediente y su lote |
| Diferencias de precio | Los emparejados cuyo precio no coincide, **de mayor a menor diferencia**, diciendo si se emparejaron por matrícula o por descripción |
| Resumen | Las cifras del cruce y la nota que explica el criterio de emparejamiento |

Las cifras sueltas, sin generar el fichero:

```bash
curl -s "http://localhost:8000/mantenimiento/catalogo-antiguo/resumen"
```

---

## Qué NO hace ninguno de los tres

- **No dan por buena una columna que no se ha sabido identificar.** Los tres
  prefieren decir "no he reconocido el formato" a emparejar por posición.
- **No escriben en el catálogo.** Ninguno cambia un precio, una cantidad ni una
  descripción de `lineas_catalogo`. El 1 encola búsquedas y da de alta
  expedientes; el 2 escribe en un campo propio de `expedientes` que solo lee su
  hoja; el 3 no escribe nada en absoluto.
- **No fallan por no estar.** Sin su variable de entorno, los tres devuelven
  `configurado: false` y el resto del sistema sigue igual. Es el mismo
  comportamiento que el maestro de materiales tuvo durante semanas.
