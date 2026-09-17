// The runtime probe once shipped two truncated PNGs -- no IEND, an IDAT shorter than its
// own length field -- and the inpainting model rejected them as a broken data stream. That
// was read as "no runtime". A probe image that is not a valid image proves nothing, so the
// bytes are checked structurally here rather than trusted.
import assert from 'node:assert/strict';
import zlib from 'node:zlib';
import {fullyEditableMask,fullyPreservedMask,solidGreyscalePng} from './image-render/png.js';

const SIGNATURE='89504e470d0a1a0a';

function parse(bytes){
  const buffer=Buffer.from(bytes);
  assert.equal(buffer.subarray(0,8).toString('hex'),SIGNATURE,'PNG signature');
  const chunks=[];
  let offset=8;
  while(offset<buffer.length){
    const length=buffer.readUInt32BE(offset);
    const type=buffer.subarray(offset+4,offset+8).toString('ascii');
    const data=buffer.subarray(offset+8,offset+8+length);
    const declared=buffer.readUInt32BE(offset+8+length);
    // A chunk whose CRC does not match is exactly what a decoder rejects.
    assert.equal(declared,zlib.crc32(Buffer.concat([Buffer.from(type,'ascii'),data])),`${type} crc`);
    chunks.push({type,data});
    offset+=12+length;
  }
  assert.equal(offset,buffer.length,'chunks must end exactly at the end of the file');
  return chunks;
}

for(const [width,height,shade] of [[256,256,128],[512,512,255],[1,1,0],[64,96,17]]){
  const chunks=parse(solidGreyscalePng(width,height,shade));
  assert.deepEqual(chunks.map(chunk=>chunk.type),['IHDR','IDAT','IEND'],`${width}x${height} chunk order`);
  const ihdr=chunks[0].data;
  assert.equal(ihdr.readUInt32BE(0),width);
  assert.equal(ihdr.readUInt32BE(4),height);
  assert.equal(ihdr[8],8,'bit depth');
  assert.equal(ihdr[9],0,'greyscale colour type');
  // The pixels must survive the round trip, or the model receives noise.
  const raw=zlib.inflateSync(chunks[1].data);
  assert.equal(raw.length,height*(1+width),'raw scanline length');
  for(let row=0;row<height;row+=1){
    assert.equal(raw[row*(1+width)],0,'filter byte');
    for(let column=0;column<width;column+=1)assert.equal(raw[row*(1+width)+1+column],shade);
  }
}

// A mask says what may change. Getting these two backwards would either freeze an edit or
// redraw a frame the caller asked to keep.
assert.equal(zlib.inflateSync(Buffer.from(parse(fullyEditableMask(8,8))[1].data))[1],255);
assert.equal(zlib.inflateSync(Buffer.from(parse(fullyPreservedMask(8,8))[1].data))[1],0);

// The probe's own images have to pass the same bar.
const probe=await import('./image-render/runtime-probe.js');
const seen=[];
await probe.probeImageRuntimes({AI:{async run(model,input){seen.push({model,input});return {image:''};}}});
for(const call of seen){
  for(const key of ['image','mask']){
    if(!call.input?.[key])continue;
    assert.ok(Array.isArray(call.input[key]),`${call.model} ${key} must be a byte array`);
    parse(call.input[key]);
  }
}
assert.ok(seen.some(call=>call.input?.image),'the probe must exercise an image-conditioned model');
assert.ok(seen.some(call=>call.input?.mask),'the probe must exercise the inpainting mask path');

console.log('image render v4 png asset contracts: PASS');
