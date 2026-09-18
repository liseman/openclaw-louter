import contextlib
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import telemetry as client
from telemetry_schema import REPOSITORY, TITLE, MARKER, MAX_VALUE, METRICS, zero, validate, encode, decode, project
from aggregate_telemetry import collect, render


def sample(n=5, install=None, sequence=1):
    totals = zero()
    totals.update(local_answers=n, estimated_input_tokens_avoided=n*15000,
                  estimated_output_tokens_avoided=n*150, cloud_attempts=3, cloud_completions=2)
    return {'schema': 1, 'install_id': install or str(uuid.uuid4()), 'sequence': sequence,
            'louter_version': '0.2.9', 'updated': dt.datetime.now(dt.timezone.utc).date().isoformat(),
            'withdrawn': False, 'totals': totals}


def issue(payload, number=1, user=12, closed=False):
    return {'number': number, 'user': {'id': user, 'login': 'someone', 'type': 'User'},
            'title': TITLE+payload['install_id'], 'body': encode(payload),
            'state': 'closed' if closed else 'open', 'labels': []}


def stats(n=5, epoch='first'):
    return {'version': 1, 'since': epoch, 'days': {'2026-09-18': {
        'autoLocal': n-1, 'forcedLocal': 1, 'avoidedInputEstimate': n*15000,
        'avoidedOutputEstimate': n*150, 'cloudAttempts': 3, 'cloudSuccesses': 2,
        'panelRuns': 2, 'cloudFailureFallbackSuccesses': 1,
        'PROMPT_SECRET': 'never send this', 'api_key': 'not allowed'}},
        'legacy': {'private': 'old counters must not be imported'}}


class FakeAPI:
    def __init__(self):
        self.calls=[]; self.issues=[]; self.user={'id':12, 'login':'someone'}
    def __call__(self, endpoint, method='GET', data=None):
        self.calls.append((endpoint, method, data))
        if endpoint=='user': return self.user
        if '?' in endpoint: return self.issues
        if method=='POST':
            row={'number':len(self.issues)+1, 'user':{**self.user,'type':'User'}, 'state':'open', **data}
            self.issues.append(row)
            return row
        row=self.issues[int(endpoint.rsplit('/',1)[1])-1]
        if method=='PATCH':row.update(data)
        return row


class SchemaTests(unittest.TestCase):
    def test_round_trip(self):self.assertEqual(decode(encode(sample()))['schema'],1)
    def test_unknown_fields_rejected(self):
        p=sample();p['prompt']='private'
        with self.assertRaises(ValueError):validate(p)
    def test_nested_unknown_fields_rejected(self):
        p=sample();p['totals']['password']='secret'
        with self.assertRaises(ValueError):validate(p)
    def test_negative_float_boolean_and_huge_rejected(self):
        for value in (-1, 1.5, True, MAX_VALUE+1):
            p=sample();p['totals']['local_answers']=value
            with self.assertRaises(ValueError):validate(p)
    def test_duplicate_keys_rejected(self):
        text=encode(sample()).replace('"schema": 1','"schema": 1, "schema": 1')
        with self.assertRaises(ValueError):decode(text)
    def test_extra_prose_rejected(self):
        with self.assertRaises(ValueError):decode('hello\n'+encode(sample()))
    def test_shell_html_injection_rejected(self):
        for field in ('install_id','louter_version','updated'):
            p=sample();p[field]='$(curl bad) <script>alert(1)</script>'
            with self.assertRaises(ValueError):validate(p)
    def test_size_cap(self):
        with self.assertRaises(ValueError):decode('x'*6001)
    def test_completion_cannot_exceed_attempts(self):
        p=sample();p['totals']['cloud_completions']=4
        with self.assertRaises(ValueError):validate(p)
    def test_only_allowlisted_stats_and_no_legacy(self):
        checkpoint=project(stats())
        self.assertEqual(checkpoint['totals']['local_answers'],5)
        self.assertNotIn('SECRET',json.dumps(checkpoint))
        self.assertEqual(checkpoint['totals']['estimated_input_tokens_avoided'],75000)
    def test_repeat_snapshot_not_added_twice(self):
        c=project(stats());self.assertEqual(project(stats(),c)['totals'],c['totals'])
    def test_reset_accumulates_without_double_count(self):
        c=project(stats());c=project(stats(2,'second'),c)
        self.assertEqual(c['totals']['local_answers'],7)
        self.assertEqual(project(stats(2,'second'),c)['totals']['local_answers'],7)
    def test_regression_fails_closed(self):
        with self.assertRaises(ValueError):project(stats(2),project(stats(5)))
    def test_fallbacks_and_panel_do_not_inflate_avoided_turns(self):
        data=stats();data['days']['2026-09-18'].update(localSuccesses=999,panelRuns=100,cloudFailureFallbackSuccesses=99)
        self.assertEqual(project(data)['totals']['local_answers'],5)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'state'
        self.file=self.root/'louter/telemetry/config.json'
        self.api=FakeAPI()
    def tearDown(self):self.temp.cleanup()
    def enable(self):
        client.atomic(self.root/'louter/stats.json',stats())
        client.atomic(self.file,{'enabled':True,'consent_version':1,'install_id':str(uuid.uuid4()),
                    'github_user_id':12,'github_login':'someone','gh':'gh','sequence':0})
    def test_disabled_has_no_network_or_files(self):
        self.assertIn('OFF',client.send(self.root,api=self.api))
        self.assertEqual(self.api.calls,[]);self.assertFalse(self.root.exists())
    def test_preview_no_network_or_writes(self):
        with patch.object(client,'gh_api',side_effect=AssertionError('network')):
            p,_=client.preview(self.root)
        self.assertEqual(p['install_id'],'created-only-after-opt-in')
        self.assertFalse(self.root.exists())
    def test_noninteractive_on_requires_explicit_yes(self):
        with patch.object(sys.stdin,'isatty',return_value=False), patch.object(client,'gh_api',side_effect=AssertionError('network')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(client.main(['--state-dir',str(self.root),'on']),0)
        self.assertFalse(self.root.exists())
    def test_sends_only_safe_payload_and_one_issue(self):
        self.enable();client.send(self.root,api=self.api,now=1_000_000)
        body=self.api.issues[0]['body'];self.assertNotIn('PROMPT_SECRET',body)
        self.assertNotIn('api_key',body);self.assertNotIn(str(self.root),body)
        self.assertEqual(decode(body)['totals']['local_answers'],5)
        client.send(self.root,api=self.api,now=1_100_000)
        self.assertEqual(len(self.api.issues),1)
        self.assertEqual(decode(self.api.issues[0]['body'])['totals']['local_answers'],5)
    def test_rate_limits_even_manual_calls(self):
        self.enable();client.send(self.root,api=self.api,now=1_000_000)
        count=len(self.api.calls)
        self.assertIn('NOT DUE',client.send(self.root,api=self.api,now=1_000_001))
        self.assertEqual(len(self.api.calls),count)
    def test_failures_rate_limited(self):
        self.enable()
        with self.assertRaises(RuntimeError):client.send(self.root,api=lambda *args:(_ for _ in ()).throw(RuntimeError('offline')),now=1_000_000)
        self.assertIn('NOT DUE',client.send(self.root,api=self.api,now=1_000_001))
        self.assertEqual(self.api.calls,[])
    def test_lost_post_response_recovers_existing_issue(self):
        self.enable();client.send(self.root,api=self.api,now=1_000_000)
        c=client.read_json(self.file);c.pop('issue_number');client.atomic(self.file,c)
        client.send(self.root,api=self.api,now=1_100_000)
        self.assertEqual(len(self.api.issues),1)
    def test_account_change_aborts_without_post(self):
        self.enable();self.api.user={'id':13,'login':'other'}
        with self.assertRaises(RuntimeError):client.send(self.root,api=self.api,now=1_000_000)
        self.assertFalse(self.api.issues)
    def test_closed_issue_is_not_reopened(self):
        self.enable();client.send(self.root,api=self.api,now=1_000_000);self.api.issues[0]['state']='closed'
        self.assertIn('OFF',client.send(self.root,api=self.api,now=1_100_000))
        self.assertFalse(client.read_json(self.file)['enabled'])
    def test_no_gh_token_in_command_or_payload(self):
        import subprocess
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'{}','')) as run:
            client.gh_api('repos/'+REPOSITORY+'/issues','POST',{'body':'safe'})
        args=run.call_args.args[0]
        self.assertIn('--hostname',args);self.assertIn('github.com',args)
        self.assertEqual(run.call_args.kwargs['input'],'{"body": "safe"}')
        self.assertNotIn('shell',run.call_args.kwargs)
    def test_profile_state_isolation(self):
        with patch.dict(os.environ,{'OPENCLAW_PROFILE':'louter-clean','OPENCLAW_HOME':self.temp.name},clear=True):
            self.assertEqual(client.state_root(),Path(self.temp.name)/'.openclaw-louter-clean')
            self.assertEqual(client.state_root(str(self.root)),self.root)
    def test_private_config_permissions(self):
        self.enable();self.assertEqual(self.file.stat().st_mode&0o777,0o600)
    def test_timer_quote(self):
        self.assertIn('%%',client.unit_quote('/x%y'))
        self.assertIn('$$',client.unit_quote('/x$y'))
        with self.assertRaises(ValueError):client.unit_quote('/x\ny')
    def test_off_never_contacts_github(self):
        self.enable()
        with patch.object(client,'schedule'),patch.object(client,'gh_api',side_effect=AssertionError('network')),contextlib.redirect_stdout(io.StringIO()):
            client.main(['--state-dir',str(self.root),'off'])
        self.assertFalse(client.read_json(self.file)['enabled'])
    def test_withdraw_does_not_need_readable_stats(self):
        self.enable();client.send(self.root,api=self.api,now=1_000_000)
        (self.root/'louter/stats.json').write_text('bad json')
        with patch.object(client,'schedule'),patch.object(client,'gh_api',side_effect=lambda e,m='GET',d=None,gh=None:self.api(e,m,d)),contextlib.redirect_stdout(io.StringIO()):
            client.main(['--state-dir',str(self.root),'withdraw','--yes'])
        self.assertTrue(decode(self.api.issues[0]['body'])['withdrawn'])


class AggregatorTests(unittest.TestCase):
    def test_duplicate_retry_counts_once(self):
        p=sample();r=issue(p);r2=issue({**p,'sequence':2},2)
        s,_=collect([r,r2]);self.assertEqual(s['participating_installations'],1)
        self.assertEqual(s['totals']['local_answers'],5)
    def test_out_of_order_uses_largest_sequence(self):
        p=sample(2);new=sample(8,p['install_id'],2)
        s,_=collect([issue(new,2),issue(p,1)]);self.assertEqual(s['totals']['local_answers'],8)
    def test_author_scoped_id_cannot_overwrite_another(self):
        p=sample();s,_=collect([issue(p,user=12),issue(sample(2,p['install_id']),2,user=13)])
        self.assertEqual(s['participating_installations'],2);self.assertEqual(s['totals']['local_answers'],7)
    def test_closed_or_withdrawn_excluded(self):
        p=sample();closed=issue(p,closed=True)
        s,_=collect([closed]);self.assertEqual(s['participating_installations'],0)
        withdrawn={**p,'withdrawn':True,'totals':zero()}
        s,_=collect([issue(p),issue(withdrawn,2)]);self.assertEqual(s['participating_installations'],0)
    def test_exclusion_label(self):
        r=issue(sample());r['labels']=[{'name':'louter-stats-exclude'}]
        self.assertEqual(collect([r])[0]['participating_installations'],0)
    def test_malformed_report_and_pr_ignored(self):
        r=issue(sample());r['body']='$(cat secret)';pr={**issue(sample(),2),'pull_request':{}}
        s,_=collect([r,pr]);self.assertEqual(s['rejected_reports'],1);self.assertEqual(s['participating_installations'],0)
    def test_plain_summary_has_no_fabricated_dollars(self):
        s,rows=collect([issue(sample())]);self.assertIsNone(s['dollars'])
        text=render(s,rows);self.assertIn('Not verified',text);self.assertIn('No default dollar claim',text)
    def test_recomputed_counts_not_increments(self):
        rows=[issue(sample())]
        self.assertEqual(collect(rows)[0]['totals'],collect(rows)[0]['totals'])


if __name__=='__main__':unittest.main(verbosity=2)
