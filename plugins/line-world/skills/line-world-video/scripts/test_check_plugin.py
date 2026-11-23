"""A stalled isolated test is retried once and cannot block the rest of the catalogue."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import check_plugin


class RegressionRunner(unittest.TestCase):
    def test_transient_and_permanent_stalls(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(check_plugin,"SKILLS",Path(directory)):
            root = Path(directory)
            script, marker = root/"test_worker.py", root/"attempted"
            env = dict(os.environ, MARKER=str(marker))
            script.write_text(
                "import os,time\nfrom pathlib import Path\nmarker=Path(os.environ['MARKER'])\n"
                "if not marker.exists():\n marker.touch()\n time.sleep(30)\nprint('Ran 3 tests in 0.1s')\n",
                encoding="utf-8")
            result = check_plugin.run(script,env,.6)
            self.assertTrue(result["ok"],result)
            self.assertEqual((result["tests"],result["retriedAfterTimeoutSeconds"]),(3,.6))
            script.write_text("import time\ntime.sleep(30)\n",encoding="utf-8")
            started = time.monotonic()
            failed = check_plugin.run(script,env,.4)
            self.assertFalse(failed["ok"])
            self.assertIn("twice",failed["error"])
            self.assertLess(time.monotonic()-started,12)

    def test_assertion_failure_is_reported_without_retry(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(check_plugin,"SKILLS",Path(directory)):
            script = Path(directory)/"test_bad.py"
            script.write_text("raise AssertionError('incorrect chart')",encoding="utf-8")
            result = check_plugin.run(script,dict(os.environ),10)
            self.assertFalse(result["ok"])
            self.assertNotIn("retriedAfterTimeoutSeconds",result)
            self.assertIn("incorrect chart",result["diagnostic"])


if __name__ == "__main__":
    unittest.main()
