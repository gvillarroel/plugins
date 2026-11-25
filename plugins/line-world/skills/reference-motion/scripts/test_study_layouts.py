"""Check that transferred editorial layouts preserve the actual groups, entities and states."""
import unittest

from motion_recipe import check_props
from study_layouts import grouped_rows, parallel_rows


class EditableStudyLayouts(unittest.TestCase):
    def test_group_bands_preserve_membership_and_reveal_order(self):
        mapping = {"group":"Equipo","item":"Pieza"}
        rows = [{"Equipo":"Restauración","Pieza":"Mapa"},
                {"Equipo":"Archivo","Pieza":"Mapa"}, {"Equipo":"Archivo","Pieza":"Carta"}]
        props = grouped_rows(rows,mapping,7)
        check_props("staged-network",props,set())
        nodes = props["nodes"]
        ids = [n["id"] for n in nodes]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([n["label"] for n in nodes], ["Restauración","Mapa","Archivo","Mapa","Carta"])
        self.assertEqual(props["edges"], [])
        self.assertEqual(props["duration"], 7)
        groups = [n for n in nodes if n.get("shape") == "group"]
        for band, count in zip(groups, [1,2]):
            inside = [n for n in nodes if n is not band and abs(n["y"]-band["y"])+n["h"]/2 <= band["h"]/2]
            self.assertEqual(len(inside), count)
            for child in inside:
                self.assertLessEqual(abs(child["x"]-band["x"])+child["w"]/2, band["w"]/2)
                self.assertGreater(child["enter"][0], band.get("enter",[0,0])[1])
        reordered = grouped_rows(list(reversed(rows)),mapping,7)
        self.assertEqual(set(ids), {n["id"] for n in reordered["nodes"]})

    def test_equal_sized_member_marks_across_different_group_sizes(self):
        rows = [{"g":"Una", "i":"Conservación"}]
        rows.extend({"g":g, "i":f"Pieza {i}"} for g in ("Dos","Tres","Cuatro") for i in range(4))
        props = grouped_rows(rows,{"group":"g","item":"i"},8)
        check_props("staged-network",props,set())
        members = [n for n in props["nodes"] if n.get("shape")!="group"]
        self.assertEqual(len(members),13)
        self.assertEqual(len({(n["w"],n["h"]) for n in members}),1)
        self.assertEqual(len({(n["x"],n["y"]) for n in members}),len(members))

    def test_parallel_conditions_match_entities_and_keep_equal_states(self):
        mapping = {"item":"Material","before":"Al ingreso","after":"Al cierre"}
        rows = [{"Material":"Grabado","Al ingreso":"Pendiente","Al cierre":"Catalogado"},
                {"Material":"Pintura","Al ingreso":"En revisión","Al cierre":"En revisión"}]
        props = parallel_rows(rows,mapping,6)
        check_props("staged-network",props,set())
        nodes = props["nodes"]
        self.assertEqual([n["label"] for n in nodes if n.get("shape")=="group"],["Al ingreso","Al cierre"])
        for index, row in enumerate(rows):
            entity, left, right = nodes[2+index*3:5+index*3]
            self.assertEqual([n["label"] for n in (entity,left,right)],list(row.values()))
            self.assertEqual(len({n["y"] for n in (entity,left,right)}),1)
            self.assertLess(entity["x"]+entity["w"]/2,left["x"]-left["w"]/2)
            self.assertLess(left["x"]+left["w"]/2,right["x"]-right["w"]/2)
            self.assertLess(left.get("enter",[0,0])[1],right["enter"][0])
            for n in (entity,left):
                self.assertAlmostEqual(n["moveFrom"][0]-n["x"], nodes[0]["moveFrom"][0]-nodes[0]["x"])
                self.assertEqual(n["moveFrom"][1], n["y"])
                self.assertEqual(n["moveFrom"][2:], nodes[0]["moveFrom"][2:])
        self.assertEqual(props["edges"], [])
        reordered = parallel_rows(list(reversed(rows)),mapping,6)
        self.assertEqual({n["id"] for n in nodes},{n["id"] for n in reordered["nodes"]})

    def test_exportable_at_maximum_row_count_and_with_wrapped_text(self):
        rows = [{"i":f"Documento {i}", "a":"Disponible", "d":"Pendiente de catalogación"} for i in range(6)]
        props = parallel_rows(rows,{"item":"i","before":"a","after":"d"},7)
        check_props("staged-network",props,set())
        states = [n for n in props["nodes"] if n["id"].startswith("after-")]
        self.assertEqual(len(states),6)
        self.assertTrue(all(n["label"].split()==["Pendiente","de","catalogación"] for n in states))
        for upper,lower in zip(states,states[1:]):
            self.assertLess(upper["y"]+upper["h"]/2,lower["y"]-lower["h"]/2)

    def test_invalid_groups_and_conditions_are_not_silently_rewritten(self):
        group_map={"group":"g","item":"i"}
        state_map={"item":"i","before":"a","after":"d"}
        for rows in ([], [{"g":"Sala","i":""}], [{"g":"Sala","i":"Mapa"}]*2,
                     [{"g":str(i),"i":"Mapa"} for i in range(5)],
                     [{"g":"Sala","i":str(i)} for i in range(5)],
                     [{"g":"Sala","i":"X"*100}]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                grouped_rows(rows,group_map,6)
        for rows in ([{"i":"Pieza","a":"1","d":"2"}], [{"i":"Pieza","a":"Abierto"}],
                     [{"i":"Pieza","a":"Abierto","d":"Cerrado"}]*2,
                     [{"i":str(i),"a":"Abierto","d":"Cerrado"} for i in range(7)]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                parallel_rows(rows,state_map,6)
        for duration in (0,float("nan"),True):
            with self.subTest(duration=duration),self.assertRaises(ValueError):
                grouped_rows([{"g":"Sala","i":"Mapa"}],group_map,duration)


if __name__ == "__main__":
    unittest.main()
