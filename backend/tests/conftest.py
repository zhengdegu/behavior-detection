"""
Pytest configuration for behavior-detection backend tests.
Adds src to the import path.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path so 'src' package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
