from agents.patch_agent import PatchAgent


def test_multi_patch_only_allows_explicit_target_files():
    agent = PatchAgent()
    raw = """[
      {"file": "sample_projects/project_1/app.py", "content": "def add(a, b):\\n    return 999\\n"},
      {"file": "sample_projects/project_1/test_unit_failure.py", "content": "fixed test\\n"}
    ]"""
    allowed = {"sample_projects/project_1/test_unit_failure.py"}
    patches = agent._parse_multi_patch(raw, allowed=allowed)

    assert len(patches) == 1
    assert patches[0].file_path == "sample_projects/project_1/test_unit_failure.py"
    assert patches[0].new_content == "fixed test\n"
