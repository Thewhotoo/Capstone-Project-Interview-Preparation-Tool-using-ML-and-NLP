"""Stage 1 -- layout-aware slide extraction.

Reads every page of a slide PDF (one slide per page) with PyMuPDF and turns
it into a structured record, using font size, position and the location of
images/vector drawings instead of the flat text stream:

  * running header / footer -- text repeated in the top/bottom band on many
    pages spread across the document (detected per PDF, never hardcoded)
  * title       -- the largest-font line near the top of the slide
  * diagram labels -- short text sitting inside an image or a cluster of
    vector drawings (the scattered "P1 R1 0 5 111" noise), kept aside
  * tables      -- rebuilt row by row with page.find_tables()
  * code        -- monospace fonts or code-like syntax, indentation rebuilt
                   from x positions
  * body        -- remaining lines rebuilt into bullet items (wrapped lines
                   rejoined, bullet glyphs normalised, nesting kept)

All position rules use fractions of the page size, because one PDF can mix
decks with different page sizes.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

# ── tunables (fractions of page height/width unless noted) ───────────────────
HEADER_BAND = 0.14          # running header lives above this line
FOOTER_BAND = 0.86          # running footer / slide number lives below this
TITLE_BAND = 0.32           # a slide title starts above this line
REPEAT_MIN_FRACTION = 0.03  # header text must appear on >= 3% of pages ...
REPEAT_MIN_SPAN = 0.25      # ... spread over >= 25% of the document
DECOR_IMAGE_MAX_AREA = 0.015  # images smaller than this are logos/icons
DIAGRAM_MIN_PATHS = 3       # a drawing cluster needs this many paths to be a diagram
LABEL_MAX_WORDS = 4
LABEL_MAX_CHARS = 32

BULLET_CHARS = "•▪❖●➢➔○◦∙■□▶►✓✔✗·‣⁃➤➣➥→⇒♦◆◇►▸-–—*"
_BULLET_RE = re.compile(r"^\s*[" + re.escape(BULLET_CHARS) + r"]+\s*")
_NUMBERED_RE = re.compile(r"^\s*(\(?\d{1,2}[.)]|\(?[a-hA-H][.)]|\(?(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\))\s+")
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)
_SLIDE_NUMBER_RE = re.compile(r"^(slide\s*|page\s*)?\d{1,4}(\s*(/|of)\s*\d{1,4})?$", re.I)
_DATE_RE = re.compile(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}$")
_CODE_RE = re.compile(
    r"(;\s*$|^\s*[{}]\s*$|\bfor\s*\(|\bwhile\s*\(|\bif\s*\(|\bswitch\s*\(|\breturn\b.*;|"
    r"#include|\bprintf\s*\(|\bscanf\s*\(|\bmalloc\s*\(|\bpublic\s+(static\s+)?\w+|"
    r"\bprivate\s+\w+\s+\w+|\bvoid\s+\w+\s*\(|\bint\s+\w+\s*[=;(\[]|\bstruct\s+\w+|"
    r"\w+\s*->\s*\w+|System\.out\.|\bdef\s+\w+\(|^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE)\s)", re.I
)
_MONO_FONT_RE = re.compile(r"courier|consolas|mono|menlo|lucida\s*console|sourcecode", re.I)


@dataclass
class Row:
    """One visual line of text (spans on the same baseline merged)."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool
    mono: bool

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class SlideRecord:
    subject: str
    pdf: str
    page: int                      # 1-based PDF page index (what citations use)
    width: float
    height: float
    title: str = ""
    items: list[dict] = field(default_factory=list)   # {"text", "level", "kind"}
    code: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)   # removed diagram labels
    urls: list[str] = field(default_factory=list)
    title_size: float = 0.0
    body_size: float = 0.0
    content_image_frac: float = 0.0
    diagram_frac: float = 0.0
    n_rows: int = 0
    max_font: float = 0.0
    raw_chars: int = 0
    formula_suspect: bool = False
    largest_text: str = ""         # text set in the slide's biggest font (deck title slides)
    running_header: str = ""       # deck-specific running header (kept as topic context)
    ocr: bool = False              # text came from OCR of a picture-only slide
    vision_text: str = ""          # Stage 3: what the vision model read from figures/tables
    removed_notes: list[str] = field(default_factory=list)   # personal PDF annotations stripped from the text
    # filled by later stages
    type: str = ""
    needs_vision: list[str] = field(default_factory=list)
    dropped: str = ""              # reason, if removed from content
    deck: int = 0
    deck_title: str = ""

    def body_text(self) -> str:
        lines = []
        for it in self.items:
            prefix = "  " * it["level"] + ("- " if it["kind"] == "bullet" else "")
            lines.append(prefix + it["text"])
        for table in self.tables:
            lines.extend(_table_markdown(table))
        if self.code:
            lines.append(self.code)
        if self.vision_text:
            lines.append(f"[Figure] {self.vision_text}")
        return "\n".join(lines)

    def full_text(self) -> str:
        body = self.body_text()
        return f"{self.title}\n{body}".strip() if self.title else body

    def to_dict(self) -> dict:
        return asdict(self)


def _table_markdown(table: list[list[str]]) -> list[str]:
    out = []
    for i, row in enumerate(table):
        out.append("| " + " | ".join(c or "" for c in row) + " |")
        if i == 0:
            out.append("|" + "---|" * len(row))
    return out


def normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip(" :-–|")


# ── low-level page reading ───────────────────────────────────────────────────

def _is_mono(span: dict) -> bool:
    return bool(span["flags"] & 8) or bool(_MONO_FONT_RE.search(span["font"]))


def _page_rows(page: pymupdf.Page) -> list[Row]:
    """Text lines of the page, with spans sharing a baseline merged into one row."""
    lines: list[Row] = []
    data = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)
    for block in data["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in line["spans"])).strip()
            main = max(spans, key=lambda s: len(s["text"].strip()))
            x0, y0, x1, y1 = line["bbox"]
            lines.append(Row(
                text=text, x0=x0, y0=y0, x1=x1, y1=y1,
                size=round(main["size"], 1),
                bold=bool(main["flags"] & 16) or "bold" in main["font"].lower(),
                mono=all(_is_mono(s) for s in spans),
            ))
    # merge fragments on the same visual line (bullet glyph + text, split spans)
    lines.sort(key=lambda r: (r.yc, r.x0))
    rows: list[Row] = []
    for ln in lines:
        prev = rows[-1] if rows else None
        if (prev is not None and not ln.mono and not prev.mono
                and abs(ln.yc - prev.yc) < 0.45 * min(ln.size, prev.size)
                and ln.x0 >= prev.x1 - 2):
            gap = ln.x0 - prev.x1
            # a wide gap between same-baseline fragments is a table/diagram, not one line
            if gap < 6 * max(ln.size, prev.size):
                prev.text = f"{prev.text} {ln.text}"
                prev.x1 = max(prev.x1, ln.x1)
                prev.y0, prev.y1 = min(prev.y0, ln.y0), max(prev.y1, ln.y1)
                prev.size = max(prev.size, ln.size) if len(ln.text) > len(prev.text) / 2 else prev.size
                prev.bold = prev.bold or (ln.bold and len(ln.text) > 3)
                continue
        rows.append(Row(**asdict(ln)))
    rows.sort(key=lambda r: (round(r.y0 / max(r.size * 0.6, 1)), r.x0))
    return rows


def _rect_area(r) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def _inside(row: Row, rect, pad: float = 6.0) -> bool:
    cx, cy = (row.x0 + row.x1) / 2, row.yc
    return rect[0] - pad <= cx <= rect[2] + pad and rect[1] - pad <= cy <= rect[3] + pad


def _cluster_rects(rects: list, pad: float) -> list[tuple[list[float], int]]:
    """Union-find style clustering of overlapping (padded) rectangles."""
    clusters: list[tuple[list[float], int]] = []
    for r in sorted(rects, key=lambda r: (r[1], r[0])):
        box = [r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad]
        merged = True
        members = 1
        while merged:
            merged = False
            for i, (c, n) in enumerate(clusters):
                if not (box[2] < c[0] or box[0] > c[2] or box[3] < c[1] or box[1] > c[3]):
                    box = [min(box[0], c[0]), min(box[1], c[1]), max(box[2], c[2]), max(box[3], c[3])]
                    members += n
                    clusters.pop(i)
                    merged = True
                    break
        clusters.append((box, members))
    return [([b[0] + pad, b[1] + pad, b[2] - pad, b[3] - pad], n) for b, n in clusters]


def _diagram_regions(page: pymupdf.Page) -> tuple[list[list[float]], list]:
    """Clusters of vector drawings that look like diagrams, plus raw path rects."""
    W, H = page.rect.width, page.rect.height
    rects = []
    for d in page.get_drawings():
        r = d["rect"]
        w, h = r.width, r.height
        if w * h > 0.85 * W * H:                   # slide background
            continue
        if r.y1 < HEADER_BAND * H:                 # header bar / rule
            continue
        if (h < 3 and w > 0.5 * W) or (w < 3 and h > 0.5 * H):   # separator rule
            continue
        if w < 1 and h < 1:
            continue
        rects.append([r.x0, r.y0, r.x1, r.y1])
    regions = []
    for box, n in _cluster_rects(rects, pad=10.0):
        if n >= DIAGRAM_MIN_PATHS and _rect_area(box) >= 0.02 * W * H:
            regions.append(box)
    return regions, rects


# ── document-level boilerplate detection ────────────────────────────────────

def _token_set(key: str) -> frozenset:
    return frozenset(t.rstrip("s") for t in re.findall(r"[a-z0-9]+", key) if t not in {"and", "&", "its", "of"})


def _repeated_texts(page_rows: list[tuple[float, list[Row]]], n_pages: int) -> tuple[set[str], set[str]]:
    """Normalised texts of rows in the header/footer bands that repeat across the document.

    Two ways to qualify:
      * document-wide: on >= 3% of pages spread over >= 25% of the document
        (the subject-name header present in every deck);
      * deck-wide: on >= 25 pages where, most of the time, a *different*
        title-sized line sits right below it (a header specific to one deck).
        A slide title repeated across consecutive slides fails this, because
        nothing title-sized varies underneath it.
    """
    seen: dict[str, list[int]] = defaultdict(list)
    below: dict[str, list[str]] = defaultdict(list)
    for pno, (H, rows) in enumerate(page_rows):
        for r in rows:
            if r.y1 <= HEADER_BAND * H * 1.35 or r.y0 >= FOOTER_BAND * H:
                key = normalize_key(r.text)
                seen[key].append(pno)
                if r.y1 <= HEADER_BAND * H * 1.35:
                    under = [o for o in rows if o is not r and r.y1 <= o.y0 < TITLE_BAND * H
                             and o.size >= 0.85 * r.size and len(o.text) > 3]
                    if under:
                        below[key].append(normalize_key(min(under, key=lambda o: o.y0).text))
    min_count = max(3, int(REPEAT_MIN_FRACTION * n_pages))
    doc_wide, deck_wide = set(), set()
    for key, pages in seen.items():
        if len(key) < 4:                       # "}" at the foot of code slides is not a footer
            continue
        spread = (max(pages) - min(pages)) / max(n_pages, 1)
        if len(pages) >= min_count and spread >= REPEAT_MIN_SPAN:
            doc_wide.add(key)
        elif (len(pages) >= 25 and len(below[key]) >= 0.7 * len(pages)
              and len(set(below[key])) >= 0.3 * len(below[key])):
            deck_wide.add(key)
    # spelling variants of the document-wide header ("... System" vs "... Systems")
    doc_sets = [_token_set(k) for k in doc_wide]
    for key, pages in seen.items():
        if key in doc_wide or len(pages) < 5 or len(key) < 4:
            continue
        ts = _token_set(key)
        if ts and any(len(ts & d) / len(ts | d) >= 0.75 for d in doc_sets if d):
            doc_wide.add(key)
    return doc_wide, deck_wide - doc_wide


def _page_images(page: pymupdf.Page) -> list[list[float]]:
    """Bounding boxes of images drawn on the page.

    Read from the text layer's image blocks: page.get_image_info(xrefs=True)
    hashes every image's pixels and was ~95% of total extraction time.
    """
    W, H = page.rect.width, page.rect.height
    out = []
    for b in page.get_text("blocks", flags=pymupdf.TEXT_PRESERVE_IMAGES):
        if b[6] == 1:
            out.append([max(0.0, b[0]), max(0.0, b[1]), min(W, b[2]), min(H, b[3])])
    return out


def _image_key(box: list[float], W: float, H: float) -> tuple:
    """Position/size signature: a logo sits in the same spot on every slide."""
    return (round(box[0] / W * 50), round(box[1] / H * 50), round(box[2] / W * 50), round(box[3] / H * 50))


def _decorative_image_keys(page_images: list[tuple[float, float, list]], n: int) -> set[tuple]:
    counts: dict[tuple, list[int]] = defaultdict(list)
    for pno, (W, H, boxes) in enumerate(page_images):
        for b in boxes:
            # only small images can be decoration; full-slide screenshots also
            # repeat the same position on every slide but ARE the content
            if _rect_area(b) < 0.1 * W * H:
                counts[_image_key(b, W, H)].append(pno)
    return {k for k, ps in counts.items()
            if len(set(ps)) >= max(3, REPEAT_MIN_FRACTION * n)
            and (max(ps) - min(ps)) / max(n, 1) >= 0.1}


# ── per-slide assembly ──────────────────────────────────────────────────────

def _looks_like_label(row: Row) -> bool:
    words = row.text.split()
    return (len(words) <= LABEL_MAX_WORDS and len(row.text) <= LABEL_MAX_CHARS
            and not _BULLET_RE.match(row.text) and not _NUMBERED_RE.match(row.text))


def _is_tiny_fragment(text: str) -> bool:
    t = text.strip()
    return len(t) <= 3 and not _BULLET_RE.fullmatch(t)


def _code_block(rows: list[Row]) -> str:
    xs = sorted({round(r.x0 / 8) for r in rows})
    level = {x: i for i, x in enumerate(xs)}
    return "\n".join("    " * level[round(r.x0 / 8)] + r.text for r in sorted(rows, key=lambda r: r.y0))


def _build_items(rows: list[Row], body_size: float) -> list[dict]:
    """Rejoin wrapped lines into bullet items and record nesting level."""
    items: list[dict] = []
    if not rows:
        return items
    base_x = min(r.x0 for r in rows)
    prev: Row | None = None
    for r in rows:
        text = r.text
        is_bullet = bool(_BULLET_RE.match(text))
        is_numbered = bool(_NUMBERED_RE.match(text))
        if is_bullet:
            text = _BULLET_RE.sub("", text, count=1)
        heading_like = r.bold and len(text.split()) <= 10 and not is_bullet
        new_item = (
            not items or is_bullet or is_numbered or heading_like
            or prev is None
            or (r.y0 - prev.y1) > 0.9 * max(r.size, 1)
            or r.x0 < items[-1]["_x"] - 8
            or abs(r.size - prev.size) > 2
        )
        if new_item:
            offset = r.x0 - base_x
            level = 0 if offset < 15 else (1 if offset < 50 else 2)
            items.append({"text": text, "level": level,
                          "kind": "bullet" if is_bullet else ("numbered" if is_numbered else "text"),
                          "_x": r.x0})
        else:
            last = items[-1]
            if last["text"].endswith("-") and text[:1].islower():
                last["text"] = last["text"][:-1] + text
            else:
                last["text"] = f"{last['text']} {text}"
        prev = r
    for it in items:
        it.pop("_x", None)
        it["text"] = it["text"].strip()
    return [it for it in items if it["text"]]


_FORMULA_RE = re.compile(
    r"\b[OΘΩθo]\s*\(\s*n\s*\d|\blog\s?\d\s?n\b|\b[nN]\d\b|\b(?:10|2)\d{1,2}\s*(?:bits?|bytes?|bps|m/s|Hz)\b"
    r"|\b\d+\s*[x×]\s*10\d\b"
)


def extract_pdf(pdf_path: Path, subject: str, ocr_engine=None) -> tuple[list[SlideRecord], set[str]]:
    """All slides of one PDF, plus the running header/footer texts that were removed.

    With `ocr_engine` (a RapidOCR instance), slides that have no text layer at
    all but do contain a picture are OCR'd (see `_ocr_slide`).
    """
    doc = pymupdf.open(pdf_path)
    pages = list(doc)
    n = len(pages)
    page_rows = [(p.rect.height, _page_rows(p)) for p in pages]
    doc_wide, deck_wide = _repeated_texts(page_rows, n)
    boiler = doc_wide | deck_wide
    page_images = [(p.rect.width, p.rect.height, _page_images(p)) for p in pages]
    decor = _decorative_image_keys(page_images, n)

    slides: list[SlideRecord] = []
    for pno, page in enumerate(pages):
        W, H = page.rect.width, page.rect.height
        rows = page_rows[pno][1]
        rec = SlideRecord(subject=subject, pdf=pdf_path.name, page=pno + 1, width=W, height=H)
        # personal notes added on top of the slides (typed note boxes) are not slide content
        note_boxes = [list(a.rect) for a in page.annots(types=[pymupdf.PDF_ANNOT_FREE_TEXT, pymupdf.PDF_ANNOT_TEXT])]
        if note_boxes:
            rec.removed_notes = [r.text for r in rows if any(_inside(r, b, pad=3) for b in note_boxes)]
            rows = [r for r in rows if not any(_inside(r, b, pad=3) for b in note_boxes)]
        rec.raw_chars = sum(len(r.text) for r in rows)
        rec.max_font = max((r.size for r in rows), default=0.0)

        # boilerplate: running header/footer, slide numbers, URLs
        kept: list[Row] = []
        for r in rows:
            key = normalize_key(r.text)
            in_bands = r.y1 <= HEADER_BAND * H * 1.35 or r.y0 >= FOOTER_BAND * H
            if in_bands and key in boiler:
                if key in deck_wide:
                    rec.running_header = r.text
                continue
            if r.y0 >= FOOTER_BAND * H and _SLIDE_NUMBER_RE.match(r.text.strip()):
                continue
            if _DATE_RE.match(r.text.strip()):
                continue
            urls = _URL_RE.findall(r.text)
            if urls:
                rec.urls.extend(urls)
                rest = _URL_RE.sub("", r.text).strip(" :-")
                if len(rest) < 4:
                    continue
                r = Row(**{**asdict(r), "text": rest})
            kept.append(r)
        if kept:
            big = max(r.size for r in kept)
            rec.largest_text = " ".join(r.text for r in sorted(kept, key=lambda r: r.y0) if r.size >= big - 0.5)

        # content images and diagram regions
        img_boxes = []
        for b in page_images[pno][2]:
            if _image_key(b, W, H) in decor or _rect_area(b) < DECOR_IMAGE_MAX_AREA * W * H:
                continue
            if _rect_area(b) > 0.9 * W * H and rec.raw_chars > 40:
                continue                      # full-slide background picture behind text
            img_boxes.append(b)
        rec.content_image_frac = min(1.0, sum(_rect_area(b) for b in img_boxes) / (W * H))
        regions, path_rects = _diagram_regions(page)
        rec.diagram_frac = min(1.0, sum(_rect_area(b) for b in regions) / (W * H))

        # tables (only worth the cost when there are enough drawn lines)
        table_boxes = []
        h_rules = sum(1 for r in path_rects if (r[3] - r[1]) < 3 and (r[2] - r[0]) > 20)
        v_rules = sum(1 for r in path_rects if (r[2] - r[0]) < 3 and (r[3] - r[1]) > 10)
        cell_boxes = sum(1 for r in path_rects if (r[2] - r[0]) > 20 and (r[3] - r[1]) > 10)
        if (h_rules >= 3 and v_rules >= 2) or cell_boxes >= 6:
            try:
                for t in page.find_tables().tables:
                    cells = t.extract()
                    if len(cells) >= 2 and len(cells[0]) >= 2:
                        clean = [[re.sub(r"\s+", " ", c or "").strip() for c in row] for row in cells]
                        filled = sum(1 for row in clean for c in row if c)
                        if filled >= 0.4 * len(clean) * len(clean[0]):
                            rec.tables.append(clean)
                            table_boxes.append(list(t.bbox))
            except Exception:
                pass
        if table_boxes:
            kept = [r for r in kept if not any(_inside(r, b, pad=2) for b in table_boxes)]
            regions = [g for g in regions if not any(_inside_box(g, b) for b in table_boxes)]

        # title: largest font near the top
        body_sizes = Counter()
        for r in kept:
            body_sizes[r.size] += len(r.text)
        rec.body_size = body_sizes.most_common(1)[0][0] if body_sizes else 0.0
        title_rows: list[Row] = []
        cands = [r for r in kept if r.y0 < TITLE_BAND * H and len(r.text) <= 140 and not _is_tiny_fragment(r.text)]
        if cands:
            top_size = max(r.size for r in cands)
            if top_size > rec.body_size + 0.5 or (top_size >= rec.body_size and cands[0].bold):
                first = min((r for r in cands if r.size >= top_size - 0.5), key=lambda r: r.y0)
                title_rows = [first]
                for r in sorted(cands, key=lambda r: r.y0):
                    if r is first or r.y0 <= first.y0:
                        continue
                    if abs(r.size - first.size) <= 0.5 and r.y0 - title_rows[-1].y1 < 0.6 * r.size:
                        title_rows.append(r)
        if title_rows:
            rec.title = _BULLET_RE.sub("", " ".join(r.text for r in title_rows)).strip()
            rec.title_size = title_rows[0].size
        title_ids = {id(r) for r in title_rows}
        kept = [r for r in kept if id(r) not in title_ids]

        # diagram labels: short text inside an image or drawing cluster, tiny fragments anywhere
        body: list[Row] = []
        code_rows: list[Row] = []
        for r in kept:
            in_figure = any(_inside(r, b) for b in img_boxes + regions)
            codeish = r.mono or bool(_CODE_RE.search(r.text))
            if codeish:
                code_rows.append(r)
                continue
            if (in_figure and _looks_like_label(r)) or _is_tiny_fragment(r.text):
                rec.labels.append(r.text)
                continue
            body.append(r)

        # code block when code dominates, otherwise code-like lines stay in the body
        if len(code_rows) >= 3 and len(code_rows) >= 0.5 * (len(code_rows) + len(body)):
            rec.code = _code_block(code_rows)
        else:
            body = sorted(body + code_rows, key=lambda r: (round(r.y0 / max(r.size * 0.6, 1)), r.x0))
        rec.items = _build_items(body, rec.body_size)
        rec.n_rows = len(body) + len(code_rows)
        rec.formula_suspect = bool(_FORMULA_RE.search(rec.body_text()))
        slides.append(rec)

    if ocr_engine is not None:
        targets = [s for s in slides if len(s.title) + len(s.body_text()) < 15 and s.content_image_frac > 0.2]
        ocr_rows = {s.page: _ocr_rows(pages[s.page - 1], ocr_engine) for s in targets}
        # text repeated on many OCR'd slides is a logo or banner ("PES UNIVERSITY")
        freq = Counter(k for rows in ocr_rows.values() for k in {normalize_key(r.text) for r in rows})
        ocr_boiler = {k for k, c in freq.items()
                      if c >= max(6, 0.3 * len(ocr_rows)) and len(k.split()) <= 3}
        for s in targets:
            _fill_from_ocr(s, [r for r in ocr_rows[s.page] if normalize_key(r.text) not in ocr_boiler])
        boiler |= ocr_boiler
    doc.close()
    return slides, boiler


OCR_DPI = 110


def _ocr_rows(page: pymupdf.Page, engine) -> list[Row]:
    """OCR a slide image into Rows (box height stands in for font size)."""
    scale = 72 / OCR_DPI
    result, _ = engine(page.get_pixmap(dpi=OCR_DPI, annots=False).tobytes("png"))   # no ink/notes
    rows = []
    for box, text, conf in result or []:
        text = re.sub(r"\s+", " ", text).strip()
        if not text or conf < 0.6:
            continue
        xs, ys = [p[0] * scale for p in box], [p[1] * scale for p in box]
        rows.append(Row(text=text, x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
                        size=round((max(ys) - min(ys)) * 0.8, 1), bold=False, mono=False))
    # join fragments on the same line, as for the text layer
    rows.sort(key=lambda r: (r.yc, r.x0))
    merged: list[Row] = []
    for r in rows:
        p = merged[-1] if merged else None
        if p and abs(r.yc - p.yc) < 0.5 * min(r.size, p.size) and 0 <= r.x0 - p.x1 < 3 * max(r.size, p.size):
            p.text, p.x1 = f"{p.text} {r.text}", max(p.x1, r.x1)
            p.y0, p.y1, p.size = min(p.y0, r.y0), max(p.y1, r.y1), max(p.size, r.size)
        else:
            merged.append(r)
    return merged


def _fill_from_ocr(rec: SlideRecord, rows: list[Row]) -> None:
    """Title = tallest line near the top; short fragments are diagram labels; the rest is body."""
    if not rows:
        return
    H = rec.height
    top = [r for r in rows if r.y0 < TITLE_BAND * H and len(r.text.split()) <= 12]
    title = None
    if top:
        tallest = max(r.size for r in top)
        if tallest >= 1.15 * sorted(r.size for r in rows)[len(rows) // 2]:
            title = min((r for r in top if r.size >= 0.85 * tallest), key=lambda r: r.y0)
    body = []
    for r in rows:
        if r is title:
            continue
        if len(r.text.split()) <= 2 and len(r.text) <= 14:
            rec.labels.append(r.text)
        else:
            body.append(r)
    if title is not None:
        rec.title = _BULLET_RE.sub("", title.text).strip()
        rec.title_size = title.size
    body.sort(key=lambda r: (round(r.y0 / max(r.size * 0.6, 1)), r.x0))
    rec.items = _build_items(body, 0.0)
    rec.ocr = True
    rec.formula_suspect = bool(_FORMULA_RE.search(rec.body_text()))


def _inside_box(inner, outer, pad: float = 4.0) -> bool:
    return (inner[0] >= outer[0] - pad and inner[1] >= outer[1] - pad
            and inner[2] <= outer[2] + pad and inner[3] <= outer[3] + pad)
