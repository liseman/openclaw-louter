/** Louter configuration. No provider credentials are read here. */
export const VERSION = '0.2.5';
export const DEFAULTS = {
  agentIds: ['main'],
  routes: {
    local: { kind: 'local', model: 'qwen', endpoint: 'http://127.0.0.1:18080/v1/chat/completions', protocol: 'openai', contextTokens: 4096, timeoutMs: 30000, maxTokens: 384, enabled: true },
    astra: { kind: 'openclaw', model: 'openai/gpt-6-astra', agentId: 'louter-astra', timeoutMs: 30000, maxTokens: 768, enabled: true },
    claude: { kind: 'openclaw', model: 'anthropic/claude-opus-5', agentId: 'louter-claude', timeoutMs: 30000, maxTokens: 768, enabled: true }
  },
  auto: { enabled: true, localRoute: 'local', timeoutMs: 5000, maxTokens: 128, maxInputChars: 600, extraKeywords: [] },
  askAround: { routes: ['local', 'astra', 'claude'], synthesizer: 'local', fallbackSynthesizer: 'astra', totalTimeoutMs: 45000, panelTimeoutMs: 20000, localPanelTimeoutMs: 12000, synthesisTimeoutMs: 10000, fallbackTimeoutMs: 12000, maxPanelTokens: 384, maxLocalPanelTokens: 96, maxSynthesisTokens: 320, maxQuestionChars: 12000, maxSynthesisChars: 24000 },
  storage: { retentionDays: 7, maxPanelsPerSession: 10, detailsPageChars: 10000 },
  estimates: { inputTokensPerAvoidedTurn: 15000, outputTokensPerAvoidedTurn: 150, inputUsdPerMillion: null, outputUsdPerMillion: null }
};
const reserved = new Set(['ask', 'around', 'details', 'savings', 'louter', 'auto', 'http', 'https', 'ftp', 'mailto']);
const obj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
export function localUrl(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.username || url.password || url.search || url.hash) {
    throw new Error('Local endpoints must use http://127.0.0.1, http://localhost or http://[::1], without credentials, query or fragment.');
  }
  // No DNS lookup, environment proxy, redirects, or remote base URL for local:.
  if (url.hostname === 'localhost') url.hostname = '127.0.0.1';
  return url;
}
export function configFrom(input = {}) {
  if (!obj(input)) throw new Error('Louter config must be an object.');
  const cfg = structuredClone(DEFAULTS);
  for (const key of ['auto', 'askAround', 'storage', 'estimates']) {
    if (input[key] !== undefined && !obj(input[key])) throw new Error(`${key} must be an object.`);
    Object.assign(cfg[key], input[key] || {});
  }
  if (input.agentIds !== undefined) cfg.agentIds = input.agentIds;
  if (input.routes !== undefined) cfg.routes = structuredClone(input.routes);
  if (!Array.isArray(cfg.agentIds) || !cfg.agentIds.length || cfg.agentIds.some(x => typeof x !== 'string' || !x.trim())) throw new Error('agentIds must be a nonempty string array.');
  if (!obj(cfg.routes) || !Object.keys(cfg.routes).length || Object.keys(cfg.routes).length > 12) throw new Error('Configure between 1 and 12 routes.');
  for (const [alias, r] of Object.entries(cfg.routes)) {
    if (!/^[a-z][a-z0-9_-]{0,31}$/.test(alias) || reserved.has(alias)) throw new Error(`Invalid or reserved route: ${alias}`);
    if (!obj(r) || !['local', 'openclaw'].includes(r.kind) || typeof r.model !== 'string' || !r.model.trim()) throw new Error(`Invalid route: ${alias}`);
    r.enabled ??= true;
    r.timeoutMs ??= 30000;
    r.maxTokens ??= r.kind === 'local' ? 384 : 768;
    if (r.kind === 'local') {
      localUrl(r.endpoint);
      r.protocol ??= 'openai';
      r.contextTokens ??= 4096;
      if (!['openai', 'ollama'].includes(r.protocol)) throw new Error(`Unknown protocol for ${alias}`);
      if (!Number.isSafeInteger(r.contextTokens) || r.contextTokens < 512 || r.contextTokens > 262144) throw new Error(`Invalid contextTokens for ${alias}`);
    } else {
      if (!/^[^\s/]+\/\S+$/.test(r.model) || r.model.includes('@')) throw new Error(`Use a full provider/model ref without an auth-profile suffix for ${alias}`);
      if (r.agentId !== undefined && (typeof r.agentId !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(r.agentId))) throw new Error(`Invalid agentId for ${alias}`);
    }
    if (!Number.isSafeInteger(r.timeoutMs) || r.timeoutMs < 10 || r.timeoutMs > 60000) throw new Error(`Invalid timeoutMs for ${alias}`);
    if (!Number.isSafeInteger(r.maxTokens) || r.maxTokens < 1 || r.maxTokens > 8192) throw new Error(`Invalid maxTokens for ${alias}`);
  }
  if (cfg.auto.enabled && cfg.routes[cfg.auto.localRoute]?.kind !== 'local') throw new Error('auto.localRoute must name a local route.');
  for (const [key, val] of Object.entries(cfg.auto)) {
    if (['timeoutMs', 'maxTokens', 'maxInputChars'].includes(key) && (!Number.isSafeInteger(val) || val < 1 || val > 60000)) throw new Error(`Invalid auto.${key}`);
  }
  if (!Array.isArray(cfg.auto.extraKeywords) || cfg.auto.extraKeywords.some(x => typeof x !== 'string')) throw new Error('auto.extraKeywords must be a string array.');
  if (!Array.isArray(cfg.askAround.routes) || !cfg.askAround.routes.length || cfg.askAround.routes.length > 8) throw new Error('askAround.routes must name between 1 and 8 routes.');
  for (const alias of [...cfg.askAround.routes, cfg.askAround.synthesizer, cfg.askAround.fallbackSynthesizer].filter(Boolean)) {
    if (!Object.hasOwn(cfg.routes, alias)) throw new Error(`Unknown Ask Around route: ${alias}`);
  }
  if (new Set(cfg.askAround.routes).size !== cfg.askAround.routes.length) throw new Error('Duplicate Ask Around aliases.');
  for (const [k, v] of Object.entries(cfg.askAround)) {
    if ((k.endsWith('Ms') || k.startsWith('max')) && (!Number.isSafeInteger(v) || v < 1 || v > 60000)) throw new Error(`Invalid askAround.${k}`);
  }
  for (const [k, v] of Object.entries(cfg.storage)) if (!Number.isSafeInteger(v) || v < 1 || v > 50000) throw new Error(`Invalid storage.${k}`);
  for (const [k, v] of Object.entries(cfg.estimates)) if (v !== null && (typeof v !== 'number' || !Number.isFinite(v) || v < 0)) throw new Error(`Invalid estimates.${k}`);
  for (const key of ['inputTokensPerAvoidedTurn','outputTokensPerAvoidedTurn']) if (typeof cfg.estimates[key] !== 'number' || !Number.isFinite(cfg.estimates[key])) throw new Error(`Invalid estimates.${key}`);
  return cfg;
}
