import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    import yaml
except ImportError:
    yaml = None


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/release.yml'
WHEEL = 'soulsteads-0.2.0-py3-none-any.whl'
SDIST = 'soulsteads-0.2.0.tar.gz'

# Replace only external service calls. Hashing, file validation and jq run normally.
STUBS = r'''
gh() {
  case "$*" in
    'api repos/example/project/releases/42')
      printf '%s\n' '{"tag_name":"v0.2.0","draft":false,"immutable":false}' ;;
    'api --paginate --slurp repos/example/project/releases/42/assets?per_page=100')
      printf '%s\n' '[[]]' ;;
    *) return 1 ;;
  esac
}
git() {
  [[ "$1" == ls-remote ]]
  printf '%s\t%s\n' "$GITHUB_SHA" refs/tags/v0.2.0
}
curl() {
  while [[ "$1" != --data-binary ]]; do shift; done
  local file=${2#@} digest
  printf '%s\n' "$file" >> "$UPLOAD_LOG"
  digest=$(sha256sum -- "$file" | cut -d ' ' -f 1)
  jq -n --arg name "$file" --arg digest "sha256:$digest" \
    '{name:$name,digest:$digest,state:"uploaded"}'
}
'''


@unittest.skipUnless(WORKFLOW.is_file(), 'requires a source checkout with GitHub workflows')
@unittest.skipUnless(
    sys.platform.startswith('linux') and yaml is not None
    and all(shutil.which(tool) for tool in ('bash', 'jq', 'sha256sum')),
    'requires PyYAML and Linux release shell tools',
)
class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.dist = root / 'dist'
        self.dist.mkdir()
        self.upload_log = root / 'uploads'
        self.manifest = self.dist / 'SHA256SUMS'
        for name, payload in [(WHEEL, b'wheel fixture'), (SDIST, b'sdist fixture')]:
            (self.dist / name).write_bytes(payload)
        self.manifest.write_text(''.join(
            f'{hashlib.sha256((self.dist / name).read_bytes()).hexdigest()}  {name}\n'
            for name in (WHEEL, SDIST)
        ), encoding='ascii')

    def run_publisher(self):
        assert yaml is not None  # Required by the test class's skip condition.
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))
        step = next(step for step in workflow['jobs']['publish']['steps'] if 'run' in step)
        result = subprocess.run(
            ['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', STUBS + step['run']],
            cwd=self.dist,
            env={'PATH': os.environ['PATH'], 'LC_ALL': 'C', 'GH_TOKEN': 'test-only',
                 'GITHUB_REPOSITORY': 'example/project', 'GITHUB_SHA': 'a' * 40,
                 'RELEASE_ID': '42', 'RELEASE_TAG': 'v0.2.0',
                 'UPLOAD_LOG': str(self.upload_log)},
            text=True, capture_output=True, timeout=10,
        )
        uploads = self.upload_log.read_text().splitlines() if self.upload_log.exists() else []
        return result, uploads

    def assert_rejected_without_uploads(self):
        result, uploads = self.run_publisher()
        self.assertEqual(uploads, [])
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_valid_handoff_uploads_only_expected_assets(self):
        result, uploads = self.run_publisher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertCountEqual(uploads, [WHEEL, SDIST, 'SHA256SUMS'])

    def test_unlisted_file_is_rejected_before_upload(self):
        (self.dist / 'extra.txt').write_text('unexpected fixture')
        self.assert_rejected_without_uploads()

    def test_hidden_file_is_rejected_before_upload(self):
        (self.dist / '.extra').touch()
        self.assert_rejected_without_uploads()

    def test_manifest_must_list_both_packages_exactly_once(self):
        wheel, sdist = self.manifest.read_text().splitlines(keepends=True)
        for case, manifest in [('missing', wheel), ('duplicate', wheel + sdist + wheel)]:
            with self.subTest(case=case):
                self.manifest.write_text(manifest)
                self.assert_rejected_without_uploads()

    def test_modified_package_is_rejected_before_upload(self):
        (self.dist / WHEEL).write_bytes(b'modified fixture')
        self.assert_rejected_without_uploads()
