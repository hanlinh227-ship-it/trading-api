from pathlib import Path

from money_ecosystem.render_gateway.asset_store import canonical_logical_path, sha256_file


def test_sha256_file_is_stable(tmp_path: Path):
    path = tmp_path / "asset.bin"
    path.write_bytes(b"curious-beyond")
    assert sha256_file(path) == "9466ba793cab5a97b9992f8a560908ca94ba37036f1ad26fd81e077840ef40f7"


def test_canonical_job_layout_is_portable():
    assert canonical_logical_path("max-bus", "job-1", "input") == (
        "CuriousBeyond_RenderGateway/projects/max-bus/jobs/job-1/input"
    )
