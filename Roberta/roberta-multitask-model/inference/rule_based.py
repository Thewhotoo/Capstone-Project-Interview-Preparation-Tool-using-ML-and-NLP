from __future__ import annotations


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def get_intent(question: str) -> str:
    q = _normalize(question)

    if q.startswith("what is") or q.startswith("define"):
        return "definition"
    if q.startswith("how would") or q.startswith("how to"):
        return "procedure"
    if q.startswith("why"):
        return "reasoning"
    if q.startswith("explain") or "how does" in q:
        return "explanation"
    if "compare" in q or "difference" in q:
        return "comparison"

    return "explanation"


def get_topic_labels(question: str) -> list[str]:
    q = _normalize(question)
    topics: list[str] = []

    if _contains_any(q, ("deadlock", "process", "thread", "semaphore", "scheduler", "paging", "kernel", "os", "operating system", "context switch", "context switching", "starvation", "critical section", "mutex", "virtual memory", "page fault", "interrupt")):
        topics.append("OS")
    if _contains_any(q, ("database", "normalization", "sql", "acid", "schema", "transaction", "transactions", "dbms", "query", "foreign key", "primary key", "index", "indexing", "join", "view", "stored procedure", "b+ tree", "b-tree", "oltp", "olap", "nosql", "relational", "mvcc")):
        topics.append("DBMS")
    if _contains_any(q, ("tcp", "udp", "network", "networking", "cn", "computer network", "ip", "dns", "http", "https", "router", "subnet", "osi", "handshake", "gateway", "firewall", "mac address", "port", "dhcp", "routing", "bandwidth", "latency")):
        topics.append("CN")
    if _contains_any(q, ("class", "object", "oop", "object oriented", "polymorphism", "polymor", "inheritance", "encapsulation", "abstraction", "interface", "constructor", "method", "overloading", "overriding", "solid", "design pattern", "singleton", "garbage collection", "jvm", "abstract class")):
        topics.append("OOP")
    if _contains_any(q, (
        "dsa",
        "data structure",
        "array",
        "linked list",
        "search",
        "sort",
        "sorting",
        "algorithm",
        "hash",
        "hashing",
        "hash map",
        "hashmap",
        "hash table",
        "tree",
        "graph",
        "queue",
        "stack",
        "traversal",
        "binary",
        "dynamic programming",
        "dp",
        "greedy",
        "backtracking",
        "recursion",
        "memoization",
        "trie",
        "heap",
        "priority queue",
        "bfs",
        "dfs",
        "dijkstra",
        "complexity",
        "time complexity",
        "space complexity",
        "big o",
        "amortized",
        "sliding window",
        "two pointer",
        "divide and conquer",
    )):
        topics.append("DSA")

    if not topics:
        return ["General"]
    return topics


def get_difficulty(question: str) -> str:
    q = _normalize(question)

    if q.startswith("what is") or q.startswith("define") or q.startswith("what are"):
        return "easy"

    # Hard implementation verbs — always hard regardless of prefix.
    HARD_ACTION_VERBS = ("implement", "design", "build", "create", "optimize", "architect", "derive", "prove")
    if _contains_any(q, HARD_ACTION_VERBS):
        return "hard"

    # "how would/how to" without implementation verbs = asking for an approach → medium.
    # "why" = asking for reasoning/justification → medium.
    if q.startswith("how would") or q.startswith("how to") or q.startswith("why"):
        return "medium"

    if "compare" in q or q.startswith("explain") or "difference" in q:
        return "medium"

    if _contains_any(q, ("architecture", "distributed")):
        return "hard"

    return "medium"
