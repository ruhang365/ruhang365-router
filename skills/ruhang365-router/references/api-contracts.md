# Community API 合同

## 在线 Catalog、离线快照与本地匹配合同

`GET /api/community/catalog` 支持 `schemaVersion=1.0.0` 和 `1.1.0`，包含 `catalogVersion`、`contentDigest` 和按类型 / ID / 版本稳定排序的公开 `items`。1.1.0 新增受白名单约束的 `guidance`：career、platform、intake，以及 `source_kind`、`source_id`、`content_kind`、`access`、`detail_ref` 和 `content_hash`。原四类资产不变。`catalog/community-full-1.1.0.json` 是完整离线索引快照，`catalog/catalog.json` 保留为旧版稳定回退；运行时重新计算摘要，摘要不一致、未知 Schema、无效 JSON、超时或 5xx 时使用对应快照并标记 `offline_fallback`。

无参数运行显示欢迎入口。`--guide career-change|work-growth|cross-border` 返回当前问题或匹配资料；`--answer question_id=option_value` 可重复传入。答案均在本地，unknown/skip 不构成正向匹配；非法选项重新询问。推荐需满足全部条件且所有引用资源有效、未过期；最多返回三项。修改时替换此前答案；不以自由文本推断未表达的条件。引导输出顶层 schemaVersion 为 0.4，包含 guidance、resources、catalogVersion、contentDigest 与 catalogSource；旧任务输出不变。

CLI 可传入 `--identity`、`--goal`、`--experience`、可重复的 `--constraint` 和 `--deliverable`。JSON 输出的 `route.communityMatches` 分为 `scenarios`、`workflows`、`resources`、`prompts`，并保留命中分数、理由、稳定 ID、版本、完成标准与来源。它是 Codex 之外的首个跨载体合同证明。命中项可用 `--read <stable_id>` 按 `detail_ref` 读取单条公开正文；不会把问题或 Profile 发送给服务端。受注册、会员或授权限制时返回摘要/来源，不绕过现有访问策略。

Catalog 由 Supabase 当前不可变 release 生成，不包含用户状态或授权信息。完整 Schema 位于仓库根目录 `schemas/`。

有效快照可为 Catalog 请求提供条件 `If-None-Match`（`catalogVersion:contentDigest` 的 SHA-256，带双引号）。200 校验新目录；304 使用已校验快照，仍记录 `catalogSource=online`。没有有效快照的 304 不可接受。显式离线为 `offline_snapshot`，在线异常降级为 `offline_fallback`。

快照更新器的 `--check` 只读；网络错误与 502/503/504 最多尝试三次（含首次），其他 HTTP、协议和摘要错误不重试。这不是运行时 Router 的重试策略。更新在目标文件未被并行改动时原子替换，失败保留旧快照；304 不重写 JSON。

## RHZL 公开只读接口

### 公开结构与关联导航

引导关键词匹配排除含 guidance 的条目（它们由固定 recommendation 单独返回），与 Web 相关资料一致。两端 tokenizer 排除泛词 `一个/怎么/什么/比较/了解/现有/已有/当前/这里/帮助/需要/可以/以及/相关/我们`，不改变权重、不排除职业/产品/运营/用户等实质关键词。

`--read` 的 `detail.structured` 只来自当前已校验 catalog 的同 ID 条目，内部保持原 snake_case 字段。Workflow 保留完整 `nodes`（id/title/action/prompt_ids/resource_ids/completion_criteria）；Prompt 保留 `template`、`variables`、`resource_ids`。仅 current、未过期、未 stale、access=public（缺省为 public）且 governance.rights.status=full 可展示完整结构；受限资料仅摘要、来源、入口、访问与授权信息。`detail.related` 是同目录的一层有效引用投影，包含稳定 ID、title、entryUrl/sourceUrl、access/rights；不自动下载关联正文。在线只按现有详情合同取 body，原 ID/version/contentHash 校验不变，不要求或接受服务端新增 structured。

引导新增顶层 `communityMatches`，固定 `guidance.recommendations` 不变。profile 的 identity/goal/experience/deliverable 为空、constraints 为空，query 由同 intake 中有效已确认选项按问题顺序拼接 `value label`，最后附自由 query。when 不成立的旧分支、unknown/skip、非法选项排除，不使用 question.prompt 或 audience。匹配沿用目录关键词算法，`matchReasons` 表示命中维度、`matchedTerms` 给出实际命中词，`boundary` 明确不代表职业适配或能力评估。所有个人输入只在本地处理。引导和无 query 的直接阅读使用完整 1.1.0 快照；旧任务默认快照不变，使用完整导航时显式传入 `--catalog catalog/community-full-1.1.0.json`。

示例：`python3 scripts/route_ruhang365.py --offline --guide work-growth --answer purpose=improve --answer role=product --query 用户访谈`；推导 query 为 `improve 比较一个现有工作怎么改进 product 产品经理 / 产品运营 用户访谈`。`python3 scripts/route_ruhang365.py --offline --read r365.workflow.customer-feedback-review` 返回三步完整结构与关联 Prompt；不会下载关联资料，也不会调用模型。

RHZL 是托管后端，不是本仓开源服务器；无需账号即可读取公开目录，离线 CLI 和贡献校验无需后端或数据库权限。相同发布版本可供 Web / Skill / CLI 消费，不上传个性化答案；旧快照不保证与在线最新目录一致。

默认基地址：`https://rhzl.ruhang365.cn`

可通过 `RUHANG365_API_BASE_URL` 指向本地或 Preview 环境。覆盖地址必须是无内嵌凭证的 HTTP(S) URL。

Catalog 接口不接受查询参数，不接收用户问题或 Profile。客户端只在本地使用 `identity`、`goal`、`experience`、`constraints` 和 `deliverable` 进行匹配；详情接口只接受目录已返回的稳定资源 ID。

## 共同约束

- Catalog 请求头仅包含 `Accept`、`Accept-Encoding: gzip`、公开的 `User-Agent`，以及有有效快照时的 `If-None-Match`；客户端受限解压后仍校验完整摘要，不发送 `Authorization`、Cookie 或模型密钥。
- 请求 URL 固定为 `/api/community/catalog`，无查询参数；正文按需读取 `/api/community/assets/<stable_id>`。
- 输出顶层记录 `remoteModelCalled=false`、`writePerformed=false`、`credentialsAccepted=false`。
- 公共投影通过后执行本地相关性匹配；没有明显匹配时返回空结果，不用热门但无关的结果填充。
- 远程错误转换为 `offline_fallback`，不打印响应正文、堆栈、请求头或环境变量。
