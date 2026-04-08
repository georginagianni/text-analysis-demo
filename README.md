# text-analysis-demo

A reproducible text analysis pipeline for humanities researchers.  
Environment provisioned automatically from `codemeta.json` — no manual setup required.

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/your-username/text-analysis-demo/HEAD)

---

## How to use this repo

### 1. Push to GitHub

```bash
# Create a new repo on github.com, then:
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/text-analysis-demo.git
git push -u origin main
```

### 2. Update codemeta.json

Edit `codemeta.json` and replace:
- `"your-username"` → your GitHub username
- Author name, email, affiliation → your details

### 3. Regenerate environment files

Every time you edit `codemeta.json`, run:

```bash
python generate_env.py
```

This rewrites `runtime.txt` and `requirements.txt` from the metadata.  
Commit and push all three files.

### 4. Launch on Binder

```
https://mybinder.org/v2/gh/YOUR-USERNAME/text-analysis-demo/HEAD
```

Or open `launcher.html` in a browser — paste the GitHub URL and click **Open in Binder**.

---

## File structure

```
text-analysis-demo/
├── codemeta.json        ← metadata source of truth (edit this)
├── generate_env.py      ← reads codemeta, writes runtime.txt + requirements.txt
├── runtime.txt          ← generated — Binder reads this for Python version
├── requirements.txt     ← generated — Binder installs these packages
├── analysis.ipynb       ← demo notebook (replace with your research code)
├── launcher.html        ← embeddable popup launcher (no server needed)
└── README.md
```

## Adding your own research

1. Replace the sample corpus in `analysis.ipynb` with your data
2. Add your new packages to `softwareRequirements` in `codemeta.json`
3. Run `python generate_env.py` to update `requirements.txt`
4. Push to GitHub — Binder picks up the changes automatically

## CLARIAH Tool Registry

To make this tool discoverable via [tools.clariah.nl](https://tools.clariah.nl),
add your repo to the [CLARIAH source registry](https://github.com/CLARIAH/tool-discovery).
The registry harvests `codemeta.json` nightly and enriches it with NWO research fields
and technology readiness levels.
