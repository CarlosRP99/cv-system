#!/usr/bin/env python3
"""
Batch process multiple job offers.

Usage:
    python batch.py                    # Process all pending offers
    python batch.py --status pending   # Filter by status
    python batch.py --list             # List all offers
"""

import sys
import os
import yaml
import argparse
from pathlib import Path


def load_yaml(filepath: str) -> dict:
    """Load a YAML file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_offers(project_root: Path, status_filter: str = None) -> list:
    """List all offers with their status."""
    offers_dir = project_root / "offers"
    if not offers_dir.exists():
        return []

    offers = []
    for offer_file in sorted(offers_dir.glob("*.md")):
        with open(offer_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
            else:
                frontmatter = {}
        else:
            frontmatter = {}

        status = frontmatter.get("status", "pending")

        if status_filter and status != status_filter:
            continue

        offers.append({
            "file": str(offer_file),
            "name": offer_file.stem,
            "company": frontmatter.get("company", "Unknown"),
            "position": frontmatter.get("position", "Unknown"),
            "date": frontmatter.get("date", ""),
            "status": status,
        })

    return offers


def update_offer_status(offer_file: str, new_status: str):
    """Update the status of an offer in its frontmatter."""
    with open(offer_file, "r", encoding="utf-8") as f:
        content = f.read()

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1])
            body = parts[2]
        else:
            frontmatter = {}
            body = content
    else:
        frontmatter = {}
        body = content

    frontmatter["status"] = new_status

    # Reconstruct file
    new_content = "---\n"
    new_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content += "---\n"
    new_content += body

    with open(offer_file, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    parser = argparse.ArgumentParser(description="Batch process job offers")
    parser.add_argument("--list", action="store_true", help="List all offers")
    parser.add_argument("--status", choices=["pending", "analyzed", "applied", "rejected", "offered"],
                        help="Filter by status")

    args = parser.parse_args()
    project_root = Path(__file__).parent.parent

    offers = list_offers(project_root, args.status)

    if args.list:
        if not offers:
            print("No se encontraron ofertas.")
            return

        print(f"\n{'=' * 70}")
        print(f"{'Oferta':<35} {'Empresa':<20} {'Estado':<15}")
        print(f"{'=' * 70}")

        for offer in offers:
            print(f"{offer['name']:<35} {offer['company']:<20} {offer['status']:<15}")

        print(f"\nTotal: {len(offers)} ofertas")
        return

    # Process pending offers
    pending = [o for o in offers if o["status"] == "pending"]

    if not pending:
        print("No hay ofertas pendientes para procesar.")
        return

    print(f"Ofertas pendientes: {len(pending)}\n")

    for offer in pending:
        print(f"Procesando: {offer['company']} - {offer['position']}")

        # Run analyze
        analyze_script = project_root / "scripts" / "analyze.py"
        os.system(f"python {analyze_script} {offer['file']}")

        # Run gaps
        gaps_script = project_root / "scripts" / "gaps.py"
        os.system(f"python {gaps_script} {offer['name']}")

        # Update status
        update_offer_status(offer["file"], "analyzed")

        print(f"  ✅ Completado: {offer['name']}\n")


if __name__ == "__main__":
    main()
