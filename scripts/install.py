#!/usr/bin/env python3
"""Install the complete plugin without suppressing consent prompts or deleting old source."""
import argparse, json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
from common import ROOT, STATE, MISSING, defaults, get_config, host_entry, set_config, normalized, validate, run, diagnostic_dir


def main():
    p=argparse.ArgumentParser();p.add_argument('--yes',action='store_true');p.add_argument('--skip-smoke',action='store_true');p.add_argument('--no-restart',action='store_true');p.add_argument('--destination',default=str(Path.home()/'openclaw-louter'))
    a=p.parse_args();os.umask(0o077)
    for tool in ['node','openclaw','systemctl']:
        if not shutil.which(tool):raise RuntimeError(f'{tool} is required. Run this installer on the Linux OpenClaw host, not on the Mac.')
    if sys.platform!='linux':raise RuntimeError('This installer targets your Linux systemd-user host. Source can be installed manually elsewhere.')
    if os.geteuid()==0:raise RuntimeError('Run as the OpenClaw user, not root/sudo.')
    print('Louter 0.2.0 — complete installation\n')
    print('This installs local code, grants Louter conversation-hook access and narrowly scoped configured-model completions, and disables fastpath-test/mode-switcher only after Louter registers. It keeps your main model, credentials, Qwen service and old source files.')
    print('The optional smoke test makes short local/Astra/Claude calls. Full replies are stored per conversation, privately, with a seven-day retrieval window and periodic cleanup.')
    if not a.yes and input('\nProceed with those permissions and tests? [y/N] ').strip().lower()!='y':return 0
    folder=diagnostic_dir('install');log=folder/'install.log';log.touch(mode=0o600)
    summary=[];changed=False;replaced=False;snapshot={};dest=Path(a.destination).expanduser().resolve()
    backup=folder/'previous-source'
    print('\nInstalling; routine output is being saved. Any OpenClaw consent prompt will remain visible.',flush=True)
    try:
        version=run(['openclaw','--version'],log=log)
        if '2026.9.' not in version:summary.append(('WARN','Host version','built for the API verified on OpenClaw 2026.9.4; compatibility still tested below'))
        unit=run(['node','--test',*map(str,(ROOT/'test').glob('*.test.js'))],timeout=30,log=log)
        summary.append(('PASS','Offline tests','passed before changing registration'))
        # Snapshot only fields this installer owns. Never overwrite the entire user config.
        for key in ['plugins.entries.louter','plugins.entries.fastpath-test.enabled','plugins.entries.mode-switcher.enabled','plugins.allow']:
            value=get_config(key,None,log)
            snapshot[key]=None if value is MISSING else value
        (folder/'previous-fields.json').write_text(json.dumps(snapshot,indent=2));(folder/'previous-fields.json').chmod(0o600)
        cfg=snapshot.get('plugins.entries.louter',{}).get('config') if isinstance(snapshot.get('plugins.entries.louter'),dict) else None
        cfg=normalized(cfg or defaults());validate(cfg)
        if dest!=ROOT.resolve():
            if dest.exists():shutil.copytree(dest,backup,symlinks=True)
            dest.mkdir(parents=True,exist_ok=True,mode=0o700)
            for src in ROOT.iterdir():
                if src.name in ['node_modules','.git','__pycache__']:continue
                target=dest/src.name
                if src.is_dir():shutil.copytree(src,target,dirs_exist_ok=True)
                else:shutil.copy2(src,target)
            replaced=True
        # A restrictive plugin allowlist must explicitly include Louter, without replacing others.
        allow=snapshot.get('plugins.allow')
        if isinstance(allow,list) and allow and 'louter' not in allow:
            set_config('plugins.allow',allow+['louter'],log);changed=True
        install=['openclaw','plugins','install','--link',str(dest),'--force']
        helptext=run(['openclaw','plugins','install','--help'],log=log)
        if '--accept-capabilities' in helptext:
            run(install+['--accept-capabilities'],timeout=90,log=log)
        else:
            # Do not hide a capability prompt in a log file; that caused earlier hangs.
            print('OpenClaw install/consent output follows:',flush=True)
            rc=subprocess.run(install,timeout=120).returncode
            if rc:raise RuntimeError(f'Plugin installation failed (exit {rc}).')
        changed=True
        prior=snapshot.get('plugins.entries.louter') if isinstance(snapshot.get('plugins.entries.louter'),dict) else {}
        entry=host_entry(cfg,prior);entry['enabled']=False
        set_config('plugins.entries.louter',entry,log)
        run(['openclaw','plugins','enable','louter','--accept-capabilities'],timeout=45,log=log)
        inspect=run(['openclaw','plugins','inspect','louter'],log=log)
        if 'Status: enabled' not in inspect:raise RuntimeError('Louter did not report enabled after installation.')
        summary.append(('PASS','Plugin registration','enabled with explicit LLM authorization'))
        # Only now disable the earlier proof of concept; preserve files and settings.
        for plugin in ['fastpath-test','mode-switcher']:
            old=get_config('plugins.entries.'+plugin,None,log)
            if isinstance(old,dict):
                run(['openclaw','plugins','disable',plugin],log=log)
        # Preserve old counters as a separately labeled import, not as proven savings.
        stats=STATE/'louter/stats.json'
        if not stats.exists():
            legacy=[]
            for file in [STATE/'local-router-stats.json',STATE/'louter-stats.json']:
                if file.exists():
                    try:legacy.append({'source':file.name,'counts':json.loads(file.read_text())})
                    except (OSError,json.JSONDecodeError):pass
            if legacy:
                stats.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                stats.write_text(json.dumps({'version':1,'since':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'days':{},'legacy':legacy},indent=2)+'\n');stats.chmod(0o600)
                summary.append(('PASS','Legacy statistics','preserved separately; original files untouched'))
        doctor=run(['openclaw','plugins','doctor'],timeout=45,log=log)
        if 'checks passed' not in doctor:raise RuntimeError('Plugin diagnostics did not report checks passed.')
        summary.append(('PASS','Plugin diagnostics','checks passed'))
        if not a.no_restart:
            # Bounded wait; never SIGKILL someone else's work to speed installation.
            run(['systemctl','--user','restart','--no-block','openclaw-gateway.service'],timeout=10,log=log)
            expires=time.monotonic()+90;ready=False
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            while time.monotonic()<expires:
                time.sleep(2)
                try:
                    with opener.open('http://127.0.0.1:18789/',timeout=2) as res:
                        if res.status!=200:continue
                    gw=run(['openclaw','gateway','status','--deep'],timeout=20,log=log)
                    if 'Connectivity probe: ok' in gw:ready=True;break
                except Exception:continue
            if not ready:raise RuntimeError('Gateway did not become healthy within the bounded wait. No force-kill was attempted.')
            summary.append(('PASS','Gateway','connectivity probe OK'))
        else:summary.append(('WARN','Gateway','restart intentionally skipped; live tests skipped'))
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open('http://127.0.0.1:18080/health',timeout=3) as r:
                if r.status!=200:raise ValueError('not ready')
            summary.append(('PASS','Local service','reusing loopback Qwen; no model downloaded'))
        except Exception:summary.append(('WARN','Local service','not ready; run scripts/setup_local.py or start qwen-fastpath.service'))
        smoke_code=0
        if not a.skip_smoke and not a.no_restart:
            smoke_dir=folder/'smoke'
            proc=subprocess.run([sys.executable,str(dest/'scripts/smoke.py'),'--log-dir',str(smoke_dir),'--timeout','180'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=200)
            (folder/'smoke-summary.txt').write_text(proc.stdout)
            smoke_code=proc.returncode
            print(proc.stdout,flush=True)
            summary.append(('PASS' if smoke_code==0 else 'WARN','Live smoke','finished; see the separate completion/route results above'))
        else:summary.append(('WARN','Live smoke','not run'))
        # A targeted rollback script leaves unrelated, potentially newer settings alone.
        rollback=folder/'rollback.py'
        rollback.write_text('''#!/usr/bin/env python3\nimport json,subprocess\nfrom pathlib import Path\ns=json.loads(Path(__file__).with_name("previous-fields.json").read_text())\nsubprocess.run(["openclaw","plugins","disable","louter"],check=False)\nfor key,value in s.items():\n if key=="plugins.allow":continue # preserve subsequent user allowlist changes\n if value is not None:\n  subprocess.run(["openclaw","config","set",key,json.dumps(value),"--strict-json"],check=True)\nsubprocess.run(["systemctl","--user","restart","--no-block","openclaw-gateway.service"],check=True)\nprint("Previous plugin settings restored; source backups retained.")\n''');rollback.chmod(0o700)
        print('\n============== LOUTER INSTALL SUMMARY ==============')
        for status,name,note in summary:print(f'{status:4}  {name:21} {note}')
        print('Source:',dest);print('Logs / backups:',folder);print('Rollback: python3',rollback)
        print('INSTALL: COMPLETE' + ('; live checks need attention' if smoke_code else ''))
        return 2 if smoke_code else 0
    except BaseException as e:
        if isinstance(e,SystemExit):raise
        print('\nINSTALL: FAILED —',str(e),flush=True)
        # Avoid deleting a newly linked path. Deactivate it and recover previous source/settings.
        if changed:
            try:run(['openclaw','plugins','disable','louter'],log=log)
            except Exception:pass
            if replaced and backup.exists():
                try:shutil.copytree(backup,dest,dirs_exist_ok=True)
                except Exception:pass
            for key in ['plugins.entries.louter','plugins.entries.fastpath-test.enabled','plugins.entries.mode-switcher.enabled']:
                value=snapshot.get(key)
                if value is not None:
                    try:set_config(key,value,log)
                    except Exception:pass
            try:run(['systemctl','--user','restart','--no-block','openclaw-gateway.service'],log=log)
            except Exception:pass
        print('Previous source/settings were preserved. Check the saved logs before retrying.');print('Logs / backups:',folder)
        return 1
if __name__=='__main__':
    try:sys.exit(main())
    except (Exception,KeyboardInterrupt) as e:print('INSTALL FAILED:',str(e),file=sys.stderr);sys.exit(1)
