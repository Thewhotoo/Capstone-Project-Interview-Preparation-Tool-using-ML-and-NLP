# Question bank: dsa

- **Active (used by the app): 50** · held back for review: 30 (confidence threshold 0.75)
- Sorted by confidence, best first. Held-back questions are kept below, not deleted.

## Active questions

### [Priority queue] Explain what a priority queue is and how it differs between ascending and descending types.
*confidence 0.96 · easy · slides [245, 246, 247, 248, 249, 250]*

**Reference:** A priority queue is a data structure where the intrinsic ordering of elements determines the results of its basic operations. An ascending priority queue removes the smallest item, while a descending priority queue removes the largest item. This distinction is important because it defines the behavior of the queue in different applications.

**Key points** (slide quote → follow-up → expected answer):
- **A priority queue is a data structure where the intrinsic ordering of elements determines the results of its basic operations.**  
  quote: "Priority Queue is a Data Structure in which intrinsic ordering of the elements does determine the results of its basic operations"  
  follow-up: _What is the main difference between a priority queue and a regular queue?_  
  expected: The main difference is that in a priority queue, the element with the highest (or lowest) priority is removed first, whereas in a regular queue, elements are removed in the order they were inserted.
- **An ascending priority queue removes the smallest item.**  
  quote: "Ascending Priority Queue: is a collection of items into which items can be inserted arbitrarily and from which only the smallest item can be removed"  
  follow-up: _What would happen if you tried to remove the largest item from an ascending priority queue?_  
  expected: It would not follow the defined behavior of an ascending priority queue, which only allows removal of the smallest item.
- **A descending priority queue removes the largest item.**  
  quote: "Descending Priority Queue: is a collection of items into which items can be inserted arbitrarily and from which only the largest item can be removed"  
  follow-up: _How would you implement a descending priority queue using an array?_  
  expected: You would use a heap structure where the largest item is always at the root, and you would use siftup and adjustheap operations to maintain the heap property.

### [Expression trees] Explain what an expression tree is and how it represents an arithmetic expression.
*confidence 0.96 · easy · slides [218, 219, 220, 224, 225, 226]*

**Reference:** An expression tree is a data structure that represents an arithmetic expression in a hierarchical form. It is built to translate code as data and then analyze and evaluate expressions. The tree is constructed such that operands are leaves and operators are internal nodes, with each operator connecting to its operands as children.

**Key points** (slide quote → follow-up → expected answer):
- **An expression tree is a data structure that represents an arithmetic expression in a hierarchical form.**  
  quote: "An expression can be represented using the Expression Tree data structure"  
  follow-up: _What is the purpose of using an expression tree for arithmetic expressions?_  
  expected: The purpose is to translate code as data and then analyze and evaluate expressions.
- **The tree is constructed such that operands are leaves and operators are internal nodes.**  
  quote: "node can be either an operand or an operator"  
  follow-up: _How are operands and operators represented in an expression tree?_  
  expected: Operands are represented as leaves, and operators are represented as internal nodes.
- **Each operator connects to its operands as children.**  
  quote: "If an operator, it connects to two leaves"  
  follow-up: _How does an operator node relate to its operands in the tree?_  
  expected: An operator node connects to its operands as its left and right children.

### [Tries] Explain what a trie is and how it is used in computer science.
*confidence 0.96 · easy · slides [22, 23, 24]*

**Reference:** A trie is a type of search tree used for locating specific keys from within a set. These keys are most often strings, with links between nodes defined not by the entire key, but by individual characters. Tries are used in applications such as dictionary storage and auto-complete features because they allow for efficient search, insert, and delete operations based on string prefixes.

**Key points** (slide quote → follow-up → expected answer):
- **A trie is a type of search tree used for locating specific keys from within a set.**  
  quote: "A trie, also called digital tree or prefix tree, is a type of search tree, a tree data structure used for locating specific keys from within a set"  
  follow-up: _What kind of data is typically stored in a trie?_  
  expected: Tries are typically used to store strings, as they allow for efficient prefix-based operations.
- **Trie nodes are linked by individual characters, not the entire key.**  
  quote: "These keys are most often strings, with links between nodes defined not by the entire key, but by individual characters"  
  follow-up: _How does this linking method help with searching for strings?_  
  expected: This method allows for efficient prefix-based searching, as each character in the string leads to a new node in the trie.
- **Tries are used in applications such as dictionary storage and auto-complete features.**  
  quote: "Common applications of tries include storing a predictive text or autocomplete dictionary and implementing approximate matching algorithms, such as those used in spell checking"  
  follow-up: _Why would someone use a trie for auto-complete?_  
  expected: A trie allows for quick prefix-based searches, which is essential for auto-complete features that suggest words based on partial input.

### [Sorting by counting] Explain how Distribution Counting Sorting works based on the information provided.
*confidence 0.96 · easy · slides [1289, 1299, 1300, 1301]*

**Reference:** Distribution Counting Sorting uses the frequency of elements from a finite set to determine their positions in the sorted list. It counts how often each element appears and then scans the set in order to print elements according to their frequency. This method relies on the idea that the accumulated sum of frequencies, known as the distribution, determines the correct placement of elements in the sorted array.

**Key points** (slide quote → follow-up → expected answer):
- **Distribution Counting Sorting uses the frequency of elements from a finite set to determine their positions in the sorted list.**  
  quote: "Count the frequency of each element of the set in the list to be sorted."  
  follow-up: _What happens if the elements are not from a finite set?_  
  expected: The method would not work because it requires a finite domain to count frequencies and determine positions.
- **The accumulated sum of frequencies determines the correct placement of elements in the sorted array.**  
  quote: "The required information which is used to place the elements at proper positions is accumulated sum of frequencies which is also called as distribution in statistics."  
  follow-up: _How does the accumulated sum of frequencies help in sorting?_  
  expected: The accumulated sum tells us where each element should be placed in the sorted array, based on how many elements are smaller or equal to it.
- **The method scans the set in order to print elements according to their frequency.**  
  quote: "Scan the set in order of sorting and print each element of the set according to its frequency, which will be the required sorted list."  
  follow-up: _Why is it important to scan the set in order?_  
  expected: Scanning the set in order ensures that elements are placed in the correct sequence, maintaining the sorted order based on their frequency.

### [Kruskal's algorithm] Explain how Kruskal’s algorithm builds a minimum spanning tree.
*confidence 0.96 · easy · slides [1382, 1386, 1387, 1388, 1401, 1402]*

**Reference:** Kruskal’s algorithm builds a minimum spanning tree by initially treating each vertex as a separate tree. It then processes edges in non-decreasing order of weight, adding an edge to the tree only if it connects two different trees. This process continues until all vertices are connected, forming a single tree.

**Key points** (slide quote → follow-up → expected answer):
- **Kruskal’s algorithm starts with each vertex as a separate tree.**  
  quote: "Initially, trees of the forest are the vertices (no edges)."  
  follow-up: _What happens to the trees before any edges are added?_  
  expected: Before any edges are added, each vertex is its own tree, forming a forest of single-node trees.
- **Edges are processed in non-decreasing order of weight.**  
  quote: "Sort the edges in non-decreasing order of their weights."  
  follow-up: _Why is the order of processing edges important?_  
  expected: The order ensures that the smallest possible edges are considered first, which is essential for finding the minimum total weight.
- **An edge is added only if it connects two different trees.**  
  quote: "If adding that edge does not create a cycle (that is, the two vertices are not already connected), add that edge to the minimum spanning tree."  
  follow-up: _What is the purpose of checking if two vertices are already connected?_  
  expected: Checking if two vertices are connected prevents cycles, ensuring that the result remains a tree rather than a graph with cycles.

### [Stacks and recursion] Explain how a stack is used in the execution of recursive functions.
*confidence 0.96 · easy · slides [658, 659, 660, 661, 662]*

**Reference:** A stack is used in the execution of recursive functions because each function call creates an activation record that is pushed onto the stack. This activation record contains the function's local variables and return address. The last-in, first-out (LIFO) property of the stack ensures that when a recursive function completes, the most recent call is removed from the stack, allowing control to return to the previous call in the call chain.

**Key points** (slide quote → follow-up → expected answer):
- **Each recursive function call creates an activation record that is pushed onto the stack.**  
  quote: "The system (or the program) must remember the place where the call was made, so that it can return there after the function is complete."  
  follow-up: _Why is it important for the system to remember where a function call was made?_  
  expected: It is important because the function needs to return to the correct location in the program after it completes its execution.
- **The stack ensures that the most recent function call is executed first, and the most recent call is removed first.**  
  quote: "The machine’s task of assigning temporary storage area (activation records) used by functions would be in same order (LIFO)."  
  follow-up: _What property of the stack makes it suitable for managing recursive function calls?_  
  expected: The LIFO property of the stack makes it suitable for managing recursive function calls, as each new call is placed on top of the previous one and is processed first.
- **The stack stores the return address so that the program can resume execution after the function call completes.**  
  quote: "The system (or the program) must remember the place where the call was made, so that it can return there after the function is complete."  
  follow-up: _What happens to the return address when a function call is made?_  
  expected: The return address is stored in the activation record on the stack so that the program can resume execution at the correct location after the function call completes.

### [Circular queue] Explain how a circular queue solves the problem of wasted space in a simple queue.
*confidence 0.96 · easy · slides [476, 477]*

**Reference:** A circular queue solves the problem of wasted space by allowing the rear pointer to wrap around to the beginning of the array once it reaches the end. This enables the queue to reuse the space that was previously occupied by removed elements. In a simple queue, once the queue is full, no new elements can be inserted even if some elements are removed, but in a circular queue, this space is made available again by moving the rear pointer to the start of the queue.

**Key points** (slide quote → follow-up → expected answer):
- **A circular queue allows the rear pointer to wrap around to the beginning of the array.**  
  quote: "It is possible to insert in a circular queue by moving the rear rear front to the beginning of the queue."  
  follow-up: _What happens to the rear pointer when the queue is full and elements are removed?_  
  expected: The rear pointer wraps around to the beginning of the array, making space available for new insertions.
- **A circular queue reuses space that was previously occupied by removed elements.**  
  quote: "In a simple queue, once the queue is completely full, it's not possible to insert more elements. Even if we perform remove operation on the queue to remove some of the elements, until the queue is reset, no new elements can be inserted."  
  follow-up: _Why can't a simple queue reuse space after elements are removed?_  
  expected: Because the rear pointer cannot wrap around to the beginning of the array, so the space is not reused until the queue is manually reset.
- **A circular queue behaves like a circular data structure.**  
  quote: "Circular Queue is a linear data structure, which follows the principle of FIFO(First In First Out), but instead of ending the queue at the last position, it again starts from the first position after the last, hence making the queue behave like a circular data structure."  
  follow-up: _How does a circular queue behave differently from a simple queue?_  
  expected: A circular queue behaves like a circular data structure by allowing the rear pointer to start from the first position after the last, making space available for new insertions.

### [Exhaustive search] Explain what exhaustive search means in the context of solving problems like the Traveling Salesman Problem or the Knapsack Problem.
*confidence 0.96 · easy · slides [935, 936, 940, 941, 942, 943]*

**Reference:** Exhaustive search means considering all possible solutions to find the optimal one. For the Traveling Salesman Problem, this means generating all permutations of cities to find the shortest tour. For the Knapsack Problem, it means generating all subsets of items to find the most valuable one that fits in the knapsack. This approach guarantees finding the optimal solution but is computationally expensive.

**Key points** (slide quote → follow-up → expected answer):
- **Exhaustive search considers all possible solutions to find the optimal one.**  
  quote: "The Exhaustive Search solution to the Travelling Salesman problem can be obtained by keeping the origin city constant and generating permutations of all the other n – 1 cities"  
  follow-up: _What is the main drawback of this approach?_  
  expected: The main drawback is that it is computationally expensive, as it requires evaluating a large number of permutations or subsets.
- **Exhaustive search is used for problems where the solution space is discrete and finite.**  
  quote: "The Exhaustive Search solution to the Knapsack Problem is obtained by generating all subsets of the set of n items given and computing the total weight of each subset in order to identify the feasible subsets"  
  follow-up: _Why is this approach called exhaustive?_  
  expected: It is called exhaustive because it explores every possible combination in the solution space without skipping any options.
- **Exhaustive search guarantees finding the optimal solution but is impractical for large problem sizes.**  
  quote: "The Assignment Problem is solved by generating all permutations of n. The number of permutations for a given number n is n! Therefore, the exhaustive search is impractical for all but very small instances of the problem"  
  follow-up: _What makes this approach impractical for large problems?_  
  expected: The number of permutations or subsets grows exponentially with the problem size, making it infeasible for large inputs.

### [N-ary tree to binary tree conversion] Explain how to convert an n-ary tree into a binary tree using the left-child-right-sibling representation.
*confidence 0.96 · easy · slides [563, 568, 569, 570, 571, 572]*

**Reference:** To convert an n-ary tree into a binary tree, we use the left-child-right-sibling representation. This means that the left child in the binary tree is the oldest child of the node in the n-ary tree, and the right child is the next sibling of the left child. The link between siblings is maintained through the right child pointer in the binary tree, while all other links from a node to its children are deleted except for the link to its leftmost child.

**Key points** (slide quote → follow-up → expected answer):
- **The left child in the binary tree is the oldest child of the node in the n-ary tree.**  
  quote: "The left child in binary tree is the node which is the oldest child of the given node in an n-ary tree."  
  follow-up: _What happens if a node has multiple children in the n-ary tree?_  
  expected: The left child in the binary tree is the first child, and the right child is the next sibling, so only the first child is kept as the left child, and the rest are linked through the right child pointer.
- **The right child in the binary tree represents the next sibling of the left child.**  
  quote: "The right child is the node to the immediate right of the given node on the same horizontal line."  
  follow-up: _How do you represent the siblings of a node in the binary tree?_  
  expected: Siblings are represented by linking them through the right child pointer of the left child, so each node's right child points to its next sibling in the original n-ary tree.
- **All links from a node to its children are deleted except for the link to its leftmost child.**  
  quote: "Delete all links from a node to its children except for the link to its leftmost child."  
  follow-up: _Why do we delete all links except for the leftmost child?_  
  expected: We delete all links except for the leftmost child to ensure that the binary tree only has one left child and the rest of the children are represented through the right child pointer as siblings.

### [Topological sorting] Explain what topological sorting is and why it is important for directed acyclic graphs.
*confidence 0.96 · easy · slides [980, 981, 982, 983, 984]*

**Reference:** Topological sorting is listing vertices of a directed graph in such an order that for every edge in the graph, the vertex where the edge starts is listed before the vertex where the edge ends. It is important for directed acyclic graphs (DAGs) because it allows us to linearly order the vertices in a way that respects the direction of edges, which is essential for modeling problems with prerequisite constraints.

**Key points** (slide quote → follow-up → expected answer):
- **Topological sorting is listing vertices of a directed graph in such an order that for every edge in the graph, the vertex where the edge starts is listed before the vertex where the edge ends.**  
  quote: "Topological Sorting: is listing vertices of a directed graph in such an order that for every edge in the graph, the vertex where the edge starts is listed before the vertex where the edge ends."  
  follow-up: _What happens if a directed graph has a cycle?_  
  expected: If a directed graph has a cycle, it is not a DAG, and topological sorting is not possible.
- **Topological sorting is only possible for directed acyclic graphs (DAGs).**  
  quote: "A digraph has a topological sorting iff it is a dag."  
  follow-up: _Why is being a DAG a necessary condition for topological sorting?_  
  expected: Because a cycle in a directed graph makes it impossible to order the vertices such that every edge starts before its destination.
- **Topological sorting is used for modeling problems with prerequisite constraints.**  
  quote: "DAGs arise in modeling many problems that involve prerequisite constraints (construction projects, document version control)."  
  follow-up: _What kind of real-world problems can be modeled using topological sorting?_  
  expected: Problems like construction projects and document version control, where certain tasks or documents must be completed before others.

### [Stack operations] Explain how a stack can be implemented using a linked list.
*confidence 0.96 · easy · slides [624, 625, 626, 627, 628, 629]*

**Reference:** A stack implemented with a linked list uses a pointer called 'top' that points to the head of the list. Push operations insert new nodes at the front of the list, and pop operations remove nodes from the front. This ensures that the most recently added element is always the first to be removed, maintaining the LIFO property.

**Key points** (slide quote → follow-up → expected answer):
- **A stack can be implemented through the linked list.**  
  quote: "A stack can be easily implemented through the linked list."  
  follow-up: _How does the linked list maintain the order of elements in a stack?_  
  expected: The linked list maintains the order by inserting and removing elements at the head of the list, ensuring the last-in is the first-out.
- **Push operation inserts an element at the front of the list.**  
  quote: "Insertion and deletion happens at the front of the list."  
  follow-up: _What happens when you push an element onto a linked list-based stack?_  
  expected: The new element is inserted at the front of the list, making it the new top of the stack.
- **Pop operation removes an element from the front of the list.**  
  quote: "delete an element from the front of the list."  
  follow-up: _What is the effect of popping an element from a linked list-based stack?_  
  expected: The element at the front of the list is removed, and the top pointer is updated to point to the next node in the list.

### [Time and space complexity] Explain what time complexity and space complexity mean in the context of algorithm performance.
*confidence 0.95 · easy · slides [763, 777, 1186, 1476]*

**Reference:** Time complexity refers to the time required for an algorithm to run as a function of input size, while space complexity refers to the memory required. These are key criteria for evaluating algorithm performance. Time efficiency is analyzed by counting the number of repetitions of the basic operation, and space efficiency is about the memory needed for the algorithm to execute.

**Key points** (slide quote → follow-up → expected answer):
- **Time complexity measures the time required for an algorithm to run as a function of input size.**  
  quote: "Time efficiency is analyzed by determining the number of repetitions of the basic operation as a function of input size."  
  follow-up: _What determines how long an algorithm takes to run?_  
  expected: The number of times the basic operation is executed, which depends on the input size.
- **Space complexity measures the memory required for an algorithm to execute.**  
  quote: "Space efficiency - the memory required, also called, space complexity"  
  follow-up: _What is the main factor in how much memory an algorithm uses?_  
  expected: The amount of memory needed to store data and variables during execution.
- **Time and space complexity are key criteria for evaluating algorithm performance.**  
  quote: "important Criteria for performance: - Space efficiency - the memory required, also called, space complexity - Time efficiency - the time required, also called time complexity"  
  follow-up: _Why are time and space complexity important when choosing an algorithm?_  
  expected: They help determine how efficient an algorithm is in terms of both time and memory usage, which affects its practicality and scalability.

### [Tree terminology] Can you explain what a leaf node is in a binary tree and how it differs from a non-leaf node?
*confidence 0.95 · easy · slides [541, 542, 543, 544, 545, 546]*

**Reference:** A leaf node is a node in a binary tree that has no children. This is different from a non-leaf node, which has at least one child. In a binary tree, every node except the root has exactly one parent, and a leaf node is a node that does not have any children. The distinction between leaf and non-leaf nodes is important for understanding tree properties, such as the relationship between the number of leaf nodes and nodes with two children.

**Key points** (slide quote → follow-up → expected answer):
- **A leaf node is a node with no children.**  
  quote: "- A node which has no children is called leaf node/external node"  
  follow-up: _What happens if a node has one child?_  
  expected: It is not a leaf node, because a leaf node must have no children.
- **A non-leaf node has at least one child.**  
  quote: "- A node which has a child is called the non leaf node/internal node"  
  follow-up: _Can a non-leaf node have only one child?_  
  expected: Yes, a non-leaf node can have one child, but it is not a strictly binary tree, as a strictly binary tree requires every node to have either zero or two children.
- **Leaf nodes are important for understanding tree properties.**  
  quote: "- For any non-empty binary tree, if n0 is the number of leaf nodes and n2 the nodes of degree 2, then n0 = n2 + 1"  
  follow-up: _Why is the relationship between leaf nodes and nodes of degree 2 important?_  
  expected: This relationship helps in analyzing and verifying the structure of a binary tree, especially in determining the number of nodes based on the number of leaves.

### [N-ary tree to binary tree conversion] How does the conversion of a forest to a binary tree differ from converting a single n-ary tree to a binary tree, and what implications does this have on the structure of the resulting binary tree?
*confidence 0.91 · medium · slides [563, 568, 569, 570, 571, 572]*

**Reference:** The conversion of a forest to a binary tree involves linking the binary trees of each individual tree in the forest through the right sibling field of the root nodes. This means that the right child of the root node of each tree in the forest becomes the right sibling of the root node of the previous tree. As a result, the binary tree representation of a forest maintains the order of the original trees and allows for a hierarchical representation of multiple trees as a single binary tree.

**Key points** (slide quote → follow-up → expected answer):
- **The right child of the root node of every resulting binary tree is empty when converting a single n-ary tree to a binary tree.**  
  quote: "Right Child of the root node of every resulting binary tree will be empty. This is because the root of the tree we are transforming has no siblings."  
  follow-up: _What happens to the right child of the root node when converting a single n-ary tree to a binary tree?_  
  expected: The right child of the root node is empty because the root has no siblings in a single tree.
- **A forest can be converted into a single binary tree by linking the binary trees of each tree in the forest through the right sibling field of the root nodes.**  
  quote: "Link all the binary trees together through the right sibling field of the root nodes"  
  follow-up: _How is the binary tree representation of a forest structured compared to a single n-ary tree?_  
  expected: The binary tree representation of a forest links each tree's binary tree through the right sibling field of the root nodes, maintaining the order of the original trees.
- **The left subtree of the root node in the binary tree representation of a forest corresponds to the binary tree representation of the subtrees of the root node of the first tree in the forest.**  
  quote: "has left subtree equal to B(T11, T12, ...,T1m) where T11 ,..., T1m are the subtrees of root(T1)"  
  follow-up: _What does the left subtree of the root node represent in the binary tree of a forest?_  
  expected: The left subtree of the root node represents the binary tree of the subtrees of the first tree in the forest.

### [Tries] How does a trie support efficient prefix-based searches, such as in auto-complete features?
*confidence 0.91 · medium · slides [22, 23, 24]*

**Reference:** A trie supports efficient prefix-based searches because each node represents a single character in the string, allowing traversal based on the prefix. This structure enables quick lookup of all words that share a common prefix. For example, inserting 'algorithm' and 'all' into a trie allows the system to quickly find 'all' when a user types 'al', which is essential for auto-complete features.

**Key points** (slide quote → follow-up → expected answer):
- **Trie nodes are linked by individual characters, not the entire key.**  
  quote: "These keys are most often strings, with links between nodes defined not by the entire key, but by individual characters"  
  follow-up: _Why would it be inefficient to link nodes by the entire key instead of individual characters?_  
  expected: Linking by the entire key would require comparing the entire string at each node, which is computationally expensive and slows down search operations.
- **Trie enables quick lookup of all words that share a common prefix.**  
  quote: "Prefix search can be done (Auto complete)"  
  follow-up: _How would you find all words that start with a given prefix using a trie?_  
  expected: You would traverse the trie according to the characters of the prefix. Once the prefix is fully traversed, all words that start with that prefix can be collected by exploring all possible paths from that node.
- **Trie is used in auto-complete features found on Search Engine, Mobile Phone.**  
  quote: "Applications: Dictionary, Auto-complete feature found on Search Engine, Mobile Phone"  
  follow-up: _What advantage does a trie provide for auto-complete that a hash table does not?_  
  expected: A trie allows for efficient prefix-based searches, enabling the system to suggest all possible completions of a partial input, whereas a hash table would require checking each possible variation of the prefix separately.

### [Graph terminology] Explain how the directionality of edges affects the classification of a graph as directed or undirected, and how this relates to the concept of weighted graphs.
*confidence 0.91 · medium · slides [261, 262]*

**Reference:** The directionality of edges determines whether a graph is directed or undirected. In a directed graph, edges have a specific direction, meaning the relationship between vertices is one-way. In contrast, an undirected graph has edges that are unordered, meaning the relationship is mutual. Weighted graphs are a separate classification, where each edge has a numerical value, but this does not affect whether the graph is directed or undirected. A graph can be both directed and weighted, or undirected and weighted, depending on its definition.

**Key points** (slide quote → follow-up → expected answer):
- **The directionality of edges determines whether a graph is directed or undirected.**  
  quote: "A graph is undirected, when the pair of vertices representing any edge is unordered."  
  follow-up: _What happens if the pair of vertices in an edge is ordered?_  
  expected: The graph would be classified as directed, since the edge has a specific direction from one vertex to another.
- **In a directed graph, edges have a specific direction, meaning the relationship between vertices is one-way.**  
  quote: "A graph with all directed edges is called diagraph or directed graph."  
  follow-up: _Can a directed graph have edges that are not directed?_  
  expected: No, by definition, a directed graph consists entirely of directed edges.
- **Weighted graphs are a separate classification, where each edge has a numerical value, but this does not affect whether the graph is directed or undirected.**  
  quote: "A weighted graph is a graph where each edge has a numerical value called weight."  
  follow-up: _Can a graph be both weighted and undirected?_  
  expected: Yes, a graph can be both weighted and undirected, as these are separate classifications.

### [Depth-first search] Explain how depth-first search explores nodes and why it uses a stack-like behavior.
*confidence 0.91 · medium · slides [276]*

**Reference:** Depth-first search explores nodes by visiting all the nodes related to one neighbor before moving to the next. This behavior is analogous to a pre-order traversal of a tree. It uses a stack-like behavior because it processes nodes in a last-in, first-out manner, which is naturally implemented through recursion.

**Key points** (slide quote → follow-up → expected answer):
- **DFS explores nodes by visiting all the nodes related to one neighbor before moving to the next.**  
  quote: "Visits all the nodes related to one neighbour before visiting the other neighbours and its related nodes."  
  follow-up: _What happens if there are multiple paths from a single node?_  
  expected: It will explore one path completely before backtracking and trying another, which is a key characteristic of DFS.
- **DFS is analogous to a pre-order traversal of a tree.**  
  quote: "Analogues to pre-order traversal of an ordered tree"  
  follow-up: _Why is this analogy important for understanding DFS?_  
  expected: Because it highlights the order in which nodes are visited, which is crucial for applications like tree traversal and graph exploration.
- **DFS uses a stack-like behavior due to its recursive implementation.**  
  quote: "Uses stack behaviour, hence implemented using recursive algorithm"  
  follow-up: _How does recursion mimic a stack in DFS?_  
  expected: Recursion mimics a stack by pushing the next node onto the call stack and processing it before returning to the previous node, which mirrors the LIFO behavior of a stack.

### [Merge sort] How does the merge step in merge sort ensure that the final merged array is sorted in the worst case?
*confidence 0.91 · medium · slides [1045, 1046, 1047, 1048, 1049]*

**Reference:** The merge step ensures that the final merged array is sorted in the worst case by comparing the smallest remaining elements of the two sorted subarrays and placing the smaller one into the result array. This process continues until all elements are merged. The worst-case number of key comparisons during merging is n – 1, which is guaranteed because each element is compared at most once during the merge.

**Key points** (slide quote → follow-up → expected answer):
- **The merge step compares the smallest remaining elements of the two sorted subarrays.**  
  quote: "Repeat the following until no elements remain in one of the arrays: compare the first elements in the remaining unprocessed portions of the arrays"  
  follow-up: _What happens if the two subarrays are not sorted?_  
  expected: The merge step would not produce a sorted array because the comparison relies on the subarrays being sorted.
- **The merge step guarantees that each element is compared at most once during the merge.**  
  quote: "The number of key comparisons performed during the merging stage in the worst case is: Cmerge(n) = n – 1"  
  follow-up: _Why is the number of comparisons in the worst case n – 1?_  
  expected: Because each element is compared exactly once during the merge, except for the last element which is copied without comparison.
- **The merge step ensures that the final array is sorted by placing elements in order.**  
  quote: "Merge(B[0 .. p -1], C[0 .. q -1], A[0 .. p + q -1]) //Merges two sorted arrays into one sorted array"  
  follow-up: _What would happen if the merge step did not place elements in order?_  
  expected: The final array would not be sorted, and the merge sort algorithm would fail to produce a correct result.

### [Horspool and Boyer-Moore string matching] Explain how the Boyer-Moore algorithm uses the concept of bad-symbol shift to improve string matching efficiency compared to Horspool’s algorithm.
*confidence 0.91 · medium · slides [1310, 1312, 1327, 1329, 1330]*

**Reference:** The Boyer-Moore algorithm uses the bad-symbol shift to determine how far to shift the pattern when a mismatch occurs. When a mismatch happens at a character c in the text, the algorithm calculates the shift based on the position of c in the pattern. This shift is similar to Horspool’s algorithm but is extended by Boyer-Moore to also consider the good suffix shift. This dual approach allows Boyer-Moore to make larger jumps in the text, improving efficiency in many cases.

**Key points** (slide quote → follow-up → expected answer):
- **The Boyer-Moore algorithm determines the shift size by considering the text’s character c that caused a mismatch with its counterpart in the pattern.**  
  quote: "If the rightmost character of the pattern doesn’t match, BM algorithm acts as Horspool’s"  
  follow-up: _What happens if the rightmost character of the pattern matches?_  
  expected: The algorithm compares preceding characters right to left until a mismatch occurs or all characters match.
- **The bad-symbol shift in Boyer-Moore is computed using the same table as Horspool’s algorithm.**  
  quote: "If c is not in the pattern, we shift the pattern to just pass this c in the text. Conveniently, the size of this shift can be computed by the formula t1(c) − k where t1(c) is the entry in the precomputed table used by Horspool’s algorithm and k is the number of matched characters:"  
  follow-up: _How does the bad-symbol shift differ from the shift in Horspool’s algorithm?_  
  expected: The bad-symbol shift in Boyer-Moore is computed using the same table as Horspool’s algorithm, but it is used in combination with the good suffix shift to allow larger jumps.
- **The bad-symbol shift allows Boyer-Moore to skip over characters in the text that do not match the pattern.**  
  quote: "The first one is guided by the text’s character c that caused a mismatch with its counterpart in the pattern. Accordingly, it is called the bad symbol shift."  
  follow-up: _Why is skipping over characters in the text beneficial for string matching?_  
  expected: Skipping over characters reduces the number of comparisons needed, improving the efficiency of the search.

### [Disjoint sets and union-find] Explain how the union and find operations maintain disjoint subsets in the union-find data structure, and why the structure is useful for tracking elements in multiple sets.
*confidence 0.91 · medium · slides [1366, 1367, 1368, 1370, 1399, 1400]*

**Reference:** The union operation merges two disjoint sets into one, while the find operation identifies the representative of a set. This allows the data structure to efficiently track which elements belong to the same subset. The structure is useful because it supports dynamic merging of sets and quick lookup of set representatives, which is essential for algorithms like Kruskal’s for minimum spanning trees.

**Key points** (slide quote → follow-up → expected answer):
- **The union operation merges two disjoint sets into one.**  
  quote: "Merging two disjoint sets to a single set using Union operation."  
  follow-up: _What happens if you try to merge two elements that are already in the same set?_  
  expected: The union operation would have no effect because the elements are already in the same set.
- **The find operation identifies the representative of a set.**  
  quote: "Finding representative of a disjoint set using Find operation."  
  follow-up: _How does the find operation help in determining if two elements are in the same set?_  
  expected: By finding the representative of each element, you can compare them to check if they belong to the same set.
- **The structure is useful for tracking elements in multiple sets.**  
  quote: "It is a data structure that keeps track of a set of elements partitioned into a number of disjoint (non overlapping) subsets."  
  follow-up: _Why is it important for the data structure to track elements in multiple sets?_  
  expected: It allows efficient merging and querying of sets, which is critical for algorithms that require dynamic connectivity checks.

### [Postfix expression evaluation] Explain how the postfix expression evaluation algorithm ensures that operators are applied to the correct operands.
*confidence 0.91 · medium · slides [697, 698, 699, 700, 701, 702]*

**Reference:** The postfix expression evaluation algorithm ensures that operators are applied to the correct operands by using a stack to store operands as they are read. When an operator is encountered, the top two elements from the stack are popped, and the operator is applied to these two operands. This ensures that each operator always acts on the most recent two operands, which is a key property of postfix notation.

**Key points** (slide quote → follow-up → expected answer):
- **Each operator in a postfix string refers to the previous two operands.**  
  quote: "Each operator in a postfix string refers to the previous two operands."  
  follow-up: _Why is it important for an operator to refer to the previous two operands in a postfix expression?_  
  expected: It is important because this structure ensures that each operator is applied to the most recently available operands, which avoids ambiguity in the order of operations.
- **When an operator is reached, its operands will be the top two elements on the stack.**  
  quote: "When an operator is reached, its operands will be the top two elements on the stack."  
  follow-up: _What would happen if an operator was applied to the wrong operands in a postfix expression?_  
  expected: The result would be incorrect, as the operator would not be applied to the intended operands, leading to a wrong computation.
- **The two elements are popped out, the indicated operation is performed on them and result is pushed on the stack so that it will be available for use as an operand of the next operator.**  
  quote: "The two elements are popped out, the indicated operation is performed on them and result is pushed on the stack so that it will be available for use as an operand of the next operator."  
  follow-up: _Why is it necessary to push the result back onto the stack after performing an operation?_  
  expected: It is necessary to push the result back onto the stack so that it can be used as an operand for subsequent operators, maintaining the correct order of operations in the postfix expression.

### [Stacks and recursion] How does the order of function completion in nested function calls relate to the structure of the stack?
*confidence 0.91 · medium · slides [658, 659, 660, 661, 662]*

**Reference:** The order of function completion in nested function calls follows the last-in, first-out (LIFO) principle, which is the defining characteristic of a stack. This is because each function call adds an activation record to the top of the stack, and when a function completes, its activation record is removed from the top. As a result, the most recently called function is the first to complete, ensuring that the stack maintains the correct execution order.

**Key points** (slide quote → follow-up → expected answer):
- **The sequence of function completion follows the LIFO principle.**  
  quote: "The sequence by which function activity proceeds is summed up as the property last in, first out."  
  follow-up: _What happens if a function completes before the one that called it?_  
  expected: It would violate the LIFO principle and could lead to incorrect program behavior, as the calling function would not have its state properly restored.
- **Each function call adds an activation record to the top of the stack.**  
  quote: "The machine’s task of assigning temporary storage area (activation records) used by functions would be in same order (LIFO)."  
  follow-up: _What would happen if a function call did not add an activation record to the stack?_  
  expected: The program would lose track of the function’s state and return address, making it impossible to resume execution correctly after the function completes.
- **The stack ensures that the most recent function call is the first to complete.**  
  quote: "Since LIFO property is used, the machine allocates these records in the stack."  
  follow-up: _Why is it important for the most recent function call to complete first?_  
  expected: It ensures that the program can correctly return to the caller and maintain the correct execution flow, which is essential for nested and recursive function calls.

### [Parenthesis matching] Explain how the parenthesis matching algorithm ensures that the parentheses are properly nested and matched.
*confidence 0.91 · medium · slides [703, 704, 705, 708]*

**Reference:** The algorithm uses a stack to keep track of opening parentheses. When a closing parenthesis is encountered, it checks the top of the stack to see if it matches. If there is a mismatch, it returns 0. If the stack is empty when a closing parenthesis is encountered, it returns 0. At the end of the expression, if the stack is not empty, it returns 0, indicating extra opening parentheses.

**Key points** (slide quote → follow-up → expected answer):
- **The stack is used to track opening parentheses.**  
  quote: "If the input symbol is one of the open parenthesis ( ‘(‘ , ‘ { ‘ or ‘ [ ‘ ), it is pushed on to the stack"  
  follow-up: _What happens if the algorithm encounters a closing parenthesis before any opening ones?_  
  expected: It would return 0 because the stack would be empty, indicating an extra closing parenthesis.
- **Mismatched parentheses result in an invalid expression.**  
  quote: "If there is a mismatch in the type of the parenthesis, return 0 ( Mismatch of parenthesis)"  
  follow-up: _What if the algorithm encounters a closing square bracket when the top of the stack is a curly brace?_  
  expected: It would return 0 because the types of the parentheses do not match.
- **The algorithm checks for extra opening or closing parentheses at the end of the expression.**  
  quote: "If at the end of the input expression, if the stack is not empty, return 0 ( Extra opening parenthesis)"  
  follow-up: _What if the expression ends with a closing parenthesis and the stack is empty?_  
  expected: It would return 0 because there is an extra closing parenthesis.

### [Insertion sort] Explain how insertion sort builds a sorted array incrementally and why it is considered a decrease and conquer algorithm.
*confidence 0.90 · medium · slides [968, 969, 971, 972, 973, 975]*

**Reference:** Insertion sort builds a sorted array incrementally by expanding the sorted portion of the array one element at a time. It sorts the subarray A[0..i-1] and then inserts A[i] into its correct position in the sorted subarray. This aligns with the decrease and conquer approach, where the problem is reduced to a smaller instance by sorting a smaller subarray and then extending the solution to the larger problem.

**Key points** (slide quote → follow-up → expected answer):
- **Insertion sort builds a sorted array incrementally.**  
  quote: "Insertion sort is based on the idea that one element from the input elements is consumed in each iteration to find its correct position i.e, the position to which it belongs in a sorted array."  
  follow-up: _What happens to the array as the algorithm progresses?_  
  expected: The array grows in size as the sorted portion increases, with each element being inserted into its correct position in the already sorted part.
- **Insertion sort is a decrease and conquer algorithm.**  
  quote: "Decrease and Conquer: ALGORITHM InsertionSort(A[o..n - 1])"  
  follow-up: _How does the algorithm solve a smaller instance of the problem?_  
  expected: It sorts the subarray A[0..i-1] recursively, which is a smaller instance of the original problem, and then inserts the next element into the sorted subarray.
- **The algorithm inserts an element into the correct position in the sorted subarray.**  
  quote: "If the current element is greater, then it leaves the element in its place and moves on to the next element else it finds its correct position in the sorted array and moves it to that position."  
  follow-up: _How does the algorithm find the correct position for an element?_  
  expected: It compares the current element with the elements in the sorted subarray and shifts elements to the right until it finds the correct position for the current element.

### [Heap sort] Explain how heap sort works in two stages.
*confidence 0.82 · easy · slides [1093, 1094, 1095, 1096, 1097, 1098]*

**Reference:** Heap sort is a two-stage algorithm. The first stage constructs a heap from the given array. The second stage repeatedly removes the maximum element from the heap, placing it at the end of the array. This results in the array being sorted in increasing order.

**Key points** (slide quote → follow-up → expected answer):
- **Heap sort is a two-stage algorithm.**  
  quote: "Heap Sort
Two-stage algorithm that works as follows: Stage 1 (heap construction): Construct a heap for a given array. Stage 2 (maximum deletions): Apply the root-deletion operation n − 1 times to the remaining heap."  
  follow-up: _What is the purpose of the first stage in heap sort?_  
  expected: The first stage constructs a heap from the given array, which ensures the largest element is at the root.
- **The result of heap sort is an array sorted in increasing order.**  
  quote: "The resulting array will be exactly the original array sorted in increasing order."  
  follow-up: _Why does heap sort produce an array sorted in increasing order?_  
  expected: Because the maximum elements are removed and placed at the end of the array, the remaining elements are in increasing order.

### [Breadth-first search] Can you explain what breadth-first search does in terms of node exploration?
*confidence 0.82 · easy · slides [281]*

**Reference:** Breadth-first search explores all the neighbour nodes in the first level from an arbitrary node before moving to the next level of neighbouring nodes. This ensures that nodes are visited in order of their distance from the starting node. It uses a queue to manage the order of exploration, which guarantees that each level of nodes is fully processed before moving to the next.

**Key points** (slide quote → follow-up → expected answer):
- **BFS explores all neighbour nodes in the first level before moving to the next level.**  
  quote: "- Explores all the neighbour nodes in first level from an arbitrary node, before moving to next level of neighbouring nodes."  
  follow-up: _Why would it be important to process all nodes at one level before moving to the next?_  
  expected: It ensures that nodes are visited in order of their distance from the starting node, which is crucial for finding the shortest path in unweighted graphs.
- **BFS ensures nodes are visited in order of their distance from the starting node.**  
  quote: "- Explores all the neighbour nodes in first level from an arbitrary node, before moving to next level of neighbouring nodes."  
  follow-up: _How does this property affect the algorithm's use in real-world applications?_  
  expected: This property makes BFS ideal for finding the shortest path in unweighted graphs, such as in network routing or social network connections.

### [Merge sort] Explain how merge sort works in terms of splitting and merging arrays.
*confidence 0.82 · easy · slides [1045, 1046, 1047, 1048, 1049]*

**Reference:** Merge sort works by splitting an array into two halves, sorting each half recursively, and then merging the sorted halves back into a single sorted array. The splitting process continues until the subarrays are of size one, which are inherently sorted. The merging process combines two sorted arrays into one by comparing the front elements of each and placing the smaller one into the result array.

**Key points** (slide quote → follow-up → expected answer):
- **Merge sort splits an array into two halves and sorts each half recursively.**  
  quote: "- Split array A[0..n-1] into about equal halves and make copies of each half in arrays B and C"  
  follow-up: _What happens if the array isn't split into equal halves?_  
  expected: The algorithm still works, but the efficiency may be slightly reduced because the merge step may involve slightly longer arrays.
- **The merge step combines two sorted arrays into one sorted array.**  
  quote: "Merge(B[0 .. p- 1], C[0 .. q -1], A[0 .. p + q -1]) //Merges two sorted arrays into one sorted array"  
  follow-up: _How does the merge process ensure the final array is sorted?_  
  expected: The merge process compares the front elements of each subarray and places the smaller one into the result array, maintaining the sorted order.

### [Dijkstra's algorithm] Explain how Dijkstra’s algorithm finds the shortest paths in a weighted graph.
*confidence 0.82 · easy · slides [1408]*

**Reference:** Dijkstra’s algorithm finds the shortest paths by iteratively selecting the vertex with the smallest tentative distance. It uses a tree of vertices that have already been processed, and for each of these, it considers their outgoing edges to update the shortest path to neighboring vertices. The algorithm ensures that once a vertex is added to the tree, its shortest path is finalized.

**Key points** (slide quote → follow-up → expected answer):
- **Dijkstra’s algorithm selects the vertex with the smallest tentative distance.**  
  quote: "Among vertices not already in the tree, it finds vertex u with the smallest sum dv + w(v,u)."  
  follow-up: _What determines which vertex is selected next in the algorithm?_  
  expected: The vertex with the smallest tentative distance is selected next.
- **The algorithm updates the shortest path to neighboring vertices using outgoing edges.**  
  quote: "w(v,u) is the length (weight) of edge from v to u"  
  follow-up: _How does the algorithm use the weight of an edge to update distances?_  
  expected: The weight of an edge is added to the shortest path to v to compute a potential new shortest path to u.

### [Asymptotic notations] Explain what it means for a function t(n) to be in Ω(g(n)).
*confidence 0.82 · easy · slides [790, 794, 795, 796, 810]*

**Reference:** When a function t(n) is in Ω(g(n)), it means that t(n) is bounded below by some constant multiple of g(n) for all sufficiently large n. This indicates that t(n) grows at least as fast as g(n). The definition requires the existence of a positive constant c and a nonnegative integer n₀ such that t(n) ≥ c·g(n) for all n ≥ n₀. This notation is used to describe the lower bound of the growth rate of a function.

**Key points** (slide quote → follow-up → expected answer):
- **Ω-notation describes a lower bound on the growth rate of a function.**  
  quote: "A function t(n) is said to be in Ω(g(n)), denoted t(n) ∈ Ω(g(n)), if t(n) is bounded below by some constant multiple of g(n) for all large n"  
  follow-up: _What does it mean for a function to be bounded below by another function?_  
  expected: It means that the function grows at least as fast as the other function, up to a constant factor.
- **Ω-notation requires the existence of a positive constant c and a threshold n₀.**  
  quote: "there exist some positive constant c and some nonnegative integer n₀ such that t(n) ≥ c·g(n) for all n ≥ n₀"  
  follow-up: _Why is it important that the inequality holds for all n ≥ n₀?_  
  expected: Because it ensures that the lower bound is valid for sufficiently large input sizes, which is the focus of asymptotic analysis.

### [Skip lists] Explain how a skip list maintains the order of elements across different levels.
*confidence 0.82 · easy · slides [599, 601, 602, 604, 605, 606]*

**Reference:** A skip list maintains the order of elements across different levels by ensuring that each list is a subsequence of the one below it. This means that the elements in a higher level list are a subset of the elements in the lower level list. The lowest level (level 0) contains all the elements in sorted order, while higher levels contain fewer elements, spaced further apart. This structure allows for efficient searching by skipping over large portions of the list at higher levels.

**Key points** (slide quote → follow-up → expected answer):
- **Each list is a subsequence of the previous one.**  
  quote: "Each list is a subsequence of the previous one, i.e., S0 ⊃ S1 ⊃ … ⊃ Sh"  
  follow-up: _What ensures that the elements in a higher level list are not out of order compared to the lower level list?_  
  expected: The structure of the skip list ensures that elements are added in a sorted manner, maintaining the order across all levels.
- **The lowest level contains all elements in sorted order.**  
  quote: "List S0 contains the keys of S in non decreasing order"  
  follow-up: _What happens if the elements in the lowest level are not sorted?_  
  expected: The skip list would not function correctly, as the search and insertion operations rely on the sorted order of elements in the lowest level.

### [Binary tree properties] Consider a complete binary tree. How does the structure of the tree ensure that the number of nodes at the last level is always odd, and what does this imply about the relationship between the depth and the number of nodes?
*confidence 0.81 · hard · slides [547, 548, 549] · ⚠ NEEDS REVIEW*

**Reference:** In a complete binary tree, the structure ensures that any node at level less than d-1 has two children, and for nodes with a right descendent at level d, they must have a left child and all left descendants are either leaves or have two children. This implies that the last level has an odd number of nodes because the tree fills the left side completely before the right. This also means that the depth of the tree is directly related to the number of nodes, as the last level contains the remaining nodes after filling all previous levels completely.

**Key points** (slide quote → follow-up → expected answer):
- **A complete binary tree ensures that any node at level less than d-1 has two children.**  
  quote: "Any node nd at level less than d-1 has two children"  
  follow-up: _What happens if a node at level less than d-1 does not have two children?_  
  expected: The tree would no longer be complete, as the definition requires all nodes at levels less than d-1 to have two children.
- **For nodes with a right descendent at level d, they must have a left child and all left descendants are either leaves or have two children.**  
  quote: "For any node nd of the tree with a right descendent at level d, nd must have a left child and every left descendent of nd is either a leaf at level d or has two children"  
  follow-up: _Why is it important that the left descendants are either leaves or have two children?_  
  expected: This ensures that the tree fills the left side completely before the right, which leads to an odd number of nodes at the last level.
- **The last level of a complete binary tree has an odd number of nodes.**  
  quote: "For a Complete Binary Tree with n nodes and depth d: ... For any node nd of the tree with a right descendent at level d, nd must have a left child and every left descendent of nd is either a leaf at level d or has two children"  
  follow-up: _How does the depth of the tree relate to the number of nodes in the last level?_  
  expected: The depth determines the level where the last nodes are placed, and the structure ensures that the number of nodes at that level is always odd.

### [Iterative tree traversals] Explain how the iterative preorder traversal works using the code provided.
*confidence 0.81 · easy · slides [317, 318, 323, 328, 329, 330]*

**Reference:** In the iterative preorder traversal, the root node is pushed onto the stack first. Then, nodes are popped from the stack, printed, and their right child is pushed before the left child, ensuring the left subtree is processed first. This order mimics the recursive preorder traversal, where the node is visited before its children. The traversal continues until the stack is empty.

**Key points** (slide quote → follow-up → expected answer):
- **The root node is pushed onto the stack first.**  
  quote: "s = emptyStack push(s, current)"  
  follow-up: _Why is the root node pushed onto the stack first?_  
  expected: Because the root is the first node to be processed in preorder traversal, and pushing it first ensures it is processed before its children.
- **Right child is pushed before the left child.**  
  quote: "right child is pushed first so that left is processed first"  
  follow-up: _Why is the right child pushed before the left child?_  
  expected: To ensure the left child is processed before the right child, which follows the preorder traversal order of visiting the node before its children.

### [Binary search tree deletion] Explain how to delete a node from a binary search tree that has two children.
*confidence 0.81 · easy · slides [185, 187, 189, 190, 191, 1204]*

**Reference:** To delete a node with two children in a binary search tree, you replace the node's value with its inorder successor or predecessor. This changes the problem to deleting a node with one or no children, which is simpler. The inorder successor is the smallest value in the right subtree, and the inorder predecessor is the largest value in the left subtree. After replacing the node's value, you then delete the inorder successor or predecessor, which may involve one or no children.

**Key points** (slide quote → follow-up → expected answer):
- **Replace the node with its inorder successor or predecessor.**  
  quote: "To delete the node with info 5: - Replace 5 with its inorder successor and delete that inorder successor"  
  follow-up: _What happens if the node has two children and you want to maintain the binary search tree properties?_  
  expected: You replace the node's value with the inorder successor or predecessor to maintain the binary search tree properties.
- **The choice between inorder successor and predecessor is arbitrary.**  
  quote: "To delete the node with info 5: - Replace 5 with its inorder predecessor and delete that inorder predecessor"  
  follow-up: _Can you delete a node with two children by using either the inorder successor or predecessor?_  
  expected: Yes, you can choose either the inorder successor or predecessor, and the choice does not affect the correctness of the deletion.

### [Binary search] What is the significance of the 'extend solution of smaller instance to obtain solution to original problem' step in the context of binary search?
*confidence 0.81 · hard · slides [834, 968, 969] · ⚠ NEEDS REVIEW*

**Reference:** In binary search, the 'extend solution of smaller instance to obtain solution to original problem' step is critical because it allows the algorithm to combine the results of the smaller subproblems into a solution for the original problem. This step is necessary because, after reducing the problem size by half, the algorithm must determine how to use the information from the smaller instance to find the target in the original instance. The process of extending the solution is implicit in the decision to move left or right in the array, based on the comparison with the middle element.

**Key points** (slide quote → follow-up → expected answer):
- **Binary search uses the result of smaller instances to make decisions about the original problem.**  
  quote: "Extend solution of smaller instance to obtain solution to original problem."  
  follow-up: _How does binary search use the result of a smaller instance to solve the original problem?_  
  expected: Binary search uses the result of a smaller instance to decide whether to search the left or right half of the array, effectively narrowing down the search space.
- **Binary search is a recursive algorithm that reduces the problem to smaller instances.**  
  quote: "Decrease-by-a-constant-factor recurrences. Example: binary search. The recurrence has the form T(n) = aT(n/b) + f (n)."  
  follow-up: _What does the recurrence T(n) = aT(n/b) + f(n) represent in the context of binary search?_  
  expected: This recurrence represents the time complexity of binary search, where each recursive call reduces the problem size by a constant factor, and the f(n) term accounts for the cost of comparing the middle element with the target.
- **The 'extend solution' step is essential for the algorithm to function correctly.**  
  quote: "Exploit the relationship between a solution to a given instance of a problem and a solution to its smaller instance."  
  follow-up: _Why is it important to exploit the relationship between the solution to a smaller instance and the original problem in binary search?_  
  expected: It is important because binary search relies on the fact that the solution to a smaller instance (e.g., finding the target in a smaller subarray) directly informs the solution to the original problem, allowing the algorithm to efficiently narrow down the search space.

### [Graph connectivity and path finding] What happens to the graph's connectivity if we remove all edges that are part of any path from a source to a destination in a connected graph?
*confidence 0.81 · hard · slides [70, 71, 72, 73, 97, 98] · ⚠ NEEDS REVIEW*

**Reference:** Removing all edges that are part of any path from a source to a destination in a connected graph can potentially disconnect the graph. If the source and destination are the only nodes connected by those edges, the graph becomes disconnected. However, if there are alternative paths between other nodes, the graph might remain connected. The core idea is that the removal of edges that support a specific path can affect the overall connectivity of the graph.

**Key points** (slide quote → follow-up → expected answer):
- **Removing all edges that are part of any path from a source to a destination can disconnect the graph.**  
  quote: "A graph is connected if there is a path between every pair of vertices."  
  follow-up: _What would happen if the only path between two nodes was removed?_  
  expected: The graph would become disconnected because there is no longer a path between those two nodes.
- **The removal of edges can affect the overall connectivity of the graph, even if other paths remain.**  
  quote: "In connected graph there is no unreachable vertex."  
  follow-up: _Can the graph still be connected if some paths are removed?_  
  expected: Yes, if there are still other paths between nodes, the graph can remain connected.
- **The connectivity of a graph is determined by the existence of paths between all pairs of nodes.**  
  quote: "Connectivity refers to connection between two or more nodes or things."  
  follow-up: _How does the removal of edges affect the connectivity of the entire graph?_  
  expected: It can reduce the connectivity, potentially turning a connected graph into a disconnected one.

### [Insertion sort] What happens to the sorted subarray during insertion sort and why is this property important for the algorithm’s performance?
*confidence 0.81 · hard · slides [968, 969, 971, 972, 973, 975] · ⚠ NEEDS REVIEW*

**Reference:** During insertion sort, the sorted subarray grows by one element in each iteration. The algorithm maintains the sorted subarray by inserting the current element into its correct position within it. This property is important because it ensures that the algorithm only needs to compare and shift elements within the sorted subarray, which limits the number of operations and makes it efficient for small or nearly sorted arrays.

**Key points** (slide quote → follow-up → expected answer):
- **The sorted subarray grows by one element in each iteration.**  
  quote: "To sort array A[0..n-1], sort A[0..n-2] recursively and then insert A[n-1] in its proper place among the sorted A[0..n-2]"  
  follow-up: _What happens to the size of the sorted subarray as the algorithm progresses?_  
  expected: The size of the sorted subarray increases by one element in each iteration.
- **The algorithm maintains the sorted subarray by inserting the current element into its correct position.**  
  quote: "If the current element is greater, then it leaves the element in its place and moves on to the next element else it finds its correct position in the sorted array and moves it to that position."  
  follow-up: _How does the algorithm ensure that the sorted subarray remains sorted after inserting a new element?_  
  expected: It shifts all elements larger than the current element to one position ahead, making space for the current element in its correct position.
- **This property makes insertion sort efficient for small or nearly sorted arrays.**  
  quote: "Cbest(n) = n - 1 ∈ Θ(n) (also fast on almost sorted arrays)"  
  follow-up: _Why is insertion sort considered efficient for nearly sorted arrays?_  
  expected: Because it only needs to perform a minimal number of comparisons and shifts when the array is already mostly sorted.

### [Brute force sorting] Explain how selection sort ensures that elements are placed in their final positions during each pass, and what this implies about the algorithm's behavior.
*confidence 0.80 · hard · slides [863, 864, 865, 870, 873, 874] · ⚠ NEEDS REVIEW*

**Reference:** Selection sort ensures that elements are placed in their final positions during each pass by finding the smallest element in the unsorted portion of the array and swapping it with the element at the current pass index. This means that after each pass, the smallest unsorted element is moved to its correct position in the sorted portion of the array. The implication is that the algorithm progressively builds the sorted array from left to right, with each pass fixing one element in its final place.

**Key points** (slide quote → follow-up → expected answer):
- **Selection sort ensures that elements are placed in their final positions during each pass.**  
  quote: "A[0] ≤ A[1] ≤ A[2] … ≤ A[i-1] | A[i], ….., A[min], …., A[n-1] in their final positions the last n – i elements"  
  follow-up: _What happens to the elements after the current pass in selection sort?_  
  expected: After each pass, the elements up to the current index are in their final positions, and the remaining elements are unsorted, but the smallest of them is now in its correct place.
- **During each pass, the smallest element in the unsorted portion is identified and moved to its correct position.**  
  quote: "Generally, on pass i (0 ≤ i ≤ n-2), find the smallest element in A[i..n-1] and swap it with A[i]."  
  follow-up: _What is the significance of the pass index in selection sort?_  
  expected: The pass index determines the position in the array where the smallest element from the unsorted portion is placed, ensuring that each pass adds one element to the sorted portion of the array.
- **The algorithm progressively builds the sorted array from left to right.**  
  quote: "A[0] ≤ A[1] ≤ A[2] … ≤ A[i-1] | A[i], ….., A[min], …., A[n-1] in their final positions the last n – i elements"  
  follow-up: _How does the algorithm maintain the sorted portion of the array?_  
  expected: The algorithm maintains the sorted portion by ensuring that once an element is placed in its final position, it is not disturbed in subsequent passes, allowing the algorithm to build the sorted array incrementally.

### [Asymptotic notations] Explain how Ω-notation and Θ-notation differ in their use for analyzing the growth rate of functions.
*confidence 0.78 · medium · slides [790, 794, 795, 796, 810]*

**Reference:** Ω-notation provides a lower bound on the growth rate of a function, meaning that the function grows at least as fast as g(n). Θ-notation, on the other hand, provides a tight bound, meaning that the function grows at the same rate as g(n). The key difference is that Θ requires both an upper and lower bound, while Ω only requires a lower bound. This distinction is important when analyzing the best-case and average-case performance of algorithms.

**Key points** (slide quote → follow-up → expected answer):
- **Ω-notation describes a lower bound on the growth rate of a function.**  
  quote: "A function t(n) is said to be in Ω(g(n)), denoted t(n) ∈ Ω(g(n)), if t(n) is bounded below by some constant multiple of g(n) for all large n"  
  follow-up: _What does it mean for a function to be bounded below by a constant multiple of another function?_  
  expected: It means that for sufficiently large n, the function t(n) will always be greater than or equal to a constant multiple of g(n).
- **Ω-notation is used for lower bounds, while Θ-notation is used for tight bounds.**  
  quote: "Figure 2.3 Big-theta notation: t(n) ∈(g(n))"  
  follow-up: _When would you use Ω-notation instead of Θ-notation?_  
  expected: You would use Ω-notation when you want to describe the minimum growth rate of a function, such as in the best-case scenario of an algorithm.

### [Circular queue] Explain how the structure of a circular queue allows it to avoid the issue of space being locked in the front of the queue.
*confidence 0.78 · medium · slides [476, 477]*

**Reference:** A circular queue avoids the issue of space being locked in the front by allowing the rear pointer to wrap around to the beginning of the array. This means that even after elements are removed from the front, the rear can continue to move forward, reusing the freed space. The structure of the circular queue behaves like a circular data structure, which enables the queue to make use of all available space efficiently.

**Key points** (slide quote → follow-up → expected answer):
- **The circular queue reuses space that was previously occupied by removed elements.**  
  quote: "In a simple queue, once the queue is completely full, it's not possible to insert more elements. Even if we perform remove operation on the queue to remove some of the elements, until the queue is reset, no new elements can be inserted."  
  follow-up: _How does a circular queue differ from a simple queue in terms of space reuse?_  
  expected: A circular queue reuses space by allowing the rear pointer to move to the beginning of the array after elements are removed.
- **The structure of a circular queue behaves like a circular data structure.**  
  quote: "Circular Queue is a linear data structure, which follows the principle of FIFO(First In First Out), but instead of ending the queue at the last position, it again starts from the first position after the last, hence making the queue behave like a circular data structure."  
  follow-up: _Why is the circular queue described as behaving like a circular data structure?_  
  expected: Because the rear pointer can wrap around to the beginning of the array, making the queue appear circular in its behavior.

### [Iterative tree traversals] Explain how the iterative postorder traversal handles the order of processing nodes using the code provided.
*confidence 0.78 · medium · slides [317, 318, 323, 328, 329, 330]*

**Reference:** The iterative postorder traversal uses two stacks to simulate the recursive process. The first stack (s1) is used to process nodes by pushing them onto the second stack (s2) in reverse order. This ensures that nodes are printed in the correct postorder sequence—left, right, then root. The second stack (s2) stores nodes in the order they should be printed, and the traversal continues until s1 is empty.

**Key points** (slide quote → follow-up → expected answer):
- **The iterative postorder traversal uses two stacks to simulate the recursive process.**  
  quote: "iterativePostorder(root) s1 = emptyStack ; s2 = emptyStack ; push(s1, root)"  
  follow-up: _Why is it necessary to use two stacks instead of one?_  
  expected: Two stacks are used to separate the processing of nodes from the printing of nodes, ensuring that the correct order is maintained.
- **The second stack (s2) stores nodes in the order they should be printed.**  
  quote: "while(!isEmpty(s2)) { //Print all the elements of stack2 print current->info }"  
  follow-up: _Why is the printing done after s1 is empty?_  
  expected: Because s1 is used to process and push nodes onto s2 in the correct order, and s2 is then used to print them in postorder.

### [Expression trees] Explain how the construction of an expression tree using a postfix notation ensures that the resulting tree can be evaluated correctly.
*confidence 0.78 · medium · slides [218, 219, 220, 224, 225, 226]*

**Reference:** The construction of an expression tree using postfix notation ensures correct evaluation by leveraging the stack-based approach. When an operator is encountered, the two most recent operands are popped from the stack and used as children of the new operator node. This ensures that the operator is applied to the correct operands in the correct order. The final root of the tree represents the entire expression, allowing for a straightforward evaluation from the leaves up to the root.

**Key points** (slide quote → follow-up → expected answer):
- **The stack is used to temporarily store operand nodes during the construction of the expression tree.**  
  quote: "If symbol is an operand, push address of node to stack"  
  follow-up: _What happens if you tried to build the tree without using a stack?_  
  expected: You would not be able to correctly associate operators with their operands, leading to an incorrect tree structure and invalid evaluation.
- **The final node on the stack becomes the root of the expression tree.**  
  quote: "Finally, stack has only element which is the 100 address of the root of expression tree"  
  follow-up: _What would happen if the stack had more than one element at the end of the construction?_  
  expected: It would indicate that the postfix expression is invalid, as there are more operands than operators, or that the operators were not properly applied to their operands.

### [Open addressing] Explain how quadratic probing differs from linear probing in open addressing, and why one might be preferred over the other in certain scenarios.
*confidence 0.78 · medium · slides [30, 31, 38, 39, 40, 41]*

**Reference:** Quadratic probing uses a formula of (h(key) + i²) % tableSize to resolve collisions, while linear probing uses (h(key) + i) % tableSize. This difference leads to a more even distribution of keys in quadratic probing, reducing primary clustering. Linear probing is simpler to implement but can lead to clustering, making quadratic probing more efficient in scenarios with high collision rates.

**Key points** (slide quote → follow-up → expected answer):
- **Quadratic probing uses the formula (h(key) + i²) % tableSize to resolve collisions.**  
  quote: "h(key) = ( h(key) + i^2 ) % tableSize where i = 1, 2, 3, …"  
  follow-up: _What happens if two keys hash to the same index in a quadratic probing table?_  
  expected: The algorithm uses i² to find the next available slot, which helps reduce clustering compared to linear probing.
- **Linear probing uses the formula (h(key) + i) % tableSize to resolve collisions.**  
  quote: "h(key) = ( h(key) + i ) % tableSize where i = 1, 2, 3, …"  
  follow-up: _Why might linear probing be less efficient than quadratic probing in some cases?_  
  expected: Linear probing can lead to primary clustering, where consecutive collisions cause keys to cluster together, reducing performance.

### [Topological sorting] How does the DFS-based algorithm for topological sorting ensure that the resulting order is valid for a directed acyclic graph?
*confidence 0.78 · medium · slides [980, 981, 982, 983, 984]*

**Reference:** The DFS-based algorithm for topological sorting ensures validity by processing vertices in such a way that all dependencies are respected. It performs a DFS traversal and records the order in which vertices are popped off the traversal stack. The final topological order is obtained by reversing this order. This method works because, in a DAG, there are no cycles, so the DFS traversal will not encounter back edges, which would indicate a cycle.

**Key points** (slide quote → follow-up → expected answer):
- **The DFS-based algorithm relies on the traversal order to determine the topological sequence.**  
  quote: "Perform DFS traversal, noting the order vertices are popped off the traversal stack. Reverse order solves topological sorting problem."  
  follow-up: _What happens if the DFS traversal encounters a back edge?_  
  expected: It indicates the presence of a cycle, meaning the graph is not a DAG and topological sorting is not possible.
- **The algorithm is only applicable to DAGs.**  
  quote: "A digraph has a topological sorting iff it is a dag."  
  follow-up: _Why is the algorithm not applicable to graphs with cycles?_  
  expected: Because cycles would cause the DFS traversal to encounter back edges, which would invalidate the topological order and make it impossible to determine a valid sequence.

### [Dijkstra's algorithm] Explain how the selection of the next vertex in Dijkstra’s algorithm depends on the structure of the graph and the current state of the algorithm.
*confidence 0.78 · medium · slides [1408]*

**Reference:** Dijkstra’s algorithm selects the next vertex based on the smallest tentative distance from the source, which is computed as dv + w(v,u). This value depends on the current shortest path to vertex v and the weight of the edge from v to u. The algorithm ensures that once a vertex is added to the tree, its shortest path is finalized, which affects how the remaining vertices are processed.

**Key points** (slide quote → follow-up → expected answer):
- **The next vertex is selected based on the smallest dv + w(v,u).**  
  quote: "Among vertices not already in the tree, it finds vertex u with the smallest sum dv + w(v,u)."  
  follow-up: _What happens if two vertices have the same dv + w(v,u) value?_  
  expected: The algorithm can select either vertex arbitrarily, as both would result in the same shortest path length.
- **Once a vertex is added to the tree, its shortest path is finalized.**  
  quote: "v is a vertex for which shortest path has been already found on preceding iterations (such vertices form a tree rooted at s)."  
  follow-up: _Why is it important that the shortest path to a vertex is finalized once it is added to the tree?_  
  expected: Finalizing the shortest path ensures that no further updates to that vertex are needed, which optimizes the algorithm’s efficiency.

### [Suffix tries and suffix trees] Explain how a suffix tree differs from a suffix trie and why this compression is useful for string operations.
*confidence 0.78 · medium · slides [10, 11, 12, 13, 14, 15]*

**Reference:** A suffix tree is a compressed version of a suffix trie, which reduces the number of nodes by merging chains of single nodes. This compression makes the suffix tree more efficient in terms of space and allows for faster string operations. The suffix tree stores all suffixes of a text, enabling efficient pattern matching and prefix matching queries.

**Key points** (slide quote → follow-up → expected answer):
- **The compression merges chains of single nodes.**  
  quote: "Join chains of single nodes, to get the following compressed trie, which is the Suffix tree for given text 'banana$'"  
  follow-up: _What is the benefit of merging single-node chains?_  
  expected: It reduces the number of nodes and makes the tree more compact and efficient.
- **Suffix trees support efficient pattern matching and prefix matching.**  
  quote: "Allow many fast implementations of many important string operations"  
  follow-up: _How does the structure of a suffix tree enable efficient pattern matching?_  
  expected: The tree structure allows for direct traversal based on the characters of the pattern, enabling quick search operations.

### [Recurrence relations] Explain how the Master Theorem determines the time complexity of a recurrence relation based on the relationship between a, b, and d.
*confidence 0.77 · medium · slides [1039]*

**Reference:** The Master Theorem evaluates the time complexity of a recurrence relation by comparing the function f(n) to n^d. If f(n) is Θ(n^d), then the theorem uses the relative sizes of a and b^d to determine the dominant term. When a < b^d, the complexity is dominated by f(n), resulting in Θ(n^d). When a = b^d, the complexity includes a logarithmic factor, leading to Θ(n^d log n). When a > b^d, the recursive part dominates, resulting in Θ(n^{log_b a}).

**Key points** (slide quote → follow-up → expected answer):
- **The Master Theorem determines time complexity by comparing f(n) to n^d.**  
  quote: "If f(n) ∈Θ(nd), where d >= 0 in the recurrence relation, then:"  
  follow-up: _What happens if f(n) is not in Θ(n^d)?_  
  expected: The Master Theorem does not apply directly, and other methods like the recursion tree or substitution method must be used.
- **When a < b^d, the time complexity is dominated by f(n).**  
  quote: "If a < bd, T(n) ∈Θ(nd)"  
  follow-up: _Why would the non-recursive part dominate the time complexity?_  
  expected: Because the cost of the subproblems is smaller than the cost of solving the problem at each level, so the total cost is dominated by the work done at the top level.
- **When a = b^d, the time complexity includes a logarithmic factor.**  
  quote: "If a = bd, T(n) ∈Θ(nd log n)"  
  follow-up: _What role does the logarithmic factor play in the time complexity?_  
  expected: The logarithmic factor accounts for the increasing number of levels in the recursion tree, which adds an extra multiplicative factor to the time complexity.

### [Binary tree properties] Explain how the relationship between leaf nodes and degree-2 nodes in a binary tree helps us understand the structure of a full binary tree.
*confidence 0.77 · medium · slides [547, 548, 549]*

**Reference:** In a non-empty binary tree, the number of leaf nodes is always one more than the number of nodes with two children. This property is a fundamental characteristic of binary trees and helps in understanding how nodes are distributed. A full binary tree, which has all leaves at the same level, follows this rule and has a total number of nodes that is 2^(d+1) - 1, where d is the depth. This relationship ensures that the tree is balanced and fully populated at every level.

**Key points** (slide quote → follow-up → expected answer):
- **The number of leaf nodes is one more than the number of degree-2 nodes.**  
  quote: "For any non-empty binary tree, if n0 is the number of leaf nodes and n2 the nodes of degree 2, then n0 = n2 + 1"  
  follow-up: _What happens if you have a binary tree with two leaf nodes and one degree-2 node?_  
  expected: That would not be a valid binary tree, since the relationship n0 = n2 + 1 must hold.
- **A full binary tree has all leaves at the same level.**  
  quote: "A binary tree with all the leaves at the same level"  
  follow-up: _How does this property affect the total number of nodes in the tree?_  
  expected: It ensures that the tree is completely filled at every level, which results in a total of 2^(d+1) - 1 nodes for a tree of depth d.

### [Heap construction] Explain how the bottom-up heap construction algorithm ensures that the final array represents a valid max-heap.
*confidence 0.77 · medium · slides [244, 385, 386, 387, 388, 389]*

**Reference:** The bottom-up heap construction algorithm starts from the middle of the array and works backward to the root, ensuring that each node satisfies the max-heap property. At each step, it compares the current node with its children and swaps them if necessary, maintaining the heap property. This process continues until the entire array is processed, resulting in a valid max-heap.

**Key points** (slide quote → follow-up → expected answer):
- **The algorithm compares a node with its children and swaps them if necessary.**  
  quote: "if v ≥ H[j] //if key of parent node ≥ key of largest child //it’s a heap"  
  follow-up: _What happens if the parent node is smaller than its child?_  
  expected: The algorithm swaps the parent with the largest child, ensuring the max-heap property is maintained at that level.
- **The algorithm ensures that the final array represents a valid max-heap.**  
  quote: "Heap Construction – Bottom Up ALGORITHM HeapBottomUp(H[1…n]) //Constructs a heap from the elements of a given array by bottom-up algorithm"  
  follow-up: _How does the algorithm ensure that all nodes satisfy the max-heap property?_  
  expected: By iteratively applying the heapify process starting from the middle of the array and moving upward, the algorithm ensures that every node is greater than or equal to its children.

### [Binary search] Explain how binary search uses the decrease-by-a-constant-factor approach to solve a problem efficiently.
*confidence 0.77 · medium · slides [834, 968, 969]*

**Reference:** Binary search uses the decrease-by-a-constant-factor approach by dividing the problem size by two at each step. This is reflected in the recurrence T(n) = aT(n/b) + f(n), where a = 1, b = 2. The algorithm exploits the relationship between a solution to a given instance and a smaller instance by comparing the target with the middle element, thereby reducing the problem size by half each time.

**Key points** (slide quote → follow-up → expected answer):
- **Binary search reduces the problem size by a constant factor at each step.**  
  quote: "A decrease-by-a-constant-factor algorithm solves a problem by dividing its given instance of size n into several smaller instances of size n/b, solving each of them recursively, and then, if necessary, combining the solutions to the smaller instances into a solution to the given instance."  
  follow-up: _What happens to the problem size after each step in binary search?_  
  expected: The problem size is halved after each step, as the algorithm focuses on one half of the array.
- **Binary search is a recursive algorithm that reduces the problem to smaller instances.**  
  quote: "This usually results in a recursive algorithm."  
  follow-up: _Can binary search be implemented iteratively? Why or why not?_  
  expected: Yes, it can be implemented iteratively, but the recursive approach naturally aligns with the decrease-by-a-constant-factor strategy.

### [Double-ended queue] Explain how the delete operations in a double-ended queue differ between array and doubly linked list implementations.
*confidence 0.76 · medium · slides [504, 505, 506, 507, 508, 509]*

**Reference:** In the array implementation, delete operations require checking for empty conditions and managing wrap-around indices, while in the doubly linked list implementation, deletions are handled by updating pointers of adjacent nodes. Both implementations must handle edge cases like single-element queues. The array implementation uses index arithmetic, whereas the linked list approach uses pointer manipulation. These differences reflect the structural differences between the two data representations.

**Key points** (slide quote → follow-up → expected answer):
- **In the array implementation, delete operations require checking for empty conditions and managing wrap-around indices.**  
  quote: "Delete element at Rear end Delete element at front end check if the queue is empty check if the queue is empty delete the element pointed by rear delete the element pointed by front"  
  follow-up: _What happens if the queue has only one element during a delete operation?_  
  expected: The front and rear pointers are both set to NULL to indicate an empty queue.
- **In the doubly linked list implementation, deletions are handled by updating pointers of adjacent nodes.**  
  quote: "struct node *q; int x; if(dq->front==NULL) return -1; q=dq->rear; x=q->data; if(dq->front==dq->rear) dq->front=dq->rear=NULL; dq->rear=dq->rear->prev; dq->rear->next=NULL; free(q); return x;"  
  follow-up: _How does the linked list implementation handle the deletion of the last node?_  
  expected: Both the front and rear pointers are set to NULL to indicate an empty queue, and the node is freed.

---

## Held back (low confidence — not used by the app)

### [Best, worst and average case] Explain the difference between best-case and worst-case efficiency for the sequential search algorithm, and why the average case is not simply the average of the two.
*confidence 0.75 · medium · slides [783, 784, 785, 786]*

**Reference:** The best-case efficiency for sequential search is when the target element is found at the first position, requiring only one comparison. The worst-case efficiency is when the target is not present or is at the last position, requiring n comparisons. The average case is not the average of these two because it considers the distribution of all possible inputs, not just the extremes.

**Key points** (slide quote → follow-up → expected answer):
- **Best-case efficiency is when the target is found at the first position.**  
  quote: "Best case: The algorithm runs the fastest among all possible inputs of size n."  
  follow-up: _What happens if the target is found immediately in the list?_  
  expected: The algorithm would terminate after the first comparison, which is the best-case scenario.
- **Average-case is not the average of best and worst-case.**  
  quote: "Average case: The algorithm runs the fastest among all possible inputs of size n. How to find the average case efficiency? NOT the average of worst and best case"  
  follow-up: _Why is the average case not calculated as the average of best and worst?_  
  expected: Because average case considers the probability distribution of inputs, not just the extremes, and is derived from analyzing all possible cases.

### [Graph representation] Explain how adjacency list representation differs from adjacency matrix representation in terms of space complexity.
*confidence 0.74 · easy · slides [135, 139, 140, 295]*

**Reference:** The adjacency list representation has a space complexity of O(V+E), as it stores only the information of edges that actually exist in the graph. In contrast, the adjacency matrix representation uses a fixed amount of space based on the number of vertices, regardless of the number of edges. This makes adjacency list more efficient for sparse graphs with fewer edges. The adjacency list is better suited for low density graphs because it avoids storing unnecessary zero entries that are present in the adjacency matrix.

**Key points** (slide quote → follow-up → expected answer):
- **The space complexity of adjacency list is O(V+E).**  
  quote: "Space Complexity of Adjacency list is O(V+E), because it stores the information of edges that actually exists in the graph"  
  follow-up: _Why would you prefer adjacency list over adjacency matrix for a graph with many vertices but few edges?_  
  expected: Because adjacency list only stores existing edges, it uses less space for sparse graphs.
- **Adjacency list is more efficient for sparse graphs.**  
  quote: "In case of low density edges, the adjacency matrix becomes sparse using adjacency list is better for representation"  
  follow-up: _What does it mean for a graph to be sparse?_  
  expected: It means the graph has relatively few edges compared to the total possible number of edges.

### [Simple queue] Explain how the simple queue's structure leads to a potential space wastage, and how this issue is resolved in a circular queue.
*confidence 0.70 · medium · slides [447, 449, 477, 504, 505, 506]*

**Reference:** The simple queue's structure uses a linear array with front and rear pointers, which can lead to space wastage when elements are removed from the front, leaving unused space at the beginning of the array. This issue is resolved in a circular queue by wrapping around the array, allowing the rear to move to the beginning of the queue after the front has moved past the end.

**Key points** (slide quote → follow-up → expected answer):
- **The simple queue's structure leads to space wastage when elements are removed from the front.**  
  quote: "Cannot insert even after two elements are removed and Space available in the front."  
  follow-up: _What happens to the unused space in the queue when elements are removed from the front?_  
  expected: The unused space remains at the front of the array, making it unavailable for new insertions.
- **A circular queue resolves the space wastage issue by allowing the rear to wrap around to the beginning of the array.**  
  quote: "It is possible to insert in a circular queue by moving the rear rear front to the beginning of the queue"  
  follow-up: _How does a circular queue avoid the space wastage problem of a simple queue?_  
  expected: A circular queue wraps around the array, allowing the rear to reuse the space at the front once it has been freed.

### [Threaded binary search tree] Explain how a Right-In Threaded Binary Tree avoids the need for an explicit stack during an in-order traversal, and how the rthread field is used in this process.
*confidence 0.70 · medium · slides [202, 203, 205, 206, 207, 208]*

**Reference:** A Right-In Threaded Binary Tree avoids the need for an explicit stack during in-order traversal by using the right pointer to point to the inorder successor when it is not a child. This allows the traversal to continue without backtracking. The rthread field indicates whether the right pointer is a thread (i.e., points to the inorder successor) or a real child. This mechanism allows the traversal to proceed efficiently by following threads instead of using a stack.

**Key points** (slide quote → follow-up → expected answer):
- **A Right-In Threaded Binary Tree avoids the need for an explicit stack during in-order traversal by using the right pointer to point to the inorder successor when it is not a child.**  
  quote: "We can use the right pointer of a node to point to the inorder successor if in case it is not pointing to the child. Such a tree is called Right-In Threaded Binary Tree"  
  follow-up: _What is the purpose of having a right pointer that points to the inorder successor?_  
  expected: The purpose is to allow traversal to continue without backtracking, eliminating the need for an explicit stack.
- **This mechanism allows the traversal to proceed efficiently by following threads instead of using a stack.**  
  quote: "If this can be achieved through some other less expensive mechanism, we can eliminate the use of explicit stack"  
  follow-up: _Why is using a thread considered less expensive than using a stack?_  
  expected: Using a thread is less expensive because it avoids the overhead of stack operations, allowing traversal to proceed with simple pointer manipulation.

### [Hash functions] Explain how double hashing resolves collisions in a hash table, and why it is considered more efficient than linear probing in certain scenarios.
*confidence 0.70 · medium · slides [32, 34, 47, 48, 49, 50]*

**Reference:** Double hashing resolves collisions by using a second hash function to compute a sequence of alternative positions within the hash table. This avoids the clustering issues that can occur with linear probing, where consecutive collisions lead to predictable patterns. The formula used is hash(key) = (hash1(key) + i * hash2(key)) % tableSize, where i is an incrementing integer. This method distributes keys more uniformly, which can improve performance in scenarios with high collision rates.

**Key points** (slide quote → follow-up → expected answer):
- **Double hashing uses a second hash function to compute alternative positions when a collision occurs.**  
  quote: "Double Hashing (Open addressing, closed hashing) resolves collision by using a second hash function whenever there results a collision."  
  follow-up: _What happens if the second hash function returns a value of zero?_  
  expected: If the second hash function returns zero, the formula would result in the same initial hash value, which could lead to an infinite loop unless the hash table is designed to handle such cases.
- **The second hash function is used to generate a sequence of alternative positions.**  
  quote: "hash(key) = (hash1(key) + i * hash2(key)) % tableSize"  
  follow-up: _Why is it important for the second hash function to be different from the first?_  
  expected: It is important for the second hash function to be different to ensure that the sequence of alternative positions is not predictable and to avoid clustering, which improves the overall performance of the hash table.

### [Graph representation] Explain how the adjacency matrix representation handles weighted edges in a graph.
*confidence 0.70 · medium · slides [135, 139, 140, 295]*

**Reference:** In the adjacency matrix representation of a weighted graph, the cost or distance between adjacent nodes is stored in the matrix. This means that each entry in the matrix represents the weight of the edge between two nodes. The matrix is used to store the exact cost value for each existing edge, which allows for efficient lookup of edge weights during traversal or algorithm execution.

**Key points** (slide quote → follow-up → expected answer):
- **Each entry in the matrix represents the weight of the edge between two nodes.**  
  quote: "cost/distance value specified on the edge between adjacent nodes are stored in the adjacency matrix"  
  follow-up: _How would you represent a graph with negative edge weights using this method?_  
  expected: The matrix would still store the actual negative value as the weight, as it is a direct representation of the edge cost.
- **The adjacency matrix is used to store the exact cost value for each existing edge.**  
  quote: "cost/distance value specified on the edge between adjacent nodes are stored in the adjacency matrix"  
  follow-up: _How does this compare to the adjacency list representation for weighted graphs?_  
  expected: In adjacency list representation, the weight is stored alongside the adjacent node in a linked list, whereas in the matrix, it is stored directly in a specific cell.

### [Graph connectivity and path finding] Explain how the DFS-based path finding algorithm ensures that all possible paths from a source to a destination are discovered in a graph.
*confidence 0.70 · medium · slides [70, 71, 72, 73, 97, 98]*

**Reference:** The DFS-based path finding algorithm explores all possible paths by recursively visiting each adjacent node, marking nodes as visited to avoid cycles. When the destination is reached, the current path is printed. If the destination is not reached, the algorithm backtracks by unmarking the node and continues exploring other branches. This ensures that all paths are considered, as long as the graph is connected.

**Key points** (slide quote → follow-up → expected answer):
- **The algorithm marks nodes as visited to prevent cycles and redundant exploration.**  
  quote: "visited[u]=1;//Mark the current node and and store it in the array path"  
  follow-up: _Why is it important to mark nodes as visited during the traversal?_  
  expected: Marking nodes as visited prevents the algorithm from revisiting the same node, which would cause infinite loops and redundant path exploration.
- **The algorithm prints the path only when the destination is reached.**  
  quote: "if(u==d) //if the current vertex is same as the destination then print the array"  
  follow-up: _What would happen if the destination was not marked as a special node?_  
  expected: The algorithm would not recognize the destination and would not print the path, even if it had reached it.

### [Sorting by counting] How does the concept of accumulated frequency in Distribution Counting Sorting ensure that elements are placed in their correct relative positions in the sorted list?
*confidence 0.70 · medium · slides [1289, 1299, 1300, 1301]*

**Reference:** The accumulated frequency in Distribution Counting Sorting ensures that elements are placed in their correct relative positions by providing a cumulative count that reflects the number of elements that should appear before each value in the sorted list. This cumulative count is derived from the frequencies of each element in the original list. As the algorithm scans the finite set in order, it uses these accumulated frequencies to determine the exact position where each element should be placed in the output array.

**Key points** (slide quote → follow-up → expected answer):
- **Accumulated frequency determines the position of each element in the sorted list.**  
  quote: "The required information which is used to place the elements at proper positions is accumulated sum of frequencies which is also called as distribution in statistics."  
  follow-up: _What happens if the frequencies are not accumulated before placing elements in the sorted list?_  
  expected: The elements would not be placed in their correct relative positions, as the algorithm would not know how many elements should come before each value.
- **The algorithm scans the finite set in order to print elements according to their frequency.**  
  quote: "Scan the set in order of sorting and print each element of the set according to its frequency, which will be the required sorted list."  
  follow-up: _Why is it important to scan the set in order of sorting?_  
  expected: Scanning the set in order of sorting ensures that elements are placed in the correct sequence, maintaining the relative order required for a sorted list.

### [Kruskal's algorithm] How does Kruskal’s algorithm ensure that the resulting tree is acyclic?
*confidence 0.70 · medium · slides [1382, 1386, 1387, 1388, 1401, 1402]*

**Reference:** Kruskal’s algorithm ensures the resulting tree is acyclic by using the Union-Find data structure to detect cycles. Before adding an edge to the minimum spanning tree, it checks whether the two vertices it connects are already in the same set. If they are, adding the edge would create a cycle, so it is skipped. This process guarantees that only edges connecting different components are added, which prevents cycles and ensures the final structure is a tree.

**Key points** (slide quote → follow-up → expected answer):
- **Kruskal’s algorithm uses Union-Find to detect cycles.**  
  quote: "Kruskal’s uses Disjoint Set (Union-Find) to check cycles"  
  follow-up: _What happens if an edge connects two nodes that are already in the same set?_  
  expected: The edge is skipped to avoid creating a cycle.
- **Edges are added only if they connect different components.**  
  quote: "If adding that edge does not create a cycle (that is, the two vertices are not already connected), add that edge to the minimum spanning tree."  
  follow-up: _Why is it important that the edge connects different components?_  
  expected: Because connecting two already connected components would create a cycle, which is not allowed in a tree.

### [Huffman coding] Explain how Huffman coding ensures that no codeword is a prefix of another, and why this is important for data compression.
*confidence 0.70 · medium · slides [1419, 1421]*

**Reference:** Huffman coding constructs a binary prefix code tree where each symbol is mapped to a binary string. This ensures that no codeword is a prefix of another, which is crucial for unambiguous decoding. This property allows the receiver to correctly interpret the compressed data without requiring additional delimiters between codewords, making the compression efficient and reliable.

**Key points** (slide quote → follow-up → expected answer):
- **Huffman coding constructs a binary prefix code tree.**  
  quote: "Huffman’s algorithm achieves data compression by finding the best variable length binary encoding scheme for the symbols that occur in the file to be compressed. Huffman coding uses frequencies of the symbols in the string to build a variable rate prefix code"  
  follow-up: _Why is it important that the encoding scheme is a prefix code?_  
  expected: It is important because it ensures that no codeword is a prefix of another, allowing for unambiguous decoding of the compressed data.
- **No codeword is a prefix of another codeword.**  
  quote: "No code is a prefix of another code (prefix free code)"  
  follow-up: _How does this property help in the decoding process?_  
  expected: This property allows the receiver to uniquely determine the end of each codeword during decoding, eliminating the need for additional markers or separators.

### [Recursive tree traversals] Explain how the order of visiting nodes differs between preorder and postorder traversal in a general tree, using the definitions provided.
*confidence 0.70 · medium · slides [314, 315, 316, 367, 368, 369]*

**Reference:** In preorder traversal, the root is visited before its subtrees and then the remaining trees in the forest. In postorder traversal, the root is visited after its subtrees and the remaining trees in the forest. This difference in order is reflected in the traversal functions, where preorder visits the root first, and postorder visits the root last. The traversal of the forest is handled recursively in both cases, but the position of the root visit determines the overall traversal order.

**Key points** (slide quote → follow-up → expected answer):
- **In preorder traversal, the root is visited before its subtrees and then the remaining trees in the forest.**  
  quote: "Preorder: 1. Visit the root of the first tree in the forest 2. Traverse in preorder the forest formed by the subtrees of the first tree, if any 3. Traverse in preorder the forest formed by the remaining trees in the forest, if any"  
  follow-up: _What happens if you visit the root after its subtrees in preorder?_  
  expected: It would no longer be preorder traversal; it would be postorder traversal.
- **In postorder traversal, the root is visited after its subtrees and the remaining trees in the forest.**  
  quote: "Postorder: 1. Traverse in postorder the forest formed by the subtrees of the first tree, if any 2. Traverse in postorder the forest formed by the remaining trees in the forest, if any 3. Visit the root of the first tree in the forest"  
  follow-up: _Why is the root visited last in postorder traversal?_  
  expected: Because postorder traversal processes the subtrees before the root, ensuring that all descendants are processed before their parent.

### [Prim's algorithm] Explain how Prim's algorithm differs from Kruskal's algorithm in terms of how they grow the minimum spanning tree, and why this difference matters for the algorithm's behavior.
*confidence 0.70 · medium · slides [1344, 1362, 1381, 1386, 1387]*

**Reference:** Prim's algorithm grows a single tree by adding edges that connect nodes to the existing tree, while Kruskal's algorithm grows a forest of trees by merging pairs of trees. This difference means that Prim's algorithm always maintains a single connected component, whereas Kruskal's algorithm may temporarily have multiple disconnected components. This distinction affects how each algorithm selects edges and manages the union-find structure.

**Key points** (slide quote → follow-up → expected answer):
- **Prim's algorithm grows a single tree until it becomes the minimum spanning tree.**  
  quote: "Prim's algorithm is very similar to Kruskal's: whereas Kruskal's 'grows' a forest of trees, Prim's algorithm grows a single tree until it becomes the minimum spanning tree."  
  follow-up: _What happens if Prim's algorithm were to grow a forest instead of a single tree?_  
  expected: It would no longer be Prim's algorithm, as the core idea is to maintain a single connected component throughout the process.
- **Prim's algorithm only adds edges that join nodes to the existing tree.**  
  quote: "Prim's algorithm only adds edges that join nodes to the existing tree."  
  follow-up: _Why would Prim's algorithm not consider edges that connect two separate trees?_  
  expected: Because the algorithm is designed to build the MST incrementally by expanding a single tree, not by merging separate trees.

### [Horspool and Boyer-Moore string matching] Compare the preprocessing steps of Horspool’s and Boyer-Moore algorithms, and explain how these differences affect their performance in string matching.
*confidence 0.70 · hard · slides [1310, 1312, 1327, 1329, 1330] · ⚠ NEEDS REVIEW*

**Reference:** Horspool’s algorithm preprocesses the pattern to create a single table that maps each character to the farthest position it appears in the pattern. Boyer-Moore preprocesses the pattern right to left and creates two tables: one for the bad-symbol shift and one for the good-suffix shift. These differences mean that Boyer-Moore can achieve larger skips in some cases, potentially leading to faster matching in average scenarios, but with more preprocessing overhead.

**Key points** (slide quote → follow-up → expected answer):
- **Horspool’s algorithm preprocesses the pattern to create a single table that maps each character to the farthest position it appears in the pattern.**  
  quote: "Horspool’s algorithm simplifies the Boyer-Moore algorithm by using just one table."  
  follow-up: _What is the purpose of the single table in Horspool’s algorithm?_  
  expected: The single table in Horspool’s algorithm is used to determine how far to shift the pattern when a mismatch occurs, based on the rightmost occurrence of the text character in the pattern.
- **Boyer-Moore preprocesses the pattern right to left and creates two tables: one for the bad-symbol shift and one for the good-suffix shift.**  
  quote: "Boyer-Moore algorithm preprocesses pattern right to left and store information into two tables."  
  follow-up: _Why does Boyer-Moore use two tables instead of one?_  
  expected: Boyer-Moore uses two tables to handle both the bad-symbol shift and the good-suffix shift, allowing it to make more efficient skips in some cases compared to Horspool’s algorithm.

### [Time and space complexity] Compare the time and space complexity of the Knapsack problem with that of a 2-3 Tree operation, and explain what this comparison reveals about their performance characteristics.
*confidence 0.70 · medium · slides [763, 777, 1186, 1476]*

**Reference:** The Knapsack problem has a time complexity of O(nW) and a space complexity of O(nW), which indicates that it requires significant computational resources and memory, especially as the input size grows. In contrast, a 2-3 Tree operation has a time complexity of O(log n) and likely a lower space complexity due to its balanced structure. This comparison reveals that the Knapsack problem is computationally more intensive and less memory-efficient than a 2-3 Tree operation, which benefits from its balanced nature and efficient memory usage.

**Key points** (slide quote → follow-up → expected answer):
- **The Knapsack problem has a time complexity of O(nW) and a space complexity of O(nW).**  
  quote: "THE KNAPSACK PROBLEM
  Space complexity: O(nW)
  Time to compose optimal solution: O(n)
  Time complexity:O(nW)"  
  follow-up: _What does the O(nW) time complexity suggest about the Knapsack problem's computational demand?_  
  expected: It suggests that the Kn'tapsack problem requires a number of operations proportional to both the number of items and the capacity, making it computationally expensive for large inputs.
- **A 2-3 Tree operation has a time complexity of O(log n) due to its balanced structure.**  
  quote: "2-3 Tree
Time Complexity
The property of being perfectly balanced, enables the 2-3 Tree operations of insert, delete and search to have a time complexity of O(log (n))."  
  follow-up: _Why does the balanced structure of a 2-3 Tree lead to a better time complexity?_  
  expected: Because the balanced structure ensures that the depth of the tree remains logarithmic relative to the number of elements, which limits the number of operations needed for insertion, deletion, and search.

### [Recurrence relations] Consider a recurrence relation where the function f(n) is not polynomial. How does the Master Theorem still apply, and what does it imply about the relative growth rates of the recursive and non-recursive parts of the algorithm?
*confidence 0.70 · hard · slides [1039] · ⚠ NEEDS REVIEW*

**Reference:** The Master Theorem applies to f(n) that is not polynomial by comparing it to n^d, even if d is not an integer. The theorem still determines the time complexity based on whether a < b^d, a = b^d, or a > b^d. When f(n) is not polynomial, the theorem implies that the dominant term depends on the relative growth rates of the recursive and non-recursive parts, with the non-recursive part potentially dominating if it grows faster than the recursive part.

**Key points** (slide quote → follow-up → expected answer):
- **The Master Theorem applies to f(n) that is not polynomial by comparing it to n^d.**  
  quote: "If f(n) ∈Θ(nd), where d >= 0 in the recurrence relation, then: ..."  
  follow-up: _What happens if f(n) is not a polynomial function?_  
  expected: The Master Theorem still applies by comparing f(n) to n^d, even if d is not an integer, as long as f(n) can be expressed in terms of n^d.
- **The theorem determines the time complexity based on the relationship between a, b, and d.**  
  quote: "If a < bd, T(n) ∈Θ(nd); If a = bd, T(n) ∈Θ(nd log n); If a > bd, T(n) ∈Θ(nlog b a )."  
  follow-up: _How does the value of d affect the outcome when f(n) is not polynomial?_  
  expected: The value of d determines which case of the Master Theorem applies, and thus the time complexity, even when f(n) is not a polynomial function.

### [Tree terminology] Explain how the depth and height of a node in a binary tree are related, and how they differ from the depth of the tree.
*confidence 0.70 · medium · slides [541, 542, 543, 544, 545, 546]*

**Reference:** The depth of a node is the path length from the root to that node, while the height of a node is the path length from that node to the deepest leaf. The depth of the tree is the maximum depth of any node in the tree, which is also equal to the height of the root node. These terms help in understanding the structure and balance of the tree.

**Key points** (slide quote → follow-up → expected answer):
- **Height of a node is the path length from that node to the deepest leaf.**  
  quote: "Height of a node: Path length from the node to the deepest leaf"  
  follow-up: _How would the height of a node change if all its descendants were removed?_  
  expected: The height of the node would become zero, as there are no descendants left to reach.
- **The depth of the tree is the maximum depth of any node in the tree.**  
  quote: "Depth of a tree: Maximum level of any leaf in the tree"  
  follow-up: _If all nodes in a tree are at the same level, what would be the depth of the tree?_  
  expected: The depth of the tree would be equal to the level of the nodes, as all leaves are at the same level.

### [Infix to postfix conversion] Explain how the precedence of operators affects the conversion of an infix expression to postfix notation, and why it is important to handle parentheses correctly.
*confidence 0.69 · medium · slides [678, 679, 680, 681, 689, 693]*

**Reference:** The precedence of operators determines the order in which operations are performed in an expression. In the conversion to postfix notation, higher precedence operators are processed before lower precedence ones, ensuring the correct evaluation order. Parentheses are used to override the default precedence, and handling them correctly is essential to maintain the intended structure of the expression during conversion.

**Key points** (slide quote → follow-up → expected answer):
- **The precedence of operators determines the order in which operations are performed in an expression.**  
  quote: "Applying the rules of precedence the table shows the conversion of Infix to Postfix and Prefix Expression"  
  follow-up: _Why is the order of operations important in converting an infix expression to postfix?_  
  expected: The order of operations ensures that the correct operations are performed at the right time, which is crucial for accurate evaluation of the expression.
- **Higher precedence operators are processed before lower precedence ones during conversion to postfix.**  
  quote: "A + B * C can be expressed as A + (B * C) as multiplication takes precedence over addition"  
  follow-up: _How does the algorithm ensure that higher precedence operators are processed first?_  
  expected: The algorithm uses a stack to temporarily hold operators, and operators with higher precedence are pushed onto the stack before lower precedence ones are processed.

### [Priority queue] Explain how the heap property enables efficient insertion and deletion in a priority queue, and why the array-based implementation is preferred over a linked list for this purpose.
*confidence 0.69 · medium · slides [245, 246, 247, 248, 249, 250]*

**Reference:** The heap property ensures that the root node always contains the maximum (or minimum) element, allowing for O(1) access to the highest-priority item. Insertion and deletion operations maintain this property through siftup and siftdown, which take O(log n) time. The array-based implementation is preferred because it allows for direct indexing of parent and child nodes, making these operations more efficient compared to a linked list, where traversal is required.

**Key points** (slide quote → follow-up → expected answer):
- **The heap property ensures that the root node always contains the maximum (or minimum) element.**  
  quote: "The root of a heap always contains its largest element."  
  follow-up: _Why is it important for the root to contain the largest element in a priority queue?_  
  expected: Because it allows for O(1) access to the highest-priority item, which is essential for efficient deletion.
- **Insertion and deletion in a heap maintain the heap property through siftup and siftdown operations.**  
  quote: "The entry with largest key is on the top (Descending heap) and can be removed immediately. But O(logn) time is required to readjust the heap with remaining keys"  
  follow-up: _What would happen if the heap property was not maintained after an insertion?_  
  expected: The priority queue would no longer correctly return the highest-priority item, breaking the fundamental behavior of the data structure.

### [Open addressing] What happens to the distribution of keys in a hash table when using open addressing with quadratic probing, and how does this affect the likelihood of future collisions compared to linear probing?
*confidence 0.69 · hard · slides [30, 31, 38, 39, 40, 41] · ⚠ NEEDS REVIEW*

**Reference:** Quadratic probing spreads out the keys more evenly than linear probing because it increases the step size non-linearly, which reduces the chance of clustering. This leads to a more uniform distribution of keys and fewer future collisions. In contrast, linear probing can lead to primary clustering, where consecutive insertions fill adjacent slots, increasing the probability of future collisions.

**Key points** (slide quote → follow-up → expected answer):
- **Quadratic probing spreads out the keys more evenly than linear probing.**  
  quote: "Quadratic Probing (Open addressing, closed hashing) resolves collision by using the below formula: h(key) = ( h(key) + i^2 ) % tableSize where i = 1, 2, 3, …"  
  follow-up: _Why do you think quadratic probing might reduce clustering?_  
  expected: Because it uses a non-linear step size, which prevents consecutive insertions from filling adjacent slots, reducing primary clustering.
- **Linear probing can lead to primary clustering, increasing the likelihood of future collisions.**  
  quote: "Linear Probing (open addressing, closed hashing) resolves collision by finding the next vacant spot in the hash table, in other words, it uses the below formula to resolve collision: h(key) = ( h(key) + i ) % tableSize where i = 1, 2, 3, …"  
  follow-up: _What is the main disadvantage of linear probing compared to quadratic probing?_  
  expected: Linear probing can create primary clustering, where consecutive insertions fill adjacent slots, making future collisions more likely and degrading performance.

### [Graph terminology] Consider a scenario where a graph has both directed and undirected edges. How does this hybrid structure differ from a purely directed or purely undirected graph, and what implications does this have for the classification of the graph as directed or undirected?
*confidence 0.69 · hard · slides [261, 262] · ⚠ NEEDS REVIEW*

**Reference:** A graph with both directed and undirected edges is neither purely directed nor purely undirected. A directed graph is defined as having all edges directed, while an undirected graph has all edges unordered. When a graph contains a mix, it does not fit into either category. This hybrid structure implies that the graph cannot be classified as directed or undirected, as the classification requires all edges to conform to one type. The presence of both types of edges complicates the graph’s classification and affects how relationships between vertices are interpreted.

**Key points** (slide quote → follow-up → expected answer):
- **A graph with both directed and undirected edges is neither purely directed nor purely undirected.**  
  quote: "A graph is undirected, when the pair of vertices representing any edge is unordered."  
  follow-up: _If a graph has some edges that are directed and some that are not, what does that imply about its classification?_  
  expected: It implies that the graph cannot be classified as either directed or undirected, as both classifications require all edges to conform to a single type.
- **A directed graph is defined as having all edges directed.**  
  quote: "A graph with all directed edges is called diagraph or directed graph."  
  follow-up: _What would happen if a directed graph had one undirected edge?_  
  expected: It would no longer be a directed graph, as the definition requires all edges to be directed.
- **An undirected graph has all edges unordered.**  
  quote: "A graph is undirected, when the pair of vertices representing any edge is unordered."  
  follow-up: _If a graph has some directed edges and some undirected edges, can it still be considered undirected?_  
  expected: No, because an undirected graph requires all edges to be unordered, and the presence of directed edges violates this condition.

### [Quick sort] Explain how the choice of pivot and partitioning affect the performance of quicksort, and why the worst-case scenario is a concern.
*confidence 0.69 · hard · slides [1053, 1054, 1055, 1056, 1057, 1058] · ⚠ NEEDS REVIEW*

**Reference:** The choice of pivot directly influences the partitioning of the array, which in turn determines the depth of the recursion tree. In the worst case, the partitioning is highly unbalanced, leading to O(n²) comparisons. This happens when the pivot is the smallest or largest element in the subarray, causing one subarray to be empty and the other to contain n-1 elements. This unbalanced partitioning leads to a worst-case time complexity that is less efficient than the average case.

**Key points** (slide quote → follow-up → expected answer):
- **The pivot selection and partitioning determine the recursion tree depth and performance.**  
  quote: "Select a pivot (partitioning element) - here, the first element"  
  follow-up: _What happens if the pivot is the smallest element in the subarray?_  
  expected: The partitioning becomes unbalanced, leading to a worst-case scenario with O(n²) comparisons.
- **The partitioning process ensures the pivot is in its final position.**  
  quote: "Exchange the pivot with the last element in the first (i.e., ≤)"  
  follow-up: _What is the role of the last swap in the partitioning process?_  
  expected: It places the pivot in its correct final position, after which the algorithm recursively sorts the two subarrays.

### [Simple queue] Explain how the simple queue's sequential representation enforces order, and what happens when the queue becomes full.
*confidence 0.69 · hard · slides [447, 449, 477, 504, 505, 506] · ⚠ NEEDS REVIEW*

**Reference:** The simple queue's sequential representation enforces order by maintaining a fixed-size array with `front` and `rear` pointers that track the oldest and newest elements, respectively. When the queue becomes full, the `rear` pointer reaches the end of the array, and no more elements can be inserted, as the array is exhausted.

**Key points** (slide quote → follow-up → expected answer):
- **The simple queue uses a fixed-size array with `front` and `rear` pointers to maintain order.**  
  quote: "struct queue { int items [MAXQUEUE]; int front, rear; };"  
  follow-up: _What ensures that elements are inserted in the correct order?_  
  expected: The `rear` pointer ensures that new elements are always added at the end of the queue, maintaining insertion order.
- **The queue becomes full when the `rear` pointer reaches the end of the array.**  
  quote: "Insert Elements at Rear end : Check whether the queue is full"  
  follow-up: _What happens when the queue is full and a new element is attempted to be inserted?_  
  expected: The insertion is denied, as the queue has no more space to accommodate the new element.

### [Greedy technique] Explain how the greedy technique ensures that a locally optimal choice leads to a globally optimal solution in the coin-change problem.
*confidence 0.68 · medium · slides [1343, 1344, 1345, 1349]*

**Reference:** The greedy technique ensures that each choice made is feasible, locally optimal, and irrevocable. In the coin-change problem, this means selecting the largest coin that does not exceed the remaining amount. This approach works when the coin denominations are such that a greedy choice always leads to the minimum number of coins. However, this is not always the case for all coin systems, which is why the greedy technique may not always yield the optimal solution.

**Key points** (slide quote → follow-up → expected answer):
- **The greedy technique requires that each choice made is locally optimal.**  
  quote: "On each step, the choice made must be: ... locally optimal: it has to be the best local choice among all feasible choices available on that step."  
  follow-up: _What happens if you choose a suboptimal coin at a step in the coin-change problem?_  
  expected: It may lead to a higher total number of coins needed to make the change, and thus not be globally optimal.
- **The greedy technique requires that each choice is irrevocable.**  
  quote: "On each step, the choice made must be: ... irrevocable: once decision was made, it cannot be changed on subsequent steps of the algorithm."  
  follow-up: _Why is it important for the greedy choice to be irrevocable in the coin-change problem?_  
  expected: Because once a coin is selected, it cannot be removed or replaced, so the algorithm must ensure that the initial choice is correct in the long run.

### [Recursive tree traversals] How does the traversal order in a general tree differ from that in a binary tree, and what implications does this have for the implementation of the traversal functions?
*confidence 0.63 · hard · slides [314, 315, 316, 367, 368, 369] · ⚠ NEEDS REVIEW*

**Reference:** In a general tree, the traversal functions visit the root before its subtrees and then the remaining trees in the forest, while in a binary tree, the traversal follows a strict left-to-right order. This difference affects the implementation because the general tree uses `child` and `sibling` pointers to traverse the forest, while the binary tree uses left and right pointers. The general tree traversal functions recursively call on `child` and `sibling`, while the binary tree traversal functions call on left and right children, respectively.

**Key points** (slide quote → follow-up → expected answer):
- **The traversal order in a general tree involves visiting the root before its subtrees and then the remaining trees in the forest.**  
  quote: "Preorder: 1. Visit the root of the first tree in the forest 2. Traverse in preorder the forest formed by the subtrees of the first tree, if any 3. Traverse in preorder the forest formed by the remaining trees in the forest, if any"  
  follow-up: _What happens if you only traverse the subtree of the first tree and ignore the remaining trees?_  
  expected: You would miss the remaining trees in the forest, leading to an incomplete traversal.
- **In a binary tree, the traversal follows a strict left-to-right order, which is different from the general tree's forest-based approach.**  
  quote: "Binary Tree Traversal: Preorder Steps: - Root Node is visited before the subtrees - Left subtree is traversed in preorder - Right subtree is traversed in preorder"  
  follow-up: _How would you adapt the general tree traversal to work for a binary tree?_  
  expected: You would treat the left child as the first subtree and the right child as the next tree in the forest, and adjust the traversal accordingly.

### [Heap construction] What happens if we apply the bottom-up heap construction algorithm to a descending heap instead of an ascending heap, and how does this affect the final structure of the heap?
*confidence 0.63 · hard · slides [244, 385, 386, 387, 388, 389] · ⚠ NEEDS REVIEW*

**Reference:** The bottom-up heap construction algorithm is designed for max-heaps, where each parent node is greater than or equal to its children. If applied to a descending heap, which is a min-heap, the algorithm would not maintain the correct heap property because it assumes the parent node should be greater than its children. This would result in an invalid heap structure, as the algorithm would incorrectly swap nodes to maintain a max-heap order instead of a min-heap order.

**Key points** (slide quote → follow-up → expected answer):
- **The bottom-up heap construction algorithm assumes the heap is a max-heap.**  
  quote: "Descending Heap: Root will have the highest element. Each node’s data is lesser than or equal to its parent’s data. It is also called max heap."  
  follow-up: _What is the key difference between a max-heap and a min-heap in terms of node values?_  
  expected: In a max-heap, each node’s value is greater than or equal to its children, while in a min-heap, each node’s value is less than or equal to its children.
- **The algorithm compares a node with its children and swaps them if necessary to maintain the max-heap property.**  
  quote: "if v ≥ H[j] //if key of parent node ≥ key of largest child //it’s a heap"  
  follow-up: _What would happen if the algorithm compared a node with its children in the opposite way?_  
  expected: The algorithm would incorrectly maintain a min-heap structure instead of a max-heap, which would violate the heap property.

### [Depth-first search] What happens to the traversal order of nodes in a graph when the starting node has multiple branches, and how does this relate to the recursive nature of depth-first search?
*confidence 0.63 · hard · slides [276] · ⚠ NEEDS REVIEW*

**Reference:** In a graph with multiple branches from the starting node, depth-first search explores one branch completely before moving to the next. This behavior is a direct result of the recursive implementation, which mimics a stack by processing the first available neighbor and then recursively visiting its neighbors. The traversal order is determined by the order in which neighbors are processed, and the recursion ensures that each path is fully explored before backtracking.

**Key points** (slide quote → follow-up → expected answer):
- **Depth-first search explores one branch completely before moving to the next.**  
  quote: "Visits all the nodes related to one neighbour before visiting the other neighbours and its related nodes."  
  follow-up: _What would happen if the order of visiting neighbors was changed?_  
  expected: The traversal order would change accordingly, as DFS processes neighbors in the order they are visited.
- **The recursive implementation mimics a stack's LIFO behavior.**  
  quote: "Uses stack behaviour, hence implemented using recursive algorithm"  
  follow-up: _Why is a stack-like behavior important for depth-first search?_  
  expected: A stack-like behavior ensures that the most recently visited node is revisited last, allowing for proper backtracking when a dead end is reached.

### [Binary search tree operations] Explain how the structure of a binary search tree ensures efficient search operations, and what happens if the tree becomes unbalanced.
*confidence 0.62 · hard · slides [177, 178, 179, 195, 196, 198] · ⚠ NEEDS REVIEW*

**Reference:** The binary search tree ensures efficient search operations by maintaining the property that all elements in the left subtree of a node are less than the node's value, and all elements in the right subtree are greater than or equal to it. This allows for a divide-and-conquer approach during search, similar to binary search on a sorted array. However, if the tree becomes unbalanced, the search time can degrade to linear time in the worst case, which is equivalent to a linked list.

**Key points** (slide quote → follow-up → expected answer):
- **The binary search tree ensures efficient search operations by maintaining the property that all elements in the left subtree of a node are less than the node's value.**  
  quote: "all the elements in the left subtree of a node n are less than the contents of node n"  
  follow-up: _What happens to the search time if the tree is not structured in a balanced way?_  
  expected: If the tree is not balanced, the search time can increase significantly, potentially degrading to linear time in the worst case.
- **All elements in the right subtree of a node are greater than or equal to the node's value.**  
  quote: "all the elements in the right subtree of a node n are greater than or equal to the contents of node n"  
  follow-up: _How does this property help in searching for a target value?_  
  expected: This property allows the search to eliminate half of the tree at each step, similar to binary search in a sorted array.

### [Prim's algorithm] What is the significance of Prim's algorithm growing a single tree rather than a forest of trees, and how does this affect the algorithm's approach to selecting edges?
*confidence 0.62 · hard · slides [1344, 1362, 1381, 1386, 1387] · ⚠ NEEDS REVIEW*

**Reference:** Prim's algorithm grows a single tree, which means it always maintains a connected component of nodes that are part of the MST. This approach ensures that every new edge added connects a new node to the existing tree, avoiding cycles. This is different from Kruskal's algorithm, which starts with a forest of isolated nodes and merges them. The single-tree growth in Prim's algorithm makes it more efficient in dense graphs, as it avoids the need to sort all edges upfront.

**Key points** (slide quote → follow-up → expected answer):
- **Prim's algorithm maintains a single connected component throughout its execution.**  
  quote: "Prim's algorithm is very similar to Kruskal's: whereas Kruskal's 'grows' a forest of trees, Prim's algorithm grows a single tree until it becomes the minimum spanning tree."  
  follow-up: _What happens if Prim's algorithm were to allow multiple disconnected components during its execution?_  
  expected: It would no longer be building a single tree, and the algorithm would risk adding edges that form cycles, which would compromise the correctness of the MST.
- **Prim's algorithm ensures that each new edge connects a new node to the existing tree.**  
  quote: "Prim's algorithm only adds edges that join nodes to the existing tree."  
  follow-up: _Why would adding an edge that connects two nodes already in the tree be problematic?_  
  expected: It would create a cycle, which is not allowed in a spanning tree, and would result in a non-minimal or invalid MST.

### [Warshall's and Floyd's algorithms] Explain how Warshall's and Floyd's algorithms differ in their approach to solving the all-pairs shortest path problem, and why one might be preferred over the other in certain scenarios.
*confidence 0.54 · hard · slides [1439, 1523, 1524, 1532, 1539, 1541] · ⚠ NEEDS REVIEW*

**Reference:** Warshall's algorithm is designed for computing the transitive closure of a graph, focusing on reachability rather than path weights. Floyd's algorithm, on the other hand, computes the shortest paths between all pairs of nodes in a weighted graph with non-negative edge weights. Warshall's algorithm is more efficient for boolean reachability problems, while Floyd's is more general and can handle weighted edges. The choice between them depends on whether the problem requires path weights or only reachability.

**Key points** (slide quote → follow-up → expected answer):
- **Floyd's algorithm is more general and can handle weighted edges.**  
  quote: "ALLPAIRS SHORTEST PATH(FLOYD'S ALGORITHM)"  
  follow-up: _(generic clarification)_
- **Both algorithms use dynamic programming principles but for different purposes.**  
  quote: "Dynamic Programming Algorithm Examples Computingabinomial coefficient Warshall's algorithmfortransitiveclosure"  
  follow-up: _How do these two algorithms relate to dynamic programming?_  
  expected: Both algorithms use dynamic programming techniques, but Warshall's is for reachability and Floyd's is for weighted shortest paths.

### [Queue applications] Explain how the Josephus problem can be implemented using a queue, and discuss the trade-offs between using a circular queue versus a circular linked list for this purpose.
*confidence 0.51 · hard · slides [515, 520, 521, 522, 523, 525] · ⚠ NEEDS REVIEW*

**Reference:** The Josephus problem can be implemented using a queue by repeatedly dequeuing and enqueuing elements to simulate the counting and elimination process. This approach mimics the behavior of the circular structure by rotating elements through the queue. However, using a circular linked list is more efficient for this problem because it allows direct access to the next node without the overhead of queue operations. The trade-off is that while a queue-based implementation is easier to understand and implement, it has higher time complexity due to repeated dequeue and enqueue operations.

**Key points** (slide quote → follow-up → expected answer):
- **The Josephus problem can be implemented using a queue by repeatedly dequeuing and enqueuing elements.**  
  quote: "while( q has one element) { dequeue n-1 names from the queue and enqueue it. dequeue the nth name. print the nth name }"  
  follow-up: _What is the main operation that simulates the counting in the Josephus problem using a queue?_  
  expected: The main operation is dequeuing n-1 elements and re-queueing them, which effectively moves the counting forward.
- **The queue-based implementation of the Josephus problem requires careful handling of the counting and elimination steps.**  
  quote: "while( q has one element) { dequeue n-1 names from the queue and enqueue it. dequeue the nth name. print the nth name }"  
  follow-up: _How does the queue-based implementation handle the counting and elimination steps?_  
  expected: The queue-based implementation handles counting by dequeuing n-1 elements and re-queueing them, then dequeuing the nth element for elimination.
