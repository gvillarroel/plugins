# Give an editable object a single timed entrance

Use a two-step scene when the viewer needs a moment to read a starting value
before the outcome arrives. Keep the opening label on screen as the reference.
For a complex chart, prepare the precise animation in the owning renderer and
decide which labels need to stay editable in Vids.

## Make and edit the copy

1. Open the authorized source and select **File > Make a copy > Entire video**.
   Check its destination and sharing controls. For a private variant, leave
   **Share it with the same people** off and verify **Private to only me** on
   the new document. Record its new ID and the target scene's stable ID.
2. Select the target scene and enable **Show timing**. Record its duration,
   current caption, object count and voice clip extents. Select the existing
   text in its actual caret and retain the first step. Use **Insert > Text >
   Add body text** to create the second box. Position the box on the canvas
   and edit its text. Check its own timing row, wrapping and alignment.
3. In the second object's timing row, drag its **left trim handle** to the
   intended cue. Read the actual local millisecond values from **Trim start**
   and **Trim end**. Dragging the scene thumbnail or audio waveform edits a
   different timeline item. A scene announcement can round to whole seconds.
4. Select the second box, open **Animation > Object**, enable **Separate enter
   and exit animations**, then choose **Enter > Slide**. Choose direction,
   duration and **Animated by > Whole** when the block is a single thought.
   Vids can initially choose **Character**, which animates letters separately.
   Check that **Exit** and **Loop** both show **None**. Use the actual choices
   exposed by the editor if labels differ by language.
5. Wait for **Saved to Drive**, reload and reselect the stable scene. At its
   opening, observe the first box alone. Seek past the entry and inspect both
   boxes. Read back the two object tracks, voice timing, selection announcement
   and the second object's **Enter**, **Exit** and **Loop** tabs. Save snapshots
   of both states and the animation settings. Make a native MP4 download.

## Measure the rendered motion

Supply two rectangles, measured as fractions of the exported picture in
`[left, top, right, bottom]` order. Use an unmoving dark-on-light label as
the anchor and a separate region containing the entire entrance. Keep your
sample window inside one scene, with frames before the cue and after it settles.
The following values illustrate a scene that starts at 31.043 s, whose object
enters 3.880 s later and whose animation setting is 0.8 s.

```json
{
  "sampleWindowSeconds": [31.1, 42.6],
  "expectedStartSeconds": 34.923,
  "durationSeconds": 0.8,
  "toleranceSeconds": 0.12,
  "minFinalHoldSeconds": 6.5,
  "revealRegion": [0, 0.53, 1, 0.92],
  "anchorRegion": [0, 0.03, 1, 0.49],
  "initiallyBlank": true,
  "darkThreshold": 175
}
```

```text
uv run --script <skill-root>/scripts/measure_reveal.py download.mp4 entrance.json --output measurement.json
```

The check measures ink masks on frames resized to 480 pixels wide. It reports
the first visible change, the first persistent match to the last pose, final
reading time, and stability of the opening label. An unchanging card, a flash
back to the opening, a cut without intermediate frames, a drifting reference
or an early/late entrance fails. Small compression changes are tolerated.
Photographic backgrounds, overlapping animations and light-on-dark designs
need their own visual comparison. Inspect real frames alongside the report.
The native panel supplies the editable-object identity and intended easing.

For exported captions and numbers, also perform the [subtitle delivery check](delivery.md#check-the-exported-subtitles).

## Coordinate a native guide with the result

1. Place the playhead after the result enters. Under **Shapes and lines > Draw
   lines > Arrow**, draw from the tail to the point. Leave enough room between
   the point and the number at the final frame. Select the line color and
   weight. Verify the editor announces the inserted arrow as its own object.
2. Drag the arrow track's left trim handle until its millisecond **Trim start**
   agrees with the result track. Leave the first value on its own uninterrupted
   track. An arrow can be animated with **Object > Enter > Scale**, with exit
   and loop disabled. Reload to check both tracks and each object's settings.
3. Take separate regions from the downloaded MP4. One can surround the price
   row and another can cover only the arrow between that row and the next.
   Check the final point at full resolution and the timing in between. The
   exposed native control specifies a duration; easing, small object size and
   contrast influence when the visible motion actually settles. A horizontal
   slide and an independently scaling arrow indicate a final position. They
   do not provide a tracking constraint between the arrow and a moving glyph.

For the same CLI, replace `revealRegion` with a `targets` list of exactly two
objects, each with a unique `id` and its own disjoint `revealRegion`. The
shared `anchorRegion` must be outside the moving artwork. Set
`minConcurrentMotionSeconds` to the required overlap. For small arrows use
`analysisWidth: 960` or higher and inspect the real frames. Other timing
options are inherited by each target. The report includes sustained final
poses, per-frame movement intervals and their actual intersection. The strict
status remains false if a declared timing tolerance is missed, even when both
objects clearly move together and settle in time to read.
