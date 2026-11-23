---
name: line-world-motion-direction
description: Direct an explanatory Line World sequence around one persistent subject. Use it when a transfer, a measured trajectory or a two-value comparison should unfold in coordinated beats with an editable frame clock.
---

# Dirección de movimiento

Escribe qué debe entender el espectador al final y elige el sujeto al que seguirá. En este productor el sujeto permanece identificado en la misma posición durante toda la secuencia. La composición reserva la otra zona de pantalla para demostrar el cambio.

Para explicar dos medidas con voz en español, empieza por el [brief de comparación](references/brief-to-video.md). El productor convierte los datos en barras a escala, valida las unidades y muestra el guion definitivo con `--validate-only`. La misma entrada genera el vídeo horizontal o vertical.

1. Parte de la [receta editable](assets/solicitud.json). Sustituye los tiempos y valores simulados por los de la pieza; documenta su procedencia en `source`. Elige `transfer` para seguir un objeto entre dos lugares, `trace` para leer una medición por etapas y `compare` para contrastar dos magnitudes de la misma unidad.
2. Dirige cada plano en fotogramas enteros. `cue` deja reconocer la composición, `move` desarrolla la acción y `hold` deja leer el resultado. Dos acciones muestran la relación. Un `note` opcional revela una tercera observación al final del movimiento. Cambia la duración de cada plano de acuerdo con lo que haya que leer.
3. Ejecuta el [productor](scripts/direction.py). Genera un MP4 silencioso, un informe JSON y una hoja de fotogramas tomados del vídeo decodificado. El sonido y la locución se incorporan en el montaje general.

```powershell
uv run --python 3.13 scripts/direction.py assets/solicitud.json -o salida/explicacion.mp4
```

La receta admite formato horizontal, cuadrado y vertical. El formato vertical lleva la identificación del sujeto a la parte superior. El productor utiliza la paleta y la tipografía del plugin. Conserva la receta con el vídeo para poder cambiar contenido y duración. Revisa las etiquetas sobre la hoja y en el formato de entrega.

Con locución ya grabada, usa el [adaptador de partitura](scripts/narrated.py). El [circuito narrado](assets/circuito-narrado.json) ancla los movimientos a las muestras de una frase y de un efecto. Para reproducir casos con datos firmados, ceros, textos largos y formatos de 390 a 1920 píxeles, ejecuta [la matriz de pruebas](scripts/audit_briefs.py).

Consulta el [contrato de la receta](references/recipe.md) para sincronizarla con el montaje y la [procedencia de las técnicas](references/provenance.md) para conocer el alcance de la adaptación.
