# VSCode + GitHub Copilot：微软全家桶的 AI 编程实战

> 从安装到实战，手把手教你用 VSCode + GitHub Copilot 进行 AI 编程



你好，我是程序员鱼皮。

AI 编程工具现在是真的百花齐放，Cursor、Claude Code、OpenCode、…… 每隔一段时间就冒出来一个新选手。

之前我一直沉迷于 Cursor 和 Claude Code，直到最近做新项目时认真体验了一把 GitHub Copilot， 才发现这玩意儿真夯啊！

![](https://pic.yupi.icu/1/13c2a89f183a7161be27361ce4908ed6.png)

先简单介绍一下主角。**VSCode** 是微软出品的全球最流行的代码编辑器，装机量破亿；**GitHub Copilot** 则是 GitHub 官方出品的 AI 编程助手插件，直接安装在 VSCode 中使用。

个人体验下来，相比其他 AI 编程工具有 4 大优势：

1. 支持最新 AI 大模型，Opus、GPT、Gemini、Claude 随便切，实测编程质量嘎嘎好，全栈项目一把梭
2. 支持本地、后台 CLI、云端、Claude Code 等多种运行模式，兼容性贼强
3. 支持 MCP、Skills、工具调用的可视化管理，既灵活又方便，不用自己手动编写配置了
4. 支持子智能体、和 AI 的每一步交互都清晰可见，Agent 执行体验巨好

啥啥啥，这都是啥？

![](https://pic.yupi.icu/1/image-20260305141036239.png)

即使你看不懂我说的这些也没关系，这篇文章就带大家从 0 开始上手 VSCode + GitHub Copilot，从安装到实战、从基础到核心特性，一条龙服务。

干货密集，建议先收藏，然后沐浴更衣、找个安静的地方放空自己，慢慢食用，助眠效果极佳~



## 安装和配置

1）首先进入 [VSCode 官网](https://code.visualstudio.com/) 下载安装包，直接傻瓜式安装。

![](https://pic.yupi.icu/1/image-20260305141229310.png)

2）打开 VSCode，点击左侧「扩展市场」图标，搜索 "GitHub Copilot"，安装官方的 AI 编程插件。

![](https://pic.yupi.icu/1/image-20260305141416199.png)

你还可以根据需要，选择安装 Chinese 汉化插件，适合国内的宝宝们：

![](https://pic.yupi.icu/1/image-20260305153013870.png)

3）安装完后，点击 VSCode 底部状态栏的 Copilot 图标，按照提示登录 GitHub 账号就行了。

![](https://pic.yupi.icu/1/setup-copilot-status-bar.png)

如果你还没有 Copilot 订阅，会自动进入 **Copilot Free 免费计划**，每月有一定的 AI 对话和代码补全额度，零门槛上手。想体验完整功能的话，Copilot Pro 支持新用户免费试用 30 天，申请一张国内银行的 Visa 卡就能开通。

我白票了 30 天的高级会员，最近能省一点其他 AI 编程工具的额度了哈哈~ 🤣

到这里，安装配置就全部搞定了，比折腾 Claude Code 那套网络受限 + 账号受限 + 命令行小黑框的组合拳简单多了。

![](https://pic.yupi.icu/1/1766562559951-d1371bb9-99d3-467a-aeec-421cd12eb3bb.png)



## 基本使用

装好之后，先来感受一下最基本的 AI 编程体验。



### AI 对话

点击 VSCode 上方的「聊天按钮」，打开 Chat 对话面板，你就可以和 AI 愉快地聊天了。让它分析需求、写代码、改 Bug，啥都行。

![](https://pic.yupi.icu/1/image-20260305142129090.png)

对话框区域有一个 **智能体选择器**，可以在 3 种内置模式之间切换：

- Agent 全自主模式：AI 自己分析、写代码、跑命令，一条龙完成任务（用的最多）
- Plan 规划模式：AI 先出方案再动手，适合复杂任务
- Ask 纯问答模式：只回答问题，不改代码，适合探索和学习（我用的比较少）

![](https://pic.yupi.icu/1/image-20260305142244467.png)

除了 Chat 面板，还有两种更轻量的 AI 对话方式。

1）按 `Ctrl+I`（Mac 是 `Cmd+I`）打开行内对话，直接在代码中跟 AI 交互：

![](https://pic.yupi.icu/1/image-20260305142602604.png)

2）按 `Ctrl+Shift+Alt+L`（Mac 是 `Cmd+Shift+Option+L`）打开 Quick Chat 弹窗，适合快问快答。

![](https://pic.yupi.icu/1/image-20260305143009366.png)



### AI 代码补全

写代码的时候，Copilot 会自动给你浅色的补全建议，按一下 `Tab` 就能接受。比如你写了一个计算日期的函数名 plusDate，它能直接帮你把整个函数体补全出来。

![](https://pic.yupi.icu/1/image-20260305143231950.png)

更智能的是 Next Edit Suggestions（NES），也就是「下一步编辑建议」。它不光补全当前位置的代码，还能预测你接下来要改哪里！

编辑器左侧会出现一个小箭头，按 Tab 就能跳过去并应用建议。

![](https://pic.yupi.icu/1/image-20260305143512348.png)

比如你把一个类名从 `Point` 改成了 `Point3D`，它会自动建议你在下面加个 `z` 变量，这个体验像秃噜鱼皮一般丝滑~

![](https://pic.yupi.icu/1/nes-point.png)

这两个功能用 Cursor 的同学应该不陌生，体验上差不多，但 Copilot 的 NES 预测精度个人感觉略胜一筹。

好了，基本功能就是这些，看到这里，你已经超过了 70% 的同学！

接下来进入正题，AI Agent 编程实战。



## AI Agent 编程实战

前面的对话和代码补全只是开胃菜，Agent 模式才是 GitHub Copilot 的大杀器。

什么是 Agent？

简单来说，你给它一个需求，它会自己分析项目、制定计划、创建文件、写代码、跑命令、装依赖，遇到报错还会自动修复，全程自主执行。

其实 Manus、OpenClaw、各种 AI 编程工具里的 Agent 模式，本质上都是 Agent，就是 AI 自主规划、调用工具、执行任务的能力。

现在各家 AI 编程工具都在卷 Agent 能力，比如 Cursor 可以在子 Agent 里操作浏览器进行自主验证，Claude Code 搞出了 Agent Teams 让多个 AI 组队协作。GitHub Copilot 也不甘示弱，除了 Agent 模式之外，也提供了各家都支持的 **Plan 模式**。先让 AI 帮你出方案、拆步骤，确认没问题后再动手，适合稍微复杂一点的项目，减少 AI 一上来就瞎写导致翻车的概率。

下面我带大家实战一把，结合 Plan 模式 + Agent 模式做个**「AI 占卜师网站」**，用户输入一个问题，让 AI 抽取塔罗牌并生成占卜解读。



### 第一步、用 Plan 制定方案

新建一个空的项目文件夹（比如 ai-diviner），在 VSCode 中打开该文件夹，应该会默认打开 Chat 对话面板。

![新建项目](https://pic.yupi.icu/1/image-20260305144504583.png)

在对话区域的智能体选择器中选择 Plan 模式、并选择大模型（比如 Claude Opus），然后输入需求：

```
帮我用 HTML + CSS + JavaScript 做一个 AI 塔罗牌占卜网站。

功能描述：
1. 用户输入一个问题（比如「我最近事业运如何」）
2. 点击「开始占卜」后，展示 3 张塔罗牌的翻牌动画
3. 翻牌完成后，根据抽到的牌生成 AI 占卜解读
4. 界面要神秘华丽，深紫色主题配金色纹理，星空背景
5. 有流畅的翻牌动画效果
6. 响应式布局，手机也能用
```

![Plan模式执行AI](https://pic.yupi.icu/1/image-20260305144551103.png)

选择 Plan 模式后，AI 不会直接开始写代码。

它会先研究你的需求，可能还会问你几个问题，比如 AI 解读是 “调用 AI 大模型接口” 还是 “从预设文案库随机生成”？

你只要像聊天一样把自己的想法告诉 AI 就好，比如我希望调用 DeepSeek 大模型的 API：

![](https://pic.yupi.icu/1/image-20260305144900988.png)

如果你自己也拿不准，可以让 AI 帮你分析不同方案的优缺点，或者交给它自主决定。

AI 理解你的需求后，会给出一份结构化的实施方案。

![](https://pic.yupi.icu/1/image-20260305145315374.png)

方案里会列出要创建哪些文件、每个文件负责什么、实现步骤的先后顺序，以及怎么验证效果。你可以在这一步跟 AI 反复讨论、调整方案，直到满意为止。

![](https://pic.yupi.icu/1/image-20260305145352874.png)

Plan 模式的本质是采用 4 个阶段的迭代工作流：需求研究 → 问题对齐 → 方案设计 → 迭代细化。AI 会先用只读工具深入研究你的代码库，再通过交互式问答来消除歧义，最后才给出方案草稿。

其实这也是软件开发的标准步骤。即使你不用 Copilot 内置的 Plan 模式，也可以通过提示词引导 AI 先设计方案、人工确认后再开发执行，养成 **先想清楚再动手** 的好习惯。



### 第二步、用 Agent 执行方案

确认方案没问题后，点击方案下方的「Start Implementation」按钮，让 AI 开始自动执行，直到实现方案。

![](https://pic.yupi.icu/1/image-20260305145604534.png)

执行过程中，Agent 会自动管理一个 Todos 任务列表来跟踪进度。你可以清楚地看到 Agent 在做什么，比如创建 `index.html`、`style.css`、`script.js` 文件，往里面写代码，甚至可能会自动打开终端执行命令。

![](https://pic.yupi.icu/1/image-20260305145807776.png)

如果 AI 要跑终端命令或者调用某些工具，会弹出确认框让你审批，安全性有保障。

![](https://pic.yupi.icu/1/image-20260305150107141.png)

你也可以在 Agent 工作时继续发消息，选择排队等待、立即打断、或者引导 AI 调整方向。

建议刚开始 AI 编程的朋友多观察一下 AI 的工作，发现不对劲的时候赶紧人工插手，可以节约 Tokens 并避免返工。



### 第三步、查看效果

几分钟后，Agent 不仅完成了开发任务，还用 Python 启动了个 Web 服务器，帮我运行了网站。

![](https://pic.yupi.icu/1/image-20260305150430976.png)

好家伙，这是多一步都不想让我做啊？照这个趋势，早晚我得退化到 Hello World 水平。

不过我还是喜欢在 Chrome 浏览器中测试，复制网址到浏览器中打开，然后输入从 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 获取到的大模型  API Key：

![](https://pic.yupi.icu/1/image-20260305150858949.png)

![](https://pic.yupi.icu/1/image-20260305150957888.png)

输入一个问题，测测俺今年的爱情运势，然后点击「开始占卜」：

![](https://pic.yupi.icu/1/image-20260305151027082.png)

三张塔罗牌依次翻开，下方出现 AI 生成的占卜解读。深紫色的星空背景，搭配金色边框，再加上流畅的翻牌动画，效果还真挺唬人的。

![](https://pic.yupi.icu/1/image-20260305151413007.png)

我感觉自己也可以开一个塔罗占卜小摊儿了，应该不是错觉。。。

![](https://pic.yupi.icu/1/image-20260305151303905.png)

如果你对页面的某些细节不满意，可以在内置浏览器中点击「元素选择」按钮，哪里不爽点哪里，然后在 Chat 框里编写提示词就行，比如：

```
改为鱼皮塔罗
```

![](https://pic.yupi.icu/1/image-20260305151754685.png)

Agent 会自动定位到对应的代码并精准修改，改完你再刷新预览就好。

![](https://pic.yupi.icu/1/image-20260305152037670.png)

整个过程，从写需求到出成品，也就几分钟。搁以前，我要是自己从零写这么个带动画的占卜网站，怎么着也得搞一下午。

你还可以继续跟 AI 对话来增加功能，整个过程中一定要注意 **上下文的用量**，如果满了 AI 可能会断片儿失忆，开始乱改。

![](https://pic.yupi.icu/1/image-20260305152200805.png)

因此，在上下文快满的时候，最好让 AI 把当前项目的信息沉淀为文档。这样之后每次打开新的 AI 对话框时，只要把历史文档交给 AI，就能快速找回记忆。 

OK，实战体验完了，看到这里你就超过了 90% 的同学！

接下来带大家看看 GitHub Copilot 的核心特性，这些才是它真正拉开差距的地方。



## 核心特性

### Tools - 给 AI 的工具箱

Agent 之所以能自主干活，靠的就是工具调用（Tool Use）。

工具就是 AI 在执行任务时可以调用的各种能力，比如搜索代码、读写文件、跑终端命令、抓取网页内容等等。没有工具，AI 就只能动嘴皮子教你做事；有了工具，AI 才能真正动手帮你干活。

VSCode 给 AI 提供了三种类型的工具：

- 内置工具：开箱即用，包括代码搜索、文件读写、终端执行、问题诊断等常用能力
- MCP 工具：通过 MCP 协议接入的外部工具（下面会详细讲）
- 扩展工具：VSCode 插件提供的工具，装了对应插件就自动可用

所有工具都可以通过 Chat 对话区域的「配置工具」按钮进行可视化管理，很方便：

![](https://pic.yupi.icu/1/image-20260305152856918.png)

你可以自由开启或关闭工具，不需要写任何配置文件，比其他 AI 编程工具方便不少。

开启工具后，大多数情况下 AI 会自动判断该调用哪些工具。你也可以在对话中用 `#` 号手动引用特定工具，比如 `#codebase` 搜索整个代码库、`#fetch codefather.cn` 抓取某个网页的内容、`#problems` 查看当前项目的所有报错。

![](https://pic.yupi.icu/1/image-20260305153343950.png)

Agent 执行终端命令时，还有一套安全审批机制。前面实战中我们也看到了，默认会弹确认框等待人工确认；你也可以配置自动审批规则，甚至开启终端沙箱（目前支持 macOS 和 Linux）来限制文件和网络访问，安全性拉满。

![](https://pic.yupi.icu/1/image-20260305153647365.png)

还有一个实用功能叫 Tool Sets（工具集），你可以把多个相关工具打包成一组，在对话中用 `#工具集名称` 一次性引用。

比如创建一个叫 `reader` 的工具集，包含 `codebase` 代码搜索、`problems` 问题诊断、`usages` 引用查找等只读工具，做代码审查的时候就很方便。

先在对话面板的设置中打开「工具集」，点击创建新的工具集文件并输入名称：

![](https://pic.yupi.icu/1/image-20260306104630540.png)

然后会自动弹出工具集的配置文件，添加下列代码并保存即可：

```json
{
  "reader": {
    "tools": ["codebase", "problems", "usages", "search"],
    "description": "只读工具集，适合代码审查",
    "icon": "book"
  }
}
```

![](https://pic.yupi.icu/1/image-20260306104906332.png)

配置好之后，在对话中输入 `#reader` 就能一次性启用这组只读工具了：

![](https://pic.yupi.icu/1/image-20260306105151652.png)



### MCP - 让 AI 连接外部能力

MCP（Model Context Protocol）是一种开放标准协议，作用是让 AI 能够连接外部工具和服务。你可以把它想象成给 AI 装了一个万能接口，通过这个接口，AI 就能操作数据库、调用 API、控制浏览器等等。

MCP 在 AI 圈已经非常火了，各种 AI 编程工具都已支持。但 GitHub Copilot 在管理 MCP 的体验上真是让我眼前一亮，微软竟然直接把 MCP 集成到了 VSCode 的扩展市场里！

你只需要打开 VSCode 扩展市场，开启 MCP 服务市场，就能看到一堆热门的 MCP 服务，哪还需要到什么 MCP 资源网站上自己安装啊？！

![](https://pic.yupi.icu/1/image-20260305154025676.png)

比如我想使用 Context7 这个获取最新技术文档的 MCP，点击安装后，会自动弹窗让我输入 API Key：

![](https://pic.yupi.icu/1/image-20260305154459227.png)

确认之后，就可以正常使用了。AI 在执行任务时会自动调用 MCP 提供的工具，你也可以用 `#` 号主动引用。

比如刚才装好了 Context7，之后让 AI 写代码时它就会自动去拉取最新的技术文档作为参考，减少 AI 瞎编 API 用法的情况。

![](https://pic.yupi.icu/1/image-20260306110049012.png)

整个过程不需要手写 JSON 配置，全程可视化选择和安装，对新手特别友好。以前在 Cursor 里配 MCP 还得自己找 JSON 粘贴，这里点点鼠标就搞定了~

当然，如果你是老手，也可以通过 `.vscode/mcp.json` 文件手动配置 MCP 服务。

```json
{
  "servers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp"
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@microsoft/mcp-server-playwright"]
    }
  }
}
```

这个文件不会自动生成，需要你自己创建，或者通过 VSCode 的命令面板执行 `MCP: Open Workspace Folder Configuration` 命令来打开：

![](https://pic.yupi.icu/1/image-20260306110305648.png)

MCP 服务除了提供工具之外，还支持 Resources（资源）和 MCP Apps（交互式应用）。Resources 可以给 AI 提供数据库表、API 响应等上下文；MCP Apps 则能在对话中渲染表单、仪表盘等交互式 UI 组件，体验拉满。

![](https://pic.yupi.icu/1/mcp-apps-flame-graph.png)

此外，VSCode 还能自动发现其他应用中已配置的 MCP 服务，省去重复配置的麻烦，在 VSCode 聊天设置中搜索 `chat.mcp.discovery.enabled` 即可开启。

![](https://pic.yupi.icu/1/image-20260306110930161.png)

MCP 配置也支持通过 Settings Sync 跨设备同步，在同步设置中勾选「MCP 服务器」选项，换电脑不用重新配一遍。

![](https://pic.yupi.icu/1/image-20260306110740774.png)



### Agent Skills - 给 AI 的技能包

Agent Skills 是给 AI 准备的能力扩展包。和前面提到的 Tools 不同，Skills 更像是一份详细的工作手册，里面包含操作指南、脚本、示例代码等资源，让 AI 在特定任务上表现更专业。

![](https://pic.yupi.icu/1/1769306811193-2ee3acbc-5e36-46c2-8d08-b2682494fb56.png)

比如你给 AI 装个「Web 应用测试」的 Skill，里面写好了用 Playwright 写测试的标准流程、示例模板、最佳实践。之后你让 AI 帮你写测试，它就会自动按照这套标准来，而不是每次都瞎写一通。

注意，Skills 是一个 [开放标准](https://agentskills.io/)，不仅在 Github Copilot 里能用，Claude Code、Cursor 等 AI 编程工具中也能用，一套 Skill 多处复用，这也是它能火的原因之一。

从哪儿搞到 SKills 呢？

大多数情况下，直接从网上安装别人开发好的 SKills 就可以了。比如 [鱼皮 AI 导航的 Skills 大全](https://ai.codefather.cn/skills) 里有我给大家精选的技能包，也可以去 GitHub 上的 [awesome-copilot](https://github.com/github/awesome-copilot) 仓库逛逛，社区贡献了不少实用的 Skills，拿来就能用。

![](https://pic.yupi.icu/1/image-20260306111855649.png)

在 VSCode 中，你可以通过对话框的 Skills 设置按钮，查看和管理本地已有的 SKills：

![](https://pic.yupi.icu/1/image-20260306111219014.png)

当然，你也可以自己创建 Skills，可以通过可视化界面选择安装位置，比如安装在当前项目下（仅本项目能用），还是安装到用户目录下（整个电脑的所有项目都能用）：

![](https://pic.yupi.icu/1/image-20260306112025446.png)

创建技能的核心是编写 `SKILL.md` 技能描述文件，比如创建一个「Web 应用测试」技能，文档内容示例如下：

```markdown
---
name: webapp-testing
description: 使用 Playwright 测试 Web 应用的指南，当需要创建或运行浏览器测试时使用
---

# Web 应用测试指南

## 创建测试
1. 参考 [测试模板](./test-template.js)
2. 确定要测试的用户流程
3. 在 tests/ 目录创建新的测试文件
4. 使用 Playwright 的定位器来查找元素

## 运行测试
运行命令：npx playwright test

## 最佳实践
- 为动态内容使用 data-testid 属性
- 保持测试独立和原子化
- 使用 Page Object Model 组织复杂页面的测试
```

![](https://pic.yupi.icu/1/image-20260306112358350.png)

Skill 创建好之后，你可以在对话区域里用 `/webapp-testing` 斜杠命令手动调用它，也可以让 AI 根据任务自动匹配加载。

![](https://pic.yupi.icu/1/image-20260306112515795.png)

Skills 采用渐进式披露的设计，AI 只在需要时才加载相关 Skill 的内容，不会一次性把所有信息都塞进上下文，既节省 Token 又保持灵活。即使装了几十个 Skill 也不用担心上下文爆炸。



### 多种 Agent 运行方式

前面实战中，我们用的是本地 Agent，但其实 GitHub Copilot 支持 4 种 Agent 运行方式，适合不同的使用场景：

| 运行方式           | 特点                                         | 适用场景                                 |
| ------------------ | -------------------------------------------- | ---------------------------------------- |
| Local 本地         | 在 VSCode 中交互式运行，实时反馈             | 探索性任务、需要即时反馈的开发           |
| Background 后台    | 在本地后台自主运行，使用 Git worktree 隔离   | 需求明确的任务，你想边干别的边让 AI 干活 |
| Cloud 云端         | 在远程服务器运行，完成后自动提 PR            | 团队协作、不想占用本地资源的任务         |
| Third-party 第三方 | 接入 Anthropic Claude、OpenAI 等第三方 Agent | 想用特定 AI 厂商的能力                   |

你可以在 Chat 对话区域底部的下拉菜单中随时切换不同的运行方式：

![](https://pic.yupi.icu/1/image-20260306094253979.png)

有个骚操作是，你可以在不同的 Agent 之间移交任务。比如先用本地 Agent 做个 Plan，觉得方案没问题了，一键移交给 Cloud Agent 去执行，它会自动创建分支、写代码、跑测试、最后提一个 Pull Request 给你的团队审查。

你还可以同时开多个 Agent Session，每个 Session 处理不同的任务，在 Chat 面板的 Sessions 列表中统一管理、查看状态、切换任务。

就像 Claude Code 可以同时开多个终端 Tab 一样，Copilot 的 Sessions 列表让你在一个面板里统一管理所有 AI 任务的状态，这是 GitHub 官方文档中重点推荐的工作流。

![](https://pic.yupi.icu/1/image-20260306112932393.png)



### Hooks - 自动触发的脚本

Hooks 允许你在 Agent 执行的关键节点自动运行自定义脚本。简单来说，就是在 Agent 工作流程的特定时机，自动执行你预设好的命令。

你可以在 VSCode 设置中查看和管理已配置的 Hooks：

![](https://pic.yupi.icu/1/image-20260306094814153.png)

目前支持的生命周期事件包括：

- PreToolUse：Agent 调用工具前触发，比如拦截 `rm -rf` 等危险命令
- PostToolUse：Agent 调用工具后触发，比如自动跑 Prettier 格式化代码
- SessionStart / Stop：Agent 会话开始和结束时触发（官方事件名分别是 SessionStart 和 Stop），比如在会话开始时自动注入项目上下文，会话结束时生成工作报告
- UserPromptSubmit：用户提交提示词时触发，比如审计用户请求、注入系统上下文
- SubagentStart / SubagentStop：子智能体启动和完成时触发，比如跟踪子任务的执行情况和资源消耗

举个例子，在项目的 `.github/hooks/` 目录下创建 JSON 配置文件，填入下列代码：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "type": "command",
        "command": "npx prettier --write \"$TOOL_INPUT_FILE_PATH\""
      }
    ]
  }
}
```

![](https://pic.yupi.icu/1/image-20260306113256929.png)

这样每次 Agent 调用工具修改了代码文件，都会自动跑一遍 Prettier 代码美化工具，保证代码风格统一。

Hooks 的应用场景很多，比如自动格式化代码、拦截危险命令（`rm -rf` 和 `DROP TABLE`，防止删库跑路）、记录每一次工具调用便于排查问题。而且 Hooks 的配置格式和 Claude Code 是兼容的，如果你之前在 Claude Code 里配过 Hooks，可以直接复用。



### Custom Instructions - 让 AI 遵循你的规范

自定义指令就是给 AI 定规矩。

你把编码规范、技术偏好、项目约定写到一个 Markdown 文件里，AI 在每次对话时都会自动遵循这些规则，不需要每次都重复说 “用 TypeScript 写”、“变量名不要用 a b c” 之类的。

其实这个概念和 AGENTS.md 类似，都是通过文件来告诉 AI 项目的规范和约定。区别在于 Copilot 的指令文件路径是 `.github/copilot-instructions.md`，而且支持更细粒度的文件模式匹配（类似 Cursor 的 Rules）。

创建指令的方式很简单，在对话区域的设置中打开「聊天指令」，然后选择创建位置：

![](https://pic.yupi.icu/1/image-20260306113751454.png)

或者手动在项目根目录下新建 `.github/copilot-instructions.md` 文件，填入内容即可，比如：

```markdown
# 项目编码规范

## 代码风格
- 使用语义化 HTML5 元素
- 优先使用 ES6+ 语法（const/let、箭头函数、模板字符串）
- 变量命名使用 camelCase，组件命名使用 PascalCase

## 技术偏好
- 前端框架优先用 React + TypeScript
- CSS 使用 Tailwind CSS
- 测试使用 Vitest

## 代码质量
- 函数和变量名要有意义，能自解释
- 复杂逻辑要加注释
- 用户输入和 API 调用要加错误处理
```

![](https://pic.yupi.icu/1/image-20260306114223424.png)

VSCode 支持两种指令类型。一种是全局生效的指令（Always-on），所有对话都会自动应用；另一种是基于文件模式匹配的指令（File-based），比如 `.tsx` 文件用 React 组件规范，`.test.ts` 文件用测试规范，只有匹配到对应文件时才生效。

像下面这种带 YAML 头部的结构，就是 File-based 指令的标准写法，通过 `description` 字段描述何时生效、`applyTo` 字段指定匹配的文件模式：

![](https://pic.yupi.icu/1/image-20260306121336765.png)

还有个小技巧，在对话区域里输入 `/init`，AI 会自动分析你的项目结构和代码风格，帮你生成一份自定义指令文件，省得自己从零写起。这个命令特别适合接手老项目、或者在已有项目上扩展功能的场景，AI 能帮你快速梳理出项目已有的编码习惯。

![](https://pic.yupi.icu/1/image-20260306100241500.png)



### Custom Agents - 给 AI 分配角色

自定义智能体就是给 AI 分配不同的角色。比如你可以创建一个安全审查员、测试工程师、架构师等角色，每个角色有自己的指令、工具权限和行为规则。

跟 Custom Instructions 自定义指令不一样的是，Instructions 是全局规则，不管你跟 AI 聊什么它都会遵循；而 Custom Agents 是角色切换，你选了某个角色后，AI 就只按那个角色的设定来工作，包括能用哪些工具、不能做哪些操作，都由角色定义。

创建自定义智能体的方式有两种。

一种是在对话区域的设置中打开「自定义智能体」，选择创建位置（当前项目或用户目录），VSCode 会自动创建对应的文件：

![](https://pic.yupi.icu/1/image-20260306114509869.png)

另一种方法是手动写一个 `.agent.md` 文件放在 `.github/agents/` 目录下。比如创建一个写作助手 `article.agent.md`：

```markdown
---
name: 写作助手
description: 帮助撰写和优化技术文章、项目文档
tools: ['search', 'codebase', 'fetch', 'editFiles']
---

# 写作助手

你是一位经验丰富的技术写作者，擅长把复杂的技术概念讲得通俗易懂。

## 写作风格
- 用口语化的表达，像跟朋友聊天一样
- 段落要短，避免大段文字堆砌
- 适当加入类比和例子帮助理解

## 重要规则
- 先列大纲，确认后再写正文
- 每段都要有明确的主题
- 技术术语第一次出现时要解释
```

![](https://pic.yupi.icu/1/image-20260306121541349.png)

保存后，在对话区域的智能体下拉菜单中就能看到这个写作助手了，选中它 AI 就会按照你定义的角色来工作。

![](https://pic.yupi.icu/1/image-20260306121613414.png)

自定义智能体还有一个更强大的玩法，叫 Handoffs（移交）。你可以在 Agent 文件中定义「下一步动作」按钮，实现智能体之间的任务接力。

比如 Plan 智能体出完方案后，底部出现一个「开始实现」按钮，点一下就自动切换到 Agent 模式开始编码，把方案的上下文完整传递过去：

```yaml
handoffs:
  - label: 开始实现        # 按钮上显示的文字
    agent: agent           # 移交给哪个智能体
    prompt: 按照上面的方案开始编码  # 自动填入的提示词
    send: false            # false 表示不自动发送，等你确认后再发
```

除了 Handoffs，你还可以编排多个专业智能体的协作流程。

假设你在做一个新功能，需要先调研项目里已有的代码模式，再动手写代码。你可以创建一个「功能开发」主智能体，让它先调用一个只读的「调研员」子智能体来分析代码库中的相关模块和设计模式，拿到分析结果后，再调用「编码员」子智能体按照分析出的模式来写新代码。这种多智能体编排在做复杂功能时特别实用，每个角色各司其职，比单个 AI 乱写一气靠谱得多。

VSCode 还支持 Claude 格式的 Agent 文件（放在 `.claude/agents` 目录），如果你之前用 Claude Code 创建过自定义 Agent，可以直接拿过来用，无缝兼容。



### Prompt Files - 可复用的提示词模板

Prompt Files（提示词文件）可以把你常用的任务封装成 **斜杠命令**，在对话中随时复用。

比如你经常需要生成 React 组件、执行安全审查、编写单元测试，每次都得重复输入类似的提示词，而有了 Prompt Files 之后就不用了。

跟自定义指令的区别是，自定义指令会自动应用到所有对话，而 Prompt Files 需要你手动在对话中输入 `/命令名` 来触发，更适合特定任务场景。

创建方式跟自定义指令完全类似，在对话区域的设置中打开「提示文件」，在弹出的对话框中选择「新建提示文件」：

![](https://pic.yupi.icu/1/image-20260306122919311.png)

然后选择创建位置（当前项目或用户目录），VSCode 会自动创建对应的文件：

![](https://pic.yupi.icu/1/image-20260306123109760.png)

你也可以直接在 `.github/prompts/` 目录下创建 `.prompt.md` 文件。举个例子，创建一个 `/gen-test` 命令来自动生成单元测试：

```markdown
---
description: 为当前文件生成单元测试
agent: agent
tools: ['search', 'search/codebase', 'edit/editFiles']
---
为 [${fileBasename}](${file}) 生成单元测试。

- 测试文件放在同目录下：${fileDirname}
- 命名为：${fileBasenameNoExtension}.test.ts
- 测试框架：${input:framework:jest or vitest}
- 参考项目的测试规范：[testing.md](../docs/testing.md)
```

这里面用到了一些变量，比如 `${file}` 会自动替换为当前打开的文件路径，`${input:framework}` 是指要从用户在对话框中输入的内容来获取值。

![](https://pic.yupi.icu/1/image-20260306123242156.png)

保存后，在对话框中输入 `/gen-test` 就能触发。你还可以在后面追加额外信息，比如 `/gen-test 只测试登录相关的函数`。

![](https://pic.yupi.icu/1/image-20260306123816437.png)



### Smart Actions - AI 快捷操作 

除了上面这些核心特性，Copilot 还在 VSCode 的各个角落埋了不少 AI 快捷操作，叫 Smart Actions。你不需要写提示词，右键菜单就能触发。

常用的有以下这些，可以先跳过，等需要的时候再回来看：

- 自动生成 Commit Message：在 Source Control 面板点一下小星星图标，AI 就根据你的代码改动自动生成提交信息
- 代码解释：选中一段代码，右键「Explain」，AI 帮你解释这段代码在干啥
- 生成测试：选中代码，右键「Generate Tests」，AI 帮你写单元测试
- 生成文档：选中代码，右键「Generate Docs」，AI 帮你写注释文档
- 修复错误：代码有报错时，AI 会自动弹出修复建议
- 代码审查：选中代码，右键「Review」，AI 给你做 Code Review
- 语义搜索：在搜索面板中启用 AI 搜索，按语义而非文本精确匹配来搜索代码
- AI 辅助重命名：重命名变量时，AI 会根据上下文给出建议的新名字

我自己平时用的最多的就是自动生成 Commit Message，再也不用绞尽脑汁想提交信息怎么写了。

![](https://pic.yupi.icu/1/image-20260306121819177.png)

这些小功能单个看起来不起眼，但用起来真的能省不少事。

恭喜，看到这里你就超过了 99% 的同学！



## 写在最后

总结一下，VSCode + GitHub Copilot 给我最大的感觉就是 **全面**。

实话说，论 Agent 编程的极致体验，Claude Code 还是更强一些；论新功能推出的速度和迭代节奏，Cursor 也一直走在前面。

但 Copilot 胜在它是 “六边形战士”，从代码补全到 AI 对话、从 Agent 编程到 MCP 生态、从自定义指令到智能体编排，AI 编程该有的能力它基本都有了，而且每个方面的体验都很丝滑。

此外，我估计很多同学在 AI 流行之前就一直在用 VSCode，现在装个插件就能无缝升级到 AI 编程，不用换编辑器、不用重新学操作、不用迁移配置，使用门槛是最低的。

感兴趣的同学可以去试试，记得先白票 30 天的 Pro 试用~ 而且如果你是在校学生，还可以通过 [GitHub Education](https://education.github.com/pack) 申请学生认证，认证通过后 Copilot Pro 直接免费用，不限时！我在学校的时候咋没有这种好事？

对了，如果你想用 GitHub Copilot 做更复杂的全栈项目实战，可以跟着鱼皮最新的 [AI 热点监控项目](https://www.codefather.cn/course/2026625439052627970) 练手，我帮大家测过了，企业级大项目 Copilot 也完全能 hold 住。

![](https://pic.yupi.icu/1/image-20260304102630302.png)

就写到这，觉得有用的话记得收藏这篇文章，也欢迎在评论区聊聊你喜欢用哪款 AI 编程工具，帮到更多同学做选择。



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)