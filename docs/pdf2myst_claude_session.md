# Claude session: PDF page → MyST markdown

Date: 2026-11-24

## Request

> I'm looking for a script to convert a pdf page to myst markdown using open source libraries

## Result

Claude wrote `scripts/pdf2myst.py`. It uses one of two open-source libraries, picked with `--backend`:

| Backend | Library | Notes |
|---|---|---|
| `pymupdf` (default) | `pymupdf4llm` | Fast and needs no ML models. Handles text, headings, tables and images well. Equations come out as images or plain Unicode text, not LaTeX. |
| `marker` | `marker-pdf` | Runs ML models to work out the page layout and turns equations into LaTeX. Much slower and installs PyTorch, but the better choice for equation-heavy pages. |

After conversion, the script turns the output into MyST:

- adds a `title:` frontmatter block
- puts `$$…$$` display math into ```` ```{math} ```` blocks, and changes `\( … \)` inline math to `$…$`
- puts images into ```` ```{figure} ```` directives with a `:name:` you can reference (`fig-<stem>-<n>`) and a path relative to the `.md` file
- saves images to `<output>_images/` and deletes that folder if no images were extracted
- removes horizontal rules (`---`) and runs of blank lines

### Usage

```bash
pip install click pymupdf4llm  # and/or: pip install marker-pdf
python scripts/pdf2myst.py notes.pdf --pages 3 -o pages/notes_p3.md --title "Notes"
python scripts/pdf2myst.py notes.pdf --pages 3-5,8 --backend marker -o out.md
```

Page numbers are 1-based, as your PDF viewer shows them. Other options: `--img-dir` (where images go) and `--title`.

### Test run

Claude ran the `pymupdf` backend on page 1 of `latex/internal_energy_notes.pdf` with:

```bash
uv run --no-project --with pymupdf4llm python scripts/pdf2myst.py \
    latex/internal_energy_notes.pdf --pages 1 --title Test -o test.md
```

(`--no-project` is needed because `pyproject.toml` has no `project.version`, so uv refuses to parse it.)

It worked, but each equation came out as a figure image followed by an HTML comment holding Unicode text, for example:

````
```{figure} test_images/internal_energy_notes.pdf-0001-05.png
:name: fig-test-1
:width: 80%

```

<!-- Start of picture text -->
𝑑𝑢= đ 𝑞−đ 𝑤 (1)<br><!-- End of picture text -->
````

To get real LaTeX math, use `--backend marker`. That backend has not been tested here because it needs PyTorch and model downloads.

## Notes

- Neither library has been added to the pixi environment. To add one: `pixi add --pypi pymupdf4llm`.
- For PDFs built from your own Typst source (like the first-law notes), converting the source directly gives much cleaner math than any PDF extraction. For example, `pandoc -f typst -t markdown notes.typ` works with the pandoc that's already in the environment.
