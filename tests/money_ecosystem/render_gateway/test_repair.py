from money_ecosystem.render_gateway.qa import QAReport, QAStatus
from money_ecosystem.render_gateway.repair import RepairAction, next_repair


def _report(status):
    return QAReport(status=status, sha256="a" * 64, assertions=(), reason="test")


def test_verified_scene_needs_no_repair():
    assert next_repair(_report(QAStatus.VERIFIED), []).action is RepairAction.NONE


def test_retry_escalates_in_defined_order():
    assert next_repair(_report(QAStatus.RETRY), []).action is RepairAction.LOCAL_INPAINT
    assert next_repair(_report(QAStatus.RETRY), ["LOCAL_INPAINT"]).action is RepairAction.PROVIDER_EDIT
    assert next_repair(_report(QAStatus.RETRY), ["LOCAL_INPAINT", "PROVIDER_EDIT"]).action is RepairAction.REGION_RERENDER
    assert next_repair(_report(QAStatus.RETRY), ["a", "b", "c"]).action is RepairAction.FULL_RERENDER
    assert next_repair(_report(QAStatus.RETRY), ["a", "b", "c", "d"]).action is RepairAction.STRONGER_PROVIDER


def test_human_review_is_preserved():
    assert next_repair(_report(QAStatus.HUMAN_REVIEW), []).action is RepairAction.HUMAN_REVIEW
