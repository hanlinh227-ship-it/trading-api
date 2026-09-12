import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';
import {createSkillGatewayHandler} from './skill-gateway-handler.js';

export const handleSkillGateway=createSkillGatewayHandler({snapshot:SKILL_GATEWAY_SNAPSHOT,freshGitContext:true,lastKnownGood:true});
export {SKILL_GATEWAY_SNAPSHOT};
