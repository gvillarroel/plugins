# Contrato de dirección

El productor usa Python, Pillow y FFmpeg con libx264. Lee el contrato de colores y Space Grotesk ya distribuidos por `line-world-video`, dentro del mismo plugin. Renderiza localmente sin navegador ni red una vez disponibles las dependencias.

| Campo | Significado |
|---|---|
| `version`, `fps`, `size` | Esquema 1. Reloj entero de 12 a 60 fps. El par ancho/alto usa píxeles pares entre 320 y 3840, compatibles con H.264 YUV 4:2:0. |
| `source` | Procedencia o carácter simulado de las mediciones. Queda preservado en la receta cuyo hash consta en el informe. |
| `anchor.label`, `anchor.value` | Identificación compartida por todos los planos. Su recorte debe producir los mismos píxeles en todos los fotogramas de una exportación. |
| `scenes[].id`, `title` | Identificador único y título visible elegido para explicar el plano. |
| `kind: transfer` | Dos lugares en `labels`. El objeto y su rastro atraviesan un eje común. |
| `kind: trace` | De dos a cinco etiquetas y mediciones finitas, en orden, más `unit`. Admite subidas, descensos, repeticiones y valores negativos. Un punto recorre la curva y cada cifra aparece al alcanzar la muestra. La colocación comprueba que la cifra queda separada del trazo y de las anteriores. |
| `kind: compare` | Dos valores con la misma unidad, un dominio común y una referencia explícita al cero en dominios con signo. Una medición nula se indica con una marca vertical y una cifra. Cuando una magnitud positiva ocupa menos de un píxel, se conserva su longitud real y se lee la cifra junto a la barra. Con `fromValues` se pueden comparar dos estados definidos mediante valores de partida y llegada. |
| `cue`, `move`, `hold` | Número de fotogramas enteros. Movimiento mínimo de 0,65 segundos y lectura mínima de 0,8 segundos. |
| `note` | Texto opcional. El recorte empieza después del 60 % del movimiento y deja la frase completa durante la lectura. |

La escala es lineal e incluye el cero. Para una escala logarítmica, una banda de incertidumbre o una magnitud conocida solo como límite, elige un productor que conserve esa información. La CLI rechaza valores como `"<0,1"` en un vector de mediciones. Un límite puede aparecer como observación textual en `note`. El ajuste distribuye frases entre hasta tres líneas, mide la caja de cada glifo y rechaza textos que siguen sin caber. En móvil, el campo `labels` se lee mejor con nombres de observaciones que con oraciones.

El informe marca `startFrame` incluido y `endFrame` excluido en el reloj de la película. `movementStart` y `readingStart` son posiciones absolutas. Para la voz, divide estos índices por `fps`. Cada plano registra el pico de capas que cambian píxeles y el número de cuadros con dos o tres cambios simultáneos. El productor compara todos los cuadros decodificados con su imagen de origen, verifica una pausa inmóvil y vuelve hacia atrás a los nueve instantes del ejemplo. La hoja de contacto ofrece inicio, desarrollo y resultado de cada plano a tamaño reducido. El suavizado de los bordes de las letras y el submuestreo del MP4 pueden producir colores intermedios en el contorno.

## Una partitura con locución medida

`scripts/narrated.py` toma una receta y el `timeline.json` del máster ya grabado. Los identificadores de plano coinciden con los de la voz. En `timing`, elige el índice de `sentence` (desde cero) con `edge: start` o `end`, o el índice de `effect`. `offsetSeconds` desplaza la entrada respecto a esa muestra y `moveSeconds` determina su duración. El adaptador usa las mismas fronteras de escena que el compositor, conserva la última fracción de cuadro y calcula la pausa que resta. En el conjunto adjunto el primer cambio se ancla al clic existente de Earshot y el segundo al comienzo de la frase sobre la apertura del interruptor.

```powershell
uv run scripts/narrated.py assets/circuito-narrado.json /ruta/al/audio/timeline.json --out salida/circuito --render
```

La salida incluye la receta sincronizada, dos escenas HTML locales, cuadros PNG de origen deduplicados, `atencion.json`, `film.json`, la película con voz y el informe de `compose_narrated.py`. Las dos filas de comparación ofrecen regiones independientes que el adaptador puede declarar automáticamente. Para recorridos, curvas o notas adicionales, suministra el archivo de regiones y beats del proyecto con `--attention`. El mismo auditor del compositor comprueba cada segundo del MP4 y verifica audio, capítulos y subtítulos.
