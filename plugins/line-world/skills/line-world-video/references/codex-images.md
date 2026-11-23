# Imágenes generadas con Codex en una película Line World

Elige el recurso según lo que el espectador necesita reconocer.

| Pregunta del plano | Recurso de producción |
| --- | --- |
| ¿Qué aspecto podría tener un objeto genérico, una escena imaginada o una analogía? | Genera una ilustración editorial con ImageGen. Puedes pedir una bobina de demostración genérica, una sección de terreno imaginaria o una herramienta sin marca. |
| ¿Qué persona, producto, lugar o acontecimiento concreto estamos identificando? | Usa una fotografía documental cuya identidad y procedencia estén verificadas. Identifica un retrato oficial con el nombre y el cargo correctos. Lleva cualquier recreación en una escena rotulada como tal. Consulta [fotografías documentales](documentary-images.md). |
| ¿Cuánto cambió un índice, dónde está una conexión, cómo gira una pieza o qué dice una cita? | Dibuja la serie de datos, el esquema, los estados y el texto por código. Usa los valores originales y conserva una escala coherente. Una ilustración puede acompañar la explicación. |

## Generar o editar

1. Para una imagen nueva, usa la herramienta nativa ImageGen con el sujeto, el propósito y el encuadre. Describe el área que ocupará en la película, las partes que deben verse completas, la dirección de la mirada o las conexiones importantes. Pide el dibujo sin tipografía si vas a añadir rótulos.
2. Para cambiar algo concreto en una imagen existente, inspecciona el archivo original y pásalo como referencia de edición a la herramienta nativa. Especifica el cambio y qué rasgos o proporciones debe preservar. Guarda la salida con otro nombre y registra tanto el original como la edición.
3. Para un recorte compuesto sobre el fondo del vídeo, solicita fondo transparente y activa `transparent_background:true` en la generación o edición nativa. Comprueba el canal alfa al guardar. Una imagen RGB con damero dibujado sigue siendo opaca. Un PNG RGBA puede tener todos sus píxeles opacos.
4. Conserva el bitmap original en el proyecto y guarda literalmente el prompt enviado. Registra la operación, el ID comunicado por ImageGen, el propósito y las referencias de edición. El hash identifica los bytes usados en el montaje. Para regenerar los mismos fotogramas, usa ese archivo conservado. Otra ejecución del prompt puede dibujar una variante.

Un prompt de producción para la bobina especificó una sola pieza, dos terminales visibles, el hueco reconocible a 390 px, margen alrededor y una vista de tres cuartos. El rótulo y el diagrama del campo se compusieron después en la película.

Para un recorte con asa o aberturas, revisa el archivo compuesto sobre blanco
y sobre el color de destino. Inspecciona el perímetro y los huecos para
detectar fondo residual, halos o bordes comidos. Si el resultado no sirve
como recorte, registra el diagnóstico y reintenta con ImageGen o conserva
una lámina enmarcada. Una jarra sin graduaciones puede ilustrar la idea
de medir. El diagrama, sus unidades y las cantidades del ejemplo deben
proceder de los datos o escribirse por código.

## Encuadre y atención

Sitúa el punto focal en la parte que explica la frase, aunque el centro geométrico esté en otro lugar. Usa `contain` para conservar salientes y terminales. Usa `cover` y `focal:[x,y]` si el objeto admite recorte. Una mirada, un eje o un cable pueden dirigir la atención al siguiente elemento. Mantén el rótulo en su propia superficie si taparía el detalle. Revisa el plano a tamaño de teléfono, al inicio del rótulo y cuando termina su tiempo de lectura.

En el ejemplo, el PNG original es RGB de 1536 × 1024. Se midieron **34 colores distintos en el borde** y el tono más frecuente solo ocupa el 19,37 % del perímetro. El ligero grano y el blanco cálido se ven al lado de la paleta del vídeo. La receta coloca el original entero dentro de una lámina a la derecha y genera por código la columna blanca de lectura. A los tres segundos, el 100 % de los píxeles en la zona de margen comprobada quedó a un máximo de tres niveles RGB de blanco. Los terminales se ven completos. El segundo plano dibuja las relaciones del campo sin reutilizar el bitmap.

## Registro y comprobación

Desde la raíz del repositorio, registra un original nuevo junto al prompt.

```sh
uv run plugins/line-world/skills/line-world-video/scripts/codex_image_asset.py record proyecto/bobina.png proyecto/prompt.txt proyecto/procedencia.json --generation-id ID_DE_LA_HERRAMIENTA --purpose "Ilustrar la forma de una bobina" --alpha opaque
```

Para una edición añade `--operation edit --reference proyecto/original.png`.
Para transparencia real usa `--alpha cutout`. El comando comprueba que
haya píxeles transparentes y visibles antes de registrar el archivo.
`verify` informa el alfa máximo, la caja visible, el porcentaje del
perímetro transparente y la fracción de píxeles visibles con alfa de
250 a 255. Para una superficie casi opaca, puedes declarar un mínimo
con `--min-near-opaque 0.96`. Deja el umbral sin especificar para vidrio,
humo o transparencias expresivas. La herramienta conserva los bytes
originales y verifica su integridad local.

Para usar el bitmap original en el generador, declara el asset y enlázalo en una escena. El fondo, los rótulos, la animación y los tiempos de lectura son parte de la receta.

```json
{
  "version": 1,
  "assets": {"bobina": {"path": "bobina.png", "fit": "contain", "focal": [0.5, 0.52]}},
  "scenes": [{
    "id": "alambre",
    "artifact": "editorial-split",
    "props": {"title": "Una bobina", "detail": "La corriente recorre las espiras.", "share": 0.55, "media": "bobina"},
    "hold": 4
  }]
}
```

El ejemplo ejecutado vive en `output/line-world-lab/imagen-codex/`. Su registro amplía los datos de origen con `recipe`, `asset_id` y dos comprobaciones de píxeles en el MP4, una para el fondo y otra para la presencia de la bobina. Cada comprobación identifica un fotograma de índice cero, un rectángulo normalizado `[izquierda,arriba,derecha,abajo]`, un RGB, la tolerancia por canal y la fracción mínima de píxeles que debe cumplirla.

```sh
uv run plugins/line-world/skills/reference-motion/scripts/generate_motion.py render output/line-world-lab/imagen-codex/receta.json output/line-world-lab/imagen-codex/bobina-en-contexto.mp4 --report output/line-world-lab/imagen-codex/pelicula.qa.json
uv run plugins/line-world/skills/line-world-video/scripts/codex_image_asset.py verify output/line-world-lab/imagen-codex/procedencia.json --movie output/line-world-lab/imagen-codex/bobina-en-contexto.mp4 --report output/line-world-lab/imagen-codex/imagen.qa.json
```

Para una escena HTML o SVG en el compositor narrado, lista el PNG original
en `assets` y úsalo en la escena. Añade `composition_report` al registro
con la ruta relativa al recibo de `compose_narrated.py`. El verificador
comprueba la huella del MP4 publicado y la ruta y huella del PNG en el
recibo. Completa la evidencia con `movie_samples` en cada formato, por
ejemplo margen blanco, hueco del asa y superficie cerámica. Usa otras
muestras para los valores o estados dibujados por código.
