# Marketplace maintenance

The main marketplace was renamed from `plugins` to `gvillarroel-plugins`. Register it from `gvillarroel/plugins` and use `<plugin>@gvillarroel-plugins` to install a package. See the [installation guide](../README.md#install-from-github) for client commands.

## Edit or add a plugin

Edit each skill in `plugins/<plugin>/skills/<skill>/`. To use a skill in a different context, copy its entire directory into the destination plugin, adapt the instructions and test its scripts and examples there. Each copy evolves independently.

The main manifest for each plugin is `plugins/<plugin>/plugin.json`. Clients use its `version` when installing the plugin. Increment it when distributing changes, and keep any package manifest that declares the same version in sync. The marketplace name and client compatibility overrides are in `marketplace.toml`.

To add a plugin, create its manifest and at least one `skills/<name>/SKILL.md`. The generator discovers each directory and checks that its name matches the YAML frontmatter. The repository tools use Python 3.11 or later. From the repository root, regenerate and verify the catalogs, compatibility manifests and index.

```sh
uv run --script tools/catalog.py --write
uv run --script tools/catalog.py
```

| Client | Repository catalog | Package configuration |
| --- | --- | --- |
| [Codex](https://developers.openai.com/plugins/build/plugins) | `.agents/plugins/marketplace.json` | `plugin.json` and the `.codex-plugin/plugin.json` compatibility manifest |
| [Claude Code](https://code.claude.com/docs/en/plugin-marketplaces) | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) | `.github/plugin/marketplace.json` | `plugin.json` |
| Pi | Individual package directories in a local clone | The conventional `skills/` directory or an explicit `pi.skills` entry in `package.json` |

## Provenance

The [import inventory](provenance.json) records 169 skill copies with 160 distinct names. The first import brought in 161 copies from 11 repositories owned by `gvillarroel`. Four personal plugins supplied eight more.

| Import state | Meaning |
| --- | --- |
| `committed` | The files came from the recorded Git revision. |
| `working-tree` | The import included local edits from the source checkout. |
| `untracked` | The skill's entry point had yet to be committed at the source. |
| `verified-release` | The six Line World Video variants were checked against their release manifest. |
| `packaged-install` | The path and digest identify a copy from the former personal marketplace. Where available, `upstream.skillBlob` identifies the original Git blob for its `SKILL.md`. |

The repository revisions identify the starting checkout. Each `importSha256` identifies the files as imported, before any changes for this marketplace. To reproduce it, sort the relative file paths and, for each file, hash its UTF-8 path, a NUL byte and the 32 raw bytes of its SHA-256 into the running SHA-256 digest. A later edit to a variant can legitimately produce another digest. Source notices and licenses accompany the relevant packages and resources. Reflex XY also includes the resources and server from its locally published package.

The initial import covered maintained skill directories, project skills in `.agents/skills`, the reusable SDLC planning example and packages selected by the source `skills` repository's catalogs. Evaluation indexes, candidate snapshots, temporary checkouts and third-party installations provided context for the review. The Harbor material came from the owner's repositories. The account had write access to `mvk-001/skill-arena`, which another account administered.

## Verify a release

Run the payload checks from the repository root. They exercise local workflows from a separate working directory, including resource hashes, GIF selection, output bounds and product image composition.

```sh
uv run --script tools/test_payloads.py
```

From a clean clone, run the native client checks. Each creates a temporary profile, registers the marketplace, installs the packages offered to that client and compares the installed files with the checkout. Use `--plugin marketplace-check` to install a single fixture after checking the entire catalog.

```sh
python tools/test_clients.py codex
python tools/test_clients.py claude
python tools/test_clients.py copilot
```

Verify Pi packages separately. The test installs each documented local package into a fresh Pi profile, then checks the discovered `/skill:` commands and their source paths through Pi's RPC interface.

```sh
python tools/test_clients.py pi
```

To test a GitHub installation, start with an up-to-date clone of `main` and credentials that can read the repository. For example, `python tools/test_clients.py codex --source gvillarroel/plugins --plugin agent-utilities` compares the remotely installed plugin with the clone.
