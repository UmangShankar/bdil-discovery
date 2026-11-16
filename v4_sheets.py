"""Pure, credential-free Sheets write planner. CLI is always dry-run.

Input snapshot: {spreadsheet_id, sheet_name, headers, rows: [{row_number, values}]}.
Candidate reports keyed by exact source URL. No production writes are executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
from v4_handoff import validate

SPREADSHEET = '1Oh4ginalP3ZMirlElEQ2ADyMu-PifJRBeVTrMkbqJEE'
HEADERS = ['candidate_id','source_id','backlog_row','source_url','rank','hook','start','end',
           'captions','category','score','reviewed_by']


def plan(snapshot, reports):
    if snapshot.get('spreadsheet_id') != SPREADSHEET or snapshot.get('sheet_name') != 'backlog':
        raise ValueError('wrong spreadsheet/tab')
    headers = snapshot['headers']
    required = ['status','url','hook','start','end','captions','id']
    if any(headers.count(k) != 1 for k in required) or [headers.index(k) for k in ('start','end','captions')] != [headers.index('hook')+i for i in (1,2,3)]:
        raise ValueError('schema mismatch; re-inspect live schema')
    def column(index):
        result = ''
        while index:
            index,rem = divmod(index-1,26)
            result = chr(65+rem)+result
        return result
    hook_column = column(headers.index('hook')+1)
    captions_column = column(headers.index('captions')+1)
    schema_hash = hashlib.sha256(json.dumps(headers).encode()).hexdigest()
    appended, patches, held = [], [], []
    existing = set(snapshot.get('candidate_ids',[]))
    for row in snapshot['rows']:
        values = list(row['values']) + ['']*len(headers)
        record = dict(zip(headers,values))
        if record['status'] != 'to-cut':
            continue
        source_id = record['id']
        url = record['url']
        report = reports.get(url)
        if not report:
            held.append({'row':row['row_number'],'reason':'no matching source report'})
            continue
        if report.get('source_url') != url or not source_id:
            held.append({'row':row['row_number'],'reason':'source identity mismatch'})
            continue
        if not report.get('candidates'):
            held.append({'row':row['row_number'],'reason':'no qualifying candidates'})
        eligible = []
        for c in report['candidates']:
            try:
                validate(c,report['duration'],reviewed=True)
            except (ValueError,TypeError):
                held.append({'row':row['row_number'],'rank':c.get('rank'),'reason':'unverified or invalid candidate'})
                continue
            key = hashlib.sha256(f"{source_id}:{c['start']:.3f}:{c['end']:.3f}".encode()).hexdigest()[:20]
            eligible.append(c)
            if key in existing:
                continue
            existing.add(key)
            appended.append([key,source_id,row['row_number'],url,c['rank'],c['hook'],c['start'],c['end'],
                             c['captions'],c.get('category',''),c.get('score',0),c['reviewed_by']])
        # One reviewed top candidate can fill the legacy scalar contract only if all four cells are empty.
        if eligible and not any(record[k] for k in ('hook','start','end','captions')):
            c = min(eligible,key=lambda x:x['rank'])
            patches.append({'range':f"backlog!{hook_column}{row['row_number']}:{captions_column}{row['row_number']}",
                            'values':[[c['hook'],c['start'],c['end'],c['captions']]],
                            'precondition':{'source_id':source_id,'url':url,'status':'to-cut','destination':'all four cells empty','headers_sha256':schema_hash}})
    return {'dry_run':True,'spreadsheet_id':SPREADSHEET,'candidate_table':'v4_candidates',
            'observed_headers':headers,'legacy_columns':f'{hook_column}:{captions_column}','candidate_headers':HEADERS,'append_rows':appended,'legacy_patches':patches,'held':held,
            'write_policy':'Re-read values/formulas/validation and candidate IDs immediately before applying. Never execute this plan blind.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot',type=Path,required=True)
    ap.add_argument('--reports',type=Path,nargs='+',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--dry-run',action='store_true',default=True)
    a = ap.parse_args()
    reports = [json.loads(p.read_text()) for p in a.reports]
    result = plan(json.loads(a.snapshot.read_text()),{r['source_url']:r for r in reports})
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(f"Dry run: {len(result['append_rows'])} table rows, {len(result['legacy_patches'])} legacy patches, {len(result['held'])} held")

if __name__ == '__main__':
    main()
