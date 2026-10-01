# Contributing Guide

This repository combines the full capstone stack so the team can work on the same project without duplicating setup steps.

## Branch Ownership

- `main` is the integration branch for stable combined work.
- `adaptive-engine` is the branch for the adaptive interview, RAG, RoBERTa, and API integration work.
- `resume_classifier` is the branch for the resume classifier model and its supporting API.

## Working Pattern

1. Pull the latest branch before starting new work.
2. Create a feature branch from the branch that matches your component.
3. Keep changes focused to one model or one workflow slice.
4. Open pull requests back into the owning branch, then merge to `main` after validation.
5. Avoid committing generated caches, local environments, or OS artifacts.

## Suggested Checks

- Resume classifier: run the classifier tests or sample prediction flow.
- Adaptive engine: run the Flask app and the workflow endpoints.
- RAG system: run the standalone RAG tester scripts for the selected knowledge base.

If a change touches shared files, coordinate the merge order first so the branches do not drift.
