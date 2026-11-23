# De un brief a un vídeo de comparación

Edita el [brief de un recorrido](../assets/recorrido-brief.json) o el [brief de dos jarras](../assets/jarras-brief.json). El productor crea dos capítulos con las mismas dos filas. Las barras se desarrollan al presentar las medidas. Cuando empieza la conclusión, el título cambia y las posiciones finales permanecen fijas. Un editor o un modelo puede usar el [esquema JSON](../assets/comparison-brief.schema.json) para generar los campos.

Para generar también el guion, basta con las dos medidas, el sujeto y la fuente. En el [ejemplo del Tesoro a diez años](../assets/tasa-brief.json), las tasas de 5,15 % y 4,92 % producen la lectura «0,23 puntos porcentuales menos». El productor calcula cuál de las dos cifras es mayor y reconoce un empate. Puedes editar después los títulos y las frases de voz.

| Campo | Qué se edita |
|---|---|
| `subject`, `subjectLabel`, `title` | El sujeto permanente, su etiqueta opcional y el título opcional de la comparación. El título predeterminado reúne las dos etiquetas. Usa `{a}`, `{b}` o `{gap}` en el título si incluye medidas que pueden cambiar. |
| `source` | `type: simulated` y una descripción breve para pruebas. Con `type: observed`, añade en `citation` el documento, enlace o registro de origen. `detail` es el crédito que aparece en pantalla en ambos capítulos. |
| `measures` | Dos objetos con `label`, número finito `value` y la misma `unit`. La primera observación aparece en gris y la segunda en granate. La escala lineal contiene el cero. |
| `spokenUnit` | Unidad pronunciada, por ejemplo «minutos» para la etiqueta «min». Las unidades comunes de tiempo, longitud, capacidad, masa, temperatura y moneda concuerdan con la cifra, como «1 minuto», «0,99 euros» y «menos 1 grado Celsius». Los símbolos y las unidades personalizadas conservan su grafía. Los subtítulos mantienen junta cada medida que cabe en una línea. |
| `takeaway` | Conclusión opcional. `{gap}` expresa la diferencia absoluta. Si las medidas están en `%`, el resultado se expresa en puntos porcentuales. |
| `narration` | Dos textos opcionales para personalizar la locución. El primero usa `{a}` y `{b}` para leer ambas medidas. El segundo interpreta el resultado. Cualquiera de los textos admite `{gap}`. El autor elige el sentido de palabras como «ahorra», «pierde» o «más». |
| `recordings` | Opcional. Dos rutas relativas a archivos WAV, uno por capítulo, con las frases indicadas. Con grabaciones hay que proporcionar en `narration` la transcripción de ambas tomas. |

## Un comando

Usa rutas completas para ejecutar el productor desde cualquier directorio. Deja los números en el JSON como `0.6` o `18`. El generador formatea la coma decimal en la pantalla y el texto de la locución.

Los rótulos conservan los decimales que distinguen las medidas. Por ejemplo, `3.001` y `3.002` con unidad `%` producen «3,001 %», «3,002 %» y una diferencia de «0,001 puntos porcentuales». A esa escala las barras pueden terminar en el mismo píxel, por lo que ambas filas siguen mostrando su cifra. Los ceros finales de escritura se omiten. Si un literal perdería cifras al convertirlo para la escala, la previsualización identifica el número. Para expresar una diferencia diminuta respecto a un nivel común, puedes documentar ese nivel en el brief y dar las dos diferencias en una unidad adecuada.

```powershell
uv run --script /ruta/al/plugin/skills/line-world-motion-direction/scripts/brief_to_video.py /ruta/al/brief.json --validate-only --format vertical
uv run --script /ruta/al/plugin/skills/line-world-motion-direction/scripts/brief_to_video.py /ruta/al/brief.json --out /ruta/a/entrega --format vertical
```

El primer comando comprueba unidades, fuentes, sustitución de cifras y composición para el tamaño elegido. Devuelve el título, las palabras que se oirán y los saltos de línea previstos para cada subtítulo en `captionBlocks`. Los tiempos los fija después la locución. Puedes comprobar la lectura antes de sintetizar la voz o abrir un navegador.

El formato vertical tiene 390 × 844 píxeles y el horizontal, 960 × 540. Ambos usan 24 fps. `uv` resuelve las dependencias de Python del productor. También puedes ejecutarlo con un Python 3.11 o posterior que tenga instalados Pillow, NumPy, Playwright y PyAV. Para exportar, instala FFmpeg y FFprobe en PATH. Usa un navegador Chromium de Playwright o selecciona Edge instalado mediante `--browser msedge`. Si necesitas instalar Chromium, ejecuta `uv run --with "playwright>=1.51,<2" python -m playwright install chromium`.

Piper busca la voz mexicana `es_MX-claude-high` en su caché. La primera síntesis descarga y verifica los archivos que falten. Un modelo personalizado se indica con `--model /ruta/voz.onnx` y su fichero contiguo `.onnx.json`. Para trabajar sin conexión, prepara las dependencias y la voz y pasa `--offline` al productor y a `uv run`. Con dos grabaciones WAV, el productor usa directamente las tomas.

En `--out` se guardan el MP4 con capítulos, voz y subtítulos de español, la pista WAV, el SRT recuperado del contenedor, el brief original, la dirección con sus tiempos, una imagen de ambos capítulos y la verificación. Los cuadros intermedios se preparan en un directorio temporal. `--replace` permite actualizar una entrega creada por este productor cuyos archivos conservan sus SHA-256. Un error de locución, composición o control de calidad deja la entrega previa disponible. La estimación de espacio incluye una reserva de 8 MiB configurable con `--reserve-mib`.

## Qué se comprueba

El reloj de la voz determina el movimiento y las pausas. El compositor revisa los focos cada segundo y mide el número de regiones que cambian en el H.264. Comprueba los dos capítulos, el AAC frente al máster y las palabras y fronteras de cada frase de subtítulos. En móvil, las líneas de subtítulo tienen hasta 32 caracteres; en horizontal, hasta 42. Si una frase necesita varios subtítulos, sus divisiones interiores se estiman en proporción al texto dentro del intervalo de voz medido.

El verificador coteja en el MP4 las etiquetas, las cifras, el título y la procedencia con el recorte dibujado por el productor. Mide la estabilidad entre los cuadros inicial y final de cada pausa y el interior de las barras en los cuadros de lectura. Las etiquetas de las filas y las unidades proceden de los mismos datos que la locución. En el modo WAV, el texto declarado por el autor se usa como transcripción.

Al cambiar el trazado, ejecuta `python scripts/audit_comparisons.py --cases 30 --seed 47 --report medidas.json` desde esta skill. La prueba mide los extremos de las barras en píxeles, su dirección a lo largo de cinco instantes, la marca de cero, el signo en el guion, los cortes del subtítulo y la estabilidad durante la lectura. Cubre cruces por cero, empates y órdenes de magnitud distintos en horizontal y vertical. El informe identifica la semilla y conserva las primeras entradas que fallan para reproducirlas.
