import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { DEFAULTS, configFrom, localUrl } from '../src/config.js';
import { createRouter, parseCommand, localPost } from '../src/louter.js';
import { Store, scopeKey } from '../src/store.js';

const context = (session='test') => ({ agentId:'main', sessionKey:'agent:main:'+session, runId:'run-'+session });
function memoryStore() {
  const events=[],panels=new Map();
  return { events,panels, async event(scope,event){events.push({scope,...event});}, async savePanel(scope,panel){panels.set(scope+':'+panel.id,structuredClone(panel));}, async panel(scope,id){return id?panels.get(scope+':'+id):[...panels.entries()].filter(([k])=>k.startsWith(scope+':')).at(-1)?.[1];}, async totals(){ const counts={}; for(const e of events)for(const[k,v]of Object.entries(e.counts))counts[k]=(counts[k]||0)+v;return {counts,since:'2026-09-17',legacy:null};} };
}
const response = (text,finish='stop') => ({ choices:[{message:{content:text},finish_reason:finish}],usage:{prompt_tokens:25,completion_tokens:4} });
function fixture(overrides={}) {
  const calls=[],workerCalls=[],logs=[],store=overrides.store||memoryStore();
  const cfg=structuredClone(DEFAULTS);

  if(overrides.config)
    for(const[k,v]of Object.entries(overrides.config))
      cfg[k]=['routes','agentIds'].includes(k)?v:{...cfg[k],...v};

  const api={
    pluginConfig:cfg,
    runtime:{
      llm:{
        complete:async req=>{
          calls.push(req);

          if(overrides.cloud)
            return overrides.cloud(req);

          const i=req.model.indexOf('/');

          return {
            text:'CLOUD_OK',
            provider:req.model.slice(0,i),
            model:req.model.slice(i+1),
            usage:{inputTokens:20,outputTokens:5}
          };
        }
      },

      subagent:{
        complete:async req=>{
          workerCalls.push(req);

          if(overrides.subagent)
            return overrides.subagent(req);

          return {
            text:'WORKER_OK'
          };
        }
      }
    }
  };

  let locals=0;

  const router=createRouter(api,{
    store,
    log:r=>logs.push(r),
    localPost:async(...args)=>{
      locals++;
      return overrides.local
        ? overrides.local(...args)
        : response('391');
    }
  });

  return {
    ...router,
    calls,
    workerCalls,
    logs,
    store,
    locals:()=>locals
  };
}

test('default config has 5-second automatic local deadline',()=>assert.equal(configFrom().auto.timeoutMs,5000));
test('local endpoints reject remote, redirects-by-URL, credentials and proxy URLs',()=>{
  for(const x of ['https://example.com/x','http://example.com','http://user@127.0.0.1/x','http://127.0.0.1/x?q=1'])assert.throws(()=>localUrl(x));
  assert.equal(localUrl('http://localhost:18080/v1/chat/completions').hostname,'127.0.0.1');
});
test('configuration rejects reserved aliases and bad panel targets',()=>{
  assert.throws(()=>configFrom({routes:{...DEFAULTS.routes,savings:{kind:'local',model:'x'}}}));
  assert.throws(()=>configFrom({askAround:{routes:['absent']}}));
});
test('prefix parser preserves multiline body and supports inline details',()=>{
  assert.deepEqual(parseCommand('local: One\nTwo',DEFAULTS),{type:'explicit',alias:'local',prompt:'One\nTwo'});
  assert.equal(parseCommand('ask around --details claude: Q?',DEFAULTS).details,'claude');
});
test('strict local succeeds with no cloud calls and removes prefix',async()=>{
  let sent;const f=fixture({local:async(u,b)=>{sent=b;return response('391');}});
  const out=await f.handle({cleanedBody:'local: 17*23'},context());
  assert.equal(out.reply.text,'391');assert.equal(f.calls.length,0);assert.equal(sent.messages[1].content,'17*23');
});
test('strict local HTTP failure cannot fall through',async()=>{
  const f=fixture({local:async()=>{throw new Error('sensitive external text');}});
  const out=await f.handle({cleanedBody:'local: hello'},context());
  assert.equal(out.handled,true);assert.match(out.reply.text,/did not call a cloud/);assert.equal(f.calls.length,0);
  assert.ok(!JSON.stringify(f.logs).includes('sensitive external text'));
});
test('strict local timeout is bounded and does not call cloud',async()=>{
  const routes=structuredClone(DEFAULTS.routes);routes.local.timeoutMs=25;
  const f=fixture({config:{routes},local:()=>new Promise(()=>{})});
  const start=Date.now();const out=await f.handle({cleanedBody:'local: hi'},context());
  assert.ok(Date.now()-start<500);assert.match(out.reply.text,/timeout/);assert.equal(f.calls.length,0);
});
test('truncated local response is never accepted as a complete answer',async()=>{
  const f=fixture({local:async()=>response('incomplete','length')});
  assert.equal(await f.handle({cleanedBody:'what is 17*23?'},context()),undefined);
  assert.ok(f.logs.some(x=>x.outcome==='MAIN_FAILOPEN'));
});
test('unknown prefix is local error rather than a silent cloud handoff',async()=>{
  const f=fixture();const out=await f.handle({cleanedBody:'private: something'},context());
  assert.match(out.reply.text,/Unknown Louter route/);assert.equal(f.calls.length+f.locals(),0);
});
test('non-target agents are untouched',async()=>{
  const f=fixture();assert.equal(await f.handle({cleanedBody:'hello'},{agentId:'other',sessionKey:'a'}),undefined);assert.equal(f.locals(),0);
});
test('deterministic current-information bypass does not invoke local',async()=>{
  const f=fixture();assert.equal(await f.handle({cleanedBody:'Research the latest release'},context()),undefined);assert.equal(f.locals(),0);
});
test('automatic Qwen escalation returns the turn to main',async()=>{
  const f=fixture({local:async()=>response('ESCALATE')});
  assert.equal(await f.handle({cleanedBody:'An ambiguous question'},context()),undefined);assert.ok(f.logs.some(x=>x.outcome==='MAIN_ESCALATE'));
});
test('automatic local success records estimates separately from token usage',async()=>{
  const f=fixture();assert.equal((await f.handle({cleanedBody:'17*23?'},context())).reply.text,'391');
  const s=await f.store.totals();assert.equal(s.counts.autoLocal,1);assert.equal(s.counts.avoidedInputEstimate,15000);assert.equal(s.counts.localInputTokens,25);
});
test('Claude route invokes isolated host runtime once with exact model',async()=>{
  const f=fixture();

  const out=await f.handle(
    {cleanedBody:'claude: hello'},
    context()
  );

  assert.equal(out.reply.text,'WORKER_OK');

  assert.equal(f.workerCalls.length,1);
  assert.equal(
    f.workerCalls[0].agentId,
    'louter-claude'
  );

  // Worker owns the model; Louter must not send a cross-model override.
  assert.equal(f.workerCalls[0].model,undefined);

  // Claude worker route must not touch compatibility llm.complete().
  assert.equal(f.calls.length,0);
});
test('an unexpected actual model is rejected',async()=>{
  // Model-receipt validation belongs to the compatibility llm.complete()
  // path. Production worker routes intentionally trust their configured
  // worker agent and do not receive a provider/model receipt here.
  const routes=structuredClone(DEFAULTS.routes);

  routes.compat={
    kind:'openclaw',
    model:'openai/gpt-6-astra',
    timeoutMs:30000,
    maxTokens:768,
    enabled:true
  };

  const f=fixture({
    config:{routes},
    cloud:async()=>({
      text:'WRONG_MODEL',
      provider:'anthropic',
      model:'claude-opus-5'
    })
  });

  const out=await f.handle(
    {cleanedBody:'compat: hello'},
    context()
  );

  assert.equal(out.handled,true);
  assert.match(out.reply.text,/model_mismatch/);

  assert.equal(f.calls.length,1);
  assert.equal(f.workerCalls.length,0);
});
test('explicit errors count attempts but not completed cloud calls',async()=>{
  const f=fixture({
    subagent:async()=>{throw new Error('worker failed');}
  });

  const out=await f.handle(
    {cleanedBody:'astra: hello'},
    context()
  );

  assert.equal(out.handled,true);

  const totals=await f.store.totals();
  assert.equal(totals.counts.cloudAttempts,1);
  assert.equal(totals.counts.cloudSuccesses||0,0);

  assert.equal(f.workerCalls.length,1);
  assert.equal(f.calls.length,0);
});
test('panel runs concurrently, preserves originals and uses local synthesis',async()=>{
  let active=0;
  let peak=0;

  const f=fixture({
    local:async(u,b)=>{
      const prompt=b.messages?.[0]?.content || '';

      if(prompt.startsWith('Synthesize'))
        return response('SYNTHESIZED');

      return response('LOCAL_ORIGINAL');
    },

    subagent:async req=>{
      active++;
      peak=Math.max(peak,active);

      await new Promise(r=>setTimeout(r,20));

      active--;

      return {
        text:req.agentId==='louter-astra'
          ? 'ASTRA_ORIGINAL'
          : 'CLAUDE_ORIGINAL'
      };
    }
  });

  const out=await f.handle(
    {cleanedBody:'ask around: hi'},
    context()
  );

  assert.equal(out.handled,true);
  assert.equal(f.workerCalls.length,2);
  assert.equal(f.calls.length,0);

  // Both workers must overlap rather than execute serially.
  assert.ok(peak>=2);

  const panel=await f.store.panel(scopeKey(context()));

  assert.equal(panel.answers.length,3);
  assert.equal(
    panel.answers.find(x=>x.route==='local').text,
    'LOCAL_ORIGINAL'
  );
  assert.equal(
    panel.answers.find(x=>x.route==='astra').text,
    'ASTRA_ORIGINAL'
  );
  assert.equal(
    panel.answers.find(x=>x.route==='claude').text,
    'CLAUDE_ORIGINAL'
  );

  assert.match(out.reply.text,/SYNTHESIZED/);
});
test('panel details are not visible to another conversation',async()=>{
  const f=fixture();await f.handle({cleanedBody:'ask around: test'},context('one'));
  const out=await f.handle({cleanedBody:'details all'},context('two'));assert.match(out.reply.text,/No retained/);
});
test('details missing a session identity fail closed',async()=>{
  const f=fixture();const out=await f.handle({cleanedBody:'details all'},{agentId:'main'});assert.match(out.reply.text,/without a conversation identity/);
});
test('local synthesis failure uses only configured fallback',async()=>{
  const f=fixture({
    local:async(u,b)=>{
      const prompt=b.messages?.[0]?.content || '';

      return response(
        prompt.startsWith('Synthesize')
          ? 'ESCALATE'
          : 'LOCAL_ANSWER'
      );
    },

    subagent:async req=>({
      text:req.agentId==='louter-astra'
        ? 'ASTRA_ANSWER'
        : 'CLAUDE_ANSWER'
    })
  });

  await f.handle(
    {cleanedBody:'ask around: choice?'},
    context()
  );

  // Astra + Claude panel, then Astra fallback synthesis.
  assert.equal(f.workerCalls.length,3);
  assert.equal(f.workerCalls[0].agentId,'louter-astra');
  assert.equal(f.workerCalls[1].agentId,'louter-claude');
  assert.equal(f.workerCalls[2].agentId,'louter-astra');

  assert.equal(f.calls.length,0);
});
test('one failed panel model is visible and does not discard successful answers',async()=>{
  const f=fixture({
    subagent:async req=>{
      if(req.agentId==='louter-claude')
        throw new Error('noauth');

      return {text:'ASTRA_ANSWER'};
    }
  });

  const out=await f.handle(
    {cleanedBody:'ask around: hi'},
    context()
  );

  assert.match(out.reply.text,/claude=error/);

  const panel=await f.store.panel(scopeKey(context()));

  assert.equal(panel.answers.length,3);
  assert.equal(
    panel.answers.find(x=>x.route==='astra').status,
    'ok'
  );
  assert.equal(
    panel.answers.find(x=>x.route==='claude').status,
    'error'
  );
});
test('panel never waits indefinitely for a provider ignoring cancellation',async()=>{
  const f=fixture({
    config:{
      askAround:{
        panelTimeoutMs:25,
        localPanelTimeoutMs:20,
        totalTimeoutMs:150,
        synthesisTimeoutMs:20,
        fallbackTimeoutMs:20
      }
    },
    subagent:()=>new Promise(()=>{})
  });

  const start=Date.now();

  const out=await f.handle(
    {cleanedBody:'ask around: hi'},
    context()
  );

  assert.ok(Date.now()-start<600);
  assert.equal(out.handled,true);
  assert.equal(f.workerCalls.length,2);
});
test('identical panel responses require no extra synthesis model',async()=>{
  const f=fixture({
    local:async()=>response('SAME'),
    subagent:async()=>({text:'SAME'})
  });

  const out=await f.handle(
    {cleanedBody:'ask around: hi'},
    context()
  );

  assert.match(out.reply.text,/identical/i);
  assert.equal(f.locals(),1);
  assert.equal(f.workerCalls.length,2);
  assert.equal(f.calls.length,0);
});
test('savings command invokes no model and does not invent a dollar rate',async()=>{
  const f=fixture();const out=await f.handle({cleanedBody:'savings'},context());assert.match(out.reply.text,/not configured/);assert.equal(f.calls.length+f.locals(),0);
});
test('shutdown makes explicit local requests fail closed',async()=>{
  const f=fixture();f.close();const out=await f.handle({cleanedBody:'local: hi'},context());assert.equal(out.handled,true);assert.equal(f.calls.length,0);
});
test('recognized media bypasses automatic answering and refuses text-only explicit route',async()=>{
  const f=fixture();const ctx={...context(),channelContext:{mediaPaths:['image.png']}};
  assert.equal(await f.handle({cleanedBody:'What is this?'},ctx),undefined);
  assert.equal((await f.handle({cleanedBody:'local: explain'},ctx)).reply.isError,true);assert.equal(f.locals(),0);
});
test('persistent store creates private scoped files and serializes counter updates',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'louter-test-'));
  try {
    const s=new Store(dir,DEFAULTS.storage);await Promise.all(Array.from({length:8},()=>s.event('abc',{counts:{local:1}})));
    assert.equal((await s.totals()).counts.local,8);
    assert.equal((await fs.stat(path.join(dir,'stats.json'))).mode&0o777,0o600);
    const id='00000000-0000-4000-8000-000000000000';await s.savePanel('first',{id,answers:[{text:'secret'}]});assert.equal(await s.panel('second',id),null);
  } finally {await fs.rm(dir,{recursive:true,force:true});}
});
test('local HTTP transport never follows a redirect to a remote address',async()=>{
  const server=http.createServer((req,res)=>{res.writeHead(302,{Location:'https://example.com/private'});res.end();});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  try {await assert.rejects(localPost(`http://127.0.0.1:${server.address().port}/v1/chat/completions`,{},AbortSignal.timeout(500)),/HTTP 302/);}finally{server.close();}
});
