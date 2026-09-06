# DevKit2023CustomLinux Diagnostics

Permanent optional support utility. This is a read-only diagnostic collector,
not a repair tool or proof that every device works. No disk installation,
Windows access, radio address changes, pairing, service restarts, module reloads
or sound playback are performed. Use on any kit; no target identity is embedded.

## Included in the new live desktop

1. Open **DevKit2023CustomLinux Diagnostics** on the desktop or application menu.
2. Select **Create report**. A native KDE progress window shows collection status.
   Existing password-free live-session access is used when configured; otherwise
   approve the system-log authorization prompt. Cancelling authorization produces
   a partial report, not a settings change.
3. The completion dialog gives the exact saved text-file path and offers
   **View report**. A desktop launch saves beside the launcher. An application-menu
   launch saves on your Desktop.
4. Copy `DevKit2023CustomLinux-report-*.txt` to writable storage before restarting
   a live session, then share it with support. Each run preserves older reports.

There is one desktop launcher. The implementation is installed under
`/usr/local/libexec`, not left as a loose Python file on the desktop.

## Portable use on an older live image

1. Extract the portable tester ZIP. Copy the entire extracted folder onto the
   Linux live Desktop. Keep the launcher and hidden `.support` folder together.
   Do not run from inside the ZIP or from read-only installation media.
2. Double-click **DevKit2023CustomLinux Diagnostics**. If KDE asks whether to trust/run
   the launcher, allow it. If needed, open its Properties → Permissions and mark
   it executable. Select **Create report**; KDE shows collection progress.
3. If asked, approve the system-log authorization prompt using the live session's password.
   Existing password-free live-session access is used automatically when available;
   the tester does not change permissions or configure password-free access.
   Cancelling still produces a partial report; system and Bluetooth logs may be
   missing. Wait for the report completion dialog.
4. Copy the new `DevKit2023CustomLinux-report-*.txt` from that same folder to a
   writable USB and send it back. Do this before reboot: a live Desktop is
   normally temporary. Each run creates a new file and preserves earlier reports.

If KDE does not launch it, open Konsole **in the extracted folder** and run
`python3 -B .support/devkit2023customlinux-diagnostics --launcher ./DevKit2023Diagnostics.desktop`.
This writes beside the launcher. Use `--no-admin`
only when deliberately collecting a partial report without the password prompt.
It requires Linux and Python 3; graphical operation uses KDE's kdialog and qdbus6.
Missing optional commands are recorded rather than installed automatically.
Version 1.2 uses pollable input pipes for BlueZ commands; `/dev/null` prevents
BlueZ 5.82 from dispatching its noninteractive query. Timeout reports retain
any partial reply. Installed WirePlumber utilities also collect default-output
details without adding a PulseAudio server or utilities package.

## What is collected

Version 1.4 also recognizes installer summary/launch failures and permission-denied
errors without copying surrounding account, path or disk-plan details. Installer
failure dialogs offer **Open log** for the separate private raw log.

- Kernel/version/boot settings; PCI/USB drivers, link state and storage layout.
- Product service results and bounded current-boot system/kernel logs.
- Audio firmware/topology presence, DSP state, ALSA cards/mixers/ELD,
  PipeWire output profiles/sinks and user audio service logs.
- Bluetooth controller/configuration state, sysfs attribute names and rfkill.
- Display connector state and selected package versions.
- Version 1.3 adds recognized installer startup failures and the main-window
  initialization marker. Raw launcher and Calamares logs remain private; account
  setup, disk plans and arbitrary neighboring debug lines are not included.

No Windows files, registry hives, firmware contents, target manifest, pairing
keys, saved Wi-Fi networks or paired-device lists are collected. Common MAC/IP
addresses, UUIDs, long hex identifiers, home paths and name fields are redacted.
Raw mixer ELD byte arrays are omitted; decoded ELD capabilities are retained with
the monitor name redacted. Empty name fields do not hide subsequent status lines.
Logs can still contain unexpected personal strings: review before public sharing.
The report is a new owner-only file. Authorization is used only for reading
system diagnostics; the privileged child returns text, not output-path writes.

## Source and image integration

The maintained launcher is `overlay/etc/skel/Desktop/DevKit2023Diagnostics.desktop`;
the helper is `overlay/usr/local/libexec/devkit2023customlinux-diagnostics`.
Both generic builds and private preparation install them. The application-menu
entry is generated from the same launcher, avoiding two maintained copies.
`scripts/package-diagnostics.py` makes an optional portable ZIP, with the helper
hidden in `.support`. Per the user's revised requirement, this utility is kept
for production support. A diagnostic report is not installed-system acceptance;
the installer independently validates its target, disk plan and EFI handover.

Synthetic tests cover redaction, read-only query selection, missing commands,
timeouts, portable launcher paths (including spaces), separate new reports and
restricted permissions. They do not establish Qualcomm audio/radio operation.
