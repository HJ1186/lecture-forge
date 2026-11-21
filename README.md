# lecture-forge

**把视频或文件，变成一份"能问"的讲义。**

扒视频 / 读文件 → 提炼要点 → 写成讲透的讲义 → 讲义里内置一个速答框（调用**你自己的**大模型，key 只留在这台机器上）。

不绑定任何智能体：Claude Code、Cursor、Codex、Cline、DSH，或者只有网页版模型，都能用——因为它只是
**几条命令行 + 一组提示词 + 一个固定的文件夹约定**。

```
视频 / 文件 ──► fetch ──► transcribe ──► slides ──► [你/智能体写讲义] ──► build ──► serve ──► audit
                                                     lecture.md          网页 + 速答框      发布前自查
                                                     qa-bank.json
```

## 它解决什么问题

网课、讲座、会议录像的痛点是同一个：**六十分钟里真正有用的可能只有十分钟，但那十分钟散落在各处**，
而且你不能向视频提问。

这个工具把这段材料变成：

- 一份**按"能不能听懂"排序**的讲义（不是把字幕整理成条目，是先给问题、再给定义、再推导、再例题、再验算）；
- 一份**问答库**，30–45 个"这里读者一定会卡住"的问题，答案按五步写；
- 一个**速答框**：读到哪里不懂，问一句，答完就压缩上下文，不攒历史；
- 一套**发布前自查**：密码/token、个人隐私、本地绝对路径、临时文件、测试垃圾、不宜公开内容。

示例（本仓库自带，可删除）：`examples/demo-lecture/` —— 讲"为什么 0.1+0.2≠0.3"的十页讲义。
示例构建好后在 `site/`，`python -m lecture_forge serve` 就能看。

## 快速开始

```bash
git clone <这个仓库的地址> && cd lecture-forge
python -m venv .venv && .\.venv\Scripts\activate     # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
cp config.example.json config.json                    # 填你自己的模型 key（可留空）

python -m lecture_forge serve                         # http://127.0.0.1:8765/
```

Windows 用户也可以直接双击 `start.bat`（或 `./start.ps1`）。

详细步骤见 [`docs/QUICKSTART.md`](docs/QUICKSTART.md)。

## 命令

| 命令 | 作用 |
| --- | --- |
| `python -m lecture_forge fetch <URL或文件> -o work` | 下载音频 + 低清视频（本地文件则直接复制） |
| `python -m lecture_forge transcribe work/audio.m4a -o work` | 语音转文字，带时间戳（.txt/.srt/.jsonl） |
| `python -m lecture_forge slides work/video.mp4 -o work/slides` | 按画面变化抽幻灯片帧，自动裁边放大 |
| `python -m lecture_forge build work/lecture -o site` | 讲义 + 便签 + 速答框 → 静态网页 |
| `python -m lecture_forge serve` | 起本地服务（页面 + `/ask` 模型接口） |
| `python -m lecture_forge audit .` | 发布前六项安全检查 |

## 讲义长什么样

- 一上来先给"一个算不出来的问题"，制造需求；不给定义先行。
- 每个公式都在正文里推一遍，并且**每一步写清方向与正负**。
- 例题参数具体、步骤完整，最后**用另一条路验算**（KCL / 功率平衡 / 量纲）。
- 每张图放在它解释的那句话下面，图注写 `▲ 视频 12:50：…` 或 `▲ 自绘：…`。
- 每节末尾一句话小结；文末自测题，答案折叠在 `<details>` 里。

## 速答框怎么工作

页面 → `http://127.0.0.1:8765/ask` → 你的模型（OpenAI 兼容）。

- **不带 key 也能用**：退回离线问答库检索，照样能答"互电阻为什么是负的"这类问题。
- **key 不进 HTML**：页面里没有 key，所以你把这个 HTML 发给别人是安全的。
- **只答这一问**：每次提问先清空上次结果，不累积对话历史。
- **知道你在哪**：点「📄 看我在哪」，它把你正在读的那一节（≤2200 字）作为上下文一起发过去。
- **答案格式固定**：定义 → 对照 → 规则 → 算式/步骤 → 一句话。可以在 `prompts/qa-system.md` 里改。

## 目录

```
lecture_forge/        代码：fetch / transcribe / extract_slides / build_site / serve / audit / cli
templates/            页面模板：lecture.tpl.html、ask.tpl.html、app.js、site.css（全部内联，无 CDN）
prompts/              提示词：00 总流程、01 要点、02 正文、03 问答库、04 配图、qa-system
schemas/              qa-bank.json / meta.json 的 JSON Schema
examples/demo-lecture 示例讲义（可删）
site/                 示例构建结果（可删；重新 build 会覆盖）
docs/                 QUICKSTART / AGENT / CONFIG / SECURITY / AUDIT
```

## 用别的智能体跑

把 `prompts/00-workflow.md` 和一句委托交给它即可：

> 读 `prompts/00-workflow.md`，按流程把 `<视频>` 变成讲义；每个阶段报一次产物和自检结果；
> 例题要自己算一遍并写验算；最后跑 `audit` 到 0 blocking。

只有聊天窗口的模型也能用：让它只做第 ④ 步（写 `lecture.md` 和 `qa-bank.json`），你本地跑 build。
细节见 [`docs/AGENT.md`](docs/AGENT.md)。

## 发布前自查

```bash
python -m lecture_forge audit .
# 0 blocking, 0 to review  ->  可以 push
```

六组检查与其修法见 [`docs/AUDIT.md`](docs/AUDIT.md)。CI 里也挂了同一条命令
（`docs/ci/audit.yml`；复制到 `.github/workflows/` 就会在每次 push 时自动跑，需要带 `workflow` 权限的 token 推一次）。

## 限制（先说清楚）

- **转写质量**取决于音质与领域词表；`asr.initial_prompt` 是唯一有效的手动干预手段。
- **抽帧**假设"屏幕录制的课、一分钟一页幻灯片"。手写实拍课会抽到大量无用手写帧。
- **讲义质量靠模型**。本工具保证的是流程与验收标准，不保证任何模型一定能写出好讲义；
  例题必须自己算一遍——`prompts/00-workflow.md` 已经把这条写进硬规则。
- **速答框不是知识库**。它只答这一份讲义范围内的东西；`file://` 直开时只能查离线题库。
- 只支持 OpenAI 兼容接口。

## 版权

工具本身是 MIT。**你用它生成的讲义属于你**，但素材（课程视频、教材扫描页）的版权不在你手上时，
不要公开发布——`audit` 会把 `.pdf/.mp4` 这类源素材标成 warning，就是在提醒这件事。

## License

[MIT](LICENSE)
