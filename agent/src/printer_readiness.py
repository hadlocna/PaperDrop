"""Fail-closed ESC/POS readiness probe, serialized with managed image printing."""
import threading

PRINTER_LOCK = threading.Lock()


def printer_ready():
    if not PRINTER_LOCK.acquire(blocking=False):
        return False
    printer = None
    try:
        from escpos.printer import Usb
        from escpos.constants import RT_STATUS_ONLINE, RT_STATUS_PAPER
        printer = Usb(0x04b8, 0x0e28, profile='TM-T20II', timeout=1500,
                      auto_detach_kernel_driver=True)
        online = printer.query_status(RT_STATUS_ONLINE)
        paper = printer.query_status(RT_STATUS_PAPER)
        # Empty/invalid status is unknown, not ready. Bit 3 means offline;
        # paper-out bits 5/6 must both be clear. Near-end paper is still usable.
        return (len(online) == 1 and len(paper) == 1
                and (online[0] & 0x93) == 0x12 and not (online[0] & 0x08)
                and (paper[0] & 0x93) == 0x12 and not (paper[0] & 0x60))
    except Exception:
        return False
    finally:
        if printer is not None:
            try:
                printer.close()
            except Exception:
                pass
        PRINTER_LOCK.release()
