# Community API 合同

## 在线 Catalog、离线快照与本地匹配合同

`GET /api/community/catalog` 接受 `schemaVersion=1.0.0` 与 `1.1.0`，包含 `catalogVersion`、`contentDigest` 和按类型 / ID / 版本稳定排序的公开 `items`。随 Skill 安装的 `catalog/catalog.json` 仍是 `1.0.0` 稳定离线快照。运行时会重新计算摘要，摘要不一致、未知 Schema、无效 JSON、超时或 5xx 时使用快照并标记 `offline_fallback`。

每个 item 必须有受支持且不高于顶层 Catalog 的 `schema_version`。客户端按该 item 版本验证外部 Skill 字段；provider URL 仅接受无嵌入用户名、密码的公开 HTTPS URL。任一冲突均视为无效 Catalog 并触发稳定快照降级。

在进入本地 matcher 前，loader 还验证公开 item 和各类型的最小结构：基础标识、状态、治理、适用性、完成标准、标签与匹配词，以及 Scenario / Workflow / Resource / Prompt 分别被投影或匹配所需的字段。缺失或错类型同样是无效 Catalog，不会延迟为 matcher 的运行时 KeyError。

构建离线 Catalog 时，目标 Schema 1.0 会排除较新的资产，并在投影副本中清除其引用；目标 Schema 1.1 同时保留兼容的 1.0 与 1.1 资产。该兼容投影不修改 `content/` 源文件或当前离线快照。

CLI 可传入 `--identity`、`--goal`、`--experience`、可重复的 `--constraint` 和 `--deliverable`。JSON 输出的 `route.communityMatches` 分为 `scenarios`、`workflows`、`resources`、`prompts`，并保留命中分数、理由、稳定 ID、版本、完成标准与来源；Resource 另投影唯一权利真相 `rightsStatus`。

1.1 的外部 Skill 资源还投影 `provider`、`upstreamLicense`、`commercialUse` 与 `integrationMode`。`provider.id` 必须是稳定的 `owner/repo`，`upstreamLicense` 必须是受控 SPDX 标识并与治理许可证一致；客户端会再次验证这些字段及权利/商业/集成组合，冲突即降级到稳定快照。仅 `invoke_if_installed` 或 `embedded` 且权利完整的 Skill 可进入 `route.specialists`；1.1 还必须声明 `commercialUse=allowed`。`reference_only` 只进入 `route.externalReferences`，状态固定为 `discovered_not_invoked`，并说明提供方、许可证、商业限制和来源。Router 不会路由到外部 Router 入口，也不会把链接当成交付。

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
