# Mantenimiento

## Editar una variante

Edita `plugins/<plugin>/skills/<skill>/` directamente. Para reutilizarla en otro contexto, copia la carpeta completa al plugin de destino, adapta las instrucciones y revisa los scripts y ejemplos desde ese nuevo contexto. Las copias no se sincronizan automáticamente.

El manifiesto principal de cada plugin es `plugins/<plugin>/plugin.json`. El campo `version` identifica la versión que instala cada cliente. Al distribuir cambios de una skill, aumenta la versión de su plugin. En `marketplace.toml` están el nombre del catálogo y las excepciones de compatibilidad.

Desde la raíz, regenera los catálogos, los manifiestos de compatibilidad y el índice con:

```sh
uv run --script tools/catalog.py --write
uv run --script tools/catalog.py
```

Para añadir un plugin, crea su manifiesto y al menos una carpeta `skills/<nombre>/` con su `SKILL.md`. El generador descubre las carpetas y comprueba que cada nombre coincida con su cabecera YAML. La generación solo escribe manifiestos de compatibilidad, catálogos e índice.

| Cliente | Catálogo del repositorio | Configuración del paquete |
| --- | --- | --- |
| [Codex](https://developers.openai.com/plugins/build/plugins) | `.agents/plugins/marketplace.json` | `plugin.json` y compatibilidad en `.codex-plugin/plugin.json` |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) | `.github/plugin/marketplace.json` | `plugin.json` |
| [Claude Code](https://code.claude.com/docs/en/plugin-marketplaces) | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` |

## Procedencia

El inventario inicial registra 161 copias, 152 nombres de skill y 11 repositorios de `gvillarroel`. [Inventario por plugin y skill](provenance.json).

Cada fila identifica el repositorio, la ruta y el estado en la importación. `committed` proviene de la revisión indicada. `working-tree` incluye cambios locales y `untracked` identifica una skill cuyo archivo principal aún no estaba versionado. `verified-release` identifica las seis variantes del paquete de Line World Video, verificadas contra su manifiesto de distribución. Reflex XY también incorpora los recursos y el servidor de su paquete publicado localmente. Los identificadores de revisión describen el punto de partida de cada checkout. La huella `importSha256` identifica los archivos con los que se inició cada copia, antes de las adaptaciones de este marketplace.

La huella recorre las rutas relativas ordenadas. Para cada archivo incorpora su ruta UTF-8, un byte NUL y los 32 bytes de su SHA-256. Se conservan los avisos de origen y las licencias que acompañan a los paquetes y a sus recursos. El inventario es histórico y puede diferir de una variante editada.

Se incluyeron las carpetas de skills mantenidas en los repositorios, las skills de proyecto en `.agents/skills`, el ejemplo reutilizable de planificación de SDLC y los paquetes seleccionados por los catálogos del repositorio `skills`. Los índices de evaluación, snapshots de candidatos, checkouts temporales e instalaciones de terceros se revisaron como fuentes de contexto. El material de Harbor proviene de tus repositorios. En `mvk-001/skill-arena` la cuenta tenía permiso de escritura y la administración correspondía a otra cuenta.

## Verificar una distribución

La primera prueba ejecuta flujos locales desde un directorio de trabajo independiente. Comprueba las huellas SHA-256 de los recursos, la selección de GIFs, los límites de salida y la composición de una imagen de producto.

```sh
uv run --script tools/test_payloads.py
```

Para probar el registro, instalación y contenido con cada CLI, ejecuta los comandos siguientes desde un clon limpio. Cada prueba crea y limpia un perfil temporal. La opción `--plugin marketplace-check` instala solo el paquete de prueba después de verificar el catálogo completo.

```sh
python tools/test_clients.py codex
python tools/test_clients.py copilot
python tools/test_clients.py claude
```
