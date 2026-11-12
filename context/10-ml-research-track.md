# 10 — ML research track (mostly legacy / offline)

**Production Round 1 does NOT use DeBERTa by default** — Tier 0 `ResumeEvidenceEvaluator` is active (see 03). DeBERTa v5_1088 is Tier 1 fallback. Treat most of this as frozen research; don't refactor without reason.

## Model layer (`main_cap/cap/`)
- `model_backbone.py`: `BackboneConfig(hf_model_id, max_length)`, `CrossEncoderBackbone` (DeBERTa-v3-base, (text_a, text_b) pairs), `build_tokenizer`.
- `model_heads.py`: `CoralOrdinalHead` (CORAL ordinal regression, 5 tiers 0–4), `MultiTaskModel` (one head per dimension + concept heads, dimension masking via `reasoning_dimension_relevance.py`), minimal train loop.
- `overall_score_model.py`: `OverallScoreModel` = backbone + ONE CORAL head (V3 single-overall architecture); `load_overall_checkpoint_artifact`.
- `overall_single_evaluator.py`: Evaluator using it for overall_score; dimensions from `HeuristicDiagnosticsEngine`; its internal non-answer gate disabled.
- `averaged_evaluator.py`: 0.8 model + 0.2 heuristic (`HEURISTIC_WEIGHT`), `_grade` cutpoints .90/.75/.55/.30.
- `model_evaluator.py` (`TrainedEvaluator`, `promote_trained_model`), `hybrid_evaluator.py` (Round 3 DeBERTa-authoritative hybrid; writes `hybrid_diagnostics.jsonl`), `model_dataset.py`, `model_checkpoint_io.py`, `overall_dataset.py`.
- `training_experimentation.py`: `ExperimentConfig`, deterministic `DatasetSplit` (group/spec-level), `Checkpoint`, QWK benchmarking, `PromotionDecision` policy. `experiment_dataset_io.py` JSON IO.

## Deployed checkpoint `deployed_model_overall_single_v5_1088/`
`best_checkpoint_weights.pt` (Git LFS, 735 MB), `best_checkpoint.json` (model_version `deberta_v3_base_overall_single_v5_1088_epoch8`, dataset `overall_v5_1088`), `final_promotion_decision.json` (approved). Reported: val QWK .864, test QWK .853 (n=151). Trained on Colab (`colab_training/train_overall_v5.py`, `dataset_loader_v5.py`, `evaluate_*.py`). Dataset: `artifacts/overall_v5_1088/dataset/examples.jsonl` (1,003 + 85 short-answer calibration examples in train). Known flaw: score tracks answer length (r ≈ .6–.7); can't tell fluent-wrong from correct.
`deployed_model/` = old Experiment 4 metadata only (weights absent).

## Synthetic data pipeline (Stage A)
`training_example.py` (immutable `TrainingExample` record), `training_example_assembler.py`, `generation_recipe.py`, `coverage_strategy.py`, `prompt_assembler.py`/`prompt_controllers.py`, `generation_client.py` (`GeminiGenerationClient`, `FakeGenerationClient` templates), `generation_validation.py` (reject, never repair), `synthetic_generation_pipeline.py`, `dataset_manifest.py` (+ `ReviewEventLog`), `labeling_operations.py`, `dataset_filters.py`, `dataset_relabeling.py` (per-dimension labels), `experiment_profile_library.py`/`experiment_candidate_profiles.py`.
Rewrite augmentation (Experiment 4): `rewrite_*.py`, `deterministic_rewrite*.py` (API-free transforms + SBERT drift check `rewrite_verifier_client.py`).
Most QWK numbers come from synthetic templated data — a known train/serve gap.

## Experiment scripts (one-off, Colab-intended for training)
`run_first/second/third_experiment.py`, `run_experiment_1.py`, `run_experiment_2*.py`, `run_experiment_4_{pilot,deterministic,prepare_training_data,train,evaluate}.py`, `run_dataset_relabel.py`, `run_overall_single_training.py`, `build_v5_1088_pool.py`, `build_v5_short_quality_calibration_80.py`, `validate_*.py`, `four_dim_experiment*_split.py`, `regenerate_promotion_decision.py` (hard-wired to Exp 2).
`main_cap/cap/artifacts/` (partly git-ignored): datasets (seed_dataset_v1, hand_authored_50, v2_targeted_50, gap_coverage_20, v3_grounding, v4_diagnostic with a1/a2/b0 inference analyses, overall_v5_1088). `experiment_3_reproducibility/` reports.

## Archived / removed (not in repo)
RoBERTa intent/difficulty/topic classifiers (`archive/Roberta/`, local only), v1 discussion engine, page-per-chunk RAG, resume domain classifier, A2 four-dimension research (removed 2026-10-26).

## Tests for this track
test_model_*.py, test_training_*.py, test_overall_*.py, test_dataset_*.py, test_generation_*.py, test_rewrite_*.py, test_deterministic_rewrite*.py, test_v4_diagnostic.py, test_labeling_operations.py, test_synthetic_generation_pipeline.py, test_hybrid_evaluator.py, test_averaged_evaluator.py. Some load real models (`CAP_SKIP_MODEL_TESTS=1`).
