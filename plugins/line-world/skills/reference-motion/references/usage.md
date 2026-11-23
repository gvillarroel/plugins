# Usar los componentes en una película

Elige un patrón en [la galería](../assets/demo.html). Cada transición se reproduce una vez y mantiene el resultado en pantalla. La ficha muestra la duración de lectura y el instante de la referencia. Para producir un archivo, entrega tus datos al [generador](../scripts/generate_motion.py). La [receta de ejemplo](../assets/ejemplo.json) presenta las 12 salidas de las 14 h y añade los otros horarios sin desplazar esa barra.

## Generar desde JSON

En `guest-grid` caben cuatro personas. Para decidir qué fuentes se mueven, asigna a cada participante un clip, un retrato local o un fotograma elegido de su clip. Por ejemplo, en `assets` escribe `"ponente_c": {"path":"sesion/c.mp4","still_s":1.25}` y referencia `"media":"ponente_c"` en su fila. `still_s` se mide desde el comienzo del vídeo y utiliza el primer cuadro decodificable a partir de ese segundo. La vista previa y la exportación mantienen ese fotograma todo el plano. Cambia la asignación en la siguiente escena para ceder la palabra a otra persona.

Pueden moverse hasta tres paneles a la vez. Con tres clips, entra con un corte. Una transición con movimiento deja espacio para dos clips vivos. Los nombres aparecen ya completos si su barrido excedería el máximo y siguen legibles mientras transcurren los clips. El modo de cuatro retratos fijos conserva las cuatro personas y sus nombres desde el primer cuadro.

Desde el directorio de esta skill, usa estos comandos con una carpeta de proyecto como destino.

```sh
uv run --script scripts/generate_motion.py init data-chart mi-proyecto/grafica.json
uv run --script scripts/generate_motion.py check mi-proyecto/grafica.json
uv run --script scripts/generate_motion.py render mi-proyecto/grafica.json mi-proyecto/grafica.png
uv run --script scripts/generate_motion.py render assets/ejemplo.json mi-proyecto/comparacion.mp4
uv run --script scripts/generate_motion.py verify assets/ejemplo.json mi-proyecto/comparacion.mp4 --report mi-proyecto/comparacion.verificada.json
uv run --script scripts/generate_motion.py audit-library mi-proyecto/biblioteca.qa.json --sheet mi-proyecto/biblioteca.jpg
```

`init` crea un ejemplo para cualquiera de los 33 identificadores de la galería. Edita sus propiedades para generar otro gráfico con el mismo diseño. La exportación PNG guarda el estado de lectura de la última escena. La exportación MP4 incluye la secuencia completa y requiere FFmpeg y FFprobe en el PATH. Para el navegador, el generador usa Chromium de Playwright y en Windows también puede usar Edge instalado. Puedes elegir Chrome añadiendo `--browser chrome` **antes** del subcomando. En un equipo con uv y sin navegador compatible, instala Chromium con `uvx --from playwright==1.61.0 playwright install chromium`.

| Campo de la receta | Uso |
| --- | --- |
| `version`, `scenes` | Usa `1` y una lista ordenada. Cada escena lleva un `id` único y el `artifact` de la galería. El lienzo predeterminado es 1280 × 720 a 24 fps. |
| `props` | Contenido completo del artefacto. `init` proporciona una plantilla. Para barras, `labels` y `values` deben tener la misma longitud. `highlightIndex` selecciona una barra contando desde cero. |
| `hold` | Segundos de lectura con el último estado estable. Sin este campo, el generador estima la pausa a partir del contenido. Una pausa explícita demasiado corta produce un error con el mínimo calculado. |
| `transition` | En la escena de destino, indica por ejemplo `{"id":"push-left","seconds":2.4}`. La transición desplaza la escena anterior una sola vez. El corte ocupa un fotograma. Para un retorno deliberado A→B→A, explica el motivo con `return_reason`. |
| `handoff` | Marca la relación editorial con la escena anterior. Usa `section` para abrir una sección, `comparison` para introducir otra vista que se va a comparar o `detail` para entrar en un detalle. |
| `transition_policy` | Política del proyecto. El modo predeterminado `occasional` reserva los movimientos para uniones motivadas. `{"mode":"cuts-only"}` utiliza cortes en toda la pieza. |
| `assets` | Mapa a medios locales. En la escena usa el ID, por ejemplo `"media":"plano"`. Las rutas se resuelven junto a la receta. Se admiten PNG, JPEG, WebP, MP4 y WebM. |

### Fotografías y tomas en movimiento

```json
{
  "assets": {
    "plano": "imagenes/plano.png",
    "retrato": {"path":"imagenes/retrato.png","fit":"cover","focal":[0.43,0.23]},
    "jardin": {"path":"clips/jardin.mp4","in_s":0.25,"out_s":4.90,"fit":"contain"}
  }
}
```

`fit:"cover"` llena el marco. `focal:[x,y]` expresa el centro de interés en la imagen original, de 0 a 1. El recorte intenta centrar ese punto dentro del marco y se detiene en los bordes. Por ejemplo, localiza los ojos en el retrato para conservar la parte superior de la cabeza. `fit:"contain"` conserva la imagen entera, centrada sobre fondo blanco. Las rutas simples conservan el encuadre central.

En vídeo, `in_s` incluye el comienzo y `out_s` excluye el final. Por defecto se usa la pista visual entera. Cada escena inicia su propio reloj desde `in_s`. El plano entrante ya avanza durante la transición y el saliente conserva su último cuadro. Si se agota el fragmento antes de que termine la lectura, permanece su última imagen. El sonido de la toma se gestiona en la mezcla de audio.

FFmpeg decodifica el tramo necesario a la cadencia de la receta en una caché temporal. El índice de cuadro es entero y volver al mismo instante produce la misma imagen. Durante una pausa de lectura se estabilizan los rótulos y sigue avanzando la cámara. El informe expone `media` y, por escena, `hold_media.video_assets`, `hold_media.labels_settled`, `hold_media.image_changed` y las posiciones de los rótulos sobre el vídeo en `reading.hold_label_positions`. La verificación del MP4 compara con el original también los cuadros de una pausa con metraje.

Sobre medios locales, `caption-overlay` coloca el título en el margen inferior o superior según la posición vertical del punto focal. Puedes fijar `props.position` a `top`, `center` o `bottom`. Durante un puente compuesto sobre dos planos, el rótulo de identificación entrante aparece al completar la unión. Comprueba la trayectoria de una máscara respecto a ojos, boca, nombres y cifras. Una persiana o un iris que corta un rostro puede servir sobre un esquema y resultar incómodo durante una presentación personal.

En `chart-ring`, `value` es el porcentaje de la observación. Por ejemplo, `{"value":62.5,"label":"Ocupación del andén"}` mantiene «62,5 %» desde el primer cuadro. El arco y su punto guía recorren la fracción correspondiente. Así se puede leer la cifra durante el movimiento.

En una serie amplia, `data-chart` reparte las barras en grupos de dos o tres. `duration` determina cuánto tarda cada grupo y hay 0,25 s de lectura antes del siguiente. Con `focusHold`, el valor destacado ya está colocado cuando entran los demás. `dashboard-stack` también reserva ese tiempo al programar la siguiente tarjeta. El generador calcula la duración del plano con esos intervalos. Si estás montando una locución, usa los cuadros del informe para situar la frase que comenta el resultado.

En `dashboard-stack`, las tarjetas numéricas que comparten `unit` comparten escala y conservan sus celdas mientras entran las barras. Las unidades distintas forman grupos independientes. Un archivo gráfico aportado conserva su escala de origen. Para `chart-focus`, `props.box` localiza la región de interés y `props.padding` añade margen en fracciones de la altura del lienzo. El valor inicial, 0,055, deja espacio para la cifra y la categoría; usa 0 cuando el rectángulo de entrada ya incluya el margen necesario.

El generador comprueba la estructura, las series y los tiempos. Empieza cada artefacto medio segundo dentro de su entrada para que ya haya contenido al pasarle el cuadro. Mide encuadre, contraste y solapamiento del texto en los estados de lectura. Comprueba la altura de tinta a 390 px de ancho en la llamada de cierre y en la categoría y cifra seleccionadas de una gráfica. Con `focusHold`, vuelve a medir la posición de esas etiquetas durante la entrada. El informe registra los fotogramas inspeccionados.

Al exportar un MP4, se comprueba la paleta de las imágenes que entran al codificador. Después se decodifica el archivo y se cotejan el reloj, el número de imágenes y el contenido **de cada fotograma** con el estado dibujado para ese instante. El cotejo visual usa imágenes reducidas, error medio de color y error local por zona, con tolerancia a la compresión. La exportación reemplaza el destino cuando pasa las comprobaciones. El subcomando `verify` repite la comparación sobre un MP4 existente. Revisa además el significado del montaje y la lectura a su tamaño de uso.

### Elegir dónde mover el cuadro

Una unión ordinaria se resuelve con un corte. A partir de cuatro escenas el compilador puede escoger una transición para un cambio editorial reconocible. La configuración inicial admite un efecto por cada cuatro uniones completas, con margen para una transición deliberada en una pieza corta de varias escenas. Entre dos efectos exige al menos dos cortes y, por defecto, doce segundos desde el final del anterior. Puedes ajustar `joins_per_effect` y `min_gap_seconds`. Las elecciones explícitas se reservan primero. El informe `transition_audit.decisions` explica la decisión en cada unión.

Para revelar el contexto de una cifra en el mismo plano, usa `focusHold` en segundos y `highlightIndex` en `data-chart`. El valor y su categoría quedan fijos mientras entran las otras barras sobre la misma escala. Para ampliar la llamada final de un `disc-endcard`, usa por ejemplo `"detailScale":0.076`. El valor expresa el tamaño nominal de letra como fracción de la altura del artefacto.

El perfil de producción utiliza superficies blancas, grises sólidos y rojo `#9e1b32` para el foco. El contenido fotográfico conserva sus píxeles originales. En la galería puedes consultar el ritmo medido en la fuente. La API Canvas admite `mode:"reference"` para reproducir el fundido óptico de una referencia. El modo sólido resuelve ese relevo con una máscara opaca.

## Añadir una escena

Copia [motion.js](../assets/motion.js) junto a tu HTML. Este ejemplo funciona con un navegador y dos escenas dibujadas. Puedes sustituir cada función por un elemento `<img>`, un `<canvas>` o un `<video>` preparado en el instante correcto.

```html
<canvas id="film" width="1280" height="720"></canvas>
<script src="motion.js"></script>
<script>
  const ctx = document.querySelector("#film").getContext("2d");
  const M = LineWorldMotion;
  const theme = M.theme;
  const paint = color => (c, width, height) => {
    c.fillStyle = color;
    c.fillRect(0, 0, width, height);
  };
  function renderAt(seconds) {
    const options = {theme};
    M.transition(ctx, "iris-fill", (seconds - 2.5) / 2.2,
                 paint(theme.paper), paint(theme.quiet), options);
    M.artifact(ctx, "speaker-id", seconds - 4.7,
               {title:"Mara Vidal", detail:"Ingeniería de transporte\nProyecto Norte"}, options);
  }
  renderAt(7);
</script>
```

| Llamada | Qué recibe |
| --- | --- |
| `transition(ctx, id, progress, from, to, options)` | Progreso entre 0 y 1. Los valores fuera de ese intervalo se fijan en sus extremos. Cada plano es una fuente de imagen o una función `(ctx, ancho, alto)` que pinta una escena completa. |
| `artifact(ctx, id, seconds, props, options)` | Segundos desde que empieza el elemento. Un tiempo negativo permite programarlo para más tarde. Los rótulos y resaltados se dibujan sobre la escena que ya contiene el canvas. |
| `media(ctx, source, x, y, w, h)` | Encuadra la fuente dentro de un rectángulo. En imágenes y video conserva la relación de aspecto llenando el área y recorta el sobrante. |
| `transitions` y `artifacts` | Listas de identificadores que admite la versión instalada. |

Las opciones comunes incluyen `theme`, `width` y `height`. Las dimensiones predeterminadas son las del canvas. Puedes cambiar las propiedades del tema `accent`, `ink`, `paper`, `light`, `muted` y `font`. En las composiciones con texto introduce saltos de línea explícitos con `\n`. El detalle de un entrevistado admite dos líneas con entradas independientes. En `keypoint-list`, usa por ejemplo `{items:["Demanda","Capacidad","Frecuencia"], starts:[0,5.6,7.9]}` para ajustar cada entrada a una locución.

## Montar una entrevista

Carga también [sequences.js](../assets/sequences.js). La apertura acepta un sello, un título, un plano cercano, un plano abierto y los datos del entrevistado. El perfil sólido abre la cartela por iris, entrega el cuadro a la entrevista y mantiene el rótulo durante el cambio de cámara a los 12 s. El perfil de referencia conserva los tiempos medidos a 24 fps. El cierre acepta el último plano y el sello. [Apertura de referencia](https://www.youtube.com/watch?v=vb3k_OdYQs4&t=3s) · [Cierre de referencia](https://www.youtube.com/watch?v=vb3k_OdYQs4&t=74s)

```js
function renderAt(seconds) {
  const content = {mark, close, wide, title:"Dentro del proyecto", name:"Mara Vidal",
                   role:"Ingeniería de transporte\nProyecto Norte"};
  if (seconds < 15) LineWorldSequences.interviewOpen(ctx, seconds, content, {theme});
  else LineWorldSequences.interviewClose(ctx, seconds - 15, content, {theme});
}
```

Aquí `mark`, `close` y `wide` son tus propias fuentes. Usa un sello con fondo transparente si quieres ver el movimiento de las dos franjas hasta el último fotograma.

## Render determinista

La CLI de recetas decodifica clips con FFmpeg y entrega los cuadros por índice al lienzo. Para integrar manualmente la galería en otro capturador de 30 fps, llama a `renderAt(frame / 30)` antes de capturar cada fotograma. Si tu integración usa elementos `<video>`, espera al evento `seeked` y a que haya un cuadro disponible. Carga las imágenes y espera a `document.fonts.ready` antes de capturar. La galería admite una vista limpia como `demo.html?pattern=iris-fill&t=2&render=1` y expone `window.renderAt(seconds)` para el capturador.
