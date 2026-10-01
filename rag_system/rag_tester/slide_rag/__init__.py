"""Slide-aware RAG pipeline for faculty lecture-slide PDFs.

Stages (see docs in each module):
  1. extract   -- layout-aware reading of every slide (title, bullets, code,
                  tables; running header/footer and diagram-label noise removed)
  2. classify  -- slide type, admin/duplicate removal, incremental-build collapse
  4. sections  -- consecutive slides regrouped into self-contained sections
  6. index     -- two-level (slide child -> section parent) hybrid index with
                  contextual chunk headers
  8. report    -- per-subject diagnostics
Stages 3 (vision recovery), 5 (study notes) and 7 (question bank) need an LLM
and are not built yet.

Build:     python -m slide_rag.build --subject dbms
Evaluate:  python -m slide_rag.evaluate
"""
