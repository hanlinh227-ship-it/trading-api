from money_ecosystem.worker.image_qa import validate_image

def test_missing_image_is_rejected(tmp_path):
    r=validate_image(tmp_path/"missing.png",1024,576)
    assert not r.accepted and r.identity_status=="UNVERIFIED"

def test_no_identity_checker_never_claims_verified(tmp_path):
    p=tmp_path/"bad.png"; p.write_bytes(b"not-an-image")
    r=validate_image(p,1024,576)
    assert r.identity_status=="UNVERIFIED"
