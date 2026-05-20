from utils.secrets import (
    mask_secrets,
    register_secrets,
    safe_patch_summary,
    truncate_for_log,
)


def test_mask_github_token_pattern():
    text = "Authorization: ghp_abcdefghijklmnopqrstuvwxyz1234567890"
    masked = mask_secrets(text)
    assert "ghp_" not in masked
    assert "***REDACTED***" in masked


def test_mask_registered_secret():
    register_secrets(["my-super-secret-key-12345"])
    assert "***REDACTED***" in mask_secrets("token=my-super-secret-key-12345")


def test_safe_patch_summary_omits_body():
    patch = "def foo():\n    return 42\n" * 50
    summary = safe_patch_summary(patch)
    assert "2100" in summary or "chars" in summary
    assert "return 42" not in summary


def test_truncate_for_log():
    long_text = "x" * 1000 + " ghp_abc1234567890123456789012345678901234"
    result = truncate_for_log(long_text, limit=100)
    assert len(result) < 200
    assert "ghp_" not in result
