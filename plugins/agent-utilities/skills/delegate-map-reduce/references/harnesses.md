# Adaptar la delegación a las herramientas disponibles

La skill no añade herramientas, autenticación, permisos, un motor de caché ni un scheduler. Identifica las capacidades reales antes de elegir el mecanismo. Conserva el mismo contrato de trabajo aunque cambie el ejecutor.

## Codex con colaboración

Si el entorno expone herramientas como `spawn_agent`, `send_message`, `followup_task` y `wait_agent`, delega mediante esas herramientas. Usa los nombres y esquemas que estén realmente disponibles. Una tarea para un subagente de la ejecución actual no equivale a crear un chat independiente ni autoriza contactar a personas o tareas ajenas.

- Entrega encargos autocontenidos con objetivo, unidades, fuentes, contrato y límites. Reutiliza la sesión de un worker sólo si no arrastra contexto incompatible.
- Despacha por lotes según los slots disponibles. El padre conserva el ledger y hace trabajo independiente mientras llegan resultados.
- Para evaluar de forma independiente una conclusión, pasa las fuentes necesarias y la pregunta, evitando revelar la respuesta esperada. No uses una revisión que sólo compruebe el razonamiento que ya le sugeriste.
- Recoge resultados terminales, valida y alimenta reductores con artefactos concretos. Usa esperas con eventos o intervalos razonables, sin polling apretado. El padre entrega cobertura y conclusión.
- El contexto puede ser compartido y los agentes pueden editar el mismo filesystem: asigna propietarios de archivos para cambios y reserva una etapa de integración.

Estas herramientas pueden no exponer payloads, claves de afinidad ni usage. No declares control del prompt cache ni tokens ahorrados sin esa información. Las marcas temporales y prompts estables no prueban un hit.

## Pi con el POC de documentación disponible

Si la sesión registra `analyze_product_docs`, lee su schema efectivo y usa ese runner para el caso que cubre: un manifest de documentación, preguntas, maps y reducción con citas. No inventes parámetros a partir de esta referencia.

El POC aprendido expone `manifest`, `output_dir`, `backend`, `workers`, `question`, `cache_dir`, `cache_wait_ms`, `cache_warmup_delay_ms` y `prompt_cache`. Comprueba la versión cargada. `backend=demo` verifica orquestación determinista; no representa análisis semántico de un modelo.

La ejecución se lleva a cabo dentro de Pi y devuelve rutas a artefactos. Lee informe, cobertura y métricas antes de presentar una conclusión. Conserva el mismo `cache_dir` entre outputs que puedan compartir resultados. Si la extensión no está cargada, su nombre en este documento no la hace ejecutable.

Si existe un checkout compatible con `src/cli.ts`, `package.json` y el manifest esperado, el CLI Node es otra entrada al mismo runner. Inspecciona primero `node src/cli.ts --help` y usa rutas reales. Ejemplo del POC, desde ese checkout:

```sh
node src/cli.ts run examples/product.json --backend pi --workers 4 --cache-dir .cache/docbatch --cache-warmup-delay-ms 1000 --output runs/analisis
```

No presupongas que ese checkout existe donde se instaló esta skill. Su código no forma parte del paquete de instrucciones. Para este runner, Pi debe estar instalado y autenticado por los mecanismos del usuario.

## Pi con otra extensión de delegación o sin runner

Si hay una extensión de subagentes, usa únicamente sus herramientas verificadas y conserva contratos, presupuesto y cobertura. La CLI base o la instalación de esta skill no prueban que esa extensión exista. No la instales ni cambies configuración como efecto incidental de ejecutar un análisis.

Si sólo puedes iniciar procesos Pi y el usuario autorizó inferencia, un runner Node puede ejecutar trabajos acotados en procesos aislados, con stdin y argv sin shell, timeout, cancelación y parsing de resultados terminales. Usa el protocolo confirmado por la versión instalada; no escribas un nuevo harness si uno existente ya resuelve el encargo. Cuenta todas las llamadas y los workers anidados. Si no hay delegación utilizable, procesa las unidades en secuencia con el mismo ledger y declara el modo utilizado.

## Descubrimiento de esta skill

En Codex se invoca como `$delegate-map-reduce`. En Pi, con la skill descubierta y los comandos de skills activos, se invoca como `/skill:delegate-map-reduce`. La disponibilidad se determina al cargar o recargar los recursos del harness; los archivos instalados no implican que una sesión ya abierta haya actualizado su catálogo.
