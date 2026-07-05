from tavily import TavilyClient
import requests
from bs4 import BeautifulSoup
import os

# 🔑 Load API key from environment
tavily = TavilyClient(api_key="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")
# ✅ Allowed high-quality domains
ALLOWED_DOMAINS = [
    "wikipedia.org",
    "geeksforgeeks.org",
    "tutorialspoint.com",
    "javatpoint.com",
    "sciencedirect.com",
    "ieee.org",
    "stackoverflow.com"
]

# ❌ Block junk content
BLOCKED_KEYWORDS = [
    "quiz",
    "mcq",
    "practice",
    "test",
    "question",
    "exam"
]


# -------------------------
# 🔎 SEARCH FUNCTION
# -------------------------
def search_web(queries):
    urls = []

    for q in queries:
        try:
            response = tavily.search(query=q, max_results=5)

            for r in response["results"]:
                url = r["url"].lower()

                # ✅ domain filter
                if not any(domain in url for domain in ALLOWED_DOMAINS):
                    continue

                # ❌ block junk pages
                if any(bad in url for bad in BLOCKED_KEYWORDS):
                    continue

                urls.append(url)

        except:
            continue

    # remove duplicates
    return list(set(urls))[:5]


# -------------------------
# 🌐 FETCH + CLEAN PAGE
# -------------------------
def fetch_page(url):
    try:
        res = requests.get(url, timeout=5)

        if res.status_code != 200:
            return ""

        soup = BeautifulSoup(res.text, "html.parser")

        # ❌ remove scripts/styles/nav junk
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        paragraphs = [p.get_text() for p in soup.find_all("p")]

        text = " ".join(paragraphs)

        # 🔥 clean text
        text = text.replace("\n", " ")
        text = " ".join(text.split())

        # ❌ skip useless pages
        if len(text) < 300:
            return ""

        # ✅ CS relevance filter
        if not is_cs_related(text):
            return ""

        return text[:4000]

    except:
        return ""


# -------------------------
# 🧠 CS RELEVANCE FILTER
# -------------------------
def is_cs_related(text):
    keywords = [
        "process", "algorithm", "memory", "cpu",
        "thread", "database", "network",
        "operating system", "data structure",
        "synchronization", "deadlock"
    ]

    score = sum(1 for k in keywords if k in text.lower())

    return score >= 2