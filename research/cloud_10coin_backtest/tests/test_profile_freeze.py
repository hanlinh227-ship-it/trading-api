from optimize.selection import lock_profile


def test_profile_hash_changes_if_parameter_changes():
    a = lock_profile({"family": "trend_ote", "r": 0.85, "side": "LONG"})
    b = lock_profile({"family": "trend_ote", "r": 0.90, "side": "LONG"})
    assert a.profile_hash != b.profile_hash


def test_locked_profile_parameters_are_copied():
    params = {"family": "compression", "r": 0.85}
    locked = lock_profile(params)
    params["r"] = 0.95
    assert locked.params["r"] == 0.85
