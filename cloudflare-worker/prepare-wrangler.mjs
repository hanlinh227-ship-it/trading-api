import fs from 'node:fs';

const kvId = String(process.env.TRADING_KV_NAMESPACE_ID || '').trim();
if (!/^[a-f0-9]{32}$/i.test(kvId)) {
  throw new Error('TRADING_KV_NAMESPACE_ID is missing or invalid. Expected the existing 32-character KV namespace ID.');
}

const config = {
  $schema: './node_modules/wrangler/config-schema.json',
  name: 'trading-v77-scanner',
  main: 'index.js',
  compatibility_date: '2026-08-18',
  keep_vars: true,
  kv_namespaces: [
    {
      binding: 'TRADING_STATE',
      id: kvId,
    },
  ],
  triggers: {
    crons: ['* * * * *'],
  },
};

fs.writeFileSync('wrangler.jsonc', `${JSON.stringify(config, null, 2)}\n`, 'utf8');
console.log('Prepared wrangler.jsonc for existing TRADING_STATE namespace.');
