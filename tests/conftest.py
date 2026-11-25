"""Load the HA-free modules without importing Home Assistant.

api.py, ir.py and discovery.py have no Home Assistant imports, so we expose the
integration directory as a bare package and skip its __init__.
"""
import importlib
import pathlib
import sys
import types

PKG_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "global_cache"

if "gcpkg" not in sys.modules:
    pkg = types.ModuleType("gcpkg")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["gcpkg"] = pkg


def load(name: str):
    return importlib.import_module(f"gcpkg.{name}")
