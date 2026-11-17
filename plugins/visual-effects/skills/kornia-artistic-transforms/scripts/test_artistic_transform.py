#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["torch==2.15.0", "kornia==0.9.0", "numpy>=2,<3", "pillow>=11,<14", "scipy>=1.14,<2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Run meaningful image/CLI contract checks from a writable project workspace."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageOps
import torch

import artistic_transform as cli
from techniques import TECHNIQUES, Context, apply, quadtree_regions, regions_lab


SCRIPT=Path(__file__).with_name('artistic_transform.py').resolve()


def fixture(width=93,height=61,alpha=False):
    y,x=np.mgrid[:height,:width]
    rgb=np.stack(((x*7+y*3)%256,(x*3+y*11)%256,(x*13+y*5)%256),2).astype(np.uint8)
    if not alpha:return Image.fromarray(rgb,'RGB')
    mask=np.rint(np.linspace(0,255,width))[None].repeat(height,0).astype(np.uint8)
    return Image.fromarray(np.concatenate((rgb,mask[...,None]),2),'RGBA')


def pixels(path):
    with Image.open(path) as image:return np.asarray(image).copy()


class TransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        cls.artifacts=Path.cwd()/'projects'/'kornia-artistic-transforms'/'artifacts'/'tests'
        cls.artifacts.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='run-',dir=self.artifacts)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.input=self.root/'input.png';fixture().save(self.input)

    def run_args(self,*args):
        return cli.execute(cli.parser().parse_args([str(a) for a in args]))

    def process(self,*args):
        env=dict(os.environ);env['PYTHONIOENCODING']='utf-8'
        return subprocess.run([sys.executable,str(SCRIPT),*[str(a) for a in args]],
                              cwd=self.root,capture_output=True,text=True,encoding='utf-8',env=env,timeout=120)

    def test_rectangular_odd_batch_all_ten_and_portable_paths(self):
        output=self.root/'all'
        manifest=self.run_args(self.input,'--output-dir',output,'--techniques','all','--max-edge',0,'--seed',17)
        self.assertEqual([r['techniques'][0] for r in manifest['outputs']],list(TECHNIQUES))
        self.assertEqual(manifest['source']['output_size'],[93,61])
        ids=set();pixels=set()
        for row in manifest['outputs']:
            self.assertNotIn(row['id'],ids);ids.add(row['id'])
            self.assertNotIn(row['validation']['pixel_sha256'],pixels);pixels.add(row['validation']['pixel_sha256'])
            self.assertFalse(Path(row['image']).is_absolute());self.assertNotIn('\\',row['image'])
            with Image.open(output/row['image']) as image:
                self.assertEqual(image.mode,'RGBA');self.assertEqual(image.size,(93,61))
            report=json.loads((output/row['report']).read_text(encoding='utf-8'))
            resolved=(output/row['report']).parent/report['image']
            self.assertEqual(resolved.resolve(),(output/row['image']).resolve())
            self.assertEqual(report['id'],row['id'])
            self.assertTrue(report['validation']['finite_rgb'])
        for field in ('source_image','contact_sheet','gallery'):
            self.assertTrue((output/manifest[field]).is_file())
        with Image.open(output/'source.png') as image:self.assertEqual(image.size,(93,61))
        self.assertEqual(len(manifest['runtime']['engine_sha256']),64)
        self.assertIn('torch',manifest['runtime']['packages'])

    def test_downscale_only_preserves_aspect_and_never_upscales(self):
        for maximum,expected in [(41,(41,27)),(200,(93,61)),(0,(93,61))]:
            pixels,report=cli.load_image(self.input,maximum)
            self.assertEqual((pixels.shape[1],pixels.shape[0]),expected)
            self.assertEqual(report['oriented_size'],[93,61])
        narrow=self.root/'narrow.png';fixture(1,31).save(narrow)
        pixels,_=cli.load_image(narrow,9)
        self.assertEqual(pixels.shape,(9,1,4))

    def test_half_open_quadtree_covers_every_odd_pixel_once(self):
        for width,height in [(89,37),(13,1),(1,3),(1,1)]:
            rgb=np.asarray(fixture(width,height),np.float32)/255
            coverage=np.zeros((height,width),np.uint8)
            for xa,ya,xb,yb,mean,_ in quadtree_regions(rgb):
                self.assertLess(xa,xb);self.assertLess(ya,yb)
                coverage[ya:yb,xa:xb]+=1
                np.testing.assert_allclose(mean,rgb[ya:yb,xa:xb].mean((0,1)),atol=2e-4)
            np.testing.assert_array_equal(coverage,np.ones_like(coverage))

    def test_tiny_flat_and_constant_inputs_are_finite(self):
        for width,height in [(1,1),(1,7),(2,1),(11,9)]:
            for value in (.0,.45,1.):
                rgb=np.full((height,width,3),value,np.float32)
                for key in TECHNIQUES:
                    output,report=apply(rgb,key,seed=5)
                    self.assertEqual(output.shape,rgb.shape,(key,width,height))
                    self.assertTrue(np.isfinite(output).all(),key)
                    self.assertTrue((output>=0).all() and (output<=1).all(),key)
        labels,flat,count=regions_lab(Context(np.full((13,19,3),.4,np.float32),1.,4,'source'))
        self.assertEqual(count,1);self.assertEqual(len(np.unique(labels)),1)
        np.testing.assert_allclose(flat,.4,atol=3e-4)

    def test_seed_determinism_and_real_stochastic_variation(self):
        rgb=np.asarray(fixture(111,73),np.float32)/255
        first,_=apply(rgb,'hybrid-mezzotint',seed=17)
        again,_=apply(rgb,'hybrid-mezzotint',seed=17)
        different,_=apply(rgb,'hybrid-mezzotint',seed=18)
        np.testing.assert_array_equal(first,again)
        self.assertGreater(float(np.abs(first-different).mean()),.001)

    def test_alpha_is_anchored_and_explicit_background_flattens(self):
        source=self.root/'alpha.png';fixture(47,31,True).save(source)
        original=pixels(source)
        target=self.root/'styled.png'
        report=self.run_args(source,'-o',target,'--technique','directional-glass','--max-edge',0)
        output=pixels(target)
        np.testing.assert_array_equal(output[...,3],original[...,3])
        self.assertTrue(report['validation']['alpha_matches_processed_source'])
        flattened=self.root/'flattened.png'
        self.run_args(source,'-o',flattened,'--technique','cell-facets','--background','#123456','--max-edge',0)
        output=pixels(flattened)
        self.assertTrue((output[...,3]==255).all())
        np.testing.assert_array_equal(output[:,0,:3],np.tile([0x12,0x34,0x56],(31,1)))

    def test_zero_strength_preserves_rgba_including_hidden_rgb(self):
        source=self.root/'alpha.png';fixture(23,17,True).save(source)
        pixels,_=cli.load_image(source,0)
        output,_,_,_=cli.compose(pixels,['contour-strata','linked-cells'],strength=0.)
        np.testing.assert_array_equal(output,pixels)

    def test_palette_grayscale_and_exif_inputs(self):
        gray=self.root/'gray.png';Image.fromarray(np.arange(35,dtype=np.uint8).reshape(5,7),'L').save(gray)
        pixels,_=cli.load_image(gray,0)
        np.testing.assert_array_equal(pixels[...,0],pixels[...,1])
        palette=self.root/'palette.png';p=Image.new('P',(7,5));p.putpalette([255,0,0,0,255,0]+[0]*762)
        p.putpixel((1,2),1);p.save(palette,transparency=0)
        pixels,_=cli.load_image(palette,0)
        self.assertEqual(int(pixels[0,0,3]),0);self.assertEqual(int(pixels[2,1,3]),255)
        exif=self.root/'rotated.jpg';tag=Image.Exif();tag[274]=6;fixture(5,9).save(exif,exif=tag)
        pixels,report=cli.load_image(exif,0)
        with Image.open(exif) as image:expected=np.asarray(ImageOps.exif_transpose(image).convert('RGBA'))
        np.testing.assert_array_equal(pixels,expected)
        self.assertEqual(report['original_size'],[5,9]);self.assertEqual(report['oriented_size'],[9,5])

    def test_high_depth_is_rejected_and_frame_color_policy_is_reported(self):
        high=self.root/'high.png';Image.fromarray(np.arange(12,dtype=np.uint16).reshape(3,4)).save(high)
        with self.assertRaises(ValueError):cli.load_image(high)
        floating=self.root/'float.tif';Image.fromarray(np.ones((3,4),np.float32),'F').save(floating)
        with self.assertRaises(ValueError):cli.load_image(floating)
        animated=self.root/'animated.gif'
        Image.new('RGB',(4,6),'red').save(animated,save_all=True,append_images=[Image.new('RGB',(4,6),'blue')],duration=100,loop=0)
        pixels,report=cli.load_image(animated,0)
        self.assertEqual(report['frame_count'],2);self.assertEqual(report['frame_index'],0)
        np.testing.assert_array_equal(pixels[0,0,:3],[255,0,0])
        icc=self.root/'icc.png';fixture().save(icc,icc_profile=b'uninterpreted test profile')
        _,report=cli.load_image(icc)
        self.assertTrue(report['color_policy']['icc_profile_present'])
        self.assertFalse(report['color_policy']['icc_conversion_applied'])
        cmyk=self.root/'cmyk.jpg';Image.new('CMYK',(9,7),(0,100,30,0)).save(cmyk)
        self.assertEqual(cli.load_image(cmyk)[0].shape,(7,9,4))

    def test_ordered_composition_and_custom_report_path(self):
        target=self.root/'work.png';report_path=self.root/'reports'/'exact.json'
        report=self.run_args(self.input,'-o',target,'--report',report_path,'--technique','ink-strata','--technique','directional-glass','--seed',21)
        self.assertEqual([s['technique'] for s in report['stages']],['ink-strata','directional-glass'])
        saved=json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual((report_path.parent/saved['image']).resolve(),target.resolve())
        reverse=self.root/'reverse.png'
        other=self.run_args(self.input,'-o',reverse,'--technique','directional-glass','--technique','ink-strata','--seed',21)
        self.assertNotEqual(report['validation']['pixel_sha256'],other['validation']['pixel_sha256'])

    def test_no_overwrite_and_no_input_overwrite_even_with_flag(self):
        target=self.root/'output.png';target.write_bytes(b'preserve existing bytes')
        with self.assertRaises(ValueError):self.run_args(self.input,'-o',target,'--technique','hex-halftone')
        self.assertEqual(target.read_bytes(),b'preserve existing bytes')
        before=self.input.read_bytes()
        with self.assertRaises(ValueError):self.run_args(self.input,'-o',self.input,'--technique','hex-halftone','--overwrite')
        self.assertEqual(before,self.input.read_bytes())
        self.run_args(self.input,'-o',target,'--technique','hex-halftone','--overwrite')
        with Image.open(target) as image:self.assertEqual(image.mode,'RGBA')
        collision=self.root/'collision.png'
        with self.assertRaises(ValueError):self.run_args(self.input,'-o',collision,'--report',collision,'--technique','hex-halftone')
        self.assertFalse(collision.exists())

    def test_reports_block_existing_targets_before_images_are_written(self):
        target=self.root/'new.png';target.with_suffix('.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):self.run_args(self.input,'-o',target,'--technique','flow-stitch')
        self.assertFalse(target.exists())
        output=self.root/'batch';output.mkdir();(output/'manifest.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):self.run_args(self.input,'--output-dir',output,'--techniques','hex-halftone,cell-facets')
        self.assertFalse((output/'images').exists())

    def test_input_hardlink_alias_is_protected(self):
        alias=self.root/'alias.png'
        try:os.link(self.input,alias)
        except OSError as error:self.skipTest(f'Hard links unavailable on this filesystem: {error}')
        before=self.input.read_bytes()
        with self.assertRaises(ValueError):self.run_args(self.input,'-o',alias,'--technique','cell-facets','--overwrite')
        self.assertEqual(self.input.read_bytes(),before)

    def test_ids_bind_source_parameters_and_implementation(self):
        source={'sha256':'a'*64};runtime=cli.runtime_metadata();options={'seed':3}
        identifier=cli.stable_id(source,['cell-facets'],options,runtime)
        self.assertEqual(identifier,cli.stable_id(source,['cell-facets'],options,runtime))
        self.assertNotEqual(identifier,cli.stable_id(source,['cell-facets'],{'seed':4},runtime))
        changed={**runtime,'engine_sha256':'b'*64}
        self.assertNotEqual(identifier,cli.stable_id(source,['cell-facets'],options,changed))

    def test_actual_cli_lists_runs_and_fails_safely(self):
        listed=self.process('--list')
        self.assertEqual(listed.returncode,0,listed.stderr)
        self.assertEqual([line.split('\t')[0] for line in listed.stdout.splitlines()],list(TECHNIQUES))
        output=self.root/'cli.png'
        result=self.process(self.input,'-o',output,'--technique','region-hatching','--max-edge',57)
        self.assertEqual(result.returncode,0,result.stderr)
        with Image.open(output) as image:self.assertEqual(image.size,(57,37))
        self.assertTrue(output.with_suffix('.json').is_file())
        before=output.read_bytes();repeat=self.process(self.input,'-o',output,'--technique','region-hatching')
        self.assertNotEqual(repeat.returncode,0);self.assertEqual(output.read_bytes(),before)


if __name__=='__main__':unittest.main(verbosity=2)
