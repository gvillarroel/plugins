"""Prove that the renderer rejects unreadable labels, non-solid paints and reversals."""
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path
from PIL import Image

sys.dont_write_bytecode=True
from playwright.sync_api import sync_playwright
from generate_motion import ROOT, audit_plan, check_transitions, example, launch, load, setup, render, image_at
from verify_movie import verify_movie


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime=sync_playwright().start()
        cls.browser=launch(cls.runtime,None)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.page,self.defaults,self.transitions=setup(self.browser)
        self.addCleanup(self.page.close)
        self.recipe=example("type-title",self.defaults,self.transitions)

    def test_tiny_label_is_rejected(self):
        self.recipe["scenes"][0]["props"]["title"]="Texto demasiado largo para una línea "*24
        plan=load(self.page,self.recipe,ROOT,self.defaults,self.transitions)
        with self.assertRaisesRegex(ValueError,"demasiado pequeño"):
            audit_plan(self.page,plan)

    def test_gradient_is_rejected_even_with_two_valid_end_colors(self):
        self.page.evaluate("""() => {
          const p=CanvasRenderingContext2D.prototype, draw=p.fillRect;
          p.fillRect=function(...args) {
            this.save();
            const g=this.createLinearGradient(0,0,this.canvas.width,0);
            g.addColorStop(0,'#ffffff');g.addColorStop(1,'#e7e7e7');this.fillStyle=g;
            draw.apply(this,args);this.restore();
          };
        }""")
        plan=load(self.page,self.recipe,ROOT,self.defaults,self.transitions)
        with self.assertRaisesRegex(ValueError,"paleta sólida"):
            audit_plan(self.page,plan)

    def test_backwards_mask_is_rejected_despite_correct_endpoints(self):
        self.page.evaluate("""() => {
          const m=LineWorldMotion;
          globalThis.LineWorldMotion={...m,transition(ctx,id,p,...args) {
            m.transition(ctx,id,id==='push-left'&&p>.58&&p<.7?.18:p,...args);
          }};
        }""")
        with self.assertRaisesRegex(Exception,"invierte el avance"):
            check_transitions(self.page)

    def test_focus_stays_legible_while_the_other_bars_arrive(self):
        recipe=example("data-chart",self.defaults,self.transitions)
        recipe["scenes"][0]["props"].update(focusHold=2,highlightIndex=2)
        plan=load(self.page,recipe,ROOT,self.defaults,self.transitions)
        reading=audit_plan(self.page,plan)[0]["reading"]
        self.assertGreater(len(reading["frames"]),1)
        self.assertGreaterEqual(reading["labels"]["12"]["mobileInkHeight"],7.8)
        self.assertIn("14 h",reading["labels"])

    def test_missing_anchor_text_is_rejected_even_if_the_bar_is_present(self):
        recipe=example("data-chart",self.defaults,self.transitions)
        recipe["scenes"][0]["props"].update(focusHold=2,highlightIndex=2)
        plan=load(self.page,recipe,ROOT,self.defaults,self.transitions)
        self.page.evaluate("""() => {
          const prototype=CanvasRenderingContext2D.prototype, paint=prototype.fillText;
          prototype.fillText=function(label,...args){if(String(label)!=='12')paint.call(this,label,...args);};
        }""")
        with self.assertRaisesRegex(ValueError,"No se dibujó el texto clave: 12"):
            audit_plan(self.page,plan)

    def test_encoded_single_frame_regression_with_identical_clock(self):
        recipe=example("type-title",self.defaults,self.transitions)
        recipe.update(width=384,height=216,fps=12)
        plan=load(self.page,recipe,ROOT,self.defaults,self.transitions)
        with tempfile.TemporaryDirectory() as tmp:
            good,bad=(Path(tmp)/s for s in ("good.mp4","bad.mp4"))
            result=render(self.page,plan,good)
            self.assertEqual(result["frames"],plan["frames"])
            subprocess.run(["ffmpeg","-v","error","-i",str(good),"-an","-vf",
                            "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='eq(n,30)'",
                            "-c:v","libx264","-crf","17","-pix_fmt","yuv420p",str(bad)],check=True)
            with self.assertRaisesRegex(ValueError,"fotograma 30"):
                verify_movie(bad,plan,lambda f:image_at(self.page,f))

    def test_camera_keeps_moving_under_fixed_readable_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=192x108:rate=17:duration=5",
                            "-c:v","libvpx-vp9","-threads","1","-deadline","realtime",str(root/"source.webm")],check=True)
            recipe={"version":1,"fps":12,"width":384,"height":216,"assets":{
                "camera":{"path":"source.webm","in_s":.6,"out_s":4.2,"fit":"cover"}},
                "scenes":[{"id":"camera","artifact":"caption-overlay","props":{"title":"Prueba","media":"camera"}}]}
            plan=load(self.page,recipe,root,self.defaults,self.transitions)
            scene=plan["scenes"][0]
            hold=scene["reveal"]
            seen=image_at(self.page,hold+5)
            self.assertNotEqual(seen,image_at(self.page,hold+10))
            self.assertEqual(seen,image_at(self.page,hold+5))
            self.assertEqual(image_at(self.page,scene["end"]-1),image_at(self.page,scene["end"]-3))
            reviewed=audit_plan(self.page,plan)[0]
            self.assertTrue(reviewed["hold_media"]["image_changed"])
            self.assertIn("Prueba",reviewed["reading"]["hold_label_positions"])
            good,bad=root/"good.mp4",root/"bad.mp4"
            self.assertEqual(render(self.page,plan,good)["frames"],scene["end"])
            subprocess.run(["ffmpeg","-v","error","-i",str(good),"-vf",
                            f"trim=end_frame={hold+2},tpad=stop_mode=clone:stop_duration=8",
                            "-frames:v",str(scene["end"]),"-c:v","libx264",str(bad)],check=True)
            with self.assertRaisesRegex(ValueError,"el MP4 no reproduce la receta"):
                verify_movie(bad,plan,lambda f:image_at(self.page,f))
            recipe["assets"]["camera"]["out_s"]=8
            with self.assertRaisesRegex(ValueError,"fuera de los"):
                load(self.page,recipe,root,self.defaults,self.transitions)

    def test_focal_crop_and_contain(self):
        colors=self.page.evaluate("""() => {
          const src=document.createElement('canvas');src.width=100;src.height=200;
          const art=src.getContext('2d');art.fillStyle='blue';art.fillRect(0,0,100,200);
          art.fillStyle='red';art.fillRect(0,0,100,40);
          const canvas=document.createElement('canvas');canvas.width=200;canvas.height=100;
          const ctx=canvas.getContext('2d');
          function sample(fit,focal,x=100,y=20) {
            LineWorldMotion.media(ctx,{lineWorldMedia:true,element:src,fit,focal},0,0,200,100);
            return Array.from(ctx.getImageData(x,y,1,1).data).slice(0,3);
          }
          return [sample('cover',[.5,.05]),sample('cover',[.5,.5]),sample('contain',[.5,.05],10)];
        }""")
        self.assertEqual(colors,[[255,0,0],[0,0,255],[255,255,255]])

    def test_dashboard_comparison_uses_shared_scale_and_fixed_titles(self):
        plan=load(self.page,example("dashboard-stack",self.defaults,self.transitions),ROOT,self.defaults,self.transitions)
        result=self.page.evaluate("""async ([during,settled])=>{
          const proto=CanvasRenderingContext2D.prototype,paint=proto.fillRect,text=proto.fillText;
          async function sample(frame){
            const bars=[],titles={};
            proto.fillRect=function(x,y,w,h){
              if(this.fillStyle==="#9e1b32" && h>1) bars.push(h*this.getTransform().d);
              return paint.call(this,x,y,w,h);
            };
            proto.fillText=function(label,x,y,...args){
              if(String(label).startsWith("Salidas")){const p=this.getTransform().transformPoint({x,y});titles[label]=[p.x,p.y];}
              return text.call(this,label,x,y,...args);
            };
            try{await MotionRecipe.draw(frame);return {bars,titles};}
            finally{proto.fillRect=paint;proto.fillText=text;}
          }
          return [await sample(during),await sample(settled)];
        }""",[round(3.33*plan["fps"]),plan["frames"]-1])
        early,late=result
        self.assertEqual(early["titles"],late["titles"])
        self.assertEqual(len(late["bars"]),2)
        self.assertAlmostEqual(late["bars"][0]/late["bars"][1],12/8,places=3)

    def test_focus_frame_contains_category_and_value(self):
        plan=load(self.page,example("chart-focus",self.defaults,self.transitions),ROOT,self.defaults,self.transitions)
        result=self.page.evaluate("""async frame=>{
          const pr=CanvasRenderingContext2D.prototype, txt=pr.fillText,stroke=pr.strokeRect;
          const labels={},rects=[];
          pr.fillText=function(v,x,y,...args){
            if(["12","14 h"].includes(String(v))){
              const m=this.measureText(v),t=this.getTransform();
              const a=t.transformPoint({x:x-m.actualBoundingBoxLeft,y:y-m.actualBoundingBoxAscent});
              const b=t.transformPoint({x:x+m.actualBoundingBoxRight,y:y+m.actualBoundingBoxDescent});
              labels[v]=[a.x,a.y,b.x,b.y];
            }
            return txt.call(this,v,x,y,...args);
          };
          pr.strokeRect=function(x,y,w,h){if(this.strokeStyle==="#9e1b32")rects.push([x,y,x+w,y+h]);return stroke.call(this,x,y,w,h);};
          try{await MotionRecipe.draw(frame);return {labels,rect:rects.at(-1)};}finally{pr.fillText=txt;pr.strokeRect=stroke;}
        }""",plan["frames"]-1)
        x,y,right,bottom=result["rect"]
        self.assertEqual(set(result["labels"]),{"12","14 h"})
        for left,top,r,b in result["labels"].values():
            self.assertTrue(x<left and y<top and r<right and b<bottom,result)

    def test_media_captions_wait_for_join_and_keep_subject_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            Image.new("RGB",(180,100),"#42657c").save(base/"photo.png")
            for transition in self.transitions:
                spec={"version":1,"fps":12,"width":384,"height":216,"assets":{"photo":{"path":"photo.png","focal":[.5,.8]}},
                      "scenes":[{"id":"a","artifact":"type-title","props":{"title":"A"}},
                                {"id":"b","artifact":"caption-overlay","props":{"media":"photo","title":"Última palabra"},
                                 "transition":{"id":transition,"reason":"Cambiar de plano"}}]}
                sc=load(self.page,spec,base,self.defaults,self.transitions)["scenes"][1]
                start,span=sc["start"],sc["bridge"]
                data=self.page.evaluate("""async ([first,last,ready])=>{
                  const proto=CanvasRenderingContext2D.prototype,orig=proto.fillText,ys=[];
                  proto.fillText=function(label,x,y,...args){
                    if(label==="Última palabra")ys.push(this.getTransform().transformPoint({x,y}).y);
                    return orig.call(this,label,x,y,...args);};
                  try{
                    await MotionRecipe.draw(first);const firstCount=ys.length;
                    await MotionRecipe.draw(last);const lastCount=ys.length;
                    await MotionRecipe.draw(ready);
                    const ctx=MotionRecipe.canvas.getContext("2d");
                    return {firstCount,lastCount,y:ys.at(-1),center:[...ctx.getImageData(192,108,1,1).data].slice(0,3)};
                  }finally{proto.fillText=orig;}
                }""",[start+span//2,start+span-1,start+span])
                if span>1:
                    self.assertEqual(data["firstCount"],0,transition)
                    self.assertEqual(data["lastCount"],0,transition)
                self.assertLess(data["y"],216/3,transition)
                self.assertEqual(data["center"],[66,101,124],transition)


if __name__=="__main__":
    unittest.main()
