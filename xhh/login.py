# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import time
import qrcode
from logger import log
from .api import send_req, XHH_INFO

def login():
    qr()

def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def qr():
    print("扫码登陆")
    resp = send_req("GET", "/account/get_qrcode_url/", None, "")
    if resp is None:
        log.error("[XHH]无法创建请求")
        return

    data = _safe_json(resp)
    if not data:
        log.error("[XHH]无法解析JSON: %s", resp.text)
        return

    qr_url = data.get("result", {}).get("qr_url")
    if not qr_url:
        log.error("[XHH]未获取到qr_url，原始响应: %s", data)
        return

    qr_code = qrcode.QRCode(border=1)
    qr_code.add_data(qr_url)
    qr_code.make(fit=True)
    img = qr_code.make_image(fill_color="black", back_color="white")
    img.save("qrcode.png")
    qr_code.print_ascii(invert=True)

    last_err = None
    while True:
        query = qr_url.split("https://api.xiaoheihe.cn/account/qr_login/?")[1]
        resp = send_req("GET", "/account/qr_state/", None, f"?{query}")
        if resp is None:
            log.error("[XHH]无法查询扫码状态")
            return

        res = _safe_json(resp)
        if not res or "result" not in res:
            log.error("[XHH]扫码状态响应异常: %s", resp.text)
            return

        err = res["result"].get("error")
        err_msg = res["result"].get("error_msg")

        if err != last_err:
            print(f"[XHH]扫码状态: {err} {err_msg}")
            last_err = err

        if err != "ok":
            time.sleep(1)
            continue

        cookies = resp.cookies.get_dict()
        c1 = cookies.get("heybox_id") or cookies.get("user_heybox_id")
        c2 = cookies.get("key") or cookies.get("user_pkey")
        if not c1 or not c2:
            log.error("[XHH]登录成功但缺少关键Cookie: %s", cookies)
            return

        # 兼容两种命名
        name1 = "heybox_id" if "heybox_id" in cookies else "user_heybox_id"
        name2 = "key" if "key" in cookies else "user_pkey"

        XHH_INFO["cookie"] = f"{name1}={c1};{name2}={c2}" + get_token()
        XHH_INFO["heyboxId"] = cookies.get("user_heybox_id") or c1
        XHH_INFO["time"] = int(time.time())

        with open("cookie.json", "w", encoding="utf-8") as f:
            json.dump(XHH_INFO, f, ensure_ascii=False)

        print(f"\n欢迎您 -> {res['result'].get('nickname','')} | Cookie已保存\n")
        return

def get_token():
    raw = b""
    raw += hashlib.md5(str(int(time.time())).encode()).digest()
    raw += hashlib.md5("唉？！云朵！".encode()).digest()
    raw += hashlib.md5("哒哒哒哒哒，好想玩原神".encode()).digest()
    raw += hashlib.md5("云！原！神！".encode()).digest()
    raw += b"\x00"
    return ";x_xhh_tokenid=" + base64.b64encode(raw).decode()