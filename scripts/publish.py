#!/usr/bin/env python3
"""Publish the reviewed Louter source using local CLI authentication.

No OpenClaw state, API keys, or conversation files are read. This script does not
install Louter or restart its services. Network writes happen only after consent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.publish'
OWNER = 'liseman'
REPO = f'{OWNER}/openclaw-louter'
VERSION = json.loads((Path(__file__).resolve().parent.parent / "package.json").read_text())["version"]
TAG = f'v{VERSION}'
PACKAGE = f'@{OWNER}/openclaw-louter'
DESCRIPTION = 'Lite Router for OpenClaw: local-first replies, explicit model routes, multi-model Ask Around, and usage estimates.'

class Publisher:
    def __init__(self):
        WORK.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.log = WORK / f'publish-{time.strftime("%Y%m%d-%H%M%S")}.log'
        self.log.touch(mode=0o600)
        self.state_file = WORK / 'state.json'
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        self.rows = []
        self.stage = 'preflight'
        self.env = {**os.environ, 'GH_HOST':'github.com', 'GH_PAGER':'cat', 'NO_COLOR':'1', 'GIT_TERMINAL_PROMPT':'0'}
        self.claw = []

    def save(self):
        temp = self.state_file.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, indent=2) + '\n')
        temp.chmod(0o600)
        temp.replace(self.state_file)

    def run(self, args, timeout=90, check=True, interactive=False):
        args = list(map(str, args))
        with self.log.open('a') as f:
            f.write('\n$ ' + ' '.join(args) + '\n')
        if interactive:
            # Device codes and browser approval prompts must remain visible.
            code = subprocess.call(args, cwd=ROOT, env=self.env)
            out = ''
        else:
            p = subprocess.Popen(args, cwd=ROOT, env=self.env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, start_new_session=True)
            try:
                out, _ = p.communicate(timeout=timeout)
                code = p.returncode
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    out, _ = p.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    out, _ = p.communicate()
                code = 124
                out = (out or '') + f'\nCommand timed out after {timeout} seconds.\n'
            with self.log.open('a') as f:
                f.write(out[-500000:] + '\n')
        if check and code:
            raise RuntimeError(f'{self.stage}: command failed (exit {code}); see the saved log.')
        return code, out

    def git(self, *args, **kw):
        return self.run(['git', *args], **kw)

    def authenticate(self):
        self.stage = 'Dependencies'
        for tool in ('git', 'node', 'npm', 'gh'):
            if shutil.which(tool):
                continue
            if tool in ('gh', 'node', 'npm') and shutil.which('brew'):
                target = 'gh' if tool == 'gh' else 'node'
                print(f'Installing {target} with Homebrew; output is saved.', flush=True)
                self.run(['brew', 'install', target], timeout=600)
            if not shutil.which(tool):
                raise RuntimeError(f'{tool} is required. Install it and rerun this same file.')
        _, node = self.run(['node','-p','process.versions.node'])
        if int(node.strip().split('.')[0]) < 22:
            raise RuntimeError('Node.js 22 or newer is required. Run on the OpenClaw host with its newer Node installation.')

        self.stage = 'GitHub login'
        code, profile = self.run(['gh','api','user'], check=False)
        if code:
            print('Authorize GitHub CLI in your browser/device flow.', flush=True)
            self.run(['gh','auth','login','--hostname','github.com','--git-protocol','https','--web'], interactive=True)
            _, profile = self.run(['gh','api','user'])
        user = json.loads(profile)
        if user.get('login','').lower() != OWNER:
            raise RuntimeError(f'GitHub CLI is signed in as {user.get("login")}, not {OWNER}. Switch accounts and rerun.')
        self.rows.append(('GitHub account', OWNER))

        self.stage = 'ClawHub CLI'
        # Resolve once, then use the exact same CLI version for every operation.
        version = self.state.get('clawhubCliVersion')
        if not version:
            _, raw = self.run(['npm','view','clawhub','version'], timeout=60)
            version = raw.strip()
            if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', version):
                raise RuntimeError('Could not resolve a concrete ClawHub CLI version.')
            self.state['clawhubCliVersion'] = version
            self.save()
        self.claw = ['npm','exec','--yes',f'--package=clawhub@{version}','--','clawhub']
        self.run([*self.claw,'--help'], timeout=180)
        self.stage = 'ClawHub login'
        code, _ = self.run([*self.claw,'whoami'], check=False)
        if code:
            print(f'Authorize ClawHub as the GitHub account/publisher {OWNER}.', flush=True)
            self.run([*self.claw,'login','--device'], interactive=True)
        # Display the public account identity, never the token.
        self.run([*self.claw,'whoami'], interactive=True)
        self.rows.append(('ClawHub CLI', version))

    def preflight(self):
        self.stage = 'Source and secret checks'
        inventory = WORK / 'source-files.json'
        if not inventory.exists():
            raise RuntimeError('Run the supplied self-contained publish-louter.sh to stage the reviewed release.')
        files = json.loads(inventory.read_text())
        suspicious = [
            re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
            re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
            re.compile(r'\bgithub_pat_[A-Za-z0-9_]{35,}\b'),
            re.compile(r'\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{32,}\b'),
            re.compile(r'\bAKIA[A-Z0-9]{16}\b')
        ]
        for rel, digest in files.items():
            p = ROOT / rel
            if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(ROOT):
                raise RuntimeError(f'Unexpected source entry: {rel}')
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError(f'Release source changed since staging: {rel}. No unreviewed changes will be uploaded.')
            text = data.decode('utf-8')
            if any(pattern.search(text) for pattern in suspicious):
                raise RuntimeError(f'Possible credential in {rel}; inspect locally before publishing.')
        self.rows.append(('Source scan', f'PASS; {len(files)} reviewed text files, no credential-pattern matches'))
        self.stage = 'Offline tests'
        self.run(['node','--test',*sorted(str(p) for p in (ROOT/'test').glob('*.test.js'))], timeout=45)
        self.rows.append(('Code tests','PASS'))
        self.stage = 'ClawHub static validation'
        _, out = self.run([*self.claw,'package','validate',str(ROOT),'--json'], timeout=180)
        (WORK/'clawhub-validation.json').write_text(out)
        self.rows.append(('ClawHub validation','PASS (warnings, if any, are in the saved report)'))
        return sorted(files)

    def github(self, files):
        self.stage = 'Local Git release'
        if not (ROOT/'.git').exists():
            self.git('init','-b','main')
            self.git('config','user.name',OWNER)
            self.git('config','user.email',f'546471+{OWNER}@users.noreply.github.com')
            self.git('config','core.hooksPath','/dev/null')
            self.git('config','credential.https://github.com.helper','')
            self.git('config','--add','credential.https://github.com.helper','!gh auth git-credential')
            self.git('add','--',*files)
            self.git('-c','commit.gpgsign=false','commit','-m',f'Release Louter {VERSION} preview')
        else:
            _, dirty = self.git('status','--porcelain')
            if dirty.strip():
                raise RuntimeError('The publishing checkout has uncommitted changes; refusing to publish them automatically.')
        _, commit = self.git('rev-parse','HEAD')
        commit = commit.strip()
        _, tree = self.git('ls-tree','-r','--name-only','HEAD')
        if set(tree.splitlines()) != set(files):
            raise RuntimeError('Git commit files differ from the reviewed release inventory.')
        self.stage = 'GitHub repository'
        code, raw = self.run(['gh','api',f'repos/{REPO}'], check=False)
        if code:
            if '404' not in raw:
                raise RuntimeError('Repository lookup failed for a reason other than not-found; no repository was created.')
            self.run(['gh','repo','create',REPO,'--public','--description',DESCRIPTION,'--disable-wiki'])
            _, raw = self.run(['gh','api',f'repos/{REPO}'])
        repository = json.loads(raw)
        if repository.get('private') or repository.get('full_name','').lower() != REPO:
            raise RuntimeError('Existing repository is private or has the wrong identity. It was not modified.')
        clone_url = repository['clone_url']
        code, remote = self.git('remote','get-url','origin',check=False)
        if code:
            self.git('remote','add','origin',clone_url)
        elif remote.strip() != clone_url:
            raise RuntimeError('Existing origin does not match the intended GitHub repository.')
        _, heads = self.git('ls-remote','--heads','origin')
        for line in heads.splitlines():
            sha, ref = line.split()
            if sha != commit or ref != 'refs/heads/main':
                raise RuntimeError('The existing repository contains different history. No force-push or overwrite was attempted.')
        self.git('push','--set-upstream','origin','HEAD:main',timeout=120)
        _, verify = self.run(['gh','api',f'repos/{REPO}/commits/main'])
        if json.loads(verify)['sha'] != commit:
            raise RuntimeError('GitHub commit verification failed.')
        self.state['commit'] = commit
        self.state['githubUrl'] = repository['html_url']
        self.save()
        self.rows.append(('GitHub repository',repository['html_url']))
        self.stage = 'Release tag'
        code, tag = self.git('rev-parse','--verify',f'{TAG}^{{commit}}',check=False)
        if code:
            self.git('tag',TAG,commit)
        elif tag.strip() != commit:
            raise RuntimeError('Existing local release tag points to different source.')
        self.git('push','origin',f'refs/tags/{TAG}',timeout=120)
        self.stage = 'Pack release artifact'
        artifacts = WORK/'artifacts'; artifacts.mkdir(exist_ok=True)
        _, packed = self.run(['npm','pack','--ignore-scripts','--json','--pack-destination',str(artifacts)],timeout=90)
        package = json.loads(packed)[0]
        if package['name'] != PACKAGE or package['version'] != VERSION:
            raise RuntimeError('Packed package identity mismatch.')
        artifact = artifacts/package['filename']
        sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
        (artifacts/'SHA256SUMS.txt').write_text(f'{sha256}  {artifact.name}\n')
        self.state['artifactSha256'] = sha256
        self.save()
        self.stage = 'GitHub prerelease'
        code, release = self.run(['gh','release','view',TAG,'--repo',REPO,'--json','url,isDraft,isPrerelease'],check=False)
        if code:
            self.run(['gh','release','create',TAG,str(artifact),str(artifacts/'SHA256SUMS.txt'),
                      '--repo',REPO,'--verify-tag','--prerelease',
                      '--title',f'Louter {VERSION} — Lite Router for OpenClaw',
                      '--notes-file',str(ROOT/'RELEASE_NOTES.md')],timeout=120)
            _, release = self.run(['gh','release','view',TAG,'--repo',REPO,'--json','url,isDraft,isPrerelease'])
        release = json.loads(release)
        if release.get('isDraft'):
            raise RuntimeError('Existing release is a draft. It was not silently published.')
        self.state['releaseUrl'] = release['url']; self.save()
        self.rows.append(('GitHub prerelease',release['url']))
        return artifact, commit

    def clawhub(self, artifact, commit):
        self.stage = 'ClawHub publication check'
        verify = [*self.claw,'package','verify',str(artifact),'--package',PACKAGE,'--version',VERSION,'--json']
        code, out = self.run(verify,timeout=60,check=False)
        if code == 0:
            self.state['clawhubStatus'] = 'published-and-verified'; self.save()
            self.rows.append(('ClawHub','PUBLISHED; exact artifact verified'))
            return
        if self.state.get('clawhubSubmitted'):
            self.run([*self.claw,'package','moderation-status',PACKAGE,'--json'],check=False)
            raise RuntimeError('A ClawHub submission was already started; publication is not yet verified. Inspect the saved attempt/moderation status instead of submitting again.')
        common = [*self.claw,'package','publish',str(artifact),'--family','code-plugin',
                  '--owner',OWNER,'--source-repo',f'https://github.com/{REPO}',
                  '--source-commit',commit,'--source-ref',TAG,
                  '--topics','local-llm,model-routing,model-council','--json']
        self.stage = 'ClawHub dry run'
        _, preview = self.run([*common,'--dry-run'],timeout=120)
        (WORK/'clawhub-dry-run.json').write_text(preview)
        self.rows.append(('ClawHub dry run','PASS'))
        self.stage = 'ClawHub submission / review'
        self.state['clawhubSubmitted'] = True; self.save()
        print('GitHub is published. Submitting to ClawHub; waiting up to three minutes for registry review.',flush=True)
        code, result = self.run([*common,'--wait','--wait-timeout','180'],timeout=220,check=False)
        (WORK/'clawhub-result.json').write_text(result)
        if code:
            self.state['clawhubStatus']='not-confirmed'; self.save()
            self.rows.append(('ClawHub','NOT CONFIRMED — may be pending review or blocked; see clawhub-result.json'))
            return False
        # --wait success means the release became public; independently compare bytes.
        self.run(verify,timeout=60)
        self.state['clawhubStatus']='published-and-verified'; self.save()
        self.rows.append(('ClawHub','PUBLISHED; exact artifact verified'))
        _, inspected = self.run([*self.claw,'package','inspect',PACKAGE,'--version',VERSION,'--json'],check=False)
        (WORK/'clawhub-inspect.json').write_text(inspected)
        return True

    def summary(self, error=None):
        print('\n=============== LOUTER PUBLISH SUMMARY ===============')
        for label,value in self.rows:
            print(f'{label:21} {value}')
        if error:
            print('STOPPED:             ', str(error))
        print(f'Package:              {PACKAGE}@{VERSION}')
        print(f'Publishing checkout:  {ROOT}')
        print(f'Logs / registry JSON: {WORK}')
        if self.state.get('clawhubStatus')=='published-and-verified':
            print(f'Install:              openclaw plugins install clawhub:{PACKAGE}')
        else:
            print('ClawHub public availability is NOT confirmed.')
        print('No live OpenClaw settings or credentials were changed.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--yes',action='store_true',help='Approve public publication without the initial prompt; login approvals remain interactive.')
    args=parser.parse_args()
    os.umask(0o077)
    pub=Publisher()
    print(f'Louter {VERSION}: publish source to public GitHub {REPO} and ClawHub {PACKAGE}.')
    print('This uploads the release source, creates a public preview release, and submits the package for registry review.')
    print('Missing GitHub/Node CLIs may be installed with Homebrew. ClawHub CLI is fetched from npm at one recorded version.')
    if not args.yes and input('Proceed? [y/N] ').strip().lower()!='y':
        print('Cancelled. No publication attempted.');return 0
    try:
        pub.authenticate()
        files=pub.preflight()
        artifact,commit=pub.github(files)
        ok=pub.clawhub(artifact,commit)
        pub.summary()
        return 0 if ok is not False else 2
    except (Exception,KeyboardInterrupt) as error:
        pub.summary(error or 'Interrupted by user.')
        return 1

if __name__=='__main__':
    sys.exit(main())
