# Script Platform

面向内部团队的 Python 脚本管理与隔离执行平台。

## 本期范围

- 导入 ZIP 或已有脚本目录
- 校验 `manifest.yaml`、入口文件和依赖文件
- SQLite 保存脚本、版本和执行记录
- 本地目录保存包、日志和产物
- 每次任务使用独立 Docker 容器执行
- Vue 3 管理控制台

## 脚本包约定

```text
script.zip
├── manifest.yaml
├── main.py
└── requirements.txt
```

没有 `manifest.yaml` 时，平台会寻找 `main.py`，没有时使用压缩包根目录下唯一的 Python 文件作为入口。

## 启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8787
```

打开 `http://127.0.0.1:8787`。

## 安全边界

任务默认使用 `--network=none`、非特权容器、只读脚本目录、资源上限和执行超时。只有明确配置的任务才允许网络访问。平台不会读取或复制脚本包中的密钥。
