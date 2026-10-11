"""Create source-only ZIPs from an explicit release file list."""
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/apple-calendar-mcp'
FILES = ['plugin.json', 'mcp.json', 'README.md',
         'scripts/setup.sh', 'scripts/build.sh', 'scripts/start.sh',
         'server/CalendarCore.swift', 'server/CalendarMCP.swift', 'server/EventKitSource.swift',
         'server/Info.plist', 'server/client.py', 'tests/FixtureSource.swift', 'tests/test_server.py', 'tests/test_startup.py',
         'media/apple-calendar-mcp.mp4', 'media/apple-calendar-mcp.gif',
         'media/ATTRIBUTION.md', 'media/FONT-LICENSE.txt']
REPO_FILES = ['README.md', '.gitignore', '.agents/plugins/marketplace.json', 'scripts/package.py']


def package(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = PLUGIN / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or linked release file: {name}')
    for name in REPO_FILES:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or linked repository file: {name}')
    for filename, repository in [('apple-calendar-mcp-plugin.zip', False), ('apple-calendar-mcp-source.zip', True)]:
        with zipfile.ZipFile(destination / filename, 'w', zipfile.ZIP_DEFLATED) as archive:
            prefix = 'apple-calendar-mcp/plugins/apple-calendar-mcp' if repository else 'apple-calendar-mcp'
            for name in FILES:
                archive.write(PLUGIN / name, f'{prefix}/{name}')
            if repository:
                for name in REPO_FILES:
                    archive.write(ROOT / name, f'apple-calendar-mcp/{name}')
        print(destination / filename)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 scripts/package.py OUTPUT_DIRECTORY')
    package(Path(sys.argv[1]).resolve())
