# -*- coding: utf-8 -*-
import copy
import json
import os
import sys
import uuid
from logger import log

CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "xhh": {
        "checkTime": 0,
        "replyTime": 0,
        "foundReplyTime": 0.1,
        "foundReplyProb": 1.0,
        "foundReplyEnabled": True,
        "owner": "",
        "fansOnly": False,
        "fansAuto": False,
        "fansRefresh": 600,
        "fansLimit": 100,
        "fansUserId": "",
        "fans": "",
        "deviceID": "",
        "baseUrl": "",
        "webver": "",
        "version": ""
    },
    "database": {
        "type": "sqlite",
        "db": "",
        "host": "",
        "port": "",
        "user": "",
        "passwd": ""
    },
    "ai": {
        "model": "",
        "prompt": "",
        "baseUrl": "",
        "token": ""
    },
    "tavily": {
        "enabled": True,
        "apiKey": "",
        "maxResults": 5,
        "searchDepth": "basic"
    }
}

CONFIG = copy.deepcopy(DEFAULT_CONFIG)

def _ensure_device_id(cfg):
    if not cfg["xhh"].get("deviceID"):
        cfg["xhh"]["deviceID"] = uuid.uuid4().hex


def _deep_merge(target, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
            continue
        target[key] = value
    return target

def init_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        _ensure_device_id(cfg)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        log.error("请修改配置文件后重新启动")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        log.error("配置文件格式错误，请检查 config.json")
        sys.exit(1)

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    _deep_merge(cfg, data)
    _ensure_device_id(cfg)

    CONFIG.clear()
    CONFIG.update(cfg)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=2)

    log.info("[CFG]Init OK")
