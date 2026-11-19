"""Verify documentation links and historic ledger paths after reorganizing docs."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
LINK = re.compile(r'\]\(([^\s)]+)(?=(?:\s+[^)]*)?\))')
OLD_DOC = re.compile(r'docs/[a-z0-9-]+\.md')


class DocumentationPathsTest(unittest.TestCase):
    def test_every_document_directory_has_a_readme(self):
        missing = [str(p.relative_to(ROOT)) for p in [DOCS, *DOCS.rglob('*')] if p.is_dir() and not (p / 'README.md').is_file()]
        self.assertEqual(missing, [])
        self.assertEqual(list(DOCS.rglob('index.md')), [])

    def test_tools_web_and_support_folders_have_readmes(self):
        required = [ROOT / 'tools', ROOT / 'web', ROOT / 'licenses', ROOT / 'scenarios']
        for base in (ROOT / 'tools', ROOT / 'web'):
            required.extend(p for p in base.rglob('*') if p.is_dir() and not any(part.startswith('.') or part == '__pycache__' for part in p.relative_to(base).parts))
        self.assertEqual([str(p.relative_to(ROOT)) for p in required if not (p / 'README.md').is_file()], [])

    def test_old_ledger_document_paths_remain_resolvable(self):
        mapping = json.loads((DOCS / 'data/document-path-map.json').read_text())['paths']
        ledger = (DOCS / 'data/work-log.tsv').read_text()
        missing = [p for p in set(OLD_DOC.findall(ledger)) if not (ROOT / mapping.get(p, p)).is_file()]
        self.assertEqual(missing, [])

    def test_local_markdown_links_exist(self):
        missing = []
        for source in [ROOT / 'README.md', *DOCS.rglob('*.md'), *(ROOT / 'tools').rglob('README.md'), *(ROOT / 'web').rglob('README.md'), ROOT / 'licenses/README.md', ROOT / 'scenarios/README.md']:
            for match in LINK.finditer(source.read_text(encoding='utf-8')):
                value = match.group(1)
                if (value.startswith(('#', '/', '<')) or re.match(r'^[A-Za-z][\w+.-]*:', value)
                        or re.fullmatch(r'0x[0-9a-fA-F]+', value)):
                    continue
                path = unquote(value.split('#', 1)[0].split('?', 1)[0])
                if path and not (source.parent / path).exists():
                    missing.append(f'{source.relative_to(ROOT)} -> {value}')
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
