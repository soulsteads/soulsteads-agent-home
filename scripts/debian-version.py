"""Read the built wheel's canonical version and map it to a Debian package version."""
from email.parser import BytesParser
from pathlib import Path
import re
import sys


def debian_version(version: str) -> str:
    # The wheel backend already normalized the PEP 440 spelling. Do not assign
    # Debian ordering to local version labels, which have different sort rules.
    match = re.fullmatch(
        r'(?:(?P<epoch>[1-9][0-9]*)!)?(?P<release>[0-9]+(?:\.[0-9]+)*)'
        r'(?:(?P<pre>a|b|rc)(?P<pre_number>[0-9]+))?'
        r'(?:\.post(?P<post>[0-9]+))?(?:\.dev(?P<dev>[0-9]+))?',
        version,
    )
    if match is None:
        raise SystemExit('unsupported wheel version for Debian packaging (local labels are not supported)')
    # PEP 440 treats trailing zero release components as equal. Preserve the
    # project's existing major.minor.patch stable output and pad shorter forms.
    release = match['release'].split('.')
    while len(release) > 3 and release[-1] == '0':
        release.pop()
    upstream = '.'.join(release + ['0'] * (3 - len(release)))
    if match['pre']:
        upstream += '~' + match['pre'] + match['pre_number']
    if match['post'] is not None:
        upstream += '+post' + match['post']
    if match['dev'] is not None:
        # A standalone dev release precedes even alpha. A dev release attached
        # to a pre/post release sorts immediately before that parent.
        upstream += ('~' if match['pre'] or match['post'] is not None else '~~') + 'dev' + match['dev']
    return (match['epoch'] + ':' if match['epoch'] else '') + upstream


def main() -> None:
    root, project = sys.argv[1:]
    metadata = list(Path(root).glob('*.dist-info/METADATA'))
    if len(metadata) != 1:
        raise SystemExit('expected exactly one wheel METADATA file')
    headers = BytesParser().parsebytes(metadata[0].read_bytes(), headersonly=True)
    names, versions = headers.get_all('Name', []), headers.get_all('Version', [])
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    if len(names) != 1 or normalize(names[0]) != normalize(project) or len(versions) != 1:
        raise SystemExit('unexpected wheel project name or version metadata')
    # The .dist-info directory is normalized by the wheel builder even when
    # its Version header preserves the original spelling (e.g. Hatchling).
    distribution, separator, canonical = metadata[0].parent.name.removesuffix('.dist-info').rpartition('-')
    if not separator or normalize(distribution) != normalize(project):
        raise SystemExit('unexpected wheel .dist-info directory')
    print(debian_version(canonical))


if __name__ == '__main__':
    main()
