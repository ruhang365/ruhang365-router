# 贡献指南

感谢帮助改进入行365能力路由器。

## 开发流程

1. Fork 仓库并创建聚焦单一问题的分支。
2. 修改代码、Skill 或公开合同。
3. 运行 `./scripts/validate.sh`。
4. 提交 Pull Request，说明用户场景、行为变化和验证证据。

## Community 内容贡献

任何人都可以提交内容建议 PR，但 PR 只是候选，不是正式内容入口。只有通过自动校验、维护者审核、录入 Supabase 并进入不可变 release 的版本才进入正式 Catalog。

1. 以 `content/` 的首发种子格式提交建议；文件名必须等于 `slug`。维护者不会从该目录自动导入数据库。
2. 使用稳定 ID `r365.<type>.<slug>` 和语义版本；不得通过改 ID 规避兼容性评估。
3. 完整填写来源、SPDX 许可证、署名、Maintainer、审核日期、更新时间、失效日期、适用 / 不适用条件和完成标准。
4. 专项 Skill 或工具保持独立仓库；Resource 只登记稳定 ID、用途、版本、适用性、来源与链接。
5. 长文章继续留在 RHZL 或原始来源，用 `source_url` 引用；不要复制全文来填充 Catalog。
6. 运行 `python3 scripts/build_catalog.py --write` 只用于验证建议结构；不得把本地生成的 Catalog 当作生产快照。
7. 运行 `./scripts/validate.sh` 并在 PR 中记录结果。审核通过后由维护者在 Supabase 发布，自动快照 PR 只读取 RHZL API。

维护者审核时会把 `governance.review.status` 固定为 `approved`。未获批准、来源或许可证不清、引用断裂、含内部路径 / 凭证 / 用户数据的内容不得合并。

## 内容和安全边界

- 不提交密钥、Cookie、Token、用户数据、会员内容或内部路径。
- 不复制授权不明确的文章、Prompt、图片或资料库正文。
- 新增服务端字段时先更新公开白名单和测试；禁止直接透传完整响应。
- 网络测试必须只读，并且不能成为 CI 成功的必要条件。
- 不把安装成功、HTTP 200 或工具调用成功描述成用户成果已经完成。
- 不提交用户 Profile、Run、Result、Asset、Feedback、会员 / Pro 数据；RHZL 到本仓只允许公开 Catalog 快照，不包含用户数据。

Bug 请提供最小可复现输入和脱敏后的结构化输出，不要粘贴请求头或环境变量。
