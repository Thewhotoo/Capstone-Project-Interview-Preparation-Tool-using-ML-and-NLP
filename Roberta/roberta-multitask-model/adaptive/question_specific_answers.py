"""Generate question-specific model answers, not generic definitions."""

from __future__ import annotations


class QuestionSpecificAnswerGenerator:
    """Generate answers tailored to the specific question asked."""
    
    # Question-specific answers based on exact question patterns
    SPECIFIC_ANSWERS = {
        # OS Generic Questions
        "What is OS?": "An Operating System (OS) is system software that manages hardware resources and provides services to applications. It handles process management, memory management, file systems, input/output, and security. Examples include Windows, Linux, macOS.",
        "What is an operating system?": "An Operating System (OS) is system software that manages hardware resources and provides services to applications. It handles process management, memory management, file systems, input/output, and security. Examples include Windows, Linux, macOS.",
        "Explain operating system": "An Operating System manages the computer's hardware and software resources. It provides essential services like: 1) Process management - running multiple programs, 2) Memory management - allocating RAM efficiently, 3) File management - organizing data, 4) I/O management - handling peripherals, 5) Security - protecting data and resources.",
        
        # OOP Generic Questions
        "What is OOP?": "Object-Oriented Programming (OOP) is a programming paradigm based on objects and classes. It uses concepts like encapsulation (bundling data and methods), inheritance (reusing code), polymorphism (using objects in multiple ways), and abstraction (hiding complexity). Languages like Java, Python, and C++ use OOP.",
        "What is object oriented programming?": "Object-Oriented Programming (OOP) is a programming paradigm based on objects and classes. It uses concepts like encapsulation (bundling data and methods), inheritance (reusing code), polymorphism (using objects in multiple ways), and abstraction (hiding complexity). Languages like Java, Python, and C++ use OOP.",
        "Explain OOP": "OOP organizes code around objects that contain both data (attributes) and functions (methods). Key principles: 1) Classes - blueprints for objects, 2) Encapsulation - keeping data private, 3) Inheritance - extending existing classes, 4) Polymorphism - objects responding to the same message differently, 5) Abstraction - showing only essential features.",
        
        # Paging questions
        "What is paging?": "Paging is a memory management technique that divides memory into fixed-size pages. The OS manages these pages through a page table that maps virtual addresses to physical addresses.",
        "Explain how paging works": "Paging works by dividing memory into equal-sized pages. When a process needs memory, the OS allocates pages as needed. The page table tracks which pages belong to which process. When a page isn't in physical memory, a page fault occurs and the OS loads it from disk. This allows processes to use more memory than physically available.",
        "Explain how paging works in virtual memory": "Paging enables virtual memory by dividing the address space into pages. The OS maintains a page table for each process mapping virtual pages to physical pages in RAM. When a process accesses a virtual address, the MMU translates it to a physical address using the page table. If the page isn't in RAM, the OS handles the page fault by loading it from disk. This creates the illusion of unlimited memory.",
        "Describe the paging process": "The paging process works as follows: 1) A process generates a virtual address 2) The MMU extracts the page number and offset 3) The page table is consulted to find the physical page 4) If the page is in RAM (page table entry is valid), the physical address is computed 5) If not in RAM (page fault), the OS handles it by loading the page from disk 6) The page table is updated 7) The instruction is retried",
        
        # Deadlock questions
        "What is deadlock?": "Deadlock is a situation in operating systems where two or more processes are blocked indefinitely because each is waiting for a resource held by another. All processes involved are waiting and unable to proceed.",
        "Explain how deadlock works": "Deadlock occurs when circular wait conditions exist. Process A holds Resource 1 and waits for Resource 2, while Process B holds Resource 2 and waits for Resource 1. Both processes are blocked waiting for the other to release its resource. Neither can proceed, creating a deadlock. This requires four conditions: mutual exclusion, hold and wait, no preemption, and circular wait.",
        "Explain the conditions for deadlock": "Four conditions must exist simultaneously for deadlock to occur: 1) Mutual Exclusion - resources cannot be shared 2) Hold and Wait - processes hold resources while waiting for others 3) No Preemption - resources cannot be forcibly taken from processes 4) Circular Wait - a circular chain of processes waiting for resources. Breaking any one condition prevents deadlock.",
        "Describe deadlock prevention": "Deadlock can be prevented by breaking one of the four necessary conditions: 1) Eliminate mutual exclusion by making resources shareable (not always possible) 2) Prevent hold and wait by requiring processes to request all resources upfront 3) Allow preemption so resources can be taken back 4) Prevent circular wait by imposing an ordering on resource requests",
        
        # Virtual memory questions
        "What is virtual memory?": "Virtual memory is a memory management technique that gives each process the illusion of having access to a large, contiguous memory address space. It uses RAM and disk storage together, automatically managing transfers between them.",
        "Explain how virtual memory works": "Virtual memory works by mapping virtual addresses used by programs to physical addresses in RAM and disk. The MMU (Memory Management Unit) performs address translation using page tables. When a process accesses memory, if the page is in RAM it's accessed directly. If not (page fault), the OS loads it from disk. This allows processes to use more memory than physically available.",
        
        # Context switching questions
        "What is context switching?": "Context switching is the process of saving one process's execution state and loading another's so the CPU can run a different process. It's essential for multitasking but has overhead due to switching costs.",
        "Explain context switching": "Context switching occurs when the OS switches the CPU from executing one process to another. The current process's state (registers, program counter, memory maps) is saved to its PCB (Process Control Block). Then the PCB of the next process is loaded, restoring its state. Finally, the new process resumes execution. This overhead is a context switch cost.",
        "Describe the context switching process": "Context switching follows these steps: 1) The OS saves the current process's state to its PCB including registers, program counter, and memory address space 2) The OS selects the next process to run based on scheduling algorithm 3) The next process's PCB is loaded into the CPU 4) The program counter points to the next instruction of the selected process 5) Execution resumes for the new process. This happens many times per second enabling multitasking.",
        
        # Array and linked list
        "Compare arrays and linked lists": "Arrays have O(1) random access because elements are stored contiguously in memory, but O(n) insertion/deletion since shifting is needed. Linked lists have O(n) access time but O(1) insertion/deletion at known positions since only pointers change. Arrays are better for frequent lookups, linked lists for frequent insertions. Arrays have better cache locality; linked lists waste memory on pointers.",
        "What is the difference between array and linked list?": "The key differences are: Arrays store elements contiguously with O(1) access but O(n) insertion/deletion. Linked lists store elements via pointers with O(n) access but O(1) insertion/deletion at known positions. Arrays use less memory per element. Linked lists are more flexible in size. Arrays have better cache performance. Linked lists are better for dynamic operations.",
        
        # DSA - Sliding Window
        "What is sliding window technique?": "The sliding window technique is an algorithmic approach that uses a window (subarray or substring) that slides across the input array or string. It maintains a fixed or variable-size window and moves it step by step. This reduces time complexity from O(n²) to O(n) by avoiding recalculation of overlapping elements. Used for problems like maximum subarray sum, longest substring without repeating characters.",
        "Explain sliding window technique": "Sliding window works by maintaining two pointers (left and right) that define a window. The window slides through the array or string: 1) Expand the window by moving the right pointer, 2) Process elements in the window, 3) Shrink the window by moving the left pointer when needed. This approach is efficient because each element is visited at most twice. Applications include finding maximum/minimum in subarrays, substring problems, and array/string matching.",
        "Describe the sliding window approach": "The sliding window approach follows these steps: 1) Initialize left and right pointers at the start, 2) Move right pointer to expand the window and include new elements, 3) Calculate/update the result with the current window, 4) If condition is violated, shrink the window by moving left pointer, 5) Repeat until right pointer reaches the end. Time complexity is O(n) because each element enters and leaves the window exactly once.",
        
        # DSA - Two Pointers
        "What is two pointer technique?": "The two pointer technique uses two pointers starting from different positions (usually start and end) that move towards each other. It's useful for problems requiring comparison of elements from different ends of an array or checking if the array satisfies a condition. Time complexity is O(n) and space complexity is O(1). Used for finding pairs, removing duplicates, reversing arrays.",
        "Explain two pointer technique": "Two pointer technique maintains two pointers, often at opposite ends of an array. Based on the current values: 1) If the condition is satisfied, move one pointer, 2) If not satisfied, move the other pointer. This avoids nested loops and reduces time complexity. For example, to find a pair that sums to a target in a sorted array, use left and right pointers, moving them based on whether the sum is too small or too large.",
        
        # DSA - Binary Search
        "What is binary search?": "Binary search is a divide-and-conquer algorithm that finds a target value in a sorted array by repeatedly dividing the search interval in half. It compares the target with the middle element: if equal, found; if smaller, search the left half; if larger, search the right half. Time complexity is O(log n) making it much faster than linear search O(n).",
        "Explain how binary search works": "Binary search requires a sorted array. It uses two pointers (left and right) and repeatedly finds the middle element. If the middle element equals the target, return its index. If the target is less than the middle, search the left half by moving the right pointer. If greater, search the right half by moving the left pointer. Repeat until found or pointers cross. Time complexity O(log n) is due to halving the search space each iteration.",
        
        # DSA - Recursion
        "What is recursion?": "Recursion is a programming technique where a function calls itself to solve a problem by breaking it into smaller subproblems. Every recursive function needs a base case to stop the recursion and recursive cases that move towards the base case. Used for problems like factorial, fibonacci, tree traversal, and divide-and-conquer algorithms. Can lead to stack overflow if not designed carefully.",
        "Explain recursion": "Recursion works by: 1) Base case - a condition that stops the recursion (e.g., n == 0), 2) Recursive case - the function calls itself with modified arguments moving toward the base case. Example: factorial(n) = n * factorial(n-1). Each call uses stack memory, so deep recursion can cause stack overflow. Recursion is elegant but can be slower than iteration due to function call overhead.",
        
        # DSA - Dynamic Programming
        "What is dynamic programming?": "Dynamic Programming (DP) is an optimization technique that solves complex problems by breaking them into overlapping subproblems and storing (memoizing) the results to avoid redundant computation. It requires: 1) Overlapping subproblems - same subproblems computed multiple times, 2) Optimal substructure - optimal solution uses optimal solutions of subproblems. Used for problems like longest common subsequence, knapsack, and shortest paths.",
        "Explain dynamic programming": "Dynamic Programming combines recursion with memoization: 1) Break the problem into subproblems, 2) Solve each subproblem once and store the result in a table (array or hash map), 3) When a subproblem is encountered again, use the stored result instead of recomputing. This reduces time complexity from exponential to polynomial. Top-down (memoization) and bottom-up (tabulation) are two approaches.",
        
        # DSA - Sorting
        "What is sorting?": "Sorting is arranging elements in a specific order (ascending or descending). Common algorithms include bubble sort O(n²), insertion sort O(n²), merge sort O(n log n), quick sort O(n log n average), and heap sort O(n log n). Choice depends on factors like input size, whether already partially sorted, space constraints, and stability requirements.",
        "Explain merge sort": "Merge sort uses divide-and-conquer: 1) Divide the array into halves recursively until single elements, 2) Merge the sorted halves by comparing elements from each half and placing the smaller one into the result. It's stable (maintains relative order of equal elements) and guarantees O(n log n) time complexity. Requires O(n) extra space for merging.",
        "Explain quick sort": "Quick sort also uses divide-and-conquer: 1) Choose a pivot element, 2) Partition the array so elements less than pivot are on the left, greater on the right, 3) Recursively sort the left and right partitions. Average time complexity is O(n log n) but worst case is O(n²). It's faster in practice than merge sort due to better cache locality and requires O(log n) space for recursion.",
        "What is quick sort?": "Quick sort is a divide-and-conquer sorting algorithm that chooses a pivot, partitions the array around that pivot, and recursively sorts the two partitions. It is efficient on average with O(n log n) time, but can degrade to O(n²) in the worst case when the pivot choices are poor.",
        "What is quicksort?": "Quick sort is a divide-and-conquer sorting algorithm that chooses a pivot, partitions the array around that pivot, and recursively sorts the two partitions. It is efficient on average with O(n log n) time, but can degrade to O(n²) in the worst case when the pivot choices are poor.",

        # DSA - Tree Traversal
        "What is tree traversal?": "Tree traversal is the process of visiting every node in a tree in a systematic order. Common traversals are preorder (root-left-right), inorder (left-root-right), postorder (left-right-root), and level-order (breadth-first traversal using a queue). It is used in searching, expression evaluation, and tree processing.",
        "Explain tree traversal": "Tree traversal means visiting all nodes of a tree in a defined order. Preorder visits the root first, inorder visits the left subtree then the root then the right subtree, postorder visits the root last, and level-order visits nodes level by level using a queue. The choice of traversal depends on the problem.",
        "Explain tree traversal techniques": "Tree traversal techniques include preorder, inorder, postorder, and level-order traversal. Preorder is useful for copying a tree, inorder gives sorted order for a binary search tree, postorder is useful for deletion and evaluating expression trees, and level-order is useful for breadth-first processing.",
        "What is tree traversal and sorting?": "Tree traversal is the ordered visiting of all nodes in a tree, while sorting is arranging elements in a specific order such as ascending or descending. Tree traversal uses preorder, inorder, postorder, or level-order, whereas sorting uses algorithms like quick sort, merge sort, and heap sort.",
        "Explain tree traversal and sorting algorithms": "Tree traversal and sorting algorithms are different DSA concepts. Tree traversal visits every node of a tree in a defined order, while sorting algorithms arrange data in ascending or descending order. Traversals include preorder, inorder, postorder, and level-order; sorting algorithms include quick sort, merge sort, heap sort, and insertion sort.",
        
        # DSA - Hash Tables
        "What is a hash table?": "A hash table (hash map) uses a hash function to map keys to array indices for O(1) average-case lookup, insertion, and deletion. It handles collisions through chaining (linked lists at each index) or open addressing (finding another empty slot). Trade-off: fast access but requires good hash function and management of collisions and load factor.",
        "Explain how hash tables work": "Hash tables store key-value pairs: 1) Hash function converts a key to an array index, 2) Value is stored at that index, 3) For lookup, apply hash function to key and access the index. Collisions occur when different keys hash to the same index. Chaining resolves this by using linked lists; open addressing finds another slot. Load factor (elements/capacity) is monitored to trigger resizing.",
        # Greedy algorithm specific entries (avoid generic fallback)
        "What is greedy algorithm?": (
            "A greedy algorithm builds a solution step-by-step by choosing the locally optimal option at each step with the hope of finding a global optimum. "
            "Greedy methods are simple and efficient; correctness is usually shown via an exchange or cut-and-paste argument. Examples: activity selection (choose earliest finishing activity), Huffman coding (build optimal prefix codes), and fractional knapsack (take highest value/weight first)."
        ),
        "What is the greedy approach?": (
            "The greedy approach makes the best immediate choice at each step. It works for problems where local optimum leads to global optimum (e.g., activity selection) but can fail for others (e.g., 0/1 knapsack). Key proof techniques: exchange argument and matroid theory for formal guarantees."
        ),
        "Explain greedy algorithm": (
            "A greedy algorithm iteratively picks the best available option according to a heuristic and never revisits earlier choices. To apply it: 1) Define candidate set and selection rule, 2) prove greedy-choice property (local choice is safe), 3) prove optimal substructure or use exchange argument. Examples and counterexamples illustrate when it succeeds or fails."
        ),
        "Give an example of greedy algorithm": (
            "Classic examples: 1) Activity selection — sort by finish time, pick next compatible activity; optimal by exchange argument. "
            "2) Fractional knapsack — take items by highest value/weight ratio. 3) Prim's or Kruskal's MST algorithms — choose smallest edge that doesn't form a cycle."
        ),
        
        # Database/SQL questions
        "What is SQL?": "SQL (Structured Query Language) is a standardized language for managing and querying relational databases. It allows you to create tables, insert/update/delete data, and retrieve information using SELECT queries with various clauses and conditions.",
        "Explain SQL": "SQL is used to interact with relational databases. You can CREATE tables to define schemas, INSERT to add data, SELECT to query with WHERE clauses for filtering, JOIN to combine tables, UPDATE to modify data, and DELETE to remove data. It uses a declarative approach where you specify WHAT you want, not HOW to get it.",
        "What is DBMS?": "A Database Management System (DBMS) is software that lets you store, organize, retrieve, and manage data in databases efficiently. It provides tools for querying, transactions, security, concurrency control, backup, and recovery.",
        "What is primary key?": "A primary key is a column or set of columns that uniquely identifies each row in a table. It cannot contain duplicate values or NULLs, and it is used to enforce entity integrity.",
        "What is foreign key?": "A foreign key is a column or set of columns in one table that references the primary key of another table. It creates relationships between tables and helps maintain referential integrity.",
        "What is table?": "A table is a database structure that stores data in rows and columns. Each row represents a record, and each column represents a field or attribute.",
        "What is index?": "An index is a database structure that speeds up data retrieval by creating a fast lookup path for one or more columns. It improves SELECT performance but adds overhead to INSERT, UPDATE, and DELETE operations.",
        "What is ACID property?": "ACID properties describe reliable database transactions: Atomicity means all operations succeed or none do, Consistency means data remains valid, Isolation means concurrent transactions do not interfere, and Durability means committed changes persist after failure.",
        "What is transaction?": "A transaction is a sequence of database operations executed as one logical unit. It either commits completely or rolls back completely, which keeps the database consistent.",
        "What is normalization?": "Normalization is the process of organizing database tables to reduce redundancy and prevent anomalies. It splits data into related tables and uses normal forms such as 1NF, 2NF, 3NF, and BCNF.",
        "What is denormalization?": "Denormalization intentionally adds redundancy back into a database to speed up reads and simplify queries. It is often used in reporting systems and analytics when read performance matters more than storage efficiency.",
        "What is view in database?": "A view is a virtual table created from the result of a query. It does not always store data physically; instead, it presents a customized, reusable way to look at data from one or more tables.",
        "What is stored procedure?": "A stored procedure is a precompiled set of SQL statements stored in the database and executed as a single unit. It improves reuse, security, and performance for repeated database operations.",
        "Explain normalization": "Normalization organizes database tables to reduce duplication and improve consistency. The process usually starts with 1NF, then 2NF, then 3NF, and sometimes BCNF, each step removing a different type of dependency problem.",
        "Explain joins in SQL": "SQL joins combine rows from multiple tables based on a related column. INNER JOIN returns matching rows, LEFT JOIN keeps all rows from the left table, RIGHT JOIN keeps all rows from the right table, and FULL JOIN keeps all rows from both tables.",
        "Explain database schema": "A database schema is the logical design of a database. It defines tables, columns, data types, relationships, constraints, indexes, and how the data is organized.",
        "Explain indexing strategy": "An indexing strategy decides which columns should have indexes based on query patterns, filtering, sorting, and joining needs. Good strategies balance faster reads with the extra cost of maintaining indexes on writes.",
        "Explain B+ tree": "A B+ tree is a balanced tree data structure commonly used in databases and file systems for indexing. Internal nodes store keys for navigation, while all actual data pointers or records are stored at the leaf level, which makes range queries efficient.",
        "Explain MVCC for transaction isolation": "MVCC (Multi-Version Concurrency Control) allows multiple transactions to read and write safely by keeping multiple versions of data. Readers see a consistent snapshot while writers create new versions, which reduces locking and improves concurrency.",
        "Explain query optimization": "Query optimization is the process of choosing the most efficient execution plan for a SQL query. The optimizer considers indexes, join order, filtering conditions, and available statistics to reduce execution time.",
        "Difference between OLTP and OLAP": "OLTP systems handle day-to-day transactional workloads with many short insert/update/delete operations, while OLAP systems handle analytical workloads with large read-heavy queries and aggregations.",
        "Compare SQL and NoSQL": "SQL databases are relational and use structured tables, schema, and SQL queries, while NoSQL databases are more flexible and include document, key-value, column-family, and graph models. SQL is often best for consistency and transactions; NoSQL is often used for scalability and flexible schemas.",
        "Compare relational and hierarchical database": "Relational databases store data in tables with relationships between them, while hierarchical databases store data in a tree-like parent-child structure. Relational models are more flexible for complex queries, while hierarchical models work well when the data naturally fits a tree.",
        "Compare primary key and unique key": "A primary key uniquely identifies each row and cannot be NULL, while a unique key also enforces uniqueness but can usually allow one NULL value depending on the database system. A table can have one primary key but multiple unique keys.",
        "Design a database schema for social media platform": "A social media schema usually includes users, posts, comments, likes, follows, messages, and notifications. Tables should use primary keys, foreign keys, and indexes on common lookup columns such as user_id, post_id, and created_at.",
        "Write a query to find nth highest salary": "To find the nth highest salary, you can use ORDER BY salary DESC with LIMIT/OFFSET, or use a window function like DENSE_RANK() over salary ordering and filter by rank = n. The exact query depends on the SQL dialect.",
        "Describe how indexing improves query performance": "Indexing improves query performance by reducing the number of rows the database must scan. Instead of reading the full table, the engine can jump directly to matching keys in the index, which speeds up filters, joins, and sorting.",
        "Why should you normalize database?": "You normalize a database to reduce duplicate data, avoid update/insert/delete anomalies, and keep data consistent. Normalization also makes the schema easier to maintain and less error-prone.",
        
        # Transaction questions
        "What is a database transaction?": "A database transaction is a sequence of database operations that execute as a single atomic unit. Either all operations succeed or all are rolled back, ensuring data consistency and integrity.",
        "Explain ACID properties": "ACID properties ensure reliable database transactions: Atomicity - all or nothing execution, Consistency - database remains in valid state, Isolation - concurrent transactions don't interfere with each other, Durability - committed changes persist even after failures.",
    }
    
    # Additional comprehensive answers for common variations
    SPECIFIC_ANSWERS.update({
        # More OS Questions
        "What is a process?": "A process is an instance of a program in execution. It has its own memory space (code, data, stack, heap), program counter, and CPU registers. The OS manages processes through the Process Control Block (PCB) and uses process scheduling to allocate CPU time among multiple processes.",
        "Explain how process scheduling works": "Process scheduling determines which process gets CPU time. The scheduler uses algorithms like Round Robin (each process gets a time slice), Priority-based (higher priority first), or Shortest Job First. Context switching occurs between processes. The goal is to maximize CPU utilization, minimize waiting time, and ensure fair resource allocation.",
        "What is a thread?": "A thread is the smallest unit of execution within a process. Multiple threads within the same process share the same memory space but have separate stacks and program counters. Threads are lighter weight than processes, making context switching between threads faster. They enable concurrent execution within a single process.",
        "Explain memory management": "Memory management involves allocating and deallocating memory to processes. Techniques include: 1) Contiguous allocation - allocate large blocks, 2) Paging - divide into fixed-size pages, 3) Segmentation - divide into variable-size segments. The OS maintains page tables or segment tables to track memory allocation and handle page faults.",
        
        # OOP Specific Questions
        "What is encapsulation?": "Encapsulation is bundling data (attributes) and methods (functions) together within a class while hiding internal details from the outside world. It uses access modifiers (public, private, protected) to control visibility. Benefits: data protection, flexibility to change internal implementation, and reduced coupling between classes.",
        "Explain inheritance": "Inheritance allows a class (child/derived) to inherit attributes and methods from another class (parent/base). It promotes code reuse and establishes a hierarchical relationship. Types: single (one parent), multiple (several parents), multilevel (grandparent->parent->child). The child can override parent methods (method overriding) for specialized behavior.",
        "What is polymorphism?": "Polymorphism means 'many forms' - the same method name can behave differently in different classes. Types: Compile-time (method overloading - same name, different parameters) and Runtime (method overriding - child overrides parent method). Enables flexible code that works with different object types.",
        "Explain abstraction": "Abstraction hides complex implementation details and shows only essential features to the user. Abstract classes and interfaces define methods that subclasses must implement. Benefits: reduces complexity, makes code more maintainable, and allows focusing on what an object does rather than how it does it.",
        
        # DBMS Specific Questions
        "What is normalization?": "Normalization is the process of organizing data in a database to reduce redundancy and improve data integrity. Normal forms: 1NF (no repeating groups), 2NF (no partial dependencies), 3NF (no transitive dependencies), BCNF (strict 3NF). Benefits: reduces storage, improves query performance, and prevents anomalies.",
        "Explain indexing": "Indexing creates a data structure (usually B-tree) to enable fast lookups of data without scanning the entire table. Primary key index ensures uniqueness; secondary indexes improve query performance on other columns. Trade-off: faster reads but slower writes (must update indexes). Essential for optimizing database performance.",
        "What is a join?": "A join combines rows from two or more tables based on a related column. Types: INNER JOIN (matching rows only), LEFT JOIN (all left table rows plus matches), RIGHT JOIN (all right table rows plus matches), FULL JOIN (all rows from both tables). Joins are fundamental for querying relational data across multiple tables.",
        "Explain constraints": "Constraints enforce rules on table data: PRIMARY KEY (unique, non-null), FOREIGN KEY (references another table), UNIQUE (no duplicates), NOT NULL (must have value), CHECK (condition validation), DEFAULT (default value if not specified). Constraints maintain data integrity and prevent invalid data insertion.",
        
        # CN Specific Questions
        "What is OSI model?": "The OSI (Open Systems Interconnection) model has 7 layers: Physical (cables), Data Link (MAC addresses), Network (IP routing), Transport (TCP/UDP), Session (connections), Presentation (encryption), Application (HTTP/FTP). Each layer handles specific functions and communicates with adjacent layers, enabling interoperability.",
        "Explain TCP/IP model": "The TCP/IP model has 4 layers: Link (network interface), Internet (IP), Transport (TCP/UDP), Application (HTTP/FTP/DNS). It's more practical than OSI and is the basis of the internet. TCP ensures reliable delivery; UDP is faster but unreliable. This model enables communication across diverse networks.",
        "What is routing?": "Routing is the process of forwarding data packets from source to destination across networks. Routers use routing tables and protocols (RIP, OSPF, BGP) to determine optimal paths. Routing decisions use IP addresses and masks. Static routing (manual) is simple but inflexible; dynamic routing adapts to network changes.",
        "Explain DNS": "Domain Name System (DNS) translates domain names (www.example.com) to IP addresses. It uses a hierarchical system: root nameservers, TLD servers, authoritative nameservers. DNS enables user-friendly web browsing without memorizing IP addresses. Operates on port 53 using UDP for queries and TCP for zone transfers.",
    })
    
    # Intent-based answer templates when specific Q not found
    INTENT_TEMPLATES = {
        "definition": {
            "easy": "A {concept} is a {attribute}.",
            "medium": "A {concept} is a {attribute}. It is important for {why}.",
            "hard": "A {concept} is a {attribute} that plays a crucial role in {domain}. Key aspects include {aspects}."
        },
        "explanation": {
            "easy": "{concept} works by {mechanism}.",
            "medium": "{concept} works through a process where {detailed_mechanism}. This is important because {significance}.",
            "hard": "{concept} operates as follows: {detailed_steps}. The key insight is that {insight}."
        },
        "comparison": {
            "easy": "{concept1} and {concept2} are different in key ways.",
            "medium": "{concept1} has {attr1} while {concept2} has {attr2}. Choose {concept1} for {use1}, and {concept2} for {use2}.",
            "hard": "Detailed comparison: {concept1} vs {concept2}. Similarities: {similarities}. Differences: {differences}. Use cases: {use_cases}."
        },
        "procedure": {
            "easy": "The steps are: {steps}.",
            "medium": "The procedure involves these steps: {detailed_steps}. Each step is important because {importance}.",
            "hard": "The complete procedure: {all_steps}. Conditions to check: {conditions}. Expected outcome: {outcome}."
        }
    }
    
    def generate_model_answer(
        self,
        question_text: str,
        intent: str,
        topics: list[str],
        difficulty: str
    ) -> str:
        """Generate a question-specific model answer."""
        question_lower = question_text.lower().strip()

        # normalize function for matching (remove punctuation, extra spaces)
        def _normalize(s: str) -> str:
            import re
            s2 = s.lower()
            s2 = re.sub(r"[^a-z0-9\s]", " ", s2)
            s2 = re.sub(r"\s+", " ", s2).strip()
            return s2

        norm_question = _normalize(question_text)
        
        # STRATEGY 1: Exact or normalized matching (prefer longest explicit patterns)
        # Build list of (pattern,answer) and prefer longest normalized pattern match
        norm_map = []
        for question_pattern, answer in self.SPECIFIC_ANSWERS.items():
            norm_pat = _normalize(question_pattern)
            norm_map.append((norm_pat, question_pattern, answer))

        # Prefer exact normalized equality first
        for norm_pat, raw_pat, answer in norm_map:
            if norm_question == norm_pat:
                return answer

        # Then prefer the longest pattern that appears inside question or vice-versa
        best_pat = None
        best_len = 0
        for norm_pat, raw_pat, answer in norm_map:
            if norm_pat in norm_question or norm_question in norm_pat:
                l = len(norm_pat.split())
                if l > best_len:
                    best_len = l
                    best_pat = answer

        if best_pat:
            return best_pat
        
        # STRATEGY 2: Keyword-based matching - weighted scoring with synonym support
        best_match = None
        best_score = 0.0

        question_words = set(norm_question.split())
        stopwords = {"what", "is", "explain", "describe", "compare", "how", "why", "the", "a", "an", "do", "does", "give", "example", "list"}
        question_keywords = question_words - stopwords

        # synonyms mapping to collapse variants (e.g., greedy, greedy algorithm)
        synonyms = {
            "greedy": "greedy algorithm",
            "greedyalgorithm": "greedy algorithm",
            "activityselection": "activity selection",
        }

        def _map_synonyms(words:set[str]) -> set[str]:
            out = set()
            for w in words:
                key = w.replace(" ", "")
                out.add(synonyms.get(key, w))
            return out

        mapped_qk = _map_synonyms(question_keywords)

        # Score each pattern by weighted overlap (favor longer pattern matches)
        for pattern, answer in self.SPECIFIC_ANSWERS.items():
            norm_pat = _normalize(pattern)
            pat_words = set(norm_pat.split()) - stopwords
            mapped_pat = _map_synonyms(pat_words)

            overlap = len(mapped_pat & mapped_qk)
            # base score: overlap ratio + bonus for pattern length
            if mapped_pat or mapped_qk:
                jaccard = overlap / len(mapped_pat | mapped_qk) if (mapped_pat | mapped_qk) else 0
            else:
                jaccard = 0

            length_bonus = min(1.0, len(mapped_pat) / 6.0)  # prefer more-specific patterns
            score = jaccard * 0.7 + length_bonus * 0.3 + overlap * 0.1

            # Accept single-keyword matches for well-known algorithm keywords (e.g., greedy, dp)
            if overlap >= 1 and ("greedy" in mapped_qk or "greedy algorithm" in mapped_qk or "activity" in mapped_qk):
                score += 0.25

            if score > best_score:
                best_score = score
                best_match = answer

        if best_match and best_score > 0.18:
            return best_match
        
        # STRATEGY 3: Try substring/phrase matching for very similar questions
        for question_pattern, answer in self.SPECIFIC_ANSWERS.items():
            pattern_lower = question_pattern.lower()
            if len(question_lower) > 5 and len(pattern_lower) > 5:
                if question_lower in pattern_lower or pattern_lower in question_lower:
                    return answer
        
        # STRATEGY 4: Try topic-based answer
        topic_answer = self._get_topic_answer(question_text, topics)
        if topic_answer:
            return topic_answer
        
        # STRATEGY 5: Fallback to intent-based generation
        return self._generate_intent_based_answer(question_text, intent, topics, difficulty)
    
    def _get_topic_answer(self, question_text: str, topics: list[str]) -> str | None:
        """Get answer based on topic if question mentions the topic directly."""
        question_lower = question_text.lower()
        
        # Map topic names to answers
        topic_answers = {
            "os": "An Operating System manages hardware and software resources. It handles process management, memory management, file systems, I/O operations, and security. Examples: Windows, Linux, macOS.",
            "oop": "Object-Oriented Programming uses objects and classes. Key principles: encapsulation (bundling data/methods), inheritance (reusing code), polymorphism (using objects multiple ways), and abstraction (hiding complexity).",
            "dbms": "A Database Management System stores, retrieves, and manages data efficiently. It provides data integrity through ACID properties, supports complex queries via SQL, ensures security, and enables concurrent access.",
            "dsa": "Data Structures and Algorithms provide efficient ways to store and process data. Data structures (arrays, linked lists, trees) organize data; algorithms (sorting, searching) process it. Together they enable optimal performance.",
            "cn": "Computer Networks enable communication between devices through protocols and infrastructure. Key concepts: layered models (OSI/TCP-IP), protocols (TCP/UDP/IP), routing, and services like DNS and HTTP.",
        }
        
        for topic in topics:
            topic_key = topic.lower()[:2]  # OS, OO, DB, DS, CN
            if topic_key in topic_answers and topic_key in question_lower:
                return topic_answers[topic_key]
        
        return None
    
    def _generate_intent_based_answer(self, question_text: str, intent: str, topics: list[str], difficulty: str) -> str:
        """Generate answer based on intent when no specific Q found."""
        main_concept = self._extract_main_concept(question_text, topics)
        
        # Return specific answers based on concept, not generic fallback
        if "dsa" in main_concept.lower() or "data structure" in question_text.lower():
            return "Data Structures and Algorithms (DSA) involves arrays, linked lists, trees, graphs, and their operations for solving computational problems efficiently. DSA is fundamental to writing optimized code with good time and space complexity."
        elif any(term in question_text.lower() for term in ["dbms", "database", "sql", "primary key", "foreign key", "normalization", "transaction", "index", "join", "schema", "acid", "oltp", "olap"]):
            return "A Database Management System (DBMS) stores and manages structured data, supports SQL queries, enforces constraints and relationships, and provides transactions, indexing, concurrency control, backup, and recovery. Understanding tables, keys, normalization, and query performance is essential for database design."
        elif "array" in question_text.lower():
            return "An array is a contiguous block of memory storing elements of the same type. It provides O(1) random access by index but requires O(n) time for insertion/deletion. Arrays are efficient for lookups and iterations."
        elif "linked list" in question_text.lower():
            return "A linked list consists of nodes connected by pointers, allowing O(1) insertion/deletion at known positions but O(n) for random access. Linked lists are more flexible than arrays for dynamic operations but waste memory on pointers."
        elif "quick sort" in question_text.lower() or "quicksort" in question_text.lower():
            return "Quick sort is a divide-and-conquer sorting algorithm. It chooses a pivot, partitions the array into smaller and larger elements, and recursively sorts each partition. Average time complexity is O(n log n), while the worst case is O(n²) if partitions are unbalanced."
        elif "tree" in question_text.lower():
            if "traversal" in question_text.lower() or "inorder" in question_text.lower() or "preorder" in question_text.lower() or "postorder" in question_text.lower():
                return "Tree traversal is the process of visiting every node in a tree in a specific order. Preorder visits root-left-right, inorder visits left-root-right, postorder visits left-right-root, and level-order visits level by level using a queue."
            return "A tree is a hierarchical data structure with a root node and child nodes. Trees provide O(log n) operations for balanced structures. Uses include binary search trees for sorting and search, and expression trees for parsing."
        elif "graph" in question_text.lower():
            return "A graph consists of nodes (vertices) connected by edges, representing relationships. Graphs can be directed or undirected, weighted or unweighted. They're used for networks, social relationships, and pathfinding algorithms."
        elif "oop" in main_concept.lower() or "class" in question_text.lower():
            return "Object-Oriented Programming uses classes and objects to organize code. Key principles: encapsulation (bundling data/methods), inheritance (code reuse), polymorphism (different implementations), and abstraction (hiding complexity). Benefits include modularity and reusability."
        elif "database" in main_concept.lower() or "sql" in question_text.lower():
            return "A database management system stores and retrieves data efficiently using structured tables with relationships. SQL allows querying and manipulating data. Key features: ACID properties ensure reliability, indexing for speed, and query optimization."
        elif "network" in main_concept.lower() or "protocol" in question_text.lower():
            return "Computer networks enable communication between devices through protocols and layered models. TCP/IP stack handles transmission, DNS resolves names, HTTP transfers web data. Networks use routers, switches, and firewalls for connectivity and security."
        
        # Fallback: provide meaningful answer related to concept
        if intent == "definition":
            return f"{main_concept} is a key concept in {topics[0] if topics else 'computer science'} that is important for solving computational problems and understanding system design."
        elif intent == "explanation":
            return f"{main_concept} works by processing information through organized steps and structures. Understanding it requires knowing its components and how they interact to achieve the desired outcome."
        elif intent == "comparison":
            return f"Different approaches to {main_concept} have various tradeoffs in terms of time complexity, space complexity, and practical performance. The best choice depends on your specific use case and constraints."
        elif intent == "procedure":
            return f"The process of working with {main_concept} involves: 1) Understanding the requirements, 2) Choosing the right approach, 3) Implementing systematically, 4) Testing and validating results."
        else:
            return f"{main_concept} is an important concept that requires understanding its structure, operations, and applications in real-world scenarios."
    
    def _extract_main_concept(self, question_text: str, topics: list[str]) -> str:
        """Extract the main concept from question text."""
        question_lower = question_text.lower()
        
        # Common concept keywords
        concepts = {
            "paging": "Paging",
            "deadlock": "Deadlock",
            "virtual memory": "Virtual Memory",
            "context switch": "Context Switching",
            "process": "Process",
            "thread": "Thread",
            "memory": "Memory",
            "array": "Array",
            "linked list": "Linked List",
            "tree": "Tree",
            "graph": "Graph",
            "database": "Database",
            "sql": "SQL",
            "transaction": "Transaction",
            "network": "Network",
            "protocol": "Protocol",
            "class": "Class",
            "object": "Object",
        }
        
        for concept, title in concepts.items():
            if concept in question_lower:
                return title
        
        return topics[0] if topics else "Concept"
    
    def get_key_points(self, intent: str, topics: list[str], difficulty: str) -> list[str]:
        """Get key points that should be in the answer."""
        if intent == "definition":
            points = [
                "Clear and concise explanation",
                "Essential characteristics",
            ]
            if difficulty in ["medium", "hard"]:
                points.append("Related concepts or context")
            if difficulty == "hard":
                points.append("Applications or use cases")
            return points
        
        elif intent == "explanation":
            return [
                "Detailed mechanism or process",
                "Step-by-step explanation",
                "Why it's important",
                "Related concepts",
            ]
        
        elif intent == "comparison":
            return [
                "Identify at least 2 key differences",
                "Identify at least 2 key similarities",
                "Pros/cons of each concept",
                "When to use each one",
            ]
        
        elif intent == "procedure":
            return [
                "Clear step-by-step process",
                "Numbered or sequential steps",
                "Conditions or prerequisites",
                "Expected outcome",
            ]
        
        else:
            return ["Comprehensive understanding", "Supporting details", "Relevant examples"]


# Global instance
question_specific_generator = QuestionSpecificAnswerGenerator()
