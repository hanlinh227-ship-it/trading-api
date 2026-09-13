from pathlib import Path
import pytest
from money_ecosystem.worker.image_render_contract import ImageRenderJob, ContractError


def valid_payload():
    return {
        "project_id": "max-bus",
        "width": 1024,
        "height": 576,
        "max_attempts": 2,
        "workflow_profile": "sd15_reference_lowvram",
        "references": [
            {"id": "max", "path": "assets/max.png", "character": "Max"},
            {"id": "dad", "path": "assets/dad.png", "character": "Dad Max"},
        ],
        "scenes": [{"id": 1, "prompt": "Max waves beside the bus", "reference_ids": ["max", "dad"]}],
    }


def test_accepts_valid_job(tmp_path):
    job = ImageRenderJob.from_payload(valid_payload(), tmp_path)
    assert job.width == 1024 and job.height == 576
    assert job.scenes[0].reference_ids == ("max", "dad")

@pytest.mark.parametrize("field", ["project_id", "width", "height", "references", "scenes"])
def test_required_fields(field, tmp_path):
    p = valid_payload(); p.pop(field)
    with pytest.raises(ContractError): ImageRenderJob.from_payload(p, tmp_path)

def test_duplicate_reference_rejected(tmp_path):
    p = valid_payload(); p["references"].append(dict(p["references"][0]))
    with pytest.raises(ContractError): ImageRenderJob.from_payload(p, tmp_path)

def test_undeclared_reference_rejected(tmp_path):
    p = valid_payload(); p["scenes"][0]["reference_ids"] = ["ghost"]
    with pytest.raises(ContractError): ImageRenderJob.from_payload(p, tmp_path)

def test_path_traversal_rejected(tmp_path):
    p = valid_payload(); p["references"][0]["path"] = "../secret.png"
    with pytest.raises(ContractError): ImageRenderJob.from_payload(p, tmp_path)

@pytest.mark.parametrize("w,h", [(0,576),(1024,0),(1025,576),(1024,577)])
def test_dimensions_must_be_safe_and_multiple_of_8(w,h,tmp_path):
    p=valid_payload(); p["width"]=w; p["height"]=h
    with pytest.raises(ContractError): ImageRenderJob.from_payload(p,tmp_path)

@pytest.mark.parametrize("attempts", [0,5])
def test_attempt_bounds(attempts,tmp_path):
    p=valid_payload(); p["max_attempts"]=attempts
    with pytest.raises(ContractError): ImageRenderJob.from_payload(p,tmp_path)
