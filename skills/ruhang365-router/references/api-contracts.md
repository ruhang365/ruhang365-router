# Community API 合同

## 在线 Catalog、离线快照与本地匹配合同

`GET /api/community/catalog` 使用 `schemaVersion=1.0.0`，包含 `catalogVersion`、`contentDigest` 和按类型 / ID / 版本稳定排序的公开 `items`。随 Skill 安装的 `catalog/catalog.json` 是相同合同的稳定离线快照。运行时会重新计算摘要，摘要不一致、未知 Schema、无效 JSON、超时或 5xx 时使用快照并标记 `offline_fallback`。

CLI 可传入 `--identity`、`--goal`、`--experience`、可重复的 `--constraint` 和 `--deliverable`。JSON 输出的 `route.communityMatches` 分为 `scenarios`、`workflows`、`resources`、`prompts`，并保留命中分数、理由、稳定 ID、版本、完成标准与来源。它是 Codex 之外的首个跨载体合同证明。

Catalog 由 Supabase 当前不可变 release 生成，不包含用户状态或授权信息。完整 Schema 位于仓库根目录 `schemas/`。

## RHZL 公开只读接口

默认基地址：`https://rhzl.ruhang365.cn`

可通过 `RUHANG365_API_BASE_URL` 指向本地或 Preview 环境。覆盖地址必须是无内嵌凭证的 HTTP(S) URL。

接口不接受查询参数，不接收用户问题或 Profile。客户端只在本地使用 `identity`、`goal`、`experience`、`constraints` 和 `deliverable` 进行匹配。

## 共同约束

- 请求头只包含 `Accept` 和公开的 `User-Agent`；当前公开核心不发送 `Authorization`、Cookie 或模型密钥。
- 请求 URL 固定为 `/api/community/catalog`，无查询参数。
- 输出顶层记录 `remoteModelCalled=false`、`writePerformed=false`、`credentialsAccepted=false`。
- 公共投影通过后执行本地相关性匹配；没有明显匹配时返回空结果，不用热门但无关的结果填充。
- 远程错误转换为 `offline_fallback`，不打印响应正文、堆栈、请求头或环境变量。
