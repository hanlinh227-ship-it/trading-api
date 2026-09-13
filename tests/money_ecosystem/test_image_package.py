import json, zipfile
from money_ecosystem.worker.image_package import package_batch

def test_package_contains_manifest_and_zero_paid_assertion(tmp_path):
    img=tmp_path/"scene_01.png"; img.write_bytes(b"x")
    out=package_batch("job1",[{"scene_id":1,"status":"ACCEPTED","artifact_path":str(img)}],tmp_path,"batch.zip")
    assert out["zero_paid_services"] is True
    with zipfile.ZipFile(out["zip_path"]) as z:
        assert "manifest.json" in z.namelist() and "scene_01.png" in z.namelist()
        m=json.loads(z.read("manifest.json")); assert m["cloud_fallback"] is False
