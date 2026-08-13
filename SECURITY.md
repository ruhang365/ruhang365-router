# 安全策略

## 支持范围

当前支持最新的 `0.3.x` 版本。

## 报告漏洞

请通过 GitHub 仓库的 **Security → Report a vulnerability** 私密报告安全问题。不要在公开 Issue 中提交密钥、Token、Cookie、私人资料或可利用细节。

报告应包含影响范围、最小复现步骤和建议修复方向。维护者会先确认收到，再根据风险协调修复和披露。

## 设计边界

- v0.3 运行时只调用固定的公开只读 `/api/community/catalog`。
- Catalog 请求不包含用户问题、身份、目标、约束、交付物、Authorization、Cookie、会员 Token 或模型 API Key。
- 服务响应经过字段白名单投影；未知字段不会进入输出。
- `reference_only` 结果即使意外包含正文，也会在客户端删除。
- 环境覆盖地址不得嵌入用户名或密码。
- Community 内容构建会拒绝内部文件路径、本机地址、常见私钥 / Token 形态、缺失来源或许可证以及未批准内容。
- Catalog 摘要在运行时重新计算；被修改但未重新生成摘要的 Catalog 会被拒绝。
- 公开仓不保存用户 Profile、Run、Result、Asset、Feedback、会员或 Pro 数据；只接受 RHZL 已发布公开 Catalog 的快照更新。
