from stackhub.accounts import account_status


def test_account_status_never_returns_secret_values():
    rows = account_status(
        {
            "TASKBOUNTY_API_KEY": "fake_taskbounty_value",
            "GUMROAD_ACCESS_TOKEN": "fake_gumroad_value",
        }
    )
    text = repr(rows)
    assert "fake_taskbounty_value" not in text
    assert "fake_gumroad_value" not in text
    assert all(row["ready_for_mode"] for row in rows)


def test_account_status_reports_missing_env_names_only():
    rows = {row["name"]: row for row in account_status({})}
    assert rows["taskbounty"]["missing_secrets"] == ("TASKBOUNTY_API_KEY",)
    assert rows["gumroad"]["missing_secrets"] == ("GUMROAD_ACCESS_TOKEN",)
    assert rows["paypal"]["missing_secrets"] == ()
