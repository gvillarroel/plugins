# Decidir qué tiene que verse

Lee primero la última afirmación que el espectador debe poder verificar. Vuelve al guion para identificar quién cambia, qué lo relaciona con las otras entidades y qué dato o forma permitiría comprobarlo sin voz. Si hay dos preguntas con evidencias distintas, prepara un plano por pregunta.

| Pregunta del guion | Cómo asignar la fuente a la escena |
|---|---|
| ¿En qué grupo ocurre con más frecuencia? | Conserva las filas originales. Mapea `fields.category`, `numerator` y `denominator` a grupo, casos y total expuesto. El productor calcula el porcentaje por fila y deja visibles los dos recuentos. Una base cero deja el porcentaje sin dato. Para cantidades absolutas usa `category,value,unit`. |
| ¿Quién cambió y en qué sentido? | Usa `fields.item,before,after` y `unit`, con `intent: "paired-change"`. Cada entidad ocupa una fila. El círculo abierto marca su primera medida y el lleno la última. Una coincidencia conserva ambos signos en el mismo lugar. Usa `focus` si el guion se detiene en una entidad. |
| ¿Qué se observó en cada instante? | Usa `fields.date,value` para fechas ISO reales. Para días del mes, minutos transcurridos u otra coordenada temporal numérica, usa `fields.t,value`, `timeUnit` y la unidad de la medida. Conserva las distancias y los nulos explícitos. |
| ¿Cuáles son alternativas? ¿De qué depende cada una? | Con `concepts`, especifica `conceptRelation`. En `fan-out` el primer nombre es el origen. En `fan-in` el último es el destino. Para equivalentes usa `peers`. Para pasos en un orden documentado usa `sequence`. Para relaciones más complejas, pasa una fila por vínculo real con `source,target`. Una asociación observada entre variables pide puntos emparejados en ejes, sin flechas de causalidad. |
| ¿Por qué se conserva una superficie al redistribuirla? | Si el guion permite deducir dimensiones y posiciones de rectángulos trasladados, usa `intent: "rigid-rearrangement"` y `content: {unit,pieces}`. Cada pieza lleva `id,label,width,height,from:[x,y],to:[x,y]`. Las coordenadas identifican su esquina inferior izquierda. Mantén la misma escala y sigue la misma pieza hasta el nuevo contorno. Para otro tipo de construcción conserva su geometría propia. |
| ¿Qué hace que un movimiento produzca un efecto? | Si hay un accionador, una pieza impulsada y un material sobre el que deja huella o desplaza algo, usa `intent: "contact-transfer"`. En `content.labels` identifica por orden accionador, pieza, material y efecto. Usa `drive: "lever"` o `"linear"` y `effect: "mark"` o `"displace"`. Si el proceso es otro, construye sus estados y su propio acoplamiento. |

Una coincidencia de dos hechos en un lugar o intervalo conocido se puede ver dentro de un encuadre compartido. Usa `conceptRelation: "co-occurrence"`, asigna los hechos observados a `concepts` y el lugar o intervalo a `context`. Las marcas entran juntas. Si el registro incluye mediciones emparejadas, un diagrama de dispersión permite ver la asociación cuantitativa.

Para una rotación con radio y ángulo conocidos usa `intent: "pivot-rotation"` y `content` con `unit,radius,startAngle,sweepAngle`. Con `orientation: "cartesian"`, el cero apunta al este y el sentido positivo es antihorario. Con `"compass"`, el cero apunta al norte y el sentido positivo es horario. La escala y el pivote se mantienen fijos al seguir el punto marcado.

Cuando el relato sigue un solo objeto, identifica qué se mueve y qué estaciones permanecen fijas. Usa `intent: "object-route"` con `content.objectLabel` y la lista de visitas en `content.stops`. Repite el nombre exacto de la estación cuando el objeto vuelva a ella.

## Dirigir las poses con la voz

1. Sitúa el contexto que permitirá reconocer el primer sustantivo. Al oír el verbo, el espectador ya debe poder localizar qué pieza se va a mover.
2. Elige el gesto que aporta la evidencia. Para una tasa, sigue la extensión de la marca con ambos recuentos fijos. Para un mecanismo, sigue el contacto. Para una construcción geométrica, conserva la identidad y la escala de las piezas.
3. Especifica qué deberá seguir visible al decir la conclusión. En una comparación incluye las dos cantidades que la sostienen. Reserva tiempo para leerlas juntas.
4. Si solo tienes el texto, usa fragmentos literales como marcas editoriales. Puedes pasar `staging: {claim,anchor,poses:[{role,phrase,visual}, ...]}` con los roles `context,action,result` una vez cada uno, en ese orden. Copia cada `phrase` del `brief`. Para sincronizar con una grabación, usa `narration.cues` con marcas medidas sobre esa toma. [Formato de las marcas de voz](poses-y-menciones.md)

## Revisar la animación producida

Abre el MP4 que entrega `from-brief` o acaba el plano con el productor indicado en `direction.json`. Detén la imagen en la pose inicial, en el instante que demuestra la relación y al terminar. Intenta contestar la pregunta mirando solo esas imágenes. Si la respuesta depende de leer el guion, modifica el dibujo o el movimiento y vuelve a exportar. Con voz, vuelve a reproducir el plano y comprueba el primer fotograma en que se entiende el resultado respecto de la frase real.

Comprueba si la conclusión depende de una segunda entidad que permanece quieta. Dibuja las dos desde la pose inicial y conserva la posición de la que sirve de referencia mientras mueves la elegida. Si la tarea consiste en reconocer un símbolo, dibuja su contorno, orientación y número de trazos. Mantén al lado el significado que el espectador tendrá que recuperar. Si se pide una proporción conjunta, muestra las sumas del numerador y del denominador antes de presentar el cociente.

Cuando una plantilla pierde alguna de esas evidencias, abre una composición original con [Line World D3](../../line-world-d3/SKILL.md) para datos o [Line World HyperFrames](../../line-world-hyperframes/SKILL.md) para objetos y gestos. Asigna identificadores estables a los elementos del guion y dirige las poses sobre el reloj de esa composición. Entrega el archivo editable y el MP4. Repite la lectura de los tres fotogramas sobre ese archivo.
