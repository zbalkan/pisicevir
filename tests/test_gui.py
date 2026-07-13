import sys
import pytest
from PyQt5.QtWidgets import QApplication
from pisicevir.gui import PisicevirGUI

@pytest.fixture
def app(qtbot):
    # This requires pytest-qt which might not be installed
    # We will do a simpler import check for now
    pass

def test_gui_imports():
    from pisicevir.gui import PisicevirGUI
    assert PisicevirGUI is not None

def test_gui_init():
    # Only test initialization if we can mock the display
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = PisicevirGUI()
    assert window.windowTitle() == "Pisicevir - PISI Recipe Generator"
    assert window.btn_generate.isEnabled() == False
