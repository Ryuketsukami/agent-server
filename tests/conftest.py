"""pytest configuration — adds src/ to sys.path so imports resolve without
needing `pip install -e .` first (e.g. in a bare CI environment)."""

import sys
from pathlib import Path

# Project root is one level up from tests/
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
