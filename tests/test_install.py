import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("installer", Path(__file__).parents[1] / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Minecraft with spaces"
        source = self.root / "versions/b1.7.3"
        source.mkdir(parents=True)
        self.jar = b"fixture game jar"
        (source / "b1.7.3.jar").write_bytes(self.jar)
        self.original = {"id": "b1.7.3", "mainClass": "net.minecraft.launchwrapper.Launch",
                         "minecraftArguments": "${auth_player_name} ${auth_session}",
                         "downloads": {"client": {"url": "https://example.invalid/client.jar"}},
                         "libraries": [{"name": "org.lwjgl.lwjgl:lwjgl:2.9.0"},
                                       {"name": "net.minecraft:launchwrapper:1.5"}]}
        (source / "b1.7.3.json").write_text(json.dumps(self.original))
        (self.root / "options.txt").write_bytes(b"sound:1.0\r\nguiScale:5\r\nfancyGraphics:true\r\n")
        (self.root / "saves/World1").mkdir(parents=True)
        (self.root / "saves/World1/level.dat").write_bytes(b"world fixture")
        self.addCleanup(patch.stopall)
        patch.object(installer, "VANILLA_SHA1", hashlib.sha1(self.jar).hexdigest()).start()

    @staticmethod
    def fake_download(url, destination, expected):
        if destination.name == "natives.jar":
            with zipfile.ZipFile(destination, "w") as z:
                z.writestr("liblwjgl-macos-amd64.dylib", b"native fixture")
                z.writestr("../escaped.dylib", b"must not extract")
        else:
            destination.write_bytes(b"dependency fixture " + destination.name.encode())

    def test_install_preserves_game_and_world_and_fixes_profile(self):
        with patch.object(installer, "download", side_effect=self.fake_download):
            installer.install(self.root)
        target = self.root / "versions" / installer.PROFILE
        result = json.loads((target / f"{installer.PROFILE}.json").read_text())
        self.assertEqual((target / f"{installer.PROFILE}.jar").read_bytes(), self.jar)
        self.assertEqual(json.loads((self.root / "versions/b1.7.3/b1.7.3.json").read_text()), self.original)
        self.assertEqual((self.root / "saves/World1/level.dat").read_bytes(), b"world fixture")
        self.assertNotIn("downloads", result)
        self.assertEqual(result["minecraftArguments"], self.original["minecraftArguments"])
        self.assertEqual(len(result["libraries"]), 4)
        self.assertTrue(all("2.9.0" not in lib["name"] for lib in result["libraries"]))
        self.assertIn("${game_directory}", result["jvmArguments"])
        self.assertTrue((target / "natives/liblwjgl-macos-amd64.dylib").exists())
        self.assertFalse((target / "escaped.dylib").exists())
        self.assertEqual((self.root / "options.txt").read_bytes(), b"sound:1.0\r\nguiScale:0\r\nfancyGraphics:true\r\n")
        backup, = self.root.glob("options.txt.before-*.bak")
        self.assertIn(b"guiScale:5", backup.read_bytes())
        with self.assertRaisesRegex(ValueError, "already exists"):
            installer.install(self.root)

    def test_failed_download_does_not_modify_installation(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(installer, "download", side_effect=ValueError("Checksum mismatch")):
            with self.assertRaises(ValueError):
                installer.install(self.root)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_rejects_modified_jar_without_download(self):
        (self.root / "versions/b1.7.3/b1.7.3.jar").write_bytes(b"modified")
        with patch.object(installer, "download") as download:
            with self.assertRaisesRegex(ValueError, "not vanilla"):
                installer.install(self.root)
            download.assert_not_called()

    def test_dry_run_has_no_side_effects(self):
        with patch.object(installer, "download") as download:
            installer.install(self.root, dry_run=True)
            download.assert_not_called()
        self.assertFalse((self.root / "versions" / installer.PROFILE).exists())
        self.assertIn("guiScale:5", (self.root / "options.txt").read_text())

    def test_gui_scale_preserves_valid_values(self):
        for value in range(4):
            source = f"guiScale:{value}\nsound:1.0\n"
            self.assertEqual(installer.fixed_options(source), source)
        self.assertEqual(installer.fixed_options("guiScale:-1"), "guiScale:0")

    def test_rejects_path_traversal_profile(self):
        with self.assertRaises(ValueError):
            installer.install(self.root, "../../outside")


if __name__ == "__main__":
    unittest.main()
