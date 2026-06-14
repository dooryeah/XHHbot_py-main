# XhhRobot（Python 版）

小黑盒类 Grok 机器人（Python 重构版）

# 能做什么？
自动检查指定用户的 @ 消息并使用 AI 回复

- 自定义提示词
- 自定义 AI 接口

# 开始使用

问题解答，有偿部署，技术交流；此项目的QQ群：1105459042

## 运行环境

- Windows / Linux
- Python 3.9+（建议 3.10/3.11）
- 依赖见 `requirements.txt`

## 下载

- 可直接下载 Release（含 Python 源码）
- 或 `git clone` 后运行

## 安装依赖

Windows 用户可直接运行 `登录.bat` / `启动.bat` 自动安装依赖
Linux/macOS 请手动安装：

```bash
python -m pip install -r requirements.txt
```

## 配置

首次运行前请复制示例配置：

```bash
cp config.example.json config.json
```

然后按需填写：

- `xhh.owner`：机器人所有者的小黑盒用户 ID，可用英文逗号分隔多个 ID
- `ai.model`：兼容 OpenAI Chat Completions 的模型名
- `ai.baseUrl`：兼容 OpenAI Chat Completions 的接口地址
- `ai.token`：AI 服务 token
- `tavily.apiKey`：可选，启用联网搜索时填写

`config.json`、`cookie.json`、`sql.db`、`log/`、`qrcode.png` 都是本地运行数据，已在 `.gitignore` 中忽略，请不要提交到公开仓库。

## 登录与启动

Windows：

```bat
登录.bat
启动.bat
```

其他系统：

```bash
python main.py -mode login
python main.py -mode start
```
