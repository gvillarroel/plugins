# Comentarios de edición por fotograma

Una nota de montaje tiene más contexto cuando señala el detalle al que se refiere. El visor de Line World toma esa idea de Huashu Motion y la aplica al MP4 entregado. Su código es local, usa la paleta del plugin y funciona al abrir un HTML junto al vídeo. [Huashu Motion, revisión señalada sobre la imagen](https://github.com/alchaincyf/huashu-motion/blob/0a6157d9cd7556347d67bf8f70ebde8a1594fc07/README.en.md)

Desde la raíz del proyecto de vídeo, sustituye la ruta del script por la de tu copia del plugin.

```sh
python ruta/al/plugin/skills/line-world-video/scripts/frame_notes.py build film.mp4 revisar.html --attention atencion.json --title "Revisión del montaje"
```

Abre `revisar.html`. Pausa durante la frase que quieres comprobar. Las flechas del teclado y los botones de un cuadro permiten localizar el cambio exacto. Pulsa el objeto o usa **Marcar centro**. Para un problema de ritmo, avanza hasta el último cuadro y pulsa **Hasta este cuadro**. Escribe qué debería poder leer, seguir u oír el espectador. **Guardar nota** la conserva en ese navegador y **Exportar notas** produce un JSON transportable.

Si el vídeo contiene una pista de subtítulos de texto, pulsa **Subtítulos** en los controles. La frase activa aparece en una franja debajo de la imagen, también durante las pausas y al avanzar un solo cuadro. El botón permite ocultarla. Abre **Subtítulos del vídeo** para recorrer la lista de frases. Cada frase lleva al milisegundo en que empieza y muestra el fotograma que se veía en ese instante. En un plano sostenido pueden oírse varias frases sobre la misma imagen. Las palabras aparecen bajo la imagen para poder comprobar a la vez la cifra, su unidad y el eje. El botón **Descargar WebVTT** conserva el texto y los milisegundos de la pista entregada. En películas con varias pistas, añade `--subtitle-language spa` al comando de creación para seleccionar la española.

### Comprobar los subtítulos sobre un gráfico

Para revisar el aspecto de los subtítulos superpuestos, el [script de comprobación](../scripts/review_caption_overlay.py) abre el MP4 en Chromium y dibuja una pista WebVTT con el texto y los tiempos extraídos. Compara dos capturas del mismo instante, con subtítulos y sin ellos. Mide el rectángulo pintado y los píxeles que cambian dentro de las zonas de lectura. Por defecto el vídeo ocupa su tamaño nativo. Con `--display-width 360` se mide en un reproductor de 360 píxeles CSS de ancho, a su proporción original. El informe conserva las dimensiones del archivo, las dimensiones en pantalla y la versión del navegador. Una pista legible en el lienzo de 1280 píxeles puede quedar encima de las cifras cuando se comparte el horizontal en un teléfono.

Guarda las zonas en un JSON. Por ejemplo, `[{"id":"unidad del eje","box":[0.65,0.81,0.29,0.07],"startMs":900,"endMs":4800}]` protege una etiqueta desde 0,9 hasta 4,8 s. Las cuatro coordenadas son izquierda, arriba, ancho y alto en fracciones del cuadro. Acota el rectángulo a la tinta o al objeto que necesitas leer.

```sh
python ruta/al/plugin/skills/line-world-video/scripts/review_caption_overlay.py film.mp4 --language spa --regions zonas.json --step-ms 500 --report subtitulos-pantalla.json --require-clear
```

El control toma muestras en cada intervalo donde coinciden el mismo texto y las mismas zonas. `--step-ms` permite acortar el intervalo entre ellas. El informe distingue el área cubierta y la tinta oscura que cambió. Un fondo dentro de un rectángulo amplio también puede generar intersección. Revisa el instante indicado en el visor y ajusta la posición del rótulo si queda oculto.

El selector ofrece los elementos visibles del plan cuya región contiene el punto. En una película sin plan se puede marcar cualquier zona. Cada nota lleva la huella del MP4, el cuadro inicial y final, las coordenadas normalizadas, el texto y la decisión. Cuando el plan declara las frases, el visor incluye la escena, la idea narrada y las referencias a esas frases.

Para recuperar el fotograma original y sus coordenadas en píxeles, ejecutar

```sh
python ruta/al/plugin/skills/line-world-video/scripts/frame_notes.py check film.mp4 notas.json --attention atencion.json --evidence revision
```

El comprobador usa los tiempos de presentación del MP4. Si una edición cambia el montaje, la huella identifica de qué versión proceden las observaciones. El director puede aplicar la nota en la receta, exportar la nueva versión y volver al mismo elemento durante la frase correspondiente.

### Revisar la misma nota después de editar

```sh
python ruta/al/plugin/skills/line-world-video/scripts/compare_frame_notes.py original.mp4 candidata.mp4 notas.json --before-plan atencion-original.json --after-plan atencion-candidata.json --out comparacion
```

Abre `comparacion/comparar.html`. Las imágenes provienen de ambos MP4 y el anillo señala una posición relativa al elemento en cada formato. El programa busca el tramo por escena, frase, foco, idea y tipo de movimiento. Conserva la posición del fotograma dentro de ese tramo aunque cambien los fps o la duración. Si se cambió el texto de la idea, se repitió el tramo o desapareció el objeto, deja la observación pendiente de localizar y devuelve código 2. En la carpeta quedan los fotogramas y el motivo.

Importa `notas-candidata.json` en el visor generado para el nuevo vídeo y reproduce el intervalo. Las marcas trasladadas conservan su identificador. El revisor comprueba si la nueva composición resolvió la observación escuchando la frase y mirando el detalle.
