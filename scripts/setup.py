#!/usr/bin/env python3
"""Friendly first-run setup: detect local/cloud availability and configure Louter routes."""
import argparse, copy, json, re, shutil, subprocess, sys, urllib.request
from pathlib import Path
from common import ROOT, defaults, get_config, host_entry, set_config, normalized, validate, run, parse_json, diagnostic_dir

MODEL_REF = re.compile(r'(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+/[A-Za-z0-9_.:@+-]+)')

def provider(model):
    return model.split('/', 1)[0] if '/' in model else ''

def loopback_ok(url):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url,timeout=2) as r:return 200 <= r.status < 300
    except Exception:return False

def discover(log=None):
    catalog=set()
    try:
        text=run(['openclaw','models','list','--all'],timeout=30,log=log)
        catalog.update(MODEL_REF.findall(text))
    except Exception:pass
    status={}
    try:
        j=parse_json(run(['openclaw','models','status','--json'],timeout=30,log=log))
        def walk(v):
            if isinstance(v,dict):
                p=v.get('provider')
                st=v.get('status')
                if isinstance(p,str) and st:
                    status.setdefault(p,set()).add(str(st).lower())
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(j)
    except Exception:pass
    local={
        'qwen-loopback':loopback_ok('http://127.0.0.1:18080/health'),
        'ollama':loopback_ok('http://127.0.0.1:11434/api/tags')
    }
    return catalog,status,local

def replace_alias(cfg,old,new):
    if old==new:return
    if new in cfg['routes']:raise ValueError(f'Route alias already exists: {new}')
    cfg['routes'][new]=cfg['routes'].pop(old)
    cfg['askAround']['routes']=[new if x==old else x for x in cfg['askAround']['routes']]
    if cfg['askAround']['synthesizer']==old:cfg['askAround']['synthesizer']=new
    if cfg['askAround'].get('fallbackSynthesizer')==old:cfg['askAround']['fallbackSynthesizer']=new
    if cfg['auto']['localRoute']==old:cfg['auto']['localRoute']=new
    if cfg.get('fallback',{}).get('route')==old:cfg['fallback']['route']=new

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--yes',action='store_true',help='Keep suggested route names/models and apply without prompts')
    p.add_argument('--show',action='store_true',help='Detect and print only; do not change config')
    a=p.parse_args()
    d=diagnostic_dir('setup');log=d/'setup.log'
    old=get_config('plugins.entries.louter',{})
    cfg=copy.deepcopy(normalized(old.get('config') or defaults()))
    catalog,status,local=discover(log)
    print('========== LOUTER SETUP ==========')
    print('Local Qwen loopback:', 'ready' if local['qwen-loopback'] else 'not detected')
    print('Ollama:', 'ready' if local['ollama'] else 'not detected')
    print('Authenticated/known providers:', ', '.join(sorted(p for p,states in status.items() if 'ok' in states)) or 'none reported')
    print('\nCurrent cloud routes:')
    for alias,r in cfg['routes'].items():
        if r['kind']!='openclaw':continue
        present='catalog' if r['model'] in catalog else 'not seen in catalog'
        auth='provider-ok' if 'ok' in status.get(provider(r['model']),set()) else 'auth not confirmed'
        worker=f", worker={r.get('agentId')}" if r.get('agentId') else ', direct completion'
        print(f'  {alias}: {r["model"]} [{present}; {auth}{worker}]')
    if a.show:
        print('\nConfiguration: UNCHANGED');return 0
    if not local['qwen-loopback'] and not local['ollama']:
        print('\nNo supported local runtime is ready. Install/start Ollama or provide a loopback endpoint with scripts/setup_local.py.')
    if not a.yes:
        print('\nPress Enter to keep each value. Changing a model removes its dedicated worker binding unless you configure a matching worker separately.')
        cloud_aliases=[x for x,r in cfg['routes'].items() if r['kind']=='openclaw']
        for old_alias in list(cloud_aliases):
            r=cfg['routes'][old_alias]
            alias=input(f'Route alias [{old_alias}]: ').strip() or old_alias
            if alias!=old_alias:
                replace_alias(cfg,old_alias,alias)
                r=cfg['routes'][alias]
            model=input(f'{alias} model [{r["model"]}]: ').strip() or r['model']
            if model!=r['model']:
                r['model']=model
                r.pop('agentId',None)
        panel_default=', '.join(cfg['askAround']['routes'])
        raw=input(f'Ask Around routes, comma-separated [{panel_default}]: ').strip()
        if raw:cfg['askAround']['routes']=[x.strip() for x in raw.split(',') if x.strip()]
    validate(cfg)
    if not a.yes:
        print('\nPlanned routes:')
        for alias,r in cfg['routes'].items():print(f'  {alias}: {r["kind"]} -> {r["model"]}')
        if input('Apply this Louter configuration? [y/N] ').strip().lower()!='y':
            print('Configuration: UNCHANGED');return 0
    set_config('plugins.entries.louter',host_entry(cfg,old),log)
    run(['openclaw','plugins','enable','louter','--accept-capabilities'],timeout=45,log=log)
    print('\nConfiguration: UPDATED')
    print('Try: local: hello')
    print('Try: ask around: compare two approaches')
    print('Logs:',d)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (Exception,KeyboardInterrupt) as e:
        print('SETUP FAILED:',str(e),file=sys.stderr);sys.exit(1)
