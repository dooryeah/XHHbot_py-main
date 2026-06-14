import hashlib
import secrets
import time
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
import requests
from config import CONFIG
from logger import log

_session = requests.Session()
_session.trust_env = False  # 禁用系统代理

def vm(num):
    if num & 128 != 0:
        return int(255 & ((num << 1) ^ 27))
    return num << 1

def qm(num):
    return vm(num) ^ num

def _m(num):
    return qm(vm(num))

def ym(num):
    return _m(qm(vm(num)))

def gm(num):
    return ym(num) ^ _m(num) ^ qm(num)

def mixed(e):
    t = [0]*6
    t[0] = gm(e[0]) ^ ym(e[1]) ^ _m(e[2]) ^ qm(e[3])
    t[1] = qm(e[0]) ^ gm(e[1]) ^ ym(e[2]) ^ _m(e[3])
    t[2] = _m(e[0]) ^ qm(e[1]) ^ gm(e[2]) ^ ym(e[3])
    t[3] = ym(e[0]) ^ _m(e[1]) ^ qm(e[2]) ^ gm(e[3])
    t[4] = e[4]
    t[5] = e[5]
    return t

def get_nonce(ts):
    rand = secrets.randbelow(int(time.time()*1000))
    raw = f"{ts}{rand}".encode("utf-8")
    return hashlib.md5(raw).hexdigest().upper()

def av(s, key, n):
    i = key[:len(key)+n]
    r = []
    for ch in s:
        p = i[ord(ch) % len(i)]
        r.append(p)
    return "".join(r)

def sv(s, key):
    r = []
    for ch in s:
        p = key[ord(ch) % len(key)]
        r.append(p)
    return "".join(r)

def new_str(arr):
    out = []
    max_len = max(len(arr[0]), len(arr[1]), len(arr[2]))
    for i in range(max_len):
        if len(arr[0]) > i:
            out.append(arr[0][i])
        if len(arr[1]) > i:
            out.append(arr[1][i])
        if len(arr[2]) > i:
            out.append(arr[2][i])
    return "".join(out)

def get_keys(reqpath):
    r = "AB45STUVWZEFGJ6CH01D237IXYPQRKLMN89"
    _time = int(time.time())
    nonce = get_nonce(_time)
    str1 = av(str(_time), r, -2)
    str2 = sv(reqpath, r)
    str3 = sv(nonce, r)
    arr = sorted([str1, str2, str3], key=len)
    new_string = new_str(arr)
    source = new_string[:20]  # 与 Go 版一致，只取前20
    md5 = hashlib.md5(source.encode("utf-8")).hexdigest()
    last_six = md5[-6:]
    mix = mixed([ord(c) for c in last_six])
    count = sum(mix)
    a = f"{count%100:02d}"
    s = av(md5[0:5], r, -4)
    return f"{s}{a}", nonce, _time

def send_req(method, path, body=None, other=""):
    cfg = CONFIG["xhh"]
    base_url = cfg["baseUrl"].rstrip("/") + path

    initial = {}
    if other:
        if other.startswith("?"):
            initial = parse_qs(other[1:], keep_blank_values=True)
        else:
            initial = parse_qs(other, keep_blank_values=True)
        initial = {k: v[0] if isinstance(v, list) else v for k, v in initial.items()}

    hkey, nonce, t = get_keys(path)
    params = {
        **initial,
        "os_type": "web",
        "app": "web",
        "client_type": "web",
        "version": cfg["version"],
        "web_version": cfg["webver"],
        "x_client_type": "web",
        "x_app": "heybox_website",
        "x_os_type": "Windows",
        "device_info": "Chrome",
        "device_id": cfg["deviceID"],
        "hkey": hkey,
        "_time": str(t),
        "nonce": nonce,
        "_notip": "true",
    }
    if XHH_INFO.get("heyboxId"):
        params["heybox_id"] = XHH_INFO["heyboxId"]

    headers = {
        "host": "api.xiaoheihe.cn",
        "Referer": "https://www.xiaoheihe.cn/",
        "Origin": "https://www.xiaoheihe.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if XHH_INFO.get("cookie"):
        headers["cookie"] = XHH_INFO["cookie"]
    if body is not None:
        headers["content-type"] = "application/x-www-form-urlencoded;charset=utf-8"

    try:
        req = requests.Request(method, base_url, params=params, data=body, headers=headers)
        prep = _session.prepare_request(req)
        if not (path in ("/bbs/app/user/message", "/bbs/app/feeds")):
            log.info("[XHH]REQ %s", prep.url)
        return _session.send(prep, timeout=20)
    except Exception as e:
        log.error("[XHH] SendReq Failed %s", e)
        return None

XHH_INFO = {"cookie": "", "heyboxId": "", "time": 0}