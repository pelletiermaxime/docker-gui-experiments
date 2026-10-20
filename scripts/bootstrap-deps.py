"""Restore pinned external sources; does not install tools, build, or run apps."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = [
    ('https://github.com/justrach/nanoui',
     '.verification/gui-comparison/deps/nanoui',
     'd61e253205472cef0854367125295d87c810c5b3', None),
    ('https://github.com/egoist/mygo',
     '.verification/gui-comparison/deps/mygo',
     '5fb60098a44a4c629cbdeac5f0ff80ce2f843c2f', None),
    ('https://github.com/GuangYiL/container-zig',
     '.verification/gui-live-comparison/deps/container-zig',
     'd65b714977eeadb5b38c1b577f4ef53e3f88083a',
     '.verification/gui-live-comparison/container-zig-zig017.patch'),
    ('https://github.com/danielsuo/libdocker',
     '.verification/gui-live-comparison/deps/libdocker',
     '4e6c007615fe151ea59609d5081175ea1fe8e65b',
     '.verification/gui-live-comparison/libdocker-unix-host.patch'),
]


def git(path, *args, check=True):
    return subprocess.run(['git', '-C', str(path), *args], check=check,
                          capture_output=True, text=True)


def main():
    for url, relative, revision, patch in DEPENDENCIES:
        path = ROOT / relative
        if not path.exists():
            path.mkdir(parents=True)
            git(path, 'init')
            git(path, 'remote', 'add', 'origin', url)
            git(path, 'fetch', '--depth=1', 'origin', revision)
            git(path, 'checkout', '--detach', revision)
        else:
            actual = git(path, 'rev-parse', 'HEAD').stdout.strip()
            if actual != revision:
                raise SystemExit(f'{relative}: expected {revision}, found {actual}; '
                                 'refusing to reset an existing checkout')
        if patch:
            patch_path = str(ROOT / patch)
            pending = git(path, 'apply', '--check', patch_path, check=False)
            if pending.returncode == 0:
                git(path, 'apply', patch_path)
            elif git(path, 'apply', '--reverse', '--check', patch_path,
                     check=False).returncode != 0:
                raise SystemExit(f'{relative}: patch conflicts with local changes')
        print(f'Ready: {relative} @ {revision}')


if __name__ == '__main__':
    main()
