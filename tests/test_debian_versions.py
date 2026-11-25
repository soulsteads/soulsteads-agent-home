"""Exercise PEP 440 to Debian ordering with actual wheel-backed packages."""
import email
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'soulsteads-agent-home'
DPKG_DEB = os.environ.get('DPKG_DEB', 'dpkg-deb')


@unittest.skipUnless(all(shutil.which(tool) for tool in ('uv', 'dpkg', DPKG_DEB)),
                     'requires uv, dpkg and dpkg-deb')
class DebianVersionTests(unittest.TestCase):
    def test_prerelease_final_and_epoch_versions(self):
        work = Path(self.enterContext(tempfile.TemporaryDirectory()))
        fixture = work / 'source'
        fixture.mkdir()
        for folder in ('soulsteads',):
            shutil.copytree(ROOT / folder, fixture / folder,
                            ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('LICENSE', 'NOTICE', 'README.md'):
            shutil.copyfile(ROOT / name, fixture / name)
        shutil.copytree(ROOT / 'scripts', fixture / 'scripts')
        manifest = (ROOT / 'pyproject.toml').read_text()
        previous = None
        for i, (source, wheel, debian, filename) in enumerate((
            ('0.4.0.dev2', '0.4.0.dev2', '0.4.0~~dev2', '0.4.0~~dev2'),
            ('v0.4.0-rc.1', '0.4.0rc1', '0.4.0~rc1', '0.4.0~rc1'),
            ('0.4.0rc1.post1.dev1', '0.4.0rc1.post1.dev1', '0.4.0~rc1+post1~dev1', '0.4.0~rc1+post1~dev1'),
            ('0.4.0', '0.4.0', '0.4.0', '0.4.0'),
            ('0.4.0.post1', '0.4.0.post1', '0.4.0+post1', '0.4.0+post1'),
            ('1!0.3.0', '1!0.3.0', '1:0.3.0', '1%3a0.3.0'),
        )):
            with self.subTest(version=source):
                changed, count = re.subn(r'(?m)^version = "[^"\n]+"$', f'version = "{source}"', manifest)
                self.assertEqual(count, 1)
                (fixture / 'pyproject.toml').write_text(changed)
                output = work / f'output-{i}'
                run = subprocess.run(['bash', 'scripts/build-deb.sh', '--out-dir', str(output)],
                                     cwd=fixture, capture_output=True, text=True, timeout=90)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                artifact = output / f'{PACKAGE}_{filename}_all.deb'
                self.assertEqual(list(output.glob('*.deb')), [artifact])
                version = subprocess.check_output([DPKG_DEB, '-f', artifact, 'Version'], text=True).strip()
                self.assertEqual(version, debian)
                tree = work / f'payload-{i}'
                subprocess.run([DPKG_DEB, '-x', artifact, tree], check=True)
                metadata, = (tree / 'usr/lib/python3/dist-packages').glob('*.dist-info/METADATA')
                self.assertEqual(email.message_from_bytes(metadata.read_bytes())['Version'], wheel)
                if previous is not None:
                    subprocess.run(['dpkg', '--compare-versions', previous, 'lt', version], check=True)
                previous = version

        (fixture / 'pyproject.toml').write_text(re.sub(
            r'(?m)^version = "[^"\n]+"$', 'version = "0.4.0+local"', manifest))
        output = work / 'unsupported'
        run = subprocess.run(['bash', 'scripts/build-deb.sh', '--out-dir', str(output)],
                             cwd=fixture, capture_output=True, text=True, timeout=90)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('local labels are not supported', run.stderr)
        self.assertEqual(list(output.glob('*.deb')), [])


if __name__ == '__main__':
    unittest.main()
