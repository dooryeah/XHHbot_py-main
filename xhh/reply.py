import time
import threading
import urllib.parse
from logger import log
from .api import send_req
import db

_lock = threading.Lock()

def reply(text, link_id, reply_id, root_id, iscy=""):
    with _lock:
        if str(reply_id) in ("0", "", "None") and str(root_id) in ("0", "", "None"):
            body = f"is_cy={iscy}&link_id={link_id}&text={urllib.parse.quote(text)}"
        else:
            body = f"is_cy={iscy}&link_id={link_id}&reply_id={reply_id}&root_id={root_id}&text={urllib.parse.quote(text)}"
        resp = send_req("POST", "/bbs/app/comment/create", body.encode("utf-8"), "")
        if resp is None:
            log.error("[XHH]链接发送失败了")
            return False

        try:
            data = resp.json()
        except Exception:
            log.error("[XHH]评论返回非JSON或无法解析 body=%s", resp.text[:1000])
            return False

        if data.get("status") != "ok":
            if data.get("status") == "failed":
                if str(reply_id) not in ("0", "", "None"):
                    try:
                        db.replied(int(reply_id))
                    except Exception:
                        log.exception("[XHH]在标记已完成时出错 reply_id=%s", reply_id)
                    log.info("[XHH]因为无法评论，所以已标记为完成 %s", data)
                else:
                    log.warning("[XHH]顶层评论失败，未标记为完成 %s", data)
                time.sleep(5)
                return True
            if data.get("msg") == "评论已被删除":
                time.sleep(5)
                return True
            log.error("[XHH]评论发送失败 %s", data)
            return False

        time.sleep(5)
        return True