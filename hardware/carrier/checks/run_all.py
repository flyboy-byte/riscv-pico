#!/usr/bin/env python3
"""Run every check in checks/checks.json from the project root, record results, and rewrite the checks table in
STATE.md (between <!-- checks:start --> and <!-- checks:end -->). Exit 1 if any check fails.

checks.json: [{"name": "CPL vs board", "cmd": ["python3", "checks/cpl_vs_board.py", "board.kicad_pcb", "cpl.csv"],
               "files": ["board.kicad_pcb", "cpl.csv"]}, ...]
Each check prints its result on its last line and exits 0 (pass) or non-zero (fail). A command that is not
installed, or a check that exits 77 (kicad_check.py without KiCad), is recorded as "skipped", never as passed.

  run_all.py --report DIR    reviewer mode: results and DRC/ERC reports go to DIR; STATE.md, checks/last_run.json and
                             checks/out/ are left alone"""
import datetime, hashlib, json, os, re, shutil, subprocess, sys


def sha(path):
    try:
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:12]
    except OSError:
        return 'missing'


def head():
    r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else 'no-git'


def main():
    report = sys.argv[sys.argv.index('--report') + 1] if '--report' in sys.argv else None
    env = dict(os.environ)
    if report:
        os.makedirs(report, exist_ok=True)
        env['CHECKS_REPORT_DIR'] = os.path.abspath(report)   # kicad_check.py writes its reports there
    checks = json.load(open('checks/checks.json'))
    today = datetime.date.today().isoformat()
    results = []
    for c in checks:
        files = {f: sha(f) for f in c.get('files', [])}
        if not shutil.which(c['cmd'][0]):
            results.append({'name': c['name'], 'status': 'skipped', 'summary': f"{c['cmd'][0]} not installed", 'files': files})
            continue
        r = subprocess.run(c['cmd'], capture_output=True, text=True, env=env)
        lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and ': Debug: ' not in l]
        results.append({'name': c['name'], 'status': 'pass' if r.returncode == 0 else 'skipped' if r.returncode == 77 else 'fail',
                        'summary': lines[-1] if lines else f'exit {r.returncode}', 'files': files})
        if c.get('advisory'):
            results[-1]['advisory'] = c['advisory']   # shown, never blocks release.py
    run = {'date': today, 'git_head': head(), 'results': results}
    json.dump(run, open(os.path.join(report, 'last_run.json') if report else 'checks/last_run.json', 'w'), indent=1)
    rows = ['| Check | Result | Summary | Date | Files (sha256/12) |', '| --- | --- | --- | --- | --- |']
    for x in results:
        rows.append(f"| {x['name']} | {x['status'].upper()}{' (advisory)' if x.get('advisory') else ''} | {x['summary'].replace('|', '/')} | {today} | "
                    + ', '.join(f'`{os.path.basename(f)}` {h}' for f, h in x['files'].items()) + ' |')
    table = '<!-- checks:start -->\n' + '\n'.join(rows) + f'\n\nWritten by `checks/run_all.py` at commit {run["git_head"]}. Don\'t edit by hand.\n<!-- checks:end -->'
    if os.path.exists('STATE.md') and not report:
        s = open('STATE.md').read()
        if '<!-- checks:start -->' in s:
            s = re.sub(r'<!-- checks:start -->.*?<!-- checks:end -->', lambda _: table, s, flags=re.S)
            open('STATE.md', 'w').write(s)
    for x in results:
        print(f"{x['status'].upper():7} {x['name']}: {x['summary']}" + (f"  [advisory: {x['advisory']}]" if x.get('advisory') else ''))
    failed = [x for x in results if x['status'] == 'fail' and not x.get('advisory')]
    adv = sum(x['status'] == 'fail' and bool(x.get('advisory')) for x in results)
    print(f"{len(results)} checks, {len(failed)} failed, {adv} advisory failed, {sum(x['status'] == 'skipped' for x in results)} skipped")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
