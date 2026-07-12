import re
from utils.config import EXPERIENCE_LEVELS
from datetime import datetime

# Lazy load KeyBERT model on first use
_kw_model = None

def get_keybert_model():
    """Lazy load KeyBERT model on first use to avoid startup delays"""
    global _kw_model
    if _kw_model is None:
        from keybert import KeyBERT
        _kw_model = KeyBERT()
    return _kw_model

# ── Experience Level ─────────────────────────────────────────────────────────

def parse_date_range(date_str: str) -> dict:
    """Parse date ranges like 'January 2021 - Present' or '2019 - 2024'"""
    # Extract full 4-digit years
    years = []
    for year_match in re.finditer(r'([12]\d{3})', date_str):
        year_val = int(year_match.group(1))
        years.append(year_val)
    
    if len(years) >= 2:
        start_year = min(years)
        end_year = max(years)
        duration = end_year - start_year
        return {
            "start_year": start_year,
            "end_year": end_year,
            "duration_years": duration
        }
    elif len(years) == 1 and ("present" in date_str.lower() or "current" in date_str.lower()):
        current_year = datetime.now().year
        start_year = years[0]
        duration = current_year - start_year
        return {
            "start_year": start_year,
            "end_year": current_year,
            "duration_years": duration
        }
    
    return {"duration_years": 0, "start_year": None, "end_year": None}

def extract_primary_focus(text: str) -> str:
    """Extract primary focus/responsibilities from job description text"""
    lines = [l.strip() for l in text.split('\n') if l.strip() and l.strip().startswith(('-', '•', '*'))]
    
    if not lines:
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 10]
    
    if lines:
        primary = ' '.join(lines[:2])
        primary = re.sub(r'^[-•*]\s*', '', primary)
        return primary[:150]
    
    return "Not specified"

def extract_job_experiences(text: str) -> list:
    """Extract individual job experiences with duration and primary focus"""
    experiences = []

    # Find the EXPERIENCE section — handle both newline and inline formats
    _SECTION_HEADERS = (
        r'EDUCATION|SKILLS|CERTIFICATIONS|PROJECTS|TECHNICAL\s+SKILLS|'
        r'COMPETENCIES|SUMMARY|CONTACT|REFERENCES|OBJECTIVE|ACHIEVEMENTS|'
        r'PUBLICATIONS|AWARDS|LANGUAGES|INTERESTS|VOLUNTEER|PORTFOLIO'
    )
    exp_match = re.search(
        r'(?:^|\n)\s*(?:EXPERIENCE|WORK\s+EXPERIENCE)[:\s]*[\s]+'
        r'([\s\S]+?)(?=\n\s*(?:' + _SECTION_HEADERS + r')[:\s]*\n|\Z)',
        text, re.IGNORECASE
    )
    # Fallback: single-line resume (no newlines between sections)
    if not exp_match:
        exp_match = re.search(
            r'(?:Experience|Work\s+Experience)\s+(.+?)(?:\s+(?:Honors|Additional|Education|Projects|Certifications|Technical Skills|Skills)|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
    if not exp_match:
        return experiences

    exp_section = exp_match.group(1)

    # Strategy 1: Try multiline format (title\ncompany\ndate)
    job_pattern_ml = r'^([A-Za-z\s,]+?)\n([A-Za-z0-9\s,\.&\-]+?)\n([^\n]*?[12]\d{3}[^\n]*)'
    matches = list(re.finditer(job_pattern_ml, exp_section, re.IGNORECASE | re.MULTILINE))

    # Strategy 2: Pipe-delimited format: "Title | Company | Location | Date"
    if not matches:
        job_pattern_pipe = r'([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*([^\n]+)'
        raw_matches = list(re.finditer(job_pattern_pipe, exp_section))
        for rm in raw_matches:
            title = rm.group(1).strip()
            company = rm.group(2).strip()
            location = rm.group(3).strip()
            date_part = rm.group(4).strip()
            # Skip if date_part doesn't contain a year
            if not re.search(r'[12]\d{3}', date_part):
                continue
            # Handle "Present" / "Current"
            if re.search(r'present|current', date_part, re.IGNORECASE):
                date_range = date_part
            else:
                date_range = date_part
            end_pos = rm.end()
            context = exp_section[end_pos:end_pos + 400]
            duration_info = parse_date_range(date_range)
            primary_focus = extract_primary_focus(context)
            if duration_info.get('start_year') and duration_info.get('end_year'):
                experiences.append({
                    "title": title,
                    "company": company,
                    "date_range": date_range,
                    "duration_years": duration_info['duration_years'],
                    "start_year": duration_info['start_year'],
                    "end_year": duration_info['end_year'],
                    "primary_focus": primary_focus
                })
        if experiences:
            return experiences

    # Strategy 3: If no multiline matches, try inline format with multiple spaces as delimiter
    if not matches:
        # Format: "Title   Company Month Year Month Year   Description"
        # Double+ spaces separate fields; single space between company and date
        job_pattern_inline = r'([A-Za-z][A-Za-z\s&]{2,}?)\s{2,}(.+?)\s+((?:[A-Z][a-z]+\s+)?[12]\d{3})\s+([A-Z][a-z]+\s+[12]\d{3})'
        raw_matches = list(re.finditer(job_pattern_inline, exp_section))
        # Convert to named groups compatible with main loop (Strategy 3)
        for rm in raw_matches:
            title = rm.group(1).strip()
            company = rm.group(2).strip()
            date_range = rm.group(3).strip() + ' - ' + rm.group(4).strip()
            end_pos = rm.end()
            context = exp_section[end_pos:end_pos + 400]
            duration_info = parse_date_range(date_range)
            primary_focus = extract_primary_focus(context)
            if duration_info['start_year'] and duration_info['end_year']:
                experiences.append({
                    "title": title,
                    "company": company,
                    "date_range": date_range,
                    "duration_years": duration_info['duration_years'],
                    "start_year": duration_info['start_year'],
                    "end_year": duration_info['end_year'],
                    "primary_focus": primary_focus
                })
        return experiences

    for match in matches:
        title = match.group(1).strip()
        company = match.group(2).strip()
        date_range = match.group(3).strip()
        if match.lastindex and match.lastindex >= 4 and match.group(4):
            date_range = match.group(3).strip() + ' - ' + match.group(4).strip()

        # Skip invalid entries
        if len(title) < 3 or any(word in title.lower() for word in ['inc', 'llc', 'ltd', 'corp', 'experience']):
            continue

        # Get text after for context
        end_pos = match.end()
        context = exp_section[end_pos:end_pos + 400]

        duration_info = parse_date_range(date_range)
        primary_focus = extract_primary_focus(context)

        if duration_info['start_year'] and duration_info['end_year']:
            experiences.append({
                "title": title,
                "company": company,
                "date_range": date_range,
                "duration_years": duration_info['duration_years'],
                "start_year": duration_info['start_year'],
                "end_year": duration_info['end_year'],
                "primary_focus": primary_focus
            })

    return experiences

def calculate_total_experience(text: str) -> dict:
    """Calculate total experience from job experiences"""
    jobs = extract_job_experiences(text)
    
    if not jobs:
        # Fallback: scan EXPERIENCE section for year-span patterns
        # to avoid counting education years (e.g. graduation 2027)
        _SECTION_HEADERS = (
            r'EXPERIENCE|WORK\s+EXPERIENCE|EDUCATION|SKILLS|CERTIFICATIONS|'
            r'SUMMARY|CONTACT|REFERENCES|OBJECTIVE|PROJECTS|TECHNICAL\s+SKILLS'
        )
        exp_match = re.search(
            r'(?:^|\n)\s*(?:EXPERIENCE|WORK\s+EXPERIENCE)[:\s]*[\s]+'
            r'([\s\S]+?)(?=\n\s*(?:' + _SECTION_HEADERS + r')[:\s]*\n|\Z)',
            text, re.IGNORECASE
        )
        scan_text = exp_match.group(1) if exp_match else text
        years_found = [int(y) for y in re.findall(r'(20\d{2})', scan_text)]
        if len(years_found) >= 2:
            min_y, max_y = min(years_found), max(years_found)
            if max_y > min_y:
                total_years = max_y - min_y
                level = "Unknown"
                for lvl, (low, high) in EXPERIENCE_LEVELS.items():
                    if low <= total_years < high:
                        level = lvl
                        break
                return {"years": total_years, "months": total_years * 12, "level": level}
        return {"years": 0, "months": 0, "level": "Unknown"}
    
    start_years = [job['start_year'] for job in jobs if job['start_year']]
    end_years = [job['end_year'] for job in jobs if job['end_year']]
    
    if not start_years or not end_years:
        return {"years": 0, "months": 0, "level": "Unknown"}
    
    total_years = max(end_years) - min(start_years)
    
    # For sub-year experiences, estimate months from the date ranges
    total_months = total_years * 12
    if total_years == 0:
        # Count months from individual job durations
        for job in jobs:
            dr = job.get('date_range', '')
            month_match = re.findall(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', dr, re.IGNORECASE)
            if len(month_match) >= 2:
                MONTH_MAP = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
                             'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
                start_m = MONTH_MAP.get(month_match[0][:3].lower(), 1)
                end_m = MONTH_MAP.get(month_match[-1][:3].lower(), 12)
                total_months += max(1, end_m - start_m)

    level = "Unknown"
    effective_years = total_years if total_years > 0 else total_months / 12.0
    for lvl, (low, high) in EXPERIENCE_LEVELS.items():
        if low <= effective_years < high:
            level = lvl
            break
    
    return {"years": total_years, "months": total_months, "level": level}

# ── Skills Extraction (Hybrid Pipeline) ──────────────────────────────────────

# Priority 1: Known technology dictionary
TECH_SKILLS = {
    # Programming Languages
    "python", "java", "c++", "c", "c#", "javascript", "typescript", "go", "golang",
    "rust", "kotlin", "swift", "ruby", "php", "scala", "r", "matlab", "sql",
    "html", "css", "scss", "sass", "graphql", "solidity", "lua", "perl", "haskell",
    "objective-c", "dart", "elixir", "clojure", "fortran", "cobol", "assembly",
    "bash", "shell", "powershell",
    # Frontend Frameworks
    "react", "react.js", "reactjs", "angular", "angularjs", "vue", "vue.js", "vuejs",
    "next.js", "nextjs", "nuxt", "nuxt.js", "svelte", "sveltekit",
    "jquery", "bootstrap", "tailwind", "tailwind css", "material ui", "chakra ui",
    "redux", "zustand", "mobx", "ember.js", "backbone.js",
    # Backend Frameworks
    "node.js", "nodejs", "express", "express.js", "flask", "django", "fastapi",
    "fastapi", "spring", "spring boot", "springboot", "laravel", "rails", "ruby on rails",
    "asp.net", ".net", ".net core", "dotnet", "gin", "fiber", "actix",
    "graphql", "rest", "rest api", "restful", "grpc",
    # Databases
    "mysql", "postgresql", "postgres", "mongodb", "mongo", "redis", "cassandra",
    "dynamodb", "sqlite", "oracle", "sql server", "mssql", "mariadb", "couchdb",
    "neo4j", "elasticsearch", "firebase", "supabase", "prisma", "sequelize",
    "typeorm", "sqlalchemy", "mongoose",
    # Cloud & DevOps
    "aws", "amazon web services", "azure", "microsoft azure", "gcp", "google cloud",
    "docker", "kubernetes", "k8s", "jenkins", "github actions", "gitlab ci",
    "ci/cd", "travis ci", "circleci", "terraform", "ansible", "puppet", "chef",
    "nginx", "apache", "linux", "ubuntu", "centos", "unix",
    "render", "vercel",
    # ML/AI
    "tensorflow", "keras", "pytorch", "scikit-learn", "sklearn", "pandas", "numpy",
    "scipy", "matplotlib", "seaborn", "plotly", "opencv", "nltk", "spacy",
    "hugging face", "huggingface", "transformers", "langchain", "langgraph",
    "openai", "gemini", "gemini api", "llamaindex", "llama index", "rag", "xgboost", "lightgbm",
    "machine learning", "deep learning", "neural network", "nlp",
    "natural language processing", "computer vision", "dsa", "data structures",
    # Data Tools
    "jupyter", "jupyter notebook", "google colab", "apache spark", "spark",
    "hadoop", "kafka", "airflow", "dbt", "tableau", "power bi",
    "excel", "google sheets",
    # Version Control & IDEs
    "git", "github", "gitlab", "bitbucket", "svn", "subversion",
    "vs code", "visual studio code", "intellij", "pycharm", "eclipse",
    "vim", "neovim",
    # Testing
    "jest", "mocha", "chai", "pytest", "unittest", "junit", "selenium",
    "cypress", "playwright", "postman",
    # Game Development
    "unity", "unreal engine", "unreal", "godot", "blender", "maya",
    "3ds max", "cinema 4d",
    # Mobile
    "android", "ios", "react native", "flutter", "xamarin", "ionic",
    "swift ui", "swiftui", "jetpack compose",
    # Other
    "microservices", "serverless", "agile", "scrum", "kanban",
    "jira", "confluence", "notion", "figma", "sketch",
    "blockchain", "web3", "solidity", "ethereum",
    # Core CS Topics
    "oop", "object-oriented programming",
    "dbms", "database management systems",
    "operating systems", "computer networks", "software engineering",
    "dsa", "data structures", "algorithms",
}

# Canonical display names (maps lowercase canonical → display form)
_SKILL_DISPLAY = {
    "python": "Python", "java": "Java", "c++": "C++", "c": "C", "c#": "C#",
    "javascript": "JavaScript", "typescript": "TypeScript", "go": "Go",
    "golang": "Go", "rust": "Rust", "kotlin": "Kotlin", "swift": "Swift",
    "ruby": "Ruby", "php": "PHP", "scala": "Scala", "r": "R", "matlab": "MATLAB",
    "sql": "SQL", "html": "HTML", "css": "CSS", "scss": "SCSS", "sass": "Sass",
    "graphql": "GraphQL", "solidity": "Solidity", "lua": "Lua", "perl": "Perl",
    "haskell": "Haskell", "objective-c": "Objective-C", "dart": "Dart",
    "bash": "Bash", "shell": "Shell", "powershell": "PowerShell",
    "react": "React", "react.js": "React", "reactjs": "React",
    "angular": "Angular", "angularjs": "Angular", "vue": "Vue.js",
    "vue.js": "Vue.js", "vuejs": "Vue.js",
    "next.js": "Next.js", "nextjs": "Next.js", "nuxt": "Nuxt.js",
    "nuxt.js": "Nuxt.js", "svelte": "Svelte", "sveltekit": "SvelteKit",
    "jquery": "jQuery", "bootstrap": "Bootstrap", "tailwind": "Tailwind CSS",
    "tailwind css": "Tailwind CSS", "material ui": "Material UI",
    "chakra ui": "Chakra UI", "redux": "Redux", "zustand": "Zustand",
    "node.js": "Node.js", "nodejs": "Node.js",
    "express": "Express.js", "express.js": "Express.js",
    "flask": "Flask", "django": "Django", "fastapi": "FastAPI",
    "spring": "Spring", "spring boot": "Spring Boot", "springboot": "Spring Boot",
    "laravel": "Laravel", "rails": "Ruby on Rails", "ruby on rails": "Ruby on Rails",
    "asp.net": "ASP.NET", ".net": ".NET", ".net core": ".NET Core",
    "dotnet": ".NET", "gin": "Gin", "fiber": "Fiber", "actix": "Actix",
    "rest": "REST API", "rest api": "REST API", "restful": "RESTful",
    "grpc": "gRPC",
    "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mongodb": "MongoDB", "mongo": "MongoDB", "redis": "Redis",
    "cassandra": "Cassandra", "dynamodb": "DynamoDB", "sqlite": "SQLite",
    "oracle": "Oracle", "sql server": "SQL Server", "mssql": "SQL Server",
    "mariadb": "MariaDB", "couchdb": "CouchDB", "neo4j": "Neo4j",
    "elasticsearch": "Elasticsearch", "firebase": "Firebase",
    "supabase": "Supabase", "prisma": "Prisma", "sequelize": "Sequelize",
    "typeorm": "TypeORM", "sqlalchemy": "SQLAlchemy", "mongoose": "Mongoose",
    "aws": "AWS", "amazon web services": "AWS",
    "azure": "Azure", "microsoft azure": "Azure",
    "gcp": "GCP", "google cloud": "GCP",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "jenkins": "Jenkins", "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI", "ci/cd": "CI/CD",
    "travis ci": "Travis CI", "circleci": "CircleCI",
    "terraform": "Terraform", "ansible": "Ansible", "puppet": "Puppet",
    "chef": "Chef", "nginx": "Nginx", "apache": "Apache",
    "linux": "Linux", "ubuntu": "Ubuntu", "centos": "CentOS", "unix": "Unix",
    "render": "Render", "vercel": "Vercel",
    "tensorflow": "TensorFlow", "keras": "Keras", "pytorch": "PyTorch",
    "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "pandas": "Pandas", "numpy": "NumPy", "scipy": "SciPy",
    "matplotlib": "Matplotlib", "seaborn": "Seaborn", "plotly": "Plotly",
    "opencv": "OpenCV", "nltk": "NLTK", "spacy": "spaCy",
    "hugging face": "Hugging Face", "huggingface": "Hugging Face",
    "transformers": "Transformers", "langchain": "LangChain",
    "langgraph": "LangGraph", "openai": "OpenAI",
    "gemini": "Gemini", "gemini api": "Gemini API",
    "llamaindex": "LlamaIndex", "llama index": "LlamaIndex",
    "rag": "RAG", "xgboost": "XGBoost", "lightgbm": "LightGBM",
    "machine learning": "Machine Learning", "deep learning": "Deep Learning",
    "neural network": "Neural Networks", "nlp": "NLP",
    "natural language processing": "NLP", "computer vision": "Computer Vision",
    "dsa": "DSA", "data structures": "DSA",
    "jupyter": "Jupyter", "jupyter notebook": "Jupyter Notebook",
    "google colab": "Google Colab", "apache spark": "Apache Spark",
    "spark": "Spark", "hadoop": "Hadoop", "kafka": "Kafka",
    "airflow": "Airflow", "dbt": "dbt", "tableau": "Tableau",
    "power bi": "Power BI", "excel": "Excel",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab",
    "bitbucket": "Bitbucket", "svn": "SVN",
    "vs code": "VS Code", "visual studio code": "VS Code",
    "intellij": "IntelliJ", "pycharm": "PyCharm", "eclipse": "Eclipse",
    "jest": "Jest", "mocha": "Mocha", "chai": "Chai", "pytest": "Pytest",
    "junit": "JUnit", "selenium": "Selenium", "cypress": "Cypress",
    "playwright": "Playwright", "postman": "Postman",
    "unity": "Unity", "unreal engine": "Unreal Engine", "unreal": "Unreal Engine",
    "godot": "Godot", "blender": "Blender", "maya": "Maya",
    "3ds max": "3ds Max", "cinema 4d": "Cinema 4D",
    "android": "Android", "ios": "iOS",
    "react native": "React Native", "flutter": "Flutter",
    "xamarin": "Xamarin", "ionic": "Ionic",
    "swift ui": "SwiftUI", "swiftui": "SwiftUI", "jetpack compose": "Jetpack Compose",
    "microservices": "Microservices", "serverless": "Serverless",
    "agile": "Agile", "scrum": "Scrum", "kanban": "Kanban",
    "jira": "Jira", "confluence": "Confluence", "notion": "Notion",
    "figma": "Figma", "sketch": "Sketch",
    "blockchain": "Blockchain", "web3": "Web3", "ethereum": "Ethereum",
    "oop": "OOP", "object-oriented programming": "OOP",
    "dbms": "DBMS", "database management systems": "DBMS",
    "operating systems": "Operating Systems",
    "computer networks": "Computer Networks",
    "software engineering": "Software Engineering",
    "dsa": "DSA", "data structures": "DSA", "algorithms": "Algorithms",
}


def _extract_from_skills_section(text: str) -> list:
    """Extract skills from a dedicated SKILLS / TECHNICAL SKILLS section."""
    # Match from SKILLS header to next resume section or end of text
    _SECTION_HEADERS = (
        r'EXPERIENCE|WORK\s+EXPERIENCE|EDUCATION|PROJECTS|CERTIFICATIONS|'
        r'SUMMARY|CONTACT|REFERENCES|OBJECTIVE|ACHIEVEMENTS|PUBLICATIONS|'
        r'AWARDS|LANGUAGES|INTERESTS|VOLUNTEER|PORTFOLIO|SIDE\s+PROJECTS|'
        r'PERSONAL\s+PROJECTS|OPEN\s+SOURCE|WORK\s+HISTORY'
    )
    # Try multiline format first (section header must start on its own line)
    # Matches: SKILLS, TECHNICAL SKILLS, KEY SKILLS, CORE COMPETENCIES,
    # COMPETENCIES, TECHNOLOGIES, TECH STACK, ABOUT SKILLS & COMPETENCIES
    pattern = (
        r'(?:^|\n)\s*'
        r'(?:'
        r'(?:ABOUT\s+)?(?:KEY\s+)?(?:TECHNICAL\s+|CORE\s+)?(?:PRIMARY\s+)?'
        r'(?:SKILLS?|COMPETENCIES|TECHNOLOGIES|TECH\s+STACK)'
        r'(?:\s*(?:AND|&)\s*(?:COMPETENCIES|SKILLS?))?'
        r')\s*[:\s]+'
        r'([\s\S]+?)(?=\n\s*(?:' + _SECTION_HEADERS + r')[:\s]*\n|\Z)'
    )
    m = re.search(pattern, text, re.IGNORECASE)

    # Fallback: single-line format (entire resume on one line)
    if not m:
        pattern_inline = (
            r'(?:'
            r'(?:ABOUT\s+)?(?:KEY\s+)?(?:TECHNICAL\s+|CORE\s+)?(?:PRIMARY\s+)?'
            r'(?:SKILLS?|COMPETENCIES|TECHNOLOGIES|TECH\s+STACK)'
            r'(?:\s*(?:AND|&)\s*(?:COMPETENCIES|SKILLS?))?'
            r')[:\s]+'
            r'(.+?)(?:\s+(?:Honors|Additional|Education|Projects|Experience|Certifications|References)|\Z)'
        )
        m = re.search(pattern_inline, text, re.IGNORECASE)
    if not m:
        return []
    section = m.group(1)
    # First, normalize: replace category headers (e.g. "Frontend:", "Backend:", "AI/ML:") with newlines
    section = re.sub(r'\b(Languages?|Frontend|Backend|AI/ML|ML/AI|Databases?|Cloud/DevOps|DevOps|Tools?|Core CS|Honors|Additional)[^,;\n]*?:', r'\n', section)
    # Split on commas, pipes, semicolons, newlines
    raw = re.split(r'[,;|\n]', section)
    found = []
    for item in raw:
        item = item.strip().strip('-•*·→:').strip()
        # Remove category prefixes like "Languages:", "Frontend:", "Backend:"
        item = re.sub(r'^[A-Za-z/]+:\s*', '', item).strip()
        if not item or len(item) > 40:
            continue
        lower = item.lower()
        # Direct match
        if lower in TECH_SKILLS:
            found.append(_SKILL_DISPLAY.get(lower, item))
            continue
        # Substring match (e.g. "React.js, Node.js" within a single token)
        for tech in TECH_SKILLS:
            if tech in lower and len(tech) >= 3:
                # Verify it's a word-boundary match, not a substring inside another word
                if re.search(r'(?<![a-zA-Z])' + re.escape(tech) + r'(?![a-zA-Z])', lower):
                    display = _SKILL_DISPLAY.get(tech, tech.title())
                    if display not in found:
                        found.append(display)
    return found


def _extract_by_regex(text: str) -> list:
    """Match known technology names anywhere in the resume text."""
    found = []
    text_lower = text.lower()
    # Sort by length descending so "react.js" matches before "react" when both present
    for tech in sorted(TECH_SKILLS, key=len, reverse=True):
        # Use word-boundary-like match for ALL techs to avoid false positives
        # Match tech surrounded by non-alpha chars (spaces, punctuation, line boundaries)
        pattern = r'(?<![a-zA-Z])' + re.escape(tech) + r'(?![a-zA-Z])'
        if re.search(pattern, text_lower):
            display = _SKILL_DISPLAY.get(tech, tech.title())
            if display not in found:
                found.append(display)
    return found


def _extract_by_keybert(text: str, existing: list, top_n: int = 20) -> list:
    """KeyBERT fallback — only used if other methods return too few skills."""
    try:
        kw_model = get_keybert_model()
        text_limited = text[:3000] if len(text) > 3000 else text
        keywords = kw_model.extract_keywords(
            text_limited,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=top_n,
        )
        existing_lower = {s.lower() for s in existing}
        result = list(existing)
        for kw, score in keywords:
            kw_clean = kw.strip()
            if kw_clean.lower() not in existing_lower and len(kw_clean) >= 2:
                result.append(kw_clean)
                existing_lower.add(kw_clean.lower())
        return result
    except Exception as e:
        print(f"Warning: KeyBERT fallback failed: {e}")
        return existing


def extract_skills(text: str, top_n: int = 50) -> list:
    """Hybrid skill extraction pipeline.

    Priority order:
      1. Resume section parsing (SKILLS / TECHNICAL SKILLS sections) — highest precision
      2. Known technology dictionary (regex over full text) — high recall
    No KeyBERT fallback — it produces more noise than signal.
    """
    # Phase 1: Section-based extraction (high precision for explicitly listed skills)
    section_skills = _extract_from_skills_section(text)

    # Phase 2: Regex dictionary scan (fast, high recall)
    regex_skills = _extract_by_regex(text)

    # Merge: section skills first (they're explicitly listed), then regex finds
    seen_lower = set()
    merged = []
    for s in section_skills + regex_skills:
        key = s.lower()
        if key not in seen_lower:
            seen_lower.add(key)
            merged.append(s)

    return merged[:top_n]

# ── Education Extraction ────────────────────────────────────────────────────

def extract_education(text: str) -> list:
    """Extract education entries from resume text.
    Returns list of dicts with keys: institution, degree, major, graduation_year, gpa, details.
    """
    edu_entries = []

    # Find EDUCATION section — multiline then inline fallback
    _SECTION_HEADERS = (
        r'EXPERIENCE|WORK\s+EXPERIENCE|PROJECTS|CERTIFICATIONS|'
        r'SUMMARY|CONTACT|REFERENCES|OBJECTIVE|ACHIEVEMENTS|PUBLICATIONS|'
        r'AWARDS|LANGUAGES|INTERESTS|VOLUNTEER|PORTFOLIO|TECHNICAL\s+SKILLS|'
        r'SKILLS|COMPETENCIES|TECHNOLOGIES|WORK\s+HISTORY'
    )
    m = re.search(
        r'(?:^|\n)\s*(?:EDUCATION|EDUCATIONAL\s+BACKGROUND)[:\s]*[\s]+'
        r'([\s\S]+?)(?=\n\s*(?:' + _SECTION_HEADERS + r')[:\s]*\n|\Z)',
        text, re.IGNORECASE
    )
    if not m:
        # Inline fallback for single-line PDFs
        m = re.search(
            r'Education\s+(.+?)(?:\s+(?:Experience|Projects|Technical Skills|Certifications|Honors|Additional|Contact|Skills)|\Z)',
            text, re.IGNORECASE
        )
    if not m:
        return edu_entries

    section = m.group(1)

    # Split on known resume section boundaries within the captured text
    # (Sometimes the experience section leaks into education capture)
    section = re.split(
        r'\b(?:Experience|Projects|Technical Skills|Certifications|Honors|Additional|Skills|Work\s+History)\b',
        section, maxsplit=1, flags=re.IGNORECASE
    )[0]

    # Also strip any leading noise (non-education text that leaked before the actual degree)
    # Look for degree keywords to find where education actually starts
    degree_start = re.search(
        r'(?:B\.?Tech|M\.?Tech|B\.?S\.?|M\.?S\.?|B\.?E\.?|M\.?E\.?|Bachelor|Master|Ph\.?D)',
        section, re.IGNORECASE
    )
    if degree_start and degree_start.start() > 10:
        section = section[degree_start.start():]

    # Extract institution names (University, College, Institute, School)
    institutions = re.findall(
        r'([\w\s]+(?:University|College|Institute|School|Centre for Excellence)[\w\s,]*?)(?=\s*(?:Expected|Class|B\.|M\.|GPA|CGPA|\d{4}|$))',
        section, re.IGNORECASE
    )

    # Extract degree types
    degree_match = re.search(
        r'((?:B\.?Tech|M\.?Tech|B\.?S\.?|M\.?S\.?|B\.?E\.?|M\.?E\.?|Bachelor|Master|Ph\.?D\.?)(?:\s+(?:in|of)\s+)?[\w\s]*?)(?=\s*(?:CGPA|GPA|Expected|\d{4}|Class|National|$))',
        section, re.IGNORECASE
    )

    # Extract major
    major_match = re.search(
        r'(?:in\s+)(Computer Science[\w\s]*?(?:and\s+Engineering)?|Information Technology[\w\s]*|Electronics[\w\s]*|Mechanical[\w\s]*|Electrical[\w\s]*|Civil[\w\s]*|Data Science[\w\s]*|Artificial Intelligence[\w\s]*|Software[\w\s]*|Mathematics[\w\s]*|Physics[\w\s]*|Chemistry[\w\s]*)',
        section, re.IGNORECASE
    )

    # Extract graduation year
    year_match = re.search(r'(?:Expected\s+)?(\d{4})', section)
    grad_year = int(year_match.group(1)) if year_match else None

    # Extract CGPA/GPA
    gpa_match = re.search(r'(?:CGPA|GPA)\s*:?\s*([\d.]+(?:\s*/\s*[\d.]+)?)', section, re.IGNORECASE)
    gpa = gpa_match.group(1).strip() if gpa_match else None

    # Extract high school info (Class XII, Class X)
    hs_info = re.findall(r'Class\s+(X|XII|10|12)\s*:?\s*([\d]+%?)', section, re.IGNORECASE)

    # Build education entry
    degree_str = degree_match.group(0).strip() if degree_match else None
    major_str = major_match.group(1).strip() if major_match else None
    institution_str = institutions[0].strip() if institutions else None

    # Clean up institution name (remove trailing noise)
    if institution_str:
        institution_str = re.sub(r'\s+', ' ', institution_str).strip()
        # Remove any leading/trailing commas
        institution_str = institution_str.strip(', ')
        # Remove trailing garbage (e.g. "University of X\nBachelor...")
        institution_str = re.split(r'\n', institution_str)[0].strip()
        # Remove leading year numbers (e.g. "2020 Northgate University")
        institution_str = re.sub(r'^\d{4}\s+', '', institution_str)
        # Remove trailing words that aren't part of the name
        institution_str = re.sub(r'\s+(?:KEY|ABOUT|CORE|PRIMARY|ADDITIONAL).*$', '', institution_str, flags=re.IGNORECASE)

    entry = {
        "institution": institution_str,
        "degree": degree_str,
        "major": major_str,
        "graduation_year": grad_year,
        "gpa": gpa,
        "high_school": [{"class": c, "score": s} for c, s in hs_info] if hs_info else [],
        "raw": re.sub(r'\s+', ' ', section.strip())[:300],
    }
    edu_entries.append(entry)

    return edu_entries


# ── Project Extraction ────────────────────────────────────────────────────

def count_projects(text: str) -> int:
    """Count distinct projects from the PROJECTS section."""
    _SECTION_HEADERS = (
        r'EXPERIENCE|WORK\s+EXPERIENCE|EDUCATION|CERTIFICATIONS|'
        r'SUMMARY|CONTACT|REFERENCES|OBJECTIVE|ACHIEVEMENTS|PUBLICATIONS|'
        r'AWARDS|LANGUAGES|INTERESTS|VOLUNTEER|PORTFOLIO|TECHNICAL\s+SKILLS|'
        r'SKILLS|COMPETENCIES|TECHNOLOGIES|TECH\s+STACK'
    )
    m = re.search(
        r'(?:^|\n)\s*(?:PROJECTS?|PERSONAL\s+PROJECTS?|SIDE\s+PROJECTS?|PORTFOLIO|OPEN\s+SOURCE)[:\s]*[\s]+'
        r'([\s\S]+?)(?=\n\s*(?:' + _SECTION_HEADERS + r')[:\s]*\n|\Z)',
        text, re.IGNORECASE
    )
    if not m:
        m = re.search(
            r'(?:Projects?|Personal\s+Projects?|Side\s+Projects?|Portfolio)\s+(.+?)(?:\s+(?:Technical Skills|Honors|Additional|Certifications|Contact|Skills|Education|Experience)|\Z)',
            text, re.IGNORECASE
        )
    if not m:
        return 0

    section = m.group(1)

    # Multiline: count non-bullet, non-description title lines
    projects = 0
    lines = section.split('\n')
    if len(lines) > 1:
        for line in lines:
            line = line.strip()
            # Project titles: not starting with bullet markers, reasonable length
            if (10 < len(line) < 80 and line[0].isupper()
                    and not line.startswith(('-', '•', '*'))
                    and not line.startswith(('Built', 'Developed', 'Detects', 'Designed', 'Created', 'Implemented'))):
                projects += 1
    else:
        # Inline format: split on sentence starters to find project names
        # Project titles are typically Title Case multi-word phrases before a verb
        parts = re.split(r'\s{2,}', section)
        for part in parts:
            part = part.strip()
            # Heuristic: starts uppercase, contains multiple words, ends with a title marker
            if (5 < len(part) < 80
                    and part[0].isupper()
                    and not part.startswith(('Built', 'Developed', 'Detects', 'Designed', 'Using', 'Uses', 'Awarded', 'Award'))):
                projects += 1

    return projects


# ── Combined Features ────────────────────────────────────────────────────────

def extract_features(text: str) -> dict:
    return {
        "total_experience": calculate_total_experience(text),
        "job_experiences": extract_job_experiences(text),
        "skills": extract_skills(text),
        "education": extract_education(text),
        "projects_count": count_projects(text),
    }