import tempfile,pathlib,json,os,subprocess,sys,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
FAKE=r'''#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
p=Path(os.environ['MOCK_CFG']);d=json.loads(p.read_text());a=sys.argv[1:]
def get(k):
 x=d
 for q in k.split('.'):
  if not isinstance(x,dict) or q not in x:return None
  x=x[q]
 return x
def put(k,v):
 x=d;parts=k.split('.')
 for q in parts[:-1]:x=x.setdefault(q,{})
 x[parts[-1]]=v;p.write_text(json.dumps(d))
if a==['--version']:print('OpenClaw 2026.9.4');sys.exit(0)
if a[:2]==['config','get']:
 v=get(a[2]);print('Config path is valid but unset: '+a[2] if v is None else json.dumps(v));sys.exit(0)
if a[:2]==['config','set']:put(a[2],json.loads(a[3]));print('Updated');sys.exit(0)
if a[:2]==['plugins','install']:
 if '--help' in a:print('Usage --link --force --accept-capabilities');sys.exit(0)
 put('plugins.entries.louter',{'enabled':True});print('Linked');sys.exit(0)
if a[:2]==['plugins','enable']:put('plugins.entries.'+a[2]+'.enabled',True);print('Enabled');sys.exit(0)
if a[:2]==['plugins','disable']:put('plugins.entries.'+a[2]+'.enabled',False);print('Disabled');sys.exit(0)
if a[:2]==['plugins','inspect']:print('Status: enabled' if get('plugins.entries.'+a[2]+'.enabled') else 'Status: disabled');sys.exit(0)
if a[:2]==['plugins','doctor']:print('Diagnostics: mocked failure' if os.environ.get('MOCK_FAIL') else 'Plugin discovery, module loading, compatibility, and configuration checks passed.');sys.exit(0)
print('Unknown mock command',a);sys.exit(1)
'''
for should_fail in (False,True):
 with tempfile.TemporaryDirectory() as temp:
  t=pathlib.Path(temp);bin=t/'bin';bin.mkdir();(bin/'openclaw').write_text(FAKE);(bin/'openclaw').chmod(0o755)
  (bin/'systemctl').write_text('#!/bin/sh\nexit 0\n');(bin/'systemctl').chmod(0o755)
  cfg=t/'config.json';cfg.write_text(json.dumps({'agents':{'entries':{'main':{'model':'unchanged/model'}}},'plugins':{'allow':['existing'],'entries':{'fastpath-test':{'enabled':True},'mode-switcher':{'enabled':False}}}}))
  env={**os.environ,'PATH':str(bin)+':'+os.environ['PATH'],'MOCK_CFG':str(cfg),'OPENCLAW_STATE_DIR':str(t/'state')}
  if should_fail:env['MOCK_FAIL']='1'
  command=[sys.executable,'-c','import os,runpy,sys;os.geteuid=lambda:1000;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name="__main__")',str(ROOT/'scripts'),str(ROOT/'scripts/install.py'),'--yes','--skip-smoke','--no-restart','--destination',str(t/'destination')]
  p=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=45)
  state=json.loads(cfg.read_text())
  assert p.returncode==(1 if should_fail else 0),p.stdout
  assert state['agents']['entries']['main']['model']=='unchanged/model'
  assert state['plugins']['entries']['fastpath-test']['enabled']==should_fail
  assert state['plugins']['entries']['louter']['enabled']==(not should_fail)
  if not should_fail:assert state['plugins']['entries']['louter']['llm']['allowedCompletionModels']==['openai/gpt-6-astra','anthropic/claude-opus-5']
  print('PASS installer '+('rollback on diagnostics failure' if should_fail else 'new installation, permissions, preservation'))
