# Edit an existing Google Vids project

Use the editable project link already authorized for the task. Confirm the
signed-in identity, editor controls, full timeline and a saved baseline.
Select a scene and note both the ordinal and the native `scene=id.…` from
the address. A playhead position or file name cannot identify a scene.
When only the name is known, search the authorized Drive or Vids home,
verify the exact item and resolve duplicate names before applying edits.
To create a variant when requested, use the native **File > Make a copy**
flow and record the new file ID before preparing edits. Preserve sharing.

## Supported surfaces

The Google Drive MIME type `application/vnd.google-apps.vid` identifies the
editable file. Drive metadata can locate and verify the file; the public
Drive API documentation does not expose scene, script, track or transition
edits. Discover any purpose-built connector first, then use the supported
Google Vids editor for operations it does not expose. A Drive file with MIME
`video/mp4` is exported media. If a verified API integration is available to
download a native Vids file, Google documents `files.download` with a
long-running operation. `files.export` returns `fileNotExportable` for Vids.

[Google Vids editing help](https://support.google.com/docs/answer/15082958)
· [Google Drive file MIME types](https://developers.google.com/workspace/drive/api/guides/mime-types)
· [Google Vids download API](https://developers.google.com/workspace/drive/api/guides/manage-downloads)

## Guarded single edits

Keep one JSON journal per requested edit outside the skill. In the documented
CUA runtime, load `assets/runtime/vids-ui.js` and `assets/runtime/vids-edit.js`
in that order. Both helpers are pure. Supply a fresh full accessibility
observation from the selected foreground editor. Use the documented app/tab
methods to perform a returned action, then read current state again. At no
point use hidden endpoints, private browser transports or session extraction.

Example plan for an existing scene, using fictitious identifiers:

```json
{
  "operation": "set-script",
  "projectUrl": "https://docs.google.com/videos/d/example/edit",
  "sceneId": "id.example_0_0",
  "order": 2,
  "count": 3,
  "before": "The old narration.",
  "script": "Current splits at the node and recombines downstream."
}
```

```javascript
const ax = await tab.getAXState({emit: false, disableDiffing: true});
nodeRepl.write(LineWorldVidsEdit.editNext({
  ax, fullState: true, foreground: true, scope: 'native-ui', phase, plan,
}));
```

Use `scope: 'local-fixture'` for a replay or local test.

| Operation | Required plan fields besides project URL | Native action and verification |
|---|---|---|
| `rename-project` | `before`, `title` | Edit the observed **Rename** field and confirm the desired title after a reload. |
| `append-scene` | Original `count`, last `anchorSceneId` | Select the last scene and use **New scene** once. Observe the new last scene, verify the count increased by exactly one, then add its native `createdSceneId` to the journal and verify it after a reload. |
| `set-script` | `sceneId`, `order`, `count`, `before`, `script` | Select the scene, open **Voiceover > Current scene > Edit script**, paste into the actual script caret or select its current text first, exit edit mode and check the script after a reload. This changes the script only. |

Persist `ready` with the observed baseline before starting. If the helper
recommends a mutation, write `await-save` to the journal before executing
that action once. If a click, paste, or observation fails, leave the journal
at `await-save` and inspect fresh state. A repeated ready request with an
already-matching title or script skips the mutation. For an append, an extra
scene without a recorded ID in `ready` is a conflict. In `await-save`, record
the candidate ID only when the native editor shows the newly appended blank
scene from the one authorized action. Otherwise resolve the uncertainty before
retrying. Treat a conflicting value, count or native ID as a concurrent edit
or stale plan and obtain a fresh baseline before writing again.

When the planner returns `reload-to-verify`, record the native save indicator,
reload or reopen the same editor and use `phase: 'reopened'` only after the
new page loads. Reselect the stable scene and reopen **Current scene** if
needed. Record the returned receipt with the observed time and an exact
evidence excerpt or screenshot. Keep document IDs and account details private.
The helper verifies supplied observations; a receipt from fixture input
validates decision logic only.

The accessible script view splits text into rendered words. The helper
compares visible words and punctuation after collapsing whitespace. When the
request depends on exact newlines or spaces, inspect the actual editable
selection after reload and document the check. A script saved after a pasting
accident can be a canvas text box. If Vids announces such a paste, undo that
own change immediately, establish script focus and verify active scene, script
and unchanged canvas before continuing.

## Other native edit controls

For two editable elements with independently timed entrances, follow the
[two-step object edit and pixel check](object-entrance.md).

For clip replacement, voiceover, timing and transitions, inspect the selected
scene or object in the [native UI workflow](ui-workflow.md) and use the control
currently exposed. Preserve unaffected tracks. Compare before setting an
absolute target through the editor. Avoid repeating inserts or generation while
the previous operation is unresolved. After a save and reload, verify matching
media/voice track identity or count and playback, exact timings using a
sufficiently precise control, and both sides of a transition. If generating
speech, check the wording, voice, one intended audio start and actual duration.
The script-only receipt does not certify voice generation or a correct final
mix. For a requested MP4, also run the [delivery check](delivery.md).

[Google Vids accessible controls](https://support.google.com/docs/answer/15003436)
· [Google Vids media timing and formatting](https://support.google.com/docs/answer/14923154)
