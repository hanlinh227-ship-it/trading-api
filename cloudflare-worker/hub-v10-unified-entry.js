import unifiedUx from "./hub-v10-unified-v2.js";
import {scheduledV10} from "./signal-v10-scheduled-v2.js";

export default {
  async fetch(req,env,ctx){return unifiedUx.fetch(req,env,ctx);},
  async scheduled(event,env,ctx){return scheduledV10(event,env,ctx);}
};
