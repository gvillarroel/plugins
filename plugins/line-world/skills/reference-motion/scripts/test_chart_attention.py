"""Check the actual number on an arc and count distinct bars whose geometry moves."""
import unittest

from playwright.sync_api import sync_playwright
from generate_motion import launch,setup
from motion_recipe import reveal_time

TRACE = """({kind,props,width,height,fps,frames}) => {
  const c=document.createElement('canvas'); c.width=width; c.height=height;
  const ctx=c.getContext('2d'); let bars,labels,circles; let labelWidth=0;
  const fill=ctx.fillRect, text=ctx.fillText, arc=ctx.arc;
  ctx.fillRect=function(x,y,w,h){
    if(['#b5b5b5','#9e1b32'].includes(this.fillStyle)){
      const point=new DOMPoint(x+w/2,0).matrixTransform(this.getTransform());
      const matrix=this.getTransform();
      const id=[matrix.e.toFixed(1),matrix.f.toFixed(1),point.x.toFixed(1)].join('/');
      bars[id]=[y,w,h];
    }
    return fill.apply(this,arguments);
  };
  ctx.fillText=function(t){
    labels.push(t);
    if(t.includes('%')) labelWidth=Math.max(labelWidth,this.measureText(t).width);
    return text.apply(this,arguments);
  };
  ctx.arc=function(x,y,r,a,b){circles.push([x,y,r,a,b]);return arc.apply(this,arguments);};
  const digits=new Set(), activeCounts=[];
  let last=null,lastLabels=[],first=null,currentArcs=[],seenMarker=false,firstTip=null;
  for(let frame=0;frame<frames;frame++){
    bars={};labels=[];circles=[];
    LineWorldMotion.artifact(ctx,kind,frame/fps,props,{width,height,mode:'solid'});
    for(const t of labels) if(t.includes('%')) digits.add(t);
    if(last){
      let active=0;
      for(const id of new Set([...Object.keys(bars),...Object.keys(last)])){
        const a=last[id] || [0,0,0], b=bars[id] || [0,0,0];
        if((a[1]*a[2] || b[1]*b[2]) && a.some((v,k)=>Math.abs(v-b[k])>.0001)) active++;
      }
      activeCounts.push(active);
    }
    if(frame===0) first=labels.filter(t=>t.includes('%'));
    const tip=circles.find(a=>a[2]>0 && a[2]<Math.min(width,height)*.035);
    if(tip && firstTip && Math.hypot(tip[0]-firstTip[0],tip[1]-firstTip[1])>.1) seenMarker=true;
    if(tip && !firstTip)firstTip=tip;
    last=bars;lastLabels=labels;currentArcs=circles;
  }
  return {distinctNumbers:[...digits],labelWidth,first,final:lastLabels,arcs:currentArcs,seenMarker,peak:Math.max(0,...activeCounts),
          counts:[...new Set(activeCounts)],finalBars:last};
}"""


class ChartAttention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime=cls.enterClassContext(sync_playwright())
        browser=launch(runtime,None)
        cls.addClassCleanup(browser.close)
        cls.page,_,_=setup(browser)

    def sample(self,kind,props,size=(390,844),fps=24):
        duration=reveal_time(kind,props)
        return self.page.evaluate(TRACE,{"kind":kind,"props":props,"width":size[0],"height":size[1],
                                        "fps":fps,"frames":round((duration+.5)*fps)+1})

    def test_ring_names_the_requested_quantity_during_the_entire_trace(self):
        for value,number in [(0,"0"),(.125,"0,125"),(62.5,"62,5"),(75,"75"),(100,"100")]:
            for size in [(640,360),(390,844)]:
                with self.subTest(value=value,size=size):
                    row=self.sample("chart-ring",{"value":value,"duration":2.4,"label":"Ocupación del andén"},size)
                    self.assertEqual(row["distinctNumbers"],[number+" %"])
                    self.assertEqual(row["first"],row["distinctNumbers"])
                    self.assertLessEqual(row["labelWidth"],1.63*row["arcs"][0][2])
                    self.assertEqual(row["seenMarker"],value>0)
                    self.assertAlmostEqual(abs(row["arcs"][1][4]-row["arcs"][1][3])/(2*3.141592653589793),value/100)

    def test_larger_comparisons_keep_at_most_three_bars_moving(self):
        for n in [2,3,4,5,7,8,10]:
            values=[([2,-3,9,4,-6,8,11,-5,7,3])[i] for i in range(n)]
            labels=[chr(65+i) for i in range(n)]
            for focus in [False,True]:
                props={"title":"Medidas","labels":labels,"values":values,"duration":1.2}
                if focus: props.update(focusHold=1.5,highlightIndex=n//2)
                data=self.sample("data-chart",props)
                with self.subTest(n=n,focus=focus):
                    self.assertLessEqual(data["peak"],3)
                    self.assertGreaterEqual(data["peak"],min(2,n-int(focus)))
                    self.assertEqual(len(data["finalBars"]),n)
                    self.assertTrue(set(labels).issubset(data["final"]))
                    self.assertTrue({str(v) for v in values}.issubset(data["final"]))

    def test_group_boundaries_are_settled_at_delivery_rates(self):
        props={"title":"Lecturas","values":[5,8,11,2,4,1,6,3],"labels":list("ABCDEFGH"),"duration":.85}
        for fps in (12,15,24,25,30,50,60):
            with self.subTest(fps=fps):
                result=self.sample("data-chart",props,(640,360),fps)
                self.assertEqual(result["peak"],3)
                self.assertEqual(set(result["counts"]),{0,2,3})

    def test_two_dashboard_cards_complete_their_comparisons_in_order(self):
        for n in (4,7,11):
            cards=[{"title":title,"values":list(range(1,n+1)),"labels":[chr(65+i) for i in range(n)]}
                   for title in ("Primera","Segunda")]
            result=self.sample("dashboard-stack",{"cards":cards,"beat":2.0})
            with self.subTest(n=n):
                self.assertGreaterEqual(result["peak"],2)
                self.assertLessEqual(result["peak"],3)
                self.assertEqual(len(result["finalBars"]),2*n)


if __name__=="__main__":
    unittest.main()
