import json, zipfile
from hashlib import sha256
from pathlib import Path

def package_batch(job_id,scene_records,output_dir,package_name="images.zip"):
    root=Path(output_dir); root.mkdir(parents=True,exist_ok=True)
    manifest={"job_id":job_id,"zero_paid_services":True,"cloud_fallback":False,"scenes":[]}
    failed=[]
    for r in scene_records:
        rec=dict(r)
        p=rec.get("artifact_path")
        if p and Path(p).is_file(): rec["sha256"]=sha256(Path(p).read_bytes()).hexdigest()
        if rec.get("status")!="ACCEPTED": failed.append(rec)
        manifest["scenes"].append(rec)
    manifest_path=root/"manifest.json"; manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    failed_path=None
    if failed:
        failed_path=root/"failed_scenes.json"; failed_path.write_text(json.dumps(failed,indent=2,ensure_ascii=False),encoding="utf-8")
    zip_path=root/package_name
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(manifest_path,"manifest.json")
        if failed_path: z.write(failed_path,"failed_scenes.json")
        for rec in manifest["scenes"]:
            p=rec.get("artifact_path")
            if rec.get("status")=="ACCEPTED" and p and Path(p).is_file(): z.write(p,Path(p).name)
    return {"zip_path":str(zip_path),"manifest_path":str(manifest_path),"accepted":sum(x.get("status")=="ACCEPTED" for x in manifest["scenes"]),"failed":len(failed),"zero_paid_services":True}
