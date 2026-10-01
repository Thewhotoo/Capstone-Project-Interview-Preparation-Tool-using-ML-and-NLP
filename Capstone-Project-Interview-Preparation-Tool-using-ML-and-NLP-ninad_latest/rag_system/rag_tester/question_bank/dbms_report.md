# Question bank: dbms

- **Active (used by the app): 61** · held back for review: 40 (confidence threshold 0.75)
- Sorted by confidence, best first. Held-back questions are kept below, not deleted.

## Active questions

### [Entities and attributes] Explain what a primary key is in the context of entity sets.
*confidence 0.96 · easy · slides [177, 178, 179, 180, 181, 227]*

**Reference:** A primary key is a set of attributes that distinguish entities within an entity set. It ensures that no two entities in the set have the same values for all attributes. The primary key of an entity set becomes the primary key of the resulting schema. This helps uniquely identify each entity in the database. The primary key is essential for maintaining data integrity and enabling efficient data retrieval.

**Key points** (slide quote → follow-up → expected answer):
- **A primary key is a set of attributes that distinguish entities within an entity set.**  
  quote: "Key for an entity is a set of attributes that distinguish entities."  
  follow-up: _What happens if two entities have the same values for all attributes?_  
  expected: This would violate the uniqueness constraint of the primary key, making it impossible to distinguish between the two entities.
- **The primary key of an entity set becomes the primary key of the resulting schema.**  
  quote: "For schemas derived from strong entity sets, the primary key of the entity set serves as the primary key of the resulting schema."  
  follow-up: _Why is it important for the primary key to be part of the schema?_  
  expected: It ensures that each entity can be uniquely identified and referenced in the database, which is essential for data integrity and query operations.
- **The primary key ensures that no two entities in the set have the same values for all attributes.**  
  quote: "No two entities in an entity set can share the same values for all attributes."  
  follow-up: _What would be an example of a primary key in the university database?_  
  expected: The ID attribute in the Student entity set is a primary key because it uniquely identifies each student.

### [GRANT and REVOKE privileges] Explain what the REVOKE statement does in the context of database privileges.
*confidence 0.96 · easy · slides [698]*

**Reference:** The REVOKE statement is used to remove an authorization that was previously granted using the GRANT statement. It follows a syntax similar to GRANT, specifying the privilege to be revoked, the database and table it applies to, and the user from whom the privilege is removed. This ensures that access rights can be dynamically adjusted as needed in a database system.

**Key points** (slide quote → follow-up → expected answer):
- **The REVOKE statement removes an authorization previously granted by GRANT.**  
  quote: "To revoke an authorization, we use the REVOKE statement. It takes a form almost identical to that of GRANT."  
  follow-up: _What happens if you try to revoke a privilege that was never granted?_  
  expected: You would get an error because the privilege does not exist in the system's authorization records.
- **The REVOKE statement specifies the privilege to be revoked.**  
  quote: "REVOKE privileges ON database.table FROM ‘username’@’localhost’;"  
  follow-up: _What if you want to revoke a privilege from all users?_  
  expected: You would need to specify each user individually, or use a wildcard if supported by the system.
- **The REVOKE statement identifies the user from whom the privilege is removed.**  
  quote: "REVOKE privileges ON database.table FROM ‘username’@’localhost’;"  
  follow-up: _Why is the host part of the user identifier in the REVOKE statement?_  
  expected: The host part specifies which connection or session the privilege applies to, allowing fine-grained control over access.

### [Stored procedures and functions] Explain what a stored procedure is and why it is useful in a database system.
*confidence 0.96 · easy · slides [724, 725, 726, 727, 734, 735]*

**Reference:** A stored procedure is a collection of pre-compiled SQL statements stored inside the database. It is useful because it allows a database program to be stored at the server and invoked by any application program, reducing duplication of effort and improving software modularity. It also reduces data transfer and communication cost between the client and server in certain situations.

**Key points** (slide quote → follow-up → expected answer):
- **A stored procedure is a collection of pre-compiled SQL statements stored inside the database.**  
  quote: "A procedure (often called a stored procedure) is a collection of pre-compiled SQL statements stored inside the database."  
  follow-up: _What is the main purpose of storing SQL statements in the database?_  
  expected: The main purpose is to allow the database program to be stored at the server and invoked by any application program.
- **Stored procedures reduce duplication of effort and improve software modularity.**  
  quote: "If a database program is needed by several applications, it can be stored at the server and invoked by any of the application programs. This reduces duplication of effort and improves software modularity."  
  follow-up: _How does using stored procedures help in reducing duplication of effort?_  
  expected: Using stored procedures allows a single implementation of a database program to be reused by multiple applications, thus reducing duplication of effort.
- **Stored procedures can reduce data transfer and communication cost between the client and server.**  
  quote: "Executing a program at the server can reduce data transfer and communication cost between the client and server in certain situations."  
  follow-up: _In what situations might stored procedures reduce communication costs?_  
  expected: Stored procedures can reduce communication costs when complex operations are performed on the server, minimizing the need to send large amounts of data between the client and server.

### [Second normal form (2NF)] Explain what it means for a relation to be in second normal form (2NF).
*confidence 0.96 · easy · slides [941, 942, 952]*

**Reference:** A relation schema R is in second normal form (2NF) if every non-prime attribute A in R is fully functionally dependent on the primary key and R is in 1NF. This means that no non-prime attribute should be partially dependent on the primary key. The test for 2NF involves checking for FDs whose left-hand side attributes are part of the primary key.

**Key points** (slide quote → follow-up → expected answer):
- **A relation is in 2NF if every non-prime attribute is fully functionally dependent on the primary key.**  
  quote: "A relation schema R is in second normal form (2NF) if every non-prime attribute A in R is fully functionally dependent on the primary key and R is in 1NF"  
  follow-up: _What happens if a non-prime attribute is only partially dependent on the primary key?_  
  expected: The relation would not be in 2NF, as 2NF requires full functional dependency of non-prime attributes on the primary key.
- **2NF requires that the relation is already in 1NF.**  
  quote: "A relation schema R is in second normal form (2NF) if every non-prime attribute A in R is fully functionally dependent on the primary key and R is in 1NF"  
  follow-up: _Why is it necessary for a relation to be in 1NF before being in 2NF?_  
  expected: Because 2NF builds upon 1NF, which ensures there are no repeating groups and all atomic values are stored.
- **2NF normalization involves eliminating partial dependencies.**  
  quote: "The test for 2NF involves testing for FDs whose left hand side attributes are part"  
  follow-up: _What is the purpose of checking for FDs with left-hand side attributes that are part of the primary key?_  
  expected: To identify and eliminate partial dependencies, which violate the requirements of 2NF.

### [Transaction states] Explain what happens when a transaction reaches the partially committed state.
*confidence 0.96 · easy · slides [1093, 1094, 1095]*

**Reference:** When a transaction ends, it moves to the partially committed state. At this point, some types of concurrency control protocols may do additional checks to see if the transaction can be committed or not. Also, some recovery protocols need to ensure that a system failure will not result in an inability to record the changes of the transaction permanently. If these checks are successful, the transaction is said to have reached its commit point and enters the committed state.

**Key points** (slide quote → follow-up → expected answer):
- **A transaction moves to the partially committed state when it ends.**  
  quote: "When the transaction ends, it moves to the partially committed state."  
  follow-up: _What is the purpose of the partially committed state?_  
  expected: The purpose is to allow concurrency control protocols to perform additional checks and for recovery protocols to ensure that changes can be permanently recorded even if a system failure occurs.
- **Concurrency control protocols may perform additional checks in the partially committed state.**  
  quote: "some types of concurrency control protocols may do additional checks to see if the transaction can be committed or not."  
  follow-up: _Why would a concurrency control protocol need to check the transaction in this state?_  
  expected: To ensure that the transaction's changes are consistent with the database and that no conflicts with other transactions exist.
- **Recovery protocols ensure that changes can be permanently recorded in the partially committed state.**  
  quote: "some recovery protocols need to ensure that a system failure will not result in an inability to record the changes of the transaction permanently."  
  follow-up: _What could happen if the partially committed state was skipped?_  
  expected: The system might be unable to record the transaction's changes permanently in the event of a failure, leading to data inconsistency.

### [Graph databases and Neo4j] Explain how Neo4j represents entities and relationships in its data model.
*confidence 0.96 · easy · slides [1297, 1298, 1299, 1300, 1301, 1318]*

**Reference:** Neo4j represents entities as nodes, which can have labels to identify their type. Relationships in Neo4j are directed and connect nodes, with a relationship type that identifies the nature of the connection. Both nodes and relationships can have properties to store additional data. This model allows for intuitive modeling of real-world networks as graphs.

**Key points** (slide quote → follow-up → expected answer):
- **Nodes represent entities in Neo4j.**  
  quote: "Nodes in Neo4j correspond to entities"  
  follow-up: _What do you call the equivalent of a table in a relational database in Neo4j?_  
  expected: In Neo4j, the equivalent of a table is a node label, which groups nodes of the same type.
- **Relationships are directed in Neo4j.**  
  quote: "Relationships are directed; each relationship has a start node and end node as well as a relationship type"  
  follow-up: _Can a relationship in Neo4j connect two nodes in both directions?_  
  expected: No, relationships in Neo4j are directed, meaning they have a specific start and end node.
- **Relationships have a type that identifies their nature.**  
  quote: "Relationship type, which serves a similar role to a node label by identifying similar relationships that have the same relationship type"  
  follow-up: _How does Neo4j help you find all relationships of a certain type?_  
  expected: Neo4j uses the relationship type to group similar relationships, making it easier to query and analyze them.

### [Aggregate functions and GROUP BY] Explain what aggregate functions do and how they are used in SQL queries.
*confidence 0.96 · easy · slides [359, 368, 369, 547, 560, 561]*

**Reference:** Aggregate functions take a collection of values and return a single value, such as SUM, MAX, MIN, AVG, or COUNT. They are used to summarize information from multiple tuples into a single tuple summary. When used with the GROUP BY clause, they allow you to compute these summaries for each group of tuples that share the same value for the grouping attribute.

**Key points** (slide quote → follow-up → expected answer):
- **Aggregate functions take a collection of values and return a single value.**  
  quote: "Aggregate functions are functions that take a collection (a set or multiset) of values as input and return a single value."  
  follow-up: _What happens if you apply an aggregate function to a single value?_  
  expected: It will return that same value, since there's no collection to summarize.
- **Aggregate functions are used to summarize information from multiple tuples into a single tuple summary.**  
  quote: "Aggregate functions are used to summarize information from multiple tuples into a single tuple summary."  
  follow-up: _Can you use an aggregate function in a query without grouping?_  
  expected: Yes, you can use aggregate functions without GROUP BY, but they will apply to all rows in the table.
- **Aggregate functions are used with GROUP BY to compute summaries for each group.**  
  quote: "The SELECT clause must contain only the grouping attributes and aggregate functions applied on each group of tuples."  
  follow-up: _What happens if you include a non-aggregated attribute in the SELECT clause with GROUP BY?_  
  expected: It will result in an error, because the non-aggregated attribute is not part of the grouping and cannot be uniquely determined for each group.

### [Denormalization] Explain what denormalization is and why it might be used in a database.
*confidence 0.96 · easy · slides [933, 934, 935]*

**Reference:** Denormalization is a database optimization technique where redundant data is added to one or more tables to avoid costly joins. It is used when retrieving data is prioritized over update efficiency, and when the cost of joins becomes a performance bottleneck. This approach allows for simpler queries and faster data retrieval, but at the expense of increased storage and potential data inconsistency.

**Key points** (slide quote → follow-up → expected answer):
- **Denormalization is a database optimization technique where redundant data is added to one or more tables.**  
  quote: "Denormalization is a database optimization technique in which we add redundant data to one or more tables."  
  follow-up: _Why would someone want to add redundant data to a table?_  
  expected: To avoid costly joins and improve query performance by reducing the need for complex joins between tables.
- **Denormalization is used when retrieving data is prioritized over update efficiency.**  
  quote: "Denormalization, then, strikes a different compromise. Under denormalization, we decide that we’re okay with some redundancy and some extra effort to update the database in order to get the efficiency advantages of fewer joins."  
  follow-up: _What is the main trade-off of denormalization?_  
  expected: The main trade-off is that updates and inserts become more expensive and data consistency is harder to maintain.
- **Denormalization allows for simpler queries and faster data retrieval.**  
  quote: "Queries to retrieve can be simpler (and therefore less likely to have bugs), since we need to look at fewer tables."  
  follow-up: _How does denormalization affect query complexity?_  
  expected: Denormalization reduces query complexity by requiring fewer tables to be joined, making queries simpler and less error-prone.

### [Inner join] Can you explain what an Inner Join does in SQL, based on what you've learned?
*confidence 0.96 · easy · slides [582, 583, 584]*

**Reference:** An Inner Join combines records from two related tables based on a join predicate. It compares each row of the first table with each row of the second table to find all pairs that satisfy the join condition. When the condition is met, the column values from both tables are combined into a result row. This is the default type of join in SQL, and it is also known as an Equijoin.

**Key points** (slide quote → follow-up → expected answer):
- **Inner Join combines records from two related tables based on a join predicate.**  
  quote: "SQL Inner Join is a type of join that is used to combine records from two related tables, based and select the rows depending on the condition (join predicate)"  
  follow-up: _What happens if there's no matching row in one of the tables?_  
  expected: No rows are returned from that table, as Inner Join only includes rows that satisfy the join condition.
- **Inner Join compares each row of the first table with each row of the second table to find all pairs that satisfy the join predicate.**  
  quote: "Inner Join query compares each row of the first table with each row of the second table to find all pairs of rows that satisfy the join-predicate."  
  follow-up: _How does this process affect performance?_  
  expected: It can be computationally expensive if the tables are large, as it may require checking many row pairs.
- **Inner Join is the default type of join in SQL.**  
  quote: "The Inner Join is a default join; i.e., even if the 'Join' keyword is used instead of 'Inner Join', tables are joined using matching records of common columns, by default."  
  follow-up: _What is the difference between using 'Inner Join' and 'Join' in SQL?_  
  expected: There is no difference in the result; both keywords produce the same behavior, which is to return only matching rows from both tables.

### [NULL handling in SQL] Explain how SQL handles comparisons involving NULL values.
*confidence 0.96 · easy · slides [536, 537, 539]*

**Reference:** In SQL, comparisons involving NULL values result in UNKNOWN. This is because NULL represents an unknown or missing value, and it cannot be determined whether the comparison is true or false. For example, the expression (1 < NULL) evaluates to UNKNOWN. Similarly, NOT(1 < NULL) also evaluates to UNKNOWN. This behavior is part of SQL's approach to handling NULL values in logical operations.

**Key points** (slide quote → follow-up → expected answer):
- **Comparisons involving NULL values result in UNKNOWN.**  
  quote: "Any comparison operation involving NULL values would result in an UNKNOWN."  
  follow-up: _What happens if you compare a value to NULL using the equals operator?_  
  expected: The result would be UNKNOWN, as NULL is not considered equal to any value, including itself.
- **NULL represents an unknown or missing value.**  
  quote: "NULL has one of the three representations: Unknown value: value exists but is not known, or it is not known whether or not the value exists."  
  follow-up: _Why can't SQL distinguish between different meanings of NULL?_  
  expected: SQL does not distinguish among the different meanings of NULL because it is designed to handle the logical uncertainty of unknown values uniformly.
- **The logical value UNKNOWN is used in SQL for comparisons with NULL.**  
  quote: "To handle comparisons involving NULL values in SQL, a third logical value UNKNOWN, in addition to TRUE and FALSE, is used."  
  follow-up: _How does this affect the outcome of a WHERE clause with a NULL comparison?_  
  expected: It means that rows with NULL values will not be included in the result unless the query explicitly accounts for UNKNOWN using conditions like IS NULL or IS NOT NULL.

### [Query processing and join algorithms] Explain how an index-based nested-loop join improves upon the standard nested-loop join.
*confidence 0.96 · easy · slides [1032, 1033, 1034, 1039]*

**Reference:** An index-based nested-loop join improves upon the standard nested-loop join by using an index on the join attribute of the inner relation. This allows for quick lookup of matching tuples instead of scanning the entire inner table. As a result, the process becomes much faster compared to the brute force approach of checking every tuple in the inner relation for each tuple in the outer relation.

**Key points** (slide quote → follow-up → expected answer):
- **An index-based nested-loop join uses an index on the join attribute of the inner relation.**  
  quote: "Improves on nested-loop join by using an index on the join attribute of the inner relation."  
  follow-up: _What is the main advantage of using an index in this context?_  
  expected: The main advantage is that it allows for quick lookup of matching tuples instead of scanning the entire inner table.
- **The index allows for direct lookup of matching tuples instead of scanning the entire inner table.**  
  quote: "Instead of scanning the inner table completely, use the index to find matching tuples quickly."  
  follow-up: _How does this affect the performance of the join operation?_  
  expected: This significantly improves performance by reducing the number of disk I/O operations needed to find matching tuples.
- **The index-based nested-loop join is faster than the standard nested-loop join.**  
  quote: "Thus, the whole process is much faster."  
  follow-up: _Why is the index-based nested-loop join considered more efficient?_  
  expected: Because it reduces the number of comparisons and disk accesses by leveraging the index to directly locate matching tuples.

### [Relational algebra joins and division] Explain what a natural join is in relational algebra.
*confidence 0.95 · easy · slides [575, 576, 577, 578, 579, 580]*

**Reference:** A natural join is a type of join operation that creates an implicit join by combining tables based on columns with the same name and data type. It does not require specifying a join condition, and it automatically creates an implicit EQUIJOIN condition for each pair of attributes with the same name from the two relations. The resultant table always contains unique columns, and it is possible to perform a natural join on more than two tables.

**Key points** (slide quote → follow-up → expected answer):
- **A natural join combines tables based on columns with the same name and data type.**  
  quote: "A natural join is a type of join operation that creates an implicit join by combining tables based on columns with the same name and data type."  
  follow-up: _What happens if the columns have the same name but different data types?_  
  expected: The natural join would not combine those columns because they must have both the same name and data type to be matched.
- **A natural join does not require specifying a join condition.**  
  quote: "In a NATURAL JOIN on two relations R and S, no join condition is specified."  
  follow-up: _Can you use the ON clause with a natural join?_  
  expected: No, you cannot use the ON clause with a natural join because it is an implicit join that automatically creates the join condition based on matching column names and data types.
- **The resultant table of a natural join contains unique columns.**  
  quote: "The resultant table always contains unique columns."  
  follow-up: _Why is it important for the resultant table to have unique columns?_  
  expected: It is important because duplicate column names can cause confusion and ambiguity in the result, making it harder to interpret the data correctly.

### [Deadlocks in DBMS] Explain what a deadlock is in the context of database transactions.
*confidence 0.95 · easy · slides [1214, 1215, 1216, 1220, 1221, 1222]*

**Reference:** A deadlock occurs when two or more transactions are waiting for each other to release locks, creating a cycle where none can proceed. In such a situation, neither transaction can make progress. One of the transactions must be rolled back to resolve the deadlock. Deadlocks are a common issue in lock-based protocols where transactions hold locks and request new ones in a conflicting order.

**Key points** (slide quote → follow-up → expected answer):
- **A deadlock is a situation where two or more transactions are waiting for each other to release locks.**  
  quote: "Neither T3 or T4 can make progress — executing lock-S(B) causes T4 to wait for T3 to release its lock on B, while executing lock-X(A) causes T3 to wait for T4 to release its lock on A. Such a situation is called a deadlock."  
  follow-up: _What happens if two transactions are waiting for each other to release locks?_  
  expected: They become deadlocked and cannot proceed until one of them is rolled back.
- **Deadlock results in a cycle where no transaction can make progress.**  
  quote: "Such a situation is called a deadlock. One of the two transactions must rollback."  
  follow-up: _Why can't a deadlock be resolved without rolling back a transaction?_  
  expected: Because each transaction is waiting for the other to release a lock, and there's no way to break the cycle without one of them giving up its lock.
- **Deadlock resolution requires one transaction to be rolled back.**  
  quote: "One of the two transactions must rollback."  
  follow-up: _What is the implication of having to roll back a transaction in a deadlock?_  
  expected: Rolling back a transaction can lead to loss of work, but it is necessary to break the deadlock and allow other transactions to proceed.

### [Relational model] Explain how the relational model represents relationships between data and how this affects the design of a database schema.
*confidence 0.91 · medium · slides [350, 351, 352, 421, 822]*

**Reference:** The relational model represents relationships between data through the use of tables, rows, and columns, where tables represent relations, rows represent tuples, and columns represent attributes. The design of a database schema must consider how attributes are grouped into relations based on common sense or conceptual models like the ER model. This grouping affects the logical interpretation of the data and the efficiency of storage and retrieval.

**Key points** (slide quote → follow-up → expected answer):
- **The relational model uses tables, rows, and columns to represent relations, tuples, and attributes respectively.**  
  quote: "Table, row, and column used for relational model terms relation, tuple, and attribute respectively."  
  follow-up: _How does the structure of a table influence the way data is stored and accessed?_  
  expected: The structure of a table determines how data is organized and stored, which impacts query performance and data integrity.
- **The grouping of attributes into relations is based on the designer's intuition or conceptual models.**  
  quote: "We have assumed that attributes are grouped to form a relation schema by using the common sense of the database designer or by mapping a database schema design from a conceptual data model such as the ER data model."  
  follow-up: _What role does the conceptual data model play in the design of a relational schema?_  
  expected: The conceptual data model provides a foundation for organizing attributes into relations, ensuring that the schema reflects real-world entities and relationships.
- **The design of a relational schema affects both the logical interpretation and the physical storage of data.**  
  quote: "There are two levels at which we can discuss the goodness of relation schemas. The first is the logical (or conceptual) level—how users interpret the relation schemas and the meaning of their attributes. The second is the implementation (or physical storage) level—how the tuples in a base relation are stored and updated."  
  follow-up: _Why is it important to consider both logical and physical aspects when designing a relational schema?_  
  expected: Considering both logical and physical aspects ensures that the schema is both user-friendly and efficient in terms of storage and query performance.

### [Integrity constraints] Explain how referential integrity constraints work in SQL and why they are important for maintaining data consistency.
*confidence 0.91 · medium · slides [439, 440, 441, 442, 443, 444]*

**Reference:** Referential integrity constraints ensure that foreign key values in a table must match existing primary key values in another table, or be null. This prevents orphaned records and maintains consistency between related tables. These constraints are important because they enforce logical relationships between tables, ensuring that data remains accurate and consistent across the database.

**Key points** (slide quote → follow-up → expected answer):
- **Referential integrity constraints ensure that foreign key values must match existing primary key values or be null.**  
  quote: "Referential integrity constraints : The “foreign key “ must have a value that is already present as a primary key, or may be null"  
  follow-up: _What happens if you try to insert a foreign key value that doesn't exist in the referenced table?_  
  expected: The database will reject the insertion, as it violates the referential integrity constraint.
- **Referential integrity constraints help maintain logical relationships between tables.**  
  quote: "The “foreign key “ must have a value that is already present as a primary key, or may be null"  
  follow-up: _Why is it important for the database to enforce these relationships?_  
  expected: It ensures that data remains consistent and that relationships between tables are maintained, preventing invalid or orphaned data.
- **Referential integrity constraints can be modified with referential triggered actions like CASCADE, SET NULL, or SET DEFAULT.**  
  quote: "Attach referential triggered action clause - Options include SET NULL, CASCADE, and SET DEFAULT"  
  follow-up: _What is the purpose of the CASCADE option in referential integrity?_  
  expected: The CASCADE option automatically updates or deletes related records in other tables when a record is updated or deleted in the referenced table.

### [Weak entity sets] Explain how a weak entity set is identified in an ER diagram and why it must have total participation in its identifying relationship.
*confidence 0.91 · medium · slides [243, 244, 245, 246, 247, 248]*

**Reference:** A weak entity set is identified in an ER diagram by being depicted with a double rectangle, and its discriminator is underlined with a dashed line. It must have total participation in its identifying relationship because the existence of a weak entity depends entirely on the identifying entity set. This ensures that every instance of the weak entity is uniquely associated with an instance of the identifying entity.

**Key points** (slide quote → follow-up → expected answer):
- **A weak entity set is depicted with a double rectangle in an ER diagram.**  
  quote: "a weak entity set is depicted via a double rectangle"  
  follow-up: _What does the double rectangle in an ER diagram signify about the entity?_  
  expected: It signifies that the entity is a weak entity set, meaning its existence depends on another entity.
- **The discriminator of a weak entity set is underlined with a dashed line.**  
  quote: "discriminator is underlined with a dashed line"  
  follow-up: _What is the purpose of the dashed line underlining the discriminator?_  
  expected: It indicates that the discriminator is a unique attribute used to distinguish between instances of the weak entity set.
- **A weak entity set must have total participation in its identifying relationship.**  
  quote: "a weak entity set must have total participation in its identifying relationship set"  
  follow-up: _Why is total participation required for a weak entity set?_  
  expected: Because the existence of a weak entity depends entirely on the identifying entity set, ensuring that every instance of the weak entity is associated with an instance of the identifying entity.

### [Aggregate functions and GROUP BY] Explain how the GROUP BY clause interacts with aggregate functions in SQL queries, and why it is necessary to include grouping attributes in the SELECT clause.
*confidence 0.91 · medium · slides [359, 368, 369, 547, 560, 561]*

**Reference:** The GROUP BY clause partitions a relation into groups based on the values of one or more attributes. Each group is then processed independently by aggregate functions, which compute summary values for each group. It is necessary to include grouping attributes in the SELECT clause because these attributes define the groups, and the result must reflect the grouping structure. Without them, the output would not clearly associate the summary values with the correct group.

**Key points** (slide quote → follow-up → expected answer):
- **The GROUP BY clause partitions a relation into groups based on the values of one or more attributes.**  
  quote: "The EMPLOYEE relation is partitioned into groups in such a way that each group has tuples with the same value of Dno."  
  follow-up: _What happens if you don't use GROUP BY when you have multiple values in a column?_  
  expected: The query would return a single group containing all tuples, and aggregate functions would apply to the entire relation, not to individual groups.
- **Each group is processed independently by aggregate functions, which compute summary values for each group.**  
  quote: "The COUNT and AVG functions are applied to each group independently and are displayed in the result relation."  
  follow-up: _Why can't you apply an aggregate function to a non-grouped column in the SELECT clause?_  
  expected: Because the aggregate function would need to operate on a group, and without GROUP BY, there is no grouping structure to apply the function to.
- **It is necessary to include grouping attributes in the SELECT clause because these attributes define the groups.**  
  quote: "The SELECT clause must contain only the grouping attributes and aggregate functions applied on each group of tuples."  
  follow-up: _What if you omit a grouping attribute from the SELECT clause?_  
  expected: The query would fail because the result would not be able to distinguish between different groups, violating the requirement that the SELECT clause must include grouping attributes.

### [HAVING vs WHERE] Explain how the HAVING clause differs from the WHERE clause in terms of when they are applied and what they filter.
*confidence 0.91 · medium · slides [563, 567, 568, 569, 570]*

**Reference:** The WHERE clause is applied first to filter individual tuples before grouping, while the HAVING clause is applied after grouping to filter groups. The WHERE clause filters rows based on conditions on individual tuples, whereas the HAVING clause filters groups based on conditions on aggregated values. This distinction is crucial because it affects which data is included in the final result.

**Key points** (slide quote → follow-up → expected answer):
- **The WHERE clause is used to specify conditions for individual tuples.**  
  quote: "The WHERE clause is used to specify conditions for individual tuples."  
  follow-up: _What happens if you apply a condition on an aggregate function in the WHERE clause?_  
  expected: It would result in an error because the WHERE clause is applied before grouping and cannot reference aggregate functions.
- **The HAVING clause is used to specify conditions for groups of tuples.**  
  quote: "The HAVING clause is used to specify conditions for groups of tuples."  
  follow-up: _Can the HAVING clause be used to filter rows before grouping?_  
  expected: No, because the HAVING clause is applied after grouping and cannot filter individual rows.
- **The WHERE clause is executed first, then the HAVING clause.**  
  quote: "The rule is that the condition specified in the WHERE clause is executed first, to select the individual tuples, and then the HAVING clause is executed, to select groups of tuples."  
  follow-up: _Why is the order of execution important for the result of a query?_  
  expected: Because the WHERE clause filters the data before grouping, which affects what groups are available for the HAVING clause to filter.

### [Outer joins] Explain how a Full Outer Join differs from a Left or Right Outer Join, and why it might be useful in a database query.
*confidence 0.91 · medium · slides [588, 589, 590, 591, 592, 593]*

**Reference:** A Full Outer Join returns all records from both tables, including unmatched rows, which are padded with NULL values. This is different from a Left or Right Outer Join, which only returns all records from one table (left or right) and unmatched rows from the other. Full Outer Join is useful when you need to combine data from both tables regardless of whether there is a match, ensuring no data is lost.

**Key points** (slide quote → follow-up → expected answer):
- **A Full Outer Join returns all records from both tables, including unmatched rows, which are padded with NULL values.**  
  quote: "If we use a full outer join to combine two different tables, then we will get all the records from both tables."  
  follow-up: _What happens to rows that don't have a matching row in the other table?_  
  expected: They are included in the result with NULL values for the attributes of the other table.
- **Full Outer Join is useful when you need to combine data from both tables regardless of whether there is a match.**  
  quote: "Even though the records from both the tables are matched or not, the matching and nonmatching records from both the tables will be considered an output of the outer join in SQL."  
  follow-up: _Why would you want to include unmatched rows in your result?_  
  expected: To ensure that no data is lost when combining tables, especially when analyzing relationships or discrepancies between them.
- **Full Outer Join cannot be directly implemented in MySQL and requires combining LEFT and RIGHT Outer Joins with UNION.**  
  quote: "MySQL doesn't support FULL OUTER JOIN directly. So to implement full outer join in MySQL, we will execute two queries in a single query."  
  follow-up: _What is a common workaround for implementing Full Outer Join in MySQL?_  
  expected: Using a combination of LEFT OUTER JOIN and RIGHT OUTER JOIN with the UNION operator to merge their results.

### [Window functions] How do ranking window functions like RANK(), DENSE_RANK(), and ROW_NUMBER() differ in their behavior when there are ties in the data?
*confidence 0.91 · medium · slides [752, 753, 756, 757, 758, 759]*

**Reference:** Ranking window functions like RANK(), DENSE_RANK(), and ROW_NUMBER() differ in how they handle ties. RANK() assigns the same rank to tied rows and skips the next rank, as stated: 'Ties (equal values) get the same rank, and the next rank is skipped.' DENSE_RANK() also assigns the same rank to tied rows, but it does not skip the next rank, as noted: 'No ranks are skipped (this is the main difference from RANK()).' ROW_NUMBER() assigns unique sequential numbers to each row, regardless of ties, as explained: 'Unlike RANK() or DENSE_RANK(), there are no ties → every row gets its own distinct number, even if values are equal.'

**Key points** (slide quote → follow-up → expected answer):
- **RANK() skips the next rank after ties.**  
  quote: "Ties (equal values) get the same rank, and the next rank is skipped."  
  follow-up: _What happens to the rank of the next row if two rows are tied for first place?_  
  expected: The next row will receive a rank of 3, skipping rank 2.
- **DENSE_RANK() does not skip ranks after ties.**  
  quote: "No ranks are skipped (this is the main difference from RANK())."  
  follow-up: _If two rows are tied for first place, what rank will the next row get using DENSE_RANK()?_  
  expected: The next row will receive a rank of 2, as ranks are not skipped.
- **ROW_NUMBER() assigns unique ranks to all rows, even with ties.**  
  quote: "Unlike RANK() or DENSE_RANK(), there are no ties → every row gets its own distinct number, even if values are equal."  
  follow-up: _What is the rank of the next row if two rows have the same value and are using ROW_NUMBER()?_  
  expected: The next row will receive a rank of 2, even though the values are the same.

### [Stored procedures and functions] Compare and contrast the use of IN, OUT, and INOUT parameters in stored procedures, and explain how each affects the flow of data between the procedure and the calling program.
*confidence 0.91 · medium · slides [724, 725, 726, 727, 734, 735]*

**Reference:** IN parameters allow the calling program to pass data into the procedure, which is then used within the procedure. OUT parameters allow the procedure to return data back to the calling program. INOUT parameters allow both data to be passed into the procedure and modified values to be returned to the calling program. The use of these parameters affects how data is shared and how the procedure interacts with the calling program.

**Key points** (slide quote → follow-up → expected answer):
- **IN parameters are used to pass data into the procedure from the calling program.**  
  quote: "IN: It is the default mode. It takes a parameter as input, such as an attribute. When we define it, the calling program has to pass an argument to the stored procedure."  
  follow-up: _What happens if you try to modify an IN parameter inside the procedure?_  
  expected: The value of an IN parameter cannot be modified inside the procedure, as it is read-only.
- **OUT parameters allow the procedure to return data back to the calling program.**  
  quote: "OUT: It is used to pass a parameter as output. Its value can be changed inside the stored procedure, and the changed (new) value is passed back to the calling program."  
  follow-up: _How does the calling program access the value of an OUT parameter after the procedure completes?_  
  expected: The calling program accesses the value of an OUT parameter through a variable that is passed to the procedure, which is then updated by the procedure.
- **INOUT parameters allow data to be passed into the procedure and modified values to be returned to the calling program.**  
  quote: "INOUT: It is a combination of IN and OUT parameters. It means the calling program can pass the argument, and the procedure can modify the INOUT parameter, and then passes the new value back to the calling program."  
  follow-up: _What is the advantage of using an INOUT parameter over using separate IN and OUT parameters?_  
  expected: Using an INOUT parameter reduces the number of parameters needed, as it can both receive input and return output in a single parameter.

### [Minimal cover of FDs] Explain how to determine if a functional dependency in a set is redundant and how this relates to finding the minimal cover.
*confidence 0.91 · medium · slides [893, 895, 896, 898, 899, 924]*

**Reference:** To determine if a functional dependency is redundant, we check if it can be inferred from the remaining dependencies in the set. This is part of the process of finding the minimal cover, where we aim to remove any dependency that is logically implied by others. The minimal cover is a set of dependencies that is equivalent to the original set but with no redundancies. This process ensures that each dependency is necessary and contributes to the closure of the set.

**Key points** (slide quote → follow-up → expected answer):
- **We cannot remove any dependency from F and still have a set of dependencies that is equivalent to F.**  
  quote: "We cannot remove any dependency from F and still have a set of dependencies that is equivalent to F."  
  follow-up: _What happens if you remove a dependency and the closure remains the same?_  
  expected: The dependency is redundant and can be removed without affecting the closure of the set.
- **An attribute in a functional dependency is considered extraneous if we can remove it without changing the closure of the set of dependencies.**  
  quote: "An attribute in a functional dependency is considered extraneous attribute if we can remove it without changing the closure of the set of dependencies."  
  follow-up: _How would you determine if an attribute on the left-hand side of a dependency is extraneous?_  
  expected: By checking if the closure of the set remains unchanged after removing the attribute.
- **The minimal cover is a minimal set of dependencies that is equivalent to the original set.**  
  quote: "A minimal cover of a set of functional dependencies E is a minimal set of dependencies ( in the standard canonical form and without redundancy) that is equivalent to E."  
  follow-up: _Why is it important for the minimal cover to be equivalent to the original set?_  
  expected: Because the minimal cover must preserve all the logical implications of the original set, ensuring that no information is lost.

### [Lossless decomposition] Explain how lossless decomposition ensures that a relation can be reconstructed without data loss after decomposition.
*confidence 0.91 · medium · slides [931, 958]*

**Reference:** Lossless decomposition ensures that when decomposed relations are joined back together, the original relation can be perfectly reconstructed without any loss of data or introduction of spurious tuples. This is critical because it guarantees that no information is lost during the decomposition process. The decomposition must satisfy the non additive join property, which is extremely critical and must be achieved at any cost. This property ensures that the join of the decomposed relations results in the original relation without any extraneous data.

**Key points** (slide quote → follow-up → expected answer):
- **Lossless decomposition ensures that a relation can be reconstructed without any loss of data or introduction of spurious tuples.**  
  quote: "a lossless join refers to a property of a decomposition where a relation (table) is"  
  follow-up: _What happens if the decomposition is not lossless?_  
  expected: Spurious tuples may be introduced, leading to incorrect or incomplete data when the relations are joined back together.
- **The non additive join property is extremely critical and must be achieved at any cost.**  
  quote: "Property i) is extremely critical and must be achieved at any cost"  
  follow-up: _Why is the non additive join property considered more critical than dependency preservation?_  
  expected: Because it ensures the original relation can be accurately reconstructed, whereas dependency preservation is a desirable but optional property.
- **Lossless decomposition is essential for ensuring that the join of decomposed relations results in the original relation.**  
  quote: "when these smaller relations are joined back together, the original relation can"  
  follow-up: _What is the main consequence of not having a lossless decomposition?_  
  expected: The original relation cannot be accurately reconstructed, which leads to data loss or incorrect data being generated.

### [Transactions and ACID properties] Explain how the ACID properties ensure that a database remains consistent even when multiple transactions are executed concurrently.
*confidence 0.91 · medium · slides [1101, 1102]*

**Reference:** The ACID properties ensure consistency by enforcing that each transaction is executed in isolation, which means that intermediate results are hidden from other transactions. This isolation prevents conflicts and ensures that the database remains in a consistent state. Additionally, atomicity guarantees that all operations of a transaction are completed or none are, which prevents partial updates. Durability ensures that once a transaction is committed, its changes are permanently saved, maintaining consistency across system failures.

**Key points** (slide quote → follow-up → expected answer):
- **Isolation ensures that transactions do not interfere with each other.**  
  quote: "Although multiple transactions may execute concurrently, each transaction must be unaware of other concurrently executing transactions."  
  follow-up: _What happens if one transaction reads data that another transaction is modifying?_  
  expected: The database system must ensure that the first transaction does not see the intermediate state of the second transaction, which is achieved through isolation.
- **Atomicity ensures that all operations of a transaction are completed or none are.**  
  quote: "Atomicity. Either all operations of the transaction are properly reflected in the database or none are. This 'all-or-none' property is referred to as atomicity."  
  follow-up: _Why is it important that a transaction either fully completes or is rolled back entirely?_  
  expected: It ensures that the database remains in a consistent state, as partial updates could lead to data corruption.
- **Durability ensures that changes made by a committed transaction are permanent.**  
  quote: "Durability. After a transaction completes successfully, the changes it has made to the database must persist, even if there are system failures."  
  follow-up: _How does the system ensure that changes are not lost after a failure?_  
  expected: The system uses logging and recovery mechanisms to ensure that once a transaction is committed, its changes are written to durable storage.

### [Transaction states] Explain how a transaction can transition from the failed state to the terminated state, and what are the implications of each path.
*confidence 0.91 · medium · slides [1093, 1094, 1095]*

**Reference:** A transaction can transition from the failed state to the terminated state either by being killed or by being restarted. If a transaction is killed, it is permanently terminated and its changes are rolled back. If it is restarted, it is treated as a new transaction and may proceed from the active state again. The implications of these paths are that killing a transaction prevents any further processing, while restarting allows for potential recovery and reexecution.

**Key points** (slide quote → follow-up → expected answer):
- **A transaction can transition from the failed state to the terminated state by being killed.**  
  quote: "It can kill the transaction. It usually does so because of some internal logical error that can be corrected only by rewriting the application program, or because the input was bad, or because the desired data were not found in the database."  
  follow-up: _What happens to a transaction that is killed?_  
  expected: A killed transaction is permanently terminated and its changes are rolled back.
- **A transaction can transition from the failed state to the terminated state by being restarted.**  
  quote: "It can restart the transaction, but only if the transaction was aborted as a result of some hardware or software error that was not created through the internal logic of the transaction. A restarted transaction is considered to be a new transaction."  
  follow-up: _What is the difference between restarting and killing a transaction?_  
  expected: Restarting a transaction treats it as a new transaction, while killing it permanently terminates it.
- **Restarting a transaction allows for potential recovery and reexecution.**  
  quote: "Failed or aborted transactions may be restarted later—either automatically or after being resubmitted by the user—as brand new transactions."  
  follow-up: _Why would a transaction be restarted instead of being killed?_  
  expected: A transaction may be restarted if the failure was due to an external error, not an internal logical error, allowing it to be reexecuted as a new transaction.

### [Indexing basics] Explain how indexing improves the performance of SELECT operations, and why it's more efficient than a full table scan.
*confidence 0.91 · medium · slides [1047, 1048, 1049]*

**Reference:** Indexing improves the performance of SELECT operations by allowing the database to use a B-tree index to jump directly to qualifying records, rather than scanning the entire table. This reduces the cost from O(n) to O(log n), as only relevant blocks are read. Without an index, the database must check every record, which is slower for large tables.

**Key points** (slide quote → follow-up → expected answer):
- **Indexing allows the database to use a B-tree index to jump directly to qualifying records.**  
  quote: "MySQL uses the B-tree index to jump directly to qualifying records."  
  follow-up: _What happens if there is no index on the column used in the WHERE clause?_  
  expected: The database must perform a full table scan, checking every record, which is slower for large tables.
- **Indexing reduces the cost of query execution from O(n) to O(log n).**  
  quote: "Cost drastically reduced (O(log n))"  
  follow-up: _Why is the cost of a query with an index significantly lower than without one?_  
  expected: Because the index allows the database to directly access relevant blocks, rather than scanning every row.
- **Without an index, the database must perform a full table scan, which is inefficient for large tables.**  
  quote: "MySQL performs a full table scan — every record checked."  
  follow-up: _What is the main disadvantage of a full table scan?_  
  expected: It checks every record, leading to linear time complexity and poor performance on large tables.

### [CAP theorem] How does the CAP theorem influence the design trade-offs in distributed systems, particularly in the context of SQL versus NoSQL databases?
*confidence 0.91 · medium · slides [1247, 1248, 1249, 1251]*

**Reference:** The CAP theorem influences design trade-offs by forcing system designers to prioritize two out of the three properties—consistency, availability, and partition tolerance. In traditional SQL databases, consistency is prioritized through ACID properties, ensuring strong consistency. In contrast, NoSQL systems often prioritize availability and partition tolerance, accepting weaker consistency levels such as eventual consistency. This reflects a fundamental design choice between strict consistency and system availability in the face of network partitions.

**Key points** (slide quote → follow-up → expected answer):
- **The CAP theorem forces a trade-off between consistency, availability, and partition tolerance.**  
  quote: "It is not possible to guarantee all three of the desirable properties—consistency, availability, and partition tolerance—at the same time in a distributed system with data replication."  
  follow-up: _What happens if a system tries to guarantee all three properties?_  
  expected: It is not possible to guarantee all three properties simultaneously, as the theorem states that a distributed system must choose at least two of the three.
- **SQL databases prioritize consistency through ACID properties.**  
  quote: "In many traditional (SQL) applications, guaranteeing consistency through the ACID properties is important."  
  follow-up: _Why might a SQL database prioritize consistency over availability?_  
  expected: Because ACID properties ensure strong consistency, which is critical for transactional integrity in SQL databases.
- **NoSQL systems often prioritize availability and partition tolerance over strict consistency.**  
  quote: "weaker consistency levels are often used in NOSQL system instead of guaranteeing serializability. In particular, a form of consistency known as eventual consistency is often adopted in NOSQL systems."  
  follow-up: _What kind of consistency do NoSQL systems typically use?_  
  expected: NoSQL systems often use eventual consistency, which allows for weaker consistency levels in exchange for higher availability and partition tolerance.

### [Key-value stores and Redis] Explain how Redis uses key-value pairs to store data efficiently, and why this approach is suitable for certain applications.
*confidence 0.91 · medium · slides [1256, 1257, 1261, 1262]*

**Reference:** Redis uses key-value pairs to store data efficiently by keeping the entire database in memory, which allows for fast access and high performance. Each key is a unique string, and the value can be of various data structures like strings, hashes, or sets. This approach is suitable for applications that require quick read and write operations, such as caching or session storage, because the in-memory storage and rich data types enable efficient data retrieval and manipulation.

**Key points** (slide quote → follow-up → expected answer):
- **Redis stores its database entirely in memory (RAM), using the disk only for persistence.**  
  quote: "Redis holds its database entirely in the memory (RAM), using the disk only for persistence."  
  follow-up: _Why would storing data in memory be beneficial for certain applications?_  
  expected: Storing data in memory allows for faster access and lower latency, which is crucial for applications that require high performance, such as caching or real-time data processing.
- **Each key in Redis is a unique string and can be used to represent a namespace or hierarchy.**  
  quote: "Each key should be unique in Redis and : (colon) is used to show hierarchy (Similar to namespaces concept in OS)."  
  follow-up: _How does the use of colons in keys help with organizing data?_  
  expected: The use of colons allows for a hierarchical structure, similar to namespaces in an operating system, which helps in organizing data and avoiding key collisions.
- **Redis supports various data structures, which makes it versatile for different use cases.**  
  quote: "Redis has a relatively rich set of data types like hashes, lists, sets, strings etc."  
  follow-up: _Why is having a rich set of data types important for Redis?_  
  expected: Having a rich set of data types allows Redis to handle a wide range of use cases, from simple key-value storage to complex operations like maintaining sets or hashes, which are useful for caching, session management, and more.

### [Vector databases and embeddings] Explain how vector databases enable efficient similarity searches compared to traditional databases.
*confidence 0.91 · medium · slides [1398, 1399, 1400, 1402, 1419, 1423]*

**Reference:** Vector databases enable efficient similarity searches by storing data as high-dimensional vectors, which capture semantic relationships. This allows the database to find vectors most similar to a query vector using distance metrics like cosine similarity. Traditional relational databases, on the other hand, rely on exact matches and structured queries, which are less effective for semantic similarity searches.

**Key points** (slide quote → follow-up → expected answer):
- **Vector databases store data as high-dimensional vectors.**  
  quote: "Converts data into high-dimensional vectors"  
  follow-up: _How do traditional databases handle data representation?_  
  expected: Traditional databases store data in structured tabular formats, which are not suitable for representing complex semantic relationships.
- **Vector databases use distance metrics to find similar vectors.**  
  quote: "Distance Metrics: Used to quantify similarity between vectors Common metrics: Euclidean distance, Cosine similarity"  
  follow-up: _What is the role of distance metrics in vector databases?_  
  expected: Distance metrics help quantify how similar two vectors are, enabling the database to find the most relevant results.
- **Vector databases use indexing techniques to speed up similarity searches.**  
  quote: "Vector database used several Approximate Nearest Neighbor algorithms to speed up the similarity search process."  
  follow-up: _Why is indexing important for vector databases?_  
  expected: Indexing helps organize vectors in a way that allows for faster retrieval, which is critical for handling large datasets.

### [Common table expressions (CTE)] Explain how a recursive CTE works and why it is useful for hierarchical data.
*confidence 0.91 · medium · slides [628, 629, 642, 643, 644, 645]*

**Reference:** A recursive CTE works by combining an anchor member and a recursive member. The anchor member provides the initial result set, and the recursive member repeatedly references the CTE itself to build upon the results. This process continues until no more rows are returned. Recursive CTEs are useful for hierarchical data because they allow you to traverse relationships, such as employee-supervisor chains, by iteratively expanding the result set.

**Key points** (slide quote → follow-up → expected answer):
- **A recursive CTE combines an anchor member and a recursive member.**  
  quote: "A recursive CTE is one that references itself within that CTE."  
  follow-up: _What is the role of the anchor member in a recursive CTE?_  
  expected: The anchor member provides the initial result set that starts the recursion.
- **The recursive member repeatedly references the CTE itself.**  
  quote: "The recursive member: This is the query that refers to the CTE itself, creating the recursion."  
  follow-up: _How does the recursive member continue the process?_  
  expected: The recursive member continues the process by referencing the CTE itself and applying the same logic iteratively.
- **Recursive CTEs are useful for hierarchical data.**  
  quote: "A typical example of hierarchical data is a table that includes a list of employees like in the company database employee has recursive relationship, which represents the employee–supervisor relationship."  
  follow-up: _Why is a recursive CTE suitable for hierarchical data?_  
  expected: A recursive CTE is suitable for hierarchical data because it can traverse relationships, such as employee-supervisor chains, by iteratively expanding the result set.

### [NULL handling in SQL] How does SQL treat NULL values in arithmetic operations?
*confidence 0.91 · medium · slides [536, 537, 539]*

**Reference:** In SQL, the result of an arithmetic operation is NULL if any of the input values are NULL. This is because NULL represents an unknown or missing value, and performing arithmetic with an unknown value leads to an unknown result. This behavior is consistent with how SQL handles comparisons involving NULL, where the outcome is also considered UNKNOWN. The treatment of NULL in arithmetic operations reflects the broader challenge of handling unknown values in relational operations.

**Key points** (slide quote → follow-up → expected answer):
- **Arithmetic operations involving NULL result in NULL.**  
  quote: "Result of an arithmetic operation ( +,-,* or /) is NULL if any of the input values are NULL."  
  follow-up: _What happens if one operand is NULL and the other is a valid number in an arithmetic operation?_  
  expected: The result of the operation is NULL because the presence of NULL indicates an unknown value, and arithmetic with an unknown value cannot yield a known result.
- **NULL represents an unknown or missing value.**  
  quote: "NULL has one of the three representations: Unknown value: value exists but is not known, or it is not known whether or not the value exists."  
  follow-up: _Why is it problematic to treat NULL as a regular value in arithmetic operations?_  
  expected: Treating NULL as a regular value would introduce uncertainty into the result, making it impossible to determine the correctness of the arithmetic outcome.
- **SQL treats NULL as a special value that affects all operations.**  
  quote: "Null values present special problems in relational operations, including arithmetic operations, comparison operations, and set operations."  
  follow-up: _How does this special treatment of NULL affect the reliability of query results?_  
  expected: It reduces the reliability of query results because any operation involving NULL can return NULL, which may lead to unexpected or incomplete data.

### [Third normal form (3NF)] Explain how the definition of third normal form (3NF) addresses transitive dependencies in a relation schema.
*confidence 0.91 · medium · slides [943, 944, 954, 955, 956]*

**Reference:** Third normal form (3NF) addresses transitive dependencies by ensuring that no non-prime attribute is transitively dependent on the primary key. This is achieved by requiring that for every functional dependency X → A in the relation, either X is a superkey or A is a prime attribute. This prevents situations where a non-prime attribute depends on another non-prime attribute, which would create a transitive dependency.

**Key points** (slide quote → follow-up → expected answer):
- **A relation schema R is in third normal form (3NF) if whenever a FD X → A holds in R, then either X is a superkey of R or A is a prime attribute of R.**  
  quote: "A relation schema R is in third normal form (3NF) if whenever a FD X → A holds in R, then either: (a) X is a superkey of R, or (b) A is a prime attribute of R"  
  follow-up: _What happens if a non-prime attribute depends on another non-prime attribute?_  
  expected: This creates a transitive dependency, which violates 3NF because the non-prime attribute is not directly dependent on the primary key.
- **Transitive dependencies are resolved by ensuring that non-prime attributes are fully functionally dependent on every key of R and are non-transitively dependent on every key of R.**  
  quote: "A relation schema R is in third normal form (3NF) if every non-prime attribute in R meets both of these conditions: It is fully functionally dependent on every key of R and it is non-transitively dependent on every key of R"  
  follow-up: _Why is it important for a non-prime attribute to be non-transitively dependent on every key of R?_  
  expected: This ensures that the attribute is directly dependent on the key, avoiding any indirect or transitive dependencies that could lead to data redundancy and anomalies.
- **The definition of 3NF allows for some transitive dependencies if the dependent attribute is a candidate key.**  
  quote: "When Y is a candidate key, there is no problem with the transitive dependency. E.g., Consider EMP (SSN, Emp#, Salary ). Here, SSN -> Emp# -> Salary and Emp# is a candidate key."  
  follow-up: _Why is it acceptable for a candidate key to be part of a transitive dependency?_  
  expected: Because the candidate key is a prime attribute, the transitive dependency does not violate 3NF, as the definition allows for dependencies where the dependent is a prime attribute.

### [Denormalization] How does denormalization affect the balance between query performance and data consistency in a database?
*confidence 0.91 · medium · slides [933, 934, 935]*

**Reference:** Denormalization improves query performance by reducing the need for joins, which allows for faster data retrieval and simpler queries. However, it introduces the risk of data inconsistency because redundant data may not be updated across all relevant tables simultaneously. This trade-off means that while denormalization can speed up read operations, it requires careful management to avoid data redundancy and potential inaccuracies.

**Key points** (slide quote → follow-up → expected answer):
- **Denormalization improves query performance by reducing the need for joins.**  
  quote: "Retrieving data is faster since we do fewer joins"  
  follow-up: _What happens to query speed when joins are required?_  
  expected: Query speed decreases because joins are computationally expensive and can slow down data retrieval.
- **Denormalization introduces the risk of data inconsistency.**  
  quote: "Data may be inconsistent. Which is the 'correct' value for a piece of data?"  
  follow-up: _Why might data become inconsistent with denormalization?_  
  expected: Because redundant data may not be updated across all relevant tables simultaneously, leading to potential discrepancies.
- **Denormalization requires careful management to avoid data redundancy and inaccuracies.**  
  quote: "Denormalization can make update and insert code harder to write."  
  follow-up: _What challenge does denormalization introduce for data updates?_  
  expected: It makes update and insert code more complex, increasing the risk of errors and data inconsistency.

### [Set operations in SQL] How does the INTERSECT operator differ from the UNION operator in SQL, and what implications does this have for the data being combined?
*confidence 0.91 · medium · slides [330, 331, 521]*

**Reference:** The INTERSECT operator returns only the tuples that are present in both relations, whereas the UNION operator returns all tuples from both relations, eliminating duplicates. This difference means that INTERSECT requires the relations to be union compatible, just like UNION, but it also enforces that the result must contain only the common tuples. This has implications for data redundancy and the uniqueness of results.

**Key points** (slide quote → follow-up → expected answer):
- **INTERSECT returns only the tuples that are present in both relations.**  
  quote: "The result of R ∩ S, is a relation that includes all tuples that are in both R and S."  
  follow-up: _What happens if a tuple appears in one relation but not the other?_  
  expected: It would be excluded from the result of the INTERSECT operation.
- **INTERSECT and UNION both require the relations to be union compatible.**  
  quote: "These operations can be applied on the relations which are union compatible."  
  follow-up: _What would happen if the relations were not union compatible?_  
  expected: The operation would fail because the attributes would not match in type or number.
- **INTERSECT enforces uniqueness in the result, similar to UNION.**  
  quote: "Duplicate tuples are eliminated."  
  follow-up: _Does INTERSECT allow duplicate tuples in the result?_  
  expected: No, INTERSECT also eliminates duplicate tuples, ensuring the result contains only distinct values.

### [Deadlocks in DBMS] How does the Two-Phase Locking (2PL) protocol contribute to deadlock prevention, and what are the limitations of this approach?
*confidence 0.91 · medium · slides [1214, 1215, 1216, 1220, 1221, 1222]*

**Reference:** The Two-Phase Locking (2PL) protocol ensures that transactions follow a growing phase followed by a shrinking phase, which helps in achieving serializability. However, it does not guarantee freedom from deadlocks. The protocol allows for the possibility of deadlocks because transactions may hold locks and wait for other locks, creating a cycle. Therefore, additional mechanisms such as deadlock detection or prevention are required to handle such situations.

**Key points** (slide quote → follow-up → expected answer):
- **The Two-Phase Locking (2PL) protocol ensures that transactions follow a growing phase followed by a shrinking phase.**  
  quote: "Phase 1: Growing Phase :A transaction may obtain locks, but may not release any lock. Phase 2: Shrinking Phase : A transaction may release locks, but may not obtain any new locks"  
  follow-up: _What happens if a transaction tries to acquire a new lock during the shrinking phase?_  
  expected: The transaction would be rolled back, as acquiring new locks during the shrinking phase is not allowed in the Two-Phase Locking protocol.
- **The Two-Phase Locking protocol does not guarantee freedom from deadlocks.**  
  quote: "Two-phase locking does not ensure freedom from deadlocks."  
  follow-up: _Why does the Two-Phase Locking protocol not prevent deadlocks?_  
  expected: Because transactions may hold locks and wait for other locks, creating a cycle that leads to a deadlock.
- **Deadlock resolution in Two-Phase Locking requires additional mechanisms.**  
  quote: "Deadlock Detection: MySQL automatically detects and resolves deadlocks by rolling back one of the conflicting transactions to break the cycle."  
  follow-up: _What is the role of the lock manager in deadlock resolution?_  
  expected: The lock manager maintains a lock table and detects cycles in lock requests, which allows it to roll back a transaction to resolve a deadlock.

### [First normal form (1NF)] Explain how First Normal Form (1NF) ensures that a relation is properly structured for relational database systems.
*confidence 0.90 · medium · slides [938, 945, 957]*

**Reference:** First Normal Form (1NF) ensures that all attributes in a relation are atomic, meaning they contain only single, indivisible values. This prevents composite, multivalued, or nested attributes from being part of the relation. By enforcing atomicity, 1NF aligns with the fundamental definition of a relation in relational databases. Most RDBMSs only allow relations that are in 1NF, which ensures data can be efficiently stored and queried.

**Key points** (slide quote → follow-up → expected answer):
- **All attributes must be atomic.**  
  quote: "The domain of an attribute must include only atomic values (single value from the domain of attribute)."  
  follow-up: _What happens if an attribute contains multiple values in a single cell?_  
  expected: The relation would not be in 1NF, as it violates the requirement for atomic values.
- **Composite and multivalued attributes are disallowed.**  
  quote: "Disallows composite attributes, multivalued attributes, nested relations; attributes whose values for an individual tuple are non-atomic."  
  follow-up: _Why are composite attributes not allowed in 1NF?_  
  expected: Composite attributes contain multiple values in a single attribute, which violates the atomicity requirement of 1NF.
- **1NF is a prerequisite for higher normal forms.**  
  quote: "Every 2NF relation is in 1NF."  
  follow-up: _Why is 1NF considered a foundational normal form?_  
  expected: Because all higher normal forms (like 2NF and 3NF) require the relation to already be in 1NF, ensuring atomicity and proper structure.

### [Functional dependency] Explain how Armstrong’s Axioms can be used to infer new functional dependencies from a given set of dependencies.
*confidence 0.90 · medium · slides [851, 852, 853, 893, 989]*

**Reference:** Armstrong’s Axioms provide a systematic way to infer new functional dependencies by applying three rules: the reflexive rule, which allows us to infer trivial dependencies; the augmentation rule, which allows us to add attributes to both sides of a dependency; and the transitivity rule, which allows us to chain dependencies. These rules are both sound and complete, meaning they generate only valid dependencies and all valid dependencies can be derived from them.

**Key points** (slide quote → follow-up → expected answer):
- **Armstrong’s Axioms provide a systematic way to infer new functional dependencies.**  
  quote: "We can compute F+, the closure of F, by repeatedly applying Armstrong’s Axioms"  
  follow-up: _What is the purpose of using Armstrong’s Axioms?_  
  expected: The purpose is to systematically infer all functional dependencies that logically follow from a given set of dependencies.
- **The reflexive rule allows us to infer trivial dependencies.**  
  quote: "Reflexive rule: if β ⊆α, then α → β"  
  follow-up: _What kind of dependency does the reflexive rule allow us to infer?_  
  expected: It allows us to infer trivial dependencies where the right-hand side is a subset of the left-hand side.
- **The transitivity rule allows us to chain dependencies.**  
  quote: "Transitivity rule: if α → β, and β → γ, then α → γ"  
  follow-up: _How can the transitivity rule be used in practice?_  
  expected: It can be used to infer new dependencies by combining existing ones, such as if A → B and B → C, then we can infer A → C.

### [Update anomalies] Explain how update anomalies can occur in a database schema and why they are problematic.
*confidence 0.90 · medium · slides [806, 807, 808, 811]*

**Reference:** Update anomalies occur when redundant data is stored in multiple places, and an update in one place is not reflected in all others, leading to inconsistent data. This is problematic because it can result in loss of essential information or incorrect data. For example, changing an instructor’s name in one record without updating all related records can cause inconsistencies.

**Key points** (slide quote → follow-up → expected answer):
- **Update anomalies occur when redundant data is stored in multiple places.**  
  quote: "Redundant data causes problems with: update anomalies: Storing natural joins of base relations leads to an additional problem referred to as update anomalies."  
  follow-up: _What happens if the same data is stored in two different tables?_  
  expected: It can lead to inconsistencies if the data is not updated in all places, causing update anomalies.
- **Update anomalies result in inconsistent data.**  
  quote: "If we forget one row → inconsistent data."  
  follow-up: _Why would updating a single record cause problems in the database?_  
  expected: Because the same data is stored in multiple places, and an update in one place may not be reflected in all others, leading to inconsistencies.
- **Update anomalies are a consequence of poor schema design.**  
  quote: "Design a schema that does not suffer from the insertion, deletion and update anomalies."  
  follow-up: _What is one way to avoid update anomalies in a database?_  
  expected: By normalizing the schema to eliminate redundant data and ensure that each piece of information is stored in only one place.

### [Relationships and cardinality] Explain how cardinality ratios affect the interpretation of a relationship between two entity sets in a database design.
*confidence 0.90 · medium · slides [209, 210, 211, 212, 213, 214]*

**Reference:** Cardinality ratios define the number of entities in one set that can be associated with each entity in another set. For example, a one-to-many relationship means one entity in the first set can be associated with many in the second, but each in the second is associated with at most one in the first. This affects how data is structured and how relationships are enforced in the database. A many-to-many relationship allows multiple entities in both sets to be associated with each other, which often requires an intermediary relationship table.

**Key points** (slide quote → follow-up → expected answer):
- **Cardinality ratios define the number of entities in one set that can be associated with each entity in another set.**  
  quote: "Mapping cardinalities, or cardinality ratios, express the number of entities to which another entity can be associated via a relationship set."  
  follow-up: _What happens if a relationship allows an entity in one set to be associated with multiple entities in another set?_  
  expected: This is a many-to-one or many-to-many relationship, depending on whether the reverse is also allowed.
- **A one-to-many relationship means one entity in the first set can be associated with many in the second, but each in the second is associated with at most one in the first.**  
  quote: "One-to-many (1:N): An entity in A is associated with any number (zero or more) of entities in B. An entity in B, however, can be associated with at most one entity in A."  
  follow-up: _Can a student have multiple advisors if the relationship is one-to-many?_  
  expected: No, a student can have at most one advisor in a one-to-many relationship.
- **A many-to-many relationship allows multiple entities in both sets to be associated with each other.**  
  quote: "Many-to-many (M:N): An entity in A is associated with any number (zero or more) of entities in B, and an entity in B is associated with any number (zero or more) of entities in A."  
  follow-up: _Why is an intermediary table often used for many-to-many relationships?_  
  expected: Because a many-to-many relationship cannot be directly represented in a relational database without introducing an intermediate entity to hold the associations.

### [ER to relational mapping] How does the mapping of a many-to-many relationship differ from that of a one-to-many relationship in ER to relational mapping?
*confidence 0.88 · medium · slides [267, 268]*

**Reference:** In ER to relational mapping, a many-to-many relationship is mapped to a separate relation schema that includes foreign keys referencing both participating entity sets. This is because a many-to-many relationship cannot be directly represented as a single relation without creating an intermediate entity. In contrast, a one-to-many relationship is handled by adding a foreign key to the 'many' side of the relationship, without requiring a new relation schema.

**Key points** (slide quote → follow-up → expected answer):
- **A many-to-many relationship requires a separate relation schema with foreign keys to both entity sets.**  
  quote: "Mapping of relational sets... M:N or many-to-many"  
  follow-up: _Why can't a many-to-many relationship be directly represented in a single relation?_  
  expected: Because it would require a single relation to represent multiple combinations, which is not possible without an intermediate entity.
- **A one-to-many relationship is handled by adding a foreign key to the 'many' side without a new relation schema.**  
  quote: "Mapping of relational sets... 1:N or one-to-many or many-to-one"  
  follow-up: _What is the effect of adding a foreign key to the 'many' side of a one-to-many relationship?_  
  expected: It allows the database to enforce referential integrity and correctly represent the one-to-many relationship.
- **The distinction between these two types of relationships affects how they are represented in the relational schema.**  
  quote: "For each relationship set in the database design, there is a unique relation schema to which we assign the name of the corresponding relationship set."  
  follow-up: _What happens if you try to map a many-to-many relationship without an intermediate relation?_  
  expected: It would result in data redundancy and an inability to correctly represent the many-to-many relationship.

### [Primary key] Explain how the primary key of a weak entity set is determined, and what role the identifying relationship plays in this process.
*confidence 0.85 · hard · slides [227, 247, 271, 272, 273, 274] · ⚠ NEEDS REVIEW*

**Reference:** The primary key of a weak entity set is formed by combining the primary key of the identifying entity set with the discriminator of the weak entity set. This ensures that each weak entity instance is uniquely identified in relation to its identifying entity. The identifying relationship ensures that the weak entity is always associated with a valid instance of the identifying entity, which is enforced through a foreign key constraint.

**Key points** (slide quote → follow-up → expected answer):
- **The primary key of a weak entity set includes the primary key of the identifying entity set.**  
  quote: "The primary key of the section is formed by the primary key of the identifying entity set (that is, course), plus the discriminator of the weak entity set (that is, section)."  
  follow-up: _What happens if the identifying entity set doesn't have a unique identifier?_  
  expected: The identifying entity set must have a primary key to uniquely identify its instances, as the weak entity relies on it for uniqueness.
- **The discriminator of the weak entity set is part of the primary key.**  
  quote: "Primary key is {course id, sec id, year, semester}."  
  follow-up: _Why is the discriminator necessary in the primary key of a weak entity?_  
  expected: The discriminator distinguishes between different instances of the weak entity that share the same identifying entity, ensuring uniqueness.
- **The identifying relationship enforces a foreign key constraint.**  
  quote: "Foreign key constraint is also added to the relational schema of the weak entity (to the primary-key of the identifying entity set)."  
  follow-up: _What would happen if the foreign key constraint was not enforced?_  
  expected: Without the foreign key constraint, a weak entity could exist without a corresponding identifying entity, violating the integrity of the relationship.
- **The combination of the identifying entity's primary key and the weak entity's discriminator ensures uniqueness.**  
  quote: "The primary key consists of the primary key of Identifying/strong entity set union with the discriminator of weak entity."  
  follow-up: _Can a weak entity have a primary key that doesn't include the identifying entity's primary key?_  
  expected: No, because the weak entity's existence depends on the identifying entity, and its primary key must include the identifying entity's primary key to ensure uniqueness.

### [Data independence] Explain what physical data independence means in the context of a database system.
*confidence 0.82 · easy · slides [63, 64, 65, 66, 67, 68]*

**Reference:** Physical data independence refers to the characteristic of being able to modify the physical schema without any alterations to the conceptual or logical schema, done for optimization purposes. This allows database administrators to make changes to the storage structure, such as switching from sequential to random access files, without affecting the logical structure or the applications that use the database. This ensures that changes in storage systems do not disrupt the functionality of the database or the applications relying on it.

**Key points** (slide quote → follow-up → expected answer):
- **Physical data independence allows changes to the physical schema without affecting the logical or conceptual schema.**  
  quote: "It refers to the characteristic of being able to modify the physical schema without any alterations to the conceptual or logical schema, done for optimization purposes."  
  follow-up: _What happens if the physical schema is changed without physical data independence?_  
  expected: Without physical data independence, changes to the storage system could break existing queries, applications, and interfaces, requiring extensive modifications to the application layer.
- **Physical data independence supports easier maintenance and upgrades of the database system.**  
  quote: "It allows for easier maintenance, upgrades, and performance enhancements without disrupting the application layer."  
  follow-up: _How does physical data independence help in the long-term management of a database?_  
  expected: Physical data independence allows for easier maintenance and upgrades of the storage system without requiring changes to the logical or application layers, reducing the risk of disruptions and increasing system flexibility.

### [Schema vs instance] Explain the difference between a database schema and a database instance.
*confidence 0.82 · easy · slides [71, 74, 75, 116, 119, 120]*

**Reference:** The database schema defines the structure of the database, including tables, attributes, and relationships. The database instance is the actual data stored in the database at a particular moment. The schema remains constant unless changed, while the instance changes as data is inserted, deleted, or modified.

**Key points** (slide quote → follow-up → expected answer):
- **The schema defines the structure of the database.**  
  quote: "The overall design of the database is called the database schema."  
  follow-up: _What happens if the structure of the database changes?_  
  expected: The schema would need to be updated, which changes the design of the database.
- **The instance is the collection of data stored at a particular moment.**  
  quote: "The collection of information stored in the database at a particular moment is called an instance of the database."  
  follow-up: _Can the instance ever be the same as the schema?_  
  expected: No, the instance is data, while the schema is the structure, so they are fundamentally different.

### [Participation constraints] Explain what total participation means in the context of database relationships.
*confidence 0.82 · easy · slides [220, 221]*

**Reference:** Total participation means that every entity in an entity set must participate in at least one relationship in a relationship set. This is often required by business rules, such as a university requiring every student to have at least one advisor. Total participation is indicated by double lines in the relationship set, showing that no student can exist without being associated with an advisor.

**Key points** (slide quote → follow-up → expected answer):
- **Total participation requires every entity in an entity set to participate in at least one relationship.**  
  quote: "The participation of an entity set E in a relationship set R is said to be total if every entity in E must participate in at least one relationship in R."  
  follow-up: _What happens if an entity does not participate in a relationship when total participation is required?_  
  expected: It violates the participation constraint, meaning the database design is invalid under that rule.
- **Total participation is visually indicated by double lines in the relationship set.**  
  quote: "We indicate the total participation of an entity in a relationship set using double lines."  
  follow-up: _What is the significance of double lines in a relationship set?_  
  expected: Double lines indicate that the participation of an entity in the relationship set is total, meaning every entity must participate.

### [Equivalence of sets of FDs] Explain what it means for two sets of functional dependencies to be equivalent.
*confidence 0.82 · easy · slides [882, 883, 885, 886, 887, 889]*

**Reference:** Two sets of functional dependencies E and F are equivalent if E+ = F+, meaning every FD in E can be inferred from F and every FD in F can be inferred from E. This implies that both sets cover each other, which is the definition of equivalence. To determine this, we check if each set covers the other by comparing closures of attributes.

**Key points** (slide quote → follow-up → expected answer):
- **Equivalence requires that both sets cover each other.**  
  quote: "Equivalence means that every FD in E can be inferred from F, and every FD in F can be inferred from E; that is, E is equivalent to F if both the conditions—E covers F and F covers E—hold."  
  follow-up: _Why is it necessary for both sets to cover each other?_  
  expected: Because if only one set covers the other, they are not equivalent. Equivalence requires mutual inference, ensuring that neither set is more powerful than the other in terms of deriving functional dependencies.
- **Covering is determined by comparing closures of attributes.**  
  quote: "We can determine whether F covers E by calculating X+ with respect to F for each FD X →Y in E, and then checking whether this X+ includes the attributes in Y."  
  follow-up: _How do you check if one set covers another?_  
  expected: For each FD in the set being covered, compute the closure of its left-hand side using the covering set. If the closure includes all attributes on the right-hand side, the covering holds.

### [Weak entity sets] Suppose we have a weak entity set that is identified by more than one strong entity set. How does this affect the primary key of the weak entity set, and what implications does this have for the design of the database schema?
*confidence 0.82 · hard · slides [243, 244, 245, 246, 247, 248] · ⚠ NEEDS REVIEW*

**Reference:** The primary key of a weak entity set consists of the union of the primary keys of the identifying entity sets, plus the discriminator of the weak entity set. This ensures that each instance of the weak entity is uniquely identified by the combination of its identifying entities and its own discriminator. This design allows for a more precise and flexible representation of relationships where a weak entity depends on multiple strong entities for its existence.

**Key points** (slide quote → follow-up → expected answer):
- **The primary key of a weak entity set includes the primary keys of all identifying entity sets.**  
  quote: "The primary key of the weak entity set would consist of the union of the primary keys of the identifying entity sets, plus the discriminator of the weak entity set."  
  follow-up: _What happens if a weak entity is identified by two different strong entity sets?_  
  expected: The weak entity's primary key would include the primary keys of both strong entity sets, ensuring that each instance is uniquely identified by the combination of these keys and the discriminator.
- **A weak entity set can be identified by more than one strong entity set.**  
  quote: "It is also possible to have a weak entity set with more than one identifying entity set. A particular weak entity would then be identified by a combination of entities, one from each identifying entity set."  
  follow-up: _Why would a weak entity need to be identified by more than one strong entity set?_  
  expected: This allows for a more complex and accurate representation of real-world dependencies, where an entity's existence is contingent on multiple other entities.
- **The design of the database schema must reflect the combination of identifying entities and the discriminator.**  
  quote: "The primary key of the weak entity set would consist of the union of the primary keys of the identifying entity sets, plus the discriminator of the weak entity set."  
  follow-up: _How does this affect the way relationships are modeled in the database?_  
  expected: It ensures that the relationships are explicitly modeled through the primary key, which includes the identifying entities and the discriminator, making the dependencies clear and enforceable.

### [Triggers] What happens if a trigger is defined as BEFORE INSERT and the same table is modified in a cascading foreign key constraint?
*confidence 0.82 · hard · slides [707, 708, 709, 712, 713, 714] · ⚠ NEEDS REVIEW*

**Reference:** If a trigger is defined as BEFORE INSERT on a table and the same table is modified via a cascading foreign key constraint, the trigger will execute before the insert operation is applied. The trigger code will run for each row affected by the insert, including those inserted due to the cascade. However, if the trigger raises an error, it will prevent the entire operation, including the cascading inserts, from completing.

**Key points** (slide quote → follow-up → expected answer):
- **The trigger executes before the insert operation is applied.**  
  quote: "The keyword BEFORE specifies that the trigger execution occurs before the triggering operation (in this case, insertion of tuples in the Marks_sample relation) is executed."  
  follow-up: _What happens if the trigger is defined as BEFORE and the insert operation is part of a cascading foreign key constraint?_  
  expected: The trigger will execute before the insert operation is applied, including any inserts caused by the cascade.
- **The trigger code runs for each row affected by the insert, including cascading inserts.**  
  quote: "The trigger action gets executed for every row that is inserted. This is specified by the FOR EACH ROW clause."  
  follow-up: _Does the trigger run for rows inserted due to a foreign key cascade?_  
  expected: Yes, the trigger runs for each row affected by the insert, including those inserted due to a foreign key cascade.
- **Raising an error in the trigger will prevent the entire operation, including cascading inserts.**  
  quote: "If the specified condition is satisfied, the trigger raises an error, an appropriate error message is displayed and the tuple is not inserted (trigger execution occurs before insertion)."  
  follow-up: _What happens if the trigger raises an error during a cascading insert?_  
  expected: The entire operation, including the cascading inserts, will be rolled back and the error will be raised.

### [Isolation levels] How does the SERIALIZABLE isolation level address the phantom record problem compared to REPEATABLE READ?
*confidence 0.82 · hard · slides [1123, 1124, 1125, 1126] · ⚠ NEEDS REVIEW*

**Reference:** The SERIALIZABLE isolation level guarantees complete isolation from other transactions, which means it avoids all three problems, including the phantom record problem. In contrast, REPEATABLE READ does not prevent the phantom record problem. The phantom record problem occurs when a transaction T1 reads a set of rows, and another transaction T2 inserts a new row that satisfies T1's WHERE clause. If the system cannot ensure the correct behavior, the phantom record may or may not be seen by T1. SERIALIZABLE ensures that the phantom record is not seen if the equivalent serial order is T1 followed by T2.

**Key points** (slide quote → follow-up → expected answer):
- **SERIALIZABLE guarantees complete isolation from other transactions.**  
  quote: "SERIALIZABLE: Highest isolation, guarantees complete isolation from other"  
  follow-up: _What happens if a transaction is running at the REPEATABLE READ level and another transaction inserts a new row that matches its WHERE clause?_  
  expected: The phantom record may or may not be seen by the first transaction, depending on the system's implementation.
- **The phantom record problem occurs when a transaction T1 reads a set of rows, and another transaction T3 inserts a new row that satisfies T1's WHERE clause.**  
  quote: "Suppose that a transaction T2 inserts a new row r that also satisfies the WHERE clause condition used in T1, into the table used by T1. The record r is called a phantom record because it was not there when T1 starts but is there when T1 ends."  
  follow-up: _What is the significance of the WHERE clause in the context of the phantom record problem?_  
  expected: The WHERE clause determines which rows are considered in the transaction's read, and a phantom record is one that satisfies this condition but was not present at the start of the transaction.
- **REPEATABLE READ does not prevent the phantom record problem.**  
  quote: "The equivalent serial order is T1 followed by T2, then the record r should not be seen; but if it is T2 followed by T1, then the phantom record should be in the result given to T1. If the system cannot ensure the correct behavior, then it does not deal with the phantom record problem."  
  follow-up: _Why is the phantom record problem more complex than dirty reads or non-repeatable reads?_  
  expected: The phantom record problem involves changes to the set of rows that a transaction sees, which is more complex than changes to individual rows or uncommitted data.

### [Super key and candidate key] Explain the difference between a superkey and a candidate key.
*confidence 0.82 · easy · slides [240, 241, 242, 926, 936, 937]*

**Reference:** A superkey is a set of attributes that uniquely identifies a tuple in a relation. A candidate key is a superkey that is minimal, meaning no attribute can be removed without losing the uniqueness property. The key difference is that a candidate key is a minimal superkey, while a superkey may contain extra attributes. A relation can have multiple candidate keys, but only one is chosen as the primary key. The definition of a superkey is broader than that of a candidate key.

**Key points** (slide quote → follow-up → expected answer):
- **A superkey is a set of attributes that uniquely identifies a tuple in a relation.**  
  quote: "A superkey of a relation schema R = {A1, A2, ...., An} is a set of attributes S (subset-of R) with the property that no two tuples t1 and t2 in any legal relation state r of R will have t1[S] = t2[S]."  
  follow-up: _What happens if you remove an attribute from a superkey?_  
  expected: The superkey may no longer be a superkey, but it could still be a superkey if the remaining attributes still uniquely identify tuples.
- **A candidate key is a minimal superkey.**  
  quote: "A key K is a superkey with the additional property that removal of any attribute from K will cause K not to be a superkey any more (ie minimal superkey)."  
  follow-up: _Can a relation have more than one candidate key?_  
  expected: Yes, a relation can have multiple candidate keys, and each is a minimal superkey that uniquely identifies tuples.

### [Vector databases and embeddings] What trade-off does the use of Approximate Nearest Neighbor (ANN) algorithms in vector databases introduce, and how does it affect the system's performance?
*confidence 0.82 · hard · slides [1398, 1399, 1400, 1402, 1419, 1423] · ⚠ NEEDS REVIEW*

**Reference:** The use of ANN algorithms in vector databases introduces a trade-off between search accuracy and computational efficiency. These algorithms prioritize speed and scalability for large, high-dimensional datasets by approximating the nearest neighbors rather than finding exact matches. This trade-off allows vector databases to handle massive data volumes and real-time queries more effectively, though it may slightly reduce the precision of similarity search results.

**Key points** (slide quote → follow-up → expected answer):
- **ANN algorithms prioritize speed and scalability over exact search accuracy.**  
  quote: "Vector databases used several Approximate Nearest Neighbor algorithms to speed up the similarity search process."  
  follow-up: _What is the main benefit of using ANN algorithms in vector databases?_  
  expected: The main benefit is enabling faster and more scalable similarity searches for large, high-dimensional datasets.
- **ANN algorithms are suitable for large, high-dimensional data.**  
  quote: "ANN (Approximate Nearest Neighbors): Finds approximate nearest neighbors; improves efficiency for large, high-dimensional data."  
  follow-up: _Why would a vector database use ANN algorithms instead of exact nearest neighbor methods?_  
  expected: Because ANN algorithms improve efficiency for large, high-dimensional data, making similarity searches faster and more scalable.
- **The trade-off affects the precision of similarity search results.**  
  quote: "ANN (Approximate Nearest Neighbors): Finds approximate nearest neighbors."  
  follow-up: _How does using ANN algorithms impact the accuracy of search results?_  
  expected: Using ANN algorithms may slightly reduce the precision of search results, as they find approximate rather than exact nearest neighbors.

### [First normal form (1NF)] What is the significance of disallowing nested relations in the context of First Normal Form (1NF)?
*confidence 0.81 · hard · slides [938, 945, 957] · ⚠ NEEDS REVIEW*

**Reference:** Disallowing nested relations in 1NF ensures that all attribute values are atomic and indivisible, which is essential for relational database systems to process and query data efficiently. This restriction prevents the storage of complex or hierarchical data structures within a single attribute, which could complicate data retrieval and integrity. By enforcing atomicity, 1NF aligns with the relational model's requirement that each cell in a table contain a single value from the domain of that attribute.

**Key points** (slide quote → follow-up → expected answer):
- **Nested relations are disallowed in 1NF to ensure atomicity of attribute values.**  
  quote: "Disallows ... nested relations; attributes whose values for an individual tuple are non-atomic"  
  follow-up: _Why would allowing nested relations cause problems for relational databases?_  
  expected: Allowing nested relations would introduce non-atomic values, making it difficult to perform standard relational operations like selection and join, which require flat, atomic data structures.
- **1NF requires that each attribute's domain contains only atomic values.**  
  quote: "The domain of an attribute must include only atomic values (single value from the domain of attribute)"  
  follow-up: _How does the requirement for atomic values in 1NF affect data storage and querying?_  
  expected: Atomic values ensure that each piece of data is stored in a single cell, simplifying data storage and enabling precise querying and manipulation through relational operations.
- **1NF is a prerequisite for higher normal forms and relational database design.**  
  quote: "Most RDBMSs allow only those relations to be defined that are in First Normal Form"  
  follow-up: _What would happen if a database schema violated the 1NF requirement for atomicity?_  
  expected: A database schema that violates 1NF would not be compatible with standard relational database systems, leading to potential data integrity issues and difficulties in querying and maintaining the data.

### [Functional dependency] Explain how the concept of closure of functional dependencies can be used to determine whether a set of functional dependencies is minimal.
*confidence 0.80 · hard · slides [851, 852, 853, 893, 989] · ⚠ NEEDS REVIEW*

**Reference:** The closure of a set of functional dependencies, F+, includes all dependencies logically implied by F. To determine if a set of FDs is minimal, we must ensure that no dependency can be removed without changing the closure. This requires checking if any attribute in a dependency is extraneous, meaning it can be removed without affecting the closure. If an attribute is found to be extraneous, the set is not minimal. The closure helps us verify that removing an FD or an attribute does not alter the logical implications of the set.

**Key points** (slide quote → follow-up → expected answer):
- **The closure of a set of FDs includes all dependencies logically implied by that set.**  
  quote: "The closure of F, denoted by F+, is the set of all functional dependencies logically implied by F."  
  follow-up: _What happens if a dependency is removed from a set and the closure remains unchanged?_  
  expected: The dependency is considered extraneous, and the set can be minimized by removing it.
- **An extraneous attribute in a FD is one that can be removed without changing the closure of the set.**  
  quote: "An attribute in a functional dependency is considered extraneous attribute if we can remove it without changing the closure of the set of dependencies."  
  follow-up: _How would you determine if an attribute is extraneous in a functional dependency?_  
  expected: By checking if the closure of the set remains unchanged after removing the attribute.
- **A minimal set of FDs is one where no dependency or attribute can be removed without altering the closure.**  
  quote: "We can shrink or reduce the set F to its minimal form so that the minimal set is still equivalent to the original set F."  
  follow-up: _What is the purpose of finding a minimal cover of a set of FDs?_  
  expected: To simplify the set of dependencies while preserving all logical implications, making it easier to analyze and understand the database schema.

### [Nested and correlated subqueries] What is the significance of using EXISTS or NOT EXISTS with correlated subqueries, and how does it influence the evaluation of the outer query?
*confidence 0.80 · hard · slides [621, 661, 662, 663] · ⚠ NEEDS REVIEW*

**Reference:** The EXISTS and NOT EXISTS operators are Boolean functions that check whether the result of a nested query is empty or not. When used with correlated subqueries, they allow the outer query to determine whether a condition is met based on the existence of tuples in the nested query. This can lead to more efficient query execution because the nested query stops evaluating as soon as a matching tuple is found, which can reduce unnecessary computation.

**Key points** (slide quote → follow-up → expected answer):
- **The EXISTS function in SQL is used to check whether the result of a nested query is empty (contains no tuples) or not.**  
  quote: "The EXISTS function in SQL is used to check whether the result of a nested query is empty (contains no tuples) or not."  
  follow-up: _Can you explain how EXISTS affects the evaluation of a correlated subquery?_  
  expected: EXISTS stops the evaluation of the nested query as soon as a tuple is found, which can improve performance by avoiding unnecessary computation.
- **The result of EXISTS is True if the nested query result contains at least one tuple, and False if the nested query result contains no tuples.**  
  quote: "The result of EXISTS is True if the nested query result contains at least one tuple, and False if the nested query result contains no tuples."  
  follow-up: _What happens if the nested query returns no tuples in the context of EXISTS?_  
  expected: The EXISTS condition would evaluate to False, and the outer query would not select that tuple.
- **EXISTS and NOT EXISTS are typically used in conjunction with a correlated nested query.**  
  quote: "EXISTS and NOT EXISTS are typically used in conjunction with a correlated nested query."  
  follow-up: _Why would you use NOT EXISTS instead of EXISTS in a correlated subquery?_  
  expected: NOT EXISTS is used when you want to ensure that no tuples from the nested query match, such as in cases where you want to exclude certain records from the outer query.

### [Schema vs instance] How does the analogy between a program's variable declarations and a database's schema help in understanding the difference between schema and instance?
*confidence 0.78 · medium · slides [71, 74, 75, 116, 119, 120]*

**Reference:** The analogy helps clarify that the schema is like variable declarations, which define the structure and types of data, while the instance is like the current value of those variables. This distinction shows that the schema is static and defines the database's structure, while the instance is dynamic and represents the actual data stored at any given time. The analogy also emphasizes that the schema remains unchanged unless modified, while the instance changes as data is inserted, deleted, or updated.

**Key points** (slide quote → follow-up → expected answer):
- **The schema is analogous to variable declarations in a program.**  
  quote: "Database Schema => variable declarations along with the associated type definitions"  
  follow-up: _What would happen if the variable declarations in a program changed without updating the values?_  
  expected: The program would no longer compile or run correctly, as the structure of the data would be inconsistent with the values being used.
- **The instance is analogous to the value of a variable at a particular moment.**  
  quote: "Instances => Value of the variable at a particular point in time in the program"  
  follow-up: _How does this analogy explain the fact that the instance can change over time?_  
  expected: Just as a variable's value can change during program execution, the instance of a database can change as data is inserted, deleted, or modified.

### [Foreign key] How do the `ON DELETE CASCADE` and `ON UPDATE CASCADE` options affect the child table when changes are made to the parent table?
*confidence 0.78 · medium · slides [446, 449, 450, 476, 716, 717]*

**Reference:** The `ON DELETE CASCADE` option automatically deletes corresponding rows in the child table when a row in the parent table is deleted. The `ON UPDATE CASCADE` option automatically updates corresponding rows in the child table when a row in the parent table is updated. Both options ensure that the child table remains consistent with the parent table by propagating the changes.

**Key points** (slide quote → follow-up → expected answer):
- **The `ON DELETE CASCADE` option deletes corresponding rows in the child table when a row in the parent table is deleted.**  
  quote: "ON DELETE CASCADE: SQL Server deletes the rows in the child table that is corresponding to the row deleted from the parent table."  
  follow-up: _What happens to the child table if you delete a row in the parent table and `ON DELETE CASCADE` is not specified?_  
  expected: The child table remains unchanged, and an error may be raised if the foreign key constraint is violated.
- **The `ON UPDATE CASCADE` option updates corresponding rows in the child table when a row in the parent table is updated.**  
  quote: "ON UPDATE CASCADE: SQL Server updates the corresponding rows in the child table when the rows in the parent table are updated."  
  follow-up: _Can `ON UPDATE CASCADE` be used to automatically update the child table when the primary key of the parent table changes?_  
  expected: Yes, `ON UPDATE CASCADE` ensures that the child table is automatically updated to reflect the new primary key value in the parent table.

### [Full-text search] Explain how full-text search in MySQL differs from a simple string search like LIKE or REGEXP, and why full-text search is more effective for certain tasks.
*confidence 0.78 · medium · slides [777, 778, 779, 781, 782, 783]*

**Reference:** Full-text search in MySQL uses a special index and natural language processing to rank results by relevance, while LIKE and REGEXP do not use indexes and only check for substring matches. Full-text search supports features like stopwords filtering, word boundary detection, and boolean logic, making it more effective for searching large text fields and returning relevant results. It also provides relevance ranking, which is not available in simple string searches.

**Key points** (slide quote → follow-up → expected answer):
- **Full-text search uses a special index for faster searches.**  
  quote: "Full-Text Indexes → much faster than LIKE"  
  follow-up: _Why would a full-text index be faster than using LIKE on a text column?_  
  expected: A full-text index is optimized for searching text content, allowing for faster lookups and more efficient processing of search terms compared to scanning each row with LIKE.
- **Full-text search supports relevance ranking based on how well a row matches the query.**  
  quote: "Relevance Ranking → Scores based on closeness of match"  
  follow-up: _How does full-text search determine the relevance of a row to a query?_  
  expected: Full-text search uses natural language processing and calculates a relevance score based on the frequency and significance of matching terms in the text.

### [Lock-based concurrency control] Explain how the lock-compatibility matrix determines whether two transactions can hold locks on the same data item simultaneously.
*confidence 0.78 · medium · slides [1207, 1208, 1209, 1210, 1211, 1217]*

**Reference:** The lock-compatibility matrix determines compatibility based on whether a transaction requesting a lock of mode A can be granted the lock despite the presence of a lock of mode B held by another transaction. Shared mode is compatible with shared mode but not with exclusive mode. If a transaction Ti requests a lock of mode A on a data item Q, and there is already a lock of mode B held by another transaction Tj on the same data item, Ti will be blocked unless mode A is compatible with mode B.

**Key points** (slide quote → follow-up → expected answer):
- **Compatibility is determined by whether a transaction can acquire a lock despite another transaction holding a different lock mode.**  
  quote: "If Ti can acquire the lock without being blocked by the existing B mode lock, then mode A is considered compatible with mode B."  
  follow-up: _What happens if a transaction requests an exclusive lock on a data item that is already locked in shared mode?_  
  expected: The transaction requesting the exclusive lock will be blocked until the shared lock is released, as exclusive mode is not compatible with shared mode.
- **Shared mode is compatible with shared mode but not with exclusive mode.**  
  quote: "Shared mode is compatible with shared mode, but not with exclusive mode. At any time, several shared-mode locks can be held simultaneously."  
  follow-up: _Can multiple transactions hold shared-mode locks on the same data item at the same time?_  
  expected: Yes, multiple transactions can hold shared-mode locks on the same data item simultaneously.

### [Data independence] How does logical data independence benefit the University database when changes are made to the logical schema?
*confidence 0.78 · medium · slides [63, 64, 65, 66, 67, 68]*

**Reference:** Logical data independence ensures that changes to the logical schema, such as adding or removing attributes, do not affect the external schema or application programs. This allows database designers to modify the conceptual structure of the database without disrupting the user views or existing applications. As a result, the University can adapt its data model to new requirements without requiring extensive changes to the application layer, reducing maintenance costs and minimizing downtime.

**Key points** (slide quote → follow-up → expected answer):
- **Logical data independence allows changes to the logical schema without affecting the external schema.**  
  quote: "It refers to the characteristic of being able to modify the logical schema without affecting the external schema or application program."  
  follow-up: _What happens if the logical schema is changed but the external schema remains the same?_  
  expected: The external schema and application programs remain unaffected, ensuring that user views and queries continue to function as intended.
- **Logical data independence enables easier adaptability to changes in the University's requirements.**  
  quote: "This flexibility allows for easier adaptability to changes in the University's requirements and business rules without causing application disruptions."  
  follow-up: _Why would the University want to make changes to the logical schema without affecting the applications?_  
  expected: To accommodate new business rules or data requirements without requiring developers to rewrite application code.

### [GRANT and REVOKE privileges] How does the REVOKE statement relate to the GRANT statement in terms of privilege management?
*confidence 0.78 · medium · slides [698]*

**Reference:** The REVOKE statement is structurally similar to the GRANT statement, as both are used to manage privileges in a database. The REVOKE statement removes a privilege that was previously granted by GRANT. Both statements specify the privilege, the object it applies to, and the user who is affected.

**Key points** (slide quote → follow-up → expected answer):
- **The REVOKE statement is structurally similar to the GRANT statement.**  
  quote: "The REVOKE statement takes a form almost identical to that of GRANT."  
  follow-up: _What is the main difference between the REVOKE and GRANT statements?_  
  expected: The main difference is that GRANT adds a privilege, while REVOKE removes it.
- **The REVOKE statement removes a privilege that was previously granted by GRANT.**  
  quote: "To revoke an authorization, we use the REVOKE statement."  
  follow-up: _Can you revoke a privilege that was not previously granted?_  
  expected: No, the REVOKE statement can only remove privileges that were previously granted by GRANT.

### [Nested and correlated subqueries] Explain how correlated subqueries differ from regular nested queries in terms of execution and their impact on query results.
*confidence 0.78 · medium · slides [621, 661, 662, 663]*

**Reference:** Correlated subqueries are evaluated once for each tuple in the outer query, and they reference attributes from the outer query. This means the subquery depends on the outer query's tuple for its execution. In contrast, regular nested queries are evaluated once and do not depend on the outer query's tuples. This difference in execution leads to different results, as correlated subqueries can produce different results for each row of the outer query.

**Key points** (slide quote → follow-up → expected answer):
- **A correlated nested query is evaluated once for each tuple (or combination of tuples) of the relation in the outer query.**  
  quote: "For each EMPLOYEE tuple, the nested query is evaluated, and the Essn values of all DEPENDENT tuples with the same Gender as that of the EMPLOYEE tuple are retrieved."  
  follow-up: _What happens if the subquery does not reference the outer query's attributes?_  
  expected: The subquery would be treated as a regular nested query and evaluated once, not once per tuple from the outer query.
- **Correlated subqueries are often used with EXISTS or NOT EXISTS to check for the presence of tuples.**  
  quote: "EXISTS and NOT EXISTS are typically used in conjunction with a correlated nested query."  
  follow-up: _Why would you use EXISTS with a correlated subquery?_  
  expected: To check if there is at least one matching tuple in the subquery result for a given row in the outer query.

### [Graph databases and Neo4j] Explain how Neo4j handles the flexibility of schema in comparison to traditional relational databases.
*confidence 0.77 · medium · slides [1297, 1298, 1299, 1300, 1301, 1318]*

**Reference:** Neo4j provides a flexible schema by allowing nodes and relationships to have properties without requiring predefined structures. In contrast, traditional relational databases require a fixed schema with predefined tables and columns. This flexibility enables Neo4j to easily accommodate new nodes, relationships, or properties without altering the existing data model. This is particularly useful in applications where data models evolve over time.

**Key points** (slide quote → follow-up → expected answer):
- **Neo4j allows nodes and relationships to have properties without a predefined structure.**  
  quote: "Properties can be specified via a map pattern, which is made of one or more 'name: value' pairs for example {Lname: 'Smith', Fname: 'John', Minit: 'B'}."  
  follow-up: _What is the implication of not having a predefined structure for nodes and relationships?_  
  expected: It means that new properties can be added dynamically without changing the existing data model.
- **Neo4j's flexible schema supports dynamic addition of new elements to the graph.**  
  quote: "Flexible schema → can easily add new nodes, edges, or properties."  
  follow-up: _Why is this flexibility particularly useful in real-world applications?_  
  expected: Because real-world data models often evolve, and Neo4j allows for these changes without significant restructuring.

---

## Held back (low confidence — not used by the app)

### [ER to relational mapping] Explain what it means to map an entity set to a relation schema in the context of ER to relational mapping.
*confidence 0.74 · easy · slides [267, 268]*

**Reference:** Mapping an entity set to a relation schema means creating a unique relation for each entity set, where the relation's name corresponds to the entity set. This transformation ensures that the logical structure of the entity set is preserved in the relational model. The relation schema includes attributes that represent the entity's properties, and each entity instance becomes a tuple in the relation.

**Key points** (slide quote → follow-up → expected answer):
- **Each entity set is mapped to a unique relation schema.**  
  quote: "For each entity set and for each relationship set in the database design, there is a unique relation schema to which we assign the name of the corresponding entity set or relationship set."  
  follow-up: _What happens if two entity sets are mapped to the same relation schema?_  
  expected: It would violate the principle of unique relation schemas per entity set, leading to ambiguity and potential data integrity issues.
- **The relation schema's name corresponds to the entity set.**  
  quote: "For each entity set and for each relationship set in the database design, there is a unique relation schema to which we assign the name of the corresponding entity set or relationship set."  
  follow-up: _Why is it important that the relation schema's name matches the entity set?_  
  expected: It ensures clarity and consistency in the relational model, making it easier to understand and maintain the database structure.

### [Self join and cross join] Explain the difference between a cross join and a self join in terms of how they operate.
*confidence 0.74 · easy · slides [575, 599]*

**Reference:** A cross join returns the Cartesian product of two tables, meaning it combines every row from one table with every row from another table, without any join condition. A self join, on the other hand, is a type of join where a table is joined with itself, typically used to compare rows within the same table. Both types of joins do not require a join condition, but a self join is a specific case of a cross join where the same table is involved.

**Key points** (slide quote → follow-up → expected answer):
- **A cross join returns the Cartesian product of two tables.**  
  quote: "Cross Join returns the Cartesian Product"  
  follow-up: _What happens if you perform a cross join between two tables with 8 and 7 rows respectively?_  
  expected: It would return 56 rows, which is the product of the number of rows in both tables.
- **A cross join does not use a join condition.**  
  quote: "It does not use a join condition (ON ...), so it doesn’t care about matching columns."  
  follow-up: _Can you use a WHERE clause to filter results from a cross join?_  
  expected: Yes, you can use a WHERE clause to filter the results of a cross join, but it won’t affect the Cartesian product itself.

### [Window functions] Can you explain what a window function is and how it differs from a regular aggregate function?
*confidence 0.74 · easy · slides [752, 753, 756, 757, 758, 759]*

**Reference:** A window function performs calculations across a set of rows that are related to the current row, without collapsing them into a single row like a regular aggregate function. This allows you to retain all rows while performing operations such as averaging or ranking. Unlike regular aggregate functions, which group rows and return a single result per group, window functions operate on a 'window' of rows and return a result for each row.

**Key points** (slide quote → follow-up → expected answer):
- **A window function performs calculations across a set of rows that are related to the current row, without collapsing them into a single row.**  
  quote: "OVER clause tells SQL to not collapse rows like GROUP BY and instead, calculate an aggregate in a ‘window’ while keeping all rows visible."  
  follow-up: _What happens if you use a window function without specifying a PARTITION BY clause?_  
  expected: The window function will apply the calculation across all rows in the table, treating them as a single window, which may not be the intended behavior.
- **Unlike regular aggregate functions, which group rows and return a single result per group, window functions operate on a 'window' of rows and return a result for each row.**  
  quote: "Aggregate window functions calculate aggregates over a window of rows while retaining individual rows."  
  follow-up: _Can you give an example of a situation where a window function would be more useful than a regular aggregate function?_  
  expected: A window function is more useful when you want to calculate an aggregate for each row while keeping all rows intact, such as calculating the average salary per department for each employee in the department.

### [Boyce-Codd normal form (BCNF)] Explain what it means for a relation schema to be in Boyce-Codd Normal Form (BCNF).
*confidence 0.74 · easy · slides [957, 959, 960]*

**Reference:** A relation schema R is in BCNF if whenever a functional dependency X → A holds in R, then X is a superkey of R. This ensures that all dependencies are based on superkeys, eliminating any potential anomalies. BCNF is a stronger normal form than 3NF, and it guarantees that every non-trivial dependency has a superkey on the left-hand side. This helps ensure data integrity and reduces redundancy in the database design.

**Key points** (slide quote → follow-up → expected answer):
- **A relation schema R is in BCNF if whenever a functional dependency X → A holds in R, then X is a superkey of R.**  
  quote: "A relation schema R is in Boyce-Codd Normal Form (BCNF) if whenever an FD X →A holds in R, then X is a superkey of R BCNF"  
  follow-up: _What happens if a functional dependency exists where X is not a superkey?_  
  expected: The relation would not be in BCNF, as BCNF requires that all dependencies have X as a superkey.
- **BCNF is a stronger normal form than 3NF.**  
  quote: "Every BCNF relation is in 3NF"  
  follow-up: _Why is BCNF considered a stronger form than 3NF?_  
  expected: Because BCNF enforces a stricter condition: all dependencies must have X as a superkey, whereas 3NF allows for some dependencies where X is not a superkey, as long as A is a prime attribute.

### [Foreign key] Explain what a foreign key is and how it enforces referential integrity.
*confidence 0.74 · easy · slides [446, 449, 450, 476, 716, 717]*

**Reference:** A foreign key is a column or set of columns in a table that refers to the primary key of another table. It enforces referential integrity by ensuring that the values in the foreign key column exist in the referenced primary key column of the parent table. This prevents orphaned records and maintains consistency between related tables.

**Key points** (slide quote → follow-up → expected answer):
- **A foreign key is a column or set of columns in a table that refers to the primary key of another table.**  
  quote: "ALTER TABLE employee ADD CONSTRAINT fk_dept FOREIGN KEY (dept_ref_id) REFERENCES department(id);"  
  follow-up: _What happens if a value in the foreign key column does not exist in the referenced primary key column?_  
  expected: It violates the referential integrity constraint and typically results in an error, preventing the operation from completing.
- **The foreign key constraint can be added to an existing column, but it may require dropping the existing constraint first.**  
  quote: "If the foreign key constraint is being added to an attribute which already has an existing foreign key constraint, we first have to drop the existing constraint and then add a new one. Otherwise, it is not necessary."  
  follow-up: _Why might you need to drop an existing foreign key constraint before adding a new one?_  
  expected: Because the column already has a foreign key constraint, and you need to modify or replace it with a new one.

### [CAP theorem] Explain what the CAP theorem states about distributed systems with replicated data.
*confidence 0.74 · easy · slides [1247, 1248, 1249, 1251]*

**Reference:** The CAP theorem states that it is not possible to guarantee all three of the desirable properties—consistency, availability, and partition tolerance—at the same time in a distributed system with data replication. This means that a system must choose at least two of these properties to guarantee. The theorem highlights the inherent trade-offs in designing distributed systems with replicated data.

**Key points** (slide quote → follow-up → expected answer):
- **The CAP theorem states that consistency, availability, and partition tolerance cannot all be guaranteed simultaneously.**  
  quote: "The CAP theorem states that: 'It is not possible to guarantee all three of the desirable properties—consistency, availability, and partition tolerance—at the same, time in a distributed system with data replication'."  
  follow-up: _What happens if a system tries to guarantee all three properties?_  
  expected: It is not possible to guarantee all three properties at the same time, which means the system will eventually fail to meet at least one of them.
- **A distributed system must choose at least two of the three properties to guarantee.**  
  quote: "If this is the case, then the distributed system designer would have to choose two properties out of the three to guarantee."  
  follow-up: _Why would a system designer have to make a choice between these properties?_  
  expected: Because the CAP theorem states that it is not possible to guarantee all three properties at the same time, so a trade-off must be made.

### [Lock-based concurrency control] Explain what a lock is and how it controls access to a data item in a transaction system.
*confidence 0.74 · easy · slides [1207, 1208, 1209, 1210, 1211, 1217]*

**Reference:** A lock is a mechanism to control concurrent access to a data item. A transaction can access a data item only if it is currently holding a lock on it. Locks are used to ensure that no other transaction can access the data item in an incompatible way while a lock is held.

**Key points** (slide quote → follow-up → expected answer):
- **A lock is a mechanism to control concurrent access to a data item.**  
  quote: "A lock is a mechanism to control concurrent access to a data item."  
  follow-up: _What happens if two transactions try to access the same data item at the same time?_  
  expected: One transaction will be blocked until the other releases its lock, ensuring exclusive access.
- **A transaction can access a data item only if it is currently holding a lock on it.**  
  quote: "A transaction can proceed only after the request is granted."  
  follow-up: _What is the role of the concurrency-control manager in this process?_  
  expected: The concurrency-control manager grants or denies lock requests based on compatibility and current lock modes.

### [DBMS vs file system] What is one key advantage of a database system over a file system?
*confidence 0.73 · easy · slides [41, 50, 51]*

**Reference:** A database system provides persistent storage for program objects, such as in object-oriented DBMSs, which allows program objects to be stored and retrieved even after the program that created them has terminated. This is a significant advantage over file systems, which typically do not support such persistent storage for program objects. This feature enables more robust and reusable software development.

**Key points** (slide quote → follow-up → expected answer):
- **Persistent storage for program objects**  
  quote: "Providing persistent storage for program Objects - E.g., Object-oriented DBMSs make program objects persistent"  
  follow-up: _Can you explain why persistent storage for program objects is important in software development?_  
  expected: Persistent storage for program objects allows them to be retained even after the program that created them has ended, which supports long-term data management and reuse.
- **Enhanced data integrity and security**  
  quote: "Restricting unauthorized access to data"  
  follow-up: _How does a database system ensure that data is not accessed by unauthorized users?_  
  expected: A database system restricts unauthorized access to data through access control mechanisms, which are not typically available in file systems.

### [Set operations in SQL] Explain what the UNION operator does in SQL, and why it is important for combining relations.
*confidence 0.73 · easy · slides [330, 331, 521]*

**Reference:** The UNION operator in SQL combines the results of two or more SELECT statements into a single result set. It ensures that duplicate tuples are eliminated from the final output. This is important for combining relations because it allows us to merge data from different tables while maintaining uniqueness, which is essential for accurate data analysis.

**Key points** (slide quote → follow-up → expected answer):
- **UNION combines the results of two or more SELECT statements.**  
  quote: "SQL Set operations are used to combine two or more SQL SELECT statements."  
  follow-up: _What happens if you try to combine two queries that return different numbers of columns?_  
  expected: You will get an error because the relations must be union compatible, which requires them to have the same number of columns.
- **UNION requires that the relations are union compatible.**  
  quote: "Two relations are said to be union compatible if 1. Both the relations have the same arity (number of attributes) and 2. The corresponding attribute domains must be compatible."  
  follow-up: _What does it mean for two relations to be union compatible?_  
  expected: It means they must have the same number of columns, and the data types of corresponding columns must be compatible.

### [Database architecture] Explain how the three-tier client-server architecture enhances security in database systems, and why the middle tier is critical to this design.
*confidence 0.70 · medium · slides [90, 135]*

**Reference:** The three-tier architecture enhances security by ensuring the database server is only accessible via the middle tier. This prevents clients from directly accessing the database server, which reduces the risk of unauthorized data access. The middle tier, also known as the application or web server, acts as a conduit for sending partially processed data between the client and the database server. This design isolates the database from direct client interaction, making it harder for malicious actors to exploit vulnerabilities in the client layer. The middle tier also stores the business logic, which further secures the data by controlling how it is accessed and processed.

**Key points** (slide quote → follow-up → expected answer):
- **The three-tier architecture enhances security by ensuring the database server is only accessible via the middle tier.**  
  quote: "Database server only accessible via middle tier"  
  follow-up: _Why would allowing direct client access to the database be a security risk?_  
  expected: Allowing direct client access to the database could expose sensitive data to unauthorized users and make the system more vulnerable to attacks.
- **The middle tier acts as a conduit for sending partially processed data between the client and the database server.**  
  quote: "Acts like a conduit for sending partially processed data between the database server and the client."  
  follow-up: _What role does the middle tier play in data processing?_  
  expected: The middle tier processes data before sending it to the client, which helps reduce the amount of raw data exposed to the client and improves security.

### [Super key and candidate key] Consider a relation schema R with attributes A, B, and C, and suppose that the set {A, B} is a superkey. Can {A, B} also be a candidate key? Explain why or why not, and what condition must be satisfied for this to be true.
*confidence 0.70 · medium · slides [240, 241, 242, 926, 936, 937]*

**Reference:** Yes, {A, B} can be a candidate key if it is a minimal superkey. This means that removing any attribute from {A, B} would result in a set that is no longer a superkey. For example, if removing A from {A, B} leaves {B}, and {B} is not a superkey, then {A, B} is a candidate key. This aligns with the definition that a candidate key is a superkey that is minimal in the sense that no subset of it is also a superkey.

**Key points** (slide quote → follow-up → expected answer):
- **A candidate key is a minimal superkey.**  
  quote: "A key K is a superkey with the additional property that removal of any attribute from K will cause K not to be a superkey any more (ie minimal superkey)."  
  follow-up: _What happens if you remove one attribute from a candidate key?_  
  expected: The resulting set is no longer a superkey, which confirms that the original set was minimal.
- **Minimality is the defining characteristic of a candidate key.**  
  quote: "A key K is a superkey with the additional property that removal of any attribute from K will cause K not to be a superkey any more (ie minimal superkey)."  
  follow-up: _Why is minimality important for a key to be a candidate key?_  
  expected: Minimality ensures that the key is as small as possible while still uniquely identifying tuples, which is essential for efficient database design.

### [Entities and attributes] Explain how multivalued attributes are represented in a relational schema, and why this representation is necessary.
*confidence 0.70 · medium · slides [177, 178, 179, 180, 181, 227]*

**Reference:** Multivalued attributes are represented by creating a separate relation schema that includes the primary key of the original entity set and the multivalued attribute. This is necessary because a single entity may have multiple values for a particular attribute, and storing them all in one row would violate the atomicity principle of the relational model. For example, if an instructor has multiple phone numbers, a separate relation like Instructor_phone is created to store each phone number with a reference to the instructor's ID.

**Key points** (slide quote → follow-up → expected answer):
- **Multivalued attributes require a separate relation schema.**  
  quote: "For a multivalued attribute M, create a relation schema R with an attribute A that corresponds to M and attributes corresponding to the primary key of the entity set or relationship set of which M is an attribute."  
  follow-up: _What happens if you try to store multiple values of a multivalued attribute in a single column of a table?_  
  expected: It would violate the atomicity principle of the relational model, making the data difficult to query and manage.
- **A foreign-key constraint is added to the new relation schema.**  
  quote: "A foreign-key constraint is to be added to the relation schema created from the multivalued attribute."  
  follow-up: _What is the purpose of the foreign-key constraint in this context?_  
  expected: It ensures that the values in the multivalued attribute relation are linked to valid entities in the original entity set, preventing orphaned records.

### [Participation constraints] How does the concept of partial participation affect the design of a database schema, and what implications does it have for data integrity?
*confidence 0.70 · medium · slides [220, 221]*

**Reference:** Partial participation means that some entities in an entity set may not participate in a relationship set. This allows for flexibility in the database design, as not all entities are required to be related. However, it can impact data integrity because it may lead to incomplete relationships, where some entities are not connected to others, potentially causing inconsistencies or missing data.

**Key points** (slide quote → follow-up → expected answer):
- **Partial participation allows for entities in an entity set to not participate in a relationship set.**  
  quote: "If it is possible that some entities in E do not participate in relationships in R, the participation of entity set E in relationship R is said to be partial."  
  follow-up: _What happens if an entity is not required to be part of a relationship?_  
  expected: It means that the entity may exist in the database without being connected to any related entities, which can lead to incomplete data relationships.
- **The design of a database schema must account for whether participation is total or partial.**  
  quote: "The participation of an entity set E in a relationship set R is said to be total if every entity in E must participate in at least one relationship in R."  
  follow-up: _Why is it important to decide whether participation is total or partial during schema design?_  
  expected: It ensures that the database accurately reflects the business rules and constraints, maintaining data integrity and consistency.

### [Inner join] How does the Inner Join operation ensure that only relevant rows are combined from two tables?
*confidence 0.70 · medium · slides [582, 583, 584]*

**Reference:** The Inner Join operation ensures that only relevant rows are combined by comparing each row of the first table with each row of the second table to find all pairs that satisfy the join-predicate. When the join-predicate is satisfied, the column values for each matched pair of rows are combined into a result row. This process effectively filters out any rows that do not meet the condition, ensuring that only matching rows are included in the final output.

**Key points** (slide quote → follow-up → expected answer):
- **Inner Join compares each row of the first table with each row of the second table to find all pairs that satisfy the join-predicate.**  
  quote: "Inner Join query compares each row of the first table with each row of the second table to find all pairs of rows that satisfy the join-predicate."  
  follow-up: _What happens if no rows in one table match any rows in the other table?_  
  expected: If no rows match, the Inner Join will return an empty result set, as it only includes rows that satisfy the join-predicate.
- **Inner Join combines column values for each matched pair of rows into a result row.**  
  quote: "When the join-predicate is satisfied, column values for each matched pair of rows of both tables are combined into a result row."  
  follow-up: _What happens to rows that do not satisfy the join-predicate?_  
  expected: Rows that do not satisfy the join-predicate are excluded from the result set, as Inner Join only includes rows that meet the condition.

### [Schedules and serializability] How does the presence of a cycle in the precedence graph affect the conflict serializability of a schedule?
*confidence 0.70 · medium · slides [1163, 1166, 1189, 1199, 1200, 1228]*

**Reference:** The presence of a cycle in the precedence graph indicates that the schedule is not conflict serializable. This is because the precedence graph is used to determine if a schedule can be transformed into a serial schedule through reordering, and cycles prevent such reordering. The algorithm for testing conflict serializability relies on the absence of cycles to confirm that a schedule is equivalent to some serial schedule.

**Key points** (slide quote → follow-up → expected answer):
- **A cycle in the precedence graph means the schedule is not conflict serializable.**  
  quote: "Clearly, there exists a cycle in the precedence graph. Therefore,"  
  follow-up: _What happens if a precedence graph has a cycle during conflict serializability testing?_  
  expected: The schedule is not conflict serializable because cycles prevent the schedule from being reordered into a serial schedule.
- **Conflict serializability is determined by the absence of cycles in the precedence graph.**  
  quote: "The schedule S is serializable if and only if the precedence graph has no cycles."  
  follow-up: _What is the condition for a schedule to be conflict serializable according to the algorithm?_  
  expected: A schedule is conflict serializable if and only if the precedence graph has no cycles.

### [Concurrency anomalies] Explain how the Unrepeatable Read problem can lead to incorrect results in a database system, and why it is a concurrency anomaly.
*confidence 0.70 · medium · slides [1119, 1120, 1121]*

**Reference:** The Unrepeatable Read problem occurs when a transaction T reads the same item twice, and between the two reads, another transaction T′ changes the item. This leads to T receiving different values for the same item, which can cause confusion or incorrect logic in the application. It is a concurrency anomaly because it violates the expectation that a transaction should see a consistent view of the database during its execution.

**Key points** (slide quote → follow-up → expected answer):
- **A transaction T reads the same item twice and the item is changed by another transaction T′ between the two reads.**  
  quote: "A transaction T reads the same item twice and the item is changed by another transaction T′ between the two reads. Hence, T receives different values for its two reads of the same item."  
  follow-up: _What happens if a transaction reads the same data twice and the data changes in between?_  
  expected: The transaction will see different values for the same data, which can lead to confusion or incorrect logic in the application.
- **This leads to T receiving different values for its two reads of the same item.**  
  quote: "A transaction T reads the same item twice and the item is changed by another transaction T′ between the two reads. Hence, T receives different values for its two reads of the same item."  
  follow-up: _Why is this considered an anomaly in concurrency control?_  
  expected: It is considered an anomaly because it violates the consistency of the transaction's view of the database, leading to potential errors in the application logic.

### [Isolation levels] Explain how isolation levels affect the possibility of dirty reads and non-repeatable reads in a database system.
*confidence 0.70 · medium · slides [1123, 1124, 1125, 1126]*

**Reference:** Isolation levels determine how transactions are isolated from each other, which directly affects the possibility of dirty reads and non-repeatable reads. The READ UNCOMMITTED level allows dirty reads because it permits reading uncommitted data. The READ COMMITTED level prevents dirty reads but allows non-repeatable reads. The REPEATABLE READ level prevents both dirty reads and non-repeatable reads, but may still allow phantom records. The SERIALIZABLE level prevents all three issues by ensuring complete isolation.

**Key points** (slide quote → follow-up → expected answer):
- **The READ UNCOMMITTED isolation level allows dirty reads because it permits reading uncommitted data.**  
  quote: "READ UNCOMMITTED: Lowest isolation, allows reading uncommitted data"  
  follow-up: _What happens if a transaction reads data that another transaction has not yet committed?_  
  expected: It may read uncommitted data, which could later be rolled back, leading to a dirty read.
- **The REPEATABLE READ level prevents both dirty reads and non-repeatable reads.**  
  quote: "REPEATABLE READ: Ensures that data read once will not change during the"  
  follow-up: _How does REPEATABLE READ prevent non-repeatable reads?_  
  expected: By ensuring that once data is read, it remains unchanged for the duration of the transaction, even if other transactions modify it.

### [SQL command categories] Explain how DDL and DML differ in their purpose and how they interact with database objects.
*confidence 0.70 · medium · slides [405, 422]*

**Reference:** DDL is used to define and modify the structure of database objects like tables, views, and users, using commands such as CREATE, ALTER, and DROP. DML, on the other hand, is used to manipulate data within these objects, such as inserting, updating, or deleting records. DDL commands can affect the structure of the database, which in turn influences how DML operations can be performed on the data.

**Key points** (slide quote → follow-up → expected answer):
- **DDL is used to define and modify the structure of database objects.**  
  quote: "Data Definition Language (DDL) statements are used to define the database structure or schema."  
  follow-up: _What happens if you try to update a table without first defining it?_  
  expected: You would receive an error because the table does not exist, which means the structure hasn't been defined yet.
- **DML is used to manipulate data within schema objects.**  
  quote: "Data Manipulation Language (DML) statements are used for managing data within schema objects."  
  follow-up: _Can DML commands change the structure of a table?_  
  expected: No, DML commands are used to manage data, not the structure of the table. Changing the structure requires DDL commands.

### [SELECT query clauses] Explain how the DISTINCT clause interacts with the ORDER BY clause in a SELECT query.
*confidence 0.70 · medium · slides [506, 509, 513, 514]*

**Reference:** The DISTINCT clause eliminates duplicate rows from the result set, while the ORDER BY clause sorts the output. When both are used, DISTINCT is applied first, and then ORDER BY sorts the unique rows. The ORDER BY clause can use ASC or DESC to specify the sort order, with ASC being the default. This interaction ensures that the final output is both unique and sorted as required.

**Key points** (slide quote → follow-up → expected answer):
- **The DISTINCT clause eliminates duplicate rows from the result set.**  
  quote: "To force the elimination of duplicates, insert the keyword DISTINCT after SELECT."  
  follow-up: _What happens if you apply DISTINCT to a column that already has unique values?_  
  expected: The DISTINCT clause has no effect, as there are no duplicates to remove.
- **The ORDER BY clause can use ASC or DESC to specify the sort order, with ASC being the default.**  
  quote: "ASC – For sorting results in ascending order. DESC – For sorting results in descending order. If we do not place either 'ASC or DESC' at the end of the query, the data is sorted in ascending order by default."  
  follow-up: _What is the default sort order if you omit both DISTINCT and ORDER BY?_  
  expected: The default is to return the data as it is stored, without any sorting or deduplication.

### [Triggers] Explain how a trigger can enforce data integrity in a database, using the example of validating marks in a table.
*confidence 0.70 · medium · slides [707, 708, 709, 712, 713, 714]*

**Reference:** A trigger enforces data integrity by executing predefined logic automatically when a specific event occurs. In the example, the `CheckMarks` trigger validates marks before insertion, ensuring they are between 0 and 100. If not, it raises an error and prevents the invalid data from being inserted. This mechanism ensures that only valid data is stored in the table. The trigger operates before the insertion, allowing it to intercept and reject invalid data at the point of entry.

**Key points** (slide quote → follow-up → expected answer):
- **Triggers can validate data before it is inserted into the database.**  
  quote: "The keyword BEFORE specifies that the trigger execution occurs before the triggering operation (in this case, insertion of tuples in the Marks_sample relation) is executed."  
  follow-up: _Why is it important for the trigger to execute before the insertion?_  
  expected: Because it allows the trigger to intercept and reject invalid data before it is actually stored in the table.
- **Triggers can raise errors to prevent invalid data from being inserted.**  
  quote: "If the specified condition is satisfied, the trigger raises an error, an appropriate error message is displayed and the tuple is not inserted (trigger execution occurs before insertion)."  
  follow-up: _What would happen if the trigger did not raise an error?_  
  expected: The invalid data would be inserted into the table, violating the integrity constraints defined by the trigger.

### [Boyce-Codd normal form (BCNF)] How does a relation schema that is in 3NF but not in BCNF differ from one that is in BCNF, based on the conditions for functional dependencies?
*confidence 0.70 · medium · slides [957, 959, 960]*

**Reference:** A relation schema that is in 3NF but not in BCNF has at least one functional dependency X → A where X is not a superkey and A is a prime attribute. This violates the stricter condition of BCNF, which requires that for every functional dependency X → A, X must be a superkey. In contrast, BCNF ensures that all such dependencies meet this superkey condition, making it a stronger normal form than 3NF.

**Key points** (slide quote → follow-up → expected answer):
- **A relation in 3NF but not BCNF has a functional dependency where X is not a superkey and A is a prime attribute.**  
  quote: "In practice, most relation schemas that are in 3NF are in BCNF, only if there exists some X->A in R with X not being superkey and A being prime attribute, will R be in 3NF but not in BCNF."  
  follow-up: _What happens if a functional dependency has X not being a superkey and A being a prime attribute?_  
  expected: The relation is in 3NF but not in BCNF, because BCNF requires X to be a superkey for all functional dependencies.
- **BCNF enforces that all functional dependencies have X as a superkey.**  
  quote: "A relation schema R is in BCNF if whenever a FD X → A holds in R, the X is a superkey of R."  
  follow-up: _Why is BCNF considered a stronger normal form than 3NF?_  
  expected: Because BCNF imposes a stricter condition on all functional dependencies, requiring X to be a superkey, whereas 3NF allows for X to be non-superkey as long as A is a prime attribute.

### [Relational model] Consider a scenario where two relations are joined using a Cartesian product. How does the structure of the resulting relation affect the interpretation of data and the efficiency of storage and retrieval?
*confidence 0.70 · hard · slides [350, 351, 352, 421, 822] · ⚠ NEEDS REVIEW*

**Reference:** The Cartesian product combines every tuple from one relation with every tuple from another, resulting in a relation with a degree equal to the sum of the degrees of the two operands. This structure can lead to a large number of tuples, which may complicate the interpretation of data as the meaning of attributes becomes ambiguous. The physical storage of such a relation can also become inefficient due to the increased size and the lack of meaningful grouping of attributes.

**Key points** (slide quote → follow-up → expected answer):
- **The Cartesian product results in a relation with a degree equal to the sum of the degrees of the two operands.**  
  quote: "The resulting relation state has one tuple for each combination of tuples—one from R and one from S."  
  follow-up: _What happens to the number of attributes when you perform a Cartesian product on two relations?_  
  expected: The number of attributes in the resulting relation is the sum of the number of attributes in each of the two original relations.
- **The structure of the resulting relation can complicate the interpretation of data.**  
  quote: "We have assumed that attributes are grouped to form a relation schema by using the common sense of the database designer or by mapping a database schema design from a conceptual data model such as the ER data model."  
  follow-up: _Why might the Cartesian product make it harder to interpret the data in the resulting relation?_  
  expected: Because the attributes from the two original relations are combined without any meaningful grouping, the meaning of each attribute becomes ambiguous.

### [Database architecture] What are the implications of the middle tier acting as a conduit for partially processed data in a three-tier client-server architecture, and how does this affect the design of the application logic?
*confidence 0.70 · hard · slides [90, 135] · ⚠ NEEDS REVIEW*

**Reference:** In a three-tier architecture, the middle tier acts as a conduit for sending partially processed data between the client and the database server. This implies that the middle tier is responsible for handling data transformation and processing before it reaches the database server. As a result, the application logic is concentrated in the middle tier, which allows for centralized control over data access and processing. This design choice enhances modularity and facilitates security by limiting direct access to the database server.

**Key points** (slide quote → follow-up → expected answer):
- **The middle tier acts as a conduit for sending partially processed data between the client and the database server.**  
  quote: "Acts like a conduit for sending partially processed data between the database server and the client."  
  follow-up: _What does it mean for the middle tier to send partially processed data?_  
  expected: It means the middle tier processes data before sending it to the database server, reducing the amount of raw data that needs to be transferred.
- **The application logic is centralized in the middle tier.**  
  quote: "Stores the web connectivity software and the business logic part of the application used to access the corresponding data from the database server"  
  follow-up: _How does centralizing application logic affect system design?_  
  expected: Centralizing logic in the middle tier improves modularity and makes the system easier to maintain and secure.

### [SELECT query clauses] Consider a query that includes both the DISTINCT and ORDER BY clauses. What is the relationship between the order of these clauses and the final output of the query?
*confidence 0.70 · hard · slides [506, 509, 513, 514] · ⚠ NEEDS REVIEW*

**Reference:** The DISTINCT clause eliminates duplicate rows from the result set, while the ORDER BY clause sorts the remaining rows. The order of these clauses in the query does not affect the final output, as DISTINCT is applied before ORDER BY. The ORDER BY clause determines the final sort order of the unique rows produced by the DISTINCT clause.

**Key points** (slide quote → follow-up → expected answer):
- **The DISTINCT clause eliminates duplicate rows from the result set.**  
  quote: "To force the elimination of duplicates, insert the keyword DISTINCT after SELECT."  
  follow-up: _What happens if you apply DISTINCT to a column that has repeated values?_  
  expected: The query will return only unique values for that column, removing any duplicates.
- **The ORDER BY clause sorts the result in either ascending or descending order.**  
  quote: "The main function of the ORDER BY clause is to sort the result in either ascending or descending order."  
  follow-up: _Can you sort the output of a query that uses DISTINCT?_  
  expected: Yes, you can use ORDER BY after DISTINCT to sort the unique rows returned.

### [Outer joins] What happens when you perform a Full Outer Join in a database that does not support it natively, and how does this affect the final result compared to a standard Full Outer Join?
*confidence 0.70 · hard · slides [588, 589, 590, 591, 592, 593] · ⚠ NEEDS REVIEW*

**Reference:** When a database does not support Full Outer Join natively, it is implemented by combining a LEFT OUTER JOIN and a RIGHT OUTER JOIN using the UNION operator. This ensures that all records from both tables are included in the result, with unmatched rows padded with NULL values. However, this approach may introduce duplicate rows if the tables have overlapping data, which could affect the accuracy of the final result.

**Key points** (slide quote → follow-up → expected answer):
- **Full Outer Join is implemented by combining LEFT and RIGHT Outer Joins with UNION.**  
  quote: "To implement full outer join in MySQL, we will execute two queries in a single query. The first query will be of LEFT OUTER JOIN, and the second query will be of RIGHT OUTER JOIN. We will combine the first and the second query with the UNION operator to see the results of FULL OUTER JOIN."  
  follow-up: _What is the purpose of using the UNION operator in this context?_  
  expected: The UNION operator is used to combine the results of two separate queries, ensuring that all rows from both tables are included in the final output without duplicates.
- **Unmatched rows are padded with NULL values in both tables.**  
  quote: "In the SQL outer JOIN, all the content from both the tables is integrated together. Even though the records from both the tables are matched or not, the matching and nonmatching records from both the tables will be considered an output of the outer join in SQL."  
  follow-up: _What happens to rows that do not have a matching tuple in the other table?_  
  expected: Rows that do not have a matching tuple in the other table are padded with NULL values for the attributes of the other table, ensuring that all data from both tables is included in the result.

### [Relationships and cardinality] Explain how cardinality ratios affect the design of a database schema, and why a many-to-many relationship cannot be directly represented in a relational model without additional steps.
*confidence 0.70 · hard · slides [209, 210, 211, 212, 213, 214] · ⚠ NEEDS REVIEW*

**Reference:** Cardinality ratios define how entities are related, which directly influences how tables and foreign keys are structured. A many-to-many relationship cannot be directly represented in a relational model because it would require an entity to have multiple parents, which violates the principles of relational database design. Instead, a junction table is used to model the many-to-many relationship by breaking it into two one-to-many relationships.

**Key points** (slide quote → follow-up → expected answer):
- **Cardinality ratios define how entities are related, which directly influences how tables and foreign keys are structured.**  
  quote: "Mapping cardinalities, or cardinality ratios, express the number of entities to which another entity can be associated via a relationship set."  
  follow-up: _What happens if you try to model a many-to-many relationship without a junction table?_  
  expected: You would end up with an entity that has multiple parents, which is not allowed in a relational model.
- **A junction table is used to model the many-to-many relationship by breaking it into two one-to-many relationships.**  
  quote: "The relationship type WORKS_ON is of cardinality ratio M:N. The rule is that an employee can work on several projects and a project can have several employees which is represented by the diagram on the right."  
  follow-up: _How does a junction table resolve the many-to-many issue?_  
  expected: A junction table acts as an intermediary, allowing each entity to have a one-to-many relationship with the junction table, effectively modeling the many-to-many relationship.

### [SQL vs NoSQL] Explain the trade-offs between SQL and NoSQL databases in terms of data structure, consistency, and scalability, and why these trade-offs matter in real-world applications.
*confidence 0.70 · hard · slides [1233, 1234, 1243, 1256] · ⚠ NEEDS REVIEW*

**Reference:** SQL databases are relational and use structured tables with fixed schemas, emphasizing consistency and complex queries, while NoSQL databases are non-tabular, schema-less, and prioritize scalability and flexibility. SQL databases enforce ACID properties for consistency, which can limit scalability, whereas NoSQL databases often sacrifice immediate consistency for high availability and horizontal scaling. These trade-offs matter because applications requiring complex transactions and structured data benefit from SQL, while those needing high scalability and handling unstructured data often choose NoSQL.

**Key points** (slide quote → follow-up → expected answer):
- **SQL databases are relational and use structured tables with fixed schemas.**  
  quote: "NoSQL databases ('not only SQL') are non-tabular databases and store data differently than relational tables."  
  follow-up: _Why would a database need a fixed schema?_  
  expected: A fixed schema allows for strict data validation and ensures consistency through ACID properties, which are critical for applications requiring precise data integrity.
- **NoSQL databases prioritize scalability and flexibility over immediate consistency.**  
  quote: "Most NOSQL systems are distributed databases or distributed storage systems, focusing on semi-structured data storage, high performance, availability, data replication, and scalability instead of emphasizing immediate data consistency, powerful query languages, and structured data storage."  
  follow-up: _What does it mean for a database to prioritize scalability over consistency?_  
  expected: It means the system is designed to handle large-scale data and high availability by allowing eventual consistency, which sacrifices immediate data accuracy for system reliability and performance.

### [Relational algebra joins and division] Explain how a natural join differs from an inner join in relational algebra, and why the result of a natural join may have fewer attributes than an inner join.
*confidence 0.70 · medium · slides [575, 576, 577, 578, 579, 580]*

**Reference:** A natural join implicitly creates an EQUIJOIN condition on all attributes with the same name and data type between two relations, whereas an inner join requires an explicit join condition. The resultant table of a natural join contains unique columns, meaning duplicate attribute names are removed, while an inner join retains all attributes from both relations. This is why the result of a natural join may have fewer attributes than an inner join.

**Key points** (slide quote → follow-up → expected answer):
- **A natural join implicitly creates an EQUIJOIN condition on all attributes with the same name and data type between two relations.**  
  quote: "An implicit EQUIJOIN condition for each pair of attributes with the same name from R and S is created."  
  follow-up: _What happens if two relations have multiple attributes with the same name?_  
  expected: The natural join would create an EQUIJOIN condition for each pair, and the resulting relation would include only one instance of each attribute name.
- **The resultant table of a natural join contains unique columns, meaning duplicate attribute names are removed.**  
  quote: "The resultant table always contains unique columns."  
  follow-up: _Why would a natural join result in fewer attributes than an inner join?_  
  expected: Because duplicate attribute names are removed, and only one instance of each attribute name is included in the result.

### [Two-phase locking] Explain how two-phase locking ensures serializability and why strict two-phase locking improves recoverability and avoids cascading roll-backs.
*confidence 0.69 · hard · slides [1220, 1221, 1222] · ⚠ NEEDS REVIEW*

**Reference:** Two-phase locking ensures serializability by requiring transactions to first acquire all necessary locks (growing phase) before releasing any (shrinking phase), allowing transactions to be serialized in the order of their lock points. Strict two-phase locking improves recoverability and avoids cascading roll-backs because it requires transactions to hold all exclusive locks until commit or abort, ensuring that no other transaction can interfere with the data being modified until the transaction is fully completed.

**Key points** (slide quote → follow-up → expected answer):
- **Two-phase locking ensures serializability by requiring transactions to first acquire all necessary locks (growing phase) before releasing any (shrinking phase).**  
  quote: "The protocol ensures serializability. It can be proved that the transactions can be serialized in the order of their lock points (i.e., the point where a transaction acquired its final lock - end of growing phase)."  
  follow-up: _What happens if a transaction releases a lock before acquiring all necessary locks?_  
  expected: It would violate the two-phase locking protocol and could result in a non-serializable schedule.
- **Strict two-phase locking requires transactions to hold all exclusive locks until commit or abort.**  
  quote: "Strict two-phase locking: a transaction must hold all its exclusive locks till it commits/aborts."  
  follow-up: _How does this differ from basic two-phase locking?_  
  expected: Basic two-phase locking allows for lock release during the shrinking phase, while strict two-phase locking requires all locks to be held until commit or abort.

### [Equivalence of sets of FDs] Consider two sets of functional dependencies, F and G, for a relation R. Suppose that for every FD in F, the closure of its left-hand side using G includes all the attributes on the right-hand side. What does this imply about the relationship between F and G?
*confidence 0.69 · medium · slides [882, 883, 885, 886, 887, 889]*

**Reference:** This implies that set G covers set F, meaning every functional dependency in F can be inferred from G. This is a key step in determining whether two sets of FDs are equivalent. If G covers F, but F does not cover G, then the two sets are not equivalent. However, if both sets cover each other, then they are equivalent.

**Key points** (slide quote → follow-up → expected answer):
- **Covering is determined by comparing closures of attributes.**  
  quote: "We can determine whether F covers E by calculating X+ with respect to F for each FD X → Y in E, and then checking whether this X+ includes the attributes in Y."  
  follow-up: _How would you check if G covers F?_  
  expected: You would calculate the closure of the left-hand side of each FD in F using G and check if it includes the right-hand side attributes.
- **Equivalence requires that both sets cover each other.**  
  quote: "Two sets of functional dependencies E and F are equivalent if E+ = F+."  
  follow-up: _What is the significance of both sets covering each other?_  
  expected: It means that both sets are logically equivalent, and each can be used to infer the other, making them interchangeable in normalization and design.

### [Minimal cover of FDs] Explain how the process of finding a minimal cover ensures that no dependency can be removed without losing equivalence to the original set of FDs, and why this is important for database design.
*confidence 0.69 · hard · slides [893, 895, 896, 898, 899, 924] · ⚠ NEEDS REVIEW*

**Reference:** The process of finding a minimal cover ensures that no dependency can be removed without losing equivalence to the original set of FDs because it enforces the third condition of minimality: we cannot remove any dependency from F and still have a set of dependencies that is equivalent to F. This is important for database design because it guarantees that the minimal cover retains all the constraints of the original set, allowing for efficient storage and manipulation of FDs without redundancy. This ensures that the database schema remains consistent and that all dependencies are explicitly represented without unnecessary duplication.

**Key points** (slide quote → follow-up → expected answer):
- **The minimal cover ensures no dependency can be removed without losing equivalence to the original set of FDs.**  
  quote: "We cannot remove any dependency from F and still have a set of dependencies that is equivalent to F."  
  follow-up: _Why is it important to ensure that no dependency can be removed without losing equivalence?_  
  expected: It is important because removing a dependency without losing equivalence could result in a loss of constraints, which could lead to inconsistencies or incorrect data relationships in the database.
- **Ensuring no dependency can be removed is part of the definition of a minimal cover.**  
  quote: "A minimal cover of a set of functional dependencies E is a minimal set of dependencies ( in the standard canonical form and without redundancy) that is equivalent to E."  
  follow-up: _What would happen if a dependency could be removed without affecting the closure of the set?_  
  expected: If a dependency could be removed without affecting the closure, then the set would not be minimal, and the minimal cover would not be correctly computed, leading to a loss of essential constraints.

### [Indexing basics] What trade-off exists when using indexing, and how does it affect query performance in different scenarios?
*confidence 0.69 · hard · slides [1047, 1048, 1049] · ⚠ NEEDS REVIEW*

**Reference:** Indexing improves query performance for selective conditions by reducing the cost from O(n) to O(log n), as the database can jump directly to qualifying records. However, it introduces overhead during write operations, as indexes must be updated alongside the data. This trade-off means indexing is most beneficial for queries with high selectivity and frequent read operations, but may not be optimal for tables with frequent updates or low selectivity.

**Key points** (slide quote → follow-up → expected answer):
- **Indexing improves query performance for selective conditions by reducing the cost from O(n) to O(log n).**  
  quote: "MySQL uses the B-tree index to jump directly to qualifying records."  
  follow-up: _What happens to query performance when the condition in the WHERE clause is not selective?_  
  expected: The performance gain from indexing diminishes because the index covers a large portion of the table, making it less effective as a search tool.
- **Indexing is most beneficial for queries with high selectivity and frequent read operations.**  
  quote: "The time taken to retrieve the rows is much faster when indexing is used."  
  follow-up: _In what scenario would you expect indexing to have little impact on query performance?_  
  expected: When the query condition is not selective, and the index covers a large portion of the table, the benefit of indexing is reduced.

### [Views] Explain how views can be used to improve security in a database system, and why some views are not updatable.
*confidence 0.67 · medium · slides [677, 678, 679, 687, 689]*

**Reference:** Views improve security by allowing sensitive data to be excluded from the view, so users only see what they are authorized to access. This is because a view is a virtual table that hides the complexity of the underlying data structure. Some views are not updatable because they may involve joins, aggregations, or other operations that make it impossible to directly modify the base tables through the view.

**Key points** (slide quote → follow-up → expected answer):
- **Views improve security by excluding sensitive information from the view.**  
  quote: "It increases security by excluding sensitive information from the view."  
  follow-up: _Can a user modify data through a view that hides sensitive information?_  
  expected: No, because the view is a virtual table and does not store actual data. The user can only see the data that is included in the view.
- **Some views are not updatable because they involve joins or aggregations.**  
  quote: "NOTE: A view is updatable (CRUD operations) only if these criterias are met: ... Does not have joins or subqueries (query within query like select for example)"  
  follow-up: _Why would a view that includes a join not be updatable?_  
  expected: Because the database cannot determine which rows in the base tables to update when a row in the view is modified, leading to potential data inconsistencies.

### [Common table expressions (CTE)] What happens if the recursive member of a CTE does not include a termination condition, and how does this affect the execution of the query?
*confidence 0.67 · hard · slides [628, 629, 642, 643, 644, 645] · ⚠ NEEDS REVIEW*

**Reference:** If the recursive member of a CTE does not include a termination condition, the query may enter an infinite loop, causing the database engine to run indefinitely. This is because the recursive member keeps referencing the CTE itself without any condition to stop the recursion.

**Key points** (slide quote → follow-up → expected answer):
- **A recursive CTE must include a termination condition to prevent infinite recursion.**  
  quote: "The recursive member: This is the query that refers to the CTE itself, creating the recursion. It must reference the CTE by its name and should include a termination condition to stop the recursion."  
  follow-up: _What would happen if the recursive member didn't have a condition to stop the recursion?_  
  expected: The query would run indefinitely, leading to an infinite loop and potentially exhausting system resources.
- **The termination condition is essential for ensuring the query eventually completes.**  
  quote: "The recursive member: This is the query that refers to the CTE itself, creating the recursion. It must reference the CTE by its name and should include a termination condition to stop the recursion."  
  follow-up: _Why is it important for the recursive member to include a termination condition?_  
  expected: It ensures the query terminates and prevents the database from running indefinitely, which could lead to resource exhaustion or incorrect results.

### [Integrity constraints] Consider a scenario where a database must enforce both NOT NULL and CHECK constraints on the same attribute. What trade-offs might arise in designing such constraints, and how do these constraints interact with the default behavior of SQL when no explicit value is provided for an attribute?
*confidence 0.66 · hard · slides [439, 440, 441, 442, 443, 444] · ⚠ NEEDS REVIEW*

**Reference:** NOT NULL constraints ensure that an attribute cannot be left empty, while CHECK constraints enforce specific conditions on the value of the attribute. When both are applied, they work together to guarantee data quality. However, if no explicit value is provided for an attribute, the default value is NULL unless a DEFAULT clause is specified. This means that the NOT NULL constraint will prevent the insertion of a row if the attribute is left unassigned, even if the CHECK constraint is satisfied by a default value. Thus, the NOT NULL constraint takes precedence over the default behavior, enforcing the requirement that the attribute must have a valid value.

**Key points** (slide quote → follow-up → expected answer):
- **NOT NULL constraints prevent an attribute from being left empty.**  
  quote: "NOT NULL: Because SQL allows NULLs as attribute values, a constraint NOT NULL may be specified if NULL is not permitted for a particular attribute."  
  follow-up: _What happens if an attribute has a NOT NULL constraint but no value is provided during insertion?_  
  expected: The database will reject the insertion because the NOT NULL constraint requires the attribute to have a valid value.
- **The default behavior of SQL is to use NULL if no value is provided, unless a DEFAULT clause is used.**  
  quote: "If no default clause is specified, the default default value is NULL for attributes that do not have the NOT NULL constraint."  
  follow-up: _What happens if an attribute has a DEFAULT clause but no value is provided during insertion?_  
  expected: The database will automatically assign the default value specified in the DEFAULT clause.
- **The interaction between NOT NULL and CHECK constraints ensures data quality by enforcing both presence and validity of attribute values.**  
  quote: "CHECK clause Dnumber INT NOT NULL CHECK (Dnumber > 0 AND Dnumber < 21);"  
  follow-up: _How do NOT NULL and CHECK constraints work together to ensure data integrity?_  
  expected: NOT NULL ensures the attribute is not empty, while CHECK ensures the value meets specific conditions, together guaranteeing both presence and correctness of data.

### [Relational algebra operations] Explain how the sequence of relational algebra operations can affect the final result of a query, and why the order of operations matters in relational algebra.
*confidence 0.63 · hard · slides [304, 305, 306, 317] · ⚠ NEEDS REVIEW*

**Reference:** The sequence of relational algebra operations can affect the final result because each operation produces a new relation that serves as input for the next operation. For example, selecting a subset of tuples before projecting attributes yields a different result than projecting first and then filtering. The order of operations matters because relational algebra is not always commutative—applying operations in a different sequence may not produce the same relation, especially when operations like join or set difference are involved.

**Key points** (slide quote → follow-up → expected answer):
- **The sequence of relational algebra operations can affect the final result of a query.**  
  quote: "A sequence of relational algebra operations forms a relational algebra expression."  
  follow-up: _What would happen if you applied a project operation before a select operation on the same relation?_  
  expected: The result would likely be different because projecting first reduces the number of attributes, which may change the outcome of the select operation.
- **The order of operations matters in relational algebra because it is not always commutative.**  
  quote: "The result of a relational algebra expression  relation that represents the result of a database query."  
  follow-up: _Can you give an example of two operations where the order would definitely change the result?_  
  expected: Join and set difference are examples where the order of operations can change the result, as joining first may produce a relation that is then modified by set difference in a different way than if the operations were reversed.

### [Transactions and ACID properties] What happens to the consistency of a database if a transaction is rolled back after it has been committed, and how does this relate to the ACID properties?
*confidence 0.63 · hard · slides [1101, 1102] · ⚠ NEEDS REVIEW*

**Reference:** If a transaction is rolled back after it has been committed, the database must revert to its previous state to maintain consistency. This is ensured by the atomicity property, which guarantees that all operations of a transaction are either fully completed or none are. The durability property ensures that once a transaction is committed, its changes are permanently saved, so rolling back a committed transaction would violate durability unless the system has a mechanism to undo those changes, such as logging and recovery.

**Key points** (slide quote → follow-up → expected answer):
- **Atomicity guarantees that a transaction is treated as an indivisible unit of work.**  
  quote: "Either all operations of the transaction are properly reflected in the database or none are. This “all-or-none” property is referred to as atomicity."  
  follow-up: _How does atomicity help in maintaining consistency when a transaction is rolled back?_  
  expected: Atomicity ensures that the database can treat the transaction as a single unit, so if it is rolled back, the system can revert all changes made by that transaction without leaving the database in an inconsistent state.
- **Durability requires that once a transaction is committed, its changes are permanent.**  
  quote: "After a transaction completes successfully, the changes it has made to the database must persist, even if there are system failures."  
  follow-up: _How can a committed transaction be rolled back without violating durability?_  
  expected: Durability is maintained through mechanisms like logging and recovery, which allow the system to undo changes made by a committed transaction if necessary, without losing the data permanently.

### [SQL command categories] Consider a scenario where a user wants to change the structure of a table and then insert new data into it. How do the SQL command categories interact in this scenario, and what are the implications of this interaction?
*confidence 0.62 · hard · slides [405, 422] · ⚠ NEEDS REVIEW*

**Reference:** In this scenario, the user first uses a DDL command like ALTER to modify the table structure, which changes the schema. Then, they use a DML command like INSERT to add new data. The DDL command affects the structure that the DML command operates on, which means the DML must align with the updated schema. This interaction highlights how DDL and DML are interdependent, with DDL shaping the environment in which DML operates.

**Key points** (slide quote → follow-up → expected answer):
- **DDL commands like ALTER modify the structure of database objects, which affects how DML commands operate on them.**  
  quote: "ALTER - alters the structure of the database"  
  follow-up: _What happens if you try to insert data into a table after altering its structure?_  
  expected: The DML command will operate on the new structure, and if the data doesn't match the new schema, it may result in an error.
- **DML commands such as INSERT manipulate data within the schema objects defined by DDL.**  
  quote: "DML is used for managing data within schema objects"  
  follow-up: _How does the structure of a table influence the data that can be inserted into it?_  
  expected: The structure defines the columns, data types, and constraints, which determine what data can be inserted.

### [HAVING vs WHERE] Consider a scenario where you want to find all departments where the average salary of employees is greater than $50,000, but only for those departments that have more than 5 employees. Explain how the placement of conditions in WHERE and HAVING clauses affects the outcome of the query.
*confidence 0.62 · hard · slides [563, 567, 568, 569, 570] · ⚠ NEEDS REVIEW*

**Reference:** The WHERE clause filters individual employee records before grouping, while the HAVING clause filters groups after they are formed. In this scenario, placing the condition on the number of employees in the WHERE clause would exclude departments with more than 5 employees before any aggregation. However, the correct approach is to use the HAVING clause to filter groups based on the count of employees, and the WHERE clause to filter employees by salary. This ensures that the average salary is computed only for departments with more than 5 employees, and then the average is checked against $50,000.

**Key points** (slide quote → follow-up → expected answer):
- **HAVING provides a condition on the summary information regarding the group of tuples associated with each value of the grouping attributes.**  
  quote: "HAVING provides a condition on the summary information regarding the group of tuples associated with each value of the grouping attributes."  
  follow-up: _What happens if you apply a condition on the count of employees in the WHERE clause?_  
  expected: It would filter out departments with more than 5 employees before any grouping or aggregation occurs, which is not the intended behavior.
- **The WHERE clause is used to specify conditions for individual tuples; the HAVING clause is used to specify conditions for groups of tuples.**  
  quote: "The WHERE clause is used to specify conditions for individual tuples; the HAVING clause is used to specify conditions for groups of tuples."  
  follow-up: _What is the difference between filtering individual rows and filtering groups of rows?_  
  expected: Filtering individual rows is done by the WHERE clause, which operates on the raw data before grouping. Filtering groups is done by the HAVING clause, which operates on aggregated results after grouping.

### [Full-text search] What happens if a user searches for a term that is a stopword in natural language mode, and how does this affect the relevance ranking of results?
*confidence 0.61 · hard · slides [777, 778, 779, 781, 782, 783] · ⚠ NEEDS REVIEW*

**Reference:** In natural language mode, stopwords are ignored, which means they are not considered in the search. This helps improve search efficiency by filtering out common, less meaningful words. However, this also means that stopwords do not contribute to the relevance ranking, so rows containing stopwords may still be ranked based on other terms. The relevance ranking is determined by the presence and significance of non-stopwords in the text.

**Key points** (slide quote → follow-up → expected answer):
- **Stopwords are ignored in natural language mode.**  
  quote: "Natural Language Mode: 2. Ignores stopwords (like 'a', 'the', etc.) and very short words (less than 4 characters, by default)."  
  follow-up: _What is the impact of ignoring stopwords on the search results?_  
  expected: Ignoring stopwords reduces noise in the search, allowing the search to focus on more meaningful terms, but it may also exclude some relevant rows that include stopwords in combination with other terms.
- **Stopwords do not contribute to relevance ranking.**  
  quote: "Natural Language Mode: 2. Ignores stopwords (like 'a', 'the', etc.) and very short words (less than 4 characters, by default)."  
  follow-up: _Can a row with a high number of stopwords still be ranked highly in natural language mode?_  
  expected: A row with a high number of stopwords may still be ranked highly if it contains other significant terms, but the stopwords themselves do not contribute to the relevance score.
