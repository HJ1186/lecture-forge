# AGENT.md · 让任何智能体接管

这个项目刻意做成"**命令行 + 提示词 + 文件约定**"，不绑定任何一家智能体。
Claude Code、Cursor、Codex、Cline、Aider、DSH、自己写的脚本——都能跑，
因为它们要做的只有两件事：**执行 shell 命令**、**读写文件**。

## 一、把这三样东西丢给它

1. `prompts/00-workflow.md`（总流程与验收标准）
2. `prompts/01~04-*.md`（要点、正文、问答库、配图的写法）
3. 一句委托：

> 目标：把 `<视频地址或文件>` 变成一份能教零基础读者的讲义，并带可用的速答框。
> 步骤按 `prompts/00-workflow.md` 走；每个阶段结束时把产物路径和自检结果报给我，不要一口气全做完。
> 讲义写完要自己把例题算一遍并在正文里给验算。

## 二、智能体需要遵守的契约

| 阶段 | 它要做的事 | 产物 |
| --- | --- | --- |
| ① fetch | `python -m lecture_forge fetch <src> -o work` | `work/audio.*`、`work/video.*` |
| ② transcribe | 转写；若术语错字多，改 `asr.initial_prompt` 重跑 | `work/audio.txt/.srt/.jsonl` |
| ③ slides | 抽帧；必要时用固定坐标手工裁 | `work/slides/*.png` |
| ④ write | 写 `lecture.md` / `meta.json` / `qa-bank.json` / `img/` | `work/lecture/` |
| ⑤ build | `python -m lecture_forge build work/lecture -o site` | `site/` |
| ⑥ audit | `python -m lecture_forge audit .`，修到 0 blocking | 干净的仓库 |

四条硬约束（写进任何智能体的系统提示里都成立）：

1. **不许编数**。听不清就写"（此处原文不清）"。
2. **算过的数要验算**，验算过程写进讲义。
3. **问答库按五步写**（定义 → 对照 → 规则 → 算式 → 一句话），见 `prompts/03-qa-bank.md`。
4. **提交前运行 audit**，它失败就不许 push。

## 三、给不同工具的最小接入方式

### 有 shell 的编码智能体（Claude Code / Cursor / Codex / DSH / Cline）

直接把仓库根目录交给它，然后：

```
请读 AGENTS.md（或 prompts/00-workflow.md），按流程执行；
每一步把命令和输出摘要贴出来给我看。
```

### 只有"聊天窗口"的模型（网页版 ChatGPT / Claude / 通义…）

它不能跑命令，那就把**素材**喂给它，让它只做 ④：

```
这是一段课程的文字稿（带时间戳）和 12 张幻灯片帧的文字描述。
请按下面的规则写讲义：<粘贴 prompts/02-lecture.md>
再按这个规则写问答库：<粘贴 prompts/03-qa-bank.md>
输出两个代码块：lecture.md 和 qa-bank.json。
```

拿到结果后，本地跑 ⑤ `build` 即可。

### 完全自动化的脚本

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "lecture_forge", "fetch", url, "-o", "work"], check=True)
subprocess.run([sys.executable, "-m", "lecture_forge", "transcribe", "work/audio.m4a", "-o", "work"], check=True)
# ④ 调你自己的模型写 work/lecture/*
subprocess.run([sys.executable, "-m", "lecture_forge", "build", "work/lecture", "-o", "site"], check=True)
subprocess.run([sys.executable, "-m", "lecture_forge", "audit", "."], check=True)
```

## 四、质量闸门（智能体自查清单）

写完后逐条自问，任一为"否"就回去改：

- [ ] 读者完全没学过，也能顺着读完不卡住吗？
- [ ] 每个公式都能在正文里找到推导吗？
- [ ] 例题的数字我算过，并且用另一种方式验算过吗？
- [ ] 问答库 30 条以上吗？每条都是五步格式吗？
- [ ] 每张图都对应"需要想象"的那一处吗？图糊吗？
- [ ] `audit` 是 0 blocking 吗？
