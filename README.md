# 入行365能力路由器

[![Validate](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml/badge.svg)](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

`ruhang365-router` 是入行实验室的 Public Core / Community 内容真相源和公开能力入口。它把“我不知道 AI 能做什么”或“我该调用哪种能力”转成一个明确场景，按身份、目标、经验、约束和交付物匹配已审核的 Scenario / Workflow / Resource / Prompt，再按需检索少量公开资料。

它不是资料库镜像，也不会合并其他项目。写作、视觉等专项能力继续保留各自的独立仓库；Router 只负责诊断、发现、检索和编排。

## 能做什么

- 从模糊需求中识别 `discover`、`writing`、`visual`、`tool` 或 `knowledge` 意图。
- 从版本化 Community Catalog 匹配 Scenario、Workflow、Resource 和 Prompt；匹配逻辑不再维护硬编码 Profile 内容。
- 针对已收录的门店与创作者场景，在离线状态下给出可交付场景与 1 个推荐起点。
- 通过公开只读接口检索最多 5 条知识、Skill 或授权感知的 Prompt 结果。
- 只保留客户端白名单字段，不输出服务端未知字段或会员内容。
- 过滤与查询没有明显匹配的热门结果，不用无关推荐凑数。
- 为写作任务推荐 [`ai-writing-humanizer`](https://github.com/ruhang365/ruhang365-ai-writing-humanizer-skill)。
- 为视觉任务推荐 [`ruhang365-visual-prompt-router`](https://github.com/fzy2012/ruhang365-visual-prompt-skill)。
- 在离线或服务不可用时保留本地场景判断，不虚构远程检索结果。

## 安装

需要 macOS、Linux 或 WSL，并已安装 Git、Bash 和 Python 3.10 或更高版本。

```bash
git clone https://github.com/ruhang365/ruhang365-router.git
cd ruhang365-router
./scripts/install.sh
```

安装脚本不会覆盖已有 Skill。安装后新建一个 Codex 任务，让 Skill 元数据重新加载。

## 使用

直接在 Codex 中说：

```text
Use $ruhang365-router 我不知道 AI 能为自己的小店做什么。
请给三个真实场景，推荐一个今天可以完成的成果，并直接带我开始。
```

也可以单独运行只读客户端：

```bash
python3 skills/ruhang365-router/scripts/route_ruhang365.py \
  --query "给我的公众号文章找写作和配图能力" \
  --intent auto \
  --format markdown
```

提供结构化匹配条件时，CLI / JSON 会消费与 Codex 相同的 Catalog：

```bash
python3 skills/ruhang365-router/scripts/route_ruhang365.py \
  --query "为咖啡店做一周获客内容" \
  --identity local-business \
  --goal content-growth \
  --experience beginner \
  --constraint free-only \
  --deliverable weekly-content-kit \
  --offline
```

只运行本地路由，不访问网络：

```bash
python3 skills/ruhang365-router/scripts/route_ruhang365.py \
  --query "我不知道 AI 能做什么" \
  --offline
```

## Community 内容与发布链

正式内容位于：

```text
content/scenarios/
content/workflows/
content/resources/
content/prompts/
```

每项资产使用稳定 ID、语义版本和治理元数据。`scripts/build_catalog.py` 会校验 Schema、重复 ID、引用完整性、来源、许可证、审核状态、内部路径与常见密钥形态，然后生成确定性的 [`catalog.json`](skills/ruhang365-router/catalog/catalog.json)。生成结果没有动态时间戳，并带有内容 SHA-256，因此相同内容总是得到相同字节。

发布链只有一个方向：

```text
GitHub 审核合并的 Community 内容
  -> CI 校验与版本化 catalog
  -> RHZL / Supabase 运行时索引
  -> Codex / CLI / JSON / Web / 后续 MCP
```

任何人可以提交 PR，但只有通过维护者审核并合并的内容才是正式资产。RHZL 不反向编辑本仓；用户状态、Run、Result、Asset、Feedback、会员与 Pro 数据只留在 RHZL。

## RHZL 只读导入合同

本仓不会连接或写入数据库。以下命令只把 Catalog 投影为现有 `rhzl_scenarios`、`rhzl_knowledge_base`、`rhzl_skills` 可消费的确定性 JSON：

```bash
python3 scripts/export_rhzl_import.py > rhzl-community-import.json
```

详细字段和运行时责任见 [`contracts/rhzl-import-v1.md`](contracts/rhzl-import-v1.md)。Skill 的 `creator_ref` 必须由 RHZL 导入器解析为已有官方创建者，不能在公开 Catalog 中保存用户 UUID，也不新建第二套运行时表。

## Community 边界

公开核心永久可执行：本地意图判断、Catalog 匹配、公开资料检索、专项 Skill 路由、失败降级和交付规则都在本仓库中。Catalog 匹配当前仅覆盖已审核种子；未收录场景会返回空结果，不虚构“全职业覆盖”。

当前公开核心有意不支持会员 Token：

- 不读取或发送 API Key、Cookie、登录凭证和会员 Token。
- 不接收图片、完整文章、客户资料或私人素材。
- 不批量导出入行365资料库。
- 不自动安装专项 Skill，不执行发布、发送、购买或部署。

未来会员服务仍由 RHZL 服务端负责鉴权、配额和内容授权，不能通过本地开关绕过。

## 公开接口

默认只读基地址为 `https://rhzl.ruhang365.cn`：

- `/api/knowledge/search`
- `/api/skills/recommend`
- `/api/v1/prompt-library/search`

本地或 Preview 验证可以设置 `RUHANG365_API_BASE_URL`。覆盖地址不得包含用户名、密码、查询参数或 fragment。

## 开发与验证

```bash
./scripts/validate.sh
```

验证包括 Python 编译、单元测试、非覆盖式安装测试和可用时的 Codex 官方 Skill 校验。

修改 `content/` 后先运行：

```bash
python3 scripts/build_catalog.py --write
./scripts/validate.sh
```

贡献流程、审核标准和维护职责见 [`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`GOVERNANCE.md`](GOVERNANCE.md)。

## 许可证

本仓库代码、脚本和 Codex Skill 采用 [Apache License 2.0](LICENSE)。`content/`、Schema 文档与由其生成的 Catalog 默认采用 [CC BY 4.0](CONTENT_LICENSE.md)，每项资产仍必须声明自己的来源、许可证和署名。远程检索结果继续遵守结果中声明的来源和许可证；`reference_only` 内容不得被补全、反推或复制。
