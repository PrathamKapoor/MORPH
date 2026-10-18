"""Accessible styles and color palettes for MORPH 2.0."""

# High-contrast accessible palette meeting WCAG AAA ratio (>7:1)
THEME_DARK = """
QMainWindow, QWidget {
    background-color: #121418;
    color: #F0F2F5;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
}

QTabBar::tab {
    background-color: #1E222A;
    color: #B0B8C4;
    padding: 12px 24px;
    font-size: 15px;
    font-weight: bold;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #2D3340;
    color: #38BDF8;
    border-bottom: 3px solid #38BDF8;
}

QPushButton {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 2px solid #334155;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #64748B;
}

QPushButton:focus {
    border: 3px solid #38BDF8;
    outline: none;
}

QPushButton:disabled {
    background-color: #0F172A;
    color: #475569;
    border-color: #1E293B;
}

QPushButton#activate_btn_paused {
    background-color: #065F46;
    color: #ECFDF5;
    border: 2px solid #10B981;
    font-size: 18px;
    padding: 16px 32px;
}

QPushButton#activate_btn_paused:hover {
    background-color: #047857;
}

QPushButton#activate_btn_active {
    background-color: #991B1B;
    color: #FEF2F2;
    border: 2px solid #EF4444;
    font-size: 18px;
    padding: 16px 32px;
}

QPushButton#activate_btn_active:hover {
    background-color: #B91C1C;
}

QLabel {
    color: #E2E8F0;
}

QLabel#header_status_paused {
    color: #FBBF24;
    font-size: 16px;
    font-weight: bold;
    padding: 6px 14px;
    background-color: #451A03;
    border: 1px solid #B45309;
    border-radius: 6px;
}

QLabel#header_status_active {
    color: #34D399;
    font-size: 16px;
    font-weight: bold;
    padding: 6px 14px;
    background-color: #064E3B;
    border: 1px solid #059669;
    border-radius: 6px;
}

QLabel#header_status_lost {
    color: #F87171;
    font-size: 16px;
    font-weight: bold;
    padding: 6px 14px;
    background-color: #450A0A;
    border: 1px solid #DC2626;
    border-radius: 6px;
}

QGroupBox {
    border: 2px solid #334155;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: bold;
    color: #94A3B8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QProgressBar {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #F8FAFC;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #38BDF8;
    border-radius: 5px;
}
"""
