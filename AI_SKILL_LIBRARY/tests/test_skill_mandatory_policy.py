from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


class SkillMandatoryPolicyTests(unittest.TestCase):
    def test_every_profile_requires_exactly_one_primary_skill(self):
        router = load("AI_SKILL_LIBRARY/v4/stable/router.yaml")
        runtime = load("AI_SKILL_LIBRARY/v4/stable/runtime.yaml")
        self.assertIs(router["policy"]["primary_skill_required"], True)
        self.assertEqual(router["policy"]["fallback_primary_skill"], "core_reasoning")
        self.assertIs(router["policy"]["skill_execution_capsule_required"], True)
        for name in ("FAST", "STANDARD", "DEEP"):
            self.assertEqual(runtime["profiles"][name]["primary_skill_count"], 1)
            self.assertIs(runtime["profiles"][name]["skill_capsule_required"], True)
        self.assertEqual(runtime["profiles"]["FAST"]["max_supporting_skills"], 0)

    def test_deep_escalation_covers_security_risk_vocabulary(self):
        """security.yaml risk classes (financial, destructive, credential) and
        runtime.yaml DEEP triggers must be represented in the canonical compiled
        escalation list, in English and Vietnamese (accented and unaccented).
        4.11.0 routed 'withdraw', 'rút tiền', 'seed phrase' FAST without authority."""
        aliases = load("AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml")
        deep = {" ".join(str(t).lower().split()) for t in aliases["profile_escalation"]["DEEP"]}
        required = {
            "financial": ["withdraw", "rút tiền", "rut tien", "chuyển tiền", "chuyen tien", "transfer funds", "send money", "payment", "thanh toán", "thanh toan", "wallet", "sign transaction", "broadcast transaction", "swap token", "bridge asset", "financial action"],
            "credential_sensitive": ["private key", "seed phrase", "cụm từ khôi phục", "passphrase", "api key", "secret", "credential", "mật khẩu", "mat khau"],
            "destructive": ["xóa", "xoa", "delete", "drop table", "rm -rf", "destroy", "destructive", "xóa dữ liệu"],
            "permission_change": ["permission", "phân quyền", "cấp quyền", "revoke scope"],
            "deployment_or_runtime": ["deploy", "triển khai", "production", "runtime"],
            "live_or_trading": ["live", "trading", "giao dịch", "market entry"],
        }
        missing = {cls: [t for t in terms if t not in deep] for cls, terms in required.items()}
        missing = {cls: terms for cls, terms in missing.items() if terms}
        self.assertEqual(missing, {}, f"routing_aliases DEEP escalation missing risk vocabulary: {missing}")


if __name__ == "__main__":
    unittest.main()
