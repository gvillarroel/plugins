# Narración y mezcla local por escenas

Este ejemplo genera el clic de un interruptor con Earshot y dos escenas narradas. Requiere uv, FFmpeg y el ejecutable `earshot` en PATH. Piper descarga el modelo seleccionado la primera vez, verifica su SHA-256 y lo reutiliza localmente.

Abre PowerShell en la carpeta instalada de Line World que contiene `plugin.json` y `skills/`. Guarda esa ruta y selecciona una carpeta de proyecto donde escribir la mezcla:

```powershell
$plugin = (Get-Location).Path
$proyecto = Join-Path $HOME 'line-world-projects/audio-por-escenas'
New-Item -ItemType Directory -Path $proyecto -Force | Out-Null
Set-Location -LiteralPath $proyecto
uv run --python 3.13 --script "$plugin/skills/media-use/audio/scripts/scene_audio.py" "$plugin/skills/media-use/audio/assets/examples/circuito.json" --out audio
```

### Entrada

La receta JSON usa un array ordenado `scenes`. Cada escena incluye un `id` único en minúsculas y su transcripción `text`. Las rutas de entrada se resuelven respecto a la receta.

| Opción | Significado |
| --- | --- |
| `voice` | `es_MX-claude-high` por defecto, o `es_AR-daniela-high`. El recibo conserva la ficha del modelo y la licencia declarada para sus datos. Para cualquier otro idioma o locutor, usa `--model modelo.onnx` con su `.onnx.json` junto a él. |
| `preset` | `neutral`, `deliberate` o `brisk`. Controlan la velocidad de fonemas y la pausa entre oraciones. |
| `seed`, `pronunciations` | Semilla entera por proyecto y diccionario opcional, por ejemplo `{"Nasdaq":"Násdac"}`. Los subtítulos conservan la grafía original. |
| `target_lufs` | Sonoridad integrada del máster mono. Valor inicial de −18 LUFS. |
| `caption_layout` | `sentences` entrega una entrada SRT por frase. `es-lectura` divide la pista española en bloques de lectura y guarda en `timeline.json` la procedencia de sus tiempos. La pista opcional con nombres de hablantes conserva las frases y etiquetas originales. |
| `lead_s`, `tail_s`, `duration_s` de escena | Margen inicial y final, por defecto 0,22 y 0,45 s. Una duración explícita fija el límite de la escena. La CLI detecta textos o efectos que excedan ese límite. |
| `file`, `marks` de escena | Importa una grabación local admitida por FFmpeg. `marks` acepta frases con `text,start_s,end_s` relativos al inicio de la grabación. Sin marcas se subtitula el bloque completo. Cuando todas las voces proceden de archivos se omite la carga de modelos. |
| `effects` de escena | Cada señal emplea `sound`, ID exacto de `earshot sounds`, y `want` opcional, o bien un `file` aportado. `at_s` marca el instante desde el inicio de la escena. `at_sentence` sitúa el efecto al inicio de una frase, numerada desde 1. `peak_dbfs` fija el pico del efecto después de mezclar a mono, inicialmente −24 dBFS. |

### Salida y sincronización

`master.wav` es PCM de 16 bits, mono, a 48 kHz. `timeline.json` contiene las huellas de voz, las pistas en `voices/`, los efectos en `effects/` y los resultados de medición. `captions.srt` usa tiempos absolutos. El máster se comprueba con FFmpeg mediante EBU R128, con tolerancia de 1 LU y techo de −1,5 dBTP. Para efectos cortos, Earshot registra pico verdadero, muestras recortadas y duración del diseño antes de ajustar su volumen.

Los cortes se expresan en muestras, con `start_sample` inclusivo y `end_sample` exclusivo. `master.samples` indica el total. En cada frase, `start_s` y `end_s` son relativos a la escena y `absolute_start_sample` y `absolute_end_sample` permiten sincronización directa. Para una exportación a vídeo, redondea cada límite interior una sola vez y usa el techo para el último cuadro. Conviene usar una carpeta de generación dedicada.

Para obtener la misma partición sobre un máster existente, ejecuta desde la misma carpeta:

```powershell
uv run --python 3.13 "$plugin/skills/media-use/audio/scripts/spanish_captions.py" audio/timeline.json --out pista-nueva
```

Este comando verifica el WAV, crea un SRT en un directorio nuevo y escribe los límites de cada bloque en `cortes-subtitulos.json`. Admite `--words marcas.json` asociadas al SHA-256 de ese máster. Un corte interior sin marcas alineadas lleva `estimated`. El comando usa la biblioteca estándar de Python 3.11 o posterior.

### Turnos con varias personas

Usa un identificador estable para cada intervención y declara los hablantes en `speakers`. El nombre es una etiqueta editorial. Cada voz sintetizada se selecciona primero en la escena, luego en su hablante y después en la configuración global. En cada nivel puedes dar un `voice` de la tabla anterior o un archivo local `model`, acompañado de su configuración. El productor carga cada voz utilizada una vez por ejecución. El `preset` sigue la misma precedencia y solo regula ritmo y pausas.

```json
{
  "speaker_captions": true,
  "speakers": {
    "leo": {"name": "Leo", "voice": "es_MX-claude-high"},
    "ines": {"name": "Inés"}
  },
  "scenes": [
    {"id": "pregunta", "speaker": "leo", "text": "¿Qué cambia al cerrar el interruptor?"},
    {"id": "respuesta", "speaker": "ines", "text": "La corriente empieza a circular.",
     "file": "tomas/respuesta.wav", "lead_s": 0.4}
  ]
}
```

Coloca una grabación de la respuesta en la ruta indicada, o asigna a Inés su propio modelo y omite el campo `file`. Cuando existe `file`, se usa directamente la toma aunque el hablante también tenga una voz Piper configurada. Conserva el origen y la autorización de las grabaciones en el proyecto. Los dos identificadores de hablante pueden referirse al mismo modelo. Si el guion requiere voces distinguibles, verifica dos fuentes realmente distintas.

Para mantener el procesamiento local agrega `--offline`. Con los modelos requeridos en caché o todos los turnos importados funciona sin red. Las recetas anteriores de una sola voz siguen emitiendo los mismos archivos. El modo opcional `speaker_captions` añade `captions-speakers.srt` con etiquetas como `[Inés]`; `captions.srt` conserva solo las palabras pronunciadas para el compositor. Los dos SRT usan los mismos tiempos. La cronología incluye el nombre por escena, la huella de cada entrada y, cuando corresponde, los datos del modelo que la sintetizó.

Para retocar una intervención conservando las tomas aceptadas, usa archivos WAV originales y sus marcas como entradas. Modifica solo el texto y el WAV de la intervención elegida, mantén su ID y vuelve a ejecutar la receta. Comprueba que los hashes de los otros stems coincidan y que sus tiempos absolutos se hayan desplazado lo que corresponde a la nueva duración. El máster vuelve a medirse en conjunto.
