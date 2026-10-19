import pytest

from scripts.audit_dependencies import audit


def test_advisory_failures_are_not_reported_as_clean():
    with pytest.raises(ValueError):
        audit([("example", "1.0")], lambda payload: {"results": []})
    assert audit([("example", "1.0")], lambda payload: {"results": [{}]}) == []
    result = audit(
        [("example", "1.0")], lambda payload: {"results": [{"vulns": [{"id": "TEST-ADVISORY"}]}]}
    )
    assert result == [{"package": "example", "version": "1.0", "advisories": ["TEST-ADVISORY"]}]
