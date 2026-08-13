# Community 治理

## 当前维护者

- [`fzy2012`](https://github.com/fzy2012) — Primary Maintainer。负责项目方向、公开 API 与 Schema 合同、版本发布、安全与兼容性审核，以及最终合并决策。

贡献代码或内容不会自动获得 Maintainer 权限。新增 Maintainer 必须具有持续、可验证的评审与发布贡献，并由现有 Maintainer 在公开 PR 中确认。

## 权威与角色

Supabase 是公开、跨载体结构化资产的唯一可编辑内容真相源。Contributor 可在 Router 提交内容建议；Reviewer 核验 Schema、来源、权利、可执行性和边界；Maintainer 把通过审核的变更录入 Supabase 并发布不可变 release。Router 只保存公开离线快照。

Supabase release 和对应审核记录是发布凭证。CI 通过只证明自动合同成立，不代替维护者审核；Router PR 未合并前不能被描述为正式离线分发版本。

## 变更级别

- Patch：文字澄清、标签或来源补充，不改变适用范围、步骤与结果。
- Minor：新增向后兼容资产、可选节点、适用条件或替代 Resource。
- Major：删除或改名稳定 ID，改变步骤、适用范围、完成标准、许可证或载体合同。必须给出迁移和回退说明。

Catalog 版本和单项资产版本分别治理。任何会改变现有消费者结果的修改都必须同步测试与生成 Catalog。

Catalog 结构演进必须使用新的 `schemaVersion`，并在成为 current 前完成在线、离线和旧 Tag 兼容验证。现有客户端遇到未知 Schema 必须回退稳定快照；不能通过放宽校验或直接修改快照绕过版本门禁。

## 新鲜度与失效

每项资产明确 `updated_at`、`stale_after` 和 `stale`。超过复核日期不会由构建器按当前时间自动改写，以保持确定性；Maintainer 必须在 PR 中复核并显式更新状态。失效但仍有迁移价值的资产标记 `needs_review` 或 `archived`，不得静默删除稳定 ID。

## 边界与回退

- 发布链固定为 Supabase → RHZL Public Catalog API → Router 自动快照 PR → Skill；Router 不能反向覆盖 Supabase。
- 专项 Skill / 工具保留独立仓库，本仓只维护注册信息。
- RHZL 独占用户状态、个性化、Run / Result / Asset / Feedback、权限和 Pro 服务。
- 发现错误时优先把 Supabase current 指针切回上一不可变 release；Router 保留旧 Tag 并通过补丁版本更新快照。
- Marketplace、分润、自助直发和企业私有 Workflow 不属于当前试点。

## 生产收口后的治理

2026-08-13 的技术与生产闭环已经收口。后续优先处理 API / digest / 快照工作流告警、前滚与回滚演练、公共投影 deny-list 负向测试和兼容门禁；这些属于稳定运行治理，不改变 Supabase 唯一可编辑主源和 Router 只读派生物的职责。
