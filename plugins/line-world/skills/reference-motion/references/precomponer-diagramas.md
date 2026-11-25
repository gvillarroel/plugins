# Precomponer un diagrama con Line World

Una precomposición reúne las figuras que explican una misma relación y les da un reloj local. La película decide cuándo aparece el grupo y cuánto espacio ocupa. El componente decide dónde están sus piezas y cómo se relacionan en cada instante. Así se puede colocar el mismo diagrama en dos momentos del montaje o volver a un fotograma concreto.

## Del concepto a las poses

En este ejemplo queremos que se entienda qué recibe la etapa de **Edición** de un artículo y qué entrega. La receta usa `module-transfer`. La tercera fila de un proceso de cinco etapas cruza desde el inventario hasta su ficha de detalle. El hueco identifica su origen mientras se leen las entradas y la salida. [Receta editable](../assets/precomposicion-ejemplo.json)

1. **Formula la pregunta visual.** ¿En qué parte del proceso se convierte el borrador en texto revisado? La identidad que debe seguir la mirada es «Edición».
2. **Coloca origen, destino y anclas.** El inventario de la derecha actúa como emisor. El panel de la izquierda recibe la fila y está visible desde el primer cuadro. Las otras cuatro filas sirven de ancla y conservan su posición. El nombre permanece unido a la pieza que viaja.
3. **Dibuja tres poses.** En la de partida, «Edición» ocupa su tercera fila. A medio camino, se distinguen la pieza en tránsito, el hueco y el destino. En la de llegada, el hueco sigue abierto y debajo de «Edición» caben «Borrador», «Guía de estilo» y «Texto revisado».
4. **Ordena las acciones según lo que explican.** Primero deja reconocer la fila. Después trasládala. Cuando llega, revela sus entradas y por último su salida. La pausa de lectura comienza con la pose final completa.

| Reloj local del ejemplo | Estado |
| --- | --- |
| 0–0,96 s | La etapa seleccionada se lee en su lugar original. |
| 0,96–3,12 s | Viajan juntos el fondo y el nombre de la fila. Los vecinos quedan fijos. |
| 3,12–6 s | La ficha recibe la fila. Las entradas empiezan a aparecer a los 3,30 s y la salida a los 4,26 s. |
| 6–10 s | La ficha conserva el resultado durante los cuatro segundos de `hold`. |

Los tiempos corresponden a `props.duration: 6`. El componente expresa el movimiento como una fracción de esa duración. Al duplicarla también se duplican los tiempos de las poses. `hold` se configura aparte en segundos. Para adaptar el ejemplo, cambia `labels`, el índice de la fila en `highlightIndex` y sus listas `inputs` y `outputs`.

## Poner el bloque en un reloj mayor

En una receta, cada entrada de `scenes` es una instancia con su propio contenido. El generador monta la lista en orden y calcula el inicio de cada escena. Usa un solo componente cuando el espectador necesite seguir una pieza entre posiciones, como ocurre con «Edición». Abre una segunda escena con un corte cuando cambie la pregunta, por ejemplo, para comparar el tiempo que tarda cada etapa. Para superponer dos elementos simultáneos se necesita un compositor que los dibuje en el mismo cuadro.

En un compositor Canvas, carga `motion.js` y `diagram-motion.js` desde `assets`. La función siguiente usa las dimensiones locales de la caja de destino y el reloj de la película. Se puede llamar después de dibujar el fondo de cada fotograma.

Para los nueve diagramas del [estudio de sistemas](bytebytego-study.md), carga también `assets/systems-motion.js`. La galería y el generador ya incluyen los tres archivos.

```js
function dibujarBloque(ctx, segundoPelicula, inicio, escena, caja) {
  const segundoLocal = segundoPelicula - inicio;
  const movimiento = escena.props.duration;
  if (segundoLocal < 0 || segundoLocal >= movimiento + escena.hold) return;

  ctx.save();
  try {
    ctx.translate(caja.x, caja.y);
    ctx.beginPath();
    ctx.rect(0, 0, caja.width, caja.height);
    ctx.clip();
    LineWorldMotion.artifact(
      ctx, escena.artifact, Math.min(segundoLocal, movimiento), escena.props,
      {width: caja.width, height: caja.height}
    );
  } finally {
    ctx.restore();
  }
}
```

Por ejemplo, con la receta de esta guía, `inicio = 12` y una caja de 960 × 540, el segundo 14 del montaje muestra el segundo 2 del traslado. Del segundo 18 al 22 se sostiene la llegada. Al reproducir hacia atrás se vuelve a calcular la pose a partir del mismo instante.

Los diez diagramas del estudio pintan un fondo opaco dentro de su caja. Su MP4 sirve como plano completo o como recuadro sobre una película. Para componer objetos sueltos sobre metraje con transparencia real, prepara esos objetos como SVG con fondo transparente y asigna sus límites, puertos y orden de dibujo al compositor. Si el texto ha de ocupar parte del plano exterior, reserva ese espacio al colocar la caja. [Contrato de interacción entre elementos](../../video/references/scene-interaction-contract.md)

## Renderizar y revisar

Desde el directorio de la skill `reference-motion`, ejecuta el generador con la receta incluida. Cambia `proyecto` por el directorio donde quieres la película.

```sh
uv run --script scripts/generate_motion.py render assets/precomposicion-ejemplo.json proyecto/edicion.mp4
uv run --script scripts/generate_motion.py verify assets/precomposicion-ejemplo.json proyecto/edicion.mp4 --report proyecto/edicion.verificada.json
```

La receta produce 240 fotogramas a 24 fps en 1280 × 720. Revisa los fotogramas 0, 48 y 239. El primero presenta el inventario, el segundo permite reconocer la fila y su hueco durante el viaje, y el último permite leer qué recibe y qué entrega. Para otro diagrama conserva esas tres preguntas de revisión y sitúa los controles en sus propios instantes. [Catálogo de relaciones y parámetros](usage.md#diagramas-de-estructura-y-ejecución) · [Diez ejemplos con instantes de referencia](typegpu-study.md)
