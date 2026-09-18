#!/usr/bin/env python3
"""Short real-host tests. Quiet execution, exact session-correlated evidence, final summary."""
import argparse, hashlib, json, os, signal, subprocess, sys, time, uuid
from pathlib import Path
from common import ROOT, STATE, get_config, parse_json, diagnostic_dir


def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--timeout',type=int,default=180);p.add_argument('--log-dir')
    args=p.parse_args();folder=Path(args.log_dir) if args.log_dir else diagnostic_dir('smoke');folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    started=time.monotonic();rows=[]
    try:cfg=get_config('plugins.entries.louter.config',{})
    except Exception:cfg={}
    agent=(cfg.get('agentIds') or ['main'])[0]
    panel_session=f'agent:{agent}:louter-panel-test-{uuid.uuid4()}'
    print('Testing Louter quietly; cloud smoke tests make a few short configured-model calls.',flush=True)
    def events(key):
        scope=hashlib.sha256((agent+'\0'+key).encode()).hexdigest();file=STATE/'louter/sessions'/scope/'events.jsonl'
        if not file.exists():return []
        result=[]
        for line in file.read_text().splitlines():
            try:result.append(json.loads(line))
            except json.JSONDecodeError:pass
        return result
    def run_test(name,prompt,contains,kind=None,alias=None,key=None,seconds=30):
        if time.monotonic()-started>args.timeout:
            rows.append(('FAIL',name,0,'suite deadline; not run'));return
        key=key or f'agent:{agent}:louter-smoke-{uuid.uuid4()}'
        before=len(events(key));begin=time.monotonic();reason='';status='FAIL'
        limit=max(1,min(seconds+5,int(args.timeout-(begin-started))))
        cmd=['openclaw','agent','--agent',agent,'--session-key',key,'--message',prompt,'--timeout',str(seconds),'--json']
        out='';proc=None
        try:
            proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
            out,_=proc.communicate(timeout=limit)
            (folder/(name.replace(' ','-')+'.txt')).write_text(out);(folder/(name.replace(' ','-')+'.txt')).chmod(0o600)
            result=parse_json(out)
            payloads=result.get('result',{}).get('payloads',[])
            text='\n'.join(str(x.get('text','')) for x in payloads)
            if proc.returncode!=0 or result.get('status')!='ok' or any(x.get('isError') for x in payloads):raise ValueError('turn failed/timeout: '+text[:100].replace('\n',' '))
            if (text.strip()!=contains if kind in ['local','cloud','main'] else contains not in text):raise ValueError('unexpected reply: '+text[:90].replace('\n',' '))
            new=events(key)[before:]
            if kind=='local' and not any(x.get('event')=='route' and x.get('outcome')=='LOCAL' for x in new):raise ValueError('answer present but local route was not verified')
            if kind=='cloud':
                target=cfg.get('routes',{}).get(alias,{}).get('model')
                matching=[e for e in new if e.get('event')=='call_end' and e.get('route')==alias and e.get('status')=='ok']
                if not matching:raise ValueError('no completed isolated call receipt')
                if not target or not any(e.get('actualModel')==target for e in matching):
                    status='WARN';reason='reply OK; runtime model attribution unavailable'
                else:status='PASS';reason=target
            elif kind=='panel':
                panel=[e for e in new if e.get('event')=='panel_end']
                if not panel:raise ValueError('panel never completed')
                want=[r for r in cfg.get('askAround',{}).get('routes',['local','astra','claude']) if cfg.get('routes',{}).get(r,{}).get('enabled',True)]
                done=panel[-1].get('completed',[])
                status='PASS' if set(want).issubset(done) else 'WARN'
                reason=f'{len(done)}/{len(want)} complete; synth={panel[-1].get("synthesisRoute")}'
            elif kind=='no-calls':
                if any(e.get('event')=='call_start' for e in new):raise ValueError('administrative/details command unexpectedly called a model')
                status='PASS';reason='no model calls'
            elif kind=='main':
                if not any(e.get('event')=='route' and e.get('outcome')=='MAIN_DIRECT' for e in new):raise ValueError('main handoff not observed')
                meta=result.get('result',{}).get('meta',{}).get('agentMeta',{})
                reason='/'.join([str(meta.get('provider','?')),str(meta.get('model','?'))]);status='PASS'
            else:status='PASS';reason='reply and route verified' if kind else 'reply verified'
        except subprocess.TimeoutExpired:
            if proc:
                os.killpg(proc.pid,signal.SIGTERM)
                try:out,_=proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);out,_=proc.communicate()
            reason='deadline exceeded (not a pass)'
        except Exception as e:reason=str(e)[:150]
        finally:
            if out:(folder/(name.replace(' ','-')+'.txt')).write_text(out);(folder/(name.replace(' ','-')+'.txt')).chmod(0o600)
            rows.append((status,name,time.monotonic()-begin,reason))
    run_test('Hook','louter ping','LOUTER_OK',kind='no-calls',seconds=10)
    run_test('Local','local: What is 17*23? Reply with only the number.','391',kind='local',seconds=35)
    for alias in ['astra','claude']:
        if cfg.get('routes',{}).get(alias,{}).get('enabled',True):run_test(alias.title(),f'{alias}: Reply with exactly LOUTER_{alias.upper()}_OK.',f'LOUTER_{alias.upper()}_OK',kind='cloud',alias=alias,seconds=35)
    if not args.quick:
        run_test('Ask Around','ask around: Reply with exactly LOUTER_PANEL_OK.','Ask Around',kind='panel',key=panel_session,seconds=55)
        run_test('Details','details all','LOUTER_PANEL_OK',kind='no-calls',key=panel_session,seconds=10)
        run_test('Main handoff','Current routing test only: reply exactly LOUTER_MAIN_OK. Do not use tools.','LOUTER_MAIN_OK',kind='main',seconds=25)
    run_test('Savings','savings','Louter Savings',kind='no-calls',seconds=10)
    fails=sum(r[0]=='FAIL' for r in rows);warns=sum(r[0]=='WARN' for r in rows)
    print('\n================ LOUTER SUMMARY ================')
    for status,name,secs,reason in rows:print(f'{status:4}  {name:14} {secs:6.2f}s  {reason}')
    print(f'OVERALL: {"FAIL" if fails else "PASS WITH WARNINGS" if warns else "PASS"} | {len(rows)-fails-warns} pass, {warns} warn, {fails} fail')
    print('Detailed logs:',folder)
    (folder/'summary.json').write_text(json.dumps({'results':rows,'fail':fails,'warn':warns},indent=2))
    return 1 if fails else 0
if __name__=='__main__':sys.exit(main())
