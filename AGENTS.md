# AGENTS.md

给**任何**编码智能体（Claude Code / Codex / Cursor / Cline / Aider / DSH / 自写脚本）的入口说明。
你只需要会两件事：执行 shell 命令、读写文件。其余规则都在 `prompts/` 里。

## 你要交付什么

把一段视频或一份文件，变成一份**能教零基础读者**的讲义：一个 `site/index.html`，
正文里挂着便签，右下角有一个速答框（能用用户自己的模型回答，没配 key 时查离线题库）。

## 四个硬规则（不可违反）

1. **不许编数。** 视频里没听清、教材里没印的，写「（此处原文不清）」，不要补一个看起来合理的值。
2. **算过的要验算。** 每道例题自己解一遍，验算过程写进正文（代回去、功率平衡、KCL/KVL 复核任选）。
3. **问答库按五步写。** 定义 → 对照 → 规则 → 算式 → 一句话，见 `prompts/03-qa-bank.md`。
4. **提交前必须 `python -m lecture_forge audit .`，结果为 0 blocking 才允许 push。**

## 六个阶段（分工与产物）

```bash
python -m lecture_forge fetch <URL或本地文件> -o work   # → work/audio.*  work/video.*
python -m lecture_forge transcribe work/audio.* -o work  # → work/audio.txt/.srt/.jsonl
python -m lecture_forge slides work/video.* -o work/slides  # → work/slides/t*.png
#   ④ 写讲义：work/lecture/{lecture.md, meta.json, qa-bank.json, img/}
python -m lecture_forge build work/lecture -o site       # → site/index.html, ask.html
python -m lecture_forge audit .                          # → 六项发布前自查
python -m lecture_forge serve                            # → http://127.0.0.1:8765
```

阶段 ④ 是唯一的"创作"阶段，写法见 `prompts/02-lecture.md`；
要点表（先给用户确认）见 `prompts/01-outline.md`；配图见 `prompts/04-figures.md`。

## 讲义文件夹约定

```
work/lecture/
  lecture.md      正文（Markdown，第一个 # 标题会被取为页面标题）
  meta.json       {"title": "...", "subtitle": "...", "lang": "zh"}
  qa-bank.json    问答库（数组，字段见 schemas/qa-bank.schema.json）
  img/            图片（正文里写 ![]('img/xxx.png')）
```

便签只会挂在**小节标题（`##`）**上：条目里的 `pin` 写成 `"三、"` 这样的前缀，
`build` 时会把它挂到匹配的小节下方。

## 不要做

- 不要提交 `work/`、`site/`、`config.json`、媒体文件（`.gitignore` 已覆盖，别用 `git add -f` 破例）。
- 不要向用户索取 API key 或要求把它写进代码；key 只放在本地 `config.json`。
- 不要把本地绝对路径、手机号、真实邮箱写进仓库；`audit` 会拦，但别指望它兜底。

## 用户怎么跟你配合

一次只做一个阶段，每个阶段结束时报告：产物路径 + 自检结果 + 下一阶段的命令。
不要一口气跑完六个阶段再说话——用户在阶段 ④ 需要看要点表并确认方向。
