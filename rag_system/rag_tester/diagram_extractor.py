"""
Diagram extraction from PDF pages.

Pulls out embedded images AND renders full-page crops around image
regions (diagrams are often vector-drawn, not embedded raster images —
e.g. a UML diagram made of PDF line/rect primitives won't show up as an
"image" at all). Rendering a page-region screenshot catches both cases.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class ExtractedDiagram:
    page_number: int              # 1-indexed, matches your existing citation convention
    image_bytes: bytes            # PNG bytes, ready for a VLM call
    bbox: tuple                   # (x0, y0, x1, y1) on the page, for provenance
    source: str                   # "embedded_image" | "vector_region"
    nearby_text: str              # text on the same page, for grounding/context


# Minimum size to filter out logos, bullet icons, decorative dividers
MIN_DIAGRAM_WIDTH = 120
MIN_DIAGRAM_HEIGHT = 80


def extract_embedded_images(page: fitz.Page, doc: fitz.Document) -> list[ExtractedDiagram]:
    results = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            base_image = doc.extract_image(xref)
        except Exception:
            continue
        img_bytes = base_image["image"]

        # get bbox on page for this image, if available
        rects = page.get_image_rects(xref)
        bbox = tuple(rects[0]) if rects else (0, 0, page.rect.width, page.rect.height)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w < MIN_DIAGRAM_WIDTH or h < MIN_DIAGRAM_HEIGHT:
            continue

        results.append(ExtractedDiagram(
            page_number=page.number + 1,
            image_bytes=img_bytes,
            bbox=bbox,
            source="embedded_image",
            nearby_text=page.get_text().strip(),
        ))
    return results


def detect_vector_diagram_regions(page: fitz.Page, min_drawings: int = 15) -> list[tuple]:
    """
    Heuristic for vector-drawn diagrams (common for UML/network diagrams made
    directly in the source document, not pasted as images): if a page has a
    dense cluster of line/rect drawing commands, treat that cluster's
    bounding region as a likely diagram, and render it as a screenshot for
    the VLM to interpret (VLMs work on pixels, not PDF vector primitives).
    """
    drawings = page.get_drawings()
    if len(drawings) < min_drawings:
        return []

    xs, ys, xe, ye = [], [], [], []
    for d in drawings:
        r = d["rect"]
        xs.append(r.x0); ys.append(r.y0); xe.append(r.x1); ye.append(r.y1)
    if not xs:
        return []

    region = (min(xs), min(ys), max(xe), max(ye))
    w, h = region[2] - region[0], region[3] - region[1]
    if w < MIN_DIAGRAM_WIDTH or h < MIN_DIAGRAM_HEIGHT:
        return []
    return [region]


def render_region_as_image(page: fitz.Page, bbox: tuple, zoom: float = 2.0) -> bytes:
    """Render a page region to PNG bytes at higher-than-1x zoom for VLM legibility."""
    rect = fitz.Rect(bbox)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=rect)
    return pix.tobytes("png")


def extract_diagrams_from_pdf(pdf_path: str) -> list[ExtractedDiagram]:
    doc = fitz.open(pdf_path)
    all_diagrams: list[ExtractedDiagram] = []

    for page in doc:
        all_diagrams.extend(extract_embedded_images(page, doc))

        for region in detect_vector_diagram_regions(page):
            img_bytes = render_region_as_image(page, region)
            all_diagrams.append(ExtractedDiagram(
                page_number=page.number + 1,
                image_bytes=img_bytes,
                bbox=region,
                source="vector_region",
                nearby_text=page.get_text().strip(),
            ))

    doc.close()
    return all_diagrams


def save_diagrams(diagrams: list[ExtractedDiagram], out_dir: str) -> list[dict]:
    """Save extracted diagram images to disk, return manifest entries for indexing."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, d in enumerate(diagrams):
        fname = f"page{d.page_number:03d}_{d.source}_{i}.png"
        fpath = out_path / fname
        fpath.write_bytes(d.image_bytes)
        manifest.append({
            "file": str(fpath),
            "page": d.page_number,
            "bbox": d.bbox,
            "source": d.source,
            "nearby_text": d.nearby_text[:500],  # cap for storage
        })
    return manifest
