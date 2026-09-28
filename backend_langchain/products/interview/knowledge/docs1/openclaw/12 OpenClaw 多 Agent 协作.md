# OpenClaw 多 Agent 协作

> 组建龙虾军团，子 Agent 和多 Agent 玩法全解析

你好，我是鱼皮。这应该是大家最期待的玩法了 —— 搞个龙虾军团！OpenClaw 支持两种多智能体模式：子 Agent 和多 Agent。这篇教程带你全面了解它们的用法和区别。



## 子 Agent（最常用）

子 Agent（Subagent）你可以理解成临时外包。

主龙虾是队长，遇到可以并行的任务时，临时派出几只 “外包小龙虾” 去干活，干完了再回来汇报结果，然后外包虾就下班走人了。



### 什么是子 Agent

子智能体有几个重要特点：

- 并行执行：多个子智能体可以同时干活，互不阻塞，效率翻倍
- 上下文隔离：每个子智能体有自己独立的上下文，不会污染主龙虾的对话
- 自动汇报：干完活会自动把结果汇报给主龙虾，主龙虾再整合



### 使用子 Agent

使用子智能体的方法很简单，有两种方式。

**方式一：对话触发**

可以直接在对话中提到 “用子智能体去做”，AI 会自己判断要不要使用 OpenClaw 内置的 `sessions_spawn` 工具，然后派子智能体去干活。

比如我跟小龙虾说：

```markdown
我想获取鱼皮 2 个网站的截图，请你派 2 个子智能体分别完成。
- mianshiya.com
- codefather.cn
```

可以看到，AI 成功派了多个子智能体，它们会并行运行，互不阻塞。比起一个龙虾自己干活，更快速地完成了任务：

![](https://pic.yupi.icu/1/1773911571363-24678c6c-7980-4fbd-ad89-a53c72a4eea2.png)

可以在 Web 控制台中，查看到更详细的子智能体信息：

![](https://pic.yupi.icu/1/1773911504019-eed87a8f-228c-4f7d-98e6-0d510b8e197d.png)



**方式二：斜杠命令触发**

使用 OpenClaw 的斜杠命令 `/subagents spawn`，相当于你亲自下令派一个子智能体去干活，能更稳定地触发子智能体机制。

比如让小龙虾帮我截取自己的 3 个网站的图片，拼接到一起然后发送给我：

```markdown
帮我截取 3 个网站，并且把 3 张图横着拼接到一起然后发送给我
/subagents spawn 截图 mianshiya.com
/subagents spawn 截图 codefather.cn
/subagents spawn 截图 laoyujianli.com
```

可以看到，创建了 3 个子智能体，然后由主智能体汇总截图并拼接，快速完成了任务：

![](https://pic.yupi.icu/1/1773911853354-df98768b-845d-4817-8429-c64196d050af.png)

对了，还有个省钱技巧，子智能体可以用便宜的模型，还能单独设置回复模式。

```bash
# 全局设置子智能体的默认模型
openclaw config set agents.defaults.subagents.model "zai/glm-4.7-flash"

# 或者在对话中临时指定
/subagents spawn --model zai/glm-5 --thinking high 帮我写一篇技术报告
```



### 管理子 Agent

为什么要管理子智能体？

因为子智能体派出去之后不一定乖乖干活，可能跑偏了、卡住了、或者你想看看它具体做了什么。这时候就需要查看、指挥、甚至干掉它们。

建议先开启 `/verbose full`，否则在飞书里可能看不到子智能体的 runId，有了这个 id 我们后续能控制这个子智能体：

![](https://pic.yupi.icu/1/1773910849723-bd057770-21cd-4407-95f7-419b1df60d13.png)

来试一试，比如我让 AI：

```markdown
帮我派 2 个子智能体，每个智能体都睡觉 3 分钟，其他什么事都不用做。
```

可以看到每个子智能体的 runId：

![](https://pic.yupi.icu/1/1773912277450-01769f38-df8d-4649-8dc0-a03374ff1d6e.png)

子智能体管理常用命令如下，我们依次来玩一玩：

| 命令              | 作用                       | 用法示例                    |
| ----------------- | -------------------------- | --------------------------- |
| `/subagents list` | 查看所有子智能体           | `/subagents list`           |
| `/subagents kill` | 终止子智能体               | `/subagents kill <id>`      |
| `/steer`          | 给正在运行的子智能体发指令 | `/steer <id> 换个方向做`    |
| `/kill`           | 立即终止子智能体（无确认） | `/kill <id>` 或 `/kill all` |

1）`/subagents list` 查看正在运行的子智能体，还能看到最近执行完成任务的子智能体：

![](https://pic.yupi.icu/1/1773912142552-f602fb3f-5f16-4b29-9b0d-738feb2f5267.png)

2）`/subagents info <runId>` 查看某个子智能体的详情：

![](https://pic.yupi.icu/1/1773912317629-38f77623-2de4-4551-83a5-6b9bcee37abc.png)

3）`/subagents steer <runId> <新指令>` 给正在跑的子智能体发新指令，改变任务方向：

![](https://pic.yupi.icu/1/1773912714239-491ab747-8a12-412c-b378-fbdece143472.png)

4）`/subagents kill <runId>` 停掉某个子智能体，`/subagents kill all` 停掉当前会话所有子智能体：

![](https://pic.yupi.icu/1/1773912467265-41f9eae5-c511-475f-b7a6-d9bd1a79b3de.png)

其实执行 `/stop` 干掉主对话后，子智能体也会全部停掉。



## 多 Agent

多 Agent 和子 Agent 不一样，相当于你养了多只 **独立的** 小龙虾，每只龙虾有自己独立的工作空间、身份人设、记忆和会话。

你可以让不同的 Agent 干不同的活，比如一只专门写代码、一只专门审核代码、一只专门管理家族群。



### 创建新的 Agent

先执行命令来创建一个 Agent，名称为 `review`，专门负责审核代码：

```bash
openclaw agents add review
```

按照引导选择配置就好，复用主代理的鉴权配置（不用再配置一通 API Key 了），其他的都选择 No：

![](https://pic.yupi.icu/1/1773915876829-14dfafb6-adff-4c50-8a31-e61e926c2b0c.png)

同样的方法，再创建一个编程小龙虾：

```bash
openclaw agents add coding
```

每个小龙虾对应的工作空间都是独立的：

![](https://pic.yupi.icu/1/1773916015240-38dddad4-4b5f-44bc-b02c-787900dac6e3.png)

可以在 Web 控制台查看和管理各个小龙虾：

![](https://pic.yupi.icu/1/1773916087882-9f03ebe8-196a-43d0-bb49-59a8e2a02e05.png)



### 配置路由

接下来需要配置「路由」，也就是 “谁的消息” 发给 “哪个 Agent” 来处理。

先通过飞书提供的工具快速创建 2 个飞书机器人：

![](https://pic.yupi.icu/1/1773916506635-c38e3d93-ef3f-40ad-a98b-5b10477e9fa5.png)

![](https://pic.yupi.icu/1/1773916793595-feb75a64-9441-418b-8b5c-226656cf3418.png)

跟之前接入飞书一样，需要到管理后台审核应用并通过：

![](https://pic.yupi.icu/1/1773916847944-67746bd5-0cb9-46ab-89c8-2b4e8f11dc6b.png)

然后到了最复杂的部分，建议先把当前的 `openclaw.json` 配置文件备份一下。

一定要仔细看下面几张图改动的部分，主要是在 `agents.list` 中添加新 Agent 的信息、在 `channels.feishu.accounts` 中添加新机器人的 AppID 和 AppSecret、以及添加 `bindings` 路由绑定：

![](https://pic.yupi.icu/1/1773918646676-cae06929-bce0-4731-881b-b4205baaa662.png)

![](https://pic.yupi.icu/1/1773918775330-36cdfc1f-ddff-41cc-91f6-ae339734205c.png)

![](https://pic.yupi.icu/1/1773918835278-e601c162-e1fe-44ed-a2a6-8dac32a726c7.png)

飞书官方有提供示例的配置文件，可以到官方文档复制：

![](https://pic.yupi.icu/1/1773919164569-1c1b0835-99cf-4348-ba2b-767a298a4eb2.png)

注意编写配置文件的过程中，不要多加逗号、也不要添加中文注释。建议在 VSCode 等代码编辑器中打开，会自动帮你做格式校验。

改完配置后，重启网关：

```bash
openclaw gateway restart
```

![](https://pic.yupi.icu/1/1773917505810-3901c771-8ce7-4209-9a8c-a2f8cc5e5934.png)

然后就可以愉快地跟多只小龙虾对话了~

![](https://pic.yupi.icu/1/1773918903905-912e308e-98a8-4af7-8947-14afb3d66157.png)

一样的，先初始化小龙虾，我这里就随便说 2 句了：

```markdown
你是鱼皮的编码虾，你的工作就是编写代码
你是鱼皮的审核虾，你的工作就是审核代码
```

![](https://pic.yupi.icu/1/1773918978670-76a33350-3221-4727-9f0f-db9c57d22390.png)

然后你就可以给它们不同的任务，让多只小龙虾同时干活了：

![](https://pic.yupi.icu/1/1773919067863-a9939ddc-6f28-458c-8ee2-14e51506be97.png)



### 多个 Agent 共享上下文协作

如果你想让多个机器人之间共享记忆、或者共同完成一个任务，最简单粗暴的方法就是让它们共享记忆文件，比如把主 Agent 的长期记忆文件 `MEMORY.md` 和主人信息 `USER.md` 拷贝给其他的 Agent。

还有更灵活的方法，开启 A2A（agent-to-agent）通信，让 Agent 之间可以互相发消息。

执行下面这几条命令：前两条开启 A2A 通信并设置允许哪些 Agent 互相联系，第三条将会话可见性设为 `all`，让 Agent 能看到其他 Agent 的会话（默认只能看到自己的），最后重启网关让配置生效。

```bash
openclaw config set tools.agentToAgent.enabled true
openclaw config set tools.agentToAgent.allow '["main","coding","review"]' --strict-json
openclaw config set tools.sessions.visibility "all"
openclaw gateway restart
```

![](https://pic.yupi.icu/1/1773919714069-d243dd46-37f4-4d42-92bd-7399320bbea6.png)

还要告诉主 Agent “能够通过 OpenClaw 内置的工具找其他 Agent 干活”。需要修改主 Agent 的 `AGENTS.md`，这是专门教 Agent 如何干活的文件，需要增加多 Agent 协作的说明。

但是这种方式有个不足之处，虽然任务成功派发给了其他 Agent，但主 Agent 并不能及时获取到其他 Agent 的回应，可能仍然会自己干活。

![](https://pic.yupi.icu/1/1773920728472-010ba8fd-43fc-452d-8048-1a415a6f523b-20260319211759809.png)

实际上其他 Agent 已经在干活了：

![](https://pic.yupi.icu/1/1773920767310-c3fab963-ac19-457d-9801-9b287476fc17-20260319211759867.png)

这里有个细节：`sessions_send` 是同步等待的，适合快速问答；而 `sessions_spawn` 是异步的，对方干完活会自动汇报回来，适合耗时任务。所以正确的做法是让 Agent 根据任务复杂度选择工具。

需要确保 main Agent 可以 spawn 派发任务到其他 Agent，执行下列命令：

```bash
openclaw config set 'agents.list[0].subagents.allowAgents' '["main","coding","review"]' --strict-json
openclaw gateway restart
```

在主 Agent 的 `AGENTS.md` 文件末尾追加这段多 Agent 协作说明（里面的 Agent 名称和职责换成你自己的）：

```markdown
## 多 Agent 协作

你不是一个人在战斗！你可以找其他 Agent 帮忙。

### 可用的 Agent

| Agent ID | 名字 | 擅长什么 |
|---|---|---|
| `coding` | 编码虾 | 写代码、调试、技术问题 |
| `review` | 审核虾 | 代码审查、方案评审、质量把关 |

### 怎么找它们

根据任务复杂度选择方式：

快速问答（几秒能回）→ 用 `sessions_send`（A2A 对话）：
- `sessionKey` 填 `agent:<agentId>:main`
- `timeoutSeconds` 建议设 60

耗时任务（超过 30 秒）→ 用 `sessions_spawn`（派任务）：
- `agentId` 填目标 Agent 的 id
- `task` 填具体任务描述
- 对方干完会自动汇报结果回来

### 注意事项

- 简单问题用 sessions_send（快速同步），复杂任务用 sessions_spawn（异步后台）
- sessions_send 默认等 30 秒，复杂问题会超时，这时改用 sessions_spawn
- 收到结果后，总结给主人，不要原封不动转发
- 不要同时找多个 Agent 做同一件事
```

![](https://pic.yupi.icu/1/1773921274064-96281e6c-8a37-4b4f-bfaf-280a5d0104c3.png)

这次，主 Agent 就可以给其他的小龙虾派发任务了（类似子 Agent 模式）。你可以额外给其他龙虾也进行类似的配置，让多个龙虾之间可以自由协作：

![](https://pic.yupi.icu/1/1773920953759-295a1ae9-64db-47ad-af1e-8e3351ebb6be.png)

能在 Web UI 看到派发的任务和执行过程：

![](https://pic.yupi.icu/1/1773921027498-fa442bd1-8458-48a9-8ae3-5f7dc416648c.png)



## 子 Agent 和多 Agent 的区别

简单列举一下两者的核心区别：

| 对比项   | 子智能体（Sub-Agent）  | 多 Agent                     |
| -------- | ---------------------- | ---------------------------- |
| 关系     | 同一个大脑派出的临时工 | 多个独立的大脑               |
| 工作区   | 共享主 Agent 的工作区  | 各自独立的工作区、记忆、人格 |
| 生命周期 | 任务完成就结束         | 永久存在，一直在线           |
| 用途     | 并行干活提效率         | 不同场景用不同人格/模型/权限 |

对大多数朋友来说，子 Agent 就够用了。多 Agent 更适合有多种使用场景、需要严格隔离的龙虾熟练工。



## 写在最后

龙虾军团组建好了！接下来我们来学习记忆管理和成本控制，让你的龙虾用得省心又省钱。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
