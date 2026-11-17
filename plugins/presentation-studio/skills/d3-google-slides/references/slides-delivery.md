# Google Slides delivery

## Prepare the destination

- For an existing deck, confirm its native Google Slides ID and use its slide object IDs, page size, and fresh revision ID. In the Google Drive connector, use `get_presentation` or `get_slide`. Preserve template content around the target frame. Copy a reference deck first when the requested output is a new deck based on that reference.
- For a new deck with supported custom curves, import the editable PPTX using `import_presentation` with `upload_mode` set to `native_google_slides`. Check the returned native MIME type and follow the verification steps below. For the in-place batch workflow, use the existing deck or create an empty native presentation with `create_file` and read its dimensions and revision. Use `--create-slide` to create a blank page within the batch when needed.
- Use an explicit `--page-size W H` for a nonstandard deck. `--frame X Y W H` defines the maximum rectangle in points from the slide's top-left. The script centers and uniformly scales the source within it. Read the fitted rectangle from `framePt` in the report.
- The browser runs the trusted local HTML or SVG and may load its local dependencies. Bundle D3, fonts, and data with the source. Install Playwright Chromium if no supported local browser is available. Use explicit SVG bounds, `--viewport` for responsive sources, and a settled state with the full visual inside the SVG viewport. Place meaning-bearing HTML overlays inside the SVG as part of the artwork before transfer, or capture the composite separately.

## Apply the batch

1. Read the batch as JSON. For the Google Drive connector's `batch_update_presentation`, pass the actual `requests` array, native `presentation_id`, and `write_control` set from `writeControl` when present. For an image batch, pass the PNG's absolute workspace path as the top-level `image_uris` sidecar. Keep the matching `createImage.url` placeholder inside the request. Use one local image per connector call.
2. With an already authorized Google Workspace CLI or Slides API client, send the full JSON body for editable requests. For example, `gws slides presentations batchUpdate --params '{"presentationId":"DECK_ID"}' --json '<batch JSON body>'`. An image batch's local URL is a connector placeholder. For a raw API client, use an authorized fetchable PNG URL or use one of the private delivery routes below. Keep the source and image private unless the user authorizes sharing.
3. After any uncertain response, read the destination page before retrying. The visual IDs in the report are deterministic. If the IDs are present, verify the applied result. If they are absent, refresh the revision, check the frame for concurrent edits, and retry only as needed. When applying several visuals, refresh the revision between batches or compose editable requests into one checked batch with unique IDs.

For image delivery without a connector sidecar, pass `--pptx out/snapshot.pptx` and import it as a new native Slides deck through Drive. The connector action is `import_presentation` with the absolute PPTX path and `upload_mode` set to `native_google_slides`. A Google Workspace CLI with Drive authorization can convert it using `gws drive files create --upload out/snapshot.pptx --json '{"name":"Visual snapshot","mimeType":"application/vnd.google-apps.presentation"}' --params '{"fields":"id,mimeType,webViewLink"}'`. The PPTX contains one placed image. In an existing deck without a connector sidecar, use the Slides editor's upload-from-computer image insertion and place it using the fitted rectangle. Preserve the image's alternative text from the batch.

## Verify and deliver

- Read the target slide and confirm the visual object IDs, expected object types, native text, and intended placement. For image transfer, confirm the embedded image and alt text. After importing PPTX, confirm the returned MIME type is native Google Slides and read back the new slide's generated IDs.
- Inspect a thumbnail or exported render against the source preview. Use the connector's `get_slide_thumbnail` with the verified slide object ID and `thumbnail_size: LARGE` to check fine details. Check values, label order, text fit, image aspect ratio, and surrounding content. If font substitution or a geometry difference matters, fix the editable mapping or use the image route when the user permits it.
- Return the verified Google Slides URL after a live write. For a prepared handoff, return the local files and identify the pending apply or import step.

## Representation limits

The editable routes preserve the supported marks as Slides objects and keep source data joins, scales, event handlers, and transitions in the source. Check the geometry route for the supported paint and shape features. Use the SVG title and description or explicit `--alt-title` and `--alt-description` for image accessibility.

- [Google Slides batch update](https://developers.google.com/workspace/slides/api/reference/rest/v1/presentations/batchUpdate)
- [Google Slides requests](https://developers.google.com/workspace/slides/api/reference/rest/v1/presentations/request)
- [Google Drive import conversion](https://developers.google.com/workspace/drive/api/guides/manage-uploads#convert_to_google_workspace_types)
