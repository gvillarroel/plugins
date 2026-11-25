"""Check word-index binding, on-screen attention and deterministic rendering on the voice clock."""
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.61.0", "Pillow>=10,<13"]
# ///
import unittest

from playwright.sync_api import sync_playwright
from adapt_motion import adapt
from analyze_pose_mentions import compare, observations, summarize
from generate_motion import launch, setup
from narration_poses import pose_at


def request():
    return {"brief":"Destinos de cada envío","rows":[{"from":"Central","to":"Aurora"},{"from":"Central","to":"Ribera"}],
            "narration":{"duration_s":8,"words":[{"text":"Aurora","start_s":2},{"text":"Aurora","start_s":6.5}],
                         "cues":[{"target":"Central","role":"context","mention_s":.6},
                                 {"target":"Aurora","role":"readable","word_index":0,"offset_s":-.2},
                                 {"target":"Ribera","role":"enter","mention_s":4},
                                 {"target":"Aurora","role":"emphasis","word_index":1,"hold_s":.6}]}}


class NarrationPoseTests(unittest.TestCase):
    def test_caption_windows_and_pose_bounds_do_not_collapse_to_an_instant(self):
        self.assertEqual(compare([4.0,4.2],[3.5,4.4]),{"delta_s":[-.4,.7],"timing":"unresolved"})
        self.assertEqual(compare([4.04,4.08],4.06)["timing"],"near")
        rows=observations()
        self.assertEqual(len({(r["video_id"],r["passage_index"]) for r in rows}),40)
        count=summarize(rows)["counts"]["direct"]
        self.assertEqual(sum(count["primary"].values()),32)
        self.assertEqual(count["by_pose"]["appearance"],dict(before=19,near=1,after=2,unresolved=3))

    def test_distinguishes_present_arriving_and_repeated_entity(self):
        recipe,report=adapt(request()); props=recipe["scenes"][0]["props"]
        cues=report["narration"]["cues"]
        self.assertEqual([c["frame"] for c in cues],[15,44,96,156])
        self.assertEqual(cues[0]["check"],"already-visible")
        self.assertEqual(cues[1]["word"],"Aurora")
        nodes={n["label"]:n for n in props["nodes"]}
        self.assertAlmostEqual(pose_at(props["poseClock"],1.8/8),nodes["Aurora"]["enter"][1])
        self.assertAlmostEqual(pose_at(props["poseClock"],.5),nodes["Ribera"]["enter"][0])
        self.assertEqual(props["poseFocus"],[[nodes["Aurora"]["id"],6.5/8,7.1/8]])
        self.assertEqual(props["poseLabels"],{nodes["Aurora"]["id"]:1.8/8})
        self.assertGreaterEqual(recipe["scenes"][0]["hold"],2.5)

    def test_landmarks_must_agree_with_the_original_order(self):
        for i,change in ((0,{"target":"Aurora"}),(1,{"word_index":23}),(2,{"mention_s":1}),
                         (2,{"mention_s":10}),(2,{"target":"Sala desconocida"}),(3,{"word_index":0,"offset_s":-1.8})):
            r=request();r["narration"]["cues"][i].update(change)
            with self.subTest(i=i, change=change), self.assertRaises(ValueError): adapt(r)

    def test_author_can_pin_a_pose_in_a_specialized_diagram(self):
        r={"brief":"Probar pertenencia","intent":"bit-probe","content":{"labels":["A","B","C"],
           "bits":{"size":6,"groups":[[0,2],[1,3],[1,4]]}},
           "narration":{"duration_s":7,"cues":[{"target":"C","role":"result","mention_s":5,"pose":.91}]}}
        recipe,_=adapt(r)
        self.assertEqual(recipe["scenes"][0]["props"]["poseClock"],[[0,0],[5/7,.91],[1,1]])
        del r["narration"]
        self.assertNotIn("poseClock",adapt(r)[0]["scenes"][0]["props"])

    def test_press_binds_touch_result_and_release_to_separate_frames(self):
        from narration_poses import bind
        labels = ["Maneta","Cabezal","Lámina","Huella"]
        scene = {"artifact":"contact-transfer", "props":{"labels":labels}}
        cues = [{"target":"Lámina","role":"context","mention_s":.5},
                {"target":"Maneta","role":"action","mention_s":1.01},
                {"target":"contact","mention_s":2.53},
                {"target":"Huella","role":"result","mention_s":3.01,"hold_s":.8},
                {"target":"release","mention_s":5.02}]
        score = bind(scene,{"duration_s":7,"cues":cues},24)
        self.assertEqual([c["pose"] for c in score["cues"]], [None,.12,.50,.64,.88])
        for c in score["cues"][1:]:
            self.assertAlmostEqual(pose_at(scene["props"]["poseClock"],c["frame"]/168),c["pose"])
        self.assertAlmostEqual(pose_at(scene["props"]["poseClock"],3.5/7),.64)

    def test_specialist_gets_the_real_voice_marks_as_a_handoff(self):
        r={"brief":"Comparar visitas por región","fields":{"category":"región","value":"visitas"},"unit":"visitas",
           "rows":[{"región":"Sur","visitas":3},{"región":"Norte","visitas":7}],
           "narration":{"duration_s":4,"cues":[{"target":"Sur","mention_s":1.8}]}}
        recipe,report=adapt(r)
        self.assertIsNone(recipe)
        self.assertEqual(report["narration"]["status"],"handoff")
        self.assertEqual(report["narration"]["cues"][0]["mention_s"],1.8)

    def test_painted_geometry_at_the_cue_and_on_backward_seek(self):
        recipe,_=adapt(request())
        with sync_playwright() as runtime:
            browser=launch(runtime,None)
            try:
                page,_,_=setup(browser)
                data=recipe["scenes"][0]["props"]
                result=page.evaluate("""props=>{
                    const c=document.createElement('canvas');c.width=960;c.height=540;
                    const g=c.getContext('2d',{willReadFrequently:true});
                    const at=t=>{LineWorldPresets.drawArtifact(g,'staged-network',t,props,{mode:'solid'});
                        const pix=(x,y)=>Array.from(g.getImageData(x,y,1,1).data).slice(0,3);
                        return [pix(820,100),pix(820,445),c.toDataURL()];};
                    return [at(1.85),at(4),at(5.9),at(6.6),at(7.5),at(1.85)]
                        .map(([a,b,png],i,arr)=>[a,b,png===arr[0][2]]);
                }""",data)
                self.assertEqual(result[0][1],[255]*3)
                self.assertEqual(result[1][1],[255]*3)
                self.assertNotEqual(result[2][1],[255]*3)
                self.assertEqual(result[3][0],[158,27,50])
                self.assertNotEqual(result[4][0],[158,27,50])
                self.assertTrue(result[-1][2])
                shown=page.evaluate("""props=>{
                    const c=document.createElement('canvas');c.width=960;c.height=540;
                    const g=c.getContext('2d');let painted=[];
                    g.fillText=text=>painted.push(text);
                    return [43,44].map(frame=>{painted=[];LineWorldPresets.drawArtifact(g,'staged-network',frame/24,props);
                        return painted.includes('Aurora');});
                }""",data)
                self.assertEqual(shown,[False,True])
            finally: browser.close()


if __name__=="__main__": unittest.main()
