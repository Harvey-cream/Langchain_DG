# AI IDE 插件

> 在熟悉的编辑器中加入 AI 能力



你好，我是鱼皮。

在前面的文章中，我们学习了 AI 代码编辑器和 AI 命令行编程工具。

但如果你有编程基础，已经习惯用 VS Code / IntelliJ IDEA 等集成开发环境（IDE）了，不想换编辑器，又想 Vibe Coding，怎么办呢？

**IDE AI 插件** 就是你要找的答案。

这篇文章，我会介绍最主流的 IDE AI 插件，帮你在熟悉的编辑器中加入 AI 能力。



## 一、为什么选择 IDE 插件？

在了解具体插件之前，我们先来搞清楚：IDE 插件和 Cursor 有什么区别？为什么要用插件？

Cursor 是一个独立的编辑器，虽然基于 VS Code，但是一个完整的软件。而 IDE 插件是安装在你现有编辑器（VS Code、IntelliJ IDEA 等）上的扩展，不需要换编辑器。

打个比方，Cursor 像买了一辆新车，配好了所有功能；IDE 插件像给你现在的车加装了新功能，车还是原来那辆。

IDE 插件的优势很明显。首先是无需切换编辑器，如果你已经习惯了某个编辑器，配置好了各种插件和快捷键，不想重新适应新环境，那用插件是最好的选择。

而且可以根据需要安装不同的插件，自由组合，不喜欢某个插件随时可以卸载换另一个。很多插件是开源免费的，或者可以使用自己的 API Key，成本更可控。

如果你是新手，还没有固定的编辑器习惯，可能直接用 Cursor 会更简单。但如果你已经是某个编辑器的老用户，插件会是更好的选择。



## 二、Cline 最强大的开源 AI 插件

[Cline](https://cline.bot/) 是目前功能最强大的开源 AI 编程插件，被称为 开源版 Cursor。

Cline 最大的优势是 **跨平台支持**，不仅支持 VS Code，还支持 JetBrains 系列的 IntelliJ IDEA、PyCharm、WebStorm 等多个编辑器。

![](https://pic.yupi.icu/1/image-20260108222935455.png)

它完全开源免费，支持 Claude、GPT、Gemini、DeepSeek 等各种大模型，还可以部署 MCP 服务扩展功能。不仅能对话生成代码，还能自主执行命令、修改多个文件、使用浏览器，总之功能非常全面。

下面来演示一下 Cline 的使用流程。



### VS Code 中使用 Cline

比如我想用 Cline 在 VS Code 中创建一个 React 项目。

1）在 VS Code 中打开扩展商店，搜索 "Cline"，点击安装。

![](https://pic.yupi.icu/1/image-20260108223139213.png)

2）安装后，点击侧边栏的 Cline 图标，可以直接免费使用，也可以使用你自己的大模型 API Key。

![](https://pic.yupi.icu/1/image-20260108223220642.png)

3）点击下一步后，Cline 会引导你创建一个账号，使用 GitHub 或邮箱注册登录就好。

4）搞定账号后，就可以愉快使用了，直接在 Cline 面板中输入需求：

```
创建一个 React + TypeScript 项目，包含：
- 首页
- 关于页面
- 导航栏
- 使用 React Router
```

![](https://pic.yupi.icu/1/image-20260108223531152.png)

5）接下来 Cline 会自动运行命令、安装必要的依赖、创建各个组件文件、配置路由、修改样式。整个过程你只需要确认每一步操作，或者直接让它全自动执行。

![](https://pic.yupi.icu/1/image-20260108223742056.png)



### JetBrains 中使用 Cline

如果你是 JetBrains IDE 的用户，在 IDE 中打开 Settings → Plugins，搜索 "Cline"，安装即可。使用方式和 VS Code 版本完全一样。

![](https://pic.yupi.icu/1/image-20260108224135571.png)



## 三、AI 编程助手 IDE 插件

除了 Cline，还有一些其他的 AI 编程助手 IDE 插件也值得了解。



### Claude Code 官方扩展

Claude Code 是 Anthropic 推出的 AI 编程助手，原本是独立的命令行工具。而 [Claude Code VS Code 扩展](https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously) 能让你在代码编辑器中直接使用 Claude Code，不用额外打开终端。

这个扩展的优点是提供了图形界面，你可以通过侧边栏面板和 Claude 对话，能够灵活输入文字。

![](https://pic.yupi.icu/1/image-20260116124614180.png)

当 AI 修改代码时，你能在编辑器里实时看到变化，并且自动显示 diff 对比，让你清楚地知道 AI 改了哪些地方。

![](https://pic.yupi.icu/1/image-20260116124700221-20260118135011240.png)

我经常用它来重构代码、修复 Bug、添加新功能。它还支持多会话并行，也就是说你可以同时让多个 Claude 代理处理不同的任务，比如一个负责前端，一个负责后端，大大提高开发效率。

![](https://pic.yupi.icu/1/image-20260116124928547.png)



### GitHub Copilot

[GitHub Copilot](https://github.com/features/copilot) 是最成熟的 AI 编程助手之一，支持 VS Code、JetBrains 全系列、Vim、Neovim 等多个编辑器。

除了代码补全和 Chat 对话之外，GitHub Copilot 现在已经支持了非常强大的 Agent 模式、Plan 模式、MCP 服务管理、Agent Skills 技能包、自定义智能体、Hooks 自动化脚本等核心特性，体验上堪称 “六边形战士”。

![](https://pic.yupi.icu/1/image-20260108225417720.png)

它的优点是成熟稳定、代码补全质量高、跨平台支持、支持最新的 AI 大模型随便切换。最关键的是，学生和开源贡献者可以免费使用，新用户还有 30 天 Pro 免费试用。

鱼皮写了一篇非常详细的 VSCode + GitHub Copilot 实战教程，涵盖了从安装到核心特性的方方面面，感兴趣的可以去本教程编程工具板块的「工具实战」中阅读《VSCode + GitHub Copilot：微软全家桶的 AI 编程实战》。



### JetBrains AI Assistant

[JetBrains AI Assistant](https://www.jetbrains.com/ai-assistant/) 是 JetBrains 官方推出的 AI 编程助手，专门为 JetBrains IDE 优化，刚出的时候鱼皮还在阿里云栖大会现场给大家做过这个的分享哈哈。

![](https://pic.yupi.icu/1/image-20260108230013824.png)

它不仅有代码补全，还能生成测试、解释代码、重构代码、生成文档等。而且和 IDE 的各种功能深度集成，比如调试、重构、测试、生成提交信息等。

![](https://pic.yupi.icu/1/image-20260108225718180.png)

优势是官方出品，和 IDE 集成最好，支持多种 AI 模型，功能全面。缺点是需要订阅 JetBrains 的付费计划。



### Continue

[Continue](https://www.continue.dev/) 是开源的 AI 编程插件，功能和 Cline 类似但更轻量。支持多种 AI 模型，有代码补全、对话、代码编辑等功能，界面比较简洁，上手容易。完全免费，支持 VS Code 和 JetBrains。

![](https://pic.yupi.icu/1/image-20260108230116299.png)



### Amazon Q Developer

[Amazon Q Developer](https://aws.amazon.com/q/developer/)（原名 CodeWhisperer）是亚马逊推出的 AI 编程助手。

特点是与 AWS 服务深度集成、支持多种 IDE（VS Code、JetBrains 等）、有免费版本、代码安全扫描。适合使用 AWS 服务的开发者、需要代码安全扫描的团队。



## 四、IDE 扩展插件

除了 AI 编程助手插件，还有一些实用的 IDE 扩展插件。

这些插件虽然不是 AI 工具，但配合 AI 编程使用，能让你的开发效率更上一层楼。



### GitLens

GitLens 能让你更直观地查看 Git 代码的修改历史，把鼠标放到任意代码行上就能看到这行代码的作者、提交时间等信息。

![](https://pic.yupi.icu/1/image-20260116125445257.png)



### Office Viewer

Office Viewer 能在编辑器里直接预览和编辑各种文档，包括 Markdown、Excel、Word、PDF 等，不用来回切换窗口。

![](https://pic.yupi.icu/1/image-20260116130527681.png)



### ESLint 和 Prettier

ESLint 是代码质量检查工具，Prettier 是代码格式化工具。这两个插件能帮你保持代码规范，避免 AI 生成的代码出现格式问题。

![](https://pic.yupi.icu/1/image-20260116131356553.png)



### Error Lens

Error Lens 能让错误信息直接高亮显示在代码行尾，一眼就能看到哪里有问题。

![](https://pic.yupi.icu/1/image-20260116140619858.png)



### Console Ninja

Console Ninja 能让你在编辑器里直接看到代码的运行结果，不用频繁切换到浏览器控制台。

![](https://pic.yupi.icu/1/image-20260116141109420.png)



### Supermaven

[Supermaven](https://supermaven.com/) 是一个专注于代码补全的插件，最大的特点是 100 万 Token 的上下文窗口，补全速度极快，准确度也很高。

![](https://pic.yupi.icu/1/image-20260108230146505.png)





## 五、怎么选择 AI IDE 插件？

- 如果想要最强大的功能（智能体、多文件编辑），选 Cline。它支持 VS Code 和 JetBrains，完全免费，功能接近 Cursor。
- 如果想要全面的 AI 编程体验，选 GitHub Copilot。它不仅代码补全质量最高，现在还支持 Agent 模式、MCP、Skills 等核心能力，而且学生和开源贡献者可以免费使用。
- 如果你已经订阅了 JetBrains，直接用 JetBrains AI Assistant，因为它和 IDE 的集成最好。
- 如果想要轻量级、开源免费的工具，选 Continue。它功能和 Cline 类似但更简洁，支持多种 AI 模型，有代码补全、对话、代码编辑等能力，上手容易。
- 如果你习惯用国产工具，也可以试试智谱 CodeGeeX、通义灵码等国产 AI 插件，对国内网络环境更友好，部分功能免费。

我之前一直沉迷于 Cursor 和 Claude Code，最近做新项目认真体验了一把 GitHub Copilot，发现它在 Agent 编程、MCP 管理、Skills 集成等方面的体验确实很好。如果你本来就在用 VSCode，装个 Copilot 插件就能无缝升级到 AI 编程，使用门槛是最低的。当然，每个人的使用习惯不同，建议都试试再做选择。



## 写在最后

到目前为止，鱼皮已经把主流的 AI 编程工具介绍完了，建议大家都体验一下，选择适合自己的才是最好的。

在下一篇文章中，我会介绍最近超火的 AI 数字员工 OpenClaw，手把手带你安装配置，体验 AI 帮你操控电脑的感觉。

加油！




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
