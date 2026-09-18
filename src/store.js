import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

export const scopeKey = ctx => {
  if (!ctx?.agentId || !ctx?.sessionKey) return null;
  return createHash('sha256').update(`${ctx.agentId}\0${ctx.sessionKey}`).digest('hex');
};
const fresh = () => ({ version: 1, since: new Date().toISOString(), days: {}, legacy: null });
export class Store {
  constructor(root, opts) { this.root = root; this.opts = opts; this.queue = Promise.resolve(); }
  async readJson(file, fallback) {
    try { return JSON.parse(await fs.readFile(file, 'utf8')); }
    catch (e) { if (e.code === 'ENOENT') return fallback; throw e; }
  }
  async atomic(file, data) {
    await fs.mkdir(path.dirname(file), { recursive: true, mode: 0o700 });
    const tmp = `${file}.${process.pid}.${randomUUID()}.tmp`;
    try {
      await fs.writeFile(tmp, JSON.stringify(data, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
      await fs.rename(tmp, file);
    } finally { await fs.unlink(tmp).catch(() => {}); }
  }
  async lock(fn) {
    await fs.mkdir(this.root, { recursive: true, mode: 0o700 });
    const lock = path.join(this.root, '.stats-lock');
    const start = Date.now();
    for (;;) {
      try { await fs.mkdir(lock, { mode: 0o700 }); break; }
      catch (e) {
        if (e.code !== 'EEXIST') throw e;
        const st = await fs.stat(lock).catch(() => null);
        if (st && Date.now() - st.mtimeMs > 120000) await fs.rmdir(lock).catch(() => {});
        if (Date.now() - start > 1500) throw new Error('Stats busy');
        await new Promise(r => setTimeout(r, 30));
      }
    }
    try { return await fn(); } finally { await fs.rmdir(lock).catch(() => {}); }
  }
  event(scope, e) {
    const work = this.queue.catch(() => {}).then(() => this.lock(async () => {
      const file = path.join(this.root, 'stats.json');
      const s = await this.readJson(file, fresh());
      const day = new Date().toISOString().slice(0, 10);
      const d = s.days[day] ||= {};
      for (const [key, n] of Object.entries(e.counts || {})) {
        if (!Number.isFinite(n) || n < 0) continue;
        d[key] = (d[key] || 0) + n;
      }
      await this.atomic(file, s);
      if (scope) {
        const dir = path.join(this.root, 'sessions', scope);
        await fs.mkdir(dir, { recursive: true, mode: 0o700 });
        const eventFile = path.join(dir, 'events.jsonl');
        const stat = await fs.stat(eventFile).catch(() => null);
        if (stat?.size > 2_000_000) await fs.rename(eventFile, eventFile + '.previous').catch(() => {});
        // Intentionally excludes prompts, answers, credentials and raw provider errors.
        await fs.appendFile(eventFile, JSON.stringify({ at: new Date().toISOString(), ...e }) + '\n', { mode: 0o600 });
      }
    }));
    this.queue = work;
    return work;
  }
  async totals(period = 'all') {
    await this.queue.catch(() => {});
    const s = await this.readJson(path.join(this.root, 'stats.json'), fresh());
    const now = new Date();
    let after = '';
    if (period === 'today') after = now.toISOString().slice(0, 10);
    if (period === 'week') after = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);
    if (period === 'month') after = now.toISOString().slice(0, 7) + '-01';
    const sum = {};
    for (const [day, values] of Object.entries(s.days)) if (day >= after) for (const [k, v] of Object.entries(values)) sum[k] = (sum[k] || 0) + v;
    return { since: s.since, counts: sum, legacy: s.legacy };
  }
  async savePanel(scope, panel) {
    if (!scope) throw new Error('A session identity is required to save panel responses.');
    const dir = path.join(this.root, 'sessions', scope, 'panels');
    await this.atomic(path.join(dir, panel.id + '.json'), panel);
    await this.prune(scope);
  }
  async prune(scope) {
    const dir = path.join(this.root, 'sessions', scope, 'panels');
    const names = (await fs.readdir(dir).catch(() => [])).filter(n => /^[a-f0-9-]{36}\.json$/.test(n));
    const rows = await Promise.all(names.map(async name => ({ name, st: await fs.stat(path.join(dir, name)).catch(() => null) })));
    rows.sort((a, b) => (b.st?.mtimeMs || 0) - (a.st?.mtimeMs || 0));
    for (let i = 0; i < rows.length; i++) if (i >= this.opts.maxPanelsPerSession || (rows[i].st && Date.now() - rows[i].st.mtimeMs > this.opts.retentionDays * 86400000)) await fs.unlink(path.join(dir, rows[i].name)).catch(() => {});
  }
  async cleanup() {
    const dir = path.join(this.root, 'sessions');
    const entries = await fs.readdir(dir, { withFileTypes: true }).catch(() => []);
    for (const e of entries) {
      if (!e.isDirectory() || !/^[a-f0-9]{64}$/.test(e.name)) continue;
      await this.prune(e.name);
      for (const name of ['events.jsonl', 'events.jsonl.previous']) {
        const file = path.join(dir, e.name, name);
        const st = await fs.stat(file).catch(() => null);
        if (st && Date.now() - st.mtimeMs > this.opts.retentionDays * 86400000) await fs.unlink(file).catch(() => {});
      }
    }
  }
  async panel(scope, id) {
    if (!scope) return null;
    await this.prune(scope);
    const dir = path.join(this.root, 'sessions', scope, 'panels');
    if (id && !/^[a-f0-9-]{36}$/.test(id)) return null;
    if (!id) {
      const names = (await fs.readdir(dir).catch(() => [])).filter(n => /^[a-f0-9-]{36}\.json$/.test(n));
      const rows = await Promise.all(names.map(async name => ({ name, time: (await fs.stat(path.join(dir, name))).mtimeMs })));
      rows.sort((a, b) => b.time - a.time);
      if (!rows.length) return null;
      id = rows[0].name.slice(0, -5);
    }
    return this.readJson(path.join(dir, id + '.json'), null);
  }
}
