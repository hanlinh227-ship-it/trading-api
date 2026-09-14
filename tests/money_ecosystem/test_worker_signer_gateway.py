from pathlib import Path


def test_sign_workflow_allows_render_gateway():
    workflow = Path('.github/workflows/sign-curious-worker-job.yml').read_text(encoding='utf-8')
    assert '"RENDER_GATEWAY"' in workflow
