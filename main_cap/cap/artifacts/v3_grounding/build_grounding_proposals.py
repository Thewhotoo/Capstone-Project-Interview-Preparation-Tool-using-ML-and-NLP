"""
V3 DATA REPAIR -- read-only grounding-proposal builder (Phase 3/4).

Builds `grounding_proposals.jsonl` from hand-curated, evidence-cited fragment
data below. This script does NOT modify any training artifact -- it only
reads the existing raw+judged JSONL pools (to validate example_ids/source_ids
exist and to run leakage/safety checks) and writes new files under
artifacts/v3_grounding/.

Hard rule enforced throughout: an example's grounding fragment NEVER cites
that same example_id as evidence (no self-sourcing -- prevents the grounding
text from being a near-paraphrase of the very answer being evaluated).
Fragments are scoped to the RECEIVING example's own QUESTION topic, not to
whatever its own answer happens to discuss (this is what makes the
irrelevant-but-detailed and misconception hard cases safe to enrich).
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ARTIFACTS_DIR = os.path.dirname(_HERE)  # main_cap/cap/artifacts

# ---------------------------------------------------------------------------
# Fragment library: one entry per (source_id, topic_tag) -> grounding text +
# the example_ids whose ANSWER TEXT the fact was drawn from (the fragment's
# "source pool" -- an individual assignment below may only cite a subset of
# this pool that excludes itself).
# ---------------------------------------------------------------------------
FRAGMENTS = {
    ("AuthEdge", "jwt_validation"): (
        "AuthEdge validates an incoming JWT by checking the signature "
        "against the issuer's public key, confirming the token has not "
        "expired, and verifying the audience claim.",
        ["v2t50_v1_010"],
    ),
    ("AuthEdge", "cookie_migration"): (
        "AuthEdge moved session tokens from localStorage to httpOnly "
        "cookies to close an XSS token-theft vector, pairing the change "
        "with SameSite=Strict and a required CSRF token on state-changing "
        "requests to avoid introducing CSRF.",
        ["v2t50_v1_019", "v2t50_v1_041"],
    ),
    ("CacheFront", "cache_invalidation"): (
        # Tightened 2026-09-09 (V3 tokenization-truncation fix, gap20_v1_016):
        # dropped the redundant second key-pattern example and the trailing
        # "since multiple app instances run" justification clause -- neither
        # was distinguishing evidence (one key example already establishes
        # the namespaced-key convention; the "why pub/sub" rationale isn't
        # needed for the textbook-vs-project contrast this example tests).
        # All load-bearing facts kept: cache-aside pattern, a concrete key
        # example, the TTL value, and the explicit pub/sub invalidation
        # mechanism every instance subscribes to.
        "CacheFront uses cache-aside with Redis (user:{id}:profile keys, "
        "10-min TTL), invalidated via a Redis pub/sub channel every "
        "instance subscribes to on writes.",
        ["gap20_v1_017"],
    ),
    ("CloudBudget", "idle_instance_detection"): (
        "CloudBudget's idle-instance flagger runs nightly via EventBridge, "
        "pulling each instance's CPU/network I/O from CloudWatch over a "
        "trailing 14-day window and flagging anything under 5% average CPU "
        "for Slack review before termination.",
        ["hand50_v1_048"],
    ),
    ("CloudScaler", "scale_out_metric"): (
        "CloudScaler's scale-out decision uses a blended CloudWatch metric "
        "(normalized CPU plus SQS queue depth) rather than CPU alone, "
        "because CPU alone reacted too late during bursty traffic spikes.",
        ["seed_v1_006", "seed_v1_031"],
    ),
    ("CloudScaler", "cooldown_asymmetry"): (
        "CloudScaler uses an asymmetric cooldown -- a short scale-out "
        "cooldown and a much longer scale-in cooldown -- specifically to "
        "avoid flapping when traffic dips briefly between spikes.",
        ["seed_v1_031", "seed_v1_079"],
    ),
    ("ConsensusHub", "randomized_timeout"): (
        "ConsensusHub's election timeout window was originally set "
        "following the original Raft paper's range, but had to be widened "
        "after JVM full-GC stop-the-world pauses caused spurious leader "
        "elections under real GC pressure.",
        ["gap20_v1_019"],
    ),
    ("DefectScan", "augmentation_class_imbalance"): (
        "DefectScan's training pipeline handles class imbalance between "
        "defective and non-defective images with targeted augmentation "
        "(rotation, brightness jitter, synthetic crop-and-paste of defect "
        "regions) plus a class-weighted loss, validated on a held-out set "
        "that preserves the original imbalance.",
        ["seed_v1_046"],
    ),
    ("DeployWave", "blue_green_mechanism"): (
        # Tightened 2026-09-09 (V3 tokenization-truncation fix, gap20_v1_014):
        # dropped "blue-green" (redundant -- already in the project title,
        # which grounding_to_text prepends), "full"/"release job" (filler
        # adjectives/nouns with no distinguishing content), and the
        # redundant "AWS" prefix on CodeDeploy (already in the trailing
        # technologies list). All load-bearing facts kept: the two-ECS-sets/
        # one-ALB-listener shape, the GitHub-Actions-triggers-CodeDeploy
        # relationship, the target-group-weight-shift mechanism, and the
        # concrete /healthz 5-consecutive-200s gate.
        "DeployWave runs two ECS service sets behind one ALB listener; "
        "GitHub Actions triggers CodeDeploy to shift target-group weight, "
        "gated on 5 consecutive /healthz 200s.",
        ["gap20_v1_015"],
    ),
    ("EdgeRelay", "failing_node_detection"): (
        "EdgeRelay tracks a rolling per-node production error rate (not "
        "just liveness health checks) and pulls a node out of rotation if "
        "that error rate crosses a threshold even while its health check "
        "stays green, using shadow traffic to confirm recovery before "
        "re-adding it.",
        ["v2t50_v1_018"],
    ),
    ("FitTrack", "offline_sync_mechanism"): (
        "FitTrack's offline sync stores workout entries locally with a "
        "sequence number and a synced flag, then batches unsynced rows to "
        "the sync endpoint once connectivity returns.",
        ["seed_v1_007"],
    ),
    ("FitTrack", "conflict_resolution"): (
        "FitTrack resolves concurrent edit conflicts with last-write-wins "
        "keyed on a server-assigned timestamp, chosen over full CRDT "
        "merging because the data model did not need partial-field merge "
        "semantics.",
        ["seed_v1_007"],
    ),
    ("GeoIndex", "gist_index_performance"): (
        "GeoIndex uses a PostGIS GiST spatial index so most of the table "
        "can be pruned by the index itself before an exact distance is "
        "computed, which measurably cut radius-search latency versus a "
        "naive bounding-box-then-filter approach on a large dataset.",
        ["hand50_v1_028"],
    ),
    ("InsightBoard", "indexing_strategy"): (
        "InsightBoard's slowest dashboard report was sped up with a "
        "covering index on (org_id, event_date, event_type), letting the "
        "database satisfy the GROUP BY entirely from the index.",
        ["v2t50_v1_048"],
    ),
    ("InvoiceCore", "double_charge_prevention"): (
        "InvoiceCore prevents double-charging using an idempotency key "
        "per charge attempt, checked against the payment provider before "
        "a retried request is allowed to charge again.",
        ["seed_v1_030"],
    ),
    ("MeshRouter", "circuit_breaking_thresholds"): (
        "MeshRouter's circuit breaker trips after a small number of "
        "consecutive failures within a short window and holds the "
        "circuit open for a bounded period before a single half-open "
        "probe is allowed through; the payments service is given a "
        "stricter override (fewer failures to trip, longer open period) "
        "than the mesh default.",
        ["seed_v1_029", "seed_v1_088"],
    ),
    ("OrderMesh", "kafka_rationale"): (
        "OrderMesh uses Kafka for order events instead of a direct "
        "database write for durability and decoupling between the order "
        "service and its downstream consumers (billing, inventory), and "
        "to allow replaying events if a downstream service falls behind.",
        ["seed_v1_001"],
    ),
    ("QueryTune", "composite_index"): (
        "QueryTune sped up its slowest dashboard query by adding a "
        "composite index covering both the WHERE-clause columns and the "
        "ORDER BY column together, letting the database satisfy the query "
        "directly from the index.",
        ["v2t50_v1_011"],
    ),
    ("QuickLookup", "cache_invalidation"): (
        "QuickLookup invalidates its Redis cache proactively: the write "
        "path publishes an invalidation event with the product ID right "
        "after the database commit, and every app instance deletes the "
        "corresponding key on receipt, with a short TTL kept only as a "
        "safety net.",
        ["v2t50_v1_016"],
    ),
    ("RollOut", "no_downtime_deploy"): (
        "RollOut brings up the new version alongside the old, runs a "
        "health check against it, then switches the load balancer to the "
        "new version and terminates the old one after a short drain "
        "period.",
        ["v2t50_v1_009"],
    ),
    ("ShardDB", "shard_rebalancing"): (
        "ShardDB rebalances shards using consistent hashing with virtual "
        "nodes so adding a shard moves roughly 1/N of the keyspace, via a "
        "background dual-write phase (writes go to both old and new shard "
        "for a key range while a migration worker backfills) with an "
        "atomic per-key-range cutover.",
        ["seed_v1_005", "seed_v1_044", "seed_v1_092"],
    ),
    ("ShardDB", "query_routing"): (
        "ShardDB routes each query by hashing the customer ID to decide "
        "which shard owns the corresponding rows.",
        ["seed_v1_076"],
    ),
    ("StreamETL", "schema_evolution"): (
        "StreamETL writes to S3 in Parquet format, which enforces "
        "backward-compatible schema evolution at the storage layer -- new "
        "upstream columns appear as null in old files and removed columns "
        "are ignored on read.",
        ["seed_v1_011"],
    ),
    ("StreamETL", "backfill_tooling"): (
        "StreamETL's backfill CLI re-runs any historical partition "
        "through the current DAG version by pinning the Spark job's "
        "config to a snapshot of the transform code from that date, "
        "tracking backfilled partitions in a metadata table to avoid "
        "double-processing.",
        ["seed_v1_023", "seed_v1_045"],
    ),
    ("TaskFlow", "realtime_collaboration"): (
        "TaskFlow implements real-time collaboration using WebSockets to "
        "push updates to connected clients, with Redis used to keep state "
        "in sync across multiple server instances.",
        ["seed_v1_000"],
    ),
    ("TaskRunner", "duplicate_prevention_and_recovery"): (
        "TaskRunner workers claim jobs with an atomic conditional update "
        "that only succeeds for one worker, preventing duplicate "
        "processing at claim time; separately, every claimed job carries "
        "a heartbeat the worker refreshes while working, and a reaper "
        "resets any job whose heartbeat goes stale back to pending so "
        "another worker can pick it up.",
        ["v2t50_v1_007", "v2t50_v1_017"],
    ),
    ("VaultGuard", "key_rotation"): (
        "VaultGuard's key rotation uses envelope encryption: each secret "
        "has its own data key, which is itself wrapped by a master key in "
        "Vault's KMS-backed keyring, so rotating the master key only "
        "re-wraps the small data keys rather than re-encrypting the "
        "secret payloads.",
        ["seed_v1_028"],
    ),
    ("VaultGuard", "access_control"): (
        "VaultGuard controls access through Vault's policy system, with "
        "each service given a policy scoped to only the secret paths it "
        "needs.",
        ["seed_v1_014", "seed_v1_041"],
    ),
    ("VoteRing", "randomized_election_timeout"): (
        "VoteRing gives each node a randomized election timeout so that "
        "nodes do not all time out and start an election simultaneously, "
        "reducing the chance of a split vote.",
        ["v2t50_v1_014"],
    ),
}

# ---------------------------------------------------------------------------
# Assignments: example_id -> (fragment_key, evidence_ids, confidence)
# evidence_ids is an explicit subset of the fragment's source pool that
# EXCLUDES this example_id itself (enforced by an assertion below too).
# ---------------------------------------------------------------------------
ASSIGNMENTS = {
    # AuthEdge
    "v2t50_v1_035": (("AuthEdge", "jwt_validation"), ["v2t50_v1_010"], "MEDIUM"),
    "v2t50_v1_019": (("AuthEdge", "cookie_migration"), ["v2t50_v1_041"], "HIGH"),
    "v2t50_v1_041": (("AuthEdge", "cookie_migration"), ["v2t50_v1_019"], "HIGH"),
    # CacheFront
    "gap20_v1_016": (("CacheFront", "cache_invalidation"), ["gap20_v1_017"], "MEDIUM"),
    # CloudBudget
    "hand50_v1_047": (("CloudBudget", "idle_instance_detection"), ["hand50_v1_048"], "MEDIUM"),
    # CloudScaler
    "seed_v1_006": (("CloudScaler", "scale_out_metric"), ["seed_v1_031"], "HIGH"),
    "seed_v1_031": (("CloudScaler", "scale_out_metric"), ["seed_v1_006"], "HIGH"),
    "seed_v1_067": (("CloudScaler", "scale_out_metric"), ["seed_v1_006", "seed_v1_031"], "MEDIUM"),
    "seed_v1_099": (("CloudScaler", "scale_out_metric"), ["seed_v1_006", "seed_v1_031"], "MEDIUM"),
    "seed_v1_021": (("CloudScaler", "scale_out_metric"), ["seed_v1_006", "seed_v1_031"], "MEDIUM"),
    "seed_v1_079": (("CloudScaler", "cooldown_asymmetry"), ["seed_v1_031"], "HIGH"),
    # ConsensusHub
    "gap20_v1_018": (("ConsensusHub", "randomized_timeout"), ["gap20_v1_019"], "MEDIUM"),
    # DefectScan
    "seed_v1_070": (("DefectScan", "augmentation_class_imbalance"), ["seed_v1_046"], "MEDIUM"),
    # DeployWave
    "gap20_v1_014": (("DeployWave", "blue_green_mechanism"), ["gap20_v1_015"], "MEDIUM"),
    # EdgeRelay
    "v2t50_v1_033": (("EdgeRelay", "failing_node_detection"), ["v2t50_v1_018"], "MEDIUM"),
    # FitTrack
    "seed_v1_043": (("FitTrack", "offline_sync_mechanism"), ["seed_v1_007"], "MEDIUM"),
    "seed_v1_022": (("FitTrack", "offline_sync_mechanism"), ["seed_v1_007"], "HIGH"),
    "seed_v1_094": (("FitTrack", "conflict_resolution"), ["seed_v1_007"], "HIGH"),
    # GeoIndex
    "hand50_v1_027": (("GeoIndex", "gist_index_performance"), ["hand50_v1_028"], "MEDIUM"),
    # InsightBoard
    "v2t50_v1_046": (("InsightBoard", "indexing_strategy"), ["v2t50_v1_048"], "MEDIUM"),
    # InvoiceCore
    "seed_v1_042": (("InvoiceCore", "double_charge_prevention"), ["seed_v1_030"], "MEDIUM"),
    "seed_v1_020": (("InvoiceCore", "double_charge_prevention"), ["seed_v1_030"], "HIGH"),
    # MeshRouter
    "seed_v1_029": (("MeshRouter", "circuit_breaking_thresholds"), ["seed_v1_088"], "HIGH"),
    "seed_v1_088": (("MeshRouter", "circuit_breaking_thresholds"), ["seed_v1_029"], "HIGH"),
    "seed_v1_009": (("MeshRouter", "circuit_breaking_thresholds"), ["seed_v1_029", "seed_v1_088"], "HIGH"),
    # OrderMesh
    "seed_v1_025": (("OrderMesh", "kafka_rationale"), ["seed_v1_001"], "MEDIUM"),
    # QueryTune
    "v2t50_v1_032": (("QueryTune", "composite_index"), ["v2t50_v1_011"], "MEDIUM"),
    # QuickLookup
    "v2t50_v1_043": (("QuickLookup", "cache_invalidation"), ["v2t50_v1_016"], "MEDIUM"),
    # RollOut
    "v2t50_v1_044": (("RollOut", "no_downtime_deploy"), ["v2t50_v1_009"], "MEDIUM"),
    # ShardDB
    "seed_v1_005": (("ShardDB", "shard_rebalancing"), ["seed_v1_044", "seed_v1_092"], "HIGH"),
    "seed_v1_044": (("ShardDB", "shard_rebalancing"), ["seed_v1_005", "seed_v1_092"], "HIGH"),
    "seed_v1_092": (("ShardDB", "shard_rebalancing"), ["seed_v1_005", "seed_v1_044"], "HIGH"),
    "seed_v1_027": (("ShardDB", "query_routing"), ["seed_v1_076"], "MEDIUM"),
    "seed_v1_017": (("ShardDB", "query_routing"), ["seed_v1_076"], "HIGH"),
    # StreamETL
    "seed_v1_023": (("StreamETL", "schema_evolution"), ["seed_v1_011"], "HIGH"),
    "seed_v1_045": (("StreamETL", "backfill_tooling"), ["seed_v1_023"], "HIGH"),
    # TaskFlow
    "seed_v1_024": (("TaskFlow", "realtime_collaboration"), ["seed_v1_000"], "MEDIUM"),
    # TaskRunner
    "v2t50_v1_040": (
        ("TaskRunner", "duplicate_prevention_and_recovery"),
        ["v2t50_v1_007", "v2t50_v1_017"],
        "HIGH",
    ),
    # VaultGuard
    "seed_v1_008": (("VaultGuard", "key_rotation"), ["seed_v1_028"], "HIGH"),
    "seed_v1_014": (("VaultGuard", "access_control"), ["seed_v1_041"], "MEDIUM"),
    "seed_v1_041": (("VaultGuard", "access_control"), ["seed_v1_014"], "MEDIUM"),
    # VisionSort -- none (see analysis)
    # VoteRing
    "v2t50_v1_034": (("VoteRing", "randomized_election_timeout"), ["v2t50_v1_014"], "MEDIUM"),
}

# TaskRunner's v2t50_v1_040 fragment is a concatenation of two scoped
# fragments since its own question is explicitly multipart (asks about both
# duplicate prevention AND crash recovery). Build its text specially.
_TASKRUNNER_COMBINED_TEXT = (
    FRAGMENTS[("TaskRunner", "duplicate_prevention_and_recovery")][0]
)

SCOPE_LABELS = {
    ("AuthEdge", "jwt_validation"): "jwt_validation",
    ("AuthEdge", "cookie_migration"): "cookie_migration",
    ("CacheFront", "cache_invalidation"): "cache_invalidation",
    ("CloudBudget", "idle_instance_detection"): "idle_instance_detection",
    ("CloudScaler", "scale_out_metric"): "scale_out_metric",
    ("CloudScaler", "cooldown_asymmetry"): "cooldown_asymmetry",
    ("ConsensusHub", "randomized_timeout"): "randomized_timeout",
    ("DefectScan", "augmentation_class_imbalance"): "augmentation_class_imbalance",
    ("DeployWave", "blue_green_mechanism"): "blue_green_mechanism",
    ("EdgeRelay", "failing_node_detection"): "failing_node_detection",
    ("FitTrack", "offline_sync_mechanism"): "offline_sync_mechanism",
    ("FitTrack", "conflict_resolution"): "conflict_resolution",
    ("GeoIndex", "gist_index_performance"): "gist_index_performance",
    ("InsightBoard", "indexing_strategy"): "indexing_strategy",
    ("InvoiceCore", "double_charge_prevention"): "double_charge_prevention",
    ("MeshRouter", "circuit_breaking_thresholds"): "circuit_breaking_thresholds",
    ("OrderMesh", "kafka_rationale"): "kafka_rationale",
    ("QueryTune", "composite_index"): "composite_index",
    ("QuickLookup", "cache_invalidation"): "cache_invalidation",
    ("RollOut", "no_downtime_deploy"): "no_downtime_deploy",
    ("ShardDB", "shard_rebalancing"): "shard_rebalancing",
    ("ShardDB", "query_routing"): "query_routing",
    ("StreamETL", "schema_evolution"): "schema_evolution",
    ("StreamETL", "backfill_tooling"): "backfill_tooling",
    ("TaskFlow", "realtime_collaboration"): "realtime_collaboration",
    ("TaskRunner", "duplicate_prevention_and_recovery"): "duplicate_prevention_and_recovery",
    ("VaultGuard", "key_rotation"): "key_rotation",
    ("VaultGuard", "access_control"): "access_control",
    ("VoteRing", "randomized_election_timeout"): "randomized_election_timeout",
}


def build_proposals(pool):
    """pool: list of TrainingExample-like dicts with example_id/source_id."""
    by_id = {e["example_id"]: e for e in pool}
    proposals = []
    for example_id, (frag_key, evidence_ids, confidence) in ASSIGNMENTS.items():
        assert example_id in by_id, f"unknown example_id in assignments: {example_id}"
        assert example_id not in evidence_ids, f"self-sourcing detected for {example_id}"
        rec = by_id[example_id]
        source_id = rec["source_id"]
        assert frag_key[0] == source_id, (
            f"{example_id}: fragment project {frag_key[0]!r} != "
            f"example's own source_id {source_id!r}"
        )
        for eid in evidence_ids:
            assert eid in by_id, f"{example_id}: evidence {eid} not found in pool"
            assert by_id[eid]["source_id"] == source_id, (
                f"{example_id}: evidence {eid} belongs to a different "
                f"source_id ({by_id[eid]['source_id']} != {source_id})"
            )
        text = FRAGMENTS[frag_key][0]
        proposals.append(
            {
                "example_id": example_id,
                "source_id": source_id,
                "grounding_text": text,
                "evidence_example_ids": evidence_ids,
                "grounding_scope": SCOPE_LABELS[frag_key],
                "confidence": confidence,
            }
        )
    return proposals


def load_pool_records():
    """Read the raw pool JSONLs directly (no dependency on pydantic models)
    to keep this script runnable standalone for audit purposes."""
    files = [
        os.path.join(_ARTIFACTS_DIR, "seed_dataset_v1", "seed_v1_3_repaired.jsonl"),
        os.path.join(_ARTIFACTS_DIR, "hand_authored_50", "hand_authored_50_v1.jsonl"),
        os.path.join(_ARTIFACTS_DIR, "gap_coverage_20", "gap20_v1.jsonl"),
        os.path.join(_ARTIFACTS_DIR, "v2_targeted_50", "v2_targeted_50_v1.jsonl"),
    ]
    records = []
    seen = set()
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                eid = rec["example_id"]
                if eid in seen:
                    continue
                seen.add(eid)
                records.append(rec)
    return records


if __name__ == "__main__":
    pool = load_pool_records()
    assert len(pool) == 220, f"expected 220 pool records, got {len(pool)}"
    proposals = build_proposals(pool)
    out_path = os.path.join(_HERE, "grounding_proposals.jsonl")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for p in proposals:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Wrote {len(proposals)} grounding proposals to {out_path}")
