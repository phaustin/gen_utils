"""
Convert one or more PDF pages to MyST markdown.

\b
Backends (both open source):
  pymupdf  -- pymupdf4llm: fast, no ML models, good for text/tables.
              Equations come out as images/plain text (no LaTeX).
  marker   -- marker-pdf: ML-based layout + OCR, converts equations to LaTeX.
              Much slower and pulls in torch, but the right choice for
              equation-heavy notes.

\b
The backends are not on conda-forge; install them with pip:
  pip install pymupdf4llm          # pymupdf backend
  pip install marker-pdf           # marker backend

\b
Usage:
  pdf2myst notes.pdf --pages 3 -o pages/notes_p3.md
  pdf2myst notes.pdf --pages 3-5,8 --backend marker -o out.md

Pages are 1-based, as printed in a PDF viewer.
"""

import re
from pathlib import Path

import click


def parse_pages(spec: str) -> list[int]:
    """'3-5,8' -> [2, 3, 4, 7]  (0-based)."""
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            pages.extend(range(lo - 1, hi))
        else:
            pages.append(int(part) - 1)
    return pages


# ---------------------------------------------------------------- backends


def _missing(backend: str, package: str) -> click.ClickException:
    return click.ClickException(
        f"the {backend} backend needs {package}: pip install {package}"
    )


def convert_pymupdf(pdf: Path, pages: list[int], img_dir: Path) -> str:
    try:
        import pymupdf4llm
    except ImportError:
        raise _missing("pymupdf", "pymupdf4llm") from None

    img_dir.mkdir(parents=True, exist_ok=True)
    return pymupdf4llm.to_markdown(
        str(pdf),
        pages=pages,
        write_images=True,
        image_path=str(img_dir),
        image_format="png",
        dpi=150,
    )


def convert_marker(pdf: Path, pages: list[int], img_dir: Path) -> str:
    try:
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError:
        raise _missing("marker", "marker-pdf") from None

    config = ConfigParser(
        {
            "output_format": "markdown",
            "page_range": ",".join(str(p) for p in pages),  # marker is 0-based
        }
    )
    converter = PdfConverter(
        config=config.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config.get_processors(),
        renderer=config.get_renderer(),
    )
    text, _, images = text_from_rendered(converter(str(pdf)))

    img_dir.mkdir(parents=True, exist_ok=True)
    for name, img in images.items():
        img.save(img_dir / name)
        # marker references images by bare filename; point them at img_dir
        text = text.replace(f"]({name})", f"]({img_dir.as_posix()}/{name})")
    return text


# ---------------------------------------------------------- MyST cleanup


def to_myst(md: str, md_path: Path, title: str | None) -> str:
    # Display math: $$ ... $$  ->  ```{math} block
    def math_block(m):
        body = m.group(1).strip()
        return f"\n```{{math}}\n{body}\n```\n"

    md = re.sub(r"\$\$(.+?)\$\$", math_block, md, flags=re.S)

    # Inline math: \( ... \)  ->  $...$   (MyST supports dollar math)
    md = re.sub(r"\\\((.+?)\\\)", r"$\1$", md)

    # Images  ![alt](path)  ->  figure directive with path relative to the .md
    fig_n = 0

    def figure(m):
        nonlocal fig_n
        fig_n += 1
        alt, src = m.group(1), m.group(2)
        try:
            src = Path(src).resolve().relative_to(md_path.parent.resolve()).as_posix()
        except ValueError:
            pass
        caption = alt if alt and not alt.lower().endswith((".png", ".jpg", ".jpeg")) else ""
        return (
            f"\n```{{figure}} {src}\n:name: fig-{md_path.stem}-{fig_n}\n:width: 80%\n\n"
            f"{caption}\n```\n"
        )

    md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", figure, md)

    # Drop page-break rules / marker page markers and collapse blank runs
    md = re.sub(r"^\s*-{3,}\s*$", "", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"

    front = "---\n"
    if title:
        front += f"title: {title}\n"
    front += "---\n\n"
    return front + md


@click.command(help=__doc__)
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--pages", required=True, help="1-based pages, e.g. '3' or '3-5,8'")
@click.option(
    "-o", "--output", type=click.Path(dir_okay=False, path_type=Path),
    help="output .md (default: <pdf>_p<pages>.md)",
)
@click.option(
    "--backend", type=click.Choice(["pymupdf", "marker"]), default="pymupdf",
    show_default=True,
)
@click.option("--title", help="title for the MyST frontmatter")
@click.option(
    "--img-dir", type=click.Path(file_okay=False, path_type=Path),
    help="where to write images (default: <output>_images/)",
)
def main(pdf, pages, output, backend, title, img_dir):
    page_list = parse_pages(pages)
    out = output or pdf.with_name(f"{pdf.stem}_p{pages.replace(',', '_')}.md")
    img_dir = img_dir or out.with_name(f"{out.stem}_images")

    convert = convert_marker if backend == "marker" else convert_pymupdf
    md = convert(pdf, page_list, img_dir)
    out.write_text(to_myst(md, out, title))

    # remove the image dir if nothing was extracted
    if img_dir.exists() and not any(img_dir.iterdir()):
        img_dir.rmdir()
    click.echo(f"wrote {out}")


if __name__ == "__main__":
    main()
