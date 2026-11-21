# 00 · 总流程（任何智能体都按这个跑）

你是"把视频/文件变成能问的讲义"的执行者。整条流水线有 6 个阶段，**每个阶段都能单独跑、单独检查**，
不要一口气全做完再说结果。

```
① fetch   ── 拿媒体（视频/音频/本地文件）
② transcribe ── 出带时间戳的文字稿
③ slides  ── 从视频里抠出幻灯片帧（讲义配图）
④ 写讲义  ── 你（或任何模型）根据文字稿+帧写 lecture.md / meta.json / qa-bank.json
⑤ build   ── 生成网页（讲义 + 速答框 + 独立提问页）
⑥ audit   ── 发布前安全检查
```

## 命令

```bash
python -m lecture_forge fetch "<URL 或本地文件>" -o work
python -m lecture_forge transcribe work/audio.m4a -o work
python -m lecture_forge slides work/video.mp4 -o work/slides --min-interval 8
python -m lecture_forge build work/lecture -o site
python -m lecture_forge serve            # http://127.0.0.1:8765/
python -m lecture_forge audit .          # 发布前必须 0 blocking
```

## 目录约定

```
work/
  audio.m4a          ① 的产物
  video.mp4          ① 的产物（可无）
  audio.txt/.srt/.jsonl  ② 的产物（每行带 [mm:ss -> mm:ss]）
  slides/t00120.png  ③ 的产物
  lecture/           ← ④ 的产物，你要写的就是这个文件夹
    lecture.md
    meta.json
    qa-bank.json
    img/*.png
site/                ⑤ 的产物（index.html + ask.html + img/）
config.json          你的模型 key（**永不提交**）
```

## 每个阶段的验收标准

| 阶段 | 通过条件 |
| --- | --- |
| ① fetch | `work/audio.*` 存在且能播放；视频 ≤720p |
| ② transcribe | `.txt` 至少 20 行/分钟量级；随机抽查 10 句，术语错字少于 2 处（多了就改 `asr.initial_prompt` 后重跑） |
| ③ slides | 帧数在"分钟数 × 0.5 ～ × 1"之间；每张能看清标题 |
| ④ lecture | 见 `01/02/03/04`；**自己先按讲义做一遍练习并算出答案**，答案与讲义一致 |
| ⑤ build | `site/index.html` 打开后图能显示、速答框能开、便签在对应章节下 |
| ⑥ audit | `0 blocking`；warning 逐条说明理由 |

## 三条硬规则

1. **不懂就说不懂。** 文字稿听不清、帧看不清的地方写"（此处原文不清）"，不要编造公式或数据。
2. **凡是算出来的数，必须验算。** 方程要独立解一遍（代入回原式）；答案与讲义不一致就改讲义，不是改答案。
3. **写完讲义要降级复习。** 用自己的话把每一节压成 2–3 句，检查有没有"看起来对但没讲清为什么"的地方。

## 给用户的三样东西

- `site/`（双击 `index.html` 就能看，速答框在右下角）
- `work/lecture/lecture.md`（原文，方便改）
- 一句话说明：哪里是原文、哪里是推断、哪些地方没听清
