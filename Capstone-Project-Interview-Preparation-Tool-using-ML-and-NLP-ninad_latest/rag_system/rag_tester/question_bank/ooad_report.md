# Question bank: ooad

- **Active (used by the app): 64** · held back for review: 23 (confidence threshold 0.75)
- Sorted by confidence, best first. Held-back questions are kept below, not deleted.

## Active questions

### [Interfaces] Explain what an interface is in Java, and how it supports abstraction.
*confidence 0.96 · easy · slides [121, 309, 314, 420, 421, 424]*

**Reference:** An interface in Java is a collection of abstract methods and constants that a class must implement. It says what a class supporting this interface can do, but not how. This supports 100% abstraction by defining behavior without implementation details. Interfaces allow multiple inheritance in Java, which is not possible with classes.

**Key points** (slide quote → follow-up → expected answer):
- **An interface defines behavior without implementation.**  
  quote: "An interface in Java says what a class supporting this interface can do. It does not say how these will be implemented by the class supporting this interface."  
  follow-up: _What is the purpose of an interface if it doesn't provide implementation?_  
  expected: The purpose is to define the behavior that a class must support, enabling abstraction and allowing different classes to implement the same interface in different ways.
- **Interfaces support 100% abstraction.**  
  quote: "It is used to achieve 100% abstraction and multiple inheritance in Java."  
  follow-up: _How does an interface help in achieving abstraction?_  
  expected: An interface allows you to define a contract without providing implementation, which hides the internal details and focuses on what the class can do.
- **Interfaces enable multiple inheritance in Java.**  
  quote: "Note : In Java 8+ version, interfaces can have methods with default implementation."  
  follow-up: _Why is multiple inheritance not possible with classes but possible with interfaces?_  
  expected: Multiple inheritance is not possible with classes due to ambiguity, but interfaces avoid this by only defining behavior, not implementation, allowing a class to implement multiple interfaces.

### [Constructors] Can you explain what a constructor is and why it's important in object-oriented programming?
*confidence 0.96 · easy · slides [324, 325, 326, 329, 390, 766]*

**Reference:** A constructor is a special method that initializes an object when it is created. It has the same name as its class and no explicit return type. It is important because it allows you to set initial values for the instance variables of a class, ensuring that the object is in a valid state as soon as it is created.

**Key points** (slide quote → follow-up → expected answer):
- **A constructor is a special method that initializes an object when it is created.**  
  quote: "A constructor initializes an object when it is created."  
  follow-up: _What happens if you don't define a constructor in a class?_  
  expected: The Java compiler automatically provides a default constructor that initializes all member variables to zero or their corresponding default values.
- **A constructor has the same name as its class and no explicit return type.**  
  quote: "It has the same name as its class and is syntactically similar to a method. Constructors have no explicit return type."  
  follow-up: _Can a constructor have a return type?_  
  expected: No, constructors cannot have a return type, not even void.
- **A constructor is important for initializing instance variables.**  
  quote: "Use a constructor to give initial values to the instance variables defined by the class, or to perform any other start-up procedures required to create a fully formed object."  
  follow-up: _Why would you want to use a constructor instead of initializing variables in a method?_  
  expected: Because constructors ensure that the object is properly initialized as soon as it is created, which helps prevent bugs and ensures consistent object states.

### [Coupling and cohesion] Explain what high cohesion means and why it is important in software design.
*confidence 0.96 · easy · slides [506, 507, 508, 509, 519, 520]*

**Reference:** High cohesion means that the responsibilities of a class are strongly related and focused. This makes the class easier to understand, maintain, and reuse. When a class has high cohesion, it performs a single, well-defined task, which reduces complexity and improves the overall design of the system.

**Key points** (slide quote → follow-up → expected answer):
- **High cohesion means that the responsibilities of a class are strongly related and focused.**  
  quote: "Cohesion - A measure of how strongly related and focused the responsibilities of an element (class, subsystem, etc.)"  
  follow-up: _What happens if a class has many unrelated responsibilities?_  
  expected: It leads to low cohesion, making the class harder to understand, maintain, and reuse.
- **High cohesion makes the class easier to understand, maintain, and reuse.**  
  quote: "Problems from low cohesion (does many unrelated things or does too much work): Hard to understand/comprehend Hard to reuse Hard to maintain Brittle – easily affected by change"  
  follow-up: _Why is it important to keep cohesion high in a system?_  
  expected: High cohesion reduces complexity, improves maintainability, and increases the reusability of code.
- **High cohesion reduces complexity and improves the overall design of the system.**  
  quote: "High cohesion - Monopoly example"  
  follow-up: _How does high cohesion affect the overall design of a system?_  
  expected: It leads to a more modular, maintainable, and understandable system structure.

### [Indirection and pure fabrication] Explain what pure fabrication is and when it is used.
*confidence 0.96 · easy · slides [492, 553, 554, 555, 556, 561]*

**Reference:** Pure fabrication is a design principle used when assigning responsibility to domain classes causes design issues. It involves creating artificial or convenience classes to encapsulate complex or non-natural responsibilities, promoting modularity and reusability. This approach helps maintain high cohesion and low coupling by isolating responsibilities from core domain objects.

**Key points** (slide quote → follow-up → expected answer):
- **Pure fabrication is used when assigning responsibility to domain classes causes design issues.**  
  quote: "Pure Fabrication is used when: A) Assigning responsibility to domain classes causes design issues"  
  follow-up: _What happens if you assign responsibilities directly to domain classes?_  
  expected: It can lead to poor cohesion, poor coupling, or low reuse potential, which violates good design principles.
- **Pure fabrication involves creating artificial or convenience classes.**  
  quote: "Solution: Assign a highly cohesive set of responsibilities to an artificial or convenience class that does not represent a domain concept"  
  follow-up: _What is the purpose of creating an artificial class in this context?_  
  expected: To encapsulate complex or non-natural responsibilities, isolating them from the core domain objects.
- **Pure fabrication promotes modularity and reusability.**  
  quote: "Promote Modularity and Reusability: By encapsulating complex responsibilities in pure fabrication classes, Java developers can promote modularity and reusability in their codebase."  
  follow-up: _How does pure fabrication help with reusability?_  
  expected: By encapsulating responsibilities in separate classes, these can be reused across different parts of the system or in different applications.

### [Open-closed principle] Explain the Open-Closed Principle in your own words.
*confidence 0.96 · easy · slides [601]*

**Reference:** The Open-Closed Principle states that classes, modules, and other code units should be open for extension but closed for modification. This means that existing code should not need to be changed when new features are added. Instead, we should extend the behavior of existing code using OOP features like inheritance and interfaces. The principle helps minimize the risk of introducing bugs by avoiding direct modifications to working code.

**Key points** (slide quote → follow-up → expected answer):
- **Classes and modules should be open for extension but closed for modification.**  
  quote: "Classes, modules, microservices, and other code units should be open for extension but closed for modification."  
  follow-up: _What happens if you need to add a new feature to an existing class?_  
  expected: You should extend the class using inheritance or interfaces, rather than modifying its existing code.
- **The principle encourages using OOP features like inheritance and interfaces for extension.**  
  quote: "We should be able to extend the existing code using OOP features like inheritance via subclasses and interfaces."  
  follow-up: _Why is inheritance useful in this context?_  
  expected: Inheritance allows us to create new classes that build upon existing ones without changing their original code.
- **Modifying existing code can lead to unexpected behavior.**  
  quote: "Never modify classes, interfaces, and other code units that already exist, as it can lead to unexpected behavior."  
  follow-up: _Why is it risky to modify existing code?_  
  expected: Modifying existing code can introduce bugs or break existing functionality that depends on it.

### [Interface segregation principle] Explain the Interface Segregation Principle (ISP) in your own words.
*confidence 0.96 · easy · slides [615, 616]*

**Reference:** The Interface Segregation Principle states that 'Make fine grained interfaces that are client-specific. Clients should not be forced to implement interfaces they do not use.' This means that instead of having one large interface with many methods, we should create smaller, more specific interfaces that better match the needs of the clients. This helps avoid forcing classes to implement methods they don’t need, leading to more flexible and maintainable designs.

**Key points** (slide quote → follow-up → expected answer):
- **ISP encourages the use of many small, client-specific interfaces rather than one large interface.**  
  quote: "Make fine grained interfaces that are client-specific."  
  follow-up: _What happens if you have a single interface with many methods that not all classes need?_  
  expected: Clients would be forced to implement methods they don’t use, leading to unnecessary complexity and potential misuse.
- **Clients should not be forced to implement methods they don’t use.**  
  quote: "Clients should not be forced to implement a function they do not need."  
  follow-up: _Why is it important to avoid forcing clients to implement unused methods?_  
  expected: It improves design flexibility and reduces the risk of incorrect or incomplete implementations.
- **ISP helps avoid bloated interfaces with unnecessary methods.**  
  quote: "Interface should not be bloated with methods that implementing classes don’t require."  
  follow-up: _What is the consequence of having a fat interface?_  
  expected: Implementing classes may have to define methods they don’t need, leading to unnecessary dependencies and potential errors.

### [Singleton pattern] Explain how the Singleton pattern ensures that only one instance of a class is created in Java.
*confidence 0.96 · easy · slides [688, 689, 708, 712, 713, 714]*

**Reference:** The Singleton pattern ensures that only one instance of a class is created by making the constructor private and providing a static method to access the instance. This method either creates the instance on first use or returns the existing one. The pattern also prevents external instantiation by restricting access to the constructor.

**Key points** (slide quote → follow-up → expected answer):
- **The Singleton pattern ensures that only one instance of a class is created.**  
  quote: "The singleton pattern is a design pattern that restricts the instantiation of a class to one object."  
  follow-up: _Why would you want to restrict instantiation to one object?_  
  expected: To ensure a global point of access and control over the object's lifecycle, which is useful for resources like configuration or database connections.
- **The constructor is made private to prevent external instantiation.**  
  quote: "Make the constructor of the class private. The static method of the class will still be able to call the constructor, but not the other objects."  
  follow-up: _What would happen if the constructor was not private?_  
  expected: Other classes could instantiate the Singleton class directly, violating the pattern's goal of having a single instance.
- **A static method provides a global access point to the instance.**  
  quote: "A Singleton class also provides one unique global access point to the object so that each subsequent call to the access point returns only that particular object."  
  follow-up: _Why is having a global access point important?_  
  expected: It ensures that all parts of the application access the same instance, maintaining consistency and shared state across the system.

### [Builder pattern] Explain what the Builder pattern is, and why it is useful in object-oriented design.
*confidence 0.96 · easy · slides [757, 758]*

**Reference:** The Builder pattern is a creational design pattern that deals with the construction of complex objects. It separates the instantiation process from the object's representation, allowing for the creation of different representations of the same object. This pattern is useful because it simplifies the creation of complex objects by encapsulating the construction process in a separate builder object, making the code more readable and maintainable.

**Key points** (slide quote → follow-up → expected answer):
- **The Builder pattern is a creational design pattern that deals with the construction of complex objects.**  
  quote: "The Builder Design Pattern is another creational pattern designed to deal with the construction of comparatively complex objects."  
  follow-up: _What is the main purpose of the Builder pattern?_  
  expected: The main purpose is to deal with the construction of complex objects by separating the instantiation process from the object's representation.
- **The Builder pattern separates the instantiation process from the object's representation.**  
  quote: "The Builder pattern can separate out the instantiation process by using another object (a builder) to construct the object."  
  follow-up: _Why would you want to separate the instantiation process from the object's representation?_  
  expected: Separating the process makes the code more readable, maintainable, and allows for different representations of the same object to be created easily.
- **The Builder pattern allows for the creation of different representations of the same object.**  
  quote: "A class (the same construction process) can delegate to different Builder objects to create different representations of a complex object."  
  follow-up: _How does the Builder pattern support creating different representations of an object?_  
  expected: By delegating the construction process to different Builder objects, the same class can create various representations of a complex object.

### [Command pattern] Can you explain what the Command pattern is and how it works, based on what you've learned?
*confidence 0.96 · easy · slides [927]*

**Reference:** The Command pattern wraps a request into an object, allowing the request to be passed around and executed independently. This pattern is data-driven and falls under behavioral patterns. The invoker object is responsible for finding the appropriate command object to handle the request and execute it. The command object contains all the information needed to perform the action, such as the method name, owner, and arguments.

**Key points** (slide quote → follow-up → expected answer):
- **The Command pattern wraps a request into an object.**  
  quote: "A request is wrapped under an object as command and passed to an invoker object."  
  follow-up: _What is the purpose of wrapping a request into an object?_  
  expected: Wrapping a request into an object allows the request to be passed around and executed independently, which supports flexibility and decoupling in the system.
- **The Command pattern is data-driven and falls under behavioral patterns.**  
  quote: "Command pattern is a data-driven design pattern and falls under behavioral patterns."  
  follow-up: _Why is the Command pattern considered data-driven?_  
  expected: The Command pattern is data-driven because it encapsulates the request as an object, making the data (the command) the central part of the interaction.
- **The command object contains all the information needed to perform the action.**  
  quote: "The object, called Command, contains all the information needed to perform an action or trigger an event, such as the method name, the method owner, and the arguments for method parameters."  
  follow-up: _What kind of information does the command object hold?_  
  expected: The command object holds the method name, the method owner, and the arguments for method parameters, which are all necessary to perform the action.

### [Java collections and List interface] Explain what makes the List interface in Java different from other collection interfaces like Set.
*confidence 0.96 · easy · slides [435, 462]*

**Reference:** The List interface in Java maintains an ordered collection of elements, which means the position of each element is significant. Unlike Set, which does not allow duplicate elements, List allows duplicates. Additionally, List provides index-based methods for inserting, updating, deleting, and searching elements, which are not available in Set.

**Key points** (slide quote → follow-up → expected answer):
- **List maintains an ordered collection of elements.**  
  quote: "List in Java provides the facility to maintain the ordered collection."  
  follow-up: _Can you give an example of when the order of elements matters in a collection?_  
  expected: In a list of tasks, the order determines the sequence in which tasks are executed.
- **List allows duplicate elements.**  
  quote: "It can have the duplicate elements also."  
  follow-up: _What would happen if you tried to add the same element twice to a Set?_  
  expected: The Set would only store one instance of the element, as duplicates are not allowed.
- **List provides index-based operations.**  
  quote: "It contains the index based methods to insert, update, delete and search the elements."  
  follow-up: _What kind of operations would you use if you needed to access elements by their position?_  
  expected: You would use methods like get(int index), set(int index, E element), or remove(int index).

### [Creator (GRASP)] Explain the Creator pattern in GRASP and why it is important for object design.
*confidence 0.96 · easy · slides [492, 493, 494, 495, 496, 497]*

**Reference:** The Creator pattern in GRASP assigns the responsibility of creating instances of a class to the class that has the most knowledge about when and how to create them. This ensures that object creation is encapsulated and promotes loose coupling. By delegating object creation to the appropriate class, we avoid tight coupling between classes and make the system more maintainable and flexible.

**Key points** (slide quote → follow-up → expected answer):
- **The Creator pattern assigns the responsibility of creating instances of a class to the class that has the most knowledge about when and how to create them.**  
  quote: "Assign the responsibility of creating instances of a class to the class that has the most knowledge about when and how to create them"  
  follow-up: _Why would a class have more knowledge about creating another class?_  
  expected: Because it has the most interaction or association with the object being created, which makes it the best candidate for knowing when and how to create it.
- **The Creator pattern promotes loose coupling by decoupling object creation logic from the classes that use the created objects.**  
  quote: "Promote Loose Coupling: Aim to minimize dependencies between classes by decoupping object creation logic from the classes that use the created objects."  
  follow-up: _How does decoupling object creation logic help in object design?_  
  expected: It reduces dependencies between classes, making the system more modular and easier to maintain and extend.
- **The Creator pattern ensures that object creation is encapsulated within the responsible class.**  
  quote: "Encapsulate Initialization Logic: Ensure that the classes responsible for creating objects encapsulate the initialization logic within them."  
  follow-up: _What is the benefit of encapsulating initialization logic?_  
  expected: It hides the details of object creation from other classes, making the system more robust and easier to manage.

### [Static members] Explain what a static block is and when it is executed in Java.
*confidence 0.96 · easy · slides [370]*

**Reference:** A static block in Java is used to initialize static data members. It is executed before the main method at the time of class loading. The static block runs exactly once when the class is first loaded, ensuring that static initialization happens early in the program lifecycle.

**Key points** (slide quote → follow-up → expected answer):
- **A static block is used to initialize static data members.**  
  quote: "Java static block Is used to initialize the static data member."  
  follow-up: _What happens if you try to initialize a static variable without a static block?_  
  expected: The variable can still be initialized directly in the class declaration, but a static block provides more complex initialization logic.
- **A static block is executed before the main method.**  
  quote: "It is executed before the main method at the time of class loading."  
  follow-up: _Can a static block be used to perform actions that depend on other classes not yet loaded?_  
  expected: No, because the static block runs when the class is first loaded, and other classes may not be available at that time.
- **A static block is executed exactly once.**  
  quote: "Static block gets executed exactly once, when the class is first loaded."  
  follow-up: _What would happen if you create multiple instances of the class?_  
  expected: The static block would still execute only once, regardless of how many instances are created.

### [Method overriding] Can you explain what method overriding is and why it's useful in object-oriented programming?
*confidence 0.96 · easy · slides [391, 392]*

**Reference:** Method overriding is when a subclass provides a specific implementation of a method that is already declared in its parent class. This allows the subclass to redefine the behavior of the method, which is useful for runtime polymorphism. It enables objects of different classes to be treated as objects of a common superclass, while still allowing for specialized behavior.

**Key points** (slide quote → follow-up → expected answer):
- **Method overriding is when a subclass provides a specific implementation of a method that is already declared in its parent class.**  
  quote: "If a subclass provides the specific implementation of the method which has been declared by one of its parent class, it is known as method overriding."  
  follow-up: _What happens if a subclass defines a method with the same name but different parameters as its parent?_  
  expected: That would not be method overriding, it would be method overloading, which is a different concept.
- **Method overriding is used for runtime polymorphism.**  
  quote: "Method overriding is used for runtime polymorphism."  
  follow-up: _Why is runtime polymorphism important in object-oriented programming?_  
  expected: Runtime polymorphism allows a single method call to behave differently based on the object it is acting upon, making programs more flexible and reusable.
- **Method overriding requires an IS-A relationship (inheritance).**  
  quote: "There must be an IS-A relationship (inheritance)."  
  follow-up: _Can a class override a method from a class it does not inherit from?_  
  expected: No, method overriding can only occur between a superclass and a subclass, which requires an inheritance relationship.

### [Association] Explain what an association is in object-oriented modeling, and how it differs between unidirectional and bidirectional associations.
*confidence 0.96 · easy · slides [88, 89, 90, 91, 92, 93]*

**Reference:** An association denotes a link between two classes in a model that need to communicate. In a unidirectional association, only one class 'knows' about the relationship, and it is represented by a solid line with an open arrowhead pointing to the known class. In contrast, a bidirectional association means both classes are aware of the relationship, and it is represented by a solid line without an arrowhead, or with an arrowhead on both ends.

**Key points** (slide quote → follow-up → expected answer):
- **An association denotes a link between two classes in a model that need to communicate.**  
  quote: "If two classes in a model need to communicate with each other, there must be link between them. An association denotes that link."  
  follow-up: _What happens if two classes need to communicate but there is no association between them?_  
  expected: They cannot effectively communicate, as there is no defined link or relationship in the model.
- **In a unidirectional association, only one class 'knows' about the relationship.**  
  quote: "In a unidirectional association, two classes are related, but only one class 'knows' that the relationship exists."  
  follow-up: _Can a unidirectional association have a multiplicity defined for both classes?_  
  expected: No, multiplicity is only defined for the known class in a unidirectional association.
- **A bidirectional association means both classes are aware of the relationship.**  
  quote: "We can specify dual associations using bidirectional association. Two objects might store each other in fields."  
  follow-up: _How is a bidirectional association represented in a diagram?_  
  expected: It is represented by a solid line without an arrowhead, or with an arrowhead on both ends, indicating mutual awareness.

### [Facade and proxy patterns] Explain what the Proxy Design Pattern is and one of its main purposes.
*confidence 0.96 · easy · slides [847, 848, 849, 855, 856]*

**Reference:** The Proxy Design Pattern is a pattern where a proxy object provides a surrogate or placeholder for another object to control access to it. One of its main purposes is to allow a class to represent the functionality of another class, enabling controlled access to the original object.

**Key points** (slide quote → follow-up → expected answer):
- **The proxy object acts as a surrogate or placeholder for another object.**  
  quote: "A proxy object provide a surrogate or placeholder for another object to control access to it."  
  follow-up: _What is the role of the proxy in relation to the original object?_  
  expected: The proxy controls access to the original object, allowing actions to be performed before or after the request gets through to the original object.
- **The proxy controls access to the original object.**  
  quote: "A proxy controls access to the original object, allowing you to perform something either before or after the request gets through to the original object."  
  follow-up: _Why would you want to control access to the original object?_  
  expected: To implement features like lazy loading, access control, or to add additional behavior without modifying the original object.
- **The proxy allows a class to represent the functionality of another class.**  
  quote: "Using the proxy pattern, a class represents the functionality of another class."  
  follow-up: _How does this help in software design?_  
  expected: It allows for abstraction and decoupling, making the system more flexible and easier to maintain.

### [Low-level design approach] Explain what low-level design approach is in object-oriented analysis and design.
*confidence 0.95 · easy · slides [4, 75, 451, 452, 453]*

**Reference:** Low-level design approach is the stage in object-oriented analysis and design where class designers add details to the analysis model in accordance with the system design strategy. The focus is on the data structures and algorithms needed to implement each class. This stage translates the logical solution into a concrete representation in a programming language, ensuring that the design remains flexible and extensible.

**Key points** (slide quote → follow-up → expected answer):
- **Low-level design is the stage where class designers add details to the analysis model.**  
  quote: "The class designer adds details to the analysis model in accordance with the system design strategy."  
  follow-up: _What is the purpose of adding details to the analysis model in this stage?_  
  expected: The purpose is to translate the logical solution into a concrete representation in a programming language, ensuring that the design remains flexible and extensible.
- **Low-level design focuses on data structures and algorithms needed to implement each class.**  
  quote: "The focus of class design is the data structures and algorithms needed to implement each class."  
  follow-up: _What is the main focus of the low-level design stage?_  
  expected: The main focus is on the data structures and algorithms needed to implement each class.
- **Low-level design ensures that the system remains flexible and extensible.**  
  quote: "During implementation, it is important to follow good software engineering practice so that traceability to the design is apparent and so that the system remains flexible and extensible."  
  follow-up: _Why is flexibility and extensibility important in low-level design?_  
  expected: Flexibility and extensibility are important to ensure that the system can adapt to future changes and requirements without requiring a complete redesign.

### [Object memory allocation] Explain what it means for an object to have its own memory in Java.
*confidence 0.95 · easy · slides [296]*

**Reference:** In Java, when an object is created using the new keyword, it has its own memory. This means that each object instance is allocated a separate memory space. This allows multiple objects to be created from the same class, each with their own set of instance variables. The object can access class attributes and methods using the dot operator, which works because each object has its own memory to store its state.

**Key points** (slide quote → follow-up → expected answer):
- **Each object has its own memory space.**  
  quote: "Java Object : Key Characteristics
  Created using new keyword Has its own memory..."  
  follow-up: _Why do you think multiple objects can be created from one class?_  
  expected: Because each object has its own memory, they can coexist without interfering with each other's data.
- **Objects are created using the new keyword.**  
  quote: "Java Object : Key Characteristics
  Created using new keyword Has its own memory..."  
  follow-up: _What would happen if you didn't use the new keyword to create an object?_  
  expected: You would not get a new object with its own memory; instead, you would get a reference to an existing object or a null reference.
- **Objects can access class attributes and methods using the dot operator.**  
  quote: "Java Object : Key Characteristics
  Created using new keyword Has its own memory Can access class attributes and methods using dot operator..."  
  follow-up: _How does the dot operator relate to memory in an object?_  
  expected: The dot operator allows the object to access its own memory space, where instance variables and methods are stored.

### [Information Expert] Explain how the Information Expert principle helps in assigning responsibilities to objects in object-oriented design.
*confidence 0.95 · medium · slides [500, 501]*

**Reference:** The Information Expert principle assigns responsibilities to the class that has the information needed to fulfill them. This ensures that objects do things related to the information they have. When information is spread across multiple classes, objects interact via messages to fulfill responsibilities. The principle does not mean that having information guarantees responsibility, but it guides the selection of the most appropriate class. It also supports collaboration when no single class has all the necessary information.

**Key points** (slide quote → follow-up → expected answer):
- **Assign a responsibility to the class that has the information needed to fulfill it.**  
  quote: "Assign a responsibility to the class that has the information needed to respond to it."  
  follow-up: _What if an object doesn't have the information needed to perform a task?_  
  expected: Then the responsibility should be assigned to another object that has the required information, or the objects should collaborate to fulfill the responsibility.
- **Objects do things related to the information they have.**  
  quote: "objects do things related to the information they have"  
  follow-up: _Why is it important for objects to act on the information they hold?_  
  expected: Because it aligns responsibilities with the data an object is designed to manage, leading to more coherent and maintainable designs.
- **Information may be spread across several classes, requiring interaction.**  
  quote: "Information necessary may be spread across several classes => objects interact via messages"  
  follow-up: _How does the Information Expert principle handle situations where information is distributed?_  
  expected: It encourages interaction between objects through messages, ensuring that each object contributes what it can based on its own information.
- **Having information does not guarantee responsibility.**  
  quote: "Just because an object has information necessary doesn’t mean it will have responsibility for action related to the information"  
  follow-up: _Can an object have information but not be responsible for an action?_  
  expected: Yes, because responsibility is determined by the need to act on the information, not just by possessing it.

### [Encapsulation] Explain how encapsulation supports data hiding and why it is important for software design.
*confidence 0.91 · medium · slides [272, 273, 274]*

**Reference:** Encapsulation supports data hiding by wrapping data and functions into a single unit, making the data inaccessible to the outside world. This insulation of data from direct access is called data hiding or information hiding. It is important for software design because it restricts access to data members, preventing unintended modification and ensuring that the internal implementation details are protected. This also allows for greater flexibility in changing the implementation without affecting the external interface.

**Key points** (slide quote → follow-up → expected answer):
- **Encapsulation wraps data and functions into a single unit.**  
  quote: "The wrapping up of data and functions into a single unit is known as encapsulation."  
  follow-up: _What is the purpose of grouping data and functions together in this way?_  
  expected: The purpose is to create a self-contained unit that manages its own data and behavior, which supports data hiding and improves system design.
- **Data is not accessible to the outside world.**  
  quote: "The data is not accessible to the outside world, only those functions which are wrapped in can access it."  
  follow-up: _Why would you want to prevent external access to data?_  
  expected: To protect the internal state of an object and prevent unintended modification, which helps maintain data integrity and security.
- **Encapsulation supports data hiding through insulation of data.**  
  quote: "This insulation of the data from direct access by the program is called data hiding or information hiding."  
  follow-up: _How does data hiding benefit the overall design of a system?_  
  expected: Data hiding improves flexibility and maintainability by allowing changes to the internal implementation without affecting the external interface, which makes the system more robust and easier to manage.

### [Interfaces] How do interfaces in Java support multiple inheritance, and what is the difference between a provided interface and a required interface?
*confidence 0.91 · medium · slides [121, 309, 314, 420, 421, 424]*

**Reference:** Interfaces in Java support multiple inheritance by allowing a class to implement multiple interfaces, which enables a class to inherit behavior from multiple sources. A provided interface is implemented by a class, meaning the class provides the implementation for the interface's methods. A required interface is used by a component, such as when a method parameter expects an interface type, indicating that the component requires the interface's behavior without implementing it.

**Key points** (slide quote → follow-up → expected answer):
- **Interfaces enable multiple inheritance in Java.**  
  quote: "It is used to achieve 100% abstraction and multiple inheritance in Java."  
  follow-up: _Can a class inherit behavior from more than one class in Java?_  
  expected: No, Java does not support multiple inheritance for classes, but interfaces allow a class to implement multiple interfaces, effectively achieving multiple inheritance through interfaces.
- **A provided interface is implemented by a class.**  
  quote: "On the implementation level a provided interface is the interface implemented by a class (in the most common sense, e.g. a class B implements the interface"  
  follow-up: _What does it mean for a class to provide an interface?_  
  expected: It means the class implements the interface's methods, providing the actual behavior that the interface defines.
- **A required interface is used by a component.**  
  quote: "Required interface would be any use of an interface by a component (e.g. if a class A defines a method that has the interface I as a parameter, this means that class A has a required interface I)."  
  follow-up: _Why would a class need a required interface?_  
  expected: A class needs a required interface to interact with other components that expect a specific behavior, without needing to implement the interface itself.

### [Abstract class vs interface] Explain the difference between an abstract class and an interface in terms of their use for abstraction and inheritance.
*confidence 0.91 · medium · slides [314, 420, 421, 424]*

**Reference:** An abstract class provides partial abstraction by allowing both abstract and concrete methods, while an interface provides full abstraction by only containing abstract methods (and later, default/static methods). An abstract class can be inherited by a class, but a class can only implement multiple interfaces. This makes interfaces more flexible for defining behavior that can be shared across unrelated classes.

**Key points** (slide quote → follow-up → expected answer):
- **Abstract classes can have both abstract and concrete methods, while interfaces (before Java 8) only had abstract methods.**  
  quote: "Methods Can have abstract + concrete By default abstract methods (can have methods default & static methods from Java 8)"  
  follow-up: _Can an interface have implementation for its methods?_  
  expected: No, interfaces (before Java 8) could only declare methods without implementation. From Java 8, they can have default and static methods with implementation.
- **An interface represents what an object can do, while a class represents what an object is.**  
  quote: "Purpose Represents what an object is Represents what an object can do"  
  follow-up: _What is the main purpose of an interface in object-oriented design?_  
  expected: The main purpose of an interface is to define a contract for what a class can do, without specifying how it does it.
- **A class can implement multiple interfaces, but cannot extend multiple classes.**  
  quote: "Multiple Not supported (for classes) A class can implement multiple"  
  follow-up: _Why would you prefer using interfaces over abstract classes in some cases?_  
  expected: Because interfaces allow for multiple inheritance of type, enabling a class to adopt multiple behaviors from different sources.

### [Types of inheritance] Explain how hybrid inheritance combines different types of inheritance and why Java uses interfaces to support it.
*confidence 0.91 · medium · slides [383, 384, 389]*

**Reference:** Hybrid inheritance combines two or more types of inheritance, such as hierarchical and multiple inheritance. Java does not support multiple inheritance via classes, so it uses interfaces to achieve hybrid structures. This allows for more flexible and complex class hierarchies while avoiding the limitations of class-based multiple inheritance.

**Key points** (slide quote → follow-up → expected answer):
- **Hybrid inheritance combines two or more types of inheritance.**  
  quote: "Two or more types of inheritance—such as single, multiple, multilevel, or hierarchical—are combined to create a complex class hierarchy"  
  follow-up: _Why would you need more than one type of inheritance in a class hierarchy?_  
  expected: To model complex relationships between classes, such as when a class needs to inherit from multiple parents or build upon multiple levels of inheritance.
- **Hybrid inheritance typically merges hierarchical and multiple inheritance.**  
  quote: "It typically merges patterns like hierarchical and multiple inheritance or single and multilevel inheritance."  
  follow-up: _What is the difference between hierarchical and multiple inheritance?_  
  expected: Hierarchical inheritance involves one parent class with multiple child classes, while multiple inheritance involves a child class inheriting from multiple parent classes.
- **Java uses interfaces to support hybrid inheritance.**  
  quote: "Java does not support multiple inheritance via classes; must use interfaces to achieve hybrid structures."  
  follow-up: _Why can't Java support multiple inheritance via classes?_  
  expected: Because multiple inheritance via classes can lead to ambiguity in method resolution, which Java avoids by using interfaces instead.

### [Method overloading] Explain how method overloading allows a class to have multiple methods with the same name but different behaviors, and why this is considered compile-time polymorphism.
*confidence 0.91 · medium · slides [354, 355, 356, 357]*

**Reference:** Method overloading allows a class to have multiple methods with the same name but different parameter lists, enabling the same method name to perform different actions based on the input. This is considered compile-time polymorphism because the compiler determines which method to call based on the method signature at compile time, not at runtime. The key is that the method name remains the same, but the parameter list differs in number, type, or order, allowing flexibility in method invocation.

**Key points** (slide quote → follow-up → expected answer):
- **Method overloading allows a class to have more than one method with the same name if their argument lists are different.**  
  quote: "A feature that allows a class to have more than one method having the same name, if their argument lists are different."  
  follow-up: _Can you give an example of how two methods with the same name can behave differently?_  
  expected: Yes, for example, a method `add(int a, int b)` and a method `add(double a, double b)` can both be named `add`, but they perform addition on different data types.
- **The compiler decides which method to call based on the method signature at compile time.**  
  quote: "Compiler decides which method to call (compile-time polymorphism) based on the method signature : method name + parameter list (number, type, order)"  
  follow-up: _Why is the decision made at compile time rather than runtime?_  
  expected: Because the method signature is known at compile time, allowing the compiler to resolve the correct method to call without needing to inspect the actual runtime arguments.
- **Method overloading is considered compile-time polymorphism or static polymorphism.**  
  quote: "Method overloading is also known - Compile Time polymorphism, Static polymorphism , Early Binding."  
  follow-up: _What does 'early binding' mean in this context?_  
  expected: Early binding means that the method to be called is determined at compile time, which improves performance and allows for more predictable execution.

### [Constructors] How does the use of a parameterized constructor differ from a default constructor in Java, and what are the implications for object initialization?
*confidence 0.91 · medium · slides [324, 325, 326, 329, 390, 766]*

**Reference:** A parameterized constructor allows you to pass arguments to initialize an object's instance variables with specific values, while a default constructor provides default values. The parameterized constructor is used when you want to set initial values during object creation, whereas the default constructor is used when no specific values are needed. When you define a parameterized constructor, the default constructor is no longer available, which means you must explicitly define it if needed. This affects how objects are initialized and can influence design decisions when multiple initialization scenarios are required.

**Key points** (slide quote → follow-up → expected answer):
- **A parameterized constructor allows you to pass arguments to initialize an object's instance variables with specific values.**  
  quote: "Parameterized constructor: A constructor with parameters. To initialize the fields of a object with given values"  
  follow-up: _What happens if you don't use a parameterized constructor and instead rely on the default constructor?_  
  expected: The default constructor provides default values to the object's instance variables, such as 0, false, or null, depending on the data type.
- **The default constructor provides default values to the object's instance variables.**  
  quote: "Default constructor provides default values to the objects like 0, false, null etc depending on the data type of the instance variables."  
  follow-up: _What is the impact of defining a parameterized constructor on the availability of the default constructor?_  
  expected: Once you define a parameterized constructor, the default constructor is no longer added, so you must define it explicitly if needed.
- **Defining a parameterized constructor affects the availability of the default constructor.**  
  quote: "Once you define your own constructor, the default constructor is no longer added."  
  follow-up: _Why would you choose a parameterized constructor over a default constructor in a real-world scenario?_  
  expected: You would choose a parameterized constructor when you need to initialize an object with specific values, ensuring that the object is in a valid state upon creation.

### [this and super keywords] Explain how the 'super' keyword is used in constructors and why it must be the first statement in a constructor.
*confidence 0.91 · medium · slides [390]*

**Reference:** The 'super' keyword is used to explicitly call the constructor of the superclass. It must be the first statement in a constructor because the superclass must be fully initialized before the subclass can proceed with its own construction. When the object of a subclass is created, the constructor of the subclass by default invokes the default constructor of the superclass, but this can be explicitly called using 'super'.

**Key points** (slide quote → follow-up → expected answer):
- **The 'super' keyword is used to explicitly call the superclass constructor.**  
  quote: "The superclass constructor can be called explicitly using the super keyword, but it should be first statement in a constructor."  
  follow-up: _What happens if you try to call 'super' after another statement in the constructor?_  
  expected: The code will not compile because 'super' must be the first statement in a constructor.
- **'super' must be the first statement in a constructor because the superclass must be initialized first.**  
  quote: "When the object of subclass is created, constructor of sub class by default invokes the default constructor of super class . Hence, in inheritance the objects are constructed top-down."  
  follow-up: _Why is it important for the superclass to be initialized before the subclass?_  
  expected: Because the superclass contains the foundational state and behavior that the subclass relies on, so it must be fully initialized before the subclass can proceed.
- **The 'super' keyword refers to the superclass immediately above the calling class in the hierarchy.**  
  quote: "The super keyword refers to the superclass, immediately above of the calling class in the hierarchy."  
  follow-up: _What would happen if a subclass had two superclasses and you called 'super' in its constructor?_  
  expected: It would call the constructor of the immediate superclass, which is the one directly above the subclass in the inheritance hierarchy.

### [Composition over inheritance] Explain how composition differs from inheritance in terms of how they model relationships between objects, and why composition is often preferred in object-oriented design.
*confidence 0.91 · medium · slides [276, 277, 278, 279, 686, 687]*

**Reference:** Composition models a 'has-a' relationship, where one object contains another, while inheritance models an 'is-a' relationship. Composition allows for greater flexibility and reusability, as it enables dynamic behavior changes at runtime.

**Key points** (slide quote → follow-up → expected answer):
- **Composition models a 'has-a' relationship.**  
  quote: "The Composition represents a part-of relationship."  
  follow-up: _Can you give an example of a 'has-a' relationship in real-world objects?_  
  expected: A university has a list of colleges, which is a classic example of a 'has-a' relationship.
- **Composition allows for dynamic behavior changes at runtime.**  
  quote: "Composition allows us to dynamically change our program's behavior by changing the member objects at run time."  
  follow-up: _How does this flexibility compare to inheritance in terms of runtime behavior?_  
  expected: With inheritance, the behavior is fixed at compile time, whereas with composition, it can be altered dynamically.
- **Composition provides better test-ability.**  
  quote: "Composition provides better test-ability of a class."  
  follow-up: _Why might test-ability be an important factor in choosing composition over inheritance?_  
  expected: Better test-ability means that individual components can be tested in isolation, which simplifies debugging and maintenance.

### [Creator (GRASP)] In the context of the Creator pattern, how does the responsibility of object creation relate to the interactions between objects in a system?
*confidence 0.91 · medium · slides [492, 493, 494, 495, 496, 497]*

**Reference:** The Creator pattern assigns the responsibility of creating instances of a class to the class that has the most knowledge about when and how to create them. This ensures that the object creation aligns with the interactions between objects, as the creator is typically the one that understands the context in which the object is used. By delegating object creation to the appropriate class, the system maintains loose coupling and promotes encapsulation of initialization logic.

**Key points** (slide quote → follow-up → expected answer):
- **The responsibility of object creation is assigned to the class that has the most knowledge about when and how to create them.**  
  quote: "Assign the responsibility of creating instances of a class to the class that has the most knowledge about when and how to create them"  
  follow-up: _Why would a class have more knowledge about when to create an object than another?_  
  expected: Because that class is typically involved in the interactions that require the object, making it the most suitable for knowing when and how to create it.
- **Object creation should align with the interactions between objects in a system.**  
  quote: "Decide who can be creator based on the object's association and their interaction"  
  follow-up: _How does the association between objects influence who should create them?_  
  expected: The association indicates which class is more likely to know the context in which the object is used, thus making it the natural creator.
- **The Creator pattern promotes loose coupling by decoupling object creation from the classes that use the created objects.**  
  quote: "Promote Loose Coupling: Aim to minimize dependencies between classes by decoupling object creation logic from the classes that use the created objects"  
  follow-up: _How does assigning object creation to the right class help with coupling?_  
  expected: It reduces dependencies by ensuring that the creation logic is encapsulated within the responsible class, rather than being spread across multiple classes.

### [Controller (GRASP)] Explain how the Controller pattern in GRASP helps reduce coupling between GUI components and system operation classes.
*confidence 0.91 · medium · slides [492, 528, 529, 530, 543]*

**Reference:** The Controller pattern helps minimize the dependency between GUI components and system operation classes by acting as an intermediary. When a request comes from a UI layer object, the Controller determines which object should receive the message and delegates the work to it. This separation ensures that the GUI does not directly interact with the system operation classes, reducing tight coupling and improving maintainability.

**Key points** (slide quote → follow-up → expected answer):
- **The Controller pattern helps minimize the dependency between GUI components and system operation classes.**  
  quote: "Helps in minimizing the dependency between GUI components and the system operation classes"  
  follow-up: _What happens if the GUI components directly interact with the system operation classes?_  
  expected: It leads to tight coupling, making the system harder to maintain and less flexible.
- **The Controller acts as an intermediary between the UI and domain objects.**  
  quote: "Deals with how to delegate the request from the UI layer objects to domain layer objects."  
  follow-up: _Why is it important for the Controller to determine which object receives the message?_  
  expected: Because it ensures that the right object is responsible for handling the request, maintaining separation of concerns.
- **The Controller delegates work to other objects rather than performing it itself.**  
  quote: "Normally controller coordinates activity but delegates work to other objects rather than doing work itself"  
  follow-up: _What is the benefit of the Controller not performing work itself?_  
  expected: It keeps the Controller focused on coordination, allowing domain objects to handle business logic, which improves modularity and testability.

### [Single responsibility principle] Explain how the Single Responsibility Principle improves software design, using the example of the Order class and its responsibilities.
*confidence 0.91 · medium · slides [572, 644, 645]*

**Reference:** The Single Responsibility Principle improves software design by ensuring that each class has only one reason to change. In the example, the Order class was responsible for managing order details, processing payments, and sending notifications, which made it hard to maintain. By splitting these into separate classes like PaymentProcessor and NotificationService, the system becomes more modular, easier to test, and less coupled. This aligns with the principle that each class should have responsibility for only one part of the software’s functionality.

**Key points** (slide quote → follow-up → expected answer):
- **A class should have one, and only one, reason to change.**  
  quote: "A class should have one, and only one, reason to change - Robert C. Martin"  
  follow-up: _What happens if a class has multiple reasons to change?_  
  expected: The class becomes harder to maintain and more prone to errors, as changes in one area may inadvertently affect others.
- **Each class only does one thing.**  
  quote: "Each class only does one thing."  
  follow-up: _Why is it important for a class to do only one thing?_  
  expected: It makes the code more predictable, easier to understand, and reduces the risk of unintended side effects when changes are made.
- **Code becomes easier to test and maintain.**  
  quote: "Code becomes easier to test and maintain, it makes software easier to implement, and it helps to avoid unanticipated side-effects of future changes."  
  follow-up: _How does separating responsibilities help with testing?_  
  expected: It allows for focused unit tests on individual responsibilities, making it easier to isolate and verify functionality.

### [Open-closed principle] How does the Open-Closed Principle help in minimizing the risk of failure when adding new features to existing code?
*confidence 0.91 · medium · slides [601]*

**Reference:** The Open-Closed Principle helps in minimizing the risk of failure by encouraging the extension of existing code rather than modifying it. This is because modifying existing code can lead to unexpected behavior. By using OOP features like inheritance and interfaces, new features can be added without changing the existing code, which reduces the chance of introducing bugs.

**Key points** (slide quote → follow-up → expected answer):
- **Modifying existing code can lead to unexpected behavior.**  
  quote: "Never modify classes, interfaces, and other code units that already exist, as it can lead to unexpected behavior."  
  follow-up: _What is a potential consequence of changing existing code without considering its impact?_  
  expected: It can lead to unexpected behavior and introduce bugs in parts of the system that were previously working correctly.
- **New features should be added through extension, not modification.**  
  quote: "While adding a new feature extend the code rather than modifying it, so that the risk of failure is minimized."  
  follow-up: _Why is it better to extend code than to modify it when adding new features?_  
  expected: Extending code allows for new functionality without altering existing behavior, which reduces the risk of introducing errors.
- **OOP features like inheritance and interfaces support the principle.**  
  quote: "We should be able to extend the existing code using OOP features like inheritance via subclasses and interfaces."  
  follow-up: _How can inheritance help in following the Open-Closed Principle?_  
  expected: Inheritance allows new classes to extend existing ones, enabling new behavior without changing the original class.

### [Liskov substitution principle] Explain how the Liskov Substitution Principle applies to the `DeliveryService` interface and its implementations in the example provided.
*confidence 0.91 · medium · slides [586, 648, 649]*

**Reference:** The Liskov Substitution Principle ensures that a subclass like `DroneDelivery` should be able to replace its superclass `DeliveryPerson` without altering the correctness of the program. In the example, `DroneDelivery` implements the `DeliveryService` interface, which defines the `deliverOrder()` method. This avoids forcing `DroneDelivery` to inherit unnecessary methods like `assignVehicle()`, which it does not need. By using a common interface, the principle is upheld because both classes can be used interchangeably in any context that expects a `DeliveryService`.

**Key points** (slide quote → follow-up → expected answer):
- **Derived types must be completely substitutable for their base types.**  
  quote: "Derived types must be completely substitutable for their base types"  
  follow-up: _Why is it important for a subclass to be substitutable for its superclass?_  
  expected: It ensures that code using the superclass can work with the subclass without modification, maintaining the integrity of the program.
- **A child class should never change the characteristics of its parent class.**  
  quote: "A child class should never change the characteristics of its parent class"  
  follow-up: _What would happen if a subclass changed the behavior of a method from its parent class?_  
  expected: It would violate the Liskov Substitution Principle, as the subclass would not behave as expected in contexts that rely on the parent class's behavior.
- **Using a common interface avoids forcing inheritance.**  
  quote: "Use a common interface instead of forcing inheritance."  
  follow-up: _Why is using a common interface better than forcing inheritance in this case?_  
  expected: It allows for substitutability without requiring subclasses to inherit and implement unnecessary methods, which could lead to incorrect behavior.

### [Interface segregation principle] How does the Interface Segregation Principle help avoid unnecessary dependencies in client implementations?
*confidence 0.91 · medium · slides [615, 616]*

**Reference:** The Interface Segregation Principle helps avoid unnecessary dependencies by ensuring that clients are not forced to implement methods they do not use. This is because it encourages the creation of smaller, more specific interfaces tailored to individual clients. By breaking down a fat interface into leaner, role-based interfaces, the principle reduces the burden on implementing classes to define unused methods. This leads to more flexible and maintainable code. As a result, clients only depend on the methods they actually need, which improves design clarity and reduces potential errors.

**Key points** (slide quote → follow-up → expected answer):
- **Clients are not forced to implement methods they do not use.**  
  quote: "Clients should not be forced to implement a function they do not need."  
  follow-up: _What happens if a client is required to implement a method it doesn't use?_  
  expected: It creates unnecessary dependencies and may lead to code that is harder to maintain and more error-prone.
- **ISP encourages the creation of smaller, more specific interfaces.**  
  quote: "Make fine grained interfaces that are client-specific."  
  follow-up: _Why would you prefer a small, client-specific interface over a large general-purpose one?_  
  expected: Because a small interface is more focused and reduces the need for clients to implement unused methods, improving clarity and flexibility.
- **ISP reduces the burden on implementing classes to define unused methods.**  
  quote: "Failure to comply with this principle means that in our implementations we will have dependencies on methods that we do not need but that we are obliged to define."  
  follow-up: _What is the consequence of having to define methods you don't need?_  
  expected: It introduces unnecessary complexity and can lead to code that is harder to understand and maintain.

### [Dependency inversion principle] Explain how the Dependency Inversion Principle helps reduce coupling between high-level and low-level modules in the given example.
*confidence 0.91 · medium · slides [631, 652, 653, 654]*

**Reference:** The Dependency Inversion Principle helps reduce coupling by having high-level modules depend on abstractions rather than concrete implementations. In the example, the OrderService depends on the Database interface, not on specific databases like MySQL or MongoDB. This allows the OrderService to remain decoupled from the specific database implementation, making it easier to switch or extend the system without changing the high-level logic.

**Key points** (slide quote → follow-up → expected answer):
- **High-level modules should not depend on low-level modules, both should depend upon abstractions.**  
  quote: "High level modules should not depend on low level modules, both should depend upon abstractions."  
  follow-up: _Why would changing the database require changes to the OrderService if it's using an abstraction?_  
  expected: If the OrderService directly depended on MySQLDatabase, changing to MongoDB would require modifying the OrderService to use MongoDB, which violates the principle of depending on abstractions.
- **Abstractions should not depend upon details, details should depend upon abstractions.**  
  quote: "Abstractions should not depend upon details , details should depend upon abstractions."  
  follow-up: _How does the Database interface ensure that details like MySQL or MongoDB depend on abstractions?_  
  expected: The Database interface is an abstraction, and both MySQLDatabase and MongoDBDatabase implement it. This means the concrete classes depend on the abstraction, not the other way around.
- **The goal is to avoid tightly coupled code, as it easily breaks the application.**  
  quote: "The goal is to avoid tightly coupled code, as it easily breaks the application."  
  follow-up: _What would happen if the OrderService was tightly coupled to MySQLDatabase?_  
  expected: If the OrderService was tightly coupled to MySQLDatabase, switching to MongoDB would require significant changes to the OrderService, increasing the risk of breaking the application.

### [Singleton pattern] Compare the thread safety and performance characteristics of the eager instantiation and double-checked locking approaches for implementing the Singleton pattern in Java.
*confidence 0.91 · medium · slides [688, 689, 708, 712, 713, 714]*

**Reference:** The eager instantiation approach is thread-safe because the instance is created during class loading, but it may use more memory if the singleton is not immediately needed. The double-checked locking approach is more efficient as it avoids synchronization until the instance is actually needed, but it requires the use of the volatile keyword to ensure visibility of the instance across threads.

**Key points** (slide quote → follow-up → expected answer):
- **Eager instantiation is thread-safe because the instance is created during class loading.**  
  quote: "JVM executes static initializer when the class is loaded and hence this is guaranteed to be thread safe."  
  follow-up: _Why is eager instantiation considered thread-safe?_  
  expected: Because the JVM guarantees that the static initializer runs once and in a thread-safe manner when the class is loaded.
- **Double-checked locking reduces synchronization overhead by only synchronizing when the instance is null.**  
  quote: "This method drastically reduces the overhead of calling the synchronized method every time."  
  follow-up: _What is the benefit of synchronizing only when the instance is null?_  
  expected: It reduces the overhead of synchronization by only acquiring the lock when the instance has not yet been created.
- **Double-checked locking requires the use of the volatile keyword to ensure visibility of the instance across threads.**  
  quote: "We have declared the obj volatile which ensures that multiple threads offer the obj variable correctly when it is being initialized to Singleton instance."  
  follow-up: _Why is the volatile keyword necessary in double-checked locking?_  
  expected: The volatile keyword ensures that changes to the obj variable are visible to all threads, preventing issues with lazy initialization.

### [Facade and proxy patterns] How does the Proxy Design Pattern support the Open/Closed Principle, and what trade-off does it introduce in terms of system complexity?
*confidence 0.91 · medium · slides [847, 848, 849, 855, 856]*

**Reference:** The Proxy Design Pattern supports the Open/Closed Principle by allowing new proxies to be introduced without modifying existing service objects or clients. This means the system remains open for extension but closed for modification. However, it introduces a trade-off by adding an extra layer of indirection between the client and the real subject, which increases code complexity and may delay responses due to additional request forwarding.

**Key points** (slide quote → follow-up → expected answer):
- **The Proxy Design Pattern supports the Open/Closed Principle by allowing new proxies to be introduced without changing the service or clients.**  
  quote: "A few of the advantages of the Proxy Design Pattern are as follows: The proxy works even if the service object isn’t ready or is not available. Open/Closed Principle - new proxies can be introduced without changing the service or clients."  
  follow-up: _What happens if you need to add a new type of access control without changing existing code?_  
  expected: You can introduce a new protection proxy that implements the same interface, allowing you to extend the system without modifying existing classes.
- **The Proxy Design and its additional layer between client and real subject increases code complexity.**  
  quote: "The Proxy Design Pattern introduces an additional layer between the client and the Real Subject, this contributes to the code complexity."  
  follow-up: _How might this additional layer affect the maintainability of the system?_  
  expected: It may make the system harder to understand and maintain, as the client interacts with a proxy rather than the real object directly.
- **The Proxy Pattern may delay responses due to the additional request forwarding between client and real subject.**  
  quote: "The response from the service might get delayed. Additional request forwarding is introduced between the client and the Real Subject."  
  follow-up: _In what scenarios might this delay be considered a drawback?_  
  expected: In performance-critical systems, the added overhead of proxy calls could be a drawback, especially if the proxy is not optimized.

### [Command pattern] How does the Command pattern enable decoupling between the invoker and the receiver, and what role does the command object play in this?
*confidence 0.91 · medium · slides [927]*

**Reference:** The Command pattern enables decoupling by encapsulating a request into a command object, which separates the request from the object that invokes it. This allows the invoker to work with the command without knowing the receiver's details. The command object contains all the information needed to perform the action, including the method name, the method owner, and the arguments for method parameters, which ensures that the invoker does not need to be tightly coupled to the receiver.

**Key points** (slide quote → follow-up → expected answer):
- **The Command pattern encapsulates a request into a command object.**  
  quote: "A request is wrapped under an object as command and passed to an invoker object."  
  follow-up: _What happens if the invoker needs to execute a request without knowing the receiver?_  
  expected: The invoker can execute the command without knowing the receiver, because the command object contains all the necessary information to perform the action.
- **The command object contains all the information needed to perform the action.**  
  quote: "The object, called Command, contains all the information needed to perform an action or trigger an event, such as the method name, the method owner, and the arguments for method parameters."  
  follow-up: _Why is it important for the command object to contain the method owner?_  
  expected: It is important because the command object needs to know which object (receiver) to invoke the method on, ensuring the correct execution of the request.
- **The invoker does not need to be tightly coupled to the receiver.**  
  quote: "The Invoker then searches for the appropriate object to handle the Command and passes it to the corresponding object that can execute it."  
  follow-up: _How does this separation affect the flexibility of the system?_  
  expected: This separation allows the system to be more flexible, as new commands can be added without modifying the invoker or the receiver, supporting open/closed principle.

### [Chain of responsibility pattern] Explain how the Chain of Responsibility pattern allows for dynamic decision-making in handling requests, and why this is important for loose coupling.
*confidence 0.91 · medium · slides [896, 898]*

**Reference:** The Chain of Responsibility pattern allows for dynamic decision-making by letting the client decide at runtime which objects form the chain and the order in which they handle requests. This is important for loose coupling because it decouples the sender of a request from its receiver, allowing multiple objects to handle the request without the sender needing to know which one will ultimately do so.

**Key points** (slide quote → follow-up → expected answer):
- **The Chain of Responsibility pattern allows multiple objects to handle a request.**  
  quote: "The receiving objects are chained and pass the request along the chain until one of the objects handles it."  
  follow-up: _What happens if no object in the chain is able to handle the request?_  
  expected: The request may be unhandled, or the chain may be designed to have a default handler to address this.
- **The chain can be decided dynamically at runtime.**  
  quote: "The set of potential request handler objects and the order in which these objects form the chain can be decided dynamically at runtime by the client depending on the current state of the application."  
  follow-up: _Why would the client want to decide the chain at runtime rather than at compile time?_  
  expected: Because the application's state may change, and the appropriate handlers may vary depending on that state.
- **The pattern promotes loose coupling between the sender and the receiver.**  
  quote: "The Chain of Responsibility is intended to promote loose coupling between the sender of a request and its receiver by giving more than one object an opportunity to handle the request."  
  follow-up: _How does giving multiple objects an opportunity to handle the request contribute to loose coupling?_  
  expected: It allows the sender to remain unaware of which specific object will handle the request, reducing dependencies between components.

### [Method overriding] How does method overriding support runtime polymorphism, and what constraints must be met for this to occur?
*confidence 0.91 · medium · slides [391, 392]*

**Reference:** Method overriding supports runtime polymorphism by allowing a subclass to provide a specific implementation of a method that is already defined in its parent class. This enables the correct method to be called based on the actual object type at runtime, rather than the reference type. For this to occur, the method must have the same name and parameters as in the parent class, and there must be an IS-A relationship through inheritance.

**Key points** (slide quote → follow-up → expected answer):
- **Method overriding enables runtime polymorphism by allowing the correct method to be called based on the actual object type.**  
  quote: "Method overriding is used for runtime polymorphism."  
  follow-up: _What happens if a subclass defines a method with the same name but different parameters as its parent?_  
  expected: That would not be method overriding, but method overloading, which is a different concept and does not support runtime polymorphism.
- **The method must have the same name and parameters as in the parent class for overriding to occur.**  
  quote: "The method must have the same name as in the parent class. The method must have the same parameter as in the parent class."  
  follow-up: _Can a subclass override a method with a different return type?_  
  expected: No, the return type must be the same or a subtype (covariant return type), otherwise it would not be considered overriding.
- **An IS-A relationship (inheritance) is required for method overriding to occur.**  
  quote: "There must be an IS-A relationship (inheritance)."  
  follow-up: _What if a class implements an interface with a method that it does not inherit from a parent class?_  
  expected: That is not method overriding, but method implementation in an interface, which is a separate mechanism and does not involve inheritance.

### [Destructors and garbage collection] How does the Java garbage collector determine which objects are no longer needed, and what role does the `finalize()` method play in this process?
*confidence 0.91 · medium · slides [331, 332, 333, 337]*

**Reference:** The Java garbage collector identifies unreferenced objects by tracing references from active objects in memory. The `finalize()` method is called just prior to garbage collection, allowing for cleanup tasks before an object is destroyed. However, it is not guaranteed to execute, and its use is deprecated in Java 9 due to its unreliable behavior.

**Key points** (slide quote → follow-up → expected answer):
- **The garbage collector identifies unreferenced objects by tracing references from active objects.**  
  quote: "Garbage Collector is the program running in the background that looks into all the objects in the memory and find out objects that are not referenced by any part of the program."  
  follow-up: _What happens to an object that is no longer referenced by any part of the program?_  
  expected: It is identified as unreferenced and is eligible for garbage collection, meaning it may be deleted and its memory reclaimed.
- **The `finalize()` method is called just prior to garbage collection.**  
  quote: "Java run time calls this method whenever it is about to recycle an object of the class."  
  follow-up: _Why is the `finalize()` method called just before garbage collection?_  
  expected: To allow the object to perform any necessary cleanup tasks before it is destroyed, such as releasing resources or closing connections.
- **The `finalize()` method is not guaranteed to execute.**  
  quote: "Execution is not guaranteed."  
  follow-up: _What could cause the `finalize()` method to not be called?_  
  expected: If the garbage collector does not run, or if the object is not properly referenced, the `finalize()` method may not be invoked.

### [Association] How can an association be used to model a relationship where one class has multiple instances of another class, and what role does multiplicity play in this?
*confidence 0.91 · medium · slides [88, 89, 90, 91, 92, 93]*

**Reference:** An association can model a relationship where one class has multiple instances of another class by using multiplicity adornments on the association line. For example, a Student can have one or more Instructors, which is represented as '1..*'. Multiplicity indicates the number of possible instances of the class associated with a single instance of the other end, allowing the model to express how many objects of one class can be linked to a single object of another class.

**Key points** (slide quote → follow-up → expected answer):
- **Multiplicity indicates the number of possible instances of the class associated with a single instance of the other end.**  
  quote: "Multiplicity of an association is the number of possible instances of the class associated with a single instance of the other end."  
  follow-up: _Can you give an example of how multiplicity might be used in a real-world scenario?_  
  expected: Yes, for example, a Person can own any number of Books, which is modeled as 'owns: Book[ ]' where the multiplicity '*' indicates zero or more books.
- **An association can be used to model a relationship where one class has multiple instances of another class.**  
  quote: "An object might store another object in a field. For example, people own books, which might be modeled by an owns field in Person objects."  
  follow-up: _How does this differ from a one-to-one relationship?_  
  expected: In a one-to-one relationship, a single instance of one class is associated with exactly one instance of another class, whereas in this case, a single instance can be associated with multiple instances.
- **Multiplicity can be represented as a single number or a range of numbers.**  
  quote: "Multiplicities are single number or ranges of numbers."  
  follow-up: _What does a multiplicity of '1..*' mean in terms of the relationship between two classes?_  
  expected: It means that one instance of the class can be associated with one or more instances of the other class, but not zero.

### [Adapter pattern] Explain how the Adapter pattern enables incompatible classes to work together, and why it is considered a structural design pattern.
*confidence 0.91 · medium · slides [807, 808, 809, 816, 817]*

**Reference:** The Adapter pattern enables incompatible classes to work together by converting the interface of a class into another interface that a client wants. This is achieved by implementing the target interface and wrapping the adaptee's functionality. It is considered a structural design pattern because it focuses on how classes and objects are composed to form larger structures, rather than on algorithms or data flow.

**Key points** (slide quote → follow-up → expected answer):
- **The Adapter pattern allows two or more previously incompatible objects to interact.**  
  quote: "Adapter lets classes work together that couldn't otherwise because of incompatible interfaces."  
  follow-up: _What is the main purpose of the Adapter pattern in terms of class interaction?_  
  expected: The main purpose is to enable previously incompatible classes to work together by adapting their interfaces.
- **The Adapter pattern is a structural design pattern.**  
  quote: "The Adapter Pattern is also known as Wrapper. Adapter is a structural design pattern that"  
  follow-up: _Why is the Adapter pattern classified as a structural design pattern?_  
  expected: It is classified as a structural design pattern because it focuses on how classes and objects are composed to form larger structures.
- **The Adapter pattern provides the interface according to client requirements.**  
  quote: "Adapter Pattern says that 'convert the interface of a class into another interface that a client wants'."  
  follow-up: _How does the Adapter pattern ensure that the client's needs are met?_  
  expected: The Adapter pattern ensures that the client's needs are met by converting the interface of a class into one that matches the client's expected interface.

### [Inheritance] Explain how inheritance supports code reusability and what kind of relationship it represents in object-oriented design.
*confidence 0.91 · medium · slides [83, 378, 379]*

**Reference:** Inheritance allows a child class to inherit the properties and methods of a parent class, which supports code reusability by avoiding duplication. It represents an 'is a' relationship, meaning the child class is a specific type of the parent class. This relationship enables the child class to extend or specialize the functionality of the parent class without rewriting existing code.

**Key points** (slide quote → follow-up → expected answer):
- **Inheritance enables code reusability by allowing a child class to inherit features from a parent class.**  
  quote: "Acquiring the properties (data and methods) from one class to other classes enables reusability of code."  
  follow-up: _Can you give an example of how a child class might reuse code from a parent class?_  
  expected: A child class can reuse the attributes and methods of the parent class without needing to redefine them.
- **Inheritance represents an 'is a' relationship between a child class and a parent class.**  
  quote: "Inheritance represents IS-A relationship which is also known as a parent-child relationship"  
  follow-up: _What does it mean for a class to be a 'specific type' of another class?_  
  expected: It means that the child class inherits the general characteristics of the parent class and adds its own specific behavior.
- **Inheritance is also referred to as generalization in class diagrams.**  
  quote: "Generalization is also known as Inheritance."  
  follow-up: _How is inheritance represented in a class diagram?_  
  expected: In a class diagram, inheritance is shown as a line with a hollow triangle arrowhead pointing to the superclass.

### [Low-level design approach] How does the low-level design approach ensure that the system remains flexible and extensible, and what role does the analysis model play in this process?
*confidence 0.91 · medium · slides [4, 75, 451, 452, 453]*

**Reference:** This allows for the system to be modified or extended without requiring major rework. The analysis model provides a precise abstraction of what the system must do, which serves as a foundation for the low-level design. By aligning the implementation with the analysis model, the system can evolve while maintaining its core functionality. This alignment ensures that changes in requirements or new features can be incorporated without disrupting existing components.

**Key points** (slide quote → follow-up → expected answer):
- **Low-level design ensures flexibility and extensibility by focusing on data structures and algorithms.**  
  quote: "The focus of class design is the data structures and algorithms needed to implement each class."  
  follow-up: _Why is it important for the system to be flexible and extensible during implementation?_  
  expected: It is important because the system may need to evolve over time, and flexibility allows for changes without major rework.
- **The analysis model provides a foundation for the low-level design.**  
  quote: "The analysis model is a precise abstraction of what the desired system must do, not how it will be done."  
  follow-up: _How does the analysis model support the low-level design process?_  
  expected: The analysis model supports the low-level design by providing a clear understanding of the system's requirements, which guides the implementation of data structures and algorithms.
- **The system can evolve while maintaining its core functionality.**  
  quote: "During implementation, it is important to follow good software engineering practice so that traceability to the design is apparent and so that the system remains flexible and extensible."  
  follow-up: _What does traceability to the design mean in the context of low-level design?_  
  expected: Traceability to the design means that the implementation can be traced back to the original design decisions, ensuring that changes can be made while maintaining the system's integrity.

### [Java Object class] Explain how the `equals()` method in the `Object` class behaves by default, and why it's important to override it in subclasses.
*confidence 0.90 · medium · slides [402, 404, 405, 407, 434]*

**Reference:** By default, the `equals()` method in the `Object` class compares memory references, meaning it checks if two object references point to the same memory location. This behavior is the same as using the `==` operator. However, in most cases, especially when comparing objects based on their content rather than their identity, it's important to override the `equals()` method to provide a meaningful comparison. This ensures that objects are considered equal based on their actual data, not just their memory address.

**Key points** (slide quote → follow-up → expected answer):
- **The default `equals()` method compares memory references.**  
  quote: "public boolean equals(Object obj) Indicates whether some other object is "equal to" this one. Default Behavior: Compares memory reference (same as ==)."  
  follow-up: _What is the default behavior of the `equals()` method when comparing two objects?_  
  expected: The default behavior compares memory references, meaning it checks if two object references point to the same memory location.
- **The `equals()` method is part of the `Object` class, which is the root of the class hierarchy.**  
  quote: "Class Object is the root of the class hierarchy. Every class has Object as a superclass."  
  follow-up: _Why is it important for all classes to inherit the `equals()` method?_  
  expected: Because the `equals()` method is part of the `Object` class, which is the root of the class hierarchy, all classes inherit this method and can override it to define their own equality logic.
- **Overriding `equals()` is important for content-based comparison.**  
  quote: "Often overridden for content comparison."  
  follow-up: _Why would you want to override the `equals()` method in a subclass?_  
  expected: To provide a meaningful comparison based on the object's content rather than its memory address, which is the default behavior.

### [Builder pattern] Explain how the Builder pattern allows a class to delegate object creation to a builder, and why this is useful for creating different representations of a complex object.
*confidence 0.90 · medium · slides [757, 758]*

**Reference:** The Builder pattern allows a class to delegate object creation to a builder by encapsulating the construction process in a separate object. This means the class does not need to handle the complex logic of assembling parts. Instead, it can use different builders to create different representations of the same complex object, which simplifies the class and enhances flexibility.

**Key points** (slide quote → follow-up → expected answer):
- **The Builder pattern allows a class to delegate object creation to a builder.**  
  quote: "A class (the same construction process) can delegate to different Builder objects to create different representations of a complex object."  
  follow-up: _What would happen if the class handled the construction of the object directly?_  
  expected: The class would need to manage the complex logic of assembling parts, which could make it difficult to maintain and extend.
- **The Builder pattern encapsulates the construction process in a separate object.**  
  quote: "The Builder design pattern describes how to solve such problems: ❑Encapsulate creating and assembling the parts of a complex object in a separate Builder object."  
  follow-up: _Why is encapsulating the construction process in a separate object beneficial?_  
  expected: It separates the construction logic from the main class, making the system more modular and easier to maintain.
- **Using different builders allows for different representations of the same complex object.**  
  quote: "A class (the same construction process) can delegate to different Builder objects to create different representations of a complex object."  
  follow-up: _How does the Builder pattern support the creation of different representations?_  
  expected: By allowing different builders to implement the same interface, the same class can produce various representations of the object without changing its structure.

### [Parameter passing in Java] In Java, what is the difference between how primitive types and objects are passed as parameters, and what are the implications of this behavior?
*confidence 0.90 · medium · slides [343, 344]*

**Reference:** In Java, all parameters are passed by value. For primitive types, this means a copy of the value is made, and changes to the parameter do not affect the original value in the caller. For objects, a copy of the reference is passed, meaning the method can modify the object's state, but cannot change the reference itself to point to a different object. This distinction is important because it affects how data is manipulated and shared between methods.

**Key points** (slide quote → follow-up → expected answer):
- **In Java, all parameters are passed by value.**  
  quote: "Argument is copied to the parameter when some data has to be passed between methods / functions."  
  follow-up: _What happens if you pass an object to a method and then change the object's state inside that method?_  
  expected: The object's state will be modified because the method receives a copy of the reference, allowing it to alter the object's state.
- **Changes to primitive parameters do not affect the original value in the caller.**  
  quote: "Changes made to formal parameter do not get transmitted back to the caller."  
  follow-up: _If you pass a primitive type to a method and assign a new value to the parameter inside the method, what happens to the original variable?_  
  expected: The original variable in the caller remains unchanged because the method works with a copy of the value.
- **For objects, a copy of the reference is passed, not the object itself.**  
  quote: "creates a copy of v1"  
  follow-up: _Can a method that receives an object as a parameter change the reference that the caller holds?_  
  expected: No, the method cannot change the reference that the caller holds, but it can modify the object's state if it has access to the same instance.

### [Polymorphism] Explain how polymorphism allows objects of different classes to be treated as objects of a common superclass, and why this is important for software design.
*confidence 0.89 · medium · slides [284, 354, 355, 535, 536, 537]*

**Reference:** Polymorphism allows objects of different classes to be treated as objects of a common superclass, which is essential for writing flexible and reusable code. This is achieved through inclusion polymorphism, also known as subtyping, where derived classes can be used through base class references. This enables a single interface to work with objects of different types, allowing for dynamic method dispatch and making it easier to replace one implementation with another without changing the client code.

**Key points** (slide quote → follow-up → expected answer):
- **Polymorphism allows objects of different classes to be treated as objects of a common superclass.**  
  quote: "Inclusion Polymorphism, also called as Subtyping. Inclusion Polymorphism is the ability to use derived classes through base class references."  
  follow-up: _Can you give an example of how a base class reference can point to a derived class object?_  
  expected: In Java, a reference of type `Animal` can point to an object of type `Dog` or `Cat`, allowing the same interface to be used for different implementations.
- **Polymorphism enables a single interface to work with objects of different types.**  
  quote: "Polymorphism Problem: How to handle alternatives based on type. Pluggable software components -- how can you replace one server component with another without affecting the client?"  
  follow-up: _Why is it important for software design to have a single interface that works with multiple types?_  
  expected: It allows for greater flexibility and reusability of code. Clients can interact with different implementations through the same interface without needing to know the specific type of object they are working with.
- **Polymorphism supports dynamic method dispatch, which determines the method to call at runtime.**  
  quote: "In Java, runtime polymorphism is achieved through dynamic method dispatch. The method to be invoked is determined at runtime based on the actual object type, not the reference type."  
  follow-up: _How does dynamic method dispatch differ from static method binding?_  
  expected: Dynamic method dispatch determines the method to call at runtime based on the actual object type, whereas static method binding resolves the method at compile time based on the reference type.

### [Overloading vs overriding] Explain the difference between method overloading and method overriding, and why they are used in different scenarios.
*confidence 0.89 · medium · slides [354, 356, 382, 391, 392]*

**Reference:** Method overloading allows a class to have multiple methods with the same name but different parameters, enabling flexibility in calling the same method with different inputs. Method overriding, on the other hand, allows a subclass to provide a specific implementation of a method already defined in its parent class, supporting runtime polymorphism. These two concepts are used in different scenarios: overloading is used to enhance readability and reusability within a single class, while overriding is used to customize behavior in a hierarchy of classes.

**Key points** (slide quote → follow-up → expected answer):
- **Method overloading is a compile-time polymorphism, while method overriding is a runtime polymorphism.**  
  quote: "Method overloading is also known - Compile Time polymorphism, Static polymorphism , Early Binding."  
  follow-up: _Can you explain why method overriding is associated with runtime polymorphism?_  
  expected: Method overriding is associated with runtime polymorphism because the actual method to be executed is determined at runtime based on the object's type, not the reference type.
- **Method overloading differs based on the parameters, while method overriding requires the same method name and parameters.**  
  quote: "Three ways to overload : The argument lists of the methods must differ in either of these: Changing the number of parameters, Changing the data type of parameters, Changing the order of parameters of methods."  
  follow-up: _What is required for two methods to be considered overloaded?_  
  expected: Two methods are considered overloaded if they have the same name but different argument lists, which can differ in number, data type, or order of parameters.
- **Method overriding is used for runtime polymorphism, while method overloading is used to enhance code readability and reusability.**  
  quote: "Method overriding is used for runtime polymorphism."  
  follow-up: _Why would you use method overloading instead of creating multiple methods with different names?_  
  expected: Method overloading is used to enhance code readability and reusability by allowing the same method name to be used with different parameter types, reducing the need for multiple method names.

### [IS-A vs HAS-A relationship] What is the difference between an 'is-a' relationship and a 'has-a' relationship in object-oriented design?
*confidence 0.88 · easy · slides [276, 277, 278, 279, 284]*

**Reference:** An 'is-a' relationship is implemented using inheritance and represents a type-of relationship, such as a 'Dog' being a type of 'Animal'. A 'has-a' relationship is implemented using composition and represents a part-of relationship, such as a 'University' having a 'College'. The 'is-a' relationship defines a hierarchy, while the 'has-a' relationship defines containment and dependency.

**Key points** (slide quote → follow-up → expected answer):
- **Inheritance is used to implement the 'is-a' relationship.**  
  quote: "The Inheritance is used to implement the 'is a' relationship."  
  follow-up: _Can you give an example of when you would use an 'is-a' relationship?_  
  expected: An example is when a class like 'Car' inherits from a class like 'Vehicle', indicating that a Car is a type of Vehicle.
- **Composition is used to implement the 'has-a' relationship.**  
  quote: "The Composition represents a part-of relationship."  
  follow-up: _What does it mean for one object to 'have-a' another object?_  
  expected: It means that one object contains another object as part of its structure, such as a 'House' having a 'Kitchen'.
- **The 'has-a' relationship allows for more flexible design and easier modification.**  
  quote: "Composition allows us to easily replace the composed class implementation with a better and improved version."  
  follow-up: _Why might a developer prefer composition over inheritance?_  
  expected: Because composition allows for more flexible and dynamic behavior, and it avoids the complexities and potential issues of deep inheritance hierarchies.

### [Abstraction vs encapsulation] What is the difference between abstraction and encapsulation in object-oriented programming?
*confidence 0.82 · easy · slides [9, 272, 273, 274, 283]*

**Reference:** Abstraction and encapsulation are both fundamental concepts in object-oriented programming, but they serve different purposes. Abstraction focuses on hiding complex implementation details and exposing only the necessary features of an object, as described by 'Provides higher-level abstraction by allowing the creation of abstract classes and interfaces.' Encapsulation, on the other hand, is about bundling data and methods into a single unit and restricting direct access to an object's internal state, as stated by 'The wrapping up of data and functions into a single unit is known as encapsulation.' While abstraction is about simplifying complexity, encapsulation is about controlling access to data.

**Key points** (slide quote → follow-up → expected answer):
- **Encapsulation bundles data and methods into a single unit.**  
  quote: "The wrapping up of data and functions into a single unit is known as encapsulation."  
  follow-up: _Why would you want to bundle data and methods together?_  
  expected: To control access to the data and provide a clear interface for interacting with the object.
- **Encapsulation restricts direct access to an object's internal state.**  
  quote: "The data is not accessible to the outside world, only those functions which are wrapped in can access it."  
  follow-up: _What is the benefit of not allowing direct access to data?_  
  expected: It protects the integrity of the data and allows for more flexible and secure design of the system.

### [Design pattern categories] What are the implications of grouping design patterns into the three categories—creational, structural, and behavioral—and how does this grouping affect the way we think about object-oriented design?
*confidence 0.82 · hard · slides [661] · ⚠ NEEDS REVIEW*

**Reference:** Grouping design patterns into these three categories helps us understand the primary focus of each pattern. Structural patterns deal primarily with the static composition and structure of classes and objects. Behavioral patterns deal primarily with dynamic interaction among classes and objects. This categorization allows us to think about design problems in terms of creation, structure, and interaction, which are core aspects of object-oriented design.

**Key points** (slide quote → follow-up → expected answer):
- **Creational patterns deal with the process of object creation.**  
  quote: "Creational patterns deal with the process of object creation"  
  follow-up: _What kind of problems would you use a creational pattern to solve?_  
  expected: A creational pattern would be used to solve problems related to object creation, such as managing object instantiation or ensuring that a class has only one instance.
- **Structural patterns deal primarily with the static composition and structure of classes and objects.**  
  quote: "Structural patterns, deal primarily with the static composition and structure of classes and objects"  
  follow-up: _How might a structural pattern help in organizing a system?_  
  expected: A structural pattern helps in organizing a system by defining how classes and objects are composed to form larger structures, which can improve flexibility and reusability.
- **Behavioral patterns deal primarily with dynamic interaction among classes and objects.**  
  quote: "Behavioral patterns, which deal primarily with dynamic interaction among classes and objects"  
  follow-up: _What kind of behavior would a behavioral pattern address?_  
  expected: A behavioral pattern would address behaviors such as communication between objects, responsibility assignment, and interaction patterns that govern how objects collaborate.

### [Classes and objects] How does the concept of a class as a blueprint influence the creation and behavior of objects in Java, and what role does the Object class play in this context?
*confidence 0.82 · hard · slides [60, 61, 294, 297, 402] · ⚠ NEEDS REVIEW*

**Reference:** A class serves as a blueprint that defines the structure and behavior of objects, which are instances of that class. The Object class, being the root of the class hierarchy, ensures that all objects in Java inherit common methods like equals(), hashCode(), and toString(). This inheritance allows for a consistent interface across all objects, enabling polymorphism and uniform handling of objects through a reference of type Object.

**Key points** (slide quote → follow-up → expected answer):
- **A class is a blueprint that defines the structure and behavior of objects.**  
  quote: "A class is a description of a set of objects that share the same attributes, operations, relationships and semantics."  
  follow-up: _What happens if two objects have different attributes but are based on the same class?_  
  expected: They would still share the same structure and behavior defined by the class, but can have different state values.
- **The Object class provides a common interface for all objects in Java.**  
  quote: "Class Object is the root of the class hierarchy. Every class has Object as a superclass."  
  follow-up: _Why would you want to use a reference variable of type Object to refer to any object?_  
  expected: Because it allows for polymorphism, enabling a single reference to handle objects of different types that share a common superclass.
- **Inheritance from Object ensures all objects have basic functionality.**  
  quote: "All objects, including arrays, implement the methods of this class."  
  follow-up: _What would happen if a class did not inherit from Object?_  
  expected: It would not have access to the fundamental methods like equals() and hashCode(), which are essential for object comparison and hashing.

### [Abstract classes] What are the implications of an abstract class being unable to be instantiated, and how does this affect its role in an inheritance hierarchy?
*confidence 0.82 · hard · slides [85, 266, 267, 268, 269, 416] · ⚠ NEEDS REVIEW*

**Reference:** An abstract class cannot be instantiated, which means you cannot create objects of its type directly. This reinforces its role as a template for subclasses, as it is designed to be extended rather than used as a standalone class. The inability to instantiate an abstract class ensures that subclasses must provide the necessary implementation for abstract methods, thereby enforcing a contract. This also prevents misuse of the class as a concrete type, ensuring that the abstraction remains intact. The fact that an abstract class can have both abstract and concrete methods allows for partial implementation, which is useful in defining a common framework for subclasses.

**Key points** (slide quote → follow-up → expected answer):
- **An abstract class cannot be instantiated.**  
  quote: "An abstract class is a class whose objects can’t be created."  
  follow-up: _Why would you want to prevent creating objects of an abstract class?_  
  expected: Because it is meant to be extended, not used as a concrete type. Its purpose is to define a common framework for subclasses.
- **An abstract class enforces a contract for subclasses.**  
  quote: "If a class extends abstract class then either it has to provide implementation of all abstract methods or declare this class as abstract class."  
  follow-up: _What happens if a subclass does not implement all abstract methods?_  
  expected: The subclass must also be declared abstract, which means it cannot be instantiated and must be further extended by another subclass.
- **An abstract class allows for partial implementation.**  
  quote: "An abstract class can have both abstract methods (methods without body) as well as nonabstract methods or concrete methods (methods with the body)."  
  follow-up: _How does this help in designing an inheritance hierarchy?_  
  expected: It allows the superclass to define common behavior while leaving specific details to be implemented by subclasses, promoting code reuse and reducing duplication.

### [Types of inheritance] Consider a scenario where a class inherits from two parent classes, one of which also inherits from another class. How does this scenario relate to the concept of inheritance types, and what limitations does Java impose on such a structure?
*confidence 0.82 · hard · slides [383, 384, 389] · ⚠ NEEDS REVIEW*

**Reference:** This scenario describes a hybrid inheritance structure, which combines multiple and hierarchical inheritance. Java does not support multiple inheritance via classes, so such a structure cannot be achieved directly with classes. Instead, Java allows the use of interfaces to simulate multiple inheritance, enabling a class to implement multiple interfaces while still maintaining a single class hierarchy.

**Key points** (slide quote → follow-up → expected answer):
- **Hybrid inheritance combines multiple and hierarchical inheritance.**  
  quote: "Hybrid Inheritance: Two or more types of inheritance—such as single, multiple, multilevel, or hierarchical—are combined to create a complex class hierarchy"  
  follow-up: _What happens if a class inherits from two parent classes, one of which also inherits from another class?_  
  expected: This creates a hybrid inheritance structure, combining multiple and hierarchical inheritance.
- **Java does not support multiple inheritance via classes.**  
  quote: "Java does not support multiple inheritance via classes; must use interfaces to achieve hybrid structures."  
  follow-up: _How does Java handle a situation where a class needs to inherit from two parent classes?_  
  expected: Java uses interfaces to simulate multiple inheritance, allowing a class to implement multiple interfaces.
- **Interfaces are used to simulate multiple inheritance in Java.**  
  quote: "Java does not support multiple inheritance via classes; must use interfaces to achieve hybrid structures."  
  follow-up: _What is the role of interfaces in Java's support for hybrid inheritance?_  
  expected: Interfaces allow a class to inherit behavior from multiple sources, effectively simulating multiple inheritance.

### [Method overloading] What happens if two overloaded methods differ only in their return types, and how does this affect the compiler's ability to resolve the correct method call?
*confidence 0.82 · hard · slides [354, 355, 356, 357] · ⚠ NEEDS REVIEW*

**Reference:** If two overloaded methods differ only in their return types, the compiler will not be able to resolve which method to call, resulting in a compilation error. This is because the return type is not part of the method signature used for overloading. The compiler relies solely on the method name and parameter list to determine which method to invoke. This highlights that return type cannot be used to distinguish between overloaded methods.

**Key points** (slide quote → follow-up → expected answer):
- **The return type is not part of the method signature used for method overloading.**  
  quote: "The argument lists of the methods must differ in either of these: Changing the number of parameters, Changing the data type of parameters, Changing the order of parameters of methods."  
  follow-up: _Can two methods with the same name, same parameter list, but different return types coexist in the same class?_  
  expected: No, they cannot. The return type is not part of the method signature, so the compiler will treat them as the same method and throw an error.
- **A difference in return type alone does not allow the compiler to resolve which method to call.**  
  quote: "The compiler decides which method to call (compile-time polymorphism) based on the method signature: method name + parameter list (number, type, order)."  
  follow-up: _If two methods have the same name and parameter list but different return types, what does the compiler do?_  
  expected: The compiler will throw a compilation error because it cannot distinguish between the two methods based on the method signature.
- **Method overloading relies solely on the method name and parameter list, not the return type.**  
  quote: "Method overloading is also known - Compile Time polymorphism, Static polymorphism, Early Binding."  
  follow-up: _Why is the return type not considered when resolving overloaded methods?_  
  expected: Because the return type does not affect the method signature, which is what the compiler uses to determine which method to call at compile time.

### [Overloading vs overriding] Consider a scenario where a base class has a method with a specific parameter type, and a derived class has a method with the same name but a different parameter type. What is the implication of this scenario, and how does it relate to the concepts of overloading and overriding?
*confidence 0.81 · hard · slides [354, 356, 382, 391, 392] · ⚠ NEEDS REVIEW*

**Reference:** This scenario illustrates a case where the derived class is attempting to overload a method from the base class, but the method signature is not identical. Overloading requires the same method name with different parameter lists, which is not the case here. However, if the derived class were to override the method, it would need to match the parameter list exactly. This highlights the distinction between overloading, which is compile-time polymorphism, and overriding, which is runtime polymorphism and requires method signature matching.

**Key points** (slide quote → follow-up → expected answer):
- **Overloading requires the same method name with different parameter lists.**  
  quote: "A feature that allows a class to have more than one method having the same name, if their argument lists are different."  
  follow-up: _What happens if a derived class defines a method with the same name but different parameters than the base class?_  
  expected: The derived class is overloading the method, which is allowed as long as the parameter lists differ.
- **Overriding requires the same method name and parameter list as the base class.**  
  quote: "If a subclass provides the specific implementation of the method that has been declared by one of its parent class, it is known as method overriding."  
  follow-up: _What must be true about the method signature in the derived class for it to override the base class method?_  
  expected: The method must have the same name and parameter list as the method in the base class.
- **Overloading is compile-time polymorphism, while overriding is runtime polymorphism.**  
  quote: "Method overloading is also known - Compile Time polymorphism, Static polymorphism , Early Binding."  
  follow-up: _How does the timing of resolution differ between overloading and overriding?_  
  expected: Overloading is resolved at compile time, while overriding is resolved at runtime based on the object type.

### [Liskov substitution principle] Consider a scenario where a subclass overrides a method from its superclass. What is the potential violation of the Liskov Substitution Principle, and how does this relate to the behavior of programs that depend on the superclass?
*confidence 0.81 · hard · slides [586, 648, 649] · ⚠ NEEDS REVIEW*

**Reference:** The Liskov Substitution Principle states that objects of a superclass should be replaceable with objects of its subclasses without altering the correctness of the program. If a subclass overrides a method and changes its behavior in a way that violates the expectations of the superclass, this can break the principle. For example, if a superclass method guarantees a certain outcome, and the subclass method does not uphold that guarantee, it can lead to incorrect behavior in programs that rely on the superclass's behavior.

**Key points** (slide quote → follow-up → expected answer):
- **The Liskov Substitution Principle requires that derived types must be completely substitutable for their base types.**  
  quote: "Let S be a subtype of T, then for each object o1 of type S there is an object o2 of type T such that for all programs P defined in terms of T, the behaviour of P is unchanged when o1 is substituted for o2."  
  follow-up: _What happens if a subclass changes the behavior of a method in a way that breaks the expectations of the superclass?_  
  expected: It can cause incorrect behavior in programs that rely on the superclass's behavior, violating the Liskov Substitution Principle.
- **A child class should never change the characteristics of its parent class.**  
  quote: "A child class should never change the characteristics of its parent class."  
  follow-up: _Why would changing the characteristics of a parent class be problematic in an inheritance hierarchy?_  
  expected: Because it breaks the expectations of programs that rely on the parent class's behavior, making substitution impossible without introducing errors.
- **Derived classes should never do less than their base class.**  
  quote: "Derived classes should never do less than their base class."  
  follow-up: _What does it mean for a derived class to 'do less than' its base class?_  
  expected: It means the derived class fails to provide the full functionality expected from the base class, which can break the substitutability required by the Liskov Substitution Principle.

### [Copy constructor] Explain how a copy constructor prevents unwanted reference sharing and why it's important in object-oriented design.
*confidence 0.78 · medium · slides [330]*

**Reference:** A copy constructor prevents unwanted reference sharing by creating a new object with the same data as the original, but without sharing references to mutable objects. This is important in object-oriented design because it ensures that changes to one object do not unintentionally affect another. In the example, the `name` field is copied using `new String(s.name)`, which avoids sharing the same reference.

**Key points** (slide quote → follow-up → expected answer):
- **A copy constructor takes an object of the same class as an argument.**  
  quote: "Copy constructor takes object of the same class as argument"  
  follow-up: _Why would you pass an object of the same class to a constructor?_  
  expected: To allow the constructor to initialize the new object using the data from the existing object, while still maintaining control over how the data is copied.
- **A copy constructor prevents unwanted reference sharing.**  
  quote: "Prevents unwanted reference sharing"  
  follow-up: _What could happen if reference sharing was not prevented in a copy constructor?_  
  expected: Changes made to one object could unintentionally affect another, leading to bugs that are hard to trace.

### [Anti-patterns] Explain how Vendor Lock-In is an AntiPattern in software architecture, and why it affects both development and management.
*confidence 0.78 · medium · slides [1000, 1001, 1016, 1020, 1021, 1022]*

**Reference:** Vendor Lock-In is an AntiPattern because it creates a situation where a software project becomes completely dependent on a vendor's implementation, leading to maintenance challenges and schedule slips. This affects development because it increases the complexity and difficulty of managing the application system architecture. It also affects management because it ties the application software maintenance cycle to commercial product upgrades, which can delay or prevent the delivery of desired features.

**Key points** (slide quote → follow-up → expected answer):
- **Vendor Lock-In ties the application maintenance cycle to product upgrades.**  
  quote: "Commercial product upgrades drive the application software maintenance cycle."  
  follow-up: _How does this affect the project timeline?_  
  expected: It forces the project to wait for product upgrades, which can delay the delivery of application features.
- **Vendor Lock-In increases the complexity of the application system architecture.**  
  quote: "The complexity and generality of the product technology greatly exceeds that of the application needs; direct dependence upon the product results in failure to manage the complexity of the application system architecture."  
  follow-up: _Why would using a complex product lead to problems?_  
  expected: Because the application system architecture becomes harder to manage, leading to increased technical debt and maintenance costs.

### [Indirection and pure fabrication] How does pure fabrication help in achieving low coupling and high cohesion in object-oriented design, and what role does indirection play in this?
*confidence 0.78 · medium · slides [492, 553, 554, 555, 556, 561]*

**Reference:** Pure fabrication helps achieve low coupling and high cohesion by encapsulating complex responsibilities in artificial classes, which isolates them from domain objects. This allows domain classes to remain focused on their core responsibilities, improving cohesion. Indirection is used to delegate these responsibilities to fabrication classes, reducing direct dependencies between domain objects and promoting modularity.

**Key points** (slide quote → follow-up → expected answer):
- **Pure fabrication encapsulates complex responsibilities in artificial classes.**  
  quote: "Introduce Fabrication Classes: Once complex responsibilities are identified, the 'Pure Fabrication' principle suggests introducing additional classes or objects solely for the purpose of encapsulating these responsibilities."  
  follow-up: _Can you give an example of a responsibility that might be encapsulated in a fabrication class?_  
  expected: An example is data validation, which can be encapsulated in a helper class rather than being scattered across domain classes.
- **Pure fabrication supports high cohesion by keeping domain classes focused on their core responsibilities.**  
  quote: "The pure fabrication classes encapsulate the complex or non-natural responsibilities, isolating them from the core domain objects."  
  follow-up: _Why is it important for domain classes to remain focused on their core responsibilities?_  
  expected: It ensures high cohesion, as domain classes are only responsible for what they represent in the domain, avoiding unnecessary complexity and improving maintainability.

### [Factory pattern] Explain how the Factory Method pattern improves flexibility in object creation, and why it is considered a better approach than direct constructor calls.
*confidence 0.78 · medium · slides [726, 745, 746, 748, 749, 750]*

**Reference:** The Factory Method pattern improves flexibility by delegating object creation to subclasses, allowing different subclasses to instantiate different concrete classes without changing the client code. This is in contrast to direct constructor calls, where the client is tightly coupled to the specific class being instantiated. By using a factory method, the client accesses objects through a common interface, which hides the actual implementation details and makes the system more maintainable and extensible.

**Key points** (slide quote → follow-up → expected answer):
- **The Factory Method pattern improves flexibility by delegating object creation to subclasses.**  
  quote: "The Factory method lets a class defer instantiation to subclasses."  
  follow-up: _What happens if the client code directly calls a constructor instead of using a factory method?_  
  expected: The client code becomes tightly coupled to the specific class being instantiated, reducing flexibility and making the system harder to maintain.
- **The client accesses objects using a common interface.**  
  quote: "The created objects are accessed using a common interface."  
  follow-up: _Why is it important for the client to access objects through a common interface rather than directly?_  
  expected: It allows the client to work with objects without knowing their specific implementation, promoting loose coupling and making the system more flexible and easier to extend.

### [Abstraction] Explain how abstraction in object-oriented programming helps in managing complexity in software design.
*confidence 0.77 · medium · slides [266, 267, 268, 269, 282]*

**Reference:** Abstraction in object-oriented programming helps manage complexity by hiding the internal implementation details of an entity and exposing only its essential features. This allows users to interact with the entity through its interface without needing to understand its internal workings. By focusing on what an object does rather than how it does it, abstraction reduces the cognitive load on developers and makes systems easier to maintain and scale.

**Key points** (slide quote → follow-up → expected answer):
- **Abstraction hides implementation details from users.**  
  quote: "Data abstraction in Object-oriented programming is a process of providing functionality to the users by hiding its implementation details from them."  
  follow-up: _Can you give an example of when you would want to hide the implementation details?_  
  expected: For instance, when using a database connection class, the user doesn't need to know how the connection is established, only that it can be used to query the database.
- **Abstraction allows interaction through an interface.**  
  quote: "Abstraction defines an object in terms of its properties (attributes), behavior (methods), and interfaces (means of communicating with other objects)."  
  follow-up: _What is the role of an interface in abstraction?_  
  expected: An interface provides a way for other objects to interact with the entity without needing to know its internal structure, which is a key aspect of abstraction.

### [Model-View-Controller] How does the Model-View-Controller pattern help in separating the user interface from the application logic, and what are the implications of this separation?
*confidence 0.77 · medium · slides [473]*

**Reference:** The Model-View-Controller pattern helps in separating the user interface from the application logic by dividing the application into three distinct components: model, view, and controller. This separation ensures that the graphical interface displayed to the user is completely decoupled from the code that manages user actions. As a result, changes in the user interface do not directly affect the business logic or data handling, making the system more maintainable and scalable.

**Key points** (slide quote → follow-up → expected answer):
- **The pattern ensures the graphical interface is decoupled from the code that manages user actions.**  
  quote: "It neatly separates the graphical interface displayed to the user from the code that manages the user actions."  
  follow-up: _What happens if the user interface changes but the business logic remains the same?_  
  expected: The controller and model remain unaffected, allowing for easier maintenance and updates to the view without altering the underlying logic.
- **The controller acts as an intermediary between the model and the view.**  
  quote: "A design pattern for computer software considered to distinguish between the data model, processing control and the user interface."  
  follow-up: _What role does the controller play in this separation?_  
  expected: The controller processes user input and updates the model or view accordingly, maintaining the separation between the user interface and the application logic.

### [IS-A vs HAS-A relationship] How does the 'has-a' relationship affect the lifecycle of objects in a system?
*confidence 0.77 · medium · slides [276, 277, 278, 279, 284]*

**Reference:** The 'has-a' relationship implies that the composed object cannot exist independently of the container object. When the container object is deleted, the composed object should also be deleted. This ensures that the lifecycle of the composed object is tied to the lifecycle of the container object, maintaining data integrity and consistency in the system.

**Key points** (slide quote → follow-up → expected answer):
- **The 'has-a' relationship enforces a dependency between objects.**  
  quote: "The Composition between two entities is done when an object contains a composed object, and the composed object cannot exist without another entity."  
  follow-up: _Why is it important for the composed object to depend on the container object?_  
  expected: It ensures that the composed object is properly managed and does not exist in isolation, which maintains the integrity of the system.
- **The 'has-a' relationship supports code reuse and flexibility.**  
  quote: "The Composition allows us to reuse the code."  
  follow-up: _How does the 'has-a' relationship support code reuse?_  
  expected: By allowing an object to contain another object, it can reuse the functionality of the composed object without needing to inherit its structure.

---

## Held back (low confidence — not used by the app)

### [Model-View-Controller] Can you explain what the Model-View-Controller pattern is and why it's useful in software design?
*confidence 0.74 · easy · slides [473]*

**Reference:** Model-View-Controller is an architectural pattern that separates application logic from presentation. It divides the application into three main components: model, view, and controller. This separation helps to decouple data access and business logic from the user interface, making the system more maintainable and scalable.

**Key points** (slide quote → follow-up → expected answer):
- **MVC is an architectural pattern that separates application logic from presentation.**  
  quote: "MVC - An architectural pattern in Software Engineering."  
  follow-up: _What is the main benefit of separating application logic from presentation?_  
  expected: It makes the system more maintainable and scalable by allowing different parts of the application to be developed and modified independently.
- **MVC divides the application into three main logical components: model, view, and controller.**  
  quote: "Division of application into three main logical components: model, view, and controller."  
  follow-up: _What are the three main components of the MVC pattern?_  
  expected: The three main components are model, view, and controller.

### [Destructors and garbage collection] Explain what the `finalize()` method in Java is used for, and why it is not always called.
*confidence 0.74 · easy · slides [331, 332, 333, 337]*

**Reference:** The `finalize()` method in Java is used to perform cleanup actions before an object is destroyed, such as closing database connections or releasing network resources. It is not always called because the Java runtime does not guarantee its execution just prior to garbage collection. The method is deprecated since Java 9, indicating that it is not a reliable mechanism for resource management.

**Key points** (slide quote → follow-up → expected answer):
- **The `finalize()` method is called just prior to garbage collection.**  
  quote: "Java run time calls this method whenever it is about to recycle an object of the class."  
  follow-up: _Is the `finalize()` method called when an object goes out of scope?_  
  expected: No, the `finalize()` method is not called when an object goes out of scope. It is only called just prior to garbage collection.
- **The execution of the `finalize()` method is not guaranteed.**  
  quote: "Execution is not guaranteed."  
  follow-up: _Why might the `finalize()` method not be called even if an object is no longer referenced?_  
  expected: Because the garbage collector may decide to reclaim the object's memory at any time, and the `finalize()` method is not guaranteed to be called before that happens.

### [Classes and objects] Explain how a class and an object are related in Java, and why the Object class is important in this relationship.
*confidence 0.70 · medium · slides [60, 61, 294, 297, 402]*

**Reference:** A class is a blueprint that defines the structure and behavior of objects, while an object is an instance of a class that occupies memory and has specific state and behavior. The Object class is the root of the class hierarchy in Java, meaning every class implicitly inherits from it, providing common methods like equals(), hashCode(), and toString() that are essential for object manipulation.

**Key points** (slide quote → follow-up → expected answer):
- **A class is a blueprint that defines the structure and behavior of objects.**  
  quote: "A class is a description of a set of objects that share the same attributes, operations, relationships and semantics."  
  follow-up: _What happens if you try to create an object without a class?_  
  expected: You cannot create an object without a class because a class provides the blueprint needed to instantiate an object.
- **An object is an instance of a class that occupies memory and has specific state and behavior.**  
  quote: "Object: An instance of a class that contains state (attributes) and behavior (methods)."  
  follow-up: _How would you access the behavior of an object?_  
  expected: You would access the behavior of an object using the dot (.) operator to call its methods.

### [Abstract classes] Explain how abstract classes support the concept of abstraction in object-oriented design, and why they are useful in an inheritance hierarchy.
*confidence 0.70 · medium · slides [85, 266, 267, 268, 269, 416]*

**Reference:** Abstract classes support abstraction by defining a generalized form that subclasses must implement, while hiding the implementation details from users. They allow for partial implementation, which reduces code duplication and increases reusability. In an inheritance hierarchy, abstract classes serve as a template for common methods, ensuring that subclasses provide specific details while adhering to a shared structure.

**Key points** (slide quote → follow-up → expected answer):
- **Abstract classes provide a template for common methods that subclasses must implement.**  
  quote: "The parent class also serves as a template for common methods that will be implemented by its subclasses."  
  follow-up: _What happens if a subclass does not implement all the methods defined in the abstract class?_  
  expected: The subclass must either implement all abstract methods or be declared as abstract itself, otherwise it will not compile.
- **Abstract classes cannot be instantiated, which reinforces their role in abstraction.**  
  quote: "An abstract class is a class whose objects can’t be created."  
  follow-up: _Why is it important that an abstract class cannot be instantiated?_  
  expected: Because the purpose of an abstract class is to define a common structure and interface for subclasses, not to be used directly as a concrete entity.

### [Coupling and cohesion] Explain how low coupling contributes to system maintainability and why it is important to balance it with high cohesion.
*confidence 0.70 · medium · slides [506, 507, 508, 509, 519, 520]*

**Reference:** Low coupling reduces the impact of changes in one class on others, making the system more maintainable. It allows classes to interact through well-defined interfaces, minimizing dependencies. However, it must be balanced with high cohesion to ensure that classes are focused and manageable. A class with low coupling but low cohesion may be hard to understand and reuse. High cohesion ensures that a class has a single, focused responsibility, which complements low coupling by making the system both flexible and maintainable.

**Key points** (slide quote → follow-up → expected answer):
- **Low coupling reduces the impact of changes in one class on others.**  
  quote: "Low coupling – How can we reduce the impact of change in depended elements on dependent elements? Assign responsibilities so that coupling remains low."  
  follow-up: _What happens if two classes are tightly coupled and one changes?_  
  expected: Changes in one class may require changes in the other, increasing the risk of errors and making the system harder to maintain.
- **Low coupling allows classes to interact through well-defined interfaces.**  
  quote: "Loose coupling occurs when classes are less dependent on the specifics of other classes. This can be achieved by using interfaces, abstract classes, or dependency injection, allowing classes to interact without knowing the implementation details of each other."  
  follow-up: _How does using an interface help with low coupling?_  
  expected: An interface defines a contract that classes can implement without knowing the specific implementation details, reducing direct dependency between classes.

### [Protected variations] Explain how protected variation helps manage instability in a system design.
*confidence 0.70 · medium · slides [557, 558, 559, 562, 563]*

**Reference:** Protected variation helps manage instability by identifying points of likely change and creating stable interfaces around them. This ensures that changes in one part of the system do not negatively impact other parts. By doing so, it supports the Open-Closed Principle and reduces coupling between components.

**Key points** (slide quote → follow-up → expected answer):
- **Protected variation identifies points of likely change.**  
  quote: "Identify points of likely change (variation points) and create a stable interface around them so that changes don’t affect the rest of the system."  
  follow-up: _What happens if you don’t identify variation points in your design?_  
  expected: You risk having changes in one part of the system ripple through and destabilize other parts, increasing complexity and maintenance costs.
- **Protected variation creates stable interfaces around change points.**  
  quote: "Identify points of likely change (variation points) and create a stable interface around them so that changes don’t affect the rest of the system."  
  follow-up: _Why is creating a stable interface important for system design?_  
  expected: A stable interface ensures that changes to one part of the system do not require changes to other parts, maintaining consistency and reducing coupling.

### [Java collections and List interface] How does the List interface in Java support efficient insertion and deletion of elements compared to other collection interfaces?
*confidence 0.70 · medium · slides [435, 462]*

**Reference:** The List interface in Java supports efficient insertion and deletion of elements through its index-based methods. This is because the List interface is designed to maintain an ordered collection, which allows for direct access to elements by their position. The implementation classes like ArrayList and LinkedList provide different mechanisms for these operations, but the interface itself ensures that such operations can be performed with index-based access.

**Key points** (slide quote → follow-up → expected answer):
- **The List interface provides index-based operations for inserting, updating, deleting, and searching elements.**  
  quote: "It contains the index based methods to insert, update, delete and search the elements."  
  follow-up: _Can you give an example of an operation that would require index-based access?_  
  expected: An example is the remove(int index) method, which deletes an element at a specific position in the list.
- **The List interface allows for direct access to elements by their position, which is essential for efficient insertion and deletion.**  
  quote: "List in Java provides the facility to maintain the ordered collection."  
  follow-up: _Why is maintaining an ordered collection important for insertion and deletion?_  
  expected: Maintaining an ordered collection allows for direct access to elements by their index, which makes insertion and deletion operations more efficient.

### [Design pattern categories] Explain how the categorization of design patterns into creational, structural, and behavioral categories helps in understanding and applying them in software design.
*confidence 0.70 · medium · slides [661]*

**Reference:** The categorization of design patterns into creational, structural, and behavioral categories helps in understanding and applying them by grouping patterns based on their primary purpose. Creational patterns deal with object creation, structural patterns deal with static composition, and behavioral patterns deal with dynamic interaction. This grouping allows developers to choose the most appropriate pattern for a given problem, based on whether the issue is about creation, structure, or interaction.

**Key points** (slide quote → follow-up → expected answer):
- **Categorization helps in understanding the purpose of each pattern.**  
  quote: "Creational patterns deal with the process of object creation."  
  follow-up: _What is the main purpose of structural patterns?_  
  expected: Structural patterns deal primarily with the static composition and structure of classes and objects.
- **Categorization helps in applying patterns to specific problems.**  
  quote: "Structural patterns, deal primarily with the static composition and structure of classes and objects."  
  follow-up: _How would you choose between a creational and a structural pattern?_  
  expected: You would choose a creational pattern if the issue is about object creation, and a structural pattern if the issue is about the composition or structure of classes and objects.

### [Dependency inversion principle] What happens if the OrderService class directly used MongoDBDatabase instead of the Database abstraction, and how does this relate to the Dependency Inversion Principle?
*confidence 0.70 · hard · slides [631, 652, 653, 654] · ⚠ NEEDS REVIEW*

**Reference:** If the OrderService directly used MongoDBDatabase, it would create a tight coupling between the high-level OrderService and the low-level MongoDBDatabase. This violates the Dependency Inversion Principle, which states that high-level modules should not depend on low-level modules. Instead, both should depend on abstractions. This tight coupling would make the system less flexible and harder to maintain, as changing the database would require modifying the OrderService class.

**Key points** (slide quote → follow-up → expected answer):
- **Dependency Inversion Principle requires both modules to depend on abstractions.**  
  quote: "High level modules should not depend on low level modules, both should depend upon abstractions."  
  follow-up: _Why is it important for both modules to depend on abstractions?_  
  expected: Because it ensures that changes in the implementation of low-level modules do not affect the high-level modules, improving maintainability and flexibility.
- **Using abstractions allows for easier substitution of implementations.**  
  quote: "Depend on abstractions instead of concrete classes."  
  follow-up: _How does using abstractions help when switching from MySQL to MongoDB?_  
  expected: By using the Database abstraction, the OrderService can work with any implementation of the interface, making it easier to switch databases without changing its code.

### [Java Object class] Explain how the `toString()` method in the `Object` class is used in Java, and why it's important for developers to override it in their own classes.
*confidence 0.70 · hard · slides [402, 404, 405, 407, 434] · ⚠ NEEDS REVIEW*

**Reference:** The `toString()` method in the `Object` class returns a string representation of an object, typically in the format `ClassName@hashCode`. This default behavior is not very informative for human readers. Developers are encouraged to override this method in their own classes to provide a more meaningful and readable string representation of the object's state, which is especially useful for debugging and logging.

**Key points** (slide quote → follow-up → expected answer):
- **The `toString()` method returns a string in the format `ClassName@hashCode` by default.**  
  quote: "The toString method for class Object returns a string consisting of the name of the class of which the object is an instance, the at-sign character `@`, and the unsigned hexadecimal representation of the hash code of the object."  
  follow-up: _What is the default string representation of an object if you don't override `toString()`?_  
  expected: It is `ClassName@hashCode`, where `ClassName` is the name of the class and `hashCode` is the object's hash code.
- **The `toString()` method is part of the `Object` class, which is the root of the class hierarchy.**  
  quote: "Class Object is the root of the class hierarchy. Every class has Object as a superclass."  
  follow-up: _Why is it important that `toString()` is defined in the `Object` class?_  
  expected: Because it ensures that all objects in Java have a default string representation, and it allows subclasses to override this behavior while maintaining consistency across the class hierarchy.

### [this and super keywords] What happens if a subclass constructor does not explicitly call a superclass constructor, and how does this relate to the use of the 'this' keyword?
*confidence 0.70 · hard · slides [390] · ⚠ NEEDS REVIEW*

**Reference:** When a subclass constructor does not explicitly call a superclass constructor, the default constructor of the superclass is invoked by default. This is because the object is constructed top-down in inheritance. The 'this' keyword refers to the current instance of the class, and it is used to differentiate between instance variables and parameters with the same name. However, 'this' cannot be used in a constructor to call another constructor of the same class unless it is the first statement.

**Key points** (slide quote → follow-up → expected answer):
- **The default constructor of the superclass is invoked if not explicitly called.**  
  quote: "When the object of subclass is created, constructor of sub class by default invokes the default constructor of super class."  
  follow-up: _What happens if the superclass does not have a default constructor?_  
  expected: In that case, the subclass constructor must explicitly call a constructor of the superclass using the 'super' keyword.
- **The 'this' keyword cannot be used to call a superclass constructor.**  
  quote: "The 'super' keyword refers to the superclass, immediately above of the calling class in the hierarchy."  
  follow-up: _Why can't you use 'this' to call a superclass constructor?_  
  expected: Because 'this' refers to the current instance, not the superclass, and calling a superclass constructor requires the 'super' keyword.

### [Iterator pattern] Explain how the Iterator pattern supports multiple traversals and why this is important for code flexibility.
*confidence 0.70 · hard · slides [977, 979, 983, 984] · ⚠ NEEDS REVIEW*

**Reference:** The Iterator pattern supports multiple traversals by providing a standardized interface that allows different algorithms to traverse a collection without knowing its internal structure. This is important for code flexibility because it enables clients to iterate over collections in various ways without modifying the collection itself. The pattern also allows for the same collection to be traversed multiple times without resetting the traversal, which is especially useful for large datasets where loading all elements into memory is inefficient.

**Key points** (slide quote → follow-up → expected answer):
- **The Iterator pattern supports multiple traversals by providing a standardized interface.**  
  quote: "The Iterator pattern is used to traverse them in a standardized way."  
  follow-up: _What does it mean for a traversal to be standardized?_  
  expected: It means that the traversal process follows a consistent interface, making it easier for different algorithms to use the same collection without knowing its internal structure.
- **The Iterator pattern improves code flexibility by decoupling the traversal logic from the collection structure.**  
  quote: "The Iterator pattern allows clients to iterate over collections in different ways without changing the underlying collection's structure."  
  follow-up: _How does this decoupling affect the code's maintainability?_  
  expected: It makes the code more maintainable because changes to the collection's structure do not require changes to the traversal logic, reducing the risk of introducing bugs.

### [Prototype pattern] In the Prototype pattern, how does the client create new objects without being tightly coupled to their classes?
*confidence 0.70 · medium · slides [784, 785, 787, 788, 791, 792]*

**Reference:** The client creates new objects by requesting an existing object to clone itself. This approach allows the client to make new instances without knowing which specific class is being instantiated. The client uses the clone method provided by the prototype, which ensures that the new object is a copy of the existing one. This decouples the client from the specific class implementation, making the system more flexible and easier to maintain.

**Key points** (slide quote → follow-up → expected answer):
- **The client requests an object to clone itself.**  
  quote: "Client: creates a new object by p=prototype.Clone() and then making required ConcretePrototype2 return copy of this"  
  follow-up: _Why would the client not directly create an object using the new keyword?_  
  expected: Because the client wants to avoid being tightly coupled to the specific class implementation, and cloning allows for more flexibility and reuse.
- **The client does not need to know the specific class being instantiated.**  
  quote: "Client code can make new instances without knowing which specific class is being instantiated"  
  follow-up: _How does the client avoid knowing the specific class?_  
  expected: By interacting with the prototype interface, the client works with an abstract representation, not the concrete class, which hides the implementation details.

### [Object memory allocation] How does the ability of multiple objects to be created from one class affect memory allocation in Java?
*confidence 0.68 · medium · slides [296]*

**Reference:** The ability to create multiple objects from one class means each object is allocated its own separate memory space. This ensures that changes to one object do not affect others. Each object has its own memory, which allows for independent state management. This is a core aspect of object-oriented design in Java.

**Key points** (slide quote → follow-up → expected answer):
- **Multiple objects can be created from one class.**  
  quote: "Multiple objects can be created from one class"  
  follow-up: _What happens if you create two objects from the same class and modify one of them?_  
  expected: Modifying one object does not affect the other because each has its own memory space.
- **Each object has its own memory space.**  
  quote: "Java Object : Key Characteristics ... Has its own memory"  
  follow-up: _Why is it important for each object to have its own memory?_  
  expected: It allows each object to maintain its own state independently, which is essential for correct behavior in object-oriented programs.

### [Encapsulation] Consider a scenario where a class's internal state is modified without changing its public interface. How does encapsulation enable this flexibility, and what trade-off does it introduce in terms of system design?
*confidence 0.63 · hard · slides [272, 273, 274] · ⚠ NEEDS REVIEW*

**Reference:** Encapsulation enables this flexibility by allowing the internal implementation of a class to change without affecting the external behavior, as the public interface remains stable. This is because the data is insulated from direct access, and only the provided functions can modify it. However, this insulation can introduce a trade-off where the complexity of the system increases, especially if the internal details are not well understood by the developers using the class.

**Key points** (slide quote → follow-up → expected answer):
- **Encapsulation insulates data from direct access, which supports internal changes.**  
  quote: "This insulation of the data from direct access by the program is called data hiding or information hiding."  
  follow-up: _Why would a programmer want to prevent external code from directly accessing a class's data?_  
  expected: To protect the integrity of the internal state and allow for controlled modifications through well-defined interfaces.
- **Encapsulation can introduce increased complexity in system design.**  
  quote: "Can lead to increased complexity, especially if not used properly."  
  follow-up: _How might encapsulation lead to increased complexity in a system?_  
  expected: When the internal details are abstracted away, developers may have a harder time understanding how the system works, especially if the encapsulation is overused or not well-documented.

### [Abstraction] What trade-off exists between the level of abstraction in an abstract class and the flexibility of its implementation?
*confidence 0.63 · hard · slides [266, 267, 268, 269, 282] · ⚠ NEEDS REVIEW*

**Reference:** An abstract class can achieve 0 to 100% abstraction, which means it can have both abstract and concrete methods. This allows for partial abstraction, giving developers more control over the implementation. However, this also means that the implementation details are not fully hidden, which reduces the flexibility compared to interfaces that provide 100% abstraction. The trade-off is between control and flexibility: abstract classes offer more control over implementation, but interfaces offer greater flexibility by fully hiding implementation details.

**Key points** (slide quote → follow-up → expected answer):
- **An abstract class can achieve 0 to 100% abstraction.**  
  quote: "Using an abstract class, we can achieve 0 to 100% abstraction."  
  follow-up: _Can an abstract class fully hide the implementation details of its methods?_  
  expected: No, an abstract class can only achieve up to 100% abstraction if it contains only abstract methods, but it can also have concrete methods that expose implementation details.
- **Interfaces provide 100% abstraction.**  
  quote: "We can achieve 100% abstraction using interfaces."  
  follow-up: _Why might an abstract class be less flexible than an interface?_  
  expected: Because an abstract class can have concrete methods that expose implementation details, while an interface can only define abstract methods and thus fully hides the implementation.

### [Information Expert] Consider a scenario where two classes share the information needed to fulfill a responsibility. How does the Information Expert principle guide the assignment of that responsibility, and what trade-off might arise from this decision?
*confidence 0.63 · hard · slides [500, 501] · ⚠ NEEDS REVIEW*

**Reference:** The Information Expert principle suggests that the responsibility should be assigned to the class that has the most relevant information, even if another class also has some of it. This ensures that the object with the most complete information can act on it more effectively. However, this may lead to a trade-off where one class becomes overly burdened with responsibilities, potentially reducing cohesion and increasing complexity.

**Key points** (slide quote → follow-up → expected answer):
- **The responsibility should be assigned to the class with the most relevant information.**  
  quote: "Assign a responsibility to the class that has the information needed to fulfill it."  
  follow-up: _What happens if two classes have equal access to the information needed for a responsibility?_  
  expected: In such a case, the Information Expert principle suggests choosing the class that has the most complete or directly relevant information, which may require further analysis of the domain model.
- **Assigning responsibility based on information may lead to increased complexity.**  
  quote: "Information necessary may be spread across several classes => objects interact via messages."  
  follow-up: _How might assigning a responsibility based on information affect the overall system design?_  
  expected: It may increase the number of interactions between objects, which can complicate the system and reduce maintainability if not carefully managed.

### [Factory pattern] How does the Factory Method pattern support language-specific variations in object creation, and what trade-offs might arise from this?
*confidence 0.63 · hard · slides [726, 745, 746, 748, 749, 750] · ⚠ NEEDS REVIEW*

**Reference:** The Factory Method pattern supports language-specific variations by allowing the factory method to return the class of the object to be instantiated, which can be stored or computed by the ConcreteCreator. This enables later binding for the type of ConcreteProduct to be instantiated, offering flexibility. However, this variation may complicate the design by requiring additional logic in the ConcreteCreator to determine the appropriate class, which can reduce clarity and increase the potential for errors.

**Key points** (slide quote → follow-up → expected answer):
- **The Factory Method pattern allows for language-specific variations by letting the factory method return the class of the object to be instantiated.**  
  quote: "Smalltalk programs often use a method that returns the class of the object to be instantiated. A Creator factory method can use this value to create a product, and a ConcreteCreator may store or even compute this value."  
  follow-up: _Can you explain how returning the class of the object to be instantiated affects the design?_  
  expected: Returning the class of the object to be instantiated allows for later binding, which increases flexibility but may require more complex logic in the ConcreteCreator.
- **This variation enables later binding for the type of ConcreteProduct to be instantiated.**  
  quote: "The result is an even later binding for the type of ConcreteProduct to be instantiated."  
  follow-up: _What does later binding mean in the context of the Factory Method pattern?_  
  expected: Later binding means that the specific type of object to be created is determined at runtime rather than at compile time, which increases flexibility but can make the system harder to understand and debug.

### [Chain of responsibility pattern] What happens if no object in the chain of responsibility handles a request, and how does this affect the system's behavior?
*confidence 0.63 · hard · slides [896, 898] · ⚠ NEEDS REVIEW*

**Reference:** If no object in the chain handles a request, the request is ultimately not processed, which can lead to an unhandled exception or an error in the system. The pattern does not inherently provide a default handler, so the responsibility for handling such cases must be explicitly defined by the client or the chain's configuration. This highlights the importance of ensuring that the chain is properly constructed to avoid unhandled requests.

**Key points** (slide quote → follow-up → expected answer):
- **The Chain of Responsibility pattern does not guarantee that a request will be handled if no object in the chain can handle it.**  
  quote: "The receiving objects are chained and pass the request along the chain until one of the objects handles it."  
  follow-up: _What happens if the chain is not properly configured and no object can handle the request?_  
  expected: The request may not be handled, which could result in an error or an unhandled exception.
- **The responsibility for handling unhandled requests lies with the client or the chain's configuration.**  
  quote: "The set of potential request handler objects and the order in which these objects form the chain can be decided dynamically at runtime by the client depending on the current state of the application."  
  follow-up: _Who is responsible for ensuring that the chain can handle all possible requests?_  
  expected: The client is responsible for ensuring that the chain is configured to handle all possible requests, or for providing a default handler.

### [Single responsibility principle] What happens if a class violates the Single Responsibility Principle, and how does this affect the system's maintainability and testability?
*confidence 0.63 · hard · slides [572, 644, 645] · ⚠ NEEDS REVIEW*

**Reference:** When a class violates the Single Responsibility Principle, it becomes tightly coupled and harder to maintain. The class has multiple reasons to change, which increases the risk of introducing bugs during updates. This also makes the class harder to test, as changes in one responsibility can inadvertently affect others. Without SRP, these benefits are lost, leading to a more fragile and complex system.

**Key points** (slide quote → follow-up → expected answer):
- **A class with multiple responsibilities has multiple reasons to change.**  
  quote: "A class should have one, and only one, reason to change - Robert C. Martin"  
  follow-up: _What is the impact of having multiple reasons to change in a class?_  
  expected: It increases the risk of introducing bugs and makes the class harder to maintain.
- **SRP improves testability by isolating responsibilities.**  
  quote: "Code becomes easier to test and maintain."  
  follow-up: _Why is testability improved when a class follows SRP?_  
  expected: Because each responsibility is isolated, making it easier to write and maintain focused tests.

### [Adapter pattern] What is the difference between a class adapter and an object adapter in the Adapter pattern, and how does this difference affect their implementation and usage?
*confidence 0.63 · hard · slides [807, 808, 809, 816, 817] · ⚠ NEEDS REVIEW*

**Reference:** A class adapter uses multiple inheritance to adapt one interface to another, while an object adapter relies on object composition through delegation. This difference affects their implementation because class adapters are only possible in languages that support multiple inheritance, whereas object adapters are more flexible and widely applicable. The choice between them also influences how the Adapter interacts with the Adaptee and Target interfaces, with object adapters providing greater decoupling and easier extension.

**Key points** (slide quote → follow-up → expected answer):
- **A class adapter uses multiple inheritance to adapt one interface to another.**  
  quote: "A class adapter uses multiple inheritance to adapt one interface to another: Class adapters can be implemented in languages supporting multiple inheritance (Java, C# or PHP does not support multiple inheritance)."  
  follow-up: _Can you explain why class adapters are limited to certain programming languages?_  
  expected: Because class adapters rely on multiple inheritance, they can only be implemented in languages that support this feature, such as C++ or Python, but not in Java or PHP.
- **An object adapter relies on object composition through delegation.**  
  quote: "An object adapter relies on object composition: Based on delegation."  
  follow-up: _How does delegation affect the relationship between the Adapter and the Adaptee?_  
  expected: Delegation allows the Adapter to encapsulate an instance of the Adaptee and forward requests to it, which provides greater flexibility and decoupling between the Adapter and the Adaptee.

### [Protected variations] What is the difference between a variation point and an evolution point in the context of protected variation?
*confidence 0.63 · hard · slides [557, 558, 559, 562, 563] · ⚠ NEEDS REVIEW*

**Reference:** A variation point is a branching point in an existing system or requirements that is already known and likely to change. An evolution point, on the other hand, is a supposed branching point that may occur in the future but is not declared by current requirements. The distinction is important because variation points require immediate design for stability, while evolution points are potential future changes that should be anticipated but not yet addressed.

**Key points** (slide quote → follow-up → expected answer):
- **A variation point is a branching point in an existing system or requirements.**  
  quote: "Variation point: Branching point on existing system or in requirements."  
  follow-up: _What is the significance of identifying a branching point in the existing system?_  
  expected: It allows the design to anticipate and isolate changes, reducing their impact on the rest of the system.
- **An evolution point is a supposed branching point that may occur in the future.**  
  quote: "Evolution point: Supposed branching point, which might occur in future, but does not declare by existing requirements."  
  follow-up: _Why is an evolution point not declared by existing requirements?_  
  expected: Because it represents a potential future change that has not yet been confirmed or required by current specifications.

### [Controller (GRASP)] What are the implications of using a bloated controller in a system design, and how does it contradict the principles of GRASP?
*confidence 0.62 · hard · slides [492, 528, 529, 530, 543] · ⚠ NEEDS REVIEW*

**Reference:** A bloated controller is a single class that receives all system events and performs many tasks rather than delegating them. This contradicts the Controller pattern's goal of coordinating activities while delegating work to other objects. It also violates the principle of low coupling and high cohesion, as the controller becomes tightly coupled with many system components and holds too much responsibility. This makes the system harder to maintain and less flexible, as changes in one part of the system can have widespread effects.

**Key points** (slide quote → follow-up → expected answer):
- **A bloated controller is a single class that receives all system events and performs many tasks rather than delegating them.**  
  quote: "Bloated Controller: A class that receives all system events and there are many of them. Controller performs many tasks rather than delegating them."  
  follow-up: _What happens if a single controller handles all system events?_  
  expected: It leads to a single point of failure and makes the system harder to maintain and scale.
- **A bloated controller contradicts the Controller pattern's goal of coordinating activities while delegating work to other objects.**  
  quote: "Normally controller coordinates activity but delegates work to other objects rather than doing work itself."  
  follow-up: _Why is it important for a controller to delegate work to other objects?_  
  expected: To maintain low coupling and high cohesion, ensuring that each object has a single responsibility and the system remains modular and maintainable.
