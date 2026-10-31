"""Guard discoverability and resource integrity of the bundled developer skills."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "agents" / "skills"
LINKS = re.compile(r"\]\(([^)]+)\)")
NAME = re.compile(r"^name:\s*([^\s]+)\s*$", re.MULTILINE)
VALID_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillBundleContractTest(unittest.TestCase):
    def test_skill_directory_names_and_index_match_frontmatter(self):
        entries = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertEqual(len(entries), 22)
        index = (ROOT / "agents" / "README.md").read_text(encoding="utf-8")
        indexed = set(re.findall(r"^\|\s*\x60([^\x60]+)\x60\s*\|", index, re.MULTILINE))
        self.assertEqual(indexed, {entry.parent.name for entry in entries})
        for entry in entries:
            with self.subTest(skill=entry.parent.name):
                source = entry.read_text(encoding="utf-8")
                self.assertTrue(source.startswith("---\n"), "Missing YAML frontmatter")
                metadata = source.split("---", 2)[1]
                name = NAME.search(metadata)
                self.assertIsNotNone(name, "Missing name metadata")
                self.assertRegex(name.group(1), VALID_NAME)
                self.assertEqual(name.group(1), entry.parent.name)

    def test_skill_entrypoint_file_links_exist(self):
        examined = 0
        for entry in sorted(SKILLS.glob("*/SKILL.md")):
            for line_number, line in enumerate(entry.read_text(encoding="utf-8").splitlines(), 1):
                for raw in LINKS.findall(line):
                    target = raw.split(" ", 1)[0]
                    parsed = urlsplit(target)
                    if parsed.scheme or target.startswith("#") or parsed.path == "url":
                        continue
                    examined += 1
                    destination = (entry.parent / unquote(parsed.path)).resolve()
                    with self.subTest(skill=entry.parent.name, line=line_number, target=target):
                        self.assertTrue(destination.is_relative_to(SKILLS), "Escaped skill bundle")
                        self.assertTrue(destination.is_file(), f"Missing file: {destination}")
        self.assertGreaterEqual(examined, 20, "No meaningful skill links examined")

    def test_academic_paper_registry_guide_link_resolves(self):
        registry = SKILLS / "academic-paper" / "references" / "output_language_pair.md"
        self.assertTrue(registry.is_file())
        self.assertIn("](abstract_writing_guide.md)", registry.read_text(encoding="utf-8"))
        self.assertTrue((registry.parent / "abstract_writing_guide.md").is_file())

    def test_extracted_skill_sources_have_no_duplicate_zip_bundles(self):
        self.assertEqual(sorted(SKILLS.rglob("*.zip")), [])


if __name__ == "__main__":
    unittest.main()
