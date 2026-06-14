# -*- coding: utf-8 -*-
import json
import re
from urllib.parse import urljoin
import requests
from config import CONFIG
from logger import log

_session = requests.Session()
_session.trust_env = False  # 禁用系统代理

def _chat_completions_url(base_url: str) -> str:
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        return ""
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url + "/chat/completions"

def _safe_text(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit]
    return text

def _build_user_content(contents, user_say, search_text, safe_mode: bool = False):
    if safe_mode:
        text_parts = []
        for c in contents:
            if c.get("type") == "text":
                text = _safe_text(c.get("text", ""))
                if text:
                    text_parts.append(text)
            if len(text_parts) >= 2:
                break
        if user_say:
            text_parts.append(_safe_text(user_say))
        if not text_parts:
            text_parts = ["请简短回复。"]
        return [{"type": "text", "text": " ".join(text_parts)}]

    user_content = contents + [{"type": "text", "text": "以上是帖子内容。" + user_say}]
    if search_text:
        user_content.append({"type": "text", "text": "以下是联网搜索结果：\n" + search_text})
    return user_content

def _tavily_search(query: str) -> str:
    cfg = CONFIG.get("tavily", {})
    if not cfg.get("enabled") or not cfg.get("apiKey"):
        return ""

    if query:
        query = query.strip()
        if len(query) > 400:
            query = query[:400]

    log.info("[Ai]Tavily搜索: %s", query)

    payload = {
        "api_key": cfg["apiKey"],
        "query": query,
        "search_depth": cfg.get("searchDepth", "basic"),
        "max_results": cfg.get("maxResults", 5),
    }

    try:
        resp = _session.post("https://api.tavily.com/search", json=payload, timeout=(10, 20))
    except Exception as e:
        log.error("[Ai]Tavily请求失败 %s", e)
        return ""

    if resp.status_code != 200:
        log.error("[Ai]Tavily HTTP %s: %s", resp.status_code, resp.text)
        return ""

    try:
        data = resp.json()
    except Exception:
        log.error("[Ai]Tavily返回非JSON: %s", resp.text)
        return ""

    results = data.get("results", [])
    if not results:
        log.info("[Ai]Tavily无结果")
        return ""

    lines = []
    for i, item in enumerate(results, 1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        content = item.get("content") or ""
        lines.append(f"{i}. {title}\n{url}\n{content}")

    log.info("[Ai]Tavily结果数=%d", len(results))
    return "\n\n".join(lines)

def _post_with_redirect(url, headers, body):
    resp = _session.post(
        url,
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
        timeout=(10, 120),
        allow_redirects=False
    )
    if resp.status_code in (301, 302, 307, 308):
        location = resp.headers.get("Location")
        if location:
            redirect_url = urljoin(url, location)
            resp = _session.post(
                redirect_url,
                headers=headers,
                data=json.dumps(body).encode("utf-8"),
                timeout=(10, 120),
                allow_redirects=False
            )
    return resp

def get_ai_reply(contents, user_say, topics, tags):
    log.info("[Ai]正在询问Ai")
    cfg = CONFIG["ai"]
    chat_url = _chat_completions_url(cfg.get("baseUrl", ""))
    prompt = cfg["prompt"] or ""

    top_str = "".join([t["name"] for t in topics])
    tag_str = "".join([t["name"] for t in tags])
    prompt = prompt.replace("?!top!?", top_str).replace("?!tag!?", tag_str)

    system_msg = {"role": "system", "content": prompt}

    text_parts = [user_say.strip()] if user_say else []
    for c in contents:
        if c.get("type") == "text":
            text = c.get("text", "").strip()
            if text:
                text_parts.append(text)
        if len(text_parts) >= 6:
            break
    search_query = " ".join(text_parts).strip()
    if not search_query:
        search_query = "小黑盒 帖子 搜索"
    search_text = _tavily_search(search_query)

    user_content = _build_user_content(contents, user_say, search_text, safe_mode=False)

    user_msg = {"role": "user", "content": user_content}

    body = {
        "model": cfg["model"],
        "messages": [system_msg, user_msg],
        "stream": False
    }

    if not cfg["model"]:
        raise SystemExit("[Ai]请确保配置文件中的模型是存在的")
    if not chat_url:
        raise SystemExit("[Ai]请确保配置文件中的AI接口地址是存在的")

    headers = {"Authorization": "Bearer " + cfg["token"], "Content-Type": "application/json"}
    try:
        resp = _post_with_redirect(chat_url, headers, body)
    except requests.exceptions.RequestException as e:
        log.error("[Ai]请求失败 %s", e)
        return ""

    if resp.status_code != 200:
        if 300 <= resp.status_code < 400:
            log.error("[Ai]HTTP %s 重定向到 %s", resp.status_code, resp.headers.get("Location"))
        else:
            log.error("[Ai]HTTP %s: %s", resp.status_code, resp.text)
        if resp.status_code == 400 and "data_inspection_failed" in resp.text:
            log.warning("[Ai]内容安全拦截，尝试降级输入")
            user_msg = {"role": "user", "content": _build_user_content(contents, user_say, "", safe_mode=True)}
            body = {
                "model": cfg["model"],
                "messages": [system_msg, user_msg],
                "stream": False
            }
            try:
                resp = _post_with_redirect(chat_url, headers, body)
            except requests.exceptions.RequestException as e:
                log.error("[Ai]请求失败 %s", e)
                return ""
            if resp.status_code != 200:
                if 300 <= resp.status_code < 400:
                    log.error("[Ai]HTTP %s 重定向到 %s", resp.status_code, resp.headers.get("Location"))
                else:
                    log.error("[Ai]HTTP %s: %s", resp.status_code, resp.text)
                return ""
        else:
            return ""

    try:
        data = resp.json()
    except Exception:
        log.error("[Ai]非JSON响应: %s", resp.text)
        return ""
    choices = data.get("choices", [])
    if not choices:
        log.error("[Ai]Ai返回错误 %s", data)
        return ""
    text = choices[0]["message"]["content"]
    log.info("[Ai]Ai说：%s | 本次消耗token=%s", text, data.get("usage", {}).get("total_tokens"))
    return text
