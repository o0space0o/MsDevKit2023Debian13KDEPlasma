# Contributing

Read [AGENTS.md](AGENTS.md), [the project map](docs/PROJECT-MAP.md) and
[the validation checklist](docs/VALIDATION.md) first.

Work only on the current prepared workflow. Do not add alternate old firmware
importers, generated Bluetooth addresses, or another device's files as fallbacks.
Public source and public bases must never contain a private target bundle.

Before a pull request, on Linux run:

```sh
python3 -B scripts/check-source.py --shell
python3 -B -m unittest discover -s tests
```

On Windows, parse all PowerShell scripts, then run the synthetic
`tests/windows-launcher-tests.ps1` checks (no elevation or WSL required). When adding a
file, register its component in `config/project-map.json`, regenerate the file
index using `scripts/check-source.py --render-index`, then rerun the checks.
Tests use synthetic fixtures; never include real firmware, registry exports,
hardware IDs, pairing keys, or diagnostic reports in a pull request.

Keep product branding, pinned kernel and proven boot options intact. Report
hardware acceptance separately from QEMU/static checks. Installer changes need
file-backed virtual-disk tests before any real disk test. No unattended real-disk
tests or automatic Windows resizing are permitted by the current workflow.
