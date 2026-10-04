# RHZL Community Catalog v1

这是托管 RHZL 的发布合同，不是开源服务器或数据库安装说明。本仓仅分发公开 Router、Skill、协议与快照；使用和本地贡献均不需要数据库权限。

Supabase 是 Community 内容唯一可编辑真相源。RHZL 从已发布的不可变 release 提供：

```http
GET https://rhzl.ruhang365.cn/api/community/catalog
```

Router 只保存该接口的版本化公开快照，并在运行时优先读取在线 API。它不生成数据库导入合同、不写 Supabase，也不接收用户问题、身份、约束、交付物、Cookie 或凭据。

响应支持 `schemaVersion=1.0.0` 与 `1.1.0`，包含语义化 `catalogVersion`、公开 `items` 和规范化 `items` 的 `contentDigest`。客户端必须重新计算摘要；超时、5xx、无效 JSON、未知协议或摘要不匹配时，使用有效快照并标记 `offline_fallback`。

1.1.0 增加结构化职业引导、来源身份、内容类别、访问条件和版本化正文引用；四类资产保持兼容。大型目录使用 `Content-Encoding: gzip`，Python 客户端限制响应及解压大小后重新校验摘要。正文通过 `/api/community/assets/<stable_id>?catalogVersion=<version>` 按需读取；版本不可用返回 409，正文变化且哈希不一致返回 503。注册、会员与 reference_only 内容不提供复制正文，继续使用原站入口。

有效本地快照可提供 `If-None-Match`：将 `catalogVersion:contentDigest` 的 UTF-8 字节做 SHA-256，并以双引号包围摘要作为 ETag。200 响应重新校验数据；304 仅在已有有效快照时可用，沿用快照且标记 `source=online`，不改变原 JSON。显式离线为 `offline_snapshot`，不是网络故障回退。同一发布版本供各入口消费；不上传个人答案，不承诺在线与旧离线快照始终最新一致。

快照更新只能来自 RHZL 的已发布 API。快照 PR 合并只更新离线分发版本，不触发数据库导入或反向覆盖 Supabase。Catalog 结构变化必须版本化；未知 Schema 直接触发稳定快照回退，未完成兼容验证前不得接受新合同。

本地同步写入使用同目录稳定的 `.snapshot.lock` 文件，将最终指纹比较及原子替换放在目标级互斥保护中；另一个 updater 正在写入时返回 `concurrent_update`，不自动重试，先核对现有文件再重新开始。锁文件保持同一 inode、不删除重建，进程结束释放系统锁；`--check` 和无变化读取不创建锁。该保护适用于使用本更新器的协作写入者，不是对任意不合作编辑器的文件级原子 CAS。macOS 真实双进程测试通过；Windows 标准库锁分支尚未在 Windows 实机验证。

## 历史生产基线

以下是 2026-08-13 的历史证据，不代表当前部署或当前版本的验收。公开发布基线已到 Router `v0.5.0`；本文件新增行为仍需结合本次测试证据，不以旧版通过推定新版通过。

2026-08-13 当时的生产版本为 Catalog `1.0.0`，digest 为 `215d7ea85d81a01dfbcc2477403b2df8b5f5b967c05d93825165bdd43decf321`，共 14 项。公共投影把 2 个非 Skill Resource 与 2 个官方 Skill 统一计入 `type=resource`，因此 API 类型统计为 4 `scenario`、4 `workflow`、4 `resource`、2 `prompt`。

Router 公开版本为 `v0.3.0`。从公开 Tag 全新安装、在线 API 匹配、强制 API 不可用时的 `offline_fallback`、摘要校验和快照幂等更新均已验证。该结论证明技术与生产闭环已完成，不代表真实用户留存、商业价值或 PMF 已验证。
