"""Implementation compatibility layer.

The validated research code predates package-relative imports.  Adding this
directory to ``sys.path`` preserves that frozen implementation while the
tutor-facing API remains small and explicit.
"""
from pathlib import Path
import sys


INTERNAL_DIR = str(Path(__file__).resolve().parent)
if INTERNAL_DIR not in sys.path:
    sys.path.insert(0, INTERNAL_DIR)
