"""How often each question-bank topic comes up in placement / fresher technical
interviews, as a tier:

    3  asked very often (OSI/TCP vs UDP, ACID, normalization, sorting, OOP pillars,
       deadlocks, paging, scheduling ...)
    2  asked regularly
    1  rarely asked (textbook-specific or niche)

Stored on every bank question as "interview_priority"; the technical interview's
selector (main_cap/cap/tech_interview/selector.py) weights tier-3 topics up and
tier-1 topics down, so the most-asked concepts come up most. Topics not listed
default to 2. Re-apply after regenerating the bank:

    python -m slide_rag.interview_priority        (from rag_system/rag_tester)

Hand-assigned 2026-09-30. Several tier-3 topics have no question yet (e.g. OSI
model, DNS, paging, quick sort, hashing, round robin, SQL views); they are listed
so newly generated questions pick up the right tier.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_TIER = 2

TIERS: dict[str, int] = {
    # ── Computer Networks ────────────────────────────────────────────────
    "cn.osi_model": 3, "cn.tcp_ip_model": 3, "cn.tcp_vs_udp": 3, "cn.tcp_connection_establishment": 3,
    "cn.dns": 3, "cn.network_devices": 3, "cn.arp": 3, "cn.https_and_tls": 3, "cn.ipv4_addressing": 3,
    "cn.cidr": 3, "cn.dhcp": 3, "cn.nat": 3, "cn.mac_addressing": 3, "cn.tcp_flow_control": 3,
    "cn.tcp_congestion_control": 3, "cn.packet_switching_vs_circuit_switching": 3,
    "cn.ipv6": 2, "cn.icmp": 2, "cn.udp": 2, "cn.transport_layer_services": 2,
    "cn.go_back_n_and_selective_repeat": 2, "cn.error_detection": 2, "cn.csma_cd_and_csma_ca": 2,
    "cn.firewalls": 2, "cn.distance_vector_routing": 2, "cn.link_state_routing": 2,
    "cn.switching_and_vlans": 2, "cn.collision_and_broadcast_domains": 2,
    "cn.tcp_connection_termination": 2, "cn.persistent_vs_non_persistent_http": 2, "cn.network_delays": 2,
    "cn.ethernet": 2, "cn.client_server_vs_peer_to_peer": 2, "cn.web_caching": 2, "cn.ftp": 2,
    "cn.multiple_access_protocols": 2,
    "cn.throughput_and_bottleneck_link": 1, "cn.network_edge_and_access_networks": 1,

    # ── DBMS ─────────────────────────────────────────────────────────────
    "dbms.transactions_and_acid_properties": 3, "dbms.first_normal_form_1nf": 3,
    "dbms.second_normal_form_2nf": 3, "dbms.third_normal_form_3nf": 3, "dbms.boyce_codd_normal_form_bcnf": 3,
    "dbms.super_key_and_candidate_key": 3, "dbms.primary_key": 3, "dbms.foreign_key": 3,
    "dbms.integrity_constraints": 3, "dbms.indexing_basics": 3, "dbms.inner_join": 3, "dbms.outer_joins": 3,
    "dbms.self_join_and_cross_join": 3, "dbms.having_vs_where": 3, "dbms.aggregate_functions_and_group_by": 3,
    "dbms.isolation_levels": 3, "dbms.concurrency_anomalies": 3, "dbms.sql_vs_nosql": 3, "dbms.views": 3,
    "dbms.dbms_vs_file_system": 3, "dbms.sql_command_categories": 3, "dbms.window_functions": 3,
    "dbms.er_to_relational_mapping": 2, "dbms.relationships_and_cardinality": 2, "dbms.weak_entity_sets": 2,
    "dbms.functional_dependency": 2, "dbms.update_anomalies": 2, "dbms.lossless_decomposition": 2,
    "dbms.schedules_and_serializability": 2, "dbms.two_phase_locking": 2,
    "dbms.lock_based_concurrency_control": 2, "dbms.cap_theorem": 2, "dbms.set_operations_in_sql": 2,
    "dbms.null_handling_in_sql": 2, "dbms.nested_and_correlated_subqueries": 2,
    "dbms.common_table_expressions_cte": 2, "dbms.entities_and_attributes": 2, "dbms.data_independence": 2,
    "dbms.schema_vs_instance": 2, "dbms.database_architecture": 2, "dbms.participation_constraints": 2,
    "dbms.transaction_states": 2, "dbms.relational_algebra_operations": 2, "dbms.deadlocks_in_dbms": 2,
    "dbms.denormalization": 2, "dbms.triggers": 2, "dbms.stored_procedures_and_functions": 2,
    "dbms.key_value_stores_and_redis": 2, "dbms.select_query_clauses": 2,
    "dbms.minimal_cover_of_fds": 1, "dbms.equivalence_of_sets_of_fds": 1, "dbms.relational_model": 1,
    "dbms.relational_algebra_joins_and_division": 1, "dbms.query_processing_and_join_algorithms": 1,
    "dbms.full_text_search": 1, "dbms.graph_databases_and_neo4j": 1, "dbms.vector_databases_and_embeddings": 1,
    "dbms.grant_and_revoke_privileges": 1,

    # ── Data Structures & Algorithms ─────────────────────────────────────
    "dsa.time_and_space_complexity": 3, "dsa.asymptotic_notations": 3, "dsa.best_worst_and_average_case": 3,
    "dsa.binary_search": 3, "dsa.merge_sort": 3, "dsa.quick_sort": 3, "dsa.heap_sort": 3,
    "dsa.stack_operations": 3, "dsa.simple_queue": 3, "dsa.priority_queue": 3, "dsa.hash_functions": 3,
    "dsa.open_addressing": 3, "dsa.binary_search_tree_operations": 3, "dsa.binary_search_tree_deletion": 3,
    "dsa.recursive_tree_traversals": 3, "dsa.breadth_first_search": 3, "dsa.depth_first_search": 3,
    "dsa.dijkstra_s_algorithm": 3, "dsa.graph_representation": 3,
    "dsa.insertion_sort": 2, "dsa.brute_force_sorting": 2, "dsa.sorting_by_counting": 2,
    "dsa.circular_queue": 2, "dsa.double_ended_queue": 2, "dsa.iterative_tree_traversals": 2,
    "dsa.topological_sorting": 2, "dsa.tries": 2, "dsa.heap_construction": 2, "dsa.parenthesis_matching": 2,
    "dsa.infix_to_postfix_conversion": 2, "dsa.postfix_expression_evaluation": 2, "dsa.expression_trees": 2,
    "dsa.recurrence_relations": 2, "dsa.kruskal_s_algorithm": 2, "dsa.prim_s_algorithm": 2,
    "dsa.greedy_technique": 2, "dsa.disjoint_sets_and_union_find": 2, "dsa.stacks_and_recursion": 2,
    "dsa.tree_terminology": 2, "dsa.binary_tree_properties": 2, "dsa.warshall_s_and_floyd_s_algorithms": 2,
    "dsa.huffman_coding": 2,
    "dsa.exhaustive_search": 1, "dsa.n_ary_tree_to_binary_tree_conversion": 1,
    "dsa.horspool_and_boyer_moore_string_matching": 1, "dsa.skip_lists": 1,
    "dsa.suffix_tries_and_suffix_trees": 1, "dsa.graph_terminology": 1,
    "dsa.graph_connectivity_and_path_finding": 1, "dsa.threaded_binary_search_tree": 1,
    "dsa.queue_applications": 1,

    # ── OOAD / OOP ───────────────────────────────────────────────────────
    "ooad.encapsulation": 3, "ooad.abstraction": 3, "ooad.inheritance": 3, "ooad.polymorphism": 3,
    "ooad.abstract_class_vs_interface": 3, "ooad.method_overloading": 3, "ooad.method_overriding": 3,
    "ooad.overloading_vs_overriding": 3, "ooad.constructors": 3, "ooad.singleton_pattern": 3,
    "ooad.single_responsibility_principle": 3, "ooad.open_closed_principle": 3,
    "ooad.liskov_substitution_principle": 3, "ooad.interface_segregation_principle": 3,
    "ooad.dependency_inversion_principle": 3, "ooad.is_a_vs_has_a_relationship": 3,
    "ooad.composition_over_inheritance": 3, "ooad.abstraction_vs_encapsulation": 3,
    "ooad.classes_and_objects": 3, "ooad.factory_pattern": 3, "ooad.interfaces": 3,
    "ooad.types_of_inheritance": 3, "ooad.static_members": 3, "ooad.java_object_class": 3,
    "ooad.builder_pattern": 2, "ooad.adapter_pattern": 2, "ooad.facade_and_proxy_patterns": 2,
    "ooad.command_pattern": 2, "ooad.chain_of_responsibility_pattern": 2, "ooad.model_view_controller": 2,
    "ooad.coupling_and_cohesion": 2, "ooad.design_pattern_categories": 2, "ooad.parameter_passing_in_java": 2,
    "ooad.copy_constructor": 2, "ooad.destructors_and_garbage_collection": 2, "ooad.abstract_classes": 2,
    "ooad.java_collections_and_list_interface": 2, "ooad.association": 2, "ooad.iterator_pattern": 2,
    "ooad.this_and_super_keywords": 2, "ooad.prototype_pattern": 2,
    "ooad.information_expert": 1, "ooad.creator_grasp": 1, "ooad.controller_grasp": 1,
    "ooad.indirection_and_pure_fabrication": 1, "ooad.protected_variations": 1,
    "ooad.low_level_design_approach": 1, "ooad.object_memory_allocation": 1, "ooad.anti_patterns": 1,

    # ── Operating Systems ────────────────────────────────────────────────
    "os.threads": 3, "os.process_vs_thread": 3, "os.deadlock_conditions": 3, "os.deadlock_avoidance": 3,
    "os.banker_s_algorithm": 3, "os.deadlock_vs_starvation_vs_livelock": 3, "os.paging": 3,
    "os.segmentation": 3, "os.virtual_memory_and_demand_paging": 3, "os.thrashing": 3,
    "os.fifo_page_replacement": 3, "os.optimal_and_lru_page_replacement": 3, "os.fcfs_scheduling": 3,
    "os.sjf_and_srtf_scheduling": 3, "os.round_robin_scheduling": 3, "os.priority_scheduling": 3,
    "os.preemptive_vs_non_preemptive_scheduling": 3, "os.context_switching": 3, "os.semaphores": 3,
    "os.mutex_locks": 3, "os.critical_section_problem": 3, "os.race_condition": 3,
    "os.producer_consumer_problem": 3, "os.fragmentation": 3,
    "os.deadlock_prevention": 2, "os.deadlock_detection_and_recovery": 2, "os.resource_allocation_graph": 2,
    "os.page_faults": 2, "os.user_level_vs_kernel_level_threads": 2, "os.dining_philosophers_problem": 2,
    "os.readers_writers_problem": 2, "os.contiguous_memory_allocation": 2, "os.user_mode_vs_kernel_mode": 2,
    "os.system_calls": 2, "os.interrupts": 2, "os.process_creation_and_termination": 2,
    "os.inter_process_communication": 2, "os.logical_vs_physical_address": 2,
    "os.translation_lookaside_buffer": 2, "os.multilevel_page_tables": 2, "os.peterson_s_solution": 2,
    "os.hardware_synchronization": 2, "os.scheduling_criteria": 2, "os.multilevel_queue_scheduling": 2,
    "os.schedulers": 2, "os.swapping": 2, "os.disk_scheduling": 2, "os.file_allocation_methods": 2,
    "os.raid_levels": 2,
    "os.signals": 1, "os.bash_shell_and_cron": 1, "os.pthreads": 1, "os.linux_and_windows_scheduling": 1,
    "os.multiprocessor_scheduling": 1, "os.free_space_management": 1, "os.file_system_concepts": 1,
    "os.operating_system_functions": 1,
}


def tier(topic_id: str) -> int:
    return TIERS.get(topic_id, DEFAULT_TIER)


def apply(bank_dir: Path) -> dict[str, int]:
    """Write "interview_priority" onto every question in bank_dir/*.json, keeping
    the files' layout (1-space indent, CRLF). Returns {subject: questions updated}."""
    counts = {}
    for path in sorted(bank_dir.glob("*.json")):
        raw = path.read_bytes()
        items = json.loads(raw.decode("utf-8"))
        if not isinstance(items, list):
            continue
        for q in items:
            q["interview_priority"] = tier(q["topic_id"])
        newline = "\r\n" if b"\r\n" in raw else "\n"
        with path.open("w", encoding="utf-8", newline=newline) as f:
            f.write(json.dumps(items, ensure_ascii=False, indent=1))
        counts[path.stem] = len(items)
    return counts


if __name__ == "__main__":
    print(apply(Path(__file__).resolve().parents[1] / "question_bank"))
