"""Strict public savings schema shared by the optional client and GitHub collector."""
import datetime as dt
import json
import math
import re

REPOSITORY = 'liseman/openclaw-louter'
MARKER = '<!-- louter-public-savings:v1 -->'
TITLE = '[Louter savings] '
MAX_VALUE = 9_000_000_000_000_000
METRICS = {
    'local_answers': ('autoLocal', 'forcedLocal'),
    'estimated_input_tokens_avoided': ('avoidedInputEstimate',),
    'estimated_output_tokens_avoided': ('avoidedOutputEstimate',),
    'main_agent_handoffs': ('autoHandoffs',),
    'cloud_attempts': ('cloudAttempts',),
    'cloud_completions': ('cloudSuccesses',),
    'ask_around_runs': ('panelRuns',),
    'local_fallback_answers': ('cloudFailureFallbackSuccesses',),
}
UUID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$')
VERSION = re.compile(r'^\d{1,4}\.\d{1,4}\.\d{1,4}(?:-[a-zA-Z0-9.-]{1,40})?$')


def zero():
    return dict.fromkeys(METRICS, 0)


def integer(value):
    if type(value) is not int or not 0 <= value <= MAX_VALUE:
        raise ValueError('Counters must be nonnegative bounded integers')
    return value


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Expected object')
    fields = {'schema', 'install_id', 'sequence', 'louter_version', 'updated', 'withdrawn', 'totals'}
    if set(payload) != fields or type(payload['schema']) is not int or payload['schema'] != 1:
        raise ValueError('Unknown/missing fields or schema')
    if not isinstance(payload['install_id'], str) or not UUID.fullmatch(payload['install_id']):
        raise ValueError('Invalid installation ID')
    if not isinstance(payload['louter_version'], str) or not VERSION.fullmatch(payload['louter_version']):
        raise ValueError('Invalid version')
    integer(payload['sequence'])
    if type(payload['withdrawn']) is not bool:
        raise ValueError('Invalid withdrawal flag')
    date = payload['updated']
    if not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        raise ValueError('Invalid reporting date')
    if dt.date.fromisoformat(date) > dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1):
        raise ValueError('Future reporting date')
    totals = payload['totals']
    if not isinstance(totals, dict) or set(totals) != set(METRICS):
        raise ValueError('Unknown/missing counter fields')
    for value in totals.values():
        integer(value)
    if totals['cloud_completions'] > totals['cloud_attempts']:
        raise ValueError('Completed calls exceed attempted calls')
    if payload['withdrawn'] and any(totals.values()):
        raise ValueError('Withdrawal must contain zero counters')
    return payload


def encode(payload):
    validate(payload)
    return MARKER + '\n```json\n' + json.dumps(payload, indent=2, sort_keys=True) + '\n```\n'


def decode(body):
    if not isinstance(body, str) or len(body.encode()) > 6000:
        raise ValueError('Oversized or nontext report')
    prefix = MARKER + '\n```json\n'
    if not body.startswith(prefix) or not body.endswith('\n```\n'):
        raise ValueError('Invalid report envelope')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return validate(json.loads(body[len(prefix):-5], object_pairs_hook=unique))


def project(stats, checkpoint=None):
    """Only aggregate numeric counters; never read prompts, sessions or credentials."""
    if not isinstance(stats, dict) or stats.get('version') != 1 or not isinstance(stats.get('days'), dict):
        raise ValueError('Unsupported local stats format')
    epoch = stats.get('since')
    if not isinstance(epoch, str) or not epoch:
        raise ValueError('Missing stats epoch')
    raw = zero()
    for day, counts in stats['days'].items():
        if not isinstance(counts, dict):
            raise ValueError('Invalid daily counters')
        for metric, source_keys in METRICS.items():
            for key in source_keys:
                value = counts.get(key, 0)
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid local counter')
                raw[metric] += math.floor(value)
    checkpoint = checkpoint or {}
    previous = checkpoint.get('raw', zero()) if checkpoint.get('epoch') == epoch else zero()
    cumulative = checkpoint.get('totals', zero())
    if any(raw[key] < previous[key] for key in METRICS):
        raise ValueError('Stats decreased without an epoch change; refusing to guess')
    totals = {key: integer(cumulative[key] + raw[key] - previous[key]) for key in METRICS}
    return {'epoch': epoch, 'raw': raw, 'totals': totals}
