# Animación de diagramas para vídeo

Para incorporar un diagrama que controla el reloj del montaje, entrega la fuente y un SVG con `--animation none`. En esta modalidad se omiten las directivas `%% @animate`, el número de animaciones es cero y la duración propia es cero. Un SVG externo con animaciones CSS o SMIL propias necesita congelarse o sincronizarse antes del montaje.

Para un diagrama que se anima por sí mismo, usa el productor y conserva su informe.

```powershell
python scripts/animate_mermaid_svg.py mapa.mmd -o mapa.svg --animation mindmap-level --animation-report mapa.json
```

La apariencia predeterminada `solid` usa tinta opaca. Las relaciones se dibujan con trazo cuando lo permite la geometría y las etiquetas se descubren con un recorte. Los movimientos de escala y desplazamiento mantienen el color. La punta de una flecha entra al final del trazo. El modo conserva la longitud y el patrón originales de las líneas discontinuas al terminar. Para una disolución solicitada explícitamente, usa `--animation fade --appearance native`.

| Entrada pública | Tratamiento |
|---|---|
| `auto` | Selecciona un orden según la gramática. En los ejemplos resuelve el flujo por recorrido, el mapa por niveles, Ishikawa por ramas y el intercambio por secuencia. |
| `sequence`, `organic` | Ordenan la presentación de elementos. En el mismo flujo de prueba producen la misma secuencia visible. |
| `ishikawa` | Despliega las ramas de un diagrama de causas y deja visible lo ya explicado. |
| `mindmap-level`, `mindmap-branch` | Agrupan nodos por profundidad o completan una rama antes de pasar a la siguiente. |
| `fade` | Recorta de izquierda a derecha con tinta opaca. La apariencia `native` interpola opacidad. |
| `draw` | Traza conexiones y descubre los rótulos sin partir su geometría al finalizar. |
| `pop`, `zoom` | Usan escala. `pop` tiene un breve sobrepaso, mientras `zoom` aproxima el tamaño final de forma continua. |
| `slide-up`, `slide-left` | Introducen el objeto desde abajo o desde la derecha. El recorte mantiene relaciones y conectores en su posición. |
| `none` | Entrega el diagrama completo desde el primer fotograma. |

El modo sólido reparte las entradas entre un máximo de tres objetos activos. `--max-active 1` produce una lectura individual. Si un grupo supera la capacidad, el productor retrasa el inicio de las entradas sobrantes respetando su orden y duración. Usa `duration_ms` del informe para sincronizar la narración. El argumento `--total-ms` es un objetivo de planificación, y una rama, una permanencia editorial o el límite de concurrencia pueden alargarlo.

El informe JSON incluye `requested`, `effective`, `appearance`, `detected`, `animated`, `effects`, `directive_actions`, `peak_active_entrances`, `entrance_limit` y `duration_ms`. Los efectos y el pico se refieren a entradas programadas. En un programa de directivas, `animated` cuenta objetivos distintos y `directive_actions` cuenta acciones declaradas, incluidos los cambios instantáneos. Las directivas conservan su reloj explícito. Reparte las entradas que superen el límite. Fija la pintura de marcas y pulsos dentro del juego de colores. Usa opacidad cero o uno para los estados discretos. La apariencia nativa conserva la interpolación original cuando la producción la requiere.

## Repetir la comprobación visual

Se necesitan FFmpeg con libx264, uv, Node con Mermaid CLI y Chromium. El script usa el Mermaid CLI disponible o resuelve la versión 11.16.0 con npx. En Windows puede utilizar Edge para capturas y recibir la ruta de Chromium para Mermaid mediante `--mmdc-browser`.

```powershell
uv run --python 3.13 scripts/audit_animation_modes.py --out salida/solido
uv run --python 3.13 scripts/audit_animation_modes.py --out salida/nativo --appearance native --native-sources salida/solido/sources
uv run --python 3.13 scripts/audit_animation_modes.py --dense --out salida/denso
python scripts/test_animation_modes.py
```

La matriz renderiza veinte casos de cuatro gramáticas y cubre los trece valores de la CLI. `--dense` añade un mapa de veintiún nodos y veinte enlaces. Cada carpeta contiene fuentes, SVG, planes y MP4 de doce cuadros por segundo. Las hojas muestran capturas de los MP4 decodificados. `coverage.json` registra todos los cuadros y hashes.

El auditor compara cada cuadro codificado con Chromium, vuelve hacia atrás en el reloj y contrasta la pose final con el SVG de origen. Mide la opacidad computada de los elementos visibles y busca colores nuevos en interiores planos, excluyendo el vecindario de bordes con suavizado. También oculta los conectores del mapa y exige que cada rama pinte en su recorrido. El modo sólido exige un seek idéntico a píxel. El informe nativo admite hasta dieciséis píxeles con un nivel de diferencia por canal y declara las diferencias observadas. La comparación se hace sobre planos de prueba de 512 × 288. La legibilidad del texto se revisa de nuevo al tamaño que ocupará en la película final.
