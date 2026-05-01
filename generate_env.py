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
    if isinstance(platform, list):
        platform = platform[0] if platform else ""
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
            # Strip strict == pins to avoid incompatibility with newer Python
            if ver.startswith("=="):
                ver = ""
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

    # 3. Text cleaning utility (must come before corpus cell)
    clean_code = "\n".join([
        "import unicodedata",
        "",
        "def clean_text(text):",
        "    text = unicodedata.normalize('NFKC', text)",
        "    replacements = {",
        "        chr(0x2018): chr(39), chr(0x2019): chr(39),",
        "        chr(0x201c): chr(34), chr(0x201d): chr(34),",
        "        chr(0x2013): '-', chr(0x2014): '-',",
        "        chr(0x2026): '...', chr(0x00a0): ' ',",
        "        chr(0x00ad): '',",
        "    }",
        "    for k, v in replacements.items():",
        "        text = text.replace(k, v)",
        "    return text",
        "",
        "print('clean_text() ready.')",
    ])
    cells.append(md_cell("## 3. Text cleaning utility\n\nRun this cell first before pasting any text. It removes curly quotes and other characters that cause errors."))
    cells.append(code_cell(clean_code))

    # 4. Dataset
    cells.append(md_cell("## 4. Dataset"))
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
            "# OPTION 1: Upload a file (.txt or .pdf)\n"
            "# Click the upload button, select your file, then run the cell below\n"
            "import ipywidgets as widgets\n"
            "from IPython.display import display\n"
            "import io\n"
            "\n"
            "upload = widgets.FileUpload(accept='.txt,.pdf', multiple=False)\n"
            "display(upload)\n"
            "print('Select a .txt or .pdf file above, then run the next cell.')"
        ))
        cells.append(code_cell(
            "# Run this cell after uploading to load the file\n"
            "if upload.value:\n"
            "    # Compatible with both old and new ipywidgets API\n"
            "    val = upload.value\n"
            "    if isinstance(val, dict):\n"
            "        file_info = list(val.values())[0]\n"
            "        fname = file_info['metadata']['name']\n"
            "        raw = bytes(file_info['content'])\n"
            "    else:\n"
            "        file_info = val[0]\n"
            "        fname = file_info['name']\n"
            "        raw = bytes(file_info['content'])\n"
            "    if fname.endswith('.pdf'):\n"
            "        import subprocess, sys\n"
            "        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pypdf2', '-q'])\n"
            "        import PyPDF2, io as _io\n"
            "        reader = PyPDF2.PdfReader(_io.BytesIO(raw))\n"
            "        text = ' '.join(page.extract_text() or '' for page in reader.pages)\n"
            "    else:\n"
            "        text = raw.decode('utf-8', errors='ignore')\n"
            "    corpus = clean_text(text)\n"
            "    print(f'Loaded: {fname} — {len(corpus.split())} words')\n"
            "else:\n"
            "    print('No file uploaded yet. Use Option 2 below to paste text instead.')"
        ))
        cells.append(code_cell(
            "# OPTION 2: Paste your text directly\n"
            "# Only use this if you did NOT upload a file above\n"
            "# If you uploaded a file, skip this cell entirely\n"
            "if not upload.value:\n"
            "    corpus = clean_text(\"\"\"\n"
            "Paste your text here. Any paragraph from an article, paper,\n"
            "or any source relevant to your research. At least 50 words\n"
            "works best for meaningful results.\n"
            "\"\"\")\n"
            "    print(f'Corpus loaded: {len(corpus.split())} words')\n"
            "else:\n"
            "    print(f'Using uploaded file — corpus already loaded: {len(corpus.split())} words')"
        ))

    # 5. Start exploring
    cells.append(md_cell(
        f"## 5. Start exploring\n\n"
        f"The environment for **{name}** is ready. "
        "All dependencies are installed. Add your analysis below.\n\n"
        "Tip: use `clean_text(your_text)` on any pasted text to avoid encoding errors."
    ))

    # 5b. Results summary (auto-generated for text analysis tools)
    if any(d["name"].lower() in ["nltk", "wordcloud", "matplotlib"] for d in deps):
        cells.append(md_cell("## 5b. Text analysis\n\nThis cell runs the full text analysis on your corpus and generates the word frequency chart and word cloud."))
        cells.append(code_cell(
            "from nltk.corpus import stopwords\n"
            "from nltk.tokenize import word_tokenize\n"
            "from collections import Counter\n"
            "from wordcloud import WordCloud\n"
            "import matplotlib.pyplot as plt\n"
            "import pandas as pd\n"
            "\n"
            "# Download required NLTK data\n"
            "import nltk\n"
            "nltk.download('stopwords', quiet=True)\n"
            "nltk.download('punkt', quiet=True)\n"
            "nltk.download('punkt_tab', quiet=True)\n"
            "\n"
            "# Tokenize and filter\n"
            "stop_words = set(stopwords.words('english'))\n"
            "tokens = word_tokenize(corpus.lower())\n"
            "words = [w for w in tokens if w.isalpha() and w not in stop_words]\n"
            "freq = Counter(words)\n"
            "\n"
            "# Word frequency chart\n"
            "top_words = freq.most_common(15)\n"
            "df = pd.DataFrame(top_words, columns=['word', 'count'])\n"
            "fig, ax = plt.subplots(figsize=(10, 4))\n"
            "ax.barh(df['word'][::-1], df['count'][::-1], color='#534AB7', alpha=0.8)\n"
            "ax.set_xlabel('Frequency')\n"
            "ax.set_title('Top 15 words in corpus')\n"
            "ax.spines[['top', 'right']].set_visible(False)\n"
            "plt.tight_layout()\n"
            "plt.show()\n"
            "\n"
            "# Word cloud\n"
            "text_clean = ' '.join(words)\n"
            "wc = WordCloud(width=800, height=400, background_color='white',\n"
            "               colormap='viridis', max_words=80).generate(text_clean)\n"
            "plt.figure(figsize=(12, 5))\n"
            "plt.imshow(wc, interpolation='bilinear')\n"
            "plt.axis('off')\n"
            "plt.title('Word cloud')\n"
            "plt.tight_layout()\n"
            "plt.savefig('wordcloud.png')\n"
            "plt.show()\n"
            "\n"
            "# Top 5 summary\n"
            "freq_df = pd.DataFrame(freq.most_common(5), columns=['word', 'count'])\n"
            "print('Top 5 words:')\n"
            "print(freq_df.to_string())\n"
            "print('Word cloud saved as wordcloud.png')"
        ))
    elif any(d["name"].lower() == "trafilatura" for d in deps):
        cells.append(md_cell("## 5b. Build your corpus from URLs\n\nPaste your URLs below — one per line. Trafilatura will extract clean text from each page automatically."))
        cells.append(code_cell(
            "import trafilatura\n"
            "\n"
            "# Paste your URLs here — one per line\n"
            "urls = [\n"
            "    'https://en.wikipedia.org/wiki/Digital_humanities',\n"
            "    'https://en.wikipedia.org/wiki/Computational_linguistics',\n"
            "    # Add more URLs here...\n"
            "]\n"
            "\n"
            "corpus = ''\n"
            "for url in urls:\n"
            "    downloaded = trafilatura.fetch_url(url)\n"
            "    text = trafilatura.extract(downloaded) or ''\n"
            "    corpus += text + ' '\n"
            "    print(f'Extracted: {url[:50]} — {len(text.split())} words')\n"
            "\n"
            "print(f'\\nTotal corpus: {len(corpus.split())} words from {len(urls)} sources')"
        ))
        cells.append(md_cell("## 5c. Search your corpus for a keyword\n\nChange the keyword below to find relevant sentences across all your sources automatically."))
        cells.append(code_cell(
            "# Change this to your research keyword\n"
            "keyword = 'digital humanities'\n"
            "\n"
            "print(f'Searching for: \"{keyword}\"\\n')\n"
            "for url in urls:\n"
            "    downloaded = trafilatura.fetch_url(url)\n"
            "    text = trafilatura.extract(downloaded) or ''\n"
            "    sentences = [s.strip() for s in text.split('.') if keyword.lower() in s.lower()]\n"
            "    if sentences:\n"
            "        print(f'From {url[:50]}:')\n"
            "        for s in sentences[:2]:\n"
            "            print(f'  → {s}')\n"
            "        print()\n"
            "print('Search complete.')"
        ))
        cells.append(md_cell("## 5d. Save corpus to file\n\nSave the full extracted text for further analysis."))
        cells.append(code_cell(
            "with open('corpus.txt', 'w') as f:\n"
            "    f.write(corpus)\n"
            "print(f'Corpus saved as corpus.txt — {len(corpus.split())} words total')"
        ))
    else:
        cells.append(code_cell("# Your analysis starts here\n"))

    # 5. Metadata summary
    cells.append(md_cell("## 6. Reproducibility info"))
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
