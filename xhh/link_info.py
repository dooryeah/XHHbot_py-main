import json
import json
from logger import log
from .api import send_req
import db

def get_link_info(link_id: int, comment_id: int):
    resp = send_req("GET", "/bbs/app/link/tree", None, f"?h_src&link_id={link_id}")
    if resp is None:
        return [], [], []
    data = resp.json()
    if data.get("status") != "ok":
        if data.get("status") == "failed":
            db.replied(comment_id)
            log.warning("[XHH]原帖无法被查看，所以已标记为完成")
            return [], [], []
        log.error("[XHH]返回了错误的内容 %s", data)
        return [], [], []

    link = data["result"]["link"]
    raw_text = link.get("text") or ""
    if not raw_text.strip():
        log.warning("[XHH]帖子内容为空")
        content_list = []
    else:
        try:
            content_list = json.loads(raw_text)
        except Exception as e:
            log.error("[XHH]无法解析内容 %s", e)
            content_list = [{"type": "text", "text": raw_text}]

    contents = [{"type": "text", "text": "以下是帖子内容：\n标题：" + link["title"]}]
    for v in content_list:
        if v.get("type") == "html":
            contents.append({"type": "text", "text": v.get("text", "")})
        elif v.get("type") != "text":
            url = v.get("url") or v.get("image_url")
            if url:
                contents.append({"type": "image_url", "image_url": {"url": url}})
            else:
                log.warning("[XHH]内容图片缺少url，已跳过 %s", v)
        else:
            contents.append({"type": "text", "text": v.get("text", "")})

    return contents, link.get("topics", []), link.get("hashtags", [])