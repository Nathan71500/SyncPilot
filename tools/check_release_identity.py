"""Block deployment wrappers with an identity different from the source."""
import argparse
import json
import zipfile
from pathlib import Path


def check(archive, target=None):
    with zipfile.ZipFile(archive) as z:
        roots = [n for n in z.namelist() if n.endswith('/plugin.json') and '/.codex-plugin/' not in n]
        if roots != ['syncpilot/plugin.json']:
            raise ValueError('Exactly one SyncPilot root manifest required')
        root = json.loads(z.read(roots[0]))
        overlay = json.loads(z.read('syncpilot/.codex-plugin/plugin.json'))
        if root['name'] != 'syncpilot' or overlay['name'] != 'syncpilot' or root['version'] != overlay['version']:
            raise ValueError('Source and deployment identity must be SyncPilot')
        skills = {n.split('/')[2] for n in z.namelist() if n.startswith('syncpilot/skills/') and n.endswith('/SKILL.md')}
        expected = {'syncpilot-init', 'syncpilot-codex', 'syncpilot-work', 'syncpilot-dc', 'syncpilot-decisions', 'syncpilot-persistence'}
        if skills != expected or any(n.startswith('syncpilot/skills/project-sync-') for n in z.namelist()):
            raise ValueError('Only canonical SyncPilot skills may be installed')
        if target is not None and target.get('name') != root['name']:
            raise ValueError('Immutable backend name: create a new SyncPilot identity at checkpoint, never rename the deployment wrapper')
        return {'name': root['name'], 'version': root['version'], 'skills': sorted(skills), 'publication_action': 'CREATE_NEW_IDENTITY_AT_CHECKPOINT' if target is None else 'UPDATE_MATCHING_IDENTITY'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--target-metadata', type=Path)
    a = p.parse_args()
    try:
        print(json.dumps(check(a.archive, json.loads(a.target_metadata.read_bytes()) if a.target_metadata else None)))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        p.exit(2, 'SyncPilot release blocked: ' + str(exc) + '\n')
