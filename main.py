# -*- coding: utf-8 -*-
import argparse
import time
from config import init_config
from logger import init_logger, log
import db
from xhh.worker import init as xhh_init, start as xhh_start
from xhh.login import login
from xhh.worker import check_new_first_run

def main():
    init_logger()
    init_config()
    time.sleep(1)
    db.init()

    parser = argparse.ArgumentParser()
    parser.add_argument("-mode", default="default")
    args = parser.parse_args()

    if args.mode == "default":
        log.info("\nhttps://github.com/SomeOvO/xhhRobot\n浣犻渶瑕佽緭鍏ュ惎鍔ㄩ」\n-mode start | login | test")
        return
    if args.mode == "test":
        print("浣犲ソ")
        return
    if args.mode == "login":
        login()
        return
    if args.mode == "start":
        check_new_first_run()
        xhh_init()
        xhh_start()
        while True:
            time.sleep(3600)

if __name__ == "__main__":
    main()