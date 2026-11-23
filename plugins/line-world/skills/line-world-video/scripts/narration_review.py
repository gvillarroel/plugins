#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Find narration passages needing editorial review without rewriting their meaning."""
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


RULES = [
    ('representation-disclaimer', r'\b(?:diagram|scheme|animation|diagrama|esquema|animacion|curva)\b.{0,110}\b(?:not (?:reality|a measurement)|only a map|does not measure|simplif\w*|no (?:es|mide|una medicion)|no una medicion|representa el mecanismo|es un esquema)\b',
     'Check whether this explains the subject or only the representation. Preserve a material data/provenance limitation.'),
    ('representation-disclaimer', r'\b(?:is not reality|is only a map|no es la realidad|mapa de la realidad)\b',
     'Explain the relevant relationship or consequence rather than the status of the diagram.'),
    ('guide-commentary', r'\b(?:red (?:dot|point)|punto rojo)\b.{0,100}\b(?:identif\w*|indica\w*|show\w*|indicat\w*|marks?\b)',
     'Let the guide direct attention; use speech for the operation or result.'),
    ('presentation-commentary', r'\b(?:chart|graph|grafico)\b.{0,90}\b(?:translates? (?:the |those )?rows|traduce.{0,30}filas)\b',
     'Use the spoken time to interpret the comparison rather than describe a redundant translation.'),
    ('color-commentary', r'\b(?:colors? (?:of|belong)|colores de)\b.{0,120}\b(?:original|problem|problema)\b',
     'Explain color only when its encoding is needed to interpret the subject.'),
]


def scene_script(scene):
    if 'script' in scene and 'text' in scene and scene['script'] != scene['text']:
        raise ValueError(f"Scene {scene['id']!r} has different values for 'script' and 'text'.")
    script = scene.get('script', scene.get('text'))
    if not isinstance(script, str) or not script.strip():
        raise ValueError(f"Scene {scene['id']!r} needs a nonempty 'script' or 'text'.")
    return script


def read_story(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    scenes = value.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        raise ValueError('A nonempty scenes array is required.')
    ids = [s.get('id') for s in scenes]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Scene IDs must be nonempty and unique.')
    for scene in scenes:
        scene_script(scene)
    return value


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def inspect(story, baseline=None):
    findings, inventory = [], []
    old = {s['id']: scene_script(s) for s in baseline['scenes']} if baseline else {}
    revisions = [] if baseline else None
    for order, scene in enumerate(story['scenes'], 1):
        scene_id = scene['id']
        script = scene_script(scene)
        script_digest = digest(script)
        inventory.append({'id': scene_id, 'order': order, 'scriptSha256': script_digest,
                          'wordCount': len(script.split()), 'editorialReview': 'pending'})
        if revisions is not None and old.get(scene_id) != script:
            previous = old.get(scene_id)
            revisions.append({'id': scene_id, 'previousScriptSha256': digest(previous) if previous is not None else None,
                              'scriptSha256': script_digest, 'nativeAudioTiming': 'must-be-measured'})
        for n, sentence in enumerate(re.split(r'(?<=[.!?])\s+', script.strip()), 1):
            matched = []
            for code, pattern, reason in RULES:
                if code not in matched and re.search(pattern, normalize(sentence)):
                    matched.append(code)
                    findings.append({'sceneId': scene_id, 'sentence': n, 'code': code,
                                     'text': sentence, 'reason': reason, 'decision': 'pending'})
    return {'schemaVersion': 1, 'status': 'editorial-review-required', 'sceneCount': len(inventory),
            'candidateCount': len(findings), 'scenes': inventory, 'candidates': findings,
            'changedScripts': revisions,
            'limits': 'Advisory lexical scan. Review all scenes; no semantic approval or actual audio timing is inferred.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--story', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(read_story(args.story), read_story(args.baseline) if args.baseline else None)
    except ValueError as error:
        parser.exit(2, f'narration_review: {error}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'ok': True, 'scenes': report['sceneCount'], 'reviewCandidates': report['candidateCount'],
                      'changedScripts': None if report['changedScripts'] is None else [s['id'] for s in report['changedScripts']],
                      'status': report['status']}))


if __name__ == '__main__':
    main()
