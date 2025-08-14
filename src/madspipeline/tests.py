import sys

# pylsl
try:
    from pylsl import StreamInfo, StreamOutlet
    info = StreamInfo('TestStream', 'Markers', 1, 0, 'string', 'test123')
    outlet = StreamOutlet(info)
    outlet.push_sample(['hello'])
    print("pylsl OK")
except Exception as e:
    print("pylsl error:", e)

# tobii-research
try:
    import tobii_research
    print("tobii_research OK")
except Exception as e:
    print("tobii_research error:", e)

# GUI
try:
    from PySide6.QtWidgets import QApplication, QLabel
    app = QApplication([])
    lbl = QLabel("PySide6 window — close me")
    lbl.resize(400, 150)
    lbl.show()
    app.exec()
except Exception as e:
    print("GUI error:", e)
