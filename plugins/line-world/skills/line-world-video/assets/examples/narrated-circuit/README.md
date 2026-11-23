# Circuito narrado

La pieza conserva un esquema de corriente continua y una vista de la misma bobina durante sus dos capítulos. La placa larga de la pila es el polo positivo. El interruptor cierra la rama superior. Las flechas muestran el sentido convencional de la corriente. Una línea de campo pasa por el centro de la bobina y se cierra por fuera.

## Reproducir desde el plugin instalado

Abre PowerShell en la carpeta instalada de Line World que contiene `plugin.json` y `skills/`. El primer comando guarda esa ruta. Los siguientes crean una carpeta de trabajo, sintetizan la voz y el clic con la [receta de audio del circuito](../../../../media-use/audio/assets/examples/circuito.json) y generan el vídeo. Necesitas uv, Earshot, FFmpeg, FFprobe y Chromium o Edge. Piper descarga la voz española la primera vez y comprueba su huella.

```powershell
$plugin = (Get-Location).Path
$proyecto = Join-Path $HOME 'line-world-projects/circuito-narrado'
New-Item -ItemType Directory -Path $proyecto -Force | Out-Null
Set-Location -LiteralPath $proyecto
uv run --python 3.13 --script "$plugin/skills/media-use/audio/scripts/scene_audio.py" "$plugin/skills/media-use/audio/assets/examples/circuito.json" --out audio
uv run --script "$plugin/skills/line-world-video/assets/examples/narrated-circuit/generar.py" --audio audio --out circuito
```

La carpeta `audio` contiene `timeline.json`, `master.wav` y `captions.srt`. La película queda en `circuito/circuito.mp4`.

El argumento `--browser msedge` permite usar Edge en Windows. Con `--preflight-only`, se generan la escena, el reloj, las capturas de fuente y la revisión previa. El render completo invoca los dos programas del plugin y comprueba también el audio AAC y los fotogramas decodificados.

```powershell
uv run --script "$plugin/skills/line-world-video/scripts/review_attention.py" pre-render circuito/atencion.json --audio-timeline audio/timeline.json --report circuito/pre-render.json
uv run --script "$plugin/skills/line-world-video/scripts/compose_narrated.py" circuito/proyecto.json --output circuito/circuito.mp4 --report circuito/composicion.json
uv run --script "$plugin/skills/line-world-video/scripts/review_attention.py" post-export circuito/atencion.json --audio-timeline audio/timeline.json --video circuito/circuito.mp4 --report circuito/post-export.json
```

## Qué se mueve

| Frase de la voz | Evidencia visual |
|---|---|
| «Al cerrar el interruptor, se completa el circuito» | La palanca cierra el único hueco. La marca vertical junto al contacto se contrae con él. |
| «La corriente puede circular» | Dos flechas recorren los conductores superior e inferior en el sentido de la corriente convencional. |
| «Al pasar por la bobina, la corriente crea un campo magnético» | Un marcador recorre el símbolo de la bobina mientras aparece el énfasis sobre una línea cerrada del campo. |
| «Si abrimos el interruptor, la corriente se detiene» | La palanca se separa, la flecha superior sale del conductor y desaparece la representación del campo. El circuito permanece abierto al final. |

El tiempo del movimiento sirve para seguir la explicación. La geometría ilustra la corriente continua antes de abrir y su estado final después del transitorio. El ejemplo carece de escalas de intensidad, tensión, tiempo de descarga y campo.

## Archivos de revisión

`fuente.json` registra la posición del interruptor, el foco segundo a segundo y el transitorio del máster. `post-export.json` conserva la inspección de todas las imágenes codificadas. `verificacion-mp4.json` mide el contacto en el MP4, la aparición real del clic en el AAC, la continuidad entre capítulos y las cuatro frases de subtítulos. Las capturas `mp4-*.png` y `segundo-a-segundo.jpg` proceden de la decodificación del archivo final.
