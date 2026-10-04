# 入行365｜职业成长向导

[![Validate](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml/badge.svg)](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml)
[![Apache 2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

结合你的现状，看懂职业变化，找到适合的方向、成长路径与资料。

职业成长不必从“给 AI 一个任务”开始。入行365帮助你先认识现状、理解选择，再找到值得深入的内容；需要实践时，也可以进入工具或专项 Skill。

`ruhang365-router` 保留现有安装与调用兼容。Codex 是一个载体，而不是唯一入口：公开核心也提供 Python CLI、JSON 输出和离线目录。

本仓开源的是可移植 Router、Skill、公开协议与离线快照；RHZL 网站、托管 Catalog 服务及其私有数据库不是本仓开源范围。无需账号、会员凭据或维护者数据库权限即可运行离线 CLI；在线目录来自 RHZL 的公开只读接口。

> 发布状态：职业成长引导与全内容目录 1.1.0 已上线。公开 Web 入口：[入行365｜职业成长向导](https://rhzl.ruhang365.cn/career/guide)。

资源导航支持读取公开目录已有的完整方法步骤、提示词、填写变量与相关资料，Web 和 Skill 使用同一来源。选择方向或补充问题后，资料查找会说明关键词依据；是否适用仍需结合资料的条件判断。目录版本保持 1.1.0，软件发行版本与目录版本分别维护。

## 能提供什么帮助

| 你的情况 | 得到的帮助 |
| --- | --- |
| 探索或转行 | 梳理已有经验，比较方向、门槛与起步资料 |
| 在岗成长 | 认识工作状态，寻找适用方法与能力补足资料 |
| 跨境入行 | 按经验和投入条件理解入口，不强行指定平台 |
| 明确需求 | 查找 Prompt、工具、案例、学习内容或专项能力 |

通用 AI 可以回答问题；本项目着重解决“从哪里开始，以及哪些资料适合我”。引导规则、内容版本和资源引用让推荐依据可检查，让社区可以持续修正内容。

理解、比较、阅读和行动都可以成为结果。允许不确定、跳过、修改和自由补充，不要求完成固定问卷或提交成果。资料不足时保留缺口，不把 AI 即时建议冒充为社区已审核知识；没有可靠适用标签的内容可以检索，但不能伪装成有依据的个性化推荐。

## 快速开始

### 1. 把链接交给 Codex 安装

在 Codex 聊天框粘贴下面这段话，无需自己下载仓库或执行终端命令：

```text
帮我安装这个 Skill：
https://github.com/ruhang365/ruhang365-router/tree/main/skills/ruhang365-router
如果已经安装，请先检查版本并保留本机修改，不要直接覆盖。
```

这不是网页上的“一键安装”按钮：Codex 需要能够访问 GitHub 和本机 Skill 目录，并会在需要权限时提示你。链接安装的是公开 main 分支中的稳定版本。

### 2. 新建任务，开始使用

安装完成后新建一个 Codex 任务，让 Skill 被重新识别，然后输入：

```text
使用 $ruhang365-router，你能为我做什么？
```

也可以直接描述现状：

```text
使用 $ruhang365-router，我以前做产品经理，想了解 AI 产品经理。
先帮我理解能力差异，再找适合我的学习和面试资料。
```

已有明确需求时不必重复欢迎和诊断。推荐专项能力不代表已经安装或实际执行。

如果已经安装并能识别 `$ruhang365-router`，直接开始使用，无需重复安装。

## 内容与权限

1.1.0 索引文章、知识与术语、文字与生图 Prompt、案例、探索教程、工具、Skill、场景与工作流、学习内容与路径、职业方向及公开日报。接入范围已经逐来源核验；收录不等于每个方向已经拥有完整课程或面试题库。

目录保存精简摘要和来源引用，正文继续在原处维护。正文接口按 ID、目录版本与哈希检查内容；来源变化可能导致暂时不可读，不保证历史正文永久可用。

- 公开且获准提供正文的资料可按需读取。
- 注册或会员内容保留原访问限制，只显示获准公开的介绍和原站入口。
- 授权不明的第三方资料只引用来源；公开可看不等于允许再分发。
- 内部内容不进入公开目录，本地开关不能绕过鉴权或服务限额。

## 隐私与可靠性

个人回答与匹配留在当前环境，不向 Catalog API 发送问题或用户画像，不读取会员 Token、Cookie 或 API Key。

服务端发布时校验公开字段；客户端复核协议、引导字段和摘要，在线失败时使用有效离线快照。未知协议或损坏数据不能覆盖有效旧快照。离线内容不代表实时规则，平台条件仍需核验时效。

```text
GET https://rhzl.ruhang365.cn/api/community/catalog
```

正文接口为 `/api/community/assets/<stable_id>`。详见 [Catalog 合同](contracts/rhzl-catalog-v1.md)。

## 社区与治理

Web 与 Skill 的目标是消费共同的审核发布版本，而不是维护两套正文：

```text
原来源 → 公开投影与审核 → 版本化 Catalog → Web / Skill / CLI
```

来源更新先形成候选，不自动等于社区认可。欢迎补充案例、修正过期资料、推荐资源和改善引导；贡献不是使用前提。代码 PR 不直接写入生产库，也不能改变原内容会员或发布状态。

参见 [贡献指南](CONTRIBUTING.md)、[维护治理](GOVERNANCE.md) 和 [安全报告](SECURITY.md)。

## 开发与验证

### 手动安装与 CLI（可选）

以下方式面向开发者和希望自行操作的用户，不是使用 Codex Skill 的前置步骤。需要 Git、Bash 与 Python 3.10 或更新版本：

```bash
git clone https://github.com/ruhang365/ruhang365-router.git
cd ruhang365-router
./scripts/install.sh
```

脚本发现已有安装会停止，不会覆盖。更新已有版本时，应先检查差异并保留可恢复副本。

只体验 CLI、不安装 Skill：

```bash
python3 skills/ruhang365-router/scripts/route_ruhang365.py --offline --format markdown
```

使用完整离线目录体验职业成长引导：

```bash
python3 skills/ruhang365-router/scripts/route_ruhang365.py \
  --guide work-growth --offline \
  --catalog skills/ruhang365-router/catalog/community-full-1.1.0.json \
  --format markdown
```

CLI 提供可检查的引导和匹配结果，多轮自然语言交互由宿主 AI 承载。

### 三个可复现的离线例子

在仓库根目录运行，无需安装 Skill 或登录账号。下列选择是演示输入，不代表对你的实际情况作判断：

```bash
# AI 产品方向
python3 skills/ruhang365-router/scripts/route_ruhang365.py --offline --guide career-change --answer route=new-role --answer new-role-focus=product --format json
# 工作成长：从现有产品工作出发
python3 skills/ruhang365-router/scripts/route_ruhang365.py --offline --guide work-growth --answer purpose=understand --answer role=product --format json
# 跨境入行：有供货基础，先了解 B2B
python3 skills/ruhang365-router/scripts/route_ruhang365.py --offline --guide cross-border --answer model=b2b --answer supply=factory --format json
```

随仓 `1.1.0` 快照中，三条命令均返回 `guidance.status=ready`、`catalogSource=offline_snapshot`，资源 ID 依次为 `r365.resource.career-ai-product`、`r365.resource.career-product-manager-ai-upgrade`、`r365.resource.platform-alibaba-com`。不带 `--answer` 可查看真实问题与选项；每次继续需保留此前答案。离线结果包含摘要、引导与来源链接，不承诺可离线读取原站全文。

真实试用任务和空白记录表见 [三项试用](docs/trial-tasks.md)；目前状态为 **NOT RUN**，上述命令检查不算用户采用。

2026-10-04 完成三个全新上下文的 **AI 模拟用户测试**，分别检查转型探索、反馈整理和企业客户供货的资料发现与理解。三个情境均观察到明确帮助，也记录了长句搜索、同名资料、受限路线与 B2B 原始流程为空的限制。该结果不是实际用户采用、岗位胜任或经营效果证明。

### 验证

```bash
./scripts/validate.sh
```

验证包含 Python 编译、单元测试、非覆盖式安装测试及环境可用时的官方 Skill 校验。模拟测试不计作真实外部用户采用。

只读检查托管目录（需要网络；不写快照）：

```bash
python3 scripts/update_catalog_snapshot.py --check
./scripts/validate.sh
```

维护者确认要更新离线分发版本时才运行不带 `--check` 的更新命令。它仅消费已发布 API，不写 RHZL 数据库；有效本地快照提供条件 ETag，304 保留原 JSON。仅网络错误及 502/503/504 最多尝试三次（含首次）；失败或下载期间目标文件被改动时保留原文件，成功更新采用同目录临时文件原子替换。不要用本地内容构建结果覆盖托管快照。

## English overview

This repository open-sources the portable Router, Skill, contracts, and offline snapshots, not the hosted RHZL website, server, or private database. Offline CLI use requires no account or maintainer database access.

Ruhang365 Career Guide is an open-source guidance and content-discovery layer for career exploration and professional growth. It combines explicit guidance rules with a versioned catalog to help users understand choices and find relevant resources without requiring a predefined task. Codex is one host; Python CLI, JSON output, and offline snapshots are also supported.

Career guidance and the full-content 1.1.0 Catalog are live. The public Web entry is [Ruhang365 Career Guide](https://rhzl.ruhang365.cn/career/guide). User queries and profiles are not sent to the Catalog API. Access restrictions, provenance, licensing, and evidence gaps remain explicit.

## 许可证

代码、脚本与 Skill 使用 [Apache 2.0](LICENSE)。原创内容许可见 [内容许可证](CONTENT_LICENSE.md)。外部资料保留逐项来源、署名与许可，本仓许可证不覆盖第三方或受限正文。
