# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "rea-video @ git+https://github.com/JuneYaooo/rea-video.git@a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8",
# ]
# ///
"""Run the upstream rea-video CLI at the revision used by Line World."""

import sys

from rea_video.cli import main


if __name__ == "__main__":
    # The upstream CLI includes Chinese diagnostics even for English reports.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
