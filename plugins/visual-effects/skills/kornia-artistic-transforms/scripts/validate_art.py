#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pillow>=11,<14", "numpy>=2,<3"]
# ///
"""Independently check collection/single reports against decoded PNG artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys

import numpy as np
from PIL import Image, ImageOps

HASH = re.compile(r'^[0-9a-f]{64}$')
CORE_FIELDS = ('schema_version', 'id', 'techniques', 'runtime', 'source', 'options', 'stages', 'validation')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    with Path(path).open(encoding='utf-8') as handle:
        data = json.load(handle)
    require(isinstance(data, dict), f'{path}: expected a JSON object')
    return data


def artifact(base, value):
    require(isinstance(value, str) and bool(value), 'An artifact path must be a nonempty string')
    require('\\' not in value and not PurePosixPath(value).is_absolute() and not PureWindowsPath(value).is_absolute(),
            f'Artifact paths must be relative POSIX paths: {value!r}')
    path = (base / value).resolve()
    require(path.is_file(), f'Missing artifact: {path}')
    return path


def png(path):
    with Image.open(path) as image:
        require(image.format == 'PNG', f'{path}: expected PNG bytes')
        image.load()
        require(image.mode == 'RGBA', f'{path}: expected the runner RGBA output mode')
        return np.array(image, copy=True)


def expected_source(path, max_edge):
    with Image.open(path) as image:
        image.seek(0)
        original_size = list(image.size)
        original_mode = image.mode
        oriented = ImageOps.exif_transpose(image).convert('RGBA')
        oriented_size = list(oriented.size)
        if max_edge and max(oriented.size) > max_edge:
            ratio = max_edge / max(oriented.size)
            oriented = oriented.resize(tuple(max(1, round(n * ratio)) for n in oriented.size), Image.Resampling.LANCZOS)
        pixels = np.array(oriented, copy=True)
    return pixels, original_size, oriented_size, original_mode


def verify_record(record, base, sources, warnings):
    require(record.get('schema_version') == 1, 'Unsupported render report schema')
    require(all(key in record for key in CORE_FIELDS), 'Missing technical provenance fields')
    require(isinstance(record['id'], str) and bool(record['id']), 'Missing stable output identity')
    keys, stages = record['techniques'], record['stages']
    require(isinstance(keys, list) and bool(keys) and all(isinstance(k, str) for k in keys), 'Invalid ordered technique list')
    require(isinstance(stages, list) and [stage.get('technique') for stage in stages] == keys, 'Recorded stage order differs from technique order')
    image_path = artifact(base, record['image'])
    report_path = artifact(base, record['report'])
    per_image = read_json(report_path)
    for key in CORE_FIELDS:
        require(per_image.get(key) == record[key], f'{record["id"]}: per-image {key} differs from collection metadata')
    require(artifact(report_path.parent, per_image['image']) == image_path, 'Per-image image path resolves to another artifact')
    require(artifact(report_path.parent, per_image['report']) == report_path, 'Per-image report path does not resolve to itself')
    pixels = png(image_path)
    height, width = pixels.shape[:2]
    validation, source, options = record['validation'], record['source'], record['options']
    require(source.get('output_size') == [width, height], 'Decoded PNG dimensions differ from source output_size')
    require(validation.get('width') == width and validation.get('height') == height, 'Decoded dimensions differ from validation metadata')
    require(validation.get('pixel_sha256') == hashlib.sha256(pixels.tobytes()).hexdigest(), 'Decoded RGBA pixel hash differs from its report')
    require(isinstance(source.get('sha256'), str) and HASH.fullmatch(source['sha256']), 'Invalid source byte hash')
    require(isinstance(options.get('seed'), int) and not isinstance(options['seed'], bool), 'Invalid global seed')
    require(isinstance(options.get('max_edge'), int) and options['max_edge'] >= 0, 'Invalid downscale limit')
    for key in ('strength', 'scale'):
        require(isinstance(options.get(key), (int, float)) and math.isfinite(options[key]), f'Invalid {key}')
    require(0 <= options['strength'] <= 1 and options['scale'] > 0, 'Invalid strength or scale range')
    runtime = record['runtime']
    require(all(isinstance(runtime.get(key), str) and HASH.fullmatch(runtime[key]) for key in ('engine_sha256', 'executor_sha256')), 'Missing implementation hashes')
    require(isinstance(runtime.get('packages'), dict) and bool(runtime['packages']), 'Missing effective package versions')
    identity = {'source_sha256': source['sha256'], 'techniques': keys, 'options': options, 'runtime': runtime}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(record['id'] == 'kat-' + digest[:20], 'Output identity does not bind its recorded source, techniques, settings and implementation')
    source_verified = False
    if source['sha256'] in sources:
        original, original_size, oriented_size, original_mode = expected_source(sources[source['sha256']], options['max_edge'])
        require(source['original_size'] == original_size and source['oriented_size'] == oriented_size, 'Source orientation dimensions differ from actual input')
        require(source['original_mode'] == original_mode, 'Reported input mode differs from the actual source')
        require(original.shape == pixels.shape, 'Output changed the complete oriented/resized canvas')
        if options.get('background') is None:
            require(np.array_equal(original[..., 3], pixels[..., 3]), 'Output alpha differs from the anchored processed source')
        else:
            require(np.all(pixels[..., 3] == 255), 'Explicit flattening left transparent output pixels')
        source_verified = True
    else:
        warnings.add('Original source bytes/alpha not independently checked: supply its path with --input.')
    return {'id': record['id'], 'image': image_path.name, 'techniques': keys,
            'width': width, 'height': height, 'source_verified': source_verified,
            'pixel_sha256': validation['pixel_sha256']}


def validate(paths, inputs=(), expected_count=None):
    sources = {}
    for path in inputs:
        path = Path(path).resolve()
        require(path.is_file(), f'Input does not exist: {path}')
        sources[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    records, warnings = [], set()
    for path in paths:
        path = Path(path).resolve()
        data = read_json(path)
        if 'outputs' in data:
            require(data.get('schema_version') == 1 and isinstance(data['outputs'], list) and bool(data['outputs']), 'Invalid collection manifest')
            ids = [row.get('id') for row in data['outputs']]
            require(len(ids) == len(set(ids)), 'A collection contains duplicate output identities')
            for field in ('source_image', 'contact_sheet', 'gallery'):
                artifact(path.parent, data[field])
            for row in data['outputs']:
                records.append(verify_record(row, path.parent, sources, warnings))
        else:
            require(artifact(path.parent, data['report']) == path, 'The selected report does not identify itself')
            records.append(verify_record(data, path.parent, sources, warnings))
    require(bool(records), 'No rendered outputs were supplied')
    if expected_count is not None:
        require(len(records) == expected_count, f'Expected {expected_count} outputs, found {len(records)}')
    if inputs:
        require(all(row['source_verified'] for row in records), 'The supplied inputs do not match every reported source hash')
    return {'passed': True, 'output_count': len(records), 'source_checked_outputs': sum(row['source_verified'] for row in records),
            'outputs': records, 'warnings': sorted(warnings),
            'limits': 'Checks decoded artifacts, metadata consistency, source geometry and anchored alpha. It does not certify aesthetic quality, physical calibration or pre-quantization tensor values.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', type=Path, help='Collection manifest or per-image report JSON paths.')
    parser.add_argument('--input', action='append', default=[], type=Path, help='Original source image; repeat for several sources.')
    parser.add_argument('--expect-count', type=int, help='Expected total rendered output records.')
    args = parser.parse_args(argv)
    try:
        result = validate(args.reports, args.input, args.expect_count)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(json.dumps({'passed': False, 'error': str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
