#!/usr/bin/env python3
"""
Validate knowledge base integrity.

Usage:
    python validate.py
"""

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
        try:
            data = load_yaml(str(yaml_file))
            if data:
                items.append({"file": str(yaml_file), "data": data})
        except Exception as e:
            items.append({"file": str(yaml_file), "error": str(e)})
    return items


def validate_profile(project_root: Path) -> list:
    """Validate profile.yaml has required fields."""
    issues = []
    profile_path = project_root / "kb" / "profile.yaml"

    if not profile_path.exists():
        issues.append({"severity": "error", "message": "kb/profile.yaml no existe"})
        return issues

    profile = load_yaml(str(profile_path))

    required_fields = ["name", "email", "phone"]
    for field in required_fields:
        if not profile.get(field):
            issues.append({
                "severity": "warning",
                "message": f"profile.yaml: Campo '{field}' vacío o no definido",
            })

    # Check bilingual fields
    bilingual_fields = ["title", "summary"]
    for field in bilingual_fields:
        value = profile.get(field, {})
        if not value.get("es"):
            issues.append({
                "severity": "warning",
                "message": f"profile.yaml: Campo '{field}.es' vacío",
            })
        if not value.get("en"):
            issues.append({
                "severity": "warning",
                "message": f"profile.yaml: Campo '{field}.en' vacío",
            })

    return issues


def validate_skills(project_root: Path) -> list:
    """Validate skills.yaml has no duplicates and required fields."""
    issues = []
    skills_path = project_root / "kb" / "skills" / "skills.yaml"

    if not skills_path.exists():
        issues.append({"severity": "error", "message": "kb/skills/skills.yaml no existe"})
        return issues

    skills_data = load_yaml(str(skills_path))
    skills = skills_data.get("skills", [])

    # Check for duplicate IDs
    seen_ids = {}
    for skill in skills:
        skill_id = skill.get("id")
        if not skill_id:
            issues.append({
                "severity": "error",
                "message": "Skill sin 'id' definido",
            })
            continue

        if skill_id in seen_ids:
            issues.append({
                "severity": "error",
                "message": f"Skill ID duplicado: '{skill_id}'",
            })
        seen_ids[skill_id] = skill

        # Check required fields
        if not skill.get("name"):
            issues.append({
                "severity": "warning",
                "message": f"Skill '{skill_id}': Campo 'name' vacío",
            })
        if not skill.get("category"):
            issues.append({
                "severity": "warning",
                "message": f"Skill '{skill_id}': Campo 'category' vacío",
            })

    return issues


def validate_experiences(project_root: Path) -> list:
    """Validate experience files."""
    issues = []
    exp_dir = project_root / "kb" / "experience"

    if not exp_dir.exists():
        issues.append({"severity": "error", "message": "kb/experience/ no existe"})
        return issues

    experiences = load_all_yaml_in_dir(str(exp_dir))

    for exp_item in experiences:
        if "error" in exp_item:
            issues.append({
                "severity": "error",
                "message": f"Error al cargar {exp_item['file']}: {exp_item['error']}",
            })
            continue

        exp = exp_item["data"]
        filename = Path(exp_item["file"]).name

        # Check required fields
        if not exp.get("id"):
            issues.append({
                "severity": "error",
                "message": f"{filename}: Campo 'id' vacío",
            })
        if not exp.get("company"):
            issues.append({
                "severity": "warning",
                "message": f"{filename}: Campo 'company' vacío",
            })
        if not exp.get("role"):
            issues.append({
                "severity": "warning",
                "message": f"{filename}: Campo 'role' vacío",
            })
        if not exp.get("startDate"):
            issues.append({
                "severity": "warning",
                "message": f"{filename}: Campo 'startDate' vacío",
            })

        # Check bilingual fields
        role = exp.get("role", {})
        if isinstance(role, dict):
            if not role.get("es"):
                issues.append({
                    "severity": "warning",
                    "message": f"{filename}: role.es vacío",
                })
            if not role.get("en"):
                issues.append({
                    "severity": "warning",
                    "message": f"{filename}: role.en vacío",
                })

    return issues


def validate_cross_references(project_root: Path) -> list:
    """Validate that cross-references between files are valid."""
    issues = []

    # Load registries
    skills_path = project_root / "kb" / "skills" / "skills.yaml"
    if skills_path.exists():
        skills_data = load_yaml(str(skills_path))
        valid_skill_ids = {s["id"] for s in skills_data.get("skills", [])}
    else:
        valid_skill_ids = set()

    # Check experience references
    exp_dir = project_root / "kb" / "experience"
    if exp_dir.exists():
        for exp_file in sorted(exp_dir.glob("*.yaml")):
            exp = load_yaml(str(exp_file))
            if not exp:
                continue

            for skill_id in exp.get("skills_used", []):
                if skill_id not in valid_skill_ids:
                    issues.append({
                        "severity": "error",
                        "message": f"{exp_file.name}: Skill ID '{skill_id}' no existe en skills registry",
                    })

    return issues


def main():
    project_root = Path(__file__).parent.parent

    print("Validando base de conocimiento...\n")

    all_issues = []

    # Run validations
    print("1. Validando profile.yaml...")
    all_issues.extend(validate_profile(project_root))

    print("2. Validando skills.yaml...")
    all_issues.extend(validate_skills(project_root))

    print("3. Validando experiences...")
    all_issues.extend(validate_experiences(project_root))

    print("4. Validando cross-references...")
    all_issues.extend(validate_cross_references(project_root))

    # Report
    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]

    print(f"\n{'=' * 50}")
    print(f"Resultados: {len(errors)} errores, {len(warnings)} advertencias")

    if errors:
        print(f"\n[ERROR] ERRORES:")
        for issue in errors:
            print(f"  - {issue['message']}")

    if warnings:
        print(f"\n[WARN]  ADVERTENCIAS:")
        for issue in warnings:
            print(f"  - {issue['message']}")

    if not all_issues:
        print("\n[OK] Base de conocimiento valida. No se encontraron problemas.")

    return 1 if errors else 0


if __name__ == "__main__":
    exit(main())
