#!/usr/bin/env python3
"""
Detect gaps between job requirements and knowledge base.

Usage:
    python gaps.py <offer_name>
    python gaps.py 2026-07-techcorp-senior-backend
"""

import sys
import os
import yaml
from pathlib import Path


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


def load_skills_registry(project_root: Path) -> dict:
    """Load skills master registry and index by ID."""
    skills_path = project_root / "kb" / "skills" / "skills.yaml"
    if not skills_path.exists():
        return {}
    data = load_yaml(str(skills_path))
    return {s["id"]: s for s in data.get("skills", [])}


def load_experience(project_root: Path) -> list:
    """Load all experience entries."""
    exp_dir = project_root / "kb" / "experience"
    return load_all_yaml_in_dir(str(exp_dir))


def check_skill_coverage(requirements: dict, skills_registry: dict, experiences: list) -> dict:
    """Check which required skills are covered by the knowledge base."""
    coverage = {
        "covered": [],
        "partial": [],
        "missing": [],
    }

    # Collect all skills from experience
    experience_skills = set()
    for exp in experiences:
        for skill_id in exp.get("skills_used", []):
            experience_skills.add(skill_id)

    # Check each requirement
    all_requirements = requirements.get("must_have", []) + requirements.get("nice_to_have", [])

    for req in all_requirements:
        parsed = req.get("parsed", {})
        required_techs = parsed.get("technologies", [])

        for tech_id in required_techs:
            if tech_id in experience_skills:
                # Check if it's in the skills registry
                if tech_id in skills_registry:
                    skill = skills_registry[tech_id]
                    coverage["covered"].append({
                        "requirement": req["text"],
                        "skill_id": tech_id,
                        "skill_name": skill.get("name", {}),
                        "level": skill.get("level", "unknown"),
                        "years": skill.get("years", 0),
                    })
                else:
                    coverage["partial"].append({
                        "requirement": req["text"],
                        "skill_id": tech_id,
                        "note": "Used in experience but not in skills registry",
                    })
            else:
                coverage["missing"].append({
                    "requirement": req["text"],
                    "skill_id": tech_id,
                    "type": req.get("type", "other"),
                })

    return coverage


def check_experience_years(requirements: dict, experiences: list) -> dict:
    """Check if experience years requirement is met."""
    total_years = 0
    for exp in experiences:
        start = exp.get("startDate", "")
        end = exp.get("endDate") or "2026-12"

        if start:
            start_year = int(start.split("-")[0])
            end_year = int(end.split("-")[0])
            total_years += end_year - start_year

    result = {
        "total_years": total_years,
        "meets_requirement": True,
        "required_years": None,
    }

    for req in requirements.get("must_have", []):
        parsed = req.get("parsed", {})
        if "years" in parsed:
            required = parsed["years"]
            result["required_years"] = required
            if total_years < required:
                result["meets_requirement"] = False

    return result


def generate_gap_report(coverage: dict, years_check: dict, output_dir: str):
    """Generate a gap analysis report."""
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "gaps.md")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Análisis de Gaps\n\n")

        # Years check
        f.write("## Experiencia\n\n")
        if years_check["required_years"]:
            status = "✅" if years_check["meets_requirement"] else "❌"
            f.write(f"{status} Años de experiencia: {years_check['total_years']} años ")
            f.write(f"(requeridos: {years_check['required_years']}+)\n\n")
        else:
            f.write(f"ℹ️ Años de experiencia: {years_check['total_years']} años ")
            f.write("(no especificado en la oferta)\n\n")

        # Covered skills
        f.write("## Habilidades Cubiertas ✅\n\n")
        if coverage["covered"]:
            for item in coverage["covered"]:
                name = item["skill_name"]
                display_name = name.get("en", name.get("es", item["skill_id"]))
                f.write(f"- **{display_name}** — Nivel: {item['level']}, ")
                f.write(f"Años: {item['years']}\n")
        else:
            f.write("- No se encontraron habilidades coincidentes\n")
        f.write("\n")

        # Partial coverage
        f.write("## Cobertura Parcial ⚠️\n\n")
        if coverage["partial"]:
            for item in coverage["partial"]:
                f.write(f"- {item['requirement']} — {item.get('note', '')}\n")
        else:
            f.write("- No hay coberturas parciales\n")
        f.write("\n")

        # Missing skills
        f.write("## Habilidades Faltantes ❌\n\n")
        if coverage["missing"]:
            for item in coverage["missing"]:
                f.write(f"- {item['requirement']} ")
                f.write(f"(Tipo: {item['type']})\n")
        else:
            f.write("- No se detectaron habilidades faltantes\n")
        f.write("\n")

        # Summary
        total_covered = len(coverage["covered"])
        total_partial = len(coverage["partial"])
        total_missing = len(coverage["missing"])
        total = total_covered + total_partial + total_missing

        f.write("## Resumen\n\n")
        f.write(f"- Cubierto: {total_covered}/{total}")
        if total > 0:
            f.write(f" ({total_covered * 100 // total}%)")
        f.write("\n")
        f.write(f"- Parcial: {total_partial}/{total}\n")
        f.write(f"- Faltante: {total_missing}/{total}\n")

    print(f"Reporte de gaps guardado en: {report_path}")
    return report_path


def main():
    if len(sys.argv) < 2:
        print("Uso: python gaps.py <offer_name>")
        print("Ejemplo: python gaps.py 2026-07-techcorp-senior-backend")
        sys.exit(1)

    offer_name = sys.argv[1]
    project_root = Path(__file__).parent.parent

    # Load analysis
    analysis_path = project_root / "outputs" / offer_name / "analysis.yaml"
    if not analysis_path.exists():
        print(f"Error: No se encontró el análisis en {analysis_path}")
        print("Ejecuta primero: python analyze.py <offer_file.md>")
        sys.exit(1)

    analysis = load_yaml(str(analysis_path))
    requirements = analysis.get("requirements", {})

    # Load knowledge base
    skills_registry = load_skills_registry(project_root)
    experiences = load_experience(project_root)

    print(f"Analizando gaps para: {analysis['offer']['company']} - {analysis['offer']['position']}")

    # Check coverage
    coverage = check_skill_coverage(requirements, skills_registry, experiences)
    years_check = check_experience_years(requirements, experiences)

    # Generate report
    output_dir = project_root / "outputs" / offer_name
    generate_gap_report(coverage, years_check, str(output_dir))

    print("\nAnálisis de gaps completado.")


if __name__ == "__main__":
    main()
