"""Native launch paths must consume admitted bytes, not changed Home names."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from soulsteads import cli, core
from soulsteads.launch import prepare_launch
from soulsteads.project_adapters.resources import ResourceLaunch


class ProjectResourceBindingTests(unittest.TestCase):
    def setUp(self):
        previous = os.umask(0o077)
        self.addCleanup(os.umask, previous)
        temporary = tempfile.TemporaryDirectory(prefix="resource-binding-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = core.create("binding", "opencode", path=self.root / "home")
        self.project = self.root / "project"
        self.project.mkdir(mode=0o700)

    def test_opencode_instruction_replacement_cannot_change_admitted_content(self):
        source = self.home / ".pi/APPEND_SYSTEM.md"
        expected = source.read_text()
        plan = prepare_launch(self.home, "opencode", self.project)
        self.addCleanup(getattr(plan, "close", lambda: None))
        instruction = Path(
            json.loads(plan["env"]["OPENCODE_CONFIG_CONTENT"])["instructions"][0]
        )
        external = self.root / "external.txt"
        external.write_text("EXTERNAL_CONTEXT_SENTINEL")
        source.unlink()
        source.symlink_to(external)
        self.assertEqual(instruction.read_text(), expected)

    def test_pi_instruction_replacement_cannot_change_admitted_content(self):
        source = self.home / "AGENTS.md"
        expected = source.read_text()
        plan = prepare_launch(self.home, "pi", self.project)
        self.addCleanup(getattr(plan, "close", lambda: None))
        instruction = Path(plan["argv"][4])
        external = self.root / "external.txt"
        external.write_text("EXTERNAL_CONTEXT_SENTINEL")
        source.unlink()
        source.symlink_to(external)
        self.assertEqual(instruction.read_text(), expected)

    def test_cli_dry_run_does_not_materialize_private_resource_copies(self):
        output = StringIO()
        with (
            patch(
                "soulsteads.project_adapters.resources.tempfile.TemporaryDirectory",
                side_effect=AssertionError("dry-run created private copies"),
            ),
            redirect_stdout(output),
        ):
            result = cli.main(
                ["run", str(self.home), "--project", str(self.project), "--dry-run"]
            )
        self.assertEqual(result, 0)
        preview = json.loads(output.getvalue())
        self.assertTrue(preview["preview"])
        self.assertNotIn("argv", preview)
        self.assertNotIn("env", preview)

    def _skill(self):
        skill = self.home / "skills" / "binding-skill"
        (skill / "scripts").mkdir(mode=0o700, parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: binding-skill\ndescription: fixture\n---\nSKILL_CANARY\n"
        )
        asset = skill / "scripts" / "run.py"
        asset.write_text("ASSET_CANARY\n")
        asset.chmod(0o700)
        return skill

    def test_inventory_and_total_byte_limits_are_enforced(self):
        self._skill()
        for target in (
            "soulsteads.project_adapters.resources.MAX_ENTRIES",
            "soulsteads.hermes_import.MAX_TOTAL",
        ):
            with (
                self.subTest(limit=target),
                patch(target, 1),
                self.assertRaises((core.HomeError, ValueError)),
            ):
                prepare_launch(self.home, "opencode", self.project)

    def test_source_change_at_final_admission_is_refused(self):
        from soulsteads.hermes_import import Snapshot

        skill = self._skill()
        verify = Snapshot.verify

        def changed(snapshot):
            (skill / "scripts/run.py").write_text("CHANGED_BEFORE_HANDOFF")
            verify(snapshot)

        with (
            patch.object(Snapshot, "verify", changed),
            self.assertRaises((core.HomeError, ValueError)),
        ):
            prepare_launch(self.home, "opencode", self.project)

    def test_temp_storage_inside_home_is_refused_before_creation(self):
        original = tempfile.TemporaryDirectory
        with (
            patch.object(tempfile, "tempdir", str(self.home)),
            patch(
                "soulsteads.project_adapters.resources.tempfile.TemporaryDirectory",
                wraps=original,
            ) as create,
            self.assertRaisesRegex(core.HomeError, "outside Home and project"),
        ):
            prepare_launch(self.home, "opencode", self.project)
        create.assert_not_called()

    def test_deep_skill_tree_is_rejected_with_a_bounded_error(self):
        skill = self._skill()
        path = skill
        for _ in range(34):
            path = path / "d"
            path.mkdir(mode=0o700)
        with self.assertRaisesRegex(core.HomeError, "depth limit"):
            plan = prepare_launch(self.home, "opencode", self.project)
            if isinstance(plan, ResourceLaunch):
                self.addCleanup(plan.close)

    def test_writable_skill_asset_is_rejected(self):
        skill = self._skill()
        (skill / "scripts/run.py").chmod(0o666)
        with self.assertRaises((core.HomeError, ValueError)):
            prepare_launch(self.home, "opencode", self.project)

    def test_instruction_skill_and_relative_asset_swaps_do_not_change_snapshot(self):
        self._skill()
        for runtime in ("opencode", "pi"):
            for relative in (
                ".pi/APPEND_SYSTEM.md",
                "AGENTS.md",
                "skills/binding-skill/SKILL.md",
                "skills/binding-skill/scripts/run.py",
                "skills",
            ):
                with self.subTest(runtime=runtime, resource=relative):
                    plan = prepare_launch(self.home, runtime, self.project)
                    assert isinstance(plan, ResourceLaunch)
                    with plan:
                        first = (
                            json.loads(plan["env"]["OPENCODE_CONFIG_CONTENT"])[
                                "instructions"
                            ][0]
                            if runtime == "opencode"
                            else plan["argv"][2]
                        )
                        root = Path(first).parents[1]
                        before = {
                            p.relative_to(root): p.read_bytes()
                            for p in root.rglob("*")
                            if p.is_file()
                        }
                        source = self.home / relative
                        saved = source.with_name(source.name + "-saved")
                        source.rename(saved)
                        external = self.root / "outside"
                        if saved.is_dir():
                            external.mkdir(exist_ok=True)
                        else:
                            external.write_text("EXTERNAL_CONTEXT_SENTINEL")
                        source.symlink_to(external, target_is_directory=saved.is_dir())
                        try:
                            self.assertFalse(root.is_relative_to(self.home))
                            self.assertFalse(root.is_relative_to(self.project))
                            self.assertEqual(
                                {
                                    p.relative_to(root): p.read_bytes()
                                    for p in root.rglob("*")
                                    if p.is_file()
                                },
                                before,
                            )
                        finally:
                            source.unlink()
                            saved.rename(source)
                            if external.is_dir():
                                external.rmdir()
                            else:
                                external.unlink()
                    self.assertFalse(root.exists())

    def test_unsafe_relative_assets_refuse_and_remove_partial_copies(self):
        skill = self._skill()
        asset = skill / "scripts/run.py"
        for kind in ("symlink", "hardlink", "fifo", "oversize"):
            with self.subTest(kind=kind):
                asset.unlink()
                external = self.root / "outside"
                external.write_text("EXTERNAL_CONTEXT_SENTINEL")
                if kind == "symlink":
                    asset.symlink_to(external)
                elif kind == "hardlink":
                    os.link(external, asset)
                elif kind == "fifo":
                    os.mkfifo(asset)
                else:
                    asset.write_bytes(b"x" * (1024 * 1024 + 1))
                roots = []
                original = tempfile.TemporaryDirectory

                def temporary(*args, original=original, roots=roots, **kwargs):
                    owner = original(*args, **kwargs)
                    roots.append(Path(owner.name))
                    return owner

                with (
                    patch(
                        "soulsteads.project_adapters.resources.tempfile.TemporaryDirectory",
                        side_effect=temporary,
                    ),
                    self.assertRaises((core.HomeError, ValueError)),
                ):
                    prepare_launch(self.home, "opencode", self.project)
                self.assertTrue(all(not root.exists() for root in roots))
                self.assertEqual(external.read_text(), "EXTERNAL_CONTEXT_SENTINEL")

    def test_cli_child_consumes_snapshot_and_cleanup_survives_nonzero_and_spawn_failure(
        self,
    ):
        self._skill()
        original_run = subprocess.run
        for failure in (False, True):
            with self.subTest(spawn_failure=failure):
                retained = []

                def capture(*args, retained=retained, **kwargs):
                    plan = prepare_launch(*args, **kwargs)
                    assert isinstance(plan, ResourceLaunch)
                    retained.append(plan)
                    self.addCleanup(plan.close)
                    return plan

                def child(argv, failure=failure, **kwargs):
                    if argv[0] != "opencode":
                        return original_run(argv, **kwargs)
                    overlay = json.loads(kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
                    root = Path(overlay["instructions"][0]).parents[1]
                    self.assertTrue(root.exists())
                    if failure:
                        raise OSError("synthetic spawn failure")
                    source = self.home / "skills/binding-skill/scripts/run.py"
                    source.write_text("CHANGED_SOURCE_NOT_ADMITTED")
                    code = (
                        "import os,json,pathlib; c=json.loads(os.environ['OPENCODE_CONFIG_CONTENT']); r=pathlib.Path(c['skills'][0]); assert (r/'binding-skill/scripts/run.py').read_text()=="
                        + repr("ASSET_CANARY\n")
                        + "; raise SystemExit(7)"
                    )
                    return original_run([sys.executable, "-c", code], **kwargs)

                with (
                    patch("soulsteads.launch.prepare_launch", side_effect=capture),
                    patch("soulsteads.cli.subprocess.run", side_effect=child),
                    redirect_stderr(StringIO()),
                ):
                    self.assertEqual(
                        cli.main(
                            ["run", str(self.home), "--project", str(self.project)]
                        ),
                        1 if failure else 7,
                    )
                self.assertEqual(len(retained), 1)
                root = Path(
                    json.loads(retained[0]["env"]["OPENCODE_CONFIG_CONTENT"])["skills"][
                        0
                    ]
                ).parent
                self.assertFalse(root.exists())
                (self.home / "skills/binding-skill/scripts/run.py").write_text(
                    "ASSET_CANARY\n"
                )
