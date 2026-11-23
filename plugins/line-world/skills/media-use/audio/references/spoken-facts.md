# Revisar hechos en la voz final

Un subtítulo puede contener «−6» aunque el sintetizador pronuncie «seis». El [verificador](../scripts/check_spoken_facts.py) decodifica con FFmpeg la primera pista de audio del MP4 o WAV, busca expresiones completas en la ventana correspondiente y guarda las palabras reconocidas con sus tiempos. Se puede escuchar ese intervalo en el archivo para decidir una corrección.

## Expresiones editoriales

Guarda un plan JSON. Los segundos se cuentan desde la primera muestra decodificada de la pista de audio. Con una pista desplazada respecto de la imagen hay que convertir los tiempos de los planos al reloj del audio.

En español, «1 euro», «1€» y «€1» son formas equivalentes. Exigir la moneda descarta una cifra aislada. El signo `$` se usa para diversas monedas. Si la fuente identifica dólares y el editor acepta el símbolo que puede devolver el reconocedor, declara ambas lecturas en `expressions`, por ejemplo `["2 dólares", "2$"]`.

```json
{
  "version": 1,
  "checks": [
    {"id":"temperatura-final","start":2,"end":5.5,"expressions":["menos seis grados","menos 6 grados"]},
    {"id":"cambio","start":9.2,"end":12.7,"expressions":["diez grados","10 grados"]}
  ]
}
```

Elige la ventana y las variantes a partir del hecho que exige el guion. Incluye el signo, el verbo de dirección o la unidad cuando importen. Para «23 puntos básicos» sirven «veintitrés puntos básicos» y «23 puntos básicos». Para un porcentaje, escribe «4,92 %», «4,92 por ciento» o «cuatro coma noventa y dos por ciento» según las variantes aceptables. Cada expresión es literal. Las palabras deben aparecer seguidas y por completo dentro de la ventana. El límite superior de inicio es exclusivo. Una pausa superior a un segundo corta la secuencia. El cotejo respeta las palabras enteras, los decimales y los signos. Conserva la equivalencia entre los signos gráficos y las palabras españolas «más» y «menos». Los acentos se conservan.

## Captura local

Instala FFmpeg en el PATH y usa Python 3.11 o posterior. Para reconocimiento local se necesita un entorno con `faster-whisper` y un modelo multilingüe de CTranslate2 ya disponible, por ejemplo `base`. La captura usa CPU y un modelo local o en caché. El audio se decodifica en memoria, a PCM mono de 16 kHz. El reconocedor recibe el audio y el idioma. Los controles editoriales, los subtítulos y el guion se mantienen fuera del reconocimiento.

```powershell
$control = 'plugins/line-world/skills/media-use/audio/scripts/check_spoken_facts.py'
python -B $control video.mp4 hechos.json --model base --language es --save-transcript palabras.json --report revision.json
```

También se puede pasar una carpeta de modelo a `--model`. Conserva el informe, el plan editorial y la transcripción exportada. El informe lleva el SHA-256 del archivo multimedia completo, el del plan y el del JSON de palabras normalizado.

## Transcripción independiente

Con una transcripción previa solo se necesitan Python y FFmpeg. Usa palabras con marcas originales de un reconocedor sin guion ni pistas léxicas, o de una persona que haya escuchado y marcado ese mismo archivo. Los subtítulos, los tiempos inferidos por longitud de texto y una alineación forzada del guion pueden repetir el error que se busca. La procedencia externa la declara quien prepara la evidencia. El hash comprueba que la declaración corresponde al archivo seleccionado. Una transcodificación o modificación del contenedor requiere una nueva vinculación y revisión.

```powershell
python -B $control video.mp4 hechos.json --transcript palabras.json --report revision.json
```

```json
{
  "version": 1,
  "origin": {
    "mediaSha256": "REEMPLAZAR_POR_EL_SHA256_REAL_EN_HEXADECIMAL_MINUSCULO",
    "audioStream": "a:0",
    "clock": "seconds-from-first-decoded-sample",
    "method": "unprompted-asr",
    "provider": "nombre y versión del reconocedor",
    "language": "es"
  },
  "words": [
    {"word":"menos","start":3.22,"end":3.60},
    {"word":"seis","start":3.60,"end":3.92},
    {"word":"grados","start":3.92,"end":4.34}
  ]
}
```

Usa `human-listening` como `method` para marcas de escucha humana y registra la procedencia en `provider`. Cada registro contiene una palabra o un fragmento tipográfico y un intervalo finito, ordenado, sin solapamiento, dentro de la duración decodificada. Se admiten marcas puntuales y una lista vacía cuando el reconocedor devuelve silencio. Los fragmentos contiguos como «5» y «,15» conservan sus tiempos y se cotejan como «5,15».

## Interpretación

| Salida | Significado |
|---|---|
| `0 · coincide` | Se reconoció una expresión admitida para cada hecho en su ventana. |
| `1 · revisar` | Algún hecho carece de coincidencia completa. El informe conserva el intervalo y las palabras cercanas para escucharlas. En una ventana sin palabras, `heard` está vacío. |
| `2` | Falló la lectura de la pista, la carga del modelo o la validación de entradas y procedencia. |

La decisión expresa una coincidencia de palabras en la transcripción. Una omisión puede proceder del reconocedor o de la locución. Escucha el intervalo antes de corregir el guion o dar una cifra por verificada por una persona.

El [test de regresión](../scripts/test_check_spoken_facts.py) cubre signos, unidades, límites temporales, decimales y la vinculación al archivo. Para repetir además el control de los dos AAC del congelador y el WAV de bonos, usa sus exportaciones y transcripciones congeladas.

```powershell
$env:LINE_WORLD_AUDIO_REVIEW_CASES = (Resolve-Path 'output/line-world-lab/critica').Path
python -B -m unittest discover -s plugins/line-world/skills/media-use/audio/scripts -p test_check_spoken_facts.py -v
```
