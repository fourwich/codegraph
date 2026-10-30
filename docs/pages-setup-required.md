# 需要你手动改的一处设置（约 1 分钟）

## 问题

仓库的文档站 `https://fourwich.github.io/codegraph/docs/` 一直是 **404**，我在 CI 里修好了构建与组装步骤（`pages.yml` 现在构建 VitePress 并把产物放到 `_site/docs`，`path: _site`），部署记录也显示 **success**，但线上仍然是旧的。

诊断证据：

| 探测 | 结果 | 含义 |
|---|---|---|
| `/codegraph/` | 200 | 根页面在线 |
| `/codegraph/README.md` | 200 | 仓库根文件被直接发布 |
| `/codegraph/pyproject.toml` | 200 | 同上 |
| `/codegraph/docs/architecture.md` | **200** | 这是 **源码里的 markdown**，不是 VitePress 产物 |
| `/codegraph/docs/index.html` | 404 | VitePress 的入口不存在 |

结论：GitHub Pages 正在发布 **main 分支的仓库根目录**，我提交的 `_site` artifact 被完全忽略。

## 原因

仓库 **Settings → Pages → Build and deployment → Source** 大概率是 **"Deploy from a branch"**（main / root），而不是 **"GitHub Actions"**。前者会忽略 workflow 上传的 artifact。

（我无法用 API 读取这个设置：`GET /repos/.../pages` 返回 404，需要 token；也不会去读你的凭据。）

## 你需要做的

1. 打开 https://github.com/fourwich/codegraph/settings/pages
2. 在 **Build and deployment** 下，把 **Source** 从 `Deploy from a branch` 改成 **`GitHub Actions`**
3. 保存（不需要重新跑 workflow，下一次 push 就会生效）

改完后，下一次推送会重新部署，`/codegraph/docs/` 应该返回 200。

## 如果不想改设置

那也行：目前 `/codegraph/` 和 `/codegraph/docs/architecture.md` 等源码文件都能访问，评委点 Live demo 能看到落地页。只是 VitePress 的完整文档站（指南、命令参考、JSON 契约）不可达。

这种情况下建议：**把 `docs/` 下的关键文档也在仓库根放一份可读的入口**，或者干脆接受现状，因为落地页 `index.html` 本身信息是完整的。

## 一个我应该早点发现的事实

`README.md` 能通过 `https://fourwich.github.io/codegraph/README.md` 访问到，这件事本身就是"部署的是仓库根"的铁证。我先前测到 `/docs/` 返回 200 时，那可能只是 GitHub Pages 短暂的旧缓存，我没有对同一 URL 做多次一致性验证就下了结论。
