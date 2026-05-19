"""
main.py
-------
Entry point للنسخه الـ headless (بدون GUI).
للـ GUI استخدم: python gui_app.py

الـ exe المبني بـ Nuitka بيشغل gui_app.py مش main.py.
"""

import keyboard
import ClientsClass as cc
import scanner
import debug_monitor
import thread_logger

# اعداد اللوج للثريدز و الكراش (لازم يتنده الأول)
log = thread_logger.setup(watchdog_interval=2.0)


def scanner_thread():
    scanner.start_listener()


if __name__ == "__main__":
    log.info("=== main.py: program starting ===")
    app = cc.App()

    thread_logger.LoggedThread(
        target=scanner_thread,
        name="scanner-listener",
        daemon=True,
    ).start()

    # Debug monitor (بنخليها فعّالة دايماً)
    debug_monitor.start(app_ref=app, interval=5.0, force=True)

    app.run()  # بيشغل threads ويرجع فوراً

    try:
        keyboard.wait('esc')  # يقفل البرنامج لما تدوس esc
    finally:
        log.info("Esc pressed - shutting down...")
        try:
            scanner.stop_listener()
        except Exception as e:
            log.warning(f"scanner.stop_listener failed: {e}")
        try:
            app.stop()
        except Exception as e:
            log.warning(f"app.stop failed: {e}")
        try:
            debug_monitor.stop()
        except Exception:
            pass
        log.info("=== main.py: program exited ===")
