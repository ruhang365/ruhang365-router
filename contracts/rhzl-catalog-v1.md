# RHZL Community Catalog v1

Supabase 是 Community 内容唯一可编辑真相源。RHZL 从已发布的不可变 release 提供：

```http
GET https://rhzl.ruhang365.cn/api/community/catalog
```

Router 只保存该接口的版本化公开快照，并在运行时优先读取在线 API。它不生成数据库导入合同、不写 Supabase，也不接收用户问题、身份、约束、交付物、Cookie 或凭据。

响应合同接受 `schemaVersion=1.0.0` 或 `1.1.0`、语义化 `catalogVersion`、公开 `items` 和对规范化 `items` 计算的 `contentDigest`。客户端必须重新计算摘要；超时、5xx、无效 JSON、未知 Schema 或摘要不匹配时，使用已随 Tag 发布的稳定快照并标记 `offline_fallback`。当前随 Tag 的稳定离线快照仍为 `1.0.0`，不会因 1.1 试点被静默升级。

每个 `item` 都必须声明受支持的 `schema_version`，且不得高于顶层 `schemaVersion`；客户端按 item 版本复验相应字段，而不是只信任顶层版本。所有 provider URL 都必须是无用户名、密码的公开 HTTPS 地址。

客户端在本地匹配前会拒绝缺失或错类型的公开基础字段与类型必填字段，避免把无效 Catalog 变成 matcher 的运行时错误；在线响应因此回退到稳定快照。

构建器按目标 Schema 生成独立投影：1.0 输出只保留 `schema_version<=1.0.0` 的资产，并在深拷贝中移除指向较新资产的 Scenario / Workflow / Prompt 引用；源资产与已检入快照都不被改写。1.1 输出保留兼容的 1.0 资产及已审核的 1.1 资产。

## 1.1 外部 Skill Resource

`schema_version=1.1.0` 的 `resource_kind=skill` 必须提供公开 `provider={id,name,url}`、`upstream_license`、`commercial_use` 和 `integration_mode`。`provider.id` 使用稳定的 GitHub `owner/repo` 形式；本试点的批准值为 `dontbesilent2025/dbskill`。`upstream_license` 必须是受控的 SPDX 标识并与 `governance.license.spdx` 完全一致。`governance.rights.status` 是唯一权利真相源，匹配投影必须显式返回它。

- `reference_only` 只允许 `rights.status=reference_only`；它只作为“已发现、未调用”的外部参考，不生成调用。
- `invoke_if_installed` 与 `embedded` 都只允许 `commercial_use=allowed` 且 `rights.status=full`。

外部参考链接不是 Router 的交付物。匹配后仍须由自有 Scenario / Workflow 负责给出可完成的下一步与结果边界。

快照更新只能来自 RHZL 的已发布 API。当前 1.1 试点不会修改已检入的 1.0 快照；未来 1.1 release 获授权发布后，`update_catalog_snapshot.py` 可校验并写入该发布 Catalog，随后由既有自动快照 PR 流程生成独立变更。快照 PR 合并只更新离线分发版本，不触发数据库导入或反向覆盖 Supabase。Catalog 结构变化必须版本化；未知 Schema 直接触发稳定快照回退，未完成兼容验证前不得接受新合同。

## 生产基线

2026-08-13 当前生产版本为 Catalog `1.0.0`，digest 为 `215d7ea85d81a01dfbcc2477403b2df8b5f5b967c05d93825165bdd43decf321`，共 14 项。公共投影把 2 个非 Skill Resource 与 2 个官方 Skill 统一计入 `type=resource`，因此 API 类型统计为 4 `scenario`、4 `workflow`、4 `resource`、2 `prompt`。

Router 公开版本为 `v0.3.0`。从公开 Tag 全新安装、在线 API 匹配、强制 API 不可用时的 `offline_fallback`、摘要校验和快照幂等更新均已验证。该结论证明技术与生产闭环已完成，不代表真实用户留存、商业价值或 PMF 已验证。
