# QUICKSTART · 十分钟跑通

## 0. 你需要什么

- Python 3.10 以上
- 想学的一个视频（B 站/YouTube/本地文件都行）或一份文件（PDF、录音）
- 可选：一个大模型的 API key（OpenAI 兼容接口）。**没有也能用**，只是速答框只能查问答库。

## 1. 装

```bash
git clone <这个仓库的地址> lecture-forge
cd lecture-forge
python -m venv .venv
# Windows: .\.venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
cp config.example.json config.json     # 然后填上你的模型信息（可以留空先跳过）
```

只想先看看长什么样：先不配 key，直接 `python -m lecture_forge build examples/demo-lecture -o site`，再 `serve`。

## 2. 先看成品

```bash
python -m lecture_forge serve
```

打开 http://127.0.0.1:8765/ ，这就是最终形态：

- 正文是讲义；
- 每节下面有一张淡黄色的**便签**（折叠着，点开就是答案）；
- 右下角圆形「问」按钮 → **速答框**：输入关键词回车就给答案，并告诉你"去讲义第几节看"；
- `/ask.html` 是独立提问页：粘贴一段看不懂的内容 + 一个问题，回车。

> 直接双击 `site/index.html` 也能看，但那样**速答框不能调用模型**（浏览器禁止 `file://` 页面发起跨域请求），
> 只能查离线题库。想用模型就走 `serve`。

## 3. 做一个自己的讲义

```bash
# ① 拿媒体（URL 或本地文件都行；--no-video 表示只留音频）
python -m lecture_forge fetch "https://www.bilibili.com/video/BVxxxxxxxx" -o work

# ② 语音转文字（这一步最慢：GPU 约 3 倍速，CPU 约 0.3 倍速）
python -m lecture_forge transcribe work/audio.m4a -o work

# ③ 抽幻灯片帧（配图用；纯音频可以跳过）
python -m lecture_forge slides work/video.mp4 -o work/slides --min-interval 8
```

接下来 ④ 是**写讲义**，由你或你的智能体完成。把这段提示词给它：

> 读 `prompts/00-workflow.md`，然后按 `prompts/01-outline.md` 出一份要点表给我确认；
> 确认后按 `prompts/02-lecture.md` 写 `work/lecture/lecture.md`，
> 按 `prompts/03-qa-bank.md` 写 `work/lecture/qa-bank.json`，
> 按 `prompts/04-figures.md` 从 `work/slides/` 选图放进 `work/lecture/img/`。
> 数字都要自己算一遍。

```bash
# ⑤ 生成网页
python -m lecture_forge build work/lecture -o site

# ⑥ 发布前检查（非常重要：发布前必须 0 blocking）
python -m lecture_forge audit .
```

## 4. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 速答框只回"题库未命中" | `config.json` 的 `model.api_key` 还是空的，或者没走 `serve` |
| 页面打开是空白 | 用了 `file://` 打开但 JS 被浏览器拦；改用 `serve` |
| 转写全是错字 | 在 `config.json` 的 `asr.initial_prompt` 里塞这门课的专业术语，然后重跑 ② |
| 抽出来的图糊得看不清 | 源视频分辨率太低。宁可少放图，或者自己画 |
| `yt-dlp failed` | 先 `python -m pip install -U yt-dlp`；有些站点要登录，用 `--cookies-from-browser` |
| 幻灯片被裁掉一半 | 加 `--no-crop` 保留整帧再手动裁 |
