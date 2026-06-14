@echo off
cd /d %~dp0
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt
python main.py -mode start
pause