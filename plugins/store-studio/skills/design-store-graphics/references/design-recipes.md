# Design recipes for IA Referencias

Resolve `shared/`, `stores/` and `docs/` paths from the store project's root. Read the recipe that fits the brief. These are the store's adaptations. DGH IDs identify the observations that informed them. [Video notes](dgh-video-notes.md)

## A. Lead with the phrase — `vector-icon-text`

Use this family when the phrase carries the joke and a symbol can clarify it. DGH-01 and DGH-02 illustrate hierarchy. DGH-08 shows how to give an accent a specific purpose.

1. Identify the word or relationship that changes the meaning. Write the exact text before drawing and decide where the punchline should land.
2. Build an unframed stacked composition. Adjust line breaks, optical width, leading and weight contrast. Derive margins from the surface.
3. Try a compact emblem that groups the words. If its outline forces the phrase to shrink, open or remove the outline.
4. Try a symbol or UI fragment that completes the contradiction. Keep the relevant control or state. Integrate a symbol into a letter only if readers can still recognize the letter.
5. Compare all three on the same surface. Apply color to the element that carries meaning and check that the phrase still reads without it.

**Illustrative study.** Try `HUMAN OVERRIDE` with the response `DENIED`. Variant A can emphasize the response below the headline, B can use a stamp and C can show one disabled override control. Compare whether the symbol adds meaning or repeats the words. This example has no product approval attached.

Check kerning, open counters, punctuation, meaningful line breaks, exact wording and icon balance. If only the first word reads in the thumbnail, correct the hierarchy before adding effects.

## B. Bring two images together — `segmented-photo-collage`

Use this family when two objects or scenes make the contradiction visible. DGH-04 and DGH-05 inform integration and framing. DGH-03 informs texture.

1. State the visual relationship, such as a digital promise alongside a physical consequence. Choose a lead image and the fewest supporting elements needed.
2. Compare crops and orientations before committing to a photograph. Check its provenance and usable resolution at the final scale.
3. Build editable masks. Inspect hair, holes, thin objects and edges against light and dark backgrounds. Keep the original for mask repairs.
4. Vary scale, overlap and negative space using the same assets. Give each variant a decision to test, such as whether the object or the image dominates.
5. Match tonal values and lighting direction when seeking continuity. Retain a deliberate visible cut where the contradiction depends on it.
6. Place the phrase outside the busiest region. Use a common palette if it unifies the images, reserve an accent for the punchline and compare with the clean control.

At reduced size, the objects should remain recognizable and their relationship should make sense without the caption. If they look like independent cutouts, adjust scale, direction or overlap before adding grain. On garments, check the edges and background for an unintended rectangle.

## C. Intervene in one detail — `targeted-accent-intervention`

Use this family when one detail can reveal the whole joke. DGH-05 addresses the relationship between text and image. DGH-08 addresses the accent.

1. Name the area carrying the contradiction, such as a checkbox, signature, eye, label, result or figure. Simplify the surrounding image to support it.
2. Compare three treatments of that area. Crop to enlarge it, use a mark or stripe to point to it, or extract it as a symbol. Keep the same phrase while judging the effect.
3. Preserve enough context to identify what changed. Adjust contrast and surrounding space. Position supporting detail so it reads after the focal point.
4. Hide the accent temporarily. Restoring it should change the interpretation or locate the punchline. Reconsider a purely decorative intervention.

Check that highlighting preserves the evidence that makes the satire intelligible. Keep the chosen mascot or symbol even if another asset makes a tutorial effect easier to reproduce.

## Editorial or vintage finish

Use this finish when the brief calls for it. Posters, covers and editorial pieces can support more detail than a tee designed to read at a glance.

### Grid and secondary detail

Use the amount of actual content to choose rows, columns and exceptions. Check the focal point against edges, obscured areas and the spine. An original hand-drawn mark can break the grid on the word that carries the meaning. Digitize it and preserve its shape.

Include secondary detail when it contributes content. Source any numbers or quotations presented as factual. For satire, write original copy that readers can recognize as such. Leave song lyrics and borrowed poster credits out of filler text.

### Reproducible texture

Adapt this layer structure to the editing tool.

```text
editable-art/
  exact-wording
  symbol-or-cutouts
print-finish/
  per-element-masks
  tonal-adjustments
presentation/
  background-and-mockup
```

1. Choose what the treatment represents, such as worn ink, paper, a hand mark or a photocopy. Save an output with the finish turned off.
2. Work on the edge or mask of each affected element. Reduce intensity on small letters. Restore strokes whose loss changes a word or silhouette.
3. Apply general texture when it helps the parts belong together. Inspect both light and dark areas for lost contrast.
4. Save scale, random seed where applicable, masks, source and parameters. At reduced size, check for pattern seams and halos.
5. Export the art separately from its presentation. For transparent prints, inspect alpha over the real product color.

The store repository includes `shared/scripts/generate_product_textures.py` and `shared/scripts/apply_subtraction_mask.py`. Check their help and input/output contracts before use. Generate only the resources needed for the composition.

### Limited palette

Keep meaningful colors editable so the same artwork can be tested with different combinations. For flat tonal masses, use masks to separate ranges and adjust their boundaries by eye. Preserve essential details and check for unexpected gaps. DGH-06 informs this layered editing. Production decisions such as trapping and registration depend on the process and supplier.

## Brief an image generator

When a model is appropriate, describe observable choices. A vague request to make the result “more professional” or a designer's name gives little direction.

```text
Destination and aspect ratio: [product and work area].
Idea and contradiction: [relationship the viewer should recognize].
Family: [one of the store's design families].
Composition: [focus, relative size, direction, space and area reserved for type].
Image: [required objects or figures and their relationship].
Palette: [base, accent and its purpose on the chosen surface].
Finish: [clean or localized treatment and its relative intensity].
Text: reserve space for exact wording during deterministic typesetting.
References: [the specific function of each authorized image].
Variation: [the one main decision to change from the control].
```

Open the generated result and typeset the final phrase with deterministic tools. Apply the store's labeling policy to the delivered file. For a campaign featuring an existing product, use the required real references to establish scale and fidelity.
