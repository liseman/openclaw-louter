#!/usr/bin/env python3
import sys as _louter_sys
_louter_sys.dont_write_bytecode = True
"""Explicitly opt-in public GitHub savings reports. No telemetry from the reply hook."""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
sys.dont_write_bytecode = True
from telemetry_schema import REPOSITORY, TITLE, encode, project, zero

ROOT = Path(__file__).resolve().parents[1]
DAY = 86400
CONSENT = '''Share aggregate Louter savings publicly on GitHub? (OFF by default)
Destination: https://github.com/liseman/openclaw-louter/issues
Reports include a random installation ID, Louter version, reporting date and
lifetime aggregate counters, including already accumulated local totals.
Your GitHub USERNAME and issue/edit timestamps are PUBLIC. This is NOT anonymous.
No prompts, answers, session IDs, provider credentials, machine names, model names,
or local paths are included. GitHub receives normal connection metadata.
One issue per installation is updated at most once per 24 hours automatically.
The dashboard reports self-reported usage and estimated tokens, NOT verified bill
savings. Turning off stops uploads; prior issues/history remain public. Withdraw
removes a report from current totals but cannot erase GitHub history or copies.
This uses your existing gh login; no shared publisher token is installed.'''


def state_root(value=None):
    if value or os.environ.get('OPENCLAW_STATE_DIR'):
        return Path(value or os.environ['OPENCLAW_STATE_DIR']).expanduser().resolve()
    profile = os.environ.get('OPENCLAW_PROFILE', '')
    if profile and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', profile):
        raise ValueError('Invalid OPENCLAW_PROFILE')
    home = Path(os.environ.get('OPENCLAW_HOME', str(Path.home()))).expanduser()
    return (home / ('.openclaw-' + profile if profile else '.openclaw')).resolve()


def read_json(path, default=None):
    try:
        if path.stat().st_size > 8_000_000:
            raise ValueError('Local file too large')
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write('\n')
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


@contextlib.contextmanager
def lock(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / '.lock').open('a') as handle:
        os.chmod(root / '.lock', 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def gh_api(endpoint, method='GET', data=None, gh='gh'):
    # Fixed public github.com API, argv arrays, stdin JSON, never shell=True.
    command = [gh, 'api', '--hostname', 'github.com', '--method', method,
               '-H', 'Accept: application/vnd.github+json', endpoint]
    if data is not None:
        command += ['--input', '-']
    env = {**os.environ, 'GH_PROMPT_DISABLED': '1', 'GH_PAGER': 'cat'}
    result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                            text=True, capture_output=True, timeout=30, env=env)
    if result.returncode:
        # Never echo API responses/credentials into timers or compact diagnostics.
        raise RuntimeError(f'GitHub API failed (exit {result.returncode}); check gh auth status')
    return json.loads(result.stdout) if result.stdout.strip() else None


def current_stats(state):
    return read_json(state / 'louter/stats.json',
                     {'version': 1, 'since': 'no-stats-yet', 'days': {}})


def preview(state, config=None):
    config = config if config is not None else read_json(state / 'louter/telemetry/config.json', {})
    checkpoint = project(current_stats(state), config.get('checkpoint'))
    version = json.loads((ROOT / 'package.json').read_text())['version']
    payload = {'schema': 1, 'install_id': config.get('install_id', 'created-only-after-opt-in'),
               'sequence': config.get('sequence', 0) + 1, 'louter_version': version,
               'updated': dt.datetime.now(dt.timezone.utc).date().isoformat(),
               'withdrawn': False, 'totals': checkpoint['totals']}
    return payload, checkpoint


def timer_name(state):
    return 'louter-public-stats-' + hashlib.sha256(str(state).encode()).hexdigest()[:12]


def unit_quote(value):
    # systemd quoting is not shell quoting; protect specifiers and env expansion.
    value = str(value)
    if '\n' in value or '\r' in value:
        raise ValueError('Newline in timer path')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def schedule(state, enable):
    name = timer_name(state)
    command = shutil.which('systemctl')
    if not command:
        if enable:
            raise RuntimeError('Automatic reporting needs systemd-user; use on --manual instead')
        return
    if enable:
        directory = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'systemd/user'
        directory.mkdir(parents=True, exist_ok=True)
        invocation = ' '.join(unit_quote(x) for x in [sys.executable, '-B', Path(__file__).resolve(),
                                  '--state-dir', state, 'send', '--due'])
        (directory / (name + '.service')).write_text(
            '[Unit]\nDescription=Opt-in public Louter savings report\n'
            '[Service]\nType=oneshot\nUMask=0077\nTimeoutStartSec=180\n'
            'ExecStart=' + invocation + '\n')
        (directory / (name + '.timer')).write_text(
            '[Unit]\nDescription=Daily opt-in Louter savings report\n'
            '[Timer]\nOnCalendar=daily\nRandomizedDelaySec=1h\nPersistent=true\n'
            '[Install]\nWantedBy=timers.target\n')
        subprocess.run([command, '--user', 'daemon-reload'], check=True, capture_output=True, timeout=15)
        subprocess.run([command, '--user', 'enable', '--now', name + '.timer'],
                       check=True, capture_output=True, timeout=15)
    else:
        subprocess.run([command, '--user', 'disable', '--now', name + '.timer'],
                       check=False, capture_output=True, timeout=15)


def find_issue(config, api):
    endpoint = f'repos/{REPOSITORY}/issues'
    number = config.get('issue_number')
    if number:
        row = api(endpoint + '/' + str(int(number)))
        if row.get('user', {}).get('id') != config['github_user_id'] or row.get('title') != TITLE + config['install_id']:
            raise RuntimeError('Saved issue identity changed; refusing to overwrite it')
        return row
    # Recover from a lost POST response. Do not create another issue blindly.
    for page in range(1, 51):
        rows = api(endpoint + f'?state=all&creator={config["github_login"]}&per_page=100&page={page}')
        for row in rows:
            if ('pull_request' not in row and row.get('user', {}).get('id') == config['github_user_id']
                    and row.get('title') == TITLE + config['install_id']):
                return row
        if len(rows) < 100:
            return None
    raise RuntimeError('Issue recovery search incomplete; refusing a duplicate submission')


def send(state, due=False, api=None, now=None):
    folder = state / 'louter/telemetry'
    file = folder / 'config.json'
    # Disabled path creates nothing and performs no network/auth probe.
    if not read_json(file, {}).get('enabled'):
        return 'OFF: no network request'
    with lock(folder):
        config = read_json(file, {})
        if not config.get('enabled'):
            return 'OFF: no network request'
        now = time.time() if now is None else now
        if now - config.get('last_attempt', 0) < DAY:
            return 'NOT DUE: at most one reporting attempt per 24 hours'
        if config.get('consent_version') != 1:
            raise RuntimeError('Consent version changed; opt in again')
        api = api or (lambda endpoint, method='GET', data=None: gh_api(endpoint, method, data, config['gh']))
        config['last_attempt'] = now
        atomic(file, config)  # Rate-limit failures too; never hammer GitHub.
        user = api('user')
        if user.get('id') != config['github_user_id']:
            raise RuntimeError('gh account changed; disable/re-enable telemetry to consent to this account')
        config['github_login'] = user['login']
        payload, checkpoint = preview(state, config)
        body = encode(payload)
        # Sampling is durable even if the network reply is lost.
        config.update(checkpoint=checkpoint, sequence=payload['sequence'])
        atomic(file, config)
        row = find_issue(config, api)
        if row and row.get('state') == 'closed':
            config['enabled'] = False
            atomic(file, config)
            return 'OFF: public report was closed; not reopening it automatically'
        request = {'title': TITLE + config['install_id'], 'body': body}
        if row:
            number = int(row['number'])
            api(f'repos/{REPOSITORY}/issues/{number}', 'PATCH', request)
        else:
            row = api(f'repos/{REPOSITORY}/issues', 'POST', request)
            number = int(row['number'])
        config.update(issue_number=number, last_success=now)
        atomic(file, config)
        return f'REPORTED: https://github.com/{REPOSITORY}/issues/{number}'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', help='Explicit OpenClaw state root; otherwise respects profile/state environment')
    sub = parser.add_subparsers(dest='command', required=True)
    on = sub.add_parser('on'); on.add_argument('--yes', action='store_true'); on.add_argument('--manual', action='store_true')
    for name in ('off', 'status', 'preview'):
        sub.add_parser(name)
    reporting = sub.add_parser('send'); reporting.add_argument('--due', action='store_true')
    withdraw = sub.add_parser('withdraw'); withdraw.add_argument('--yes', action='store_true')
    args = parser.parse_args(argv)
    state = state_root(args.state_dir)
    file = state / 'louter/telemetry/config.json'
    config = read_json(file, {})
    if args.command == 'preview':
        payload, _ = preview(state, config)
        print(json.dumps({'destination': REPOSITORY, 'public_github_username': config.get('github_login', 'shown at opt-in'),
                          'payload': payload}, indent=2))
        return 0
    if args.command == 'status':
        print(json.dumps({'enabled': config.get('enabled', False), 'automatic_daily': config.get('automatic_daily', False),
                          'repository': REPOSITORY, 'github_login': config.get('github_login'),
                          'issue_number': config.get('issue_number'), 'last_success': config.get('last_success'),
                          'privacy': 'Public, GitHub-account-linked; not anonymous'}, indent=2))
        return 0
    if args.command == 'send':
        print(send(state, args.due)); return 0
    if args.command == 'on':
        print(CONSENT)
        if not args.yes and (not sys.stdin.isatty() or input('\nOpt in to public reporting? [y/N] ').strip().lower() != 'y'):
            print('UNCHANGED: no reporting enabled'); return 0
        gh = shutil.which('gh')
        if not gh:
            raise RuntimeError('Install GitHub CLI and run gh auth login first; no account was changed')
        user = gh_api('user', gh=gh)
        if not isinstance(user.get('id'), int) or not re.fullmatch(r'[a-zA-Z0-9-]+', user.get('login', '')):
            raise RuntimeError('Could not verify GitHub account')
        print('Public report author:', user['login'])
        if not args.yes and input('Confirm this public GitHub identity? [y/N] ').strip().lower() != 'y':
            print('UNCHANGED'); return 0
        with lock(file.parent):
            config = read_json(file, {})
            if config.get('withdrawn') or (config.get('github_user_id') and config['github_user_id'] != user['id']):
                raise RuntimeError('Existing withdrawn/other-account record: keep it for audit; choose a new profile for a new installation')
            config.update(enabled=False, consent_version=1, install_id=config.get('install_id') or str(uuid.uuid4()),
                          github_user_id=user['id'], github_login=user['login'], gh=gh,
                          automatic_daily=not args.manual)
            atomic(file, config)
            try:
                schedule(state, not args.manual)
            except (OSError, subprocess.SubprocessError, RuntimeError):
                config['automatic_daily'] = False
                atomic(file, config)
                raise RuntimeError('Timer setup failed; reporting remains OFF. Retry on --manual or fix systemd-user')
            config['enabled'] = True
            atomic(file, config)
        print('ON: ' + ('manual reporting' if args.manual else 'daily user timer installed') + '; no statistics sent yet')
        print('Review with telemetry preview, then telemetry send for the first report.')
        return 0
    if args.command in ('off', 'withdraw'):
        with lock(file.parent):
            config = read_json(file, {})
            config['enabled'] = False
            config['automatic_daily'] = False
            atomic(file, config)
        try:
            schedule(state, False)
        except (OSError, subprocess.SubprocessError):
            print('WARN: timer disable failed; disabled consent still blocks uploads')
        print('OFF: future uploads disabled. Existing public issues/history are not erased.')
        if args.command == 'off':
            return 0
        if not args.yes and (not sys.stdin.isatty() or input('Withdraw the public report from current totals? [y/N] ').strip().lower() != 'y'):
            return 0
        if not config.get('install_id'):
            print('No opted-in report exists'); return 0
        api = lambda endpoint, method='GET', data=None: gh_api(endpoint, method, data, config['gh'])
        if api('user').get('id') != config['github_user_id']:
            raise RuntimeError('Use the GitHub account that created this report')
        row = find_issue(config, api)
        if row:
            payload = {'schema': 1, 'install_id': config['install_id'],
                       'sequence': config.get('sequence', 0) + 1,
                       'louter_version': json.loads((ROOT / 'package.json').read_text())['version'],
                       'updated': dt.datetime.now(dt.timezone.utc).date().isoformat(),
                       'withdrawn': True, 'totals': zero()}
            api(f'repos/{REPOSITORY}/issues/{int(row["number"])}', 'PATCH',
                {'body': encode(payload), 'state': 'closed'})
        config['withdrawn'] = True
        atomic(file, config)
        print('WITHDRAWN: excluded on next dashboard rebuild; historical copies may remain')
        return 0
    return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        print('TELEMETRY: FAILED — ' + str(error), file=sys.stderr)
        raise SystemExit(1)
