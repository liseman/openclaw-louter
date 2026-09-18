import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { createRouter } from './src/louter.js';
import { configFrom } from './src/config.js';
import manifest from './openclaw.plugin.json' with { type: 'json' };
export default definePluginEntry({
  id: 'louter',
  name: 'Louter',
  description: 'Lite Router: local fast path, explicit model replies, Ask Around and usage estimates.',
  configSchema: {
    jsonSchema: manifest.configSchema,
    safeParse(value) {
      try { return { success: true, data: configFrom(value ?? {}) }; }
      catch (error) { return { success: false, error: { issues: [{ path: [], message: String(error.message) }] } }; }
    }
  },
  register(api) {
    // Registration is synchronous and side-effect-free. No config writes or downloads.
    const router = createRouter(api);
    api.on('before_agent_reply', (event, ctx) => router.handle(event, ctx), {
      eligibleTriggers: ['user'], timeoutMs: 120000, registrationId: 'louter.reply'
    });
    api.on('gateway_start', () => router.start(), { registrationId: 'louter.start' });
    api.on('gateway_stop', () => router.close(), { registrationId: 'louter.stop' });
  }
});
