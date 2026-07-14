from __future__ import annotations

from pisicevir.gui import PisicevirGUI


def test_gui_initial_state(qtbot) -> None:
    window = PisicevirGUI()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Pisicevir - PISI Recipe Generator"
    assert window.btn_generate.isEnabled() is False
    assert window.plan_text.isReadOnly() is False


def test_gui_error_is_visible(qtbot) -> None:
    window = PisicevirGUI()
    qtbot.addWidget(window)
    window.on_error("example failure")
    assert "example failure" in window.linter_text.toPlainText()
    assert window.tabs.currentIndex() == 1


def test_gui_worker_reports_validation_error_without_traceback(qtbot, tmp_path) -> None:
    from pisicevir.analysis.planning import create_initial_plan
    from pisicevir.gui import Worker
    from pisicevir.source_adapters.deb import DebAdapter
    from tests.test_deb_adapter import create_dummy_deb

    package = tmp_path / "test.deb"
    create_dummy_deb(str(package))
    inspection = DebAdapter(str(package)).inspect()
    classification = {
        "conversion_class": "A",
        "policy_family": "deb-data",
        "confidence": "high",
        "reasons": [],
        "warnings": [],
    }
    plan = create_initial_plan(inspection, classification)
    worker = Worker(
        "generate",
        source_path=str(package),
        inspection=inspection,
        plan=plan,
        output=str(tmp_path / "recipe"),
    )
    with qtbot.waitSignal(worker.error) as blocker:
        worker.run()

    message = blocker.args[0]
    assert "Traceback" not in message
    assert "approved" in message
    assert "homepage" in message
    assert "licenses" in message
    assert "packager.name" in message
    assert "packager.email" in message
