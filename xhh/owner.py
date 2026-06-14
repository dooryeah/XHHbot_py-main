from config import CONFIG
from logger import log
from .api import send_req
import time

OWNERS = []
FANS = []
_FANS_LAST = 0


def _load_ids(key: str, target: list, label: str):
    if target:
        return
    raw = CONFIG["xhh"].get(key, "") or ""
    for v in raw.split(","):
        v = v.strip()
        if not v:
            continue
        try:
            target.append(int(v))
        except ValueError:
            log.error("[XHH]%s配置->%s<-似乎并非数字", label, v)


def _refresh_fans_if_needed():
    global _FANS_LAST
    cfg = CONFIG["xhh"]
    if not cfg.get("fansAuto", False):
        return
    now = int(time.time())
    refresh = int(cfg.get("fansRefresh", 3600) or 3600)
    if _FANS_LAST and now - _FANS_LAST < refresh:
        return

    user_id_cfg = (cfg.get("fansUserId") or "").strip()
    if user_id_cfg:
        try:
            userid = int(user_id_cfg)
        except ValueError:
            log.error("[XHH]粉丝用户ID配置无效 %s", user_id_cfg)
            return
    else:
        owner_ids = []
        _load_ids("owner", owner_ids, "所有者")
        if not owner_ids:
            return
        userid = owner_ids[0]

    limit = int(cfg.get("fansLimit", 100) or 100)
    limit = max(1, min(200, limit))
    offset = 0
    fans = []

    total = None
    while True:
        qs = f"?userid={userid}&offset={offset}&limit={limit}"
        resp = send_req("GET", "/bbs/app/profile/follower/list", None, qs)
        if resp is None or resp.status_code != 200:
            log.error("[XHH]粉丝列表请求失败 code=%s", getattr(resp, "status_code", None))
            break
        try:
            data = resp.json()
        except Exception:
            log.error("[XHH]粉丝列表JSON解析失败")
            break
        if data.get("status") != "ok":
            log.error("[XHH]粉丝列表返回失败 %s", data)
            break

        result = data.get("result") or {}
        if total is None:
            follow_cnt = data.get("follow_cnt") or {}
            try:
                total = int(follow_cnt.get("fan_num"))
            except Exception:
                total = None
        items = (
            result.get("list")
            or result.get("items")
            or result.get("follower_list")
            or result.get("follow_list")
            or result.get("followers")
            or result.get("data")
            or data.get("follow_list")
            or []
        )
        if isinstance(result, list):
            items = result

        batch = []
        for it in items:
            uid = it.get("userid") or it.get("user_id") or it.get("id")
            try:
                uid = int(uid)
            except Exception:
                uid = None
            if uid:
                batch.append(uid)
        fans.extend(batch)

        if not items:
            log.warning(
                "[XHH]粉丝列表为空 result_keys=%s top_keys=%s",
                list(result.keys()) if isinstance(result, dict) else type(result),
                list(data.keys())
            )
            break

        fetched = len(items)
        if total is not None and offset + fetched < total:
            offset += fetched
            continue

        if fetched < limit:
            break
        offset += limit

    if fans:
        FANS.clear()
        FANS.extend(sorted(set(fans)))
        _FANS_LAST = now
        log.info("[XHH]粉丝列表已更新 count=%d", len(FANS))


def check(uid: int) -> bool:
    if not OWNERS:
        owner = CONFIG["xhh"].get("owner", "")
        if not owner:
            log.error("您未在配置中设置所有者（Xhh.owner）程序已退出！")
            raise SystemExit(1)
        for v in owner.split(","):
            v = v.strip()
            if not v:
                continue
            try:
                OWNERS.append(int(v))
            except ValueError:
                log.error("[XHH]您的所有者配置->%s<-似乎并非数字", v)
    return True


def is_fan(uid: int) -> bool:
    if not CONFIG["xhh"].get("fansOnly", False):
        return True
    _refresh_fans_if_needed()
    _load_ids("fans", FANS, "粉丝")
    if not FANS:
        if CONFIG["xhh"].get("fansAuto", False):
            log.warning("[XHH]已开启仅粉丝回复，但粉丝列表为空，请检查接口返回或手动设置 xhh.fans")
        else:
            log.warning("[XHH]已开启仅粉丝回复，但未配置粉丝列表（xhh.fans）")
        return False
    return uid in FANS


def can_reply(uid: int) -> bool:
    check(uid)
    return is_fan(uid)