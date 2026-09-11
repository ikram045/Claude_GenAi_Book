"""Make the exercise modules importable and enable async tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
