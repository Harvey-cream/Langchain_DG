# OpenCode：开源免费的 AI 命令行工具实测

你好，我是程序员鱼皮。

Claude Code 一直是大家公认的 AI 编程命令行工具 Top 1，在 AI 和程序员圈子里几乎是神一般的存在。

![](https://pic.yupi.icu/1/happy-new-year-claude-coders-v0-o2quvbl99lag1.png)

但是，这狗玩意儿对中国用户可不太友好……

首先，如果你想要使用 Claude Code，就必须要有特殊的网络 + 官方账号，否则就会看到一片红。

![](https://pic.yupi.icu/1/cannotuseclaude.png)

此外，2025 年 9 月，Anthropic 公司不知道抽什么风，突然宣布 **全面禁止中国控股企业使用 Claude 服务**，不仅包括中国大陆企业，连海外中资控股超过 50% 的公司都在封禁范围内！

甚至 Anthropic 还特别点名了中国，把咱们称为 **敌对国家**！

![](https://pic.yupi.icu/1/image-20250905164631315.png)

天下苦 Claude Code 久矣！

但是最近我身边很多程序员朋友开始从 Claude Code 转向了另一个工具，正是突然大火的开源项目 OpenCode。

![](https://pic.yupi.icu/1/image-20260107174223010.png)

这玩意只用了半年的时间，就在 GitHub 上涨到了 5.2w Star！

这是个什么概念？比我在 GitHub 上开源的几十个项目的总和加起来都多！慕了慕了……

![](https://pic.yupi.icu/1/opencodestarhistory.png)

OpenCode 到底是什么？凭什么这么火？



## 啥是 OpenCode？

[OpenCode](https://opencode.ai/) 是一款 100% 开源的 AI 编程命令行工具，可以在 **终端、IDE、甚至桌面应用** 中使用。

![](https://pic.yupi.icu/1/screenshot.png)

你可能会问：这玩意儿跟 Claude Code 有啥区别？

试试不就知道了？

接下来我带大家实操一下，从零开始安装、配置、到实际写代码，一条龙服务~



## 从 0 开始上手 OpenCode

### 1、安装运行 OpenCode

直接进入 OpenCode 官网，复制一行命令：

![](https://pic.yupi.icu/1/image-20260107174407894.png)

命令如下：

```bash
curl -fsSL https://opencode.ai/install | bash
```

然后在终端中执行，就可以完成安装了。

安装完成之后，输入 `opencode` 进入程序，接下来你就可以愉快地使用了~

![](https://pic.yupi.icu/1/image-20260107174646918.png)

先来个经典的 Hello World，AI 成功给出了回复。

![](https://pic.yupi.icu/1/image-20260107174755331.png)

恭喜，到这里你已经掌握了 OpenCode 的 70% 了。



### 2、选择模式和模型

OpenCode 支持 2 种模式，默认是 Build 模式，用来构建应用、生成代码。

按一下 Tab 键，就可以切换到 Plan 模式，用于生成执行计划。

![](https://pic.yupi.icu/1/image-20260107174952823.png)

按一下 `Ctrl + p` 键，可以打开命令面板，里面有几十个内置命令。我们先来试着切换一下大模型：

![](https://pic.yupi.icu/1/image-20260107175255527.png)

默认提供了 4 个免费模型：

![](https://pic.yupi.icu/1/image-20260107175409282.png)

好家伙，连智谱最新的 GLM-4.7 竟然也免费？那我的 Coding Plan 套餐不是白开了？

![](https://pic.yupi.icu/1/image-20260107175513490.png)

除了免费的模型外，OpenCode 支持超多的 AI 模型，你可以自由选择：

![](https://pic.yupi.icu/1/image-20260107175614359.png)

选中模型后，配置自己的 API Key 就好了：

![](https://pic.yupi.icu/1/image-20260107175657296.png)

如果你之前有 **Claude Pro/Max 订阅账号**，可以直接登录使用，无缝从 Claude Code 迁移过来。

![](https://pic.yupi.icu/1/image-20260107175745963.png)



### 3、快捷指令

OpenCode 支持斜杠命令，输入 `/`，能看到很多操作，比如查看模型列表、查看 Agents、管理 MCP、切换主题等等：

![](https://pic.yupi.icu/1/image-20260107175926346.png)

支持几十个不同的主题，颜值都挺高的，从这点也能看出来 OpenCode 很注重用户的体验：

![](https://pic.yupi.icu/1/image-20260107180108430.png)

输入 `@` 可以快速关联目录文件，给 AI 添加上下文： 

![](https://pic.yupi.icu/1/image-20260107182710150.png)



### 4、交互体验

相比于 Claude Code，OpenCode 真是把命令行的交互体验拉满了，甚至我觉得它是一个伪装成命令行的桌面应用。

你可以点击某条消息，然后会弹出一个消息动作框，你可以撤回消息和 AI 的回复，也可以复制、或者基于当前对话新开一个对话框。

![](https://pic.yupi.icu/1/image-20260107180609525.png)

你可以通过鼠标上下滚动来切换选单，并且可以直接通过鼠标点击进入下一步。

你可以按 `Ctrl + p` 键打开命令面板，然后开启侧边栏：

![](https://pic.yupi.icu/1/image-20260107181100523.png)

然后界面就变成了这样，你管这叫命令行？

![](https://pic.yupi.icu/1/image-20260107181218259.png)



### 5、LSP 支持

细心的你一定看到了，右边的侧边栏有个 `LSP`，这是什么鬼东西？老色批？

LSP（Language Server Protocol 语言服务器协议）是微软开发的一种通信协议，用于让代码编辑器和语言服务器之间进行通信。

简单来说，**LSP 就是让编辑器看懂代码的技术。**

比如你在 VS Code 里写代码，输入 `console.` 它会自动提示 `log`、点击函数名能跳转到代码定义、写错代码会画红线提醒。这些代码编辑器的功能，背后都是 LSP 在干活。

OpenCode 支持 LSP，意味着 AI 能真正理解你的代码结构，而不是把代码当普通文字瞎猜，改起来更精准。

比如我让 AI 介绍我的 AI 答题平台项目中最有价值的代码，LSP 就派上用场了。它能帮 AI 快速定位某段代码在哪里被调用、引用了哪些变量，而不是让 AI 傻傻地全局搜索文本。

![](https://pic.yupi.icu/1/image-20260107181807464.png)



### 6、回到之前的会话

如果你不小心关闭了 OpenCode，不用担心，可以打开命令面板，选中 “Switch session” 切换会话：

![](https://pic.yupi.icu/1/image-20260107183241477.png)

就能回到之前的聊天了：

![](https://pic.yupi.icu/1/image-20260107183320692.png)



## 桌面版 OpenCode

即使 OpenCode 支持了这么多改进用户体验的交互，但我估计大多数同学还是不喜欢小黑框的。

没关系，OpenCode 还提供了桌面应用版本！macOS、Windows、Linux 全端支持，这是真的要卷死 Claude Code 的节奏啊……

> 指路：https://opencode.ai/download

![](https://pic.yupi.icu/1/image-20260107182151987.png)

不过当我怀着满腔热血安装并打开它时，竟然报错了！

![](https://pic.yupi.icu/1/image-20260107183123854.png)

经过一番排查，发现原来是我开了代理，关闭之后就正常运行了。

![](https://pic.yupi.icu/1/image-20260107183605119.png)

但是用惯了 Cursor，这个交互体验真的有点敷衍了，不推荐大家使用。



## OpenCode 扩展能力

到目前为止，我觉得 OpenCode 在前端用户体验上全方面碾压 Claude Code，而且 OpenCode 完全兼容 Claude Code 的 Skills 系统！

Skills 是一种给 AI 准备的能力扩展包。你可以把它理解成给新同事准备的工作交接文档，里面包含任务执行方法、工具使用说明、模板素材等。

比如你可以创建一个 `公司代码规范 Skill`，把代码风格、命名规则、注释要求等写进去。之后 Claude Code 生成的代码就会自动遵循这些规范，不用每次都重复说明。

根据官方文档，OpenCode 会自动搜索这些位置的 Skills：

- `.opencode/skill/<name>/SKILL.md`（项目目录）
- `~/.config/opencode/skill/<name>/SKILL.md`（用户目录）
- `.claude/skills/<name>/SKILL.md`（Claude Code 兼容）
- `~/.claude/skills/<name>/SKILL.md`（Claude Code 兼容）

也就是说，如果你之前给 Claude Code 创建过自定义 Skills，直接拿过来就能用！又是无缝迁移。



## Oh My OpenCode 开挂插件

如果你觉得 OpenCode 还不够强，可以试试 `Oh My OpenCode` 这个开源的 OpenCode 增强插件，已经 1w Star 了。

> 项目地址：https://github.com/code-yeongyu/oh-my-opencode

![](https://pic.yupi.icu/1/image-20260107184457429.png)

这个插件有多牛？看看用户评价：

> "It made me cancel my Cursor subscription."（它让我取消了 Cursor 订阅）
> 
> "Knocked out 8000 eslint warnings with Oh My Opencode, just in a day"（一天内用它解决了 8000 个 eslint 警告）



Oh My OpenCode 的核心功能是引入了一个叫 **Sisyphus** 的智能体编排系统。

我特地去搜了一下：

> 西西弗斯（Sisyphus）是古希腊神话中一位因欺骗众神、挑战权威而被诸神惩罚的国王，他的惩罚是永无止境地将一块巨石推上山顶，而石头一到山顶便会滚落，如此周而复始，象征着徒劳无功、永无休止的任务，也代表着一种对荒诞命运的抗争精神。

这个系统可以：

1. 并行调度多个 AI 模型：比如让 GPT debug 的同时让 Gemini 写前端
2. 自动任务管理：不完成任务不让停，像西西弗斯推石头一样锲而不舍
3. 智能代码审查：自动检测并清理 AI 生成的冗余注释
4. LSP 深度集成：提供重命名、跳转定义等 IDE 级功能

简单来说，Sisyphus 就是一个 AI 监工，它能同时指挥多个 AI 模型干活，还会盯着它们把任务做完。

![](https://pic.yupi.icu/1/omo.png)

虽然官方说用一行命令就能完成安装，但我建议你先安装 bun，再执行 npx 来安装，否则可能会报错。

```bash
npm install bun -g
npx oh-my-opencode install
```

安装过程中，可能会问你有没有某些模型的订阅，我反正啥都没有，一直选 "No" 就行了：

![](https://pic.yupi.icu/1/image-20260107185251337.png)

安装完成后，再次进入 OpenCode，之后只需要在你的提示词里加上 `ultrawork`（或 `ulw`）这个开挂咒语，就能激活全部增强功能。自动调度多个 AI 模型同时工作、深度探索代码库、锲而不舍地执行。

下面我们试试看，正好来验证一下 OpenCode 做项目的能力如何？能不能把 Claude Code 一脚踹飞？



## 实战项目 - 用 OpenCode 做个 AI 健康助手

最近蚂蚁集团的 `蚂蚁阿福` AI 健康助手火了，地铁口、公司楼下的电视广告中随处可见何炅老师的身影。

![](https://pic.yupi.icu/1/mayiafuad.jpeg)

虽然我还没有用过它，但是听说它可以通过拍皮肤、拍报告提供 AI 初诊，还能智能回答医学科普和治疗建议。

那我们也来做个类似的健康小助手网站吧！

前有蚂蚁阿福，今有鱼皮阿坤。

![](https://pic.yupi.icu/1/image-20260107194117758.png)

先分析一下，我们要做的是包含前端 + 后端的全栈项目，而且后端还需要调用 AI 大模型来生成内容。

这里我选择用 **Vercel AI Gateway** 来实现 AI 能力，这是一款简单易用的 AI 网关。

![](https://pic.yupi.icu/1/1760687990497-90720fbb-0df6-4ede-87b8-64b8702994e9-20251028181254840.png)

什么是 AI 网关？

简单来说，它就像是火车站的检票口，你的应用发来的请求先经过网关，网关帮你处理认证、限流、监控等一系列复杂的操作，然后把请求转发给 AI 大模型。

![](https://pic.yupi.icu/1/1761645642401-683e786e-3e06-420a-abce-cd43f7bfa901.png)

而且 Vercel AI Gateway 支持对接 500 多个大模型，还有免费额度，非常适合学习和小项目。

> 指路：https://vercel.com/ai-gateway



1）首先你需要注册登录 Vercel，然后在控制台创建 API Key，注意不要泄露哦：

![](https://pic.yupi.icu/1/1760688078133-7b91b6f3-2fc4-4bb4-b2c1-d517699f0968-20251028181254879.png)



2）启动 OpenCode，切换模型到编程能力很强、并且免费的 GLM-4.7，然后输入这段提示词：

```markdown
你是一位专业的程序员，请帮我开发《每日健康小助手》网站，用户可以通过和 AI 聊天来记录和管理每日健康状态。

## 开发要求

1. 需要包含完整的前端和后端，后端使用 Node.js
2. 使用 Vercel 的 AI Gateway 实现 AI 能力，需要先通过官方文档来获取用法：https://vercel.com/docs/ai-gateway/getting-started
3. 以完成核心功能为目标，确保项目可以正常运行
4. 整体网站界面采用清新的绿色健康风格，响应式适配各种尺寸的设备
5. AI 需要主动询问用户的健康状况，比如睡眠、运动、饮食等
```

点击发送后，OpenCode 会自动使用网页抓取工具读取 Vercel AI Gateway 的官方文档，学习最新的用法：

![](https://pic.yupi.icu/1/image-20260107190151933.png)

大概 5 分钟左右，AI 就完成了全部代码的生成，并且自动安装了依赖。

![](https://pic.yupi.icu/1/image-20260107190629349.png)



3）我直接把之前拿到的 Vercel 的 API Key 提供给 AI，让它帮我启动项目：

![](https://pic.yupi.icu/1/image-20260107190751628.png)



4）启动项目成功后，打开浏览器访问 `localhost:3000`，测试一下效果。

结果报错了！无法调用 AI。

![](https://pic.yupi.icu/1/image-20260107191838608.png)



可能是 AI 对 Vercel AI Gateway 文档的理解不到位，导致写错了调用 AI 的代码。于是我再次把文档输入给 AI，让它再战一次：

![](https://pic.yupi.icu/1/image-20260107191719979.png)

结果又报错了，明明我已经给 AI 提供了 API Key，系统还是报错 “缺少 API Key”。

于是我又调了一次 AI，告诉它 “这个 key 我之前已经提供给你了”。

![](https://pic.yupi.icu/1/image-20260107192718301.png)

经过大概 5 次左右的报错和修复，仍然不能正常使用！我麻了啊……

![](https://pic.yupi.icu/1/image-20260107193542108.png)

于是，我有一个鬼点子：既然要跟 Claude Code 比较，那我不妨尝试用 Claude Code 修复这个 OpenCode 解决不了的问题？

![](https://pic.yupi.icu/1/image-20260107193829543.png)

试试看！输入提示词：

```markdown
现在项目后端 AI 功能不可用
请参考 https://vercel.com/docs/ai-gateway/getting-started 文档
帮我修复后端，确保项目能正常运行
```

![](https://pic.yupi.icu/1/image-20260107193701784.png)

Claude Code 成功修复了问题，终于能够正常使用了：

![](https://pic.yupi.icu/1/image-20260107194915666.png)

💡 注意，如果你遇到了调用 AI 网络超时的问题，可以让 AI 把调用的 baseURL 改为 https://ai-gateway.vercel.sh/v1

之前类似的任务我用 Claude Code / Cursor + GLM，不到 10 分钟就搞定了。这次竟然花了 20 分钟左右，还要经过来回拉扯，才能正常使用。

这让我不得不怀疑 OpenCode 的能力了。而且感觉 GLM 大模型在 OpenCode 中好像变笨了，不知道是不是我的错觉…… 

不行，大家把 OpenCode 吹得这么牛批，我得再试试，一定是我用法的问题！

![](https://pic.yupi.icu/1/image-20260107195050357.png)

### Ultrawork 模式

还记得前面提到的 `ultrawork`（或 `ulw`）开挂咒语么？搞起！

![](https://pic.yupi.icu/1/image-20260107195327425.png)

进入战斗状态了：

![](https://pic.yupi.icu/1/image-20260107195346575.png)

可以查看子代理运行详情，先按 `Ctrl + x` 键，再按方向键来查看不同的代理。

而且当后台任务完成时，会有一个提示。可以看到 “研究 Vercel AI SDK 对话模式” 的任务已经完成。

![](https://pic.yupi.icu/1/image-20260107195605772.png)

不过你猜怎么着？我等了将近 10 分钟，任务还没结束……

看看这个任务列表，需要这么复杂吗？连数据库都给我干出来了？

![=](https://pic.yupi.icu/1/image-20260107200237753.png)

我已经没耐心等下去了，毁灭吧！

看来这种不算太复杂的工作并不能发挥出多代理的优势。就像你只是要打印一张纸，没必要发动全公司的人，有的研究打印的纸张类型、有的研究打印机的状态、有的研究怎么打印姿势更优雅。



## 最后

经过上述简单的测试，我暂时对 OpenCode 保持观望状态。

前端做的确实很不错，但后端的能力感觉跟 Claude Code 还有差距。

如果只是追求前端使用方便，那我为什么不用 Cursor？

![](https://pic.yupi.icu/1/image-20260107200720088.png)

不过 OpenCode 的成功说明了一个道理：**谁离用户近、谁能发现痛点，谁就有超越巨头的机会。**

Claude Code 确实很强，但它对中国用户的封禁，给了开源社区一个绝佳的机会。OpenCode 抓住了这个痛点，用更开放的方式赢得了用户的心。

虽然效果有待提高，但毕竟 OpenCode 完全开源免费，对于喜欢折腾的程序员来说，可定制性更强。你甚至可以 fork 一份自己魔改，想怎么玩就怎么玩。

OK，就聊到这里。你用过 OpenCode 吗？欢迎评论区聊聊你的体验~



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
