# Equifax · estudio de referencia

El inventario comprende los **140 videos públicos** que publicó el canal oficial entre el 22 de noviembre de 2024 y el 22 de noviembre de 2026, ambos inclusive. Sus duraciones publicadas suman **29 h 12 min 47 s**. Se cotejaron la pestaña de videos y la lista de subidas, se comprobó la fecha de publicación de cada pieza y se revisaron las pestañas de Shorts y directos. [Canal oficial](https://www.youtube.com/@equifax)

El [inventario portátil](equifax-corpus.json) recoge la fecha, el enlace, la duración y las observaciones visuales por video. Se inspeccionaron ocho posiciones de storyboard por título, 1.120 celdas en total, correspondientes a 1.071 pares distintos de video e instante. Se anotaron 515 observaciones en 22 categorías. Los recuentos indican el número mínimo de videos en los que se vio cada composición. Las categorías pueden coincidir dentro de una misma pieza.

Se analizó la pista visual completa de los 140 videos con `build_track` y `detect_shots` de rea-video. En 95 piezas de hasta seis minutos se trabajó a la cadencia original. En las otras 45 se cubrió la duración a cuatro fotogramas por segundo y se revisaron ventanas seleccionadas a cadencia original. El detector procesó 657.483 muestras y propuso 3.962 segmentos. El inventario portátil conserva los tiempos candidatos, la cadencia y la huella de la fuente de cada título. El estudio se centra en la edición visual. [Versión de rea-video utilizada](https://github.com/JuneYaooo/rea-video/tree/a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8)

| Composición observada | Videos |
| --- | ---: |
| Llamada a la acción | 79 |
| Persona como plano principal | 77 |
| Cierre con disco | 68 |
| Título tipográfico | 41 |
| Identificación del ponente | 38 |
| Placa de marca o de serie | 29 |
| Varios participantes en pantalla | 26 |
| Texto e imagen en dos zonas | 25 |

## Cómo montar secuencias a partir de los ejemplos

| Fragmento | Patrón que se puede reutilizar | Fuente |
| --- | --- | --- |
| Entrevista con cambio de cámara | Inicia la identificación a los 5,50 s. Mantén su reloj mientras cambias del plano cercano al abierto a los 9,21 s. La regla, el nombre y las dos líneas de cargo entran por separado. | [Grasshopper Bank, 5 s](https://www.youtube.com/watch?v=vb3k_OdYQs4&t=5s) |
| Cierre de entrevista | Anima primero la franja inferior. La superior arranca cuatro fotogramas después. Haz que ambas se junten al 41,7 % de la altura y coloca el nuevo sello en ese eje. | [Grasshopper Bank, 74 s](https://www.youtube.com/watch?v=vb3k_OdYQs4&t=74s) |
| Resumen con datos | Introduce una gráfica desde la parte inferior, dale tiempo de lectura, redúcela a una celda y presenta la siguiente. La superposición temporal ayuda a conservar el contexto. | [Presentación de datos, 51 s](https://www.youtube.com/watch?v=pPladopITb4&t=51s) |
| Llamada a la acción de una serie | Mantén primero el disco grande. Redúcelo desde un 34 % hasta un 22 % del ancho y eleva su centro desde un 50 % hasta un 34 % de la altura. Coloca la dirección debajo. Dos piezas repiten la misma geometría. | [Primer cierre, 82 s](https://www.youtube.com/watch?v=zCr72dcu7Do&t=82s) · [Segundo cierre, 98 s](https://www.youtube.com/watch?v=gd4xyHOOb2U&t=98s) |
| Explicador numerado | Empuja la página anterior a la izquierda. Después revela un número de contorno dentro de un arco abierto y una frase breve en la otra columna. | [Tarjeta numerada, 29 s](https://www.youtube.com/watch?v=p2y6xFqv35Y&t=29s) |
| Cifra destacada | Contrae la escena hasta un disco central y da paso al indicador. El contador llega al 79 % mientras el contorno completa prácticamente una vuelta. | [Anillo y contador, 87 s](https://www.youtube.com/watch?v=5tOPcX52B6s&t=87s) |

El [índice de los 33 componentes](../../../plugins/line-world/skills/reference-motion/references/patterns.json) contiene 43 referencias con título, enlace e instante. Incluye mediciones de los fotogramas originales y composiciones identificadas en imágenes fijas. Una referencia con el mismo segundo de inicio y fin documenta la disposición visual. En esos casos la duración y el movimiento de entrada son decisiones del montaje. Los colores, las tipografías, los textos y las imágenes de cada ejemplo son editables. [Guía de uso](../../../plugins/line-world/skills/reference-motion/references/usage.md)
