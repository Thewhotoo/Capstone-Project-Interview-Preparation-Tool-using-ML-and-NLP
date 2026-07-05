from tavily import TavilyClient
import json
import time

# Put your actual key here!
tavily_client = TavilyClient(api_key="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")

# We broke the subjects down into highly specific technical queries
# This forces Tavily to find deep, niche interview questions instead of just surface-level stuff.
topics = [
    # --- Operating Systems ---
    "Operating Systems Deadlock and Concurrency interview questions and answers",
    "Operating Systems Memory Management and Paging interview questions",
    "Operating Systems CPU Scheduling algorithms interview questions",
    "Operating Systems Threads and Process Management interview questions",
    "Operating Systems File Systems and Storage interview questions",
    
    # --- DBMS ---
    "DBMS ACID properties and transactions interview questions",
    "DBMS Normalization 1NF 2NF 3NF BCNF interview questions",
    "DBMS SQL Joins, Views, and Triggers interview questions",
    "DBMS Indexing, B-Trees, and Hashing interview questions",
    
    # --- Computer Networks ---
    "Computer Networks OSI model layers interview questions",
    "Computer Networks TCP vs UDP and Transport layer interview questions",
    "Computer Networks Subnetting, IPv4, and IP addressing interview questions",
    "Computer Networks Routing protocols OSPF BGP interview questions"
]

scraped_data = []

print("🚀 Starting Deep Tavily Research...")

for topic in topics:
    print(f"Scraping: {topic}")
    try:
        # We bumped max_results to 5 per highly-specific query
        # 13 topics * 5 results = 65 dense pages of technical content
        response = tavily_client.search(
            query=topic, 
            search_depth="advanced", 
            max_results=5
        )
        
        for result in response.get('results', []):
            scraped_data.append({
                "source_topic": topic,
                "url": result['url'],
                "raw_content": result['content']
            })
            
        # A tiny sleep to be polite to the API
        time.sleep(1)
        
    except Exception as e:
        print(f"⚠️ Error scraping '{topic}': {e}")

# Save the massive raw context file
with open("tavily_raw_context.json", "w") as f:
    json.dump(scraped_data, f, indent=4)

print(f"✅ Scraping complete! Gathered {len(scraped_data)} dense pages of context.")