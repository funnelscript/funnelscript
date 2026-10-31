"""Canonical developer docs must point to real repository files."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "README.md", ROOT / "CONTRIBUTING.md",
        *(sorted((ROOT / "docs").glob("*.md"))),
        *(sorted((ROOT / "failure-lessons").glob("*.md"))))
LINKS = re.compile(r"\]\(([^)]+)\)")


def test_relative_documentation_links_resolve():
    examined = 0
    for document in DOCS:
        for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            for raw_target in LINKS.findall(line):
                target = raw_target.split(" ", 1)[0]
                parsed = urlsplit(target)
                assert parsed.scheme != "file", f"{document}:{line_number}: local machine URL"
                if parsed.scheme or target.startswith("#"):
                    continue
                examined += 1
                destination = (document.parent / unquote(parsed.path)).resolve()
                assert destination.is_relative_to(ROOT), f"{document}:{line_number}: path escapes repo"
                assert destination.is_file(), f"{document}:{line_number}: missing {target}"
    assert examined >= 20, "Link extraction did not inspect expected local navigation"
