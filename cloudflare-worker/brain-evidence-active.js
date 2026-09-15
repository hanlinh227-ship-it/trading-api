import {routeSkillRequest} from './skill-gateway.js';
import {ACTIVE_SKILL_GATEWAY_SNAPSHOT} from './skill-gateway-runtime.js';
import {createBrainEvidenceHandler} from './brain-evidence-handler.js';

export const handleBrainEvidence=createBrainEvidenceHandler({routeSkill:({text})=>routeSkillRequest({text},ACTIVE_SKILL_GATEWAY_SNAPSHOT)});
