'use strict';
// TikTok's export may contain unescaped quotation marks in descriptions, so
// parse each record around its stable TikTok URL and numeric trailing fields.
function tiktokRows(text) {
  text=text.replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
  const first=text.indexOf('\n'); if(first<0)throw Error('File is empty.');
  const header=text.slice(0,first);
  for(const name of ['Video title','Video link','Post time','Total likes','Total comments','Total shares','Total views'])if(!header.includes('"'+name+'"'))throw Error('Choose Content.csv from the TikTok Content ZIP.');
  const re=/^"([^"\n]+)","([\s\S]*?)","(https:\/\/www\.tiktok\.com\/@[^"\s/]+\/video\/\d+)","([^"\n]+)","(\d+)","(\d+)","(\d+)","(\d+)"\s*(?=\n|$)/gm;
  const body=text.slice(first+1);let rows=[],last=0,m;
  while((m=re.exec(body))){if(body.slice(last,m.index).trim())throw Error('Could not safely parse all TikTok rows; no data imported.');rows.push({captured:m[1],title:m[2].replace(/""/g,'"'),url:m[3],postDate:m[4],likes:m[5],comments:m[6],shares:m[7],views:m[8]});last=re.lastIndex;}
  if(!rows.length||body.slice(last).trim())throw Error('Could not safely parse all TikTok rows; no data imported.');
  if(new Set(rows.map(r=>r.url.match(/\/video\/(\d+)/)[1])).size!==rows.length)throw Error('Duplicate video IDs found.');return rows;
}
function tiktokDate(s,year){const m=/^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})$/.exec(s);if(!m)throw Error('Unrecognised date: '+s);const month=['January','February','March','April','May','June','July','August','September','October','November','December'].indexOf(m[1])+1;const day=+m[2];const d=new Date(Date.UTC(year,month-1,day));if(d.getUTCMonth()!==month-1||d.getUTCDate()!==day)throw Error('Invalid date: '+s);return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`}
function mergeTiktok(posts,channelId,rows,year){
 if(!/^\d{4}$/.test(String(year)))throw Error('Enter the year shown by the export.');let created=0,updated=0,result=posts.map(p=>({...p}));
 for(const r of rows){let id=r.url.match(/\/video\/(\d+)/)[1];let capture=tiktokDate(r.captured,+year),date=tiktokDate(r.postDate,+year);if(date>capture)throw Error('A post date is later than its capture date. The file may cross a year boundary; import stopped.');let p=result.find(x=>x.channelId===channelId&&x.platform==='TikTok'&&(x.tiktokId===id||x.url?.includes('/video/'+id)));if(p)updated++;else{p={id:crypto.randomUUID(),channelId,platform:'TikTok',format:'Unclassified',tiktokId:id,title:r.title.split(/\s+DESCRIPTION\s+/i)[0].trim(),url:r.url};result.push(p);created++}p.tiktokId=id;
 // Preserve the previous capture and the new one, with one observation per date.
 let history=Array.isArray(p.tiktokHistory)?[...p.tiktokHistory]:[];
 if(p.tiktokCapture&&p.tiktokViews!==undefined&&p.tiktokViews!=='')history.push({date:p.tiktokCapture,views:Number(p.tiktokViews)});
 history.push({date:capture,views:Number(r.views)});
 p.tiktokHistory=Array.from(new Map(history.map(x=>[x.date,x])).values()).sort((a,b)=>a.date.localeCompare(b.date));
 p.tiktokCapture=capture;p.tiktokViews=r.views;p.tiktokLikes=r.likes;p.tiktokComments=r.comments;p.tiktokShares=r.shares;if(!p.published&&!p.publishedDate)p.publishedDate=date;}
 return {posts:result,created,updated};
}
if(typeof module!=='undefined')module.exports={tiktokRows,tiktokDate,mergeTiktok};
