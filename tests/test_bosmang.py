import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "bosmang" / "scripts"
# charter.py writes launchers on every run; keep the tests' out of the user's own.
BIN = tempfile.TemporaryDirectory()
os.environ["BOSMANG_BIN_DIR"] = BIN.name


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

    def test_handoff_ids_never_repeat(self):
        first = json.loads(self.run_ledger("handoff", "add", "--item", "same", "--from", "a"))
        with mock.patch.object(ledger.secrets, "token_hex", side_effect=[first["id"], "beef01"]):
            second = json.loads(self.run_ledger("handoff", "add", "--item", "same", "--from", "b"))
        self.assertEqual(second["id"], "beef01")
        self.assertEqual(len(self.state()["handoffs"]), 2)

    def test_changes_wait_for_the_write_lock(self):
        added = json.loads(self.run_ledger("handoff", "add", "--item", "x", "--from", "a"))
        with ledger.exclusive():
            close = subprocess.Popen([sys.executable, str(SCRIPTS / "ledger.py"), "handoff", "close", added["id"]],
                                     stdout=subprocess.DEVNULL)
            with self.assertRaises(subprocess.TimeoutExpired):
                close.wait(timeout=0.5)
        self.assertEqual(close.wait(timeout=5), 0)
        self.assertEqual(self.state()["handoffs"], [])

    def test_questions_wait_on_the_owner_until_answered(self):
        q = json.loads(self.run_ledger("question", "add", "--scope", "EPIC-1", "--text", "Push the branch?"))
        self.assertIn(f"{q['id']}  EPIC-1  Push the branch?", self.run_ledger("list"))
        self.run_ledger("question", "answer", q["id"], "--answer", "yes")
        self.assertEqual(self.state()["questions"], [])
        with self.assertRaises(SystemExit):
            self.run_ledger("question", "answer", q["id"], "--answer", "again")

    def test_notices_are_injected_at_session_start_until_closed(self):
        n = json.loads(self.run_ledger("notice", "add", "--text", "Never shallow-fetch.", "--from", "nagata"))
        parts = charter.render_parts({"owner": "Ada"})
        self.assertIn("- Never shallow-fetch. (", parts["notices"])
        self.assertIn("nothing Ada tells you directly", parts["notices"])
        self.run_ledger("notice", "close", n["id"])
        self.assertEqual(charter.render_parts({})["notices"], "")

    def test_handoff_update_keeps_its_id(self):
        added = json.loads(self.run_ledger("handoff", "add", "--item", "draft", "--from", "a"))
        self.run_ledger("handoff", "update", added["id"], "--item", "revised", "--due", "2026-11-01", "--note", "scope grew")
        [handoff] = self.state()["handoffs"]
        self.assertEqual((handoff["id"], handoff["item"], handoff["due"], handoff["from"]), (added["id"], "revised", "2026-11-01", "a"))
        self.run_ledger("handoff", "close", added["id"])
        self.assertEqual(self.state()["handoffs"], [])

    def test_handoff_update_refuses_unknown_closed_or_empty(self):
        added = json.loads(self.run_ledger("handoff", "add", "--item", "x", "--from", "a"))
        with self.assertRaises(SystemExit):
            self.run_ledger("handoff", "update", added["id"])
        self.run_ledger("handoff", "close", added["id"])
        with self.assertRaises(SystemExit):
            self.run_ledger("handoff", "update", added["id"], "--item", "y")

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

    def test_the_latest_coordinator_wins(self):
        self.assertIsNone(self.state()["coordinator"])
        self.run_ledger("coordinator", "set", "--name", "old", "--session-id", "aaaa", "--cwd", self.dir.name)
        self.run_ledger("coordinator", "set", "--name", "new", "--session-id", "bbbb", "--cwd", self.dir.name)
        coord = self.state()["coordinator"]
        self.assertEqual((coord["name"], coord["session_id"]), ("new", "bbbb"))
        self.assertIn("Coordinator: new  session bbbb", self.run_ledger("list"))

    def test_coordinator_needs_a_session_id(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            with self.assertRaises(SystemExit):
                self.run_ledger("coordinator", "set", "--name", "c")


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

    def test_clear_does_not_orphan_the_lead(self):
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="clear")
        self.assertEqual(self.lead()["event"], "cleared")
        self.assertNotIn("ORPHANED", self.run_ledger("list"))

    def test_a_visitor_clearing_in_the_worktree_does_not_take_a_live_lead(self):
        self.open_lead("--session-id", "LEAD")
        self.end("VISITOR", reason="clear")
        self.hook("session-start-hook", {"session_id": "VISITOR-2", "cwd": self.worktree.name, "source": "clear"})
        self.assertEqual((self.lead()["event"], self.lead()["session_id"]), ("open", "LEAD"))

    def test_resume_takes_an_orphaned_lead_back(self):
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="resume")
        result = self.hook("session-start-hook", {"session_id": "LEAD", "cwd": self.worktree.name, "source": "resume"})
        self.assertEqual(result.stdout, "", "a SessionStart hook's stdout becomes context")
        self.assertEqual(self.lead()["event"], "resumed")
        self.assertNotIn("ORPHANED", self.run_ledger("list"))

    def test_resume_from_another_directory_takes_the_lead_back(self):
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="prompt_input_exit")
        self.hook("session-start-hook", {"session_id": "LEAD", "cwd": tempfile.gettempdir(), "source": "resume"})
        self.assertEqual(self.lead()["event"], "resumed")

    def test_another_session_in_the_worktree_does_not_take_an_orphaned_lead(self):
        # Seen in real use: a visitor took the orphaned lead, then its exit orphaned it
        # again while the lead's own session was running elsewhere.
        self.open_lead("--session-id", "LEAD")
        self.end("LEAD", reason="prompt_input_exit")
        self.hook("session-start-hook", {"session_id": "VISITOR", "cwd": self.worktree.name, "source": "startup"})
        self.assertEqual((self.lead()["event"], self.lead()["session_id"]), ("ended", "LEAD"))
        self.hook("session-start-hook", {"session_id": "LEAD", "cwd": tempfile.gettempdir(), "source": "resume"})
        self.end("VISITOR")
        self.assertEqual(self.lead()["event"], "resumed")

    def test_an_orphaned_lead_without_a_session_id_goes_to_its_worktree(self):
        self.open_lead()
        self.end("ANYONE")
        self.hook("session-start-hook", {"session_id": "NEXT", "cwd": self.worktree.name, "source": "startup"})
        self.assertEqual(self.lead()["event"], "resumed")

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
    def fake_plugin(self, root, version):
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
        (root / "scripts").mkdir()
        for name in ("ledger", "charter"):
            (root / "scripts" / f"{name}.py").write_text("")
            (Path(BIN.name) / name).write_text(f'#!/bin/sh\nexec python3 {root / "scripts" / f"{name}.py"} "$@"\n')

    def test_launchers_never_move_back_to_an_older_copy(self):
        with tempfile.TemporaryDirectory() as d:
            self.fake_plugin(Path(d), "99.0.0")
            ledger.write_launchers()
            self.assertEqual(ledger.launcher_target(Path(BIN.name) / "ledger"), Path(d))
        with tempfile.TemporaryDirectory() as d:
            self.fake_plugin(Path(d), "0.0.1")
            ledger.write_launchers()
            self.assertEqual(ledger.launcher_target(Path(BIN.name) / "ledger"), SCRIPTS.parent)

    def test_any_ledger_run_writes_the_launchers(self):
        # /reload-plugins fires no SessionStart hook, so the launchers can't wait for one.
        for name in ("ledger", "charter"):
            (Path(BIN.name) / name).unlink(missing_ok=True)
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(SCRIPTS / "ledger.py"), "list"], capture_output=True,
                           env=dict(os.environ, BOSMANG_LEDGER_DIR=d))
        self.assertEqual(ledger.launcher_target(Path(BIN.name) / "charter"), SCRIPTS.parent)

    def test_launchers_run_this_copy_of_the_scripts(self):
        ledger.write_launchers()
        run = subprocess.run([str(Path(BIN.name) / "ledger"), "--help"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("handoff", run.stdout)
        self.assertIn(str(SCRIPTS / "charter.py"), (Path(BIN.name) / "charter").read_text())

    def test_defaults_render_without_config(self):
        text = charter.render({})
        self.assertIn("working for the human", text)
        self.assertIn("| Action |", text)
        self.assertIn("[REQUEST]", text)
        self.assertIn("## Messages", text)
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
        self.assertIn(f"`{BIN.name}/charter --install <draft>`", text)
        self.assertIn(f"`{BIN.name}/ledger list`", text)
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

    def install(self, draft, home):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "charter.py"), "--install", str(draft)],
            capture_output=True, text=True, env=dict(os.environ, BOSMANG_CONFIG=str(home / "config.json")),
        )

    def test_install_moves_a_valid_draft_into_place_and_backs_up(self):
        with tempfile.TemporaryDirectory() as d:
            draft, home = Path(d, "draft"), Path(d, "home")
            draft.mkdir()
            home.mkdir()
            (draft / "local-rules.md").write_text("- new rule")
            (draft / "config.json").write_text(json.dumps({"owner": "Ada", "append": [str(home / "local-rules.md")]}))
            (home / "local-rules.md").write_text("- old rule")
            # a symlinked file is written through, never replaced by a plain file
            real = Path(d, "dotfiles-config.json")
            real.write_text("{}")
            (home / "config.json").symlink_to(real)

            run = self.install(draft, home)
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertEqual((home / "local-rules.md").read_text(), "- new rule")
            self.assertTrue((home / "config.json").is_symlink())
            self.assertEqual(json.loads(real.read_text())["owner"], "Ada")
            backups = list(home.glob("backup-*/local-rules.md"))
            self.assertEqual([b.read_text() for b in backups], ["- old rule"])

    def test_install_writes_each_file_to_its_configured_path(self):
        with tempfile.TemporaryDirectory() as d:
            draft, home, notes = Path(d, "draft"), Path(d, "home"), Path(d, "notes")
            draft.mkdir()
            notes.mkdir()
            (notes / "local-rules.md").write_text("- old rule")
            (draft / "local-rules.md").write_text("- new rule")
            (draft / "config.json").write_text(json.dumps({"append": [str(notes / "local-rules.md")]}))
            config = home / "crew.json"  # a custom $BOSMANG_CONFIG name
            run = subprocess.run([sys.executable, str(SCRIPTS / "charter.py"), "--install", str(draft)],
                                 capture_output=True, text=True, env=dict(os.environ, BOSMANG_CONFIG=str(config)))
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertEqual((notes / "local-rules.md").read_text(), "- new rule")
            self.assertEqual(json.loads(config.read_text())["append"], [str(notes / "local-rules.md")])
            self.assertEqual(sorted(f.name for f in home.iterdir() if f.is_file()), ["crew.json"])

    def test_install_refuses_a_file_the_config_does_not_name(self):
        with tempfile.TemporaryDirectory() as d:
            draft, home = Path(d, "draft"), Path(d, "home")
            draft.mkdir()
            (draft / "stray.md").write_text("- unused")
            (draft / "config.json").write_text(json.dumps({"owner": "Ada"}))
            run = self.install(draft, home)
            self.assertEqual(run.returncode, 1)
            self.assertIn("stray.md", run.stdout)
            self.assertFalse(home.exists())

    def test_draft_preview_shows_the_draft_not_the_installed_rules(self):
        with tempfile.TemporaryDirectory() as d:
            draft, home = Path(d, "draft"), Path(d, "home")
            draft.mkdir()
            (draft / "local-rules.md").write_text("- DRAFTED-RULE")
            (draft / "config.json").write_text(json.dumps({"owner": "Ada", "append": [str(home / "local-rules.md")]}))
            run = subprocess.run([sys.executable, str(SCRIPTS / "charter.py"), "--draft", str(draft)],
                                 capture_output=True, text=True, env=dict(os.environ, BOSMANG_CONFIG=str(home / "config.json")))
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("DRAFTED-RULE", run.stdout)
            self.assertIn("working for Ada", run.stdout)

    def test_install_refuses_an_invalid_draft(self):
        with tempfile.TemporaryDirectory() as d:
            draft, home = Path(d, "draft"), Path(d, "home")
            draft.mkdir()
            (draft / "config.json").write_text(json.dumps({"owner": "Ada", "append": [str(home / "missing.md")]}))
            run = self.install(draft, home)
            self.assertEqual(run.returncode, 1)
            self.assertIn("not installed", run.stdout)
            self.assertFalse(home.exists())

    def test_survey_reports_sign_in_by_exit_code_only(self):
        with tempfile.TemporaryDirectory() as d:
            bin_dir = Path(d)
            # a fake gh whose status output carries a secret-looking line, signed in
            (bin_dir / "gh").write_text(
                "#!/bin/sh\n"
                'case "$1 $2" in\n'
                "  'auth status') echo 'Token: gho_SECRET'; exit 0;;\n"
                "  'api user') echo octo;;\n"
                "  'search prs') echo '[{\"repository\":{\"nameWithOwner\":\"o/a\"}},"
                "{\"repository\":{\"nameWithOwner\":\"o/b\"}},{\"repository\":{\"nameWithOwner\":\"o/a\"}}]';;\n"
                "esac\n"
            )
            (bin_dir / "acli").write_text("#!/bin/sh\nexit 1\n")
            for f in bin_dir.iterdir():
                f.chmod(0o755)
            run = subprocess.run(
                [sys.executable, str(SCRIPTS / "survey.py")], capture_output=True, text=True, cwd=d,
                env=dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin", BOSMANG_CONFIG=str(bin_dir / "none.json"),
                         BOSMANG_LEDGER_DIR=str(bin_dir / "ledger")),
            )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("SECRET", run.stdout)
        tools = json.loads(next(l for l in run.stdout.splitlines() if l.startswith("tools: "))[7:])
        self.assertEqual(tools["gh"], "signed in")
        self.assertEqual(tools["acli"], "installed, not signed in")
        lines = dict(l.split(": ", 1) for l in run.stdout.splitlines())
        self.assertEqual(json.loads(lines["forge_user"]), {"github": "octo"})
        self.assertEqual(json.loads(lines["merged_pr_repos_last_90_days"]), ["o/a (2)", "o/b (1)"])

    def test_an_oversized_part_becomes_a_pointer_not_a_preview(self):
        self.assertEqual(charter.hook_text("local", "short"), "short")
        text = charter.hook_text("local", "x" * charter.HOOK_LIMIT)
        self.assertLess(len(text), 1000)
        self.assertIn("--print --part local", text)
        self.assertEqual(charter.hook_text("local", ""), "")

    def test_problems_flags_an_oversized_part(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as big:
            big.write("x" * charter.HOOK_LIMIT)
        try:
            found = charter.problems({"append": [big.name]})
        finally:
            os.unlink(big.name)
        self.assertTrue(any("local part" in p for p in found), found)

    def test_procedures_are_printed_on_demand_and_never_injected(self):
        with tempfile.TemporaryDirectory() as d:
            proc = Path(d, "procedures.md"); proc.write_text("## Closing steps\nPROCEDURE-MARKER")
            cfg = Path(d, "config.json"); cfg.write_text(json.dumps({"procedures": [str(proc)]}))
            env = dict(os.environ, BOSMANG_CONFIG=str(cfg))
            run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "charter.py"), *a], capture_output=True, text=True, env=env, check=True).stdout
            self.assertIn("PROCEDURE-MARKER", run("--procedures"))
            self.assertNotIn("PROCEDURE-MARKER", run("--part", "orders") + run("--part", "local") + run("--print"))

    def test_the_owner_never_starts_a_sentence(self):
        # The default owner is "the human", which reads wrong at the start of a sentence.
        import re
        self.assertIsNone(re.search(r"(^|[.!?]\s+|^- |\| )the human", charter.render({}), re.M))

    def test_default_orders_fit_the_injected_budget(self):
        self.assertLess(len(charter.render({})), charter.INJECTED_BUDGET)

    def test_empty_local_part_emits_nothing(self):
        env = dict(os.environ, BOSMANG_CONFIG="/nonexistent/config.json")
        out = subprocess.run([sys.executable, str(SCRIPTS / "charter.py"), "--part", "local"], capture_output=True, text=True, env=env, check=True)
        self.assertEqual(out.stdout, "")

    def test_hook_output_is_session_start_json(self):
        env = dict(os.environ, BOSMANG_CONFIG="/nonexistent/config.json")
        out = subprocess.run([sys.executable, str(SCRIPTS / "charter.py")], capture_output=True, text=True, env=env, check=True)
        payload = json.loads(out.stdout)["hookSpecificOutput"]
        self.assertEqual(payload["hookEventName"], "SessionStart")
        self.assertIn("Standing orders", payload["additionalContext"])


if __name__ == "__main__":
    unittest.main()
