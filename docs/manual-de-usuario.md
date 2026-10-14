# Manual de usuario

<!-- Fuente del manual en PDF (privado/manual/manual-de-usuario.pdf). Las
capturas no están en el repositorio: viven en privado/manual/capturas/,
fuera de git, y el PDF se genera con privado/manual/construir_pdf.py.
Reglas de estilo pedidas: español de España, sin tecnicismos, sin dos
puntos en los títulos y sin guiones largos. -->

Catálogo de materiales de ADIF

Para el personal de ADIF que consulta el catálogo y exporta el Excel

Elaborado por INECO para ADIF

Octubre de 2026

## 1. Qué es la plataforma

La plataforma es una página web que reúne en **un solo catálogo** los materiales que ADIF ha licitado, con lo que se ha comprado o se va a comprar, en qué expediente y en qué lote, en qué cantidad y a qué precio.

Cada fila del catálogo es **un artículo de un lote de un expediente**. Si el mismo material se ha comprado en tres expedientes, aparece tres veces, cada una con su precio. Así se puede ver cómo ha cambiado el precio de un material con el tiempo.

Se usa desde el navegador, sin instalar nada. La dirección es

**https://adif-catalogo-ineco.spaincentral.cloudapp.azure.com**

Con la plataforma se puede

- consultar el catálogo y buscar por matrícula, expediente, lote o descripción;
- ver, para cada línea, de qué documento y de qué página sale, y abrir ese documento original;
- ver qué expedientes están incluidos y por qué algunos no aportan materiales;
- exportar el catálogo completo a Excel.

## 2. De dónde salen los datos

Todo lo que se ve sale de dos sitios.

- **Los documentos publicados en la Plataforma de Contratación del Sector Público.** La plataforma descarga los pliegos, anejos, adjudicaciones y contratos de cada expediente y lee de ellos los cuadros de precios.
- **Los listados que ADIF ha enviado**, como el listado de códigos de proyecto, el listado de expedientes en ejecución, los estados según SAP y el maestro de materiales.

Algunos documentos están escaneados, es decir, son una imagen sin texto. Esos los lee un servicio de reconocimiento de imagen, y las líneas que salen de ellos llevan un aviso para comprobarlas contra el documento.

Hay una regla importante, y es que **la plataforma nunca se inventa un dato.** Si un documento no publica la cantidad, la matrícula o el precio, la celda se queda vacía y se explica por qué. Cada cifra se puede seguir hasta el documento, la página y el fragmento de texto de los que se leyó.

Los datos se ponen al día solos una vez por semana (capítulo 13).

## 3. Entrar en la plataforma

### Datos de acceso

Cada persona tiene su propio usuario. La primera vez recibirá, por un canal aparte, su nombre de usuario y una **contraseña temporal**. No comparta su usuario con nadie.

### Entrar

Abra la dirección de la plataforma. Lo primero que aparece siempre es la pantalla de entrada. Escriba su usuario y su contraseña y pulse **Entrar**.

![La pantalla de entrada es lo primero que se ve](../privado/manual/capturas/01-entrar.png)

![Con el usuario escrito. La contraseña nunca se ve al escribirla](../privado/manual/capturas/02-entrar-usuario.png)

### Primer acceso, cambio de contraseña obligatorio

La primera vez que entre con la contraseña temporal, la plataforma le pedirá que elija una nueva. Hasta que no la cambie no podrá ver nada más.

1. En **Contraseña actual**, escriba la contraseña temporal que le han dado.
2. En **Contraseña nueva**, escriba la que quiera usar. Debe tener **al menos 12 caracteres**. Una frase corta que recuerde con facilidad vale.
3. Repítala en **Repite la contraseña nueva**.
4. Pulse **Cambiar contraseña**.

![Pantalla de cambio de contraseña en el primer acceso](../privado/manual/capturas/03-cambio-obligatorio.png)

### Cambiar la contraseña más adelante

Puede cambiarla cuando quiera desde el enlace **Contraseña**, arriba a la derecha, junto a su nombre de usuario. Funciona igual que en el primer acceso.

![Cambio de contraseña desde el enlace Contraseña](../privado/manual/capturas/16-cambiar-contrasena.png)

Si olvida su contraseña, la plataforma no tiene un botón para recuperarla. Avise a la persona de contacto (capítulo 15) y le darán una contraseña temporal nueva.

### Cuánto dura la sesión

- La sesión se cierra sola tras **30 minutos sin actividad**.
- En todo caso, se cierra a las **12 horas** de haber entrado, aunque la esté usando.

Cuando se cierra, la plataforma le devuelve a la pantalla de entrada. No se pierde nada, basta con volver a entrar y seguir. Para salir antes, pulse **Salir**, arriba a la derecha. Si usa un ordenador compartido, salga siempre al terminar.

### Si se equivoca varias veces

Después de **5 intentos fallidos** seguidos, el usuario queda bloqueado durante **15 minutos**, aunque luego escriba bien la contraseña. No hay que hacer nada, se desbloquea solo. Si sigue sin poder entrar, avise a la persona de contacto.

## 4. Cómo moverse por la plataforma

Arriba de todas las pantallas hay una barra con los apartados. El apartado en el que está aparece subrayado. A la derecha están su nombre de usuario, el enlace **Contraseña** y **Salir**.

![La barra de arriba, con todos los apartados](../privado/manual/capturas/05-barra.png)

| Apartado | Para qué sirve |
|---|---|
| **Expedientes** | La lista de expedientes que sigue la plataforma y en qué punto está cada uno |
| **Catálogo** | Los materiales, con sus precios, y la exportación a Excel |
| **Conciliación** | Todos los expedientes publicados del departamento, aporten materiales o no, y por qué |
| **Contraste de presupuestos** | Para cada lote, si la suma de sus materiales cuadra con el presupuesto publicado |
| **Cola de revisión** | Casos que necesitan que alguien los mire con el documento delante |
| **Candidatos de matrícula** | Propuestas de matrícula para materiales que el documento publica sin ella |
| **Mantenimiento** | Cuándo se pone al día la plataforma y cómo fue la última vez |

Las pantallas que más va a usar son **Catálogo** y **Expedientes**.

## 5. Expedientes

Muestra todos los expedientes que sigue la plataforma. Arriba se ve el recuento, por ejemplo cuántos están completados, cuántos en revisión y cuántos no están publicados.

![Pantalla de expedientes](../privado/manual/capturas/04-expedientes.png)

### Buscar un expediente

Escriba en el buscador una parte del código del expediente (por ejemplo 28510.0088) o una palabra del título (por ejemplo balasto). La lista se filtra al escribir.

Los botones de la derecha filtran por estado.

- **Completado**. Se han leído sus documentos y sus materiales están en el catálogo.
- **En revisión**. Algo no se ha podido resolver solo y hay que mirarlo. Debajo del estado aparece el motivo en una frase. Muchos expedientes en revisión sí tienen materiales en el catálogo; lo que falta suele ser un dato concreto, como la baja.
- **No publicado**. La plataforma lo ha buscado y no está en la Plataforma de Contratación. Se agrupan al final de la lista, plegados. La plataforma los vuelve a buscar sola cada cierto tiempo.

![Búsqueda de la palabra balasto entre los expedientes completados](../privado/manual/capturas/06-expedientes-filtro.png)

### Qué se ve de cada expediente

| Columna | Qué es |
|---|---|
| **Expediente** | El código del expediente. Si de él cuelgan pedidos, aparece debajo cuántos, y al pulsar se despliegan |
| **Matriz** | El acuerdo marco del que cuelga, si lo hay. Lo normal es que diga No aplica |
| **Estado** | En qué punto está en la plataforma. Debajo pueden aparecer el estado según SAP y el estado según ADIF, que vienen de los listados de ADIF y son otra cosa |
| **Licitación** | El importe de licitación |
| **Adjudicación** | El importe de adjudicación |
| **Baja** | El porcentaje de rebaja de la oferta ganadora. Si cada lote tiene la suya, dice Varía por lote |

**No consta** en una celda quiere decir que ese dato no aparece en los documentos publicados.

### Los lotes

Un expediente se puede dividir en **lotes**. Cada lote es un contrato independiente con su propio adjudicatario y su propia baja. En el catálogo cada material lleva su lote, y se puede filtrar por él (capítulo 6). La comprobación lote a lote está en **Contraste de presupuestos** (capítulo 8).

En los pedidos que cuelgan de un acuerdo marco, la palabra lote a veces no es una división en contratos sino una familia de productos del acuerdo marco. Son dos cosas distintas con el mismo nombre.

### Botones que no debe usar

En esta pantalla hay un recuadro **Añadir expediente** y, en cada fila, los botones **Descargar** y **Extraer**. Sirven para que el equipo que mantiene la plataforma dé de alta un expediente o vuelva a procesarlo, y cambian el catálogo para todos. **Si no se lo han pedido, no los use.** Para pedir que se añada un expediente, avise a la persona de contacto.

## 6. Catálogo

Es la pantalla principal. Muestra todas las líneas del catálogo, 25 por página, con botones para pasar de página abajo del todo.

![Pantalla del catálogo](../privado/manual/capturas/07-catalogo.png)

### Filtros y búsquedas

![Los filtros del catálogo y el botón para exportar el Excel](../privado/manual/capturas/17-filtros-y-excel.png)

- **Buscar por matrícula**. Escriba la matrícula del material, el código de 9 cifras de ADIF (8 en pliegos antiguos). Busca en todos los expedientes.
- **Expediente**. Una parte del código del expediente.
- **Lote**. El lote tal como aparece en la columna Lote de la tabla, por ejemplo 1.
- **Descripción o código**. Una palabra de la descripción (brida, traviesa, cable) o un código de precio (P-014).
- **Orden**. **Líneas más completas primero** pone arriba las líneas con más datos rellenos. **Alfabético** las ordena por expediente y lote.

Los filtros se pueden combinar y la lista se actualiza sola al escribir. Encima de la tabla se ve cuántas líneas cumplen los filtros. Para volver a verlo todo, borre lo escrito en los filtros.

![Búsqueda de la palabra brida en la descripción](../privado/manual/capturas/08-catalogo-busqueda.png)

### Qué se ve de cada línea

Las columnas de la tabla son las mismas que las del Excel, que se explican una a una en el capítulo 11. Hay una más, **Revisión**, que puede decir

- **Revisar**, con un recuadro de color. La línea tiene un aviso, por ejemplo que se leyó de un documento escaneado o que la cantidad parece un año. Si deja el ratón encima, aparece el motivo. Estas líneas sí salen en el Excel;
- **Confirmado** o **Corregido**, si alguien ya la ha comprobado contra el documento;
- **Descartado**, si alguien la ha comprobado y la ha retirado. No sale en el Excel;
- nada, si no hay nada que decir.

En el **Precio adjudicado** puede aparecer **Pendiente**, que quiere decir que todavía falta la baja de ese lote para poder calcularlo.

### La trazabilidad de una línea

Pulse sobre cualquier línea. Debajo de la tabla se abre el recuadro **Trazabilidad**, con

- el expediente, el código interno y el título;
- la cantidad y su unidad;
- el precio, la baja y el precio adjudicado que resulta, o el aviso de que aún no hay baja;
- el **origen documental**, es decir, el documento y la página de los que sale la línea, con el texto exacto que se leyó.

![Recuadro de trazabilidad de una línea](../privado/manual/capturas/09-trazabilidad.png)

Pulse **Cerrar** para quitarlo.

## 7. Abrir los documentos originales

En el recuadro de trazabilidad, pulse el botón del **origen documental**, que lleva el nombre del documento y la página (por ejemplo ANEJO_1.pdf · página 15). El documento se abre en una pestaña nueva del navegador. Desde ahí se puede leer, pasar de página, descargar o imprimir con los botones de arriba.

![El documento original abierto en el navegador](../privado/manual/capturas/10-documento.png)

El documento se abre por la primera página. Para llegar al renglón de la línea, vaya a la página que indicaba el botón, escribiendo el número en el recuadro de página de arriba.

## 8. Conciliación y contraste de presupuestos

Son dos pantallas de comprobación. Enseñan lo mismo que las hojas del Excel que llevan su nombre (capítulo 11).

### Conciliación

Contesta a la pregunta de si la plataforma ha leído todo lo publicado. Hay una fila por cada expediente del departamento publicado en la Plataforma de Contratación, aporte materiales al catálogo o no, con su **Situación** y el **Motivo**.

Arriba se puede buscar un expediente por código o por título, y filtrar por situación pulsando los botones, que llevan al lado el número de expedientes de cada una.

![Pantalla de conciliación](../privado/manual/capturas/11-conciliacion.png)

### Contraste de presupuestos

Hay una fila por lote. Suma cantidad por precio de todas las líneas del lote y lo compara con el presupuesto de licitación publicado para ese lote. Si cuadra al céntimo, es una buena señal de que las líneas son las de ese lote y están bien leídas. Cuando no cuadra, la columna **Explicación** dice por qué.

Se puede buscar por código de expediente y filtrar por resultado. El desplegable **Qué significa cada resultado** explica cada uno.

![Pantalla de contraste de presupuestos](../privado/manual/capturas/12-contraste.png)

Que un lote no cuadre **no siempre es un error**. El caso más frecuente es que el documento da cantidades estimadas y el presupuesto es un máximo de gasto, así que no tienen por qué coincidir.

## 9. Cola de revisión y candidatos de matrícula

**Cola de revisión** reúne los expedientes que necesitan que alguien los mire con el documento delante. A la izquierda está la lista, con el motivo de cada uno. A la derecha, el motivo completo, un formulario para corregir datos del expediente y el documento abierto al lado.

![Cola de revisión](../privado/manual/capturas/13-revision.png)

**Candidatos de matrícula** propone matrículas para materiales que el documento publica sin ella, a partir del maestro de materiales de ADIF.

Puede entrar en las dos para consultar. Pero **lo que se guarda en ellas cambia el catálogo para todos**, porque cualquier corrección, confirmación o descarte se ve al momento en la web y en el siguiente Excel. Si no forma parte de su trabajo, no cambie nada ahí. Si ve un dato que cree que está mal, avise a la persona de contacto con el expediente, el lote y el código de precio o la matrícula.

## 10. Exportar el Excel

1. Vaya a **Catálogo**.
2. Pulse **Exportar Excel**, el botón verde a la derecha de los filtros.
3. **Espere sin hacer nada.** El navegador no muestra ningún avance mientras el fichero se prepara.
4. Cuando termine, el navegador descarga el fichero **catalogo_materiales_adif.xlsx** a su carpeta de descargas.

### Cuánto tarda

- Unos **4 minutos** si nadie más está exportando.
- Unos **5 minutos y medio** si otra persona exporta a la vez.

Pulse el botón **una sola vez**. Cada pulsación prepara otro Excel completo y hace que todos tarden más.

### Use Chrome o Edge, no Firefox

Firefox deja de esperar a los **5 minutos**. Si en ese momento el Excel no está listo, la descarga falla, y eso puede pasar si dos personas exportan a la vez. **Use Chrome o Edge**, que esperan lo necesario.

### Qué trae el Excel

El Excel trae **siempre el catálogo completo**, aunque en la pantalla tenga puestos filtros. Los filtros de la pantalla solo sirven para consultar. Para ver solo una parte en el Excel, use los filtros del propio Excel.

Se genera en el momento con los datos que hay en ese instante. Si lo exporta dos veces el mismo día sin que haya pasado el ciclo semanal, sale igual.

## 11. Qué contiene el Excel

El Excel tiene cuatro hojas. Puede aparecer una quinta, **Presupuestos ADIF**, si ADIF envía su listado de estados con el presupuesto de licitación.

| Hoja | Qué contiene |
|---|---|
| **Materiales** | El catálogo. Una fila por artículo, lote y expediente |
| **Conciliación** | Una fila por cada expediente publicado del departamento, aporte materiales o no, y por qué |
| **Contraste de presupuestos** | Una fila por lote, comparando la suma de sus materiales con su presupuesto publicado |
| **Resumen** | Las cifras del Excel y por qué hay líneas que no están en Materiales |

### Hoja Materiales

Tiene 18 columnas, siempre en este orden. Las once primeras son el formato original que pidió ADIF.

| Columna | Qué es | Cuándo puede estar vacía |
|---|---|---|
| **1. Código interno** | El número interno con el que ADIF agrupa el expediente en su listado de códigos de proyecto. Es el número por el que se busca en almacenes. Se repite entre expedientes de la misma familia, así que no identifica un expediente por sí solo | Cuando el expediente no está en el listado de códigos de ADIF, o el listado no le da número, o solo aparece otro expediente de su familia |
| **2. Código de expediente** | El número del expediente, en el formato de ADIF (6.24/28510.0088) | Nunca |
| **3. Código matriz** | El acuerdo marco del que cuelga este pedido | Es lo normal, porque la mayoría de los expedientes no cuelgan de ninguno |
| **4. Título expediente** | El objeto del contrato, tal como lo publica el anuncio | Si no se encuentra en los documentos |
| **5. Matrícula del material** | El código de 9 cifras con el que ADIF identifica el artículo (8 en pliegos antiguos) | Cuando el cuadro de precios no publica matrículas, que pasa en muchos pliegos, o cuando es una partida alzada |
| **6. Descripción del material** | La descripción del artículo, copiada tal cual del documento | Nunca |
| **7. Código del material** | La familia de la pieza (AGUJA, BRIDA, TRAVIESA, CABLE...). Sirve para agrupar el mismo tipo de material entre expedientes | Cuando la descripción no encaja en ninguna familia conocida, como marcas o servicios |
| **8. Cantidad** | Las unidades que el cuadro de precios prevé comprar | Cuando el documento no la publica, es una partida alzada, o da una cantidad distinta para cada lote |
| **9. Precio unitario** | El precio de licitación del artículo, es decir, el precio máximo publicado, antes de la rebaja | Cuando el documento no lo publica o da un precio distinto para cada lote |
| **10. Lote** | El lote al que pertenece el artículo | Nunca en la hoja Materiales, porque las líneas sin lote no salen en ella (capítulo 12) |
| **11. Precio adjudicado** | Lo que se paga de verdad por unidad. Es el precio unitario con la baja del lote aplicada. Se calcula, no se lee de ningún documento | Mientras falte la baja del lote o el precio unitario, o en contratos cuyo precio se revisa en cada pedido |
| **12. Baja del lote** | El porcentaje de rebaja que ofreció el adjudicatario de ese lote, tal como lo dice la adjudicación o el contrato. Una baja de 0 % puede ser real | Mientras no se haya publicado la adjudicación, o si el contrato no tiene una baja única |
| **13. Unidad de medida** | En qué se mide la cantidad y el precio (ud, m, kg, t, h...). Si el documento no la trae, se toma del maestro de materiales de ADIF, y la fila lo dice en la columna 17 | Cuando el documento no la publica y tampoco está en el maestro, o es una partida alzada |
| **14. Estado del contrato (SAP)** | En qué punto está el contrato según el listado de expedientes en ejecución de SAP que envió ADIF. No es el estado en la plataforma | Si el expediente no está en ese listado |
| **15. Objeto del contrato (documento)** | El mismo título de la columna 4, repetido por el orden de columnas que pidió ADIF | Igual que la columna 4 |
| **16. Código de precio** | El número del renglón dentro del cuadro de precios (P-001, P-067). Junto con el expediente y el lote, lleva a la fila exacta del documento | Cuando el cuadro de precios no numera sus renglones, que pasa en más de la mitad de las filas |
| **17. Motivo de las celdas vacías** | Explica, una por una, por qué está vacía cada celda vacía de esa fila (ver abajo) | Cuando la fila no tiene ninguna celda vacía |
| **18. Comentarios** | Columna libre para quien use el Excel. Sale siempre vacía | Siempre |

**Cómo leer el Motivo de las celdas vacías.** Cada celda vacía se explica con uno de tres motivos.

| Motivo | Qué quiere decir |
|---|---|
| **no aplica** | Ese dato no existe para este tipo de línea. Por ejemplo, una partida alzada no tiene matrícula. No falta nada |
| **no consta** | El documento no publica ese dato. No es un fallo de lectura, en el documento no hay nada que leer |
| **pendiente** | El dato existe pero falta otro para poder darlo. Por ejemplo, un precio adjudicado sin la baja del lote |

Casi siempre va acompañado de una explicación entre paréntesis. A veces esta columna también avisa de algo aunque la celda no esté vacía, por ejemplo que la unidad viene del maestro de materiales de ADIF y no del documento.

Las celdas vacías se dejan vacías a propósito, en lugar de poner un texto como N/D, para que las sumas y los filtros de números del Excel sigan funcionando.

**Dos cosas que conviene saber.**

- Una **partida alzada** es una cantidad reservada para un concepto, no un artículo de almacén. Por eso no tiene matrícula ni, a veces, cantidad.
- Hay matrículas correctas, copiadas del pliego, que **no están en el maestro de materiales de ADIF**, porque ese listado está incompleto. Salen igual. La plataforma no corrige ni completa matrículas.

### Hoja Conciliación

Una fila por cada expediente del departamento publicado en la Plataforma de Contratación, aporte materiales o no.

| Columna | Qué es |
|---|---|
| **Código de expediente** y **Título** | El expediente |
| **Órgano de contratación** | Quién licita, según el anuncio |
| **Estado que consta publicado en la Plataforma** | Hasta dónde llega lo publicado, que puede ser anuncio previo, en plazo, pendiente de adjudicación, adjudicada, resuelta o anulada. La Plataforma no publica lo que pasa después |
| **Estado según ADIF** | Lo que dice el listado de SAP que envía ADIF (en ejecución, recepcionado, cerrado...). Se mantiene separado del anterior para saber siempre de dónde sale cada uno |
| **Documentos descargados** | Cuántos documentos se han bajado de su ficha |
| **Documentos leídos con reconocimiento óptico** | Cuántos de ellos eran escaneados y se leyeron como imagen |
| **Líneas que aporta al catálogo** | Cuántas filas pone en la hoja Materiales |
| **Baja y de dónde sale** | La baja, con el texto del documento que la declara |
| **Situación** | Por qué aporta o no aporta materiales (ver abajo) |
| **Motivo** | La explicación de ese caso concreto |
| **En ejecución según ADIF** | La fecha de firma del acta de inicio, según el listado interno de ADIF de expedientes en ejecución |

Las situaciones más frecuentes son estas.

| Situación | Qué quiere decir |
|---|---|
| **Aporta líneas** | Sus materiales están en el catálogo |
| **Publicado sin cuadro de precios** | Se han leído todos sus documentos y ninguno trae un cuadro de precios |
| **Los precios están en un acuerdo marco que no está publicado** | Es un pedido de un acuerdo marco cuyos documentos no están en la Plataforma, así que no hay de dónde leer el precio |
| **El acuerdo marco está publicado pero no publica precios unitarios** | El acuerdo marco solo publica el modelo de oferta en blanco |
| **Documentos escaneados que no se han podido leer** | Sus documentos son imágenes y no se ha podido sacar de ellos un cuadro de precios fiable |
| **Publicado dentro de la ficha de otro expediente** | Sus documentos están publicados bajo el número del expediente principal. Lo que aporta se cuenta en la fila del principal |
| **Licitación por lotes de la que solo se conocen algunos lotes** | Solo se puede leer la información de algunos lotes, y no del suyo |
| **Pendiente de procesar** | Aún no se han descargado o leído sus documentos |
| **Otro** | Ninguna de las anteriores. La columna Motivo explica el caso |

### Hoja Contraste de presupuestos

Una fila por lote. Compara la suma de cantidad por precio de sus líneas en Materiales con el presupuesto de licitación publicado para ese lote, siempre sin IVA o con la cifra equivalente.

| Columna | Qué es |
|---|---|
| **Código de expediente** y **Lote** | El lote |
| **Presupuesto publicado** | La cifra tal como se publicó |
| **Qué cifra es** | Si es la base sin IVA, con IVA, o el presupuesto de ejecución material |
| **Cifra con la que se compara** | La que corresponde a los precios del cuadro |
| **Documento** y **Página** | De dónde sale el presupuesto |
| **Suma de sus líneas** | Cantidad por precio de todas sus líneas |
| **Diferencia (€)** y **Diferencia (%)** | Cuánto se separa la suma del presupuesto |
| **Líneas** y **Líneas sin cantidad** | Cuántas líneas tiene el lote y cuántas no traen cantidad en el documento |
| **Resultado** | Si cuadra o por qué no (ver abajo) |
| **Explicación** | En una frase, qué pasa con ese lote |

Cuando el lote cuadra, el resultado es **Cuadra al céntimo**, si la suma es exactamente el presupuesto, o **Cuadra con diferencia menor del 0,01 %**, si es casi exacta.

Cuando no cuadra, el resultado empieza por **No cuadra** y sigue con la causa. Las más frecuentes son estas.

| Causa que acompaña a No cuadra | Qué quiere decir |
|---|---|
| **cantidades estimadas, el presupuesto es un máximo** | El documento da cantidades de referencia y el presupuesto es un máximo de gasto. Es lo más habitual y no es un error |
| **faltan líneas del lote en el catálogo** | Hay líneas del lote que no están en Materiales. La explicación dice cuáles |
| **el presupuesto incluye partidas que el cuadro no trae** | El presupuesto incluye obra, servicios u otros conceptos que no están en el cuadro de precios |
| **discrepancia del propio documento** | Las líneas están bien leídas y es el propio documento el que no suma su presupuesto |

Si alguna línea del lote no trae cantidad, la suma está incompleta y el resultado es **No se puede cerrar**, seguido de **faltan cantidades**.

Debajo de la tabla, la hoja cuenta los lotes que no entran en el contraste y por qué, por ejemplo porque no se publica un presupuesto para ese lote.

### Hoja Resumen

Recoge las cifras del Excel (cuántas líneas hay en Materiales, cuántas están en revisión y no salen, cuántas tienen avisos) y, sobre todo, una tabla con **por qué hay líneas que no están en Materiales**, que para cada causa dice qué ha pasado, cuántas líneas son y qué haría falta para resolverlo.

## 12. Líneas en revisión, y por qué no salen en Materiales

En el catálogo de la web aparecen **todas** las líneas que se han leído de los documentos, unas 40.000. En la hoja Materiales del Excel salen bastantes menos, unas 19.400. La diferencia son las líneas **en revisión**.

Una línea queda en revisión, y fuera de la hoja Materiales, cuando la plataforma no puede asegurar algo sin inventárselo. Los casos son estos.

- **No se sabe con seguridad a qué lote pertenece.** Es, con mucho, el caso más frecuente. Ponerla en un lote al azar podría atribuir un precio al contrato equivocado, y repetirla en todos los lotes duplicaría materiales.
- **No se ha podido identificar con seguridad qué columna del cuadro es cada dato**, o el documento solo publica el importe total del renglón y no el precio unitario.
- **Alguien la ha descartado** después de comprobarla contra el documento.
- **Es un material ya incluido**, repetido en otro documento del mismo expediente.

Estas líneas **no se pierden**, porque siguen guardadas, se ven en el catálogo de la web y están contadas, por causa, en la hoja Resumen. Cuando alguien las resuelve, pasan a la hoja Materiales en el siguiente Excel.

No hay que confundirlas con las líneas que llevan la marca **Revisar** en la web. Esas tienen un aviso, por ejemplo que se leyeron de un documento escaneado, pero **sí salen** en Materiales. El aviso es para que las compruebe contra el documento antes de dar la cifra por buena.

## 13. El ciclo semanal

La plataforma se pone al día sola **una vez por semana**, sin que nadie tenga que hacer nada. Ahora mismo se lanza los **miércoles a media tarde** (la fecha y la hora exactas están en la pantalla de Mantenimiento) y tarda entre 20 y 40 minutos. Mientras dura se puede seguir consultando y exportando con normalidad.

### Qué hace

- Busca en la Plataforma de Contratación expedientes nuevos del departamento.
- Descarga los documentos nuevos que se hayan publicado, por ejemplo una adjudicación que antes no estaba.
- Lee lo que es nuevo o ha cambiado y pone al día el catálogo con los materiales nuevos, las bajas y los precios adjudicados que llegan con la adjudicación, y los cambios de estado.
- Vuelve a buscar los expedientes que la otra vez no estaban publicados.
- Pasa una auditoría automática del catálogo, que solo avisa de cosas raras y nunca corrige nada por su cuenta.

Después de cada ciclo, un Excel nuevo puede traer más filas o filas con datos que antes faltaban. Es lo esperado.

### Dónde se ve si ha ido bien

En **Mantenimiento**, recuadro **Ejecución programada**.

- **Última ejecución** y **Próxima ejecución** dicen cuándo fue la última vez y cuándo será la siguiente.
- **Qué encontró la última ejecución** resume lo que hizo, es decir, cuántos expedientes nuevos encontró y cuántas descargas y extracciones hizo.

![Pantalla de mantenimiento, con la ejecución programada](../privado/manual/capturas/14-mantenimiento.png)

Más abajo, el **Histórico** lista los ciclos anteriores. En la columna **Estado**, **completado** quiere decir que fue bien. Si aparece **fallido**, o la última ejecución tiene más de una semana, avise a la persona de contacto.

![Histórico de ciclos](../privado/manual/capturas/15-mantenimiento-historico.png)

En esta pantalla hay dos botones, **Lanzar ciclo ahora** y **Ejecutar ahora** (ingesta manual de documentos). **No los pulse.** Lanzan trabajos largos que cambian el catálogo para todos y son cosa del equipo que mantiene la plataforma.

## 14. Lo que la plataforma no hace

Para que nadie espere algo que no es.

- **No inventa datos.** Si un documento no publica un dato, la celda queda vacía y explicada.
- **No conoce lo que no está publicado.** Si un precio no está en ningún documento de la Plataforma de Contratación ni en los listados que ha enviado ADIF, no lo tiene.
- **No está conectada con SAP.** Los estados según SAP y según ADIF son los de los listados que ADIF envió, y solo cambian cuando ADIF manda uno nuevo.
- **No se actualiza al momento.** Lo publicado hoy en la Plataforma de Contratación entra en el siguiente ciclo semanal.
- **No es un sistema de compras ni de pedidos.** Solo informa. Desde ella no se compra ni se tramita nada.
- **No corrige ni completa matrículas**, ni unifica descripciones que el pliego escribe de formas distintas.
- **No envía avisos ni correos.**
- **No guarda los Excel exportados.** Cada exportación se genera en el momento. Si necesita conservar el de una fecha, guarde el fichero.
- **No tiene recuperación de contraseña** ni gestión de usuarios desde la web. Para eso, la persona de contacto.

## 15. Si algo no funciona

| Qué pasa | Qué hacer |
|---|---|
| La plataforma me devuelve a la pantalla de entrada | La sesión ha caducado (30 minutos sin actividad o 12 horas). Vuelva a entrar |
| No puedo entrar con mi contraseña | Compruebe las mayúsculas. Tras 5 intentos fallidos, espere 15 minutos. Si la ha olvidado, avise a la persona de contacto |
| El Excel no termina de descargarse | Use Chrome o Edge, no Firefox. Pulse el botón una sola vez y espere unos 4 minutos, o unos 5 minutos y medio si otra persona exporta a la vez. Si falla con Chrome o Edge, vuelva a intentarlo pasados unos minutos |
| Una pantalla se queda en Cargando o da un error de conexión | Recargue la página. Si sigue, compruebe su conexión a internet y vuelva a intentarlo en unos minutos |
| Un dato del catálogo me parece incorrecto | Abra el documento original desde la trazabilidad y compruébelo. Si el documento dice otra cosa, avise con el expediente, el lote y el código de precio o la matrícula |
| Falta un expediente que debería estar | Búsquelo en Conciliación y en Expedientes. Si no está, avise con su código |
| El último ciclo semanal falló o lleva más de una semana sin ejecutarse | Avise a la persona de contacto |

Al avisar, diga siempre qué estaba haciendo, en qué pantalla, a qué hora y, si puede, adjunte una captura de pantalla. **Nunca envíe su contraseña**, ni siquiera a la persona de contacto, porque nadie se la va a pedir.

### Persona de contacto

| | |
|---|---|
| **Nombre** | |
| **Correo electrónico** | |
| **Teléfono** | |
| **Horario de atención** | |
