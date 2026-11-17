# plugins

Marketplace de skills de Gerardo Villarroel para Codex, GitHub Copilot CLI y Claude Code. Instala los plugins que corresponden a tu trabajo. Cada uno lleva sus propias skills, scripts y recursos. Puedes editar una variante dentro de su plugin sin cambiar las demás.

[Ver los plugins y las skills que contiene cada uno](docs/catalog.md).

## Instalar desde GitHub

Con una cuenta que tenga acceso a `gvillarroel/plugins`, registra el marketplace una vez en cada cliente. El ejemplo instala `diagram-studio` desde la rama `main`.

| Cliente | Registrar `gvillarroel/plugins` | Instalar `diagram-studio` |
| --- | --- | --- |
| Codex | `codex plugin marketplace add gvillarroel/plugins --ref main` | `codex plugin add diagram-studio@plugins` |
| GitHub Copilot CLI | `copilot plugin marketplace add gvillarroel/plugins` | `copilot plugin install diagram-studio@plugins` |
| Claude Code | `claude plugin marketplace add gvillarroel/plugins` | `claude plugin install diagram-studio@plugins` |

Las utilidades personales también se instalan desde este catálogo. Por ejemplo, `agent-utilities@plugins` contiene `find-skills` y `delegate-map-reduce`, y `workstation-tools@plugins` contiene Playwright y las instrucciones de Google Workspace CLI.

## Trabajar desde un clon

```sh
gh repo clone gvillarroel/plugins
cd plugins
```

Abre una terminal en la raíz de este repositorio. Guarda la ruta absoluta con `$repo = (Get-Location).Path` en PowerShell o `repo="$PWD"` en Bash. Registra el marketplace en el cliente que usas y elige un plugin del catálogo. Este ejemplo instala `diagram-studio`.

| Cliente | Registrar el marketplace | Instalar el plugin |
| --- | --- | --- |
| Codex | `codex plugin marketplace add "$repo"` | `codex plugin add diagram-studio@plugins` |
| GitHub Copilot CLI | `copilot plugin marketplace add "$repo"` | `copilot plugin install diagram-studio@plugins` |
| Claude Code | `claude plugin marketplace add "$repo"` | `claude plugin install diagram-studio@plugins` |

En Claude Code, por ejemplo, `/diagram-studio:mermaid` abre la variante de Mermaid de ese plugin. Para una prueba pequeña en cualquiera de los tres clientes, instala `marketplace-check@plugins` y pide a la skill `shared-example-1` que lea su archivo de prueba.

**Agent Foundry** se ofrece en Copilot CLI. Su comando `/contract` necesita la extensión nativa de Copilot. El paquete incluye esa extensión y su runtime. Para usar sus controles, inicia Copilot con `copilot --experimental`.

Algunos flujos necesitan datos o herramientas del proyecto. Por ejemplo, `editorial-research` consulta los corpus privados del blog desde su checkout, `store-studio` usa el catálogo y los recursos de la tienda activa y `reflex-xy` usa Node y `uv` para renderizar gráficos. Los requisitos de cada flujo están en su `SKILL.md`.

[Mantenimiento, procedencia y pruebas](docs/maintenance.md).
