"""CLI helpers: no shell interpolation, bounded subprocesses, complete diagnostics to file."""
import json, os, re, subprocess, time
from pathlib import Path
STATE = Path(os.environ.get('OPENCLAW_STATE_DIR', str(Path.home()/'.openclaw'))).expanduser()
ROOT = Path(__file__).resolve().parents[1]
MISSING = object()
ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

def run(args, timeout=30, input_text=None, log=None):
    p = subprocess.run([str(x) for x in args], input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    text=ANSI.sub('',p.stdout)
    if log:
        with open(log,'a') as f: f.write('\n$ '+ ' '.join(map(str,args))+'\n'+text+'\n')
    if p.returncode:
        # Do not echo possibly secret config into the compact report.
        raise RuntimeError(f'{args[0]} {args[1] if len(args)>1 else ""}: exit {p.returncode}; see saved log')
    return text

def parse_json(text):
    text=ANSI.sub('',text).strip()
    try:return json.loads(text)
    except json.JSONDecodeError:pass
    for m in re.finditer(r'[\[{]',text):
        try:
            value,end=json.JSONDecoder().raw_decode(text[m.start():])
            if not text[m.start()+end:].strip():return value
        except json.JSONDecodeError:continue
    raise ValueError('No complete JSON object in CLI response')

def get_config(key, default=MISSING, log=None):
    try:
        raw=run(['openclaw','config','get',key],log=log)
        if 'valid but unset' in raw or 'Unknown config path' in raw or 'Config path not found' in raw:
            if default is MISSING: raise KeyError(key)
            return default
        try:return parse_json(raw)
        except ValueError:
            lines=[s.strip() for s in raw.splitlines() if s.strip()]
            return lines[-1].strip('"') if lines else default
    except RuntimeError:
        if default is not MISSING:return default
        raise

def set_config(key,value,log=None):
    return run(['openclaw','config','set',key,json.dumps(value,separators=(',',':')),'--strict-json'],log=log)

def defaults():
    return parse_json(run(['node','--input-type=module','-e',f'import {{ DEFAULTS }} from {json.dumps((ROOT/"src/config.js").as_uri())}; console.log(JSON.stringify(DEFAULTS));']))

def normalized(value):
    return parse_json(run(['node','--input-type=module','-e',f'import {{ configFrom }} from {json.dumps((ROOT/"src/config.js").as_uri())}; let s=""; for await (const c of process.stdin) s+=c; console.log(JSON.stringify(configFrom(JSON.parse(s))));'],input_text=json.dumps(value)))

def validate(value):
    normalized(value)

def host_entry(cfg,previous=None):
    entry=dict(previous or {})
    entry['config']=cfg
    entry['hooks']={**entry.get('hooks',{}),'allowConversationAccess':True,'timeouts':{**entry.get('hooks',{}).get('timeouts',{}),'before_agent_reply':120000}}
    models=list(dict.fromkeys(r['model'] for r in cfg['routes'].values() if r.get('enabled',True) and r['kind']=='openclaw'))
    # Empty host allowlists mean unrestricted; never use [] as a deny-all policy.
    if models:
        entry['llm']={**entry.get('llm',{}),'allowModelOverride':True,'allowedModels':models,'allowedCompletionModels':models}
    else:
        entry['llm']={**entry.get('llm',{}),'allowModelOverride':False}
    return entry

def diagnostic_dir(prefix):
    p=STATE/'louter-diagnostics'/f'{prefix}-{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}'
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    return p
