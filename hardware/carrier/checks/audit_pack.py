#!/usr/bin/env python3
"""Build a read-only audit pack for an independent reviewer (another model, a person) on this commit.

  audit_pack.py REV [FILE[=NAME]...]    FILEs: BOM, CPL, Gerber zip, board/schematic files, datasheets to include;
                                        =NAME renames the copy (two files with the same basename must be renamed)

Writes audit/REV-DATE/ with PROMPT.md (paste this first), the hand-off from AUDIT.md, REQUIREMENTS.md (incl. the
bring-up tests), pinmap.csv, the last check results, renders/REV/*, and the given files, all read-only, plus INDEX.md
(each pack file and where it came from). If review/PROMPT.md exists it replaces the built-in prompt ({rev}, {head}).
Bring the reviewer's findings back into AUDIT.md as a new round naming the auditor and this commit."""
import datetime, glob, os, re, shutil, stat, subprocess, sys

PROMPT = """# Independent PCB audit: {rev} at commit {head}

You are auditing a printed circuit board before it is ordered. You have only the files in this folder; you
did not design it. Don't trust the designer's conclusions; check from the files and first principles.

Read in this order: HANDOFF.md (what the board is, what changed, what to check first, what is already known and
accepted), REQUIREMENTS.md (including the numbered bring-up tests that define "working"), pinmap.csv, the check
results, then the fab files and pictures.

Report:
1. Verdict first: "Would I order these files as they are?" yes / no, one sentence why.
2. Findings table: ID | Severity | Location | Evidence (numbers) | Smallest fix
   Severity: BLOCKER = don't order; BUG = wrong but workable; RISK = could bite (state the condition); NOTE.
   Location = file and line, or reference designator and coordinates.
3. What you checked and found correct.
4. What you could not check, and what you would need to.
Don't re-report items listed as known and accepted.
"""


def main(rev, files):
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip() or 'no-git'
    dst = os.path.join('audit', f'{rev}-{datetime.date.today().isoformat()}')
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(dst):  # rebuilding the same day: make the old copies writable again
        os.chmod(os.path.join(dst, f), stat.S_IRUSR | stat.S_IWUSR)
    prompt = open('review/PROMPT.md').read() if os.path.exists('review/PROMPT.md') else PROMPT
    open(os.path.join(dst, 'PROMPT.md'), 'w').write(prompt.replace('{rev}', rev).replace('{head}', head))
    audit = open('AUDIT.md').read() if os.path.exists('AUDIT.md') else ''
    m = re.search(r'## Hand-off.*?(?=\n## )', audit, re.S)
    open(os.path.join(dst, 'HANDOFF.md'), 'w').write((m.group(0) if m else '## Hand-off\n(missing in AUDIT.md: fill it first)') + '\n')
    picked = ['REQUIREMENTS.md', 'pinmap.csv', 'checks/last_run.json'] + sorted(glob.glob(f'renders/{rev}/*')) + files
    missing, names = [], {}
    for f in picked:
        src, _, name = f.partition('=')
        name = name or os.path.basename(src)
        if name in names or name in ('PROMPT.md', 'HANDOFF.md', 'INDEX.md'):
            sys.exit(f'audit pack: two files would both be {name} ({names.get(name, "built-in")}, {src}): rename one with =NAME')
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst, name))
            names[name] = src
        else:
            missing.append(src)
    idx = [f'# Pack index: {rev} at commit {head}', '', '| Pack file | Copied from (repo path, relative to work/) |', '| --- | --- |',
           '| PROMPT.md | the reviewer prompt |', '| HANDOFF.md | the "Hand-off" section of AUDIT.md |']
    idx += [f'| {n} | `{s}` |' for n, s in names.items()]
    open(os.path.join(dst, 'INDEX.md'), 'w').write('\n'.join(idx) + '\n')
    for f in os.listdir(dst):
        p = os.path.join(dst, f)
        os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    print(f'audit pack: {dst}/ ({len(os.listdir(dst))} files, read-only). Paste PROMPT.md first, then attach the rest.')
    for f in missing:
        print(f'  not included (not found): {f}')
    if not m or re.search(r'<[^>\n]+>', m.group(0)):
        print('  WARNING: the hand-off in AUDIT.md still has <placeholders>; fill it before sending')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
