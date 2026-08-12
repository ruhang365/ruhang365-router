# Community API 合同

默认基地址：`https://rhzl.ruhang365.cn`

可通过 `RUHANG365_API_BASE_URL` 指向本地或 Preview 环境。覆盖地址必须是无内嵌凭证的 HTTP(S) URL。

## 知识检索

`GET /api/knowledge/search?q=<query>&limit=<1..5>`

只保留：`id`、`title`、`description`、`content_type`、`source_url`、`action_label`、`tags`、`target_goals`、`target_identities`、`difficulty`、`estimated_minutes`、`risk_note`。

客户端不得输出服务返回的完整正文或未知字段。

## Skill 推荐

`GET /api/skills/recommend?goal=<query>&limit=<1..5>`

只保留：`id`、`slug`、`title`、`subtitle`、`description`、`skill_type`、`version`、`tags`、`usage_count`、`average_rating`、`pricing_mode`。

客户端不得输出服务端内容正文、创建者内部标识、价格或未知字段。

## Prompt 检索

`GET /api/v1/prompt-library/search?q=<query>&assetType=image_prompt&limit=<1..5>`

只保留：`id`、`collection`、`title`、`category`、`tags`、`recommended`、`rights`、`summary`、`prompt`、`score`。

只有 `rights.status=full` 才保留 `prompt`；`reference_only` 即使意外返回正文也必须删除。

## 共同约束

- 请求头只包含 `Accept` 和公开的 `User-Agent`；v0.1 不发送 `Authorization`、Cookie 或模型密钥。
- 查询为 2–240 个字符，默认 3 条、最多 5 条。
- 输出顶层记录 `remoteModelCalled=false`、`writePerformed=false`、`credentialsAccepted=false`。
- 白名单投影后执行本地相关性过滤；没有明显匹配时返回 `no_relevant_results`，不透传热门但无关的结果。
- 远程错误转换为结构化状态，不打印响应正文、堆栈、请求头或环境变量。
