"""pytest configuration for the agent-server test suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to sys.path so imports like `from src.agent.x import y`
# resolve without needing `pip install -e .` first (bare CI environments).
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Pre-import agent submodules so unittest.mock.patch can resolve dotted paths
# like "src.agent.agent.ChatOpenAI".  mock.patch walks the path via getattr();
# the src/agent/__init__.py doesn't export its submodules unless they have been
# explicitly imported first.
import src.agent.agent   # noqa: E402, F401
import src.agent.tools   # noqa: E402, F401
