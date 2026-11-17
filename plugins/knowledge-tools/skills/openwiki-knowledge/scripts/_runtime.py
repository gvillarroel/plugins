"""Load only the library bundled with this copied skill package."""

from importlib import import_module
from pathlib import Path
import sys

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parents[1]
LIBRARY = SKILL / "assets" / "runtime"
sys.path.insert(0, str(LIBRARY))


def module(name: str):
    """Import a maintained module and reject an unrelated installed package."""
    imported = import_module("knowledge." + name)
    if not Path(imported.__file__).resolve().is_relative_to(LIBRARY.resolve()):
        raise RuntimeError("The standalone skill loaded an unrelated library")
    return imported
