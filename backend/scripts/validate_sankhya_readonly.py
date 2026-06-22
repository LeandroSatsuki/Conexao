from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _run() -> int:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    module = importlib.import_module("app.validation.sankhya_readonly")
    return module.main()


if __name__ == "__main__":
    raise SystemExit(_run())
