from pathlib import Path

import pytest
from click.testing import CliRunner

from gen_utils.utils import pdf2myst


def test_parse_pages():
    assert pdf2myst.parse_pages("3") == [2]
    assert pdf2myst.parse_pages("3-5, 8") == [2, 3, 4, 7]


def test_to_myst(tmp_path):
    md_path = tmp_path / "out.md"
    img = tmp_path / "out_images" / "a.png"
    md = f"Text $$x = 1$$ and \\(y\\)\n\n---\n\n![Caption]({img})\n"
    out = pdf2myst.to_myst(md, md_path, "My title")
    assert out.startswith("---\ntitle: My title\n---\n")
    assert "```{math}\nx = 1\n```" in out
    assert "and $y$" in out
    assert "```{figure} out_images/a.png\n:name: fig-out-1\n" in out
    assert "Caption\n```" in out


def test_missing_backend(tmp_path, monkeypatch):
    # a fake PDF is enough: the import fails before the file is read
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setitem(__import__("sys").modules, "pymupdf4llm", None)
    result = CliRunner().invoke(pdf2myst.main, [str(pdf), "--pages", "1"])
    assert result.exit_code == 1
    assert "pip install pymupdf4llm" in result.output


def _make_pdf(path: Path) -> None:
    """Two-page PDF: page 2 has a heading, a paragraph and an image."""
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Page one text", fontsize=12)
    page = doc.new_page()
    page.insert_text((72, 72), "Conservation of energy", fontsize=24)
    page.insert_text((72, 110), "The first law relates heating and working.", fontsize=11)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 120), False)
    pix.clear_with(180)
    page.insert_image(pymupdf.Rect(72, 150, 372, 330), pixmap=pix)
    doc.save(path)


def test_convert_pymupdf(tmp_path):
    pytest.importorskip("pymupdf4llm", reason="run with: pixi run -e pdf pytest")
    pdf = tmp_path / "notes.pdf"
    _make_pdf(pdf)
    out = tmp_path / "notes_p2.md"

    result = CliRunner().invoke(
        pdf2myst.main, [str(pdf), "--pages", "2", "-o", str(out), "--title", "Week 2"]
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()

    assert text.startswith("---\ntitle: Week 2\n---\n")
    assert "Conservation of energy" in text
    assert "heating and working" in text
    assert "Page one text" not in text  # only the requested page

    # the image is written next to the output and referenced relatively
    images = list((tmp_path / "notes_p2_images").glob("*.png"))
    assert len(images) == 1
    assert f"```{{figure}} notes_p2_images/{images[0].name}\n:name: fig-notes_p2-1" in text
