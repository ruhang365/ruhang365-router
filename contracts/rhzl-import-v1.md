# RHZL Community 单向导入合同 v1

## 方向与职责

输入是审核合并后生成的 `catalog.json`，输出是 `scripts/export_rhzl_import.py` 的只读 JSON。该脚本不连接 Supabase、不解析凭证、不执行写操作。

```text
Community catalog
  -> deterministic import JSON
  -> RHZL importer resolves runtime-only references
  -> existing runtime indexes
```

RHZL 导入器必须用 `source_url` 执行现有幂等 upsert，并记录形如 `github:ruhang365/ruhang365-router:<community_id>@<version>` 的 `source_uid`、Catalog 版本与内容摘要。它不能把运行时记录反向写入 GitHub。

## 现有索引映射

| Community 类型 | RHZL 现有索引 | 唯一键 / 说明 |
| --- | --- | --- |
| `scenario` | `rhzl_scenarios` | `slug`；Community ID、版本和完成标准进入 `recipe_data` |
| `workflow` | `rhzl_knowledge_base` | `source_uid`；`content_type=workflow` |
| `prompt` | `rhzl_knowledge_base` | `source_uid`；仅自有且公开的完整 Prompt 进入 `public_body` |
| 非 Skill Resource | `rhzl_knowledge_base` | 映射到现有 `knowledge_card`、`task`、`tool` 或 `use_case` |
| Skill Resource | `rhzl_skills` | `slug`；其余字段对齐现有表，`creator_ref=official:ruhang365` 必须由 RHZL 解析并替换为已有官方 `creator_id` 后才能 upsert |

不新增重复数据库表。`creator_id`、用户 UUID、Run、Result、Asset、Feedback、entitlement 和 Pro 内容不进入导出文件。

`rhzl_knowledge_base` 的 `source_repo`、`content`、`target_level`、`target_role`、`tags` 和 `status` 等历史非空字段也会显式输出；公开 Catalog 没有内部正文，因此 `internal_body=null`，不能由导入器自行补写。

## 应用门禁

正式导入器实现前至少验证：Catalog 摘要、合同版本、允许的 `content_type`、稳定 ID 冲突、官方创建者解析、事务回滚和 dry-run 差异。当前仓只交付并测试 JSON 合同，不授权生产写入。
