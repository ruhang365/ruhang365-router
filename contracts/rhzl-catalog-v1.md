# RHZL Community Catalog v1

Supabase 是 Community 内容唯一可编辑真相源。RHZL 从已发布的不可变 release 提供：

```http
GET https://rhzl.ruhang365.cn/api/community/catalog
```

Router 只保存该接口的版本化公开快照，并在运行时优先读取在线 API。它不生成数据库导入合同、不写 Supabase，也不接收用户问题、身份、约束、交付物、Cookie 或凭据。

响应支持 `schemaVersion=1.0.0` 与 `1.1.0`，包含语义化 `catalogVersion`、公开 `items` 和规范化 `items` 的 `contentDigest`。客户端必须重新计算摘要；超时、5xx、无效 JSON、未知协议或摘要不匹配时，使用有效快照并标记 `offline_fallback`。

1.1.0 增加结构化职业引导、来源身份、内容类别、访问条件和版本化正文引用；四类资产保持兼容。大型目录使用 `Content-Encoding: gzip`，Python 客户端限制响应及解压大小后重新校验摘要。正文通过 `/api/community/assets/<stable_id>?catalogVersion=<version>` 按需读取；版本不可用返回 409，正文变化且哈希不一致返回 503。注册、会员与 reference_only 内容不提供复制正文，继续使用原站入口。

快照更新只能来自 RHZL 的已发布 API。快照 PR 合并只更新离线分发版本，不触发数据库导入或反向覆盖 Supabase。Catalog 结构变化必须版本化；未知 Schema 直接触发稳定快照回退，未完成兼容验证前不得接受新合同。

## 历史生产基线

2026-08-13 当前生产版本为 Catalog `1.0.0`，digest 为 `215d7ea85d81a01dfbcc2477403b2df8b5f5b967c05d93825165bdd43decf321`，共 14 项。公共投影把 2 个非 Skill Resource 与 2 个官方 Skill 统一计入 `type=resource`，因此 API 类型统计为 4 `scenario`、4 `workflow`、4 `resource`、2 `prompt`。

Router 公开版本为 `v0.3.0`。从公开 Tag 全新安装、在线 API 匹配、强制 API 不可用时的 `offline_fallback`、摘要校验和快照幂等更新均已验证。该结论证明技术与生产闭环已完成，不代表真实用户留存、商业价值或 PMF 已验证。
