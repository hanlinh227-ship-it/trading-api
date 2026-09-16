import {timingSafeToken} from './model-mesh/auth.js';
import {handleImageRenderV3Authorized} from './image-render/v3-handler.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const enabled=env=>String(env?.IMAGE_RENDER_EXECUTION_ENABLED||'0')==='1';
const configuredToken=env=>String(env?.IMAGE_RENDER_EXECUTION_TOKEN||env?.MODEL_MESH_EXECUTION_TOKEN||'');
const suppliedToken=request=>String(request.headers.get('x-image-render-token')||request.headers.get('x-model-mesh-token')||'');

export async function handleImageRenderV3(request,env={}){
  const url=new URL(request.url);
  if(!url.pathname.startsWith('/brain/image/v3/'))return null;
  if(!enabled(env))return json({ok:false,error:'image_render_execution_disabled'},503);
  const expected=configuredToken(env);
  if(!expected||!timingSafeToken(expected,suppliedToken(request)))return json({ok:false,error:'unauthorized'},401);
  return await handleImageRenderV3Authorized(request,env);
}
