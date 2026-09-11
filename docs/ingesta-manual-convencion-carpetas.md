# Convención de carpetas para la ingesta manual de documentos

Este documento describe cómo tienen que organizarse los PDF que la macro
del cliente deje en la carpeta compartida, para que el sistema los
reconozca automáticamente. Pensado para poder enviarse tal cual al equipo
que está construyendo la macro.

## Resumen

**Una subcarpeta por expediente**, nombrada con el código de expediente
sustituyendo la barra (`/`) por un guion bajo (`_`).

```
carpeta_de_entrada/
├── 6.24_28510.0088/
│   ├── cualquier_nombre_de_fichero.pdf
│   └── otro_documento.pdf
├── 6.25_28510.0142/
│   └── contrato_firmado.pdf
└── ...
```

- El código de expediente tiene siempre la forma `N.NN/DDDDD.NNNN`
  (ejemplo: `6.24/28510.0088`). Para el nombre de la carpeta, esa barra se
  sustituye por un guion bajo: `6.24_28510.0088`.
- Dentro de cada carpeta puede haber uno o varios PDF. El nombre de cada
  fichero es libre — puede ser el que use SAP internamente, o el que genere
  la macro — no hace falta seguir ninguna convención de nombre de fichero.
- Solo se leen ficheros con extensión `.pdf`. Cualquier otro tipo de
  fichero en la misma carpeta se ignora.

## Por qué esta convención y no otra

Se valoraron tres formas de indicar a qué expediente pertenece cada
documento:

1. **Una carpeta por expediente (la elegida).** Funciona igual para
   cualquier tipo de documento, incluidos los que nunca declaran su propio
   código de expediente en el texto — que son, precisamente, los cuadros de
   precios (anejos) que más importan para el catálogo.
2. Código en el nombre del fichero. Descartado: más frágil si algún paso
   de la macro (compresión, exportación, copia) trunca o normaliza nombres
   de fichero largos.
3. Leer el código dentro de cada PDF. Descartado como único mecanismo:
   solo funciona con los documentos que declaran su código de forma
   explícita (el Anuncio de adjudicación de la Plataforma, y algunos
   Contratos firmados) — la mayoría de los cuadros de precios no lo hacen.

## Comprobación automática

Cuando un documento sí declara su propio código de expediente en el texto
(el Anuncio de adjudicación con "Número de Expediente", o un Contrato
firmado con "Contrato nº"), el sistema compara ese código con el de la
carpeta que lo contiene:

- Si coinciden, el documento se registra con normalidad.
- Si **no coinciden**, el documento **no se enlaza automáticamente** — el
  sistema nunca adivina cuál de los dos códigos es el correcto. Queda
  señalado en la ficha del expediente para que alguien lo revise a mano
  (misma carpeta, corregir el código de la carpeta o mover el fichero a la
  carpeta correcta, y volver a lanzar la ingesta).

## Qué pasa con cada fichero

- **Nunca se duplica nada.** Si la misma carpeta se vuelve a leer sin
  cambios (o con algún fichero nuevo añadido), los documentos ya
  registrados no se vuelven a guardar ni a enlazar — el sistema identifica
  cada fichero por su contenido, no por su nombre ni por cuándo se leyó.
- **Nunca se borra ni se sustituye nada de la carpeta de entrada.** El
  sistema lee y copia los PDF a su propio almacenamiento; los originales
  de la carpeta compartida pueden dejarse, moverse o archivarse según el
  criterio del cliente.
- Si el mismo expediente aparece más adelante publicado de verdad en la
  Plataforma de Contratación, y se descarga desde ahí, el sistema lo sabe
  distinguir de lo aportado a mano — y si algún dato del documento
  publicado no coincide con el aportado a mano, prevalece el documento
  publicado, sin perder de vista que hubo una discrepancia.

## Cómo se lanza

La ingesta no ocurre sola: alguien del equipo del sistema pulsa "Ejecutar
ahora" en la pantalla de mantenimiento (o se lanza a través de la API)
después de que la macro haya dejado ficheros nuevos en la carpeta
compartida. No hace falta avisar con antelación de cada tanda — basta con
saber que hay ficheros nuevos esperando.
