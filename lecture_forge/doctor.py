"""`python -m lecture_forge doctor` - why doesn't it start?

Every check is independent, so one missing piece never hides the rest:
它逐项报告 Python、可选依赖、ffmpeg、模型、配置、site/ 与端口，最后给一句
"下一步该做什么"。给刚 clone 下来就跑不动的人用，也适合发 issue 时贴输出。
"""

from __future__ import annotations

import importlib
import os
import shutil
import socket
import sys

from .util import load_config

OK = "  [OK]   "
MISS = "  [MISS] "
WARN = "  [WARN] "
HINT = "         "


def _line(tag: str, text: str) -> None:
    print(tag + text)


def _version(mod) -> str:
    ver = getattr(mod, "__version__", "")
    if isinstance(ver, str) and ver:
        return ver
    sub = getattr(mod, "version", None)          # e.g. yt_dlp.version
    ver = getattr(sub, "__version__", "")
    if isinstance(ver, str) and ver:
        return ver
    return ver if isinstance(sub, str) and sub else "?"


def _pkg(module: str, pip_name: str, need: str) -> bool:
    try:
        m = importlib.import_module(module)
        _line(OK, "%-18s %s" % (module, _version(m)))
        return True
    except Exception as e:
        _line(MISS, "%-18s %s" % (module, "缺失（阶段：%s）" % need))
        _line(HINT, "装它：%s -m pip install %s" % (os.path.basename(sys.executable), pip_name))
        _line(HINT, "原因：%s: %s" % (type(e).__name__, str(e)[:90]))
        return False


def _port_free(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def doctor(config_path: str | None = None, root: str = ".") -> int:
    root = os.path.abspath(root)
    problems = 0
    print("")
    print("lecture-forge 环境自检")
    print("=" * 56)

    # 1) python
    print("\n[1] Python")
    _line(OK if sys.version_info >= (3, 9) else MISS, "%s  (%s)" % (sys.version.split()[0], sys.executable))
    if sys.version_info < (3, 9):
        problems += 1
        _line(HINT, "需要 Python 3.9 以上；装新版后重建 venv：python -m venv .venv")

    # 2) 依赖
    print("\n[2] 依赖包")
    ok_md = _pkg("markdown", "markdown", "build / serve / audit（必需）")
    if not ok_md:
        problems += 1
    _pkg("yt_dlp", "yt-dlp", "fetch（只有抓 URL 时才需要）")
    _pkg("faster_whisper", "faster-whisper", "transcribe")
    _pkg("ctranslate2", "ctranslate2", "transcribe（faster-whisper 的内核）")
    _pkg("av", "av", "slides / transcribe 解码")
    _pkg("PIL", "pillow", "slides")

    # 3) 外部工具
    print("\n[3] 外部命令")
    for name in ("ffmpeg", "ffprobe"):
        p = shutil.which(name)
        _line(OK if p else WARN, "%-8s %s" % (name, p or "没找到（yt-dlp 合并/转封装时需要）"))
        if not p:
            _line(HINT, "Windows: winget install Gyan.FFmpeg.Essentials   （装完要开新终端）")

    # 4) 配置
    print("\n[4] 配置")
    cfg_path = config_path or os.path.join(root, "config.json")
    if os.path.isfile(cfg_path):
        _line(OK, "config.json  %s" % cfg_path)
    else:
        _line(WARN, "没有 config.json —— 会全部用默认值（速答框只能查离线题库）")
        _line(HINT, "从模板复制一份：copy config.example.json config.json")
    cfg = load_config(cfg_path if os.path.isfile(cfg_path) else None)
    key = ((cfg.get("model") or {}).get("api_key") or "").strip()
    if key:
        _line(OK, "model.api_key 已填（长度 %d，不显示内容）" % len(key))
    else:
        _line(WARN, "model.api_key 为空 —— 速答框将使用离线问答库")
    _line(OK, "model         %s  @ %s" % ((cfg.get("model") or {}).get("model"),
                                          (cfg.get("model") or {}).get("base_url")))
    asr = cfg.get("asr") or {}
    _line(OK, "asr.model     %s  (%s/%s)" % (asr.get("model"), asr.get("device"), asr.get("compute_type")))

    # 5) 模型缓存
    print("\n[5] 语音模型")
    name = str(asr.get("model") or "large-v3")
    if os.path.isdir(name):
        _line(OK, "本地模型目录存在：%s" % name)
    else:
        cache = asr.get("download_root") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
        hit = os.path.isdir(os.path.join(cache, "models--Systran--faster-whisper-%s" % name))
        if hit:
            _line(OK, "已在本地缓存：%s\\models--Systran--faster-whisper-%s" % (cache, name))
        else:
            _line(WARN, "没有找到 %r 的本地副本，第一次 transcribe 会联网下载" % name)
            _line(HINT, "国内常卡住：把 asr.download_root 指向已有缓存，或 asr.model 直接写本地目录")

    # 6) 站点与端口
    print("\n[6] 站点与服务")
    site = os.path.join(root, str((cfg.get("site_dir") or "site")))
    if os.path.isfile(os.path.join(site, "index.html")):
        _line(OK, "site/index.html 已构建")
    else:
        _line(WARN, "还没有 %s/index.html" % (cfg.get("site_dir") or "site"))
        _line(HINT, "先构建一次：python -m lecture_forge build examples/demo-lecture -o site")
    host, port = cfg.get("host", "127.0.0.1"), int(cfg.get("port", 8765))
    if _port_free(host, port):
        _line(OK, "端口 %s:%d 空闲" % (host, port))
    else:
        _line(WARN, "端口 %s:%d 被占用（服务已经在跑？或换 config.json 里的 port）" % (host, port))

    # 7) git 仓库卫生（可选）
    print("\n[7] 发布前自查提示")
    _line(OK if os.path.isfile(os.path.join(root, ".gitignore")) else WARN,
          ".gitignore %s" % ("存在" if os.path.isfile(os.path.join(root, ".gitignore")) else "缺失，config.json 可能被提交"))
    _line(HINT, "真的要发布前，跑：python -m lecture_forge audit .")

    print("\n" + "=" * 56)
    if problems:
        print("结果：有 %d 个必需项没满足（见上面 [MISS]）。修完再启动。" % problems)
        return 1
    print("结果：必需项齐全。启动命令：python -m lecture_forge serve")
    print("      或者直接运行仓库根目录的 start.bat（Windows）。")
    return 0
