const secretNames=['CLOUDFLARE_API_TOKEN','CLOUDFLARE_ACCOUNT_ID','TRADING_KV_NAMESPACE_ID','AI_BRIDGE_SERVICE_ID','V11_AI_BRIDGE_SERVICE_ID','MODEL_MESH_EXECUTION_TOKEN','TINY_FISH_API','GROQ_API_KEY','GEMINI_API_KEY','CLOUDFLARE_AI_API_TOKEN','OPENROUTER_API_KEY','MISTRAL_API_KEY','COHERE_API_KEY','HF_TOKEN','NVIDIA_API_KEY','CEREBRAS_API_KEY','SAMBANOVA_API_KEY','DASHSCOPE_API_KEY','OPENCODE_ZEN_API_KEY'];
let text='';for await(const chunk of process.stdin){text+=chunk;if(text.length>1024*1024)throw new Error('deploy_output_too_large');}
for(const name of secretNames){const value=String(process.env[name]||'');if(value.length>=4)text=text.split(value).join('[REDACTED]');}
text=text.replace(/(?:sk-|AIza|hf_)[A-Za-z0-9._-]{8,}/g,'[REDACTED]').replace(/Bearer\s+\S+/gi,'Bearer [REDACTED]');
process.stdout.write(text);
