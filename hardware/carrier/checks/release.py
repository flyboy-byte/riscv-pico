#!/usr/bin/env python3
"""The money gate: copy the fab files for revision REV into fab/REV/ only when it is safe to order them.

  release.py REV FILE...     e.g. release.py v1.1.0 out/board-gerbers.zip out/board-bom.csv out/board-cpl.csv

Refuses (exit 1, every reason listed) unless:
  - the git working tree is clean, so the files are exactly a commit;
  - checks/last_run.json passed (none failed or skipped; a check marked "advisory" in checks.json may fail, it is listed), nothing but notes (*.md) changed since the commit it
    ran at, and every checked file still has the hash it was checked with;
  - checks/drift.py reports no hand edits waiting to be folded into the generator;
  - the latest round in AUDIT.md (the highest round number, wherever it sits in the file) names a commit after which only
    notes (*.md), check scripts and reviewers' audit folders changed, and has no open BLOCKER or BUG;
  - REV is not already used (fab/REV/ absent, REV not in STATE.md's "Revisions used" line).
On success writes fab/REV/RELEASE.json (commit, hashes, checks) and reminds you what to record."""
import datetime, hashlib, json, os, re, shutil, subprocess, sys


def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def design_changes(since, audit=False):
    """Files other than notes changed between commit `since` and HEAD; None if `since` is unknown. Reviewers' audit
    folders and check output never count; with audit=True check scripts don't either (the checks gate covers them)."""
    rc, out = sh('git', 'diff', '--name-only', since, 'HEAD')
    if rc:
        return None
    def counts(f):
        dirs = f.split('/')[:-1]
        if f.endswith('.md') or f.endswith('checks/last_run.json') or 'audit' in dirs:
            return False
        if 'checks' in dirs:                      # checks/out/ is check output; the scripts count unless audit=True
            return not audit and 'out' not in dirs
        return True
    return [f for f in out.splitlines() if f and counts(f)]


def latest_round(audit):
    """The section of AUDIT.md for the highest-numbered round; files list rounds newest first or last, so use the number."""
    parts = re.split(r'\n(?=### Round )', audit)[1:]
    num = lambda p: int(re.match(r'### Round (\d+)', p).group(1)) if re.match(r'### Round (\d+)', p) else -1
    return max(parts, key=num) if parts else None


def sha(p):
    try:
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]
    except OSError:
        return 'missing'


def main(rev, files):
    why = []
    rc, head = sh('git', 'rev-parse', '--short', 'HEAD')
    if rc:
        return print('not a git repository: commit the project first') or 1
    rc, dirty = sh('git', 'status', '--porcelain', '--untracked-files=no')
    if dirty:
        why.append('working tree has uncommitted changes:\n    ' + dirty.replace('\n', '\n    '))
    if not files:
        why.append('no fab files given')
    for f in files:
        if not os.path.isfile(f):
            why.append(f'{f}: not found')
    try:
        run = json.load(open('checks/last_run.json'))
        moved = design_changes(run.get('git_head', ''))
        if moved is None or moved:
            why.append(f"design files changed since checks ran at {run.get('git_head')}: run checks/run_all.py"
                       + (f" ({', '.join(moved[:5])})" if moved else ''))
        for x in run['results']:
            if x['status'] == 'fail' and x.get('advisory'):
                print(f"note: advisory check failed (does not block): {x['name']}: {x['advisory']}")
            elif x['status'] != 'pass':
                why.append(f"check {x['status']}: {x['name']}: {x['summary']}")
            for f, h in x['files'].items():
                if sha(f) != h:
                    why.append(f"{f} changed after check '{x['name']}' ran")
    except (OSError, ValueError, KeyError):
        why.append('no valid checks/last_run.json: run checks/run_all.py')
    if os.path.exists('checks/generated.json'):
        rc, out = sh(sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drift.py'), 'check')
        if rc:
            why.append('hand edits not folded into the generator:\n    ' + out.replace('\n', '\n    '))
    try:
        audit = open('AUDIT.md').read()
        last = latest_round(audit)
        if last is None:
            why.append('AUDIT.md has no round')
        else:
            m = re.search(r'Commit:\s*`?([0-9a-f]{7,40})', last)
            moved = design_changes(m.group(1), audit=True) if m else None
            if moved is None or moved:
                why.append(f"design files changed since the audited commit ({m.group(1) if m else 'none named'}): audit again"
                           + (f" ({', '.join(moved[:5])})" if moved else ''))
            for row in re.findall(r'^\|(.+)\|\s*$', last, re.M):
                cells = [c.strip() for c in row.split('|')]
                if len(cells) >= 6 and cells[1].upper() in ('BLOCKER', 'BUG') and not cells[-1].lower().startswith(('fixed', 'accepted')):
                    why.append(f'open {cells[1].upper()} {cells[0]}: status "{cells[-1]}"')
    except OSError:
        why.append('no AUDIT.md')
    used = re.search(r'Revisions used[^:]*:(.*)', open('STATE.md').read()) if os.path.exists('STATE.md') else None
    if os.path.exists(os.path.join('fab', rev)) or (used and re.search(rf'(?<![\w.]){re.escape(rev)}(?![\w.])', used.group(1))):
        why.append(f'revision {rev} is already used; pick the next one')
    if why:
        print(f'REFUSED: revision {rev} is not ready to order')
        for w in why:
            print('  - ' + w)
        return 1
    dst = os.path.join('fab', rev)
    os.makedirs(dst)
    for f in files:
        shutil.copy2(f, dst)
    json.dump({'revision': rev, 'date': datetime.date.today().isoformat(), 'commit': head,
               'files': {os.path.basename(f): sha(f) for f in files}, 'checks': run['results']},
              open(os.path.join(dst, 'RELEASE.json'), 'w'), indent=1)
    print(f'RELEASED {rev} at {head} to {dst}/')
    print(f'Now: fill {dst}/README.md, add {rev} to "Revisions used" in STATE.md, add the order to ORDERS.md, commit today.')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
