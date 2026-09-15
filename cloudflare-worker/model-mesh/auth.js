async function digest(value){return new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(String(value))));}
export async function timingSafeToken(expected,supplied){
  if(!expected||!supplied)return false;
  const [left,right]=await Promise.all([digest(expected),digest(supplied)]);let diff=0;
  for(let index=0;index<left.length;index+=1)diff|=left[index]^right[index];
  return diff===0;
}
