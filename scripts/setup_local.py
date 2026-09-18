#!/usr/bin/env python3
"""Reuse a loopback server, or provision a model through an existing Ollama install."""
import argparse, json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path
from common import defaults, get_config, set_config, host_entry, normalized, validate, diagnostic_dir, run

opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def http_json(url,body=None,timeout=5):
    from urllib.parse import urlsplit
    u=urlsplit(url)
    if u.scheme!='http' or u.hostname not in ['127.0.0.1','localhost','::1']:raise ValueError('Use a loopback HTTP endpoint.')
    req=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=timeout) as r:return json.load(r)

def benchmark(route):
    cases=[('17*23? Reply only the number.','391'),('Convert 12 feet to meters. Reply only the number.','3.6576')]
    rows=[]
    for prompt,want in cases:
        body={'model':route['model'],'messages':[{'role':'user','content':prompt}],'stream':False}
        if route['protocol']=='ollama':body.update(think=False,keep_alive='30m',options={'num_ctx':4096,'num_predict':24,'temperature':0})
        else:body.update(max_tokens=24,temperature=0,chat_template_kwargs={'enable_thinking':False})
        start=time.monotonic();j=http_json(route['endpoint'],body,timeout=30)
        text=j.get('message',{}).get('content','') if route['protocol']=='ollama' else j.get('choices',[{}])[0].get('message',{}).get('content','')
        rows.append((want in text,time.monotonic()-start))
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--yes',action='store_true');p.add_argument('--ollama-model');p.add_argument('--endpoint');p.add_argument('--model',default='qwen');p.add_argument('--protocol',choices=['openai','ollama'],default='openai');p.add_argument('--apply',action='store_true')
    a=p.parse_args();d=diagnostic_dir('setup-local');log=d/'setup.log'
    old=get_config('plugins.entries.louter',{});cfg=normalized(old.get('config') or defaults());route=None
    if a.endpoint:route={'kind':'local','model':a.model,'endpoint':a.endpoint,'protocol':a.protocol,'contextTokens':4096,'timeoutMs':30000,'maxTokens':384,'enabled':True}
    if not route and not a.ollama_model:
        try:
            http_json('http://127.0.0.1:18080/health');route=cfg['routes'].get('local',defaults()['routes']['local'])
            print('Reusing existing Qwen loopback server on port 18080.')
        except Exception:pass
    if not route:
        try:http_json('http://127.0.0.1:11434/api/tags')
        except Exception:raise RuntimeError('No supported local server found. Start an installed Ollama runtime, or supply --endpoint and --model. Setup does not run a downloaded OS installer or request sudo.')
        if not shutil.which('ollama'):raise RuntimeError('Ollama HTTP is present but its CLI is missing; use --endpoint http://127.0.0.1:11434/api/chat --protocol ollama --model <already-installed-tag>.')
        try:
            kib=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')));gib=kib/1048576
        except Exception:gib=8
        model=a.ollama_model or ('qwen3.5:0.8b' if gib<6 else 'qwen3.5:2b' if gib<16 else 'qwen3.5:4b')
        if model not in ['qwen3.5:0.8b','qwen3.5:2b','qwen3.5:4b']:raise ValueError('This setup offers verified local Qwen 3.5 tags only. Existing arbitrary models can be configured with --endpoint.')
        print(f'Memory-based starting candidate: {model} ({gib:.1f} GiB RAM). Benchmark results, not RAM alone, decide acceptance.')
        if not a.yes and input('Download/pull this model with Ollama? [y/N] ').strip().lower()!='y':return 0
        run(['ollama','pull',model],timeout=1800,log=log)
        route={'kind':'local','model':model,'endpoint':'http://127.0.0.1:11434/api/chat','protocol':'ollama','contextTokens':4096,'timeoutMs':30000,'maxTokens':384,'enabled':True}
        # Empty prompt loads it without an unconstrained warmup generation.
        http_json('http://127.0.0.1:11434/api/generate',{'model':model,'prompt':'','stream':False,'keep_alive':'30m'},timeout=90)
    cfg['routes']['local']=route;validate(cfg)
    rows=benchmark(route)
    passed=all(ok for ok,_ in rows)
    fast=max(t for _,t in rows)<=5
    print('\n========== LOCAL SETUP SUMMARY ==========')
    print('Model:',route['model']);print('Accuracy smoke:', 'PASS' if passed else 'FAIL');print('Times:',', '.join(f'{t:.2f}s' for _,t in rows))
    if not passed:raise RuntimeError('Candidate failed the small accuracy smoke test. The existing configured route was not changed.')
    if not fast:print('WARN: cold/recent calls exceeded the 5-second automatic budget. Warm use may differ; no speed guarantee.')
    if a.apply:
        set_config('plugins.entries.louter',host_entry(cfg,old),log)
        print('Configuration: UPDATED')
    else:print('Configuration: UNCHANGED; rerun with --apply to select this route.')
    print('This is a tiny smoke test, not an evaluation of general model accuracy.');print('Logs:',d)
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (Exception,KeyboardInterrupt) as e:print('SETUP FAILED:',str(e),file=sys.stderr);sys.exit(1)
