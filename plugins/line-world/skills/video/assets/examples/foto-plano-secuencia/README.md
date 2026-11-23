# Una fotografía, un plano y una secuencia

Este ejemplo mudo dura nueve segundos. El retrato de Eileen Collins invita a mirar un detalle fijo. El plano de la flor muestra la apertura de los pétalos. Al final se ven seis imágenes del mismo plano, separadas por medio segundo. La barra inferior sigue el tiempo de lectura a lo largo de las tres escenas.

El retrato es de la NASA. El vídeo procede de la colección CC0 de ejemplos de MDN. El generador comprueba ambos originales y escribe su procedencia y sus huellas en `fuentes.json`. El GIF conserva el orden del plano. La barra es un SVG y el texto se ajusta en un documento HTML local. [Retrato](https://scikit-image.org/docs/0.20.x/api/skimage.data.html#skimage.data.astronaut) · [Metraje](https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4)

Desde la raíz del plugin, con FFmpeg, FFprobe y uv en el PATH, ejecutar

```sh
uv run --script skills/reference-motion/scripts/review_catalogue.py fetch-media --media-dir produccion/media
uv run --script skills/video/assets/examples/foto-plano-secuencia/generar.py --media-dir produccion/media --out produccion/horizontal
uv run --script skills/video/assets/examples/foto-plano-secuencia/verificar.py produccion/horizontal
uv run --script skills/video/assets/examples/foto-plano-secuencia/generar.py --media-dir produccion/media --out produccion/vertical --portrait
uv run --script skills/video/assets/examples/foto-plano-secuencia/verificar.py produccion/vertical
```

El proyecto contiene el contrato editable `escena.json`, sus medios, la composición HTML y el archivo `ejemplo.mp4`. El verificador compara diez instantes del MP4 con los originales, comprueba la escala del retrato, el avance del metraje, los seis cuadros del GIF, el color del margen y la legibilidad del bloque de texto. Al volver de la secuencia a un instante anterior del plano, también compara dos capturas del navegador.

El compositor acepta `playback.offsetSeconds` en GIF y vídeo. Los segundos se suman al reloj maestro. Durante el intervalo visible del plano, 3,00–6,00 s, un desfase de −1,25 s empieza en 1,75 s del original. El GIF utiliza −6,00 s para empezar con su primer cuadro al entrar en pantalla. En un visor HTTP, el servidor debe ofrecer rangos de bytes para que el reproductor pueda recuperar el fotograma solicitado. El renderizador incluido los ofrece.
