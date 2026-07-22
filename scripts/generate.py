#!/usr/bin/env python3
"""
Generate a CV tailored for a specific job offer.

Usage:
    python generate.py <offer_name> [--lang es|en|both]
    python generate.py 2026-07-techcorp-senior-backend --lang both
"""

import sys
import os
import yaml
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from string import Template


def load_yaml(filepath: str) -> dict:
    """Load a YAML file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_yaml_in_dir(directory: str) -> list:
    """Load all YAML files in a directory."""
    items = []
    dir_path = Path(directory)
    if not dir_path.exists():
        return items
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        data = load_yaml(str(yaml_file))
        if data:
            items.append(data)
    return items


def load_template(template_path: str) -> str:
    """Load a template file."""
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def load_config(project_root: Path) -> dict:
    """Load system configuration."""
    config_path = project_root / "config.yaml"
    if config_path.exists():
        return load_yaml(str(config_path))
    return {}


def load_analysis(project_root: Path, offer_name: str) -> dict:
    """Load the analysis for an offer."""
    analysis_path = project_root / "outputs" / offer_name / "analysis.yaml"
    if analysis_path.exists():
        return load_yaml(str(analysis_path))
    return {}


def load_profile(project_root: Path) -> dict:
    """Load personal profile."""
    profile_path = project_root / "kb" / "profile.yaml"
    if profile_path.exists():
        return load_yaml(str(profile_path))
    return {}


def load_skills_registry(project_root: Path) -> dict:
    """Load skills master registry indexed by ID."""
    skills_path = project_root / "kb" / "skills" / "skills.yaml"
    if not skills_path.exists():
        return {}
    data = load_yaml(str(skills_path))
    return {s["id"]: s for s in data.get("skills", [])}


def load_technologies_registry(project_root: Path) -> dict:
    """Load technologies master registry indexed by ID."""
    tech_path = project_root / "kb" / "technologies" / "technologies.yaml"
    if not tech_path.exists():
        return {}
    data = load_yaml(str(tech_path))
    return {t["id"]: t for t in data.get("technologies", [])}


def select_relevant_experiences(experiences: list, analysis: dict, config: dict) -> list:
    """Select and rank experiences based on relevance to job offer."""
    if not analysis:
        return experiences[:config.get("experience", {}).get("max_items", 6)]

    # Collect all required technologies from analysis
    required_techs = set()
    for req_type in ["must_have", "nice_to_have"]:
        for req in analysis.get("requirements", {}).get(req_type, []):
            parsed = req.get("parsed", {})
            for tech in parsed.get("technologies", []):
                required_techs.add(tech)

    # Score each experience
    scored = []
    for exp in experiences:
        score = 0
        exp_skills = set(exp.get("skills_used", []))
        exp_tags = set(exp.get("tags", []))

        # Score based on skill matches
        for skill_id in exp_skills:
            if skill_id in required_techs:
                score += 3

        # Score based on tag matches
        for tag in exp_tags:
            if tag in required_techs:
                score += 2

        # Bonus for recent experience
        start_date = exp.get("startDate", "")
        if start_date:
            year = int(start_date.split("-")[0])
            if year >= 2023:
                score += 2
            elif year >= 2021:
                score += 1

        scored.append((score, exp))

    # Sort by score (descending), then by date (descending)
    scored.sort(key=lambda x: (-x[0], x[1].get("startDate", "")), reverse=False)
    scored.sort(key=lambda x: -x[0])

    max_items = config.get("experience", {}).get("max_items", 6)
    return [exp for _, exp in scored[:max_items]]


def select_relevant_projects(projects: list, experiences: list, config: dict) -> list:
    """Select projects that are referenced by selected experiences."""
    relevant_ids = set()
    for exp in experiences:
        for proj_id in exp.get("projects_involved", []):
            relevant_ids.add(proj_id)

    if not config.get("projects", {}).get("only_relevant", True):
        return projects

    selected = [p for p in projects if p.get("id") in relevant_ids]
    max_items = config.get("projects", {}).get("max_items", 3)
    return selected[:max_items]


def select_relevant_skills(skills_registry: dict, experiences: list, config: dict) -> list:
    """Select skills that are used in selected experiences."""
    used_skill_ids = set()
    for exp in experiences:
        for skill_id in exp.get("skills_used", []):
            used_skill_ids.add(skill_id)

    selected = []
    for skill_id, skill in skills_registry.items():
        if skill_id in used_skill_ids:
            selected.append(skill)

    max_items = config.get("skills", {}).get("max_items", 15)
    return selected[:max_items]


def group_skills_by_category(skills: list) -> list:
    """Group skills by category for display."""
    groups = {}
    for skill in skills:
        category = skill.get("category", "other")
        if category not in groups:
            groups[category] = []
        groups[category].append(skill)

    # Map category IDs to display names
    category_names = {
        "programming": {"es": "Lenguajes", "en": "Languages"},
        "framework": {"es": "Frameworks", "en": "Frameworks"},
        "tool": {"es": "Herramientas", "en": "Tools"},
        "database": {"es": "Bases de datos", "en": "Databases"},
        "soft-skill": {"es": "Habilidades blandas", "en": "Soft Skills"},
        "domain": {"es": "Conocimiento del dominio", "en": "Domain Knowledge"},
        "library": {"es": "Librerías", "en": "Libraries"},
        "cloud": {"es": "Cloud", "en": "Cloud"},
        "data-format": {"es": "Formatos de datos", "en": "Data Formats"},
    }

    result = []
    for category_id, skills_list in groups.items():
        result.append({
            "category": category_names.get(category_id, {}).get("en", category_id),
            "skills": skills_list,
        })

    return result


def render_section(template_path: str, context: dict) -> str:
    """Render a template section with context data."""
    if not os.path.exists(template_path):
        return ""

    template_str = load_template(template_path)

    # Simple template rendering using string replacement
    # Handles {{variable}} and basic {{#each}} blocks
    result = template_str

    # Simple variable replacement
    for key, value in context.items():
        if isinstance(value, str):
            result = result.replace("{{" + key + "}}", value)
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str):
                    result = result.replace("{{" + key + "." + sub_key + "}}", sub_value)

    return result


def render_cv_markdown(profile: dict, data: dict, lang: str, templates_dir: Path, config: dict = None) -> str:
    """Render the complete CV as markdown."""
    if config is None:
        config = {}
    sections = []

    # Header
    header_template = templates_dir / "header.md"
    if header_template.exists():
        context = {
            "name": profile.get("name", ""),
            "title": profile.get("title", {}),
            "location": profile.get("location", ""),
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "links": profile.get("links", {}),
        }
        sections.append(render_section(str(header_template), context))

    # Summary
    summary_template = templates_dir / "summary.md"
    if summary_template.exists():
        context = {
            "summary": profile.get("summary", {}),
        }
        sections.append(render_section(str(summary_template), context))

    # Experience
    experience_template = templates_dir / "experience.md"
    if experience_template.exists() and data.get("experiences"):
        exp_config = config.get("experience", {})
        max_highlights = exp_config.get("max_highlights", 3)
        show_desc = exp_config.get("show_description", True)
        sections.append(_render_experience_section(data["experiences"], lang, max_highlights, show_desc))

    # Projects
    projects_template = templates_dir / "projects.md"
    if projects_template.exists() and data.get("projects"):
        sections.append(_render_projects_section(data["projects"], lang))

    # Skills
    skills_template = templates_dir / "skills.md"
    if skills_template.exists() and data.get("skills"):
        skill_groups = group_skills_by_category(data["skills"])
        compact_skills = config.get("skills", {}).get("compact", True)
        sections.append(_render_skills_section(skill_groups, lang, compact_skills))

    # Education
    education_template = templates_dir / "education.md"
    if education_template.exists() and data.get("education"):
        sections.append(_render_education_section(data["education"], lang))

    # Certifications
    cert_template = templates_dir / "certifications.md"
    if cert_template.exists() and data.get("certifications"):
        sections.append(_render_certifications_section(data["certifications"], lang))

    return "\n\n".join(filter(None, sections))


def _render_experience_section(experiences: list, lang: str, max_highlights: int = 3, show_description: bool = True) -> str:
    """Render the experience section."""
    lines = ["## Experiencia Profesional" if lang == "es" else "## Professional Experience"]

    for exp in experiences:
        role = exp.get("role", {}).get(lang, exp.get("role", {}).get("en", ""))
        company = exp.get("company", "")
        start = exp.get("startDate", "")
        end = exp.get("endDate") or ("Presente" if lang == "es" else "Present")
        location = exp.get("location", "")

        lines.append(f"\n### {role} — {company}")
        lines.append(f"{start} – {end} | {location}")

        desc = exp.get("description", {}).get(lang, "")
        if desc and show_description:
            lines.append(f"\n{desc}")

        highlights = exp.get("highlights", {}).get(lang, [])
        if highlights:
            lines.append("")
            for h in highlights[:max_highlights]:
                lines.append(f"- {h}")

    return "\n".join(lines)


def _render_projects_section(projects: list, lang: str) -> str:
    """Render the projects section."""
    title = "## Proyectos Destacados" if lang == "es" else "## Key Projects"
    lines = [title]

    for proj in projects:
        name = proj.get("name", "")
        start = proj.get("startDate", "")
        end = proj.get("endDate") or ("Presente" if lang == "es" else "Present")
        role = proj.get("role", {}).get(lang, "")
        desc = proj.get("description", {}).get(lang, "")
        highlights = proj.get("highlights", {}).get(lang, [])

        lines.append(f"\n### {name}")
        lines.append(f"{start} – {end} | {role}")

        if desc:
            lines.append(f"\n{desc}")

        if highlights:
            lines.append("")
            for h in highlights:
                lines.append(f"- {h}")

    return "\n".join(lines)


def _render_skills_section(skill_groups: list, lang: str, compact: bool = True) -> str:
    """Render the skills section."""
    title = "## Habilidades" if lang == "es" else "## Skills"
    lines = [title]

    for group in skill_groups:
        category = group.get("category", "")
        skills = group.get("skills", [])
        skill_names = []
        for s in skills:
            name = s.get("name", {}).get(lang, s.get("name", {}).get("en", s.get("id", "")))
            skill_names.append(name)

        if skill_names:
            if compact:
                # One line per category, all skills comma-separated
                lines.append(f"\n**{category}:** {', '.join(skill_names)}")
            else:
                # Multiple lines per category
                lines.append(f"\n**{category}:**")
                for name in skill_names:
                    lines.append(f"  - {name}")

    return "\n".join(lines)


def _render_education_section(education: list, lang: str) -> str:
    """Render the education section."""
    title = "## Formación Académica" if lang == "es" else "## Education"
    lines = [title]

    for edu in education:
        degree = edu.get("degree", {}).get(lang, "")
        institution = edu.get("institution", {}).get(lang, "")
        start = edu.get("startDate", "")
        end = edu.get("endDate", "")
        desc = edu.get("description", {}).get(lang, "")

        lines.append(f"\n### {degree} — {institution}")
        lines.append(f"{start} – {end}")

        if desc:
            lines.append(f"\n{desc}")

    return "\n".join(lines)


def _render_certifications_section(certifications: list, lang: str) -> str:
    """Render the certifications section."""
    title = "## Certificaciones" if lang == "es" else "## Certifications"
    lines = [title]

    for cert in certifications:
        name = cert.get("name", {}).get(lang, "")
        issuer = cert.get("issuer", "")
        issue_date = cert.get("issueDate", "")
        expiry = cert.get("expiryDate", "")

        date_str = issue_date
        if expiry:
            date_str += f" - {expiry}"

        lines.append(f"\n- **{name}** — {issuer} ({date_str})")

    return "\n".join(lines)


def generate_pdf(markdown_path: str, pdf_path: str, config: dict):
    """Generate PDF from markdown using Pandoc."""
    pdf_config = config.get("pdf", {})
    margins = pdf_config.get("margins", {})
    font_size = pdf_config.get("font_size", "10pt")

    top = margins.get("top", "1.5cm")
    bottom = margins.get("bottom", "1.5cm")
    left = margins.get("left", "2cm")
    right = margins.get("right", "2cm")

    try:
        cmd = [
            "pandoc",
            markdown_path,
            "-o", pdf_path,
            "--pdf-engine=xelatex",
            "-V", f"geometry:top={top}",
            "-V", f"geometry:bottom={bottom}",
            "-V", f"geometry:left={left}",
            "-V", f"geometry:right={right}",
            "-V", f"fontsize={font_size}",
            "-V", "mainfont=Calibri",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"  PDF generado: {pdf_path}")
    except FileNotFoundError:
        print(f"  [WARN] Pandoc no encontrado. PDF no generado.")
        print(f"     Instala Pandoc: https://pandoc.org/installing.html")
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] Error al generar PDF: {e.stderr}")


def main():
    parser = argparse.ArgumentParser(description="Generate a tailored CV")
    parser.add_argument("offer_name", help="Name of the offer (folder name in outputs/)")
    parser.add_argument("--lang", choices=["es", "en", "both"], default="both",
                        help="Language(s) to generate (default: both)")
    parser.add_argument("--pdf", action="store_true", default=True,
                        help="Generate PDF (requires Pandoc)")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF generation")

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    offer_dir = project_root / "outputs" / args.offer_name

    if not offer_dir.exists():
        print(f"Error: No se encontró la oferta en {offer_dir}")
        print("Ejecuta primero: python analyze.py <offer_file.md>")
        sys.exit(1)

    # Load all data
    print(f"Generando CV para: {args.offer_name}")
    config = load_config(project_root)
    profile = load_profile(project_root)
    analysis = load_analysis(project_root, args.offer_name)
    experiences = load_all_yaml_in_dir(str(project_root / "kb" / "experience"))
    projects = load_all_yaml_in_dir(str(project_root / "kb" / "projects"))
    education = load_all_yaml_in_dir(str(project_root / "kb" / "education"))
    certifications = load_all_yaml_in_dir(str(project_root / "kb" / "certifications"))
    skills_registry = load_skills_registry(project_root)

    # Select relevant content
    selected_experiences = select_relevant_experiences(experiences, analysis, config)
    selected_projects = select_relevant_projects(projects, selected_experiences, config)
    selected_skills = select_relevant_skills(skills_registry, selected_experiences, config)

    print(f"  Experiencias seleccionadas: {len(selected_experiences)}")
    print(f"  Proyectos seleccionados: {len(selected_projects)}")
    print(f"  Habilidades seleccionadas: {len(selected_skills)}")

    # Determine languages to generate
    languages = []
    if args.lang == "both":
        languages = config.get("languages", ["es", "en"])
    else:
        languages = [args.lang]

    # Generate CVs
    data = {
        "experiences": selected_experiences,
        "projects": selected_projects,
        "skills": selected_skills,
        "education": education,
        "certifications": certifications,
    }

    for lang in languages:
        templates_dir = project_root / "templates" / lang
        output_md = offer_dir / f"cv-{lang}.md"

        print(f"\nGenerando CV en {lang.upper()}...")

        # Render markdown
        cv_content = render_cv_markdown(profile, data, lang, templates_dir, config)

        # Save markdown
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(cv_content)
        print(f"  Markdown generado: {output_md}")

        # Generate PDF if requested
        if not args.no_pdf and args.pdf:
            pdf_path = offer_dir / f"cv-{lang}.pdf"
            generate_pdf(str(output_md), str(pdf_path), config)

    print("\nGeneración completada.")


if __name__ == "__main__":
    main()
