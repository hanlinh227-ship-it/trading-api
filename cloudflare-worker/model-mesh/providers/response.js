export async function readJsonBounded(response,maxBytes=65536){
  const declared=Number(response.headers.get('content-length')||0);
  if(declared>maxBytes)throw Object.assign(new Error('response_too_large'),{code:'PARSE_FAILED'});
  if(!response.body){try{return JSON.parse(await response.text());}catch{throw Object.assign(new Error('invalid_json'),{code:'PARSE_FAILED'});}}
  const reader=response.body.getReader(),chunks=[];let size=0;
  try{
    while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>maxBytes){await reader.cancel();throw Object.assign(new Error('response_too_large'),{code:'PARSE_FAILED'});}chunks.push(value);}
  }finally{reader.releaseLock();}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  try{return JSON.parse(new TextDecoder().decode(bytes));}catch{throw Object.assign(new Error('invalid_json'),{code:'PARSE_FAILED'});}
}
