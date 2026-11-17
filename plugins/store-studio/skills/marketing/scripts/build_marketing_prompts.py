#!/usr/bin/env python3
"""Build a deterministic marketing prompt pack for a Printify product reference."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

SCENARIO_SETS = {
    "tech-workplace": [
        {
            "id": "office-dashboard-irony",
            "title": "Office dashboard irony",
            "scene": (
                "high-end startup office, two-screen meeting monitor glow, one person in an upscale context "
                "wearing the product as social proof."
            ),
            "tone": "dry startup satire, sharp but not cruel",
        },
        {
            "id": "conference-booth-revenue",
            "title": "Conference booth irony",
            "scene": (
                "professional conference booth, one person presenting a pitch deck, the product clearly visible "
                "as the centerpiece, with enough ambient context to keep the image editorial but not cluttered."
            ),
            "tone": "clean irony, success theater, anti-hype",
        },
        {
            "id": "quiet-corner-debate",
            "title": "Quiet corner contradiction",
            "scene": (
                "calm coworking corner with a notebook, planner, or old notebook stack, one person appearing "
                "composed and slightly amused while the shirt is front-and-center."
            ),
            "tone": "subtle observational satire",
        },
        {
            "id": "home-desk-mockery",
            "title": "Home desk irony",
            "scene": (
                "home office desk, analog notes, manual workflow artifacts, realistic and tidy, no extra logo clutter, "
                "focus on the printed item on body."
            ),
            "tone": "self-aware contradiction, calm satire",
        },
    ],
    "claude-terminal-chaos": [
        {
            "id": "twenty-terminals-all-red",
            "title": "Twenty terminals, all red",
            "scene": (
                "overloaded programmer desk at night, one adult programmer surrounded by about twenty terminal "
                "windows across multiple monitors, Claude Code-style coding assistant panes, red error output, "
                "failed tests, merge conflicts, todo lists, sticky notes, cables, and the product mug clearly on the desk "
                "within reach as the calm center of the disaster."
            ),
            "tone": "sharp developer satire: multitasking as a managed outage",
        },
        {
            "id": "parallel-agents-wrong-branch",
            "title": "Parallel agents, wrong branch",
            "scene": (
                "busy home office with a programmer trying to supervise many simultaneous AI coding assistant terminal panes, "
                "several monitors showing build logs, wrong-branch warnings, broken deployment dashboards, and repeated command prompts; "
                "the product mug is in the foreground near the keyboard, visible and not hidden by hands."
            ),
            "tone": "self-aware AI workflow satire: more automation, more ways to be wrong",
        },
        {
            "id": "standup-from-incident-room",
            "title": "Standup from incident room",
            "scene": (
                "remote standup call from an incident-room desk, one programmer half-composed while multiple monitors show terminal panes, "
                "test failures, rollback notes, and Claude Code-like assistant windows competing for attention; "
                "the product mug sits beside a notebook labeled only with abstract marks, not readable brand text."
            ),
            "tone": "dry office satire: executive calm powered by unresolved stack traces",
        },
        {
            "id": "coffee-refill-while-ci-burns",
            "title": "Coffee refill while CI burns",
            "scene": (
                "programmer in a compact studio desk setup pouring coffee into or reaching for the product mug while many terminal windows "
                "fill the background monitors, CI failures, package conflicts, and code assistant panes all active at once; "
                "the product mug remains sharp, central, and faithful to the Printify reference."
            ),
            "tone": "sarcastic productivity theater: the workflow is optimized, the result is not",
        },
        {
            "id": "keyboard-shortcut-panic",
            "title": "Keyboard shortcut panic",
            "scene": (
                "developer workstation with split keyboards, two laptops, tablet, multiple external monitors, and about twenty overlapping terminal panes; "
                "one programmer looks calmly defeated while every screen implies a different task failing; "
                "the product mug is front-left on the desk, visibly purple and readable."
            ),
            "tone": "absurd but plausible developer chaos, no slapstick",
        },
        {
            "id": "ai-pair-programming-committee",
            "title": "AI pair programming committee",
            "scene": (
                "sleek coworking desk where one programmer appears to be pair-programming with too many AI agents at once, "
                "monitors filled with terminal panes, agent status panels, refactor attempts, failed tests, and TODO warnings; "
                "the product mug sits next to the keyboard like a ritual object for expensive mistakes."
            ),
            "tone": "capitalism selling its own critique, developer culture irony",
        },
    ],
    "nonprogramming-lifestyle": [
        {
            "id": "gym-weights-token-detox",
            "title": "Gym weights token detox",
            "scene": (
                "real gym weight room after a workout, dumbbells and bench nearby, one adult wearing the shirt "
                "while resting between sets; no computers, no code, no office props."
            ),
            "tone": "dry self-improvement satire: rep count over token count",
        },
        {
            "id": "family-dad-mode-no-dashboard",
            "title": "Family dad mode",
            "scene": (
                "warm family morning at a kitchen table, breakfast clutter and children's drawings visible, one adult parent "
                "wearing the shirt while handling ordinary family chaos; no laptop dashboard."
            ),
            "tone": "parent-life irony: some KPIs have crumbs on them",
        },
        {
            "id": "church-token-confession",
            "title": "Church confession",
            "scene": (
                "quiet church or community hall after service, pews and soft window light, one adult wearing the shirt "
                "with a composed confessional expression; respectful, satirical, not mocking religion."
            ),
            "tone": "confessional satire: forgive me, I maxxed",
        },
        {
            "id": "touch-grass-log-nothing",
            "title": "Touch grass",
            "scene": (
                "park or weekend errand setting with grass and a stroller or tote bag nearby, one adult wearing the shirt "
                "outdoors, deliberately away from screens and metrics."
            ),
            "tone": "offline recovery satire: touch grass, log nothing",
        },
        {
            "id": "basketball-pickup-no-burn-rate",
            "title": "Pickup basketball",
            "scene": (
                "neighborhood basketball court after a casual pickup game, one adult wearing the shirt with a ball under one arm, "
                "sweat, concrete, daylight, and no tech workplace cues."
            ),
            "tone": "casual competition satire: leaderboard detox without a leaderboard",
        },
        {
            "id": "grocery-run-ai-usage",
            "title": "Grocery run",
            "scene": (
                "grocery store or farmers market aisle, one adult wearing the shirt while carrying a basket, ordinary life details, "
                "the product artwork clear and readable, no programming context."
            ),
            "tone": "mundane capitalism satire: AI usage is not a personality",
        },
        {
            "id": "public-transit-metric-detox",
            "title": "Public transit commute",
            "scene": (
                "subway platform or bus stop commute, one adult wearing the shirt with headphones and a tote bag, "
                "ordinary morning travel details, no screens as the focal point, no workplace cues."
            ),
            "tone": "commuter satire: the only queue that matters is the train",
        },
        {
            "id": "laundromat-token-cleanse",
            "title": "Laundromat cleanse",
            "scene": (
                "neighborhood laundromat with washers, folded clothes, and fluorescent light, one adult wearing the shirt "
                "while sorting laundry, clean product front visible, no office or programming context."
            ),
            "tone": "literal detox satire: wash the shirt, not the dashboard",
        },
        {
            "id": "community-picnic-no-dashboard",
            "title": "Community picnic",
            "scene": (
                "casual backyard or park picnic with friends in soft daylight, one adult wearing the shirt while holding a plate or drink, "
                "social ordinary-life context, no laptops, no metrics, no office cues."
            ),
            "tone": "social-life satire: not every ranking deserves a leaderboard",
        },
        {
            "id": "bookstore-analog-recovery",
            "title": "Bookstore analog recovery",
            "scene": (
                "independent bookstore or library aisle with paper books and warm light, one adult wearing the shirt while browsing, "
                "quiet analog recovery mood, no screens, no tech workplace cues."
            ),
            "tone": "analog recovery satire: usage is not wisdom",
        },
    ],
}

CAST_DEFAULT = ["masculine-presenting", "feminine-presenting", "masculine-presenting", "feminine-presenting"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic marketing campaign prompts.")
    parser.add_argument("--input-manifest", required=True, help="Printify extraction manifest path")
    parser.add_argument("--output-dir", required=True, help="Output folder for generated prompt artifacts")
    parser.add_argument(
        "--model-reference-dir",
        help="Directory containing selected model/person reference images; defaults to <spike>/assets/source/models",
    )
    parser.add_argument("--max-options", type=int, default=4, help="Number of prompts to generate")
    parser.add_argument(
        "--cast-pattern",
        default="2m2f",
        help="Cast pattern; accepts raw value like 2m2f or explicit count like 2m2f",
    )
    parser.add_argument(
        "--scenario-set",
        default="tech-workplace",
        choices=sorted(SCENARIO_SETS.keys()),
        help="Scenario set to use for prompt construction",
    )
    parser.add_argument("--tone", default="sarcastic", help="Optional campaign tone override")
    return parser.parse_args()


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("extracted_images"):
        raise SystemExit(f"No extracted_images in manifest: {path}")
    return data


def relative_posix(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def default_model_reference_dir(output_dir: Path) -> Path:
    spike_dir = output_dir.resolve().parent
    return spike_dir / "assets" / "source" / "models"


def infer_cast_from_name(filename: str, fallback: str) -> str:
    lowered = filename.lower()
    if any(token in lowered for token in ("feminine", "female", "woman", "women")):
        return "feminine-presenting"
    if any(token in lowered for token in ("masculine", "male", "man", "men")):
        return "masculine-presenting"
    return fallback


def read_model_references(model_dir: Path, max_options: int, cast: list[str]) -> list[dict]:
    if not model_dir.exists():
        raise SystemExit(
            f"No model reference directory found: {model_dir}. "
            "Select model/person references first and save them under assets/source/models/."
        )
    files = sorted(
        path for path in model_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if len(files) < max_options:
        raise SystemExit(
            f"Need at least {max_options} model/person reference images in {model_dir}; found {len(files)}."
        )

    references = []
    for index, path in enumerate(files[:max_options]):
        references.append(
            {
                "slot": index + 1,
                "file": relative_posix(path),
                "cast": infer_cast_from_name(path.name, cast[index]),
                "selection_note": "Selected before prompt composition as the model/person reference for this slot.",
            }
        )
    return references


def cast_from_pattern(max_options: int, pattern: str) -> list[str]:
    if pattern.lower() == "2m2f":
        base = CAST_DEFAULT
    else:
        lowered = pattern.lower()
        male = lowered.count("m")
        female = lowered.count("f")
        if male + female == 0:
            base = CAST_DEFAULT
        else:
            base = []
            for char in lowered:
                if char == "m":
                    base.append("masculine-presenting")
                if char == "f":
                    base.append("feminine-presenting")
            if not base:
                base = CAST_DEFAULT
    while len(base) < max_options:
        base.extend(base[:max_options - len(base)])
    return base[:max_options]


def build_prompt(product_title: str, product_truth: dict, model_reference: dict, scenario: dict, tone: str) -> str:
    product_kind = infer_product_kind(product_title, product_truth)
    if product_kind == "mug":
        product_instruction = (
            "Use the direct Printify product reference as strict product truth for the mug shape, purple wrap artwork, "
            "accent color, artwork scale, and placement. The mug should be held naturally or placed on the desk as a real ceramic mug, "
            "not flattened into a poster, not redesigned, and not replaced with a generic cup."
        )
        visibility_instruction = (
            "Keep the mug legible, visibly purple, and not hidden by hands, steam, blur, crop, foreground clutter, or extreme angle. "
            "The product can be a desk focal point rather than worn by the model."
        )
    else:
        product_instruction = (
            "Use the direct Printify product reference as strict product truth for shirt color, garment cut, artwork, artwork scale, and print placement. "
            "The shirt must be worn by the model, not pasted flat on top as a poster or cutout."
        )
        visibility_instruction = "Keep product legible, readable, and not hidden by hands, props, blur, crop, or clutter."

    return (
        "Photorealistic ecommerce lifestyle marketing image generated with ChatGPT/OpenAI image generation. "
        "Use the selected model/person reference as the human identity/style reference for this one image; "
        "do not impersonate a real public figure. "
        f"Model/person reference image: {model_reference['file']}. "
        f"{product_instruction} "
        f"Direct Printify product reference image: {product_truth['file']}. "
        f"Cast: {model_reference['cast']} adult, distinct person for this slot, clean product-facing lifestyle shot, natural posture, controlled visual chaos. "
        f"Scene: {scenario['scene']}. "
        f"Tone: {scenario['tone']}; keep the tone {tone} and store-style satire, "
        "without defaming real groups, without hate symbols, and without false factual claims. "
        f"{visibility_instruction} "
        "Do not include any other graphic brand marks in the scene except the referenced product. "
        "Screens may show generic terminal-like panes, abstract code, build failures, TODO markers, and assistant-style panels, but no real company logos or readable private code. "
        f"Product: {product_title}. "
        "After generation, add a visible corner label reading exactly 'AI Generated Image' in the final storefront-facing image."
    )


def infer_product_kind(product_title: str, product_truth: dict) -> str:
    haystack = " ".join(
        [
            product_title or "",
            str(product_truth.get("file") or ""),
            str(product_truth.get("alt") or ""),
        ]
    ).lower()
    if "mug" in haystack or "taza" in haystack:
        return "mug"
    return "shirt"


def write_markdown(output_dir: Path, entries: list[dict], manifest_path: Path) -> Path:
    path = output_dir / "marketing-candidates.md"
    lines = [
        "# Marketing campaign candidates",
        "",
        f"- Source manifest: `{manifest_path.as_posix()}`",
        f"- Generated at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
    ]

    for entry in entries:
        lines.extend(
            [
                f"## {entry['id']}",
                "",
                f"- Cast: {entry['cast']}",
                f"- Model reference: `{entry['model_reference']['file']}`",
                f"- Product truth: `{entry['product_truth']['file']}`",
                f"- Scenario: {entry['scenario']['title']}",
                f"- Scene: {entry['scenario']['description']}",
                "- Prompt:",
                "",
                f"```",
                entry["prompt"],
                "```",
                "",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_manifest = Path(args.input_manifest).resolve()
    manifest = read_manifest(input_manifest)
    images = manifest.get("extracted_images", [])
    if not images:
        raise SystemExit("Manifest has no extracted_images.")

    product_title = manifest.get("product_title") or "Printify Product"
    cast = cast_from_pattern(args.max_options, args.cast_pattern)
    model_dir = Path(args.model_reference_dir).resolve() if args.model_reference_dir else default_model_reference_dir(output_dir)
    model_references = read_model_references(model_dir, args.max_options, cast)
    selected_scenarios = SCENARIO_SETS[args.scenario_set]
    scenarios = selected_scenarios[: args.max_options]
    if len(scenarios) < args.max_options:
        repeat = []
        while len(repeat) < args.max_options - len(scenarios):
            repeat.extend(selected_scenarios)
        scenarios.extend(repeat[: args.max_options - len(scenarios)])

    entries = []
    for index in range(args.max_options):
        scenario = scenarios[index]
        model_reference = model_references[index]
        product_truth = images[index % len(images)]
        prompt = build_prompt(product_title, product_truth, model_reference, scenario, args.tone)
        entries.append(
            {
                "id": f"marketing-{index + 1:02d}",
                "slot": index + 1,
                "cast": model_reference["cast"],
                "model_reference": model_reference,
                "product_truth": product_truth,
                "scenario": {
                    "id": scenario["id"],
                    "title": scenario["title"],
                    "description": scenario["scene"],
                    "tone": scenario["tone"],
                },
                "prompt": prompt,
                "expected_output": f"marketing-{index + 1:02d}.png",
                "model_reference_file": model_reference["file"],
                "product_truth_file": product_truth["file"],
                "required_disclosure": "AI Generated Image",
            }
        )

    output_manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_manifest": input_manifest.as_posix(),
        "product_title": product_title,
        "product_id": manifest.get("product_id"),
        "model_reference_dir": relative_posix(model_dir),
        "cast_pattern": args.cast_pattern,
        "scenario_set": args.scenario_set,
        "tone": args.tone,
        "entries": entries,
    }
    output_json = output_dir / "marketing-candidates.json"
    output_json.write_text(json.dumps(output_manifest, indent=2) + "\n", encoding="utf-8")

    output_md = write_markdown(output_dir, entries, input_manifest)
    print(
        json.dumps(
            {
                "marketing_json": output_json.as_posix(),
                "marketing_md": output_md.as_posix(),
                "count": len(entries),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
