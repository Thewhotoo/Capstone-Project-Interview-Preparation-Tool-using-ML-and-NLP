"""Generate model answers and identify missing concepts."""

from __future__ import annotations

from inference.predict_topic import predict_topic


# Knowledge base for different topics and concepts
CONCEPT_DEFINITIONS = {
    "OS": {
        "process": "An instance of a program in execution with its own memory space, registers, and execution context",
        "thread": "A lightweight unit of execution within a process that shares the process's memory space",
        "memory": "Computer storage used to store data and program instructions during execution",
        "cpu": "Central Processing Unit - the core component that executes program instructions",
        "interrupt": "A signal to the CPU that causes it to pause current execution and handle a high-priority event",
        "deadlock": "A situation where two or more processes are waiting for resources held by each other",
        "scheduling": "The process of allocating CPU time to different processes",
        "paging": "A memory management technique that divides memory into fixed-size pages",
        "virtual memory": "A technique that extends physical RAM using disk storage",
        "context switching": "The process of saving one process's state and loading another's",
    },
    "DSA": {
        "array": "A contiguous data structure storing elements of the same type",
        "linked list": "A data structure where elements are connected via pointers/references",
        "tree": "A hierarchical data structure with a root node and child nodes",
        "graph": "A data structure consisting of vertices and edges connecting them",
        "sorting": "Arranging elements in a specific order (ascending or descending)",
        "searching": "Finding a specific element in a data structure",
        "hash table": "A data structure that implements an associative array using a hash function",
        "stack": "A Last-In-First-Out (LIFO) data structure",
        "queue": "A First-In-First-Out (FIFO) data structure",
        "binary search tree": "A tree where left child < parent < right child",
    },
    "DBMS": {
        "database": "Organized collection of structured data stored and accessed electronically",
        "schema": "The structure describing the tables, columns, and relationships in a database",
        "transaction": "A sequence of database operations that complete as a single unit",
        "index": "A data structure that speeds up data retrieval operations",
        "query": "A request to retrieve or modify data from a database",
        "normalization": "The process of organizing data to minimize redundancy",
        "sql": "Structured Query Language for managing relational databases",
        "primary key": "A unique identifier for each record in a table",
        "foreign key": "A field that references the primary key of another table",
        "acid": "Properties ensuring reliable database transactions (Atomicity, Consistency, Isolation, Durability)",
    },
    "CN": {
        "network": "A collection of interconnected computers and devices",
        "protocol": "A set of rules for data communication",
        "packet": "A unit of data transmitted over a network",
        "routing": "The process of forwarding packets from source to destination",
        "bandwidth": "The maximum rate of data transfer in a network",
        "latency": "The delay in data transmission",
        "tcp": "Transmission Control Protocol - connection-oriented protocol",
        "udp": "User Datagram Protocol - connectionless protocol",
        "ip": "Internet Protocol - handles addressing and routing",
    },
    "OOP": {
        "class": "A blueprint for creating objects with properties and methods",
        "object": "An instance of a class",
        "inheritance": "A mechanism where a class inherits properties from another class",
        "polymorphism": "The ability to use an object in multiple ways",
        "encapsulation": "Bundling data and methods together while hiding internal details",
        "abstraction": "Showing only essential features while hiding complex implementation",
        "method": "A function associated with an object or class",
        "constructor": "A special method that initializes an object",
        "interface": "A contract defining methods that implementing classes must provide",
    },
}

# Key concepts for different topics
TOPIC_KEY_CONCEPTS = {
    "OS": ["process", "thread", "memory", "cpu", "interrupt", "scheduling", "deadlock", "paging"],
    "DSA": ["array", "linked list", "tree", "graph", "sorting", "searching", "stack", "queue"],
    "DBMS": ["database", "schema", "transaction", "index", "query", "normalization", "acid"],
    "CN": ["network", "protocol", "packet", "routing", "bandwidth", "latency", "tcp", "udp"],
    "OOP": ["class", "object", "inheritance", "polymorphism", "encapsulation", "abstraction"],
}


class AnswerGenerator:
    """Generate model answers for different question types."""
    
    def generate_model_answer(
        self,
        question_text: str,
        intent: str,
        topics: list[str],
        difficulty: str
    ) -> str:
        """Generate a model answer based on question characteristics."""
        
        # Extract key concepts from the question
        concepts = self._extract_question_concepts(question_text, topics)
        
        # Generate answer based on intent
        if intent == "definition":
            return self._generate_definition_answer(concepts, difficulty)
        elif intent == "explanation":
            return self._generate_explanation_answer(concepts, topics, difficulty)
        elif intent == "comparison":
            return self._generate_comparison_answer(concepts)
        elif intent == "procedure":
            return self._generate_procedure_answer(concepts)
        elif intent == "reasoning":
            return self._generate_reasoning_answer(concepts, topics)
        else:
            return self._generate_generic_answer(concepts, topics)
    
    def _extract_question_concepts(self, question_text: str, topics: list[str]) -> list[str]:
        """Extract key concepts from the question text."""
        question_lower = question_text.lower()
        concepts = []
        
        # Check for compound concepts first (e.g., "context switching", "linked list")
        compound_concepts = [
            "context switching", "linked list", "binary search tree", "hash table",
            "cpu scheduling", "memory management", "virtual memory", "deadlock prevention",
            "context switch", "quicksort", "mergesort", "binary search"
        ]
        
        for compound in compound_concepts:
            if compound in question_lower:
                concepts.append(compound)
        
        # For comparison questions, also look for related concepts
        if "compare" in question_lower or "vs" in question_lower or "versus" in question_lower:
            # If we found "linked list", also look for "array"
            if "linked list" in concepts and "array" not in concepts and "array" in question_lower:
                concepts.insert(0, "array")
        
        # Look for ALL concepts from CONCEPT_DEFINITIONS first
        if not concepts:
            for topic, concepts_dict in CONCEPT_DEFINITIONS.items():
                for concept in concepts_dict.keys():
                    if concept.lower() in question_lower:
                        concepts.append(concept)
                        break  # Take first match
        
        # Look for single-word keywords in the question if needed
        if len(concepts) < 1:
            for topic in topics:
                if topic in TOPIC_KEY_CONCEPTS:
                    for concept in TOPIC_KEY_CONCEPTS[topic]:
                        if concept.lower() in question_lower and concept not in concepts:
                            concepts.append(concept)
                            break
        
        # If still no matches, get main concepts for the topic
        if not concepts:
            for topic in topics:
                if topic in TOPIC_KEY_CONCEPTS:
                    concepts.extend(TOPIC_KEY_CONCEPTS[topic][:3])
        
        return concepts[:3] if concepts else ["concept"]
    
    def _generate_definition_answer(self, concepts: list[str], difficulty: str) -> str:
        """Generate a definition-type answer."""
        if not concepts:
            concepts = ["concept"]
        
        main_concept = concepts[0]
        definition = None
        
        # Search for the concept in all topics' definitions
        for topic, concepts_dict in CONCEPT_DEFINITIONS.items():
            if main_concept.lower() in concepts_dict:
                definition = concepts_dict[main_concept.lower()]
                break
        
        # If not found, use generic
        if not definition:
            definition = f"a fundamental concept in computer science"
        
        if difficulty == "easy":
            return f"{main_concept.capitalize()} is {definition}."
        elif difficulty == "medium":
            related = concepts[1:] if len(concepts) > 1 else []
            answer = f"{main_concept.capitalize()} is {definition}."
            if related:
                answer += f" It relates to {', '.join(related)}."
            return answer
        else:  # hard
            answer = f"{main_concept.capitalize()} is {definition}."
            if len(concepts) > 1:
                answer += f" It is closely associated with concepts like {', '.join(concepts[1:])}."
            return answer
    
    def _generate_explanation_answer(
        self,
        concepts: list[str],
        topics: list[str],
        difficulty: str
    ) -> str:
        """Generate an explanation-type answer."""
        main_concept = concepts[0] if concepts else "the concept"
        
        explanations = {
            "process": "A process is created when a program is executed. The OS allocates memory space (heap, stack), registers, and file descriptors. Each process has its own address space and cannot directly access another process's memory.",
            "thread": "Threads are lighter weight than processes and share the same memory space. They have independent execution stacks but can access shared data, making inter-thread communication faster but requiring synchronization.",
            "deadlock": "Deadlock occurs when circular wait conditions exist - process A waits for a resource held by process B while B waits for a resource held by A. Prevention requires breaking one of the four necessary conditions: mutual exclusion, hold and wait, no preemption, or circular wait.",
            "scheduling": "CPU scheduling decides which process gets CPU time. Algorithms include FCFS (First Come First Served), SJF (Shortest Job First), Round Robin, and Priority scheduling. Context switching is the overhead.",
            "array": "Arrays are contiguous memory blocks storing same-type elements. They offer O(1) random access but O(n) insertion/deletion. They're cache-friendly due to contiguous memory layout.",
            "sorting": "Sorting arranges elements in order. Algorithms vary: Bubble sort (O(n²)), Quick sort (O(n log n) average), Merge sort (O(n log n) guaranteed). Choice depends on data size, stability needs, and space constraints.",
        }
        
        if main_concept.lower() in explanations:
            return explanations[main_concept.lower()]
        
        # Generic explanation
        return f"{main_concept} works by {', '.join(concepts[1:])} to achieve the desired outcome. This is important in {topics[0]} because it provides efficiency and reliability."
    
    def _generate_comparison_answer(self, concepts: list[str]) -> str:
        """Generate a comparison-type answer."""
        comparisons = {
            ("array", "linked list"): "Arrays have O(1) random access and cache efficiency due to contiguity, but O(n) insertion/deletion. Linked lists have O(1) insertion/deletion at known positions but O(n) search time and poor cache locality. Use arrays for frequent access, linked lists for frequent insertions.",
            ("arrays", "linked lists"): "Arrays have O(1) random access and cache efficiency due to contiguity, but O(n) insertion/deletion. Linked lists have O(1) insertion/deletion at known positions but O(n) search time and poor cache locality. Use arrays for frequent access, linked lists for frequent insertions.",
            ("process", "thread"): "Processes have separate memory spaces and are isolated, but context switching is expensive. Threads share memory, making communication faster but requiring synchronization. Threads are lighter weight than processes.",
            ("tcp", "udp"): "TCP is connection-oriented, reliable, and ordered - good for applications needing accuracy. UDP is connectionless, fast, and unreliable - good for streaming where speed matters more than accuracy.",
        }
        
        # Normalize concepts for comparison
        concepts_lower = [c.lower() for c in concepts]
        concepts_str = ' '.join(concepts_lower)
        
        # Try to find a matching comparison
        for (c1, c2), comparison in comparisons.items():
            c1_low = c1.lower()
            c2_low = c2.lower()
            # Check if both concepts are present (allowing for partial matches)
            if (c1_low in concepts_str and c2_low in concepts_str):
                return comparison
        
        # Try single word matching for linked lists
        if "linked" in concepts_str and "array" in concepts_str:
            return comparisons[("array", "linked list")]
        
        # Generic comparison
        if len(concepts) >= 2:
            return f"{concepts[0]} and {concepts[1]} have different characteristics and use cases. {concepts[0]} is better for certain scenarios while {concepts[1]} is better for others."
        return "These concepts have distinct advantages and disadvantages depending on the use case."
    
    def _generate_procedure_answer(self, concepts: list[str]) -> str:
        """Generate a procedure-type answer."""
        procedures = {
            "context switching": "1. Save the current process's state (PC, registers, memory maps) to its PCB\n2. Select the next process to run\n3. Load the selected process's state from its PCB\n4. Resume execution of the selected process\n5. Repeat for each time slice or interrupt",
            "context_switching": "1. Save the current process's state (PC, registers, memory maps) to its PCB\n2. Select the next process to run\n3. Load the selected process's state from its PCB\n4. Resume execution of the selected process\n5. Repeat for each time slice or interrupt",
            "sorting": "1. Divide the array into smaller subarrays\n2. Sort the subarrays recursively\n3. Merge the sorted subarrays\n4. Compare and arrange elements\n5. Verify the final sorted order",
        }
        
        main_concept = concepts[0] if concepts else "process"
        
        # Check exact and underscore versions
        if main_concept.lower() in procedures:
            return procedures[main_concept.lower()]
        elif main_concept.lower().replace(" ", "_") in procedures:
            return procedures[main_concept.lower().replace(" ", "_")]
        
        return f"The process of {main_concept} involves multiple steps: (1) Initialize, (2) Execute core logic, (3) Finalize, (4) Verify result."
    
    def _generate_reasoning_answer(self, concepts: list[str], topics: list[str]) -> str:
        """Generate a reasoning-type answer."""
        reasoning = {
            "deadlock": "Deadlock must be prevented because it causes system hang. The four necessary conditions are: (1) Mutual Exclusion - resources cannot be shared, (2) Hold and Wait - processes hold resources while waiting, (3) No Preemption - resources cannot be forcibly taken, (4) Circular Wait - processes form a cycle. Break any one condition to prevent deadlock.",
            "scheduling": "Different scheduling algorithms are used because no single algorithm is optimal for all scenarios. FCFS is simple but causes convoy effect. SJF minimizes average wait but favors short jobs. Round Robin is fair but has high context switch overhead. Priority scheduling handles critical tasks but can starve low-priority processes.",
        }
        
        main_concept = concepts[0] if concepts else "concept"
        return reasoning.get(main_concept.lower(), f"The reason for {main_concept} is to ensure system efficiency, prevent resource conflicts, and provide fair access to all processes.")
    
    def _generate_generic_answer(self, concepts: list[str], topics: list[str]) -> str:
        """Generate a generic answer."""
        if not concepts:
            concepts = ["the concept"]
        return f"{concepts[0].capitalize()} is an important concept in {topics[0]}. It provides important functionality for system operation and efficiency."
    
    def get_key_points(
        self,
        intent: str,
        topics: list[str],
        difficulty: str
    ) -> list[str]:
        """Get key points that should be in an answer for this question type."""
        
        key_points = {
            "definition": [
                "Clear and concise explanation",
                "Essential characteristics",
                "Related concepts (optional for easy)",
                "Context or application area (for hard)",
            ],
            "explanation": [
                "Detailed mechanism or process",
                "How it works step-by-step",
                "Why it's important",
                "Related concepts or implications",
                "Examples or use cases (for hard)",
            ],
            "comparison": [
                "Identify similarities",
                "Identify differences",
                "Advantages of first concept",
                "Advantages of second concept",
                "When to use each (for hard)",
            ],
            "procedure": [
                "Clear step-by-step process",
                "Numbered or sequential steps",
                "Conditions and prerequisites",
                "Expected outcome",
                "Edge cases or special handling (for hard)",
            ],
            "reasoning": [
                "Logical explanation",
                "Evidence or justification",
                "Causal relationship",
                "Consideration of alternatives",
                "Impact or implications (for hard)",
            ],
        }
        
        return key_points.get(intent, [
            "Relevant information",
            "Clear explanation",
            "Context-specific details",
        ])


# Create a global instance
answer_generator = AnswerGenerator()
