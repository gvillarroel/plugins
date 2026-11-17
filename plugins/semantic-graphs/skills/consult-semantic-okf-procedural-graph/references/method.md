# Procedural Graph Method Contract

The source method is [Procedural Graphs, arXiv:2609.09153v1](https://arxiv.org/html/2609.09153v1),
Sections 3.1–3.3 and Appendix B.6. This package is a consultation adaptation,
not a reproduction of the paper's benchmark results.

The graph stores typed procedures and directed relations with condition,
guidance and pitfalls attributes. Allowed node types are tool, skill, reasoning
and status; relations are LEADS_TO and PROVIDES_INPUT_FOR. `Start` is required.
A terminal is any node with zero outgoing edges, regardless of its name.

Before each solver decision the runtime localizes the exact most recent tool
name, retrieves its directed two-hop induced neighborhood, and requests
situational guidance from the same frozen model. An unmatched action exposes
the full graph. The solver retains all tools and may disregard advice.
The graph file is hash-checked at each decision and cannot evolve online.

Offline edits apply to a copy: delete edges, delete nodes, add nodes, add edges.
Deleting an endpoint pair removes every relation between those endpoints.
Attribute replacement therefore deletes and re-adds the desired edges.
Structural failure avoids a model evaluation. With cycles disabled, DFS removes
cycle-closing edges in stored order before evaluation. Every node must reach
a zero-outdegree terminal. With cycles allowed, no repair runs, but terminal
reachability remains mandatory.

The retained graph has a cached development screen score. A proposed graph is
accepted when its mean complete native Harbor reward is at least that score;
ties are accepted. Rejected proposals and their development traces, edits,
screen scores or structural diagnostics remain available only to the offline
refiner. A rejected graph never becomes the next parent.

The paper's repeatedly consulted validation subset is called a development
screen here. Repository policy requires an additional independent validation
portfolio registered and sealed before evolution. That portfolio opens once,
after a selected candidate is frozen. Its feedback cannot guide further edits
or selection. Historical benchmark cohorts are descriptive evaluation data,
not fresh validation by virtue of their original cohort labels.

The declared runtime uses Python 3.10+ (standard library), Node 22.19+,
`@earendil-works/pi-coding-agent` 1.0.4 and `js-tiktoken` 1.0.21.
The recent-trajectory window preserves the final 4096 `o200k_base` tokens.
This explicit tokenizer is a reproducible window convention; it does not claim
to be the provider's undisclosed exact Luna tokenizer. Each guidance call uses
the latest Luna frozen at study start, medium reasoning, SSE transport and no
provider or application retry/fallback. Automatic solver compaction is disabled.
The Codex provider in this runtime does not emit an output-token limit, even
when the SDK receives maxTokens; requested values must not be reported as an
enforced budget. The episode time limit and decision cap are enforced.
The runtime caps solver decisions at 12 per episode and records both solver
and guidance usage. These model, domain and budget choices differ from the paper.

The kernel does not implement a benchmark scorer. Native Harbor rewards remain
the fitness source. `check_answer` is an agent-visible provenance helper without
semantic gold data. Semantic qualification requires the separately declared
private verifier or independent answer review.
