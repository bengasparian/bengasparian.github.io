// BFF's timer (a free Cloudflare Worker with Cron Triggers). GitHub starts its own scheduled jobs late or skips them
// when it is busy (Nov 2026: about 1 in 12 of the every-30-minutes runs ran), so this starts them on time instead:
//   every 15 minutes   the scores job (scores.yml: final scores, box scores, news, lines, BFF Originals)
//   every 3 hours      the data update (update.yml: projections, values, the page)
// It needs one secret, GH_TOKEN: a fine-grained GitHub token for this repository only, with "Actions: Read and write"
// (it can start and list workflow runs, nothing else). The workflows' own timers stay on as a backup.
// Before starting a job it checks that no data job is already waiting its turn: the data jobs share one queue, and a
// new run would push a waiting one out of it. (The free plan allows 5 cron triggers and 10 ms of CPU a run: it reads
// only the 12 latest runs.)
const REPO = 'bengasparian/bengasparian.github.io';
const DATA = ['.github/workflows/scores.yml', '.github/workflows/update.yml', '.github/workflows/photos.yml'];
const WAITING = ['queued', 'pending', 'waiting', 'requested'];
async function gh(env, path, body) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'bff-timer', 'X-GitHub-Api-Version': '2022-11-28' },
    body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.status === 204 ? {} : r.json().catch(() => ({}));
}
async function start(env, wf) {
  const runs = (await gh(env, 'actions/runs?per_page=12')).workflow_runs || [];
  const busy = runs.filter(x => DATA.includes(x.path) && WAITING.includes(x.status));
  const same = runs.some(x => x.path === `.github/workflows/${wf}` && (WAITING.includes(x.status) || x.status === 'in_progress'));
  if (busy.length || same) return `${wf}: not started (${busy.length ? 'a data job is waiting its turn' : 'one is already running'})`;
  await gh(env, `actions/workflows/${wf}/dispatches`, { ref: 'main' });
  return `${wf}: started`;
}
export default {
  async scheduled(event, env, ctx) {
    const wf = event.cron === '23 */3 * * *' ? 'update.yml' : 'scores.yml';
    ctx.waitUntil(start(env, wf).then(m => console.log(m), e => console.log('failed:', e.message)));
  },
  // visiting the Worker's address shows that it is alive (it starts nothing)
  async fetch() { return new Response('BFF timer: starts the scores job every 15 minutes and the data update every 3 hours.', { headers: { 'content-type': 'text/plain' } }); }
};
