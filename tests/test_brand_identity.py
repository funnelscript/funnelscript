"""Portable logo assets and Studio integration for the FunnelScript identity."""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
SVG = "{http://www.w3.org/2000/svg}"


def test_brand_variants_are_valid_self_contained_svg():
    names = (
        "funnelscript-icon-color.svg", "funnelscript-icon-light.svg",
        "funnelscript-icon-dark.svg", "funnelscript-icon-mono.svg",
        "funnelscript-favicon.svg", "funnelscript-wordmark-light.svg",
        "funnelscript-wordmark-dark.svg", "funnelscript-wordmark-mono.svg",
    )
    for name in names:
        data = (BRAND / name).read_text()
        root = ET.fromstring(data)
        assert root.tag == SVG + "svg"
        assert root.attrib.get("viewBox")
        assert not any(tag in data.lower() for tag in ("<script", "<foreignobject", "javascript:", "data:"))
        assert not re.search(r"(?:href|xlink:href)\s*=", data)
        assert any(element.tag == SVG + "path" for element in root.iter())


def test_vector_wordmark_has_no_font_file_dependency():
    for theme in ("light", "dark", "mono"):
        root = ET.parse(BRAND / f"funnelscript-wordmark-{theme}.svg").getroot()
        assert not any(item.tag == SVG + "text" for item in root.iter())
        assert sum(item.tag == SVG + "path" for item in root.iter()) >= 12


def test_favicon_exactly_matches_public_web_asset():
    assert (BRAND / "funnelscript-favicon.svg").read_bytes() == (
        ROOT / "apps/web/public/funnelscript-icon.svg"
    ).read_bytes()
    assert 'href="/funnelscript-icon.svg"' in (ROOT / "apps/web/index.html").read_text()


def test_accessible_button_violet_contrast():
    def luminance(code):
        channels = [int(code[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055)**2.4 for c in channels]
        return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))

    button = "#6D54F5"
    assert (luminance("#FFFFFF") + 0.05) / (luminance(button) + 0.05) >= 4.5
    assert button in (ROOT / "apps/web/tailwind.config.js").read_text()
    assert button in (ROOT / "docs/brand/tokens.css").read_text()
