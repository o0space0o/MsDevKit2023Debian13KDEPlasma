# Working on DevKit2023CustomLinux

Read README.md, SETUP.md, BUILD-STATUS.md, docs/PROJECT-MAP.md and
docs/PREPARATION.md first. They are the handoff; conversation history is not needed.

## Boundaries

- Keep DevKit2023CustomLinux branding, minimal Debian ARM64 and the pinned kernel.
- Never put target firmware, registry hives, hardware IDs, pairing keys,
  credentials, screenshots or logs in public source or the target-free base.
- Private preparation always uses an explicitly selected target. No builder
  default, cached-other-device input or generated Bluetooth address.
- Keep catalog signature/member checks, target binding, GPT/mount and EFI checks.
- Keep clk_ignore_unused and pd_ignore_unused without contrary hardware evidence.
- efi=noruntime is not an installation default; EFI entries need runtime services.
- Automated tests must never modify physical Windows partitions or host EFI.
- Do not infer all-driver, pairing or dual-boot success from static/QEMU results.

## Organization and outputs

- This root is the only public source project. ISO/ is the only normal output
  folder and is excluded from Git, source inventory and source mirrors.
- Preserve the current working ISO unless the owner confirms replacement.
  A new completed image is published only after verification; no history remains.
- Build intermediates belong to newly allocated Windows/native temporary runs.
  Finally/EXIT cleanup must remove only validated owned paths, including failures.
- No persistent Data folder, implicit base reuse or retained build caches.
  WSL and installed build prerequisites remain; do not remove unrelated OS state.
- An explicitly selected external export bundle is user-owned, not disposable.
- Keep one Windows preparation workflow and windows-free-space-v1 installation.
  Never restore boot-time Windows import/cache or generic erase/resize jobs.

## Discoverability and evidence

1. Find ownership in config/project-map.json and docs/FILE-INDEX.md.
2. Change the smallest coherent component and update its regression test source.
3. Register added/removed files and render the explicit file index.
4. Perform source/privacy/link/syntax checks after edits. Do not claim tests ran
   when they did not. Do not run new hardware/QEMU tests unless requested.
5. Keep BUILD-STATUS.md honest about the owner's acceptance and evidence limits.
6. SETUP.md is the beginner guide. Keep its PDF and IMPLEMENTATION.md aligned.

Version 1.0.0 is the definitive owner-accepted baseline. No further hardware tests
were requested for this cleanup. That does not certify a second kit, every port
or unsupported partition layout. New substantive changes need their own evidence.
The guide PDF is an explicitly mapped public document; no other PDFs or private
binary payloads belong in the source inventory.
