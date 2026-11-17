# Evidence-grounded book interpretation

## Read the edition, then interpret

Record title, author, language, translation/editor when known, source URL or supplied-file identity, and the exact input hash. A quotation belongs to that edition. A translation can change wordplay, recurring vocabulary, and inferred relationships; avoid transferring fine-grained claims between editions without comparison.

Read the requested scope before synthesis. Keep chapter notes that distinguish what happens, who says it, how it is narrated, and why it might matter. Do not replace whole-book reading with keyword hits. Retrieval can help revisit candidate passages after reading, but a retrieved subset supports only the stated subset unless broader review actually occurred.

The parser normalizes paragraph whitespace for stable display and citation matching. Preserve the original file separately. If input contains poorly extracted columns, recurring headers, unmarked chapter boundaries, or OCR damage, repair or label the affected scope before analysis. Chapter coverage declarations are auditable metadata, not proof of comprehension.

## Claims that deserve a place

Prefer a few specific propositions over a long inventory of nouns. A theme names a recurring concern; a claim says something about how the text develops it. Distinguish:

- **Observation:** a verifiable feature of the supplied text, such as repeated questioning or a particular speaker changing a rule.
- **Interpretation:** an explanation of the feature's role, significance, tension, or change.
- **External assertion:** a claim about the author, history, psychology, or reception that requires additional evidence beyond this book.

For fiction, test perspective and irony: a villain's assertion is not automatically the narrator's endorsement, and the narrator's phrasing does not automatically establish the author's intention. Preserve ambiguity when competing readings remain possible. Track developments and reversals rather than treating every recurrence as identical.

For nonfiction, separate thesis from examples, warrants from unsupported assertion, descriptive generalizations from prescriptions, and the author's position from a quoted opponent. A documented author's claim need not be true in the world. Explain that distinction when evidence supports attribution rather than factual correctness.

Do not turn fiction into a productivity manual by default. Do not convert nonfiction into character analysis when the user wants its argument. The user's question and the book's genre determine the emphasis.

## Evidence and challenges

Attach at least one supporting passage per claim. Prefer two separated passages for a claim about change or recurrence across a book. A single scene may support a local reading; it rarely establishes an unqualified claim about the whole book.

Use short exact substrings from normalized paragraph text, including punctuation. Create separate evidence entries for discontinuous selections. State the inferential connection in `rationale`; a matching keyword is not enough. Provide full cited paragraph context in the explorer so the reader can challenge quote selection.

Seek a serious competing explanation and a contrary or limiting passage. A useful alternative changes the inference, rather than restating it with synonyms. For example, a speech might demonstrate personal conviction, perform compliance with an authority, or satirize a familiar formula; the surrounding narration helps discriminate these readings. Label this as a generic illustration, never as evidence from the user's book.

Use confidence labels consistently:

- `strong`: directly supported in the declared scope, with the main qualification addressed.
- `plausible`: supported interpretation with a meaningful unresolved alternative.
- `tentative`: limited, ambiguous, or locally supported inference requiring further reading.

These labels are editorial judgments. Do not calculate them from word counts or present them as calibrated accuracy.

## Semantic relations and display

Use an edge between claims only when it adds explanatory value. Follow the exact direction conventions in [data-contract.md](data-contract.md): `supports` strengthens the target; `complicates` qualifies it; `develops` reads source **develops into** target; `contrasts` is a symmetric juxtaposition. State why the type applies to the actual endpoint propositions, with exact passage evidence. Do not label supportive evidence as a complication of an imagined stronger claim. Avoid decorative all-to-all networks and unsupported causal arrows.

For a visual semantic exploration request, start with a visible graph linked to inspectable evidence. Draw claims as selectable nodes, organize them by theme, and distinguish grouping from the typed semantic edges. Use the supplied analysis IDs and evidence; a diagram must not introduce new interpretation merely to fill space. Keep nodes without semantic edges visible, and explain an empty relationship set without fabricating connections.

Use a stable, measured layout rather than an uncontrolled force simulation for a small book map. Give each node a compact meaningful `label` and show its full proposition on selection. Avoid automatically cutting every claim after its opening words: a map of indistinct sentence prefixes carries little semantic information. Let selecting an edge reveal its direction, rationale and exact evidence, with access to both endpoint claims. Synchronize the graph, selectors, evidence and saved selection. Keep the first graph state useful without requiring a menu search. On narrow screens, reflow or use focused neighborhoods with clear access to all claims; never shrink a desktop canvas until its text becomes unreadable. Use native keyboard/touch controls, visible focus and tap-accessible evidence. Do not require hover or dragging for essential access.

Add a second diagram only when it answers another real reading question. A chapter-by-theme matrix can show where cited evidence occurs; a directed claim map shows interpretive relations. Keep these meanings distinct. Counts in a matrix or chapter table describe distinct cited paragraphs, not semantic importance, proof that a theme is absent, or evidence that the model read the entire book. Do not label such a matrix as an embedding, similarity model or causal graph.

For screenshot review, compare a graph with all nodes against a selected-node and selected-edge state, including an unconnected node and the empty-edge case. Inspect 320-pixel and normal-width layouts in light/dark appearance. Reject hidden graphs, unusable labels, overlapping hit targets, arbitrary connections, and edges whose displayed relation disagrees with the underlying data even if the HTML and citation checker pass.

Review source grounding and reasoning separately. A structurally valid graph can contain a bad inference. Before delivery, inspect the most general claim, the most uncertain claim, and a claim whose passage could support an alternative. Record what was revised and what remains uncertain.
