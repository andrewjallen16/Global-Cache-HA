"""Minimal runner so the suite can run where pytest isn't installed."""
import importlib
import pathlib
import sys
import traceback

here = pathlib.Path(__file__).parent
sys.path.insert(0, str(here))
failed = passed = 0
for path in sorted(here.glob("test_*.py")):
    mod = importlib.import_module(path.stem)
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)()
            passed += 1
            print(f"PASS {path.stem}::{name}")
        except Exception:
            failed += 1
            print(f"FAIL {path.stem}::{name}")
            traceback.print_exc()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
