# Llevar una composición aprendida a datos nuevos

Empieza por lo que el espectador necesita entender. Una imprenta que envía material a cuatro salas y un chat que distribuye un mensaje comparten una relación. Conserva el origen visible, abre una conexión por destinatario y deja los cuatro destinos en pantalla al terminar. El número de ramas y los nombres salen del encargo.

La consulta examina cuarenta pasajes de veinte videos. Cada pasaje conserva su intervalo, el ancla visual, el cambio observado, cómo transferirlo y cuándo emplear otro recurso. Los veinte pasajes incorporados después de la demo incluyen subdivisión espacial, relevo entre carriles, estabilización de ejes, comparación de criterios, contención y vuelta del detalle al contexto. Puedes consultar las direcciones recuperadas para una pregunta con `python scripts/recommend_motion.py --brief "..." --json`. [Catálogo de pasajes y observaciones](transfer-corpus.json)

## Usar el flujo de producción

Desde el directorio de `line-world-video`, ejecuta `python scripts/line_world.py from-brief solicitud.json --project salida`. El director usa la relación que expresan el brief y sus registros. En el proyecto queda la dirección con la referencia y los archivos de la composición producida. Para obtener solo una receta o una derivación desde `reference-motion`, usa los comandos siguientes.

```sh
python scripts/adapt_motion.py solicitud.json --out escena.json --report direccion.json
uv run --script scripts/generate_motion.py render escena.json escena.mp4
```

Esta solicitud puede venir de un encargo en lenguaje corriente. El autor del video traduce a registros las relaciones que el usuario ha especificado. `fields` asocia nombres de columnas con funciones visuales. Para una tabla existente, `data` admite la ruta de un CSV o JSON relativa a la solicitud.

```json
{
  "brief": "¿A qué salas distribuye el taller los carteles?",
  "rows": [
    {"Entrega": "Taller", "Sala": "Grabado"},
    {"Entrega": "Taller", "Sala": "Cerámica"},
    {"Entrega": "Taller", "Sala": "Fotografía"}
  ],
  "fields": {"source": "Entrega", "target": "Sala"}
}
```

| Lo que aportan los registros o conceptos | Composición que se puede construir |
| --- | --- |
| Pares dirigidos en `source` y `target` | Origen común, destino común, árbol o recorrido según las conexiones observadas. Las aristas siguen los nodos durante el movimiento. |
| Dos interlocutores, `message` y `order` | Dos columnas fijas y un mensaje por turno en el sentido correcto. El orden se obtiene de la columna. |
| `group` e `item` | Una banda por grupo y una marca por pertenencia observada. |
| `item`, `before` y `after` cualitativos | Una fila por identidad. La primera columna se desplaza con sus rótulos al abrir la segunda. Los encabezados conservan los nombres de las columnas. |
| Una lista `concepts` ya ordenada, o columnas `step` y `order` | Una cadena editable de etapas. Reserva esta forma para un orden expresado en la fuente. |
| `category`, `value` y una unidad común | Barras con el mismo cero. `focus` puede fijar una categoría existente antes de presentar sus pares. |
| `date`, `value` y una unidad común | Serie D3 con eje temporal real y huecos explícitos. Las observaciones con fecha ISO completa se ordenan por calendario. |
| Un mecanismo con parámetros conocidos | `content` admite los parámetros propios de consultas de bits, conversión de base, fichas, despiece, intercambio, huella y transferencia de módulo. `intent` permite indicar la intención del selector si ya se conoce. Entrega todos los campos semánticos con los valores del encargo. |

La pregunta tiene prioridad. Una vista de turnos muestra quién responde a quién. Medir cuánto tarda cada respuesta exige tiempos y unidades. En datos ambiguos, conserva las lecturas alternativas en la dirección hasta que el contexto identifique la relevante. Ante una relación compleja, entrega al productor elegido los registros completos y las indicaciones del pasaje. Para una lectura exacta o una petición estática, deja la composición en reposo.

## Comprobar la transferencia

Si el plano lleva locución, marca el término y la pose que debe coincidir con él. La entrada inicial, el rótulo legible y el énfasis en una segunda mención pueden ocurrir en instantes distintos. [Estudio de poses, menciones y formato de la partitura](poses-y-menciones.md)

Revisa el comienzo, el momento de cambio y la pausa final del archivo exportado. En el comienzo se debe reconocer el ancla. Durante el cambio, sigue una entidad elegida del encargo y comprueba que el rótulo llega con ella. Al final, cuenta ramas, filas o elementos contra la tabla y comprueba unidades, huecos y proporciones. El informe distingue la referencia observada (`reference`) de la decisión tomada para este plano (`direction`).

## Comparar decisiones entre pasajes

| Video | Pasaje reconstruido en la demo original | Segundo pasaje estudiado |
| --- | --- | --- |
| 01 | [Del balanceador a las réplicas · 6:46](https://www.youtube.com/watch?v=M4lR_Va97cQ&t=406s) | [Subdividir una región conservando el conjunto · 18:05](https://www.youtube.com/watch?v=M4lR_Va97cQ&t=1085s) |
| 02 | [Un nodo entra en el anillo · 4:03](https://www.youtube.com/watch?v=UF9Iqmg94tk&t=243s) | [Seguir la identidad de piezas que cambian de destino · 2:05](https://www.youtube.com/watch?v=UF9Iqmg94tk&t=125s) |
| 03 | [Dos escrituras y una consulta · 3:48](https://www.youtube.com/watch?v=V3pzxngeLqw&t=228s) | [Cambiar el criterio que recibe atención · 1:05](https://www.youtube.com/watch?v=V3pzxngeLqw&t=65s) |
| 04 | [De la carga total al tamaño de la flota · 0:47](https://www.youtube.com/watch?v=UC5xf8FbdJc&t=47s) | [Revelar el pico y conservar su contexto · 2:11](https://www.youtube.com/watch?v=UC5xf8FbdJc&t=131s) |
| 05 | [Cuatro versiones de una emisión · 2:29](https://www.youtube.com/watch?v=7AMRfNKwuYo&t=149s) | [Separar una salida continua en unidades consecutivas · 3:13](https://www.youtube.com/watch?v=7AMRfNKwuYo&t=193s) |
| 06 | [Tres rondas, tres tarjetas · 0:13](https://www.youtube.com/watch?v=EyMRZpgJUuc&t=13s) | [Comparar totales y aportes de varias categorías · 0:58](https://www.youtube.com/watch?v=EyMRZpgJUuc&t=58s) |
| 07 | [El servidor incorpora tres clientes · 4:46](https://www.youtube.com/watch?v=i7twT3x5yv8&t=286s) | [Mostrar una ruta dentro del espacio de posibilidades · 1:39](https://www.youtube.com/watch?v=i7twT3x5yv8&t=99s) |
| 08 | [Tres hilos comparten el heap · 1:47](https://www.youtube.com/watch?v=4rLW7zg21gI&t=107s) | [Conservar el dueño del turno mientras cambia la actividad · 2:10](https://www.youtube.com/watch?v=4rLW7zg21gI&t=130s) |
| 09 | [Tres mensajes entre cliente y servidor · 1:10](https://www.youtube.com/watch?v=j9QmMEWmcfo&t=70s) | [Relacionar la operación de ida con la de vuelta · 3:17](https://www.youtube.com/watch?v=j9QmMEWmcfo&t=197s) |
| 10 | [Una dirección, cuatro partes · 0:31](https://www.youtube.com/watch?v=AlkDbnbv7dk&t=31s) | [Acercarse al resultado y devolverlo a su posición en el mapa · 4:31](https://www.youtube.com/watch?v=AlkDbnbv7dk&t=271s) |
| 11 | [Prefijos que comparten ramas · 3:32](https://www.youtube.com/watch?v=xbgzl2maQUU&t=212s) | [Subdividir una superficie sin perder la referencia al conjunto · 1:48](https://www.youtube.com/watch?v=xbgzl2maQUU&t=108s) |
| 12 | [Tres productores y tres consumidores · 1:25](https://www.youtube.com/watch?v=f6zXyq4VPP8&t=85s) | [Revelar primero un nivel y luego las piezas que lo integran · 0:48](https://www.youtube.com/watch?v=f6zXyq4VPP8&t=48s) |
| 13 | [Hitos que se van resolviendo · 7:00](https://www.youtube.com/watch?v=o-k7h2G3Gco&t=420s) | [Comparar dos soluciones con los mismos extremos y distinto interior · 4:12](https://www.youtube.com/watch?v=o-k7h2G3Gco&t=252s) |
| 14 | [Una categoría y tres recursos · 0:24](https://www.youtube.com/watch?v=wAMc7NyL4tQ&t=24s) | [Construir una secuencia textual con tarjetas de igual jerarquía · 2:02](https://www.youtube.com/watch?v=wAMc7NyL4tQ&t=122s) |
| 15 | [División sucesiva y lectura inversa · 3:14](https://www.youtube.com/watch?v=HHUi8F_qAXM&t=194s) | [Añadir filas exactas hasta que una satisface la pregunta · 1:31](https://www.youtube.com/watch?v=HHUi8F_qAXM&t=91s) |
| 16 | [Una clave selecciona un solo nodo · 0:54](https://www.youtube.com/watch?v=Dwt8R0KPu7k&t=54s) | [Seguir dos versiones hasta una operación común · 4:07](https://www.youtube.com/watch?v=Dwt8R0KPu7k&t=247s) |
| 17 | [Un original, siete resoluciones · 2:37](https://www.youtube.com/watch?v=jWRW2xGMqSw&t=157s) | [Marcar fronteras antes de separar los grupos · 3:42](https://www.youtube.com/watch?v=jWRW2xGMqSw&t=222s) |
| 18 | [Un mensaje, muchos destinatarios · 5:38](https://www.youtube.com/watch?v=okrR1KXNLtA&t=338s) | [Distinguir un aviso periódico del estado que queda registrado · 6:22](https://www.youtube.com/watch?v=okrR1KXNLtA&t=382s) |
| 19 | [Una ficha admite la primera solicitud · 3:20](https://www.youtube.com/watch?v=YXkOdWBwqaA&t=200s) | [Relacionar eventos discretos, contador y umbral por intervalo · 1:16](https://www.youtube.com/watch?v=YXkOdWBwqaA&t=76s) |
| 20 | [Tres colas de prioridad ante un selector · 2:50](https://www.youtube.com/watch?v=6u25GckPhLU&t=170s) | [Distinguir dos criterios aplicados al mismo problema · 3:40](https://www.youtube.com/watch?v=6u25GckPhLU&t=220s) |
