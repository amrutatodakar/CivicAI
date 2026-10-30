"""Developer entry point for loading the synthetic demo dataset.

Usage (from the project root, with the virtual environment active):
    python scripts/seed_data.py
    python scripts/seed_data.py --force
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from seed import seed_database  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Load CivicAI synthetic demo data.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete all complaints and reload the demo dataset (destructive).",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        result = seed_database(force=args.force)
        print(result.get("message") or result.get("reason"))
        if result.get("seeded"):
            print(f"Complaints: {result['complaints']}")
            print(f"Duplicate suggestions: {result['duplicate_links']}")


if __name__ == "__main__":
    main()
