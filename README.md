# 入行365能力路由器

[![Validate](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml/badge.svg)](https://github.com/ruhang365/ruhang365-router/actions/workflows/validate.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

`ruhang365-router` 是入行实验室的公开能力入口。它把“我不知道 AI 能做什么”或“我该调用哪种能力”转成一个明确场景，检索少量公开的入行365资料，并把任务路由到独立的专项 Skill。

它不是资料库镜像，也不会合并其他项目。写作、视觉等专项能力继续保留各自的独立仓库；Router 只负责诊断、发现、检索和编排。

## 能做什么

- 从模糊需求中识别 `discover`、`writing`、`visual`、`tool` 或 `knowledge` 意图。
- 通过公开只读接口检索最多 5 条知识、Skill 或授权感知的 Prompt 结果。
- 只保留客户端白名单字段，不输出服务端未知字段或会员内容。
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

只运行本地路由，不访问网络：

```bash
python3 skills/ruhang365-router/scripts/route_ruhang365.py \
  --query "我不知道 AI 能做什么" \
  --offline
```

## Community 边界

公开核心永久可执行：本地意图判断、公开资料检索、专项 Skill 路由、失败降级和交付规则都在本仓库中。

v0.1 有意不支持会员 Token：

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

## 许可证

本仓库原创代码、Skill 和文档采用 [Apache License 2.0](LICENSE)。远程检索结果继续遵守结果中声明的来源和许可证；`reference_only` 内容不得被补全、反推或复制。
