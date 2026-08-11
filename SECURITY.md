# 安全策略

## 支持范围

当前支持最新的 `0.1.x` 版本。

## 报告漏洞

请通过 GitHub 仓库的 **Security → Report a vulnerability** 私密报告安全问题。不要在公开 Issue 中提交密钥、Token、Cookie、私人资料或可利用细节。

报告应包含影响范围、最小复现步骤和建议修复方向。维护者会先确认收到，再根据风险协调修复和披露。

## 设计边界

- v0.1 只调用公开、只读的 Community 接口。
- 客户端不接受或发送 Authorization、Cookie、会员 Token 或模型 API Key。
- 服务响应经过字段白名单投影；未知字段不会进入输出。
- `reference_only` 结果即使意外包含正文，也会在客户端删除。
- 环境覆盖地址不得嵌入用户名或密码。
