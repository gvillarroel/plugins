# gvillarroel-plugins plugin catalog

Register the marketplace once in your client using the [installation guide](../README.md#install-from-github). Run Pi commands from the root of a local clone. Each skill link opens the version shipped by that plugin.

## agent-foundry

Manage a declarative user bench, current-folder profiles, disposable subagents, and trusted skill references.

| Client | Install command |
| --- | --- |
| GitHub Copilot CLI | `copilot plugin install agent-foundry@gvillarroel-plugins` |

**Skills**

- [contract](../plugins/agent-foundry/skills/contract/SKILL.md)

## agent-utilities

Discover plugins, coordinate multi-source research and refactor complex methods.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add agent-utilities@gvillarroel-plugins` |
| Claude Code | `claude plugin install agent-utilities@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install agent-utilities@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/agent-utilities` |

**Skills**

- [delegate-map-reduce](../plugins/agent-utilities/skills/delegate-map-reduce/SKILL.md)
- [find-skills](../plugins/agent-utilities/skills/find-skills/SKILL.md)
- [refactor-method-complexity-reduce](../plugins/agent-utilities/skills/refactor-method-complexity-reduce/SKILL.md)

## cloud-operations

Work with GCS user access, Google Cloud SKU pricing and evaluation datasets for GCP Radar.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add cloud-operations@gvillarroel-plugins` |
| Claude Code | `claude plugin install cloud-operations@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install cloud-operations@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/cloud-operations` |

**Skills**

- [gcs-user-access](../plugins/cloud-operations/skills/gcs-user-access/SKILL.md)
- [google-cloud-sku-pricing](../plugins/cloud-operations/skills/google-cloud-sku-pricing/SKILL.md)
- [harbor-author-evaluation-datasets](../plugins/cloud-operations/skills/harbor-author-evaluation-datasets/SKILL.md)

## confluence-publishing

Prepare Markdown for Confluence and round-trip pages with their attachments and formatting.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add confluence-publishing@gvillarroel-plugins` |
| Claude Code | `claude plugin install confluence-publishing@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install confluence-publishing@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/confluence-publishing` |

**Skills**

- [md2conf](../plugins/confluence-publishing/skills/md2conf/SKILL.md)
- [roundtrip-confluence-pages](../plugins/confluence-publishing/skills/roundtrip-confluence-pages/SKILL.md)

## data-simulation

Plan, generate and evaluate synthetic tabular datasets, build simulations and test their quality and privacy.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add data-simulation@gvillarroel-plugins` |
| Claude Code | `claude plugin install data-simulation@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install data-simulation@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/data-simulation` |

**Skills**

- [evaluate-synthetic-data](../plugins/data-simulation/skills/evaluate-synthetic-data/SKILL.md)
- [generate-synthetic-data](../plugins/data-simulation/skills/generate-synthetic-data/SKILL.md)
- [harbor-author-evaluation-datasets](../plugins/data-simulation/skills/harbor-author-evaluation-datasets/SKILL.md)
- [plan-synthetic-data](../plugins/data-simulation/skills/plan-synthetic-data/SKILL.md)
- [run-synthetic-data-workflow](../plugins/data-simulation/skills/run-synthetic-data-workflow/SKILL.md)
- [simulation-data-lab](../plugins/data-simulation/skills/simulation-data-lab/SKILL.md)

## delivery-planning

Extract requirements, review assumptions, plan delivery and construct project-specific Harbor evaluation datasets.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add delivery-planning@gvillarroel-plugins` |
| Claude Code | `claude plugin install delivery-planning@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install delivery-planning@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/delivery-planning` |

**Skills**

- [build-delivery-plan](../plugins/delivery-planning/skills/build-delivery-plan/SKILL.md)
- [challenge-assumptions](../plugins/delivery-planning/skills/challenge-assumptions/SKILL.md)
- [extract-requirements](../plugins/delivery-planning/skills/extract-requirements/SKILL.md)
- [harbor-author-evaluation-datasets](../plugins/delivery-planning/skills/harbor-author-evaluation-datasets/SKILL.md)

## design-assets

Find licensed visual assets, stock footage, textures, icons and technical logos for creative projects.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add design-assets@gvillarroel-plugins` |
| Claude Code | `claude plugin install design-assets@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install design-assets@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/design-assets` |

**Skills**

- [ambientcg-material-search](../plugins/design-assets/skills/ambientcg-material-search/SKILL.md)
- [destockd-video-search](../plugins/design-assets/skills/destockd-video-search/SKILL.md)
- [iconify-icon-search](../plugins/design-assets/skills/iconify-icon-search/SKILL.md)
- [kenney-asset-search](../plugins/design-assets/skills/kenney-asset-search/SKILL.md)
- [pexels-media-search](../plugins/design-assets/skills/pexels-media-search/SKILL.md)
- [polyhaven-asset-search](../plugins/design-assets/skills/polyhaven-asset-search/SKILL.md)
- [technical-logo-assets](../plugins/design-assets/skills/technical-logo-assets/SKILL.md)

## diagram-studio

Compose and animate diagrams, charts and SVGs with D3, Mermaid, PlantUML, ECharts and Lucidchart.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add diagram-studio@gvillarroel-plugins` |
| Claude Code | `claude plugin install diagram-studio@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install diagram-studio@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/diagram-studio` |

**Skills**

- [compose-synchronized-svg](../plugins/diagram-studio/skills/compose-synchronized-svg/SKILL.md)
- [d3](../plugins/diagram-studio/skills/d3/SKILL.md)
- [diagram-composition](../plugins/diagram-studio/skills/diagram-composition/SKILL.md)
- [echarts-animated-svg](../plugins/diagram-studio/skills/echarts-animated-svg/SKILL.md)
- [hierarchy-lens](../plugins/diagram-studio/skills/hierarchy-lens/SKILL.md)
- [lucidchart-svg](../plugins/diagram-studio/skills/lucidchart-svg/SKILL.md)
- [mermaid](../plugins/diagram-studio/skills/mermaid/SKILL.md)
- [plantuml-colorset-renderer](../plugins/diagram-studio/skills/plantuml-colorset-renderer/SKILL.md)
- [procedural-svg-animation](../plugins/diagram-studio/skills/procedural-svg-animation/SKILL.md)
- [svg-brief-design](../plugins/diagram-studio/skills/svg-brief-design/SKILL.md)
- [usefulcharts-style](../plugins/diagram-studio/skills/usefulcharts-style/SKILL.md)

## editorial-research

Find reaction GIFs and consult the blog workspace's verified expert sources while drafting articles.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add editorial-research@gvillarroel-plugins` |
| Claude Code | `claude plugin install editorial-research@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install editorial-research@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/editorial-research` |

**Skills**

- [choose-contextual-gif](../plugins/editorial-research/skills/choose-contextual-gif/SKILL.md)
- [consult-expert-knowledge](../plugins/editorial-research/skills/consult-expert-knowledge/SKILL.md)

## harbor

Author evaluation datasets, organize and report native Harbor studies, recover external failures, and improve complete skills with controlled evolution and independent validation.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add harbor@gvillarroel-plugins` |
| Claude Code | `claude plugin install harbor@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install harbor@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/harbor` |

**Skills**

- [harbor-author-evaluation-datasets](../plugins/harbor/skills/harbor-author-evaluation-datasets/SKILL.md)
- [harbor-evolve-skill](../plugins/harbor/skills/harbor-evolve-skill/SKILL.md)
- [harbor-maximize-knowledge-expertise](../plugins/harbor/skills/harbor-maximize-knowledge-expertise/SKILL.md)
- [harbor-metaskill-evolution](../plugins/harbor/skills/harbor-metaskill-evolution/SKILL.md)
- [harbor-operator-coevolution](../plugins/harbor/skills/harbor-operator-coevolution/SKILL.md)
- [harbor-organize-evaluations](../plugins/harbor/skills/harbor-organize-evaluations/SKILL.md)
- [harbor-population-search](../plugins/harbor/skills/harbor-population-search/SKILL.md)
- [harbor-realize-skill-candidate](../plugins/harbor/skills/harbor-realize-skill-candidate/SKILL.md)
- [harbor-reflective-pareto-search](../plugins/harbor/skills/harbor-reflective-pareto-search/SKILL.md)
- [harbor-resume-external-failures](../plugins/harbor/skills/harbor-resume-external-failures/SKILL.md)
- [harbor-run-results](../plugins/harbor/skills/harbor-run-results/SKILL.md)
- [harbor-trace-distillation](../plugins/harbor/skills/harbor-trace-distillation/SKILL.md)

## hyperframes

Compose and render HTML video using HyperFrames by HeyGen and the project Colorsets.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add hyperframes@gvillarroel-plugins` |
| Claude Code | `claude plugin install hyperframes@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install hyperframes@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/hyperframes` |

**Skills**

- [colorsets](../plugins/hyperframes/skills/colorsets/SKILL.md)
- [hyperframes](../plugins/hyperframes/skills/hyperframes/SKILL.md)
- [hyperframes-cli](../plugins/hyperframes/skills/hyperframes-cli/SKILL.md)
- [hyperframes-registry](../plugins/hyperframes/skills/hyperframes-registry/SKILL.md)
- [media-use](../plugins/hyperframes/skills/media-use/SKILL.md)

## knowledge-authoring

Build expert skills and knowledge bundles, extract ontologies and review methodology against its bundled research corpus.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add knowledge-authoring@gvillarroel-plugins` |
| Claude Code | `claude plugin install knowledge-authoring@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install knowledge-authoring@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/knowledge-authoring` |

**Skills**

- [build-classical-chunked-knowledge-skill](../plugins/knowledge-authoring/skills/build-classical-chunked-knowledge-skill/SKILL.md)
- [build-classical-knowledge-skill](../plugins/knowledge-authoring/skills/build-classical-knowledge-skill/SKILL.md)
- [build-semantic-okf-knowledge-skill](../plugins/knowledge-authoring/skills/build-semantic-okf-knowledge-skill/SKILL.md)
- [build-specialized-skill](../plugins/knowledge-authoring/skills/build-specialized-skill/SKILL.md)
- [extract-ontologies](../plugins/knowledge-authoring/skills/extract-ontologies/SKILL.md)
- [harbor-author-evaluation-datasets](../plugins/knowledge-authoring/skills/harbor-author-evaluation-datasets/SKILL.md)
- [open-knowledge-format](../plugins/knowledge-authoring/skills/open-knowledge-format/SKILL.md)
- [review-knowledge-methodology](../plugins/knowledge-authoring/skills/review-knowledge-methodology/SKILL.md)

## knowledge-tools

Register, index and search knowledge with know, XERJ, OpenWiki, Open Ontologies and Television.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add knowledge-tools@gvillarroel-plugins` |
| Claude Code | `claude plugin install knowledge-tools@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install knowledge-tools@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/knowledge-tools` |

**Skills**

- [know](../plugins/knowledge-tools/skills/know/SKILL.md)
- [open-ontologies](../plugins/knowledge-tools/skills/open-ontologies/SKILL.md)
- [openwiki-knowledge](../plugins/knowledge-tools/skills/openwiki-knowledge/SKILL.md)
- [television](../plugins/knowledge-tools/skills/television/SKILL.md)
- [xerj](../plugins/knowledge-tools/skills/xerj/SKILL.md)

## layers-evaluation

Author and audit Harbor evaluation datasets for the Layers workspace.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add layers-evaluation@gvillarroel-plugins` |
| Claude Code | `claude plugin install layers-evaluation@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install layers-evaluation@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/layers-evaluation` |

**Skills**

- [harbor-author-evaluation-datasets](../plugins/layers-evaluation/skills/harbor-author-evaluation-datasets/SKILL.md)

## line-world

Create and edit narrated explainers with measured attention, source-based charts, portraits, original illustrations and filmed scenes. Generate voices and effects, edit Google Vids and verify the exported MP4.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add line-world@gvillarroel-plugins` |
| Claude Code | `claude plugin install line-world@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install line-world@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/line-world` |

**Skills**

- [animated-svg-to-gif](../plugins/line-world/skills/animated-svg-to-gif/SKILL.md)
- [asciinema-real-command-video](../plugins/line-world/skills/asciinema-real-command-video/SKILL.md)
- [colorsets](../plugins/line-world/skills/colorsets/SKILL.md)
- [hyperframes-explainer](../plugins/line-world/skills/hyperframes-explainer/SKILL.md)
- [line-world-d3](../plugins/line-world/skills/line-world-d3/SKILL.md)
- [line-world-google-vids](../plugins/line-world/skills/line-world-google-vids/SKILL.md)
- [line-world-hyperframes](../plugins/line-world/skills/line-world-hyperframes/SKILL.md)
- [line-world-icons](../plugins/line-world/skills/line-world-icons/SKILL.md)
- [line-world-images](../plugins/line-world/skills/line-world-images/SKILL.md)
- [line-world-mermaid](../plugins/line-world/skills/line-world-mermaid/SKILL.md)
- [line-world-motion-direction](../plugins/line-world/skills/line-world-motion-direction/SKILL.md)
- [line-world-sound](../plugins/line-world/skills/line-world-sound/SKILL.md)
- [line-world-video](../plugins/line-world/skills/line-world-video/SKILL.md)
- [manim-svg-video](../plugins/line-world/skills/manim-svg-video/SKILL.md)
- [media-use](../plugins/line-world/skills/media-use/SKILL.md)
- [pydub-audio](../plugins/line-world/skills/pydub-audio/SKILL.md)
- [pydub-projects](../plugins/line-world/skills/pydub-projects/SKILL.md)
- [reference-motion](../plugins/line-world/skills/reference-motion/SKILL.md)
- [video](../plugins/line-world/skills/video/SKILL.md)
- [video-style-reverse-engineering](../plugins/line-world/skills/video-style-reverse-engineering/SKILL.md)

## local-pdf

Create, inspect and visually verify PDFs with the workstation PDF workflow.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add local-pdf@gvillarroel-plugins` |
| Claude Code | `claude plugin install local-pdf@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install local-pdf@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/local-pdf` |

**Skills**

- [pdf](../plugins/local-pdf/skills/pdf/SKILL.md)

## marketplace-check

Verify that installed skills can read the proof files shipped in their own package.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add marketplace-check@gvillarroel-plugins` |
| Claude Code | `claude plugin install marketplace-check@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install marketplace-check@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/marketplace-check` |

**Skills**

- [shared-example-1](../plugins/marketplace-check/skills/shared-example-1/SKILL.md)
- [shared-example-2](../plugins/marketplace-check/skills/shared-example-2/SKILL.md)
- [shared-example-3](../plugins/marketplace-check/skills/shared-example-3/SKILL.md)

## material-ui

Build Material UI components and themes.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add material-ui@gvillarroel-plugins` |
| Claude Code | `claude plugin install material-ui@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install material-ui@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/material-ui` |

**Skills**

- [mui](../plugins/material-ui/skills/mui/SKILL.md)

## plugin-authoring

Design agent plugin interfaces and MCP Apps, and author evaluation datasets in the marketplace development context.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add plugin-authoring@gvillarroel-plugins` |
| Claude Code | `claude plugin install plugin-authoring@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install plugin-authoring@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/plugin-authoring` |

**Skills**

- [chatgpt-desktop-plugin-ui](../plugins/plugin-authoring/skills/chatgpt-desktop-plugin-ui/SKILL.md)
- [code-native-plugin-ui](../plugins/plugin-authoring/skills/code-native-plugin-ui/SKILL.md)
- [codex-plugin-ui](../plugins/plugin-authoring/skills/codex-plugin-ui/SKILL.md)
- [desktop-chat-plugin-ui](../plugins/plugin-authoring/skills/desktop-chat-plugin-ui/SKILL.md)
- [desktop-plugin-ui](../plugins/plugin-authoring/skills/desktop-plugin-ui/SKILL.md)
- [gemini-enterprise-ui](../plugins/plugin-authoring/skills/gemini-enterprise-ui/SKILL.md)
- [harbor-author-evaluation-datasets](../plugins/plugin-authoring/skills/harbor-author-evaluation-datasets/SKILL.md)
- [pi-extension-ui](../plugins/plugin-authoring/skills/pi-extension-ui/SKILL.md)

## presentation-studio

Build and audit Slidev presentations or transfer D3 graphics into editable Google Slides.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add presentation-studio@gvillarroel-plugins` |
| Claude Code | `claude plugin install presentation-studio@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install presentation-studio@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/presentation-studio` |

**Skills**

- [d3-google-slides](../plugins/presentation-studio/skills/d3-google-slides/SKILL.md)
- [slidev-animejs](../plugins/presentation-studio/skills/slidev-animejs/SKILL.md)
- [slidev-echarts](../plugins/presentation-studio/skills/slidev-echarts/SKILL.md)
- [slidev-quality-audit](../plugins/presentation-studio/skills/slidev-quality-audit/SKILL.md)

## reflex-xy

Create interactive Python XY charts with a local MCP renderer and standalone HTML export.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add reflex-xy@gvillarroel-plugins` |
| Claude Code | `claude plugin install reflex-xy@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install reflex-xy@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/reflex-xy` |

**Skills**

- [reflex-xy](../plugins/reflex-xy/skills/reflex-xy/SKILL.md)

## semantic-curation

Curate semantic models, extract ontologies and map evidence to knowledge catalogs, book analysis and question indexes.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add semantic-curation@gvillarroel-plugins` |
| Claude Code | `claude plugin install semantic-curation@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install semantic-curation@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/semantic-curation` |

**Skills**

- [book-semantic-analysis](../plugins/semantic-curation/skills/book-semantic-analysis/SKILL.md)
- [curate-semantic-model](../plugins/semantic-curation/skills/curate-semantic-model/SKILL.md)
- [extract-ontologies](../plugins/semantic-curation/skills/extract-ontologies/SKILL.md)
- [extract-with-ontology](../plugins/semantic-curation/skills/extract-with-ontology/SKILL.md)
- [index-knowledge-questions](../plugins/semantic-curation/skills/index-knowledge-questions/SKILL.md)
- [knowledge-catalog-curator](../plugins/semantic-curation/skills/knowledge-catalog-curator/SKILL.md)

## semantic-graphs

Build and query graph-based Semantic OKF snapshots, including entity graphs, Graphify and procedural graphs.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add semantic-graphs@gvillarroel-plugins` |
| Claude Code | `claude plugin install semantic-graphs@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install semantic-graphs@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/semantic-graphs` |

**Skills**

- [build-semantic-okf-entity-graph](../plugins/semantic-graphs/skills/build-semantic-okf-entity-graph/SKILL.md)
- [build-semantic-okf-graphify](../plugins/semantic-graphs/skills/build-semantic-okf-graphify/SKILL.md)
- [build-semantic-okf-graphify-next](../plugins/semantic-graphs/skills/build-semantic-okf-graphify-next/SKILL.md)
- [build-semantic-okf-harbor-graphify](../plugins/semantic-graphs/skills/build-semantic-okf-harbor-graphify/SKILL.md)
- [consult-semantic-okf-entity-graph](../plugins/semantic-graphs/skills/consult-semantic-okf-entity-graph/SKILL.md)
- [consult-semantic-okf-graphify](../plugins/semantic-graphs/skills/consult-semantic-okf-graphify/SKILL.md)
- [consult-semantic-okf-harbor-entity-graph](../plugins/semantic-graphs/skills/consult-semantic-okf-harbor-entity-graph/SKILL.md)
- [consult-semantic-okf-harbor-graphify](../plugins/semantic-graphs/skills/consult-semantic-okf-harbor-graphify/SKILL.md)
- [consult-semantic-okf-procedural-graph](../plugins/semantic-graphs/skills/consult-semantic-okf-procedural-graph/SKILL.md)

## semantic-okf

Build, consult and visualize Semantic OKF snapshots with classical, adaptive, embedding and ensemble retrieval.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add semantic-okf@gvillarroel-plugins` |
| Claude Code | `claude plugin install semantic-okf@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install semantic-okf@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/semantic-okf` |

**Skills**

- [build-semantic-okf](../plugins/semantic-okf/skills/build-semantic-okf/SKILL.md)
- [build-semantic-okf-adaptive](../plugins/semantic-okf/skills/build-semantic-okf-adaptive/SKILL.md)
- [build-semantic-okf-classical](../plugins/semantic-okf/skills/build-semantic-okf-classical/SKILL.md)
- [build-semantic-okf-embeddings](../plugins/semantic-okf/skills/build-semantic-okf-embeddings/SKILL.md)
- [build-semantic-okf-ensemble](../plugins/semantic-okf/skills/build-semantic-okf-ensemble/SKILL.md)
- [consult-semantic-okf](../plugins/semantic-okf/skills/consult-semantic-okf/SKILL.md)
- [consult-semantic-okf-adaptive](../plugins/semantic-okf/skills/consult-semantic-okf-adaptive/SKILL.md)
- [consult-semantic-okf-classical](../plugins/semantic-okf/skills/consult-semantic-okf-classical/SKILL.md)
- [consult-semantic-okf-embeddings](../plugins/semantic-okf/skills/consult-semantic-okf-embeddings/SKILL.md)
- [consult-semantic-okf-ensemble](../plugins/semantic-okf/skills/consult-semantic-okf-ensemble/SKILL.md)
- [consult-semantic-okf-harbor-adaptive](../plugins/semantic-okf/skills/consult-semantic-okf-harbor-adaptive/SKILL.md)
- [consult-semantic-okf-harbor-classical](../plugins/semantic-okf/skills/consult-semantic-okf-harbor-classical/SKILL.md)
- [consult-semantic-okf-harbor-embeddings](../plugins/semantic-okf/skills/consult-semantic-okf-harbor-embeddings/SKILL.md)
- [consult-semantic-okf-harbor-ensemble](../plugins/semantic-okf/skills/consult-semantic-okf-harbor-ensemble/SKILL.md)
- [consult-semantic-okf-harbor-legacy](../plugins/semantic-okf/skills/consult-semantic-okf-harbor-legacy/SKILL.md)
- [visualize-semantic-okf-classical](../plugins/semantic-okf/skills/visualize-semantic-okf-classical/SKILL.md)

## semantic-search

Build and query knowledge snapshots with Tantivy, Turso, Tika and RustMallet search backends.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add semantic-search@gvillarroel-plugins` |
| Claude Code | `claude plugin install semantic-search@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install semantic-search@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/semantic-search` |

**Skills**

- [build-semantic-okf-rust-mallet](../plugins/semantic-search/skills/build-semantic-okf-rust-mallet/SKILL.md)
- [build-semantic-okf-rust-mallet-evolved](../plugins/semantic-search/skills/build-semantic-okf-rust-mallet-evolved/SKILL.md)
- [build-semantic-okf-tantivy](../plugins/semantic-search/skills/build-semantic-okf-tantivy/SKILL.md)
- [build-semantic-okf-tika-mallet](../plugins/semantic-search/skills/build-semantic-okf-tika-mallet/SKILL.md)
- [build-semantic-okf-turso](../plugins/semantic-search/skills/build-semantic-okf-turso/SKILL.md)
- [consult-semantic-okf-rust-mallet](../plugins/semantic-search/skills/consult-semantic-okf-rust-mallet/SKILL.md)
- [consult-semantic-okf-rust-mallet-evolved](../plugins/semantic-search/skills/consult-semantic-okf-rust-mallet-evolved/SKILL.md)
- [consult-semantic-okf-tantivy](../plugins/semantic-search/skills/consult-semantic-okf-tantivy/SKILL.md)
- [consult-semantic-okf-tika-mallet](../plugins/semantic-search/skills/consult-semantic-okf-tika-mallet/SKILL.md)
- [consult-semantic-okf-tika-mallet-bounded](../plugins/semantic-search/skills/consult-semantic-okf-tika-mallet-bounded/SKILL.md)
- [consult-semantic-okf-tika-mallet-tantivy](../plugins/semantic-search/skills/consult-semantic-okf-tika-mallet-tantivy/SKILL.md)
- [consult-semantic-okf-turso](../plugins/semantic-search/skills/consult-semantic-okf-turso/SKILL.md)

## store-studio

Prepare, critique and market print-on-demand products with artwork, photoshoots and Printify workflows.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add store-studio@gvillarroel-plugins` |
| Claude Code | `claude plugin install store-studio@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install store-studio@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/store-studio` |

**Skills**

- [create-printify-product](../plugins/store-studio/skills/create-printify-product/SKILL.md)
- [create-shirt-product](../plugins/store-studio/skills/create-shirt-product/SKILL.md)
- [design-store-graphics](../plugins/store-studio/skills/design-store-graphics/SKILL.md)
- [higgsfield-generate](../plugins/store-studio/skills/higgsfield-generate/SKILL.md)
- [higgsfield-product-photoshoot](../plugins/store-studio/skills/higgsfield-product-photoshoot/SKILL.md)
- [marketing](../plugins/store-studio/skills/marketing/SKILL.md)
- [optimize-printify-product](../plugins/store-studio/skills/optimize-printify-product/SKILL.md)
- [product-design-critic](../plugins/store-studio/skills/product-design-critic/SKILL.md)
- [rapid-image-prototype](../plugins/store-studio/skills/rapid-image-prototype/SKILL.md)

## video-production

Plan and produce mixed-media videos with motion graphics, screen recordings, audio and delivery through Google Vids.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add video-production@gvillarroel-plugins` |
| Claude Code | `claude plugin install video-production@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install video-production@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/video-production` |

**Skills**

- [animated-svg-to-gif](../plugins/video-production/skills/animated-svg-to-gif/SKILL.md)
- [asciinema-real-command-video](../plugins/video-production/skills/asciinema-real-command-video/SKILL.md)
- [hyperframes-explainer](../plugins/video-production/skills/hyperframes-explainer/SKILL.md)
- [line-world-google-vids](../plugins/video-production/skills/line-world-google-vids/SKILL.md)
- [line-world-video](../plugins/video-production/skills/line-world-video/SKILL.md)
- [manim-svg-video](../plugins/video-production/skills/manim-svg-video/SKILL.md)
- [pydub-audio](../plugins/video-production/skills/pydub-audio/SKILL.md)
- [pydub-projects](../plugins/video-production/skills/pydub-projects/SKILL.md)
- [video](../plugins/video-production/skills/video/SKILL.md)
- [video-style-reverse-engineering](../plugins/video-production/skills/video-style-reverse-engineering/SKILL.md)

## visual-effects

Create 3D scenes, pixel art, vector patterns and image effects using Three.js, Kornia and SVG.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add visual-effects@gvillarroel-plugins` |
| Claude Code | `claude plugin install visual-effects@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install visual-effects@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/visual-effects` |

**Skills**

- [kornia-artistic-transforms](../plugins/visual-effects/skills/kornia-artistic-transforms/SKILL.md)
- [one-bit-dither-svg](../plugins/visual-effects/skills/one-bit-dither-svg/SKILL.md)
- [pixel-art-image-video](../plugins/visual-effects/skills/pixel-art-image-video/SKILL.md)
- [threejs-animated-3d](../plugins/visual-effects/skills/threejs-animated-3d/SKILL.md)
- [vectorize-art-patterns](../plugins/visual-effects/skills/vectorize-art-patterns/SKILL.md)

## workflow-engineering

Author ZX and Pi workflows, durable agent applications, repository reviewers and batch decisions.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add workflow-engineering@gvillarroel-plugins` |
| Claude Code | `claude plugin install workflow-engineering@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install workflow-engineering@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/workflow-engineering` |

**Skills**

- [jev-batch-decisions](../plugins/workflow-engineering/skills/jev-batch-decisions/SKILL.md)
- [pi-durable](../plugins/workflow-engineering/skills/pi-durable/SKILL.md)
- [pi-mentor](../plugins/workflow-engineering/skills/pi-mentor/SKILL.md)
- [repository-reviewer-creator](../plugins/workflow-engineering/skills/repository-reviewer-creator/SKILL.md)
- [zx-workflow-author](../plugins/workflow-engineering/skills/zx-workflow-author/SKILL.md)

## workstation-tools

Operate Google Workspace from the command line, automate browsers and produce HTML animation videos.

| Client | Install command |
| --- | --- |
| Codex | `codex plugin add workstation-tools@gvillarroel-plugins` |
| Claude Code | `claude plugin install workstation-tools@gvillarroel-plugins` |
| GitHub Copilot CLI | `copilot plugin install workstation-tools@gvillarroel-plugins` |
| Pi (skills) | `pi install ./plugins/workstation-tools` |

**Skills**

- [gws-shared](../plugins/workstation-tools/skills/gws-shared/SKILL.md)
- [html-d3-anime-video-workflow](../plugins/workstation-tools/skills/html-d3-anime-video-workflow/SKILL.md)
- [playwright](../plugins/workstation-tools/skills/playwright/SKILL.md)
