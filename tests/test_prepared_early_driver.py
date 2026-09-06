"""Exercise the production loader function with stubbed modprobe/sysfs, no hardware."""
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
EARLY = ROOT / 'profiles/prepared/overlay/etc/initramfs-tools/scripts/init-premount/devkit2023customlinux-prepared'


class EarlyDriverTests(unittest.TestCase):
    def run_loader(self, present=0, command_status=0):
        text = EARLY.read_text()
        function = re.search(r'^activate_driver\(\) \{\n.*?^\}', text, re.M | re.S)
        self.assertIsNotNone(function)
        # Redirect only the console to this test's stdout. test() handles the
        # production sysfs postcondition without consulting the host's /sys.
        body = function.group().replace('>/dev/console', '>&1')
        harness = r'''
fail() { printf 'FAIL:%s\n' "$*"; exit 71; }
modprobe() { printf 'OPTIONS:%s\nMODULE:%s\n' "$MODPROBE_OPTIONS" "$1"; return "$COMMAND_STATUS"; }
test() {
    if [ "$1" = -d ]; then
        case "$2" in /sys/module/*) return "$PRESENT" ;; esac
    fi
    command test "$@"
}
'''
        environment = dict(os.environ, MODPROBE_OPTIONS='-qb', PRESENT=str(present), COMMAND_STATUS=str(command_status))
        return subprocess.run(['sh', '-c', harness + body + '\nactivate_driver msm\nprintf "PARENT:%s\\n" "$MODPROBE_OPTIONS"\n'], env=environment, capture_output=True, text=True)

    def test_named_load_clears_inherited_blacklist_only_for_load(self):
        result = self.run_loader()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('OPTIONS:\nMODULE:msm\n', result.stdout)
        self.assertIn('PARENT:-qb\n', result.stdout)

    def test_successful_noop_without_sysfs_module_fails(self):
        result = self.run_loader(present=1)
        self.assertEqual(result.returncode, 71)
        self.assertIn('absent after the load command', result.stdout)
        self.assertNotIn('PARENT:', result.stdout)

    def test_failed_module_command_fails_before_success(self):
        result = self.run_loader(command_status=1)
        self.assertEqual(result.returncode, 71)
        self.assertIn('required driver msm failed to load', result.stdout)

    def test_target_and_firmware_checks_precede_driver_loop(self):
        text = EARLY.read_text()
        loop = text.index('for module in msm qcom_q6v5_pas snd_soc_sc8280xp; do')
        self.assertLess(text.index('test "$token" ='), loop)
        self.assertLess(text.index('sha256sum -c '), loop)
        self.assertIn('    activate_driver "$module"\n', text[loop:])


if __name__ == '__main__': unittest.main()
