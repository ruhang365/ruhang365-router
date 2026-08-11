---
name: ruhang365-router
description: Diagnose an AI task, discover practical AI application scenarios, retrieve a small rights-aware set of public Ruhan365 knowledge or Prompt references, and route the task to a suitable specialist Skill. Use when a user asks what AI can do for them, wants help choosing an AI workflow or tool, asks to use the 入行365 or 入行之路 knowledge base, or needs coordinated writing, visual, knowledge-learning, or tool-selection support. Keep retrieval read-only, never request credentials, and deliver an outcome rather than a list of links.
---

# 入行365能力路由器

把模糊问题转成一个可完成的 AI 场景任务。先诊断目标，再检索少量公开资料，最后路由到合适的专项 Skill 并交付成果。

## 工作流

1. 从用户描述中提取目标、对象、交付物、平台和限制。信息不足时最多问一个会改变路线的问题。
2. 把任务归入 `discover`、`writing`、`visual`、`tool` 或 `knowledge`。拿不准时使用 `discover`。
3. 运行只读路由脚本：

   ```bash
   python3 "$SKILL_DIR/scripts/route_ruhang365.py" \
     --query "我不知道 AI 能帮我的小店做什么" \
     --intent discover \
     --format markdown
   ```

4. 从返回结果中选择最少且足够的资料。普通任务最多使用 3 条知识、3 个 Skill 和 1 条视觉 Prompt；不得遍历或导出整个资料库。
5. 路由到专项 Skill：中文公开写作优先 `ai-writing-humanizer`，视觉生成或改图优先 `ruhang365-visual-prompt-router`。未安装专项 Skill 时，提供仓库链接和本地可完成的替代方案，不得自动安装。
6. 交付用户要求的成果，例如场景清单、执行步骤、文章、视觉 Prompt 或工具选择建议。不要把检索结果列表当作最终交付。
7. 说明使用了哪些公开结果、哪些能力未调用，以及仍需用户决定的事项。

## 路由规则

- 用户不知道 AI 能做什么：优先给 3 个与其身份和目标匹配的场景，并推荐一个当天可完成的首个成果。
- 写作任务：保留用户立场和事实边界；需要公开发布时路由到 `ai-writing-humanizer`。
- 视觉任务：先确定用途、比例和准确文字；需要案例检索时路由到 `ruhang365-visual-prompt-router`。
- 工具选择：围绕待完成的任务比较工具，不输出脱离场景的排行榜。
- 知识学习：返回最少的学习材料和下一步练习，不把用户送进资料堆。

详细意图、专项 Skill 注册表和交付合同见 `references/routing-policy.md`。接口字段、错误语义和公开投影见 `references/api-contracts.md`。

## 执行边界

- 只调用公开、只读的 Community 接口。v0.1 不接收、读取、存储或传输会员 Token、API Key、Cookie 或登录凭证。
- 查询只包含完成检索所需的短语；不得发送图片、完整文章、客户资料、账号信息或其他私人素材。
- 仅使用客户端白名单字段。即使服务返回额外内部字段，也不得展示、缓存或据此推断会员内容。
- `rights.status=full` 的 Prompt 可以按许可证改写；`reference_only` 只能使用标题、摘要、分类和来源，禁止补全或反推原文。
- 服务失败时保留离线路由并明确标记远程检索不可用；不得声称已经使用入行365资料。
- 检索成功不代表专项 Skill 已执行，Skill 执行不代表用户成果已经验收。分别报告这些状态。
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
