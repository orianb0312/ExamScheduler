from src.ui.main_window import MainWindow


def test_main_window_starts_maximized_and_remains_resizable(tmp_path, qtbot):
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window.show_resizable_maximized()
    qtbot.waitUntil(window.isMaximized, timeout=1000)
    window.showNormal()
    qtbot.waitUntil(lambda: not window.isMaximized(), timeout=1000)
    window.resize(980, 700)

    assert window.size().width() == 980
    assert window.size().height() == 700
    assert window.minimumSize().width() == 820
    assert window.maximumSize().width() > 980
