# Beta 1.7.3 Mac Fix

Fix **Minecraft Beta 1.7.3 inverted/swapped colors, fullscreen and window resize crashes, and Video Settings crashes** on Apple Silicon Macs using TLauncher.

This is an installer and setup guide. The actual color fix comes from **[LegacyFix by the Betacraft team](https://github.com/betacraftuk/legacyfix)**. The updated graphics library comes from **[Legacy Fabric's LWJGL fork](https://github.com/Legacy-Fabric/lwjgl)**. This project does not claim authorship of those fixes.

## Confirmed working

A MacBook with an **Apple M4**, TLauncher, and vanilla **b1.7.3**. The user confirmed that colors, fullscreen, resizing, and Video Settings worked after applying this combination. Other Macs, launchers, beta versions, and modded installations have not been verified. The reusable installer is tested separately against a temporary installation.

## What this changes

| Symptom | Change |
| --- | --- |
| Red and blue appear swapped | Load LegacyFix 26.10 as a Java agent; its `deawt` patch fixes the window rendering path |
| Fullscreen or resizing crashes | Replace LWJGL 2.9.0 with `2.9.4+legacyfabric.18`, including its macOS native libraries |
| Opening Video Settings crashes | Reset unsupported `guiScale` values, such as `5`, to Auto (`0`). Beta 1.7.3 supports `0`–`3` |

LegacyFix itself configures this LWJGL version for supported Prism Launcher installations. This installer applies the corresponding library configuration to a separate TLauncher profile. See the [upstream implementation](https://github.com/betacraftuk/legacyfix/blob/6ed9e82/common/src/main/java/uk/betacraft/legacyfix/util/launchers/PrismLauncherUtils.java).

The installer copies your existing vanilla game JAR locally, creates **b1.7.3-AppleSiliconFix**, and leaves the original b1.7.3 profile intact. Worlds are not moved or edited by the installer. Both profiles use the same game directory and saves. If it changes `options.txt`, it first saves a dated backup beside that file. Existing profiles are never overwritten.

LegacyFix's proxy, skin/profile handling, and server-join authentication features are disabled in this configuration. Other default applicable LegacyFix patches may still run. This tool does not provide Minecraft, bypass ownership checks, or install TLauncher.

## Requirements

- macOS on an Apple Silicon Mac (M1, M2, M3, M4, or later); only M4 has been confirmed here.
- Your own installed, unmodified **Minecraft Beta b1.7.3** profile. Launch it once in TLauncher so its files are downloaded, then close it.
- Python 3.8 or later and `curl`. Check with `python3 --version`. If Python is missing, install it from [python.org](https://www.python.org/downloads/macos/).
- Internet access to GitHub and the Legacy Fabric Maven repository.

## Install

1. **Quit Minecraft and TLauncher completely** so they cannot overwrite settings during installation.
2. Download this repository with **Code → Download ZIP**, then extract it.
3. Open Terminal in the extracted folder and run:

   ```sh
   python3 install.py --dry-run
   python3 install.py
   ```

4. Reopen TLauncher. Enable modified/local versions in its version filters if necessary, select **b1.7.3-AppleSiliconFix**, and launch.
5. Check colors, **Options → Video Settings**, window resizing, and fullscreen (F11, or Fn+F11 depending on your keyboard settings).

For a custom game directory:

```sh
python3 install.py --minecraft-dir "/path/to/minecraft"
```

For a different new profile name:

```sh
python3 install.py --profile b1.7.3-MyMacFix
```

Downloads are pinned to exact versions and checked against SHA-256 hashes. If a download fails or a checksum differs, installation stops before changing the game installation. Do not enable force-update for the custom profile.

## Undo

Quit the game and choose the original **b1.7.3** profile in TLauncher. The custom profile can be moved to Trash from `versions/b1.7.3-AppleSiliconFix` inside your Minecraft folder. Keep `saves` intact. Shared downloaded libraries may remain; they do not change which libraries the original profile uses.

If the installer reset the GUI scale, its backup is named `options.txt.before-apple-silicon-fix-<timestamp>.bak`. To undo just that setting, copy its original `guiScale` value back into `options.txt` while the game is closed. Restoring a value outside `0`–`3` reintroduces the beta Video Settings crash. Restoring the entire backup also discards later settings changes.

## Troubleshooting

- **Profile already exists:** installation refuses to overwrite it. Use another `--profile` name, or move the previous custom profile to Trash first.
- **Non-vanilla JAR:** this installer deliberately rejects modified JARs. It is not a modpack installer.
- **Video Settings breaks again after playing a newer Minecraft version:** the shared `options.txt` may now contain an unsupported GUI scale. With the game closed, set `guiScale:0`. Separate game directories are preferable if you regularly switch eras.
- **Still crashing:** report the macOS version, chip, TLauncher/Java versions, and exact action. Remove account names, tokens, server addresses, and personal paths before posting logs.
- **Old Java TLS warnings:** the confirmed setup used TLauncher's existing Java 8. This installer does not upgrade Java. LegacyFix recommends a current Java 8 runtime for its network features; those features are disabled here.

## Credits and licensing

- **LegacyFix 26.10** — [source and releases](https://github.com/betacraftuk/legacyfix), [GPL v3](https://github.com/betacraftuk/legacyfix/blob/26.10/LICENSE). Downloaded unchanged from the authors' release.
- **LWJGL `2.9.4+legacyfabric.18`** — [Legacy Fabric source](https://github.com/Legacy-Fabric/lwjgl), [official Maven repository](https://maven.legacyfabric.net/org/lwjgl/lwjgl/). Its code, native components, and dependencies retain their upstream licenses; see the upstream repository and distribution notices.
- **Minecraft** — owned by Mojang/Microsoft. No game binaries, assets, decompiled game code, or ready-to-run modified clients are distributed here. The installer requires an existing vanilla installation and performs configuration locally. See the [Minecraft EULA](https://www.minecraft.net/en-us/eula).
- This repository's original installer, tests, and documentation are released under the MIT license in [LICENSE](LICENSE). That license does not relicense any third-party work.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary directories and mocked downloads; they do not modify a real Minecraft installation or launch the game.
