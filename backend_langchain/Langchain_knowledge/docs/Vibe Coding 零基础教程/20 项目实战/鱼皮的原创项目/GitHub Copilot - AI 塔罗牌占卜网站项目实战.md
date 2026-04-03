# GitHub Copilot - AI 塔罗牌占卜项目实战

这是一个利用 VSCode + GitHub Copilot 的 Plan 模式 + Agent 模式，从 0 到 1 开发的 AI 塔罗牌占卜网站。通过这个项目，你可以快速体验 GitHub Copilot 的核心 AI 编程能力，几分钟就能做出一个有翻牌动画、AI 占卜解读、神秘华丽界面的小项目。

预计 30 分钟学完，适合零基础入门 VSCode + GitHub Copilot 的 AI 编程。

如果你想了解 GitHub Copilot 的更多核心特性（MCP、Agent Skills、自定义智能体等），可以阅读本教程编程工具板块「工具实战」中的《VSCode + GitHub Copilot：微软全家桶的 AI 编程实战》。



## 项目介绍

用户输入一个问题（比如 “我最近的爱情运势如何”），点击「开始占卜」后，展示 3 张塔罗牌的翻牌动画，翻牌完成后调用 DeepSeek 大模型 API，根据抽到的牌生成 AI 占卜解读。

界面采用深紫色主题配金色纹理，星空背景，搭配流畅的翻牌动画效果，响应式布局手机也能用。

技术栈很简单：HTML + CSS + JavaScript，调用 DeepSeek API 生成占卜解读。

![](https://pic.yupi.icu/1/image-20260305151413007.png)



## 安装 VSCode + GitHub Copilot

在开始做项目之前，需要先安装好开发工具。

1）进入 [VSCode 官网](https://code.visualstudio.com/) 下载安装包，直接傻瓜式安装。

![](https://pic.yupi.icu/1/image-20260305141229310.png)

2）打开 VSCode，点击左侧「扩展市场」图标，搜索 "GitHub Copilot"，安装官方的 AI 编程插件。

![](https://pic.yupi.icu/1/image-20260305141416199.png)

你还可以根据需要，选择安装 Chinese 汉化插件：

![](https://pic.yupi.icu/1/image-20260305153013870.png)

3）安装完后，点击 VSCode 底部状态栏的 Copilot 图标，按照提示登录 GitHub 账号就行了。

![](https://pic.yupi.icu/1/setup-copilot-status-bar.png)

如果你还没有 Copilot 订阅，会自动进入 **Copilot Free 免费计划**，每月有一定的 AI 对话和代码补全额度，零门槛上手。想体验完整功能的话，Copilot Pro 支持新用户免费试用 30 天。如果你是在校学生，还可以通过 [GitHub Education](https://education.github.com/pack) 申请学生认证，认证通过后 Copilot Pro 直接免费用。

安装配置搞定后，就可以开始做项目了。



## 开发流程

这个项目完美展示了 GitHub Copilot 的 Plan + Agent 工作流。

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

你只要像聊天一样把自己的想法告诉 AI 就好，比如希望调用 DeepSeek 大模型的 API：

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

几分钟后，Agent 不仅完成了开发任务，还用 Python 启动了个 Web 服务器，帮忙运行了网站。

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

Agent 会自动定位到对应的代码并精准修改，改完刷新预览就好。

![](https://pic.yupi.icu/1/image-20260305152037670.png)

整个过程，从写需求到出成品，也就几分钟。搁以前，我要是自己从零写这么个带动画的占卜网站，怎么着也得搞一下午。

你还可以继续跟 AI 对话来增加功能，整个过程中一定要注意 **上下文的用量**，如果满了 AI 可能会断片儿失忆，开始乱改。

![](https://pic.yupi.icu/1/image-20260305152200805.png)

因此，在上下文快满的时候，最好让 AI 把当前项目的信息沉淀为文档。这样之后每次打开新的 AI 对话框时，只要把历史文档交给 AI，就能快速找回记忆。 



## 项目收获

通过这个小项目，你可以学到：

- 如何使用 GitHub Copilot 的 Plan 模式进行需求分析和方案设计
- 如何使用 Agent 模式让 AI 自主完成代码开发
- 如何调用 DeepSeek 大模型 API
- 如何用 CSS 实现翻牌动画和星空背景效果
- 如何在 AI 编程中进行人工插手和精细调整
- 如何管理上下文用量，避免 AI 断片儿

这个项目虽然小巧，但完整展示了 Vibe Coding 的核心工作流 —— 用自然语言描述需求，AI 帮你设计方案和编写代码，人工审核和调整细节。掌握了这个流程，你就可以用同样的方式去做更复杂的项目了。
