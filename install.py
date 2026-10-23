#!/usr/bin/env python3
"""Install a separate vanilla Beta 1.7.3 profile for TLauncher on macOS."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

PROFILE = "b1.7.3-AppleSiliconFix"
VANILLA_SHA1 = "43db9b498cb67058d2e12d394e6507722e71bb45"
LWJGL = "2.9.4+legacyfabric.18"
ARTIFACTS = [
    ("legacyfix-26.10.jar", "https://github.com/betacraftuk/legacyfix/releases/download/26.10/legacyfix-26.10.jar", "ea89b3418b049ffcf4090605710c29a5eacd6f1fd181b74d253b5612f17b548e"),
    ("lwjgl.jar", f"https://maven.legacyfabric.net/org/lwjgl/lwjgl/lwjgl/{LWJGL}/lwjgl-{LWJGL}.jar", "fe9e3fefbbc450ba20aa6c26dddc11ff372cb3cb143a3c99a75b4dcdb440f912"),
    ("lwjgl_util.jar", f"https://maven.legacyfabric.net/org/lwjgl/lwjgl/lwjgl_util/{LWJGL}/lwjgl_util-{LWJGL}.jar", "b1be28748e954f5ebdedfac5816cb91345c2efdcae0341d81225a56b8ebb3097"),
    ("natives.jar", f"https://maven.legacyfabric.net/org/lwjgl/lwjgl/lwjgl-platform/{LWJGL}/lwjgl-platform-{LWJGL}-natives-osx.jar", "ca5d92abd2fc7ac952414ce791b95782cdba57eb22b9f1e1b739c8d0da359170"),
]


def digest(path, algorithm="sha256"):
    return hashlib.new(algorithm, Path(path).read_bytes()).hexdigest()


def download(url, destination, expected):
    subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                    "--proto", "=https", "--proto-redir", "=https",
                    "--connect-timeout", "20", "--max-time", "180",
                    "--output", str(destination), url], check=True)
    if digest(destination) != expected:
        raise ValueError(f"Checksum mismatch: {destination.name}. Nothing will be installed.")


def fixed_options(text):
    """Keep valid beta scales (0–3); reset unsupported values from newer versions."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("guiScale:"):
            try:
                valid = int(line.split(":", 1)[1].strip()) in range(4)
            except ValueError:
                valid = False
            if not valid:
                ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                lines[i] = "guiScale:0" + ending
    return "".join(lines)


def build_profile(original, name, files):
    result = copy.deepcopy(original)
    result["id"] = name
    result.pop("downloads", None)
    # Use TLauncher's legacy argument conversion. It splits before expanding paths,
    # so ${game_directory} also works when Application Support contains a space.
    result["jvmArguments"] = (
        f"-javaagent:${{game_directory}}/versions/{name}/legacyfix-26.10.jar "
        "-Dlf.proxy.disable -Dlf.skin.disable -Dlf.profile.disable "
        "-Dlf.auth-on-server-join.disable"
    )
    result["libraries"] = [lib for lib in result["libraries"]
                           if not lib["name"].startswith("org.lwjgl.lwjgl:")]
    for artifact, source, classifier in [
        ("lwjgl", "lwjgl.jar", None), ("lwjgl_util", "lwjgl_util.jar", None),
        ("lwjgl-platform", "natives.jar", "natives-osx")
    ]:
        suffix = "-" + classifier if classifier else ""
        relative = f"org/lwjgl/lwjgl/{artifact}/{LWJGL}/{artifact}-{LWJGL}{suffix}.jar"
        metadata = {"path": relative, "sha1": digest(files / source, "sha1"),
                    "size": (files / source).stat().st_size,
                    "url": "https://maven.legacyfabric.net/" + relative}
        library = {"name": f"org.lwjgl.lwjgl:{artifact}:{LWJGL}"}
        if classifier:
            library.update(downloads={"classifiers": {classifier: metadata}},
                           natives={"osx": classifier}, extract={"exclude": ["META-INF/"]})
        else:
            library["downloads"] = {"artifact": metadata}
        result["libraries"].append(library)
    return result


def install(root, name=PROFILE, dry_run=False):
    root = Path(root).expanduser().resolve()
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", name) or name == "b1.7.3":
        raise ValueError("Choose a new profile name containing only letters, numbers, dots, - or _.")
    source = root / "versions/b1.7.3"
    target = root / "versions" / name
    if target.exists():
        raise ValueError(f"Profile already exists: {target}. Choose another --profile; it will not be overwritten.")
    original = json.loads((source / "b1.7.3.json").read_text())
    if original.get("id") != "b1.7.3" or original.get("inheritsFrom") or original.get("arguments"):
        raise ValueError("This installer requires the original legacy b1.7.3 profile JSON.")
    if digest(source / "b1.7.3.jar", "sha1") != VANILLA_SHA1:
        raise ValueError("The source JAR is not vanilla Beta 1.7.3. Modded JARs are unsupported.")
    options = root / "options.txt"
    old_options = options.read_bytes() if options.exists() else None
    new_options = fixed_options(old_options.decode("utf-8")) if old_options is not None else None
    print(f"Source: {source}\nNew profile: {target}")
    if dry_run:
        print("Dry run: validated source; no files changed and no downloads made.")
        return

    # Complete and verify downloads before changing the installation.
    with tempfile.TemporaryDirectory(prefix="minecraft-beta-fix-") as scratch:
        files = Path(scratch)
        for filename, url, expected in ARTIFACTS:
            print(f"Downloading {filename}...")
            download(url, files / filename, expected)
        result = build_profile(original, name, files)
        # Verify existing shared libraries before writing any files.
        copies = []
        for lib, filename in zip(result["libraries"][-3:], ["lwjgl.jar", "lwjgl_util.jar", "natives.jar"]):
            downloads = lib["downloads"]
            metadata = downloads.get("artifact") or downloads["classifiers"]["natives-osx"]
            destination = root / "libraries" / metadata["path"]
            if destination.exists() and digest(destination) != digest(files / filename):
                raise ValueError(f"Existing library differs: {destination}. No files changed.")
            copies.append((files / filename, destination))
        staged = files / name
        staged.mkdir()
        shutil.copy2(source / "b1.7.3.jar", staged / f"{name}.jar")
        shutil.copy2(files / "legacyfix-26.10.jar", staged / "legacyfix-26.10.jar")
        (staged / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        natives = staged / "natives"
        natives.mkdir()
        with zipfile.ZipFile(files / "natives.jar") as archive:
            for member in archive.namelist():
                if member.endswith(".dylib") and "/" not in member:
                    (natives / member).write_bytes(archive.read(member))
        for src, destination in copies:
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, destination)
        # Copy to a hidden sibling before publishing the complete profile.
        with tempfile.TemporaryDirectory(prefix=".apple-silicon-fix-", dir=target.parent) as publish:
            ready = Path(publish) / name
            shutil.copytree(staged, ready)
            if target.exists():
                raise ValueError("Target appeared during installation; refusing to overwrite it.")
            ready.rename(target)

    if old_options is not None and new_options.encode("utf-8") != old_options:
        # Avoid overwriting changes from a game still running during installation.
        if options.read_bytes() != old_options:
            raise ValueError("Profile installed, but options.txt changed. Close Minecraft and set guiScale:0 manually.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = root / f"options.txt.before-apple-silicon-fix-{stamp}.bak"
        backup.write_bytes(old_options)
        temporary = root / f".options-{stamp}.tmp"
        temporary.write_bytes(new_options.encode("utf-8"))
        os.replace(temporary, options)
        print(f"Unsupported GUI scale reset to Auto. Backup: {backup}")
    print(f"Installed. Restart TLauncher, select {name}, and launch.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minecraft-dir", type=Path,
                        default=Path.home() / "Library/Application Support/minecraft")
    parser.add_argument("--profile", default=PROFILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This installer targets macOS only.")
    try:
        install(args.minecraft_dir, args.profile, args.dry_run)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
