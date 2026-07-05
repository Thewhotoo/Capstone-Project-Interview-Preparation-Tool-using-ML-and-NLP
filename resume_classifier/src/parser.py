import re
import os
from utils.helpers import clean_text

# Lazy-loaded document parsing libraries
_pdfplumber = None
_docx = None

def get_pdfplumber():
    """Lazy load pdfplumber on first use"""
    global _pdfplumber
    if _pdfplumber is None:
        import pdfplumber
        _pdfplumber = pdfplumber
    return _pdfplumber

def get_docx():
    """Lazy load python-docx on first use with compatibility handling"""
    global _docx
    if _docx is None:
        try:
            import docx
            _docx = docx
        except ImportError as e:
            if "exceptions" in str(e):
                # Known issue with python-docx, apply fix
                import sys
                import builtins
                original_import = builtins.__import__
                
                def patched_import(name, *args, **kwargs):
                    if name == 'exceptions':
                        return sys.modules.get('builtins')
                    return original_import(name, *args, **kwargs)
                
                builtins.__import__ = patched_import
                import docx
                _docx = docx
            else:
                raise
    return _docx

# ── Text Extraction ─────────────────────────────────────────────────────────

def extract_from_pdf(path: str) -> str:
    pdfplumber = get_pdfplumber()
    with pdfplumber.open(path) as pdf:
        return " ".join(page.extract_text() or "" for page in pdf.pages)

def extract_from_docx(path: str) -> str:
    docx = get_docx()
    doc = docx.Document(path)
    return " ".join(para.text for para in doc.paragraphs)

def extract_from_txt(path: str) -> str:
    """Extract text from plain text files (.txt, .ats)"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def extract_from_ats(path: str) -> str:
    """Extract and parse ATS format resumes (plain text with structure)"""
    text = extract_from_txt(path)
    # ATS format is typically plain text, so just return cleaned version
    # The structure is preserved in the raw text for better parsing
    return text

def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[-1].lower()
    if ext == ".pdf":
        text = extract_from_pdf(path)
        return clean_text(text)
    elif ext in [".docx", ".doc"]:
        text = extract_from_docx(path)
        return clean_text(text)
    elif ext in [".txt", ".ats"]:
        text = extract_from_ats(path)
        # For ATS files, preserve newline structure for better feature extraction
        # Only remove non-ASCII characters but keep newlines
        text = re.sub(r'[^\x00-\x7F\n]+', ' ', text)  
        text = re.sub(r'http\S+', '', text)  # remove URLs
        return text.strip()
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .pdf, .docx, .doc, .txt, .ats")

# ── NER Extraction ───────────────────────────────────────────────────────────

def extract_ats_sections(text: str) -> dict:
    """Extract structured sections from ATS format resumes"""
    sections = {
        "summary": "",
        "experience": "",
        "skills": "",
        "education": "",
        "certifications": "",
        "other": ""
    }
    
    # Common ATS section headers (case-insensitive)
    section_patterns = {
        "summary": r"(PROFESSIONAL\s+SUMMARY|SUMMARY|OBJECTIVE|PROFILE)",
        "experience": r"(WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT|PROFESSIONAL\s+EXPERIENCE|WORK\s+HISTORY)",
        "skills": r"(SKILLS|TECHNICAL\s+SKILLS|COMPETENCIES|CORE\s+COMPETENCIES)",
        "education": r"(EDUCATION|EDUCATIONAL\s+BACKGROUND|QUALIFICATIONS)",
        "certifications": r"(CERTIFICATIONS|LICENSES|CREDENTIALS|AWARDS)"
    }
    
    # Split text by section headers
    current_section = "other"
    lines = text.split("\n")
    
    for line in lines:
        line_upper = line.upper().strip()
        # Check if this line is a section header
        found_section = False
        for section_name, pattern in section_patterns.items():
            if re.search(pattern, line_upper):
                current_section = section_name
                found_section = True
                break
        
        if not found_section and line.strip():
            sections[current_section] += line + "\n"
    
    return sections

def extract_entities(text: str) -> dict:
    """Extract basic entities using regex patterns (simplified, no spacy)"""
    entities = {
        "names":         [],
        "organizations": [],
        "dates":         [],
        "locations":     []
    }
    
    # Simple patterns for dates and basic entity extraction
    dates = re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}', text)
    entities["dates"] = list(set(dates))[:10]
    
    return entities

def extract_email(text: str) -> str:
    match = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)
    return match.group(0) if match else None

def extract_phone(text: str) -> str:
    match = re.search(r'(\+?\d[\d\s\-().]{7,}\d)', text)
    return match.group(0) if match else None

# ── Main Parse Function ──────────────────────────────────────────────────────

def parse_resume(path: str) -> dict:
    ext = os.path.splitext(path)[-1].lower()
    text = extract_text(path)
    entities = extract_entities(text)
    
    result = {
        "raw_text":      text,
        "email":         extract_email(text),
        "phone":         extract_phone(text),
        "entities":      entities,
        "format":        "ATS" if ext in [".txt", ".ats"] else ext[1:].upper()
    }
    
    # For ATS and text formats, also extract structured sections
    if ext in [".txt", ".ats"]:
        sections = extract_ats_sections(text)
        result["sections"] = sections
    
    return result