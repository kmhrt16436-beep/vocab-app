"""Package public runtime files with explicit permissions, independent of the caller's umask."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import sys


def package(root, destination):
    root = Path(root)
    names = ['host.json', 'package.json', 'package-lock.json']
    names += sorted(str(p.relative_to(root)) for p in (root / 'src').glob('*.js'))
    if not (root / 'src/functions.js').is_file():
        raise ValueError('Missing function entry point')
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        directory = ZipInfo('src/')
        directory.create_system = 3
        directory.external_attr = (0o40755 << 16) | 0x10
        archive.writestr(directory, b'')
        for name in names:
            entry = ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, (root / name).read_bytes())
    with ZipFile(destination) as archive:
        for entry in archive.infolist():
            mode = (entry.external_attr >> 16) & 0o777
            expected = 0o755 if entry.is_dir() else 0o644
            if mode != expected:
                raise ValueError('Invalid package permission: ' + entry.filename)
    return names


if __name__ == '__main__':
    names = package(sys.argv[1], sys.argv[2])
    print(f'Validated deployment ZIP: {len(names)} files (644), directories (755).')
