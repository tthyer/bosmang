import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "bosmang" / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


charter = load("charter")
ledger = load("ledger")


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.environ["BOSMANG_LEDGER_DIR"] = self.dir.name

    def tearDown(self):
        del os.environ["BOSMANG_LEDGER_DIR"]
        self.dir.cleanup()

    def run_ledger(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ledger.main(list(argv))
        return out.getvalue()

    def state(self):
        return json.loads(self.run_ledger("list", "--json"))



class LedgerTest(LedgerCase):
    def test_lead_survives_rename_and_closes_by_scope(self):
        self.run_ledger("lead", "open", "--scope", "EPIC-1", "--session", "old-name")
        self.run_ledger("lead", "open", "--scope", "EPIC-1", "--session", "new-name")
        leads = self.state()["leads"]
        self.assertEqual([(l["scope"], l["session"]) for l in leads], [("EPIC-1", "new-name")])

        self.run_ledger("lead", "close", "--scope", "EPIC-1")
        self.assertEqual(self.state()["leads"], [])

    def test_closing_unknown_scope_fails(self):
        with self.assertRaises(SystemExit):
            self.run_ledger("lead", "close", "--scope", "NOPE")

    def test_handoffs_sort_by_due_and_close_by_id(self):
        late = json.loads(self.run_ledger("handoff", "add", "--item", "later", "--from", "a", "--due", "2026-12-01"))
        self.run_ledger("handoff", "add", "--item", "sooner", "--from", "b", "--due", "2026-11-01")
        self.assertEqual([h["item"] for h in self.state()["handoffs"]], ["sooner", "later"])

        self.run_ledger("handoff", "close", late["id"], "--note", "done")
        self.assertEqual([h["item"] for h in self.state()["handoffs"]], ["sooner"])

    def test_history_is_kept(self):
        self.run_ledger("lead", "open", "--scope", "EPIC-1", "--session", "s")
        self.run_ledger("lead", "close", "--scope", "EPIC-1")
        lines = (Path(self.dir.name) / "leads.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(l)["event"] for l in lines], ["open", "close"])

    def test_concurrent_appends_are_not_lost(self):
        cmd = [sys.executable, str(SCRIPTS / "ledger.py"), "handoff", "add", "--from", "x", "--item"]
        procs = [subprocess.Popen(cmd + [f"item-{i}"], stdout=subprocess.DEVNULL) for i in range(20)]
        for p in procs:
            p.wait()
        lines = (Path(self.dir.name) / "handoffs.jsonl").read_text().splitlines()
        self.assertEqual(sorted(json.loads(l)["item"] for l in lines), sorted(f"item-{i}" for i in range(20)))


class SessionHookTest(LedgerCase):
    """The hooks see session_id, cwd and reason. On macOS the temp dir is a symlink
    (/var -> /private/var), which also exercises path resolution."""

    def setUp(self):
        super().setUp()
        # These tests may themselves run inside Claude Code, which exports its own ID.
        self.saved_id = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.worktree = tempfile.TemporaryDirectory()
        (Path(self.worktree.name) / "src").mkdir()

    def tearDown(self):
        if self.saved_id is not None:
            os.environ["CLAUDE_CODE_SESSION_ID"] = self.saved_id
        self.worktree.cleanup()
        super().tearDown()

    def open_lead(self, *extra):
        self.run_ledger("lead", "open", "--scope", "EPIC-1", "--session", "s", "--worktree", self.worktree.name, *extra)

    def hook(self, name, payload):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "ledger.py"), name], input=stdin, capture_output=True, text=True, env=env
        )

    def end(self, session_id, reason="other", cwd=None):
        self.hook("session-end-hook", {"session_id": session_id, "cwd": cwd or self.worktree.name, "reason": reason})

    def lead(self):
        (lead,) = self.state()["leads"]
        return lead

    def test_lead_open_records_the_session_from_the_environment(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "from-env"
        self.open_lead()
        self.assertEqual(self.lead()["session_id"], "from-env")

    def test_own_session_ending_orphans_the_lead_from_any_directory(self):
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="logout", cwd=tempfile.gettempdir())
        self.assertEqual(self.lead()["event"], "ended")
        self.assertIn("ORPHANED", self.run_ledger("list"))

    def test_a_visitor_ending_in_the_worktree_is_ignored(self):
        # A headless `claude -p` run reports reason "other", like an interactive exit.
        self.open_lead("--session-id", "LEAD")
        self.end("VISITOR", cwd=str(Path(self.worktree.name) / "src"))
        self.assertEqual(self.lead()["event"], "open")

    def test_clear_is_ignored(self):
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="clear")
        self.assertEqual(self.lead()["event"], "open")

    def test_resume_takes_an_orphaned_lead_back(self):
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="resume")
        result = self.hook("session-start-hook", {"session_id": "LEAD", "cwd": self.worktree.name, "source": "resume"})
        self.assertEqual(result.stdout, "", "a SessionStart hook's stdout becomes context")
        self.assertEqual(self.lead()["event"], "resumed")
        self.assertNotIn("ORPHANED", self.run_ledger("list"))

    def test_the_session_after_clear_inherits_the_lead(self):
        self.open_lead("--session-id", "OLD")
        self.end("OLD", reason="clear")
        self.hook("session-start-hook", {"session_id": "NEW", "cwd": self.worktree.name, "source": "clear"})
        self.assertEqual(self.lead()["session_id"], "NEW")
        self.end("NEW")
        self.assertEqual(self.lead()["event"], "ended")

    def test_a_lead_without_a_session_id_falls_back_to_its_worktree(self):
        self.open_lead()
        self.end("ANYONE", cwd=str(Path(self.worktree.name) / "src"))
        self.assertEqual(self.lead()["event"], "ended")

    def test_hooks_never_fail(self):
        for name in ("session-start-hook", "session-end-hook"):
            result = self.hook(name, "not json")
            self.assertEqual((result.returncode, result.stdout), (0, ""))


class CharterTest(unittest.TestCase):
    def test_defaults_render_without_config(self):
        text = charter.render({})
        self.assertIn("working for the human", text)
        self.assertIn("| Action |", text)
        self.assertNotIn("$", text.replace("$$", ""))

    def test_config_fills_names_and_appends_local_rules(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as extra:
            extra.write("## Local rules\nUse the tracker.")
        try:
            text = charter.render({"owner": "Ada", "coordinator": "nagata", "append": [extra.name]})
        finally:
            os.unlink(extra.name)
        self.assertIn("working for Ada", text)
        self.assertIn("`nagata`", text)
        self.assertTrue(text.rstrip().endswith("Use the tracker."))

    def test_problems_flags_bad_keys_and_missing_files(self):
        found = charter.problems({"owner": "", "coordinater": "x", "authority_matrix": "/nonexistent.md"})
        self.assertEqual(len(found), 3)
        self.assertEqual(charter.problems({"owner": "Ada", "coordinator": "nagata"}), [])

    def test_check_exit_codes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as cfg:
            cfg.write('{"owner": "Ada", "append": ["/nonexistent.md"]}')
        try:
            run = lambda: subprocess.run(
                [sys.executable, str(SCRIPTS / "charter.py"), "--check"],
                capture_output=True, text=True, env=dict(os.environ, BOSMANG_CONFIG=cfg.name),
            )
            self.assertEqual(run().returncode, 1)
            Path(cfg.name).write_text('{"owner": "Ada"}')
            self.assertEqual(run().returncode, 0)
        finally:
            os.unlink(cfg.name)

    def test_hook_output_is_session_start_json(self):
        env = dict(os.environ, BOSMANG_CONFIG="/nonexistent/config.json")
        out = subprocess.run([sys.executable, str(SCRIPTS / "charter.py")], capture_output=True, text=True, env=env, check=True)
        payload = json.loads(out.stdout)["hookSpecificOutput"]
        self.assertEqual(payload["hookEventName"], "SessionStart")
        self.assertIn("Standing orders", payload["additionalContext"])


if __name__ == "__main__":
    unittest.main()
