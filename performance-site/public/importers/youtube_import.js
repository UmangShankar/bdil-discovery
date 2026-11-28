'use strict';
// YouTube Studio table export. These report-period metrics are not lifetime or 24-hour snapshots.
function parseCsv(text) {
  const rows=[]; let row=[], cell='', quoted=false;
  text=text.replace(/^\uFEFF/,'');
  for(let i=0;i<text.length;i++) { const c=text[i];
    if(quoted) { if(c==='"' && text[i+1]==='"') {cell+='"';i++} else if(c==='"') quoted=false; else cell+=c; }
    else if(c==='"' && cell==='') quoted=true;
    else if(c===',') {row.push(cell);cell=''}
    else if(c==='\n'||c==='\r') {if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x!==''))rows.push(row);row=[];cell=''}
    else cell+=c;
  }
  if(quoted)throw Error('The CSV contains an unfinished quoted field.');
  if(cell!==''||row.length){row.push(cell);rows.push(row)}
  return rows;
}
function youtubeRows(text) {
  const rows=parseCsv(text), headers=rows.shift()||[], required=['Content','Video title','Video publish time','Views'];
  if(required.some(k=>!headers.includes(k)))throw Error('Choose YouTube’s Table data.csv, not Chart data.csv or Totals.csv.');
  const values=rows.map(a=>Object.fromEntries(headers.map((h,i)=>[h,(a[i]||'').trim()]))).filter(r=>r.Content&&r.Content!=='Total');
  if(!values.length)throw Error('No video rows found.');
  if(values.some(r=>!/^[\w-]{11}$/.test(r.Content)))throw Error('A video ID is invalid; no rows were imported.');
  if(new Set(values.map(r=>r.Content)).size!==values.length)throw Error('Duplicate video IDs found in the file; no rows were imported.');
  return values;
}
function youtubeDate(s) { const m=/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})$/.exec(s); return m?`${m[3]}-${String(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].indexOf(m[1])+1).padStart(2,'0')}-${m[2].padStart(2,'0')}`:''; }
function youtubeNumber(s) {if(s===''||s==null)return '';const n=Number(String(s).replace(/,/g,''));if(!Number.isFinite(n)||n<0)throw Error('Invalid numeric value in export.');return String(n)}
function youtubeSeconds(s) {if(!s)return '';const p=s.split(':').map(Number);if(p.some(x=>!Number.isFinite(x))||p.length>3)throw Error('Invalid average view duration.');return String(p.reduce((a,x)=>a*60+x,0));}
function mergeYoutube(posts,channelId,rows,start,end) {
  if(!start||!end||start>end)throw Error('Enter a valid report date range.');
  let created=0,updated=0;const result=posts.map(p=>({...p}));
  for(const r of rows){
    const id=r.Content; let p=result.find(x=>x.channelId===channelId&&x.platform==='YouTube'&&(x.youtubeId===id||x.url===`https://www.youtube.com/watch?v=${id}`||x.url===`https://www.youtube.com/shorts/${id}`));
    if(p)updated++;else{p={id:crypto.randomUUID(),channelId,platform:'YouTube',youtubeId:id,format:'Unclassified',title:r['Video title'],url:`https://www.youtube.com/watch?v=${id}`};result.push(p);created++;}
    // Do not overwrite user labels, manually entered snapshots, or post time.
    p.youtubeId=id;p.reportStart=start;p.reportEnd=end;p.reportViews=youtubeNumber(r.Views);p.reportEngaged=youtubeNumber(r['Engaged views']);p.reportWatchHours=youtubeNumber(r['Watch time (hours)']);p.reportAverageSeconds=youtubeSeconds(r['Average view duration']);p.reportAvgPercent=youtubeNumber(r['Average percentage viewed (%)']);p.reportStayed=youtubeNumber(r['Stayed to watch (%)']);p.reportSubscribers=youtubeNumber(r.Subscribers);p.reportUnique=youtubeNumber(r['Unique viewers']);
    if(!p.duration)p.duration=youtubeNumber(r.Duration);
    if(!p.published && !p.publishedDate)p.publishedDate=youtubeDate(r['Video publish time']);
  }
  return {posts:result,created,updated};
}
if(typeof module!=='undefined')module.exports={parseCsv,youtubeRows,youtubeDate,youtubeNumber,youtubeSeconds,mergeYoutube};
