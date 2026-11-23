# Mercados semanales con voz medida

Este ejemplo convierte cierres fechados, grabaciones de voz y una hoja de escenas en dos vídeos. El lienzo horizontal mide 1280 × 720. El vertical recompone las etiquetas, las cifras, el gráfico y las fuentes directamente a 390 × 844. Ambos avanzan a 30 fps usando el reloj del audio.

Si el reproductor superpone los subtítulos al crédito o al eje, puedes entregar un MP4 adicional con el texto en una franja fija. Desde la carpeta de la skill ejecuta `python scripts/open_captions.py /ruta/al/mercados.mp4 /ruta/al/mercados-subtitulado.mp4 --language spa`. El mismo comando funciona con el máster vertical. Requiere Pillow, FFmpeg y ffprobe. Conserva las palabras, la pista de audio y los capítulos. La imagen completa se reduce al 85 % de su ancho en horizontal y al 87,2 % en vertical. [Exportación de subtítulos fijos](../../../references/narrated-production.md#open-caption-mp4)

## Generar el ejemplo incluido

El plugin trae los cierres del 13 y el 20 de noviembre de 2026, las cinco grabaciones de voz y sus marcas de tiempo. Puedes renderizar la semana sin consultar proveedores ni sintetizar voz. Abre PowerShell en tu carpeta de trabajo y asigna a `$mercados` la ruta de la carpeta que contiene esta guía. Los resultados se guardan en tu carpeta de trabajo.

```powershell
$mercados = (Resolve-Path 'RUTA/AL/PLUGIN/skills/line-world-video/assets/examples/narrated-markets').Path
uv run --script "$mercados/generar.py" --ejemplo --out semana/horizontal
uv run --script "$mercados/generar.py" --ejemplo --formato vertical --out semana/vertical
```

Abre `semana/horizontal/mercados.mp4` o `semana/vertical/mercados.mp4`. Cada película tiene cinco capítulos. El archivo `verificacion.json` contiene el resultado de las comprobaciones sobre la exportación. Puedes cotejar los 38 cierres en una carpeta nueva con `python "$mercados/cierres.py" compare "$mercados/ejemplo-2026-11-20/datos.json" "$mercados/ejemplo-2026-11-20/evidencia/recibo.json" semana/cotejo`. [Datos del episodio](ejemplo-2026-11-20/datos.json) · [Filas originales y proveedores](ejemplo-2026-11-20/evidencia/recibo.json) · [Guion hablado](ejemplo-2026-11-20/voces/narracion.json) · [Duraciones y procedencia de la voz](ejemplo-2026-11-20/voces/duraciones.json)

Se necesitan FFmpeg, FFprobe y Chromium. En Windows se puede añadir `--browser msedge`. `--preflight-only` prepara el proyecto, los movimientos y los subtítulos antes de exportar. Cada directorio de salida conserva un HTML editable, los datos normalizados, la atención segundo a segundo, la película, una plancha de las frases y una verificación del MP4.

## Adaptación a la siguiente semana

El ejemplo incluido coteja automáticamente cada valor con el recibo congelado antes de componer. En un episodio propio, añade `--recibo semana/evidencia/recibo.json` a `generar.py` para aplicar el mismo control. El archivo `cotejo-fuentes.json` registra por fecha el valor observado, la unidad y el proveedor. Una diferencia de un centavo impide publicar la revisión y conserva la edición aceptada. Las grabaciones y sus marcas de tiempo deben corresponder al nuevo guion.

### Subtítulos en español

La receta semanal que genera `preparar_guion.py` activa `"caption_layout": "es-lectura"` en el productor de voz. Así, `scene_audio.py` ya entrega un SRT de lectura y registra sus tiempos en `timeline.json`, también cuando recibe grabaciones. Los guiones de voz que omiten el campo conservan la partición por frases. Para preparar una pista adicional con un máster existente puedes usar el mismo código sin volver a sintetizar.

```powershell
python "$mercados/../../../../media-use/audio/scripts/spanish_captions.py" semana/audio/timeline.json --out semana/pista-nueva
```

El destino nuevo contiene `captions.srt` y `cortes-subtitulos.json`. Admite `--words` para marcas de este máster. Un número completo con unidad que físicamente no quepa en dos líneas de 42 puede usar hasta 48 caracteres por línea dentro de esa cifra. El recibo identifica el ancho excepcional con `longQuantityLine`. Si el valor supera incluso ese espacio, `quantityContinues` identifica un corte entre grupos del número. En la semana del 13 de noviembre, el precio del bitcóin ocupa dos líneas de 40 y 43 caracteres. Se conserva en un solo bloque, y Chromium dibuja dos líneas en la pantalla de 390 × 844.

Si entregas un `timeline.json` con su `captions.srt`, el compositor conserva los tiempos, las palabras y los saltos de línea del autor. Para las grabaciones por tramos de `duraciones.json`, arma el máster y divide cada frase en subtítulos de hasta dos líneas, con un objetivo de 42 caracteres por línea. Busca cortes de cláusula o de grupo sintáctico, y favorece una sola línea cuando cabe. Conserva juntos los numerales, los decimales hablados y sus unidades. Cuando una medida completa excede una línea, puede pasar la unidad a la línea siguiente del mismo subtítulo. El objetivo de lectura de este productor es 17 caracteres por segundo; la velocidad concreta depende de la voz y se informa en la revisión del archivo exportado. Estos criterios de segmentación siguen la [guía española de texto cronometrado de Netflix](https://partnerhelp.netflixstudios.com/hc/en-us/articles/217349997-Spanish-Latin-America-Spain-Timed-Text-Style-Guide).

Con `--palabras`, los cambios de subtítulo se ajustan al comienzo de las palabras que el reconocedor pudo alinear en la frase del máster. `audio/cortes-subtitulos.json` indica la procedencia de cada extremo. `phrase` es el límite medido de una frase grabada, `asr` es la estimación por palabra del reconocedor, y `estimated` es una interpolación entre marcas vecinas. El comprobador coteja los tiempos de palabra con la huella SHA-256 del máster. Si el reconocimiento confunde una cifra, el texto sigue siendo el del guion.

Al comparar dos viernes consecutivos, la cabecera y el comienzo del guion nombran la semana de lunes a viernes. El viernes previo sigue siendo el punto de partida para calcular los cambios. En una ventana de fechas personalizada se muestra el intervalo solicitado. Cada serie mantiene las fechas que realmente observó su proveedor, incluidos los festivos.

El archivo de palabras admite un objeto editorial opcional `subtitleLayouts`. Cada clave identifica la escena y el índice de frase contado desde cero. Cada cadena de su lista es un subtítulo; usa un salto de línea dentro de la cadena para elegir el corte visual. El productor exige todas las palabras y la puntuación originales en el mismo orden y comprueba las líneas y las unidades. La semana documentada incluye una decisión para «bajó del cinco coma quince» seguido por «al cuatro coma noventa y dos por ciento» en la segunda línea del mismo subtítulo. [Marcas y elecciones editoriales del ejemplo](palabras-voz.json)

### Validar fechas, unidades y fuentes

Para obtener los cierres desde la fecha final de una semana, usa [cierres.py](cierres.py), que solo requiere Python 3.11 o posterior. Los tres comandos separan la captura pública, la creación de los datos y su contraste sin conexión. Usa destinos nuevos.

```sh
python /ruta/al/ejemplo/cierres.py week-ending 2026-11-13 captura.json
python /ruta/al/ejemplo/cierres.py export captura.json datos.json
python /ruta/al/ejemplo/cierres.py compare datos.json captura.json comprobacion
```

`week-ending` incluye la fecha final y los siete días naturales anteriores. Para elegir los dos extremos, usa `capture 2026-11-06 2026-11-13 captura.json`. El recibo conserva la URL, el instante de descarga, las filas disponibles, la unidad implícita en el campo original y la huella de cada respuesta HTTP. Se consultan FRED y Cboe para el S&P 500, Nasdaq para el Composite y el cierre bursátil de TLT, Investing.com para el oro al contado, CoinMarketCap para los cierres UTC de Bitcoin y el Tesoro para el rendimiento par a diez años. iShares ofrece el último cierre del fondo y un histórico independiente de NAV.

Una fuente bloqueada o sin filas queda identificada en la captura. Si falta por completo una serie, la captura conserva el recibo parcial y devuelve código 1. Si el histórico de oro no está disponible por HTTP, selecciona las fechas de interés y guarda las filas visibles de la tabla diaria **XAU/USD** del proveedor en un CSV de cinco columnas `Date,Price,Open,High,Low`. La edición inglesa usa `Nov 13, 2026` y `3,880.70`; entrecomilla los campos que contienen comas. Puedes aportar otro CSV de la edición española con `13.11.2026` y `3.880,70`. Ejecuta `add-public-tables captura.json tabla-en.csv [tabla-es.csv] captura-completa.json` y usa ese recibo en los pasos siguientes. [Tabla de XAU/USD](https://www.investing.com/currencies/xau-usd-historical-data)

`export` conserva cada fecha observada. Exige todos los días naturales de Bitcoin, coteja los calendarios de las tres referencias de renta variable y comprueba los extremos de las demás series. Si un mercado cerró en un extremo, `--sessions calendario.json` permite declarar las fechas comprobadas para esa serie, por ejemplo `{"ust10":["2026-11-06","2026-11-09","2026-11-10","2026-11-12","2026-11-13"]}`. También puedes declarar todas las fechas esperadas para detectar un hueco interior. El productor devuelve un error cuando la evidencia resulta insuficiente. `compare` genera un CSV y un JSON por observación, con código 0 si todo coincide y 1 si encuentra diferencias o fechas pendientes. Los recibos y las entregas previas se conservan. [Pruebas del importador](test_cierres.py)

Cada activo lleva su calendario. Guarda las fechas ISO y los valores en dos listas de la misma longitud (`fechas` y `values`), o usa una lista de `observaciones` como la siguiente. `fecha` identifica la sesión. Si conoces la hora efectiva del cierre, `cierre` conserva ese instante con su desplazamiento UTC. Un activo que cotiza diariamente puede incluir el sábado, el domingo y un festivo de otro mercado. Omite las fechas para las que la fuente carezca de valor. `convencion_cierre` permite distinguir, por ejemplo, la última operación de una vela BTC-USD de una observación diaria de rendimiento. `zona_horaria` documenta qué reloj utiliza la fuente.

```json
{
  "nombre": "Índice de muestra",
  "unidad": "puntos",
  "tipo": "precio",
  "zona_horaria": "America/New_York",
  "observaciones": [
    {"fecha": "2024-11-27", "cierre": "2024-11-27T16:00:00-05:00", "valor": 133},
    {"fecha": "2024-11-29", "cierre": "2024-11-29T13:00:00-05:00", "valor": 132}
  ]
}
```

Los dos horarios y precios del ejemplo son sintéticos. En una receta real, añade `fuentes` con enlaces HTTPS a las publicaciones que contrastaste. El pie del gráfico utiliza el primer proveedor declarado, o la atribución editorial de `fuente_corta`. Una causa como «festivo» requiere confirmación de la fuente. El informe enumera `sinObservacion` para las fechas sin una cifra en los datos.

```powershell
python "$mercados/validar.py" semana/datos.json --out semana/validado
python "$mercados/validar.py" semana/dos-series.json --parcial
```

La primera orden comprueba las seis referencias del vídeo, escribe los cierres normalizados en `datos.json` y desglosa sus variaciones y extremos observados en `informe.json`. Usa una carpeta de destino nueva. La segunda permite revisar las series disponibles mientras reúnes las restantes. Ambas comprueban fechas, valores y estructura de las fuentes. El contraste con cada publicación sigue siendo editorial. [Esquema JSON](datos.schema.json)

Para una tasa, declara su escala de origen en `escala_tasa`: `porcentaje` para 4,18, `fraccion` para 0,0418 o `puntos_basicos` para 418. Las tres expresiones corresponden a un rendimiento anual de 4,18 %. Al convertir fracciones o puntos básicos, el normalizador conserva la unidad y las cifras originales en `tasa_origen`. En una semana con extremos de 4,41 % y 4,18 %, la variación es −0,23 puntos porcentuales, o −23 pb. Para un precio, la variación se calcula como 100 × (precio final / precio inicial − 1). Cuando dos series tienen extremos fechados distintos, el balance lo indica.

El formato heredado `dias` sigue disponible. El generador sólo hereda la lista global de días cuando la serie carece de calendario propio. Un calendario local vacío, fechas duplicadas o dos representaciones contradictorias producen un error antes de sintetizar voz o renderizar.

### Preparar voz y edición

Cuando la voz cambia de porcentaje a precio dentro de una misma frase, añade `"startOn": "y cerró"` al plano del precio. El plano anterior seguirá visible hasta el primer cuadro que contenga el inicio medido de esas palabras. Proporciona `--palabras transcripcion.json` o guarda `palabras-voz.json` junto al guion visual. El archivo usa la forma `origin.mediaSha256`, `origin.clock = "seconds-from-first-decoded-sample"` y `words` con `word`, `start` y `end` en segundos. Transcribe el máster WAV de la semana con tiempos por palabra y comprueba la expresión en contexto. El compositor exige una sola coincidencia dentro de la frase y coteja la huella con el máster actual. El ZIP incluye las marcas necesarias para reconstruir el episodio sin transcribir de nuevo. Las frases que empiezan directamente con su cifra usan su tiempo habitual.

En una tarjeta de rendimiento, `"yieldUnit": "percentage-points"` muestra el movimiento completo en puntos porcentuales y la equivalencia en puntos básicos. Obtiene dirección y cifras del primer y último dato. El titular móvil se reparte en dos líneas. Las recetas previas que eligen la presentación abreviada conservan su composición.

Con los cierres y sus fuentes ya revisados puedes generar la primera versión de los dos guiones desde tu carpeta de trabajo.

```powershell
$voz = "$mercados/../../../../media-use/audio/scripts/scene_audio.py"
python "$mercados/preparar_guion.py" --datos semana/datos.json --preview
python "$mercados/preparar_guion.py" --datos semana/datos.json --out semana/guion
```

`semana/guion/narracion.json` es la receta de voz de cinco capítulos. `semana/guion/guion-visual.json` indica qué cifra o comparación mostrar en cada frase. Puedes editar ambos archivos antes de sintetizar. Si añades o eliminas una frase, actualiza las entradas de su escena y sus índices, que comienzan en cero. El productor comprueba el calendario, los valores y la presencia de enlaces de procedencia con la normalización del generador. El contraste de esos cierres con las publicaciones citadas corresponde a quien prepara la semana. El borrador calcula la dirección, los empates, la posición por magnitud y la variación de la tasa en puntos básicos. Las muestras marcadas `sintetico` se identifican también en la voz. Cada serie acepta `nombre_hablado` y `unidad_hablada` para aclarar siglas o unidades al oído.

Una vez editados los borradores, sintetiza sus frases con Piper y pasa el directorio de audio medido al compositor. Con la voz ya instalada se puede añadir `--offline` a la primera orden.

```powershell
uv run --script $voz semana/guion/narracion.json --out semana/audio
uv run --script "$mercados/generar.py" --datos semana/datos.json --audio semana/audio --guion-visual semana/guion/guion-visual.json --out semana/horizontal
uv run --script "$mercados/generar.py" --datos semana/datos.json --audio semana/audio --guion-visual semana/guion/guion-visual.json --out semana/vertical --formato vertical
```

1. Define `inicio` y `fin` como los límites del período de comparación, y `semana` como el texto que aparecerá en la cabecera. Cada serie declara `nombre`, `unidad`, `tipo`, `values`, `fechas` ISO y `fuentes`. La forma original con `dias` sigue admitida. Incluye al menos dos cierres observados por serie, ordenados y dentro del período. El dato inicial y el final pueden caer en fechas distintas según el mercado. Omite los festivos o sesiones sin cotización e incluye el fin de semana cuando haya datos de bitcoin. Cada variación usa los dos extremos observados de esa serie. El balance avisa si los cierres difieren entre mercados.
   - Los precios deben ser positivos. Un rendimiento de cero es válido y su cambio se calcula en puntos básicos. Un cierre nulo produce un error que identifica la serie y la fecha.
   - Puedes indicar `orden` para las cinco referencias de precio y usar `etiqueta`, `nombre_corto`, `fuente_corta` o `unidad_eje` por serie. El balance identifica la dirección más frecuente. En caso de empate muestra las dos direcciones y el número de referencias que tiene cada una.
   - Para datos de prueba, indica `sintetico: true` y una `procedencia` breve. Ambos formatos muestran la atribución sintética.
2. Proporciona el directorio de la narración de esa misma semana. Se admite un `timeline.json` del productor de audio con su máster y subtítulos o el formato de cinco grabaciones originales con `duraciones.json`. En el segundo caso se verifica el SHA-256 y se ensambla el PCM preservando las pausas.
3. Copia y edita [la hoja de escenas](guion-visual.json). Cada frase medida identifica una escena, su índice de frase, la serie, la idea y una vista. `breadth` agrupa referencias por dirección, `ranking` compara cambios de precio, `line` representa niveles y `coupon` explica la relación inversa entre precio y rendimiento de un bono con pagos pactados. `from` y `to` permiten continuar un recorrido en la frase siguiente. Pasa esta copia con `--guion-visual`.
4. Ejecuta ambos formatos en directorios propios. El verificador comprueba en un navegador los titulares, los valores, la ausencia de colisiones y el tamaño de letra. Compara una pose de cada frase con la imagen realmente decodificada del MP4. El compositor recibe `captionMode: "verbatim"` para validar el texto de los subtítulos con el reloj de las frases medidas. El verificador también coteja el AAC con el máster por escena y recupera los subtítulos del contenedor para compararlos con la narración.

El balance muestra la cuenta semanal completa desde el primer cuadro. A medida que avanza la lectura aparece una marca junto a cada nombre señalado y una línea bajo su porcentaje. En las tarjetas de precio, el titular identifica la fecha del cierre final. La guía y el rótulo «Cierre observado» recorren las observaciones diarias. El trazo une días naturales consecutivos y deja un hueco en cada interrupción del calendario, incluido un fin de semana sin datos.

En la vista `rank`, el porcentaje exacto y la barra de la fila seleccionada llevan el color de énfasis. El ordinal expresa el orden por magnitud dentro de su dirección («3.ª mayor caída»). Si la voz redondea hacia arriba por menos de una décima de punto, la escena acepta `approxPercent` y la cita literal `spokenApprox`. El generador contrasta la cita con la frase medida y el redondeo con los cierres. Retira ambos campos al adaptar una escena cuya nueva locución no haga esa aproximación.

La etiqueta de TLT identifica el plazo de sus bonos desde el balance y la tarjeta conserva el dólar por participación junto a los cierres. La última tarjeta de la semana identifica el rendimiento anual del Tesoro a diez años junto a los valores inicial y final.

El esquema del cupón mueve el rendimiento exigido y el precio teórico del bono en sentidos opuestos cuando cambia la tasa. Si la tasa se mantiene, conserva dos marcas horizontales quietas y explica que el descuento se mantiene.

## Publicación y recuperación

Cada ejecución prepara los datos, el proyecto y los informes en una carpeta hermana del destino. La entrega se publica después de pasar la verificación final. En un destino nuevo, la carpeta se instala con una única sustitución. En un episodio existente, el productor bloquea otras publicaciones y sustituye cada archivo generado de forma atómica. Instala al final `publicacion.json`, que identifica esos archivos por SHA-256. El empaquetador usa los mismos bloqueos para tomar una instantánea coherente de los dos formatos.

Si la ejecución falla durante el render o la verificación, el episodio anterior sigue disponible. Si falla durante la sustitución, el diario restaura los archivos previos. Tras terminar el proceso por la fuerza en ese punto, la próxima generación o empaquetado del mismo destino ejecuta la recuperación antes de continuar. Un lector que abra varios archivos durante la breve fase de sustitución debe coordinar su lectura mediante el bloqueo de publicación.

Con `--preflight-only`, un destino que ya tiene película conserva su entrega y recibe el proyecto de prueba en `preflight/`. Un directorio nuevo recibe directamente la preparación. El productor conserva las fuentes de audio y los archivos de usuario. Si un archivo que necesita sustituir contiene una edición manual o colisiona con un archivo sin inventariar, elige otro `--out` para publicar esa revisión. Los episodios antiguos se reconocen por sus recibos y por los datos incluidos en el HTML verificado.

## Entrega del código y las fuentes

Si utilizaste las carpetas hermanas del ejemplo inicial, este comando crea un paquete con las dos películas identificadas por sus huellas y los materiales para reconstruirlas.

```powershell
uv run --script "$mercados/empaquetar.py" --out semana/horizontal --vertical semana/vertical --audio "$mercados/ejemplo-2026-11-20/voces" --recibo "$mercados/ejemplo-2026-11-20/evidencia/recibo.json" --zip semana/fuentes.zip
```

Con ambos formatos revisados, `empaquetar.py --out <horizontal> --audio <voces-originales> --zip <archivo.zip>` reúne las grabaciones una sola vez, los cierres, las citas, el productor de voz y el compositor de vídeo. El directorio vertical se sitúa bajo el horizontal. Puedes añadir `--recibo <captura.json>` para incluir las filas originales de los proveedores. El empaquetador coteja los datos con ese recibo antes de incorporarlo. El paquete usa rutas relativas y registra las huellas de los dos MP4. `probar_paquete.py <archivo.zip> <recibo.json>` extrae los archivos fuera del repositorio, prueba la receta y el particionador de subtítulos, repite el cotejo de datos si se adjuntó un recibo y vuelve a renderizar ambos formatos.

La vista del cupón ilustra un bono con pagos y vencimiento fijos. Si el rendimiento observado aumenta, la flecha superior sube, la del precio baja y el texto explica el efecto del mayor descuento. La pregunta «¿Y su precio?» se usa cuando alguna serie queda plana o ambas se mueven en la misma dirección. TLT invierte en bonos del Tesoro con vencimientos superiores a veinte años y su cifra representa el precio en dólares de una participación. La cifra del Tesoro a diez años representa un rendimiento anual a vencimiento constante. [iShares TLT](https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf) · [SEC sobre la relación entre tipos y precios de bonos](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-86)

## Pruebas de regresión

```powershell
uv run --script "$mercados/test_narrated_markets.py"
python -B "$mercados/test_guion_semanal.py"
python -B "$mercados/test_validar.py"
python -B "$mercados/test_publicar.py"
python -B "$mercados/test_subtitulos.py"
```

Las pruebas usan un período sintético con dos alzas, dos bajas, un precio
sin cambio y una tasa que parte de cero. Comprueban los errores por fecha
inválida, precio cero y cierre nulo, la dirección del cupón, el recuento
entero frente a las filas marcadas y la proyección de la curva sobre el eje.
Las vistas se inspeccionan a 1280 × 720 y 390 × 844.
