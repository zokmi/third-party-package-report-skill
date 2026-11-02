"""Distribution contract for the shared Claude Code / Codex plugin."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DistributionTests(unittest.TestCase):
    def test_manifests_resolve_same_bundled_skill(self):
        manifests = [json.loads((ROOT / p).read_text(encoding='utf-8')) for p in
                     ('plugin.json', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json')]
        self.assertEqual(len({m['name'] for m in manifests}), 1)
        self.assertEqual(len({m['version'] for m in manifests}), 1)
        for manifest in manifests[1:]:
            skills = ROOT / manifest['skills']
            bundled = skills / 'generating-third-party-package-report'
            for path in ('SKILL.md', 'assets/report-template.md', 'scripts/collect_packages.py'):
                self.assertTrue((bundled / path).is_file(), path)
        self.assertIn('interface', manifests[2])

    def test_marketplace_resolves_plugin_root(self):
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
        entry, = marketplace['plugins']
        self.assertEqual((ROOT / entry['source']).resolve(), ROOT)
        manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(entry['name'], manifest['name'])

    def test_skill_assets_are_relative_to_loaded_skill(self):
        skill = ROOT / 'skills/generating-third-party-package-report'
        text = (skill / 'SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn('~/.claude/', text)
        self.assertNotIn('~/.agents/', text)
        self.assertIn('UNAVAILABLE', text)
        self.assertFalse(list(skill.rglob('*.html')))

if __name__ == '__main__':
    unittest.main()