"""Collect reproducible coverage fixtures using an existing CLOUD runtime only.

Never downloads/builds SimC. Raw reports remain in the supplied private directory.
Run on the managed cloud host; classification/localization can run without SimC.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile


def collect(archive: Path, binary: Path, output: Path):
    if os.name == 'nt' or not str(binary.resolve()).startswith('/opt/wow-simc/'):
        raise ValueError('requires existing managed cloud runtime')
    from server.app.simulation.readiness import inspect_managed_simc_runtime
    identity = inspect_managed_simc_runtime({'WOW_SIMC_BIN': str(binary)})
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    records = []
    binary_digest = identity.binary_sha256
    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive) as source:
        members = sorted((m for m in source.getmembers() if re.fullmatch(
            r'[^/]+/profiles/MID[12]/MID[12]_[^/]+\.simc', m.name) and m.isfile()), key=lambda m: m.name)
        if not members or len(members) > 256:
            raise ValueError('unexpected profile inventory')
        if any(not member.name.startswith(f'simc-{identity.source_commit}/') for member in members):
            raise ValueError('profile archive does not match managed engine source')
        for member in members:
            profile = source.extractfile(member).read().decode('utf-8')
            # Corpus must be self-contained and may not ask for remote characters.
            if re.search(r'(?m)^\s*(?:input|armory|guild|copy|profileset\..*)\s*=', profile):
                raise ValueError('unsupported profile directive')
            for targets in (1, 5):
                stem = Path(member.name).stem + f'-{targets}'
                report = output / f'{stem}.json'; html = output / f'{stem}.html'
                command = [str(identity.binary_path), '-', 'iterations=100', 'max_time=60', 'vary_combat_length=0.2',
                    'threads=1', 'seed=69299', 'fight_style=Patchwerk', f'desired_targets={targets}',
                    'item_db_source=local', f'json={report},full_states=0', f'html={html}', 'report_details=1']
                try:
                    done = subprocess.run(command, input=profile, encoding='utf-8', capture_output=True,
                        timeout=45, cwd=output)
                    record = {'profile': member.name, 'targets': targets,
                              'profileSha256': hashlib.sha256(profile.encode()).hexdigest(),
                              'returnCode': done.returncode, 'report': report.name,
                              'diagnostic': (done.stdout + done.stderr)[-1200:] if done.returncode else ''}
                    if report.exists():
                        record['reportSha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
                except subprocess.TimeoutExpired:
                    record = {'profile': member.name, 'targets': targets, 'returnCode': None, 'diagnostic': 'timeout'}
                if inspect_managed_simc_runtime({'WOW_SIMC_BIN': str(binary)}) != identity:
                    raise ValueError('managed runtime changed during collection')
                record['runtimeRevision'] = identity.runtime_revision
                record['html'] = html.name
                record['htmlStatus'] = 'present' if html.is_file() and html.stat().st_size <= 16 * 1024 * 1024 else 'missing_or_oversized'
                record['htmlSha256'] = hashlib.sha256(html.read_bytes()).hexdigest() if record['htmlStatus'] == 'present' else None
                records.append(record)
                (output / 'collection.json').write_text(json.dumps({'binarySha256': binary_digest,
                    'runtimeRevision': identity.runtime_revision, 'engineSourceCommit': identity.source_commit,
                    'archiveSha256': archive_digest, 'records': records}, indent=2))
                print(stem, record['returnCode'], flush=True)


def analyze(output: Path):
    from collections import Counter
    from server.app.simulation.report import normalize_simc_report
    from server.app.simulation.report_identity import npc_sources_from_html
    from server.app.simulation.localization import catalog_for_build, localize_report
    collection = json.loads((output / 'collection.json').read_text())
    expected_revision = f'simc:managed:{collection["engineSourceCommit"]}:{collection["binarySha256"]}'
    if not re.fullmatch(r'simc:managed:[a-f0-9]{40}:[a-f0-9]{64}', expected_revision) or collection['runtimeRevision'] != expected_revision:
        raise ValueError('invalid runtime identity')
    records = []; missing = {}; counts = Counter(); latin_labels = []
    for item in collection['records']:
        if item['returnCode'] != 0:
            records.append(item)
            continue
        try:
            if item['runtimeRevision'] != expected_revision:
                raise ValueError('report runtime mismatch')
            if not item['profile'].startswith(f'simc-{collection["engineSourceCommit"]}/'):
                raise ValueError('profile source mismatch')
            path = output / item['report']
            if path.parent.resolve() != output.resolve() or path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('invalid report file')
            raw = path.read_bytes(); data = json.loads(raw)
            if hashlib.sha256(raw).hexdigest() != item['reportSha256']:
                raise ValueError('fixture changed')
            identity = {}
            npcs = {}
            if item['htmlStatus'] == 'present':
                html_path = output / item['html']
                if html_path.parent.resolve() != output.resolve() or html_path.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError('invalid html file')
                html_bytes = html_path.read_bytes()
                if hashlib.sha256(html_bytes).hexdigest() != item['htmlSha256']:
                    raise ValueError('html fixture changed')
                npcs = npc_sources_from_html(html_bytes.decode('utf-8'))
            elif item['htmlStatus'] != 'missing_or_oversized' or item['htmlSha256'] is not None:
                raise ValueError('invalid html status')
            report = normalize_simc_report(raw, expected_actor=data['sim']['players'][0]['name'], identity_sink=identity, npc_sources=npcs)
            names = localize_report(report, identity, catalog_for_build(report['engine']['gameVersion']),
                                    engine_revision=item['runtimeRevision'])
            row_counts = Counter()
            for group in ('abilities', 'buffs'):
                for descriptor, label in zip(identity[group], names[group]):
                    counts[f'{group}.{label["status"]}'] += 1
                    row_counts[f'{group}.{label["status"]}'] += 1
                    if re.search('[A-Za-z]', label['text']):
                        latin_labels.append({'profile': item['profile'], 'token': descriptor['token'], 'text': label['text']})
                    if label['status'] != 'resolved':
                        key = f'{group}:{descriptor["token"]}:{descriptor["spellId"]}:{descriptor["sourceNpcId"]}'
                        missing.setdefault(key, {'identity': descriptor, 'label': label, 'profiles': []})['profiles'].append(Path(item['profile']).stem)
            records.append({**item, 'actor': report['actor'], 'engine': report['engine'], 'metric': report['metric'],
                'counts': dict(row_counts), 'npcSources': npcs, 'catalogRevision': names['catalogRevision'], 'localizationStatus': names['status']})
        except (ValueError, OSError, KeyError) as error:
            records.append({**item, 'analysisError': str(error)})
    summary = {'binarySha256': collection['binarySha256'], 'archiveSha256': collection['archiveSha256'],
               'runtimeRevision': expected_revision, 'engineSourceCommit': collection['engineSourceCommit'],
               'counts': dict(counts), 'records': records, 'missing': missing, 'latinLabels': latin_labels}
    (output / 'coverage.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'profiles': len(records), 'successfulReports': sum('counts' in row for row in records),
        'specializations': sorted({row['actor']['className'] + '/' + row['actor']['specialization'] for row in records if 'actor' in row}),
        'counts': dict(counts), 'uniqueMissing': len(missing)}, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--analyze', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.analyze:
        result = analyze(args.output)
        if any('analysisError' in row for row in result['records']):
            raise SystemExit(1)
    elif args.archive and args.binary:
        collect(args.archive, args.binary, args.output)
    else:
        parser.error('--archive and --binary are required for cloud collection')
