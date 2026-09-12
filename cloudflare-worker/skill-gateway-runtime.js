import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';
import {createSkillGatewayHandler} from './skill-gateway-handler.js';

export const ACTIVE_SKILL_GATEWAY_SNAPSHOT=SKILL_GATEWAY_SNAPSHOT;
export const handleSkillGateway=createSkillGatewayHandler({snapshot:SKILL_GATEWAY_SNAPSHOT});
