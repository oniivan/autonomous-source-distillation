from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL_ROOT.parent
CANONICAL_ID = "autonomous-source-distillation"
DISPLAY_NAME = "Autonomous Source Distillation"
FORMER_ID = "long" + "-material-distillation"


class SkillIdentityTests(unittest.TestCase):
    def test_folder_frontmatter_and_heading_match_canonical_identity(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)

        self.assertEqual(SKILL_ROOT.name, CANONICAL_ID)
        self.assertIsNotNone(name_match)
        self.assertEqual(name_match.group(1), CANONICAL_ID)
        self.assertIn(f"# {DISPLAY_NAME}", text)

    def test_display_metadata_and_default_invocation_match(self):
        text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn(f'display_name: "{DISPLAY_NAME}"', text)
        self.assertIn(f"${CANONICAL_ID}", text)
        self.assertNotIn(f"${FORMER_ID}", text)

    def test_former_identity_has_no_package_or_wrapper(self):
        self.assertFalse((SKILLS_ROOT / FORMER_ID).exists())

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
