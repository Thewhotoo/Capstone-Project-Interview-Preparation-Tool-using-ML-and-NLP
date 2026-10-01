# Question bank: cn

- **Active (used by the app): 39** · held back for review: 21 (confidence threshold 0.75)
- Sorted by confidence, best first. Held-back questions are kept below, not deleted.

## Active questions

### [Transport layer services] Explain what a socket is and how it relates to the transport layer.
*confidence 0.96 · easy · slides [158, 297, 326, 453]*

**Reference:** A socket is the interface through which a process sends and receives messages. It acts like a door, allowing a sending process to shove a message out and relying on the transport infrastructure to deliver it to the receiving socket. The transport layer uses sockets to manage communication between processes across different hosts.

**Key points** (slide quote → follow-up → expected answer):
- **A socket is the interface through which a process sends and receives messages.**  
  quote: "process sends/receives messages to/from its socket"  
  follow-up: _What happens if a process doesn't use a socket?_  
  expected: The process cannot communicate with other processes over the network, as the transport layer relies on sockets to manage message delivery.
- **A socket acts like a door, allowing messages to be sent out and received.**  
  quote: "socket analogous to door - sending process shoves message out door"  
  follow-up: _Why is the socket compared to a door?_  
  expected: Because it serves as the entry and exit point for messages, much like a door allows people to enter and exit a building.
- **Two sockets are involved in a communication: one on each side of the connection.**  
  quote: "two sockets involved: one on each side"  
  follow-up: _What would happen if only one socket was used?_  
  expected: The message would not be delivered properly, as there would be no receiving endpoint to accept the message.

### [FTP] Explain what FTP is and how it is used in networking.
*confidence 0.96 · easy · slides [285, 286]*

**Reference:** FTP, or File Transfer Protocol, is used to exchange large files on the internet using TCP. It is invoked from the command prompt or a GUI and allows users to update files on a server, such as deleting, renaming, or copying them. FTP uses two separate connections: a control connection on port 21 and a data connection on port 20.

**Key points** (slide quote → follow-up → expected answer):
- **FTP is used to exchange large files on the internet using TCP.**  
  quote: "File Transfer Protocol (FTP) - used to exchange large files on the internet TCP"  
  follow-up: _Why is TCP used for FTP instead of UDP?_  
  expected: TCP is used because it provides reliable, ordered, and error-checked delivery of data, which is essential for transferring large files accurately.
- **FTP allows users to update files on a server.**  
  quote: "Allows to update (delete, rename, move, and copy) files at a server."  
  follow-up: _What are some examples of file updates that FTP supports?_  
  expected: FTP supports deleting, renaming, moving, and copying files on a server, which are common file management operations.
- **FTP uses two separate connections: control and data.**  
  quote: "Data connection (Port No. 20) & Control connection (Port No. 21)"  
  follow-up: _What is the purpose of the control connection in FTP?_  
  expected: The control connection is used to send commands and receive responses, while the data connection is used for the actual transfer of file data.

### [Network devices] Explain how a Switch differs from a Hub in terms of network communication and device intelligence.
*confidence 0.91 · medium · slides [99, 100, 101, 104]*

**Reference:** A Switch operates at the Data Link Layer and uses MAC addresses to forward data packets to the appropriate destination ports, whereas a Hub operates at the Physical Layer and broadcasts data to all connected devices. Switches can operate in full-duplex mode, enabling simultaneous data transmission and reception, while Hubs only support half-duplex communication. Switches store MAC addresses of connected devices, allowing them to route communication only to the intended destination, reducing collisions, whereas Hubs cannot store MAC addresses and transmit all data to all connected devices without filtering.

**Key points** (slide quote → follow-up → expected answer):
- **Switches operate at the Data Link Layer and use MAC addresses for data forwarding.**  
  quote: "An intelligent network device, functioning as a multiport bridge, uses MAC addresses to forward data packets to the appropriate destination ports."  
  follow-up: _What happens if a Switch doesn't know the MAC address of the destination device?_  
  expected: The Switch will broadcast the data to all connected devices, similar to a Hub, until it learns the MAC address through communication.
- **Switches support full-duplex communication, while Hubs only support half-duplex.**  
  quote: "Can operate in full-duplex mode, enabling simultaneous data transmission & reception in network"  
  follow-up: _Why would full-duplex communication be beneficial in a network?_  
  expected: Full-duplex communication allows devices to send and receive data simultaneously, improving network efficiency and reducing collisions.
- **Switches store MAC addresses, allowing them to route data only to the intended destination.**  
  quote: "Store MAC addresses of connected devices, routing communication only to the intended destination, reducing collisions and eliminating"  
  follow-up: _How does a Switch handle a device that it has not learned the MAC address for?_  
  expected: The Switch will forward the data to all ports until it learns the MAC address, at which point it will direct the data only to the appropriate port.

### [Error detection] Explain how CRC codes ensure that burst errors are detected, and why this is important for network communication.
*confidence 0.91 · medium · slides [657]*

**Reference:** CRC codes ensure that burst errors are detected by using a generator polynomial to divide the data along with the CRC bits. If the result is divisible by the generator, it means no error occurred. CRC codes can detect all burst errors less than r+1 bits because the polynomial division ensures that any such error pattern will not divide evenly by the generator. This is important for network communication because burst errors are common in transmission, and detecting them ensures data integrity.

**Key points** (slide quote → follow-up → expected answer):
- **CRC codes can detect all burst errors less than r+1 bits.**  
  quote: "can detect all burst errors less than r+1 bits"  
  follow-up: _Why is it important to detect burst errors in network communication?_  
  expected: Because burst errors are common in transmission and can corrupt multiple bits at once, making them hard to detect with simple parity checks.
- **The CRC is chosen so that <D,R> is divisible by G (mod 2).**  
  quote: "<D,R> exactly divisible by G (mod 2)"  
  follow-up: _What happens if the remainder is not zero after dividing <D,R> by G?_  
  expected: If the remainder is not zero, it means an error has occurred, and the receiver discards the data.
- **The receiver uses the same generator polynomial to divide the received data.**  
  quote: "receiver knows G, divides <D,R> by G. If non-zero remainder: error detected!"  
  follow-up: _Why does the receiver need to know the generator polynomial?_  
  expected: Because the generator polynomial is used to compute the CRC bits at the sender's side, and the receiver uses the same to verify the integrity of the received data.

### [Ethernet] Explain how Ethernet frames are used to support communication between devices on a local network, and why the frame structure is important for reliable data transmission.
*confidence 0.91 · medium · slides [712, 713, 715, 734]*

**Reference:** Ethernet frames encapsulate higher-layer data, such as IP packets, to ensure proper delivery across the network. The frame structure includes synchronization patterns, source and destination MAC addresses, a type field for protocol identification, and a CRC for error detection. These elements ensure that devices can correctly receive, interpret, and validate the data being transmitted.

**Key points** (slide quote → follow-up → expected answer):
- **Ethernet frames encapsulate higher-layer data such as IP packets.**  
  quote: "Sending interface encapsulates IP datagram (or other network layer protocol packet) in Ethernet frame"  
  follow-up: _Why is it important for Ethernet to encapsulate higher-layer data?_  
  expected: Encapsulation allows Ethernet to provide a standardized way to deliver data across different network layers, ensuring compatibility and proper routing.
- **The frame structure includes synchronization patterns to align sender and receiver clocks.**  
  quote: "Used to synchronize receiver, sender clock rates"  
  follow-up: _What would happen if the sender and receiver clocks were not synchronized?_  
  expected: Without synchronization, the receiver might misinterpret the data stream, leading to errors or data loss.
- **The frame includes a CRC field for error detection.**  
  quote: "CRC: cyclic redundancy check at receiver - error detected: frame is dropped"  
  follow-up: _Why is error detection important in Ethernet communication?_  
  expected: Error detection ensures that only valid data is processed, improving reliability and reducing the risk of corrupted data being passed up the protocol stack.

### [DHCP] Explain how a DHCP client and server coordinate to assign an IP address to a host, and why this process is important for network management.
*confidence 0.91 · medium · slides [287, 522, 573]*

**Reference:** A DHCP client and server coordinate through a four-step process: the client broadcasts a DHCP discover message, the server responds with a DHCP offer, the client requests an IP address via DHCP request, and the server confirms the assignment with a DHCP ack. This process is important for network management because it allows dynamic IP address allocation, supports mobile users, and enables efficient reuse of IP addresses across the network.

**Key points** (slide quote → follow-up → expected answer):
- **DHCP allows dynamic IP address allocation.**  
  quote: "Dynamic Host Configuration Protocol - assign IP addresses to computers in a network dynamically."  
  follow-up: _What happens if a device is connected to the network but doesn't receive an IP address?_  
  expected: The device cannot communicate on the network, as it lacks a valid IP address.
- **DHCP supports mobile users who join/leave the network.**  
  quote: "support for mobile users who join/leave network"  
  follow-up: _Why is it important for a network to support mobile users?_  
  expected: It ensures that users can maintain connectivity as they move between different network segments.
- **DHCP uses a client-server model with specific message exchanges.**  
  quote: "A client-server model & based on discovery, offer, request, and ACK."  
  follow-up: _What would happen if the DHCP server did not respond to a DHCP discover message?_  
  expected: The client would not receive an IP address and would be unable to communicate on the network.

### [Firewalls] Explain how a firewall enforces security rules at different layers of the network stack, and why this matters for network security.
*confidence 0.91 · medium · slides [109]*

**Reference:** A firewall monitors incoming and outgoing network traffic and decides whether to allow or block specific traffic based on a defined set of security rules. It can be used in the transport layer or the application layer, which means it can inspect data at different levels of detail. Using it at the transport layer allows it to make decisions based on port numbers, while at the application layer it can inspect the actual content of the data. This matters for network security because inspecting at a higher layer allows for more precise control over the types of traffic that are allowed or blocked.

**Key points** (slide quote → follow-up → expected answer):
- **Firewalls can operate at different layers of the network stack.**  
  quote: "It can used in the transport layer or the application layer"  
  follow-up: _What difference does it make if a firewall operates at the transport layer versus the application layer?_  
  expected: Operating at the transport layer allows the firewall to make decisions based on port numbers, while at the application layer it can inspect the actual content of the data.
- **Firewalls make decisions based on a defined set of security rules.**  
  quote: "Network security device that monitors incoming and outgoing network traffic and decides whether to allow or block specific traffic based on a defined set of security rules"  
  follow-up: _How do the rules influence the firewall's behavior?_  
  expected: The rules define what traffic is allowed or blocked, so they determine the firewall's filtering behavior and the level of security it provides.
- **Operating at different layers affects the level of detail the firewall can inspect.**  
  quote: "It can used in the transport layer or the application layer"  
  follow-up: _Why would a firewall inspect data at the application layer?_  
  expected: Because inspecting at the application layer allows the firewall to examine the actual content of the data, enabling more precise and granular control over network traffic.

### [Throughput and bottleneck link] In a network with multiple client-server pairs sharing a common middle link, how does the bottleneck link affect the end-to-end throughput for each pair?
*confidence 0.91 · medium · slides [74, 128, 129, 144, 145, 146]*

**Reference:** The bottleneck link limits the maximum end-to-end throughput for each client-server pair because it is the link with the smallest capacity in the path. When the middle link is fairly shared, its capacity is divided among all pairs, reducing the effective capacity available to each. This means the throughput for each pair is constrained by the minimum of the server link capacity, the client link capacity, and the shared link capacity divided by the number of pairs.

**Key points** (slide quote → follow-up → expected answer):
- **The bottleneck link limits the maximum end-to-end throughput for each client-server pair.**  
  quote: "The maximum achievable end-end throughput is the capacity of the link with the minimum capacity."  
  follow-up: _What happens if the shared link has a higher capacity than the server or client links?_  
  expected: The throughput for each pair is still limited by the server or client links, which have lower capacities than the shared link.
- **The shared link capacity is divided among all pairs when it is fairly shared.**  
  quote: "The middle link is fairly shared (divides its transmission rate equally)."  
  follow-up: _Why would the shared link capacity be divided among all pairs?_  
  expected: Because the shared link is used by all pairs simultaneously, its capacity must be divided to ensure fair allocation among them.
- **The throughput for each pair is constrained by the minimum of the server link, client link, and shared link capacity divided by the number of pairs.**  
  quote: "The bottleneck link is the link with the smallest capacity between RS, RC, and R/4."  
  follow-up: _How does the number of pairs affect the shared link capacity available to each pair?_  
  expected: The number of pairs reduces the effective capacity of the shared link for each pair, as the capacity is divided equally among them.

### [ARP] Explain how a device determines the MAC address of another device on the same LAN when it only knows the IP address of that device.
*confidence 0.91 · medium · slides [682, 683, 684, 685, 699, 736]*

**Reference:** A device uses ARP to find the MAC address of another device on the same LAN. When it doesn't have the MAC address in its ARP table, it broadcasts an ARP query with the target IP address. The device with the matching IP address responds with its MAC address. The requesting device then adds this IP-MAC mapping to its ARP table for future use.

**Key points** (slide quote → follow-up → expected answer):
- **ARP is used to find the MAC address of a device when only the IP address is known.**  
  quote: "A wants to send datagram to B. B’s MAC address not in A’s ARP table, so A uses ARP to find B’s MAC address"  
  follow-up: _What happens if the device already knows the MAC address?_  
  expected: It would use the existing entry in its ARP table instead of broadcasting an ARP query.
- **ARP queries are broadcasted to all devices on the LAN.**  
  quote: "A broadcasts ARP query, containing B's IP addr. destination MAC address = FF-FF-FF-FF-FF-FF"  
  follow-up: _Why is the destination MAC address set to FF-FF-FF-FF-FF-FF?_  
  expected: This is the Ethernet broadcast address, ensuring all devices on the LAN receive the ARP query.
- **The ARP table stores IP-MAC mappings with a Time To Live (TTL) value.**  
  quote: "ARP table: each IP node (host, router) - IP/MAC address mappings for some < IP address; MAC address; TTL>"  
  follow-up: _What happens to an ARP table entry when the TTL expires?_  
  expected: The entry is removed from the ARP table, and the device will need to re-query for the MAC address if it is needed again.

### [Transport layer services] How does the transport layer ensure that data sent from one process reaches the correct process on the receiving end?
*confidence 0.91 · medium · slides [158, 297, 326, 453]*

**Reference:** The transport layer ensures correct delivery by using sockets to associate data with the correct process. A socket acts like a door, allowing messages to be sent out and received. The receiving process uses its socket to accept messages, ensuring that data is delivered to the correct application. This process relies on the transport infrastructure to deliver messages to the right socket on the receiving end.

**Key points** (slide quote → follow-up → expected answer):
- **The transport layer uses sockets to associate data with the correct process.**  
  quote: "process sends/receives messages to/from its socket"  
  follow-up: _What happens if a message is sent to the wrong socket?_  
  expected: The message would not be delivered to the correct process, as the socket is the interface through which messages are directed.
- **A socket acts like a door, allowing messages to be sent out and received.**  
  quote: "socket analogous to door"  
  follow-up: _How does the transport layer know which socket to deliver a message to?_  
  expected: The transport layer uses the socket address, which includes the port number, to determine which socket to deliver the message to.
- **The receiving process uses its socket to accept messages, ensuring correct delivery.**  
  quote: "receiving process relies on transport infrastructure on other side of door to deliver message to socket at receiving"  
  follow-up: _What would happen if the receiving process did not have a socket?_  
  expected: The message would not be delivered, as there would be no interface for the transport layer to deliver the data to.

### [Collision and broadcast domains] How does a switch allow multiple simultaneous transmissions without collisions, and what role does the Ethernet protocol play in this?
*confidence 0.90 · medium · slides [110, 718, 719]*

**Reference:** A switch allows multiple simultaneous transmissions without collisions because each link is its own collision domain, and the Ethernet protocol operates in full-duplex mode. This means that each connection between a switch and a host can transmit and receive data simultaneously without interference. The Ethernet protocol ensures that collisions are avoided on each individual link, which is why a switch can support multiple simultaneous transmissions without issues.

**Key points** (slide quote → follow-up → expected answer):
- **Each link is its own collision domain.**  
  quote: "Each link is its own collision domain"  
  follow-up: _If a switch had only one collision domain, how would that affect multiple devices transmitting at the same time?_  
  expected: It would cause collisions because all devices would share the same collision domain, leading to data loss and retransmissions.
- **The Ethernet protocol operates in full-duplex mode.**  
  quote: "Ethernet protocol used on each incoming - no collisions; full duplex"  
  follow-up: _What would happen if Ethernet operated in half-duplex mode on a switch?_  
  expected: Collisions could occur because devices would not be able to transmit and receive simultaneously on the same link.
- **Switching allows A-to-A’ and B-to-B’ to transmit simultaneously, without collisions.**  
  quote: "Switching: A-to-A’ and B-to-B’ can transmit simultaneously, without collisions"  
  follow-up: _Why can't A-to-A’ and C-to-A’ transmit simultaneously?_  
  expected: Because the switch can only forward data to one destination at a time on the same port, and the Ethernet protocol prevents collisions on the same link.

### [TCP vs UDP] How do TCP and UDP differ in their handling of network congestion and throughput guarantees?
*confidence 0.90 · medium · slides [163, 272, 291, 328]*

**Reference:** TCP provides congestion control and guarantees minimum throughput by throttling the sender when the network is overloaded. UDP does not provide congestion control or throughput guarantees, allowing the sender to transmit data at full speed regardless of network conditions. This makes TCP suitable for applications that require stable and predictable data transfer, while UDP is better suited for applications that prioritize speed over reliability.

**Key points** (slide quote → follow-up → expected answer):
- **TCP provides congestion control to throttle the sender when the network is overloaded.**  
  quote: "congestion control: throttle congestion control, timing, sender when network overloaded throughput guarantee"  
  follow-up: _What happens if a TCP sender continues to send data when the network is already congested?_  
  expected: The sender will be throttled by TCP's congestion control mechanisms to prevent further network overload.
- **TCP guarantees minimum throughput under congestion.**  
  quote: "congestion control: throttle congestion control, timing, sender when network overloaded throughput guarantee"  
  follow-up: _How does TCP ensure that it maintains a minimum throughput during network congestion?_  
  expected: TCP uses algorithms like congestion window adjustments to maintain a minimum throughput while avoiding network overload.
- **UDP does not provide congestion control or throughput guarantees.**  
  quote: "does not provide: timing, security, or connection minimum throughput guarantee, setup."  
  follow-up: _Why might an application choose UDP over TCP if it requires high speed?_  
  expected: Because UDP does not throttle the sender, allowing for faster data transmission even under network congestion.

### [Go-Back-N and Selective Repeat] Explain how the sender and receiver manage retransmissions and window advancement in Selective Repeat, and why this approach is more efficient than Go-Back-N in certain scenarios.
*confidence 0.90 · medium · slides [388, 389, 390, 392]*

**Reference:** In Selective Repeat, the sender retransmits only the unacknowledged packets individually, while the receiver acknowledges each correctly received packet individually. This allows the sender to advance the window base only when the smallest unacknowledged packet is acknowledged, which improves efficiency in cases of partial packet loss. The receiver buffers out-of-order packets and delivers them in order once the sequence is complete, which reduces the need for retransmitting multiple packets in case of a single lost packet.

**Key points** (slide quote → follow-up → expected answer):
- **The sender retransmits only the unacknowledged packets individually.**  
  quote: "sender times-out/retransmits individually for upper layer unACKed packets"  
  follow-up: _What happens if a packet in the middle of the window is lost and not acknowledged?_  
  expected: The sender will retransmit only that specific packet, not the entire window, which is more efficient than Go-Back-N.
- **The receiver acknowledges each correctly received packet individually.**  
  quote: "receiver individually acknowledges all correctly received packets"  
  follow-up: _Why would the receiver need to acknowledge packets individually?_  
  expected: To allow the sender to advance the window base incrementally, and to enable the receiver to buffer out-of-order packets for later delivery.
- **The sender advances the window base only when the smallest unacknowledged packet is acknowledged.**  
  quote: "if n smallest unACKed packet, advance window base to next unACKed seq #"  
  follow-up: _How does this differ from Go-Back-N's window advancement?_  
  expected: In Go-Back-N, the window advances when any packet in the window is acknowledged, whereas in Selective Repeat, it only advances when the smallest unacknowledged packet is acknowledged.

### [ARP] What happens if a device tries to send a packet to another device on the same LAN, but the target device’s MAC address is not in the sender’s ARP table, and the sender has no prior knowledge of the target’s IP address?
*confidence 0.84 · hard · slides [682, 683, 684, 685, 699, 736] · ⚠ NEEDS REVIEW*

**Reference:** The sender will broadcast an ARP query to all devices on the LAN to request the MAC address of the target device. This ARP query includes the target’s IP address and is sent to the broadcast MAC address FF-FF-FF-FF-FF-FF. The target device, upon receiving the ARP query, will respond with its MAC address in an ARP reply. The sender then adds this IP-to-MAC mapping to its ARP table with a Time To Live (TTL) value, ensuring the entry is valid for a limited period.

**Key points** (slide quote → follow-up → expected answer):
- **The sender broadcasts an ARP query to the broadcast MAC address.**  
  quote: "A broadcasts ARP query, containing B's IP addr; destination MAC address = FF-FF-FF-FF-FF-FF"  
  follow-up: _What is the purpose of sending the ARP query to the broadcast MAC address?_  
  expected: Sending the ARP query to the broadcast MAC address ensures that all devices on the LAN receive the request, allowing the target device to identify itself and respond.
- **The ARP query includes the target’s IP address.**  
  quote: "A broadcasts ARP query, containing B's IP addr"  
  follow-up: _Why is the target’s IP address included in the ARP query?_  
  expected: The IP address is included so that the target device can recognize the query as being directed to it, even though the query is broadcasted to all devices.
- **The target device responds with its MAC address in an ARP reply.**  
  quote: "B replies to A with ARP response"  
  follow-up: _What happens if the target device does not respond to the ARP query?_  
  expected: If the target device does not respond, the sender may retry the ARP query or fall back to other mechanisms, such as using a proxy ARP or routing tables, depending on the network configuration.
- **The sender adds the IP-to-MAC mapping to its ARP table with a TTL.**  
  quote: "ARP table: each IP node (host, router) - IP/MAC address mappings for some < IP address; MAC address; TTL>"  
  follow-up: _Why is the TTL value important in the ARP table?_  
  expected: The TTL value ensures that the ARP table remains up-to-date by removing outdated entries, preventing the use of stale MAC addresses that may no longer be valid.

### [ICMP] Explain what ICMP is used for in computer networks.
*confidence 0.82 · easy · slides [580, 581]*

**Reference:** ICMP is used by hosts and routers to communicate network-layer issues. It is commonly used for error reporting, such as when a destination is unreachable. ICMP messages are carried as IP packets and include various types and codes to indicate specific conditions.

**Key points** (slide quote → follow-up → expected answer):
- **ICMP is used by hosts and routers to communicate network-layer issues.**  
  quote: "Used by hosts and routers to communicate network-layer 0 0 echo reply (ping)"  
  follow-up: _What happens when a router detects a problem with a packet it receives?_  
  expected: It may send an ICMP message to inform the source host about the issue, such as a destination unreachable.
- **ICMP is commonly used for error reporting.**  
  quote: "Typical use of ICMP is for error"  
  follow-up: _Can you give an example of an ICMP message used for error reporting?_  
  expected: An example is the 'Destination network unreachable' message, which indicates that a packet's destination network is not reachable.

### [TCP vs UDP] Explain one key difference between TCP and UDP in terms of reliability and connection setup.
*confidence 0.82 · easy · slides [163, 272, 291, 328]*

**Reference:** TCP provides reliable transport and requires a connection setup between client and server, while UDP does not provide reliability and has no connection setup. This means TCP guarantees data delivery and order, whereas UDP sends datagrams without ensuring they arrive or are in the correct sequence.

**Key points** (slide quote → follow-up → expected answer):
- **TCP requires a connection setup.**  
  quote: "connection-oriented: setup required between client and server processes"  
  follow-up: _Does UDP require a handshake before sending data?_  
  expected: No, UDP does not require a handshake and sends data immediately.
- **UDP does not provide reliability.**  
  quote: "UDP provides unreliable transfer of groups of bytes ('datagrams') between client and server"  
  follow-up: _Why would an application choose UDP over TCP?_  
  expected: Because UDP is faster and more efficient for applications that can tolerate packet loss, such as streaming media.

### [CSMA/CD and CSMA/CA] Explain how CSMA/CD differs from CSMA/CA in terms of handling collisions.
*confidence 0.82 · easy · slides [673]*

**Reference:** CSMA/CD is used in wired networks and detects collisions by monitoring the channel during transmission. If a collision is detected, the transmission is stopped immediately. CSMA/CA, on the other hand, is used in wireless networks and avoids collisions by requiring stations to wait for a random backoff time before transmitting, even if the channel appears idle.

**Key points** (slide quote → follow-up → expected answer):
- **CSMA/CD detects collisions during transmission and stops them immediately.**  
  quote: "If someone else begins talking at the same time, collisions detected within short time, stop talking – Collision Detection"  
  follow-up: _What happens if a collision is not detected in CSMA/CD?_  
  expected: The transmission continues, leading to wasted channel time and potential retransmission overhead.
- **CSMA/CD is suitable for wired networks due to the ease of collision detection.**  
  quote: "Collision detection easy in wired, difficult with wireless"  
  follow-up: _Why is collision detection harder in wireless networks?_  
  expected: Because wireless signals cannot be easily monitored for collisions due to the nature of radio frequency communication.

### [Link state routing] Explain what a link-state routing algorithm is and how it differs from other routing methods.
*confidence 0.82 · easy · slides [607, 608, 610, 611]*

**Reference:** A link-state routing algorithm is a centralized method where all nodes share the same network topology and link costs. This allows each node to compute the least-cost paths to all other nodes independently. Unlike distance-vector routing, link-state routing ensures all nodes have identical information about the network, enabling accurate and consistent path calculations.

**Key points** (slide quote → follow-up → expected answer):
- **A link-state routing algorithm is centralized.**  
  quote: "centralized: network topology, link notation costs known to all nodes"  
  follow-up: _What does it mean for a routing algorithm to be centralized?_  
  expected: It means that all nodes have access to the same complete information about the network topology and link costs.
- **Each node computes the least-cost paths to all other nodes.**  
  quote: "computes least cost paths from one of least-cost-path from source to all other nodes"  
  follow-up: _How does a node compute the least-cost paths to all other nodes?_  
  expected: It uses an algorithm like Dijkstra's to iteratively find the shortest paths based on the known network topology and link costs.

### [HTTPS and TLS] Explain how HTTPS ensures secure communication between a browser and a server.
*confidence 0.82 · easy · slides [186, 187, 188, 189]*

**Reference:** HTTPS ensures secure communication by using TLS to encrypt all data exchanged between the browser and the server. This encryption is bi-directional, meaning both the client and server encrypt and decrypt data. The process involves the use of public and private keys, where the server's public key is used to encrypt a symmetric key that is then used for efficient data encryption during the session.

**Key points** (slide quote → follow-up → expected answer):
- **HTTPS uses TLS to encrypt all communications between the browser and the server.**  
  quote: "HTTPS is HTTP with encryption – All communications between browser and server are encrypted (bi-directional)."  
  follow-up: _What happens if the communication isn't encrypted?_  
  expected: The data could be intercepted and read by attackers, compromising the privacy and integrity of the information.
- **HTTPS relies on public and private key pairs for secure communication.**  
  quote: "HTTPS is based on public/private-key. The public key is used for encryption."  
  follow-up: _How does the server prove it is who it says it is?_  
  expected: The server provides a certificate signed by a trusted Certificate Authority, which the browser verifies to confirm the server's identity.

### [Network edge and access networks] Explain how a DSL modem connects a home network to the Internet.
*confidence 0.81 · easy · slides [19, 20, 21, 24, 25, 26]*

**Reference:** A DSL modem connects a home network to the Internet by using existing telephone lines to transmit data. It separates the voice and data signals on the same line using a splitter. The modem sends data over a high-speed downstream channel and receives data over a medium-speed upstream channel, allowing the home network to access the Internet through the DSL access multiplexer at the central office.

**Key points** (slide quote → follow-up → expected answer):
- **DSL uses existing telephone lines to transmit data.**  
  quote: "use existing telephone line to central office DSLAM"  
  follow-up: _What is the purpose of using telephone lines for data transmission in DSL?_  
  expected: The purpose is to leverage existing infrastructure, reducing the cost and complexity of deploying new wiring for internet access.
- **DSL provides an asymmetric access model with different speeds for upstream and downstream.**  
  quote: "24-52 Mbps – downstream transmission rate • 3.5-16 Mbps – upstream transmission rate • Asymmetric access"  
  follow-up: _Why is the upstream speed typically lower than the downstream speed in DSL?_  
  expected: This is because most users consume more data downstream (e.g., streaming, browsing) than upstream (e.g., uploading), so higher downstream speeds are prioritized.

### [TCP connection establishment] Explain what happens during the TCP connection establishment process.
*confidence 0.81 · easy · slides [419]*

**Reference:** During TCP connection establishment, the sender and receiver perform a handshake to agree to establish a connection and to agree on connection parameters such as starting sequence numbers. This handshake ensures both sides are ready to communicate. The process begins with the sender sending a SYN segment to the receiver.

**Key points** (slide quote → follow-up → expected answer):
- **TCP connection establishment involves a handshake to agree to establish a connection.**  
  quote: "before exchanging data, sender/receiver “handshake” agree to establish connection (each knowing the other willing to establish connection)"  
  follow-up: _What is the purpose of the handshake in TCP connection establishment?_  
  expected: The purpose of the handshake is to ensure both the sender and receiver are willing to establish a connection and to agree on the parameters needed for communication.
- **TCP connection establishment includes agreement on connection parameters such as starting sequence numbers.**  
  quote: "agree on connection parameters (e.g., starting seq #s)"  
  follow-up: _Why is it important to agree on starting sequence numbers during connection establishment?_  
  expected: It is important to agree on starting sequence numbers so that both sides can correctly track and acknowledge data transmission, ensuring reliable communication.

### [Switching and VLANs] Explain how a self-learning switch builds its MAC address table.
*confidence 0.80 · easy · slides [717, 721, 724, 725]*

**Reference:** A self-learning switch builds its MAC address table by recording the sender's MAC address and the interface it was received on. When a frame is received, the switch examines the source MAC address and associates it with the incoming port. This process is automatic and requires no manual configuration. The switch updates its table whenever it receives a new frame from a device, allowing it to forward future frames more efficiently.

**Key points** (slide quote → follow-up → expected answer):
- **A self-learning switch learns which hosts are connected by recording the sender's MAC address and the interface it was received on.**  
  quote: "Switch learns which hosts can be - When frame received, switch - Records sender/location pair in - Switch table MAC addr interface"  
  follow-up: _What happens if a device sends a frame from a different port than before?_  
  expected: The switch updates the MAC address table to reflect the new port, replacing the old entry with the new one.
- **The MAC address table is used to selectively forward frames to the correct port.**  
  quote: "Switch is a link-layer device: takes an active role - Store, forward Ethernet frames - Examine incoming frame’s MAC address, selectively forward frame to one-or-more outgoing links when frame is to be forwarded on segment"  
  follow-up: _What happens if the destination MAC address is not in the switch's table?_  
  expected: The switch forwards the frame to all ports except the one it was received on, using a process called flooding.

### [Network devices] Consider a scenario where a network administrator is deciding between using a Repeater and a Switch to connect two segments of a network. What are the key differences in their operation and how might these differences affect network performance?
*confidence 0.80 · hard · slides [99, 100, 101, 104] · ⚠ NEEDS REVIEW*

**Reference:** A Repeater operates at the Physical Layer and regenerates signals to extend the reach of a network, while a Switch operates at the Data Link Layer and uses MAC addresses to forward data directly to the intended device. The Repeater broadcasts all data to all connected devices, which can lead to increased collisions and reduced network efficiency. In contrast, a Switch reduces collisions by only forwarding data to the intended recipient, improving overall network performance. These differences mean that a Repeater is suitable for extending a single segment, whereas a Switch is better for managing multiple devices in a more intelligent and efficient manner.

**Key points** (slide quote → follow-up → expected answer):
- **A Repeater regenerates signals to extend the reach of a network.**  
  quote: "Regenerate the signal over the same network before the signal becomes too weak or corrupted to extend the length to which the signal can be transmitted over the same network"  
  follow-up: _What happens if a signal becomes too weak or corrupted in a network segment?_  
  expected: The signal may become unreliable or lost, which is why a Repeater is used to regenerate and extend its reach.
- **A Repeater broadcasts all data to all connected devices.**  
  quote: "Hubs broadcast data to all connected devices, regardless of the intended recipient."  
  follow-up: _How does this behavior affect network efficiency?_  
  expected: It leads to increased collisions and reduced bandwidth efficiency, as all devices receive every packet.
- **A Switch uses MAC addresses to forward data directly to the intended device.**  
  quote: "An intelligent network device, functioning as a multiport bridge, uses MAC addresses to forward data packets to the appropriate destination ports."  
  follow-up: _Why is using MAC addresses beneficial in a network?_  
  expected: It allows the Switch to direct traffic only to the intended recipient, reducing unnecessary traffic and collisions.
- **A Switch reduces collisions by only forwarding data to the intended recipient.**  
  quote: "Store MAC addresses of connected devices, routing communication only to the intended destination, reducing collisions and eliminating"  
  follow-up: _How does this compare to the behavior of a Repeater?_  
  expected: A Repeater broadcasts all data, leading to more collisions, while a Switch forwards data only to the intended recipient, minimizing collisions.

### [Network delays] How does the store-and-forward mechanism in packet switching affect the end-to-end delay in a network with multiple hops?
*confidence 0.78 · medium · slides [36, 37, 116, 117, 118, 141]*

**Reference:** The store-and-forward mechanism requires that an entire packet must arrive at a router before it can be transmitted on the next link. This means that the transmission delay of each hop is added to the end-to-end delay, as the packet cannot move to the next link until it has fully arrived. Additionally, the propagation delay of each link is also added, as the signal must travel the physical distance of the link. Therefore, the total end-to-end delay is the sum of all transmission and propagation delays across the network hops.

**Key points** (slide quote → follow-up → expected answer):
- **The transmission delay of each hop is added to the end-to-end delay.**  
  quote: "- Transmission delay: takes L/R seconds to transmit (push out) L-bit packet into"  
  follow-up: _Why is the transmission delay of each hop added to the end-to-end delay?_  
  expected: Because the packet must be fully transmitted onto the link before the next hop can begin transmitting, so each hop's transmission delay contributes to the total delay.
- **The propagation delay of each link is also added to the end-to-end delay.**  
  quote: "The speed of light propagation delay on each link is 3x10**8 m/sec"  
  follow-up: _How does the physical distance of a link affect the end-to-end delay?_  
  expected: The longer the physical distance of a link, the greater the propagation delay, which increases the total end-to-end delay.

### [CIDR] Explain how CIDR allows for more efficient allocation of IP addresses compared to traditional class-based addressing.
*confidence 0.78 · medium · slides [508, 509]*

**Reference:** CIDR allows for more efficient allocation of IP addresses by enabling variable-length subnet masks, which means the subnet portion of an address can be of arbitrary length. This flexibility reduces the number of wasted IP addresses that were common with class-based addressing.

**Key points** (slide quote → follow-up → expected answer):
- **CIDR allows for variable-length subnet masks.**  
  quote: "subnet portion of address of arbitrary length"  
  follow-up: _What is the main advantage of having a subnet portion of arbitrary length?_  
  expected: It allows for more efficient allocation of IP addresses by enabling flexible subnet sizes.
- **CIDR addresses are written in the format a.b.c.d/x.**  
  quote: "address format: a.b.c.d/x, where x is # bits in subnet"  
  follow-up: _How does the format a.b.c.d/x help in CIDR?_  
  expected: It clearly indicates the number of bits used for the subnet portion, making it easier to determine the network and host portions of an IP address.

### [TCP connection establishment] Why does TCP use a three-way handshake to establish a connection, rather than a two-way handshake?
*confidence 0.78 · medium · slides [419]*

**Reference:** TCP uses a three-way handshake to ensure both the sender and receiver agree to establish the connection and to synchronize their initial sequence numbers. A two-way handshake would not guarantee that both parties are ready to communicate, which could lead to lost data or failed connections. The three-way handshake allows each side to confirm the other's willingness to connect and to exchange initial sequence numbers, ensuring reliable communication.

**Key points** (slide quote → follow-up → expected answer):
- **TCP uses a three-way handshake to ensure both parties agree to establish the connection.**  
  quote: "agree to establish connection (each knowing the other willing to establish connection)"  
  follow-up: _What would happen if only one side sent a connection request and the other did not respond?_  
  expected: The connection would not be established, and the initiating side might remain in a waiting state, leading to potential resource waste and failed communication.
- **A two-way handshake would not guarantee mutual acknowledgment of the connection request.**  
  quote: "agree to establish connection (each knowing the other willing to establish connection)"  
  follow-up: _What is the risk of using a two-way handshake in a network with packet loss?_  
  expected: The receiving side might not receive the connection request, leading to a failed connection and potential retransmission issues.

### [IPv4 addressing] Explain how the default subnet mask for a Class C network is derived from its classful addressing structure.
*confidence 0.78 · medium · slides [510, 511, 512, 515, 516]*

**Reference:** The default subnet mask for a Class C network is derived from its classful addressing structure, where the first 24 bits are reserved for the network ID and the remaining 8 bits are for the host ID. This results in a subnet mask of 255.255.255.0. The subnet mask defines which portion of the IP address is the network and which is the host, enabling proper routing and communication within the network.

**Key points** (slide quote → follow-up → expected answer):
- **The subnet mask is derived from the division of the IP address into network and host portions.**  
  quote: "Network portion - 8, 16, or 24 bits in length – known as Class A, B and C networks respectively."  
  follow-up: _How does the subnet mask reflect the network and host portions of an IP address?_  
  expected: The subnet mask uses 1s for the network portion and 0s for the host portion, indicating which bits are fixed and which can vary.
- **The subnet mask is used to determine the network and host portions of an IP address.**  
  quote: "The addresses in color are the default masks for classes A, B, and C."  
  follow-up: _What is the purpose of the default subnet mask in a Class C network?_  
  expected: The default subnet mask helps identify the network and host portions of an IP address, which is essential for routing and communication.

### [Network edge and access networks] Explain how the structure of access networks affects the performance of a home network.
*confidence 0.78 · medium · slides [19, 20, 21, 24, 25, 26]*

**Reference:** The structure of access networks directly influences the performance of a home network by determining the available bandwidth, the type of connection (shared or dedicated), and the physical medium used. For example, a DSL connection provides asymmetric access with higher downstream speeds than upstream, which can impact how data is transferred from the internet to local devices. Additionally, the presence of a router and firewall in the home network can affect latency and security, shaping the overall user experience.

**Key points** (slide quote → follow-up → expected answer):
- **The physical medium and transmission rates of the access network determine the available bandwidth for the home network.**  
  quote: "24-52 Mbps – downstream transmission rate, 3.5-16 Mbps – upstream transmission rate, Asymmetric access"  
  follow-up: _What happens if the access network has a lower bandwidth?_  
  expected: The home network would experience slower data transfer rates, especially for downstream activities like streaming or downloading.
- **Shared or dedicated access among users affects the consistency of performance in a home network.**  
  quote: "What to look for: ▪ Transmission rate (bits per second of access network? ▪ Shared or dedicated access among users?"  
  follow-up: _How does shared access impact the home network?_  
  expected: Shared access can lead to variable performance, as bandwidth is divided among multiple users, potentially causing congestion during peak times.

### [IPv6] Explain how IPv6 datagrams can be transmitted across a network that contains both IPv6 and IPv4 routers, and why this is important for network transition.
*confidence 0.78 · medium · slides [585, 595, 597]*

**Reference:** IPv6 datagrams can be transmitted across a network with mixed IPv6 and IPv4 routers through tunneling, where the IPv6 datagram is encapsulated within an IPv4 datagram. This allows IPv6 traffic to traverse IPv4-only segments of the network. This is important for network transition because it enables gradual migration without requiring all routers to be upgraded simultaneously, avoiding the need for a 'flag day' that could disrupt existing services.

**Key points** (slide quote → follow-up → expected answer):
- **IPv6 datagrams can be transmitted across a network with mixed IPv6 and IPv4 routers through tunneling.**  
  quote: "IPv4 datagram tunneling: IPv6 datagram as payload in a IPv4 datagram"  
  follow-up: _What happens if there are no IPv4 routers in the network?_  
  expected: The IPv6 datagram would be directly transmitted over the link-layer without encapsulation, as both routers support IPv6.
- **Tunneling allows for gradual migration without requiring all routers to be upgraded simultaneously.**  
  quote: "not all routers can be upgraded simultaneously; no 'flag days'"  
  follow-up: _What would happen if all routers were upgraded at once?_  
  expected: A 'flag day' would occur, which could disrupt existing services and require a complete network shutdown for the transition.

### [Multiple access protocols] Explain how random access protocols like ALOHA manage collisions and why they are different from channel partitioning protocols like TDMA.
*confidence 0.78 · medium · slides [672]*

**Reference:** Random access protocols like ALOHA allow multiple nodes to transmit simultaneously, which can lead to collisions. However, they are designed to recover from these collisions through mechanisms like retransmission after a random delay. In contrast, channel partitioning protocols like TDMA divide the channel into time slots and allocate them exclusively to nodes, which prevents collisions but requires strict scheduling.

**Key points** (slide quote → follow-up → expected answer):
- **Random access protocols allow collisions but recover from them.**  
  quote: "channel not divided, allow collisions, 'recover' from collisions"  
  follow-up: _What happens if two nodes transmit at the same time in a random access protocol?_  
  expected: They may collide, but the protocol is designed to detect the collision and allow retransmission after a random delay.
- **Channel partitioning protocols prevent collisions by allocating exclusive time slots.**  
  quote: "divide channel into smaller 'pieces', allocate piece to node for exclusive use"  
  follow-up: _Why would a protocol like TDMA not need to handle collisions?_  
  expected: Because each node is allocated a specific time slot, so only one node transmits at a time, eliminating the possibility of collision.

### [TCP connection termination] Explain how TCP handles the termination of a connection when both the client and server send FIN segments at the same time.
*confidence 0.78 · medium · slides [421, 422]*

**Reference:** TCP allows for simultaneous FIN exchanges by combining the ACK with the own FIN. When a side receives a FIN, it responds with an ACK, and if it also wishes to close, it sends its own FIN in the same segment. This avoids the need for a full four-way handshake in this specific case, reducing the number of packets exchanged.

**Key points** (slide quote → follow-up → expected answer):
- **TCP allows for simultaneous FIN exchanges by combining the ACK with the own FIN.**  
  quote: "simultaneous FIN exchanges can be handled - on receiving FIN, ACK can be combined with own FIN"  
  follow-up: _What happens if both sides send a FIN at the same time without combining the ACK?_  
  expected: The receiving side would acknowledge the received FIN and send its own FIN in the same packet, avoiding the need for a full four-way handshake.
- **When a side receives a FIN, it responds with an ACK.**  
  quote: "respond to received FIN with ACK"  
  follow-up: _What is the purpose of sending an ACK in response to a received FIN?_  
  expected: The ACK confirms receipt of the FIN and ensures the other side knows the connection is being closed properly.

### [TCP flow control] Explain how TCP flow control prevents the sender from overwhelming the receiver's buffer.
*confidence 0.78 · medium · slides [163, 399, 415, 417]*

**Reference:** TCP flow control ensures the sender does not overwhelm the receiver's buffer by having the receiver advertise its available buffer space through the rwnd field in the TCP header. The sender limits the amount of unACKed data it can transmit based on this advertised window size. This mechanism guarantees that the receiver's buffer will not overflow, even if the network layer delivers data faster than the application layer can process it.

**Key points** (slide quote → follow-up → expected answer):
- **The receiver advertises its available buffer space through the rwnd field in the TCP header.**  
  quote: "TCP receiver “advertises” free buffer space in rwnd field in TCP header"  
  follow-up: _What happens if the receiver's buffer is full?_  
  expected: The receiver will advertise a window size of zero, which tells the sender to stop transmitting until more buffer space is available.
- **TCP flow control guarantees the receiver's buffer will not overflow.**  
  quote: "guarantees receive buffer will not overflow"  
  follow-up: _How does the sender know how much data it can send at any time?_  
  expected: The sender uses the receiver's advertised window size in the TCP header to determine the maximum amount of data it can send without overwhelming the receiver.

### [Persistent vs non-persistent HTTP] Explain how persistent HTTP improves the response time for downloading multiple objects compared to non-persistent HTTP.
*confidence 0.78 · medium · slides [172, 175, 176]*

**Reference:** Persistent HTTP improves response time by reusing a single TCP connection for multiple objects, reducing the number of round trips needed. In non-persistent HTTP, each object requires a new TCP connection, which adds two RTTs per object. Persistent HTTP allows multiple objects to be sent over a single TCP connection, reducing the total number of RTTs and improving efficiency.

**Key points** (slide quote → follow-up → expected answer):
- **Persistent HTTP reuses a single TCP connection for multiple objects.**  
  quote: "multiple objects can be sent over TCP connection"  
  follow-up: _What happens if you need to download multiple objects with non-persistent HTTP?_  
  expected: You need to open a new TCP connection for each object, which increases the number of round trips and slows down the download.
- **Non-persistent HTTP requires two RTTs per object.**  
  quote: "Non-persistent HTTP response time = 2RTT+ file transmission time"  
  follow-up: _Why does non-persistent HTTP have two RTTs per object?_  
  expected: Because it requires one RTT to establish the TCP connection and another RTT for the HTTP request and initial response.

### [UDP] Explain why UDP is suitable for streaming multimedia applications, and how its design supports this use case.
*confidence 0.77 · medium · slides [327, 328]*

**Reference:** UDP is suitable for streaming multimedia applications because it provides a 'best effort' service with no connection establishment or congestion control. This allows for low-latency transmission, which is critical for real-time media. Additionally, UDP segments can be delivered out-of-order, which aligns with how multimedia data is often processed and reassembled by the receiving application.

**Key points** (slide quote → follow-up → expected answer):
- **UDP provides a 'best effort' service with no connection establishment.**  
  quote: "UDP: User Datagram Protocol
- 'no frills,' 'bare bones' Internet transport protocol
    - no connection establishment (which"  
  follow-up: _Why would a protocol without connection establishment be useful for multimedia?_  
  expected: Because it allows for faster transmission without the overhead of setting up a connection, which is critical for real-time applications.
- **UDP segments can be delivered out-of-order.**  
  quote: "UDP: User Datagram Protocol
- 'best effort' service, UDP can add RTT delay) segments may be:
    - no connection state at sender,
  - lost receiver (buffer, seq, ack, c-c
  - delivered out-of-order to parameters)"  
  follow-up: _How does this property help in multimedia streaming?_  
  expected: It allows the receiving application to process data as it arrives, which is often how multimedia data is handled.

### [CSMA/CD and CSMA/CA] How does the human analogy for CSMA/CD differ from that of CSMA/CA, and what does this imply about their behavior in a network?
*confidence 0.77 · medium · slides [673]*

**Reference:** The human analogy for CSMA/CD describes a polite conversationalist who stops talking immediately upon detecting a collision. In contrast, the analogy for CSMA/CA is less specific but implies a more proactive approach to avoiding collisions by listening before speaking. This difference highlights that CSMA/CD relies on detecting collisions during transmission, while CSMA/CA aims to prevent collisions before they occur by listening before transmitting.

**Key points** (slide quote → follow-up → expected answer):
- **CSMA/CD is likened to a polite conversationalist who stops talking upon detecting a collision.**  
  quote: "- human analogy: the polite conversationalist"  
  follow-up: _What does it mean if someone stops talking when they detect a collision?_  
  expected: It means they are using collision detection to immediately stop transmitting and avoid further interference.
- **The difference in analogies reflects how each protocol handles collisions: CSMA/CD detects them during transmission, while CSMA/CA prevents them before transmission.**  
  quote: "CSMA/CD: CSMA with collision detection"  
  follow-up: _How does the behavior of CSMA/CD differ from CSMA/CA in terms of collision handling?_  
  expected: CSMA/CD handles collisions by detecting them and stopping transmission, while CSMA/CA avoids collisions by checking the channel before transmitting.

### [MAC addressing] How does the uniqueness of MAC addresses ensure that data is delivered correctly within a LAN?
*confidence 0.77 · medium · slides [679, 680, 681, 696, 697, 698]*

**Reference:** The uniqueness of MAC addresses ensures that data is delivered correctly within a LAN because each device has a distinct identifier. This allows the LAN switch to forward frames directly to the intended recipient. The 48-bit MAC address is burned into the NIC ROM and is globally unique, which prevents collisions and ensures accurate delivery.

**Key points** (slide quote → follow-up → expected answer):
- **MAC addresses are globally unique across all devices.**  
  quote: "has unique 48-bit MAC address"  
  follow-up: _What would happen if two devices had the same MAC address on the same LAN?_  
  expected: It would cause data to be delivered to the wrong device, leading to communication errors.
- **MAC addresses are burned into the NIC ROM by the manufacturer.**  
  quote: "48-bit MAC address (for most LANs) burned in NIC ROM"  
  follow-up: _How does this manufacturing process ensure uniqueness?_  
  expected: Manufacturers are allocated a portion of the MAC address space by IEEE, ensuring that each address is unique across all devices.

### [Distance vector routing] Explain how the Bellman-Ford algorithm ensures that distance vector routing converges to the correct least-cost paths, and why it is important that nodes update their distance vectors based on their neighbors' information.
*confidence 0.77 · medium · slides [615, 616, 617, 626, 627]*

**Reference:** The Bellman-Ford algorithm ensures convergence by iteratively updating each node’s distance vector using the minimum cost from its neighbors, as described by the equation Dx(y) = minv {cx,v + Dv(y)}. This process allows each node to refine its estimate of the least-cost path over time. It is important that nodes update their distance vectors based on their neighbors' information because this enables the propagation of accurate cost updates across the network, allowing all nodes to eventually agree on the shortest paths.

**Key points** (slide quote → follow-up → expected answer):
- **Each node updates its distance vector using the minimum cost from its neighbors.**  
  quote: "Dx(y) ← minv{cx,v + Dv(y)} for each node y ∊ N"  
  follow-up: _What would happen if a node did not update its distance vector based on its neighbors' information?_  
  expected: The node would not be able to propagate accurate cost information, leading to incorrect routing decisions and potential network inefficiency.
- **The algorithm relies on the exchange of distance vectors between neighbors to propagate correct cost information.**  
  quote: "from time-to-time, each node sends its own distance vector estimate"  
  follow-up: _Why is it important for nodes to send their distance vectors periodically?_  
  expected: It is important because it allows other nodes to update their own distance vectors and propagate accurate cost information throughout the network.

### [ICMP] How does ICMP support network diagnostics, and what are two specific examples of ICMP messages used in this role?
*confidence 0.77 · medium · slides [580, 581]*

**Reference:** ICMP supports network diagnostics by allowing hosts and routers to communicate network-layer issues. One example is the echo request and echo reply messages, used by the ping utility to check connectivity. Another example is the time exceeded message, which helps trace the path of a packet by indicating when its TTL has expired.

**Key points** (slide quote → follow-up → expected answer):
- **The echo request and echo reply messages are used for connectivity testing.**  
  quote: "8 0 echo request (ping)"  
  follow-up: _What is the purpose of the echo request message in ICMP?_  
  expected: The echo request message is used to test if a host is reachable and to measure round-trip time between hosts.
- **The time exceeded message helps trace the path of a packet.**  
  quote: "Other examples of ICMP messages: ... Time exceeded message (TTL)"  
  follow-up: _How does the time exceeded message contribute to network diagnostics?_  
  expected: The time exceeded message indicates when a packet's TTL has expired, which helps trace the path a packet took through the network.

### [TCP congestion control] How does TCP congestion control balance between underutilizing bandwidth and causing congestion collapse?
*confidence 0.76 · medium · slides [443, 444, 448]*

**Reference:** TCP congestion control balances between underutilizing bandwidth and causing congestion collapse by using a feedback mechanism based on acknowledged segments to increase the sending rate, while reducing it when packet loss occurs. This ensures the sender does not send too fast, which could lead to congestion collapse, nor too slowly, which would underutilize the available bandwidth. The algorithm uses a combination of slow start, congestion avoidance, and fast recovery to dynamically adjust the sending rate.

**Key points** (slide quote → follow-up → expected answer):
- **TCP congestion control uses a feedback mechanism based on acknowledged segments to increase the sending rate.**  
  quote: "An acknowledged segment indicates that the network is delivering the sender’s segments to the receiver, and hence, the sender’s rate can be increased when an ACK arrives for a previously unacknowledged segment."  
  follow-up: _What happens if the sender doesn’t receive any ACKs for its segments?_  
  expected: The sender may assume congestion and reduce its sending rate, which helps prevent congestion collapse.
- **TCP congestion control reduces the sending rate when packet loss occurs to prevent congestion collapse.**  
  quote: "A lost segment implies congestion, and hence, the TCP sender’s rate should be decreased when a segment is lost."  
  follow-up: _Why is reducing the sending rate on a loss event important?_  
  expected: It helps prevent congestion collapse by signaling that the network is congested and reducing the sender’s contribution to the congestion.

---

## Held back (low confidence — not used by the app)

### [Network delays] Explain what transmission delay and propagation delay are, and how they contribute to end-to-end delay in a network.
*confidence 0.74 · easy · slides [36, 37, 116, 117, 118, 141]*

**Reference:** Transmission delay is the time it takes to push all the bits of a packet onto the link, calculated as L/R, where L is the packet length and R is the transmission rate. Propagation delay is the time it takes for a bit to travel from one end of the link to the other, calculated as d/s, where d is the distance and s is the speed of light. Both transmission and propagation delays contribute to the total end-to-end delay, which is the sum of all delays across the network links.

**Key points** (slide quote → follow-up → expected answer):
- **Transmission delay is the time it takes to push all the bits of a packet onto the link.**  
  quote: "Transmission delay: takes L/R seconds to transmit (push out) L-bit packet into"  
  follow-up: _What happens if the transmission rate is very high?_  
  expected: The transmission delay decreases because the packet can be pushed out more quickly.
- **Both transmission and propagation delays contribute to the total end-to-end delay.**  
  quote: "Total end-to-end delay is the sum of these six delays: 90 + 1678 + 810 = 2.578 ms"  
  follow-up: _Why is the total end-to-end delay the sum of individual delays?_  
  expected: Because each link contributes its own transmission and propagation delay, and these delays add up as the packet travels through the network.

### [NAT] Explain how NAT helps in securing a local network.
*confidence 0.74 · easy · slides [532, 534, 536, 537]*

**Reference:** NAT secures a local network by making devices inside the network invisible to the outside world. This is because external devices cannot directly address or communicate with internal hosts, as they only see the NAT router's public IP address. The NAT router translates internal private addresses to the public one, preventing direct access to internal devices. This translation also ensures that changes to internal IP addresses do not affect external connectivity. As a result, the network is protected from unsolicited access and potential attacks.

**Key points** (slide quote → follow-up → expected answer):
- **NAT makes internal devices invisible to the outside world.**  
  quote: "security: devices inside local net not directly addressable, visible by outside world"  
  follow-up: _What happens if a device inside the network is directly addressable from the outside?_  
  expected: It becomes vulnerable to attacks and unauthorized access, as external entities can directly target and communicate with it.
- **NAT ensures that changes to internal IP addresses do not affect external connectivity.**  
  quote: "can change addresses of host in local network without notifying outside world"  
  follow-up: _How does NAT allow for flexibility in internal network configuration?_  
  expected: NAT abstracts the internal IP addresses from the outside world, so changes to internal addresses do not require updates to external systems or configurations.

### [MAC addressing] Explain what a MAC address is and how it is used in a network.
*confidence 0.74 · easy · slides [679, 680, 681, 696, 697, 698]*

**Reference:** A MAC address is a 48-bit address used to identify a device at the data link layer. It is used to get a frame from one interface to another physically-connected interface within the same subnet. MAC addresses are burned into the NIC ROM and are unique across all devices.

**Key points** (slide quote → follow-up → expected answer):
- **MAC addresses are burned into the NIC ROM and are unique across all devices.**  
  quote: "48-bit MAC address (for most LANs) burned in NIC ROM, e.g.: 1A-2F-BB-76-09-AD"  
  follow-up: _How are MAC addresses assigned to devices?_  
  expected: MAC addresses are assigned by the manufacturer and are burned into the NIC ROM to ensure uniqueness across all devices.
- **MAC addresses are used to get a frame from one interface to another physically-connected interface within the same subnet.**  
  quote: "used 'locally' to get frame from one interface to another physically-connected interface (same subnet, in"  
  follow-up: _Why is a MAC address important for communication within a LAN?_  
  expected: A MAC address is important for communication within a LAN because it allows devices to directly communicate with each other without needing to rely on higher-layer addressing.

### [Collision and broadcast domains] Explain what a collision domain is and how it differs between hubs and switches.
*confidence 0.74 · easy · slides [110, 718, 719]*

**Reference:** A collision domain is a network segment where data collisions can occur. Hubs operate at the Physical Layer and create a single collision domain, meaning all connected devices share the same bandwidth and can collide during transmission. Switches, operating at the Data Link Layer, create multiple collision domains, with each port having its own domain, allowing for simultaneous, collision-free communication between devices.

**Key points** (slide quote → follow-up → expected answer):
- **Hubs create a single collision domain.**  
  quote: "Collision Domain | Single collision domain | Multiple collision domains (one per port)"  
  follow-up: _Why would a hub cause more collisions than a switch?_  
  expected: Because all devices connected to a hub share the same collision domain, increasing the chance of collisions during transmission.
- **Switches create multiple collision domains, one per port.**  
  quote: "Switching: A-to-A’ and B-to-B’ can transmit simultaneously, without collisions"  
  follow-up: _How does a switch allow multiple devices to transmit without collisions?_  
  expected: Because each port on a switch is its own collision domain, allowing simultaneous, collision-free communication between devices connected to different ports.

### [Packet switching vs circuit switching] Explain how packet switching and circuit switching differ in terms of bandwidth usage and message ordering.
*confidence 0.74 · medium · slides [44, 121, 130, 132, 255]*

**Reference:** Packet switching and circuit switching differ in how they use bandwidth and handle message ordering. In circuit switching, bandwidth is reserved and fixed for the duration of a connection, which saves bandwidth but makes it inflexible. In packet switching, bandwidth is used dynamically and shared among multiple connections, which can waste bandwidth but allows for more flexibility. Additionally, in circuit switching, messages are received in the same order they were sent, while in packet switching, messages may arrive out of order and must be reassembled at the destination.

**Key points** (slide quote → follow-up → expected answer):
- **Circuit switching reserves bandwidth for the duration of a connection.**  
  quote: "Bandwidth is saved (fixed) (dynamic)"  
  follow-up: _What happens to bandwidth when multiple users share a circuit-switched network?_  
  expected: Bandwidth is reserved for each user, which can lead to underutilization if not all users are active at the same time.
- **In packet switching, messages may arrive out of order and must be reassembled at the destination.**  
  quote: "Message received in out of order, assembled at the dest"  
  follow-up: _Why is message ordering important in some applications?_  
  expected: It is important for real-time applications like voice or video, where out-of-order delivery can cause noticeable delays or distortion.

### [IPv4 addressing] Explain how the class of an IPv4 address is determined based on its binary representation.
*confidence 0.73 · easy · slides [510, 511, 512, 515, 516]*

**Reference:** The class of an IPv4 address is determined by the leading bits of its binary form. For example, if the first bit is 0, it is a Class A address. If the first two bits are 10, it is a Class B address. If the first three bits are 110, it is a Class C address. Class D and E addresses are identified by their first four bits being 1110 and 1111, respectively. This classification helps in determining the default subnet mask and the size of the network and host portions.

**Key points** (slide quote → follow-up → expected answer):
- **The class of an IPv4 address is determined by the leading bits of its binary form.**  
  quote: "a. The first bit is 0. This is a class A address."  
  follow-up: _What happens if the first bit is 1?_  
  expected: If the first bit is 1, the address belongs to a Class B, C, D, or E category, depending on the next few bits.
- **Class C addresses start with the binary prefix 110.**  
  quote: "b. The first 2 bits are 1; the third bit is 0. This is a class C address."  
  follow-up: _What is the binary prefix for a Class C address?_  
  expected: The binary prefix for a Class C address is 110.
- **This classification helps in determining the default subnet mask and the size of the network and host portions.**  
  quote: "The addresses in color are the default masks for classes A, B, and C."  
  follow-up: _Why is the classification of IP addresses important?_  
  expected: Classification helps in determining the default subnet mask and the size of the network and host portions, which is essential for routing and addressing in networks.

### [TCP congestion control] Explain what TCP congestion control is and how it avoids congestion collapse.
*confidence 0.72 · easy · slides [443, 444, 448]*

**Reference:** TCP congestion control is a mechanism that allows senders to increase their sending rate until packet loss occurs, which indicates congestion. When a packet is lost, the sender reduces its rate to avoid congestion collapse. The goal is to send at a high rate without congesting the network.

**Key points** (slide quote → follow-up → expected answer):
- **TCP congestion control prevents congestion collapse by reducing the sending rate when packet loss occurs.**  
  quote: "A lost segment implies congestion, and hence, the TCP sender’s rate should be decreased when a segment is lost."  
  follow-up: _What happens if a sender continues to send at full capacity without any packet loss?_  
  expected: The sender may cause congestion collapse, where the network becomes overwhelmed and throughput drops drastically.
- **TCP congestion control uses a feedback mechanism based on acknowledged segments.**  
  quote: "An acknowledged segment indicates that the network is delivering the sender’s segments to the receiver, and hence, the sender’s rate can be increased when an ACK arrives for a previously unacknowledged segment."  
  follow-up: _What does an acknowledgment tell the sender about the network?_  
  expected: An acknowledgment tells the sender that the network is functioning correctly and that it can safely increase its sending rate.

### [NAT] Explain how NAT enables a single public IP address to support multiple devices in a local network.
*confidence 0.70 · medium · slides [532, 534, 536, 537]*

**Reference:** NAT allows all devices in a local network to use a single public IP address by translating their private IP addresses and ports to the public IP and a unique port. This is done by replacing the source IP address and port of outgoing datagrams with the NAT IP address and a new port number. The NAT router maintains a translation table to map these private addresses and ports to the public ones, ensuring that responses from the internet are correctly routed back to the intended device.

**Key points** (slide quote → follow-up → expected answer):
- **NAT translates private IP addresses and ports to a public IP and a new port.**  
  quote: "outgoing datagrams: replace (source IP address, port #) of every outgoing datagram to (NAT IP address, new port #)"  
  follow-up: _How does the NAT router ensure that responses are correctly routed back to the right device?_  
  expected: The NAT router maintains a translation table that maps the public IP and port back to the original private IP and port, allowing it to correctly forward incoming responses.
- **NAT maintains a translation table to track the mapping of private to public addresses and ports.**  
  quote: "remember (in NAT translation table) every (source IP address, port #) to (NAT IP address, new port #) translation pair"  
  follow-up: _What would happen if the NAT router did not maintain this translation table?_  
  expected: The router would not be able to correctly route incoming responses back to the correct device, leading to communication failures.

### [Link state routing] Explain how the Dijkstra’s link-state routing algorithm ensures that all nodes in the network have the same information about the network topology.
*confidence 0.70 · medium · slides [607, 608, 610, 611]*

**Reference:** Dijkstra’s link-state routing algorithm ensures that all nodes have the same information about the network topology by having each node broadcast its local link-state information to all other nodes. This is done through the use of link-state packets that contain details about the direct links and their associated costs. As a result, every node maintains a consistent view of the entire network, which is essential for computing the least-cost paths to all other nodes.

**Key points** (slide quote → follow-up → expected answer):
- **Link-state packets contain details about direct links and their associated costs.**  
  quote: "cx,y: direct link cost from"  
  follow-up: _What kind of information is included in the link-state packets?_  
  expected: Link-state packets include information about direct links and their associated costs.
- **All nodes maintain a consistent view of the entire network.**  
  quote: "all nodes have same info"  
  follow-up: _(generic clarification)_

### [Error detection] What happens if a burst error of exactly r+1 bits occurs in a data stream using CRC codes, and why is this an important limitation for error detection?
*confidence 0.70 · hard · slides [657] · ⚠ NEEDS REVIEW*

**Reference:** If a burst error of exactly r+1 bits occurs, the CRC code may fail to detect the error. This is because the error pattern could align with the generator polynomial, making the remainder zero. This limitation is important because it highlights the trade-off between the length of the CRC and the types of errors it can reliably detect.

**Key points** (slide quote → follow-up → expected answer):
- **CRC codes cannot detect all burst errors of length r+1 bits.**  
  quote: "can detect all burst errors less than r+1 bits"  
  follow-up: _What happens if a burst error of exactly r+1 bits occurs?_  
  expected: It may not be detected because the error pattern could align with the generator polynomial, resulting in a zero remainder.
- **The effectiveness of CRC codes depends on the length of the burst error.**  
  quote: "can detect all burst errors less than r+1 bits"  
  follow-up: _Why is the length of the burst error important for CRC detection?_  
  expected: Because the CRC is designed to detect errors up to r bits, a burst error of r+1 bits may not be detected if it matches the generator polynomial.

### [DHCP] What is the significance of DHCP lease renewal, and how does it impact network resource management?
*confidence 0.70 · hard · slides [287, 522, 573] · ⚠ NEEDS REVIEW*

**Reference:** DHCP lease renewal ensures that a host continues to use an assigned IP address while it remains connected to the network. This mechanism allows network resources to be reused efficiently when a host leaves or rejoins the network. Lease renewal also supports mobile users by enabling them to maintain connectivity without manual reconfiguration.

**Key points** (slide quote → follow-up → expected answer):
- **DHCP lease renewal allows reuse of addresses when a host is no longer connected.**  
  quote: "allows reuse of addresses (only hold address while connected/on)"  
  follow-up: _What happens if a host doesn't renew its lease before the lease expires?_  
  expected: The IP address is reclaimed by the DHCP server and can be reassigned to another host, improving address utilization.
- **DHCP lease renewal supports mobile users who join/leave the network.**  
  quote: "support for mobile users who join/leave network"  
  follow-up: _How does lease renewal help a mobile user maintain connectivity?_  
  expected: It allows the user to retain the same IP address while connected, ensuring consistent network access.

### [Client-server vs peer-to-peer] In a peer-to-peer network, how does the system scale when new peers join, and how does this contrast with a client-server model?
*confidence 0.70 · hard · slides [232, 236] · ⚠ NEEDS REVIEW*

**Reference:** In a peer-to-peer network, new peers bring new service capacity, which enhances scalability. This is because each peer can both request and provide service, distributing the load. In contrast, a client-server model relies on a central server, so adding more clients does not increase the server's capacity, potentially leading to bottlenecks.

**Key points** (slide quote → follow-up → expected answer):
- **Peer-to-peer networks are self-scalable because new peers add service capacity.**  
  quote: "self scalability – new peers bring new service capacity, and new"  
  follow-up: _What happens to the system's capacity when a new peer joins in a P2P network?_  
  expected: The system's capacity increases because the new peer can both request and provide service.
- **In P2P, peers can both request and provide service, unlike in client-server.**  
  quote: "peers request service from other peers, provide service in"  
  follow-up: _How does a peer in a P2P network differ from a client in a client-server model?_  
  expected: A peer in a P2P network can both request and provide service, whereas a client in a client-server model only requests service.

### [TCP flow control] What happens if the sender transmits data faster than the receiver can process it, and how does TCP flow control address this issue without relying on the receiver's buffer size?
*confidence 0.69 · hard · slides [163, 399, 415, 417] · ⚠ NEEDS REVIEW*

**Reference:** TCP flow control ensures that the sender does not overwhelm the receiver by using the receiver's advertised window size (rwnd) to limit the amount of unacknowledged data in flight. The receiver advertises its available buffer space through the rwnd field in the TCP header, which the sender uses to adjust its transmission rate. This mechanism allows the sender to dynamically adapt to the receiver's processing speed without directly relying on the receiver's buffer size, ensuring that the receiver is not overwhelmed by data it cannot process.

**Key points** (slide quote → follow-up → expected answer):
- **TCP flow control uses the receiver's advertised window size (rwnd) to limit the sender's transmission rate.**  
  quote: "TCP receiver 'advertises' free buffer space in rwnd field in TCP header"  
  follow-up: _How does the sender use the rwnd field to control its transmission?_  
  expected: The sender limits the amount of unACKed data to the value of the rwnd field, ensuring it does not exceed the receiver's available buffer space.
- **TCP flow control prevents the sender from overwhelming the receiver without directly relying on the receiver's buffer size.**  
  quote: "flow control: # bytes receiver willing to accept"  
  follow-up: _Can the sender send more data than the receiver's buffer size?_  
  expected: No, the sender is restricted by the rwnd field, which represents the number of bytes the receiver is willing to accept, not necessarily the total buffer size.

### [FTP] How does FTP ensure reliable file transfer between a client and a server?
*confidence 0.69 · medium · slides [285, 286]*

**Reference:** FTP ensures reliable file transfer by using TCP for both the control and data connections. TCP provides reliable, ordered, and error-checked delivery of data. The control connection is used to send commands and receive responses, while the data connection is used for actual file transfer. This dual-connection approach ensures that both command and data are reliably transmitted.

**Key points** (slide quote → follow-up → expected answer):
- **FTP uses TCP for reliable data transmission.**  
  quote: "File Transfer Protocol (FTP) - used to exchange large files on the internet TCP"  
  follow-up: _Why is TCP used instead of UDP for FTP?_  
  expected: TCP provides reliable, ordered, and error-checked delivery, which is essential for transferring large files without corruption.
- **FTP uses a data connection for actual file transfer.**  
  quote: "Data connection (Port No. 20) & Control connection (Port No. 21)"  
  follow-up: _What is the role of the data connection in FTP?_  
  expected: The data connection is used to transfer the actual file content between the client and the server.

### [Distance vector routing] What happens if a node in a distance vector routing system incorrectly reports the cost to a destination, and how does this affect the convergence of the algorithm?
*confidence 0.69 · hard · slides [615, 616, 617, 626, 627] · ⚠ NEEDS REVIEW*

**Reference:** If a node incorrectly reports the cost to a destination, it can cause other nodes to update their distance vectors with incorrect values. This can delay or prevent convergence to the correct least-cost paths. The algorithm relies on the exchange of accurate distance vectors between neighbors to propagate correct cost information, and incorrect values can lead to suboptimal routing decisions until the error is corrected through subsequent updates.

**Key points** (slide quote → follow-up → expected answer):
- **Incorrect cost reports can delay or prevent convergence to the correct least-cost paths.**  
  quote: "under minor, natural conditions, the estimate Dx(y) converge to the actual least cost dx(y)"  
  follow-up: _What would happen if a node started reporting a higher cost than the actual cost to a destination?_  
  expected: It would cause other nodes to potentially select longer paths, delaying convergence until the incorrect information is invalidated by more accurate updates.
- **The algorithm relies on the exchange of accurate distance vectors between neighbors to propagate correct cost information.**  
  quote: "from time-to-time, each node sends its own distance vector estimate"  
  follow-up: _Why is it important for nodes to send their own distance vector estimates?_  
  expected: Because this allows other nodes to update their own distance vectors based on the latest information, which is essential for the algorithm to converge to the correct least-cost paths.

### [UDP] What is the trade-off between UDP's 'no congestion control' and its ability to function in the face of congestion, and how does this affect its use in real-world applications?
*confidence 0.69 · hard · slides [327, 328] · ⚠ NEEDS REVIEW*

**Reference:** UDP's lack of congestion control means it does not reduce transmission rates in response to network congestion, which could lead to increased packet loss and degradation of network performance. However, this also allows UDP to function in the face of congestion by sending data as quickly as possible, which can be beneficial in certain applications. This trade-off makes UDP suitable for applications that prioritize speed over reliability, such as DNS and streaming multimedia, where the application layer may handle reliability or congestion control.

**Key points** (slide quote → follow-up → expected answer):
- **UDP does not reduce transmission rates in response to network congestion.**  
  quote: "UDP can blast away as fast as desired!"  
  follow-up: _What happens if the network becomes congested and UDP continues to send data at full speed?_  
  expected: The network may experience increased packet loss and degradation of performance because UDP does not adjust its sending rate.
- **UDP's design allows it to function in the face of congestion by sending data as quickly as possible.**  
  quote: "UDP can function in the face of congestion"  
  follow-up: _Why might sending data as quickly as possible be an advantage in some cases?_  
  expected: It allows for low-latency communication, which is critical for real-time applications like streaming multimedia.

### [DNS] Explain how the hierarchical structure of DNS enables efficient name resolution, and what happens if a local DNS server does not have the required information.
*confidence 0.68 · hard · slides [211, 215] · ⚠ NEEDS REVIEW*

**Reference:** The hierarchical structure of DNS enables efficient name resolution by allowing queries to move from the root servers down through the domain hierarchy, progressively narrowing the search space. If a local DNS server does not have the required information, it forwards the query to higher-level DNS servers, starting with the root servers, until it finds an authoritative server that can provide the answer.

**Key points** (slide quote → follow-up → expected answer):
- **DNS uses a hierarchical structure to progressively resolve domain names.**  
  quote: "DNS: a distributed, hierarchical database"  
  follow-up: _How does the structure help in resolving domain names?_  
  expected: The structure allows queries to move from the root servers down through the domain hierarchy, progressively narrowing the search space.
- **The process continues until an authoritative DNS server is reached.**  
  quote: "Client wants IP address for www.amazon.com; 1st approximation: - client queries root server to find .com DNS server - client queries .com DNS server to get amazon.com DNS server - client queries amazon.com DNS server to get IP address for www.amazon.com"  
  follow-up: _What happens once the query reaches the correct DNS server?_  
  expected: The authoritative DNS server provides the IP address for the requested domain name.

### [Switching and VLANs] Explain how self-learning switches handle communication between devices connected through multiple switches.
*confidence 0.68 · medium · slides [717, 721, 724, 725]*

**Reference:** Self-learning switches build their MAC address tables by recording the source MAC address and the incoming port whenever a frame is received. When a frame is destined for a device that is not in the table, the switch forwards it to all ports except the one it was received on. This allows the switch to learn the location of the destination device through the responses it receives, even if the destination is connected through another switch.

**Key points** (slide quote → follow-up → expected answer):
- **Communication through multiple switches is handled by the self-learning process across all switches.**  
  quote: "Self-learning switches can be connected together: Q: sending from A to G - how does S1 know to forward frame destined to G via S4 and S3?"  
  follow-up: _How does a switch learn about a device connected through another switch?_  
  expected: The switch learns through the response of the destination device, which is forwarded back through the network.
- **The self-learning process allows switches to dynamically update their MAC address tables as devices communicate.**  
  quote: "Plug-and-play, self-learning - Switches do not need to be configured"  
  follow-up: _What is the benefit of self-learning in a multi-switch network?_  
  expected: Self-learning eliminates the need for manual configuration and allows the network to adapt dynamically as devices communicate.

### [Web caching] Explain how web caching improves network performance, and what trade-offs it introduces.
*confidence 0.63 · hard · slides [197, 198, 199] · ⚠ NEEDS REVIEW*

**Reference:** Web caching improves network performance by reducing the need to fetch objects from the origin server, thereby decreasing response time for clients and reducing traffic on the access link. It also enables content delivery from closer locations, improving latency. However, caching introduces trade-offs such as potential staleness of cached content and increased storage requirements on the cache server.

**Key points** (slide quote → follow-up → expected answer):
- **Web caching reduces the need to fetch objects from the origin server.**  
  quote: "satisfy client request without involving origin server"  
  follow-up: _Why would you want to avoid involving the origin server?_  
  expected: To reduce response time for the client and minimize the load on the origin server and the network.
- **Web caching can improve latency by serving content from closer locations.**  
  quote: "cache is closer to client"  
  follow-up: _How does the location of the cache affect network performance?_  
  expected: A closer cache reduces the end-to-end delay, improving the response time for the client.

### [Persistent vs non-persistent HTTP] What is the trade-off between persistent and non-persistent HTTP in terms of TCP connection management and performance?
*confidence 0.54 · hard · slides [172, 175, 176] · ⚠ NEEDS REVIEW*

**Reference:** Persistent HTTP reuses a single TCP connection for multiple objects, reducing the overhead of opening and closing connections. This allows for as little as one RTT for all objects, improving performance for multiple requests. However, it introduces potential for connection idle time and may require more complex management of the TCP connection. Non-persistent HTTP avoids this complexity by closing the connection after each object, but at the cost of requiring multiple RTTs for each object, increasing response time.

**Key points** (slide quote → follow-up → expected answer):
- **Persistent HTTP reduces the number of TCP connections needed for multiple objects.**  
  quote: "multiple objects can be sent over TCP connection"  
  follow-up: _What happens if a client requests multiple objects from the same server using non-persistent HTTP?_  
  expected: The client would need to open and close a TCP connection for each object, which increases the number of RTTs required.
- **Persistent HTTP can reduce the number of RTTs required for multiple objects.**  
  quote: "as little as one RTT for all"  
  follow-up: _Why might persistent HTTP lead to fewer RTTs compared to non-persistent HTTP?_  
  expected: Because it reuses a single TCP connection, eliminating the need to re-establish the connection for each object.

### [Multiple access protocols] Compare how taking-turns protocols handle node contention with channel partitioning protocols, and explain the trade-off between fairness and efficiency in this context.
*confidence 0.54 · hard · slides [672] · ⚠ NEEDS REVIEW*

**Reference:** Taking-turns protocols allow nodes to take turns, with nodes that have more to send getting longer turns, which ensures fairness. Channel partitioning protocols divide the channel into exclusive pieces, which prevents collisions but can lead to underutilization if some nodes are inactive. The trade-off is that fairness in taking-turns can reduce efficiency by limiting the ability of high-priority or high-data nodes to transmit quickly, while channel partitioning may be less fair but more efficient in utilization.

**Key points** (slide quote → follow-up → expected answer):
- **Taking-turns protocols allow nodes to take turns, with nodes that have more to send getting longer turns.**  
  quote: "nodes take turns, but nodes with more to send can take longer turns"  
  follow-up: _What happens if a node has a lot to send but is not allowed to take longer turns?_  
  expected: It may lead to unfairness, as the node is not able to fully utilize the channel to transmit its data.
- **Channel partitioning protocols divide the channel into exclusive pieces, preventing collisions.**  
  quote: "divide channel into smaller “pieces”; allocate piece to node for exclusive use"  
  follow-up: _What is a potential downside of dividing the channel into exclusive pieces?_  
  expected: It can lead to underutilization if some nodes are inactive, as the allocated time slots are not used.
