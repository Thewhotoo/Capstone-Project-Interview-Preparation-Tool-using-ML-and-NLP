"""Expand common CS abbreviations before grading.

The NLI model does not know that "DFS" is "depth-first search", so a key point
written "DFS explores ..." was not entailed by an answer saying "depth-first
search explores ..." (0.34), and vice versa. Students write abbreviations
constantly ("dfs", "bst", "3nf", "lru"). Both the answer and the key points are
expanded the same way before the models see them, so either spelling matches.

Terms are scoped by subject, because some abbreviations mean different things
in different subjects (ISP: interface segregation principle in OOAD, internet
service provider in networks). Whole words only, case-insensitive. Fillers are
stripped before expansion, so "er" (a filler) never becomes "entity-relationship".
Adding a term: one line in TERMS.
"""
from __future__ import annotations

import re

TERMS: dict[str, dict[str, str]] = {
    "dsa": {
        "DFS": "depth-first search", "BFS": "breadth-first search", "BST": "binary search tree",
        "MST": "minimum spanning tree", "DP": "dynamic programming", "DAG": "directed acyclic graph",
        "ADT": "abstract data type", "LIFO": "last-in first-out", "FIFO": "first-in first-out",
    },
    "os": {
        "FCFS": "first-come first-served", "SJF": "shortest job first", "SRTF": "shortest remaining time first",
        "RR": "round robin", "LRU": "least recently used", "FIFO": "first-in first-out",
        "TLB": "translation lookaside buffer", "PCB": "process control block", "IPC": "inter-process communication",
        "PFF": "page-fault frequency", "RAG": "resource-allocation graph",
    },
    "dbms": {
        "1NF": "first normal form", "2NF": "second normal form", "3NF": "third normal form",
        "BCNF": "Boyce-Codd normal form", "FDs": "functional dependencies", "FD": "functional dependency",
        "PK": "primary key", "FK": "foreign key", "2PL": "two-phase locking", "ER": "entity-relationship",
    },
    "cn": {
        "NIC": "network interface card", "TTL": "time to live", "rwnd": "receive window",
        "cwnd": "congestion window", "RTT": "round-trip time", "LAN": "local area network",
    },
    "ooad": {
        "OOP": "object-oriented programming", "SRP": "single responsibility principle",
        "OCP": "open-closed principle", "LSP": "Liskov substitution principle",
        "ISP": "interface segregation principle", "DIP": "dependency inversion principle",
        "MVC": "model-view-controller",
    },
}
_PATTERNS = {subject: [(re.compile(rf"(?<![\w-]){re.escape(k)}(?![\w-])", re.I), v) for k, v in terms.items()]
             for subject, terms in TERMS.items()}


def expand_terms(text: str, subject: str) -> str:
    """Replace the subject's known abbreviations with their full names (whole words only)."""
    for pattern, full in _PATTERNS.get(subject, ()):
        text = pattern.sub(full, text)
    return text
