"""Source-agent factory shared by local evaluation.

The base policy owns farming/routing decisions.  The value overlay adjusts only public-market
sale timing/size/order so production volume and realized price are optimized together.
"""
from policy import make_v3, validate_params
from value_overlay import coordinate_action


def make_agent(params=None):
    p = validate_params(params)
    base = make_v3(p)

    def agent(obs, configuration=None):
        cfg = configuration or {}
        action = base(obs, cfg)
        return coordinate_action(obs, cfg, action, p)

    return agent
