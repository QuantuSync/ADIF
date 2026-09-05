// Traduce los motivos técnicos que produce el motor (app/extraccion/*.py,
// concatenados con "; " por `_acumular_motivo`) a lenguaje de ADIF, y los
// clasifica en dos categorías (encargo de la sesión de diseño de interfaz):
//
//   - "contradiccion": el propio documento trae un dato que no cuadra
//     (una baja que no coincide con los importes, un número de expediente
//     distinto entre dos Anuncios, una matrícula ilegible).
//   - "limitacion": el sistema no tiene, hoy, forma de resolverlo solo
//     (una matriz sin publicar, una referencia circular, un documento
//     escaneado, una tabla sin lote reconocible por diseño).
//
// No toca el motor: solo interpreta el texto que ya produce, con sus
// literales reales (comprobados leyendo app/extraccion/*.py y app/catalogo.py).

export type CategoriaMotivo = "contradiccion" | "limitacion";

export type MotivoInterpretado = {
  categoria: CategoriaMotivo;
  texto: string;
  tecnico: string;
};

const ESTADO_HUMANO: Record<string, string> = {
  pendiente: "pendiente de descargar",
  descargando: "descargándose",
  descargado: "descargado, pendiente de extraer",
  extrayendo: "extrayéndose",
  esperando_matriz: "esperando a su propia matriz",
  pendiente_revision: "pendiente de revisión",
  completado: "completado pero sin líneas de catálogo",
  fallido: "no se pudo descargar",
  sin_publicar: "no publicado en la Plataforma",
};

function estadoHumano(estado: string): string {
  return ESTADO_HUMANO[estado] ?? estado;
}

// Prefijos que marcan el INICIO de un motivo de nivel superior (los que
// `_acumular_motivo` une con "; "). Todo lo que caiga entre el inicio de un
// prefijo y el siguiente pertenece al mismo motivo, aunque contenga sus
// propias listas internas separadas por "; " (nombres de documento, páginas).
type Regla = {
  prefijo: RegExp; // debe casar al principio del segmento (^)
  categoria: CategoriaMotivo;
  humanizar: (texto: string) => string;
};

const REGLAS: Regla[] = [
  {
    prefijo: /^la matriz (\S+) no tiene ningún lote registrado \(estado: (\w+)\)$/,
    categoria: "limitacion",
    humanizar: (t) => {
      const m = t.match(/^la matriz (\S+) no tiene ningún lote registrado \(estado: (\w+)\)$/)!;
      return `Este pedido depende del acuerdo marco ${m[1]}, pero esa matriz está ${estadoHumano(
        m[2]
      )} y no tiene ningún cuadro de precios. No se puede heredar el precio ni la baja hasta que se resuelva.`;
    },
  },
  {
    prefijo: /^la matriz declarada \('([^']+)'\) forma un ciclo/,
    categoria: "limitacion",
    humanizar: (t) => {
      const m = t.match(/^la matriz declarada \('([^']+)'\)/)!;
      return `La matriz declarada (${m[1]}) forma una referencia circular con este expediente, directa o a través de su propia cadena de matrices. El sistema no puede heredar el precio sin entrar en un bucle.`;
    },
  },
  {
    prefijo: /^la matriz (\S+) es multi-lote \((\d+) lotes\)/,
    categoria: "limitacion",
    humanizar: (t) => {
      const m = t.match(/^la matriz (\S+) es multi-lote \((\d+) lotes\)/)!;
      return `La matriz ${m[1]} reparte sus precios en ${m[2]} lotes distintos, y este pedido no indica a cuál pertenece. El sistema no elige uno al azar.`;
    },
  },
  {
    prefijo: /^la matriz (\S+) tampoco tiene cuadro de precios ni baja/,
    categoria: "limitacion",
    humanizar: (t) => {
      const m = t.match(/^la matriz (\S+) tampoco tiene cuadro de precios ni baja(?::\s*(.*))?$/);
      const detalle = m?.[2] ? ` (motivo de la matriz: ${m[2]})` : "";
      return `La matriz ${m?.[1]} tampoco tiene cuadro de precios ni baja registrada${detalle}.`;
    },
  },
  {
    prefijo: /^el pedido trae \d+ línea\(s\) propia\(s\) de catálogo/,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(
        /^el pedido trae (\d+) línea\(s\) propia\(s\) de catálogo, y la matriz (\S+) trae (\d+)/
      );
      return `Este pedido ya trae ${m?.[1]} línea(s) propias de catálogo, y su matriz (${m?.[2]}) aporta ${m?.[3]} más. El sistema no las combina automáticamente: hay que decidir cuál tabla es la que vale.`;
    },
  },
  {
    prefijo: /^esperando a que se procese la matriz (\S+)/,
    categoria: "limitacion",
    humanizar: (t) => {
      const m = t.match(/^esperando a que se procese la matriz (\S+)/)!;
      return `Esperando a que termine de procesarse primero el acuerdo marco ${m[1]}. Este pedido se revisará solo en cuanto la matriz esté lista.`;
    },
  },
  {
    // Solo cuando NO va precedido de "lote X: " (ese caso lo cubre la regla
    // de "lote" de más abajo, que humaniza el mensaje completo).
    prefijo: /^(?<!lote [^:]{1,40}: )la baja declarada \(([^)]+)\) no cuadra con la baja que resulta de los importes \(([^)]+)\)/,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(
        /^la baja declarada \(([^)]+)\) no cuadra con la baja que resulta de los importes \(([^)]+)\)/
      )!;
      return `La baja que declara el documento (${m[1]}) no coincide con la que resulta de comparar el importe de licitación y el de adjudicación (${m[2]}). Puede ser un error de transcripción, o que los importes no correspondan a este lote.`;
    },
  },
  {
    prefijo: /^(?<!lote [^:]{1,40}: )licitación y adjudicación coinciden \(posible caso de precios unitarios\)/,
    categoria: "limitacion",
    humanizar: () =>
      `El importe de licitación y el de adjudicación son iguales (el patrón habitual de "precios unitarios"), pero ningún documento declara en texto el porcentaje de baja. Hay que buscarlo a mano o confirmarlo.`,
  },
  {
    // Envuelve una de las tres anteriores con el lote al que pertenece.
    prefijo: /^lote ([^:]{1,40}): /,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(/^lote ([^:]{1,40}): ([\s\S]*)$/)!;
      const interior = interpretarUnSegmento(m[2]);
      return `En el lote ${m[1]}: ${interior.texto}`;
    },
  },
  {
    prefijo: /^los documentos Anuncio PCSP de este expediente declaran 'Número de Expediente' distintos entre sí/,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(/\(([^)]+)\)/);
      return `Los distintos formularios "Anuncio PCSP" de este expediente declaran números de expediente distintos entre sí (${m?.[1] ?? "ver detalle"}). El sistema no elige uno sin confirmación.`;
    },
  },
  {
    prefijo: /^el Anuncio PCSP declara 'Número de Expediente' (\S+), pero ya existe otro expediente/,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(/^el Anuncio PCSP declara 'Número de Expediente' (\S+), pero ya existe otro expediente \(id (\d+)\)/);
      return `El Anuncio PCSP de este expediente declara el número ${m?.[1]}, pero ya existe otro expediente registrado con ese mismo código (id interno ${m?.[2]}). Podría ser un duplicado: el sistema no fusiona expedientes solo.`;
    },
  },
  {
    prefijo: /^la matriz declarada en el Anuncio PCSP \(([^)]+)\) no coincide con la columna MATRIZ del Excel/,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(
        /^la matriz declarada en el Anuncio PCSP \(([^)]+)\) no coincide con la columna MATRIZ del Excel de códigos \(([^)]+)\)/
      )!;
      return `La matriz que declara el propio Anuncio PCSP (${m[1]}) no coincide con la columna MATRIZ del Excel de códigos (${m[2]}). Hay que confirmar cuál es la correcta.`;
    },
  },
  {
    prefijo: /^extracción encolada sin documentos descargados para este expediente/,
    categoria: "limitacion",
    humanizar: () => `Todavía no hay ningún documento descargado para este expediente: no hay nada que leer hasta que termine la descarga.`,
  },
  {
    prefijo: /^no se extrajo ninguna línea de catálogo de los documentos descargados/,
    categoria: "limitacion",
    humanizar: () => `Los documentos se descargaron bien, pero no se ha encontrado ninguna tabla de precios reconocible dentro de ellos.`,
  },
  {
    prefijo: /^no se pudo determinar la baja de ningún lote/,
    categoria: "limitacion",
    humanizar: () => `No se ha encontrado, en ningún documento, el porcentaje de baja declarado para ningún lote de este expediente.`,
  },
  {
    prefijo: /^no se pudo extraer el cuadro de precios de: /,
    categoria: "limitacion",
    humanizar: (t) => {
      const lista = t.replace(/^no se pudo extraer el cuadro de precios de: /, "");
      return `No se ha podido localizar ni leer la tabla de precios dentro de: ${lista}.`;
    },
  },
  {
    prefijo: /^documento\(s\) escaneado\(s\), sin capa de texto/,
    categoria: "limitacion",
    humanizar: (t) => {
      const lista = t.replace(/^.*CLAUDE\.md sección 15\):\s*/, "");
      return `${lista} — es un documento escaneado (imagen). El sistema todavía no lee documentos escaneados automáticamente; hay que revisarlo a mano.`;
    },
  },
  {
    prefijo: /^[^\s;]+\.pdf: página \d+: /,
    categoria: "limitacion",
    humanizar: (t) => {
      const m = t.match(/^([^\s;]+\.pdf): ([\s\S]+)$/)!;
      const items = m[2].split(/; (?=página \d+:)/).map((item) => {
        const im = item.match(/^página (\d+): ([\s\S]+)$/);
        if (!im) return item;
        const detalle = im[2].startsWith("ninguna cabecera")
          ? "no hay ninguna cabecera de lote reconocible justo antes de la tabla"
          : im[2].startsWith("varias cabeceras")
          ? `aparece más de una cabecera de lote antes de la tabla (${im[2].split(": ")[1] ?? ""})`
          : im[2];
        return `página ${im[1]} (${detalle})`;
      });
      return `No se pudo determinar a qué lote pertenece parte del cuadro de precios de ${m[1]}: ${items.join(
        ", "
      )}. Por diseño, el sistema no asigna un lote a ciegas.`;
    },
  },
  {
    prefijo: /^[^\s;]+\.pdf: \d+ línea\(s\) con un valor que no se pudo interpretar/,
    categoria: "contradiccion",
    humanizar: (t) => {
      const m = t.match(/^([^\s;]+\.pdf): (\d+) línea\(s\) con un valor/)!;
      return `En ${m[1]} hay ${m[2]} línea(s) cuyo valor de cantidad, precio o matrícula no tiene un formato reconocible. Están marcadas en la tabla de líneas para revisarlas una a una.`;
    },
  },
];

// El orden de estos prefijos decide dónde se corta cada segmento del texto
// acumulado — deben cubrir exactamente los mismos casos que `REGLAS`.
const PREFIJOS_NIVEL_SUPERIOR = REGLAS.map((r) => r.prefijo.source.replace(/^\^/, "").replace(/\$$/, ""));
const RE_CUALQUIER_PREFIJO = new RegExp(PREFIJOS_NIVEL_SUPERIOR.map((p) => `(?:${p})`).join("|"), "g");

function interpretarUnSegmento(segmento: string): MotivoInterpretado {
  const texto = segmento.trim();
  for (const regla of REGLAS) {
    if (regla.prefijo.test(texto)) {
      return { categoria: regla.categoria, texto: regla.humanizar(texto), tecnico: texto };
    }
  }
  return { categoria: "limitacion", texto, tecnico: texto };
}

// Corta el `expediente.error` acumulado (o un `motivo_revision` de línea) en
// sus motivos de nivel superior, respetando las listas internas ("; " dentro
// de un mismo motivo, como varios documentos o varias páginas).
export function interpretarMotivos(motivo: string | null | undefined): MotivoInterpretado[] {
  if (!motivo) return [];
  const inicios: number[] = [];
  RE_CUALQUIER_PREFIJO.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = RE_CUALQUIER_PREFIJO.exec(motivo))) {
    inicios.push(m.index);
    if (m[0].length === 0) RE_CUALQUIER_PREFIJO.lastIndex++;
  }
  if (inicios.length === 0 || inicios[0] !== 0) inicios.unshift(0);

  const segmentos: string[] = [];
  for (let i = 0; i < inicios.length; i++) {
    const inicio = inicios[i];
    const fin = i + 1 < inicios.length ? inicios[i + 1] : motivo.length;
    const trozo = motivo.slice(inicio, fin).replace(/^;\s*/, "").replace(/;\s*$/, "").trim();
    if (trozo) segmentos.push(trozo);
  }
  return segmentos.map(interpretarUnSegmento);
}

// Motivo de línea individual (`LineaCatalogo.motivo_revision`): mismos
// literales, un único motivo por línea (nunca acumulado con "; " entre
// varios), así que se interpreta directo.
export function interpretarMotivoLinea(motivo: string | null | undefined): MotivoInterpretado | null {
  if (!motivo) return null;
  if (motivo.startsWith("codigo_precio recuperado tras descartar ruido de pie de página")) {
    const m = motivo.match(/->\s*'([^']*)'\)$/);
    return {
      categoria: "contradiccion",
      texto: `El código de esta línea traía pegado un fragmento del sello de verificación del documento; se ha limpiado a "${
        m?.[1] ?? "su valor correcto"
      }". Confírmalo antes de darlo por bueno.`,
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("codigo_precio descartado: pie de página")) {
    return {
      categoria: "contradiccion",
      texto: "El código de esta línea es en realidad el sello de verificación del documento colado en esa celda, sin ningún código real dentro; se ha dejado en blanco.",
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("codigo_precio con formato no reconocido")) {
    const m = motivo.match(/dar por bueno: '([^']*)'$/);
    return {
      categoria: "contradiccion",
      texto: `El código de esta línea ("${
        m?.[1] ?? "ver mensaje técnico"
      }") no sigue ningún formato conocido en este tipo de documento. Puede ser válido y solo nuevo para el sistema, o un error de lectura: confírmalo antes de darlo por bueno.`,
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("cabecera desalineada con los datos")) {
    return {
      categoria: "contradiccion",
      texto: "En este documento, la cabecera de la tabla no coincidía con la posición real de los datos; el sistema ha recolocado las columnas automáticamente. Confirma esta línea antes de darla por buena.",
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("descripción recuperada de la columna siguiente")) {
    return {
      categoria: "contradiccion",
      texto: "La descripción de esta línea no estaba en su columna habitual en este documento; se ha recuperado de la columna de al lado. Confírmala antes de darla por buena.",
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("valor de matrícula no reconocible")) {
    const m = motivo.match(/descartado: (.+)$/);
    return {
      categoria: "contradiccion",
      texto: `La matrícula de esta línea no tiene un formato reconocible (valor original: ${m?.[1] ?? "—"}); se ha descartado.`,
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("cantidad no interpretable")) {
    return { categoria: "contradiccion", texto: "La cantidad de esta línea no tiene un formato numérico reconocible.", tecnico: motivo };
  }
  if (motivo.startsWith("precio unitario no interpretable")) {
    return { categoria: "contradiccion", texto: "El precio unitario de esta línea no tiene un formato numérico reconocible.", tecnico: motivo };
  }
  if (motivo.startsWith("ninguna cabecera LOTE N")) {
    return {
      categoria: "limitacion",
      texto: "No hay ninguna cabecera de lote reconocible justo antes de esta tabla; no se ha podido asignar a un lote.",
      tecnico: motivo,
    };
  }
  if (motivo.startsWith("varias cabeceras de lote")) {
    const m = motivo.match(/franja que precede a esta tabla: (.+)$/);
    return {
      categoria: "limitacion",
      texto: `Aparece más de una cabecera de lote antes de esta tabla (${m?.[1] ?? "ver detalle"}); no se ha podido asignar a uno solo.`,
      tecnico: motivo,
    };
  }
  return { categoria: "limitacion", texto: motivo, tecnico: motivo };
}
