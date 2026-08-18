const fs = require('fs');
const path = 'scripts/apply_v7780_unified_hub.js';
let s = fs.readFileSync(path, 'utf8');
const fixes = [
  ["deepReplacement + '\\nfunction broadRank('", "deepReplacement"],
  ["broadReplacement + '\\nfunction emptyGroup('", "broadReplacement"],
  ["runReplacement + '\\nasync function telegram('", "runReplacement"],
  ["uiReplacement + '\\nasync function lifecycle('", "uiReplacement"],
  ["lifecycleReplacement + '\\nasync function setupWebhook('", "lifecycleReplacement"],
  ["telegramReplacement + '\\nexport default {'", "telegramReplacement"],
];
for (const [from,to] of fixes) {
  if (!s.includes(from)) throw new Error(`Missing V77.8 migration fix target: ${from}`);
  s = s.replace(from,to);
}
// String.raw migration blocks should emit normal JS newline escapes, not literal "\\n" text.
s = s.replaceAll('\\\\n','\\n');
fs.writeFileSync(path,s,'utf8');
console.log('Fixed V77.8 migration boundary/newline handling.');
