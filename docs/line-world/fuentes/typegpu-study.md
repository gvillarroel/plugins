# Cómo se siguen las figuras en TypeGPU Kit

Software Mansion explica una arquitectura de GPU alternando demostraciones, entrevistas y diagramas animados. Cuando la explicación cambia de escala, suele quedar en pantalla algo que el espectador ya conoce. Puede ser un puerto, la posición de una fila o el extremo de una barra. Esa referencia permite identificar qué figura ha cambiado y qué relación acaba de formarse. [Video original](https://www.youtube.com/watch?v=S64kbVjlbpU)

## Diez composiciones para reutilizar

| Componente | Qué puede seguir el espectador | Qué conservar al cambiar los datos o el dibujo |
| --- | --- | --- |
| `field-packing` | Las copias que parten de cuatro campos y llenan tres filas de memoria. | Dejar visible el emisor. Colocar los bytes debajo de la vista que los consume y respetar las celdas de alineación. [0:35](https://youtu.be/S64kbVjlbpU?t=35) |
| `layer-preview` | La apertura de espacio entre la cabecera y la base, seguida de los efectos en una misma imagen. | Mover la cabecera como unidad. Mantener la base y el encuadre del resultado durante el alta de capas. [1:19](https://youtu.be/S64kbVjlbpU?t=79) · [2:15](https://youtu.be/S64kbVjlbpU?t=135) |
| `isometric-layers` | Una pieza sale de una pila y aterriza en un nuevo soporte. | Preparar el destino antes del vuelo. Mantener el texto sobre la cara y usar los mismos ejes de proyección en la pila y el soporte. [2:34](https://youtu.be/S64kbVjlbpU?t=154) |
| `pass-strip` | Cada llamada añade un segmento a una secuencia que termina en un único envío. | Alinear el orden de lectura del código con el orden de crecimiento de la tira. Conservar la imagen resultante encima de ambos. [2:47](https://youtu.be/S64kbVjlbpU?t=167) · [3:04](https://youtu.be/S64kbVjlbpU?t=184) |
| `module-transfer` | Un módulo se separa del inventario para explicar qué usa y qué devuelve. | Conservar el hueco de origen y los vecinos en su sitio. Hacer legibles las entradas y salidas después de que el módulo llegue. [3:42](https://youtu.be/S64kbVjlbpU?t=222) |
| `vertex-remap` | Los puntos del dominio forman una superficie en otro espacio. | Mantener el orden de llegada y las posiciones finales cuando aparecen las caras. Aquí 375 muestras UV forman una malla de 672 triángulos. [4:07](https://youtu.be/S64kbVjlbpU?t=247) |
| `import-footprint` | Cambia la parte destacada de un paquete de tamaño fijo. | Cada celda conserva su unidad y posición durante la selección. Dos grupos pueden iluminar la misma celda. [4:48](https://youtu.be/S64kbVjlbpU?t=288) |
| `command-lanes` | La llamada de brillo, primero aislada, se reconoce como tercera fila al ampliar el contexto. | Conservar el destino de los comandos. Comparar las duraciones desde un borde común y cambiar solo la fila afectada por la variante. [5:06](https://youtu.be/S64kbVjlbpU?t=306) |
| `shared-host` | Dos entornos consumen una escena común a través de los mismos puertos. | Introducir el segundo entorno cuando ya se entiende el primero. Preservar las dos conexiones al reducir el conjunto a un diagrama de ramas. [5:42](https://youtu.be/S64kbVjlbpU?t=342) |
| `split-clock` | Un trabajo ocupa el turno siguiente mientras la interfaz mantiene sus ocho pulsos. | Mantener la escala temporal compartida. El cuarto trabajo se alarga, se suprime el quinto despacho y los pulsos posteriores siguen alineados. [6:00](https://youtu.be/S64kbVjlbpU?t=360) |

## Elegir una composición

Cuando importa **de dónde viene una pieza**, conviene que el origen siga dando información después de la salida. En el inventario basta con dejar la ranura vacía. En la memoria hace falta conservar el emisor, porque un solo campo produce muchos bytes. Una superficie paramétrica requiere además que los puntos que llegaron primero mantengan su posición mientras se dibujan las caras.

Cuando importa **qué cambió en un resultado**, hace falta una referencia compartida para la comparación. Puede ser el mismo encuadre de cámara, el mismo extremo de una barra o el mismo pulso vertical en dos pistas. El cambio adquiere significado porque se ve al lado de algo que se mantiene.

Cuando importa **cómo se relacionan dos escalas**, hay que permitir que el espectador reconozca una figura antes y después de abrir el plano. La llamada de brillo conserva su carril. El bloque isométrico conserva sus caras y su rótulo. En la escena compartida, el vínculo son los dos puertos.

## Evidencia y reproducción

rea-video analizó la duración completa del original y propuso 78 segmentos. El archivo contiene 13 735 fotogramas de 1920 × 1080 a 30000/1001 fps. Las observaciones de esta biblioteca proceden de la inspección del video decodificado en las ventanas enlazadas. Las coordenadas del índice usan el cuadro completo y son aproximadas. Las duraciones de las recetas, las curvas de interpolación, la selección de cinco capas o filas para los ejemplos y las ilustraciones son decisiones de esta producción.

Los diez movimientos están disponibles en la galería, cada uno con enlaces a sus instantes de origen. La receta monta todos los ejemplos en una película horizontal. Para ensayar otra combinación se pueden quitar escenas de la receta o cambiar sus rótulos, duración y datos admitidos. [Galería](../../../plugins/line-world/skills/reference-motion/assets/demo.html?pattern=field-packing) · [Receta de la película](../../../plugins/line-world/skills/reference-motion/assets/diagramas-typegpu.json) · [Índice de observaciones](../../../plugins/line-world/skills/reference-motion/references/patterns.json) · [Generador y campos](../../../plugins/line-world/skills/reference-motion/references/usage.md)
