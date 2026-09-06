"""Static orchestration boundaries; Windows behavior is tested separately with mocks."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowsWorkflowTests(unittest.TestCase):
    def read(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_root_entry_and_single_guide(self):
        entry = self.read("Start-DevKit2023CustomLinux.cmd")
        self.assertIn('windows\\Start-DevKit2023CustomLinux.ps1', entry)
        ui = self.read("windows/Start-DevKit2023CustomLinux.ps1")
        self.assertIn('Get-Content -LiteralPath (Get-DevKitPaths).Guide', ui)
        self.assertIn('recommended', ui)
        self.assertIn('SETUP.md', self.read("README.md"))

    def test_build_routes_through_one_preparer_with_wsl(self):
        for name in ('Build-DevKit2023CustomLinuxISO', 'Prepare-DevKit2023CustomLinux'):
            with self.subTest(name=name):
                text = self.read('windows/' + name + '.ps1')
                self.assertIn('[switch]$PassThru', text)
        self.assertIn('Prepare-DevKit2023CustomLinux.ps1', self.read('windows/Build-DevKit2023CustomLinuxISO.ps1'))
        self.assertIn('Ensure-DevKitBuilder -Distribution $Distribution', self.read('windows/Prepare-DevKit2023CustomLinux.ps1'))

    def test_reboot_is_explicit_not_scheduled(self):
        setup = self.read('windows/Setup-WSL.ps1')
        self.assertIn('-All -NoRestart', setup)
        self.assertIn('--no-launch --web-download', setup)
        self.assertIn('--web-download --version 2', setup)
        self.assertNotIn('--set-default-version', setup)
        self.assertLess(setup.index('--install --no-distribution'),
                        setup.index('--install --distribution'))
        self.assertIn("'YesNo', 'Warning', 'Button2'", setup)
        common = self.read('windows/DevKit.Common.ps1')
        self.assertIn("$code -eq 3010", common)
        self.assertIn('Start-DevKit2023CustomLinux.cmd again', common)
        for forbidden in ('Restart-Computer', 'shutdown.exe', 'Register-ScheduledTask',
                          'RunOnce', '--unregister'):
            self.assertNotIn(forbidden, setup)

    def test_usb_is_handoff_not_drive_writer(self):
        ui = self.read('windows/Start-DevKit2023CustomLinux.ps1')
        self.assertIn('Get-DevKitPreparedIso -IsoPath', self.read('windows/Prepare-DevKit2023CustomLinux.ps1'))
        self.assertIn("https://rufus.ie/en/", ui)
        for forbidden in ('Clear-Disk', 'Format-Volume', 'diskpart', 'WriteAllBytes',
                          'Invoke-WebRequest', 'Invoke-Expression'):
            self.assertNotIn(forbidden, ui)

    def test_iso_only_publication_and_disposable_native_build(self):
        bootstrap = self.read('scripts/wsl-build-bootstrap.sh')
        self.assertIn('/var/tmp/DevKit2023CustomLinux-build', bootstrap)
        self.assertIn('! -e "$publication"', bootstrap)
        self.assertIn("Iso = Join-Path $source 'ISO'", self.read('windows/DevKit.Common.ps1'))
        self.assertIn('trap cleanup EXIT', bootstrap)
        self.assertIn('--files-from=', bootstrap)
        self.assertIn('export DEVKIT2023_WORK_ROOT="$run"', bootstrap)
        for tool in ('verify-base.py', 'verify-prepared-iso.py', 'verify-installer-startup.py'):
            self.assertIn("os.environ.get('DEVKIT2023_WORK_ROOT', '/var/tmp')", self.read('scripts/' + tool))
        prepare = self.read('windows/Prepare-DevKit2023CustomLinux.ps1')
        self.assertIn('[IO.File]::Replace($partial,$destination,$null)', prepare)
        self.assertIn('Remove-DevKitTemporaryDirectory $scratch', prepare)
        self.assertIn('[switch]$ReplaceExisting', prepare)
        self.assertNotIn('BaseIso', prepare)
        self.assertNotIn('PrivateOutputDirectory', prepare)

    def test_interrupted_cleanup_has_ownership_and_active_build_guards(self):
        cleanup = self.read('windows/Clean-InterruptedBuilds.ps1')
        self.assertIn('$record.User -ne $userSid', cleanup)
        self.assertIn('$record.Source -ne $paths.Source', cleanup)
        self.assertIn('StartTime.ToUniversalTime().Ticks -eq $record.Started', cleanup)
        self.assertIn('flock -n 9', self.read('scripts/clean-workspace.sh'))
        self.assertIn('realpath -m', self.read('scripts/clean-workspace.sh'))
        self.assertIn('umount --', self.read('scripts/clean-workspace.sh'))


if __name__ == '__main__':
    unittest.main()
