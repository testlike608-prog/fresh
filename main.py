import keyboard
import ClientsClass as cc
import threading
import scanner
import debug_monitor


def scanner_thread():
    scanner.start_listener()

if __name__ == "__main__":
    app= cc.App()
    threading.Thread(target=scanner_thread, daemon=True).start()

    # ── Debug monitor (يشتغل لما DEBUG=1) ─────────────────────────────
    if debug_monitor.is_enabled():
        debug_monitor.start(app_ref=app)

    app.run()  # ده شغّال على الـ main thread7293147930221041450501

    keyboard.wait('esc')  # يقفل البرنامج لما تدوس esc
    scanner.stop_listener()  # تأكد إنك بتوقف الـ listener لما البرنامج يخلص