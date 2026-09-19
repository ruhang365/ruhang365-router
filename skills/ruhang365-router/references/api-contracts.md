# Community API 合同

## 在线 Catalog、离线快照与本地匹配合同

`GET /api/community/catalog` 支持 `schemaVersion=1.0.0` 和 `1.1.0`，包含 `catalogVersion`、`contentDigest` 和按类型 / ID / 版本稳定排序的公开 `items`。1.1.0 新增受白名单约束的 `guidance`：career、platform、intake，以及 `source_kind`、`source_id`、`content_kind`、`access`、`detail_ref` 和 `content_hash`。原四类资产不变。`catalog/community-full-1.1.0.json` 是完整离线索引快照，`catalog/catalog.json` 保留为旧版稳定回退；运行时重新计算摘要，摘要不一致、未知 Schema、无效 JSON、超时或 5xx 时使用对应快照并标记 `offline_fallback`。

无参数运行显示欢迎入口。`--guide career-change|work-growth|cross-border` 返回当前问题或匹配资料；`--answer question_id=option_value` 可重复传入。答案均在本地，unknown/skip 不构成正向匹配；非法选项重新询问。推荐需满足全部条件且所有引用资源有效、未过期；最多返回三项。修改时替换此前答案；不以自由文本推断未表达的条件。引导输出顶层 schemaVersion 为 0.4，包含 guidance、resources、catalogVersion、contentDigest 与 catalogSource；旧任务输出不变。

CLI 可传入 `--identity`、`--goal`、`--experience`、可重复的 `--constraint` 和 `--deliverable`。JSON 输出的 `route.communityMatches` 分为 `scenarios`、`workflows`、`resources`、`prompts`，并保留命中分数、理由、稳定 ID、版本、完成标准与来源。它是 Codex 之外的首个跨载体合同证明。命中项可用 `--read <stable_id>` 按 `detail_ref` 读取单条公开正文；不会把问题或 Profile 发送给服务端。受注册、会员或授权限制时返回摘要/来源，不绕过现有访问策略。

Catalog 由 Supabase 当前不可变 release 生成，不包含用户状态或授权信息。完整 Schema 位于仓库根目录 `schemas/`。

## RHZL 公开只读接口

默认基地址：`https://rhzl.ruhang365.cn`

可通过 `RUHANG365_API_BASE_URL` 指向本地或 Preview 环境。覆盖地址必须是无内嵌凭证的 HTTP(S) URL。

Catalog 接口不接受查询参数，不接收用户问题或 Profile。客户端只在本地使用 `identity`、`goal`、`experience`、`constraints` 和 `deliverable` 进行匹配；详情接口只接受目录已返回的稳定资源 ID。

## 共同约束

- Catalog 请求头仅包含 `Accept`、`Accept-Encoding: gzip` 和公开的 `User-Agent`；客户端受限解压后仍校验完整摘要，不发送 `Authorization`、Cookie 或模型密钥。
- 请求 URL 固定为 `/api/community/catalog`，无查询参数；正文按需读取 `/api/community/assets/<stable_id>`。
- 输出顶层记录 `remoteModelCalled=false`、`writePerformed=false`、`credentialsAccepted=false`。
- 公共投影通过后执行本地相关性匹配；没有明显匹配时返回空结果，不用热门但无关的结果填充。
- 远程错误转换为 `offline_fallback`，不打印响应正文、堆栈、请求头或环境变量。
