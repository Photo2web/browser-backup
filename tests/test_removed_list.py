import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from core import removed_list as rl


@dataclass(frozen=True)
class FakeProgram:
    name: str
    publisher: str | None = "ACME"
    version: str | None = "1.0"
    scope: str = "user"


class RemovedListTests(unittest.TestCase):
    def test_load_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(rl.load_removed(Path(tmp) / "nope.json"), [])

    def test_save_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entfernt.json"
            rl.save_removed([FakeProgram("Firefox"), FakeProgram("VLC")], path=path)
            loaded = rl.load_removed(path)
            names = sorted(e["name"] for e in loaded)
            self.assertEqual(names, ["Firefox", "VLC"])
            self.assertTrue(all("removed_at" in e for e in loaded))

    def test_merge_dedupes_by_name_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entfernt.json"
            rl.save_removed([FakeProgram("Firefox", version="1.0")], path=path)
            rl.save_removed([FakeProgram("Firefox", version="1.0"),
                             FakeProgram("Chrome")], path=path)
            loaded = rl.load_removed(path)
            names = sorted(e["name"] for e in loaded)
            self.assertEqual(names, ["Chrome", "Firefox"])   # Firefox nur einmal

    def test_different_version_kept_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entfernt.json"
            rl.save_removed([FakeProgram("App", version="1.0")], path=path)
            rl.save_removed([FakeProgram("App", version="2.0")], path=path)
            self.assertEqual(len(rl.load_removed(path)), 2)

    def test_accepts_plain_dicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entfernt.json"
            rl.save_removed([{"name": "Manual", "version": "3", "scope": "user"}], path=path)
            self.assertEqual(rl.load_removed(path)[0]["name"], "Manual")

    def test_corrupt_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kaputt.json"
            path.write_text("das ist kein JSON", encoding="utf-8")
            self.assertEqual(rl.load_removed(path), [])


if __name__ == "__main__":
    unittest.main()
