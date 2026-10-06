#!/usr/bin/env python3
"""What /bosmang:init needs to know before its first question, in one call and a few lines.

Checks the existing config, which tracker and version-control tools are installed and
signed in, whether git has an identity to commit with, where the current repo is hosted,
the user's forge handle and the repos they've recently merged PRs into, the running
sessions and the ledger, and prints one line per finding. A fresh machine shows up as
missing tools and no identity, which init then offers to fix.

Sign-in checks read only exit codes, never output, so no account detail or token reaches
the session. Of git's identity, only whether it is set is reported.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# tool -> command that exits 0 only when it is signed in
TOOLS = {
    "acli": ["acli", "jira", "auth", "status"],
    "gh": ["gh", "auth", "status"],
    "glab": ["glab", "auth", "status"],
    "linear": None,
    "git": None,
    "wt": None,
}


def run(cmd, timeout=10):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return done.returncode, done.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


# reported even when missing, since a fresh machine needs them before anything else
ESSENTIAL = {"git", "gh"}
PACKAGE_MANAGERS = ("brew", "apt-get", "dnf", "pacman", "winget")
RECENT_DAYS = 90


def tools():
    found = {}
    for tool, auth in TOOLS.items():
        if not shutil.which(tool):
            if tool in ESSENTIAL:
                found[tool] = "missing"
            continue
        if auth is None:
            found[tool] = "installed"
        else:
            code, _ = run(auth)
            found[tool] = "signed in" if code == 0 else "installed, not signed in"
    return found


def repo_host():
    code, url = run(["git", "remote", "get-url", "origin"])
    if code != 0 or not url:
        return None
    # git@github.com:org/repo.git or https://github.com/org/repo
    host = url.split("@", 1)[-1].split("://", 1)[-1]
    return host.split(":", 1)[0].split("/", 1)[0]


def git_identity():
    return {key: run(["git", "config", "--global", "--get", f"user.{key}"])[0] == 0 for key in ("name", "email")}


def forge_user(found):
    """The signed-in handle, so it never has to be typed (and mistyped). None if not signed in."""
    if found.get("gh") == "signed in":
        code, out = run(["gh", "api", "user", "--jq", ".login"])
        return {"github": out} if code == 0 and out else None
    if found.get("glab") == "signed in":
        code, out = run(["glab", "api", "user"])
        try:
            return {"gitlab": json.loads(out)["username"]} if code == 0 else None
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def recent_repos(found):
    """Repos the user merged PRs into lately, most first: the candidates for which repos they work in."""
    if found.get("gh") != "signed in":
        return None
    since = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    code, out = run(["gh", "search", "prs", "--author", "@me", "--merged", "--merged-at", f">{since}",
                     "--limit", "100", "--json", "repository"], timeout=30)
    try:
        repos = Counter(pr["repository"]["nameWithOwner"] for pr in json.loads(out)) if code == 0 else None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return [f"{repo} ({n})" for repo, n in repos.most_common(8)] if repos is not None else None


def sessions():
    code, out = run(["claude", "agents", "--json"], timeout=20)
    if code != 0:
        return None
    try:
        return [f"{s.get('name') or s.get('id')} ({s.get('kind')}, {s.get('status')}) in {s.get('cwd')}" for s in json.loads(out)]
    except json.JSONDecodeError:
        return None


def config():
    charter = load("charter")
    path = charter.config_path()
    if not path.exists():
        return {"path": str(path), "exists": False}
    try:
        cfg = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"path": str(path), "exists": True, "problems": [f"not valid JSON: {e}"]}
    return {
        "path": str(path),
        "exists": True,
        "symlink": str(path.resolve()) if path.is_symlink() else None,
        "config": cfg,
        "problems": charter.problems(cfg),
    }


def main():
    ledger = load("ledger")
    settings = Path.home() / ".claude" / "settings.json"
    found = tools()
    survey = {
        "config": config(),
        "tools": found,
        "package_manager": next((pm for pm in PACKAGE_MANAGERS if shutil.which(pm)), None),
        "git_identity_set": git_identity() if found.get("git") != "missing" else None,
        "repo_host": repo_host(),
        "forge_user": forge_user(found),
        f"merged_pr_repos_last_{RECENT_DAYS}_days": recent_repos(found),
        "sessions": sessions(),
        "ledger": {"dir": str(ledger.ledger_dir()), "exists": ledger.ledger_dir().exists()},
        "global_settings": {"exists": settings.exists(), "symlink": settings.is_symlink()},
    }
    # one line per finding keeps the call to a few lines in the user's terminal
    for key, value in survey.items():
        print(f"{key}: {json.dumps(value)}")


if __name__ == "__main__":
    main()
