#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check the edit planner against anonymized Chrome AX shapes and conflicts."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path


PROJECT = "https://docs.google.com/videos/d/example/edit"
SCENE_1 = "id.p"
SCENE_2 = "id.fixture_0_0"
SCRIPT = "A test circuit lights one lamp."
RUNTIME = Path(__file__).resolve().parents[1] / "assets" / "runtime" / "vids-edit.js"


def observed_ax(*, count=2, order=2, scene_id=SCENE_2, title="Private draft",
                saved=True, panel=None, all_scenes=False):
    url = PROJECT.removeprefix("https://") + f"?scene={scene_id}#scene={scene_id}"
    status = "Saved to Drive." if saved else "Saving…."
    timeline = [f"            {80 + i} button Scene {i} of {count}" for i in range(1, count + 1)]
    lines = [
        f"1 AXWebArea {title} - Google Vids, URL: {url}",
        "  4 container Description: Menu bar, ID: docs-chrome",
        f"      11 text field (settable) Description: Rename, Value: {title}",
        f"      14 button Description: Document status: {status}, ID: docs-save-indicator-badge",
        "      45 button Description: New scene (Ctrl+M), ID: newSceneButton",
        "  66 container two-panel-layout",
        *timeline,
        "      96 button New scene (Ctrl+M)",
        f"      105 checkbox Description: Generate a voiceover, Value: {int(panel is not None)}, ID: content-library-rail-voiceovers-element",
    ]
    if panel is not None:
        lines.extend((
            f"      131 tab ({'selectable' if all_scenes else 'selected'}, settable, boolean) Current scene, Value: {int(not all_scenes)}",
            f"      132 tab ({'selected' if all_scenes else 'selectable'}, settable, boolean) All scenes, Value: {int(all_scenes)}",
            "      133 button Edit script",
            f"      134 text Scene {order} / {count}",
            "      137 container Scripts",
            "        138 image",
        ))
        lines.extend(f"          {139 + i} text {word}" for i, word in enumerate(panel.split()))
        if panel:
            lines.extend(("      146 button Gemini will analyze your script and apply audio tags",
                          "        147 text Apply audio tags"))
        lines.append("      145 heading Voiceover, Value: 3")
        if not panel:
            lines.insert(-1, "          144 text Write a script to get started")
            lines.append("      149 button (disabled) Type your script first")
    lines.append(f"The focused UI element is {80 + order} button Scene {order} of {count}")
    return "\n".join(lines)


@unittest.skipUnless(shutil.which("node"), "Node is required for the edit planner")
class VidsEditTests(unittest.TestCase):
    rename = {"projectUrl": PROJECT, "operation": "rename-project",
              "before": "Private draft", "title": "Reviewed title"}
    append = {"projectUrl": PROJECT, "operation": "append-scene",
              "count": 1, "anchorSceneId": SCENE_1}
    script = {"projectUrl": PROJECT, "operation": "set-script",
              "count": 2, "sceneId": SCENE_2, "order": 2,
              "before": "", "script": SCRIPT}

    def call(self, plan=None, ax=None, **patch):
        payload = {"plan": plan or self.rename, "ax": observed_ax() if ax is None else ax,
                   "fullState": True, "foreground": True, "phase": "ready", "scope": "local-fixture"}
        payload.update(patch)
        js = ("const {editNext} = require(process.argv[1]);"
              "const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));"
              "process.stdout.write(JSON.stringify(editNext(input)));")
        result = subprocess.run(
            ["node", "-e", js, str(RUNTIME)], input=json.dumps(payload),
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)

    def test_rename_uses_fresh_control_and_expected_baseline(self):
        self.assertEqual(self.call(), {"kind": "rename-project", "index": 11, "title": "Reviewed title"})
        self.assertEqual(self.call(ax=observed_ax(title="Concurrent rename"))["kind"], "conflict")

    def test_rename_waits_after_attempt_and_requires_reload(self):
        self.assertEqual(self.call(phase="await-save")["kind"], "observe")
        self.assertEqual(self.call(ax=observed_ax(title="Reviewed title", saved=False))["kind"], "observe")
        self.assertEqual(self.call(ax=observed_ax(title="Reviewed title"))["kind"], "reload-to-verify")
        confirmed = self.call(ax=observed_ax(title="Reviewed title"), phase="reopened")
        self.assertEqual(confirmed["kind"], "verified")
        self.assertEqual(confirmed["receipt"]["scope"], "local-fixture")
        self.assertEqual(self.call(phase="reopened")["kind"], "conflict")

    def test_rejects_wrong_incomplete_unfocused_and_blocked_edit(self):
        cases = [
            ({"ax": observed_ax().replace("/d/example/", "/d/different/")}, "verify-project"),
            ({"ax": observed_ax().replace("docs.google.com", "docs.google.com.example.net")}, "verify-project"),
            ({"ax": observed_ax().replace("82 button Scene 2 of 2", "")}, "read-full-state"),
            ({"fullState": False}, "read-full-state"),
            ({"foreground": False}, "foreground-editor"),
            ({"policyStopped": True, "fullState": False, "foreground": False}, "stop"),
        ]
        for patch, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.call(**patch)["kind"], expected)

    def test_append_requires_anchor_and_is_not_repeated_after_a_delayed_read(self):
        baseline = observed_ax(count=1, order=1, scene_id=SCENE_1)
        self.assertEqual(self.call(plan=self.append, ax=baseline)["kind"], "append-scene")
        self.assertEqual(self.call(plan=self.append, ax=baseline, phase="await-save")["kind"], "observe")
        swapped = baseline.replace(f"scene={SCENE_1}", f"scene={SCENE_2}")
        self.assertEqual(self.call(plan=self.append, ax=swapped)["kind"], "conflict")

    def test_append_requires_a_recorded_new_id_on_replay(self):
        new_scene = self.call(plan=self.append, phase="await-save")
        self.assertEqual((new_scene["kind"], new_scene["createdSceneId"]), ("record-appended-scene", SCENE_2))
        self.assertEqual(self.call(plan=self.append)["kind"], "conflict")
        recorded = dict(self.append, createdSceneId=SCENE_2)
        self.assertEqual(self.call(plan=recorded)["kind"], "reload-to-verify")
        self.assertEqual(self.call(plan=recorded, phase="reopened")["receipt"]["createdSceneId"], SCENE_2)
        wrong = observed_ax(scene_id="id.wrong")
        self.assertEqual(self.call(plan=recorded, ax=wrong, phase="reopened")["kind"], "conflict")
        self.assertEqual(self.call(plan=recorded, ax=observed_ax(count=3))["kind"], "conflict")

    def test_edit_script_requires_selected_scene_id_and_single_scene_panel(self):
        first = observed_ax(order=1, scene_id=SCENE_1)
        self.assertEqual(self.call(plan=self.script, ax=first)["kind"], "select-scene")
        self.assertEqual(self.call(plan=self.script, ax=observed_ax(scene_id=SCENE_1))["kind"], "conflict")
        self.assertEqual(self.call(plan=self.script)["kind"], "open-voiceover")
        all_scenes = observed_ax(panel="", all_scenes=True)
        self.assertEqual(self.call(plan=self.script, ax=all_scenes)["kind"], "show-current-scene")
        selected = observed_ax(panel="")
        result = self.call(plan=self.script, ax=selected)
        self.assertEqual((result["kind"], result["script"]), ("edit-script", SCRIPT))

    def test_existing_script_replays_without_writing_or_claiming_voice_generation(self):
        target = observed_ax(panel=SCRIPT)
        self.assertEqual(self.call(plan=self.script, ax=target)["kind"], "reload-to-verify")
        receipt = self.call(plan=self.script, ax=target, phase="reopened")["receipt"]
        self.assertEqual(receipt["observedScript"], SCRIPT)
        self.assertEqual(receipt["scriptMatch"], "normalized-visible-text")
        self.assertNotIn("narrationGenerated", receipt)
        changed = observed_ax(panel="An edit from another collaborator.")
        self.assertEqual(self.call(plan=self.script, ax=changed)["kind"], "conflict")

    def test_whitespace_only_and_unpersisted_script_changes_do_not_get_receipts(self):
        bad = dict(self.script, before=SCRIPT, script=SCRIPT.replace("one ", "one\n"))
        original = observed_ax(panel=SCRIPT)
        self.assertEqual(self.call(plan=bad, ax=original)["kind"], "conflict")
        saving = observed_ax(panel=SCRIPT, saved=False)
        self.assertEqual(self.call(plan=self.script, ax=saving, phase="reopened")["kind"], "observe")
        old = observed_ax(panel="")
        self.assertEqual(self.call(plan=self.script, ax=old, phase="await-save")["kind"], "observe")


if __name__ == "__main__":
    unittest.main()
