from PySide6.QtCore import QObject, Slot, Signal


class Bridge(QObject):
    # Signals -> JS
    messageFromPython = Signal(str)

    def __init__(self):
        super().__init__()

    # Slots -> callable from JS
    @Slot(str)
    def receiveMessage(self, msg: str):
        print(f"Python received: {msg}")
        # Example: send back to JS
        self.messageFromPython.emit(f"Echo from Python: {msg}")