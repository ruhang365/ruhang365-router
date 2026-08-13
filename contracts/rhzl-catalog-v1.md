# RHZL Community Catalog v1

Supabase 是 Community 内容唯一可编辑真相源。RHZL 从已发布的不可变 release 提供：

```http
GET https://rhzl.ruhang365.cn/api/community/catalog
```

Router 只保存该接口的版本化公开快照，并在运行时优先读取在线 API。它不生成数据库导入合同、不写 Supabase，也不接收用户问题、身份、约束、交付物、Cookie 或凭据。

响应合同为 `schemaVersion=1.0.0`、语义化 `catalogVersion`、公开 `items` 和对规范化 `items` 计算的 `contentDigest`。客户端必须重新计算摘要；超时、5xx、无效 JSON、未知 Schema 或摘要不匹配时，使用已随 Tag 发布的稳定快照并标记 `offline_fallback`。

快照更新只能来自 RHZL 的已发布 API。快照 PR 合并只更新离线分发版本，不触发数据库导入或反向覆盖 Supabase。
