"""Local previews, explicit review gate and existing-cutter rendering. No uploads."""
import argparse
import importlib.util
import json
import math
import subprocess
from pathlib import Path


def validate(candidate, duration, reviewed=False):
    a, b = candidate.get('start'), candidate.get('end')
    if (isinstance(a, bool) or isinstance(b, bool) or not isinstance(a,(int,float))
            or not isinstance(b,(int,float)) or not math.isfinite(a) or not math.isfinite(b)
            or not 0 <= a < b <= duration or not 12 <= b-a <= 30.001):
        raise ValueError('invalid/out-of-media candidate timestamps')
    if not all(isinstance(candidate.get(k),str) and candidate[k].strip() for k in ('hook','captions')):
        raise ValueError('hook and captions required')
    from v4_quality import ending_reasons, payoff_reasons
    ending_errors = ending_reasons(candidate['captions'])
    if reviewed:
        ending_errors += payoff_reasons(candidate.get('actual_payoff') or candidate.get('payoff') or candidate['captions'])
    if ending_errors:
        raise ValueError('clip ending rejected: ' + '; '.join(dict.fromkeys(ending_errors)))
    if reviewed and (candidate.get('review_required') is not False
                     or candidate.get('semantic_verified') is not True
                     or not candidate.get('reviewed_by')
                     or candidate.get('verification_coverage',0) < 1):
        raise ValueError('candidate requires documented content review and complete media evidence')
    return a,b


def previews(video, candidates, folder, duration):
    from v4_media import probe
    duration = min(duration,probe(video)['duration'])
    folder = Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    outputs = []
    for i,c in enumerate(candidates,1):
        a,b = validate(c,duration)
        out = folder / f'candidate-{i:02d}.mp4'
        if out.exists():
            raise ValueError(f'preview already exists: {out}')
        subprocess.run(['ffmpeg','-v','error','-threads','2','-ss',str(a),'-i',str(video),
                        '-t',str(b-a),'-map','0:v:0','-map','0:a:0?',
                        '-vf','scale=640:-2','-c:v','libx264','-threads','2','-preset','veryfast',
                        '-crf','24','-c:a','aac','-movflags','+faststart',str(out)],check=True,timeout=180)
        observed = probe(out)['duration']
        if abs(observed-(b-a)) > .25:
            raise ValueError('preview duration differs from candidate')
        outputs.append({'rank':i,'file':str(out.resolve()),'duration':observed,
                        'source_start':a,'source_end':b,'status':'decoded_preview'})
    return outputs


def render_with_cutter(video, candidate, cutter, output, caption_model=None):
    """Use unchanged cut/build_ass/render functions; never call upload or backlog."""
    from v4_media import probe
    import tempfile
    validate(candidate,probe(video)['duration'],reviewed=True)
    spec = importlib.util.spec_from_file_location('bdil_existing_cutter',cutter)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('refusing to overwrite render')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.v4-render-',dir=output.parent) as work:
        raw = module.cut_local(Path(video),candidate['start'],candidate['end'],Path(work)/'raw')
        ass = Path(work)/'captions.ass'
        # Sentence captions lack word alignment; preserve them in JSON rather than invent karaoke timing.
        caption_words = []
        if caption_model:
            from v4_transcript import words
            caption_words = words(raw,caption_model)
        module.build_ass(caption_words,candidate['hook'],candidate['end']-candidate['start'],ass)
        rendered = Path(work)/'rendered.mp4'
        module.render(raw,ass,rendered)
        if abs(probe(rendered)['duration']-(candidate['end']-candidate['start'])) > .25:
            raise ValueError('cutter changed selected duration')
        from v4_quality import audit_export
        ending_audit = audit_export(rendered,
                                   candidate.get('actual_payoff') or candidate.get('payoff') or candidate['captions'],
                                   model=caption_model or 'small')
        if not ending_audit['passed']:
            raise ValueError('final export ending rejected: ' + '; '.join(ending_audit['reasons']))
        import os
        os.link(rendered,output)  # atomic create; cannot clobber an existing output
    return {'file':str(output),'duration':probe(output)['duration'], 'upload':False,
            'ending_audit':ending_audit,
            'captions':'local Whisper word timing' if caption_model else 'hook only; transcript retained in candidate JSON'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('json',type=Path)
    ap.add_argument('--rank',type=int,default=1)
    ap.add_argument('--video',type=Path,required=True)
    ap.add_argument('--cutter',type=Path,default=Path('../clipper/clip.py'))
    ap.add_argument('--caption-model',help='Optional locally cached Whisper model for cutter karaoke captions')
    ap.add_argument('--render',type=Path,required=True)
    ap.add_argument('--thumbnail',type=Path,required=True,help='Required 1080x1920 Shorts cover')
    ap.add_argument('--short-title',required=True,help='Readable title for the dated delivery folder')
    ap.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parent/'packages')
    ap.add_argument('--package-date',help='ISO date; defaults to today in Europe/London')
    ap.add_argument('--thumbnail-prompt',type=Path)
    a = ap.parse_args()
    report = json.loads(a.json.read_text())
    c = next((c for c in report['candidates'] if c['rank']==a.rank),None)
    if c is None:
        ap.error('rank absent')
    try:
        from v4_package import build_package,thumbnail_size
        thumbnail_size(a.thumbnail)
        review=c.get('payoff_review',{})
        if not isinstance(review,dict) or not all(review.get(k) for k in ('setup','resolution','why_it_resolves','reviewed_by')):
            raise ValueError('reviewed candidate requires a complete payoff_review before rendering')
        result=render_with_cutter(a.video,c,a.cutter,a.render,a.caption_model)
        source=c.get('source') or {'url':report.get('source_url'),'creator':report.get('creator')}
        meta={**c,**result,'title':c.get('title') or c['hook'],
              'description':c.get('description') or c['captions']+'\n\nSource: '+str(report.get('source_url') or a.video),
              'tags':c.get('tags') or ['GTA','Gaming','Shorts'],'categoryId':c.get('categoryId','20'),
              'source':source,'publication_status':'local review only'}
        package=build_package(a.render,a.thumbnail,meta,root=a.package_root,short_title=a.short_title,
                              day=a.package_date,thumbnail_prompt=a.thumbnail_prompt)
        print(json.dumps({**result,'package':str(package),'thumbnail_required':True}))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        ap.exit(2,str(exc)+'\n')

if __name__ == '__main__':
    main()
