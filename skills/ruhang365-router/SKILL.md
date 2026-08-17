---
name: ruhang365-router
description: Use when a user has a vague AI need, wants to discover a practical AI application scenario, asks which 入行365 or 入行之路 knowledge or specialist Skill fits a task, or needs guided writing, visual, learning, or tool-selection help without choosing among many options.
---

# 入行365能力路由器

把模糊问题转成一个可完成的 AI 场景任务。默认选择一条低负担路线，直接带用户完成第一步，再逐轮交付和验收成果。

## 工作流

1. 从用户描述中提取身份、目标、经验、约束、期望交付物和平台。先用一句自然语言确认要完成的成果和关键约束；不要重复询问用户已经提供的信息。
2. 只有缺失信息会改变路线或事实正确性时，才问一个问题；可用一个不超过 5 项的紧凑填写块收集同一成果所需的事实。其余情况直接采用最小风险默认值开始。
3. 把任务归入 `discover`、`writing`、`visual`、`tool` 或 `knowledge`。拿不准时使用 `discover`，然后运行只读路由脚本：

   ```bash
   python3 "$SKILL_DIR/scripts/route_ruhang365.py" \
     --query "我不知道 AI 能帮我的小店做什么" \
     --identity local-business \
     --goal customer-acquisition \
     --experience beginner \
     --constraint low-budget \
     --deliverable weekly-content-kit \
     --intent discover \
     --format markdown
   ```

4. 先请求 RHZL 的公开 Catalog API；请求只含固定 URL、`Accept` 和公开 `User-Agent`，不发送用户问题或 Profile。Schema、版本和摘要有效时在线消费；超时、5xx、无效 JSON、未知 Schema 或摘要不匹配时自动使用随 Skill 安装的稳定快照并标记 `offline_fallback`。在线和离线都用同一套本地匹配算法。
5. 从相关候选中选择一个默认路线。除非用户要求比较，或两个候选会导致实质不同的结果且必须由用户决定，否则不要展示备选项。
6. 在当前回复中开始工作：直接给首个草稿、可填写模板、3–10 分钟微任务或决策建议。专项 Skill 未安装时，先用本地能力完成可行部分，再提供仓库链接；不得自动安装。
7. 对多轮任务维持同一路线并复用已知信息。每轮只推进一个清晰阶段，用自然语言说明当前进度、这一轮的完成标志和唯一下一步；收到回复后直接继续产出，不重新展示整套路线。
8. 只有成果通过可观察的完成标准，并经用户确认需要确认的事实或版本后，才报告完成。默认隐藏意图标签、匹配分数、Catalog 版本和摘要、API 状态、字段命中及能力调用审计；它们影响结果、发生降级或用户追问时再简洁说明。

## 路由规则

- 用户不知道 AI 能做什么：默认只推荐 1 个低风险、当天可完成的已收录场景并直接开始。仅当用户要求比较时展示最多 3 个候选，明确首选且不补造候选。
- 写作任务：保留用户立场和事实边界；先把可复制版本标为待确认草稿，请用户核对事实或指定一处修改。用户明确确认发布意图后再进入发布步骤，不能把“直接发布”设为首轮完成动作。需要公开发布时路由到 `ai-writing-humanizer`。
- 视觉任务：先锁定用途、比例和准确文字；信息足够时直接给视觉方向或 Prompt。需要案例检索时路由到 `ruhang365-visual-prompt-router`。
- 工具选择：围绕待完成的任务比较工具，不输出脱离场景的排行榜。
- 知识学习：用一个问题或一个小练习开始验证，不把用户送进资料堆。

详细意图和交付合同见 `references/routing-policy.md`。内容驱动的场景匹配见 `references/scenario-discovery.md`。Catalog、接口字段、错误语义和公开投影见 `references/api-contracts.md`。

## 执行边界

- 只调用无鉴权、只读的 `/api/community/catalog`。当前公开核心不接收、读取、存储或传输会员 Token，也不接收用户问题、Profile、API Key、Cookie 或登录凭证。
- 身份、目标、经验、约束、交付物和原始问题全部在本地匹配；不得发送图片、完整文章、客户资料、账号信息或其他私人素材。
- 仅使用客户端白名单字段。即使服务返回额外内部字段，也不得展示、缓存或据此推断会员内容。
- Community Catalog 只包含 Supabase 当前已发布 release 的公开投影；Router PR 只是离线快照，不得反向覆盖 Supabase。
- `rights.status=full` 的 Prompt 可以按许可证改写；`reference_only` 只能使用标题、摘要、分类和来源，禁止补全或反推原文。
- 服务失败时保留离线路由；只有故障会缩小覆盖或改变推荐时，才在任务引导之后用一句话说明远程检索不可用。不得声称已经使用远程资料。
- 远程结果与查询没有明显词项匹配时标记 `no_relevant_results`；不得用热门但无关的资料填充答案。
- 检索成功不代表专项 Skill 已执行，Skill 执行不代表用户成果已经验收。在内部保持状态分离；仅在影响用户判断或用户追问时用自然语言说明。
- 不执行发布、发送、购买、部署或其他外部写操作，除非用户在当前任务中明确授权并完成相应确认。

## 示例

应触发：

- “我完全不知道 AI 能用来做什么，帮我从自己的工作里找三个场景。”
- “从入行之路资料库里找适合小店获客的方法，并给我今天能执行的方案。”
- “这篇公众号文章还需要写作和配图，帮我调用合适的入行365能力。”
- “入行365里有没有适合产品海报的 Skill？”

不应触发：

- 用户已经指定明确代码修改，且不需要入行365资料或专项 Skill。
- 用户明确要求使用另一个资料库并排除入行365。
- 仅需闲聊、翻译或简单事实问答。
