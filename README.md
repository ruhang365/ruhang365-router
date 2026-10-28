# 入行365｜职业成长向导

[![Validate](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml/badge.svg)](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml)
[![Apache 2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

结合你的现状，看懂职业变化，找到适合的方向、成长路径与资料。

职业成长不必从“给 AI 一个任务”开始。入行365帮助你先认识现状、理解选择，再找到值得深入的内容；需要实践时，也可以进入工具或专项 Skill。

`ruhang365-router` 保留现有安装与调用兼容。Codex 是一个载体，而不是唯一入口：公开核心也提供 Python CLI、JSON 输出和离线目录。

本仓开源的是可移植 Router、Skill、公开协议与离线快照；RHZL 网站、托管 Catalog 服务及其私有数据库不是本仓开源范围。无需账号、会员凭据或维护者数据库权限即可运行离线 CLI；在线目录来自 RHZL 的公开只读接口。

> 本次分发：随仓 Catalog `1.2.24`、Schema `1.1.0`、11,682 条索引；新增六条在岗与新岗位练习，每条有材料、虚构示例与检查标准。软件标签以 [Releases](https://github.com/ruhang365/ruhang365-router/releases) 为准，在线目录版本以实际响应为准。快照文件名 `community-full-1.1.0.json` 是兼容保留名，不是当前目录版本。公开 Web 入口：[入行365｜职业成长向导](https://rhzl.ruhang365.cn/career/guide)。流程验收不等于真人采用或职业收益。

资源导航支持读取公开目录已有的完整方法步骤、提示词、填写变量与相关资料，Web 和 Skill 使用同一来源。选择方向或补充问题后，资料查找会说明关键词依据；是否适用仍需结合资料的条件判断。软件发行、目录与协议分别版本化；在线内容可能更新，实际运行以输出中的版本和来源为准。

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

这不是网页上的“一键安装”按钮：Codex 需要能够访问 GitHub 和本机 Skill 目录，并会在需要权限时提示你。链接跟随公开 main，不等于固定发行包。试用时记录安装的提交 SHA，操作与边界见 [试用材料](docs/trial-tasks.md)。安装不需要购买本项目会员，但宿主 Codex 自身的账号、可用性及用量条件仍适用。

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

公开目录索引文章、知识与术语、文字与生图 Prompt、案例、探索教程、工具、Skill、场景与工作流、学习内容与路径、职业方向及公开日报。接入范围已经逐来源核验；收录不等于每个方向已经拥有完整课程或面试题库，也不代表索引条目都是可再分发的全文。

目录保存精简摘要和来源引用，正文继续在原处维护。正文接口按 ID、目录版本与哈希检查内容；来源变化可能导致暂时不可读，不保证历史正文永久可用。

- 公开且获准提供正文的资料可按需读取。
- 注册或会员内容保留原访问限制，只显示获准公开的介绍和原站入口。
- 授权不明的第三方资料只引用来源；公开可看不等于允许再分发。
- 内部内容不进入公开目录，本地开关不能绕过鉴权或服务限额。

## 隐私与可靠性

Router CLI 不向 Catalog API 发送问题或用户画像，不读取会员 Token、Cookie 或 API Key。宿主 AI 承载的对话仍受宿主自身的数据处理规则约束，不能把 CLI 的本地匹配理解为整个对话完全离线。

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

在本次核对的随仓 Catalog `1.2.24` 中，三条命令的预期结果为 `guidance.status=ready`、`catalogSource=offline_snapshot`，资源 ID 依次为 `r365.resource.career-ai-product`、`r365.resource.career-product-manager-ai-upgrade`、`r365.resource.platform-alibaba-com`。不带 `--answer` 可查看真实问题与选项；每次继续需保留此前答案。离线结果包含摘要、引导与来源链接，不承诺可离线读取原站全文。

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

## 可核验的维护案例

以下是已发生的维护工作，不是用户证言。2026-10-24 重新读取三个 PR 的合并状态及对应运行回执。维护中使用 Codex 协助调查、实现与测试；公开链接验证的是具体变更和检查结果，不独立证明 AI 贡献比例、节省工时或外部采用。

### 1. 目录同步失败时保护已有离线内容

- **问题与影响：** 网络超时会中断目录同步；更新器还需避免无效响应、并发写入或中途变更损坏可用快照。
- **已完成：** [PR #10](https://github.com/ruhang365/ruhang365-router/pull/10) 于 2026-10-04 合并，加入 ETag 条件请求、只读检查、有限瞬时错误重试、校验后原子替换和协作写锁。权限、协议、摘要错误与 429 不盲目重试。
- **可核验证据：** [修复后自然定时运行](https://github.com/ruhang365/ruhang365-router/actions/runs/37193163730) 的事件为 schedule，源码为该合并提交，结果 success；PR 记录并发、损坏数据、304 和只读不改文件的测试。
- **边界与持续需求：** 单次恢复不是长期稳定性证明；协作锁不能防任意外部编辑，Windows 实机锁未验证。后续仍需核对协议变更、失败分类及真实定时回执。

### 2. 补回公开资源已有的步骤和模板

- **问题与影响：** 旧 Skill 读取 Workflow / Prompt 时遗漏目录已有的步骤、模板和变量，用户无法从该入口完整理解已有方法。
- **已完成：** [PR #11](https://github.com/ruhang365/ruhang365-router/pull/11) 于 2026-10-04 合并，并进入 v0.6.0；返回获准公开的 nodes、template、variables 和一层关联资料，在线正文继续检查身份、版本及哈希，保留受限内容边界。
- **可核验证据：** [合并主线 Validate](https://github.com/ruhang365/ruhang365-router/actions/runs/37204227042) 成功。PR 当时报告 75 项本地测试中 73 通过、2 项外部候选检查跳过；这不是今天重跑的数量。
- **边界与持续需求：** 读到完整结构不等于用户完成实际任务或获得帮助；后续目录变更仍需检查字段兼容、正文校验和访问限制。

### 3. 四个职业方向的跨端证据一致性

- **问题与影响：** Skill 离线内容需要同步 Web 已有的职业证据、核对日期与限制，避免两端对同一方向给出不同依据。
- **已完成：** [PR #13](https://github.com/ruhang365/ruhang365-router/pull/13) 于 2026-10-22 合并；更新四个方向的证据与快照，并补充一致性检查，保持条目 ID 和访问等级不变。
- **可核验证据：** [合并主线 Validate](https://github.com/ruhang365/ruhang365-router/actions/runs/39815774747) 成功。PR 记录本地 76 项全部通过；云端有 3 项跨仓检查跳过且未安装官方 Skill 校验器，不能把云端成功视为跨仓全量覆盖。2026-10-24 在线目录与本地快照均报告 1.2.23、11,658 条及相同摘要。
- **边界与持续需求：** PR 中“待激活”是当时状态，不是当前目录状态；同步不等于重新核验历史招聘岗位仍在招。每次相关内容变化仍需核对版本、来源日期和两端一致性。

这些案例支持“存在真实维护工作”，不证明已部署 API 自动化、获得资助或产生可量化节时收益。真实使用与反馈另见 [试用记录](docs/trial-tasks.md)。

## English overview

This repository open-sources the portable Router, Skill, contracts, and offline snapshots, not the hosted RHZL website, server, or private database. Offline CLI use requires no account or maintainer database access.

Ruhang365 Career Guide is an open-source guidance and content-discovery layer for career exploration and professional growth. It combines explicit guidance rules with a versioned catalog to help users understand choices and find relevant resources without requiring a predefined task. Codex is one host; Python CLI, JSON output, and offline snapshots are also supported.

For an independent start, install the public Skill above or run the offline Python CLI without a project account. Codex host access and usage conditions still apply. Users can explore a career direction, understand a change in their current role, or find relevant methods and learning resources. Understanding a choice is a valid outcome; completing a fixed exercise is not required.

This distribution bundles Catalog 1.2.24, schema 1.1.0 and 11,682 index entries, including six practical paths with input templates, clearly fictional examples and review criteria. Check Releases for tagged software and runtime output for the online catalog version. Entries are not users or independently reviewed recommendations. The legacy snapshot filename is retained for compatibility. User queries and profiles are not sent to the Catalog API; this does not make claims about the host AI's data handling.

Maintainer work includes [safe snapshot synchronization](https://github.com/ruhang365/ruhang365-router/pull/10), [complete public resource reading](https://github.com/ruhang365/ruhang365-router/pull/11), and [cross-client career-evidence consistency](https://github.com/ruhang365/ruhang365-router/pull/13). Continued support would help maintain these compatibility, regression-review and release-check workflows. These are real maintenance examples, not a deployed API automation or measured cost-saving claim. Independent human trials remain [NOT RUN](docs/trial-tasks.md); AI simulations do not establish adoption.

## 许可证

代码、脚本与 Skill 使用 [Apache 2.0](LICENSE)。原创内容许可见 [内容许可证](CONTENT_LICENSE.md)。外部资料保留逐项来源、署名与许可，本仓许可证不覆盖第三方或受限正文。
