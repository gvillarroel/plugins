# Curation operations

## Contents

[Catalog](#catalog-and-local-evidence), [alternatives](#concept-alternatives),
[review](#metadata-review-and-publication), [lineage](#synthetic-lineage-and-interfaces).

Prefix the following CLI examples with the owning skill's
`scripts/curator.py run --installation PATH --` through `uv run --script`.
Use the installation's actual state path; do not run from the skill directory.

## Catalog and local evidence

```sh
kc configure --project YOUR-PROJECT --location us-central1
kc inventory
kc search product
kc get projects/YOUR-PROJECT/locations/us-central1/entryGroups/YOUR-GROUP/entries/YOUR-ENTRY
kc configure --allow-root /absolute/data/folder
kc analyze /absolute/data/folder/orders.csv
kc review
kc ui
```

Here `kc` stands for the command passed to the wrapper; omit that leading word
after `--`. `configure --allow-root` replaces the allowed-root list: include all
needed source roots in the same invocation. ADC and gcloud login are separate.
Use the user's intended identity and project; inspect permission failures before
assuming an IAM role is the sole cause. Writes remain disabled by default.

Supported sources: CSV, JSON, TXT, Markdown, text-bearing PDF, and DOCX. Local
analysis uses scikit-learn; RDFLib exports DCAT/Dublin Core/SKOS and pySHACL checks
the bundled retail constraints. Other domains require their own validated
vocabulary and shapes. Profiles contain schema/statistics and interpretation;
source rows and sample values are not uploaded as metadata.

`download-kaggle publisher/dataset` accepts Kaggle handles, retains original
metadata/license/hash evidence and bounds archive extraction. A publisher's
synthetic-data claim is recorded as evidence, not independently certified truth.

## Concept alternatives

Read-only MCP tools:

- `open_ontologies_status`: verify the installed executable and report its pin.
- `compare_taxonomy_with_open_ontologies`: compare an observed saved column with
  up to three locally eligible SKOS concepts through the real native engine.
- `suggest_taxonomy(provider="local")`: explicitly select the local ranker.

Both comparison routes bind the proposal's current revision/digest. Open
Ontologies runs pairwise `--dry-run --scoring informative` comparisons with
`--no-connect`, a private temporary environment and a fixed timeout/output bound.
Scores, informative signals, coverage, ambiguity, version, binary hash and source/
target hashes remain visible as provenance. Coverage is the share of scoring
signal weight, not a probability of correctness. Label-only support is limited
evidence. Raw upstream `requires_review=false` never grants human approval.

The local eligibility policy filters partial multiword aliases, monetary-versus-
quantity conflicts and weak unrelated terms. `product_id` must not gain **Return**
only because **Product return** contains one matching word. Leave a concept
unmapped when evidence is inadequate. The current registered vocabulary is the
bundled retail SKOS corpus; external vocabularies are not automatically fetched.

## Metadata review and publication

Use **Choose → Describe → Check quality → Plan → Decide**. Selecting a candidate
stages an edit; **Save draft** persists a new revision and invalidates approval.
Observed source facts stay protected; editable claims, source quality, privacy
acknowledgments, remote plan and reviewer decisions remain distinct.

```sh
kc history PROPOSAL-ID
kc diff PROPOSAL-ID --from 1
kc export PROPOSAL-ID --format json --output metadata.json
kc export PROPOSAL-ID --format turtle --output metadata.ttl
kc plan PROPOSAL-ID --live
kc ui
```

Exports reject an existing destination. A successful live plan records remote
snapshots and operations for the exact proposal. The person reviews and approves
that revision in the panel. Publication also needs explicit write enablement,
project allowlisting, current source evidence and unchanged remote state. A
multi-call publication is not atomic; partial or unknown effects require
inspection and fresh review. Do not invoke `approve` on behalf of the reviewer.

## Synthetic lineage and interfaces

```sh
kc lineage-demo --seed 42
kc lineage-list
kc lineage-review LINEAGE-ID
kc lineage-history LINEAGE-ID
kc lineage-export LINEAGE-ID --format html --output lineage.html
kc lineage-export LINEAGE-ID --format openlineage --output openlineage.json
```

The seeded exercise generates eight datasets and executes four local recipes,
preserving observed dependencies, hashes, a fixed simulated clock and editable
claims. It starts as an unapproved draft with findings for the reviewer. Use
**Choose → Explore → Check and correct → Decide → Share** to inspect and improve it.
Saved corrections retain history; digest checks reject stale actions. Attaching
approved simulation evidence to metadata is a separate, explicit operation and
invalidates that metadata proposal's approval.

The localhost panel supports human decisions. MCP Apps uses the official host
bridge for supported views/actions. Python HTML snapshots expose exploration and
JSON download but cannot save corrections or approve. The GCP Data Lineage
adapter supports reads and request-plan exports; it does not execute those writes.
Preserve Colorset 1, text labels beside color, keyboard focus and stage disclosure.
