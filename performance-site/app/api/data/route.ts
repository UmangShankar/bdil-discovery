import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '../../chatgpt-auth';
import seed from '../../seed.json';
export const dynamic = 'force-dynamic';
export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return Response.json({error:'Sign in required'}, {status:401});
  if (!env.DB) return Response.json({error:'Storage unavailable'}, {status:503});
  const row = await env.DB.prepare('SELECT data, version FROM dashboards WHERE user_id = ?').bind(user.userId).first<{data:string,version:number}>();
  return Response.json(row ? {data:JSON.parse(row.data),version:row.version} : {data:seed,version:0}, {headers:{'Cache-Control':'no-store'}});
}
export async function PUT(request:Request) {
  const user = await getChatGPTUser();
  if (!user) return Response.json({error:'Sign in required'}, {status:401});
  if (!env.DB) return Response.json({error:'Storage unavailable'}, {status:503});
  const body=await request.json() as {data?:{channels?:unknown[],posts?:unknown[],daily?:unknown[]},version?:number};
  if (!body.data || !Array.isArray(body.data.channels)||!Array.isArray(body.data.posts)||!Array.isArray(body.data.daily)||!Number.isInteger(body.version)) return Response.json({error:'Invalid data'}, {status:400});
  const data=JSON.stringify(body.data);if(data.length>2_000_000)return Response.json({error:'Data too large'}, {status:413});
  if(body.version===0){const r=await env.DB.prepare('INSERT INTO dashboards (user_id, data, version) VALUES (?, ?, 1) ON CONFLICT(user_id) DO NOTHING').bind(user.userId,data).run();if(!r.meta.changes)return Response.json({error:'Data changed elsewhere; reload before saving.'},{status:409});return Response.json({version:1})}
  const r=await env.DB.prepare('UPDATE dashboards SET data = ?, version = version + 1 WHERE user_id = ? AND version = ?').bind(data,user.userId,body.version).run();
  if(!r.meta.changes)return Response.json({error:'Data changed elsewhere; reload before saving.'},{status:409});return Response.json({version:body.version!+1});
}
