# Community 治理

## 权威与角色

`ruhang365/ruhang365-router` 是公开、跨载体结构化资产的唯一内容真相源。Contributor 提交候选 PR；Reviewer 核验 Schema、来源、许可证、可执行性和边界；Maintainer 决定合并、版本升级、失效或归档。正式资产必须至少有一名明确 Maintainer。

GitHub 合并记录是审核凭证。CI 通过只证明自动合同成立，不代替维护者审核；PR 未合并前不能被描述为正式 Community 内容。

## 变更级别

- Patch：文字澄清、标签或来源补充，不改变适用范围、步骤与结果。
- Minor：新增向后兼容资产、可选节点、适用条件或替代 Resource。
- Major：删除或改名稳定 ID，改变步骤、适用范围、完成标准、许可证或载体合同。必须给出迁移和回退说明。

Catalog 版本和单项资产版本分别治理。任何会改变现有消费者结果的修改都必须同步测试与生成 Catalog。

## 新鲜度与失效

每项资产明确 `updated_at`、`stale_after` 和 `stale`。超过复核日期不会由构建器按当前时间自动改写，以保持确定性；Maintainer 必须在 PR 中复核并显式更新状态。失效但仍有迁移价值的资产标记 `needs_review` 或 `archived`，不得静默删除稳定 ID。

## 边界与回退

- 发布链固定为 Community GitHub → CI Catalog → RHZL 运行时索引；没有 RHZL → GitHub 的自动反向编辑。
- 专项 Skill / 工具保留独立仓库，本仓只维护注册信息。
- RHZL 独占用户状态、个性化、Run / Result / Asset / Feedback、权限和 Pro 服务。
- 发现错误时优先回退 Catalog 消费版本或恢复上一资产版本；禁止用生产数据回填公开仓。
- Marketplace、分润、自助直发和企业私有 Workflow 不属于当前试点。
