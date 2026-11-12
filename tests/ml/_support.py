"""Temporary TEST ONLY fixtures. No generated label/reviewer represents a human judgment."""
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "jobapply_pilot_v1"
sys.path.insert(0, str(PILOT))


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.test_root = ROOT / ".test-data" / "ml_handoff"
        self.folder = self.test_root / uuid4().hex
        self.folder.mkdir(parents=True)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if not self.folder.resolve().is_relative_to(self.test_root.resolve()):
            raise ValueError("Unsafe test cleanup path")
        shutil.rmtree(self.folder)
