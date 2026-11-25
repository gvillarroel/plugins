# Cómo escoger y dirigir una composición matemática

¿Qué podrá señalar el espectador al final del plano? Identifica el objeto que debe reconocer y la relación que se quiere demostrar. Dibuja la pose inicial, el cambio que aporta evidencia y la pose en que se puede leer la conclusión. Haz que la cantidad o la construcción geométrica gobierne tanto la posición como el tiempo de sus marcas.

## Elegir con datos nuevos

| Lo que se quiere explicar | Composición y orden del gesto |
|---|---|
| Una búsqueda acota un intervalo o vuelve al intervalo que lo contiene | Marca los límites, amplía la selección y conserva su ubicación en el dominio. En los primeros segundos de la codificación aritmética se abren subdivisiones. Más tarde se retrocede desde una palabra hasta otras con el mismo prefijo. [Entrada](https://www.youtube.com/watch?v=qbsb9DpdZ6s&t=1s) · [Regreso](https://www.youtube.com/watch?v=qbsb9DpdZ6s&t=620s) |
| La posición de un móvil genera una gráfica | Mantén a la vista el móvil y lleva su medida a los ejes en el mismo instante. En la lección de Euler, se distingue la oscilación y luego se puede leer su pérdida de amplitud mientras el muelle permanece visible. [Ver la oscilación](https://www.youtube.com/watch?v=-j8PzkZ70Lg&t=700s) |
| Un diagrama geométrico explica por qué se cumple una relación | Conserva las figuras de partida al introducir rectas auxiliares. Nombra la intersección cuando se pueda localizar. Para explicar el volumen, cambia la visibilidad de las dos superficies hasta que la parte común se pueda seguir por sí sola. [Rectas tangentes](https://www.youtube.com/watch?v=zxOK2vKVfQM&t=5s) · [Volumen común](https://www.youtube.com/watch?v=V_uq3v6xK-4&t=7s) |
| Una cantidad se lee de dos maneras | Vincula una muestra de la primera vista con su posición o su valor en la segunda antes de añadir otras. Conserva la identidad al cambiar de forma o sistema de coordenadas. [Curva y parámetros](https://www.youtube.com/watch?v=IQqtsm-bBRU&t=690s) |
| Un ejemplo cambia pero satisface la misma condición | Deja visible la condición en cada configuración. Un cuadrado inscrito se reconoce incluso cuando la curva y la escala cambian entre ejemplos. [Cuadrados inscritos](https://www.youtube.com/watch?v=LuVUnd0C07U&t=16s) |
| Una estimación depende de cuánto espacio se ve | Fija la regla y la unidad mientras cambia el encuadre. La referencia métrica sigue siendo útil cuando el objeto inicial se reduce hasta un punto. [Órdenes de magnitud](https://www.youtube.com/watch?v=C8baNzpnZ7o&t=17s) |

El selector también recupera direcciones sobre campos y parámetros, enumeración de estados, masas de probabilidad, cambios de orden, comparación de modelos y cronologías. El informe `direction.json` conserva enlace, intervalo, poses, ancla y tipo de evidencia. El índice portátil recoge 83 pasajes de las 60 publicaciones públicas identificadas entre el 25 de noviembre de 2024 y el 25 de noviembre de 2026. [Corpus](../../../plugins/line-world/skills/reference-motion/references/3blue1brown-corpus.json)

## Vincular una pose con la narración

Decide si la palabra presenta la operación o interpreta una figura que ya se reconoce. En la intersección de dos esferas, el verbo inglés se oye mientras ambas siguen azules. La lente roja ya se distingue cuando se habla del volumen. En el problema de las sumas, el resultado empieza a aparecer antes de que se pronuncie el número. Reproduce primero el pasaje, elige qué parte del razonamiento conservar y usa el reloj de la nueva grabación. Consulta `speech` en la ficha para distinguir reconocimiento acústico, inicio estimado de palabra y bloque de subtítulo. [Esferas](https://www.youtube.com/watch?v=V_uq3v6xK-4&t=7s) · [Sumas](https://www.youtube.com/watch?v=4h5BEALuh44&t=19s)

## Dos precomposiciones editables

**Intervalos.** La solicitud acepta filas con etapa, orden y límites anidados en una unidad común. También admite `content.intervals` en orden, con `label`, `low` y `high`. El primer intervalo puede ser el más amplio o el más estrecho. En la escala superior se conserva el dominio completo. Las guías indican qué región llena la vista inferior. Acota y amplía en planos sucesivos cuando el recorrido cambia de sentido.

```json
{
  "brief": "Acotar los intervalos anidados de la inspección",
  "title": "Tramo de inspección",
  "unit": "m",
  "rows": [
    {"orden": 1, "etapa": "Vía completa", "inferior": 0, "superior": 1200},
    {"orden": 2, "etapa": "Sector", "inferior": 300, "superior": 600},
    {"orden": 3, "etapa": "Zona de trabajo", "inferior": 420, "superior": 480}
  ]
}
```

**Trayectoria y gráfica.** Aporta filas con `x`, `y`, `t`, la unidad espacial y `unidad_tiempo`. La gráfica muestra la coordenada vertical en función del tiempo. El plano conserva las proporciones entre las coordenadas. Los dos paneles interpolan linealmente entre las mismas muestras, con su separación temporal real. Para una discontinuidad, termina un tramo y abre el siguiente. La velocidad de reproducción del video se puede dirigir con la locución. El eje de la gráfica conserva los tiempos de los datos.

Guarda la solicitud como `solicitud.json` y ejecuta `python scripts/line_world.py from-brief solicitud.json --project salida` desde la skill `line-world-video`. Los nombres `interval-1` y `sample-1` identifican el contexto inicial. Para vincular una medida a una palabra, usa por ejemplo `{"target":"sample-3","role":"result","word_index":1,"hold_s":0.8}` dentro de `narration.cues`. El reloj llega a la pose sobre un fotograma exportado y permite mantenerla durante la lectura. [Formato de locución](../../../plugins/line-world/skills/reference-motion/references/poses-y-menciones.md)
