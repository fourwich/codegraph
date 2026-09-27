# CodeGraph Demo Video Pack (60s)

## 1. English voiceover (136 words)

[Segment 1]
Git blame shows who touched a line. It never explains the design decision behind it.
SHA, author, date. Still no answer to why that code exists.
CodeGraph starts from the same question. Why is this line here?

[Segment 2]
codegraph why returns a decision card for the exact line.
Content, reason, source, status, and confidence. All in one view.
codegraph graph shows the code graph at a moment in time.
Node count, live edges, and decisions, filtered by date and scope.
History stays queryable. The snapshot is honest about valid_from and valid_to.

[Segment 3]
The web view makes the same graph clickable.
Move the time slider. The layout follows the history.
Select a node. Related decisions appear on the right.
Structure, time, and decisions, joined in one queryable graph.

CodeGraph. Not just what changed. Why it was allowed to change.

## 2. 剪映剪辑指南

1. 新建草稿：1920×1080，30 fps，时长目标 60s。
2. 轨道顺序：
   - 视频轨 A：`2026-09-25 08-31-38.mp4`（问题 / git blame）→ 拖到 0:00
   - 视频轨 A：`2026-09-25 08-40-08.mp4`（why + graph）→ 接在第一段后
   - 视频轨 A：`2026-09-25 08-59-33.mp4`（Web UI）→ 接在第二段后
3. 裁剪建议（在预览里听/看命令输出出现处对齐）：
   - 第 1 段：开头剪 0–0.5s 黑/桌面，结尾留 blame 输出完整 1s，净长约 12s
   - 第 2 段：从键入 `codegraph why` 前 0.3s 起，到 `graph` 表格读完留 0.5s，净长约 22s
   - 第 3 段：从页面完全出现起，到点选节点详情稳定后 1s，净长约 15s
4. 转场：三段之间用 **叠化 0.3s** 或直接硬切；不要滑动/旋转。
5. 旁白：
   - 推荐自己录（手机耳麦即可），按上方分段念，约 2.4–2.6 词/秒
   - 或剪映「文本朗读」英文女声/男声，语速 1.0，分段粘贴
   - 旁白轨音量 −3 dB；系统声 −12 dB，保证人声清楚
6. 字幕：开「识别字幕」或手贴英文句；字号 36–40，底部安全区，白字黑描边；命令行画面可不加双语。
7. 导出：H.264，1080p，30 fps，推荐 8–12 Mbps；AAC 128–192 kbps；文件名 `codegraph-demo-60s.mp4`。

## 3. YouTube 上传文案

**Title**
CodeGraph — Not just what changed. Why it was allowed to change.

**Description**
CodeGraph turns code structure, git history, and design decisions into one queryable graph.
Demo: codegraph why · codegraph graph --at · local web view with time slider.
Source: https://github.com/fourwich/codegraph
Product site: https://fourwich.github.io/codegraph

**Tags**
codegraph, developer tools, code analysis, git blame, graph database, tree-sitter, open source, CLI

**Visibility**
Unlisted until the competition form needs a public link; then Public (or keep Unlisted and paste the link). Enable embedding if judges embed the video.
