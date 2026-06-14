import logging
import os
import time

log = logging.getLogger("xhhrobot")

def init_logger():
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    os.makedirs("log", exist_ok=True)
    filename = time.strftime("%Y-%m-%d_%H_%M_%S") + ".log"
    file_handler = logging.FileHandler(os.path.join("log", filename), encoding="utf-8")
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    log.addHandler(file_handler)
    log.addHandler(console)
    log.info("[Loger]OK")