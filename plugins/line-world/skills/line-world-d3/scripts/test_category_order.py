#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check category allocation across native Python/JS and ordered treemap tones."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from colorset_adapter import CONTRACT, SOLID_RUNTIME, category_style
from build_treemap import build_document

ROOT = Path(__file__).resolve().parents[1]


class CategoryOrderTests(unittest.TestCase):
    def setUp(self):
        self.palettes = json.loads(CONTRACT.read_text(encoding='utf-8'))['colorsets']

    def test_usable_solids_before_overflow_and_native_js_parity(self):
        code = """const fs=require('fs'),vm=require('vm');
const data=JSON.parse(process.argv[1]),sandbox={window:{D3_SOLID_PALETTES:data.palettes},
document:{readyState:'loading',addEventListener(){}},MutationObserver:class{observe(){}disconnect(){}}};
vm.runInNewContext(fs.readFileSync(data.runtime,'utf8'),sandbox);
console.log(JSON.stringify(data.cases.map(c=>sandbox.window.D3SolidStyle.categoryStyle(c.index,c.colorset,c.canvas))));"""
        cases, expected = [], []
        for name, palette in self.palettes.items():
            for canvas in ['#ffffff', '#f7f7f7', '#000000']:
                solids = [paint for paint in palette['solidSequence'] if paint != canvas]
                for index in range(len(solids) + 3):
                    cases.append(dict(index=index, colorset=name, canvas=canvas))
                    style = category_style(index, palette, canvas)
                    expected.append(style)
                    if index < len(solids):
                        self.assertEqual(style['fill'], solids[index])
                        self.assertEqual(style['stroke'], 'none')
                        self.assertEqual(style['text'], palette['textOnFill'][style['fill']])
                    else:
                        self.assertEqual(style['tier'], 'overflow')
                        self.assertNotEqual(style['stroke'], 'none')
        observed = subprocess.run(['node', '-e', code, json.dumps(dict(palettes=self.palettes, runtime=str(SOLID_RUNTIME), cases=cases))], check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(observed.stdout), expected)
        self.assertEqual(expected[0]['fill'], '#9e1b32')
        self.assertEqual([item['fill'] for item in expected[1:4]], ['#b5b5b5', '#e7e7e7', '#9c9c9c'])
        self.assertEqual(self.palettes['colorset2']['sequence'][:8], self.palettes['colorset1']['sequence'][:8])
        self.assertEqual(self.palettes['colorset2']['roles']['secondary'], '#007298')

    def test_logo_engine_uses_contract_categories_and_keeps_semantic_roles(self):
        code = "const fs=require('fs'),vm=require('vm'),sandbox={};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);console.log(JSON.stringify(sandbox.D3LogoDesign.COLORSETS));"
        observed = subprocess.run(['node', '-e', code, str(ROOT / 'assets/templates/logo-engine.js')], check=True, capture_output=True, text=True)
        engine = json.loads(observed.stdout)
        for name, palette in self.palettes.items():
            self.assertEqual(engine[name]['sequence'], palette['sequence'])
            self.assertEqual(engine[name]['roles'], palette['roles'])
        self.assertEqual(engine['colorset1']['roles']['ink'], '#333e48')
        self.assertEqual(engine['colorset1']['roles']['primary'], '#9e1b32')

    def test_treemap_headers_follow_categories_but_child_tones_stay_ordered(self):
        data = {'name': 'Portfolio', 'children': [{'name': name, 'children': [{'name': f'{name} {i}', 'value': i + 1} for i in range(3)]} for name in ['Create', 'Serve', 'Learn']]}
        expected_tones = [['#6d1222', '#9e1b32', '#e8002a'], ['#4f4f4f', '#828282', '#b5b5b5'], ['#363636', '#696969', '#9c9c9c']]
        document = build_document(data, title='Portfolio', colorset='colorset1', width=960, height=620)
        config = json.loads(re.search(r'const config=(\{.*?\});', document).group(1))
        self.assertEqual([family[0] for family in config['families']], ['#9e1b32', '#b5b5b5', '#e7e7e7'])
        self.assertEqual([family[1] for family in config['families']], expected_tones)
        extended = build_document(data, title='Portfolio', colorset='colorset2', width=960, height=620)
        extended_config = json.loads(re.search(r'const config=(\{.*?\});', extended).group(1))
        self.assertEqual(extended_config['families'], config['families'])
        wide = {'name':'Example', 'children':[{'name':str(i), 'children':[{'name':'leaf', 'value':1}]} for i in range(8)]}
        families = json.loads(re.search(r'const config=(\{.*?\});', build_document(wide, colorset='colorset2')).group(1))['families']
        self.assertEqual(families[-1], ['#007298', ['#004d66', '#007298', '#00ace6']])
        self.assertEqual(len(set(base for base, _ in families)), 8)

    def test_switchable_studio_keeps_both_registries_and_rejects_custom_functional_paint(self):
        with tempfile.TemporaryDirectory(prefix='.d3-category-test-') as directory:
            artifact = Path(directory) / 'studio.html'
            for name in self.palettes:
                subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_logo_studio.py'),
                                '--output', str(artifact), '--colorset', name], check=True, capture_output=True, text=True)
                document = artifact.read_text(encoding='utf-8')
                manifest = json.loads(re.search(r'<script id="d3-logo-manifest" type="application/json">(.*?)</script>', document).group(1))
                self.assertEqual(manifest['palettes'], self.palettes)
                validator = [sys.executable, '-B', str(ROOT / 'scripts/validate_logo_artifact.py'), str(artifact)]
                checked = subprocess.run([*validator, '--require-colorset', name], capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                artifact.write_text(document.replace('</head>', '<style>.invalid {fill: rgb(1, 2, 3)}</style></head>'), encoding='utf-8')
                rejected = subprocess.run(validator, capture_output=True, text=True)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn('forbidden functional color', rejected.stdout)
                if name == 'colorset1':
                    mismatched = document.replace('sequence: ["#9e1b32", "#b5b5b5"', 'sequence: ["#b5b5b5", "#9e1b32"', 1)
                    self.assertNotEqual(mismatched, document)
                    artifact.write_text(mismatched, encoding='utf-8')
                    rejected = subprocess.run(validator, capture_output=True, text=True)
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn('registries differ', rejected.stdout)
                    # Both JSON copies can agree with each other and still contradict the film contract.
                    mismatch = document.replace('"accentSoft":"#ffffff"', '"accentSoft":"#ffccd5"')
                    self.assertNotEqual(mismatch, document)
                    artifact.write_text(mismatch, encoding='utf-8')
                    rejected = subprocess.run(validator, capture_output=True, text=True)
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn('differs from the Line World contract', rejected.stdout)


if __name__ == '__main__':
    unittest.main()
