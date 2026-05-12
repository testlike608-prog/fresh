"""
debug_monitor.py
----------------
Background thread that periodically prints the state of:
  - scanner.queue_barcode (size + last items snapshot)
  - scanner.flag_barcode
  - scanner.last_barcode
  - scanner._recorded_keys
  - TCPServer.shared_queue & receive_queue (لو متاحة)
  - list of active threads

شغّاله بس لو DEBUG=1 في environment (شوف launch.json).
"""

import os
import sys
import time
import threading
import queue


def _peek_queue(q: "queue.Queue", limit: int = 5):
    """يطبع لقطة من محتويات الكيو من غير ما يفرغها."""
    try:
        with q.mutex:  # ناخد lock الداخلي للكيو عشان نقرأ بأمان
            items = list(q.queue)
        return items[-limit:], len(items)
    except Exception as e:
        return [f"<peek error: {e}>"], -1


def _format_value(v, max_len: int = 80):
    s = repr(v)
    if len(s) > max_len:
        s = s[:max_len] + "..."
    return s


def _monitor_loop(interval: float, app_ref):
    import scanner  # late import عشان نضمن إن الموديول اتحمّل

    counter = 0
    print(f"[DEBUG MONITOR] started — interval={interval}s", flush=True)
    while True:
        try:
            counter += 1
            lines = []
            lines.append("\n" + "=" * 70)
            lines.append(f"[DEBUG MONITOR] tick #{counter} @ {time.strftime('%H:%M:%S')}")
            lines.append("-" * 70)

            # ── Scanner state ────────────────────────────────────────────
            q_items, q_size = _peek_queue(scanner.queue_barcode)
            lines.append(f"scanner.queue_barcode      size = {q_size}")
            lines.append(f"  last items (up to 5)     = {q_items}")
            lines.append(f"scanner.flag_barcode       = {scanner.flag_barcode}")
            lines.append(f"scanner.last_barcode       = {_format_value(scanner.last_barcode)}")
            lines.append(f"scanner._recorded_keys     = {_format_value(scanner._recorded_keys)}")
            lines.append(f"scanner._listener_started  = {scanner._listener_started}")

            # ── TCPServer state (لو app متاح) ────────────────────────────
            if app_ref is not None:
                lines.append("-" * 70)
                # نحاول نلاقي TCPServer instances جوّا الـ App
                for attr_name in dir(app_ref):
                    if attr_name.startswith("_"):
                        continue
                    try:
                        attr = getattr(app_ref, attr_name)
                    except Exception:
                        continue
                    # لو لقينا كيو في الـ App مباشرة
                    if isinstance(attr, queue.Queue):
                        items, size = _peek_queue(attr)
                        lines.append(f"app.{attr_name:<22} size = {size}, last = {items}")
                    # لو لقينا object فيه shared_queue/receive_queue
                    for sub in ("shared_queue", "receive_queue"):
                        try:
                            sub_q = getattr(attr, sub, None)
                        except Exception:
                            sub_q = None
                        if isinstance(sub_q, queue.Queue):
                            items, size = _peek_queue(sub_q)
                            lines.append(
                                f"app.{attr_name}.{sub:<14} size = {size}, last = {items}"
                            )
                    # clients list في TCPServer
                    clients = getattr(attr, "clients", None)
                    if isinstance(clients, list):
                        lines.append(f"app.{attr_name}.clients         count = {len(clients)}")

            # ── Threads ──────────────────────────────────────────────────
            lines.append("-" * 70)
            alive = [t.name for t in threading.enumerate()]
            lines.append(f"threads ({len(alive)}): {alive}")
            lines.append("=" * 70)

            print("\n".join(lines), flush=True)
        except Exception as e:
            print(f"[DEBUG MONITOR] error: {e}", file=sys.stderr, flush=True)

        time.sleep(interval)


def start(app_ref=None, interval: float = None):
    """
    يشغّل المونيتور في thread منفصل.
    - app_ref: instance من App عشان نراقب الكيوز اللي جواه (اختياري).
    - interval: ثواني بين كل طباعة. لو None ياخدها من DEBUG_INTERVAL env.
    """
    if interval is None:
        try:
            interval = float(os.environ.get("DEBUG_INTERVAL", "1.0"))
        except ValueError:
            interval = 1.0

    t = threading.Thread(
        target=_monitor_loop,
        args=(interval, app_ref),
        name="DebugMonitor",
        daemon=True,
    )
    t.start()
    return t


def is_enabled() -> bool:
    """يرجع True لو DEBUG=1 في الـ environment."""
    return os.environ.get("DEBUG", "").strip() in ("1", "true", "True", "yes")
