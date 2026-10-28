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

[fresh-000]
QUESTION: Explain what a deadlock is in the context of database transactions.
KEY POINTS:
  1. A deadlock is a situation where two or more transactions are waiting for each other to release locks.
  2. Deadlock results in a cycle where no transaction can make progress.
  3. Deadlock resolution requires one transaction to be rolled back.
ANSWER: a deadlock happens when two or more transactions are waiting for each other to release locks, so they form a cycle and none of them can move forward. usually you resolve it by rolling back one of the transactions so the other one can continue.

[fresh-001]
QUESTION: Explain how a self-learning switch builds its MAC address table.
KEY POINTS:
  1. The switch records each frame's source MAC address together with the port it arrived on.
  2. It uses the table to forward frames only to the port of the destination MAC address.
ANSWER: uh i dont really remember how the switch learns the addresses, something about storing the mac addresses in a table i think

[fresh-002]
QUESTION: Explain how polymorphism allows objects of different classes to be treated as objects of a common superclass, and why this is important for software design.
KEY POINTS:
  1. Polymorphism allows objects of different classes to be treated as objects of a common superclass.
  2. Polymorphism enables a single interface to work with objects of different types.
  3. Polymorphism supports dynamic method dispatch, which determines the method to call at runtime.
ANSWER: polymorphism lets a parent reference work with objects of different child classes, so the same interface can be used for different types. i dont remember the runtime dispatch part exactly.

[fresh-003]
QUESTION: Explain how the Chain of Responsibility pattern allows for dynamic decision-making in handling requests, and why this is important for loose coupling.
KEY POINTS:
  1. The Chain of Responsibility pattern allows multiple objects to handle a request.
  2. The chain can be decided dynamically at runtime.
  3. The pattern promotes loose coupling between the sender and the receiver.
ANSWER: chain of responsibility means one main handler receives the request and then directly chooses the next handler in a fixed order. the sender basically knows that first handler, and the chain is mostly decided when the classes are designed. it helps because all the handlers are tightly connected and know what the previous one did.

[fresh-004]
QUESTION: Explain how the primary key of a weak entity set is determined, and what role the identifying relationship plays in this process.
KEY POINTS:
  1. The primary key of a weak entity set includes the primary key of the identifying entity set.
  2. The discriminator of the weak entity set is part of the primary key.
  3. The identifying relationship enforces a foreign key constraint.
  4. The combination of the identifying entity's primary key and the weak entity's discriminator ensures uniqueness.
ANSWER: the weak entity's key uses the identifying entity's key plus its discriminator, so together they identify it.

[fresh-005]
QUESTION: Explain how user mode and kernel mode help protect the operating system from user programs.
KEY POINTS:
  1. User mode and kernel mode use a hardware-provided mode bit to distinguish between user and kernel code.
  2. Privileged instructions can only be executed in kernel mode.
  3. System calls allow user programs to request kernel services while maintaining mode separation.
ANSWER: the hardware keeps a mode bit to tell whether the cpu is running user code or kernel code. user programs run in user mode, so they cant execute privileged instructions directly. when they need something from the OS they make a system call, which enters kernel mode, does the operation, and then returns back to user mode.

[fresh-006]
QUESTION: How do the `ON DELETE CASCADE` and `ON UPDATE CASCADE` options affect the child table when changes are made to the parent table?
KEY POINTS:
  1. The `ON DELETE CASCADE` option deletes corresponding rows in the child table when a row in the parent table is deleted.
  2. The `ON UPDATE CASCADE` option updates corresponding rows in the child table when a row in the parent table is updated.
ANSWER: ON DELETE CASCADE removes the related child rows when the parent row is deleted. i dont remember the update one exactly.

[fresh-007]
QUESTION: How does the use of a parameterized constructor differ from a default constructor in Java, and what are the implications for object initialization?
KEY POINTS:
  1. A parameterized constructor allows you to pass arguments to initialize an object's instance variables with specific values.
  2. The default constructor provides default values to the object's instance variables.
  3. Defining a parameterized constructor affects the availability of the default constructor.
ANSWER: a parameterized constructor lets you pass values when the object is created. im not fully sure what happens to the default constructor though.

[fresh-008]
QUESTION: Explain how priority scheduling can lead to starvation and what is a common solution to this problem.
KEY POINTS:
  1. Priority scheduling can lead to starvation.
  2. Starvation is a problem in priority scheduling.
  3. Aging is a common solution to starvation in priority scheduling.
ANSWER: yeah, a low priority process can keep waiting if higher priority processes keep getting scheduled. aging is the usual fix, where its priority is slowly increased while it waits.

[fresh-009]
QUESTION: Explain how the sender and receiver manage retransmissions and window advancement in Selective Repeat, and why this approach is more efficient than Go-Back-N in certain scenarios.
KEY POINTS:
  1. The sender retransmits only the unacknowledged packets individually.
  2. The receiver acknowledges each correctly received packet individually.
  3. The sender advances the window base only when the smallest unacknowledged packet is acknowledged.
ANSWER: in selective repeat, the sender only resends packets that werent acknowledged, instead of resending the whole window. the receiver can acknowledge packets individually.

[fresh-010]
QUESTION: How does the concept of a safe state influence the decision-making process when a process requests a resource in a deadlock avoidance system?
KEY POINTS:
  1. The system must ensure that granting a resource request will not leave it in an unsafe state.
  2. A safe state guarantees that the system can avoid deadlocks.
  3. The behavior of processes can lead to unsafe states, which may result in deadlocks.
ANSWER: the system checks whether granting a request would leave it in a safe state. if it would be unsafe, the request has to wait.

[fresh-011]
QUESTION: Explain how the postfix expression evaluation algorithm ensures that operators are applied to the correct operands.
KEY POINTS:
  1. Each operator applies to the two operands that come just before it.
  2. When an operator is read, its operands are the top two elements of the stack.
  3. The two operands are popped, the operation is applied, and the result is pushed back.
ANSWER: you use a stack: pop the top two values, do the operation, then push the result back.

[fresh-012]
QUESTION: Can you explain what breadth-first search does in terms of node exploration?
KEY POINTS:
  1. BFS explores all neighbour nodes in the first level before moving to the next level.
  2. BFS ensures nodes are visited in order of their distance from the starting node.
ANSWER: bfs explores a graph level by level. so starting from one node, it visits all the nodes directly connected to it first, then their neighbours, and so on. because of that, a node is reached in increasing order of its distance from the start, which is why bfs is useful for shortest paths in an unweighted graph.

[fresh-013]
QUESTION: Explain how referential integrity constraints work in SQL and why they are important for maintaining data consistency.
KEY POINTS:
  1. Referential integrity constraints ensure that foreign key values must match existing primary key values or be null.
  2. Referential integrity constraints help maintain logical relationships between tables.
  3. Referential integrity constraints can be modified with referential triggered actions like CASCADE, SET NULL, or SET DEFAULT.
ANSWER: it makes sure foreign keys point to valid rows, so the tables dont have broken relationships.

[fresh-014]
QUESTION: Consider a scenario where a network administrator is deciding between using a Repeater and a Switch to connect two segments of a network. What are the key differences in their operation and how might these differences affect network performance?
KEY POINTS:
  1. A Repeater regenerates signals to extend the reach of a network.
  2. A Repeater broadcasts all data to all connected devices.
  3. A Switch uses MAC addresses to forward data directly to the intended device.
  4. A Switch reduces collisions by only forwarding data to the intended recipient.
ANSWER: a repeater regenerates a weak signal to extend the network. a switch uses MAC addresses to send the frame toward the right device.

[fresh-015]
QUESTION: Explain how composition differs from inheritance in terms of how they model relationships between objects, and why composition is often preferred in object-oriented design.
KEY POINTS:
  1. Composition models a 'has-a' relationship.
  2. Composition allows for dynamic behavior changes at runtime.
  3. Composition provides better test-ability.
ANSWER: composition is more like a has-a relationship. for example, a Car can have an Engine object instead of inheriting from Engine. because the object is held inside it, you can replace that component at runtime, and it is also easier to test the pieces separately compared with a deep inheritance setup.

[fresh-016]
QUESTION: Explain how a Full Outer Join differs from a Left or Right Outer Join, and why it might be useful in a database query.
KEY POINTS:
  1. A Full Outer Join returns all records from both tables, including unmatched rows, which are padded with NULL values.
  2. Full Outer Join is useful when you need to combine data from both tables regardless of whether there is a match.
  3. Full Outer Join cannot be directly implemented in MySQL and requires combining LEFT and RIGHT Outer Joins with UNION.
ANSWER: a full outer join keeps everything from both tables. if a row has no matching row on the other side, the missing columns become null. thats useful when you want to see the complete data from both sides instead of losing unmatched rows. mysql doesnt directly support full outer join, so you can combine a left join and right join with union.

[fresh-017]
QUESTION: Explain how TCP flow control prevents the sender from overwhelming the receiver's buffer.
KEY POINTS:
  1. The receiver tells the sender how much free buffer space it has (rwnd).
  2. The sender limits its unacknowledged data to the window the receiver advertised.
ANSWER: the receiver tells the sender how much buffer space it has using the rwnd value in the tcp header. the sender then limits the amount of unacknowledged data it sends based on that, so the receiver buffer doesnt get overloaded.

[fresh-018]
QUESTION: Explain how the 'circular wait' condition can be prevented in a system with multiple processes and shared resources.
KEY POINTS:
  1. Number all resources and make processes request them only in increasing order.
  2. This removes circular wait, one of the four necessary conditions for deadlock.
ANSWER: um, circular wait can be prevented by, like, giving the resources some order and making processes request them in increasing order. so a process cant request resource 2 and then go back and request resource 1. thats one of the deadlock conditions you have to break.

[fresh-019]
QUESTION: Explain what a stored procedure is and why it is useful in a database system.
KEY POINTS:
  1. A stored procedure is a collection of pre-compiled SQL statements stored inside the database.
  2. Stored procedures reduce duplication of effort and improve software modularity.
  3. Stored procedures can reduce data transfer and communication cost between the client and server.
ANSWER: a stored procedure is basically sql code the application sends to the database whenever it needs it. the main benefit is that the client does more processing and the server has less work, so it makes the app faster.

[fresh-020]
QUESTION: Explain one key difference between TCP and UDP in terms of reliability and connection setup.
KEY POINTS:
  1. TCP requires a connection setup.
  2. UDP does not provide reliability.
ANSWER: tcp first sets up a connection and gives you reliable, ordered delivery. udp just sends datagrams without doing that connection setup and it doesnt guarantee the packets will arrive. so udp is lighter when the application can tolerate some loss.

[fresh-021]
QUESTION: Explain how a stack is used in the execution of recursive functions.
KEY POINTS:
  1. Each recursive function call creates an activation record that is pushed onto the stack.
  2. The stack ensures that the most recent function call is executed first, and the most recent call is removed first.
  3. The stack stores the return address so that the program can resume execution after the function call completes.
ANSWER: every time a recursive function calls itself, a new call record is put on the stack. that record keeps things like local variables and where the function has to return. since the stack is lifo, the latest recursive call finishes first and gets popped, then control goes back to the previous call.

[fresh-022]
QUESTION: Explain how a stack can be implemented using a linked list.
KEY POINTS:
  1. A stack can be implemented through the linked list.
  2. Push operation inserts an element at the front of the list.
  3. Pop operation removes an element from the front of the list.
ANSWER: with a linked-list stack, push usually adds at the end, and pop removes from the front, so you dont need to worry about keeping a top pointer.

[fresh-023]
QUESTION: Explain how the FIFO page replacement algorithm works in the context of page faults and memory frames.
KEY POINTS:
  1. FIFO uses a queue to track the order of pages in memory.
  2. FIFO can lead to Belady’s Anomaly.
ANSWER: fifo keeps the pages in the order they entered memory, basically like a queue. when a page fault happens and there is no free frame, the page that has been there the longest is removed and the new page is loaded. one weird thing with fifo is belady's anomaly, where adding more frames can sometimes actually cause more page faults.

[fresh-024]
QUESTION: Why does TCP use a three-way handshake to establish a connection, rather than a two-way handshake?
KEY POINTS:
  1. The three-way handshake makes sure both sides agree to establish the connection.
  2. With a two-way handshake the server cannot know whether the client received its reply.
ANSWER: tcp uses three messages so both sides can agree that the connection is actually established. the client sends syn, the server replies with syn-ack, and then the client sends ack. with only two messages, the other side wouldnt get the same level of confirmation that the request and response were both received.

[fresh-025]
QUESTION: Explain how IPv6 datagrams can be transmitted across a network that contains both IPv6 and IPv4 routers, and why this is important for network transition.
KEY POINTS:
  1. IPv6 datagrams can be transmitted across a network with mixed IPv6 and IPv4 routers through tunneling.
  2. Tunneling allows for gradual migration without requiring all routers to be upgraded simultaneously.
ANSWER: if some routers only understand ipv4, an ipv6 packet can be put inside an ipv4 packet and tunneled across that part of the network. once it reaches an ipv6-capable router, the outer packet is removed and the ipv6 packet continues normally. this lets networks migrate gradually instead of upgrading every router at the same time.

[fresh-026]
QUESTION: Explain what topological sorting is and why it is important for directed acyclic graphs.
KEY POINTS:
  1. Topological sorting is listing vertices of a directed graph in such an order that for every edge in the graph, the vertex where the edge starts is listed before the vertex where the edge ends.
  2. Topological sorting is only possible for directed acyclic graphs (DAGs).
  3. Topological sorting is used for modeling problems with prerequisite constraints.
ANSWER: topological sorting puts a directed graph's vertices in an order where each node comes before the nodes it points to. its mainly used when there are prerequisites.

[fresh-027]
QUESTION: Explain what happens during the TCP connection establishment process.
KEY POINTS:
  1. TCP connection establishment involves a handshake to agree to establish a connection.
  2. TCP connection establishment includes agreement on connection parameters such as starting sequence numbers.
ANSWER: tcp starts with a syn, then the server sends an ack and data can start right away. the sequence numbers are mainly decided later when the actual data is sent.

[fresh-028]
QUESTION: Explain how HTTPS ensures secure communication between a browser and a server.
KEY POINTS:
  1. HTTPS uses TLS to encrypt all communications between the browser and the server.
  2. HTTPS relies on public and private key pairs for secure communication.
ANSWER: so https is basically http over tls, um, and tls encrypts the traffic between the browser and server. it also uses public and private keys during the secure setup, so other people cant just read the communication.

[fresh-029]
QUESTION: Explain how the operating system handles a page fault and how it manages the page-fault frequency to avoid thrashing.
KEY POINTS:
  1. The OS first checks whether the reference is invalid or the page is just not in memory.
  2. It finds a free frame and reads the page into it from disk.
  3. A process gains frames if its page-fault rate is too high and loses frames if it is too low.
  4. Controlling page-fault frequency avoids thrashing.
ANSWER: when a page fault happens, the OS brings the needed page into a free frame, or replaces another page if needed. it can also change the number of frames given to a process based on how often it faults.

[fresh-030]
QUESTION: Explain how method overloading allows a class to have multiple methods with the same name but different behaviors, and why this is considered compile-time polymorphism.
KEY POINTS:
  1. Method overloading allows a class to have more than one method with the same name if their argument lists are different.
  2. The compiler decides which method to call based on the method signature at compile time.
  3. Method overloading is considered compile-time polymorphism or static polymorphism.
ANSWER: method overloading means you can use the same method name with different parameter lists. the compiler decides which one to call from the arguments, but i dont remember the exact reason its called static polymorphism.

[fresh-031]
QUESTION: Explain how Dijkstra’s algorithm finds the shortest paths in a weighted graph.
KEY POINTS:
  1. It picks the unvisited vertex with the smallest tentative distance.
  2. It updates a neighbour's distance when a shorter path through that vertex is found.
ANSWER: dijkstra keeps tentative distances and repeatedly picks the vertex with the smallest current distance. then it looks at the neighbouring vertices, but im not fully sure how the update is done.

[fresh-032]
QUESTION: Explain what an expression tree is and how it represents an arithmetic expression.
KEY POINTS:
  1. An expression tree is a data structure that represents an arithmetic expression in a hierarchical form.
  2. The tree is constructed such that operands are leaves and operators are internal nodes.
  3. Each operator connects to its operands as children.
ANSWER: an expression tree has operators as internal nodes and operands as leaves.

[fresh-033]
QUESTION: How do ranking window functions like RANK(), DENSE_RANK(), and ROW_NUMBER() differ in their behavior when there are ties in the data?
KEY POINTS:
  1. RANK() skips the next rank after ties.
  2. DENSE_RANK() does not skip ranks after ties.
  3. ROW_NUMBER() assigns unique ranks to all rows, even with ties.
ANSWER: rank and dense rank both give a position to rows, and row number gives each row a number. the exact difference with ties is a little fuzzy to me.

[fresh-034]
QUESTION: In a network with multiple client-server pairs sharing a common middle link, how does the bottleneck link affect the end-to-end throughput for each pair?
KEY POINTS:
  1. The bottleneck link limits the maximum end-to-end throughput for each client-server pair.
  2. The shared link capacity is divided among all pairs when it is fairly shared.
  3. The throughput for each pair is constrained by the minimum of the server link, client link, and shared link capacity divided by the number of pairs.
ANSWER: the bottleneck link usually doesnt limit each pair separately because every pair has its own path. the shared link just adds some extra delay, and the throughput mainly depends on the fastest link in each pair. if there are more pairs they can actually get more total capacity because the link is being used more efficiently.

[fresh-035]
QUESTION: How does the store-and-forward mechanism in packet switching affect the end-to-end delay in a network with multiple hops?
KEY POINTS:
  1. The transmission delay of each hop is added to the end-to-end delay.
  2. The propagation delay of each link is also added to the end-to-end delay.
ANSWER: with store and forward, the router gets the whole packet before sending it on, so the transmission part happens at each hop. i dont remember the propagation part exactly.

[fresh-036]
QUESTION: Explain how persistent HTTP improves the response time for downloading multiple objects compared to non-persistent HTTP.
KEY POINTS:
  1. Persistent HTTP reuses a single TCP connection for multiple objects.
  2. Non-persistent HTTP requires two RTTs per object.
ANSWER: persistent http keeps the connection around for more objects, while non-persistent has extra connection overhead. so basically persistent is more efficient.

[fresh-037]
QUESTION: Explain how preemptive scheduling differs from non-preemptive scheduling in terms of when scheduling decisions occur and the implications for system behavior.
KEY POINTS:
  1. Preemptive scheduling allows the operating system to interrupt a running process.
  2. Non-preemptive scheduling decisions only occur when a process transitions to waiting or terminates.
  3. Preemptive scheduling may require mechanisms like mutex locks to prevent race conditions.
ANSWER: in preemptive scheduling the os can interrupt a process while its running and give the cpu to another process, usually because of a timer or higher priority task. in non-preemptive scheduling, once a process gets the cpu it keeps it until it finishes or blocks. preemption is more responsive, but because processes can be interrupted while sharing data, you may need locks or mutexes to avoid race conditions.

[fresh-038]
QUESTION: Explain how message passing differs from shared memory in terms of how processes communicate and synchronize.
KEY POINTS:
  1. Message passing uses send and receive operations to communicate.
  2. Message passing does not rely on shared variables.
ANSWER: message passing is basically using send and receive operations so one process can communicate with another. i dont remember the shared-memory difference exactly.

[fresh-039]
QUESTION: In Java, what is the difference between how primitive types and objects are passed as parameters, and what are the implications of this behavior?
KEY POINTS:
  1. In Java, all parameters are passed by value.
  2. Changes to primitive parameters do not affect the original value in the caller.
  3. For objects, a copy of the reference is passed, not the object itself.
ANSWER: um in java everything is passed by value. for a primitive its the actual value that gets copied, so changing the parameter doesnt change the caller's variable. for an object, whats copied is the reference, not the object itself, so both can point to the same object and its state can be changed.

[fresh-040]
QUESTION: What happens if two overloaded methods differ only in their return types, and how does this affect the compiler's ability to resolve the correct method call?
KEY POINTS:
  1. The return type is not part of the method signature used for method overloading.
  2. A difference in return type alone does not allow the compiler to resolve which method to call.
  3. Method overloading relies solely on the method name and parameter list, not the return type.
ANSWER: if the methods have the same name and same parameters but only different return types, thats not valid overloading. return type isnt used to distinguish overloaded methods, the parameter list has to be different.

[fresh-041]
QUESTION: Explain how binary search uses the decrease-by-a-constant-factor approach to solve a problem efficiently.
KEY POINTS:
  1. Binary search reduces the problem size by a constant factor at each step.
  2. Binary search is a recursive algorithm that reduces the problem to smaller instances.
ANSWER: binary search cuts the search space by a constant factor, usually half, each step.

[fresh-042]
QUESTION: Explain how First Normal Form (1NF) ensures that a relation is properly structured for relational database systems.
KEY POINTS:
  1. All attributes must be atomic.
  2. Composite and multivalued attributes are disallowed.
  3. 1NF is a prerequisite for higher normal forms.
ANSWER: 1nf mainly means every row should have the same number of columns and you should avoid duplicate rows. composite attributes are actually okay as long as they are stored in one column, and 1nf isnt really required before using the higher normal forms.

[fresh-043]
QUESTION: Explain how a circular queue solves the problem of wasted space in a simple queue.
KEY POINTS:
  1. A circular queue allows the rear pointer to wrap around to the beginning of the array.
  2. A circular queue reuses space that was previously occupied by removed elements.
  3. A circular queue behaves like a circular data structure.
ANSWER: so um, a circular queue basically connects the end back to the beginning. when the rear reaches the last array position it can wrap around and use the earlier empty positions, like after elements have been removed. so you dont waste those slots.

[fresh-044]
QUESTION: Explain how external fragmentation affects memory allocation and why compaction is a solution, but has limitations.
KEY POINTS:
  1. External fragmentation is when the total memory space exists to satisfy a request, but it is not contiguous.
  2. Compaction is a solution to external fragmentation by consolidating free memory into a single block.
  3. Compaction has limitations due to I/O problems and the need for dynamic relocation.
ANSWER: external fragmentation is when free memory is split up, and compaction joins it together. i dont remember the I/O limitation properly.

[fresh-045]
QUESTION: Explain what aggregate functions do and how they are used in SQL queries.
KEY POINTS:
  1. Aggregate functions take a collection of values and return a single value.
  2. Aggregate functions are used to summarize information from multiple tuples into a single tuple summary.
  3. Aggregate functions are used with GROUP BY to compute summaries for each group.
ANSWER: aggregate functions like COUNT, SUM and AVG combine values to give a summary. with GROUP BY, you can calculate those for each group, like each department.

[fresh-046]
QUESTION: Explain how Peterson’s solution ensures mutual exclusion between two processes.
KEY POINTS:
  1. Peterson’s solution uses a flag array to indicate if a process is ready to enter the critical section.
  2. The turn variable is used to determine which process can enter the critical section next.
ANSWER: peterson's solution uses a flag to say that a process is inside the critical section, and the turn variable tells which process is currently running. so if process 0 sets its flag, it enters and process 1 has to wait until the flag is cleared.

[fresh-047]
QUESTION: Explain the Open-Closed Principle in your own words.
KEY POINTS:
  1. Classes and modules should be open for extension but closed for modification.
  2. The principle encourages using OOP features like inheritance and interfaces for extension.
  3. Modifying existing code can lead to unexpected behavior.
ANSWER: the open-closed principle says you should extend existing code rather than keep modifying it. interfaces or inheritance can help with that.

[fresh-048]
QUESTION: Explain how abstraction in object-oriented programming helps in managing complexity in software design.
KEY POINTS:
  1. Abstraction hides implementation details from users.
  2. Abstraction allows interaction through an interface.
ANSWER: abstraction hides the complicated implementation details so the user doesnt have to deal with them. i dont remember exactly how the interface part fits in.

[fresh-049]
QUESTION: Explain what denormalization is and why it might be used in a database.
KEY POINTS:
  1. Denormalization is a database optimization technique where redundant data is added to one or more tables.
  2. Denormalization is used when retrieving data is prioritized over update efficiency.
  3. Denormalization allows for simpler queries and faster data retrieval.
ANSWER: denormalization is basically removing redundant data from tables so the database is cleaner and updates are easier. its mainly used when you have lots of writes and want to avoid updating the same information in multiple places. the queries can become a bit more complicated because the data is split up.
