#!/usr/bin/env python3
"""
generate_env.py
---------------
Reads codemeta.json and generates the Binder-compatible environment files:
  - runtime.txt
  - requirements.txt

Run once after editing codemeta.json, then commit all three files to GitHub.
Binder reads runtime.txt + requirements.txt automatically on launch.
"""

import json
import re
import sys
from pathlib import Path

CODEMETA = Path("codemeta.json")
RUNTIME  = Path("runtime.txt")
REQS     = Path("requirements.txt")

LANG_RUNTIME_PREFIX = {
    "python": "python",
    "r":      "r",
    "julia":  "julia",
}


def load_codemeta():
    if not CODEMETA.exists():
        sys.exit("codemeta.json not found. Run this script from the repo root.")
    with open(CODEMETA) as f:
        return json.load(f)


def extract_version(platform_str: str) -> str:
    """Pull version number from e.g. 'Python 3.10' → '3.10'."""
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", platform_str or "")
    return match.group(1) if match else "3.10"


def resolve_runtime(meta: dict) -> str:
    lang_raw = meta.get("programmingLanguage", {})
    if isinstance(lang_raw, list):
        lang_raw = lang_raw[0]
    lang = (lang_raw.get("name", "") if isinstance(lang_raw, dict) else str(lang_raw)).lower()

    prefix = LANG_RUNTIME_PREFIX.get(lang, "python")
    platform = meta.get("runtimePlatform", "")
    version = extract_version(platform) if platform else "3.10"

    return f"{prefix}-{version}"


def resolve_requirements(meta: dict) -> list[str]:
    raw = meta.get("softwareRequirements", [])
    lines = []
    for item in raw:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            name = item.get("name", "")
            ver  = item.get("version", "")
            if name:
                # Normalise: ">=3.8" stays, plain "3.8" becomes "==3.8"
                if ver and not re.match(r"^[><=!]", ver):
                    ver = f"=={ver}"
                lines.append(f"{name}{ver}")
    return lines


def main():
    meta = load_codemeta()

    # --- runtime.txt ---
    runtime = resolve_runtime(meta)
    RUNTIME.write_text(runtime + "\n")
    print(f"  runtime.txt  →  {runtime}")

    # --- requirements.txt ---
    reqs = resolve_requirements(meta)
    if not reqs:
        print("  WARNING: no softwareRequirements found in codemeta.json")
    REQS.write_text("\n".join(reqs) + "\n")
    print(f"  requirements.txt  →  {len(reqs)} package(s)")
    for r in reqs:
        print(f"      {r}")

    # --- Binder URL hint ---
    repo_url = meta.get("codeRepository", "")
    if repo_url and "github.com" in repo_url:
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        binder_url = f"https://mybinder.org/v2/gh/{owner}/{repo}/HEAD"
        print(f"\n  Binder URL (once pushed to GitHub):")
        print(f"  {binder_url}")
    else:
        print("\n  Set 'codeRepository' in codemeta.json to get your Binder URL.")

    print("\nDone. Commit codemeta.json, runtime.txt, and requirements.txt to GitHub.")


if __name__ == "__main__":
    main()
