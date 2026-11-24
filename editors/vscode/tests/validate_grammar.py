#!/usr/bin/env python3
"""Automated validator for FunnelScript VS Code extension manifest, grammar, and icon assets."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def find_repo_root() -> Path:
    """Resolve repository root directory from file location."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


def collect_regex_patterns(obj: object) -> list[str]:
    """Recursively extract all regex patterns ('match', 'begin', 'end') from grammar JSON."""
    patterns: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("match", "begin", "end") and isinstance(v, str):
                patterns.append(v)
            else:
                patterns.extend(collect_regex_patterns(v))
    elif isinstance(obj, list):
        for item in obj:
            patterns.extend(collect_regex_patterns(item))
    return patterns


def validate_extension() -> None:
    repo_root = find_repo_root()
    vscode_dir = repo_root / "editors" / "vscode"

    # 1. Parse JSON files
    json_files = [
        vscode_dir / "package.json",
        vscode_dir / "language-configuration.json",
        vscode_dir / "syntaxes" / "funnelscript.tmLanguage.json",
        vscode_dir / "icons" / "funnelscript-icon-theme.json",
    ]

    parsed_json: dict[Path, dict] = {}
    for json_file in json_files:
        assert json_file.exists(), f"Missing required file: {json_file}"
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                parsed_json[json_file] = json.load(f)
        except Exception as e:
            raise AssertionError(f"Invalid JSON in {json_file}: {e}") from e

    pkg = parsed_json[vscode_dir / "package.json"]
    grammar = parsed_json[vscode_dir / "syntaxes" / "funnelscript.tmLanguage.json"]
    icon_theme = parsed_json[vscode_dir / "icons" / "funnelscript-icon-theme.json"]

    # 2. Compile all regex patterns in tmLanguage.json
    patterns = collect_regex_patterns(grammar)
    assert len(patterns) > 0, "No regex patterns found in tmLanguage.json"
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as e:
            raise AssertionError(f"Invalid regex pattern '{pattern}': {e}") from e

    # 3. Verify icon paths exist and match brand assets
    lang_contrib = pkg.get("contributes", {}).get("languages", [{}])[0]
    light_icon = lang_contrib.get("icon", {}).get("light")
    dark_icon = lang_contrib.get("icon", {}).get("dark")

    assert light_icon, "Missing contributes.languages[0].icon.light"
    assert dark_icon, "Missing contributes.languages[0].icon.dark"

    light_icon_path = (vscode_dir / light_icon).resolve()
    dark_icon_path = (vscode_dir / dark_icon).resolve()

    assert light_icon_path.exists(), f"Light icon does not exist: {light_icon_path}"
    assert dark_icon_path.exists(), f"Dark icon does not exist: {dark_icon_path}"

    # Verify icon theme mappings
    icon_defs = icon_theme.get("iconDefinitions", {})
    assert "_fnls" in icon_defs, "Missing '_fnls' in iconDefinitions"
    assert (vscode_dir / "icons" / icon_defs["_fnls"]["iconPath"]).resolve().exists()

    # Compare with source assets/brand
    brand_dir = repo_root / "assets" / "brand"
    if brand_dir.exists():
        expected_color = (brand_dir / "funnelscript-icon-color.svg").read_bytes()
        actual_color = (vscode_dir / "icons" / "funnelscript-color.svg").read_bytes()
        assert actual_color == expected_color, "funnelscript-color.svg does not match assets/brand"

    # 4. Token coverage check against tokens.py
    tokens_file = repo_root / "src" / "funnelscript" / "tokens.py"
    if tokens_file.exists():
        # Import KEYWORDS from tokens.py
        sys.path.insert(0, str(repo_root / "src"))
        from funnelscript.tokens import KEYWORDS

        all_grammar_patterns = " ".join(patterns)
        for keyword in KEYWORDS:
            # Check that keyword exists within word boundaries in one of the grammar patterns
            pattern_match = re.search(r"\\b.*?" + re.escape(keyword) + r".*?\\b", all_grammar_patterns)
            assert pattern_match is not None, f"Lexer keyword '{keyword}' is not covered in tmLanguage.json"

    # 5. Tokenize / test against examples/*.fnls
    examples_dir = repo_root / "examples"
    if examples_dir.exists():
        fnls_files = list(examples_dir.glob("*.fnls"))
        assert len(fnls_files) > 0, "No .fnls files found in examples/"

        # Compile master keywords regex from grammar
        keywords_pattern = None
        for p in patterns:
            if "world" in p and "entity" in p:
                keywords_pattern = re.compile(p)
                break
        assert keywords_pattern is not None, "Could not find declaration keywords pattern in grammar"

        for fnls in fnls_files:
            content = fnls.read_text(encoding="utf-8")
            # Verify file contains recognizable tokens
            matches = list(keywords_pattern.finditer(content))
            # Most world files should match at least 'world' or 'entity' or 'agent'
            if "world" in content:
                assert len(matches) > 0, f"File {fnls.name} contains 'world' but failed keyword pattern matching"

    print("All FunnelScript editor extension validations passed successfully!")


if __name__ == "__main__":
    validate_extension()
