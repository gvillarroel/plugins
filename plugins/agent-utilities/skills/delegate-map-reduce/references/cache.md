# Caché, afinidad y esperas

Aplica sólo los controles que el harness permita y cuyo coste se justifique por la reutilización esperada. La caché de respuestas y la caché de prefijos del proveedor tienen identidades, métricas y reglas de vigencia distintas.

## Reutilizar resultados completos

Consulta la caché antes de adquirir un worker o coordinar un prefijo. La clave representa la tarea semántica: etapa, pregunta/objetivo aplicable, contenido y versión de las fuentes recibidas, instrucciones y contrato de salida, identidad resuelta del backend/modelo y parámetros que cambien la respuesta. Canoniza objetos sin alterar el orden semántico de arrays.

No uses el directorio de salida, el timestamp, el PID o la posición de una pregunta como sustitutos de esa identidad. Cambiar un objetivo debe invalidar las etapas a las que realmente afecta, sin recalcular trabajos idénticos por el simple cambio de etiqueta. Si no puedes resolver modelo o configuración, evita reutilizar entre configuraciones ambiguas.

Revalida cada hit con el contrato y las fuentes actuales. Un JSON legible con citas inexistentes es un miss. Separa el resultado semántico de su envelope administrativo: al reutilizarlo, el coordinador puede asociarlo al task_id actual conservando su origen, sin alterar afirmaciones ni evidencia. Un ID de tarea anterior no invalida por sí solo una respuesta idéntica. Mantén separadas las respuestas locales de los artefactos de cada ejecución para reutilizarlas entre outputs. La vigencia por contenido no depende del TTL de prefijos del proveedor.

Para peticiones idénticas en curso, aplica single-flight: un propietario calcula; sus seguidores esperan. En un runner con varios procesos, usa locks exclusivos con propietario y publicación completa/atómica, con relectura antes y después de adquirir el lock. Un timeout de espera no autoriza inferencia duplicada ni retirar un lock ajeno sólo por su edad. Cancelar un seguidor no cancela al propietario. Si sólo tienes herramientas de subagentes, el padre debe evitar despachar duplicados; no afirmes que eso implementa locks entre procesos.

## Reutilizar prefijos del proveedor

Conserva instrucciones, contratos y contexto compartido al principio; pregunta, feedback y otros datos variables van después. La estabilidad debe llegar al payload real: un cwd aleatorio, fecha inyectada o clave de sesión nueva puede romper la afinidad aunque la plantilla parezca idéntica.

Cuando exista soporte comprobado, usa claves de afinidad o breakpoints sobre el prefijo reutilizable y separa ese bloque del trabajo variable. Verifica las capacidades del **transporte efectivo**, no sólo el nombre del modelo. Un gateway puede rechazar campos documentados para otra API.

Coordina un grupo por proveedor, modelo, sistema y prefijo real compartido:

1. El primer trabajo útil es líder; no hagas llamadas vacías para calentar caché.
2. Los seguidores esperan su resultado válido y, cuando proceda, un margen de propagación configurable. Usa un deadline común, no una espera acumulativa por seguidor.
3. Libera la espera en éxito, fallo o cancelación. Un líder fallido no acredita calentamiento; el siguiente puede tomar su lugar dentro del presupuesto.
4. Las esperas de prefijo o capacidad no ocupan slots de inferencia. Otros grupos pueden avanzar.
5. Si limitas solicitudes por ventana, comprueba y registra el inicio real justo antes del backend. Una reserva anterior a una cola larga puede caducar y causar una ráfaga. Devuelve el worker antes de esperar de nuevo.

Mantén separadas afinidad y coordinación: un reductor puede recibir una clave estable para sus instrucciones comunes sin demorar todos los reductores por un prefijo corto de beneficio incierto. No infles prompts con relleno para intentar alcanzar un umbral.

El POC ensayó un margen por defecto de 250 ms, 1000 ms en un run, una ventana caliente estimada de 240 s y 12 inicios por grupo cada 60 s. Son puntos de partida de ese experimento. No aseguran hits, no sustituyen los límites del proveedor y no son una política óptima para cualquier modelo. El estado caliente de un scheduler es una estimación; no acredita una entrada real ni regula otros procesos sin coordinación distribuida.

Antes de usar TTL, mínimos de tokens o controles específicos, consulta las condiciones vigentes del proveedor y comprueba el SDK/transporte instalado. Referencias oficiales: [OpenAI](https://developers.openai.com/api/docs/guides/prompt-caching) y [Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-caching). Con subagentes opacos, limita las promesas a la reutilización local que puedas comprobar.

## Medir sin mezclar mecanismos

Registra por ejecución: peticiones lógicas, respuestas reutilizadas, llamadas nuevas, reintentos, esperas y cobertura. Distingue hits de disco, resultados en curso compartidos y esperas entre procesos cuando el runner lo exponga.

El usage pertenece a la llamada que lo emitió. Un backend compartido necesita callbacks o correlación por petición; tomar un historial global puede atribuir tokens de otro batch a un follower sin llamadas.

Con la normalización del Pi probado, `input` son tokens ordinarios y el total de entrada es `input + cacheRead + cacheWrite`; la tasa de lectura es `cacheRead / total_entrada`. Otros SDK pueden incluir ya los tokens de caché en `input`: comprueba la definición antes de sumar. Usa sólo registros completos y declara cuántas llamadas cubren. Ausente significa desconocido, no cero. Un replay local sin inferencia no mide de nuevo la caché del proveedor.

En el POC se observó una repetición local de 33/33 hits y cero llamadas. Un lote real previo leyó 3584 tokens de caché entre 84365 tokens totales de entrada; otros probes reportaron cero. Esto demuestra observaciones de aquel entorno, no una tasa esperable ni causalidad de la espera. Para atribuir una mejora, necesitarías una comparación controlada equivalente.
