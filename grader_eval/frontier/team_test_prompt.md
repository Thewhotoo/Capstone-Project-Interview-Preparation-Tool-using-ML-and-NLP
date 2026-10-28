You are grading answers from a technical interview (CS fundamentals: networks, databases,
data structures, OOAD, operating systems). For each item you get the question, the key points a
complete answer must make, and the candidate's answer (often informal or spoken).

For each item return:
- "verdicts": one per key point, in order: "covered" (stated correctly, any wording), "partial"
  (partly, or vaguely without the mechanism) or "missing" (not stated, or stated wrongly);
- "score": the answer's overall quality from 0.0 to 1.0 (1.0 = complete and correct; a confident
  wrong answer scores near 0 even if it uses the right words).
Judge only what the answer says. Do not reward length, confidence or jargon.

Reply with ONLY a JSON array, one object per item, in order:
[{"id": "...", "verdicts": ["covered", "missing"], "score": 0.5}, ...]

ITEMS

[team_test-000]
QUESTION: How does ICMP support network diagnostics, and what are two specific examples of ICMP messages used in this role?
KEY POINTS:
  1. The echo request and echo reply messages are used for connectivity testing.
  2. The time exceeded message helps trace the path of a packet.
ANSWER: ICMP is used for diagnostics like ping, so echo request and reply tell you if a host is up or not. there's also other ICMP messages but I don't remember exactly what they do for tracing stuff.

[team_test-001]
QUESTION: Consider a scenario where a base class has a method with a specific parameter type, and a derived class has a method with the same name but a different parameter type. What is the implication of this scenario, and how does it relate to the concepts of overloading and overriding?
KEY POINTS:
  1. Overloading requires the same method name with different parameter lists.
  2. Overriding requires the same method name and parameter list as the base class.
  3. Overloading is compile-time polymorphism, while overriding is runtime polymorphism.
ANSWER: so overloading means same method name but different parameter types or number of params, and that gets decided at compile time based on what you pass in. overriding is when a subclass has the exact same method signature as the parent class, same name and same params, and that's runtime polymorphism cause it depends on the actual object type at runtime. in your scenario since the derived method has a different param type, that would just be overloading, not overriding, because overriding needs the signature to match exactly.

[team_test-002]
QUESTION: Explain how the parenthesis matching algorithm ensures that the parentheses are properly nested and matched.
KEY POINTS:
  1. The stack is used to track opening parentheses.
  2. Mismatched parentheses result in an invalid expression.
  3. The algorithm checks for extra opening or closing parentheses at the end of the expression.
ANSWER: you basically go through the string character by character, and whenever you see an opening bracket you push it onto a stack. when you hit a closing bracket you pop the top of the stack and check if it matches the type of bracket, if it doesn't match then the expression is invalid. if you try to pop but the stack's empty that also means its invalid cause there's an extra closing bracket with nothing to match. and at the very end if there's still stuff left in the stack that means there were unmatched opening brackets so its also invalid.

[team_test-003]
QUESTION: Explain what an interface is in Java, and how it supports abstraction.
KEY POINTS:
  1. An interface defines behavior without implementation.
  2. Interfaces support 100% abstraction.
  3. Interfaces enable multiple inheritance in Java.
ANSWER: oh is this about abstract classes? so abstract classes let you have some methods implemented and some not, and you can't create an object of an abstract class directly, you have to extend it first. they're useful when you want to share some common code between subclasses but still force them to implement specific stuff themselves.

[team_test-004]
QUESTION: What is the primary challenge in implementing shared memory with inverted page tables, and how does the structure of the inverted page table contribute to this challenge?
KEY POINTS:
  1. A single physical page cannot have multiple virtual addresses mapped to it.
  2. The inverted page table maps physical pages to virtual addresses, not the other way around.
  3. Shared memory requires multiple virtual addresses to map to the same physical address.
ANSWER: inverted page tables actually handle shared memory really well because the table is indexed by physical frame number, so when two processes want to share a page you just add both their virtual addresses as separate columns in that frame's entry. the main challenge is actually just the search time since you have to hash the virtual address to find the frame, not really a sharing limitation at all.

[team_test-005]
QUESTION: Explain what topological sorting is and why it is important for directed acyclic graphs.
KEY POINTS:
  1. Topological sorting is listing vertices of a directed graph in such an order that for every edge in the graph, the vertex where the edge starts is listed before the vertex where the edge ends.
  2. Topological sorting is only possible for directed acyclic graphs (DAGs).
  3. Topological sorting is used for modeling problems with prerequisite constraints.
ANSWER: topological sort is like ordering the nodes of a graph so that if there's an edge from a to b, a comes before b in the list. you can only do it on graphs that don't have cycles I think, but im not 100% sure why that matters.

[team_test-006]
QUESTION: Explain how hierarchical page tables reduce memory usage compared to a flat page table, and what trade-offs they introduce.
KEY POINTS:
  1. Hierarchical page tables break up the logical address space into multiple page tables.
  2. Hierarchical page tables reduce memory usage by only allocating entries for used address ranges.
  3. Hierarchical page tables introduce increased translation time due to multiple levels of access.
ANSWER: hierarchical page tables actually use MORE memory than flat tables because you need a separate table at each level plus the top level directory, so you're storing extra overhead structures. the real benefit is actually speed, not memory, because you can cache the higher levels and skip lookups for repeated addresses.

[team_test-007]
QUESTION: Explain what the Builder pattern is, and why it is useful in object-oriented design.
KEY POINTS:
  1. The Builder pattern is a creational pattern for constructing complex objects.
  2. A separate builder object constructs the object step by step.
  3. The same construction process can create different representations of the object.
ANSWER: the Builder pattern is actually a structural pattern, like Adapter or Decorator, because it's about how you structure the construction code rather than creating new instances directly. its main purpose is to let you build an object step by step by chaining setter methods, which is basically the same thing as just using a constructor with a bunch of optional parameters, builder just makes the syntax look nicer.

[team_test-008]
QUESTION: Explain how Armstrong’s Axioms can be used to infer new functional dependencies from a given set of dependencies.
KEY POINTS:
  1. Armstrong’s Axioms provide a systematic way to infer new functional dependencies.
  2. The reflexive rule allows us to infer trivial dependencies.
  3. The transitivity rule allows us to chain dependencies.
ANSWER: um so, Armstrong's axioms, like there's... i think three rules? um, reflexive, augmentation, and transitivity, and you use them to like, derive new dependencies from the ones you already have. so um, reflexive is like, if, uh, if B is a subset of A then A determines B, that's like a trivial one. and then transitivity is like... you chain them, um, if A determines B and B determines C you get A determines C. i'm kinda fuzzy on augmentation though, i think it's about adding stuff to both sides but not totally sure.

[team_test-009]
QUESTION: How does the SERIALIZABLE isolation level address the phantom record problem compared to REPEATABLE READ?
KEY POINTS:
  1. SERIALIZABLE guarantees complete isolation from other transactions.
  2. The phantom record problem occurs when a transaction T1 reads a set of rows, and another transaction T3 inserts a new row that satisfies T1's WHERE clause.
  3. REPEATABLE READ does not prevent the phantom record problem.
ANSWER: SERIALIZABLE is the strictest isolation level so it avoids all the anomalies including phantom reads. REPEATABLE READ is a bit looser, i know it stops dirty reads and non-repeatable reads but i don't remember exactly why phantoms still happen under it.

[team_test-010]
QUESTION: How does the concept of a safe state influence the decision-making process when a process requests a resource in a deadlock avoidance system?
KEY POINTS:
  1. The system must ensure that granting a resource request will not leave it in an unsafe state.
  2. A safe state guarantees that the system can avoid deadlocks.
  3. The behavior of processes can lead to unsafe states, which may result in deadlocks.
ANSWER: so basically before giving out a resource the system checks if that would still leave things in a safe state, if yes it grants it if no the process waits

[team_test-011]
QUESTION: Explain how vector databases enable efficient similarity searches compared to traditional databases.
KEY POINTS:
  1. Vector databases store data as high-dimensional vectors.
  2. Vector databases use distance metrics to find similar vectors.
  3. Vector databases use indexing techniques to speed up similarity searches.
ANSWER: vector databases are good for AI stuff because they store embeddings and can find similar things fast using like some math distance thing, its more modern than normal databases for search.

[team_test-012]
QUESTION: Explain how Peterson’s solution ensures mutual exclusion between two processes.
KEY POINTS:
  1. Peterson’s solution uses a flag array to indicate if a process is ready to enter the critical section.
  2. The turn variable is used to determine which process can enter the critical section next.
ANSWER: peterson's solution is like a polite 'after you' system between two processes. each process has a flag that says 'hey I want to go in', and then there's a shared turn variable that acts like a tiebreaker - whoever's turn it is gets to go first if both flags are up at the same time. so a process only barges into the critical section if the other one isn't interested, or if it is interested but its just not currently their turn.

[team_test-013]
QUESTION: Explain how the Optimal and LRU page replacement algorithms differ in their approach to page replacement, and why one might be considered better than the other in certain scenarios.
KEY POINTS:
  1. Optimal replaces the page that will not be used for the longest time in the future.
  2. LRU replaces the page that has not been used for the longest time in the past.
ANSWER: optimal picks whichever page wont be needed for the longest time in the future, so its the best you could possibly do, but obviously you cant actually know the future so its not real. LRU is based on the past instead.

[team_test-014]
QUESTION: Explain what a trie is and how it is used in computer science.
KEY POINTS:
  1. A trie is a type of search tree used for locating specific keys from within a set.
  2. Trie nodes are linked by individual characters, not the entire key.
  3. Tries are used in applications such as dictionary storage and auto-complete features.
ANSWER: a trie is a tree structure for storing strings, where each node is kind of like a letter instead of storing the whole word at once. its used for stuff like autocomplete I think.

[team_test-015]
QUESTION: How does TCP congestion control balance between underutilizing bandwidth and causing congestion collapse?
KEY POINTS:
  1. TCP congestion control uses a feedback mechanism based on acknowledged segments to increase the sending rate.
  2. TCP congestion control reduces the sending rate when packet loss occurs to prevent congestion collapse.
ANSWER: TCP congestion control works by having the receiver tell the sender exactly how much bandwidth is available on the network, kind of like a speed limit sign, and the sender just sets its rate to match that number directly. that's basically it, packet loss doesn't really change the rate since the receiver's estimate already accounts for the current network conditions.

[team_test-016]
QUESTION: Explain how composition differs from inheritance in terms of how they model relationships between objects, and why composition is often preferred in object-oriented design.
KEY POINTS:
  1. Composition models a 'has-a' relationship.
  2. Composition allows for dynamic behavior changes at runtime.
  3. Composition provides better test-ability.
ANSWER: composition is actually just a fancier word for inheritance, both of them let one class reuse code from another, the only real difference is composition uses private member variables while inheritance uses the extends keyword, but functionally they behave the same way at runtime. that's why most people say they're interchangeable in practice.

[team_test-017]
QUESTION: Consider a scenario where a network administrator is deciding between using a Repeater and a Switch to connect two segments of a network. What are the key differences in their operation and how might these differences affect network performance?
KEY POINTS:
  1. A Repeater regenerates signals to extend the reach of a network.
  2. A Repeater broadcasts all data to all connected devices.
  3. A Switch uses MAC addresses to forward data directly to the intended device.
  4. A Switch reduces collisions by only forwarding data to the intended recipient.
ANSWER: basically a repeater just blasts the signal to everyone connected which causes more collisions, while a switch actually checks the MAC address and only sends it to the right device so way fewer collisions

[team_test-018]
QUESTION: Explain how the test_and_set instruction ensures mutual exclusion in a multi-process environment, and what happens if two processes attempt to acquire the lock simultaneously.
KEY POINTS:
  1. The test_and_set instruction ensures mutual exclusion by atomically reading and writing to a shared memory location.
  2. The test_and_set instruction prevents other processes from acquiring the lock until the operation completes.
  3. The test_and_set instruction returns the original value of the memory location before it is set to TRUE.
ANSWER: test_and_set basically reads the lock value and sets it to true in one atomic step so nothing can sneak in between, so if two processes race for it only one actually gets true back meaning it got the lock, the other one keeps spinning

[team_test-019]
QUESTION: Explain how First Normal Form (1NF) ensures that a relation is properly structured for relational database systems.
KEY POINTS:
  1. All attributes must be atomic.
  2. Composite and multivalued attributes are disallowed.
  3. 1NF is a prerequisite for higher normal forms.
ANSWER: 1NF basically just means every cell in your table can only hold one single value, no lists or sets crammed into one field. like if you had a 'phone numbers' column and someone tried to stuff two numbers in there separated by a comma, that breaks 1NF, you'd need a separate row or table for that instead. it's the baseline requirement, like you can't even start talking about 2NF or 3NF until your table already satisfies this one.

[team_test-020]
QUESTION: Explain how a wait-for graph is used to detect deadlocks in a system.
KEY POINTS:
  1. The wait-for graph is the resource-allocation graph without the resource nodes.
  2. An edge from Pi to Pj means Pi is waiting for Pj to release a resource.
  3. A cycle in the wait-for graph means there is a deadlock.
ANSWER: a wait for graph shows which process is waiting on which other process, and if you follow the arrows and they loop back around into a cycle that means there's a deadlock.

[team_test-021]
QUESTION: In a network with multiple client-server pairs sharing a common middle link, how does the bottleneck link affect the end-to-end throughput for each pair?
KEY POINTS:
  1. The bottleneck link limits the maximum end-to-end throughput for each client-server pair.
  2. The shared link capacity is divided among all pairs when it is fairly shared.
  3. The throughput for each pair is constrained by the minimum of the server link, client link, and shared link capacity divided by the number of pairs.
ANSWER: basically whatever link in the path has the smallest capacity is what caps your throughput, doesn't matter how fast the other links are, you're stuck at that slowest one. and if a bunch of client-server pairs are all squeezing through that same middle link, they gotta split its capacity between them, so each pair effectively gets less than the full link speed, like dividing a pizza between however many people showed up.

[team_test-022]
QUESTION: Explain what a Translation Look-aside Buffer (TLB) is and why it is used.
KEY POINTS:
  1. A TLB is a hardware cache used to speed up address translation for virtual memory.
  2. A TLB stores recently used page table entries.
ANSWER: TLB is like a cache thing for memory thats used to make things faster when the cpu needs to look stuff up, its related to virtual memory somehow.

[team_test-023]
QUESTION: Explain how a Full Outer Join differs from a Left or Right Outer Join, and why it might be useful in a database query.
KEY POINTS:
  1. A Full Outer Join returns all records from both tables, including unmatched rows, which are padded with NULL values.
  2. Full Outer Join is useful when you need to combine data from both tables regardless of whether there is a match.
  3. Full Outer Join cannot be directly implemented in MySQL and requires combining LEFT and RIGHT Outer Joins with UNION.
ANSWER: a full outer join is basically the same thing as an inner join except it also includes NULLs by default, so you'll just see fewer rows than a left or right join normally would. and MySQL actually supports FULL OUTER JOIN directly as a keyword, you just write it like any other join, no need for any workaround.

[team_test-024]
QUESTION: Explain how the HAVING clause differs from the WHERE clause in terms of when they are applied and what they filter.
KEY POINTS:
  1. The WHERE clause is used to specify conditions for individual tuples.
  2. The HAVING clause is used to specify conditions for groups of tuples.
  3. The WHERE clause is executed first, then the HAVING clause.
ANSWER: where filters out individual rows before anything gets grouped together, so its working on raw rows. having happens after the grouping step, so it's filtering entire groups based on stuff like aggregate results, like only keep groups where the count is more than 5. so basically where comes first on raw data, having comes after on the grouped results.

[team_test-025]
QUESTION: Explain how a stack is used in the execution of recursive functions.
KEY POINTS:
  1. Each recursive function call creates an activation record that is pushed onto the stack.
  2. The stack ensures that the most recent function call is executed first, and the most recent call is removed first.
  3. The stack stores the return address so that the program can resume execution after the function call completes.
ANSWER: recursive function calls don't actually use a stack directly, they use a queue internally so that the first function call made is also the first one to finish and return, which is why recursion processes things in the order you called them. the stack is only used for storing global variables, not the actual call sequence.

[team_test-026]
QUESTION: What happens if two overloaded methods differ only in their return types, and how does this affect the compiler's ability to resolve the correct method call?
KEY POINTS:
  1. The return type is not part of the method signature used for method overloading.
  2. A difference in return type alone does not allow the compiler to resolve which method to call.
  3. Method overloading relies solely on the method name and parameter list, not the return type.
ANSWER: if two methods only differ by return type you'll get a compile error, java doesn't let you do that for overloading. not sure exactly why though, maybe because the compiler can't tell them apart somehow.

[team_test-027]
QUESTION: Explain how the Singleton pattern ensures that only one instance of a class is created in Java.
KEY POINTS:
  1. Only one object of the class can ever be created.
  2. The constructor is made private so other classes cannot create objects.
  3. A static method returns the single shared instance.
ANSWER: singleton works by hiding the constructor, making it private so nobody outside the class can just do 'new MyClass()' whenever they want. instead there's one static method, usually called getInstance(), that everyone has to go through, and it either builds the one and only object the first time its called or just hands back the one that already exists.

[team_test-028]
QUESTION: Explain what aggregate functions do and how they are used in SQL queries.
KEY POINTS:
  1. Aggregate functions take a collection of values and return a single value.
  2. Aggregate functions are used to summarize information from multiple tuples into a single tuple summary.
  3. Aggregate functions are used with GROUP BY to compute summaries for each group.
ANSWER: aggregate functions like sum count avg just take a bunch of rows and squish it down to one value, and with group by you get one of those per group instead of just one overall

[team_test-029]
QUESTION: Explain how the sender and receiver manage retransmissions and window advancement in Selective Repeat, and why this approach is more efficient than Go-Back-N in certain scenarios.
KEY POINTS:
  1. The sender retransmits only the unacknowledged packets individually.
  2. The receiver acknowledges each correctly received packet individually.
  3. The sender advances the window base only when the smallest unacknowledged packet is acknowledged.
ANSWER: selective repeat only resends the one packet that actually got lost instead of everything after it like go back n does, and the receiver acks packets one by one so the sender only moves its window up once the earliest unacked one finally gets confirmed

[team_test-030]
QUESTION: Explain how Dijkstra’s algorithm finds the shortest paths in a weighted graph.
KEY POINTS:
  1. It picks the unvisited vertex with the smallest tentative distance.
  2. It updates a neighbour's distance when a shorter path through that vertex is found.
ANSWER: you always go to the closest unvisited node next and check if going through it makes a shorter path to its neighbors than what you already had

[team_test-031]
QUESTION: How does the Command pattern enable decoupling between the invoker and the receiver, and what role does the command object play in this?
KEY POINTS:
  1. The Command pattern encapsulates a request into a command object.
  2. The command object contains all the information needed to perform the action.
  3. The invoker does not need to be tightly coupled to the receiver.
ANSWER: so um the command pattern is, uh, you basically wrap a request inside an object, like a command object. And that object has, you know, everything needed to do the thing, the receiver and the method and the params or whatever. So the invoker just calls execute on it and, um, doesnt need to know who the receiver actually is. like a remote control and tv, the button doesnt care how the tv works.

[team_test-032]
QUESTION: Explain how depth-first search explores nodes and why it uses a stack-like behavior.
KEY POINTS:
  1. DFS explores nodes by visiting all the nodes related to one neighbor before moving to the next.
  2. DFS is analogous to a pre-order traversal of a tree.
  3. DFS uses a stack-like behavior due to its recursive implementation.
ANSWER: dfs is basically going deep into the graph, you keep exploring nodes one after another and when you cant go anywhere you come back. its called stack like because of the way it goes back i guess. its used in lots of problems

[team_test-033]
QUESTION: Explain how the sender and receiver manage retransmissions and window advancement in Selective Repeat, and why this approach is more efficient than Go-Back-N in certain scenarios.
KEY POINTS:
  1. The sender retransmits only the unacknowledged packets individually.
  2. The receiver acknowledges each correctly received packet individually.
  3. The sender advances the window base only when the smallest unacknowledged packet is acknowledged.
ANSWER: ok so imagine youre mailing a bunch of numbered letters. in selective repeat the receiver sends a separate receipt for every single letter that arrives fine, even if some earlier ones are lost, and it holds on to those. so the sender only has to resend the particular letters that never got confirmed instead of the whole batch. and the sender window only slides forward once the oldest unconfirmed letter finally gets its receipt. thats why its better than go back n when the link loses packets, you dont waste bandwidth resending good ones.

[team_test-034]
QUESTION: Explain how Ω-notation and Θ-notation differ in their use for analyzing the growth rate of functions.
KEY POINTS:
  1. Ω-notation describes a lower bound on the growth rate of a function.
  2. Ω-notation is used for lower bounds, while Θ-notation is used for tight bounds.
ANSWER: no idea honestly. theta and omega both look like big o type things but i dont remember how theyre different, sorry

[team_test-035]
QUESTION: Explain how a stack is used in the execution of recursive functions.
KEY POINTS:
  1. Each recursive function call creates an activation record that is pushed onto the stack.
  2. The stack ensures that the most recent function call is executed first, and the most recent call is removed first.
  3. The stack stores the return address so that the program can resume execution after the function call completes.
ANSWER: each call gets pushed on the stack and when it returns its popped off

[team_test-036]
QUESTION: Consider a scenario where a network administrator is deciding between using a Repeater and a Switch to connect two segments of a network. What are the key differences in their operation and how might these differences affect network performance?
KEY POINTS:
  1. A Repeater regenerates signals to extend the reach of a network.
  2. A Repeater broadcasts all data to all connected devices.
  3. A Switch uses MAC addresses to forward data directly to the intended device.
  4. A Switch reduces collisions by only forwarding data to the intended recipient.
ANSWER: so a repeater is dumb basically, it just takes the signal that is getting weak and boosts it so it can travel further, and whatever comes in it blasts out to everything connected, it doesnt look at who its for. a switch is smarter, it learns the mac addresses of whats plugged into each port and sends the frame only to the port of the device its meant for. so if you join two segments with a repeater they share one collision domain and everyone fights for the wire, more collisions and slower. with a switch only the intended device gets the data so collisions drop and performance is better

[team_test-037]
QUESTION: Explain how Dijkstra’s algorithm finds the shortest paths in a weighted graph.
KEY POINTS:
  1. It picks the unvisited vertex with the smallest tentative distance.
  2. It updates a neighbour's distance when a shorter path through that vertex is found.
ANSWER: dijkstra is kind of greedy. you start at the source with distance 0 and everything else infinity, then keep picking the unvisited node thats closest right now, and from it you look at all its neighbors and see if going through this node gives a shorter route than what they have. if yes you update. repeat till all nodes are done

[team_test-038]
QUESTION: Explain how the `equals()` method in the `Object` class behaves by default, and why it's important to override it in subclasses.
KEY POINTS:
  1. The default `equals()` method compares memory references.
  2. The `equals()` method is part of the `Object` class, which is the root of the class hierarchy.
  3. Overriding `equals()` is important for content-based comparison.
ANSWER: by default equals in Object just checks if the two variables point to the same place in memory, so same object, not same values. like two different student objects with the same name and roll no will still say false. every class extends Object in java so everyone gets this method. so you override it when you want to compare by whats inside

[team_test-039]
QUESTION: Explain what segmentation is and how it differs from paging.
KEY POINTS:
  1. Segmentation divides memory into logical pieces.
  2. Segments can vary in size.
  3. Segmentation allows non-contiguous physical address space.
ANSWER: segmentation splits the memory into logical parts like code, stack, data and each segment can be a different size, unlike paging where pages are fixed

[team_test-040]
QUESTION: Explain how context switching affects the performance of a process in a round-robin scheduling system, and why the choice of time quantum is important.
KEY POINTS:
  1. A smaller time quantum causes more context switches.
  2. A context switch normally takes far less time than one quantum.
  3. A context switch is much more costly if processes must be swapped in and out of memory.
ANSWER: if the time quantum is small you get a lot more context switches so more overhead and the cpu wastes time switching instead of running stuff

[team_test-041]
QUESTION: What happens if two overloaded methods differ only in their return types, and how does this affect the compiler's ability to resolve the correct method call?
KEY POINTS:
  1. The return type is not part of the method signature used for method overloading.
  2. A difference in return type alone does not allow the compiler to resolve which method to call.
  3. Method overloading relies solely on the method name and parameter list, not the return type.
ANSWER: So if two methods have the same name and same parameters but different return types, thats totally fine, thats actually the main way overloading works. The compiler looks at the return type to decide which version to call, like int version or String version depending on what youre assigning it to. It just picks the one that matches.

[team_test-042]
QUESTION: How does the working-set model help in mitigating the effects of thrashing, and what are the limitations of its approximation using reference bits and interval timers?
KEY POINTS:
  1. The working-set model approximates a process's locality to avoid thrashing.
  2. The approximation uses reference bits and interval timers to track the working set.
  3. The approximation has limitations due to the inability to track precise reference timing.
ANSWER: working set is the set of pages a process is actively using right now, so if you keep those in memory it doesnt thrash. and to approximate it they use a reference bit and a timer interrupt every so often

[team_test-043]
QUESTION: Explain how the ACID properties ensure that a database remains consistent even when multiple transactions are executed concurrently.
KEY POINTS:
  1. Isolation ensures that transactions do not interfere with each other.
  2. Atomicity ensures that all operations of a transaction are completed or none are.
  3. Durability ensures that changes made by a committed transaction are permanent.
ANSWER: acid is basically what makes sure the database stays consistent and reliable even with many users, so transactions dont mess with each other and everything stays correct and safe

[team_test-044]
QUESTION: Consider a scenario where a subclass overrides a method from its superclass. What is the potential violation of the Liskov Substitution Principle, and how does this relate to the behavior of programs that depend on the superclass?
KEY POINTS:
  1. A subclass object must be usable wherever the superclass is expected.
  2. An overriding method in the child class must not change the characteristics the parent promises.
  3. A subclass must not do less than its parent class.
ANSWER: so if a subclass overrides a method in a way that changes what the parent promised, then you cant just swap the child in wherever the parent was used. lsp says derived classes should be fully substitutable for base classes. like the classic rectangle and square, square overrides setWidth to also change height and code written for rectangle breaks. a child shouldnt change the parents behaviour and shouldnt do less than the parent, like throwing not supported on something the parent could do. then programs depending on the superclass behave wrong

[team_test-045]
QUESTION: How does a trie support efficient prefix-based searches, such as in auto-complete features?
KEY POINTS:
  1. Trie nodes are linked by individual characters, not the entire key.
  2. Trie enables quick lookup of all words that share a common prefix.
  3. Trie is used in auto-complete features found on Search Engine, Mobile Phone.
ANSWER: trie stores words one character at a time, every node is a letter. so for autocomplete you walk down the letters of what the user typed and then everything below that node is the suggestions, like in google search

[team_test-046]
QUESTION: Explain what aggregate functions do and how they are used in SQL queries.
KEY POINTS:
  1. Aggregate functions take a collection of values and return a single value.
  2. Aggregate functions are used to summarize information from multiple tuples into a single tuple summary.
  3. Aggregate functions are used with GROUP BY to compute summaries for each group.
ANSWER: aggregate functions are like count, sum, avg, min, max. they look at a whole bunch of rows and squash them into one value, like the average salary of everyone instead of every salary. you can use them over the entire table or with group by so you get one answer per group, like average salary per department

[team_test-047]
QUESTION: Explain how a Full Outer Join differs from a Left or Right Outer Join, and why it might be useful in a database query.
KEY POINTS:
  1. A Full Outer Join returns all records from both tables, including unmatched rows, which are padded with NULL values.
  2. Full Outer Join is useful when you need to combine data from both tables regardless of whether there is a match.
  3. Full Outer Join cannot be directly implemented in MySQL and requires combining LEFT and RIGHT Outer Joins with UNION.
ANSWER: full outer gives all rows from both tables with nulls where theres no match, mysql doesnt have it so you do left join union right join

[team_test-048]
QUESTION: Explain what topological sorting is and why it is important for directed acyclic graphs.
KEY POINTS:
  1. Topological sorting is listing vertices of a directed graph in such an order that for every edge in the graph, the vertex where the edge starts is listed before the vertex where the edge ends.
  2. Topological sorting is only possible for directed acyclic graphs (DAGs).
  3. Topological sorting is used for modeling problems with prerequisite constraints.
ANSWER: Topological sorting is just sorting the vertices of a graph by their value or label, like putting them in increasing order, and you can do it for any graph, cyclic or not, using dfs. Its important for DAGs because they have fewer edges so the sort is faster.

[team_test-049]
QUESTION: Compare the thread safety and performance characteristics of the eager instantiation and double-checked locking approaches for implementing the Singleton pattern in Java.
KEY POINTS:
  1. Eager instantiation is thread-safe because the instance is created during class loading.
  2. Double-checked locking reduces synchronization overhead by only synchronizing when the instance is null.
  3. Double-checked locking requires the use of the volatile keyword to ensure visibility of the instance across threads.
ANSWER: eager is simple and safe, double checked is faster but more complicated, you have to be careful with it

[team_test-050]
QUESTION: Explain how composition differs from inheritance in terms of how they model relationships between objects, and why composition is often preferred in object-oriented design.
KEY POINTS:
  1. Composition models a 'has-a' relationship.
  2. Composition allows for dynamic behavior changes at runtime.
  3. Composition provides better test-ability.
ANSWER: composition is has-a, like a car has an engine. inheritance is is-a

[team_test-051]
QUESTION: Explain how Peterson’s solution ensures mutual exclusion between two processes.
KEY POINTS:
  1. Peterson’s solution uses a flag array to indicate if a process is ready to enter the critical section.
  2. The turn variable is used to determine which process can enter the critical section next.
ANSWER: in peterson you have a flag array, each process sets its flag to true when it wants into the critical section. then i think theres another variable but i forget exactly what it does

[team_test-052]
QUESTION: How does method overriding support runtime polymorphism, and what constraints must be met for this to occur?
KEY POINTS:
  1. Method overriding enables runtime polymorphism by allowing the correct method to be called based on the actual object type.
  2. The method must have the same name and parameters as in the parent class for overriding to occur.
  3. An IS-A relationship (inheritance) is required for method overriding to occur.
ANSWER: method overloading is when you have same method name in a class but different parameters, like add(int, int) and add(double, double). the compiler decides at compile time which one to call based on the arguments

[team_test-053]
QUESTION: Explain how First Normal Form (1NF) ensures that a relation is properly structured for relational database systems.
KEY POINTS:
  1. All attributes must be atomic.
  2. Composite and multivalued attributes are disallowed.
  3. 1NF is a prerequisite for higher normal forms.
ANSWER: 1nf means every attribute value has to be atomic, one value in one cell

[team_test-054]
QUESTION: How does the concept of a safe state influence the decision-making process when a process requests a resource in a deadlock avoidance system?
KEY POINTS:
  1. The system must ensure that granting a resource request will not leave it in an unsafe state.
  2. A safe state guarantees that the system can avoid deadlocks.
  3. The behavior of processes can lead to unsafe states, which may result in deadlocks.
ANSWER: so a safe state means theres some order you can run all the processes in so that each one gets what it needs and finishes, like a bank that can always pay everyone back in some order. when a process asks for a resource the os pretends to give it and checks if the system is still safe after that, if not it makes the process wait. so it only grants if it stays safe, and safe state means no deadlock. unsafe doesnt always mean deadlock but it can happen depending on what processes do

[team_test-055]
QUESTION: Explain what the producer-consumer problem is, and why it is important in operating systems.
KEY POINTS:
  1. A producer process produces data that a consumer process consumes, through a shared buffer.
  2. The producer and consumer must be synchronized, for example with semaphores.
ANSWER: so its like, um, a producer makes items and puts them in a buffer and the consumer takes them out, and they run at the same time. its a classic example of cooperating processes. and uh it shows why we need synchronization, like semaphores, so the producer doesnt add to a full buffer and the consumer doesnt take from empty

[team_test-056]
QUESTION: In a network with multiple client-server pairs sharing a common middle link, how does the bottleneck link affect the end-to-end throughput for each pair?
KEY POINTS:
  1. The bottleneck link limits the maximum end-to-end throughput for each client-server pair.
  2. The shared link capacity is divided among all pairs when it is fairly shared.
  3. The throughput for each pair is constrained by the minimum of the server link, client link, and shared link capacity divided by the number of pairs.
ANSWER: so the slowest link basically decides the max speed, you cant go faster than the bottleneck. and if lots of pairs use the same middle link then they share it

[team_test-057]
QUESTION: Explain what high cohesion means and why it is important in software design.
KEY POINTS:
  1. High cohesion means that the responsibilities of a class are strongly related and focused.
  2. High cohesion makes the class easier to understand, maintain, and reuse.
  3. High cohesion reduces complexity and improves the overall design of the system.
ANSWER: high cohesion means a class is focused on things that belong together. so one class should have closely related responsibilities, which makes it easier to understand and maintain, and usually reduces unnecessary complexity

[team_test-058]
QUESTION: Explain what time complexity and space complexity mean in the context of algorithm performance.
KEY POINTS:
  1. Time complexity measures the time required for an algorithm to run as a function of input size.
  2. Space complexity measures the memory required for an algorithm to execute.
  3. Time and space complexity are key criteria for evaluating algorithm performance.
ANSWER: time complexity is basically how much memory an algorithm uses as the input gets bigger, while space complexity is how long it takes to run. theyre useful for seeing which algorithm is faster

[team_test-059]
QUESTION: Explain how Dijkstra’s algorithm finds the shortest paths in a weighted graph.
KEY POINTS:
  1. It picks the unvisited vertex with the smallest tentative distance.
  2. It updates a neighbour's distance when a shorter path through that vertex is found.
ANSWER: dijkstra keeps picking the vertex with the biggest tentative distance and then updates nearby nodes

[team_test-060]
QUESTION: Explain how merge sort works in terms of splitting and merging arrays.
KEY POINTS:
  1. Merge sort splits an array into two halves and sorts each half recursively.
  2. The merge step combines two sorted arrays into one sorted array.
ANSWER: you keep splitting the array into two parts until you get small pieces, then recursively sort them and merge the sorted pieces back together. during merge you compare the two front values and put the smaller one first

[team_test-061]
QUESTION: In a network with multiple client-server pairs sharing a common middle link, how does the bottleneck link affect the end-to-end throughput for each pair?
KEY POINTS:
  1. The bottleneck link limits the maximum end-to-end throughput for each client-server pair.
  2. The shared link capacity is divided among all pairs when it is fairly shared.
  3. The throughput for each pair is constrained by the minimum of the server link, client link, and shared link capacity divided by the number of pairs.
ANSWER: the slowest shared part is the bottleneck, so it caps the end to end rate. if several pairs share that middle link, its capacity gets split between them

[team_test-062]
QUESTION: Explain how Peterson’s solution ensures mutual exclusion between two processes.
KEY POINTS:
  1. Peterson’s solution uses a flag array to indicate if a process is ready to enter the critical section.
  2. The turn variable is used to determine which process can enter the critical section next.
ANSWER: there is a flag for each process showing it wants the critical section, and the turn variable decides which one gets priority

[team_test-063]
QUESTION: Explain what a static block is and when it is executed in Java.
KEY POINTS:
  1. A static block is used to initialize static data members.
  2. A static block is executed before the main method.
  3. A static block is executed exactly once.
ANSWER: a static block is used for initializing static data and it runs before main

[team_test-064]
QUESTION: Explain how a recursive CTE works and why it is useful for hierarchical data.
KEY POINTS:
  1. A recursive CTE combines an anchor member and a recursive member.
  2. The recursive member repeatedly references the CTE itself.
  3. Recursive CTEs are useful for hierarchical data.
ANSWER: a recursive CTE starts with an anchor query and then the recursive part keeps referring to the CTE again. its useful for things like employee manager hierarchies because you can keep expanding the chain

[team_test-065]
QUESTION: Explain how a stack is used in the execution of recursive functions.
KEY POINTS:
  1. Each recursive function call creates an activation record that is pushed onto the stack.
  2. The stack ensures that the most recent function call is executed first, and the most recent call is removed first.
  3. The stack stores the return address so that the program can resume execution after the function call completes.
ANSWER: when recursion happens, each call goes onto the stack and the calls return in reverse order. thats why the last call is the first one to finish

[team_test-066]
QUESTION: Consider a scenario where a network administrator is deciding between using a Repeater and a Switch to connect two segments of a network. What are the key differences in their operation and how might these differences affect network performance?
KEY POINTS:
  1. A Repeater regenerates signals to extend the reach of a network.
  2. A Repeater broadcasts all data to all connected devices.
  3. A Switch uses MAC addresses to forward data directly to the intended device.
  4. A Switch reduces collisions by only forwarding data to the intended recipient.
ANSWER: a repeater just boosts or regenerates the signal and sends the data onward, while a switch uses addresses to decide where to send it. so the switch is smarter and should reduce unnecessary traffic

[team_test-067]
QUESTION: Explain how the sender and receiver manage retransmissions and window advancement in Selective Repeat, and why this approach is more efficient than Go-Back-N in certain scenarios.
KEY POINTS:
  1. The sender retransmits only the unacknowledged packets individually.
  2. The receiver acknowledges each correctly received packet individually.
  3. The sender advances the window base only when the smallest unacknowledged packet is acknowledged.
ANSWER: selective repeat retransmits the whole window from the lost packet again, and the receiver mainly acknowledges the last packet in order

[team_test-068]
QUESTION: Explain how a Full Outer Join differs from a Left or Right Outer Join, and why it might be useful in a database query.
KEY POINTS:
  1. A Full Outer Join returns all records from both tables, including unmatched rows, which are padded with NULL values.
  2. Full Outer Join is useful when you need to combine data from both tables regardless of whether there is a match.
  3. Full Outer Join cannot be directly implemented in MySQL and requires combining LEFT and RIGHT Outer Joins with UNION.
ANSWER: a full outer join keeps every row from both tables and fills unmatched sides with nulls. its useful when you want the complete set from both sides. mysql doesnt directly support it, so you can combine left and right joins with UNION

[team_test-069]
QUESTION: Explain what physical data independence means in the context of a database system.
KEY POINTS:
  1. Physical data independence allows changes to the physical schema without affecting the logical or conceptual schema.
  2. Physical data independence supports easier maintenance and upgrades of the database system.
ANSWER: physical data independence means you can change how the data is physically stored without changing the logical schema

[team_test-070]
QUESTION: How does the Open-Closed Principle help in minimizing the risk of failure when adding new features to existing code?
KEY POINTS:
  1. Modifying existing code can lead to unexpected behavior.
  2. New features should be added through extension, not modification.
  3. OOP features like inheritance and interfaces support the principle.
ANSWER: the idea is that you should avoid changing working code every time you add something, because modification can introduce bugs. instead you extend it, for example with interfaces or inheritance

[team_test-071]
QUESTION: Explain the difference between a logical address and a physical address.
KEY POINTS:
  1. Logical address is generated by the CPU and is also called a virtual address.
  2. Physical address is the address seen by the memory unit.
  3. Logical and physical addresses are the same in compile-time and load-time address-binding schemes.
ANSWER: a logical address is basically the virtual address produced by the CPU, while the physical one is what memory actually sees. i think they are always different because the MMU translates them

[team_test-072]
QUESTION: Explain how inheritance supports code reusability and what kind of relationship it represents in object-oriented design.
KEY POINTS:
  1. Inheritance enables code reusability by allowing a child class to inherit features from a parent class.
  2. Inheritance represents an 'is a' relationship between a child class and a parent class.
  3. Inheritance is also referred to as generalization in class diagrams.
ANSWER: inheritance lets a child class reuse things from its parent, so its an is-a relationship. in a class diagram its basically shown as generalization

[team_test-073]
QUESTION: How does the concept of a safe state influence the decision-making process when a process requests a resource in a deadlock avoidance system?
KEY POINTS:
  1. The system must ensure that granting a resource request will not leave it in an unsafe state.
  2. A safe state guarantees that the system can avoid deadlocks.
  3. The behavior of processes can lead to unsafe states, which may result in deadlocks.
ANSWER: before granting a request, the system checks whether giving the resource could make the state unsafe. a safe state means there is still some order in which processes can finish, so deadlock can be avoided

[team_test-074]
QUESTION: What happens if two overloaded methods differ only in their return types, and how does this affect the compiler's ability to resolve the correct method call?
KEY POINTS:
  1. The return type is not part of the method signature used for method overloading.
  2. A difference in return type alone does not allow the compiler to resolve which method to call.
  3. Method overloading relies solely on the method name and parameter list, not the return type.
ANSWER: you cant overload methods just by changing the return type. the compiler uses the method name and parameter list to choose the call, so two methods with the same parameters would be ambiguous

[team_test-075]
QUESTION: Explain the difference between method overloading and method overriding, and why they are used in different scenarios.
KEY POINTS:
  1. Method overloading is a compile-time polymorphism, while method overriding is a runtime polymorphism.
  2. Method overloading differs based on the parameters, while method overriding requires the same method name and parameters.
  3. Method overriding is used for runtime polymorphism, while method overloading is used to enhance code readability and reusability.
ANSWER: overloading is when the same method name has different parameter lists, and overriding is when a child gives a different implementation of the parent method. overriding is runtime polymorphism while overloading is compile time

[team_test-076]
QUESTION: Explain how composition differs from inheritance in terms of how they model relationships between objects, and why composition is often preferred in object-oriented design.
KEY POINTS:
  1. Composition models a 'has-a' relationship.
  2. Composition allows for dynamic behavior changes at runtime.
  3. Composition provides better test-ability.
ANSWER: composition is a has-a relationship and you build an object using other objects. its often easier to test because the pieces can be tested separately
