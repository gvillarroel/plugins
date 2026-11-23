# Sonido de una imagen o un gráfico

Escoge el fotograma que transmite información al espectador. Una pala que llega al contacto tiene un instante físico claro. La aparición inicial de una cifra puede llevar un único pulso. En un diagrama continuo, la pausa de la voz suele bastar para separar dos capítulos.

Cuando intervienen dos personas, prepara una toma por turno y conserva sus nombres en la cronología. Para un sonido que separa una pregunta de su respuesta, comprueba cuánto dura la señal real después de ajustar el nivel y cuánto espacio queda hasta la primera palabra. En una prueba con un paso de página, el catálogo anunció 1,145 s y la toma generada con su semilla duró 1,782 s. La cola se metía en la siguiente frase hasta que se amplió su margen inicial. El productor puede entregar tanto el SRT literal como uno con identificadores de hablante. [Turnos con varias personas](../../media-use/audio/references/scene-audio.md#turnos-con-varias-personas)

1. Parte de una narración medida. El productor usa los archivos de voz y comprueba sus hashes antes de situarlos en su posición original. Admite el `timeline.json` de `scene_audio.py` y el formato de voces originales del ejemplo semanal. Para este último se pasa el directorio de voces con `--voices`.
2. Copia la [receta de contacto y capítulo](../assets/examples/circuito.json) o la [receta de entrada de un dato](../assets/examples/dato.json). En `cues`, cada fila declara un diseño Earshot, su semilla, el fotograma, el nivel del efecto y la decisión `play` o `silence`. `reason` explica qué se oye y `silence` describe cómo la imagen o la voz explican lo mismo en silencio.
3. Decide si el fotograma coincide con el comienzo audible (`onset`) o con el pico del efecto (`peak`). El primero se mide a −50 dBFS después de ajustar el nivel de la toma. `offset_ms` permite anticipar o retrasar el ancla hasta medio fotograma. FPS admite enteros o fracciones como `"30000/1001"`. El fotograma inicial es 0. Un rectángulo `roi` opcional delimita la prueba de imagen en píxeles mediante izquierda, arriba, derecha y abajo.
4. Declara la frase de voz desde 1 en `protect_sentence` y un término literal en `term`. Cuando el efecto alcanza −50 dBFS dentro de esa frase, el modo de edición pide ajustar el tiempo, reducir el nivel o marcar silencio. La frase completa proporciona un margen conservador cuando la narración carece de marcas por palabra.
5. Ejecuta el productor con Python, NumPy, FFmpeg, FFprobe y el CLI de Earshot. El generador de tomas usa el catálogo local. Las grabaciones de voz suministradas permiten ejecutar la mezcla sin sintetizar la narración de nuevo. Utiliza un directorio de salida propio para cada variante.

Para reproducir la mezcla desde el plugin instalado, genera primero el [circuito narrado](../../line-world-video/assets/examples/narrated-circuit/README.md). En la misma sesión de PowerShell, desde la carpeta de ese proyecto y con `$plugin` apuntando a la instalación, ejecuta:

```powershell
uv run --with numpy python "$plugin/skills/line-world-sound/scripts/score_picture.py" "$plugin/skills/line-world-sound/assets/examples/circuito.json" --timeline audio/timeline.json --video circuito/circuito.mp4 --out sonido-circuito
```

`mezcla.wav` y `solo-voz.wav` son los dos lados de la comparación. `--mode silence` conserva la narración sola. `--mode audition` activa también los efectos marcados como silenciosos para escucharlos en contexto. El modo de audición permite probar interferencias con la frase y sonidos sin cambio visual. Usa `--mode edit` para validar la versión elegida.

El informe `qa.json` recoge digestos, niveles, fotogramas, muestras del evento y correlación con cada frase protegida. Con `--video`, verifica la cadencia del MP4, mide qué fracción del rectángulo cambia entre los dos cuadros, multiplexa y decodifica una copia temporal con AAC-LC de 192 kbit/s y repite la prueba de sincronía y voz. La referencia mantiene la cadencia constante indicada por la receta. El medidor comprueba que se conserve margen antes de saturar. La coincidencia de dos ondas aporta evidencia sobre el enmascaramiento. La comprensión del mensaje por parte de una audiencia requiere una escucha contextual.

Para escuchar los archivos con Earshot, genera las tomas en una sola llamada a `make --spec`, examina cada diseño con `describe`, utiliza `timeline` en torno al evento y compara `solo-voz.wav` y `mezcla.wav` con `ab`. Revisa también el cambio real de imagen. En el circuito, el capítulo 199 conserva la misma imagen en dos cuadros consecutivos.
