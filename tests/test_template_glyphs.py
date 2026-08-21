"""Regression checks for twitterpainted's hardcoded visible glyph styling."""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path


ASCII_LETTER = re.compile(r"[A-Za-z]")
EXEMPT_TAGS = {"a", "code", "pre", "script", "style"}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.violations: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.stack:
            return
        match = len(self.stack) - 1 - self.stack[::-1].index(tag)
        del self.stack[match:]

    def handle_data(self, data: str) -> None:
        if EXEMPT_TAGS.intersection(self.stack):
            return
        if ASCII_LETTER.search(data):
            self.violations.append((self.getpos()[0], data.strip()))


def test_hardcoded_visible_copy_uses_unicode_glyph_map() -> None:
    template = Path(__file__).parents[1] / "templates" / "index.html"
    parser = _VisibleTextParser()
    parser.feed(template.read_text(encoding="utf-8"))

    assert not parser.violations, (
        "visible template text contains plain ASCII letters; URLs, code, and "
        f"accessibility attributes are intentionally excluded: {parser.violations}"
    )


def test_editable_text_placeholders_use_dark_unicode_copy() -> None:
    template = (Path(__file__).parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    placeholders = re.findall(r'placeholder="([^"]+)"', template)

    assert placeholders
    assert all(not ASCII_LETTER.search(placeholder) for placeholder in placeholders)
    assert "𓂀 𝗐𝗋𝐢𝗍𝐞 𝗐𝗁𝐚𝗍 𝗍𝗁𝐞 𝖿𝐞𝐞𝖽 𝖼𝐚𝗇𝗇𝐨𝗍 𝗄𝐢𝗅𝗅 🖤" in placeholders
    assert "🗝️ 𝗄𝐞𝗒, 𝗉𝐚𝗌𝗌𝗐𝐨𝗋𝖽, 𝐨𝗋 𝐨𝗅𝖽 𝗐𝐨𝐮𝗇𝖽" in placeholders


def test_readme_puts_the_petty_smoketest_on_main_stage() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    normalized = unicodedata.normalize("NFKC", readme).lower()

    assert "petty_smoketest_key_so_easy_you_could_probably_solve_it_on_the_first_try.png" in readme
    assert "the carrier kept its confession longer than pliny did" in normalized
    assert "regression status: humiliatingly stable" in normalized
    assert "stolen proudly from pliny’s agpl grimoire" in normalized
    assert "all is fair in love and war" in normalized
    assert "the code kept its promise longer" in normalized
    assert "risky love" not in normalized
    assert "proper attribution" not in normalized


def test_analyzer_ui_keeps_controls_editable_and_profile_tuning_persistent() -> None:
    app_js = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    checkbox_markup = re.findall(
        r'<input[^>]+class="analyzer-checkbox"[^>]*>',
        app_js,
    )

    assert checkbox_markup
    assert all("disabled" not in markup for markup in checkbox_markup)
    assert "analysisAdvancedOptions:v2:" in app_js
    assert "details.setAttribute('aria-hidden', String(!visible))" in app_js
    assert "button.setAttribute('aria-label', `${visible ? 'hide' : 'show'} details" in app_js


def test_encoder_picker_and_output_format_contract_are_explicit() -> None:
    root = Path(__file__).parents[1]
    template = (root / "templates" / "index.html").read_text(encoding="utf-8")
    app_js = (root / "static" / "app.js").read_text(encoding="utf-8")

    assert 'accept="image/*,.png,.PNG,.jpg,.JPG,.jpeg,.JPEG"' in template
    assert '<option value="twitterpaint" selected>' in template
    assert 'name="twitterpaintMode" value="combined" checked' in template
    assert 'name="twitterpaintMode" value="individual"' in template
    assert 'data-twitterpaint-channel="R"' in template
    assert 'data-twitterpaint-channel="G"' in template
    assert 'data-twitterpaint-channel="B"' in template
    assert 'data-twitterpaint-channel="A"' not in template
    assert 'option value="RGBA"' not in template
    assert 'id="output-format-hint"' in template
    assert "experimental jpeg q95 / 4:4:4: recompression is likely to erase pixel lsb data." in app_js
    assert "png is the intended x / twitter route." in app_js
    assert "const pngOnly = ['lsb', 'pvd', 'palette', 'chroma', 'png_chunks'];" in app_js
    assert "method === 'twitterpaint'" in app_js
    assert "fd.set('twitterpaintMode', twitterpaintMode)" in app_js
    assert "spread spectrum can write png or jpeg; choose either output." in app_js
    assert "if (isPng) pngFormatRadio.checked = true;" not in app_js
    assert "source_url" in app_js
    assert "license_url" in app_js
