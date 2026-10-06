#!/usr/bin/env python3
"""What /bosmang:init needs to know before its first question, in one call and a few lines.

Checks the existing config, which tracker and version-control tools are installed and
signed in, where the current repo is hosted, the running sessions and the ledger, and
prints one line per finding. Only exit codes are read from the sign-in checks, never their
output, so no account detail or token reaches the session.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
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


def tools():
    found = {}
    for tool, auth in TOOLS.items():
        if not shutil.which(tool):
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
    survey = {
        "config": config(),
        "tools": tools(),
        "repo_host": repo_host(),
        "sessions": sessions(),
        "ledger": {"dir": str(ledger.ledger_dir()), "exists": ledger.ledger_dir().exists()},
        "global_settings": {"exists": settings.exists(), "symlink": settings.is_symlink()},
    }
    # one line per finding keeps the call to a few lines in the user's terminal
    for key, value in survey.items():
        print(f"{key}: {json.dumps(value)}")


if __name__ == "__main__":
    main()
