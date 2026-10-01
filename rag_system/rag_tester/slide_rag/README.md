# slide_rag — retrieval over faculty lecture slides

Replaces the page-per-chunk ingestion (`dynamic_ingestor.py` → `knowledge_base/`)
with a slide-aware pipeline that writes to `knowledge_base_v2/`. The old index is
left untouched as the evaluation baseline.

```
sources/<subject>/*.pdf          input (git-ignored)
  │  Stage 1  extract.py          layout-aware reading: title by font size/position,
  │                               running header/footer and logos removed by repetition,
  │                               diagram labels set aside by position, tables rebuilt,
  │                               code re-indented, wrapped bullets rejoined,
  │                               OCR for picture-only slides (RapidOCR, optional)
  │  Stage 2  classify.py         slide types; admin / contents / title slides dropped;
  │                               incremental builds + duplicates collapsed;
  │                               in-slide quiz MCQs set aside (quiz.json)
  │  Stage 4  sections.py         consecutive slides regrouped into sections
  │                               ("(contd.)", same stem, untitled continuations,
  │                               problem + solution), capped at 450 words
  │  Stage 6  index.py            children (slides + section openings) with breadcrumb
  │                               headers → FAISS + BM25; parents = sections
  │  Stage 8  report.py           report.md / report.json per subject
  ▼
knowledge_base_v2/<subject>/     slides.json sections.json children.json quiz.json
                                 index.faiss bm25.pkl manifest.json report.md
```

Not built yet (need an LLM): Stage 3 vision recovery (slides listed under
`needs_vision` in slides.json), Stage 5 study notes, Stage 7 question bank.

## Commands (run from `rag_system/rag_tester`)

```
python -m slide_rag.build                      # all subjects in sources/
python -m slide_rag.build --subject dbms
python -m slide_rag.retrieval_eval             # gold + probe sets, vs the old index
python -m slide_rag.retrieval_eval --subject ooad --show-misses
python -m pytest slide_rag/tests -q
```

Stage 1 output is cached in `.slide_cache/` (keyed by PDF hash + extractor
version), so only grouping/indexing re-runs after a code change there.

## Using it

```python
from slide_rag.retrieve import retrieve, get_context_with_pages
hits = retrieve("dbms", "When do you use HAVING instead of WHERE?", top_k=3)
hits[0]["title"], hits[0]["pages"], hits[0]["best_page"], hits[0]["text"]
```

## Evaluation

`eval/gold_<subject>.json`: interview-style questions, each labelled with the
slide pages that answer it. Labels were picked from slide titles before any
retrieval was run. The probe set is generated from the slides (a bullet as
the query, its slide as the answer).

- *section hit@k*: a top-k section contains an expected page
- *slide hit@k*: the best-matching slide of a top-k result is an expected page
- the old index is credited for its chunk's page and the next page, because
  merged chunks hold two pages' text
