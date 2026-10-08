# Contributing

Bug reports and pull requests are welcome. bosmang has been used in only one real setup so far, so reports from other trackers and workflows are especially useful.

- **Run the tests:** `python3 -m unittest discover -s tests`. Python's standard library only; there is nothing to install.
- **Validate the manifests:** `claude plugin validate .` and `claude plugin validate plugins/bosmang --strict`.
- **Watch the budget:** text injected at session start is paid for in every session. Run `python3 plugins/bosmang/scripts/charter.py --check` and keep the injected text under 7,000 characters. How-to detail belongs in skills or the user's procedures, not the orders.
- **Releases:** bump `version` in both `plugins/bosmang/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, add a `CHANGELOG.md` entry, and tag the commit `vX.Y.Z`. Claude Code only updates an installed plugin when the version changes. CI checks that the two versions agree and that the changelog has an entry.
