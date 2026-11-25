# Dirigir la pose que corresponde a una palabra

Para cada mención importante, identifica la entidad, el verbo y lo que el espectador ya podía ver. Decide si en esa palabra debe reconocer el rótulo, seguir un desplazamiento, descubrir el resultado o volver la mirada a un elemento existente. Anota por separado el primer trazo, la primera lectura completa, el comienzo de la acción y la llegada.

## Qué se observó

Se revisaron dos pasajes de cada uno de los veinte videos de *System Design Interview*. En 32 de ellos la expresión corresponde directamente a una entidad, valor o acción. Ocho muestran una ilustración conceptual. Entre las 25 primeras apariciones medibles de las correspondencias directas, 19 precedieron la mención por más de 0,25 s, una quedó en la banda de ±0,25 s, dos ocurrieron después y tres quedaron indeterminadas. Para el evento principal de cada uno de los 32 pasajes directos, los conteos fueron 19, 2, 5 y 6, respectivamente. La muestra fue elegida por su composición. [Observaciones y poses de los 40 pasajes](voice-poses.json)

| Situación | Qué enseña el original | Cómo dirigir otro plano |
| --- | --- | --- |
| Se presenta una entidad que luego se mueve | La tarjeta S4 empieza a aparecer a 243,04–243,12 s. La voz dice S4 hacia 244,08 s. Su viaje empieza a 245,04–245,36 s. | Deja reconocer la entidad en su origen y reserva el siguiente gesto para el traslado. [Ver el anillo](https://www.youtube.com/watch?v=UF9Iqmg94tk&t=243s) |
| El verbo prepara una consecuencia | Tras «resolve», el primer trazo llega unos 0,44–0,56 s después y el resultado completo se lee 1,08–1,28 s después del verbo. | Distingue el comienzo de la acción de la pose en que ya se entiende el resultado. [Ver el hito resuelto](https://www.youtube.com/watch?v=o-k7h2G3Gco&t=423s) |
| La voz nombra una decisión | La solicitud ya se desplaza cuando se oye «reject» hacia 207,68 s. Cambia de color a 207,64–207,76 s. | Mantén visibles las dos salidas. Puedes sincronizar el énfasis con la decisión mientras continúa la trayectoria. [Ver la decisión](https://www.youtube.com/watch?v=YXkOdWBwqaA&t=207s) |
| Se nombra un caso particular dentro de un conjunto | 2160p ya es legible unos seis segundos antes de oír ese valor específico. La narración venía presentando el conjunto de versiones. | Identifica si la frase introduce la familia o señala un miembro. En una segunda mención puede bastar un énfasis. [Ver las resoluciones](https://www.youtube.com/watch?v=jWRW2xGMqSw&t=158s) |

Los eventos visuales se acotaron con fotogramas de 25 fps. Para la voz hay 18 inicios estimados por subtítulos automáticos, 17 por alineación acústica de subtítulos publicados y cinco intervalos de frase. El analizador resta el intervalo de voz al visual. Devuelve «indeterminado» cuando el resultado cruza un límite de la banda. Para cambiar esa banda puedes ejecutar `python scripts/analyze_pose_mentions.py --band 0.5`.

## Llevarlo a otra voz

Toma las palabras de una transcripción alineada, del reloj de locución o de marcas revisadas sobre la grabación. Los tiempos de la solicitud cuentan desde el inicio del audio del plano. El informe de dirección conserva en `voice_pose_reference` el ejemplo medido cuando existe una correspondencia con el estudio. Decide el desfase para el ritmo de la nueva frase. El valor predeterminado de `offset_s` es cero.

```json
{
  "brief": "A qué sedes envía programas la imprenta",
  "rows": [
    {"origen": "Central", "destino": "Aurora"},
    {"origen": "Central", "destino": "Ribera"}
  ],
  "narration": {
    "duration_s": 8,
    "timing_source": "Marcas revisadas en la locución de este plano",
    "words": [{"text":"Aurora","start_s":2}, {"text":"Aurora","start_s":6.5}],
    "cues": [
      {"target":"Central","role":"context","mention_s":0.6},
      {"target":"Aurora","role":"readable","word_index":0,"offset_s":-0.2},
      {"target":"Ribera","role":"enter","mention_s":4},
      {"target":"Aurora","role":"emphasis","word_index":1,"hold_s":0.8}
    ]
  }
}
```

Desde `line-world-video`, ejecuta `python scripts/line_world.py from-brief solicitud.json --project salida`. Añade a `narration` la ruta local `audio`, relativa a la solicitud, para incluir la grabación en el MP4. Su duración debe corresponder al reloj indicado. Puedes omitir el archivo para exportar solo la imagen con ese reloj. La pausa final de lectura puede continuar después de la voz.

- `context` comprueba que la entidad ya formaba parte de la pose inicial. `enter` sincroniza el inicio geométrico de la entrada. Con una máscara progresiva pueden pasar unos fotogramas hasta distinguir la figura.
- `readable` sincroniza la primera lectura completa del rótulo de un nodo o mensaje. `emphasis` destaca un nodo visible durante `hold_s`. Puede repetirse en menciones sucesivas.
- `action` y `result` distinguen comienzo y llegada de un desplazamiento. Puedes indicar un nodo por id, un enlace por `origenId->destinoId` o un turno por `message-1`, contando desde uno.
- La red y el diagrama de mensajes resuelven las poses por su significado. Para otros diagramas de la biblioteca se puede fijar una pose comprobada con `pose`, entre 0 y 1 del movimiento original. Los productores que requieren otra representación reciben las marcas en un informe de dirección.
- Revisa el MP4 en la palabra, unos fotogramas antes y unos después. Comprueba por separado la figura, la tinta del rótulo y el color del foco. Compara el audio codificado con la grabación para distinguir un desfase visual de un desplazamiento de la pista sonora.
