#!/usr/bin/env python3
"""Terminal-only route administration. Never exposes mutation commands to chat."""
import argparse, copy, json, sys
from common import ROOT, STATE, defaults, get_config, host_entry, set_config, normalized, validate, run, diagnostic_dir

p=argparse.ArgumentParser(description='Configure Louter without editing JavaScript.')
p.add_argument('--yes',action='store_true',help='Approve the displayed configuration/model-permission changes')
s=p.add_subparsers(dest='command',required=True)
s.add_parser('show')
r=s.add_parser('routes').add_subparsers(dest='operation',required=True)
r.add_parser('list')
a=r.add_parser('add');a.add_argument('alias');a.add_argument('model');a.add_argument('--local-endpoint');a.add_argument('--protocol',choices=['openai','ollama'],default='openai');a.add_argument('--context',type=int,default=4096)
d=r.add_parser('remove');d.add_argument('alias')
c=s.add_parser('panel');c.add_argument('aliases',nargs='+')
c=s.add_parser('synthesizer');c.add_argument('alias');c.add_argument('--fallback')
c=s.add_parser('prices');c.add_argument('input_per_million',type=float);c.add_argument('output_per_million',type=float)
c=s.add_parser('timeout');c.add_argument('seconds',type=float)
c=s.add_parser('reset-stats');c.add_argument('--confirm',action='store_true')
args=p.parse_args()
try:
    old=get_config('plugins.entries.louter',{})
    cfg=copy.deepcopy(normalized(old.get('config') or defaults()))
    if args.command=='show':print(json.dumps(cfg,indent=2));sys.exit(0)
    if args.command=='routes' and args.operation=='list':
        for alias,v in cfg['routes'].items():print(f'{alias:14} {v["kind"]:10} {v["model"]}')
        sys.exit(0)
    if args.command=='reset-stats':
        if not args.confirm:raise ValueError('Use reset-stats --confirm; old stats are archived, not deleted.')
        f=STATE/'louter/stats.json'
        if f.exists():
            from datetime import datetime
            f.rename(f.with_name('stats.before-reset-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json'))
        print('Louter statistics archived. New counters start with the next request.');sys.exit(0)
    if args.command=='routes':
        if args.operation=='add':
            cfg['routes'][args.alias]=({'kind':'local','model':args.model,'endpoint':args.local_endpoint,'protocol':args.protocol,'contextTokens':args.context,'enabled':True} if args.local_endpoint else {'kind':'openclaw','model':args.model,'enabled':True})
        else:
            alias=args.alias
            if alias==cfg['auto']['localRoute']:raise ValueError('Cannot remove the active automatic local route.')
            if alias==cfg['askAround']['synthesizer'] or alias==cfg['askAround'].get('fallbackSynthesizer'):raise ValueError('Change synthesizer/fallback before removing this route.')
            if alias not in cfg['routes']:raise ValueError('Unknown route')
            cfg['routes'].pop(alias);cfg['askAround']['routes']=[x for x in cfg['askAround']['routes'] if x!=alias]
    elif args.command=='panel':cfg['askAround']['routes']=args.aliases
    elif args.command=='synthesizer':
        cfg['askAround']['synthesizer']=args.alias;cfg['askAround']['fallbackSynthesizer']=args.fallback
    elif args.command=='prices':
        cfg['estimates']['inputUsdPerMillion']=args.input_per_million;cfg['estimates']['outputUsdPerMillion']=args.output_per_million
    elif args.command=='timeout':cfg['auto']['timeoutMs']=round(args.seconds*1000)
    validate(cfg)
    entry=host_entry(cfg,old)
    allowed=entry['llm'].get('allowedCompletionModels',[])
    print('Louter change:',args.command)
    print('Cloud completion targets:',', '.join(allowed) or 'none')
    if not args.yes and input('Apply this configuration and approve those Louter model overrides? [y/N] ').strip().lower()!='y':sys.exit(0)
    folder=diagnostic_dir('configure');log=folder/'configure.log'
    (folder/'previous-entry.json').write_text(json.dumps(old,indent=2));(folder/'previous-entry.json').chmod(0o600)
    set_config('plugins.entries.louter',entry,log)
    run(['openclaw','plugins','enable','louter','--accept-capabilities'],log=log)
    print('CONFIGURATION: UPDATED')
    print('Gateway hot reload normally applies config changes. Source changes still need a restart.')
    print('Saved diagnostics:',folder)
except (Exception,KeyboardInterrupt) as e:
    print('CONFIGURATION: FAILED —',str(e),file=sys.stderr);sys.exit(1)
