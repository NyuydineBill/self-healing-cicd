from sample_projects.project_8.app import first


def test_first_returns_head():
    assert first([10, 20, 30]) == 10
