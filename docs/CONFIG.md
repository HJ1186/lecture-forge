# CONFIG.md · 配置说明

所有可配置项都在 `config.json`（复制 `config.example.json` 得到）。
**`config.json` 在 `.gitignore` 里，永远不会被提交。**

> 改完**不用重启服务**：`serve` 每次收到请求都会看一眼 `config.json` 的修改时间，
> 变了就重新读（控制台会打一行 `[config] config.json changed - reloaded`）。
> 填好 `model.api_key` 之后切回网页或按 F5，右上角的标签就从「助手在线 · 题库」变成「模型在线」。

```jsonc
{
  "host": "127.0.0.1",          // 只在本机监听；想让局域网别人访问改 "0.0.0.0"
  "port": 8765,
  "site_dir": "site",           // 网页产物目录
  "model": {
    "api_key": "",              // ← 填这里。留空 = 只查离线问答库
    "base_url": "https://api.deepseek.com/v1",   // 任何 OpenAI 兼容接口
    "model": "deepseek-chat",
    "temperature": 0.3,         // 讲知识点，低一点更稳
    "max_tokens": 900
  },
  "asr": {
    "model": "large-v3",        // tiny/base/small/medium/large-v3
    "device": "auto",           // auto → 先试 cuda，失败回 cpu
    "compute_type": "auto",     // cuda 用 float16，cpu 用 int8
    "language": "zh",            // 留 null 让模型自己判断
    "beam_size": 5,
    "initial_prompt": "..."      // 关键：把专业术语塞进来，能显著减少同音错字
  }
}
```

## 常见模型的填法

| 服务 | base_url | model |
| --- | --- | --- |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-air` |
| 月之暗面 | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 本地 ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` |

只认 **OpenAI 兼容**（`POST {base_url}/chat/completions`）。其他协议的模型套一个兼容网关即可。

## 国内网络：别每次都去 huggingface 下模型

模型默认从 huggingface.co 下载，国内经常卡住。三种解法，任选一种：

```jsonc
"asr": {
  // 1) 指定一个本地模型目录，完全离线
  "model": "D:/models/faster-whisper-large-v3",
  // 2) 或者复用你之前下载过的缓存目录
  "download_root": "D:/models",
  // 3) 或者干脆禁止联网查找（缺模型时直接报错，便于定位）
  "local_files_only": true
}
```

`model` 也可以直接写成 snapshot 目录，
例如 `.../.models/models--Systran--faster-whisper-large-v3/snapshots/<hash>`。
实测组合：large-v3 + cuda/float16，25 秒音频 11.8 秒出结果。

## `initial_prompt` 为什么重要

中文技术课里，同音词是转写错误的主要来源。实测：把"节点/支路/回路/网孔"和这门课的人名、
缩写写进 `asr.initial_prompt` 之后，术语错字能少一大半。建议写 1–3 句，不要长段落。

## 站点级配置（写在 `meta.json` 里）

| 字段 | 作用 |
| --- | --- |
| `title` / `subtitle` | 页面标题与说明块 |
| `lang` | `zh` / `en` |
| `api` | 服务端地址。留空 = 与页面同源（推荐）；若把页面挂到别的静态服务器，填 `http://127.0.0.1:8765` |
| `disclaimer` | 版权/用途声明，显示在页面顶部 |

## 端口被占用怎么办

```bash
# 换端口
python - <<'PY'
import json; p="config.json"; c=json.load(open(p,encoding="utf-8")); c["port"]=8766
json.dump(c,open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
PY
python -m lecture_forge serve
```

## 我不想让它联网

除了 ① `fetch`（要下载）和 ④⑤ 的模型调用，其他阶段全部离线。
把 `model.api_key` 留空，速答框只查 `qa-bank.json`，整个工具就完全离线可用。
