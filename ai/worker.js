// BFF's AI server: a free Cloudflare Worker with Workers AI (the free plan includes 10,000 Neurons a day, roughly 300
// Ask BFF answers; past that, Ask BFF gives its quick answers until midnight UTC). The page sends BFF's rules, the facts
// for the question and the last few messages; this runs Qwen3 30B-A3B (Apache 2.0) on them and streams the reply back.
// Nothing is stored. Only BFF's own pages may call it, requests and replies are capped, and one visitor can ask 20
// questions in 10 minutes. Setup: Workers & Pages > Create > Hello World, name it bff-ai, paste this code, then
// Settings > Bindings > Add > Workers AI with the name AI, and deploy. Put its address in accounts.json ("ai").
const ORIGINS = ['https://bengasparian.github.io'];
const MODEL = '@cf/qwen/qwen3-30b-a3b-fp8';
const SEEN = new Map();
const cors = o => ({ 'Access-Control-Allow-Origin': o, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type', 'Vary': 'Origin' });
const json = (o, s, b) => new Response(JSON.stringify(b), { status: s, headers: { ...cors(o), 'content-type': 'application/json' } });
export default {
  async fetch(req, env) {
    const o = req.headers.get('Origin') || '', ok = ORIGINS.includes(o);
    if (req.method === 'OPTIONS') return new Response(null, { status: ok ? 204 : 403, headers: ok ? cors(o) : {} });
    if (req.method !== 'POST') return new Response('BFF AI: alive', { headers: { 'content-type': 'text/plain' } });
    if (!ok) return new Response('not allowed', { status: 403 });
    const ip = req.headers.get('CF-Connecting-IP') || '?', now = Date.now(), h = (SEEN.get(ip) || []).filter(t => now - t < 600000);
    if (h.length >= 20) return json(o, 429, { error: 'busy' });
    h.push(now); SEEN.set(ip, h); if (SEEN.size > 5000) SEEN.clear();
    let b; try { b = await req.json(); } catch (e) { return json(o, 400, { error: 'bad' }); }
    const sys = String(b.system || ''), msgs = Array.isArray(b.messages) ? b.messages.slice(-6) : [];
    const tot = sys.length + msgs.reduce((s, m) => s + String((m && m.content) || '').length, 0);
    if (!sys.startsWith('You are Ask BFF') || sys.length > 8000 || !msgs.length || tot > 40000) return json(o, 400, { error: 'bad' });
    try {
      const s = await env.AI.run(MODEL, { messages: [{ role: 'system', content: sys }].concat(msgs.map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: String(m.content || '') }))),
        max_tokens: Math.min(1400, +b.max_tokens || 700), temperature: Math.min(1, Math.max(0, +b.temperature || 0.4)), stream: true });
      return new Response(s, { headers: { ...cors(o), 'content-type': 'text/event-stream', 'cache-control': 'no-store' } });
    } catch (e) { return json(o, 503, { error: 'ai', detail: String((e && e.message) || e).slice(0, 200) }); }
  }
};
