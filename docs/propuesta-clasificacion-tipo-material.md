# Propuesta de clasificación por tipo de material

Bloque 3 de la sesión 2026-09-21. **Es una propuesta para que el cliente la
valide: no cambia la columna "Código del material" del Excel ni ningún otro
dato del catálogo.** La tabla para validar está en
`C:\dev\ADIF\propuesta_clasificacion_tipo_material_2026-09-21.xlsx`.

## Por qué

El cliente dice que "Código del material" sigue mostrando la palabra general de
la descripción (`PLACA`, `TORNILLO`) y que lo que quiere es **un código que
indique el tipo de material**. Se le ha preguntado si ADIF tiene ya una
clasificación propia. Mientras contesta, esto mide qué da de sí la estructura de
la propia matrícula.

## Qué se ha medido

Las familias que salen de las **primeras 3, 4 y 5 cifras de la matrícula**,
sobre las **13.509 filas con matrícula** del Excel del 20/09 (20.062 filas en
total). De ellas, 13.127 tienen matrícula de 9 cifras y 382 de 8. Las de 8
cifras se clasifican igual: el formato antiguo es el mismo número con una cifra
menos al final (`docs/matriculas-8-digitos-y-el-maestro.md`).

**Cómo de homogénea es una familia.** A cada matrícula se le da un tipo de pieza
sacado de su denominación en el **maestro de materiales de ADIF** (31.665
matrículas de 9 cifras). Se usa el **mismo vocabulario controlado** que ya
rellena "Código del material", que traduce también las siglas verificadas de
aparatos de vía (`SCI` semicambio, `CZI` cruzamiento, `CAC` contraaguja…). La
homogeneidad es la parte de la familia que comparte el tipo más frecuente. Mide
**tipo de pieza exacto**, así que es exigente: una familia con agujas y
contraagujas del mismo aparato cuenta como mezclada. Con la primera palabra de
la denominación a secas, las cifras salían aún más bajas (22 %, 44 % y 55 %)
porque las siglas y las abreviaturas ("TRAV.HORM.") no se reconocen.

| | 3 cifras | **4 cifras** | 5 cifras |
|---|---:|---:|---:|
| Familias con filas en el catálogo | 59 | **175** | 301 |
| Familias en el maestro | 145 | **558** | 1.203 |
| Filas del catálogo que cubren | 13.509 | **13.509** | 13.509 |
| Homogeneidad según el maestro (ponderada por filas) | 34 % | **61 %** | 66 % |
| Homogeneidad de las filas cuya matrícula está en el maestro | 41 % | **67 %** | 71 % |
| Homogeneidad según el "Código del material" de las filas | 38 % | **64 %** | 71 % |
| Familias 100 % homogéneas (por "Código del material") | 10 | **69** | 163 |
| Familias de una sola matrícula | 7 | **21** | 54 |
| Filas sin matrícula asignables con certeza | 334 | **334** | 333 |

## La propuesta: 4 cifras

- **De 3 a 4 cifras la homogeneidad sube 26-27 puntos; de 4 a 5, solo 4-7**,
  a cambio de pasar de 175 familias a 301 (y de 558 a 1.203 en el maestro), con
  54 familias de una sola matrícula. Con 5 cifras la clasificación empieza a ser
  una lista de artículos, no de tipos.
- Con 3 cifras las familias mezclan cosas que no tienen nada que ver (34 %).

**Cada familia lleva un nombre sacado de las denominaciones, nunca
inventado**, y la columna "De dónde sale el nombre" dice cuántas lo respaldan:

1. Si el vocabulario del sistema reconoce **al menos la mitad** de las
   denominaciones de la familia en el maestro, el término que da a esas
   denominaciones (150 familias).
2. Si reconoce menos de la mitad, la primera palabra de todas sus
   denominaciones en el maestro (19). Con la regla anterior, `6431` se habría
   llamado TORNILLO por 2 de sus 64 matrículas; sus denominaciones dicen GRIFA.
3. Si la familia no tiene matrículas en el maestro, el "Código del material" de
   sus filas del catálogo (5); y si tampoco, la primera palabra de sus
   descripciones (1, `6195`, siglas no verificadas: `EMIIH / EMRDH / EMIDH`).

Cuando el término más frecuente no llega al **80 %** de la familia, el nombre
junta los tres más frecuentes (`AGUJA / CONTRAAGUJA / PLACA`). Salen **53
familias de un solo tipo, que cubren 4.015 filas, y 122 mixtas**. En las
mixtas es donde más falta hace que ADIF diga cómo las llama.

Las familias con más filas:

| Código | Nombre propuesto | Parte de la familia que es ese término | Filas | Expedientes |
|---|---|---:|---:|---:|
| `6070` | TRAVIESA | 98 % | 1.124 | 10 |
| `6128` | PLACA / TOPE / JUEGO | 65 % | 756 | 6 |
| `6030` | TRAVIESA | 99 % | 706 | 3 |
| `6108` | AGUJA / CONTRAAGUJA / PLACA | 25 % | 700 | 7 |
| `6118` | AGUJA / ALMOHADILLA / CONTRAAGUJA | 23 % | 687 | 10 |
| `6675` | NODO / SFP / FUENTE | 25 % | 382 | 13 |
| `6429` | CABLE / RANURADO / FEEDER | 49 % | 360 | 20 |
| `6199` | TORNILLO / PLACA / CHAPA | 69 % | 324 | 11 |
| `6010` | CARRIL / CUPÓN | 56 % | 319 | 20 |
| `6678` | STM / UNIDAD / SFP | 9 % | 295 | 2 |
| `6622` | UNIDAD / CABLE / CARTELON | 9 % | 253 | 9 |
| `6114` | CRUZAMIENTO / CONTRACARRIL / APARATO | 68 % | 248 | 7 |
| `6122` | SEMICAMBIO | 83 % | 236 | 6 |
| `6124` | CRUZAMIENTO / CONTRACARRIL / CORAZÓN | 68 % | 230 | 6 |
| `6423` | ANCLAJE / CONJUNTO / GRAPA | 12 % | 230 | 11 |

**Nombres repetidos.** Nueve nombres salen en más de una familia: TRAVIESA
(`6070`, `6030`, `7611`, `7612`), SEMICAMBIO (7), DESVÍO (7), CABLE (4),
CRUZAMIENTO (4), PLACA (3), ESCAPE (2), ESCAPE / DESVÍO (2) y CONJUNTO (2). Son
familias distintas de verdad. Las denominaciones de `6070` son de hormigón
("TRAV.HORM. …", "TRAVIESA PR-VE 54E1") y las de `6030` son "TR-AK-2'60X0'24X0'14
… NEGRA". Ponerles apellido sería inventarlo, así que el Excel lo avisa en su
columna y enseña tres denominaciones de ejemplo de cada una.

## Las 6.553 filas sin matrícula

| | Filas |
|---|---:|
| **Se asignan con certeza**: su descripción es idéntica a la de filas con matrícula, y todas esas filas son de la misma familia | **334** |
| Descripción idéntica a filas de familias distintas | 0 |
| **No se pueden asignar con certeza** | **6.219** |
| — su "Código del material" solo aparece en una familia (probable, no cierto) | 214 |
| — su "Código del material" aparece en varias familias | 4.374 |
| — su "Código del material" no aparece en ninguna fila con matrícula | 1.012 |
| — sin descripción idéntica ni "Código del material" | 619 |

Las 334 van a 31 familias; las que más reciben son `6506` (CABLE, 116), `6660`
(46) y `6423` (33). Las 214 "probables" **no se cuentan como ciertas**: que una
palabra general solo aparezca hoy en una familia no demuestra que la fila sea
de ella.

La razón de fondo: **las filas sin matrícula son de pliegos que no publican
matrícula**, casi siempre con descripciones que no se repiten en los que sí la
publican. La palabra general de la descripción, lo que hoy da "Código del
material", aparece en varias familias a la vez.

## Lo que hay en el maestro y no se ha podido usar

El maestro trae **13 grupos contables de SAP con código de 4 cifras**:
`1000` Material de subestaciones, `1001` Carril, `1002` Balasto, `1003`
Traviesas de hormigón, `1004` Traviesas de madera, `1005` Resto material vía,
`1006` Aparatos vía, `1007` Material vehículos y maquinaria de vía, `1008`
Material de línea aérea de contacto, `1009` Material de señalización, `1010`
Material de telecomunicaciones, `1011` Material de uso general, `1012` Material
de instalaciones no ferroviarias. **No son prefijos de matrícula** (las
matrículas empiezan por 5, 6 o 7), y el maestro no dice a qué grupo pertenece
cada matrícula, así que no se pueden aplicar. **Si ADIF tiene esa
correspondencia matrícula → grupo, es su propia clasificación y valdría más que
esta propuesta.** Es la pregunta que conviene hacerle junto con la de si tiene
una clasificación.

## El Excel para validar

`C:\dev\ADIF\propuesta_clasificacion_tipo_material_2026-09-21.xlsx`, cuatro
hojas:

- **Cómo leer esta propuesta**: lo de este documento, en corto.
- **Familias propuestas**: una fila por familia de 4 cifras con filas en el
  catálogo (175). Lleva su código, el nombre propuesto, de dónde sale, qué
  parte de la familia es ese término, los tipos de pieza que reúne, tres
  matrículas de ejemplo con su denominación del maestro, cuántas filas,
  matrículas y expedientes cubre, cuántas matrículas tiene en el maestro, qué
  otras familias llevan el mismo nombre y **una columna vacía para que el
  cliente escriba si el nombre vale u otro**.
- **Comparación de niveles**: la tabla de 3, 4 y 5 cifras.
- **Filas sin matrícula**: el reparto de arriba y las 334 asignables, por
  familia, con una descripción de ejemplo.

## Cómo se ha hecho

De solo lectura sobre la base de datos (las filas de "Materiales", con el
mismo criterio que la exportación, y `maestro_materiales`). No se ha llamado a
ningún modelo: el vocabulario es el que ya existe, con las respuestas ya
cacheadas en `cache_codigo_material`. Si el cliente la valida, aplicarla sería
una columna nueva del Excel, con la familia y su nombre, sin tocar "Código del
material". Esa decisión es suya.
