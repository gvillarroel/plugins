#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Behavioral contracts for the offline repository review renderer."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from render_repository_review import TEMPLATE, number_lexemes, render_report
import repository_graph as graph
from semantic_model import EngineError


def fixture():
    model = {"sources": [{"id": "s:A", "locator": "knowledge.md#L1", "text": "A capability needs a definition."}],
             "nodes": [{"id": "cap:A", "label": "A capability", "type": "Capability", "definition": "An accepted capability.", "source_ids": ["s:A"]}],
             "relations": [], "bindings": {"s:A": ["cap:A"]}}
    return {"schema_version": "1", "tool": "repository-graph", "engine_status": "completed",
            "semantic_status": "not_run", "review_revision": "a" * 64,
            "base": {"model": copy.deepcopy(model), "graph_sha256": "b" * 64, "validation": {"contract_status": "valid"}},
            "head": {"model": copy.deepcopy(model), "graph_sha256": "b" * 64, "validation": {"contract_status": "valid"}},
            "changes": [], "findings": [], "summary": {}}


@unittest.skipUnless(shutil.which("node"), "Node is required to execute selection scrolling.")
class SelectionRevealTests(unittest.TestCase):
    def reveal(self, collection, entity_id, records, anchors):
        template = TEMPLATE.read_text(encoding="utf-8")
        helper = template.split("// selection-reveal:start", 1)[1].split("// selection-reveal:end", 1)[0]
        payload = json.dumps({"collection": collection, "id": entity_id,
                              "records": records, "anchors": anchors}, ensure_ascii=True)
        invocation = """
const f=JSON.parse(process.argv[1]),before=JSON.stringify(f.records),queries=[];
const indexes={},hosts={};
const $=id=>hosts[id];
globalThis.scrollTo=()=>{throw Error('Page scroll is forbidden');};
for(const side of ['base','head']){
 indexes[side]={nodes:new Map(f.records[side].nodes.map(x=>[x.id,x])),relations:new Map(f.records[side].relations.map(x=>[x.id,x]))};
 let x=3,y=4;
 const host={clientWidth:300,clientHeight:400,clientLeft:1,clientTop:2,
  getBoundingClientRect:()=>({left:100,top:200}),
  get scrollLeft(){return x;},set scrollLeft(value){x=Math.max(0,value);},
  get scrollTop(){return y;},set scrollTop(value){y=Math.max(0,value);},
  querySelectorAll(selector){queries.push(selector);return f.anchors[side].map(n=>({dataset:{entityId:n.id},getBoundingClientRect:()=>({left:101+n.x-x,top:202+n.y-y,width:180,height:86})}));}};
 hosts[side+'-graph']=host;
}
revealSelection(f.collection,f.id);
console.log(JSON.stringify({base:{x:hosts['base-graph'].scrollLeft,y:hosts['base-graph'].scrollTop},head:{x:hosts['head-graph'].scrollLeft,y:hosts['head-graph'].scrollTop},recordsUnchanged:before===JSON.stringify(f.records),queries}));
"""
        result = subprocess.run([shutil.which("node"), "-e", helper + invocation, payload],
                                capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_large_graph_node_centers_in_both_panels_with_literal_special_id(self):
        entity_id = "term:ENVO:003']<script>\u00f1"
        records = {side: {"nodes": [{"id": entity_id}], "relations": []} for side in ("base", "head")}
        anchors = {side: [{"id": entity_id, "x": 4000, "y": 300000}] for side in ("base", "head")}
        result = self.reveal("nodes", entity_id, records, anchors)
        self.assertEqual(result["base"], {"x": 3940, "y": 299843})
        self.assertEqual(result["head"], result["base"])
        self.assertTrue(result["recordsUnchanged"])
        self.assertEqual(result["queries"], [".graph-node", ".graph-node"])

    def test_node_absent_on_one_side_preserves_that_panels_scroll(self):
        records = {"base": {"nodes": [{"id": "n"}], "relations": []},
                   "head": {"nodes": [], "relations": []}}
        anchors = {"base": [{"id": "n", "x": 400, "y": 1000}], "head": []}
        result = self.reveal("nodes", "n", records, anchors)
        self.assertEqual(result["base"], {"x": 340, "y": 843})
        self.assertEqual(result["head"], {"x": 3, "y": 4})

    def test_relationship_reveals_actual_source_endpoint_on_each_side(self):
        records = {"base": {"nodes": [{"id": "a"}], "relations": [{"id": "r", "from": "a"}]},
                   "head": {"nodes": [{"id": "b"}], "relations": [{"id": "r", "from": "b"}]}}
        anchors = {"base": [{"id": "a", "x": 400, "y": 1000}],
                   "head": [{"id": "b", "x": 900, "y": 2000}]}
        result = self.reveal("relations", "r", records, anchors)
        self.assertEqual(result["base"], {"x": 340, "y": 843})
        self.assertEqual(result["head"], {"x": 840, "y": 1843})

    def test_missing_endpoint_or_drawn_anchor_is_inspectable_without_scroll_error(self):
        records = {side: {"nodes": [], "relations": [{"id": "r", "from": "missing"}]} for side in ("base", "head")}
        result = self.reveal("relations", "r", records, {"base": [], "head": []})
        self.assertEqual(result["base"], {"x": 3, "y": 4})
        self.assertEqual(result["head"], {"x": 3, "y": 4})

    def test_absent_relation_does_not_focus_a_same_id_node_on_other_side(self):
        records = {"base": {"nodes": [{"id": "a"}], "relations": [{"id": "r", "from": "a"}]},
                   "head": {"nodes": [{"id": "r"}], "relations": []}}
        anchors = {"base": [{"id": "a", "x": 400, "y": 1000}],
                   "head": [{"id": "r", "x": 700, "y": 900}]}
        result = self.reveal("relations", "r", records, anchors)
        self.assertEqual(result["base"], {"x": 340, "y": 843})
        self.assertEqual(result["head"], {"x": 3, "y": 4})


class RendererTests(unittest.TestCase):
    def test_repeat_render_is_byte_identical(self):
        self.assertEqual(render_report(fixture()).encode(), render_report(fixture()).encode())

    def test_input_dict_order_does_not_change_render(self):
        value = fixture()
        self.assertEqual(render_report(value), render_report(dict(reversed(list(value.items())))))

    def test_script_termination_cannot_escape_json(self):
        value = fixture()
        passage = '__REVIEW_JSON__ __REVIEW_NUMBER_LEXEMES__ </script><script>window.evil=true</script><img src=x onerror="evil()">&\u2028'
        value["base"]["model"]["sources"][0]["text"] = passage
        value["base"]["model"]["nodes"][0]["attributes"] = {"</script>&": 7}
        html = render_report(value)
        data = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S).group(1)
        lexeme_data = re.search(r'<script id="review-number-lexemes" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("<", data)
        self.assertNotIn("&", data)
        self.assertNotIn("<", lexeme_data)
        self.assertNotIn("&", lexeme_data)
        self.assertEqual(json.loads(data)["base"]["model"]["sources"][0]["text"], passage)
        self.assertEqual(json.loads(lexeme_data)["/base/model/nodes/0/attributes/<~1script>&"], "7")
        self.assertIn('__REVIEW_JSON__ __REVIEW_NUMBER_LEXEMES__ </script><script>window.evil=true</script>',
                      json.loads(data)["base"]["model"]["sources"][0]["text"])
        self.assertNotIn('<script>window.evil=true', html)

    def test_numeric_lexeme_map_covers_json_numbers_but_not_booleans_or_null(self):
        value = fixture()
        value["base"]["model"]["nodes"][0]["attributes"] = {
            "large": 9007199254740993, "safe": 42, "negative_zero": -0.0,
            "enabled": True, "missing": None,
        }
        value["head"]["validation"]["samples"] = [1.25]
        lexemes = number_lexemes(value)
        self.assertEqual(lexemes["/base/model/nodes/0/attributes/large"], "9007199254740993")
        self.assertEqual(lexemes["/base/model/nodes/0/attributes/safe"], "42")
        self.assertEqual(lexemes["/base/model/nodes/0/attributes/negative_zero"], "-0.0")
        self.assertEqual(lexemes["/head/validation/samples/0"], "1.25")
        self.assertNotIn("/base/model/nodes/0/attributes/enabled", lexemes)
        self.assertNotIn("/base/model/nodes/0/attributes/missing", lexemes)

    def test_original_report_payload_keeps_large_integer_as_json_number(self):
        value = fixture()
        value["head"]["model"]["nodes"][0]["attributes"] = {"limit": 9007199254740993}
        html = render_report(value)
        data = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S).group(1)
        lexeme_data = re.search(r'<script id="review-number-lexemes" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(data)["head"]["model"]["nodes"][0]["attributes"]["limit"], 9007199254740993)
        self.assertEqual(json.loads(lexeme_data)["/head/model/nodes/0/attributes/limit"], "9007199254740993")

    def test_invalid_candidate_definition_remains_visible(self):
        value = fixture()
        del value["head"]["model"]["nodes"][0]["definition"]
        value["head"]["validation"] = {"contract_status": "invalid"}
        html = render_report(value)
        self.assertIn('"contract_status":"invalid"', html)
        self.assertIn("Definition missing", html)

    def test_empty_models_are_supported(self):
        value = fixture()
        for side in ("base", "head"):
            value[side]["model"] = {"sources": [], "nodes": [], "relations": [], "bindings": {}}
        self.assertIn("No concepts in this revision.", render_report(value))

    def test_comparison_with_absent_bindings_renders_and_null_bindings_remain_inspectable(self):
        contract={"schema_version":"1","id":"render-bindings","version":"1",
                  "types":{"Entity":{"attributes":{}}},"relations":{},
                  "require_source_bindings":False,"checks":[]}
        absent={"schema_version":"1","contract_id":"render-bindings","contract_version":"1",
                "sources":[],"nodes":[],"relations":[]}
        empty=copy.deepcopy(absent);empty["bindings"]={}
        report=graph.compare_models(absent,empty,contract)
        self.assertTrue(report["summary"]["base_valid"])
        self.assertTrue(report["summary"]["head_valid"])
        self.assertEqual([item["kind"] for item in report["changes"]],["bindings_changed"])
        self.assertIn('"base_present":false',render_report(report))
        malformed=copy.deepcopy(absent);malformed["bindings"]=None
        invalid_report=graph.compare_models(absent,malformed,contract)
        self.assertFalse(invalid_report["summary"]["head_valid"])
        html=render_report(invalid_report)
        self.assertIn('"bindings":null',html)
        self.assertIn("BINDINGS_TYPE",html)

    def test_evidence_only_changes_have_a_distinctible_legend_and_counts(self):
        html = render_report(fixture())
        self.assertIn("Evidence updated only", html)
        self.assertIn("neutral dotted mark indicates evidence changed without a content change", html)
        self.assertIn("graph-node.evidence-updated rect", html)
        self.assertIn("graph-edge.evidence-updated .visible-edge", html)
        self.assertIn('[graphChanges.recorded,"recorded changes"]', html)
        self.assertIn('min-height:44px', html)

    def test_missing_report_fields_rejected(self):
        for key in ("schema_version", "tool", "engine_status", "review_revision", "base", "head", "changes", "findings"):
            with self.subTest(key=key):
                value = fixture()
                del value[key]
                with self.assertRaises(EngineError):
                    render_report(value)

    def test_duplicate_node_ids_rejected(self):
        value = fixture()
        value["head"]["model"]["nodes"].append(copy.deepcopy(value["head"]["model"]["nodes"][0]))
        with self.assertRaises(EngineError):
            render_report(value)

    def run_cli(self, report, output):
        return subprocess.run([sys.executable, str(Path(__file__).with_name("render_repository_review.py")),
                               "--report", str(report), "--output", str(output)], capture_output=True, text=True, check=False)

    def test_cli_writes_exact_path_without_crlf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "input.json"
            report.write_text(json.dumps(fixture()), encoding="utf-8")
            target = root / "nested" / "review.html"
            result = self.run_cli(report, target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(b"\r\n", target.read_bytes())
            self.assertTrue(target.read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, target = root / "input.json", root / "review.html"
            report.write_text(json.dumps(fixture()), encoding="utf-8")
            target.write_text("existing", encoding="utf-8")
            result = self.run_cli(report, target)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_text(), "existing")
            self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "OUTPUT_EXISTS")

    def test_cli_rejects_input_output_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "input.json"
            before = json.dumps(fixture())
            report.write_text(before, encoding="utf-8")
            result = self.run_cli(report, report)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(report.read_text(), before)
            self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "OUTPUT_ALIAS")

    def test_cli_duplicate_json_key_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            report, target = Path(directory) / "input.json", Path(directory) / "review.html"
            report.write_text('{"schema_version":"1","schema_version":"2"}', encoding="utf-8")
            result = self.run_cli(report, target)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(target.exists())
            self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "JSON_DUPLICATE_KEY")


@unittest.skipUnless(shutil.which("node"), "Node is required to exercise change-card text helpers.")
class ChangeCardTests(unittest.TestCase):
    def render_card_text(self, entry, kind="change", report=None, nodes=()):
        template=TEMPLATE.read_text(encoding="utf-8")
        start=template.index("function findingCard(" if kind=="finding" else "function membershipText(")
        end=template.index("function membershipText(" if kind=="finding" else "function filterFindings()",start+1)
        card_code=template[start:end]
        prelude='''
const make=(tag,text,cls)=>({tag,textContent:text===undefined?"":String(text),className:cls||"",dataset:{},children:[],append(...items){this.children.push(...items);},addEventListener(){},setAttribute(){}});
const display=value=>value===undefined?"Not supplied":typeof value==="string"?value:JSON.stringify(value);
const kindWords=value=>String(value||"change").replaceAll("_"," ");
const choiceControls=()=>{};
const focusEntity=()=>false;
const $=()=>({scrollIntoView(){},set textContent(value){}});
'''
        prelude += "const report=" + json.dumps(report or {}) + ";"
        prelude += "const indexes={base:{nodes:new Set(" + json.dumps(nodes) + ")},head:{nodes:new Set()}};"
        function_name="findingCard" if kind=="finding" else "changeCard"
        invocation="const card="+function_name+"("+json.dumps(entry,separators=(",",":"))+");function collect(e){return [e.textContent,...e.children.flatMap(collect)].filter(Boolean);}console.log(JSON.stringify(collect(card)));"
        result=subprocess.run([shutil.which("node"),"-e",prelude+card_code+invocation],
                              capture_output=True,text=True,encoding="utf-8",check=False)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_change_card_labels_membership_and_keeps_legacy_labels(self):
        root_fields=self.render_card_text({"id":"a","kind":"metadata_changed","field":"metadata",
                                           "before":None,"after":None,"base_present":False,"head_present":True})
        self.assertIn("Before: metadata absent.",root_fields)
        self.assertIn("After: metadata present.",root_fields)
        record_fields=self.render_card_text({"id":"b","kind":"source_changed","collection":"sources",
                                             "before":{},"after":{},"base_present_fields":["id","text"],
                                             "head_present_fields":["id","media_type","text"]})
        self.assertIn("Before record fields present: id, text.",record_fields)
        self.assertIn("After record fields present: id, media_type, text.",record_fields)
        legacy=self.render_card_text({"id":"c","kind":"metadata_changed","before":None,"after":None})
        self.assertNotIn("absent",legacy)
        self.assertNotIn("present",legacy)

    def test_finding_card_exposes_field_diagnostics_uncertainty_and_reviewer_attribution(self):
        values=self.render_card_text({"id":"proposal","code":"SEMANTIC_REVIEW_PROPOSAL","severity":"warning",
            "classification":"proposed","message":"Review definition scope.",
            "reviewer":{"kind":"model","id":"bounded-reviewer"},
            "diagnostic":{"side":"head","collection":"nodes","field_pointer":"/definition",
                          "uncertainty":"Only the selected clause was checked."},"evidence":[]},kind="finding")
        self.assertIn("Proposed by model reviewer: bounded-reviewer.",values)
        self.assertIn("Finding details and uncertainty",values)
        self.assertIn('"field_pointer":"/definition"'," ".join(values))
        self.assertIn("Only the selected clause was checked."," ".join(values))

    def test_competency_finding_shows_the_lost_answer_and_a_real_query_anchor(self):
        entry = {"id": "missing-edge", "code": "COMPETENCY_CHECK_FAILED", "classification": "new",
                 "entity_id": "/checks/parent", "diagnostic": {"path": "/checks/parent",
                 "expected": ["cat:Tool"], "actual": []}}
        report = {"base": {"contract": {"checks": [{"id": "parent", "query": {
            "op": "neighbors", "from": "field:input", "relation": "part_of"}}]}}}
        values = self.render_card_text(entry, "finding", report, nodes=("field:input",))
        self.assertIn("Declared check: parent · Baseline contract", values)
        self.assertIn("Expected", values)
        self.assertIn("cat:Tool", values)
        self.assertIn("Observed in candidate", values)
        self.assertIn("No matching IDs", values)
        self.assertIn("Inspect query concept field:input", values)
        self.assertNotIn("Inspect /checks/parent", values)
        unanchored = self.render_card_text(entry, "finding", report)
        self.assertNotIn("Inspect query concept field:input", unanchored)

    def test_proposed_competency_finding_reads_the_proposed_query(self):
        entry = {"id": "wrong-edge", "code": "COMPETENCY_CHECK_FAILED", "classification": "new",
                 "policy_scope": "proposed", "diagnostic": {"path": "/checks/parent",
                 "expected": ["cat:Tool"], "actual": ["cat:Annotations"]}}
        report = {
            "base": {"contract": {"checks": [{"id": "parent", "query": {"op": "neighbors", "from": "old"}}]}},
            "head": {"proposed_contract": {"checks": [{"id": "parent", "query": {
                "op": "neighbors", "from": "new"}}]}},
        }
        values = self.render_card_text(entry, "finding", report, nodes=("old", "new"))
        self.assertIn("Declared check: parent · Proposed contract", values)
        self.assertIn("cat:Annotations", values)
        self.assertIn("Inspect query concept new", values)
        self.assertNotIn("Inspect query concept old", values)

    def test_resolved_and_historical_competency_cards_label_the_reported_side(self):
        entry = {"id": "history", "code": "COMPETENCY_CHECK_FAILED", "diagnostic": {
            "path": "/checks/parent", "expected": ["cat:Tool"], "actual": []}}
        for classification, label in (("resolved", "Observed in baseline"),
                                      ("historical", "Observed in both")):
            with self.subTest(classification=classification):
                self.assertIn(label, self.render_card_text(dict(entry, classification=classification), "finding"))
        entry["diagnostic"]["actual"] = [False]
        self.assertNotIn("Observed in candidate", self.render_card_text(entry, "finding"))

    def test_unrecognized_competency_scope_cannot_claim_a_side_or_choose_a_query(self):
        entry = {"id": "old-export", "code": "COMPETENCY_CHECK_FAILED", "classification": "unknown",
                 "policy_scope": "external", "diagnostic": {"path": "/checks/parent",
                 "expected": ["cat:Tool"], "actual": ["cat:Annotations"]}}
        report = {"base": {"contract": {"checks": [{"id": "parent", "query": {
            "op": "neighbors", "from": "field:input"}}]}}}
        values = self.render_card_text(entry, "finding", report, nodes=("field:input",))
        self.assertIn("Declared check: parent · Contract scope not recognized", values)
        self.assertIn("Reported IDs", values)
        self.assertIn("cat:Annotations", values)
        self.assertNotIn("Observed in candidate", values)
        self.assertNotIn("Inspect query concept field:input", values)

    def test_finding_card_keeps_optional_proposal_fields_optional(self):
        values=self.render_card_text({"id":"legacy","code":"STRUCTURAL_CHECK","message":"Inspect record."},kind="finding")
        self.assertNotIn("Finding details and uncertainty",values)
        self.assertNotIn("Proposed by", " ".join(values))


@unittest.skipUnless(shutil.which("node"), "Node is required to execute the actual SVG route geometry.")
class RouteGeometryTests(unittest.TestCase):
    def geometry(self, ids, edges):
        source = TEMPLATE.read_text(encoding="utf-8")
        geometry = source.split("// geometry:start\n", 1)[1].split("// geometry:end", 1)[0]
        invocation = "console.log(JSON.stringify(graphGeometry(" + json.dumps(ids) + "," + json.dumps(edges) + ")));"
        result = subprocess.run([shutil.which("node"), "-e", geometry + invocation],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assert_no_unrelated_node_intersections(self, geometry, edges):
        for edge in edges:
            key = json.dumps([edge["id"], edge["from"], edge["to"]], separators=(",", ":"))
            route = geometry["routes"][key]
            for start, end in zip(route["points"], route["points"][1:]):
                self.assertTrue(start[0] == end[0] or start[1] == end[1], "Every route segment is orthogonal.")
                for node_id, rect in geometry["positions"].items():
                    if node_id in (edge["from"], edge["to"]):
                        continue
                    left, right = rect["x"], rect["x"] + geometry["nodeWidth"]
                    top, bottom = rect["y"], rect["y"] + geometry["nodeHeight"]
                    if start[0] == end[0]:
                        intersects = left < start[0] < right and max(min(start[1], end[1]), top) < min(max(start[1], end[1]), bottom)
                    else:
                        intersects = top < start[1] < bottom and max(min(start[0], end[0]), left) < min(max(start[0], end[0]), right)
                    self.assertFalse(intersects, f"{edge['id']} crosses unrelated node {node_id}.")
            for x, y in route["points"]:
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x, geometry["width"])
                self.assertLessEqual(y, geometry["height"])

    def test_same_row_skip_edge_does_not_cross_middle_node(self):
        edges = [{"id": "package-artifact", "from": "Package", "to": "Artifact"}]
        geometry = self.geometry(["Artifact", "Guide", "Package"], edges)
        self.assert_no_unrelated_node_intersections(geometry, edges)
        self.assertEqual(len(next(iter(geometry["routes"].values()))["points"]), 5)

    def test_dense_opposite_self_and_parallel_edges_use_distinct_clear_routes(self):
        ids = [f"n{i:02}" for i in range(12)]
        edges = [{"id": f"e{i:03}-{j:03}", "from": left, "to": right}
                 for i, left in enumerate(ids) for j, right in enumerate(ids)]
        edges += [{"id": "parallel-A", "from": "n00", "to": "n02"},
                  {"id": "parallel-B", "from": "n00", "to": "n02"}]
        geometry = self.geometry(ids, edges)
        self.assert_no_unrelated_node_intersections(geometry, edges)
        paths = [json.dumps(route["points"]) for route in geometry["routes"].values()]
        self.assertEqual(len(paths), len(set(paths)))

    def test_route_geometry_is_identical_under_input_permutations(self):
        ids = ["Artifact", "Guide", "Package", "Workflow"]
        edges = [{"id": "b", "from": "Package", "to": "Artifact"},
                 {"id": "a", "from": "Guide", "to": "Workflow"}]
        self.assertEqual(self.geometry(ids, edges), self.geometry(list(reversed(ids)), list(reversed(edges))))


@unittest.skipUnless(shutil.which("node"), "Node is required to execute graph change classification.")
class ChangeClassificationTests(unittest.TestCase):
    def classify(self, before, after, changes):
        source = TEMPLATE.read_text(encoding="utf-8")
        hydration = source.split("// numeric-hydration:start\n", 1)[1].split("// numeric-hydration:end", 1)[0]
        helpers = source.split("// change-classification:start\n", 1)[1].split("// change-classification:end", 1)[0]
        fixture_json = json.dumps({"before": before, "after": after, "changes": changes}, separators=(",", ":"))
        lexemes_json = json.dumps(number_lexemes({"before": before, "after": after, "changes": changes}), separators=(",", ":"))
        invocation = (
            "const f=JSON.parse(" + json.dumps(fixture_json) + ");"
            "hydrateExactNumbers(f,JSON.parse(" + json.dumps(lexemes_json) + "));"
            "const base=new Map(f.before.nodes.map(x=>[x.id,x])),head=new Map(f.after.nodes.map(x=>[x.id,x]));"
            "const relBase=new Map(f.before.relations.map(x=>[x.id,x])),relHead=new Map(f.after.relations.map(x=>[x.id,x]));"
            "const sourceChanges=changedSourceIds(f.before,f.after);"
            "console.log(JSON.stringify({nodeStatus:statusForRecords('nodes',base.get('n'),head.get('n')),"
            "nodeClass:classForRecords('nodes',base.get('n'),head.get('n'),sourceChanges),"
            "edgeStatus:statusForRecords('relations',relBase.get('e'),relHead.get('e')),"
            "edgeClass:classForRecords('relations',relBase.get('e'),relHead.get('e'),sourceChanges),"
            "counts:graphChangeCounts(f.before,f.after,f.changes)}));"
        )
        result = subprocess.run([shutil.which("node"), "-e", hydration + helpers + invocation], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def fixture(self):
        node = {"id": "n", "type": "Claim", "label": "Claim", "definition": "The claim", "attributes": {"time": "2020"}, "aliases": [], "source_ids": ["s1"]}
        relation = {"id": "e", "from": "n", "to": "n", "type": "has_claim", "review": {"status": "open"}, "source_ids": ["s1"]}
        return {"nodes": [node], "relations": [relation]}, node, relation

    def test_evidence_only_updates_are_not_content_changes_or_review_positives(self):
        before, node, relation = self.fixture()
        after = {"nodes": [{**node, "source_ids": ["s2"]}], "relations": [{**relation, "source_ids": ["s2"]}]}
        result = self.classify(before, after, [{"kind": "node_evidence_changed"}, {"kind": "relation_changed", "before": {"source_ids": ["s1"]}, "after": {"source_ids": ["s2"]}}])
        self.assertEqual(result["nodeStatus"], "unchanged")
        self.assertEqual(result["nodeClass"], "evidence-updated")
        self.assertEqual(result["edgeStatus"], "unchanged")
        self.assertEqual(result["edgeClass"], "evidence-updated")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 2, "recorded": 2})

    def test_mixed_node_content_and_evidence_change_stays_content_modified(self):
        before, node, relation = self.fixture()
        after = {"nodes": [{**node, "definition": "Revised claim", "source_ids": ["s2"]}], "relations": [relation]}
        result = self.classify(before, after, [{"kind": "node_definition_changed"}])
        self.assertEqual(result["nodeStatus"], "changed")
        self.assertEqual(result["nodeClass"], "changed")
        self.assertEqual(result["counts"], {"content": 1, "evidenceOnly": 0, "recorded": 1})

    def test_same_source_id_with_moved_locator_marks_citing_graph_records(self):
        before, _, _ = self.fixture()
        before["sources"] = [{"id": "s1", "locator": "terms.md#L1", "text": "The claim"}]
        after = copy.deepcopy(before)
        after["sources"][0]["locator"] = "terms.md#L2"
        result = self.classify(before, after, [{"kind": "source_changed"}])
        self.assertEqual(result["nodeStatus"], "unchanged")
        self.assertEqual(result["edgeStatus"], "unchanged")
        self.assertEqual(result["nodeClass"], "evidence-updated")
        self.assertEqual(result["edgeClass"], "evidence-updated")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 2, "recorded": 1})

    def test_cited_source_text_change_is_evidence_not_graph_content(self):
        before, _, _ = self.fixture()
        before["sources"] = [{"id": "s1", "text": "First supplied source assertion."}]
        after = copy.deepcopy(before)
        after["sources"][0]["text"] = "Second supplied source assertion."
        result = self.classify(before, after, [{"kind": "source_changed"}])
        self.assertEqual(result["nodeClass"], "evidence-updated")
        self.assertEqual(result["edgeClass"], "evidence-updated")
        self.assertEqual(result["counts"]["content"], 0)

    def test_uncited_source_change_does_not_mark_unaffected_records(self):
        before, _, _ = self.fixture()
        before["sources"] = [{"id": "s1", "text": "Cited"}, {"id": "unused", "text": "Earlier"}]
        after = copy.deepcopy(before)
        after["sources"][1]["text"] = "Later"
        result = self.classify(before, after, [{"kind": "source_changed"}])
        self.assertEqual(result["nodeClass"], "unchanged")
        self.assertEqual(result["edgeClass"], "unchanged")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 0, "recorded": 1})

    def test_source_collection_permutation_does_not_change_evidence(self):
        before, _, _ = self.fixture()
        before["sources"] = [{"id": "s1", "text": "Cited"}, {"id": "unused", "text": "Other"}]
        after = copy.deepcopy(before)
        after["sources"].reverse()
        result = self.classify(before, after, [])
        self.assertEqual(result["nodeClass"], "unchanged")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 0, "recorded": 0})

    def test_cited_source_large_integer_metadata_change_keeps_exact_evidence_delta(self):
        before, _, _ = self.fixture()
        before["sources"] = [{"id": "s1", "metadata": {"revision": 9007199254740992}}]
        after = copy.deepcopy(before)
        after["sources"][0]["metadata"]["revision"] = 9007199254740993
        result = self.classify(before, after, [{"kind": "source_changed"}])
        self.assertEqual(result["nodeClass"], "evidence-updated")
        self.assertEqual(result["edgeClass"], "evidence-updated")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 2, "recorded": 1})

    def test_invalid_scalar_reference_list_is_not_interpreted_as_source_ids(self):
        before, node, _ = self.fixture()
        node["source_ids"] = "s1"
        before["sources"] = [{"id": "s1", "locator": "terms.md#L1"}]
        after = copy.deepcopy(before)
        after["sources"][0]["locator"] = "terms.md#L2"
        result = self.classify(before, after, [{"kind": "source_changed"}])
        self.assertEqual(result["nodeClass"], "unchanged")
        self.assertEqual(result["edgeClass"], "evidence-updated")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 1, "recorded": 1})

    def test_invalid_id_members_are_not_resolved_by_the_classification_helper(self):
        # The display envelope separately rejects invalid source-record IDs.
        for invalid_id in (7, "", " "):
            with self.subTest(invalid_id=invalid_id):
                before, node, relation = self.fixture()
                node["source_ids"] = relation["source_ids"] = [invalid_id]
                before["sources"] = [{"id": invalid_id, "text": "Before"}]
                after = copy.deepcopy(before)
                after["sources"][0]["text"] = "After"
                result = self.classify(before, after, [{"kind": "source_changed"}])
                self.assertEqual(result["nodeClass"], "unchanged")
                self.assertEqual(result["edgeClass"], "unchanged")
                self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 0, "recorded": 1})

    def test_review_only_change_preserves_content_and_recorded_decision(self):
        before, node, relation = self.fixture()
        after = {"nodes": [node], "relations": [{**relation, "review": {"status": "resolved"}}]}
        result = self.classify(before, after, [{"kind": "relation_changed"}])
        self.assertEqual(result["edgeStatus"], "unchanged")
        self.assertEqual(result["edgeClass"], "unchanged")
        self.assertEqual(result["counts"], {"content": 0, "evidenceOnly": 0, "recorded": 1})

    def test_relation_endpoint_change_counts_as_content_when_review_also_changes(self):
        before, node, relation = self.fixture()
        other = {"id": "other", **{k: v for k, v in node.items() if k != "id"}}
        before = {"nodes": [node, other], "relations": [relation]}
        after = {"nodes": [node, other], "relations": [{**relation, "to": "other", "review": {"status": "resolved"}}]}
        result = self.classify(before, after, [{"kind": "relation_changed"}])
        self.assertEqual(result["edgeStatus"], "changed")
        self.assertEqual(result["edgeClass"], "changed")
        self.assertEqual(result["counts"], {"content": 1, "evidenceOnly": 0, "recorded": 1})

    def test_unsafe_integer_delta_survives_hydration_classification_and_display(self):
        before = {"nodes": [{"id": "n", "type": "Claim", "label": "Limit", "definition": "A value.",
                             "attributes": {"limit": 9007199254740992}, "source_ids": ["s"]}],
                  "relations": [], "sources": [{"id": "s", "metadata": {"count": 9007199254740993}}]}
        after = copy.deepcopy(before)
        after["nodes"][0]["attributes"]["limit"] = 9007199254740993
        value = {"before": before, "after": after}
        lexemes = number_lexemes(value)
        source = TEMPLATE.read_text(encoding="utf-8")
        hydration = source.split("// numeric-hydration:start\n", 1)[1].split("// numeric-hydration:end", 1)[0]
        helpers = source.split("// change-classification:start\n", 1)[1].split("// change-classification:end", 1)[0]
        invocation = (
            "const f=JSON.parse(" + json.dumps(json.dumps(value, separators=(",", ":"))) + ");"
            "const lex=JSON.parse(" + json.dumps(json.dumps(lexemes, separators=(",", ":"))) + ");"
            "hydrateExactNumbers(f,lex);const b=f.before.nodes[0],h=f.after.nodes[0];"
            "console.log(JSON.stringify({status:statusForRecords('nodes',b,h),"
            "display:losslessStringify(h.attributes,2),metadata:losslessStringify(f.before.sources[0].metadata),"
            "canonical:canonical(h.attributes.limit),baseCanonical:canonical(b.attributes.limit)}));"
        )
        result = subprocess.run([shutil.which("node"), "-e", hydration + helpers + invocation],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["status"], "changed")
        self.assertIn("9007199254740993", observed["display"])
        self.assertIn("9007199254740993", observed["metadata"])
        self.assertNotEqual(observed["canonical"], observed["baseCanonical"])

    def test_hydration_keeps_number_boolean_null_float_and_untrusted_keys_distinct(self):
        value = {"items": [{"safe": 42, "flag": True, "empty": None, "negative_zero": -0.0,
                            "beyond_float_range": 10 ** 400,
                            "quoted_key": {"__exactNumber__": "9007199254740993"}}]}
        lexemes = number_lexemes(value)
        source = TEMPLATE.read_text(encoding="utf-8")
        hydration = source.split("// numeric-hydration:start\n", 1)[1].split("// numeric-hydration:end", 1)[0]
        classification = source.split("// change-classification:start\n", 1)[1].split("// change-classification:end", 1)[0]
        invocation = (
            "const f=JSON.parse(" + json.dumps(json.dumps(value, separators=(",", ":"))) + ");"
            "const lex=JSON.parse(" + json.dumps(json.dumps(lexemes, separators=(",", ":"))) + ");"
            "hydrateExactNumbers(f,lex);const x=f.items[0];"
            "console.log(JSON.stringify({display:losslessStringify(x),safe:isExactNumber(x.safe),"
            "flag:typeof x.flag,empty:x.empty,negative:losslessStringify(x.negative_zero),"
            "huge:losslessStringify(x.beyond_float_range),"
            "fake:isExactNumber(x.quoted_key),numberVsBool:canonical(x.safe)!==canonical(x.flag),"
            "numberVsNull:canonical(x.safe)!==canonical(x.empty)}));"
        )
        result = subprocess.run([shutil.which("node"), "-e", hydration + classification + invocation],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = json.loads(result.stdout)
        self.assertIn('"safe":42', observed["display"])
        self.assertIn('"flag":true', observed["display"])
        self.assertIn('"empty":null', observed["display"])
        self.assertEqual(observed["negative"], "-0.0")
        self.assertEqual(observed["huge"], str(10 ** 400))
        self.assertTrue(observed["safe"])
        self.assertEqual(observed["flag"], "boolean")
        self.assertIsNone(observed["empty"])
        self.assertFalse(observed["fake"])
        self.assertTrue(observed["numberVsBool"])
        self.assertTrue(observed["numberVsNull"])

    def test_hydration_rejects_missing_or_invalid_numeric_paths(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        hydration = source.split("// numeric-hydration:start\n", 1)[1].split("// numeric-hydration:end", 1)[0]
        invocation = (
            "const failures=[];for(const [v,m] of [[{x:1},{}],[{x:1},{'/x':'01'}],[{x:1},{'/x':'2'}],[{x:1},{'/wrong':'1'}]]){"
            "try{hydrateExactNumbers(v,m)}catch(e){failures.push(e.message)}}console.log(JSON.stringify(failures));"
        )
        result = subprocess.run([shutil.which("node"), "-e", hydration + invocation],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(json.loads(result.stdout)), 4)

    def test_numeric_label_and_definition_coercion_is_safe_and_exact(self):
        before = {"nodes": [{"id": "zero-label", "type": "Claim", "label": 0,
                             "definition": 9007199254740993, "source_ids": ["s"]},
                            {"id": "zero-definition", "type": "Claim", "label": 9007199254740993,
                             "definition": 0, "source_ids": ["s"]}],
                  "relations": [], "sources": [{"id": "s", "text": "A source."}]}
        lexemes = number_lexemes(before)
        source = TEMPLATE.read_text(encoding="utf-8")
        hydration = source.split("// numeric-hydration:start\n", 1)[1].split("// numeric-hydration:end", 1)[0]
        classification = source.split("// change-classification:start\n", 1)[1].split("// change-classification:end", 1)[0]
        invocation = (
            "const model=JSON.parse(" + json.dumps(json.dumps(before, separators=(",", ":"))) + ");"
            "const lex=JSON.parse(" + json.dumps(json.dumps(lexemes, separators=(",", ":"))) + ");"
            "hydrateExactNumbers(model,lex);const a=model.nodes[0],b=model.nodes[1];"
            "console.log(JSON.stringify({zeroLabel:String(a.label||a.id),"
            "largeDefinition:String(a.definition||'Definition missing'),"
            "largeLabel:String(b.label||b.id),zeroDefinition:String(b.definition||'Definition missing'),"
            "aria:`${a.label||a.id}: ${a.definition||'Definition missing'}`,"
            "formatted:losslessStringify(a.definition),brand:isExactNumber(a.definition),"
            "canonical:canonical(a.definition)}));"
        )
        result = subprocess.run([shutil.which("node"), "-e", hydration + classification + invocation],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["zeroLabel"], "0")
        self.assertEqual(observed["largeDefinition"], "9007199254740993")
        self.assertEqual(observed["largeLabel"], "9007199254740993")
        self.assertEqual(observed["zeroDefinition"], "0")
        self.assertEqual(observed["aria"], "0: 9007199254740993")
        self.assertEqual(observed["formatted"], "9007199254740993")
        self.assertTrue(observed["brand"])
        self.assertEqual(observed["canonical"], "number:9007199254740993")

    def test_validation_details_show_exact_optional_repository_source_binding(self):
        value = {"review_revision": "a" * 64,
                 "base": {"model_sha256": "b" * 64, "graph_sha256": "c" * 64,
                          "contract_sha256": "d" * 64, "validation": {"contract_status": "valid"},
                          "model": {"metadata": {"repository_sources": {
                              "inventory_sha256": "e" * 64,
                              "origin": {"value": {"capture_count": 9007199254740993, "zero": 0}}}}}},
                 "head": {"model_sha256": "f" * 64, "graph_sha256": "0" * 64,
                          "contract_sha256": "1" * 64, "validation": {"contract_status": "valid"},
                          "proposed_validation": None, "model": {}},
                 "competency_deltas": [], "semantic_status": "not_run", "summary": {}}
        lexemes = number_lexemes(value)
        source = TEMPLATE.read_text(encoding="utf-8")
        hydration = source.split("// numeric-hydration:start\n", 1)[1].split("// numeric-hydration:end", 1)[0]
        details = source.split("// validation-details:start\n", 1)[1].split("// validation-details:end", 1)[0]
        invocation = (
            "const report=JSON.parse(" + json.dumps(json.dumps(value, separators=(",", ":"))) + ");"
            "const lex=JSON.parse(" + json.dumps(json.dumps(lexemes, separators=(",", ":"))) + ");"
            "hydrateExactNumbers(report,lex);console.log(JSON.stringify(losslessStringify(validationDetails(),2)));"
        )
        result = subprocess.run([shutil.which("node"), "-e", hydration + details + invocation],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        shown = json.loads(result.stdout)
        self.assertIn('"source_binding": {', shown)
        self.assertIn('"capture_count": 9007199254740993', shown)
        self.assertIn('"zero": 0', shown)
        self.assertNotIn('"source_binding"', shown.split('"head": {', 1)[1])


if __name__ == "__main__":
    unittest.main()
