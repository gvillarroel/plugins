# Precomponer diagramas de sistemas

En la lista *System Design Interview* de ByteByteGo se decodificaron 220 000 fotogramas de 20 videos a 25 fps. Se revisaron vistas generales de cada video y secuencias de fotogramas alrededor de veinte pasajes. Cada pasaje tiene una reconstrucción editable, sus instantes de origen y una descripción de las adaptaciones. El detector de planos de rea-video sirvió para localizar cambios de imagen. Las decisiones sobre anclas, figuras y recorridos proceden de la inspección de los fotogramas. [Lista original](https://www.youtube.com/playlist?list=PLCRMIe5FDPseVvwzRiCQBmNOVUIZSSkP8) · [Índice por video](../../../plugins/line-world/skills/reference-motion/references/bytebytego-corpus.json) · [Receta de las veinte escenas](../../../plugins/line-world/skills/reference-motion/assets/diagramas-bytebytego.json)

## Elegir según la pregunta

| Pregunta que debe contestar el plano | Plantilla | Datos y composición |
| --- | --- | --- |
| ¿Qué conexión aparece ahora y qué parte del sistema ya existía? | `staged-network` | Nodos, posiciones, tiempos y aristas propios. Un borde puede crecer desde el emisor, transportar una marca o enlazar dos nodos que se desplazan. Sirve también para presentar grupos sin aristas. |
| ¿Qué clave cambia de dueño cuando llega otro nodo? | `ring-handoff` | Un anillo con cuatro propietarios iniciales y una inserción. Cambia los cinco nombres y `keyLabel`. Las posiciones y la reasignación ilustrada son fijas. |
| ¿Qué bits cambian al insertar y qué comprueba una consulta? | `bit-probe` | Tres etiquetas, de 6 a 16 bits y tres grupos de índices. Los dos primeros grupos escriben, el tercero consulta. Un bit ausente da «Descartado». Si todos están presentes, el resultado es «Posible». |
| ¿Quién envía cada mensaje y en qué orden? | `message-ladder` | Dos participantes y de uno a seis mensajes. Cada entrada de `exchanges` contiene `label` y `from`, el índice 0 o 1 del emisor. Las filas indican orden. |
| ¿Cómo se reconocen las partes dentro de una expresión? | `detail-callout` | `focusLabel` identifica el elemento ampliado. Cuatro textos en `parts` se corresponden con los cuatro nombres en `labels`. |
| ¿Cómo se obtiene este código a partir de un número? | `radix-ladder` | `value` y `base` determinan los cocientes, residuos y símbolos. Se admiten bases de 2 a 62 y resultados de hasta cinco dígitos. El alfabeto usa dígitos, minúsculas y mayúsculas, en ese orden. |
| ¿Por qué se admite una solicitud y se descarta la siguiente? | `token-gate` | De 0 a 5 fichas y de 1 a 5 solicitudes. Una solicitud admitida consume exactamente una ficha. Mantén el punto de decisión en su sitio para seguir las dos salidas. |
| ¿Qué versiones salen de un mismo original? | `resolution-fan` | Una fuente y siete nombres de salida. Cada conexión termina en su propia versión. Los rectángulos comparten una esquina y sus tamaños ilustran una jerarquía cualitativa. |
| ¿Quién clasifica y quién elige lo que sale? | `queue-router` | Un clasificador, tres colas y un selector. `inputLabel` nombra la entrada y `criteria` admite hasta tres criterios. Los bloques dibujados ilustran la clasificación. Para longitudes reales de cola, representa las cantidades a escala. |

Una misma tabla admite varias lecturas. Un registro de mensajes con emisor, receptor y orden permite reconstruir un intercambio. Si la pregunta es cuánto tardó cada llamada, hacen falta marcas de tiempo, una unidad y una escala común. Conserva esa diferencia al usar el [selector](../../../plugins/line-world/skills/reference-motion/references/elegir-animacion.md).

## Construir una escena

1. **Elige el instante que explica la relación.** En el video 16, cuatro nodos se desplazan juntos para hacer sitio a una clave. Identifica el grupo y su movimiento común antes de dibujar la clave. El índice conserva los tiempos de cada cambio.
2. **Dibuja tres poses.** En la primera debe reconocerse el punto de partida. En la intermedia debe poder seguirse qué entidad cambia de lugar o estado. En la final se debe leer quién quedó conectado con quién. Deja sitio para la pausa de lectura.
3. **Separa la duración del movimiento de la pausa.** `props.duration` controla el recorrido completo en segundos. `hold` pertenece a la escena. En una red, `x,y` son el centro final y `w,h` el tamaño como fracciones del cuadro. `enter:[a,b]` dibuja la entrada y `active:[a,b]` destaca la figura. Para mover un nodo, define `moveFrom:[xInicial,yInicial,a,b]`. Las aristas siguen sus extremos. Todos estos tiempos son fracciones entre 0 y 1 de la duración del movimiento.
4. **Usa las conexiones para expresar un hecho.** `from` y `to` refieren a IDs de nodo. `via` admite puntos de paso y `token:[a,b]` hace viajar una marca. Usa `directed:false` para una asociación sin dirección. Para mover varias entidades juntas, asígnales el mismo intervalo y desplazamiento.
5. **Compara el cambio con su referencia.** Busca primero un estado reconocible en los dos videos y después un estado intermedio. En los videos 5 y 17, el espectador sigue un original y varias versiones. En el primero conserva las conexiones de la rama que se reorganiza. En el segundo conserva la esquina compartida. Revisar solo el último cuadro oculta la diferencia.

Desde la carpeta de la skill, estos comandos crean una plantilla editable y exportan el montaje del estudio.

```sh
python scripts/recommend_motion.py --brief "¿Quién envía cada mensaje entre el cliente y el servidor?"
uv run --script scripts/generate_motion.py init message-ladder intercambio.json
uv run --script scripts/generate_motion.py init video-11-staged-network prefijos.json
uv run --script scripts/generate_motion.py render intercambio.json intercambio.mp4
uv run --script scripts/generate_motion.py render assets/diagramas-bytebytego.json sistemas.mp4
```

Para partir de una de las doce arquitecturas concretas, usa su identificador de escena como en el ejemplo de `prefijos.json`. Obtendrás la disposición, los tiempos y los datos del pasaje elegido, listos para editar. El campo `scene` del índice identifica cada una.

## Pasajes y recetas individuales

Usa el identificador con `generate_motion.py init` para extraer una sola precomposición. Cada enlace abre el original en el inicio del pasaje.

| Video | Cambio que sigue el espectador | Receta |
| --- | --- | --- |
| 01 · [FAANG System Design Interview: Design A Location Based Service (Yelp, Google Places) · 6:46](https://www.youtube.com/watch?v=M4lR_Va97cQ&t=406s) | Del balanceador a las réplicas | `video-01-staged-network` |
| 02 · [Consistent Hashing – Algorithms You Should Know #1 · 4:03](https://www.youtube.com/watch?v=UF9Iqmg94tk&t=243s) | Un nodo entra en el anillo | `video-02-ring-handoff` |
| 03 · [Bloom Filters – Algorithms You Should Know #2 – Real-world Examples · 3:48](https://www.youtube.com/watch?v=V3pzxngeLqw&t=228s) | Dos escrituras y una consulta | `video-03-bit-probe` |
| 04 · [Back-Of-The-Envelope Estimation / Capacity Planning · 0:47](https://www.youtube.com/watch?v=UC5xf8FbdJc&t=47s) | De la carga total al tamaño de la flota | `video-04-staged-network` |
| 05 · [How Does Live Streaming Platform Work? (YouTube live, Twitch, TikTok Live) · 2:29](https://www.youtube.com/watch?v=7AMRfNKwuYo&t=149s) | Cuatro versiones de una emisión | `video-05-staged-network` |
| 06 · [Why Is System Design Interview Important? · 0:13](https://www.youtube.com/watch?v=EyMRZpgJUuc&t=13s) | Tres rondas, tres tarjetas | `video-06-staged-network` |
| 07 · [System Design Interview: A Step-By-Step Guide · 4:46](https://www.youtube.com/watch?v=i7twT3x5yv8&t=286s) | El servidor incorpora tres clientes | `video-07-staged-network` |
| 08 · [FANG Interview Question – Process vs Thread · 1:47](https://www.youtube.com/watch?v=4rLW7zg21gI&t=107s) | Tres hilos comparten el heap | `video-08-staged-network` |
| 09 · [SSL, TLS, HTTPS Explained · 1:10](https://www.youtube.com/watch?v=j9QmMEWmcfo&t=70s) | Tres mensajes entre cliente y servidor | `video-09-message-ladder` |
| 10 · [What happens when you type a URL into your browser? · 0:31](https://www.youtube.com/watch?v=AlkDbnbv7dk&t=31s) | Una dirección, cuatro partes | `video-10-detail-callout` |
| 11 · [Algorithms You Should Know Before System Design Interviews · 3:32](https://www.youtube.com/watch?v=xbgzl2maQUU&t=212s) | Prefijos que comparten ramas | `video-11-staged-network` |
| 12 · [Top 5 Most Used Architecture Patterns · 1:25](https://www.youtube.com/watch?v=f6zXyq4VPP8&t=85s) | Tres productores y tres consumidores | `video-12-staged-network` |
| 13 · [How to Crack Any System Design Interview · 7:00](https://www.youtube.com/watch?v=o-k7h2G3Gco&t=420s) | Hitos que se van resolviendo | `video-13-staged-network` |
| 14 · [Our Recommended Materials For Cracking Your Next Tech Interview · 0:24](https://www.youtube.com/watch?v=wAMc7NyL4tQ&t=24s) | Una categoría y tres recursos | `video-14-staged-network` |
| 15 · [How Does a URL Shortener Work? · 3:14](https://www.youtube.com/watch?v=HHUi8F_qAXM&t=194s) | División sucesiva y lectura inversa | `video-15-radix-ladder` |
| 16 · [How Key value Stores Work (Redis, DynamoDB, Memcached)? · 0:54](https://www.youtube.com/watch?v=Dwt8R0KPu7k&t=54s) | Una clave selecciona un solo nodo | `video-16-staged-network` |
| 17 · [System Design: Design YouTube · 2:37](https://www.youtube.com/watch?v=jWRW2xGMqSw&t=157s) | Un original, siete resoluciones | `video-17-resolution-fan` |
| 18 · [FAANG System Design Interview: Design A Chat System (WhatsApp, Facebook Messenger, Discord, Slack) · 5:38](https://www.youtube.com/watch?v=okrR1KXNLtA&t=338s) | Un mensaje, muchos destinatarios | `video-18-staged-network` |
| 19 · [Rate Limiter System Design: Token Bucket, Leaky Bucket, Scaling · 3:20](https://www.youtube.com/watch?v=YXkOdWBwqaA&t=200s) | Una ficha admite la primera solicitud | `video-19-token-gate` |
| 20 · [Design a Web Crawler: FAANG Interview Question · 2:50](https://www.youtube.com/watch?v=6u25GckPhLU&t=170s) | Tres colas de prioridad ante un selector | `video-20-queue-router` |
