import {ACTIVE_SKILL_GATEWAY_SNAPSHOT} from './skill-gateway-runtime.js';
import {createProjectContinuityHandler} from './project-continuity-handler.js';

export const handleProjectContinuity=createProjectContinuityHandler({snapshot:ACTIVE_SKILL_GATEWAY_SNAPSHOT});
