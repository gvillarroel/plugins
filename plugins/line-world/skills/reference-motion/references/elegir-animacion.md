# Elegir una animación por lo que debe explicar

Empieza por la pregunta del espectador. Una tabla con fecha, sucursal e importe puede servir para ver una tendencia, comparar sucursales en una fecha o consultar una cifra exacta. Cada pregunta pide una composición distinta, aunque el archivo sea el mismo.

Desde la carpeta de esta skill, el [selector](../scripts/recommend_motion.py) acepta una descripción del objetivo. Puedes añadir los datos locales para contrastar la forma del archivo con la intención.

```sh
python scripts/recommend_motion.py --brief "Comparar ventas por región" --data ventas.csv
python scripts/recommend_motion.py --brief "Dos relojes: la interfaz sigue a su ritmo mientras se retrasa un trabajo" --json
python scripts/recommend_motion.py --list-intents
```

El archivo puede ser un CSV con cabecera o un JSON con una lista de registros de valores escalares. Con una relación ya identificada, `--intent inspect-item` indica que hay que seguir un elemento desde su conjunto hasta el detalle. La salida identifica el componente o productor, explica el movimiento propuesto y señala qué referencia se debe mantener fija. Cuando quedan dos lecturas posibles, incluye la pregunta que permite distinguirlas. Usa la selección como punto de partida editorial y comprueba que los campos, unidades y entidades del usuario sostienen la lectura.

Para conceptos expresados con el vocabulario de un oficio, traduce la relación antes de escoger una técnica. Por ejemplo, «sacar un manuscrito del catálogo para ver quién lo corrige» describe una inspección de un elemento de una lista. Si el texto libre deja esa intención abierta, pasa el brief original junto con `--intent inspect-item`. Si el encargo solo dice «mostrar el catálogo», el propósito sigue abierto.

## De la pregunta a la composición

Para una pregunta sobre **qué ruta sigue una solicitud**, distingue entre un intercambio en el tiempo, el consumo de capacidad y el orden de atención. El intercambio conserva los participantes, el consumo conserva la decisión y el orden de atención conserva las colas. [Decidir el plano](decidir-el-plano.md)

Por ejemplo, «¿Cómo se ramifica un árbol de prefijos al agregar varias palabras?» selecciona la red de la escena 11. La respuesta incluye `scene_id`, `recipe` y el enlace al pasaje. Con `generate_motion.py init video-11-staged-network prefijos.json` puedes partir de ese árbol. Cuando solo se especifica una red que debe revelarse por etapas, se puede iniciar la plantilla general con `init staged-network red.json`.

| Lo que necesita entender el espectador | Qué mostrar | Qué mantener estable |
| --- | --- | --- |
| ¿Qué categoría tiene más? | Barras sobre la misma escala. Si la narración empieza por una categoría, mostrarla primero y luego incorporar sus pares. | El cero, la unidad y la posición de la categoría inicial. |
| ¿Cómo cambia una medida con el tiempo? | Una línea revelada en orden temporal. Para fechas irregulares, valores negativos o ausencias, usar el productor D3 del plugin. | El dominio de los ejes y la posición de cada fecha. Un hueco en la serie conserva su significado. |
| ¿Cuánto cambió entre antes y después? | Dos marcas o barras con la misma unidad. Mantener visible la primera al presentar la segunda. | La escala común y la identidad de lo medido en ambos momentos. |
| ¿Qué parte de un total ocupa un grupo? | Para una sola cuota con denominador conocido, un arco y su cifra. Para subconjuntos que comparten elementos, una cuadrícula con membresías explícitas. | El denominador. En la cuadrícula, también la posición de cada unidad aunque pertenezca a varios grupos. |
| ¿De dónde salió la pieza que estamos inspeccionando? | Trasladar la fila elegida al detalle. Mostrar sus entradas y salidas una vez que llegue. | El nombre de la pieza, su hueco de origen y sus vecinos. |
| ¿Cómo contribuye cada etapa al resultado? | Si cambia una misma imagen, añadir capas junto a la vista previa. Si importa el orden de las operaciones, construir una tira de etapas. | El encuadre del resultado en el primer caso y el orden de ejecución en el segundo. |
| ¿Un proceso lento afecta a otro? | Dos pistas con el mismo reloj. Alargar la tarea afectada hasta el turno que realmente ocupa. | La separación entre pulsos y la ubicación de las tareas que siguen a tiempo. |
| ¿Qué importe exacto debo consultar? | Una tabla quieta con unidades y una marca discreta en la fila pertinente. | Los dígitos y las etiquetas durante la lectura. |

Una columna llamada «porcentaje» puede contener tasas calculadas sobre poblaciones diferentes. Para comparar esas tasas, las barras conservan la unidad. Para mostrar una cuota, hace falta identificar el total al que pertenece. Del mismo modo, una lista de pasos admite un proceso secuencial, mientras que las dependencias entre pasos pueden requerir ramas y conexiones.

Si solo una categoría tiene una medida y en las demás figura «pendiente», muestra esos estados en una tabla provisional. Las barras comparativas cobran sentido cuando al menos dos categorías tienen una observación de la misma medida.

## Llevar la sugerencia al generador

Si la propuesta es un componente de la biblioteca, su `id` sirve para iniciar una receta. Por ejemplo, esta secuencia crea y comprueba la receta para el traslado de una fila.

```sh
uv run --script scripts/generate_motion.py init module-transfer detalle.json
uv run --script scripts/generate_motion.py check detalle.json
```

Reemplaza los nombres, la fila elegida y sus entradas y salidas por el contenido de la pieza. Para un productor especializado, sigue la ruta de la recomendación. La [guía de precomposición](precomponer-diagramas.md) muestra cómo convertir ese movimiento en una unidad con inicio, llegada y tiempo de lectura.

Comprueba qué propiedades recibe cada plantilla antes de asignarle datos reales. Por ejemplo, `split-clock` ya dibuja ocho pulsos y el alargamiento de la cuarta tarea. Cambiar `duration` ajusta la velocidad del ejemplo entero. Para representar los milisegundos de una traza real, usa sus marcas de inicio y fin en los dos carriles del productor D3, conservando el reloj común. Del mismo modo, al aplicar una mecánica de GPU a otro dominio, sustituye las leyendas técnicas y la ilustración de ejemplo cuando formen parte del dibujo interno. [Parámetros admitidos por los diagramas](usage.md#diagramas-de-estructura-y-ejecución)
