#!/usr/bin/env python3
"""
generate_ansible.py
-------------------
Reads any codemeta.json and generates an executable Ansible playbook.

Input  : codemeta.json  (any valid codemeta file)
Output : playbook.yml   (Ansible playbook that provisions the environment)

Run:
    python generate_ansible.py          # generates playbook.yml
    ansible-playbook playbook.yml       # runs the playbook

Restrictions (as agreed with supervisor):
    - Python-only tools
    - No API access required
    - No login credentials needed
    - No interaction with the user required
"""

import json
import re
import sys
from pathlib import Path

CODEMETA = Path("codemeta.json")
PLAYBOOK = Path("playbook.yml")

LANG_PREFIX = {"python": "python", "r": "r", "julia": "julia"}


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_codemeta():
    if not CODEMETA.exists():
        sys.exit("codemeta.json not found. Run from the repo root.")
    with open(CODEMETA) as f:
        return json.load(f)


# ── Extractors ────────────────────────────────────────────────────────────────

def get_lang(meta):
    raw = meta.get("programmingLanguage", {})
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return (raw.get("name", "") if isinstance(raw, dict) else str(raw)).strip()


def get_version(meta):
    platform = meta.get("runtimePlatform", "") or ""
    if isinstance(platform, list):
        platform = platform[0] if platform else ""
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", platform)
    return m.group(1) if m else "3.10"


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


def get_repo(meta):
    return meta.get("codeRepository", "")


def get_os(meta):
    os_raw = meta.get("operatingSystem", [])
    if isinstance(os_raw, str):
        os_raw = [os_raw]
    for os in os_raw:
        if "linux" in os.lower():
            return "Linux"
        if "mac" in os.lower():
            return "macOS"
        if "windows" in os.lower():
            return "Windows"
    return "Linux"  # default


# ── Validation ────────────────────────────────────────────────────────────────

def validate(meta):
    lang = get_lang(meta).lower()
    issues = []
    if lang not in ("python", ""):
        issues.append(f"Language '{lang}' is not Python — this tool only supports Python.")
    if not meta.get("softwareRequirements"):
        issues.append("Warning: no softwareRequirements declared in codemeta.json.")
    return issues


# ── Playbook builder ──────────────────────────────────────────────────────────

def indent(text, spaces=4):
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.splitlines())


def build_playbook(meta, deps, datasets, repo):
    name    = meta.get("name", "research-tool")
    version = get_version(meta)
    lang    = get_lang(meta) or "Python"
    desc    = meta.get("description", "")
    safe    = re.sub(r"[^a-z0-9_]", "_", name.lower())
    workdir = f"~/research/{safe}"

    # pip packages — skip runtime-only ones
    skip    = {"jupyter", "ipykernel", "notebook", "jupyterlab"}
    pip_pkgs = [
        f'"{d["name"]}{d["version"]}"'
        for d in deps if d["name"].lower() not in skip
    ]
    pip_str = "\n        - " + "\n        - ".join(pip_pkgs) if pip_pkgs else ""

    # dataset download tasks
    dataset_tasks = ""
    for url in datasets:
        fname = url.split("/")[-1] or "dataset.dat"
        dataset_tasks += f"""
    - name: Download dataset {fname}
      ansible.builtin.get_url:
        url: "{url}"
        dest: "{workdir}/{fname}"
        mode: "0644"
"""

    # repo clone task
    repo_task = ""
    if repo and "github.com" in repo:
        repo_task = f"""
    - name: Clone source repository
      ansible.builtin.git:
        repo: "{repo}"
        dest: "{workdir}/source"
        version: HEAD
        force: yes
"""

    playbook = f"""---
# Ansible playbook auto-generated from codemeta.json
# Tool    : {name}
# Version : {meta.get("version", "—")}
# Language: {lang}
# Desc    : {desc[:80]}{"..." if len(desc) > 80 else ""}
#
# Run with: ansible-playbook playbook.yml
# Requirements: ansible >= 2.9, Python {version}+ on target

- name: Provision research environment for {name}
  hosts: localhost
  connection: local
  gather_facts: yes
  become: no

  vars:
    tool_name: "{name}"
    tool_version: "{meta.get("version", "latest")}"
    python_version: "{version}"
    work_dir: "{workdir}"

  tasks:

    # ── 1. Verify Python version ──────────────────────────────────────────
    - name: Check Python version
      ansible.builtin.command: python3 --version
      register: py_ver
      changed_when: false

    - name: Show Python version
      ansible.builtin.debug:
        msg: "Found {{ py_ver.stdout }} (required: Python {version}+)"

    # ── 2. Create working directory ───────────────────────────────────────
    - name: Create working directory
      ansible.builtin.file:
        path: "{{{{ work_dir }}}}"
        state: directory
        mode: "0755"

    # ── 3. Install pip dependencies ───────────────────────────────────────
    - name: Install declared dependencies from codemeta.json
      ansible.builtin.pip:
        name:{pip_str if pip_str else ' []'}
        state: present
        extra_args: "--upgrade"
      when: {str(bool(pip_pkgs)).lower()}
{repo_task}
    # ── 4. Download datasets ──────────────────────────────────────────────
{dataset_tasks if dataset_tasks else "    # No datasets declared in codemeta.json\n"}
    # ── 5. Copy codemeta.json into working directory ──────────────────────
    - name: Copy codemeta.json to working directory
      ansible.builtin.copy:
        src: codemeta.json
        dest: "{{{{ work_dir }}}}/codemeta.json"
        mode: "0644"

    # ── 6. Copy auto-generated notebook ───────────────────────────────────
    - name: Copy notebook to working directory
      ansible.builtin.copy:
        src: notebook.ipynb
        dest: "{{{{ work_dir }}}}/notebook.ipynb"
        mode: "0644"
      ignore_errors: yes

    # ── 7. Install Jupyter ────────────────────────────────────────────────
    - name: Install Jupyter
      ansible.builtin.pip:
        name:
          - "jupyter"
          - "notebook"
        state: present

    # ── 8. Verify environment ─────────────────────────────────────────────
    - name: Verify installed packages
      ansible.builtin.pip:
        name: {pip_pkgs[0].strip('"') if pip_pkgs else "jupyter"}
        state: present
      register: verify_result
      ignore_errors: yes

    # ── 9. Print summary ──────────────────────────────────────────────────
    - name: Environment summary
      ansible.builtin.debug:
        msg:
          - "============================================"
          - " Environment ready: {{{{ tool_name }}}} {{{{ tool_version }}}}"
          - " Working directory : ~/research/{safe}"
          - " Python version    : {{{{ python_version }}}}"
          - " Dependencies      : {", ".join(d["name"] for d in deps[:5])}"
          - "============================================"
          - " To launch Jupyter:"
          - "   cd {{{{ work_dir }}}}"
          - "   jupyter notebook notebook.ipynb"
          - "============================================"
"""
    return playbook


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    meta     = load_codemeta()
    deps     = get_deps(meta)
    datasets = get_datasets(meta)
    repo     = get_repo(meta)

    # Validate
    issues = validate(meta)
    for issue in issues:
        print(f"  WARNING: {issue}")

    # Generate playbook
    playbook = build_playbook(meta, deps, datasets, repo)
    PLAYBOOK.write_text(playbook)

    name = meta.get("name", "research-tool")
    print(f"  playbook.yml  →  generated for '{name}'")
    print(f"  Dependencies  →  {len(deps)} package(s)")
    if datasets:
        print(f"  Datasets      →  {len(datasets)} URL(s) declared")
    if repo:
        print(f"  Repository    →  {repo}")

    print(f"""
To provision the environment, run:
    ansible-playbook playbook.yml

This will:
  1. Verify Python {get_version(meta)}
  2. Create working directory
  3. Install all declared dependencies
  4. Clone the source repository
  5. Download any declared datasets
  6. Install Jupyter
  7. Print a launch summary
""")


if __name__ == "__main__":
    main()
