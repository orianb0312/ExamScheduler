from PyQt6.QtWidgets import QFrame

from src.ui.main_window import MainWindow


def test_dashboard_reflows_and_controls_resize_with_window(tmp_path, qtbot):
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    window.show()

    window.resize(1400, 900)
    qtbot.wait(20)
    panel = window.input_panel
    assert panel._compact_dashboard_layout is False
    wide_button_width = panel.run_button.width()
    wide_logo_width = panel.findChild(QFrame, "homeImagePanel").width()
    wide_logo_height = panel.findChild(QFrame, "homeImagePanel").height()
    wide_chat_height = panel._copilot_card.height()

    window.resize(900, 700)
    qtbot.wait(20)

    assert panel._compact_dashboard_layout is True
    assert panel.run_button.isVisible()
    assert panel.ai_copilot.isVisible()
    assert panel.findChild(QFrame, "homeImagePanel").isVisible()
    assert panel.run_button.width() != wide_button_width
    assert panel.findChild(QFrame, "homeImagePanel").width() != wide_logo_width
    assert panel.findChild(QFrame, "homeImagePanel").height() != wide_logo_height
    assert panel._copilot_card.height() != wide_chat_height


def test_wide_short_window_shrinks_logo_and_chatbot_above_footer(
    tmp_path,
    qtbot,
):
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    window.show()
    window.resize(1600, 760)

    panel = window.input_panel
    viewport = panel._program_page.viewport()
    logo = panel._home_image_panel
    chatbot = panel._copilot_card
    qtbot.waitUntil(
        lambda: (
            logo.mapTo(viewport, logo.rect().bottomLeft()).y()
            < viewport.height()
            and chatbot.mapTo(
                viewport,
                chatbot.rect().bottomLeft(),
            ).y()
            < viewport.height()
        ),
        timeout=1000,
    )

    assert panel._compact_dashboard_layout is False
    assert logo.height() <= 240
    assert chatbot.height() == logo.height()
    assert logo.mapTo(viewport, logo.rect().bottomLeft()).y() < viewport.height()
    assert chatbot.mapTo(viewport, chatbot.rect().bottomLeft()).y() < viewport.height()
