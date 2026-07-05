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
    
    # Find the EXPERIENCE section
    exp_match = re.search(r'(?:EXPERIENCE|WORK EXPERIENCE)[:\s]*\n(.*?)(?=\n\s*(?:EDUCATION|SKILLS|CERTIFICATIONS|PROJECTS|$))', text, re.IGNORECASE | re.DOTALL)
    if not exp_match:
        return experiences
    
    exp_section = exp_match.group(1)
    
    # Pattern to match: Job Title, Company, Date range on consecutive lines
    job_pattern = r'^([A-Za-z\s]+?)\n([A-Za-z0-9\s,\.&\-]+?)\n([^\n]*?[12]\d{3}[^\n]*)'
    
    matches = list(re.finditer(job_pattern, exp_section, re.IGNORECASE | re.MULTILINE))
    
    for match in matches:
        title = match.group(1).strip()
        company = match.group(2).strip()
        date_range = match.group(3).strip()
        
        # Skip invalid entries
        if len(title) < 3 or any(word in title.lower() for word in ['inc', 'llc', 'ltd', 'corp', 'experience']):
            continue
            
        # Get text after for context
        end_pos = match.end()
        context = exp_section[end_pos:end_pos+400]
        
        duration_info = parse_date_range(date_range)
        primary_focus = extract_primary_focus(context)
        
        if duration_info['duration_years'] > 0:
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
        return {"years": 0, "level": "Unknown"}
    
    start_years = [job['start_year'] for job in jobs if job['start_year']]
    end_years = [job['end_year'] for job in jobs if job['end_year']]
    
    if not start_years or not end_years:
        return {"years": 0, "level": "Unknown"}
    
    total_years = max(end_years) - min(start_years)
    level = "Unknown"
    for lvl, (low, high) in EXPERIENCE_LEVELS.items():
        if low <= total_years < high:
            level = lvl
            break
    
    return {"years": total_years, "level": level}

# ── Skills Extraction ────────────────────────────────────────────────────────

def extract_skills(text: str, top_n: int = 15) -> list:
    """Extract skills using KeyBERT with lazy loading"""
    try:
        kw_model = get_keybert_model()
        # Limit text length to improve performance
        text_limited = text[:2000] if len(text) > 2000 else text
        keywords = kw_model.extract_keywords(
            text_limited,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=top_n,
            language="english"
        )
        return [kw[0] for kw in keywords]
    except Exception as e:
        print(f"Warning: KeyBERT extraction failed: {e}")
        return []

# ── Combined Features ────────────────────────────────────────────────────────

def extract_features(text: str) -> dict:
    return {
        "total_experience": calculate_total_experience(text),
        "job_experiences": extract_job_experiences(text),
        "skills": extract_skills(text)
    }