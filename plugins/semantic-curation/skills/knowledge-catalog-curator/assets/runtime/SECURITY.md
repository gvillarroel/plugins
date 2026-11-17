# Trust and publication boundaries

This tool runs with the local user's permissions. Its approval workflow reduces
publication mistakes and preserves an audit; **it is not operating-system
isolation**. A process able to write program files, `.kc`, or credentials can
modify them. A reviewer name is a local declaration, not a corporate identity
verified by an identity provider.

## Reads and source data

- Analyzed files must lie within `allowed_roots`; paths are resolved before the
  scope check. Parsers bound bytes, rows, columns, pages, and text. Statistics
  from a prefix do not guarantee properties of the whole file.
- Document text and catalog results are untrusted evidence. Extracted code is
  never executed. An instruction inside a CSV, PDF, or description grants no
  approval.
- Profiles do not export rows or sample values. Field names, descriptions,
  findings, and aggregates may also be sensitive; inspect final metadata before
  sending it to GCP.
- Heuristic personal-data detection has false positives and false negatives.
  `privacy_reviewed` records a human decision, not anonymization certification.
  A publisher's synthetic-data claim does not establish absence of personal data.

## Kaggle downloads

The downloader accepts `publisher/dataset`, never an arbitrary URL. It restricts
HTTPS, approved Kaggle and storage hosts, response and extracted-file sizes, and
response read times. It rejects login HTML, invalid ZIPs, absolute and traversal
paths, unsafe Windows names, symbolic links, special files, and name collisions.

Existing versions are not overwritten. Original metadata, declared licenses, and
hashes support provenance and integrity review; they do not establish ownership
or independently authenticate a publisher. Signed storage redirect parameters
are not retained in provenance. An unknown license needs supporting evidence
before publication.

## Human interface and audit

The review server listens only on `127.0.0.1`. Its initial address includes a
temporary capability. API requests require that capability and an expected Host;
mutations also check Origin. The interface renders source content as text and
sets headers preventing embedding in other sites. Do not share its complete
capability URL or expose this server to the network.

Proposals, revisions, and events persist in SQLite under `.kc`. Approval binds
the metadata, plan, validation, and revision digests. An edit invalidates it;
default configuration expires it after 24 hours. MCP exposes no approval tool
and cannot set human privacy or source-quality flags through `revise_metadata`.

These controls address workflow mistakes and ordinary MCP calls. They do not
prevent another process with the same user permissions from altering SQLite,
invoking the CLI, or directly using GCP credentials.

## Lineage and embedded views

Synthetic lineage uses generated CSVs and locally executed recipes. Its fixed
simulation clock, evidence hashes, and observed dependencies remain distinct
from editable claims. Approval verifies the local evidence and exact revision.
Attaching an approved simulation to metadata checks both current digests and
invalidates that metadata proposal's approval; it does not create Data Lineage
resources or assert a relationship to independent Kaggle sources.

MCP Apps views use the host bridge for tool calls. Read-only Python HTML
snapshots cannot persist edits or approve records. The current approval button
opens the human panel on the server machine; remote hosting needs an appropriate
authorized review destination. The repository does not expose a public endpoint
or register an application in a ChatGPT account.

## GCP scope

Writes are disabled by default and require an explicitly allowed project. The
catalog client restricts resources to its configured project and location. A
publication plan lists required supporting resources and exact entry/aspect
operations; plans without verified remote snapshots cannot be published.

The adapter implements no resource deletion, row uploads, IAM changes, or
arbitrary GCP resource editing. Before publication it rechecks remote state,
managed resources, and approved content. The API replaces an aspect as a whole:
fields within the submitted aspect are replaced, while unrelated aspects are
preserved. Conflict checks do not make several GCP calls atomic. Another writer
can act between the final read and write.

A partially completed operation may require remote-state inspection before
retrying. Network errors and pending operations must not be reported as confirmed
success. ADC authenticates the client; the service still requires enabled APIs
and appropriate IAM permissions.

The separate Data Lineage module is **read and export only**. Exported request
plans are never executed by that module. `searchLinks` can return links from all
projects accessible to the identity; its URL project is not a results filter.
Exports retain the complete local graph because GCP ingestion can omit facets,
including custom column-lineage visualization.

## Local information and reporting issues

Do not accidentally include `data/`, `.kc/`, environments, or local execution
artifacts in contributions. Do not include credentials, tokens, original
documents, or logs containing sensitive values when reporting problems.
This local repository has no configured public security-reporting channel;
coordinate disclosure with its owner before publishing details.

## Revision and policy guarantees introduced in 0.2.0

Saved revisions are immutable. History contains only versions the installation
was able to preserve. Observed names, types, statistics, and PII signals stay
protected while semantic interpretation is edited. Actual semantic changes
invalidate human acknowledgments.

New approvals bind the stable quality evaluation and configuration generation.
Approval and publication rerun those checks. New policy, a changed score, or an
older approval without that binding requires a new reviewed and approved
revision. SHACL report formatting and finding order are not semantic changes.

Recovery of interrupted publication is reserved for the human workflow. An
operating-system lock prevents recovery of an active publisher. Recovery does
not determine remote effects or retry requests: it preserves the unknown
outcome, removes approval, and requires a live read and a fresh decision.
