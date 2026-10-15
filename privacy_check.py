"""Conservative local privacy check. Reports locations, never matched values.

Run from the repository root: python3 tools/privacy_check.py
"""
from pathlib import Path
import ast
import json
import re
import sys

PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'GitHub token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    'Google API key': re.compile(r'\bAIza[0-9A-Za-z_-]{30,}\b'),
    'AWS access key': re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'),
    'embedded credential': re.compile(r'"(?:private_key|client_secret|refresh_token|access_token)"\s*:\s*"[^"\n]{10,}"'),
    'email address to review': re.compile(r'\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'private local path': re.compile(r'(?:/workspace/' r'scratch/[^\s"\']+|/Us' r'ers/[^\s"\']+|/ho' r'me/[^\s"\']+|[A-Z]:\\Users\\[^\s"\']+)'),
    'private file/share reference': re.compile(r'(?:oai-' r'library://|lib' r'file_[a-f0-9]+|colab\.research\.google\.com/drive/|drive\.google\.com/(?:file/d/|drive/folders/))'),
}
TEXT_SUFFIXES = {'.py', '.sql', '.ipynb', '.md', '.csv', '.json', '.yml', '.yaml', '.txt', '.sh', '.toml', '.cfg'}
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.venv', 'venv', 'node_modules'}
PRIVATE_METADATA = {'authors', 'author', 'email', 'path', 'signature', 'widgets', 'google_drive_id', 'drive_id'}

def text_issues(text):
    return [(kind, text.count('\n', 0, m.start()) + 1)
            for kind, pattern in PATTERNS.items() for m in pattern.finditer(text)]

def _hardcoded_identifiers(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # Notebook magics are checked by the notebook runner, not this scan.
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [n.id for n in node.targets if isinstance(n, ast.Name)]
            if set(targets) & {'PROJECT_ID', 'DATASET'} and isinstance(node.value, ast.Constant):
                value = node.value.value
                if isinstance(value, str) and value and not value.upper().startswith(('YOUR', 'EXAMPLE', 'PLACEHOLDER')):
                    hits.append(('hardcoded cloud identifier', node.lineno))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'get', 'getenv'}:
            if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) and node.args[0].value in {'SERBIA_PROJECT', 'SERBIA_DATASET'}:
                default = node.args[1]
                if isinstance(default, ast.Constant) and isinstance(default.value, str) and default.value:
                    hits.append(('hardcoded cloud identifier default', node.lineno))
    return hits

def inspect_repository(root):
    findings = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or set(path.relative_to(root).parts) & SKIP_DIRS:
            continue
        rel = str(path.relative_to(root))
        lower = path.name.lower()
        if lower == '.env' or lower.startswith('.env.') and lower != '.env.example' or lower.endswith(('.pem', '.key')) or lower in {'credentials.json', 'application_default_credentials.json', 'local_settings.json'} or re.search(r'(?:service[-_]account|client_secret|credentials).*\.json$', lower):
            findings.append((rel, 'credential/private-settings file', 1))
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {'.gitignore', '.gitattributes', 'VERSION'}:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        findings.extend((rel, kind, line) for kind, line in text_issues(text))
        if path.suffix == '.py':
            findings.extend((rel, kind, line) for kind, line in _hardcoded_identifiers(text))
        if path.suffix == '.ipynb':
            try:
                nb = json.loads(text)
            except json.JSONDecodeError:
                findings.append((rel, 'invalid notebook JSON', 1))
                continue
            if PRIVATE_METADATA & nb.get('metadata', {}).keys():
                findings.append((rel, 'identifying notebook metadata', 1))
            for i, cell in enumerate(nb.get('cells', []), 1):
                if cell.get('outputs') or cell.get('execution_count') is not None:
                    findings.append((rel, f'cell {i}: saved execution/output', 1))
                if PRIVATE_METADATA & cell.get('metadata', {}).keys() or cell.get('attachments'):
                    findings.append((rel, f'cell {i}: metadata/attachment to review', 1))
                if cell.get('cell_type') == 'code':
                    findings.extend((rel, f'cell {i}: {kind}', line)
                                    for kind, line in _hardcoded_identifiers(''.join(cell.get('source', []))))
    return sorted(set(findings))

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    findings = inspect_repository(root)
    if findings:
        for name, kind, line in findings:
            print(f'{name}:{line}: {kind}')
        print(f'FAIL: {len(findings)} issue(s) need review. Matched values were not printed.')
        sys.exit(1)
    print('PASS: no detected secrets, email addresses, private share references, or saved notebook outputs.')
    print('Review new prose, binary files, and repository history separately. This scan is not a privacy guarantee.')
