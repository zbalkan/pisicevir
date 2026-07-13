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
