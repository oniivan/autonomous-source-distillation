from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ID = "autonomous-source-distillation"
DISPLAY_NAME = "Autonomous Source Distillation"
FORMER_ID = "long" + "-material-distillation"


class SkillIdentityTests(unittest.TestCase):
    def test_frontmatter_meets_skill_creator_shape_contract(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)

        self.assertIsNotNone(match)
        rows = [
            row.split(":", 1)
            for row in match.group(1).splitlines()
            if row.strip()
        ]
        self.assertTrue(all(len(row) == 2 for row in rows))
        frontmatter = {key.strip(): value.strip() for key, value in rows}
        self.assertEqual(set(frontmatter), {"name", "description"})

        name = frontmatter["name"]
        description = frontmatter["description"]
        self.assertRegex(name, r"^[a-z0-9-]+$")
        self.assertFalse(name.startswith("-") or name.endswith("-") or "--" in name)
        self.assertLessEqual(len(name), 64)
        self.assertTrue(description)
        self.assertLessEqual(len(description), 1024)
        self.assertNotIn("<", description)
        self.assertNotIn(">", description)

    def test_frontmatter_and_heading_match_canonical_identity(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)

        self.assertIsNotNone(name_match)
        self.assertEqual(name_match.group(1), CANONICAL_ID)
        self.assertIn(f"# {DISPLAY_NAME}", text)

    def test_display_metadata_and_default_invocation_match(self):
        text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn(f'display_name: "{DISPLAY_NAME}"', text)
        self.assertIn(f"${CANONICAL_ID}", text)
        self.assertNotIn(f"${FORMER_ID}", text)

    def test_canonical_installed_layout_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            skills_root = Path(temp) / "skills"
            install_root = skills_root / CANONICAL_ID
            shutil.copytree(
                SKILL_ROOT,
                install_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )

            self.assertEqual(install_root.name, CANONICAL_ID)
            self.assertTrue((install_root / "SKILL.md").is_file())
            self.assertFalse((skills_root / FORMER_ID).exists())

    def test_former_identity_is_absent_from_package_text(self):
        matches: list[str] = []
        for path in SKILL_ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if FORMER_ID in text:
                matches.append(str(path.relative_to(SKILL_ROOT)))

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
