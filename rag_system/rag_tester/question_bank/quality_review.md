# Question bank quality review (2026-09-30)

Every **active** question was read and scored 1–10 by hand: clear and answerable in an interview, key points correct and matching the question, sensible difficulty. Score and note are stored on each question (`quality_score`, `quality_note`).

**Asked** is how often the topic comes up in placement interviews (`interview_priority`, set in `slide_rag/interview_priority.py`): ★★★ very often, ★★ regularly, ★ rarely.

**Curated** (bold score) = score 8+, or 7+ for a ★★★ topic: **132 of 282** active questions. Only these are used by new interviews (`CAP_CURATED_ONLY`, default on; `0` serves every active question). Each bank file lists them first: most-asked topics first, then by score.

New interviews favour ★★★ topics (selector weights x6 / x1 / x0.2): 87% of questions asked come from ★★★ topics.

Scores of 4 or less mark questions that are wrong, refer to text the candidate never sees, or are too vague. Bank backup from before this review: `archive/question_bank_backup_2026-09-30/`.

## Most-asked (★★★) topics with no curated question yet: 41

Generate or fix these first:

- `cn.cidr` — 1 active, none good enough
- `cn.dhcp` — 1 active, none good enough
- `cn.dns` — no question at all
- `cn.ipv4_addressing` — 1 active, none good enough
- `cn.mac_addressing` — 1 active, none good enough
- `cn.nat` — no question at all
- `cn.osi_model` — no question at all
- `cn.packet_switching_vs_circuit_switching` — no question at all
- `cn.tcp_ip_model` — no question at all
- `dbms.boyce_codd_normal_form_bcnf` — no question at all
- `dbms.concurrency_anomalies` — no question at all
- `dbms.dbms_vs_file_system` — no question at all
- `dbms.inner_join` — 1 active, none good enough
- `dbms.self_join_and_cross_join` — no question at all
- `dbms.sql_command_categories` — no question at all
- `dbms.sql_vs_nosql` — no question at all
- `dbms.third_normal_form_3nf` — 1 active, none good enough
- `dbms.views` — no question at all
- `dsa.best_worst_and_average_case` — no question at all
- `dsa.binary_search_tree_operations` — no question at all
- `dsa.graph_representation` — no question at all
- `dsa.hash_functions` — no question at all
- `dsa.heap_sort` — 1 active, none good enough
- `dsa.open_addressing` — 1 active, none good enough
- `dsa.quick_sort` — no question at all
- `dsa.recursive_tree_traversals` — no question at all
- `dsa.simple_queue` — no question at all
- `ooad.abstraction_vs_encapsulation` — 1 active, none good enough
- `ooad.classes_and_objects` — 1 active, none good enough
- `ooad.dependency_inversion_principle` — 1 active, none good enough
- `ooad.single_responsibility_principle` — 1 active, none good enough
- `os.banker_s_algorithm` — 1 active, none good enough
- `os.critical_section_problem` — 1 active, none good enough
- `os.deadlock_vs_starvation_vs_livelock` — no question at all
- `os.fcfs_scheduling` — 1 active, none good enough
- `os.paging` — no question at all
- `os.process_vs_thread` — no question at all
- `os.race_condition` — 1 active, none good enough
- `os.round_robin_scheduling` — no question at all
- `os.sjf_and_srtf_scheduling` — no question at all
- `os.threads` — 1 active, none good enough

## Computer Networks: 18 curated of 39 active

| Score | Asked | Diff | Question | Note |
|---|---|---|---|---|
| **9** | ★★★ | medium | Explain how a Switch differs from a Hub in terms of network communication and device intelligence. `cn.network_devices.medium1` | classic, correct |
| **9** | ★★★ | medium | Explain how a device determines the MAC address of another device on the same LAN when it only knows the IP address of that device. `cn.arp.medium1` | classic, correct |
| **9** | ★★★ | easy | Explain one key difference between TCP and UDP in terms of reliability and connection setup. `cn.tcp_vs_udp.easy1` | classic |
| **9** | ★★★ | medium | Why does TCP use a three-way handshake to establish a connection, rather than a two-way handshake? `cn.tcp_connection_establishment.medium2` | classic |
| **9** | ★★★ | medium | Explain how TCP flow control prevents the sender from overwhelming the receiver's buffer. `cn.tcp_flow_control.medium1` | classic |
| **8** | ★★★ | easy | Explain how HTTPS ensures secure communication between a browser and a server. `cn.https_and_tls.easy1` | good |
| **8** | ★★★ | easy | Explain what happens during the TCP connection establishment process. `cn.tcp_connection_establishment.easy1` | good |
| **8** | ★★★ | hard | Consider a scenario where a network administrator is deciding between using a Repeater and a Switch to connect two segments of a network. What are the key differences in their operation and how might these differences affect network performance? `cn.network_devices.hard2` | good (closer to medium) |
| **8** | ★★★ | medium | How does TCP congestion control balance between underutilizing bandwidth and causing congestion collapse? `cn.tcp_congestion_control.medium2` | good |
| **9** | ★★ | medium | Explain how the sender and receiver manage retransmissions and window advancement in Selective Repeat, and why this approach is more efficient than Go-Back-N in certain scenarios. `cn.go_back_n_and_selective_repeat.medium2` | good |
| **9** | ★★ | easy | Explain how a self-learning switch builds its MAC address table. `cn.switching_and_vlans.easy1` | good |
| **9** | ★★ | medium | Explain how persistent HTTP improves the response time for downloading multiple objects compared to non-persistent HTTP. `cn.persistent_vs_non_persistent_http.medium1` | classic |
| **8** | ★★ | easy | Explain what ICMP is used for in computer networks. `cn.icmp.easy1` | good |
| **8** | ★★ | medium | How does the store-and-forward mechanism in packet switching affect the end-to-end delay in a network with multiple hops? `cn.network_delays.medium2` | good |
| **8** | ★★ | medium | Explain how IPv6 datagrams can be transmitted across a network that contains both IPv6 and IPv4 routers, and why this is important for network transition. `cn.ipv6.medium1` | good |
| **8** | ★★ | medium | Explain how random access protocols like ALOHA manage collisions and why they are different from channel partitioning protocols like TDMA. `cn.multiple_access_protocols.medium1` | good |
| **8** | ★★ | medium | How does ICMP support network diagnostics, and what are two specific examples of ICMP messages used in this role? `cn.icmp.medium2` | good |
| **8** | ★ | medium | In a network with multiple client-server pairs sharing a common middle link, how does the bottleneck link affect the end-to-end throughput for each pair? `cn.throughput_and_bottleneck_link.medium1` | good |
| 6 | ★★★ | medium | Explain how a DHCP client and server coordinate to assign an IP address to a host, and why this process is important for network management. `cn.dhcp.medium1` | key points skip the DORA exchange |
| 6 | ★★★ | medium | Explain how CIDR allows for more efficient allocation of IP addresses compared to traditional class-based addressing. `cn.cidr.medium1` | key points miss the efficiency argument |
| 6 | ★★★ | medium | How does the uniqueness of MAC addresses ensure that data is delivered correctly within a LAN? `cn.mac_addressing.medium2` | ok |
| 4 | ★★★ | medium | Explain how the default subnet mask for a Class C network is derived from its classful addressing structure. `cn.ipv4_addressing.medium2` | key points never give the mask; vague |
| 3 | ★★★ | hard | What happens if a device tries to send a packet to another device on the same LAN, but the target device’s MAC address is not in the sender’s ARP table, and the sender has no prior knowledge of the target’s IP address? `cn.arp.hard2` | garbled text; contradictory premise (no knowledge of the target IP) |
| 2 | ★★★ | medium | How do TCP and UDP differ in their handling of network congestion and throughput guarantees? `cn.tcp_vs_udp.medium2` | key point is false: TCP does NOT guarantee minimum throughput |
| 7 | ★★ | easy | Explain what FTP is and how it is used in networking. `cn.ftp.easy1` | fine |
| 7 | ★★ | medium | Explain how CRC codes ensure that burst errors are detected, and why this is important for network communication. `cn.error_detection.medium1` | formula-level detail |
| 7 | ★★ | medium | Explain why UDP is suitable for streaming multimedia applications, and how its design supports this use case. `cn.udp.medium1` | fine |
| 7 | ★★ | medium | Explain how the Bellman-Ford algorithm ensures that distance vector routing converges to the correct least-cost paths, and why it is important that nodes update their distance vectors based on their neighbors' information. `cn.distance_vector_routing.medium1` | fine |
| 6 | ★★ | easy | Explain what a socket is and how it relates to the transport layer. `cn.transport_layer_services.easy1` | ok; one key point is a slide analogy |
| 6 | ★★ | medium | Explain how Ethernet frames are used to support communication between devices on a local network, and why the frame structure is important for reliable data transmission. `cn.ethernet.medium1` | vague question |
| 6 | ★★ | easy | Explain how CSMA/CD differs from CSMA/CA in terms of handling collisions. `cn.csma_cd_and_csma_ca.easy1` | asks for a difference but key points cover only CSMA/CD |
| 6 | ★★ | easy | Explain what a link-state routing algorithm is and how it differs from other routing methods. `cn.link_state_routing.easy1` | 'centralized' is textbook-specific wording |
| 6 | ★★ | medium | Explain how TCP handles the termination of a connection when both the client and server send FIN segments at the same time. `cn.tcp_connection_termination.medium1` | niche case |
| 5 | ★★ | medium | Explain how a firewall enforces security rules at different layers of the network stack, and why this matters for network security. `cn.firewalls.medium1` | vague key points |
| 4 | ★★ | medium | How does the transport layer ensure that data sent from one process reaches the correct process on the receiving end? `cn.transport_layer_services.medium2` | misses port numbers / demultiplexing; repeats a slide analogy |
| 4 | ★★ | medium | How does a switch allow multiple simultaneous transmissions without collisions, and what role does the Ethernet protocol play in this? `cn.collision_and_broadcast_domains.medium2` | garbled characters in a key point |
| 2 | ★★ | medium | How does the human analogy for CSMA/CD differ from that of CSMA/CA, and what does this imply about their behavior in a network? `cn.csma_cd_and_csma_ca.medium2` | slide-analogy trivia |
| 7 | ★ | easy | Explain how a DSL modem connects a home network to the Internet. `cn.network_edge_and_access_networks.easy1` | fine |
| 5 | ★ | medium | Explain how the structure of access networks affects the performance of a home network. `cn.network_edge_and_access_networks.medium2` | vague question |

## DBMS: 29 curated of 61 active

| Score | Asked | Diff | Question | Note |
|---|---|---|---|---|
| **9** | ★★★ | easy | Explain what it means for a relation to be in second normal form (2NF). `dbms.second_normal_form_2nf.easy1` | classic |
| **9** | ★★★ | medium | Explain how referential integrity constraints work in SQL and why they are important for maintaining data consistency. `dbms.integrity_constraints.medium1` | classic |
| **9** | ★★★ | medium | Explain how the HAVING clause differs from the WHERE clause in terms of when they are applied and what they filter. `dbms.having_vs_where.medium1` | classic |
| **9** | ★★★ | medium | How do ranking window functions like RANK(), DENSE_RANK(), and ROW_NUMBER() differ in their behavior when there are ties in the data? `dbms.window_functions.medium2` | classic |
| **9** | ★★★ | easy | Explain the difference between a superkey and a candidate key. `dbms.super_key_and_candidate_key.easy1` | classic |
| **8** | ★★★ | easy | Explain what aggregate functions do and how they are used in SQL queries. `dbms.aggregate_functions_and_group_by.easy1` | good |
| **8** | ★★★ | medium | Explain how a Full Outer Join differs from a Left or Right Outer Join, and why it might be useful in a database query. `dbms.outer_joins.medium1` | good |
| **8** | ★★★ | medium | Explain how the ACID properties ensure that a database remains consistent even when multiple transactions are executed concurrently. `dbms.transactions_and_acid_properties.medium1` | good |
| **8** | ★★★ | medium | Explain how indexing improves the performance of SELECT operations, and why it's more efficient than a full table scan. `dbms.indexing_basics.medium1` | good |
| **8** | ★★★ | medium | Explain how First Normal Form (1NF) ensures that a relation is properly structured for relational database systems. `dbms.first_normal_form_1nf.medium1` | good |
| **8** | ★★★ | hard | How does the SERIALIZABLE isolation level address the phantom record problem compared to REPEATABLE READ? `dbms.isolation_levels.hard2` | good |
| **8** | ★★★ | medium | How do the `ON DELETE CASCADE` and `ON UPDATE CASCADE` options affect the child table when changes are made to the parent table? `dbms.foreign_key.medium2` | good |
| **7** | ★★★ | hard | Explain how the primary key of a weak entity set is determined, and what role the identifying relationship plays in this process. `dbms.primary_key.hard2` | fine |
| **9** | ★★ | easy | Explain what denormalization is and why it might be used in a database. `dbms.denormalization.easy1` | classic |
| **9** | ★★ | easy | Explain what a deadlock is in the context of database transactions. `dbms.deadlocks_in_dbms.easy1` | classic |
| **9** | ★★ | medium | How does the mapping of a many-to-many relationship differ from that of a one-to-many relationship in ER to relational mapping? `dbms.er_to_relational_mapping.medium2` | classic |
| **9** | ★★ | easy | Explain the difference between a database schema and a database instance. `dbms.schema_vs_instance.easy1` | classic |
| **8** | ★★ | easy | Explain what a stored procedure is and why it is useful in a database system. `dbms.stored_procedures_and_functions.easy1` | good |
| **8** | ★★ | easy | Explain how SQL handles comparisons involving NULL values. `dbms.null_handling_in_sql.easy1` | good |
| **8** | ★★ | medium | How does the CAP theorem influence the design trade-offs in distributed systems, particularly in the context of SQL versus NoSQL databases? `dbms.cap_theorem.medium2` | good |
| **8** | ★★ | medium | Explain how a recursive CTE works and why it is useful for hierarchical data. `dbms.common_table_expressions_cte.medium1` | good |
| **8** | ★★ | medium | How does denormalization affect the balance between query performance and data consistency in a database? `dbms.denormalization.medium2` | good |
| **8** | ★★ | medium | Explain how Armstrong’s Axioms can be used to infer new functional dependencies from a given set of dependencies. `dbms.functional_dependency.medium1` | good |
| **8** | ★★ | medium | Explain how update anomalies can occur in a database schema and why they are problematic. `dbms.update_anomalies.medium2` | good |
| **8** | ★★ | medium | Explain how cardinality ratios affect the interpretation of a relationship between two entity sets in a database design. `dbms.relationships_and_cardinality.medium1` | good |
| **8** | ★★ | easy | Explain what physical data independence means in the context of a database system. `dbms.data_independence.easy1` | good |
| **8** | ★★ | medium | Explain how correlated subqueries differ from regular nested queries in terms of execution and their impact on query results. `dbms.nested_and_correlated_subqueries.medium1` | good |
| **8** | ★ | medium | Explain how vector databases enable efficient similarity searches compared to traditional databases. `dbms.vector_databases_and_embeddings.medium1` | good |
| **8** | ★ | hard | What trade-off does the use of Approximate Nearest Neighbor (ANN) algorithms in vector databases introduce, and how does it affect the system's performance? `dbms.vector_databases_and_embeddings.hard2` | good |
| 6 | ★★★ | easy | Can you explain what an Inner Join does in SQL, based on what you've learned? `dbms.inner_join.easy1` | odd phrasing ('based on what you've learned') |
| 6 | ★★★ | medium | Explain how the definition of third normal form (3NF) addresses transitive dependencies in a relation schema. `dbms.third_normal_form_3nf.medium1` | formal; one key point is imprecise |
| 6 | ★★★ | hard | What is the significance of disallowing nested relations in the context of First Normal Form (1NF)? `dbms.first_normal_form_1nf.hard2` | not really hard |
| 3 | ★★★ | medium | Explain how the GROUP BY clause interacts with aggregate functions in SQL queries, and why it is necessary to include grouping attributes in the SELECT clause. `dbms.aggregate_functions_and_group_by.medium2` | false premise: grouping columns need not be in SELECT |
| 7 | ★★ | easy | Explain what a primary key is in the context of entity sets. `dbms.entities_and_attributes.easy1` | fine |
| 7 | ★★ | medium | Compare and contrast the use of IN, OUT, and INOUT parameters in stored procedures, and explain how each affects the flow of data between the procedure and the calling program. `dbms.stored_procedures_and_functions.medium2` | fine |
| 7 | ★★ | medium | Explain how Redis uses key-value pairs to store data efficiently, and why this approach is suitable for certain applications. `dbms.key_value_stores_and_redis.medium1` | fine |
| 7 | ★★ | medium | How does SQL treat NULL values in arithmetic operations? `dbms.null_handling_in_sql.medium2` | fine, thin |
| 7 | ★★ | medium | How does the INTERSECT operator differ from the UNION operator in SQL, and what implications does this have for the data being combined? `dbms.set_operations_in_sql.medium2` | fine |
| 7 | ★★ | easy | Explain what total participation means in the context of database relationships. `dbms.participation_constraints.easy1` | fine |
| 7 | ★★ | hard | Explain how the concept of closure of functional dependencies can be used to determine whether a set of functional dependencies is minimal. `dbms.functional_dependency.hard2` | fine |
| 7 | ★★ | hard | What is the significance of using EXISTS or NOT EXISTS with correlated subqueries, and how does it influence the evaluation of the outer query? `dbms.nested_and_correlated_subqueries.hard2` | fine |
| 7 | ★★ | medium | Explain how the lock-compatibility matrix determines whether two transactions can hold locks on the same data item simultaneously. `dbms.lock_based_concurrency_control.medium2` | fine; one key point is clumsy |
| 6 | ★★ | easy | Explain what happens when a transaction reaches the partially committed state. `dbms.transaction_states.easy1` | textbook detail |
| 6 | ★★ | medium | How does the Two-Phase Locking (2PL) protocol contribute to deadlock prevention, and what are the limitations of this approach? `dbms.deadlocks_in_dbms.medium2` | trick premise (2PL does not prevent deadlock) |
| 5 | ★★ | medium | Explain how a weak entity set is identified in an ER diagram and why it must have total participation in its identifying relationship. `dbms.weak_entity_sets.medium1` | diagram-notation trivia; the 'why' isn't in the key points |
| 5 | ★★ | medium | Explain how lossless decomposition ensures that a relation can be reconstructed without data loss after decomposition. `dbms.lossless_decomposition.medium1` | circular question; a key point is filler |
| 5 | ★★ | medium | Explain how a transaction can transition from the failed state to the terminated state, and what are the implications of each path. `dbms.transaction_states.medium2` | textbook state-diagram detail |
| 5 | ★★ | hard | Suppose we have a weak entity set that is identified by more than one strong entity set. How does this affect the primary key of the weak entity set, and what implications does this have for the design of the database schema? `dbms.weak_entity_sets.hard2` | odd scenario |
| 4 | ★★ | medium | How does the analogy between a program's variable declarations and a database's schema help in understanding the difference between schema and instance? `dbms.schema_vs_instance.medium2` | slide analogy |
| 4 | ★★ | medium | How does logical data independence benefit the University database when changes are made to the logical schema? `dbms.data_independence.medium2` | tied to the textbook's 'University' example |
| 2 | ★★ | hard | What happens if a trigger is defined as BEFORE INSERT and the same table is modified in a cascading foreign key constraint? `dbms.triggers.hard2` | key points are wrong (cascades don't insert; cascaded actions don't fire triggers in MySQL) |
| 7 | ★ | easy | Explain how an index-based nested-loop join improves upon the standard nested-loop join. `dbms.query_processing_and_join_algorithms.easy1` | fine (closer to medium) |
| 7 | ★ | easy | Explain what a natural join is in relational algebra. `dbms.relational_algebra_joins_and_division.easy1` | fine |
| 7 | ★ | medium | Explain how to determine if a functional dependency in a set is redundant and how this relates to finding the minimal cover. `dbms.minimal_cover_of_fds.medium1` | fine |
| 7 | ★ | medium | Explain how full-text search in MySQL differs from a simple string search like LIKE or REGEXP, and why full-text search is more effective for certain tasks. `dbms.full_text_search.medium1` | fine |
| 6 | ★ | easy | Explain what the REVOKE statement does in the context of database privileges. `dbms.grant_and_revoke_privileges.easy1` | fine, low value |
| 6 | ★ | easy | Explain how Neo4j represents entities and relationships in its data model. `dbms.graph_databases_and_neo4j.easy1` | ok |
| 6 | ★ | easy | Explain what it means for two sets of functional dependencies to be equivalent. `dbms.equivalence_of_sets_of_fds.easy1` | ok |
| 6 | ★ | medium | Explain how Neo4j handles the flexibility of schema in comparison to traditional relational databases. `dbms.graph_databases_and_neo4j.medium2` | ok |
| 4 | ★ | medium | Explain how the relational model represents relationships between data and how this affects the design of a database schema. `dbms.relational_model.medium1` | vague key points |
| 4 | ★ | medium | How does the REVOKE statement relate to the GRANT statement in terms of privilege management? `dbms.grant_and_revoke_privileges.medium2` | near-duplicate of the easy REVOKE question |

## Data Structures & Algorithms: 20 curated of 50 active

| Score | Asked | Diff | Question | Note |
|---|---|---|---|---|
| **9** | ★★★ | easy | Explain how merge sort works in terms of splitting and merging arrays. `dsa.merge_sort.easy1` | classic |
| **9** | ★★★ | easy | Explain how Dijkstra’s algorithm finds the shortest paths in a weighted graph. `dsa.dijkstra_s_algorithm.easy1` | classic |
| **9** | ★★★ | easy | Explain how to delete a node from a binary search tree that has two children. `dsa.binary_search_tree_deletion.easy1` | classic |
| **8** | ★★★ | easy | Explain how a stack can be implemented using a linked list. `dsa.stack_operations.easy1` | good |
| **8** | ★★★ | medium | Explain how depth-first search explores nodes and why it uses a stack-like behavior. `dsa.depth_first_search.medium1` | good |
| **8** | ★★★ | easy | Can you explain what breadth-first search does in terms of node exploration? `dsa.breadth_first_search.easy1` | good |
| **7** | ★★★ | easy | Explain what a priority queue is and how it differs between ascending and descending types. `dsa.priority_queue.easy1` | fine |
| **7** | ★★★ | easy | Explain what time complexity and space complexity mean in the context of algorithm performance. `dsa.time_and_space_complexity.easy1` | basic |
| **7** | ★★★ | medium | Explain how Ω-notation and Θ-notation differ in their use for analyzing the growth rate of functions. `dsa.asymptotic_notations.medium2` | fine |
| **7** | ★★★ | medium | Explain how binary search uses the decrease-by-a-constant-factor approach to solve a problem efficiently. `dsa.binary_search.medium1` | fine |
| **9** | ★★ | easy | Explain what a trie is and how it is used in computer science. `dsa.tries.easy1` | classic |
| **9** | ★★ | easy | Explain how Kruskal’s algorithm builds a minimum spanning tree. `dsa.kruskal_s_algorithm.easy1` | classic |
| **9** | ★★ | easy | Explain how a stack is used in the execution of recursive functions. `dsa.stacks_and_recursion.easy1` | classic |
| **9** | ★★ | easy | Explain what topological sorting is and why it is important for directed acyclic graphs. `dsa.topological_sorting.easy1` | classic |
| **8** | ★★ | easy | Explain what an expression tree is and how it represents an arithmetic expression. `dsa.expression_trees.easy1` | good |
| **8** | ★★ | easy | Explain how a circular queue solves the problem of wasted space in a simple queue. `dsa.circular_queue.easy1` | good |
| **8** | ★★ | medium | How does a trie support efficient prefix-based searches, such as in auto-complete features? `dsa.tries.medium2` | good |
| **8** | ★★ | medium | Explain how the postfix expression evaluation algorithm ensures that operators are applied to the correct operands. `dsa.postfix_expression_evaluation.medium2` | good |
| **8** | ★★ | medium | Explain how the parenthesis matching algorithm ensures that the parentheses are properly nested and matched. `dsa.parenthesis_matching.medium1` | good |
| **8** | ★★ | medium | Explain how the Master Theorem determines the time complexity of a recurrence relation based on the relationship between a, b, and d. `dsa.recurrence_relations.medium1` | good |
| 6 | ★★★ | easy | Explain what it means for a function t(n) to be in Ω(g(n)). `dsa.asymptotic_notations.easy1` | formal |
| 6 | ★★★ | medium | Explain how quadratic probing differs from linear probing in open addressing, and why one might be preferred over the other in certain scenarios. `dsa.open_addressing.medium1` | key points are only formulas; miss clustering |
| 6 | ★★★ | medium | Explain how the selection of the next vertex in Dijkstra’s algorithm depends on the structure of the graph and the current state of the algorithm. `dsa.dijkstra_s_algorithm.medium2` | odd phrasing |
| 5 | ★★★ | medium | How does the merge step in merge sort ensure that the final merged array is sorted in the worst case? `dsa.merge_sort.medium2` | a key point is inaccurate |
| 4 | ★★★ | easy | Explain how heap sort works in two stages. `dsa.heap_sort.easy1` | key points never name the two stages |
| 2 | ★★★ | hard | What is the significance of the 'extend solution of smaller instance to obtain solution to original problem' step in the context of binary search? `dsa.binary_search.hard2` | textbook-jargon trivia |
| 7 | ★★ | medium | Explain how insertion sort builds a sorted array incrementally and why it is considered a decrease and conquer algorithm. `dsa.insertion_sort.medium1` | fine |
| 7 | ★★ | hard | What happens to the sorted subarray during insertion sort and why is this property important for the algorithm’s performance? `dsa.insertion_sort.hard2` | fine (not really hard) |
| 7 | ★★ | medium | Explain how the construction of an expression tree using a postfix notation ensures that the resulting tree can be evaluated correctly. `dsa.expression_trees.medium2` | fine |
| 6 | ★★ | medium | How does the order of function completion in nested function calls relate to the structure of the stack? `dsa.stacks_and_recursion.medium2` | overlaps the easy stack/recursion question |
| 6 | ★★ | hard | Explain how selection sort ensures that elements are placed in their final positions during each pass, and what this implies about the algorithm's behavior. `dsa.brute_force_sorting.hard2` | not really hard; a key point restates the question |
| 6 | ★★ | medium | Explain how the bottom-up heap construction algorithm ensures that the final array represents a valid max-heap. `dsa.heap_construction.medium1` | a key point is circular |
| 6 | ★★ | medium | Explain how the delete operations in a double-ended queue differ between array and doubly linked list implementations. `dsa.double_ended_queue.medium1` | ok |
| 5 | ★★ | easy | Can you explain what a leaf node is in a binary tree and how it differs from a non-leaf node? `dsa.tree_terminology.easy1` | trivial; filler key point |
| 5 | ★★ | medium | Explain how the union and find operations maintain disjoint subsets in the union-find data structure, and why the structure is useful for tracking elements in multiple sets. `dsa.disjoint_sets_and_union_find.medium1` | premise contradicts 'disjoint'; circular key point |
| 5 | ★★ | medium | Explain how the structure of a circular queue allows it to avoid the issue of space being locked in the front of the queue. `dsa.circular_queue.medium2` | duplicate of the easy circular-queue question |
| 5 | ★★ | medium | How does the DFS-based algorithm for topological sorting ensure that the resulting order is valid for a directed acyclic graph? `dsa.topological_sorting.medium2` | key points miss the reverse-finish-order idea |
| 5 | ★★ | medium | Explain how the relationship between leaf nodes and degree-2 nodes in a binary tree helps us understand the structure of a full binary tree. `dsa.binary_tree_properties.medium1` | 'full = all leaves on one level' is definition-dependent |
| 3 | ★★ | easy | Explain how Distribution Counting Sorting works based on the information provided. `dsa.sorting_by_counting.easy1` | 'based on the information provided' refers to text the candidate never sees |
| 2 | ★★ | easy | Explain how the iterative preorder traversal works using the code provided. `dsa.iterative_tree_traversals.easy1` | refers to 'the code provided', which the candidate never sees |
| 2 | ★★ | medium | Explain how the iterative postorder traversal handles the order of processing nodes using the code provided. `dsa.iterative_tree_traversals.medium2` | refers to 'the code provided', which the candidate never sees |
| 1 | ★★ | hard | Consider a complete binary tree. How does the structure of the tree ensure that the number of nodes at the last level is always odd, and what does this imply about the relationship between the depth and the number of nodes? `dsa.binary_tree_properties.hard2` | false premise: last level of a complete binary tree is not always odd |
| 7 | ★ | easy | Explain what exhaustive search means in the context of solving problems like the Traveling Salesman Problem or the Knapsack Problem. `dsa.exhaustive_search.easy1` | fine |
| 7 | ★ | easy | Explain how to convert an n-ary tree into a binary tree using the left-child-right-sibling representation. `dsa.n_ary_tree_to_binary_tree_conversion.easy1` | fine |
| 7 | ★ | medium | Explain how a suffix tree differs from a suffix trie and why this compression is useful for string operations. `dsa.suffix_tries_and_suffix_trees.medium1` | fine |
| 6 | ★ | medium | Explain how the Boyer-Moore algorithm uses the concept of bad-symbol shift to improve string matching efficiency compared to Horspool’s algorithm. `dsa.horspool_and_boyer_moore_string_matching.medium1` | niche |
| 6 | ★ | easy | Explain how a skip list maintains the order of elements across different levels. `dsa.skip_lists.easy1` | ok |
| 5 | ★ | medium | Explain how the directionality of edges affects the classification of a graph as directed or undirected, and how this relates to the concept of weighted graphs. `dsa.graph_terminology.medium1` | convoluted question |
| 4 | ★ | medium | How does the conversion of a forest to a binary tree differ from converting a single n-ary tree to a binary tree, and what implications does this have on the structure of the resulting binary tree? `dsa.n_ary_tree_to_binary_tree_conversion.medium2` | textbook-specific detail |
| 2 | ★ | hard | What happens to the graph's connectivity if we remove all edges that are part of any path from a source to a destination in a connected graph? `dsa.graph_connectivity_and_path_finding.hard2` | muddled question and key points |

## OOAD: 36 curated of 64 active

| Score | Asked | Diff | Question | Note |
|---|---|---|---|---|
| **9** | ★★★ | easy | Can you explain what a constructor is and why it's important in object-oriented programming? `ooad.constructors.easy1` | classic |
| **9** | ★★★ | easy | Explain the Open-Closed Principle in your own words. `ooad.open_closed_principle.easy1` | classic |
| **9** | ★★★ | easy | Explain the Interface Segregation Principle (ISP) in your own words. `ooad.interface_segregation_principle.easy1` | classic |
| **9** | ★★★ | easy | Explain how the Singleton pattern ensures that only one instance of a class is created in Java. `ooad.singleton_pattern.easy1` | classic |
| **9** | ★★★ | easy | Can you explain what method overriding is and why it's useful in object-oriented programming? `ooad.method_overriding.easy1` | classic |
| **9** | ★★★ | medium | Explain the difference between an abstract class and an interface in terms of their use for abstraction and inheritance. `ooad.abstract_class_vs_interface.medium1` | classic |
| **9** | ★★★ | medium | Explain how the `equals()` method in the `Object` class behaves by default, and why it's important to override it in subclasses. `ooad.java_object_class.medium1` | classic |
| **9** | ★★★ | medium | Explain the difference between method overloading and method overriding, and why they are used in different scenarios. `ooad.overloading_vs_overriding.medium1` | classic |
| **9** | ★★★ | easy | What is the difference between an 'is-a' relationship and a 'has-a' relationship in object-oriented design? `ooad.is_a_vs_has_a_relationship.easy1` | classic |
| **9** | ★★★ | hard | What happens if two overloaded methods differ only in their return types, and how does this affect the compiler's ability to resolve the correct method call? `ooad.method_overloading.hard2` | classic |
| **8** | ★★★ | easy | Explain what an interface is in Java, and how it supports abstraction. `ooad.interfaces.easy1` | good |
| **8** | ★★★ | easy | Explain what a static block is and when it is executed in Java. `ooad.static_members.easy1` | good |
| **8** | ★★★ | medium | Explain how encapsulation supports data hiding and why it is important for software design. `ooad.encapsulation.medium1` | good |
| **8** | ★★★ | medium | Explain how method overloading allows a class to have multiple methods with the same name but different behaviors, and why this is considered compile-time polymorphism. `ooad.method_overloading.medium1` | good |
| **8** | ★★★ | medium | How does the use of a parameterized constructor differ from a default constructor in Java, and what are the implications for object initialization? `ooad.constructors.medium2` | good |
| **8** | ★★★ | medium | Explain how composition differs from inheritance in terms of how they model relationships between objects, and why composition is often preferred in object-oriented design. `ooad.composition_over_inheritance.medium1` | good |
| **8** | ★★★ | medium | Compare the thread safety and performance characteristics of the eager instantiation and double-checked locking approaches for implementing the Singleton pattern in Java. `ooad.singleton_pattern.medium2` | good |
| **8** | ★★★ | medium | How does method overriding support runtime polymorphism, and what constraints must be met for this to occur? `ooad.method_overriding.medium2` | good |
| **8** | ★★★ | medium | Explain how inheritance supports code reusability and what kind of relationship it represents in object-oriented design. `ooad.inheritance.medium2` | good |
| **8** | ★★★ | medium | Explain how polymorphism allows objects of different classes to be treated as objects of a common superclass, and why this is important for software design. `ooad.polymorphism.medium2` | good |
| **8** | ★★★ | hard | Consider a scenario where a base class has a method with a specific parameter type, and a derived class has a method with the same name but a different parameter type. What is the implication of this scenario, and how does it relate to the concepts of overloading and overriding? `ooad.overloading_vs_overriding.hard2` | good |
| **7** | ★★★ | medium | How does the Open-Closed Principle help in minimizing the risk of failure when adding new features to existing code? `ooad.open_closed_principle.medium2` | fine; overlaps the easy OCP question |
| **7** | ★★★ | hard | Consider a scenario where a class inherits from two parent classes, one of which also inherits from another class. How does this scenario relate to the concept of inheritance types, and what limitations does Java impose on such a structure? `ooad.types_of_inheritance.hard2` | fine |
| **7** | ★★★ | hard | Consider a scenario where a subclass overrides a method from its superclass. What is the potential violation of the Liskov Substitution Principle, and how does this relate to the behavior of programs that depend on the superclass? `ooad.liskov_substitution_principle.hard2` | fine |
| **7** | ★★★ | medium | Explain how the Factory Method pattern improves flexibility in object creation, and why it is considered a better approach than direct constructor calls. `ooad.factory_pattern.medium1` | fine |
| **7** | ★★★ | medium | Explain how abstraction in object-oriented programming helps in managing complexity in software design. `ooad.abstraction.medium1` | fine |
| **9** | ★★ | easy | Explain what high cohesion means and why it is important in software design. `ooad.coupling_and_cohesion.easy1` | classic |
| **9** | ★★ | easy | Explain what makes the List interface in Java different from other collection interfaces like Set. `ooad.java_collections_and_list_interface.easy1` | classic |
| **9** | ★★ | medium | In Java, what is the difference between how primitive types and objects are passed as parameters, and what are the implications of this behavior? `ooad.parameter_passing_in_java.medium1` | classic |
| **8** | ★★ | easy | Explain what the Builder pattern is, and why it is useful in object-oriented design. `ooad.builder_pattern.easy1` | good |
| **8** | ★★ | easy | Explain what the Proxy Design Pattern is and one of its main purposes. `ooad.facade_and_proxy_patterns.easy1` | good |
| **8** | ★★ | medium | Explain how the 'super' keyword is used in constructors and why it must be the first statement in a constructor. `ooad.this_and_super_keywords.medium1` | good |
| **8** | ★★ | medium | How does the Command pattern enable decoupling between the invoker and the receiver, and what role does the command object play in this? `ooad.command_pattern.medium2` | good |
| **8** | ★★ | medium | Explain how the Chain of Responsibility pattern allows for dynamic decision-making in handling requests, and why this is important for loose coupling. `ooad.chain_of_responsibility_pattern.medium1` | good |
| **8** | ★★ | medium | Explain how the Adapter pattern enables incompatible classes to work together, and why it is considered a structural design pattern. `ooad.adapter_pattern.medium1` | good |
| **8** | ★ | medium | Explain how the Information Expert principle helps in assigning responsibilities to objects in object-oriented design. `ooad.information_expert.medium1` | good |
| 6 | ★★★ | medium | Explain how hybrid inheritance combines different types of inheritance and why Java uses interfaces to support it. `ooad.types_of_inheritance.medium1` | ok |
| 6 | ★★★ | medium | How does the Interface Segregation Principle help avoid unnecessary dependencies in client implementations? `ooad.interface_segregation_principle.medium2` | overlaps the easy ISP question |
| 5 | ★★★ | medium | How do interfaces in Java support multiple inheritance, and what is the difference between a provided interface and a required interface? `ooad.interfaces.medium2` | provided/required interface is UML-component trivia |
| 5 | ★★★ | easy | What is the difference between abstraction and encapsulation in object-oriented programming? `ooad.abstraction_vs_encapsulation.easy1` | key points cover only encapsulation |
| 5 | ★★★ | hard | How does the concept of a class as a blueprint influence the creation and behavior of objects in Java, and what role does the Object class play in this context? `ooad.classes_and_objects.hard2` | vague |
| 4 | ★★★ | medium | Explain how the Dependency Inversion Principle helps reduce coupling between high-level and low-level modules in the given example. `ooad.dependency_inversion_principle.medium1` | refers to 'the given example' |
| 4 | ★★★ | medium | How does the 'has-a' relationship affect the lifecycle of objects in a system? `ooad.is_a_vs_has_a_relationship.medium2` | vague |
| 3 | ★★★ | medium | Explain how the Single Responsibility Principle improves software design, using the example of the Order class and its responsibilities. `ooad.single_responsibility_principle.medium1` | refers to an 'Order class' example the candidate never sees |
| 2 | ★★★ | medium | Explain how the Liskov Substitution Principle applies to the `DeliveryService` interface and its implementations in the example provided. `ooad.liskov_substitution_principle.medium1` | refers to a 'DeliveryService' example the candidate never sees |
| 7 | ★★ | easy | Explain what an association is in object-oriented modeling, and how it differs between unidirectional and bidirectional associations. `ooad.association.easy1` | fine |
| 7 | ★★ | medium | How does the Proxy Design Pattern support the Open/Closed Principle, and what trade-off does it introduce in terms of system complexity? `ooad.facade_and_proxy_patterns.medium2` | fine |
| 7 | ★★ | medium | How does the Java garbage collector determine which objects are no longer needed, and what role does the `finalize()` method play in this process? `ooad.destructors_and_garbage_collection.medium2` | fine |
| 7 | ★★ | hard | What are the implications of grouping design patterns into the three categories—creational, structural, and behavioral—and how does this grouping affect the way we think about object-oriented design? `ooad.design_pattern_categories.hard2` | fine |
| 7 | ★★ | hard | What are the implications of an abstract class being unable to be instantiated, and how does this affect its role in an inheritance hierarchy? `ooad.abstract_classes.hard2` | fine |
| 7 | ★★ | medium | Explain how a copy constructor prevents unwanted reference sharing and why it's important in object-oriented design. `ooad.copy_constructor.medium1` | fine |
| 7 | ★★ | medium | How does the Model-View-Controller pattern help in separating the user interface from the application logic, and what are the implications of this separation? `ooad.model_view_controller.medium2` | fine |
| 6 | ★★ | easy | Can you explain what the Command pattern is and how it works, based on what you've learned? `ooad.command_pattern.easy1` | odd phrasing; 'data-driven' key point |
| 6 | ★★ | medium | How can an association be used to model a relationship where one class has multiple instances of another class, and what role does multiplicity play in this? `ooad.association.medium2` | ok |
| 6 | ★★ | medium | Explain how the Builder pattern allows a class to delegate object creation to a builder, and why this is useful for creating different representations of a complex object. `ooad.builder_pattern.medium2` | key points restate the question |
| 7 | ★ | medium | Explain how the Controller pattern in GRASP helps reduce coupling between GUI components and system operation classes. `ooad.controller_grasp.medium1` | fine |
| 6 | ★ | easy | Explain what pure fabrication is and when it is used. `ooad.indirection_and_pure_fabrication.easy1` | ok |
| 6 | ★ | medium | How does pure fabrication help in achieving low coupling and high cohesion in object-oriented design, and what role does indirection play in this? `ooad.indirection_and_pure_fabrication.medium2` | ok |
| 5 | ★ | easy | Explain the Creator pattern in GRASP and why it is important for object design. `ooad.creator_grasp.easy1` | a key point misstates Creator |
| 5 | ★ | medium | Explain how Vendor Lock-In is an AntiPattern in software architecture, and why it affects both development and management. `ooad.anti_patterns.medium2` | key points are one textbook's specific wording |
| 4 | ★ | easy | Explain what low-level design approach is in object-oriented analysis and design. `ooad.low_level_design_approach.easy1` | vague |
| 4 | ★ | medium | In the context of the Creator pattern, how does the responsibility of object creation relate to the interactions between objects in a system? `ooad.creator_grasp.medium2` | vague |
| 3 | ★ | easy | Explain what it means for an object to have its own memory in Java. `ooad.object_memory_allocation.easy1` | vague question and key points |
| 3 | ★ | medium | How does the low-level design approach ensure that the system remains flexible and extensible, and what role does the analysis model play in this process? `ooad.low_level_design_approach.medium2` | vague |

## Operating Systems: 29 curated of 68 active

| Score | Asked | Diff | Question | Note |
|---|---|---|---|---|
| **9** | ★★★ | medium | Explain how preemptive scheduling differs from non-preemptive scheduling in terms of when scheduling decisions occur and the implications for system behavior. `os.preemptive_vs_non_preemptive_scheduling.medium1` | classic |
| **9** | ★★★ | medium | Explain how priority scheduling can lead to starvation and what is a common solution to this problem. `os.priority_scheduling.medium1` | classic |
| **8** | ★★★ | easy | Explain what segmentation is and how it differs from paging. `os.segmentation.easy1` | good |
| **8** | ★★★ | easy | Explain how demand paging reduces the amount of memory needed for a process. `os.virtual_memory_and_demand_paging.easy1` | good |
| **8** | ★★★ | easy | Explain what a mutex lock is and how it helps solve the critical section problem. `os.mutex_locks.easy1` | good |
| **8** | ★★★ | medium | Explain how context switching affects the performance of a process in a round-robin scheduling system, and why the choice of time quantum is important. `os.context_switching.medium1` | good |
| **8** | ★★★ | medium | Explain how external fragmentation affects memory allocation and why compaction is a solution, but has limitations. `os.fragmentation.medium2` | good |
| **8** | ★★★ | easy | Explain how the FIFO page replacement algorithm works in the context of page faults and memory frames. `os.fifo_page_replacement.easy1` | good |
| **8** | ★★★ | easy | Explain what the producer-consumer problem is, and why it is important in operating systems. `os.producer_consumer_problem.easy1` | good |
| **8** | ★★★ | hard | Explain how the implementation of semaphores without busy waiting can lead to priority inversion, and why the use of the priority-inheritance protocol is necessary. `os.semaphores.hard2` | good |
| **8** | ★★★ | medium | Explain how the Optimal and LRU page replacement algorithms differ in their approach to page replacement, and why one might be considered better than the other in certain scenarios. `os.optimal_and_lru_page_replacement.medium1` | good |
| **7** | ★★★ | medium | How does the concept of a safe state influence the decision-making process when a process requests a resource in a deadlock avoidance system? `os.deadlock_avoidance.medium2` | fine |
| **7** | ★★★ | medium | How does the working-set model help in mitigating the effects of thrashing, and what are the limitations of its approximation using reference bits and interval timers? `os.thrashing.medium2` | fine |
| **7** | ★★★ | hard | Consider a scenario where a system allows preemption of resources. How does this affect the possibility of deadlock, and what condition is no longer a necessary requirement for deadlock to occur? `os.deadlock_conditions.hard2` | fine |
| **9** | ★★ | easy | Explain the difference between a logical address and a physical address. `os.logical_vs_physical_address.easy1` | classic |
| **9** | ★★ | medium | Explain how contiguous memory allocation strategies like first-fit, best-fit, and worst-fit impact memory fragmentation and efficiency, and why some are preferred over others. `os.contiguous_memory_allocation.medium1` | classic |
| **9** | ★★ | medium | Explain how user mode and kernel mode help protect the operating system from user programs. `os.user_mode_vs_kernel_mode.medium1` | classic |
| **9** | ★★ | easy | Explain what a Translation Look-aside Buffer (TLB) is and why it is used. `os.translation_lookaside_buffer.easy1` | classic |
| **8** | ★★ | medium | Explain how the operating system handles a page fault and how it manages the page-fault frequency to avoid thrashing. `os.page_faults.medium1` | good |
| **8** | ★★ | medium | How does the many-to-one model of user-level threads affect concurrency and parallelism in a multi-core system? `os.user_level_vs_kernel_level_threads.medium2` | good |
| **8** | ★★ | medium | Explain how hierarchical page tables reduce memory usage compared to a flat page table, and what trade-offs they introduce. `os.multilevel_page_tables.medium1` | good |
| **8** | ★★ | easy | Explain how Peterson’s solution ensures mutual exclusion between two processes. `os.peterson_s_solution.easy1` | good |
| **8** | ★★ | easy | Explain how a wait-for graph is used to detect deadlocks in a system. `os.deadlock_detection_and_recovery.easy1` | good |
| **8** | ★★ | hard | What is the primary challenge in implementing shared memory with inverted page tables, and how does the structure of the inverted page table contribute to this challenge? `os.multilevel_page_tables.hard2` | good |
| **8** | ★★ | hard | What happens if a user program attempts to execute a privileged instruction, and why is this behavior intentional? `os.user_mode_vs_kernel_mode.hard2` | good |
| **8** | ★★ | hard | Explain how the test_and_set instruction ensures mutual exclusion in a multi-process environment, and what happens if two processes attempt to acquire the lock simultaneously. `os.hardware_synchronization.hard2` | good |
| **8** | ★★ | medium | Explain how the 'circular wait' condition can be prevented in a system with multiple processes and shared resources. `os.deadlock_prevention.medium1` | good |
| **8** | ★★ | medium | Explain how message passing differs from shared memory in terms of how processes communicate and synchronize. `os.inter_process_communication.medium1` | good |
| **8** | ★ | easy | Explain what a signal is in the context of Linux processes. `os.signals.easy1` | good |
| 6 | ★★★ | medium | Explain how the four deadlock conditions are interdependent in the occurrence of a deadlock. `os.deadlock_conditions.medium1` | a key point is dubious |
| 6 | ★★★ | medium | Explain how a race condition can occur in the context of the `fork` system call and why it's important to use wait functions properly. `os.race_condition.medium2` | ok |
| 6 | ★★★ | medium | Explain how threads improve the scalability of a system, and why this is important for modern applications. `os.threads.medium1` | ok |
| 6 | ★★★ | medium | Explain how the incorrect use of semaphore operations can lead to deadlock and starvation, and why the implementation of semaphores with busy waiting is problematic. `os.semaphores.medium1` | ok |
| 6 | ★★★ | medium | Explain how segmentation handles logical addresses and what happens when an offset is invalid. `os.segmentation.medium2` | key points skip the invalid-offset trap |
| 6 | ★★★ | medium | Explain how the Banker’s algorithm ensures that a system remains in a safe state when allocating resources to processes. `os.banker_s_algorithm.medium1` | key points are implementation variables |
| 5 | ★★★ | medium | Why are spinlocks considered problematic in real-time systems, and how does this relate to the use of busy waiting? `os.mutex_locks.medium2` | a key point is dubious |
| 5 | ★★★ | hard | How does the size of a process affect the time required for a context switch, and what mechanisms can mitigate this impact? `os.context_switching.hard2` | conflates context switch with swapping |
| 4 | ★★★ | easy | Explain what a safe state is in the context of deadlock avoidance. `os.deadlock_avoidance.easy1` | key points are circular; miss the safe-sequence definition |
| 3 | ★★★ | medium | Explain how the progress condition ensures fairness in the critical section problem, and why it's important to assume that processes execute at a nonzero speed. `os.critical_section_problem.medium1` | key point confuses progress with bounded waiting |
| 2 | ★★★ | medium | Explain how the order of process arrival affects the average waiting time in FCFS scheduling, using the example provided. `os.fcfs_scheduling.medium2` | refers to 'the example provided', which the candidate never sees |
| 7 | ★★ | easy | Explain what the short-term scheduler does in an operating system. `os.schedulers.easy1` | fine |
| 7 | ★★ | easy | Explain the difference between user-level and kernel-level threads based on how they are scheduled. `os.user_level_vs_kernel_level_threads.easy1` | fine |
| 7 | ★★ | easy | Explain what contiguous allocation is and why it is considered simple. `os.file_allocation_methods.easy1` | fine |
| 7 | ★★ | easy | Explain the core idea of the Dining Philosophers problem. `os.dining_philosophers_problem.easy1` | fine |
| 7 | ★★ | medium | How does the resource allocation graph algorithm detect deadlocks in a system with a single instance of each resource type? `os.resource_allocation_graph.medium2` | fine |
| 7 | ★★ | medium | How does the use of an ASID in a TLB improve system performance, and what trade-offs are involved in its implementation? `os.translation_lookaside_buffer.medium2` | fine |
| 7 | ★★ | medium | Explain how the multilevel feedback queue scheduling mechanism ensures that higher-priority processes are executed before lower-priority ones, and how this affects process preemption. `os.multilevel_queue_scheduling.medium2` | fine |
| 7 | ★★ | medium | How do system calls enable communication between user programs and the operating system, and what role do they play in file manipulation? `os.system_calls.medium2` | fine |
| 7 | ★★ | medium | Explain how the asymmetric solution to the Dining Philosophers problem prevents deadlock. `os.dining_philosophers_problem.medium2` | fine |
| 6 | ★★ | medium | How does the address-binding scheme affect the relationship between logical and physical addresses during program execution? `os.logical_vs_physical_address.medium2` | ok |
| 6 | ★★ | hard | What is the role of page-fault frequency in managing memory allocation, and how does it affect the behavior of a process when the system is under memory pressure? `os.page_faults.hard2` | a key point is oddly worded |
| 6 | ★★ | medium | Explain how minimizing waiting time and maximizing throughput are related in the context of scheduling criteria. `os.scheduling_criteria.medium2` | ok |
| 5 | ★★ | medium | Explain how the turn variable in Peterson’s solution contributes to the progress of the algorithm. `os.peterson_s_solution.medium2` | narrow |
| 5 | ★★ | medium | Explain how swapping supports priority-based scheduling and why it's important for memory management. `os.swapping.medium1` | odd key point |
| 5 | ★★ | medium | What happens to the wait-for graph when a resource is allocated to a process, and how does this affect the possibility of detecting a deadlock? `os.deadlock_detection_and_recovery.medium2` | odd premise |
| 4 | ★★ | easy | Explain how the `popen()` function handles process creation and termination. `os.process_creation_and_termination.easy1` | niche library call |
| 4 | ★★ | easy | Explain what makes disk scheduling an important part of an operating system. `os.disk_scheduling.easy1` | vague |
| 3 | ★★ | hard | What happens to a process if it is preempted for a resource, and how does this relate to deadlock prevention? `os.deadlock_prevention.hard2` | key point is wrong: preemption breaks 'no preemption', not 'hold and wait' |
| 7 | ★ | easy | Explain how the Completely Fair Scheduler (CFS) in Linux determines which task to run next. `os.linux_and_windows_scheduling.easy1` | good but not easy |
| 7 | ★ | medium | How do SIGINT and SIGALRM differ in their use and behavior when delivered to a process? `os.signals.medium2` | fine |
| 7 | ★ | medium | Explain how symmetric multiprocessing differs from asymmetric multiprocessing in terms of scheduling and system complexity. `os.multiprocessor_scheduling.medium1` | fine |
| 7 | ★ | hard | What are the limitations of using a bit vector for free-space management, and how do these limitations affect the design of disk allocation strategies in operating systems? `os.free_space_management.hard2` | fine |
| 6 | ★ | medium | Explain how cron jobs are scheduled and executed in a Unix-like system, and why it's important to understand the crontab format. `os.bash_shell_and_cron.medium1` | ok |
| 6 | ★ | medium | Explain how the file system maps logical file names to physical storage locations on a disk, and why this mapping is important for efficient data access. `os.file_system_concepts.medium1` | ok |
| 6 | ★ | hard | What is the role of the file control block (FCB) in a file system, and how does it contribute to the system's ability to manage files efficiently? `os.file_system_concepts.hard2` | ok |
| 6 | ★ | medium | Explain how free-space management in an operating system helps in reusing disk space efficiently. `os.free_space_management.medium1` | ok |
| 5 | ★ | medium | Explain how the Pthreads API supports both user-level and kernel-level implementations of thread libraries, and why this distinction matters for thread scheduling. `os.pthreads.medium1` | standards trivia |
| 4 | ★ | medium | Explain how the operating system ensures efficient resource allocation and protection in a multiuser environment. `os.operating_system_functions.medium2` | vague |
