import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import numpy as np
import score_picture as score


class PictureScoreTests(unittest.TestCase):
    def setUp(self):
        self.phrase = {"text":"Se cierra el contacto.","absolute_start_sample":6000,"absolute_end_sample":9500}
        self.cue = {"id":"contacto","sound":"switch/light","seed":31,"use":"play",
                    "frame":3,"anchor":"peak","peak_dbfs":-22,"protect_sentence":1,"term":"contacto",
                    "reason":"Cierra la pala.","silence":"La pala se ve."}

    def place(self, **changes):
        cue={**self.cue,**changes}
        with patch.object(score.engine,"read_audio",return_value=np.array([0,.2,1.,.2,0])), \
             patch.object(score.engine,"checksum",return_value="dummy"):
            return score.place(cue,Path("take.wav"),[self.phrase],Fraction(30),20000,"edit")[0]

    def test_rational_frame_clock_and_peak_placement(self):
        self.assertEqual(score.frame_sample(30000,Fraction(30000,1001)),48000*1001)
        row=self.place()
        self.assertEqual((row["startSample"],row["anchoredSample"]),(4798,4800))
        self.assertEqual(row["candidateOverlapAboveGateSamples"],0)

    def test_overlap_requires_silence_or_another_placement(self):
        with self.assertRaisesRegex(ValueError,"overlaps"):
            self.place(frame=4)
        row=self.place(frame=4,use="silence")
        self.assertFalse(row["enabled"])
        self.assertGreater(row["candidateOverlapAboveGateSamples"],0)

    def test_requires_actual_term_and_skips_excessive_offset(self):
        with self.assertRaisesRegex(ValueError,"term"):
            self.place(term="bobina")
        with self.assertRaisesRegex(ValueError,"half a frame"):
            self.place(offset_ms=-17)
        with self.assertRaisesRegex(ValueError,"one-based"):
            self.place(protect_sentence=0)


if __name__=="__main__":
    unittest.main()
