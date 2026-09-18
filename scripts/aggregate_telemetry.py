#!/usr/bin/env python3
import sys as _louter_sys
_louter_sys.dont_write_bytecode = True
"""Rebuild public totals from current, strictly validated GitHub issue snapshots."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
from telemetry import gh_api
from telemetry_schema import REPOSITORY, TITLE, METRICS, decode, integer, zero


def collect(issues):
    latest = {}
    withdrawn = set()
    rejected = 0
    for issue in issues:
        if 'pull_request' in issue or not str(issue.get('title', '')).startswith(TITLE):
            continue
        try:
            report = decode(issue.get('body'))
            user = issue['user']
            if type(user.get('id')) is not int or user['id'] < 1 or user.get('type') != 'User':
                raise ValueError('Invalid report author')
            if type(issue.get('number')) is not int or issue['number'] < 1:
                raise ValueError('Invalid issue number')
            if issue['title'] != TITLE + report['install_id']:
                raise ValueError('Title/body identity mismatch')
            key = (user['id'], report['install_id'])
            labels = {x.get('name') if isinstance(x, dict) else x for x in issue.get('labels', [])}
            # Closing or withdrawing any duplicate excludes this installation.
            if report['withdrawn'] or issue.get('state') == 'closed' or 'louter-stats-exclude' in labels:
                withdrawn.add(key)
                continue
            if issue.get('state') != 'open':
                raise ValueError('Invalid issue state')
            rank = (report['sequence'], -issue['number'])
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank, {'issue_number': issue['number'], **report})
        except (ValueError, KeyError, TypeError):
            rejected += 1
    reports = [entry[1] for key, entry in latest.items() if key not in withdrawn]
    reports.sort(key=lambda row: row['issue_number'])
    totals = zero()
    for report in reports:
        for key in METRICS:
            totals[key] = integer(totals[key] + report['totals'][key])
    today = dt.datetime.now(dt.timezone.utc).date()
    active = sum((today - dt.date.fromisoformat(r['updated'])).days <= 30 for r in reports)
    summary = {
        'schema': 1,
        'updated': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'repository': REPOSITORY,
        'participating_installations': len(reports),
        'reports_updated_within_30_days': active,
        'excluded_installations': len(withdrawn),
        'rejected_reports': rejected,
        'totals': totals,
        'methodology': 'Latest cumulative snapshot per GitHub-author/installation pair; never sum retries. Self-reported, not verified savings.',
        'dollars': None,
    }
    return summary, reports


def fetch_issues():
    rows = []
    for page in range(1, 101):
        response = gh_api(f'repos/{REPOSITORY}/issues?state=all&per_page=100&page={page}&sort=created&direction=asc')
        if not isinstance(response, list):
            raise ValueError('Unexpected GitHub issues response')
        rows.extend(response)
        if len(response) < 100:
            return rows
    raise RuntimeError('Issue pagination limit reached; refusing to publish partial totals')


def render(summary, reports):
    totals = summary['totals']
    metric_rows = [
        ('Participating installations', summary['participating_installations']),
        ('Reports updated within 30 days', summary['reports_updated_within_30_days']),
        ('Locally completed direct turns', totals['local_answers']),
        ('Estimated input tokens avoided', totals['estimated_input_tokens_avoided']),
        ('Estimated output tokens avoided', totals['estimated_output_tokens_avoided']),
        ('Main-agent handoffs', totals['main_agent_handoffs']),
        ('Cloud calls attempted / completed', f'{totals["cloud_attempts"]:,} / {totals["cloud_completions"]:,}'),
        ('Ask Around runs', totals['ask_around_runs']),
        ('Local answers after cloud failures', totals['local_fallback_answers']),
    ]
    lines = ['# Louter community savings', '',
             '**Opt-in, public, self-reported statistics. Not verified reductions in cloud bills.**', '',
             'Updated: ' + summary['updated'], '', '| Metric | Total |', '|---|---:|']
    lines += [f'| {name} | {value:,} |' if isinstance(value, int) else f'| {name} | {value} |'
              for name, value in metric_rows]
    lines += ['', '## What these numbers mean', '',
              'Local answers are direct local completions, not a count of proven avoided cloud API requests. '
              'Token totals use each client\'s configured counterfactual assumptions. The main agent might '
              'itself be local. Ask Around and failure fallbacks are separate counters and do not inflate avoided-turn estimates.', '',
              '**No default dollar claim.** For assumed prices I and O in USD per million tokens: '
              '`gross API-equivalent estimate = input_tokens / 1,000,000 * I + output_tokens / 1,000,000 * O`. '
              'This excludes cloud/panel costs, caching, electricity and subscriptions; it is not net savings.', '',
              'Retries replace one cumulative installation snapshot. Stats resets are handled by the client\'s '
              'durable checkpoint. Reports are linked to public GitHub accounts and may be inaccurate or fabricated; '
              'this is not independently verified adoption or cost data.', '',
              '## Data and controls', '',
              '[Machine-readable totals](totals.json) · [Latest accepted reports](reports.json) · '
              f'[Setup and privacy](https://github.com/{REPOSITORY}/blob/main/community/README.md)', '',
              'Telemetry is disabled by default. Turning it off stops new uploads but leaves previously shared data. '
              'Withdraw or close a report to remove it from current totals on the next rebuild. Git history, '
              'issue edit history and third-party copies may remain.', '',
              f'Excluded installations: {summary["excluded_installations"]}. Rejected malformed reports: {summary["rejected_reports"]}.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issues-json', type=Path, help='Offline fixture; no network when provided')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.issues_json and os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
        raise RuntimeError('Collector must run in the intended repository')
    issues = json.loads(args.issues_json.read_text()) if args.issues_json else fetch_issues()
    summary, reports = collect(issues)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'totals.json').write_text(json.dumps(summary, indent=2) + '\n')
    (args.output / 'reports.json').write_text(json.dumps(reports, indent=2) + '\n')
    (args.output / 'README.md').write_text(render(summary, reports))
    (args.output / '.nojekyll').write_text('')
    site = Path(__file__).resolve().parents[1] / 'community/index.html'
    if site.exists():
        shutil.copyfile(site, args.output / 'index.html')
    print(f'AGGREGATED: {len(reports)} installations; {summary["rejected_reports"]} rejected reports')


if __name__ == '__main__':
    main()
