from stackhub.source_capabilities import SourceCapabilities


def test_adapter_contract_exposes_capabilities():
    class Adapter:
        source_name = "x"
        capabilities = SourceCapabilities(agent_allowed=True, auto_discovery=True)

        async def discover(self, limit=50):
            return []

    adapter = Adapter()
    assert adapter.source_name == "x"
    assert adapter.capabilities.auto_discovery is True
