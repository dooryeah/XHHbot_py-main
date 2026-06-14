import json
import time
import threading
import random
from logger import log
from config import CONFIG
import db
from .api import send_req, XHH_INFO
from .owner import check, can_reply
from .link_info import get_link_info
from .reply import reply
from ai import get_ai_reply

CHECK_TIME = 30
REPLY_TIME = 10
FOUND_REPLY_TIME = 0.1
FOUND_REPLY_PROB = 1.0
FOUND_REPLY_ENABLED = True
DONT_REPLY = False
FEED_QUERY = "?pull=0&offset=0&dw=604"

err_info = {"count": 0, "last": 0}
_found_backoff = 0.0

def _load_cookie():
    try:
        with open("cookie.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            XHH_INFO.update(data)
    except FileNotFoundError:
        log.info("[XHH]未检测到Cookie")


def _load_runtime_config():
    global CHECK_TIME, REPLY_TIME, FOUND_REPLY_TIME, FOUND_REPLY_PROB, FOUND_REPLY_ENABLED
    cfg = CONFIG["xhh"]
    CHECK_TIME = cfg.get("checkTime", 30) or 30
    REPLY_TIME = cfg.get("replyTime", 10) or 10
    FOUND_REPLY_TIME = cfg.get("foundReplyTime", 0.1) or 0.1
    FOUND_REPLY_PROB = cfg.get("foundReplyProb", 1.0)
    FOUND_REPLY_ENABLED = bool(cfg.get("foundReplyEnabled", True))

    if CHECK_TIME == 0:
        log.warning("[XHH]您的设置中未设置检查时间，已默认为30s")
        CHECK_TIME = 30
    if REPLY_TIME == 0:
        log.warning("[XHH]您的设置中未设置回复间隔，已默认为10s")
        REPLY_TIME = 10
    if FOUND_REPLY_TIME <= 0:
        log.warning("[XHH]推荐回复频率无效，已默认为0.1s")
        FOUND_REPLY_TIME = 0.1
    if not isinstance(FOUND_REPLY_PROB, (int, float)):
        FOUND_REPLY_PROB = 1.0
    FOUND_REPLY_PROB = max(0.0, min(1.0, float(FOUND_REPLY_PROB)))

    if FOUND_REPLY_ENABLED:
        log.info("[XHH]主动浏览帖子并评论：已开启")
    else:
        log.info("[XHH]主动浏览帖子并评论：已关闭")


def init():
    _load_cookie()
    _load_runtime_config()

def _sleep_with_jitter(base: float, extra: float = 0.0):
    jitter = random.uniform(0.05, 0.35)
    time.sleep(base + extra + jitter)

def _found_backoff_on_fail():
    global _found_backoff
    _found_backoff = 1.0 if _found_backoff <= 0 else min(_found_backoff * 2, 60.0)
    _sleep_with_jitter(FOUND_REPLY_TIME, _found_backoff)

def _found_backoff_reset():
    global _found_backoff
    _found_backoff = 0.0

def is_err():
    now = int(time.time())
    if err_info["count"] < 5:
        if (now - err_info["last"]) < 600:
            err_info["count"] = 1
            return
        err_info["last"] = now
        err_info["count"] += 1
        return
    log.error("[XHH]程序十分钟内错误五次，已退出防止频繁")
    raise SystemExit(1)

def _extract_link_ids(data):
    result = data.get("result") or data.get("data") or {}
    items = []

    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        for k in ("links", "items", "list", "data", "posts", "link_list"):
            v = result.get(k)
            if isinstance(v, list):
                items = v
                break

        if not items:
            sf = result.get("search_found")
            if isinstance(sf, list):
                items = sf
            elif isinstance(sf, dict):
                for k in ("list", "items", "data", "links", "posts"):
                    v = sf.get(k)
                    if isinstance(v, list):
                        items = v
                        break

    out = []
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            continue

        # 仅接受真实帖子结构，避免 search_found 建议项
        if not ("link_id" in it or "linkid" in it or "link" in it):
            continue

        link_id = it.get("link_id") or it.get("linkid")
        if not link_id and isinstance(it.get("link"), dict):
            link_id = it["link"].get("link_id") or it["link"].get("id")

        try:
            lid = int(link_id) if link_id is not None else None
        except Exception:
            lid = None

        if lid and lid not in seen:
            seen.add(lid)
            out.append(lid)

    return out

def get_found_links():
    resp = send_req("GET", "/bbs/app/feeds", None, FEED_QUERY)
    if resp is None:
        log.error("[XHH]推荐流请求失败")
        _found_backoff_on_fail()
        return []
    if resp.status_code != 200:
        log.error("[XHH]推荐流HTTP错误 code=%s body=%s", resp.status_code, resp.text[:500])
        _found_backoff_on_fail()
        return []
    try:
        data = resp.json()
    except Exception:
        log.error("[XHH]推荐流JSON解析失败 body=%s", resp.text[:500])
        _found_backoff_on_fail()
        return []
    if data.get("status") == "failed":
        log.error("[XHH]推荐流返回失败 %s", data)
        _found_backoff_on_fail()
        return []

    ids = _extract_link_ids(data)
    log.info("[XHH]推荐流link数=%d", len(ids))
    if not ids:
        log.info("[XHH]推荐流原始keys=%s", list(data.keys()))
        log.info("[XHH]推荐流result keys=%s", list((data.get("result") or {}).keys()))
    _found_backoff_reset()
    return ids

def check_at_loop():
    global DONT_REPLY
    while True:
        print("[XHH]检查@", time.strftime("%Y-%m-%d %H:%M:%S"))
        resp = send_req("GET", "/bbs/app/user/message", None, "?message_type=16&offset=0&limit=20&no_more=false")
        if resp is None:
            log.error("[XHH]链接发送失败了")
            is_err()
            time.sleep(CHECK_TIME)
            continue

        try:
            data = resp.json()
        except Exception:
            log.error("[XHH]JSON解析失败")
            time.sleep(CHECK_TIME)
            continue

        for v in data.get("result", {}).get("messages", []):
            comment_id = v.get("comment_a_id")
            if comment_id and db.is_replied(comment_id):
                continue
            if can_reply(v["userid_a"]):
                db.insert(
                    v["message_id"], v["comment_a_id"], v["root_comment_id"], v["linkid"],
                    v["userid_a"], v["comment_a_text"], DONT_REPLY
                )
        DONT_REPLY = False
        time.sleep(CHECK_TIME)

def auto_reply_loop():
    while True:
        arr = db.get_comm()
        if not arr:
            print("[XHH]无可回复", time.strftime("%Y-%m-%d %H:%M:%S"))
            time.sleep(REPLY_TIME)
            continue

        log.info("[XHH]正在回复评论 评论数=%d", len(arr))
        threads = []

        def worker(v):
            if v["comment_id"] == 0:
                return

            if not can_reply(v["uid"]):
                db.replied(v["comment_id"])
                log.info("[XHH]跳过无权限旧评论 uid=%s comment_id=%s", v["uid"], v["comment_id"])
                return

            info, top, tags = get_link_info(v["link_id"], v["comment_id"])
            if len(info) <= 1:
                log.info("[XHH]获取LinkID失败")
                is_err()
                return
            reply_text = get_ai_reply(info, v["text"], top, tags)
            if not reply_text:
                log.info("[XHH]Ai返回错误")
                is_err()
                return
            ok = reply(reply_text, str(v["link_id"]), str(v["comment_id"]), str(v["root_id"]), "")
            if ok:
                db.replied(v["comment_id"])
            else:
                is_err()
                log.error("[XHH]无法回复评论")

        for v in arr:
            t = threading.Thread(target=worker, args=(v,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        time.sleep(REPLY_TIME)

def auto_reply_found_loop():
    if not FOUND_REPLY_ENABLED:
        log.info("[XHH]主动浏览帖子并评论线程未启动")
        return

    while True:
        link_ids = get_found_links()
        if not link_ids:
            _sleep_with_jitter(FOUND_REPLY_TIME, _found_backoff)
            continue

        skipped_count = 0
        last_skipped = None
        for link_id in link_ids:
            if db.link_handled(link_id):
                continue

            if FOUND_REPLY_PROB < 1.0 and random.random() > FOUND_REPLY_PROB:
                skipped_count += 1
                last_skipped = link_id
                continue

            info, top, tags = get_link_info(link_id, 0)
            if len(info) <= 1:
                db.link_set(link_id, False)
                continue

            log.info("[XHH]推荐流link=%s topics=%s tags=%s", link_id, [t.get("name") for t in (top or [])], [t.get("name") for t in (tags or [])])

            # 不再做标签过滤：对所有解析成功的推荐项尝试生成并发布回复
            reply_text = get_ai_reply(info, "请针对该帖子给出回复。", top, tags)
            if not reply_text:
                is_err()
                _found_backoff_on_fail()
                continue

            ok = reply(reply_text, str(link_id), "0", "0", "")
            if ok:
                db.link_set(link_id, True)
                _found_backoff_reset()
            else:
                is_err()
                log.error("[XHH]无法回复推荐帖子")
                _found_backoff_on_fail()

            _sleep_with_jitter(FOUND_REPLY_TIME, _found_backoff)

        if skipped_count:
            log.info("[XHH]随机跳过推荐帖子 link=%s prob=%.2f×%d", last_skipped, FOUND_REPLY_PROB, skipped_count)

        _sleep_with_jitter(FOUND_REPLY_TIME, _found_backoff)

def start():
    print("[XHH] Starting")
    threading.Thread(target=check_at_loop, daemon=True).start()
    threading.Thread(target=auto_reply_loop, daemon=True).start()
    if FOUND_REPLY_ENABLED:
        threading.Thread(target=auto_reply_found_loop, daemon=True).start()

def check_new_first_run():
    global DONT_REPLY
    if not db.is_new():
        return
    print("检测到您是第一次运行\n是否允许将先前@过的名单加入至艾特列表？\ny(es) or n(o) 默认n\n请输入y或n")
    s = input().strip().lower()
    DONT_REPLY = (s in ("n", "no", ""))
