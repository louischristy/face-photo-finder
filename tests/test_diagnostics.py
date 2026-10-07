from pathlib import Path

from app.services.diagnostics import system_diagnostics


def test_diagnostics_returns_platform_and_checks(tmp_path: Path):
    result = system_diagnostics(tmp_path)
    assert result["platform"]
    assert result["python"]
    assert result["machine"]
    assert result["checks"]["data_directory_writable"] is True
    assert result["checks"]["detector_model"] is False
    assert result["checks"]["recognizer_model"] is False
    assert result["ready"] is False
