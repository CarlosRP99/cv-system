#!/usr/bin/env python3
"""
Analyze a job offer and extract structured requirements.

Supports both Markdown (.md) and PDF (.pdf) offer files.
Auto-detects format based on file extension.

Usage:
    python analyze.py <offer_file.md>
    python analyze.py <offer_file.pdf>
    python analyze.py offers/2026-07-techcorp-senior-backend.md
"""

import sys
import os
import re
import yaml
from pathlib import Path
from datetime import datetime


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract full text from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        print("Error: pdfplumber no esta instalado. Ejecuta: pip install pdfplumber")
        sys.exit(1)

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n".join(text_parts)


def parse_pdf_to_frontmatter_and_body(text: str) -> dict:
    """Parse extracted PDF text into frontmatter and body sections.

    Tries to detect company, position, and structured requirement sections
    from the raw text of a job offer PDF.
    """
    lines = text.split("\n")
    frontmatter = {}
    body = text

    # Try to extract company/position from the first few lines
    for i, line in enumerate(lines[:10]):
        line = line.strip()
        if not line:
            continue
        # Common patterns: "Company - Position", "Position at Company"
        if " - " in line and not frontmatter.get("company"):
            parts = line.split(" - ", 1)
            frontmatter["company"] = parts[0].strip()
            frontmatter["position"] = parts[1].strip()
            break
        elif re.search(r"\bat\b|\ben\b|\@", line, re.IGNORECASE) and not frontmatter.get("company"):
            parts = re.split(r"\bat\b|\ben\b|\@", line, maxsplit=1, flags=re.IGNORECASE)
            frontmatter["position"] = parts[0].strip()
            frontmatter["company"] = parts[1].strip() if len(parts) > 1 else ""
            break

    # Set defaults
    frontmatter.setdefault("company", "Unknown")
    frontmatter.setdefault("position", "Unknown")
    frontmatter.setdefault("url", "")
    frontmatter.setdefault("date", datetime.now().strftime("%Y-%m-%d"))

    return {"frontmatter": frontmatter, "body": body}


def parse_offer_file(filepath: str) -> dict:
    """Parse a job offer file (Markdown or PDF) into frontmatter + body."""
    ext = Path(filepath).suffix.lower()

    if ext == ".pdf":
        text = extract_text_from_pdf(filepath)
        if not text.strip():
            print("Error: No se pudo extraer texto del PDF.")
            sys.exit(1)
        return parse_pdf_to_frontmatter_and_body(text)
    else:
        # Default: parse as Markdown with YAML frontmatter
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                body = parts[2].strip()
            else:
                frontmatter = {}
                body = content
        else:
            frontmatter = {}
            body = content

        return {"frontmatter": frontmatter, "body": body}


def extract_sections(body: str) -> dict:
    """Extract sections from markdown body by headers."""
    sections = {}
    current_section = "description"
    current_content = []

    for line in body.split("\n"):
        if line.startswith("## "):
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line.replace("## ", "").strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def classify_requirements(body: str) -> dict:
    """Extract and classify requirements from job offer body.

    Supports both Markdown headers (## Section) and plain text sections
    from PDF extraction.
    """
    requirements = {
        "must_have": [],
        "nice_to_have": [],
        "implicit": [],
    }

    sections = extract_sections(body)

    # Section name aliases (Spanish and English)
    must_have_aliases = [
        "requisitos", "requirements", "requisitos obligatorios",
        "must have", "must-have", "requisitos minimos",
        "minimum requirements", "perfil requerido",
    ]
    nice_to_have_aliases = [
        "valorable", "nice to have", "nice-to-have", "deseable",
        "competencias valoradas", "competencias valorables",
        "preferred qualifications", "nice to haves",
        "what we value", "what we look for",
    ]

    # Find must-have section
    must_have_content = ""
    for alias in must_have_aliases:
        if alias in sections:
            must_have_content = sections[alias]
            break

    # Find nice-to-have section
    nice_to_have_content = ""
    for alias in nice_to_have_aliases:
        if alias in sections:
            nice_to_have_content = sections[alias]
            break

    # Parse must-have requirements
    if must_have_content:
        for line in must_have_content.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("• ") or line.startswith("* "):
                requirement = re.sub(r"^[-•*]\s*", "", line).strip()
                if requirement:
                    requirements["must_have"].append({
                        "text": requirement,
                        "type": _classify_requirement_type(requirement),
                        "parsed": _parse_requirement(requirement),
                    })
            elif line and not line.startswith("#"):
                # Plain text line that might be a requirement (PDF format)
                requirements["must_have"].append({
                    "text": line,
                    "type": _classify_requirement_type(line),
                    "parsed": _parse_requirement(line),
                })

    # Parse nice-to-have requirements
    if nice_to_have_content:
        for line in nice_to_have_content.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("• ") or line.startswith("* "):
                requirement = re.sub(r"^[-•*]\s*", "", line).strip()
                if requirement:
                    requirements["nice_to_have"].append({
                        "text": requirement,
                        "type": _classify_requirement_type(requirement),
                        "parsed": _parse_requirement(requirement),
                    })
            elif line and not line.startswith("#"):
                requirements["nice_to_have"].append({
                    "text": line,
                    "type": _classify_requirement_type(line),
                    "parsed": _parse_requirement(line),
                })

    return requirements


def _classify_requirement_type(requirement: str) -> str:
    """Classify a requirement into a type."""
    req_lower = requirement.lower()

    tech_keywords = [
        "python", "java", "javascript", "typescript", "go", "rust",
        "fastapi", "django", "flask", "react", "angular", "vue",
        "postgresql", "mysql", "mongodb", "redis",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "terraform", "jenkins", "ci/cd", "git",
        "spark", "pyspark", "hadoop", "airflow", "kafka",
        "oracle", "sql server", "mssql", "elasticsearch",
        "scrapy", "pandas", "numpy", "scikit-learn",
        "glue", "databrew", "odp", "odi",
        "csv", "json", "parquet", "avro",
        "etl", "elt", "batch", "streaming",
    ]

    for keyword in tech_keywords:
        if keyword in req_lower:
            return "technology"

    experience_patterns = [
        r"\d+\+?\s*año",
        r"\d+\+?\s*year",
        r"experiencia",
        r"experience",
    ]
    for pattern in experience_patterns:
        if re.search(pattern, req_lower):
            return "experience"

    soft_skill_keywords = [
        "liderazgo", "leadership", "comunicación", "communication",
        "trabajo en equipo", "team", "mentoring", "mentoría",
        "aprendizaje", "learning", "curiosidad", "curiosity",
        "det", "orientation", "orientación",
    ]
    for keyword in soft_skill_keywords:
        if keyword in req_lower:
            return "soft_skill"

    if any(w in req_lower for w in ["inglés", "english", "español", "spanish"]):
        return "language"

    return "other"


def _parse_requirement(requirement: str) -> dict:
    """Try to parse structured info from a requirement string."""
    parsed = {"raw": requirement}

    # Extract years of experience
    years_match = re.search(r"(\d+)\+?\s*año", requirement.lower())
    if not years_match:
        years_match = re.search(r"(\d+)\+?\s*year", requirement.lower())
    if years_match:
        parsed["years"] = int(years_match.group(1))

    # Extract technology names
    tech_patterns = {
        "python": "python",
        "java": "java",
        "javascript": "javascript",
        "typescript": "typescript",
        "sql": "sql",
        "fastapi": "fastapi",
        "django": "django",
        "flask": "flask",
        "react": "react",
        "angular": "angular",
        "vue": "vue",
        "postgresql": "postgresql",
        "postgres": "postgresql",
        "mysql": "mysql",
        "docker": "docker",
        "kubernetes": "kubernetes",
        "k8s": "kubernetes",
        "aws": "aws",
        "gcp": "gcp",
        "azure": "azure",
        "terraform": "terraform",
        "jenkins": "jenkins",
        "ci/cd": "cicd",
        "redis": "redis",
        "mongodb": "mongodb",
        "rabbitmq": "rabbitmq",
        "kafka": "kafka",
        "spark": "spark",
        "pyspark": "pyspark",
        "hadoop": "hadoop",
        "airflow": "apache-airflow",
        "git": "git",
        "scrapy": "scrapy",
        "pandas": "pandas",
        "numpy": "numpy",
        "glue": "aws-glue",
        "databrew": "glue-databrew",
        "odp": "odi",
        "odi": "odi",
        "oracle": "oracle-db",
        "sql server": "mssql",
        "mssql": "mssql",
        "csv": "csv",
        "json": "json",
        "parquet": "parquet",
        "etl": "etl",
        "elt": "elt",
        "batch": "batch-processing",
    }

    req_lower = requirement.lower()
    technologies = []
    for pattern, tech_id in tech_patterns.items():
        if pattern in req_lower:
            technologies.append(tech_id)
    if technologies:
        parsed["technologies"] = technologies

    # Extract language requirements
    if "inglés" in req_lower or "english" in req_lower:
        parsed["language"] = "english"
    if "español" in req_lower or "spanish" in req_lower:
        parsed["language"] = "spanish"

    return parsed


def save_analysis(offer_data: dict, requirements: dict, output_dir: str):
    """Save analysis to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    analysis = {
        "offer": {
            "company": offer_data["frontmatter"].get("company", "Unknown"),
            "position": offer_data["frontmatter"].get("position", "Unknown"),
            "url": offer_data["frontmatter"].get("url", ""),
            "date": offer_data["frontmatter"].get("date", ""),
        },
        "requirements": requirements,
        "analyzed_at": datetime.now().isoformat(),
    }

    # Save as YAML
    analysis_path = os.path.join(output_dir, "analysis.yaml")
    with open(analysis_path, "w", encoding="utf-8") as f:
        yaml.dump(analysis, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Save as readable markdown
    md_path = os.path.join(output_dir, "analysis.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Análisis de Oferta: {analysis['offer']['company']}\n\n")
        f.write(f"**Puesto:** {analysis['offer']['position']}\n")
        f.write(f"**URL:** {analysis['offer']['url']}\n")
        f.write(f"**Fecha de análisis:** {analysis['analyzed_at']}\n\n")

        f.write("## Requisitos Obligatorios (Must-Have)\n\n")
        for req in requirements["must_have"]:
            f.write(f"- [{req['type']}] {req['text']}\n")

        f.write("\n## Requisitos Deseables (Nice-to-Have)\n\n")
        for req in requirements["nice_to_have"]:
            f.write(f"- [{req['type']}] {req['text']}\n")

    print(f"Análisis guardado en:")
    print(f"  - {analysis_path}")
    print(f"  - {md_path}")

    return analysis


def main():
    if len(sys.argv) < 2:
        print("Uso: python analyze.py <offer_file>")
        print("Soporta formatos: .md (Markdown) y .pdf (PDF)")
        print("Ejemplo: python analyze.py offers/2026-07-techcorp-senior-backend.md")
        print("Ejemplo: python analyze.py offers/2026-07-nttdata-data-engineer.pdf")
        sys.exit(1)

    offer_file = sys.argv[1]

    if not os.path.exists(offer_file):
        print(f"Error: No se encontro el archivo {offer_file}")
        sys.exit(1)

    # Determine output directory
    offer_name = Path(offer_file).stem
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "outputs" / offer_name

    # Parse offer (auto-detect MD or PDF)
    ext = Path(offer_file).suffix.lower()
    print(f"Analizando oferta ({ext}): {offer_file}")
    offer_data = parse_offer_file(offer_file)

    # If PDF, save raw text for debugging
    if ext == ".pdf":
        raw_path = output_dir / "raw.txt"
        os.makedirs(output_dir, exist_ok=True)
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(offer_data.get("body", ""))
        print(f"  Texto extraído guardado en: {raw_path}")

    # Extract requirements
    requirements = classify_requirements(offer_data["body"])

    total_must = len(requirements["must_have"])
    total_nice = len(requirements["nice_to_have"])
    print(f"Requisitos encontrados: {total_must} obligatorios, {total_nice} deseables")

    # Save analysis
    save_analysis(offer_data, requirements, str(output_dir))

    # Update offer status
    print("\nAnalisis completado.")


if __name__ == "__main__":
    main()
