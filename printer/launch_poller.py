"""
launch_poller.py
Spawns printer_agent.py as a fully detached Windows process.
"""
import subprocess, os

BASE   = r"C:\Users\Administator\Desktop\dapurPintarMBG"
PYTHON = r"C:\Users\Administator\AppData\Local\Programs\Python\Python314\python.exe"
SCRIPT = os.path.join(BASE, "printer", "printer_agent.py")
LOG    = r"C:\Users\Administator\Desktop\poller.log"

log = open(LOG, "a")
p = subprocess.Popen(
    [PYTHON, SCRIPT],
    stdout=log,
    stderr=log,
    cwd=BASE,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
)
print(f"Printer agent started PID: {p.pid}")
