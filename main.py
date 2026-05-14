import keyboard
import ClientsClass as cc
import scanner
import debug_monitor
import thread_logger

# ── إعداد اللوج للثريدز و الكراش (لازم يتنده الأول) ────────────────
log = thread_logger.setup(watchdog_interval=2.0)


def scanner_thread():
    scanner.start_listener()

if __name__ == "__main__":
    log.info("=== main.py: program starting ===")
    app= cc.App()
    thread_logger.LoggedThread(target=scanner_thread, name="scanner-listener", daemon=True).start()

    # ── Debug monitor (يشتغل لما DEBUG=1) ─────────────────────────────
    if debug_monitor.is_enabled():
        debug_monitor.start(app_ref=app)

    app.run()  # ده شغّال على الـ main thread7293147930221041450501

    keyboard.wait('esc')  # يقفل البرنامج لما تدوس esc
    scanner.stop_listener()  # تأكد إنك بتوقف الـ listener لما البرنامج يخلص
    log.info("=== main.py: program exited ===")