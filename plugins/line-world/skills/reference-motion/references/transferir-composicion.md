# Llevar una composición aprendida a datos nuevos

Empieza por lo que el espectador necesita entender. Una imprenta que envía material a cuatro salas y un chat que distribuye un mensaje comparten una relación. Conserva el origen visible, abre una conexión por destinatario y deja los cuatro destinos en pantalla al terminar. El número de ramas y los nombres salen del encargo.

Lee el guion y mapea sus relaciones y unidades a la geometría. [Decidir el plano](decidir-el-plano.md)

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
