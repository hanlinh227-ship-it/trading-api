// Minimal PNG writer.
//
// The inpainting runtime needs a mask image, and a caller who asks for a whole-image edit
// has no mask to give. Rather than refuse the edit, we synthesize one -- but a mask is an
// encoded image, so we have to be able to write one. This does that with no dependency and
// no compression library: deflate "stored" blocks are literal bytes wrapped in a zlib
// envelope, which is all a solid-colour image needs.
//
// It is also what generates the runtime probe's images, so the probe can never again ship
// a truncated PNG that a model reports as a broken data stream.

const PNG_SIGNATURE=[0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a];

const CRC_TABLE=(()=>{
  const table=new Uint32Array(256);
  for(let n=0;n<256;n+=1){
    let c=n;
    for(let k=0;k<8;k+=1)c=c&1?0xedb88320^(c>>>1):c>>>1;
    table[n]=c>>>0;
  }
  return table;
})();

function crc32(bytes){
  let crc=0xffffffff;
  for(const byte of bytes)crc=CRC_TABLE[(crc^byte)&0xff]^(crc>>>8);
  return (crc^0xffffffff)>>>0;
}

function adler32(bytes){
  let a=1,b=0;
  for(const byte of bytes){a=(a+byte)%65521;b=(b+a)%65521;}
  return ((b<<16)|a)>>>0;
}

const uint32=value=>[(value>>>24)&0xff,(value>>>16)&0xff,(value>>>8)&0xff,value&0xff];

function chunk(type,data){
  const typed=[...type].map(char=>char.charCodeAt(0)).concat([...data]);
  return [...uint32(data.length),...typed,...uint32(crc32(typed))];
}

// zlib stream of stored (uncompressed) deflate blocks.
function storedZlib(bytes){
  const out=[0x78,0x01];
  const MAX=65535;
  for(let offset=0;offset<bytes.length||offset===0;offset+=MAX){
    const slice=bytes.slice(offset,offset+MAX);
    const last=offset+MAX>=bytes.length?1:0;
    out.push(last,slice.length&0xff,(slice.length>>>8)&0xff,(~slice.length)&0xff,((~slice.length)>>>8)&0xff,...slice);
    if(last)break;
  }
  out.push(...uint32(adler32(bytes)));
  return out;
}

// A single-shade 8-bit greyscale PNG. That is what a mask is: black preserves, white is
// open to edit.
export function solidGreyscalePng(width,height,shade){
  const w=Math.max(1,Math.trunc(Number(width)||1));
  const h=Math.max(1,Math.trunc(Number(height)||1));
  const value=Math.min(255,Math.max(0,Math.trunc(Number(shade)||0)));
  const raw=[];
  for(let row=0;row<h;row+=1){
    raw.push(0); // filter: none
    for(let column=0;column<w;column+=1)raw.push(value);
  }
  const ihdr=[...uint32(w),...uint32(h),8,0,0,0,0];
  return Uint8Array.from([
    ...PNG_SIGNATURE,
    ...chunk('IHDR',ihdr),
    ...chunk('IDAT',storedZlib(raw)),
    ...chunk('IEND',[]),
  ]);
}

// Everything is editable. Handing this to an inpainting model alongside a source image is
// what makes it behave as image-to-image.
export const fullyEditableMask=(width,height)=>solidGreyscalePng(width,height,255);
// Nothing is editable: used by the probe, which only needs the runtime to accept the call.
export const fullyPreservedMask=(width,height)=>solidGreyscalePng(width,height,0);
