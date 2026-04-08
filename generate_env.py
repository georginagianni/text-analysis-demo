#!/usr/bin/env python3
"""
generate_env.py
---------------
Reads any codemeta.json and generates:
  1. runtime.txt        — Binder-compatible runtime pin
  2. requirements.txt   — pip install list
  3. notebook.ipynb     — auto-generated starter notebook (no manual coding)

Run from the repo root:
    python generate_env.py

Completely generic — works with any codemeta.json.
No manual editing required per tool.
"""

import json
import re
import sys
from pathlib import Path

CODEMETA = Path("codemeta.json")
RUNTIME  = Path("runtime.txt")
REQS     = Path("requirements.txt")
NOTEBOOK = Path("notebook.ipynb")

LANG_PREFIX = {"python": "python", "r": "r", "julia": "julia"}


def load_codemeta():
    if not CODEMETA.exists():
        sys.exit("codemeta.json not found. Run from the repo root.")
    with open(CODEMETA) as f:
        return json.load(f)


def extract_version(platform):
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", platform or "")
    return m.group(1) if m else "3.10"


def get_lang(meta):
    raw = meta.get("programmingLanguage", {})
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return (raw.get("name", "") if isinstance(raw, dict) else str(raw)).strip()


def get_runtime(meta):
    lang = get_lang(meta).lower()
    prefix = LANG_PREFIX.get(lang, "python")
    ver = extract_version(meta.get("runtimePlatform", ""))
    return f"{prefix}-{ver}"


def get_deps(meta):
    raw = meta.get("softwareRequirements", [])
    deps = []
    for item in (raw if isinstance(raw, list) else []):
        if isinstance(item, str):
            deps.append({"name": item, "version": ""})
        elif isinstance(item, dict) and item.get("name"):
            ver = item.get("version", "")
            if ver and not re.match(r"^[><=!]", ver):
                ver = f"=={ver}"
            deps.append({"name": item["name"], "version": ver})
    return deps


def get_datasets(meta):
    urls = []
    for key in ["distribution", "contentUrl", "downloadUrl"]:
        val = meta.get(key)
        if not val:
            continue
        if isinstance(val, str):
            urls.append(val)
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str):
                    urls.append(v)
                elif isinstance(v, dict) and v.get("contentUrl"):
                    urls.append(v["contentUrl"])
    return urls


def get_authors(meta):
    authors = meta.get("author", [])
    if not authors:
        return "—"
    if not isinstance(authors, list):
        authors = [authors]
    names = []
    for a in authors:
        if isinstance(a, str):
            names.append(a)
        elif isinstance(a, dict):
            g = a.get("givenName", "")
            f = a.get("familyName", "")
            names.append((g + " " + f).strip() or a.get("name", ""))
    return ", ".join(n for n in names if n)


def md_cell(source):
    return {
        "cell_type": "markdown",
        "id": f"md{abs(hash(source)) % 99999:05d}",
        "metadata": {},
        "source": source
    }


def code_cell(source):
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": f"cd{abs(hash(source)) % 99999:05d}",
        "metadata": {},
        "outputs": [],
        "source": source
    }


def build_notebook(meta, deps, datasets):
    name        = meta.get("name", "Research Tool")
    version     = meta.get("version", "")
    description = meta.get("description", "No description provided.")
    authors     = get_authors(meta)
    repo        = meta.get("codeRepository", "")
    lang        = get_lang(meta) or "Python"
    keywords    = meta.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]

    ver_str  = f" v{version}" if version and version != "—" else ""
    kw_str   = ", ".join(keywords[:6]) if keywords else "—"
    repo_str = f"[{repo}]({repo})" if repo else "—"
    dep_list = "\n".join(f"- `{d['name']}{d['version']}`" for d in deps) or "- None declared"

    cells = []

    # Title
    cells.append(md_cell(
        f"# {name}{ver_str}\n\n"
        f"{description}\n\n"
        f"| | |\n|---|---|\n"
        f"| **Authors** | {authors} |\n"
        f"| **Language** | {lang} |\n"
        f"| **Keywords** | {kw_str} |\n"
        f"| **Repository** | {repo_str} |\n"
        f"| **Dependencies** | |\n\n"
        f"{dep_list}\n\n"
        f"---\n"
        f"*Auto-generated from `codemeta.json` — no manual coding required.*"
    ))

    # 1. Environment check
    cells.append(md_cell("## 1. Environment check"))
    env_code = "import sys\nprint(f'Python {sys.version}')\n\n"
    if deps:
        env_code += "import importlib\nmissing = []\n"
        for d in deps[:8]:
            pkg = d["name"].replace("-", "_").lower()
            name_val = d["name"]
        env_code += (
                f"try:\n    importlib.import_module('{pkg}')\n"
                f"    print('  OK  {name_val}')\n"
                f"except ImportError:\n"
                f"    missing.append('{name_val}')\n"
                f"    print('  MISSING  {name_val}')\n"
            )
        env_code += "\nprint('All OK.' if not missing else f'Missing: {missing}')\n"
    cells.append(code_cell(env_code))

    # 2. Import dependencies
    if deps:
        cells.append(md_cell("## 2. Import dependencies"))
        skip = {"jupyter", "ipykernel", "notebook", "jupyterlab"}
        import_map = {
            "scikit-learn": "sklearn", "pillow": "PIL",
            "beautifulsoup4": "bs4", "pyyaml": "yaml",
        }
        imports = []
        for d in deps:
            pkg = d["name"].lower()
            if pkg in skip:
                continue
            imp = import_map.get(pkg, pkg.replace("-", "_"))
            imports.append(f"import {imp}")
        if imports:
            cells.append(code_cell(
                "\n".join(imports) + "\n\nprint('All imports successful.')"
            ))

    # 3. Dataset
    cells.append(md_cell("## 3. Dataset"))
    if datasets:
        ds_code = "import urllib.request, os\n\ndatasets = [\n"
        for url in datasets:
            fname = url.split("/")[-1] or "dataset.dat"
            ds_code += f"    ('{url}', '{fname}'),\n"
        ds_code += "]\n\nfor url, fname in datasets:\n"
        ds_code += "    if not os.path.exists(fname):\n"
        ds_code += "        print(f'Downloading {fname}...')\n"
        ds_code += "        urllib.request.urlretrieve(url, fname)\n"
        ds_code += "    else:\n"
        ds_code += "        print(f'Already present: {fname}')\n"
        cells.append(code_cell(ds_code))
    else:
        cells.append(md_cell(
            "No dataset URL was declared in `codemeta.json`.\n\n"
            "Add a `contentUrl` or `distribution` field to your codemeta.json "
            "to have data loaded automatically.\n\n"
            "Or load your own data below:"
        ))
        cells.append(code_cell(
            "# Load your data here\n"
            "# Example:\n"
            "# import pandas as pd\n"
            "# df = pd.read_csv('your_file.csv')\n"
            "# df.head()\n"
        ))

    # 4. Start exploring
    cells.append(md_cell(
        f"## 4. Start exploring\n\n"
        f"The environment for **{name}** is ready. "
        "All dependencies are installed. Add your analysis below."
    ))
    cells.append(code_cell("# Your analysis starts here\n"))

    # 5. Metadata summary
    cells.append(md_cell("## 5. Reproducibility info"))
    cells.append(code_cell(
        "import json\n"
        "with open('codemeta.json') as f:\n"
        "    meta = json.load(f)\n\n"
        "print(f\"Tool    : {meta.get('name','—')} {meta.get('version','')}\")\n"
        "print(f\"License : {meta.get('license','—')}\")\n"
        "print(f\"Repo    : {meta.get('codeRepository','—')}\")\n"
        "deps = meta.get('softwareRequirements',[])\n"
        "print(f\"Deps    : {[d.get('name',d) if isinstance(d,dict) else d for d in deps]}\")\n"
    ))

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": f"{lang} 3",
                "language": lang.lower(),
                "name": "python3"
            },
            "language_info": {
                "name": lang.lower(),
                "version": extract_version(meta.get("runtimePlatform", "3.10"))
            }
        },
        "cells": cells
    }


def main():
    meta     = load_codemeta()
    deps     = get_deps(meta)
    datasets = get_datasets(meta)

    # 1. runtime.txt
    runtime = get_runtime(meta)
    RUNTIME.write_text(runtime + "\n")
    print(f"  runtime.txt      →  {runtime}")

    # 2. requirements.txt
    reqs = [f"{d['name']}{d['version']}" for d in deps]
    REQS.write_text("\n".join(reqs) + "\n" if reqs else "# no dependencies\n")
    print(f"  requirements.txt →  {len(reqs)} package(s)")
    for r in reqs:
        print(f"      {r}")

    # 3. notebook.ipynb
    nb = build_notebook(meta, deps, datasets)
    with open(NOTEBOOK, "w") as f:
        json.dump(nb, f, indent=1)
    print(f"  notebook.ipynb   →  {len(nb['cells'])} cells auto-generated")

    # Binder URL
    repo_url = meta.get("codeRepository", "")
    if repo_url and "github.com" in repo_url:
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        binder = f"https://mybinder.org/v2/gh/{owner}/{repo}/HEAD?urlpath=notebook/notebook.ipynb"
        print(f"\n  Binder URL (opens notebook directly):")
        print(f"  {binder}")

    print("\nDone. Commit all 4 files to GitHub.")


if __name__ == "__main__":
    main()
