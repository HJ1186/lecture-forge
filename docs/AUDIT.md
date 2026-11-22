# AUDIT.md · 发布前自查（六组）

一条命令：

```bash
python -m lecture_forge audit .
```

输出示例：

```
auditing /path/to/lecture-forge  (37 files)

4 temp files
  [FAIL] work/audio.txt.tmp             temp/backup file
         delete it or gitignore it

3 abs paths
  [FAIL] docs/notes.md:12               windows user path
         C:\Users\<user>\work\audio.txt

4 blocking, 2 to review
```

退出码：`0` 干净；`1` 有阻塞项；`2` 只在加了 `--strict` 且有 warning 时出现。
加 `--json` 可以给 CI 或别的工具消费。

---

## 六组分别查什么

### 1. secrets（阻塞）

- 私钥块 `-----BEGIN … PRIVATE KEY-----`
- 常见 key 形态：`sk-…`、`ghp_…`、`github_pat_…`、`AKIA…`、`xox?-…`、`AIza…`
- `bearer <很长的一串>`
- `api_key / secret / token / password = "..."` 这类赋值（长度 ≥12 才报，避免误报变量名）
- 文件名本身可疑：`.env`、`credentials.json`、`id_rsa`、`.npmrc`、`.pypirc`

> 报告里 key 永远是**打码**的（只留前 4 后 4）。审计脚本自己不会吐出可用凭据。

### 2. privacy（阻塞）

- 中国大陆手机号 `1[3-9]xxxxxxxxx`
- 18 位身份证号
- 邮箱地址 —— 但放过三类白名单：`*@users.noreply.github.com`、`*@example.com`、以及截图名 `img@2x.png` 这种误报

### 3. abs paths（阻塞）

- `C:\Users\...`、`C:\...`（Windows 绝对路径）
- `/Users/...`、`/home/...`（macOS / Linux 家目录）
- `file:///...`
- `\\server\share`（UNC） <!-- audit:ignore -->

想举例子又不想被报？改成占位符：`/path/to/project`、`C:\path\to\media`。

### 4. temp files（阻塞）

`.tmp .temp .bak .old .orig .rej ~结尾 ~$开头 .log .swp .swo .pyc .DS_Store Thumbs.db`，
以及本项目自己的临时习惯：`_t_*`、`_chk*`、`_shot*`、`_dump*`、`*.dump`。

### 5. junk（阻塞 / 部分 warning）

- 提交进来的 `node_modules/`、`.venv/`、`__pycache__/`、`dist/`、`build/`、`.pytest_cache/` → 阻塞
- 单个文件 > 5 MB → warning（Git 对二进制很不友好，能换 LFS 或外链就换）

### 6. not public（warning）

- 文案里出现内部标记词（仅供内部 / 内部资料 / 机密 / 绝密 / 不可外传 / CONFIDENTIAL / internal only）→ warning <!-- audit:ignore -->
- 源素材文件（`.mp4 .mkv .m4a .mp3 .wav .pdf .docx .pptx …`）→ warning：
  **技术上能提交，法律上不一定能发布**。公开发布前确认授权。

---

## 例外：占位符与文档里的反例

规则本身要写示例，示例里难免出现 `C:\path\to\x`、`/home/<user>/`、`\\server\share`、`file:///` 这种东西（本行豁免）。 <!-- audit:ignore -->
两种豁免方式：

1. **占位符自动豁免**：路径里带 `...`、`<`、`>`，或者含 `path/to`、`path\to`、`your`、`example` 的，不算泄漏。
2. **行内标记**：在那一行加 `audit:ignore`（Markdown 里写 `<!-- audit:ignore -->`），整行跳过。
   只给"说明规则"的文档行用，不要拿它关掉真实问题。

## 修法对照

| 命中 | 怎么修 |
| --- | --- |
| 文件的路径写死了本机路径 | 改成相对路径或占位符；代码里用 `pathlib.Path(__file__).parent` |
| 真有不用的临时文件 | 删掉；以后加进 `.gitignore` |
| 误报（例如示例里的 `example.com`） | 已经白名单；其他误报请提到 issue，别用注释关掉整条规则 |
| 已经提交过 key | 轮换 key → 从历史里彻底清除（`git filter-repo`）→ 重新推送；必要时联系平台 |
| 大文件 | 外链、LFS，或者干脆不放进仓库 |

## 已经提交过、后来删掉了？`--history`

默认只扫**当前这棵树**——也就是"下一次 clone 会拿到的文件"。但 git 不是这样忘事的：一行字进了某个提交，之后删掉，**那个 blob 仍然留在历史里**，`git clone` 照样下载。所以"我在新提交里把 key 删了"并不等于"它不在仓库里了"。

```bash
python -m lecture_forge audit . --history
```

`--history` 会把 `git log -p --all` 里所有**新增行**过一遍同样的规则，命中时写成 `提交号:文件`：

```
auditing .  (43 files)  [+ history: 11 commits, 3727 added lines]

1 secrets
  [FAIL] 02fbef5:leak.py           openai/llm key (in history)
         sk-A*******************AAAA
```

怎么处理：

| 情况 | 做法 |
| --- | --- |
| 命中一个**真在用的** key | 先去平台**轮换/吊销**，再 `git filter-repo` 重写历史 + 强推；顺序反了等于没救 |
| 命中一个早就作废的 key | 仍然建议重写历史（有些扫描服务会一直报），至少轮换过的就不用慌 |
| key 一直只放在 `config.json` / `.env` | 那它从没进过 git，`--history` 也就不会命中——这是正确的用法 |
| 只是文档里写着 `sk-…` 这种形态说明 | 占位符自动豁免；确实要保留就加 `audit:ignore` |

发布前建议直接跑最严格的一档：

```bash
python -m lecture_forge audit . --history --strict
```

⚠️ `--history` 靠本地的 git 历史。**浅克隆（`--depth=1`）里它只能看到一个提交**，看起来"很干净"其实什么都没查。
CI 里要先把历史拉全：`actions/checkout` 设 `fetch-depth: 0`（`docs/ci/audit.yml` 已经这么写了）。

## 接到 CI 里

`docs/ci/audit.yml` 是现成的 CI 配置：复制到 `.github/workflows/` 就会在每次 push / PR 时跑这一条命令，失败就红。
自己也建议加成本地 pre-commit 钩子：

```bash
# .git/hooks/pre-commit
#!/bin/sh
python -m lecture_forge audit . || exit 1
```
