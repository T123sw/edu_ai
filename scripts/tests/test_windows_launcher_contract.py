from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WindowsLauncherContractTests(unittest.TestCase):
    def test_required_launchers_exist(self) -> None:
        for relative in (
            "start.bat",
            "stop.bat",
            "scripts/start-dev.ps1",
            "scripts/stop-dev.ps1",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_batch_files_delegate_to_powershell_controllers(self) -> None:
        start = (ROOT / "start.bat").read_text(encoding="utf-8").lower()
        stop = (ROOT / "stop.bat").read_text(encoding="utf-8").lower()

        self.assertIn("scripts\\start-dev.ps1", start)
        self.assertIn('"--check"', start)
        self.assertIn("-check", start)
        self.assertIn("scripts\\stop-dev.ps1", stop)

    def test_launcher_uses_canonical_services_and_ports(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8")
        for token in (
            "frontend",
            "backend/src",
            "openmaic-sidecar",
            "5173",
            "8001",
            "3000",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn("HTML2PPT", source)
        self.assertNotIn("EduAgent", source)

    def test_startup_never_kills_unknown_port_owners(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8").lower()
        self.assertNotIn("taskkill", source)
        self.assertNotIn("stop-process", source)
        self.assertIn("get-nettcpconnection", source)

    def test_dotenv_parser_splits_on_the_first_equals_sign(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8")
        self.assertIn("$separator = $trimmed.IndexOf('=')", source)
        self.assertNotIn(".Split(@('='), 2)", source)

    def test_pnpm_dev_arguments_do_not_include_a_literal_separator(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8")
        self.assertNotIn("pnpm dev -- --", source)

    def test_openmaic_uses_windows_compatible_webpack_dev_server(self) -> None:
        source = (ROOT / "scripts/start-dev.ps1").read_text(encoding="utf-8")
        self.assertIn("pnpm dev --webpack --hostname 127.0.0.1 --port 3000", source)

    def test_stop_requires_owned_pid_manifest(self) -> None:
        source = (ROOT / "scripts/stop-dev.ps1").read_text(encoding="utf-8")
        self.assertIn("dev-processes.json", source)
        self.assertIn("Win32_Process", source)
        self.assertIn("CommandLine", source)
        self.assertIn("taskkill.exe", source)

    def test_runtime_state_is_ignored(self) -> None:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".runtime/probe"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)


if __name__ == "__main__":
    unittest.main()
