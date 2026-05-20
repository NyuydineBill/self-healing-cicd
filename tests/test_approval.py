from unittest.mock import patch

from utils.approval import format_patch_diff, request_patch_approval


def test_format_patch_diff_shows_changes():
    diff = format_patch_diff(
        "test.py",
        "line1\nline2\n",
        "line1\nline2_fixed\n",
    )
    assert "test.py" in diff
    assert "+" in diff or "-" in diff


@patch("utils.approval.get_settings")
def test_auto_approve(mock_settings):
    settings = mock_settings.return_value
    settings.auto_approve_patches = True
    settings.require_approval = True

    assert request_patch_approval("f.py", "a", "b") is True


@patch("utils.approval.get_settings")
@patch("utils.approval.sys.stdin")
def test_non_interactive_denies(mock_stdin, mock_settings):
    settings = mock_settings.return_value
    settings.auto_approve_patches = False
    settings.require_approval = True
    mock_stdin.isatty.return_value = False

    assert request_patch_approval("f.py", "a", "b") is False
