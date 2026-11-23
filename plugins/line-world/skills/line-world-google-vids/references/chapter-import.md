# Import a chaptered episode

From a measured producer project, run the following command against a new local directory. Python 3.11+ and FFmpeg/FFprobe must be on PATH.

```text
python <skill-root>/scripts/vids_chapters.py --video episode.mp4 --project proyecto.json --output vids-project
```

The producer project supplies ordered scene IDs, titles and its relative `audioTimeline` path. Alternatively pass `--timeline audio/timeline.json`. The transcript contains a positive integer `sample_rate` and ordered `scenes` with unique `id`, `start_sample`, `end_sample` and `sentences`. Each sentence contains its exact `text`, `absolute_start_sample` and `absolute_end_sample`. Use `--title` and `--language` to override the project's defaults. The input video needs embedded chapters covering its complete constant-rate integer frame clock. The source audio and video use the same zero point.

The default `--audio native` creates silent H.264 clips and an ordered native voiceover queue. Import each scene script into Vids, generate its native voice, and read the actual scene and voice durations. Resume from the generated directory.

```text
python <skill-root>/scripts/vids_batch.py next --project vids-project --limit 6
python <skill-root>/scripts/vids_batch.py build --project vids-project --observed measurements.json
```

The local sentence timestamps describe the source narration. A different voice can move speech-linked animation cues. Compare those cues during playback. If the native narration is shorter, keep the original scene length when appropriate. A millisecond reading such as 10.867 seconds matches 326 frames at 30 fps when the full voice fits those frames. When timing needs to change, adjust the animation in the producer and replace the affected clip. The importer treats the entire visual chapter as essential until its producer establishes a static hold.

To retain the original voice, music and effects mixed into the first audio stream, pass `--audio embedded`. Upload the clips in their listed order, retain their audio and copy each script to its corresponding scene. Skip native voice generation. The placement worksheet tracks native placement and listening. Voiceover batch commands apply to the native mode.

## Place clips from Drive and keep the scripts editable

In a new private Vids project, the initial Upload picker can also search Drive. Choose the first clip by its unique title and open it. For later clips, create a new scene, confirm it is empty, and use Insert → Drive & Photos. In the sidebar a single selection inserts the clip and the sidebar can stay open for the next scene. Check the selected scene's own media title, trim start and trim end after each insertion. A filename in the search results alone does not establish placement.

For each scene, open Voiceover → Current scene → Edit script, paste its exact text and leave the editor. In embedded mode the existing clip already contains speech. Saving the script adds editable speaker notes. Reload the document after it reports Saved to Drive, and select each timeline card to verify its notes and actual media. Some versions of the editor label earlier timeline buttons with the scene count as it stood when the card was created. The selected scene, script panel and media title provide the current identity.

The Transcript panel edits the automatically recognized clip text separately from speaker notes. Open Captions → More → Edit transcript, select the actual video on the canvas and wait for recognition. To correct one word, double-click it and choose Edit. To correct a misread number spread over several tokens, select the first token and Shift-click the last. Verify the selected words, choose Edit and enter the corrected phrase. This preserves the clip's voice and the timing of the surrounding words. Check quantities again in the exported MP4. For a whole-project authored track, use Tools → Closed captions → Add captions track → Upload file. Select the verified SRT, its language and an identifying track title. Confirm the new track in the list and check the downloaded MP4. View → Closed captions controls the playback track for the current session. The Captions sidebar styles words on the picture. [Google Vids caption tracks](https://support.google.com/docs/answer/14953386)

When the editor offers **Type manually**, the same project-level menu accepts one
timed block at a time. Choose the language and an identifying title. Copy the
start time, end time and text of each block from the reviewed SRT, including
line breaks. Save the track, wait for the Drive save indicator and reopen the
project. Select the named track and sample the first, middle and last scenes.
Use its menu to download the track and export a fresh native MP4. The editor
can round visible starts down and ends up to a tenth of a second while the
downloaded WebVTT and MP4 preserve the submitted milliseconds. Verify both the
selected language and the timed text on the delivered movie with the
[subtitle comparison](delivery.md#check-the-exported-subtitles).

## Files and checks

- `story.json` carries titles, stable IDs, frame ranges (exclusive end), scripts, individual measured phrases and relative clip paths. `clips/<id>.mp4` files start at zero and open on independently decodable keyframes.
- `chapter-checks.json` records source and clip digests, verified presentation cadence, decoded frame counts, audio-track counts and the source keyframe status at each entry. The importer compares every decoded output frame to the source frame at the corresponding absolute index. The per-frame mean PSNR must reach 38 dB. The receipt lists first, last and minimum values. `identical` denotes zero pixel error. The MP4 clips use lossy H.264.
- `handoff/scripts.txt`, `insertion-plan.json` and `upload-checklist.md` support scene insertion. Native mode creates a blank native measurement worksheet and initializes `vids_batch`. Embedded mode provides `placement.json`.

In Vids, an editor can reorder, replace or trim whole clips, change scene scripts, add overlays and manage native voiceovers. The existing chart marks, camera motion and effects are pixels inside each imported clip. To change them individually, edit the original producer sources and regenerate the affected chapter. Source subtitle tracks travel separately from these visual clips. Source audio is a single mix in embedded mode. All generated files describe a local handoff. Native insertion, saving, playback and export need observations from the actual Vids project.
