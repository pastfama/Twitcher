MAIN_WINDOW_STYLESHEET = """
QMainWindow,
QWidget {
    background-color: #08090f;
    color: #f2f2f5;
    font-family: "Segoe UI";
}
QGroupBox {
    background-color: #10121c;
    border: 1px solid #292d42;
    border-radius: 8px;
    margin-top: 8px;
    padding: 6px;
    font-size: 12px;
    font-weight: bold;
    color: #aeb8ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    background-color: #08090f;
}
QLabel {
    color: #eeeeF5;
}
QPushButton {
    background-color: #191c2c;
    color: #ffffff;
    border: 1px solid #353a58;
    border-radius: 8px;
    padding: 10px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #272c48;
    border: 1px solid #5964a0;
}
QPushButton:pressed {
    background-color: #10121e;
}
QListWidget {
    background-color: #0c0e16;
    border: 1px solid #292d42;
    border-radius: 8px;
    padding: 5px;
}
QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #1e2232;
}
QListWidget::item:hover {
    background-color: #181c2d;
}
QListWidget::item:selected {
    background-color: #30385e;
    border-left: 3px solid #7f8cff;
}
QTextEdit {
    background-color: #0b0d14;
    border: 1px solid #292d42;
    border-radius: 8px;
    color: #eeeeF5;
    padding: 8px;
}
QFrame#CurrentCard {
    background-color: #141827;
    border: 1px solid #3c456b;
    border-radius: 8px;
}
QFrame#NextCard {
    background-color: #101c1b;
    border: 1px solid #315f58;
    border-radius: 8px;
}
"""
