import {ACTIVE_SKILL_GATEWAY_SNAPSHOT} from './skill-gateway-runtime.js';
import {routeSkillRequest} from './skill-gateway.js';
import {createUniversalEntryHandler} from './universal-entry-handler.js';

export const handleUniversalEntry=createUniversalEntryHandler({
  snapshot:ACTIVE_SKILL_GATEWAY_SNAPSHOT,
  routeSkill:({text})=>routeSkillRequest({text},ACTIVE_SKILL_GATEWAY_SNAPSHOT),
});
