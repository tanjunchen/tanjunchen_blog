# tanjunchen.io

***【漫步远方，心荡神往】***

记录本人的日常生活内容，在成为更好的自己的旅途中！

博客地址：[https://tanjunchen.github.io/](https://tanjunchen.github.io/)

## 技术栈

- [Hugo](https://gohugo.io/)（extended 版本）静态站点生成器
- 主题：`hugo-cleanwhite`（位于 `themes/` 目录，非 submodule）
- 评论：Giscus；站点统计：不蒜子（busuanzi）；搜索：Algolia

## 环境要求

- Hugo **extended** ≥ 0.128.2（`hugo version` 输出需包含 `+extended`）

macOS 安装：

```bash
brew install hugo
```

## 本地开发

```bash
# 启动本地预览（含草稿），默认 http://localhost:1313
hugo server -D

# 生产构建，输出到 public/
hugo --gc --minify
```

## 新增文章

在 `content/post/` 下创建 `YYYY-MM-DD-slug.md`，front matter 参考现有文章：

```yaml
---
layout:     post
title:      "标题"
subtitle:   "副标题"
description: "用于 SEO 的摘要"
author:     "tanjunchen"
date:       2026-01-01
published:  true
tags:
    - AI Infra
categories:
    - TECHNOLOGY
showtoc:    true
---
```

配图放在 `static/images/<文章 slug>/` 下，正文中用绝对路径引用：

```markdown
![图片说明](/images/<文章 slug>/1.png)
```

> 图片规范：提交前请压缩图片（建议单图 < 300KB）。仓库根目录提供 `scripts/optimize-images.sh` 可批量无损压缩 `static/images` 下的 PNG/JPG。

## 部署

推送到 `main` 分支后由 `.github/workflows/deploy.yml`（GitHub Actions）自动构建并发布到 GitHub Pages。

站点以根路径部署，`config.toml` 中 `baseurl = "https://tanjunchen.github.io"`；workflow 构建时直接使用该 baseurl，不做子路径覆盖。

## 目录结构

```
content/        文章与页面（post/ 为博客文章）
static/         静态资源（images/ 为文章配图，img/ 为主题图片）
themes/         hugo-cleanwhite 主题及其自定义
config.toml     站点配置
scripts/        辅助脚本（图片压缩等）
```
