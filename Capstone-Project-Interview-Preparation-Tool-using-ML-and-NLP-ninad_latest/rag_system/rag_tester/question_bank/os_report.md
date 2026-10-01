# Question bank: os

- **Active (used by the app): 68** · held back for review: 26 (confidence threshold 0.75)
- Sorted by confidence, best first. Held-back questions are kept below, not deleted.

## Active questions

### [Schedulers] Explain what the short-term scheduler does in an operating system.
*confidence 0.96 · easy · slides [125]*

**Reference:** The short-term scheduler selects from among the processes in the ready queue and allocates the CPU to one of them. This selection process determines which process gets to run next. The queue may be ordered in various ways, such as FIFO, priority, or other structures. The records in the queue are PCBs of the processes. This scheduler is responsible for making the CPU allocation decision at the moment a process is ready to run.

**Key points** (slide quote → follow-up → expected answer):
- **The short-term scheduler selects a process from the ready queue.**  
  quote: "Short-term scheduler selects from among the processes in ready queue, and allocates the CPU to one of them"  
  follow-up: _What happens if there are no processes in the ready queue?_  
  expected: The CPU would be idle until a process is added to the ready queue.
- **The ready queue may be ordered in various ways.**  
  quote: "Queue may be ordered in various ways"  
  follow-up: _What are some examples of how the queue might be ordered?_  
  expected: The queue could be ordered using FIFO, priority, or other structures like a tree or unordered linked list.
- **The records in the queue are PCBs of the processes.**  
  quote: "The records in the queue are PCB’s of the processes"  
  follow-up: _What is a PCB and why is it important in scheduling?_  
  expected: A PCB is a data structure that contains all the information about a process, such as its state, program counter, and register values. It is important because the scheduler needs this information to manage the process.

### [User-level vs kernel-level threads] Explain the difference between user-level and kernel-level threads based on how they are scheduled.
*confidence 0.96 · easy · slides [254, 255, 257, 262, 263]*

**Reference:** User-level threads are scheduled by the thread library, which maps them to lightweight processes (LWPs) that interface with kernel-level threads. Kernel-level threads are directly scheduled by the operating system's scheduler. This distinction affects how threads are managed and how blocking operations impact the process.

**Key points** (slide quote → follow-up → expected answer):
- **User-level threads are scheduled by the thread library.**  
  quote: "Many-to-one and many-to-many models, thread library schedules user-level threads to run on LWP."  
  follow-up: _What happens if a user-level thread blocks?_  
  expected: The entire process may block, because user-level threads are not directly scheduled by the OS.
- **Kernel-level threads are scheduled by the system scheduler.**  
  quote: "Scheduling of kernel level threads by the system scheduler to perform different unique OS functions."  
  follow-up: _What is the advantage of kernel-level thread scheduling?_  
  expected: It allows individual threads to be scheduled independently, enabling true parallelism on multi-core systems.
- **User-level threads are mapped to lightweight processes (LWPs).**  
  quote: "Leightweight Process (LWP) : Light-weight process are threads in the user space that acts as an interface for the ULT to access the physical CPU resources"  
  follow-up: _What is the role of a lightweight process?_  
  expected: It acts as an interface between user-level threads and the kernel-level thread scheduler.

### [Signals] Explain what a signal is in the context of Linux processes.
*confidence 0.96 · easy · slides [431]*

**Reference:** A signal is a kind of software interrupt used to announce asynchronous events to a process. It allows the operating system to notify a process of external events, such as user input or timer expiration. Signals are a way for the system to communicate with processes without requiring direct interaction.

**Key points** (slide quote → follow-up → expected answer):
- **A signal is a kind of software interrupt.**  
  quote: "A signal is a kind of software interrupt, used to announce asynchronous events to a process"  
  follow-up: _What is the purpose of a signal in a process?_  
  expected: The purpose of a signal is to announce asynchronous events to a process, such as user input or system events.
- **Signals are used to announce asynchronous events.**  
  quote: "A signal is a kind of software interrupt, used to announce asynchronous events to a process"  
  follow-up: _Can a process expect a signal to arrive at a specific time?_  
  expected: No, a process cannot expect a signal to arrive at a specific time because signals are asynchronous.
- **Signals are used to communicate with processes.**  
  quote: "A signal is a kind of software interrupt, used to announce asynchronous events to a process"  
  follow-up: _What kind of events can a signal communicate?_  
  expected: Signals can communicate various events such as user input, timer expiration, or process termination.

### [Deadlock avoidance] Explain what a safe state is in the context of deadlock avoidance.
*confidence 0.96 · easy · slides [410, 412]*

**Reference:** A safe state is not a deadlocked state. In a safe state, the OS can avoid unsafe states. If a system is in a safe state, there is no deadlock. The system remains in a safe state by ensuring that resource allocation always leaves the system in a safe condition. This allows the OS to prevent deadlocks by maintaining safe states at all times.

**Key points** (slide quote → follow-up → expected answer):
- **A safe state is not a deadlocked state.**  
  quote: "A safe state is not a deadlocked state."  
  follow-up: _What happens if a system is in a deadlocked state?_  
  expected: A deadlocked state is an unsafe state, and it means that no process can proceed because each is waiting for a resource held by another.
- **In a safe state, the OS can avoid unsafe states.**  
  quote: "As long as the state is safe, the OS can avoid unsafe states."  
  follow-up: _How does the OS ensure that it remains in a safe state?_  
  expected: The OS ensures that resource allocation decisions always leave the system in a safe state, preventing it from entering an unsafe state.
- **If a system is in a safe state, there is no deadlock.**  
  quote: "If a system is in safe state no deadlocks"  
  follow-up: _What is the main goal of deadlock avoidance?_  
  expected: The main goal is to ensure that the system will never enter an unsafe state, which could lead to a deadlock.

### [Segmentation] Explain what segmentation is and how it differs from paging.
*confidence 0.96 · easy · slides [482, 485, 486, 546]*

**Reference:** Segmentation is a technique for breaking memory into logical pieces, such as data and code segments. Unlike paging, which divides memory into fixed-size blocks, segmentation allows segments to vary in size. This means that the physical address space of a process can be non-contiguous, which is a key difference from paging.

**Key points** (slide quote → follow-up → expected answer):
- **Segmentation divides memory into logical pieces.**  
  quote: "Segmentation is a technique for breaking memory up into logical pieces"  
  follow-up: _What is the purpose of dividing memory into logical pieces?_  
  expected: The purpose is to group related information, such as data segments for a process or code segments for a process.
- **Segments can vary in size.**  
  quote: "Big difference – segments can be variable in size"  
  follow-up: _How does this differ from paging?_  
  expected: In paging, memory is divided into fixed-size blocks, whereas in segmentation, each segment can be of any size.
- **Segmentation allows non-contiguous physical address space.**  
  quote: "Segmentation permits the physical address space of a process to be non-contiguous."  
  follow-up: _Why is non-contiguous memory space important?_  
  expected: It allows a process to use memory that is not physically contiguous, which can improve memory utilization and flexibility.

### [Virtual memory and demand paging] Explain how demand paging reduces the amount of memory needed for a process.
*confidence 0.96 · easy · slides [567, 568, 573, 630, 631, 632]*

**Reference:** Demand paging reduces memory usage by loading pages into memory only when they are needed. This avoids unnecessary I/O and memory allocation. It allows a process to start with no pages in memory, and pages are brought in only when accessed. This approach ensures that memory is used efficiently, as only the required pages are kept in memory at any given time.

**Key points** (slide quote → follow-up → expected answer):
- **Demand paging brings pages into memory only when needed.**  
  quote: "Or bring a page into memory only when it is needed"  
  follow-up: _What happens if a page is needed but not in memory?_  
  expected: A page fault occurs, and the page is brought into memory from secondary storage.
- **Demand paging reduces unnecessary I/O.**  
  quote: "Less I/O needed, no unnecessary I/O"  
  follow-up: _Why is reducing I/O important for memory management?_  
  expected: Reducing I/O minimizes the time and resources spent loading pages into memory, improving system performance.
- **Demand paging allows a process to start with no pages in memory.**  
  quote: "Extreme case – start process with no pages in memory"  
  follow-up: _What is the significance of starting a process with no pages in memory?_  
  expected: It enables pure demand paging, where the system only loads pages when they are actually accessed, optimizing memory usage.

### [File allocation methods] Explain what contiguous allocation is and why it is considered simple.
*confidence 0.96 · easy · slides [706, 709, 710, 713, 715]*

**Reference:** Contiguous allocation is a method where each file occupies a set of contiguous blocks. This method is considered simple because only the starting location (block #) and length (number of blocks) are required to describe the file. This simplicity makes it easy to manage and access the file data sequentially or directly.

**Key points** (slide quote → follow-up → expected answer):
- **Contiguous allocation is a method where each file occupies a set of contiguous blocks.**  
  quote: "Contiguous allocation – each file occupies set of contiguous blocks"  
  follow-up: _What makes contiguous allocation easier to manage compared to other methods?_  
  expected: It is easier to manage because only the starting block and the length of the file are needed, which reduces the complexity of tracking the file's data.
- **Contiguous allocation is considered simple because only the starting location and length are required.**  
  quote: "Simple – only starting location (block #) and length (number of blocks) are required"  
  follow-up: _Why would knowing just the starting block and length make allocation simpler?_  
  expected: Knowing just the starting block and length simplifies the process of locating and accessing the file's data without needing to traverse pointers or index structures.
- **Contiguous allocation supports both sequential and direct access.**  
  quote: "Supports both sequential and direct access"  
  follow-up: _How does contiguous allocation support direct access to a file?_  
  expected: Direct access is supported because the file's data is stored in contiguous blocks, allowing the system to calculate the exact block number for any given byte offset.

### [Logical vs physical address] Explain the difference between a logical address and a physical address.
*confidence 0.96 · easy · slides [448, 546]*

**Reference:** A logical address is generated by the CPU and is also called a virtual address. A physical address is the address seen by the memory unit. Logical and physical addresses are the same in compile-time and load-time address-binding schemes, but differ in execution-time address-binding schemes.

**Key points** (slide quote → follow-up → expected answer):
- **Logical address is generated by the CPU and is also called a virtual address.**  
  quote: "Logical address – generated by the CPU; also referred to as virtual address"  
  follow-up: _What happens to the logical address before it can be used by the memory unit?_  
  expected: The logical address is translated into a physical address through a process involving segmentation and paging.
- **Physical address is the address seen by the memory unit.**  
  quote: "Physical address – address seen by the memory unit"  
  follow-up: _Why is the physical address important for memory management?_  
  expected: The physical address is necessary for the memory unit to access the correct location in physical memory.
- **Logical and physical addresses are the same in compile-time and load-time address-binding schemes.**  
  quote: "Logical and physical addresses are the same in compile-time and load-time address-binding schemes; logical (virtual) and physical addresses differ in execution-time address-binding scheme"  
  follow-up: _In which scenario do logical and physical addresses differ?_  
  expected: Logical and physical addresses differ in execution-time address-binding schemes, where translation occurs at runtime.

### [Linux and Windows scheduling] Explain how the Completely Fair Scheduler (CFS) in Linux determines which task to run next.
*confidence 0.96 · easy · slides [160, 161, 162, 163, 164]*

**Reference:** The Completely Fair Scheduler (CFS) in Linux determines which task to run next by selecting the task with the lowest virtual run time. This virtual run time is calculated based on the task's priority and includes a decay factor. CFS maintains all runnable tasks in a balanced binary search tree, ordered by their vruntime values. The task at the leftmost node of the tree is selected for execution. This ensures that tasks with higher priority (lower nice values) or those that have been waiting longer are given precedence.

**Key points** (slide quote → follow-up → expected answer):
- **CFS selects the task with the lowest virtual run time.**  
  quote: "To decide next task to run, scheduler picks task with lowest virtual run time."  
  follow-up: _What determines the virtual run time of a task?_  
  expected: The virtual run time is calculated based on the task's priority and includes a decay factor. Lower priority tasks have a higher decay rate.
- **CFS maintains runnable tasks in a balanced binary search tree.**  
  quote: "Each runnable task is placed in a balanced binary search tree whose key is based on the value of vruntime."  
  follow-up: _How does the tree structure help in scheduling?_  
  expected: The tree structure allows the scheduler to efficiently find the task with the lowest vruntime in O(lg N) time, ensuring quick scheduling decisions.
- **Tasks with lower nice values have higher priority.**  
  quote: "A numerically lower nice value indicates a higher relative priority."  
  follow-up: _How does the nice value affect the scheduling?_  
  expected: Tasks with lower nice values receive a higher proportion of CPU time and are prioritized in the scheduling decision.

### [Process creation and termination] Explain how the `popen()` function handles process creation and termination.
*confidence 0.95 · easy · slides [97, 219]*

**Reference:** The `popen()` function handles process creation by forking a child and executing a shell to run the command. It also manages the pipe and standard I/O stream. For termination, it returns a file pointer if successful, and the `pclose()` function is used to close the stream and wait for the command to terminate.

**Key points** (slide quote → follow-up → expected answer):
- **popen() creates a child process and executes a command.**  
  quote: "The function popen() does a fork and exec to execute the cmdstring and returns a standard I/O file pointer."  
  follow-up: _What happens if the fork fails during popen()?_  
  expected: If the fork fails, popen() returns NULL to indicate an error.
- **popen() manages the pipe and I/O redirection.**  
  quote: "These two functions handle all the work: creating a pipe, forking a child, closing the unused ends of the pipe, executing a shell to run the command, and waiting for the command to terminate."  
  follow-up: _How does popen() ensure that the pipe is properly set up?_  
  expected: popen() creates a pipe, forks the child, and closes the unused ends of the pipe to ensure correct I/O redirection.
- **pclose() is used to terminate the child process and retrieve its status.**  
  quote: "The function pclose() closes the standard I/O stream, waits for the command to terminate, and returns the termination status of the shell or -1 on error."  
  follow-up: _What would happen if you don't call pclose() after popen()?_  
  expected: The child process would continue running in the background, and its termination status would not be retrieved, potentially leading to resource leaks.

### [Deadlock conditions] Explain how the four deadlock conditions are interdependent in the occurrence of a deadlock.
*confidence 0.95 · medium · slides [372, 384, 385]*

**Reference:** The four deadlock conditions—mutual exclusion, hold and wait, no preemption, and circular wait—are all necessary for a deadlock to occur. Mutual exclusion ensures that resources are not sharable, which is a prerequisite for the other conditions. Hold and wait allows a process to hold some resources while waiting for others, which is essential for the deadlock to persist. No preemption prevents resources from being forcibly taken, allowing the deadlock to continue. Circular wait creates the cyclic dependency that ties all four conditions together to form a deadlock.

**Key points** (slide quote → follow-up → expected answer):
- **Mutual exclusion is a prerequisite for the other deadlock conditions.**  
  quote: "Mutual exclusion: only one process at a time can use a resource (sharable resources like Read-only files do not require mutually exclusive access and thus cannot be involved in a deadlock."  
  follow-up: _What would happen if mutual exclusion was not a condition?_  
  expected: Without mutual exclusion, resources could be shared, and thus a deadlock could not occur because there would be no exclusive resource contention.
- **Hold and wait allows a process to hold some resources while waiting for others.**  
  quote: "Hold and wait: a process holding at least one resource is waiting to acquire additional resources held by other processes"  
  follow-up: _Why is it important for a process to hold some resources while waiting for others?_  
  expected: It is important because it creates a situation where a process is partially allocated resources, which can lead to a deadlock when combined with other conditions.
- **No preemption prevents resources from being forcibly taken, allowing the deadlock to continue.**  
  quote: "No preemption: a resource can be released only voluntarily by the process holding it, after that process has completed its task"  
  follow-up: _What would happen if a process could be preempted?_  
  expected: If preemption were allowed, a process could be forced to release its resources, breaking the deadlock cycle and preventing a deadlock from occurring.
- **Circular wait creates the cyclic dependency that ties all four conditions together.**  
  quote: "Circular wait: there exists a set {P0, P1, …, Pn} of waiting processes such that P0 is waiting for a resource that is held by P1, P1 is waiting for a resource that is held by P2, …, Pn–1 is waiting for a resource that is held by Pn, and Pn is waiting for a resource that is held by P0."  
  follow-up: _How does circular wait contribute to the deadlock?_  
  expected: Circular wait creates a cycle of resource dependencies that, when combined with mutual exclusion, hold and wait, and no preemption, results in a deadlock.

### [Mutex locks] Explain what a mutex lock is and how it helps solve the critical section problem.
*confidence 0.95 · easy · slides [316, 317]*

**Reference:** A mutex lock is a software tool used by OS designers to solve the critical section problem. It protects a critical section by requiring a process to first acquire() the lock before entering the section and then release() it afterward. This ensures mutual exclusion, as only one process can hold the lock at a time. The lock is typically implemented using a Boolean variable indicating whether the lock is available or not.

**Key points** (slide quote → follow-up → expected answer):
- **Mutex locks are a software solution for the critical section problem.**  
  quote: "OS designers build software tools to solve critical section problem"  
  follow-up: _What is the main purpose of using a mutex lock?_  
  expected: The main purpose is to ensure mutual exclusion when multiple processes access shared resources.
- **Mutex locks require a process to acquire and release the lock to enter and exit the critical section.**  
  quote: "Protect a critical section by first acquire() a lock then release() the lock"  
  follow-up: _What happens if a process does not call release() after acquiring a lock?_  
  expected: It would cause a deadlock, as the lock would remain held indefinitely, preventing other processes from entering the critical section.
- **Mutex locks use a Boolean variable to indicate lock availability.**  
  quote: "Boolean variable indicating if lock is available or not"  
  follow-up: _How is the state of a mutex lock represented in memory?_  
  expected: The state is represented by a Boolean variable that indicates whether the lock is available (false) or held (true).

### [Dining philosophers problem] Explain the core idea of the Dining Philosophers problem.
*confidence 0.95 · easy · slides [343, 344, 345]*

**Reference:** The Dining Philosophers problem models a scenario where philosophers alternate between thinking and eating. To eat, a philosopher must pick up both adjacent chopsticks, which are shared resources. The challenge is to design a protocol that avoids deadlock, resource starvation, and ensures fair access to the chopsticks.

**Key points** (slide quote → follow-up → expected answer):
- **Philosophers alternate between thinking and eating.**  
  quote: "Philosophers spend their lives alternating thinking and eating"  
  follow-up: _What happens when a philosopher wants to eat but cannot get both chopsticks?_  
  expected: The philosopher cannot eat and must wait until both chopsticks are available.
- **Each philosopher requires two chopsticks to eat.**  
  quote: "Need both to eat, then release both when done"  
  follow-up: _What would happen if a philosopher tried to eat with only one chopstick?_  
  expected: The philosopher would not be able to eat and would have to wait until both chopsticks are available.
- **Chopsticks are shared resources that must be coordinated.**  
  quote: "Shared data - Bowl of rice (data set), Semaphore chopstick [5] initialized to 1"  
  follow-up: _Why are the chopsticks considered a shared resource?_  
  expected: Because multiple philosophers may attempt to use the same chopstick at the same time, and only one can hold it at a time.

### [Page faults] Explain how the operating system handles a page fault and how it manages the page-fault frequency to avoid thrashing.
*confidence 0.95 · medium · slides [571, 572, 625]*

**Reference:** When a page fault occurs, the operating system first checks if the reference is invalid. If not, it finds a free frame, swaps in the required page, updates the page tables, and restarts the instruction. To manage page-fault frequency, the system adjusts the number of frames allocated to a process based on its actual page-fault rate. If the rate is too low, the process loses a frame; if too high, it gains a frame. This helps control thrashing by balancing memory allocation with usage patterns.

**Key points** (slide quote → follow-up → expected answer):
- **The operating system first checks if the page reference is invalid or not in memory.**  
  quote: "Operating system looks at another table to decide: Invalid reference ⇒abort; Just not in memory"  
  follow-up: _What happens if the page reference is invalid?_  
  expected: The operating system aborts the process because the reference is invalid.
- **The system finds a free frame and swaps the required page into memory.**  
  quote: "Find free frame; Swap page into frame via scheduled disk operation"  
  follow-up: _What happens if there are no free frames available?_  
  expected: The system may have to evict a page from memory using a page replacement algorithm.
- **The system adjusts the number of frames allocated to a process based on its page-fault rate.**  
  quote: "Establish 'acceptable' page-fault frequency (PFF) rate and use local replacement policy; If actual rate too low, process loses frame; If actual rate too high, process gains frame."  
  follow-up: _Why would a process lose a frame?_  
  expected: Because its page-fault rate is too low, indicating it's not using memory efficiently.
- **Managing page-fault frequency helps avoid thrashing.**  
  quote: "With the working-set strategy, we may have to swap out a process. If page fault increases and no free frames available"  
  follow-up: _What is thrashing and how does page-fault frequency help avoid it?_  
  expected: Thrashing is when the system spends more time swapping pages than executing instructions. Controlling page-fault frequency helps prevent this by balancing memory allocation.

### [Disk scheduling] Explain what makes disk scheduling an important part of an operating system.
*confidence 0.95 · easy · slides [771, 772]*

**Reference:** Disk scheduling is important because it directly affects the performance and fairness of disk I/O operations. This modularity ensures flexibility and adaptability to different workloads.

**Key points** (slide quote → follow-up → expected answer):
- **Disk scheduling is a modular component of the operating system.**  
  quote: "The disk-scheduling algorithm should be written as a separate module of the operating system, allowing it to be replaced with a different algorithm if necessary."  
  follow-up: _Why would an operating system want to replace the disk-scheduling algorithm?_  
  expected: Because different algorithms may be more suitable for different workloads or system requirements, ensuring optimal performance.
- **Disk scheduling affects the performance of disk I/O operations.**  
  quote: "Performance depends on the number and types of requests."  
  follow-up: _How might the type of request influence disk scheduling decisions?_  
  expected: The type of request can influence which algorithm is more effective, such as using SSTF for common requests or SCAN for heavy disk loads.
- **Disk scheduling helps balance fairness and efficiency.**  
  quote: "SCAN and C-SCAN perform better for systems that place a heavy load on the disk - Less starvation."  
  follow-up: _What is starvation in the context of disk scheduling?_  
  expected: Starvation occurs when certain requests are consistently delayed, and algorithms like SCAN help reduce this by ensuring all requests are eventually served.

### [Contiguous memory allocation] Explain how contiguous memory allocation strategies like first-fit, best-fit, and worst-fit impact memory fragmentation and efficiency, and why some are preferred over others.
*confidence 0.94 · medium · slides [471, 472, 473, 474]*

**Reference:** Contiguous memory allocation strategies impact fragmentation and efficiency differently. First-fit is generally faster and better than worst-fit in terms of storage utilization. Best-fit minimizes leftover space but requires searching the entire list, which can be slower. Worst-fit, while producing the largest leftover hole, is less efficient in memory usage. External fragmentation is a concern in all strategies, but compaction can help reduce it if relocation is dynamic.

**Key points** (slide quote → follow-up → expected answer):
- **First-fit is generally faster and better than worst-fit in terms of storage utilization.**  
  quote: "First-fit and best-fit better than worst-fit in terms of speed and storage utilization"  
  follow-up: _Why might first-fit be considered better than worst-fit in terms of storage utilization?_  
  expected: Because first-fit allocates the first suitable block, leaving larger holes for future allocations, which improves overall memory utilization.
- **Best-fit minimizes leftover space but requires searching the entire list, which can be slower.**  
  quote: "Best-fit: Allocate the smallest hole that is big enough; must search entire list, unless ordered by size"  
  follow-up: _What is a potential downside of using best-fit in contiguous memory allocation?_  
  expected: Best-fit can be slower because it requires searching the entire list of free holes to find the smallest suitable one.
- **Worst-fit produces the largest leftover hole, which is less efficient in memory usage.**  
  quote: "Worst-fit: Allocate the largest hole; must also search entire list - Produces the largest leftover hole"  
  follow-up: _Why is worst-fit considered less efficient in terms of memory usage?_  
  expected: Because worst-fit leaves the largest possible unused space, which may not be usable for future allocations, increasing external fragmentation.
- **External fragmentation is a concern in all strategies, but compaction can help reduce it if relocation is dynamic.**  
  quote: "Reduce external fragmentation by compaction - Compaction is possible only if relocation is dynamic, and is done at execution time"  
  follow-up: _What is one way to mitigate external fragmentation in contiguous memory allocation?_  
  expected: Compaction can be used to shuffle memory contents and consolidate free space into a single block, provided relocation is dynamic.

### [Context switching] Explain how context switching affects the performance of a process in a round-robin scheduling system, and why the choice of time quantum is important.
*confidence 0.91 · medium · slides [140, 459, 460, 466]*

**Reference:** Context switching introduces overhead that can slow down process execution, especially when the time quantum is small. A smaller quantum leads to more frequent context switches, which increases the total execution time. However, a larger quantum may reduce context switches but could lead to longer waiting times for processes. The choice of time quantum is a trade-off between minimizing context-switch overhead and ensuring fair CPU allocation among processes.

**Key points** (slide quote → follow-up → expected answer):
- **The time quantum directly influences the number of context switches.**  
  quote: "If the quantum is 6 time units, the process requires 2 quanta, resulting in one context switch."  
  follow-up: _What happens if the quantum is reduced further?_  
  expected: The number of context switches increases, which can slow down the overall execution of the process.
- **Context switch time is a small fraction of the time quantum in modern systems.**  
  quote: "The time required for a context switch is typically less than 10 microseconds. Thus, the context-switch time is a small fraction of the time quantum."  
  follow-up: _Why is it important that context-switch time is small relative to the quantum?_  
  expected: Because a larger fraction of the quantum would be spent on context switching, reducing the effective CPU time available for the process.
- **Context switching can be costly if it involves swapping processes in and out of memory.**  
  quote: "If next processes to be put on CPU is not in memory, need to swap out a process and swap in target process."  
  follow-up: _What could make a context switch particularly expensive?_  
  expected: If the process being switched in or out is large, or if swapping is required, the context switch can take significantly longer.

### [User-level vs kernel-level threads] How does the many-to-one model of user-level threads affect concurrency and parallelism in a multi-core system?
*confidence 0.91 · medium · slides [254, 255, 257, 262, 263]*

**Reference:** In the many-to-one model, multiple user-level threads are mapped to a single kernel thread. This means that if one user-level thread blocks, all threads in the process block, because they share the same kernel thread. As a result, the many-to-one model limits concurrency and parallelism on multi-core systems, since only one thread can run at a time on a single CPU core. This is why few systems currently use this model, as it does not take full advantage of multi-core hardware.

**Key points** (slide quote → follow-up → expected answer):
- **A single kernel thread is shared among multiple user-level threads.**  
  quote: "Many user-level threads mapped to single kernel thread"  
  follow-up: _What happens if one user-level thread in the many-to-one model blocks?_  
  expected: All threads in the process block because they share the same kernel thread.
- **Concurrency is limited because only one thread can run at a time.**  
  quote: "One thread blocking causes all to block"  
  follow-up: _How does this affect the ability of a process to run multiple threads in parallel?_  
  expected: It limits parallelism because only one thread can execute at a time on a single CPU core.
- **The many-to-one model is not well-suited for multi-core systems.**  
  quote: "Multiple threads may not run in parallel on multicore system because only one may be in kernel at a time"  
  follow-up: _Why might this model be less common in modern systems?_  
  expected: Because it does not take advantage of multi-core hardware, which can run multiple threads in parallel.

### [Signals] How do SIGINT and SIGALRM differ in their use and behavior when delivered to a process?
*confidence 0.91 · medium · slides [431]*

**Reference:** SIGINT is generated when a user presses Control-C and is used to terminate a program from the terminal. SIGALRM is generated when a timer set by the alarm function goes off. These signals differ in their origin and purpose: SIGINT is user-initiated and typically used for graceful termination, while SIGALRM is system-initiated and used for timing events. Both are asynchronous, but their handling can be customized by the process.

**Key points** (slide quote → follow-up → expected answer):
- **SIGINT is user-initiated and used for program termination.**  
  quote: "SIGINT is a signal generated when a user presses Control-C. This will terminate the program from the terminal."  
  follow-up: _What happens if a process ignores SIGINT?_  
  expected: The process will continue running as if the signal was not received, unless it has explicitly handled the signal.
- **SIGALRM is system-initiated and used for timing events.**  
  quote: "SIGALRM is generated when the timer set by the alarm function goes off."  
  follow-up: _Can a process control when SIGALRM is delivered?_  
  expected: Yes, a process can set and reset the timer using the alarm function, which determines when SIGALRM is delivered.
- **Both signals are asynchronous but have different use cases.**  
  quote: "A signal is a kind of software interrupt, used to announce asynchronous events to a process."  
  follow-up: _Why might a process need to handle SIGALRM differently than SIGINT?_  
  expected: Because SIGALRM is used for timing events, a process may need to perform cleanup or resume operations, whereas SIGINT is typically used for immediate termination.

### [Bash shell and cron] Explain how cron jobs are scheduled and executed in a Unix-like system, and why it's important to understand the crontab format.
*confidence 0.91 · medium · slides [184, 185]*

**Reference:** Cron is a daemon that runs continuously in the background and wakes up to handle periodic service requests. It reads the crontab for predefined scripts and executes them according to a specific syntax. Understanding the crontab format is important because it determines when and how often jobs are run, ensuring they execute at the intended times.

**Key points** (slide quote → follow-up → expected answer):
- **Cron is a daemon that runs continuously in the background and wakes up to handle periodic service requests.**  
  quote: "In Unix and Linux, cron is a daemon, which is an unattended program that runs continuously in the background and wakes up (executes) to handle periodic service requests when required."  
  follow-up: _What happens if the cron daemon is not running?_  
  expected: The cron daemon must be running for scheduled jobs to execute; otherwise, the jobs will not be triggered.
- **Cron reads the crontab for predefined scripts and executes them according to a specific syntax.**  
  quote: "The cron reads the crontab (cron tables) for running predefined scripts."  
  follow-up: _Why is the syntax of the crontab important?_  
  expected: The syntax defines the schedule for the job, including minute, hour, day, month, and day of the week, which determines when the job will run.
- **Understanding the crontab format is important because it determines when and how often jobs are run.**  
  quote: "By using a specific syntax, you can configure a cron job to schedule scripts or other commands to run automatically."  
  follow-up: _What could happen if the crontab format is incorrect?_  
  expected: Incorrect formatting can cause the cron job to not run at all or run at unintended times, leading to unexpected behavior or missed tasks.

### [Preemptive vs non-preemptive scheduling] Explain how preemptive scheduling differs from non-preemptive scheduling in terms of when scheduling decisions occur and the implications for system behavior.
*confidence 0.91 · medium · slides [126, 127, 135]*

**Reference:** Preemptive scheduling allows the operating system to interrupt a running process and switch to another process, which can occur during transitions such as running to waiting, running to ready, or waiting to ready. Non-preemptive scheduling does not allow such interruptions, and scheduling decisions only happen when a process transitions to the waiting or terminated state. This difference impacts system responsiveness and the potential for race conditions, as preemptive scheduling may require mechanisms like mutex locks to protect shared data.

**Key points** (slide quote → follow-up → expected answer):
- **Preemptive scheduling allows the operating system to interrupt a running process.**  
  quote: "CPU scheduling decisions may take place when a process Switches from running to waiting state Switches from running to ready state Switches from waiting to ready Terminates"  
  follow-up: _What happens if the operating system cannot interrupt a running process?_  
  expected: The system would use non-preemptive scheduling, and the CPU will only be allocated to another process when the current one voluntarily yields control, such as by blocking or terminating.
- **Non-preemptive scheduling decisions only occur when a process transitions to waiting or terminates.**  
  quote: "Scheduling under 1 and 4 is non-preemptive"  
  follow-up: _Why might non-preemptive scheduling be less responsive than preemptive scheduling?_  
  expected: Because non-preemptive scheduling cannot interrupt a running process, it may delay the execution of higher-priority processes until the current one completes or voluntarily yields the CPU.
- **Preemptive scheduling may require mechanisms like mutex locks to prevent race conditions.**  
  quote: "A pre-emptive kernel requires mechanisms such as mutex locks to prevent race conditions when accessing shared kernel data structures."  
  follow-up: _What is a potential downside of preemptive scheduling?_  
  expected: Preemptive scheduling can lead to race conditions if shared data is accessed without proper synchronization, requiring additional mechanisms like mutex locks to ensure data consistency.

### [Priority scheduling] Explain how priority scheduling can lead to starvation and what is a common solution to this problem.
*confidence 0.91 · medium · slides [135]*

**Reference:** Priority scheduling can lead to starvation because low-priority processes may never execute if higher-priority processes keep arriving. A common solution to this problem is aging, which gradually increases the priority of processes over time to ensure they eventually get executed.

**Key points** (slide quote → follow-up → expected answer):
- **Priority scheduling can lead to starvation.**  
  quote: "Problem ≡ Starvation – low priority processes may never execute"  
  follow-up: _What happens if a low-priority process keeps waiting for the CPU?_  
  expected: It may never execute, leading to starvation.
- **Starvation is a problem in priority scheduling.**  
  quote: "Problem ≡ Star,vation – low priority processes may never execute"  
  follow-up: _Why is starvation a concern in priority scheduling?_  
  expected: Because high-priority processes may continuously arrive, preventing lower-priority ones from ever running.
- **Aging is a common solution to starvation in priority scheduling.**  
  quote: "Solution ≡ Aging – as time progresses increase the priority of the process"  
  follow-up: _How can we prevent low-priority processes from being starved?_  
  expected: By using aging, which increases the priority of waiting processes over time.

### [Multiprocessor scheduling] Explain how symmetric multiprocessing differs from asymmetric multiprocessing in terms of scheduling and system complexity.
*confidence 0.91 · medium · slides [151]*

**Reference:** Symmetric multiprocessing allows each processor to self-schedule, with processes possibly shared in a common ready queue or private queues. This leads to more complex scheduling decisions compared to asymmetric multiprocessing, where a single master processor handles all scheduling and system activities, while others execute only user code. The complexity in symmetric multiprocessing arises from the need for coordination and data sharing across multiple processors, which is less of an issue in asymmetric multiprocessing due to centralized control.

**Key points** (slide quote → follow-up → expected answer):
- **Symmetric multiprocessing allows each processor to self-schedule.**  
  quote: "Each processor is self-scheduling. All processes may be in a common ready queue, or each processor may have its own private queue of ready processes."  
  follow-up: _What happens if all processes are in a common ready queue in a symmetric multiprocessing system?_  
  expected: In that case, the processors take turns selecting processes from the same queue, which can lead to load balancing but may also introduce contention for access to the shared queue.
- **Asymmetric multiprocessing has a single master processor handling scheduling and system activities.**  
  quote: "CPU scheduling in a multiprocessor system has all scheduling decisions, I/O processing, and other system activities handled by a single processor—the master server."  
  follow-up: _Why might asymmetric multiprocessing be simpler than symmetric multiprocessing?_  
  expected: Asymmetric multiprocessing is simpler because only one processor accesses the system data structures, reducing the need for data sharing and coordination between processors.
- **Symmetric multiprocessing introduces more complexity due to data sharing and coordination.**  
  quote: "Scheduling problems become correspondingly more complex."  
  follow-up: _How does the complexity of symmetric multiprocessing affect system design?_  
  expected: The complexity of symmetric multiprocessing affects system design by requiring mechanisms for data sharing, synchronization, and load balancing across multiple processors.

### [Race condition] Explain how a race condition can occur in the context of the `fork` system call and why it's important to use wait functions properly.
*confidence 0.91 · medium · slides [101]*

**Reference:** A race condition can occur with `fork` when the logic after the call depends on whether the parent or child runs first, which is unpredictable. This can lead to incorrect behavior if the program assumes a specific order of execution. Using wait functions properly ensures that the parent process waits for the child to finish, avoiding race conditions by synchronizing the processes.

**Key points** (slide quote → follow-up → expected answer):
- **The outcome of a race condition depends on the unpredictable order of process execution.**  
  quote: "A race condition occurs when multiple processes are trying to do something with shared data and the final outcome depends on the order in which the processes run."  
  follow-up: _What would happen if the order of execution was predictable?_  
  expected: If the order was predictable, the race condition would not occur, as the outcome would be consistent regardless of which process ran first.
- **The `fork` system call is a common source of race conditions due to the uncertainty of which process runs first.**  
  quote: "The fork function is a lively breeding ground for race conditions, if the logic after the fork either explicitly or implicitly depends on whether the parent or child runs first after the fork."  
  follow-up: _Why is `fork` a common source of race conditions?_  
  expected: Because the logic after `fork` may depend on which process (parent or child) runs first, and this order is unpredictable.
- **Proper use of wait functions is essential to avoid race conditions in process synchronization.**  
  quote: "A process that wants to wait for a child to terminate must call one of the wait functions."  
  follow-up: _What would happen if a process didn't call a wait function after `fork`?_  
  expected: The parent process might proceed before the child completes, leading to a race condition and potentially incorrect behavior.

### [Critical section problem] Explain how the progress condition ensures fairness in the critical section problem, and why it's important to assume that processes execute at a nonzero speed.
*confidence 0.91 · medium · slides [293]*

**Reference:** The progress condition ensures that if no process is in its critical section and some processes want to enter, the selection of the next process cannot be postponed indefinitely. This prevents starvation by guaranteeing that every process that wants to enter its critical section will eventually get a turn. The assumption that processes execute at a nonzero speed is important because it ensures that processes are not frozen or blocked indefinitely, allowing the system to make progress toward resolving the request.

**Key points** (slide quote → follow-up → expected answer):
- **The progress condition ensures no process is indefinitely postponed from entering its critical section.**  
  quote: "If no process is executing in its critical section and there exist some processes that wish to enter their critical section, then the selection of the processes that will enter the critical section next cannot be postponed indefinitely."  
  follow-up: _What would happen if a process could be indefinitely postponed from entering its critical section?_  
  expected: It would result in starvation, where some processes are never allowed to enter their critical section, violating the progress condition.
- **The assumption of nonzero speed ensures processes are not frozen and the system can make progress.**  
  quote: "Assume that each process executes at a nonzero speed"  
  follow-up: _Why is it important that processes execute at a nonzero speed?_  
  expected: Because if a process were to execute at zero speed, it could be indefinitely blocked, making it impossible to determine when it would be allowed to enter its critical section.
- **Progress is about fairness in selecting which process enters the critical section next.**  
  quote: "Progress - If no process is executing in its critical section and there exist some processes that wish to enter their critical section, then the selection of the processes that will enter the critical section next cannot be postponed indefinitely"  
  follow-up: _How does the progress condition relate to fairness?_  
  expected: The progress condition ensures that the selection of which process enters the critical section next is fair, preventing any process from being indefinitely denied access.

### [Peterson's solution] Explain how the turn variable in Peterson’s solution contributes to the progress of the algorithm.
*confidence 0.91 · medium · slides [295, 296]*

**Reference:** The turn variable in Peterson’s solution ensures that one process does not starve the other. It indicates whose turn it is to enter the critical section, allowing the other process to yield. This guarantees that both processes can eventually enter their critical sections, maintaining progress.

**Key points** (slide quote → follow-up → expected answer):
- **The turn variable ensures that one process does not starve the other.**  
  quote: "The variable turn indicates whose turn it is to enter the critical section"  
  follow-up: _What happens if the turn variable is not used in Peterson’s solution?_  
  expected: Without the turn variable, a process could potentially be denied access to the critical section indefinitely, leading to starvation.
- **The turn variable allows the other process to yield.**  
  quote: "The variable turn indicates whose turn it is to enter the critical section"  
  follow-up: _How does the turn variable help the other process decide to wait?_  
  expected: The turn variable signals that the other process should yield, allowing it to proceed to the waiting loop and release the critical section.
- **The turn variable guarantees progress in Peterson’s solution.**  
  quote: "The variable turn indicates whose turn it is to enter the critical section"  
  follow-up: _Why is progress important in a synchronization algorithm?_  
  expected: Progress ensures that no process is indefinitely blocked from entering the critical section, which is essential for correct and fair resource sharing.

### [Resource allocation graph] How does the resource allocation graph algorithm detect deadlocks in a system with a single instance of each resource type?
*confidence 0.91 · medium · slides [373, 374, 394, 413]*

**Reference:** The resource allocation graph algorithm detects deadlocks by periodically checking for cycles in the graph. A cycle in the graph indicates a deadlock because it means there is a set of processes and resources where each process is waiting for a resource held by another process in the set. The algorithm searches for cycles, which requires an order of n² operations, where n is the number of vertices in the graph. This approach ensures that any deadlock is detected by identifying such cycles in the resource allocation graph.

**Key points** (slide quote → follow-up → expected answer):
- **The algorithm detects deadlocks by checking for cycles in the resource allocation graph.**  
  quote: "Periodically invoke an algorithm that searches for a cycle in the graph. If there is a cycle, there exists a deadlock"  
  follow-up: _What happens if the algorithm does not find a cycle in the graph?_  
  expected: If the algorithm does not find a cycle, it means there is no deadlock in the system at that moment.
- **A cycle in the graph indicates a deadlock because processes are waiting for resources held by each other.**  
  quote: "Deadlocks are described precisely with directed graphs called system resource-allocation graph"  
  follow-up: _Why is a cycle in the graph considered a deadlock?_  
  expected: A cycle indicates that each process in the cycle is waiting for a resource held by another process in the cycle, creating a circular dependency that cannot be resolved.
- **The algorithm requires an order of n² operations to search for cycles in the graph.**  
  quote: "An algorithm to detect a cycle in a graph requires an order of n² operations, where n is the number of vertices in the graph"  
  follow-up: _Why is the algorithm's time complexity important for deadlock detection?_  
  expected: The time complexity is important because it determines how efficiently the system can detect deadlocks, which is crucial for maintaining system performance and responsiveness.

### [Fragmentation] Explain how external fragmentation affects memory allocation and why compaction is a solution, but has limitations.
*confidence 0.91 · medium · slides [473, 474]*

**Reference:** External fragmentation occurs when the total memory space exists to satisfy a request, but it is not contiguous. Compaction is a solution because it shuffles memory contents to place all free memory together in one large block. However, compaction has limitations because it requires relocation to be dynamic and is done at execution time, which can cause I/O problems by latching a job in memory during I/O operations.

**Key points** (slide quote → follow-up → expected answer):
- **External fragmentation is when the total memory space exists to satisfy a request, but it is not contiguous.**  
  quote: "External Fragmentation – total memory space exists to satisfy a request, but it is not contiguous"  
  follow-up: _What happens when a process needs memory but the available memory is fragmented?_  
  expected: The process cannot be allocated memory because the available memory is not contiguous.
- **Compaction is a solution to external fragmentation by consolidating free memory into a single block.**  
  quote: "Reduce external fragmentation by compaction – Shuffle memory contents to place all free memory together in one large block"  
  follow-up: _Why is compaction not always feasible?_  
  expected: Because compaction requires relocation to be dynamic and done at execution time, which can interfere with I/O operations.
- **Compaction has limitations due to I/O problems and the need for dynamic relocation.**  
  quote: "Compaction is possible only if relocation is dynamic, and is done at execution time – I/O problem – Latch job in memory while it is involved in I/O – Do I/O only into OS buffers"  
  follow-up: _How does I/O affect the ability to compact memory?_  
  expected: I/O operations can prevent compaction by latching a job in memory, making it impossible to shuffle memory contents during I/O.

### [Translation lookaside buffer] How does the use of an ASID in a TLB improve system performance, and what trade-offs are involved in its implementation?
*confidence 0.91 · medium · slides [514, 516, 517]*

**Reference:** The use of an ASID in a TLB allows the TLB to distinguish between entries for different processes, which prevents the need to flush the entire TLB during context switches. This improves performance by reducing the overhead of invalidating stale entries. However, the trade-off is that the TLB must store additional information (the ASID) for each entry, which increases the size and complexity of the TLB.

**Key points** (slide quote → follow-up → expected answer):
- **The use of an ASID in a TLB allows the TLB to distinguish between entries for different processes.**  
  quote: "Some TLB store address-space identifiers (ASIDs) in each TLB entry"  
  follow-up: _What happens if a TLB does not include an ASID and a context switch occurs?_  
  expected: The entire TLB would need to be flushed, which is inefficient and increases context switch overhead.
- **The inclusion of an ASID prevents the need to flush the entire TLB during context switches.**  
  quote: "Otherwise need to flush at every context switch"  
  follow-up: _Why would a system need to flush the entire TLB during a context switch without an ASID?_  
  expected: Because the TLB entries are not associated with any specific process, and entries from the previous process would be invalid for the new process.
- **The use of an ASID increases the size and complexity of the TLB.**  
  quote: "Some TLBs store address-space identifiers (ASIDs) in each TLB entry"  
  follow-up: _What is a potential downside of storing ASIDs in each TLB entry?_  
  expected: It increases the size of each TLB entry, which may reduce the number of entries that can be stored and increase the complexity of the TLB hardware.

### [Multilevel page tables] Explain how hierarchical page tables reduce memory usage compared to a flat page table, and what trade-offs they introduce.
*confidence 0.91 · medium · slides [524, 525, 533, 534, 535, 537]*

**Reference:** Hierarchical page tables break up the logical address space into multiple page tables, reducing memory usage by only allocating page table entries for used address ranges. This avoids the need for a single large flat page table, which would require storing all possible entries even for unused address space. However, this approach introduces a trade-off: while memory usage is reduced, the time to translate a virtual address increases because multiple levels of page tables must be accessed.

**Key points** (slide quote → follow-up → expected answer):
- **Hierarchical page tables break up the logical address space into multiple page tables.**  
  quote: "Break up the logical address space into multiple page tables"  
  follow-up: _What happens if a process uses a large contiguous address space?_  
  expected: The hierarchical page tables would need to allocate more entries at each level, potentially increasing memory usage and reducing the benefit of the hierarchical structure.
- **Hierarchical page tables reduce memory usage by only allocating entries for used address ranges.**  
  quote: "Memory structures for paging can get huge using straight-forward methods"  
  follow-up: _Why would a flat page table require more memory?_  
  expected: A flat page table requires storing entries for all possible logical addresses, even those not used by the process, leading to significant memory overhead.
- **Hierarchical page tables introduce increased translation time due to multiple levels of access.**  
  quote: "We then page the page table"  
  follow-up: _How does this affect the performance of address translation?_  
  expected: Address translation becomes slower because the system must access multiple levels of page tables to find the final physical address.

### [Swapping] Explain how swapping supports priority-based scheduling and why it's important for memory management.
*confidence 0.91 · medium · slides [456, 457]*

**Reference:** Swapping supports priority-based scheduling through the roll out, roll in variant, where lower-priority processes are swapped out to make room for higher-priority ones. This is important for memory management because it allows the system to temporarily free up physical memory, ensuring that higher-priority processes can be loaded and executed without delay. The total transfer time is directly proportional to the amount of memory swapped, which highlights the trade-off between responsiveness and performance.

**Key points** (slide quote → follow-up → expected answer):
- **Swapping supports priority-based scheduling through roll out, roll in.**  
  quote: "Roll out, roll in – swapping variant used for priority-based scheduling algorithms; lower-priority process is swapped out so higher-priority process can be loaded and executed"  
  follow-up: _What happens if a higher-priority process arrives while a lower-priority one is running?_  
  expected: The lower-priority process is swapped out to make room for the higher-priority one, ensuring it can be executed immediately.
- **Swapping allows memory usage to exceed physical memory capacity.**  
  quote: "Total physical memory space of processes can exceed physical memory"  
  follow-up: _Why would a system need to allow memory usage to exceed physical memory?_  
  expected: To support multiple processes running simultaneously, even if their combined memory usage exceeds the physical memory available.
- **Swapping is a major factor in determining transfer time.**  
  quote: "Major part of swap time is transfer time; total transfer time is directly proportional to the amount of memory swapped"  
  follow-up: _How does the amount of memory swapped affect system performance?_  
  expected: Larger memory swaps take longer to transfer, which can delay process execution and reduce system responsiveness.

### [Operating system functions] Explain how the operating system ensures efficient resource allocation and protection in a multiuser environment.
*confidence 0.91 · medium · slides [14, 80, 81, 82, 83, 84]*

**Reference:** The operating system ensures efficient resource allocation by managing the distribution of resources like CPU cycles, memory, and I/O devices among multiple users or processes. This is necessary because when multiple users or jobs run concurrently, resources must be allocated to each of them. Protection and security are also ensured through controlled access to system resources, preventing unauthorized use and interference between concurrent processes.

**Key points** (slide quote → follow-up → expected answer):
- **Resource allocation involves distributing CPU cycles, memory, and I/O devices among multiple users or processes.**  
  quote: "Resource allocation - When multiple users or multiple jobs running concurrently, resources must be allocated to each of them. Many types of resources - CPU cycles, main memory, file storage, I/O devices."  
  follow-up: _What happens if the OS fails to allocate resources properly among multiple users?_  
  expected: The system may experience resource contention, leading to performance degradation or denial of service for some users.
- **Protection ensures that access to system resources is controlled to prevent unauthorized use and interference between processes.**  
  quote: "Protection and security - The owners of information stored in a multiuser or networked computer system may want to control use of that information, concurrent processes should not interfere with each other."  
  follow-up: _Why is it important for the OS to control access to system resources?_  
  expected: To prevent unauthorized access, data corruption, and ensure fair and secure usage of the system by all users.
- **Efficient resource allocation is necessary to ensure the system operates smoothly and fairly for all users.**  
  quote: "Another set of OS functions exists for ensuring the efficient operation of the system itself via resource sharing."  
  follow-up: _How does the OS balance between resource allocation and protection?_  
  expected: The OS uses mechanisms like scheduling, memory management, and access control to balance resource allocation and protection, ensuring both efficiency and security.

### [Threads] Explain how threads improve the scalability of a system, and why this is important for modern applications.
*confidence 0.91 · medium · slides [231, 232, 234, 235, 236]*

**Reference:** Threads improve scalability by allowing a process to take advantage of multiprocessor architectures. Threads can run on multiple cores in parallel, which is essential for handling complex tasks efficiently. This is important for modern applications because most applications are multithreaded, and they often need to perform multiple tasks simultaneously, such as downloading and watching a video.

**Key points** (slide quote → follow-up → expected answer):
- **Threads enable scalability by running on multiple cores in parallel.**  
  quote: "Scalability – process can take advantage of multiprocessor architectures. Threads can run on multiple cores parallelly"  
  follow-up: _Why would a system with multiple cores benefit from threads?_  
  expected: Because threads can be scheduled on different cores, allowing true parallel execution and improving performance.
- **Scalability is important for modern applications that perform multiple tasks simultaneously.**  
  quote: "Most modern applications are multithreaded. Threads run within application. Multiple tasks with the application can be implemented by separate threads."  
  follow-up: _Can you give an example of a modern application that benefits from thread scalability?_  
  expected: A web browser is an example, as it can load content, play videos, and fetch data from the network using separate threads.
- **Thread scalability reduces the need for multiple processes, which are more resource-intensive.**  
  quote: "Process creation is heavy-weight while thread creation is light-weight. Process creation if time consuming, resource intensive"  
  follow-up: _How does thread creation being lightweight affect scalability?_  
  expected: Lightweight thread creation allows more threads to be created quickly, enabling better utilization of multiple cores and improving overall system performance.

### [Logical vs physical address] How does the address-binding scheme affect the relationship between logical and physical addresses during program execution?
*confidence 0.91 · medium · slides [448, 546]*

**Reference:** The address-binding scheme determines whether logical and physical addresses are the same or different. In execution-time address-binding, logical and physical addresses differ because the CPU generates logical addresses, which must be translated to physical addresses by the memory management unit. In contrast, during compile-time or load-time binding, logical and physical addresses are the same. This distinction is critical for understanding how memory management operates in different execution environments.

**Key points** (slide quote → follow-up → expected answer):
- **Logical and physical addresses differ in execution-time address-binding.**  
  quote: "Logical and physical addresses are the same in compile-time and load-time address-binding schemes; logical (virtual) and physical addresses differ in execution-time address-binding scheme."  
  follow-up: _What happens to logical addresses when the program is running and memory is being accessed?_  
  expected: They are translated into physical addresses by the memory management unit during execution.
- **Logical addresses are generated by the CPU.**  
  quote: "Logical address – generated by the CPU; also referred to as virtual address."  
  follow-up: _What is the role of the CPU in the address-binding process?_  
  expected: The CPU generates logical addresses, which must be translated into physical addresses before accessing memory.
- **The memory management unit (MMU) is responsible for translating logical to physical addresses.**  
  quote: "The segmentation and paging units form the equivalent of the memory-management unit (MMU)."  
  follow-up: _What is the role of the segmentation and paging units in address translation?_  
  expected: They work together to translate logical addresses into physical addresses through segmentation and paging.

### [File system concepts] Explain how the file system maps logical file names to physical storage locations on a disk, and why this mapping is important for efficient data access.
*confidence 0.91 · medium · slides [639, 640, 689]*

**Reference:** The file system maps logical file names to physical storage locations through the directory structure, which contains the file’s name and its unique identifier. The identifier then locates the file attributes, including the file’s location on the disk. This mapping is important for efficient data access because it allows the file system to quickly locate and retrieve file data without requiring the user to know the physical location of the file on the disk.

**Key points** (slide quote → follow-up → expected answer):
- **The directory structure contains the file’s name and its unique identifier.**  
  quote: "The information about all files is kept in the directory structure, which also resides on secondary storage. Directory entry consists of the file’s name and its unique identifier."  
  follow-up: _What happens if the file system could not associate a file name with its unique identifier?_  
  expected: The system would not be able to locate the file on the disk, making data retrieval impossible.
- **The unique identifier locates the file attributes, including the file’s physical location.**  
  quote: "The identifier in turn locates the file attributes."  
  follow-up: _Why is it important for the file system to know the file’s physical location?_  
  expected: It allows the file system to efficiently retrieve the file data from the disk, which is necessary for both reading and writing operations.
- **This mapping enables the file system to provide a user-friendly interface to the physical storage.**  
  quote: "File system resides on secondary storage (disks) – Provided user interface to storage, mapping logical to physical."  
  follow-up: _How would the user experience be affected if this mapping was not done by the file system?_  
  expected: The user would need to directly interact with the physical storage, which is not practical or user-friendly.

### [User mode vs kernel mode] Explain how user mode and kernel mode help protect the operating system from user programs.
*confidence 0.91 · medium · slides [48]*

**Reference:** User mode and kernel mode help protect the operating system by using a mode bit provided by hardware to distinguish between user code and kernel code. Some instructions are designated as privileged and can only be executed in kernel mode, preventing user programs from directly accessing critical system resources. System calls allow user programs to request services from the kernel, temporarily switching to kernel mode, and then returning to user mode after the call completes.

**Key points** (slide quote → follow-up → expected answer):
- **User mode and kernel mode use a hardware-provided mode bit to distinguish between user and kernel code.**  
  quote: "Mode bit provided by hardware. Provides ability to distinguish when system is running user code or kernel code."  
  follow-up: _What would happen if a user program could directly access privileged instructions?_  
  expected: The operating system and other system components would be vulnerable to corruption or malicious activity, as user programs could directly manipulate hardware or system resources.
- **Privileged instructions can only be executed in kernel mode.**  
  quote: "Some instructions designated as privileged, only executable in kernel mode."  
  follow-up: _Why are some instructions considered privileged?_  
  expected: Because they allow direct access to hardware or critical system resources, which could compromise the stability and security of the operating system if executed by untrusted user code.
- **System calls allow user programs to request kernel services while maintaining mode separation.**  
  quote: "System call changes mode to kernel, return from call resets it to user."  
  follow-up: _What would happen if a system call didn't switch to kernel mode?_  
  expected: The user program would be able to directly execute privileged instructions, which could lead to unauthorized access to system resources and compromise the integrity of the operating system.

### [Multilevel queue scheduling] Explain how the multilevel feedback queue scheduling mechanism ensures that higher-priority processes are executed before lower-priority ones, and how this affects process preemption.
*confidence 0.91 · medium · slides [147, 148, 149, 150]*

**Reference:** In a multilevel feedback queue, higher-priority queues are executed before lower-priority ones, ensuring that processes in higher queues get CPU time first. This is because each queue has absolute priority over lower-priority queues. A process in a higher queue can preempt a process in a lower queue, which means the lower-priority process is interrupted and moved to a lower queue. This mechanism allows for dynamic prioritization based on process behavior and resource needs.

**Key points** (slide quote → follow-up → expected answer):
- **Higher-priority queues are executed before lower-priority ones.**  
  quote: "Each queue has absolute priority over lower-priority queues."  
  follow-up: _What happens if a process in a lower-priority queue is running when a higher-priority process arrives?_  
  expected: The higher-priority process will preempt the lower-priority one, interrupting it and moving it to a lower queue.
- **A process in a higher queue can preempt a process in a lower queue.**  
  quote: "A process that arrives for queue 1 will preempt a process in queue 2."  
  follow-up: _Why would a process in a higher queue preempt a process in a lower queue?_  
  expected: Because the higher-priority queue has absolute priority, allowing it to interrupt and take over the CPU from lower-priority processes.
- **Processes are moved between queues based on their behavior.**  
  quote: "A new job enters queue Q0 which is served FCFS. When it gains CPU, job receives 8 milliseconds. If it does not finish in 8 milliseconds, job is moved to queue Q1."  
  follow-up: _What determines when a process is moved from one queue to another?_  
  expected: The process's behavior, such as not completing its time quantum, determines when it is moved to a lower or higher queue.

### [Deadlock avoidance] How does the concept of a safe state influence the decision-making process when a process requests a resource in a deadlock avoidance system?
*confidence 0.91 · medium · slides [410, 412]*

**Reference:** The concept of a safe state ensures that the system remains in a state where a deadlock cannot occur. When a process requests a resource, the system must determine if granting the request will leave the system in a safe state. If it does, the request is granted; otherwise, the process must wait. This decision is based on the idea that the system must always remain in a safe state to avoid deadlocks.

**Key points** (slide quote → follow-up → expected answer):
- **The system must ensure that granting a resource request will not leave it in an unsafe state.**  
  quote: "The request is granted only if the allocation leaves the system in a safe state."  
  follow-up: _What happens if granting a resource request would put the system in an unsafe state?_  
  expected: The process must wait, as the system cannot allow itself to enter an unsafe state.
- **A safe state guarantees that the system can avoid deadlocks.**  
  quote: "If a system is in a safe state no deadlocks"  
  follow-up: _Why is it important for the system to always remain in a safe state?_  
  expected: Because a safe state ensures that there is always a sequence of resource allocations that can satisfy all processes, preventing deadlocks.
- **The behavior of processes can lead to unsafe states, which may result in deadlocks.**  
  quote: "The behavior of processes controls unsafe states."  
  follow-up: _How does the behavior of processes affect the system's ability to avoid deadlocks?_  
  expected: If processes request resources in a way that leads to an unsafe state, the system may not be able to avoid a deadlock, even if it was initially in a safe state.

### [System calls] How do system calls enable communication between user programs and the operating system, and what role do they play in file manipulation?
*confidence 0.91 · medium · slides [85, 86]*

**Reference:** System calls provide an interface to the services made available by an operating system. This allows user programs to request operations such as reading from or writing to files. File manipulation is one of the major categories of system calls, which includes operations like opening, reading, writing, and closing files.

**Key points** (slide quote → follow-up → expected answer):
- **System calls act as an interface between user programs and the operating system.**  
  quote: "System calls provide an interface to the services made available by an operating system."  
  follow-up: _What would happen if there were no system calls available for file operations?_  
  expected: User programs would not be able to perform file operations directly, as they would lack the necessary privileges and mechanisms to interact with the file system.
- **File manipulation is one of the major categories of system calls.**  
  quote: "System calls can be grouped roughly into six major categories: Process control, File manipulation, Device manipulation, Information maintenance, Communications, and Protection."  
  follow-up: _Can you name one system call that would be used for file manipulation?_  
  expected: An example is the 'read' system call, which is used to read data from a file.
- **System calls allow user programs to request operations on files without needing to manage the underlying hardware or file system details.**  
  quote: "These calls are generally available as routines written in a higher level programming language or assembly language."  
  follow-up: _Why is it important for system calls to abstract the details of file operations from user programs?_  
  expected: It allows user programs to perform file operations in a consistent and secure manner, without needing to understand the low-level details of the file system or hardware.

### [Mutex locks] Why are spinlocks considered problematic in real-time systems, and how does this relate to the use of busy waiting?
*confidence 0.91 · medium · slides [316, 317]*

**Reference:** Spinlocks are considered problematic in real-time systems because they involve busy waiting, which wastes CPU cycles. Busy waiting means that a process repeatedly checks the lock status instead of yielding the CPU, which can prevent other processes from executing. This is inefficient in real-time systems where predictable and timely execution is critical.

**Key points** (slide quote → follow-up → expected answer):
- **Spinlocks involve busy waiting, which wastes CPU cycles.**  
  quote: "Busy waiting wastes CPU cycles."  
  follow-up: _What happens to the CPU when a process is waiting on a spinlock?_  
  expected: The CPU is repeatedly checked by the waiting process, which consumes cycles without making progress.
- **Spinlocks are problematic in real-time systems due to their inefficiency.**  
  quote: "It is problem in real time systems."  
  follow-up: _Why would a real-time system be concerned about the inefficiency of spinlocks?_  
  expected: Real-time systems require predictable and timely execution, and spinlocks can introduce unpredictable delays due to busy waiting.
- **Busy waiting is a characteristic of spinlocks and not of other locking mechanisms.**  
  quote: "But this solution requires busy waiting."  
  follow-up: _What is the difference between a spinlock and a lock that does not use busy waiting?_  
  expected: A spinlock uses busy waiting, whereas other locks may block the process and allow the CPU to be used by other tasks.

### [Pthreads] Explain how the Pthreads API supports both user-level and kernel-level implementations of thread libraries, and why this distinction matters for thread scheduling.
*confidence 0.90 · medium · slides [258, 261, 265, 266, 271, 272]*

**Reference:** The Pthreads API is a POSIX standard that specifies the behavior of thread libraries, but it does not dictate whether the implementation is user-level or kernel-level. This distinction matters because user-level thread libraries handle thread management entirely in user space, while kernel-level libraries involve the operating system. The scheduling scope in Pthreads, such as PTHREAD_SCOPE_PROCESS or PTHREAD_SCOPE_SYSTEM, reflects this distinction by determining whether threads are scheduled within a process or across the entire system.

**Key points** (slide quote → follow-up → expected answer):
- **The Pthreads API is a POSIX standard (IEEE 1003.1c) API for thread creation and synchronization.**  
  quote: "A POSIX standard (IEEE 1003.1c) API for thread creation and synchronization"  
  follow-up: _What does it mean for an API to be a specification rather than an implementation?_  
  expected: It means the API defines the behavior that the library must follow, but the actual implementation details are up to the developer or system.
- **Pthreads may be provided either as user-level or kernel-level.**  
  quote: "May be provided either as user-level or kernel-level"  
  follow-up: _What are the implications of a thread library being implemented in user space versus kernel space?_  
  expected: A user-level library keeps all code and data structures in user space, while a kernel-level library requires the operating system to manage thread execution and scheduling.
- **The scheduling scope in Pthreads reflects the distinction between user-level and kernel-level implementations.**  
  quote: "set the scheduling algorithm to PCS or SCS"  
  follow-up: _How does the scheduling scope affect thread behavior in a multi-threaded application?_  
  expected: The scheduling scope determines whether threads are scheduled within a single process (PTHREAD_SCOPE_PROCESS) or across the entire system (PTHREAD_SCOPE_SYSTEM), which impacts resource allocation and performance.

### [FCFS scheduling] Explain how the order of process arrival affects the average waiting time in FCFS scheduling, using the example provided.
*confidence 0.90 · medium · slides [106]*

**Reference:** In FCFS scheduling, the order of process arrival directly determines the waiting time for each process. The example shows that P1 starts immediately, so its waiting time is 0, while P2 and P3 must wait for P1 to complete. This leads to higher waiting times for later processes, which increases the average waiting time. The average waiting time in the example is 17, which reflects the cumulative waiting time of all processes due to the order of arrival.

**Key points** (slide quote → follow-up → expected answer):
- **The order of process arrival directly determines the waiting time for each process.**  
  quote: "Suppose that the processes arrive in the order: P1 , P2 , P3 The Gantt Chart for the schedule is:"  
  follow-up: _What would happen if the order of arrival changed to P2, P1, P3?_  
  expected: The waiting time for P1 would increase because it would have to wait for P2 to complete first.
- **Waiting time for P2 is 24, which is the time it spends waiting before execution.**  
  quote: "Waiting time for P1 = 0; P2 = 24; P3 = 27"  
  follow-up: _Why does P2 have a waiting time of 24?_  
  expected: Because P2 has to wait for P1 to complete its 24 units of burst time before it can start execution.
- **The average waiting time is calculated by summing individual waiting times and dividing by the number of processes.**  
  quote: "Average waiting time: (0 + 24 + 27)/3 = 17"  
  follow-up: _How would the average waiting time change if another process with a burst time of 10 was added?_  
  expected: The average waiting time would increase because the new process would have to wait for all previous processes to complete, adding to the total waiting time.

### [Deadlock detection and recovery] What happens to the wait-for graph when a resource is allocated to a process, and how does this affect the possibility of detecting a deadlock?
*confidence 0.90 · medium · slides [395]*

**Reference:** When a resource is allocated to a process, the corresponding edges in the resource-allocation graph are removed, which may also remove edges in the wait-for graph. This can break potential cycles in the wait-for graph, thereby reducing the possibility of a deadlock. However, if a cycle still exists after the allocation, a deadlock remains undetected unless the graph is re-evaluated.

**Key points** (slide quote → follow-up → expected answer):
- **The wait-for graph is derived from the resource-allocation graph by removing resource nodes and collapsing edges.**  
  quote: "We obtain wait-for graph from the resource-allocation graph by removing the resource nodes and collapsing the appropriate edges."  
  follow-up: _What would happen to the wait-for graph if a resource was allocated to a process?_  
  expected: The corresponding edges in the resource-allocation graph would be removed, which could also remove edges in the wait-for graph.
- **A deadlock exists in the system if and only if the wait-for graph contains a cycle.**  
  quote: "A deadlock exists in the system if and only if the wait-for graph contains a cycle."  
  follow-up: _How does the presence of a cycle in the wait-for graph relate to the detection of a deadlock?_  
  expected: A cycle in the wait-for graph indicates that a deadlock exists in the system.
- **The algorithm to detect a cycle in a graph requires an order of n² operations.**  
  quote: "An algorithm to detect a cycle in a graph requires an order of n² operations, where n is the number of vertices in the graph."  
  follow-up: _What is the computational complexity of detecting a deadlock using the wait-for graph?_  
  expected: Detecting a cycle in the wait-for graph requires an order of n² operations, where n is the number of vertices.

### [Thrashing] How does the working-set model help in mitigating the effects of thrashing, and what are the limitations of its approximation using reference bits and interval timers?
*confidence 0.90 · medium · slides [620, 621, 622, 623]*

**Reference:** The working-set model helps mitigate thrashing by approximating a process's locality, ensuring that the pages it needs are kept in memory. It uses a window of recent page references to define the working set. However, the approximation using reference bits and interval timers has limitations, such as not accurately capturing when a reference occurred within an interval. This makes it difficult to precisely determine if a page is in the working set.

**Key points** (slide quote → follow-up → expected answer):
- **The working-set model approximates a process's locality to avoid thrashing.**  
  quote: "The working-set model is based on the assumption of locality."  
  follow-up: _What happens if a process's page references don't follow the locality assumption?_  
  expected: The working-set model would not accurately represent the process's memory needs, potentially leading to thrashing.
- **The approximation uses reference bits and interval timers to track the working set.**  
  quote: "Approximate the W-S model with interval timer + a reference bit."  
  follow-up: _Why might using reference bits and interval timers not be reliable for tracking the working set?_  
  expected: Because the reference bits do not track when a reference occurred within an interval, making it hard to determine if a page is actively used.
- **The approximation has limitations due to the inability to track precise reference timing.**  
  quote: "We cannot tell where, within an interval of 5000, a reference occurred."  
  follow-up: _How could the approximation be improved without increasing the overhead significantly?_  
  expected: Using more bits and more frequent interrupts could improve accuracy, but this would increase overhead.

### [Peterson's solution] Explain how Peterson’s solution ensures mutual exclusion between two processes.
*confidence 0.82 · easy · slides [295, 296]*

**Reference:** Peterson’s solution ensures mutual exclusion by using a combination of a flag array and a turn variable. The flag array indicates whether a process is ready to enter the critical section, and the turn variable determines which process can enter next. Mutual exclusion is achieved because a process will only enter the critical section if the other process is not ready or it is not its turn.

**Key points** (slide quote → follow-up → expected answer):
- **Peterson’s solution uses a flag array to indicate if a process is ready to enter the critical section.**  
  quote: "flag[i] = true implies that process Pi is ready!"  
  follow-up: _What happens if a process sets its flag to true but then immediately enters the critical section?_  
  expected: It would violate mutual exclusion because another process might still be in the critical section.
- **The turn variable is used to determine which process can enter the critical section next.**  
  quote: "The variable turn indicates whose turn it is to enter the critical section"  
  follow-up: _Why is the turn variable necessary for mutual exclusion?_  
  expected: The turn variable ensures that only one process can enter the critical section at a time, even if both flags are set to true.

### [Deadlock detection and recovery] Explain how a wait-for graph is used to detect deadlocks in a system.
*confidence 0.82 · easy · slides [395]*

**Reference:** A wait-for graph is used to detect deadlocks by representing the waiting relationships between processes. The graph is derived from the resource-allocation graph by removing resource nodes and collapsing edges. A deadlock exists if and only if the wait-for graph contains a cycle. This cycle indicates that a set of processes are waiting for each other to release resources, forming a circular dependency. The presence of a cycle is the only condition under which a deadlock can occur in this model.

**Key points** (slide quote → follow-up → expected answer):
- **The wait-for graph is derived from the resource-allocation graph by removing resource nodes and collapsing edges.**  
  quote: "We obtain wait-for graph from the resource-allocation graph by removing the resource nodes and collapsing the appropriate edges."  
  follow-up: _Why would you remove resource nodes from the resource-allocation graph?_  
  expected: Resource nodes are removed to focus on the waiting relationships between processes, which is essential for detecting deadlocks based on circular dependencies.
- **An edge from Pi to Pj in the wait-for graph indicates that Pi is waiting for Pj to release a resource.**  
  quote: "An edge from Pi to Pj implies that process Pi is waiting for process Pj to release a resource that Pi needs."  
  follow-up: _How does this edge represent a deadlock condition?_  
  expected: This edge represents a direct dependency where Pi is waiting for Pj, and if such edges form a cycle, it indicates that each process in the cycle is waiting for another, creating a deadlock.

### [FIFO page replacement] Explain how the FIFO page replacement algorithm works in the context of page faults and memory frames.
*confidence 0.82 · easy · slides [599, 600]*

**Reference:** The FIFO page replacement algorithm uses a queue to track the order in which pages were loaded into memory. When a page fault occurs and there are no available frames, the page that has been in memory the longest is replaced. This is based on the idea that pages that were loaded earlier are less likely to be needed soon. However, this approach can sometimes lead to Belady’s Anomaly, where adding more frames can increase the number of page faults.

**Key points** (slide quote → follow-up → expected answer):
- **FIFO uses a queue to track the order of pages in memory.**  
  quote: "How to track ages of pages? - Just use a FIFO queue"  
  follow-up: _What is the purpose of using a queue in FIFO page replacement?_  
  expected: The queue is used to track the order in which pages were loaded, so that the oldest page can be replaced when a new page needs to be loaded.
- **FIFO can lead to Belady’s Anomaly.**  
  quote: "Adding more frames can cause more page faults! 4 Belady’s Anomaly"  
  follow-up: _What is an example of a situation where FIFO might cause more page faults with more memory?_  
  expected: Belady’s Anomaly occurs when increasing the number of frames leads to more page faults, which can happen in FIFO due to the order in which pages are replaced.

### [Translation lookaside buffer] Explain what a Translation Look-aside Buffer (TLB) is and why it is used.
*confidence 0.82 · easy · slides [514, 516, 517]*

**Reference:** A Translation Look-aside Buffer (TLB) is a hardware cache used to speed up address translation for virtual memory. It stores recently used page table entries so that the CPU does not have to access the page table in main memory for every address translation. This reduces the effective access time by avoiding the need for multiple memory accesses when a page table entry is not found in the TLB.

**Key points** (slide quote → follow-up → expected answer):
- **A TLB is a hardware cache used to speed up address translation for virtual memory.**  
  quote: "TLB is about ‘speeding up address translation for Virtual/logical memory’ so that page-table needn’t to be accessed for every address."  
  follow-up: _Why is it important for the TLB to speed up address translation?_  
  expected: Because without a TLB, the CPU would have to access the page table in main memory for every address translation, which would significantly increase memory access latency.
- **A TLB stores recently used page table entries.**  
  quote: "On a TLB miss, value is loaded into the TLB for faster access next time."  
  follow-up: _What happens when a page table entry is not found in the TLB?_  
  expected: A TLB miss results in the CPU accessing the page table in main memory to retrieve the entry, which increases the effective access time.

### [Context switching] How does the size of a process affect the time required for a context switch, and what mechanisms can mitigate this impact?
*confidence 0.82 · hard · slides [140, 459, 460, 466] · ⚠ NEEDS REVIEW*

**Reference:** The size of a process directly affects the time required for a context switch, especially when swapping is involved. Larger processes take longer to swap in and out, as demonstrated by the example of a 3GB process requiring 60 seconds for swapping. However, the system can mitigate this impact by reducing the amount of memory swapped through mechanisms like `request_memory()` and `release_memory()`, which allow the OS to track and manage memory usage more precisely.

**Key points** (slide quote → follow-up → expected answer):
- **Larger processes increase context switch time due to swapping overhead.**  
  quote: "If next processes to be put on CPU is not in memory, need to swap out a process and swap in target process"  
  follow-up: _What happens if a process is very large and needs to be swapped in and out frequently?_  
  expected: The context switch time becomes significantly longer, which can severely degrade system performance.
- **Swapping time is proportional to the size of the process being moved.**  
  quote: "Swap out time=100MB/50MB per sec= 2 sec"  
  follow-up: _How does the size of a process affect the time required for swapping?_  
  expected: The larger the process, the longer it takes to swap in or out, as the transfer rate is fixed.
- **Memory management mechanisms can reduce the amount of memory swapped.**  
  quote: "Can be reduced if size of memory to be swapped is reduced – by knowing how much memory really being used"  
  follow-up: _What is one way the OS can reduce the memory swapped during a context switch?_  
  expected: The OS can use system calls like `request_memory()` and `release_memory()` to track and manage memory usage more precisely.

### [Deadlock conditions] Consider a scenario where a system allows preemption of resources. How does this affect the possibility of deadlock, and what condition is no longer a necessary requirement for deadlock to occur?
*confidence 0.82 · hard · slides [372, 384, 385] · ⚠ NEEDS REVIEW*

**Reference:** Preemption allows a resource to be forcibly taken from a process, which breaks the 'no preemption' condition. This means that even if the other three conditions—mutual exclusion, hold and wait, and circular wait—are met, preemption can prevent deadlock by allowing resources to be reallocated. Therefore, preemption can eliminate the necessity of the 'no preemption' condition for deadlock to occur.

**Key points** (slide quote → follow-up → expected answer):
- **Preemption can eliminate the necessity of the 'no preemption' condition for deadlock to occur.**  
  quote: "No preemption: a resource can be released only voluntarily by the process holding it, after that process has completed its task"  
  follow-up: _If a system allows preemption, what condition is no longer required for deadlock to occur?_  
  expected: The 'no preemption' condition is no longer required for deadlock to occur.
- **Preemption can break the cycle of resource allocation that leads to deadlock.**  
  quote: "If a process that is holding some resources requests another resource that cannot be immediately allocated to it, then all resources currently being held are released"  
  follow-up: _How does preemption affect the circular wait condition?_  
  expected: Preemption can break the circular wait by allowing resources to be reallocated, thus disrupting the cycle.
- **Preemption introduces the possibility of resource starvation.**  
  quote: "Preempted resources are added to the list of resources for which the process is waiting. Process will be restarted only when it can regain its old resources, as well as the new ones that it is requesting"  
  follow-up: _What is a potential downside of allowing preemption in a system?_  
  expected: Preemption can lead to resource starvation, where a process is repeatedly preempted and never gets to complete its execution.

### [Multilevel page tables] What is the primary challenge in implementing shared memory with inverted page tables, and how does the structure of the inverted page table contribute to this challenge?
*confidence 0.82 · hard · slides [524, 525, 533, 534, 535, 537] · ⚠ NEEDS REVIEW*

**Reference:** The primary challenge in implementing shared memory with inverted page tables is that a single physical page cannot have multiple virtual addresses mapped to it. This is because the inverted page table contains one entry for each physical page, and each entry maps to a single virtual address. As a result, shared memory—where multiple virtual addresses map to the same physical address—cannot be directly supported without additional mechanisms.

**Key points** (slide quote → follow-up → expected answer):
- **A single physical page cannot have multiple virtual addresses mapped to it.**  
  quote: "One physical page cannot have two (or more) shared virtual addresses."  
  follow-up: _Why can't a single physical page have multiple virtual addresses mapped to it?_  
  expected: Because the inverted page table contains one entry for each physical page, and each entry maps to a single virtual address.
- **The inverted page table maps physical pages to virtual addresses, not the other way around.**  
  quote: "Inverted page table is sorted by physical address, but lookups occur on virtual addresses."  
  follow-up: _How does the inverted page table's structure affect the ability to support shared memory?_  
  expected: It makes it difficult to support shared memory because the table is designed to map physical pages to virtual addresses, not the other way around.
- **Shared memory requires multiple virtual addresses to map to the same physical address.**  
  quote: "Shared memory is usually implemented as multiple virtual addresses are mapped to one physical address."  
  follow-up: _What would happen if you tried to map multiple virtual addresses to the same physical address in an inverted page table?_  
  expected: It would violate the structure of the inverted page table, which only allows one virtual address per physical page.

### [File system concepts] What is the role of the file control block (FCB) in a file system, and how does it contribute to the system's ability to manage files efficiently?
*confidence 0.82 · hard · slides [639, 640, 689] · ⚠ NEEDS REVIEW*

**Reference:** The file control block (FCB) is a storage structure that contains information about a file, including ownership, permissions, and the location of the file contents. This allows the file system to track and manage files by providing essential metadata needed for access control and data retrieval. The FCB is critical for maintaining the integrity and security of files, as it holds the necessary details for both user permissions and physical storage mapping.

**Key points** (slide quote → follow-up → expected answer):
- **The FCB contains information about a file, including ownership and permissions.**  
  quote: "File control block (FCB) – storage structure consisting of information about a file including ownership, permissions, and location of the file contents"  
  follow-up: _What would happen if the file system did not track ownership and permissions for each file?_  
  expected: The system would not be able to enforce access control, leading to potential security vulnerabilities and unauthorized modifications.
- **The FCB holds the location of the file contents, which is essential for data retrieval.**  
  quote: "File control block (FCB) – storage structure consisting of information about a file including ownership, permissions, and location of the file contents"  
  follow-up: _How does the FCB's location information help in managing disk space?_  
  expected: The FCB's location information allows the file system to quickly locate and retrieve file data, improving access efficiency and enabling proper disk space management.
- **The FCB is a key component in maintaining file system integrity and security.**  
  quote: "File control block (FCB) – storage structure consisting of information about a file including ownership, permissions, and location of the file contents"  
  follow-up: _Why is the FCB considered a critical part of the file system's architecture?_  
  expected: The FCB is critical because it centralizes all essential metadata about a file, enabling the system to manage access, security, and storage efficiently.

### [Free-space management] What are the limitations of using a bit vector for free-space management, and how do these limitations affect the design of disk allocation strategies in operating systems?
*confidence 0.82 · hard · slides [723, 724, 725, 726, 727] · ⚠ NEEDS REVIEW*

**Reference:** The bit vector approach is efficient for finding free blocks but becomes impractical for large disks due to memory constraints. Keeping the entire bit vector in main memory is only feasible for smaller disks. For larger disks, this approach requires significant memory, which can limit scalability. These limitations influence the design of disk allocation strategies, such as using alternative free-space management techniques like linked lists or grouping blocks into clusters to reduce the overhead of tracking individual blocks.

**Key points** (slide quote → follow-up → expected answer):
- **The bit vector is inefficient unless the entire vector is kept in main memory.**  
  quote: "Bit vectors are inefficient unless the entire vector is kept in main memory"  
  follow-up: _What happens if the bit vector cannot fit in main memory?_  
  expected: The system would need to use a disk-based approach, which increases the time required to access the free-space information.
- **Keeping the bit vector in main memory is only feasible for smaller disks.**  
  quote: "Keeping the bit, vector in main memory is possible for smaller disks but not necessarily for larger ones"  
  follow-up: _Why would keeping the bit vector in main memory be a problem for larger disks?_  
  expected: Larger disks require larger bit vectors, which consume more memory and may exceed available RAM, leading to performance degradation.
- **The bit vector approach requires significant memory for large disks.**  
  quote: "A 1-TB disk with 4-KB blocks requires 32 MB to store its bit map."  
  follow-up: _How does the size of the bit vector affect the choice of disk allocation strategies?_  
  expected: The memory requirement for the bit vector may lead to the use of alternative methods like linked lists or cluster-based allocation to reduce memory overhead.

### [Deadlock prevention] What happens to a process if it is preempted for a resource, and how does this relate to deadlock prevention?
*confidence 0.82 · hard · slides [372, 384, 385] · ⚠ NEEDS REVIEW*

**Reference:** If a process is preempted for a resource, it must release all resources it currently holds. This is part of the 'no preemption' condition, which is one of the four necessary conditions for deadlock. By enforcing no preemption, the system ensures that a process cannot hold resources while waiting for others, thereby preventing deadlock. The preempted resources are added to the process's waiting list, and the process will be restarted only when it can regain all its previously held resources and the new ones it is requesting.

**Key points** (slide quote → follow-up → expected answer):
- **A process must release all resources it currently holds if it is preempted.**  
  quote: "If a process that is holding some resources requests another resource that cannot be immediately allocated to it, then all resources currently being held are released."  
  follow-up: _What is the consequence of a process being preempted for a resource?_  
  expected: The process must release all resources it currently holds, and it will be restarted only when it can regain all its previously held resources and the new ones it is requesting.
- **Preemption is a mechanism used to prevent deadlock by breaking the 'hold and wait' condition.**  
  quote: "No preemption – If a process that is holding some resources requests another resource that cannot be immediately allocated to it, then all resources currently being held are released."  
  follow-up: _How does preemption help prevent deadlock?_  
  expected: Preemption breaks the 'hold and wait' condition by forcing a process to release resources it is holding when it cannot immediately acquire additional ones, thereby preventing a deadlock scenario.
- **The preempted resources are added to the process's waiting list.**  
  quote: "Preempted resources are added to the list of resources for which the process is waiting."  
  follow-up: _What happens to the resources that are preempted?_  
  expected: The preempted resources are added to the list of resources for which the process is waiting, and the process will be restarted only when it can regain all its previously held resources and the new ones it is requesting.

### [Page faults] What is the role of page-fault frequency in managing memory allocation, and how does it affect the behavior of a process when the system is under memory pressure?
*confidence 0.82 · hard · slides [571, 572, 625] · ⚠ NEEDS REVIEW*

**Reference:** Page-fault frequency is used to control the rate at which a process generates page faults. If the actual rate is too low, the process loses a frame, reducing its memory allocation. If the rate is too high, the process gains a frame, increasing its memory allocation. This mechanism helps avoid thrashing by dynamically adjusting the number of frames allocated to a process based on its page-fault behavior.

**Key points** (slide quote → follow-up → expected answer):
- **Page-fault frequency is used to control the rate at which a process generates page faults.**  
  quote: "Establish 'acceptable' page-fault frequency (PFF) rate and use local replacement policy"  
  follow-up: _What happens if a process consistently generates page faults below the acceptable rate?_  
  expected: The process loses a frame, reducing its memory allocation.
- **A process can lose a frame if its page-fault rate is too low.**  
  quote: "If actual rate too low, process loses frame"  
  follow-up: _Why would a process have a page-fault rate that is too low?_  
  expected: Because it is not using enough memory, and thus not generating enough page faults to justify additional frames.
- **A process can gain a frame if its page-fault rate is too high.**  
  quote: "If actual rate too high, process gains frame."  
  follow-up: _What does it mean for a process to gain a frame?_  
  expected: It means the system increases the number of frames allocated to the process to accommodate its higher page-fault rate.

### [User mode vs kernel mode] What happens if a user program attempts to execute a privileged instruction, and why is this behavior intentional?
*confidence 0.82 · hard · slides [48] · ⚠ NEEDS REVIEW*

**Reference:** If a user program attempts to execute a privileged instruction, the CPU will trigger a protection fault, preventing the instruction from running. This behavior is intentional because privileged instructions are designed to be only executable in kernel mode, ensuring that user programs cannot directly manipulate critical system resources. The mode bit in the hardware enforces this separation, allowing the operating system to maintain control over system-level operations.

**Key points** (slide quote → follow-up → expected answer):
- **Privileged instructions are only executable in kernel mode.**  
  quote: "Some instructions designated as privileged, only executable in kernel mode."  
  follow-up: _What would happen if a user program tried to run a privileged instruction?_  
  expected: The CPU would trigger a protection fault, preventing the instruction from executing.
- **The CPU uses a mode bit to enforce mode separation.**  
  quote: "Mode bit provided by hardware. Provides ability to distinguish when system is running user code or kernel code."  
  follow-up: _How does the CPU know whether the code is running in user mode or kernel mode?_  
  expected: The CPU checks the mode bit, which is set by the hardware to indicate the current mode of execution.
- **Protection faults prevent unauthorized access to privileged operations.**  
  quote: "Dual-mode operation allows OS to protect itself and other system components."  
  follow-up: _Why is it important for the OS to prevent user programs from executing privileged instructions?_  
  expected: To protect the integrity and security of the operating system and system resources from potentially harmful user code.

### [Hardware synchronization] Explain how the test_and_set instruction ensures mutual exclusion in a multi-process environment, and what happens if two processes attempt to acquire the lock simultaneously.
*confidence 0.82 · hard · slides [307, 308] · ⚠ NEEDS REVIEW*

**Reference:** The test_and_set instruction ensures mutual exclusion by atomically reading and writing to a shared memory location. When a process executes test_and_set, it reads the current value and sets it to TRUE, preventing other processes from acquiring the lock until this operation completes. If two processes attempt to acquire the lock simultaneously, the second process will detect that the lock is already held and will be blocked until the first process releases it.

**Key points** (slide quote → follow-up → expected answer):
- **The test_and_set instruction ensures mutual exclusion by atomically reading and writing to a shared memory location.**  
  quote: "It is an instruction that returns the old value of a memory location and sets the memory location value to 1 as a single atomic operation."  
  follow-up: _What would happen if the test_and_set operation was not atomic?_  
  expected: If the operation was not atomic, multiple processes could read the same value and both set it to TRUE, leading to a race condition and violating mutual exclusion.
- **The test_and_set instruction prevents other processes from acquiring the lock until the operation completes.**  
  quote: "If one process is currently executing a test-and-set, no other process is allowed to begin another test-and-set until the first process test-and-set is finished."  
  follow-up: _Why is it important that no other process can begin another test-and-set until the first is finished?_  
  expected: It is important to prevent race conditions and ensure that only one process can hold the lock at any given time, maintaining mutual exclusion.
- **The test_and_set instruction returns the original value of the memory location before it is set to TRUE.**  
  quote: "It returns the original value of passed parameter"  
  follow-up: _How is the return value of test_and_set used in a locking mechanism?_  
  expected: The return value indicates whether the lock was acquired or not, allowing the process to determine if it successfully obtained the lock.

### [Producer-consumer problem] Explain what the producer-consumer problem is, and why it is important in operating systems.
*confidence 0.81 · easy · slides [195, 335, 336, 337]*

**Reference:** The producer-consumer problem is a paradigm for cooperating processes where a producer process generates data and a consumer process uses that data. It is important in operating systems because it models real-world scenarios where data production and consumption happen at different rates, requiring synchronization to prevent data corruption and resource starvation.

**Key points** (slide quote → follow-up → expected answer):
- **The producer-consumer problem is a paradigm for cooperating processes.**  
  quote: "Paradigm for cooperating processes, producer process produces information that is consumed by a consumer process"  
  follow-up: _What is the main purpose of having a producer and a consumer in this model?_  
  expected: The main purpose is to model situations where data is produced at one rate and consumed at another, requiring coordination to avoid data loss or buffer overflow.
- **The problem highlights the need for synchronization mechanisms such as semaphores.**  
  quote: "Semaphore mutex initialized to the value 1; Semaphore full initialized to the value 0; Semaphore empty initialized to the value n"  
  follow-up: _What role does the 'mutex' semaphore play in this problem?_  
  expected: The 'mutex' semaphore ensures mutual exclusion when accessing the shared buffer, preventing race conditions.

### [Semaphores] Explain how the implementation of semaphores without busy waiting can lead to priority inversion, and why the use of the priority-inheritance protocol is necessary.
*confidence 0.81 · hard · slides [322, 324, 325, 326, 327, 328] · ⚠ NEEDS REVIEW*

**Reference:** The implementation of semaphores without busy waiting uses a waiting queue to block processes when the semaphore value is zero. Priority inversion occurs when a lower-priority process holds a lock needed by a higher-priority process. The priority-inheritance protocol is necessary to resolve this by temporarily raising the priority of the lower-priority process until it releases the lock, ensuring the higher-priority process can proceed.

**Key points** (slide quote → follow-up → expected answer):
- **The implementation of semaphores without busy waiting uses a waiting queue to block processes when the semaphore value is zero.**  
  quote: "With each semaphore there is an associated waiting queue."  
  follow-up: _What happens to a process when it cannot acquire a semaphore in a non-busy waiting implementation?_  
  expected: It is added to the semaphore's waiting queue and blocked until it can acquire the semaphore.
- **Priority inversion occurs when a lower-priority process holds a lock needed by a higher-priority process.**  
  quote: "Priority Inversion – Scheduling problem when lower-priority process holds a lock needed by higher-priority process"  
  follow-up: _What is the fundamental problem in priority inversion?_  
  expected: A higher-priority process is blocked because a lower-priority process holds a critical resource it needs.
- **The priority-inheritance protocol is necessary to resolve priority inversion.**  
  quote: "Solved via priority-inheritance protocol"  
  follow-up: _Why would a priority-inheritance protocol help in the case of semaphores?_  
  expected: It temporarily raises the priority of the lower-priority process to ensure it can release the lock and allow the higher-priority process to proceed.

### [Scheduling criteria] Explain how minimizing waiting time and maximizing throughput are related in the context of scheduling criteria.
*confidence 0.78 · medium · slides [129, 130]*

**Reference:** Minimizing waiting time ensures that processes spend less time in the ready queue, which allows more processes to complete in a given time period, thereby maximizing throughput. Both criteria aim to improve system efficiency by reducing idle time and ensuring fair and timely execution of processes.

**Key points** (slide quote → follow-up → expected answer):
- **Minimizing waiting time reduces the time processes spend in the ready queue.**  
  quote: "Waiting time – amount of time a process has been waiting in the ready queue"  
  follow-up: _What happens if a process waits too long in the ready queue?_  
  expected: It increases waiting time, which can reduce throughput and lead to poor system performance.
- **Maximizing throughput means more processes complete in a given time period.**  
  quote: "Throughput – # of processes that complete their execution per time unit"  
  follow-up: _How does reducing waiting time help achieve higher throughput?_  
  expected: By reducing the time processes spend waiting, more processes can be executed in the same time period, increasing throughput.

### [Semaphores] Explain how the incorrect use of semaphore operations can lead to deadlock and starvation, and why the implementation of semaphores with busy waiting is problematic.
*confidence 0.78 · medium · slides [322, 324, 325, 326, 327, 328]*

**Reference:** Incorrect use of semaphore operations, such as calling wait() multiple times without a corresponding signal(), can lead to deadlock, where processes are waiting indefinitely for an event that can only be caused by one of them. Starvation occurs when a process is indefinitely blocked from the semaphore queue. The implementation of semaphores with busy waiting is problematic because it leads to wasted CPU time as processes spin in a loop while waiting, which is inefficient when the critical section is rarely used.

**Key points** (slide quote → follow-up → expected answer):
- **Starvation is a possible outcome of incorrect semaphore usage.**  
  quote: "Starvation – indefinite blocking – A process may never be removed from the semaphore queue in which it is suspended"  
  follow-up: _Why might a process never be removed from the semaphore queue?_  
  expected: Because the semaphore implementation may not prioritize processes, leading to indefinite blocking.
- **Busy waiting in semaphore implementation is inefficient.**  
  quote: "Could now have busy waiting in critical section implementation 4 But implementation code is short 4 Little busy waiting if critical section rarely occupied"  
  follow-up: _Why is busy waiting considered inefficient in some cases?_  
  expected: Because processes spend time spinning in a loop instead of doing useful work when the critical section is not frequently accessed.

### [Dining philosophers problem] Explain how the asymmetric solution to the Dining Philosophers problem prevents deadlock.
*confidence 0.78 · medium · slides [343, 344, 345]*

**Reference:** The asymmetric solution prevents deadlock by ensuring that philosophers pick up chopsticks in a different order depending on their number. This breaks the symmetry that can lead to all philosophers waiting indefinitely for chopsticks. An odd-numbered philosopher picks up the left chopstick first, while an even-numbered philosopher picks up the right chopstick first. This approach reduces the chance of a circular wait condition, which is a key factor in deadlock.

**Key points** (slide quote → follow-up → expected answer):
- **Odd-numbered philosophers pick up the left chopstick first.**  
  quote: "Use an asymmetric solution -- an odd-numbered philosopher picks up first the left chopstick and then the right chopstick."  
  follow-up: _Why is it important for odd-numbered philosophers to pick up the left chopstick first?_  
  expected: It ensures that the order in which chopsticks are picked up is different for each philosopher, reducing the possibility of a deadlock.
- **Even-numbered philosophers pick up the right chopstick first.**  
  quote: "Use an asymmetric solution -- an odd-numbered philosopher picks up first the left chopstick and then the right chopstick. Even-numbered philosopher picks up first the right chopstick and then the left chopstick."  
  follow-up: _How does this affect the overall system behavior?_  
  expected: It introduces an asymmetry in the resource allocation, which helps avoid the circular wait condition that leads to deadlock.

### [Segmentation] Explain how segmentation handles logical addresses and what happens when an offset is invalid.
*confidence 0.78 · medium · slides [482, 485, 486, 546]*

**Reference:** Segmentation handles logical addresses by splitting them into a segment number and an offset. The segment number is used to index the segment table, which contains the base and limit of each segment. When an offset is invalid—meaning it exceeds the segment limit—the system traps to the operating system. This ensures that the process cannot access memory outside its allocated segments.

**Key points** (slide quote → follow-up → expected answer):
- **Segmentation splits logical addresses into a segment number and an offset.**  
  quote: "A logical address consists of two parts: a segment number, s, and an offset into that segment, d."  
  follow-up: _What is the purpose of splitting the logical address into two parts?_  
  expected: Splitting the logical address into a segment number and an offset allows the system to locate the correct segment and then determine the position within that segment.
- **The segment table contains base and limit information for each segment.**  
  quote: "The segment table is thus essentially an array of base– limit register pairs."  
  follow-up: _What role does the segment table play in address translation?_  
  expected: The segment table stores the base address and limit of each segment, which are used to translate logical addresses into physical memory addresses.

### [Optimal and LRU page replacement] Explain how the Optimal and LRU page replacement algorithms differ in their approach to page replacement, and why one might be considered better than the other in certain scenarios.
*confidence 0.78 · medium · slides [601, 602]*

**Reference:** The Optimal algorithm replaces the page that will not be used for the longest time in the future, making it theoretically the best possible algorithm. In contrast, LRU replaces the page that has not been used for the longest time in the past. While LRU is generally good and widely used, it cannot predict the future, which is why it performs worse than Optimal in some cases. However, LRU is easier to implement, while Optimal is not practical for real systems because it requires knowledge of the future.

**Key points** (slide quote → follow-up → expected answer):
- **Optimal replaces the page that will not be used for the longest time in the future.**  
  quote: "Replace page that will not be used for longest period of time"  
  follow-up: _Why can't LRU predict the future?_  
  expected: Because LRU uses past usage patterns, not future ones, and cannot know what will happen next.
- **LRU replaces the page that has not been used for the longest time in the past.**  
  quote: "Replace page that has not been used in the most amount of time"  
  follow-up: _What is the main limitation of LRU?_  
  expected: It cannot predict the future, so it may evict a page that will be needed soon.

### [Free-space management] Explain how free-space management in an operating system helps in reusing disk space efficiently.
*confidence 0.78 · medium · slides [723, 724, 725, 726, 727]*

**Reference:** Free-space management helps in reusing disk space by maintaining a free-space list that records all free disk blocks. When a file is deleted, its disk space is added back to the free-space list, making it available for new files. This ensures that disk space is not wasted and can be reused, improving overall storage efficiency.

**Key points** (slide quote → follow-up → expected answer):
- **When a file is deleted, its disk space is added to the free-space list.**  
  quote: "When a file is deleted, its disk space is added to the free-space list."  
  follow-up: _Why is it important to add the space back to the free-space list when a file is deleted?_  
  expected: It is important to add the space back to the free-space list so that it can be reused for new files, preventing wasted disk space and ensuring efficient storage utilization.
- **Free-space management ensures that disk space is not wasted and can be reused.**  
  quote: "Need to reuse the disk space from deleted files for new files."  
  follow-up: _How does the system ensure that disk space is reused efficiently?_  
  expected: The system ensures efficient reuse of disk space by maintaining a free-space list that tracks available blocks, allowing the system to allocate freed space to new files as needed.

### [Banker's algorithm] Explain how the Banker’s algorithm ensures that a system remains in a safe state when allocating resources to processes.
*confidence 0.78 · medium · slides [415, 416, 417, 419]*

**Reference:** The Banker’s algorithm ensures a safe state by simulating resource allocation and checking if there exists a sequence of process completions that allows all processes to finish. It uses the Work and Finish vectors to determine if a process can be safely allocated resources without leading to a deadlock. If a process can be allocated resources and still leave the system in a safe state, it is granted the resources, otherwise, it must wait.

**Key points** (slide quote → follow-up → expected answer):
- **The algorithm uses the Work vector to represent the available resources after allocation.**  
  quote: "Work = Work + Allocationi"  
  follow-up: _Why is the Work vector updated after a process is allocated resources?_  
  expected: To reflect the new available resources after the process completes its execution and releases its allocated resources.
- **The algorithm ensures that all processes can eventually complete by checking if all Finish[i] are true.**  
  quote: "If Finish[i] == true for all i, then the system is in a safe state."  
  follow-up: _What would happen if not all Finish[i] are true after the algorithm completes?_  
  expected: The system is in an unsafe state, and there is a possibility of deadlock.

### [Deadlock prevention] Explain how the 'circular wait' condition can be prevented in a system with multiple processes and shared resources.
*confidence 0.78 · medium · slides [372, 384, 385]*

**Reference:** The circular wait condition can be prevented by assigning a numerical number to each resource and requiring that processes request resources in increasing order of numbering. This ensures that a cycle of waiting cannot form. By enforcing this ordering, the system can avoid the circular wait condition, which is one of the four necessary conditions for deadlock.

**Key points** (slide quote → follow-up → expected answer):
- **Processes must request resources in increasing order of their assigned numerical numbers.**  
  quote: "Each resource will be assigned with a numerical number. A process can request the resources increasing/decreasing order of numbering."  
  follow-up: _What happens if a process requests resources in a non-ordered way?_  
  expected: The system may allow a circular wait, which could lead to a deadlock.
- **This is one of the four conditions that must be violated to prevent deadlock.**  
  quote: "Deadlock can arise if four conditions hold simultaneously. ... Circular wait: there exists a set {P0, P1, …, Pn} of waiting processes such that P0 is waiting for a resource that is held by P1, P1 is waiting for a resource that is held by P2, …, Pn–1 is waiting for a resource that is held by Pn, and Pn is waiting for a resource that is held by P0."  
  follow-up: _What would happen if all four conditions were satisfied?_  
  expected: A deadlock would occur, as all four necessary conditions for deadlock are met.

### [Inter-process communication] Explain how message passing differs from shared memory in terms of how processes communicate and synchronize.
*confidence 0.77 · medium · slides [191, 192, 202]*

**Reference:** Message passing allows processes to communicate without using shared variables, relying instead on send and receive operations. Shared memory, on the other hand, involves direct access to a common memory space. These differences impact how processes synchronize and manage data, with message passing often requiring explicit coordination to avoid race conditions.

**Key points** (slide quote → follow-up → expected answer):
- **Message passing uses send and receive operations to communicate.**  
  quote: "IPC facility provides two operations: send(message), receive(message)."  
  follow-up: _How do processes coordinate when using message passing?_  
  expected: They coordinate through the send and receive operations, which ensure that messages are delivered and processed in order.
- **Message passing does not rely on shared variables.**  
  quote: "Message system – processes communicate with each other without resorting to shared variables."  
  follow-up: _Why would a system prefer message passing over shared memory?_  
  expected: Message passing avoids the complexity of managing shared variables and synchronization, making it easier to implement in distributed systems.

---

## Held back (low confidence — not used by the app)

### [System calls] Explain what system calls are and why they are important in an operating system.
*confidence 0.74 · easy · slides [85, 86]*

**Reference:** System calls provide an interface to the services made available by an operating system. They are important because they allow programs to request services from the operating system in a controlled and secure manner. These calls are generally available as routines written in a higher level programming language or assembly language.

**Key points** (slide quote → follow-up → expected answer):
- **System calls provide an interface to the services made available by an operating system.**  
  quote: "System calls provide an interface to the services made available by an operating system."  
  follow-up: _What is the purpose of having an interface between programs and the operating system?_  
  expected: The purpose is to allow programs to request services from the operating system in a controlled and secure manner.
- **System calls are generally available as routines written in a higher level programming language or assembly language.**  
  quote: "These calls are generally available as routines written in a higher level programming language or assemblylanguage"  
  follow-up: _Why would a programmer use a system call instead of directly interacting with hardware?_  
  expected: A programmer uses a system call because it abstracts the complexity of hardware interaction and provides a standardized way to access operating system services.

### [Resource allocation graph] Explain what a claim edge is in a resource allocation graph.
*confidence 0.74 · easy · slides [373, 374, 394, 413]*

**Reference:** A claim edge in a resource allocation graph is a dashed line that indicates a process may request a resource at some future time. It is used to represent potential future requests in the system. When a process actually requests a resource, the claim edge is converted to a request edge. This helps in detecting deadlocks by considering future resource needs in the graph.

**Key points** (slide quote → follow-up → expected answer):
- **A claim edge represents a potential future request of a process for a resource.**  
  quote: "A claim edge Pi → Rj indicates that process Pi may request resource Rj at some time in the future. This edge resembles a request edge in direction but is represented in the graph by a dashed line."  
  follow-up: _What happens when a process actually requests a resource?_  
  expected: When a process actually requests a resource, the claim edge is converted to a request edge.
- **Claim edges are used to model future resource needs in the system.**  
  quote: "The resources must be claimed a priori in the system. That is, before process Pi starts executing, all its claim edges must already appear in the resource-allocation graph."  
  follow-up: _Why are claim edges important for deadlock detection?_  
  expected: Claim edges are important because they allow the system to consider future resource needs, which is essential for detecting potential deadlocks.

### [Fragmentation] Explain what internal fragmentation is, and why it occurs.
*confidence 0.74 · easy · slides [473, 474]*

**Reference:** Internal fragmentation occurs when allocated memory is slightly larger than the requested memory. This unused space is internal to a partition and not used by the process. It happens because memory is allocated in fixed-size blocks, and the allocated block may be larger than what is needed by the process.

**Key points** (slide quote → follow-up → expected answer):
- **Internal fragmentation is when allocated memory is slightly larger than requested memory.**  
  quote: "Internal Fragmentation – allocated memory may be slightly larger than requested memory; this size difference is memory internal to a partition, but not being used"  
  follow-up: _What happens if a process requests exactly the size of a memory block?_  
  expected: The process would use the entire block, and there would be no internal fragmentation for that block.
- **Internal fragmentation is memory that is internal to a partition and not used.**  
  quote: "Internal Fragmentation – allocated memory may be slightly larger than requested memory; this size difference is memory internal to a partition, but not being used"  
  follow-up: _Why is the unused memory considered internal to a partition?_  
  expected: Because the unused memory is part of the allocated block, which is assigned to a process, but not used by it.

### [Thrashing] Explain what thrashing is and why it happens in a paging system.
*confidence 0.74 · easy · slides [620, 621, 622, 623]*

**Reference:** Thrashing results in severe performance problems. It occurs when the degree of multiprogramming increases to the point where the sum of the sizes of the localities of all running processes exceeds the total memory size. This causes the system to spend more time swapping pages in and out of memory than executing instructions.

**Key points** (slide quote → follow-up → expected answer):
- **Thrashing results in severe performance problems.**  
  quote: "Thrashing results in severe performance problems."  
  follow-up: _What happens to CPU utilization when thrashing occurs?_  
  expected: CPU utilization decreases because the system spends more time swapping pages than executing instructions.
- **Thrashing occurs when the sum of the sizes of the localities exceeds memory size.**  
  quote: "Why does thrashing occur? Σ size of locality > total memory size"  
  follow-up: _What is the role of locality in thrashing?_  
  expected: Locality refers to the tendency of a process to access a limited set of pages over a short period, and when this exceeds memory capacity, thrashing occurs.

### [Round robin scheduling] Explain what round-robin scheduling is and how it differs from FCFS scheduling.
*confidence 0.74 · easy · slides [137]*

**Reference:** Round-robin scheduling is a CPU scheduling algorithm designed especially for timesharing systems. It is similar to FCFS scheduling, but preemption is added to enable the system to switch between processes. This preemption is achieved by using a time quantum, which limits the amount of time a process can run before being interrupted and moved to the end of the ready queue.

**Key points** (slide quote → follow-up → expected answer):
- **Round-robin scheduling is designed especially for timesharing systems.**  
  quote: "Round-robin (RR) scheduling algorithm is designed especially for timesharing systems."  
  follow-up: _What is the main purpose of round-robin scheduling?_  
  expected: The main purpose is to enable timesharing in a system by allowing multiple processes to share the CPU in a fair and predictable manner.
- **Round-robin scheduling uses preemption to switch between processes.**  
  quote: "It is similar to FCFS scheduling, but preemption is added to enable the system to switch between processes."  
  follow-up: _How does round-robin scheduling differ from FC,FS in terms of process switching?_  
  expected: Round-robin uses preemption to switch between processes, whereas FCFS does not interrupt a running process until it completes its time slice.

### [File allocation methods] Compare the advantages and disadvantages of indexed allocation with linked allocation, focusing on how they handle external fragmentation and pointer overhead.
*confidence 0.74 · medium · slides [706, 709, 710, 713, 715]*

**Reference:** Indexed allocation overcomes external fragmentation by allowing non-contiguous block allocation, while linked allocation avoids external fragmentation entirely by chaining blocks together. Indexed allocation has higher pointer overhead because each file requires its own index block(s), whereas linked allocation only needs a pointer per block. Indexed allocation supports direct access to file blocks, which is not possible with linked allocation. However, indexed allocation is less efficient for very small files due to the overhead of maintaining an index block.

**Key points** (slide quote → follow-up → expected answer):
- **Indexed allocation has higher pointer overhead than linked allocation.**  
  quote: "The pointer overhead for indexed allocation is greater than linked allocation."  
  follow-up: _What causes indexed allocation to have higher pointer overhead?_  
  expected: Because each file requires its own index block(s) to store pointers, which uses more disk space compared to linked allocation.
- **Indexed allocation is less efficient for very small files.**  
  quote: "For very small files, say files that expand only 2-3 blocks, the indexed allocation would keep one entire block (index block) for the pointers which is inefficient in terms of memory utilization."  
  follow-up: _Why is indexed allocation inefficient for small files?_  
  expected: Because it reserves an entire block for the index, even if the file only needs a few blocks, leading to wasted space.

### [Virtual memory and demand paging] Explain how the lazy swapper improves the efficiency of demand paging.
*confidence 0.71 · medium · slides [567, 568, 573, 630, 631, 632]*

**Reference:** The lazy swapper improves the efficiency of demand paging by only swapping pages into memory when they are actually needed. This reduces unnecessary I/O operations and conserves memory resources. It ensures that pages are loaded into memory only when a page fault occurs, which aligns with the principle of demand paging. This approach also allows more users to run concurrently since memory is used more efficiently.

**Key points** (slide quote → follow-up → expected answer):
- **The lazy swapper only swaps pages into memory when they are needed.**  
  quote: "Lazy swapper – never swaps a page into memory unless page will be needed"  
  follow-up: _What happens if a page is swapped into memory before it is needed?_  
  expected: It results in unnecessary I/O operations and wasted memory resources.
- **The lazy swapper reduces unnecessary I/O operations.**  
  quote: "Less I/O needed, no unnecessary I/O"  
  follow-up: _Why would unnecessary I/O be a problem in demand paging?_  
  expected: Unnecessary I/O increases the time required to load pages into memory and reduces system performance.

### [Interrupts] Explain how the operating system handles an interrupt and why it's important for system responsiveness.
*confidence 0.70 · medium · slides [19, 20, 47]*

**Reference:** The operating system handles an interrupt by saving the state of the CPU through registers and the program counter, then transferring control to the appropriate interrupt service routine via the interrupt vector. This process is important for system responsiveness because it allows the OS to quickly respond to external events, such as device input or errors, without waiting for the current process to complete.

**Key points** (slide quote → follow-up → expected answer):
- **The operating system saves the state of the CPU during an interrupt.**  
  quote: "The operating system saves the state of the CPU by storing registers and the program counter"  
  follow-up: _What happens if the operating system doesn't save the state of the CPU during an interrupt?_  
  expected: The CPU would continue executing the interrupted instruction, potentially leading to incorrect program behavior or data corruption.
- **Interrupts are transferred to the appropriate service routine via the interrupt vector.**  
  quote: "Interrupt transfers control to the interrupt service routine generally, through the interrupt vector, which contains the addresses of all the service routines"  
  follow-up: _Why is the interrupt vector important in handling interrupts?_  
  expected: The interrupt vector is important because it provides the addresses of the service routines, allowing the OS to quickly locate and execute the correct handler for each type of interrupt.

### [Readers-writers problem] Explain how the readers-writers problem is solved using semaphores and the read_count variable, and why this solution might not prevent starvation.
*confidence 0.70 · medium · slides [338, 339, 340, 341, 342]*

**Reference:** The readers-writers problem is solved using semaphores and the read_count variable to allow multiple readers to access the shared resource simultaneously while preventing writers from accessing it when readers are present. The solution ensures that a writer can only write when no readers are active, and readers can continue reading even when a writer is waiting. However, this approach may not prevent starvation, as writers could be indefinitely delayed if readers keep arriving.

**Key points** (slide quote → follow-up → expected answer):
- **Multiple readers can access the shared resource simultaneously.**  
  quote: "Any number of readers can read from the shared resource simultaneously, but only one writer can write to the shared resource."  
  follow-up: _What happens if a writer arrives while readers are already accessing the resource?_  
  expected: The writer will have to wait until all readers have finished reading, as the writer cannot proceed while any readers are active.
- **A writer cannot write if there are active readers.**  
  quote: "A writer cannot write to the resource if there are non zero number of readers accessing the resource at that time."  
  follow-up: _How does the solution ensure that a writer cannot write while readers are active?_  
  expected: The writer process uses the rw_mutex semaphore to block until no readers are accessing the resource, which is enforced by the read_count variable.

### [RAID levels] Explain how RAID levels 1, 5, and 10 differ in terms of redundancy, performance, and storage efficiency.
*confidence 0.70 · medium · slides [786, 787, 794, 795, 917]*

**Reference:** RAID 1 provides full mirroring of data across two disks, offering high redundancy but only half the storage efficiency. RAID 5 uses parity information across multiple disks, offering better storage efficiency than RAID 1 but with slower write performance. RAID 10 combines RAID 1 and RAID 0, using mirroring within striped sets, which provides both high performance and redundancy, but at the cost of half the storage capacity due to mirroring.

**Key points** (slide quote → follow-up → expected answer):
- **RAID 1 uses mirroring to duplicate data on two disks, providing redundancy.**  
  quote: "Disk mirroring, or RAID level 1, is a robust scheme that uses a mirror set — two equally sized partitions on two disks with identical data contents."  
  follow-up: _What happens if one of the disks in a RAID 1 array fails?_  
  expected: The data remains intact because the mirror set on the second disk contains an exact copy of the data.
- **RAID 10 combines mirroring and striping to provide high performance and redundancy.**  
  quote: "RAID level 10 - combining RAID 1 and RAID 0 - provides security by mirroring all data on secondary drives while using striping across each set of drives to speed up data transfers."  
  follow-up: _What is the main trade-off of using RAID 10?_  
  expected: RAID 10 sacrifices half of the storage capacity to the mirroring process, making it less storage-efficient than RAID 5.

### [Schedulers] How does the ordering of the ready queue affect the behavior of the short-term scheduler?
*confidence 0.70 · medium · slides [125]*

**Reference:** The ordering of the ready queue directly influences which process the short-term scheduler selects next. The queue may be ordered in various ways, such as FIFO, priority, or other structures. This ordering determines the scheduling policy and impacts fairness, responsiveness, and resource utilization. For example, a priority-based queue ensures higher-priority processes are scheduled first, while FIFO ensures first-come, first-served behavior.

**Key points** (slide quote → follow-up → expected answer):
- **The ordering of the ready queue determines the scheduling policy.**  
  quote: "The queue may be ordered in various ways"  
  follow-up: _What would happen if the ready queue was unordered?_  
  expected: The scheduler would have no consistent way to choose the next process, potentially leading to arbitrary or inefficient scheduling.
- **Different queue orderings reflect different scheduling policies.**  
  quote: "The queue may be ordered in various ways"  
  follow-up: _Can you name two different ways the ready queue might be ordered?_  
  expected: Yes, examples include FIFO and priority-based ordering.

### [SJF and SRTF scheduling] Explain how SRTF differs from SJF and why it might be more suitable for certain scenarios.
*confidence 0.70 · medium · slides [109, 116, 764]*

**Reference:** SRTF is a preemptive version of SJF, where the process with the shortest remaining time is executed next. This allows for preemption, meaning a running process can be interrupted if a shorter job arrives. This makes SRTF more responsive to short jobs, which can reduce average waiting time. However, it may lead to increased context switching and potential starvation of longer processes if not managed carefully.

**Key points** (slide quote → follow-up → expected answer):
- **SRTF is a preemptive version of SJF.**  
  quote: "Preemptive SJF Scheduling is sometimes called SRTF."  
  follow-up: _What happens if a new process arrives with a shorter burst time than the currently running process?_  
  expected: The currently running process is preempted, and the new shorter process is scheduled next.
- **SRTF can lead to starvation of longer processes.**  
  quote: "SRTF scheduling is a form of SJF scheduling; may cause starvation of some requests."  
  follow-up: _What trade-off does SRTF introduce in scheduling?_  
  expected: SRTF improves average waiting time but may cause starvation of longer processes if they are continually preempted.

### [Swapping] What happens to a process's memory image when it is swapped out, and how does this affect its ability to resume execution?
*confidence 0.70 · hard · slides [456, 457] · ⚠ NEEDS REVIEW*

**Reference:** When a process is swapped out, its entire memory image is moved from physical memory to the backing store. This allows other processes to use the freed memory. The process can resume execution only if its memory image is swapped back into physical memory, which depends on the address binding method and any pending I/O operations.

**Key points** (slide quote → follow-up → expected answer):
- **The memory image of a swapped-out process is moved to the backing store.**  
  quote: "A process can be swapped temporarily out of memory to a backing store, and then brought back into memory for continued execution"  
  follow-up: _What happens to the memory used by the process when it is swapped out?_  
  expected: The memory is transferred to the backing store, freeing up physical memory for other processes.
- **The process can resume execution only if its memory image is swapped back into physical memory.**  
  quote: "Does the swapped out process need to swap back in to same physical addresses?"  
  follow-up: _Can a swapped-out process resume execution without being swapped back into the same physical addresses?_  
  expected: No, it depends on the address binding method and whether the system can rebind the addresses correctly.

### [RAID levels] How does RAID 6 differ from RAID 5 in terms of fault tolerance and performance, and what trade-off does this introduce?
*confidence 0.70 · hard · slides [786, 787, 794, 795, 917] · ⚠ NEEDS REVIEW*

**Reference:** RAID 6 differs from RAID 5 by using two parity drives instead of one, which allows it to withstand the failure of two drives simultaneously. This increased redundancy comes at the cost of slower write performance, as the system must calculate and write two sets of parity data. The trade-off is between enhanced fault tolerance and reduced write efficiency.

**Key points** (slide quote → follow-up → expected answer):
- **RAID 6 uses two parity drives to allow for the failure of two drives.**  
  quote: "RAID 6 is like RAID 5, but the parity data are written to two drives. ⮚That means it requires at least 4 drives and can withstand 2 drives dying simultaneously."  
  follow-up: _What happens if two drives fail in a RAID 5 array?_  
  expected: RAID 5 cannot recover from the failure of two drives, as it only has one parity drive to reconstruct the data.
- **RAID 6 has slower write performance due to the need to calculate and store two parity sets.**  
  quote: "RAID 6 ... Write data transactions are slower than RAID 5 due to the additional parity data that have to be calculated."  
  follow-up: _Why would someone choose RAID 5 over RAID 6?_  
  expected: RAID 5 offers better write performance and uses less storage for parity, making it more efficient for write-heavy workloads.

### [Deadlock vs starvation vs livelock] In the bridge crossing example, how do deadlock, starvation, and livelock differ in their implications for resource allocation and system behavior?
*confidence 0.69 · hard · slides [371] · ⚠ NEEDS REVIEW*

**Reference:** Deadlock occurs when cars are stuck waiting for each other to release resources, requiring one to back up to resolve. Starvation is possible when certain cars are consistently denied access to the bridge, even though they may eventually get it. Livelock is not explicitly mentioned, but it could imply that cars keep yielding without progress, which is different from deadlock and starvation.

**Key points** (slide quote → follow-up → expected answer):
- **Deadlock requires a rollback to resolve, as cars must back up to release resources.**  
  quote: "If a deadlock occurs, it can be resolved if one car backs up (preempt resources and rollback)"  
  follow-up: _What happens if no car is willing to back up in the bridge example?_  
  expected: A deadlock persists, and the system remains in a state of no progress.
- **The example highlights that OSes typically do not prevent or resolve deadlocks, implying that deadlock is a system-level challenge.**  
  quote: "Note – Most OSes do not prevent or deal with deadlocks"  
  follow-up: _Why might an OS not deal with deadlocks?_  
  expected: Because detecting and resolving deadlocks can be computationally expensive and may introduce other complexities into the system.

### [Producer-consumer problem] How do the semaphores `empty` and `full` contribute to solving the bounded-buffer problem in the producer-consumer model?
*confidence 0.69 · medium · slides [195, 335, 336, 337]*

**Reference:** The `empty` semaphore ensures that the producer does not add items to a full buffer, while the `full` semaphore ensures that the consumer does not remove items from an empty buffer. These semaphores work together with the `mutex` semaphore to prevent race conditions and ensure mutual exclusion when accessing the shared buffer. The `empty` starts at `n` because the buffer can hold `n` items, and `full` starts at `0` because the buffer is initially empty.

**Key points** (slide quote → follow-up → expected answer):
- **The `empty` semaphore ensures the producer does not add items to a full buffer.**  
  quote: "Consumer must wait if the buffer is empty; producer must wait if the buffer is full"  
  follow-up: _What happens if the `empty` semaphore is initialized to 0 instead of `n`?_  
  expected: The producer would immediately block because the buffer is full, and no items can be added.
- **The `full` semaphore ensures the consumer does not remove items from an empty buffer.**  
  quote: "Consumer must wait if the buffer is empty; producer must wait if the buffer is full"  
  follow-up: _What would be the consequence if the `full` semaphore was initialized to `n` when the buffer is empty?_  
  expected: The consumer would immediately block because the buffer is empty, even though it was initialized to `n`.

### [Readers-writers problem] What is the significance of the two semaphores (rw_mutex and mutex) in the readers-writers problem, and how do they interact with the read_count variable to manage access to the shared resource?
*confidence 0.68 · hard · slides [338, 339, 340, 341, 342] · ⚠ NEEDS REVIEW*

**Reference:** The rw_mutex ensures that writers have exclusive access when they are writing, while the mutex manages access to the read_count variable to prevent race conditions. The read_count tracks the number of active readers, and when it transitions from 0 to 1, the rw_mutex is acquired to block writers. When read_count drops to 0, the rw_mutex is released to allow writers to proceed.

**Key points** (slide quote → follow-up → expected answer):
- **The rw_mutex ensures that writers have exclusive access when they are writing.**  
  quote: "When a writer is writing data to the resource, no other process can access the resource."  
  follow-up: _What happens if a writer tries to write while another writer is already writing?_  
  expected: It would be blocked by the rw_mutex, ensuring only one writer can write at a time.
- **The read_count variable is used to determine when to block or unblock writers.**  
  quote: "if (read_count == 1) wait(rw_mutex); ... if (read_count == 0) signal(rw_mutex);"  
  follow-up: _What would happen if read_count was not used to control the rw_mutex?_  
  expected: Writers might be allowed to write even when there are active readers, violating the requirement that writers cannot write if readers are active.

### [Process creation and termination] How do `wait()` and `waitpid()` differ in their behavior when a child process terminates and how does this affect process synchronization?
*confidence 0.68 · medium · slides [97, 219]*

**Reference:** The `wait()` function blocks the parent process until any child process terminates, whereas `waitpid()` allows the parent to wait for a specific child process. This difference affects synchronization by giving the parent more control over which child it waits for. Both functions return the process ID on success, but `waitpid()` can be used to check the status of a particular child without blocking the parent.

**Key points** (slide quote → follow-up → expected answer):
- **The `wait()` function blocks the parent process until any child process terminates.**  
  quote: "A process that calls wait or waitpid can
  - Block, if all of its children are still running"  
  follow-up: _What happens if a parent process calls `wait()` while no child processes are running?_  
  expected: The `wait()` function will return immediately with an error, indicating that there are no child processes.
- **Both `wait()` and `waitpid()` return the process ID on success.**  
  quote: "Both return: process ID on success, 0 if state hasn’t changed or −1 on failure"  
  follow-up: _What does it mean if `wait()` returns 0?_  
  expected: If `wait()` returns 0, it means that no child process has terminated and there is no change in the state of the children.

### [Preemptive vs non-preemptive scheduling] Consider a scenario where a process is in the middle of updating shared data structures in kernel mode. How does the preemptive vs non-preemptive scheduling model affect the possibility of race conditions and the need for synchronization mechanisms?
*confidence 0.63 · hard · slides [126, 127, 135] · ⚠ NEEDS REVIEW*

**Reference:** In preemptive scheduling, the operating system can interrupt a process while it is in kernel mode, which may lead to race conditions if the process is interrupted during the update of shared data. This is why preemptive kernels require mechanisms like mutex locks to prevent such inconsistencies. In contrast, non-preemptive scheduling does not allow such interruptions during critical sections, reducing the risk of race conditions but potentially leading to lower system responsiveness.

**Key points** (slide quote → follow-up → expected answer):
- **Preemptive scheduling may require mechanisms like mutex locks to prevent race conditions.**  
  quote: "A pre-emptive kernel requires mechanisms such as mutex locks to prevent race conditions when accessing shared kernel data structures."  
  follow-up: _What happens if a process is interrupted while updating shared data structures without such mechanisms?_  
  expected: A race condition can occur, leading to inconsistent or corrupted data.
- **Preemptive scheduling allows the OS to interrupt a process in kernel mode.**  
  quote: "Consider preemption while in kernel mode"  
  follow-up: _Why would the OS need to be able to interrupt a process while it is in kernel mode?_  
  expected: To allow for fair resource allocation and responsiveness, even during critical operations.

### [Multiprocessor scheduling] What are the implications of having a single master processor in asymmetric multiprocessing on the system's ability to scale with additional processors?
*confidence 0.63 · hard · slides [151] · ⚠ NEEDS REVIEW*

**Reference:** In asymmetric multiprocessing, the master processor handles all scheduling decisions and system activities, which limits the system's ability to scale with additional processors. This is because the master processor becomes a bottleneck, as all scheduling and coordination must pass through it. The other processors can only execute user code, which reduces their ability to contribute to system performance as more processors are added.

**Key points** (slide quote → follow-up → expected answer):
- **The master processor in asymmetric multiprocessing is the sole scheduler and coordinator of system activities.**  
  quote: "CPU scheduling in a multiprocessor system has all scheduling decisions, I/O processing, and other system activities handled by a single processor—the master server."  
  follow-up: _What happens if you add more processors to a system using asymmetric multiprocessing?_  
  expected: Adding more processors would not improve performance because the master processor remains the bottleneck, and the additional processors cannot contribute to scheduling or system coordination.
- **Other processors in asymmetric multiprocessing can only execute user code, not system code.**  
  quote: "The other processors execute only user code."  
  follow-up: _Why would a processor in asymmetric multiprocessing not be able to handle system tasks?_  
  expected: Because the master processor is responsible for all system activities, including scheduling and I/O processing, other processors are restricted to executing user code only.

### [Interrupts] What happens if a software interrupt occurs during the execution of a critical section of code, and why is this a concern for system stability?
*confidence 0.62 · hard · slides [19, 20, 47] · ⚠ NEEDS REVIEW*

**Reference:** If a software interrupt occurs during a critical section, the operating system must save the state of the CPU to ensure the interrupted process can resume correctly. This is a concern because critical sections are designed to be atomic, and an interrupt could introduce race conditions or corrupt shared data. The interrupt handling mechanism must preserve the program counter and registers to avoid data inconsistency.

**Key points** (slide quote → follow-up → expected answer):
- **Interrupt handling must preserve the state of the CPU to allow resumption of the interrupted process.**  
  quote: "The operating system saves the state of the CPU by storing registers and the program counter"  
  follow-up: _What happens if the interrupt handler does not save the program counter?_  
  expected: The interrupted process would lose its place in execution and may execute incorrect code, leading to unpredictable behavior.
- **The interrupt vector directs the CPU to the appropriate service routine for the interrupt.**  
  quote: "Interrupt transfers control to the interrupt service routine generally, through the interrupt vector, which contains the addresses of all the service routines"  
  follow-up: _How does the interrupt vector help in handling software interrupts?_  
  expected: The interrupt vector provides the address of the service routine, ensuring the correct handler is invoked for the type of interrupt.

### [Banker's algorithm] What happens to the system’s safety status if a process requests more resources than are currently available, and how does the Banker’s algorithm handle this situation?
*confidence 0.62 · hard · slides [415, 416, 417, 419] · ⚠ NEEDS REVIEW*

**Reference:** If a process requests more resources than are currently available, the system cannot immediately grant the request. The Banker’s algorithm checks whether granting the request would leave the system in a safe state. If the system remains safe after the hypothetical allocation, the request is granted; otherwise, the process must wait until resources become available.

**Key points** (slide quote → follow-up → expected answer):
- **The Banker’s algorithm checks whether granting a resource request would leave the system in a safe state.**  
  quote: "When a user requests a set of resources, the system must determine whether the allocation of these resources will leave the system in a safe state."  
  follow-up: _What would happen if the system cannot determine whether the allocation would leave the system in a safe state?_  
  expected: The system would not grant the request, as it cannot ensure the system remains in a safe state.
- **The system may reject a request even if the requested resources are available, if the resulting state is unsafe.**  
  quote: "A request for (0,2,0) by P0 cannot be granted, even though the resources are available, since the resulting state is unsafe."  
  follow-up: _Can a process ever be denied resources even if they are available?_  
  expected: Yes, a process may be denied resources if granting the request would result in an unsafe state.

### [SJF and SRTF scheduling] Consider a scenario where multiple processes arrive at different times, and their burst times are known. How would the use of SRTF scheduling affect the average waiting time compared to non-preemptive SJF, and what trade-offs might arise from this?
*confidence 0.62 · hard · slides [109, 116, 764] · ⚠ NEEDS REVIEW*

**Reference:** SRTF scheduling can reduce average waiting time by preempting longer-running processes when shorter ones arrive, which aligns with the principle that SJF is optimal for minimizing average waiting time. However, this preemptive behavior may introduce overhead due to context switches and could lead to increased complexity in managing process priorities. The trade-off is between improved responsiveness and the potential for higher system overhead and fairness concerns.

**Key points** (slide quote → follow-up → expected answer):
- **SRTF can reduce average waiting time by preempting longer-running processes.**  
  quote: "SJF is optimal – gives minimum average waiting time for a given set of processes"  
  follow-up: _What happens to the average waiting time if a shorter process arrives while a longer one is running?_  
  expected: The average waiting time may decrease because the shorter process will be executed first, potentially reducing the overall waiting time for other processes.
- **SRTF may lead to fairness issues due to potential starvation of longer processes.**  
  quote: "SRTF scheduling is a form of SJF scheduling; may cause starvation of some requests"  
  follow-up: _How might the scheduling algorithm affect the fairness of process execution?_  
  expected: Longer processes may be starved if many shorter ones keep arriving, leading to unfairness in resource allocation.

### [Paging] Explain the trade-offs of using smaller versus larger page sizes in a paging system, and how they affect the system's memory usage and performance.
*confidence 0.61 · hard · slides [497, 498, 503, 504, 505, 524] · ⚠ NEEDS REVIEW*

**Reference:** Smaller page sizes reduce internal fragmentation and allow for more efficient use of memory, but they increase the number of page table entries, which consumes more memory and can slow down address translation. Larger page sizes reduce the number of page table entries, lowering memory overhead and improving performance, but they may lead to higher internal fragmentation. The choice between small and large page sizes involves balancing these trade-offs based on the system's workload and memory constraints.

**Key points** (slide quote → follow-up → expected answer):
- **Smaller page sizes reduce internal fragmentation.**  
  quote: "Worst case fragmentation = 1 frame – 1 byte. On average fragmentation = 1 / 2 frame size."  
  follow-up: _What happens if the page size is very small, like 1 byte?_  
  expected: It would significantly reduce internal fragmentation, but the number of page table entries would explode, making address translation very slow.
- **Larger page sizes reduce the number of page table entries.**  
  quote: "If the page size is smaller, an overhead is involved with each page table entry."  
  follow-up: _How does increasing the page size affect the memory used by the page table?_  
  expected: It reduces the number of page table entries, which decreases the memory required for the page table.

### [Critical section problem] What would be the consequence of violating the bounded waiting condition in a system with multiple processes competing for a critical section?
*confidence 0.60 · hard · slides [293] · ⚠ NEEDS REVIEW*

**Reference:** Violating the bounded waiting condition would allow a process to be indefinitely postponed from entering its critical section, even though other processes are repeatedly entering theirs. This can lead to starvation, where a process is never able to execute in its critical section. Bounded waiting ensures that every process gets a fair chance to enter its critical section within a finite number of attempts, maintaining system fairness and preventing indefinite waiting.

**Key points** (slide quote → follow-up → expected answer):
- **Bounded waiting prevents indefinite waiting for a process to enter its critical section.**  
  quote: "A bound must exist on the number of times that other processes are allowed to enter their critical sections after a process has made a request to enter its critical section and before that request is granted."  
  follow-up: _What happens if a process is allowed to wait indefinitely for its turn to enter the critical section?_  
  expected: It results in starvation, where the process is never able to execute in its critical section.
- **Bounded waiting ensures fairness among processes in accessing the critical section.**  
  quote: "A bound must exist on the ... before that request is granted."  
  follow-up: _Why is fairness important in the context of the critical section problem?_  
  expected: Fairness ensures that no process is unfairly denied access to the critical section for an extended period, maintaining system predictability and responsiveness.

### [Threads] What are the trade-offs between user-level and kernel-level threads, and how do these affect the design of multithreaded applications?
*confidence 0.50 · hard · slides [231, 232, 234, 235, 236] · ⚠ NEEDS REVIEW*

**Reference:** User-level threads are managed entirely by the application or runtime library, which allows for faster thread creation and context switching, but limits the OS's ability to schedule them. Kernel-level threads are managed by the OS, enabling true concurrency and better utilization of multiple processors, but at the cost of higher overhead. These trade-offs influence whether an application can take advantage of parallelism and how it handles blocking operations.

**Key points** (slide quote → follow-up → expected answer):
- **Kernel-level threads are managed by the OS and can be scheduled independently.**  
  quote: "Kernel-level threads: These threads are managed by the OS itself."  
  follow-up: _How does this affect the ability of a program to run on multiple processors?_  
  expected: Kernel-level threads can be scheduled on different processors, enabling true parallel execution.
- **Kernel-level threads allow for true concurrency and better scalability.**  
  quote: "Threads can run on multiple cores parallelly."  
  follow-up: _What is a potential downside of using kernel-level threads?_  
  expected: They require more system resources and have higher overhead due to OS involvement in scheduling.
