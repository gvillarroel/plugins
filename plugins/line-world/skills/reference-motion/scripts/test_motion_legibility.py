"""Measure actual Canvas primitives at the delivery size and the 390 px viewport."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

sys.dont_write_bytecode = True
from generate_motion import ROOT, launch, load, setup, video_frames
from motion_recipe import check_props, reveal_time
from review_catalogue import make_recipe, portrait_recipe


TRACE = """
({kind,props,frames,fps,width=640,height=360}) => {
  const canvas=document.createElement("canvas");
  canvas.width=width;
  canvas.height=height;
  const ctx=canvas.getContext("2d");
  const source=(width,height,color)=>{
    const tile=document.createElement("canvas");
    tile.width=width;
    tile.height=height;
    const tileContext=tile.getContext("2d");
    tileContext.fillStyle=color;
    tileContext.fillRect(0,0,width,height);
    return tile;
  };
  if (kind==="guest-grid") props.guests.forEach((guest,i)=>{
    guest.media=i===0?source(512,512,"#9e1b32"):source(847,1280,"#696969");
  });
  if (kind==="slide-pip") {
    props.media=source(512,512,"#9e1b32");
    props.slide=source(640,360,"#696969");
  }
  let trace,path,arc;
  for (const name of ["beginPath","arc","moveTo","lineTo","stroke","fillText","drawImage","rect"]) {
    const original=ctx[name];
    ctx[name]=function(...args) {
      if(name==="beginPath") {path=[];arc=null;}
      if(name==="arc") {
        arc=args.slice(0,3);
        trace.circles.push(arc);
      }
      if(name==="moveTo" || name==="lineTo") path.push(args);
      if(name==="stroke" && path.length===2) trace.lines.push(path);
      if(name==="stroke") trace.strokes.push({path,arc,width:this.lineWidth});
      if(name==="rect") trace.clips.push(args);
      if(name==="fillText") {
        const [text,x,y]=args, m=this.measureText(text);
        trace.labels.push({text,x:x-m.actualBoundingBoxLeft,y:y-m.actualBoundingBoxAscent,inkRight:x+m.actualBoundingBoxRight,
          bottom:y+m.actualBoundingBoxDescent,
          mobileInk:(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent)*Math.min(1,390/width)});
      }
      if(name==="drawImage") {
        const [source,x,y,w,h]=args, transform=this.getTransform();
        trace.images.push({source:[source.width,source.height],box:[x+transform.e,y+transform.f,w,h]});
      }
      return original.apply(this,args);
    };
  }
  return frames.map(frame=>{
    trace={circles:[],lines:[],strokes:[],labels:[],images:[],clips:[]};
    LineWorldMotion.artifact(ctx,kind,frame/fps,props);
    return trace;
  });
}
"""
COLLINS = [.346, .129, .1875, .1875]
JOHNSON = [.229, .203, .511, .338]


def portrait_region(image, face):
    x, y, width, height = image["box"]
    left, top, face_width, face_height = face
    return (x+width*left, y+height*top, width*face_width, height*face_height)


class RecipeLegibilityTests(unittest.TestCase):
    def test_optional_face_and_anchor_stay_within_their_coordinate_space(self):
        check_props("slide-pip", {"presenter": "Eileen Collins", "faceBox": COLLINS}, {})
        check_props("orbital-caption", {"anchor": [.369, .718], "title": "Asa"}, {})
        with self.assertRaisesRegex(ValueError, "faceBox"):
            check_props("slide-pip", {"faceBox": [.9, .2, .2, .5]}, {})
        with self.assertRaisesRegex(ValueError, "anchor"):
            check_props("orbital-caption", {"anchor": [-.1, .718], "title": "Asa"}, {})

    def test_video_cache_in_memory_matches_disk_payload_and_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            movie=folder/"source.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=48x32:rate=30000/1001",
                            "-t","0.5","-c:v","libx264","-threads","1",str(movie)],check=True)
            disk=folder/"jpeg"
            memory=[]
            plan={"width":390,"height":844,"fps":24}
            clip={"in_s":.06,"out_s":.4}
            expected=video_frames(movie,clip,plan,8,disk)
            actual=video_frames(movie,clip,plan,8,memory)
            self.assertEqual(actual,expected)
            self.assertEqual(memory,[path.read_bytes() for path in sorted(disk.glob("*.jpg"))])


class RenderLegibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = sync_playwright().start()
        cls.browser = launch(cls.runtime, None)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.page, self.defaults, self.transitions = setup(self.browser)
        self.addCleanup(self.page.close)

    def trace(self, kind, props, frames, fps=24, *, width=640, height=360):
        return self.page.evaluate(TRACE, {"kind": kind, "props": props, "frames": list(frames),
                                          "fps": fps, "width": width, "height": height})

    def test_concept_diagram_serializes_edges_and_nodes_and_keeps_span_labels_intact(self):
        props = self.defaults["concept-diagram"]
        for fps in (24, 60):
            complete = int(reveal_time("concept-diagram", props)*fps)
            frames = self.trace("concept-diagram", props, range(complete+4), fps)
            self.assertEqual({label["text"] for label in frames[-1]["labels"]},
                             {"Central", "Andén 1", "Vestíbulo", "Andén 2"})
            self.assertGreaterEqual(min(label["mobileInk"] for label in frames[-1]["labels"]), 9)
            self.assertEqual(len(frames[-1]["lines"]), 3)
            self.assertEqual(frames[-1], frames[complete])
            peak = 0
            for previous, current in zip(frames, frames[1:]):
                old = {**{("edge", *start): end for start, end in previous["lines"]},
                       **{("node", x, y): radius for x, y, radius in previous["circles"]}}
                new = {**{("edge", *start): end for start, end in current["lines"]},
                       **{("node", x, y): radius for x, y, radius in current["circles"]}}
                peak = max(peak, sum(old.get(key) != new.get(key) for key in old.keys() | new.keys()))
            self.assertGreater(peak, 0)
            self.assertLessEqual(peak, 2)

    def test_guest_faces_share_scale_and_the_names_stay_below_both_photos(self):
        props = {"guests": [{"name": "Eileen Collins", "faceBox": COLLINS},
                            {"name": "Katherine Johnson", "faceBox": JOHNSON}]}
        frame, = self.trace("guest-grid", props, [60])
        faces = [portrait_region(image, face) for image, face in zip(frame["images"], (COLLINS, JOHNSON))]
        photos = frame["clips"][::2]
        for face, photo, label in zip(faces, photos, frame["labels"]):
            x, y, w, h = face
            left, top, width, height = photo
            self.assertGreaterEqual(x, left)
            self.assertLessEqual(x+w, left+width)
            self.assertGreaterEqual(y, top)
            self.assertLessEqual(y+h, top+height)
            self.assertGreaterEqual(label["y"], top+height)
            self.assertGreaterEqual(label["mobileInk"], 9)
        self.assertAlmostEqual(faces[0][2], faces[1][2], delta=1)
        self.assertGreaterEqual(faces[0][2], 125)

    def test_anchored_caption_uses_two_contrast_strokes_on_one_short_path(self):
        props = {"title": "Asa", "x": .224, "y": .70, "anchor": [.369, .718], "delay": .72}
        frame, = self.trace("orbital-caption", props, [50])
        self.assertEqual(frame["lines"], [frame["lines"][0]]*2)
        start, end = frame["lines"][0]
        self.assertEqual(start, [.369*640, .718*360])
        self.assertAlmostEqual(end[0], .224*640+.122*360, delta=1)
        self.assertLess(abs(end[0]-start[0]), .085*640)
        self.assertGreaterEqual(frame["labels"][0]["mobileInk"], 9)

    def test_slide_waits_until_the_presenter_reaches_the_plot_free_corner(self):
        props = {"presenter": "Eileen Collins", "faceBox": COLLINS}
        opening, moving, settled = self.trace("slide-pip", props, [16, 40, 65])
        self.assertEqual([label["text"] for label in opening["labels"]], ["Eileen Collins"])
        self.assertEqual(len(opening["images"]), 1)
        self.assertEqual(len(moving["images"]), 1)
        self.assertEqual([image["source"] for image in settled["images"]], [[640, 360], [512, 512]])
        self.assertGreater(portrait_region(opening["images"][0], COLLINS)[2], 170)
        _, top, _, height = settled["clips"][-1]
        self.assertLess(top+height, 103)
        self.assertEqual(settled, self.trace("slide-pip", props, [125])[0])

    def test_focus_holds_its_full_duration_after_a_vertical_shutter(self):
        fps = 30
        props = {**self.defaults["data-chart"], "focusHold": 1.5}
        recipe = {"version": 1, "width": 360, "height": 640, "fps": fps, "scenes": [
            {"id": "speaker", "artifact": "speaker-id", "props": self.defaults["speaker-id"]},
            {"id": "comparison", "artifact": "data-chart", "props": props,
             "transition": {"id": "shutter-close", "seconds": 1.0}},
        ]}
        scene = load(self.page, recipe, ROOT, self.defaults, self.transitions)["scenes"][1]
        begin = scene["start"] + scene["bridge"]
        last_focus = begin + int(props["focusHold"]*fps)-1
        calls = self.page.evaluate("""async frames => {
          const ctx=MotionRecipe.canvas.getContext("2d"), original=ctx.fillText;
          let labels=[];
          ctx.fillText=function(value,...args) {
            labels.push(value);
            return original.call(this,value,...args);
          };
          const snapshots=[];
          try {
            for(const frame of frames) {
              labels=[];
              await MotionRecipe.draw(frame);
              snapshots.push(labels);
            }
          } finally {ctx.fillText=original;}
          return snapshots;
        }""", [scene["start"]+scene["bridge"]//2, begin-1, begin, last_focus, begin+scene["reveal"]])
        for masked in calls[:2]:
            self.assertNotIn("12", masked)
            self.assertNotIn("14 h", masked)
        for focused in calls[2:4]:
            self.assertIn("12", focused)
            self.assertIn("14 h", focused)
            self.assertNotIn("18 h", focused)
        self.assertIn("18 h", calls[-1])

    def test_portrait_geometry_fits_without_crossing_the_labels(self):
        for kind, frame in (("numbered-step",60),("disc-endcard",48),("chart-ring",80),("icon-card",60)):
            for side in (("left","right") if kind=="icon-card" else (None,)):
                props = dict(self.defaults[kind])
                if side:
                    props["side"]=side
                result, = self.trace(kind,props,[frame],width=390,height=844)
                left,right=390,0
                for cx,_,radius in result["circles"]:
                    left,right=min(left,cx-radius),max(right,cx+radius)
                for stroke in result["strokes"]:
                    pad=stroke["width"]/2
                    if stroke["arc"]:
                        cx,_,radius=stroke["arc"]
                        left,right=min(left,cx-radius-pad),max(right,cx+radius+pad)
                    else:
                        for x,_ in stroke["path"]:
                            left,right=min(left,x-pad),max(right,x+pad)
                self.assertGreaterEqual(left,0,kind)
                self.assertLessEqual(right,390,kind)
                if kind=="numbered-step" or side=="left":
                    self.assertLess(right,result["labels"][-1]["x"],kind)
                if side=="right":
                    self.assertGreater(left,result["labels"][-1]["inkRight"],kind)

    def test_portrait_annotation_projects_the_original_handle_into_the_crop(self):
        spec=make_recipe("join","iris-close",self.defaults,ROOT,"orbital-caption")
        portrait_recipe(spec)
        props=spec["scenes"][-1]["props"]
        result, = self.trace("orbital-caption",props,[72],width=390,height=844)
        start,end=result["lines"][0]
        self.assertAlmostEqual(start[0],67.134,places=3)
        self.assertAlmostEqual(start[1],602.563,places=3)
        self.assertGreater(start[0],0)
        self.assertGreater(end[0]-start[0],40)
        self.assertLess(end[0]-start[0],52)

    def test_portrait_slide_keeps_all_periods_and_values_readable(self):
        spans=self.page.evaluate("""() => {
          const canvas=document.createElement("canvas");canvas.width=390;canvas.height=844;
          const ctx=canvas.getContext("2d"), original=ctx.fillText, spans={};
          ctx.fillText=function(label,x,y,...rest){
            const text=this.measureText(label), transform=this.getTransform();
            const top=transform.transformPoint({x,y:y-text.actualBoundingBoxAscent}).y;
            const bottom=transform.transformPoint({x,y:y+text.actualBoundingBoxDescent}).y;
            spans[label]={top,bottom};
            return original.call(this,label,x,y,...rest);
          };
          LineWorldPresets.drawArtifact(ctx,"slide-pip",4,{slide:"@schedule",media:"@host-close",
            presenter:"Eileen Collins"});
          return spans;
        }""")
        self.assertEqual(set(spans),{"Salidas por hora","6","9","12","8","06 h","10 h","14 h","18 h"})
        for label,box in spans.items():
            self.assertGreaterEqual(box["bottom"]-box["top"],10,label)
            self.assertGreater(box["top"],.275*844,label)

    def test_portrait_question_and_dashboard_keep_long_labels_readable(self):
        question={"title":"¿Dónde está la taza?"}
        entering,settled=self.trace("question-card",question,[12,20],width=390,height=844)
        self.assertEqual(entering["labels"],[])
        label,=settled["labels"]
        self.assertEqual(label["text"],question["title"])
        self.assertGreaterEqual(label["mobileInk"],20)

        dashboard,=self.trace("dashboard-stack",self.defaults["dashboard-stack"],[165],width=390,height=844)
        titles=[label for label in dashboard["labels"] if label["text"].startswith("Salidas por hora")]
        self.assertEqual(len(titles),2)
        self.assertGreaterEqual(min(label["mobileInk"] for label in titles),17)
        self.assertGreater(titles[1]["y"]-titles[0]["y"],.40*844)

    def test_guest_names_wait_until_each_styled_join_has_finished(self):
        speaker={**self.defaults["speaker-id"],"title":"Identidad saliente","detail":"Plano original"}
        guests={"guests":[{"media":"@host-close","name":"Eileen Collins"},
                          {"media":"@guest-close","name":"Katherine Johnson"}]}
        identities={"Identidad saliente","Eileen Collins","Katherine Johnson"}
        for width,height in ((640,360),(390,844)):
            for effect in self.transitions:
                recipe={"version":1,"fps":24,"width":width,"height":height,"scenes":[
                    {"id":"speaker","artifact":"speaker-id","props":speaker},
                    {"id":"guests","artifact":"guest-grid","props":guests,"transition":{"id":effect}},
                ]}
                incoming=load(self.page,recipe,ROOT,self.defaults,self.transitions)["scenes"][-1]
                start,bridge=incoming["start"],incoming["bridge"]
                moments=[start-1,start,start+1,start+bridge//2,start+bridge-1,start+bridge]
                drawn=self.page.evaluate("""async frames => {
                    const ctx=MotionRecipe.canvas.getContext("2d"), original=ctx.fillText;
                    let labels=[];
                    ctx.fillText=function(value,...args) {
                        labels.push(value);
                        return original.call(this,value,...args);
                    };
                    try {
                        const out=[];
                        for(const frame of frames) {
                            labels=[];
                            await MotionRecipe.draw(frame);
                            out.push(labels);
                        }
                        return out;
                    } finally {ctx.fillText=original;}
                }""",moments)
                names=[identities.intersection(frame) for frame in drawn]
                self.assertEqual(names[0],{"Identidad saliente"},effect)
                if effect=="cut":
                    self.assertEqual(names[1],{"Eileen Collins","Katherine Johnson"},effect)
                else:
                    self.assertEqual(names[1],{"Identidad saliente"},effect)
                    self.assertEqual(names[2:5],[set(),set(),set()],effect)
                self.assertEqual(names[5],{"Eileen Collins","Katherine Johnson"},effect)

    def test_editorial_context_preserves_at_least_nine_pixels_of_ink(self):
        examples = {
            "type-title": {"Estación Central", "Línea Norte"},
            "metric-callout": {"12", "Salidas por hora", "14 h  ·  Estación Central"},
            "cta-card": {"Línea Norte", "Conexiones desde Central", "Consultar el plano"},
            "speaker-id": {"Eileen Collins", "Astronauta"},
            "insight-band": {"Flores", "Se abre la corola"},
        }
        for kind, expected in examples.items():
            props = dict(self.defaults[kind])
            if kind == "speaker-id":
                props.update(title="Eileen Collins", detail="Astronauta")
            if kind == "insight-band":
                props.update(kicker="", title="Flores", detail="Se abre la corola")
            frame, = self.trace(kind, props, [64])
            self.assertEqual({label["text"] for label in frame["labels"]}, expected)
            for label in frame["labels"]:
                with self.subTest(kind=kind, text=label["text"]):
                    self.assertGreaterEqual(label["mobileInk"], 9)


if __name__ == "__main__":
    unittest.main()
