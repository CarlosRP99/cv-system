#!/usr/bin/env python3
"""
Ingest a CV from PDF into the knowledge base.

Extracts profile, experience, skills, education, and certifications
from a PDF CV and generates YAML entries in kb/.

Usage:
    python ingest_cv.py <cv_file.pdf>
    python ingest_cv.py mi_cv.pdf
    python ingest_cv.py mi_cv.pdf --dry-run
"""

import sys
import os
import re
import yaml
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract full text from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        print("Error: pdfplumber no está instalado. Ejecuta: pip install pdfplumber")
        sys.exit(1)

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

# Section header patterns (English and Spanish)
SECTION_PATTERNS = {
    "profile": [
        r"^(?:contact|contacto|personal|perfil|about|sobre\s+mi|summary|resumen)\s*$",
    ],
    "experience": [
        r"^(?:work\s+experience|experience|experiencia\s+profesional|experiencia\s+laboral|empleo|employment|antecedentes\s+laborales)\s*$",
    ],
    "education": [
        r"^(?:education|formaci[oó]n\s+acad[eé]mica|formaci[oó]n|estudios|academic)\s*$",
    ],
    "skills": [
        r"^(?:skills|habilidades|technical\s+skills|competencias|conocimientos|tech\s+stack|herramientas)\s*$",
    ],
    "certifications": [
        r"^(?:certifications?|certificaciones?|licenses?|licencias?)\s*$",
    ],
    "languages": [
        r"^(?:languages?|idiomas?)\s*$",
    ],
}


def detect_sections(text: str) -> dict:
    """Detect CV sections from extracted text by matching section headers."""
    lines = text.split("\n")
    sections = {}
    current_section = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section:
                current_lines.append("")
            continue

        matched = False
        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    # Save previous section
                    if current_section:
                        sections[current_section] = "\n".join(current_lines).strip()
                    current_section = section_name
                    current_lines = []
                    matched = True
                    break
            if matched:
                break

        if not matched:
            current_lines.append(stripped)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


# ---------------------------------------------------------------------------
# Profile extraction
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,20}")
URL_RE = re.compile(r"https?://[^\s]+")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[^\s]+")
GITHUB_RE = re.compile(r"github\.com/[^\s]+")


def extract_profile(text: str, sections: dict) -> dict:
    """Extract personal profile from CV text."""
    profile = {
        "name": "",
        "title": {"es": "", "en": ""},
        "location": "",
        "email": "",
        "phone": "",
        "links": {"github": "", "linkedin": "", "website": ""},
        "summary": {"es": "", "en": ""},
        "languages": [],
    }

    # Use first 15 lines for contact info (name, email, phone, etc.)
    lines = text.split("\n")
    header_block = "\n".join(lines[:20])

    # Extract email
    email_match = EMAIL_RE.search(header_block)
    if email_match:
        profile["email"] = email_match.group(0)

    # Extract phone
    phone_match = PHONE_RE.search(header_block)
    if phone_match:
        profile["phone"] = phone_match.group(0).strip()

    # Extract links
    github_match = GITHUB_RE.search(header_block)
    if github_match:
        profile["links"]["github"] = "https://" + github_match.group(0)

    linkedin_match = LINKEDIN_RE.search(header_block)
    if linkedin_match:
        profile["links"]["linkedin"] = "https://" + linkedin_match.group(0)

    urls = URL_RE.findall(header_block)
    for url in urls:
        if "github.com" not in url and "linkedin.com" not in url:
            profile["links"]["website"] = url
            break

    # Name: first non-empty line that isn't a section header and isn't email/phone
    for line in lines[:10]:
        stripped = line.strip()
        if not stripped:
            continue
        if EMAIL_RE.search(stripped) or PHONE_RE.search(stripped):
            continue
        if URL_RE.search(stripped):
            continue
        # Skip lines that are clearly section headers
        is_header = False
        for patterns in SECTION_PATTERNS.values():
            for p in patterns:
                if re.match(p, stripped, re.IGNORECASE):
                    is_header = True
                    break
            if is_header:
                break
        if is_header:
            continue
        # If it looks like a name (short, no special chars beyond accents)
        if len(stripped) < 60 and not re.search(r"[@#\$%\^&\*]", stripped):
            profile["name"] = stripped
            break

    # Location: look for city/country patterns near the top
    location_patterns = [
        r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s*,\s*[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})",
    ]
    for line in lines[:15]:
        for pattern in location_patterns:
            match = re.search(pattern, line)
            if match and profile["email"] not in match.group(0):
                loc = match.group(0).strip()
                if len(loc) < 60:
                    profile["location"] = loc
                    break
        if profile["location"]:
            break

    # Summary: from profile/summary section or first paragraph-like block
    summary_text = ""
    if "profile" in sections:
        summary_text = sections["profile"]
    elif "summary" in sections:
        summary_text = sections["summary"]

    # Clean up summary - remove lines that look like contact info
    if summary_text:
        clean_lines = []
        for line in summary_text.split("\n"):
            if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
                continue
            # If line looks like a name we already captured, skip
            if line.strip() == profile["name"]:
                continue
            clean_lines.append(line)
        summary_text = " ".join(clean_lines).strip()

    if summary_text:
        profile["summary"]["es"] = summary_text
        profile["summary"]["en"] = summary_text

    # Languages section
    if "languages" in sections:
        for line in sections["languages"].split("\n"):
            line = line.strip()
            if not line or line.startswith("-") and len(line) < 3:
                continue
            # Try to parse "Language - Level" or "Language: Level"
            parts = re.split(r"[-:–]", line, maxsplit=1)
            if len(parts) == 2:
                lang = parts[0].strip()
                level = parts[1].strip()
                profile["languages"].append({"language": lang, "level": level})
            elif line:
                profile["languages"].append({"language": line, "level": ""})

    return profile


# ---------------------------------------------------------------------------
# Experience extraction
# ---------------------------------------------------------------------------

DATE_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    r"Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic|"
    r"\d{4})[\s\-–/]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    r"Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic|"
    r"\d{4}|[Pp]resent|[Aa]ctual|[Pp]resente)?)",
    re.IGNORECASE,
)

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "ene": "01", "abr": "04", "ago": "08", "dic": "12",
}


def normalize_date(date_str: str) -> str:
    """Normalize a date string to YYYY-MM format."""
    date_str = date_str.strip().lower()

    # Check for present/current
    if any(w in date_str for w in ["present", "actual", "current", "presente"]):
        return ""

    # Try YYYY-MM
    match = re.match(r"(\d{4})[-/](\d{1,2})", date_str)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"

    # Try "Month YYYY"
    for month_name, month_num in MONTH_MAP.items():
        if month_name in date_str:
            year_match = re.search(r"(\d{4})", date_str)
            if year_match:
                return f"{year_match.group(1)}-{month_num}"

    # Try just YYYY
    year_match = re.match(r"(\d{4})$", date_str)
    if year_match:
        return f"{year_match.group(1)}-01"

    return date_str


def extract_experiences(text: str, sections: dict) -> list:
    """Extract work experience entries from CV text."""
    experiences = []

    exp_text = sections.get("experience", "")
    if not exp_text:
        # Fallback: look for experience-like content after the first section
        return experiences

    lines = exp_text.split("\n")
    current_exp = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this line contains a date range (indicates a job entry)
        date_match = DATE_RANGE_RE.search(stripped)

        if date_match:
            # If we have a previous experience, save it
            if current_exp and current_exp.get("company"):
                experiences.append(current_exp)

            # Start new experience
            date_str = date_match.group(0)
            dates = re.split(r"[-–/]", date_str, maxsplit=1)
            start_date = normalize_date(dates[0]) if dates else ""
            end_date = normalize_date(dates[1]) if len(dates) > 1 else ""

            # The role/company is typically before the date
            before_date = stripped[:date_match.start()].strip()
            before_date = re.sub(r"[\|·•]", "", before_date).strip()

            # Try to split "Role — Company" or "Role at Company" or "Role | Company"
            role = ""
            company = ""
            if "—" in before_date:
                parts = before_date.split("—", 1)
                role = parts[0].strip()
                company = parts[1].strip()
            elif "|" in before_date:
                parts = before_date.split("|", 1)
                role = parts[0].strip()
                company = parts[1].strip()
            elif re.search(r"\bat\b|\ben\b|\@", before_date, re.IGNORECASE):
                parts = re.split(r"\bat\b|\ben\b|\@", before_date, maxsplit=1, flags=re.IGNORECASE)
                role = parts[0].strip()
                company = parts[1].strip() if len(parts) > 1 else ""
            else:
                # Assume the whole thing is the role, company might be next line
                role = before_date

            current_exp = {
                "role": role,
                "company": company,
                "startDate": start_date,
                "endDate": end_date,
                "highlights": [],
            }

        elif current_exp:
            # Check if this is a sub-line (location, bullet point, etc.)
            if stripped.startswith("-") or stripped.startswith("•") or stripped.startswith("*"):
                highlight = re.sub(r"^[-•*]\s*", "", stripped)
                current_exp["highlights"].append(highlight)
            elif not current_exp["company"] and len(stripped) < 50:
                # Might be the company name if we haven't found it yet
                current_exp["company"] = stripped
            else:
                # Could be a highlight without bullet
                if len(stripped) > 10:
                    current_exp["highlights"].append(stripped)

    # Don't forget the last experience
    if current_exp and current_exp.get("company"):
        experiences.append(current_exp)

    return experiences


# ---------------------------------------------------------------------------
# Skills extraction
# ---------------------------------------------------------------------------

# Known tech skills for matching
KNOWN_SKILLS = {
    # Programming
    "python": {"id": "python", "name": {"es": "Python", "en": "Python"}, "category": "programming"},
    "java": {"id": "java", "name": {"es": "Java", "en": "Java"}, "category": "programming"},
    "javascript": {"id": "javascript", "name": {"es": "JavaScript", "en": "JavaScript"}, "category": "programming"},
    "typescript": {"id": "typescript", "name": {"es": "TypeScript", "en": "TypeScript"}, "category": "programming"},
    "sql": {"id": "sql", "name": {"es": "SQL", "en": "SQL"}, "category": "programming"},
    "r": {"id": "r", "name": {"es": "R", "en": "R"}, "category": "programming"},
    "go": {"id": "go", "name": {"es": "Go", "en": "Go"}, "category": "programming"},
    "rust": {"id": "rust", "name": {"es": "Rust", "en": "Rust"}, "category": "programming"},
    "scala": {"id": "scala", "name": {"es": "Scala", "en": "Scala"}, "category": "programming"},
    "bash": {"id": "bash", "name": {"es": "Bash", "en": "Bash"}, "category": "programming"},
    "powershell": {"id": "powershell", "name": {"es": "PowerShell", "en": "PowerShell"}, "category": "programming"},
    "pyspark": {"id": "pyspark", "name": {"es": "PySpark", "en": "PySpark"}, "category": "programming"},
    # Frameworks
    "fastapi": {"id": "fastapi", "name": {"es": "FastAPI", "en": "FastAPI"}, "category": "framework"},
    "django": {"id": "django", "name": {"es": "Django", "en": "Django"}, "category": "framework"},
    "flask": {"id": "flask", "name": {"es": "Flask", "en": "Flask"}, "category": "framework"},
    "react": {"id": "react", "name": {"es": "React", "en": "React"}, "category": "framework"},
    "angular": {"id": "angular", "name": {"es": "Angular", "en": "Angular"}, "category": "framework"},
    "vue": {"id": "vue", "name": {"es": "Vue.js", "en": "Vue.js"}, "category": "framework"},
    "spring": {"id": "spring", "name": {"es": "Spring Boot", "en": "Spring Boot"}, "category": "framework"},
    # Libraries
    "pandas": {"id": "pandas", "name": {"es": "Pandas", "en": "Pandas"}, "category": "library"},
    "numpy": {"id": "numpy", "name": {"es": "NumPy", "en": "NumPy"}, "category": "library"},
    "scikit-learn": {"id": "scikit-learn", "name": {"es": "Scikit-learn", "en": "Scikit-learn"}, "category": "library"},
    "scrapy": {"id": "scrapy", "name": {"es": "Scrapy", "en": "Scrapy"}, "category": "library"},
    "tensorflow": {"id": "tensorflow", "name": {"es": "TensorFlow", "en": "TensorFlow"}, "category": "library"},
    "pytorch": {"id": "pytorch", "name": {"es": "PyTorch", "en": "PyTorch"}, "category": "library"},
    # Databases
    "postgresql": {"id": "postgresql", "name": {"es": "PostgreSQL", "en": "PostgreSQL"}, "category": "database"},
    "postgres": {"id": "postgresql", "name": {"es": "PostgreSQL", "en": "PostgreSQL"}, "category": "database"},
    "mysql": {"id": "mysql", "name": {"es": "MySQL", "en": "MySQL"}, "category": "database"},
    "mongodb": {"id": "mongodb", "name": {"es": "MongoDB", "en": "MongoDB"}, "category": "database"},
    "redis": {"id": "redis", "name": {"es": "Redis", "en": "Redis"}, "category": "database"},
    "oracle": {"id": "oracle-db", "name": {"es": "Oracle Database", "en": "Oracle Database"}, "category": "database"},
    "sql server": {"id": "mssql", "name": {"es": "Microsoft SQL Server", "en": "Microsoft SQL Server"}, "category": "database"},
    "mssql": {"id": "mssql", "name": {"es": "Microsoft SQL Server", "en": "Microsoft SQL Server"}, "category": "database"},
    "elasticsearch": {"id": "elasticsearch", "name": {"es": "Elasticsearch", "en": "Elasticsearch"}, "category": "database"},
    "cassandra": {"id": "cassandra", "name": {"es": "Cassandra", "en": "Cassandra"}, "category": "database"},
    "dynamodb": {"id": "dynamodb", "name": {"es": "DynamoDB", "en": "DynamoDB"}, "category": "database"},
    # Cloud
    "aws": {"id": "aws", "name": {"es": "Amazon Web Services (AWS)", "en": "Amazon Web Services (AWS)"}, "category": "cloud"},
    "gcp": {"id": "gcp", "name": {"es": "Google Cloud Platform", "en": "Google Cloud Platform"}, "category": "cloud"},
    "azure": {"id": "azure", "name": {"es": "Microsoft Azure", "en": "Microsoft Azure"}, "category": "cloud"},
    # Tools
    "docker": {"id": "docker", "name": {"es": "Docker", "en": "Docker"}, "category": "tool"},
    "kubernetes": {"id": "kubernetes", "name": {"es": "Kubernetes", "en": "Kubernetes"}, "category": "tool"},
    "k8s": {"id": "kubernetes", "name": {"es": "Kubernetes", "en": "Kubernetes"}, "category": "tool"},
    "terraform": {"id": "terraform", "name": {"es": "Terraform", "en": "Terraform"}, "category": "tool"},
    "jenkins": {"id": "jenkins", "name": {"es": "Jenkins", "en": "Jenkins"}, "category": "tool"},
    "git": {"id": "git", "name": {"es": "Git", "en": "Git"}, "category": "tool"},
    "jira": {"id": "jira", "name": {"es": "Jira", "en": "Jira"}, "category": "tool"},
    "postman": {"id": "postman", "name": {"es": "Postman", "en": "Postman"}, "category": "tool"},
    "airflow": {"id": "apache-airflow", "name": {"es": "Apache Airflow", "en": "Apache Airflow"}, "category": "tool"},
    "spark": {"id": "spark", "name": {"es": "Apache Spark", "en": "Apache Spark"}, "category": "tool"},
    "kafka": {"id": "kafka", "name": {"es": "Apache Kafka", "en": "Apache Kafka"}, "category": "tool"},
    "hadoop": {"id": "hadoop", "name": {"es": "Apache Hadoop", "en": "Apache Hadoop"}, "category": "tool"},
    "hive": {"id": "hive", "name": {"es": "Apache Hive", "en": "Apache Hive"}, "category": "tool"},
    "glue": {"id": "aws-glue", "name": {"es": "AWS Glue", "en": "AWS Glue"}, "category": "tool"},
    "databrew": {"id": "glue-databrew", "name": {"es": "AWS Glue DataBrew", "en": "AWS Glue DataBrew"}, "category": "tool"},
    "odp": {"id": "odi", "name": {"es": "Oracle Data Integrator (ODI)", "en": "Oracle Data Integrator (ODI)"}, "category": "tool"},
    "odi": {"id": "odi", "name": {"es": "Oracle Data Integrator (ODI)", "en": "Oracle Data Integrator (ODI)"}, "category": "tool"},
    # Data formats
    "csv": {"id": "csv", "name": {"es": "CSV", "en": "CSV"}, "category": "data-format"},
    "json": {"id": "json", "name": {"es": "JSON", "en": "JSON"}, "category": "data-format"},
    "parquet": {"id": "parquet", "name": {"es": "Parquet", "en": "Parquet"}, "category": "data-format"},
    "avro": {"id": "avro", "name": {"es": "Avro", "en": "Avro"}, "category": "data-format"},
    "xml": {"id": "xml", "name": {"es": "XML", "en": "XML"}, "category": "data-format"},
    # Domain
    "etl": {"id": "etl", "name": {"es": "Procesos ETL", "en": "ETL Processes"}, "category": "domain"},
    "elt": {"id": "elt", "name": {"es": "Procesos ELT", "en": "ELT Processes"}, "category": "domain"},
    "data engineering": {"id": "data-engineering", "name": {"es": "Ingenieria de Datos", "en": "Data Engineering"}, "category": "domain"},
    "data quality": {"id": "data-quality", "name": {"es": "Calidad de Datos", "en": "Data Quality"}, "category": "domain"},
    "machine learning": {"id": "machine-learning", "name": {"es": "Machine Learning", "en": "Machine Learning"}, "category": "domain"},
    "ci/cd": {"id": "cicd", "name": {"es": "CI/CD", "en": "CI/CD"}, "category": "tool"},
}


def extract_skills(text: str, sections: dict) -> list:
    """Extract skills from CV text, matching against known skills."""
    skills_text = sections.get("skills", "")
    if not skills_text:
        return []

    found_skills = []
    seen_ids = set()

    # Normalize text for matching
    text_lower = skills_text.lower()

    # Try matching known skills
    for keyword, skill_data in KNOWN_SKILLS.items():
        # Use word boundary matching for short keywords
        if len(keyword) <= 3:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text_lower):
                if skill_data["id"] not in seen_ids:
                    found_skills.append(skill_data.copy())
                    seen_ids.add(skill_data["id"])
        else:
            if keyword in text_lower:
                if skill_data["id"] not in seen_ids:
                    found_skills.append(skill_data.copy())
                    seen_ids.add(skill_data["id"])

    # Also try to extract skills from bullet points or comma-separated lists
    skill_lines = []
    for line in skills_text.split("\n"):
        line = line.strip()
        if line.startswith("-") or line.startswith("•") or line.startswith("*"):
            skill_lines.append(re.sub(r"^[-•*]\s*", "", line))
        elif "," in line:
            skill_lines.extend([s.strip() for s in line.split(",") if s.strip()])

    # Check each extracted skill line against known skills
    for skill_line in skill_lines:
        skill_lower = skill_line.lower().strip()
        if skill_lower in KNOWN_SKILLS:
            skill_data = KNOWN_SKILLS[skill_lower]
            if skill_data["id"] not in seen_ids:
                found_skills.append(skill_data.copy())
                seen_ids.add(skill_data["id"])

    return found_skills


# ---------------------------------------------------------------------------
# Education extraction
# ---------------------------------------------------------------------------

def extract_education(text: str, sections: dict) -> list:
    """Extract education entries from CV text."""
    education = []

    edu_text = sections.get("education", "")
    if not edu_text:
        return education

    lines = edu_text.split("\n")
    current_edu = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for date range
        date_match = DATE_RANGE_RE.search(stripped)
        if date_match:
            if current_edu and current_edu.get("degree"):
                education.append(current_edu)

            dates = re.split(r"[-–/]", date_match.group(0), maxsplit=1)
            start_date = normalize_date(dates[0]) if dates else ""
            end_date = normalize_date(dates[1]) if len(dates) > 1 else ""

            before_date = stripped[:date_match.start()].strip()
            before_date = re.sub(r"[\|·•]", "", before_date).strip()

            # Try to split degree and institution
            degree = ""
            institution = ""
            if "—" in before_date:
                parts = before_date.split("—", 1)
                degree = parts[0].strip()
                institution = parts[1].strip()
            elif "|" in before_date:
                parts = before_date.split("|", 1)
                degree = parts[0].strip()
                institution = parts[1].strip()
            else:
                degree = before_date

            current_edu = {
                "degree": degree,
                "institution": institution,
                "startDate": start_date,
                "endDate": end_date,
            }
        elif current_edu:
            if not current_edu["institution"] and len(stripped) < 80:
                current_edu["institution"] = stripped

    if current_edu and current_edu.get("degree"):
        education.append(current_edu)

    return education


# ---------------------------------------------------------------------------
# Certifications extraction
# ---------------------------------------------------------------------------

def extract_certifications(text: str, sections: dict) -> list:
    """Extract certifications from CV text."""
    certifications = []

    cert_text = sections.get("certifications", "")
    if not cert_text:
        return certifications

    for line in cert_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("-") and len(line) < 3:
            continue

        # Clean bullet
        line = re.sub(r"^[-•*]\s*", "", line)

        # Try to extract date
        date_match = DATE_RANGE_RE.search(line)
        issue_date = ""
        if date_match:
            issue_date = normalize_date(date_match.group(0))
            name = line[:date_match.start()].strip()
        else:
            name = line

        # Try to split name and issuer
        cert_name = name
        issuer = ""
        if "—" in name:
            parts = name.split("—", 1)
            cert_name = parts[0].strip()
            issuer = parts[1].strip()
        elif "|" in name:
            parts = name.split("|", 1)
            cert_name = parts[0].strip()
            issuer = parts[1].strip()

        if cert_name:
            certifications.append({
                "name": cert_name,
                "issuer": issuer,
                "issueDate": issue_date,
            })

    return certifications


# ---------------------------------------------------------------------------
# KB operations
# ---------------------------------------------------------------------------

def load_yaml(filepath: str) -> dict:
    """Load a YAML file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_all_yaml_in_dir(directory: str) -> list:
    """Load all YAML files in a directory."""
    items = []
    dir_path = Path(directory)
    if not dir_path.exists():
        return items
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        try:
            data = load_yaml(str(yaml_file))
            if data:
                items.append(data)
        except Exception:
            pass
    return items


def slugify(text: str) -> str:
    """Convert text to a kebab-case slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def get_next_id(prefix: str, existing_ids: list) -> str:
    """Generate the next sequential ID for a prefix."""
    max_num = 0
    for eid in existing_ids:
        match = re.match(rf"{re.escape(prefix)}-(\d+)", eid)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return f"{prefix}-{max_num + 1:03d}"


def check_duplicate_experience(exp: dict, existing_experiences: list) -> bool:
    """Check if an experience entry already exists in the KB."""
    for existing in existing_experiences:
        # Match by company name (case-insensitive)
        existing_company = existing.get("company", "").lower()
        new_company = exp.get("company", "").lower()
        if existing_company and new_company and existing_company == new_company:
            # Also check if role is similar
            existing_role = str(existing.get("role", {}).get("es", "")).lower()
            new_role = exp.get("role", "").lower()
            if existing_role and new_role and (
                new_role in existing_role or existing_role in new_role
            ):
                return True
    return False


def check_duplicate_skill(skill: dict, existing_skills: list) -> bool:
    """Check if a skill already exists in the KB."""
    for existing in existing_skills:
        if existing.get("id") == skill.get("id"):
            return True
        existing_name = str(existing.get("name", {}).get("es", "")).lower()
        new_name = str(skill.get("name", {}).get("es", "")).lower()
        if existing_name and new_name and existing_name == new_name:
            return True
    return False


def check_duplicate_education(edu: dict, existing_education: list) -> bool:
    """Check if an education entry already exists in the KB."""
    for existing in existing_education:
        existing_inst = str(existing.get("institution", {}).get("es", "")).lower()
        new_inst = edu.get("institution", "").lower()
        existing_degree = str(existing.get("degree", {}).get("es", "")).lower()
        new_degree = edu.get("degree", "").lower()
        if (existing_inst and new_inst and existing_inst == new_inst and
                existing_degree and new_degree and existing_degree == new_degree):
            return True
    return False


# ---------------------------------------------------------------------------
# YAML generation
# ---------------------------------------------------------------------------

def generate_experience_yaml(exp: dict, exp_id: str) -> str:
    """Generate YAML content for an experience entry."""
    data = {
        "id": exp_id,
        "company": exp["company"],
        "role": {"es": exp["role"], "en": exp["role"]},
        "location": exp.get("location", ""),
        "startDate": exp["startDate"],
        "endDate": exp.get("endDate") or None,
        "type": "full-time",
        "description": {"es": "", "en": ""},
        "highlights": {
            "es": exp.get("highlights", []),
            "en": exp.get("highlights", []),
        },
        "skills_used": [],
        "projects_involved": [],
        "tags": [],
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def generate_education_yaml(edu: dict, edu_id: str) -> str:
    """Generate YAML content for an education entry."""
    data = {
        "id": edu_id,
        "institution": {"es": edu["institution"], "en": edu["institution"]},
        "degree": {"es": edu["degree"], "en": edu["degree"]},
        "field": {"es": "", "en": ""},
        "startDate": edu["startDate"],
        "endDate": edu.get("endDate", ""),
        "type": "associate",
        "description": {"es": "", "en": ""},
        "grades": {"gpa": None, "honors": []},
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def generate_certification_yaml(cert: dict, cert_id: str) -> str:
    """Generate YAML content for a certification entry."""
    data = {
        "id": cert_id,
        "name": {"es": cert["name"], "en": cert["name"]},
        "issuer": cert.get("issuer", ""),
        "issueDate": cert.get("issueDate", ""),
        "expiryDate": "",
        "credentialId": "",
        "url": "",
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest a CV from PDF into the knowledge base")
    parser.add_argument("cv_file", help="Path to the CV PDF file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added without writing")

    args = parser.parse_args()

    if not os.path.exists(args.cv_file):
        print(f"Error: No se encontro el archivo {args.cv_file}")
        sys.exit(1)

    project_root = Path(__file__).parent.parent

    print(f"Parseando CV: {args.cv_file}\n")

    # 1. Extract text from PDF
    print("1. Extrayendo texto del PDF...")
    text = extract_text_from_pdf(args.cv_file)
    if not text.strip():
        print("Error: No se pudo extraer texto del PDF. Verifica que no sea una imagen.")
        sys.exit(1)
    print(f"   Texto extraido: {len(text)} caracteres")

    # 2. Detect sections
    print("\n2. Detectando secciones...")
    sections = detect_sections(text)
    for section_name, content in sections.items():
        preview = content[:80].replace("\n", " ") + ("..." if len(content) > 80 else "")
        print(f"   [{section_name}] {preview}")

    # 3. Load existing KB
    print("\n3. Cargando base de conocimiento existente...")
    existing_skills = load_all_yaml_in_dir(str(project_root / "kb" / "skills"))
    if existing_skills and isinstance(existing_skills[0], dict) and "skills" in existing_skills[0]:
        existing_skills = existing_skills[0]["skills"]
    else:
        existing_skills = []
    existing_experiences = load_all_yaml_in_dir(str(project_root / "kb" / "experience"))
    existing_education = load_all_yaml_in_dir(str(project_root / "kb" / "education"))
    existing_certs = load_all_yaml_in_dir(str(project_root / "kb" / "certifications"))

    existing_exp_ids = [e.get("id", "") for e in existing_experiences]
    existing_edu_ids = [e.get("id", "") for e in existing_education]
    existing_cert_ids = [c.get("id", "") for c in existing_certs]
    existing_skill_ids = [s.get("id", "") for s in existing_skills]

    # 4. Extract data
    print("\n4. Extrayendo datos del CV...")
    profile = extract_profile(text, sections)
    experiences = extract_experiences(text, sections)
    skills = extract_skills(text, sections)
    education = extract_education(text, sections)
    certifications = extract_certifications(text, sections)

    print(f"   Profile: {profile['name'] or '(no detectado)'}")
    print(f"   Experiencias: {len(experiences)}")
    print(f"   Skills: {len(skills)}")
    print(f"   Educacion: {len(education)}")
    print(f"   Certificaciones: {len(certifications)}")

    # 5. Deduplicate
    print("\n5. Verificando duplicados...")
    new_experiences = []
    for exp in experiences:
        if check_duplicate_experience(exp, existing_experiences):
            print(f"   [SKIP] Experiencia duplicada: {exp.get('company', '?')}")
        else:
            new_experiences.append(exp)

    new_skills = []
    for skill in skills:
        if check_duplicate_skill(skill, existing_skills):
            print(f"   [SKIP] Skill duplicada: {skill.get('id', '?')}")
        else:
            new_skills.append(skill)

    new_education = []
    for edu in education:
        if check_duplicate_education(edu, existing_education):
            print(f"   [SKIP] Educacion duplicada: {edu.get('institution', '?')}")
        else:
            new_education.append(edu)

    # Certifications are always new (no good dedup key)
    new_certs = certifications

    # 6. Show summary
    print(f"\n{'=' * 60}")
    print("RESUMEN DE INGESTA")
    print(f"{'=' * 60}")

    if profile["name"]:
        print(f"\n  Profile: {profile['name']}")
        print(f"    Email: {profile['email']}")
        print(f"    Phone: {profile['phone']}")
        print(f"    Location: {profile['location']}")

    if new_experiences:
        print(f"\n  Nuevas experiencias ({len(new_experiences)}):")
        for exp in new_experiences:
            print(f"    - {exp['role']} @ {exp['company']} ({exp['startDate']} - {exp.get('endDate', 'Present')})")

    if new_skills:
        print(f"\n  Nuevas skills ({len(new_skills)}):")
        for skill in new_skills:
            print(f"    - {skill['id']} ({skill['category']})")

    if new_education:
        print(f"\n  Nueva educacion ({len(new_education)}):")
        for edu in new_education:
            print(f"    - {edu['degree']} @ {edu['institution']}")

    if new_certs:
        print(f"\n  Nuevas certificaciones ({len(new_certs)}):")
        for cert in new_certs:
            print(f"    - {cert['name']}")

    total_new = len(new_experiences) + len(new_skills) + len(new_education) + len(new_certs)
    if total_new == 0:
        print("\n  No hay nada nuevo que agregar. La KB ya contiene toda la info del CV.")
        return

    # 7. Confirm and write
    if args.dry_run:
        print(f"\n[DRY-RUN] No se escribio nada. Total: {total_new} entradas nuevas.")
        return

    print(f"\n  Total: {total_new} entradas nuevas")
    confirm = input("\n  Confirmar ingestion? (s/n): ").strip().lower()
    if confirm not in ("s", "si", "y", "yes"):
        print("  Ingestion cancelada.")
        return

    # Write new entries
    print("\n6. Escribiendo en la KB...")

    # Profile - merge with existing
    profile_path = project_root / "kb" / "profile.yaml"
    if profile_path.exists():
        existing_profile = load_yaml(str(profile_path))
        # Merge: only overwrite empty fields
        for key in ["name", "email", "phone", "location"]:
            if not existing_profile.get(key) and profile.get(key):
                existing_profile[key] = profile[key]
        for key in ["title", "summary"]:
            if isinstance(existing_profile.get(key), dict):
                for lang in ["es", "en"]:
                    if not existing_profile[key].get(lang) and profile.get(key, {}).get(lang):
                        existing_profile[key][lang] = profile[key][lang]
            elif not existing_profile.get(key) and profile.get(key):
                existing_profile[key] = profile[key]
        if profile.get("links"):
            if not existing_profile.get("links"):
                existing_profile["links"] = profile["links"]
            else:
                for link_key, link_val in profile["links"].items():
                    if link_val and not existing_profile["links"].get(link_key):
                        existing_profile["links"][link_key] = link_val
        if profile.get("languages") and not existing_profile.get("languages"):
            existing_profile["languages"] = profile["languages"]

        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  [MERGE] profile.yaml actualizado")
    else:
        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  [NEW] profile.yaml creado")

    # Experiences
    for exp in new_experiences:
        exp_id = get_next_id("exp", existing_exp_ids)
        existing_exp_ids.append(exp_id)
        filename = f"{exp_id}-{slugify(exp['company'])}.yaml"
        filepath = project_root / "kb" / "experience" / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(generate_experience_yaml(exp, exp_id))
        print(f"  [NEW] experience/{filename}")

    # Skills
    if new_skills:
        skills_path = project_root / "kb" / "skills" / "skills.yaml"
        if skills_path.exists():
            skills_data = load_yaml(str(skills_path))
        else:
            skills_data = {"skills": []}

        for skill in new_skills:
            # Generate a unique ID if needed
            skill_id = skill["id"]
            if skill_id in existing_skill_ids:
                skill_id = f"{skill_id}-2"
            skill["id"] = skill_id
            skills_data["skills"].append(skill)
            existing_skill_ids.append(skill_id)
            print(f"  [NEW] skills: {skill_id}")

        with open(skills_path, "w", encoding="utf-8") as f:
            yaml.dump(skills_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Education
    for edu in new_education:
        edu_id = get_next_id("edu", existing_edu_ids)
        existing_edu_ids.append(edu_id)
        slug = slugify(edu.get("institution", "unknown"))
        filename = f"{edu_id}-{slug}.yaml"
        filepath = project_root / "kb" / "education" / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(generate_education_yaml(edu, edu_id))
        print(f"  [NEW] education/{filename}")

    # Certifications
    for cert in new_certs:
        cert_id = get_next_id("cert", existing_cert_ids)
        existing_cert_ids.append(cert_id)
        slug = slugify(cert.get("name", "unknown"))
        filename = f"{cert_id}-{slug}.yaml"
        filepath = project_root / "kb" / "certifications" / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(generate_certification_yaml(cert, cert_id))
        print(f"  [NEW] certifications/{filename}")

    print(f"\nIngestion completada. {total_new} entradas nuevas agregadas a la KB.")

    # 8. Validate
    print("\n7. Ejecutando validacion...")
    validate_script = project_root / "scripts" / "validate.py"
    if validate_script.exists():
        os.system(f"python {validate_script}")


if __name__ == "__main__":
    main()
