# 本地安装 OpenClaw

> 零基础也能搞定的 OpenClaw 本地安装教程

你好，我是鱼皮。这篇文章手把手教你在自己的电脑上安装 OpenClaw，哪怕你完全没学过编程，只要跟着做，也能成功养虾 🦞~

最近特别流行养龙虾，不是真的龙虾，而是一个叫 OpenClaw 的 AI 智能助手。

![](https://pic.yupi.icu/1/openclaw%E7%8E%B0%E8%B1%A1.jpg)

你可以把它理解成一个住在你电脑里的 AI 员工，它不像普通的 AI 聊天机器人只能动嘴皮子，而是真的能帮你干活，读写文件、操作浏览器、执行命令、甚至搭建网站，通通不在话下。

![](https://pic.yupi.icu/1/image-20260310160613289.png)

OpenClaw 的火爆程度远超我的想象，从 2025 年 11 月上线，仅用了大约 120 天就登顶 GitHub 星标 **历史第一**，累计拿下 29 万+ Stars，超过了 Linux、React 等一众前辈！

![](https://pic.yupi.icu/1/image-20260310161116303.png)

本来以为只是个技术圈的玩意儿，结果竟然火出圈了！

国内出现了几百块的上门代装服务，你没听错，**上门帮你装一个开源软件，收费几百**。

![](https://pic.yupi.icu/1/openclaw_setup_ondoor.jpeg)

更离谱的是，深圳腾讯大厦门口还搞了免费的线下 “装龙虾” 活动，近千人排队，四年级小学生、快 70 岁的老大爷都来了，场面跟老年人排队领鸡蛋似的。

![](https://pic.yupi.icu/1/openclaw%E4%B8%8A%E9%97%A8%E5%AE%89%E8%A3%85%E6%9C%8D%E5%8A%A1.jpeg)

但我总觉着吧，如果这玩意需要让别人操作你的电脑帮你安装，大概率你也不需要这玩意，装上后你也不会用。

实际上，在自己电脑上安装 OpenClaw 非常简单，鱼皮今天就提供一个保姆级本地安装教程，哪怕你完全没学过编程，只要跟着做，也能成功养虾 🦞~

建议收藏，我们开始。

⭐️ 推荐观看视频教程：https://www.bilibili.com/video/BV1D4wcz6EVV



## 开始前的准备

在安装之前，你只需要准备 2 样东西：

1. 10 分钟的时间
2. 一台能开机上网的电脑（Windows 就行，Mac 更好，有条件的话建议用虚拟机 / 备用机 / 云服务器，**一定要注意安全！！！**）

其他的，什么都不需要！

**不需要你会编程，不需要你有计算机基础，甚至不需要 1 分钱！**



## 安装教程大纲

整个安装过程分为 3 步：

1. 安装运行环境
2. 安装配置 OpenClaw
3. 开始使用

下面我们一步步来。



## 一、安装运行环境

打开 [OpenClaw 官网](https://openclaw.ai/)，你会看到官方提供了一行命令来安装。

![](https://pic.yupi.icu/1/image-20260310161617619.png)

**如果你是 Mac / Linux 用户**，可以直接打开终端（按 `Command + 空格` 搜索 “终端” 打开），粘贴下面这行命令并回车：

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

这行命令会自动帮你安装所有依赖和 OpenClaw 本体，一步到位，装完就可以直接跳到 **第二步 - 安装配置 OpenClaw**。

![](https://pic.yupi.icu/1/image-20260310161704012.png)

**但如果你是 Windows 用户，千万不要直接执行一行命令安装！失败率极高！！！**

鱼皮实测了多种安装方式，踩了不少坑，下面手把手带你走一遍 Windows 上最稳的安装方式。



### 1、安装 Node.js

首先，我们需要安装 Node.js。

什么是 Node.js？

你可以把它理解成 OpenClaw 的 “发动机”，OpenClaw 是用 JavaScript 语言写的，而 Node.js 就是让 JavaScript 在你电脑上跑起来的运行环境。没有它，OpenClaw 就启动不了。

打开 [Node.js 官网](https://nodejs.org/)，选择对应你操作系统的安装包，并执行下载。注意版本号 **至少选 22 以上**，低于这个版本就会逮虾失败。

![](https://pic.yupi.icu/1/image-20260310144506886.png)

下载完成后，运行安装包，什么都不用改，一路点击下一步就好：

![](https://pic.yupi.icu/1/image-20260310144530251.png)

安装 Node.js 成功后，会自动附带安装一个叫 npm 的工具，它是 Node.js 的应用商店，后面我们要用它来安装 OpenClaw。



### 2、安装 Git

接下来，安装 Git。

Git 是一个代码版本管理工具，OpenClaw 在安装过程中需要用它从网上下载一些依赖包。

你不需要学会怎么用 Git，只需要把它装上就行。

打开 [Git 官网](https://git-scm.com/downloads/win)，下载 Windows 版本的安装包：

![](https://pic.yupi.icu/1/image-20260310144749069.png)

同样，运行安装包，一路点击下一步，全都选择默认配置就好：

![](https://pic.yupi.icu/1/image-20260310144843659.png)



### 3、安装 OpenClaw

环境准备就绪，现在来安装 OpenClaw 本体。

首先，以管理员身份打开 PowerShell。PowerShell 是 Windows 自带的命令行工具，相当于 Mac / Linux 系统的终端。

在电脑的搜索栏中输入 "PowerShell"，右键选择 **以管理员身份运行**：

![](https://pic.yupi.icu/1/image-20260310144953360.png)

先试试官方提供的一键安装命令：

```bash
iwr -useb https://openclaw.ai/install.ps1 | iex
```

大概率你会跟鱼皮一样，直接报错，提示缺少执行脚本的权限：

![](https://pic.yupi.icu/1/image-20260310145038140.png)

没关系，执行下面这行命令，开启 PowerShell 的脚本执行权限：

```bash
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

如果弹出确认提示，输入 `A` 然后按回车即可。这行命令的作用是允许运行来自可信来源的脚本，类似手机上允许安装第三方应用。

![](https://pic.yupi.icu/1/image-20260310145148127.png)

然后重新执行一键安装命令，运气好的话能直接成功。但像我这种倒霉蛋子，安装过程中又报错了！

![](https://pic.yupi.icu/1/image-20260310145208509.png)

报错信息显示是 npm 安装失败，那我们手动输入 npm 命令来安装试试：

```bash
npm install -g openclaw
```

![](https://pic.yupi.icu/1/image-20260310145316319.png)

果不其然也报错了，因为一键安装脚本默认就是用 npm 来装的，根本原因一样。

![](https://pic.yupi.icu/1/image-20260310145349762.png)

别慌，其实换一个包管理工具就行，用 pnpm 来安装。

pnpm 和 npm 类似，也是一个软件商店，但它的兼容性更好、安装速度也更快。

先用 npm 全局安装 pnpm，输入命令：

```bash
npm install -g pnpm
```

安装完成后，检查一下 pnpm 的版本号，确认安装成功：

```bash
pnpm -v
```

![](https://pic.yupi.icu/1/image-20260310145555384.png)

然后执行 `pnpm setup`，这个命令会自动配置 pnpm 的全局安装路径，让你之后通过 pnpm 安装的工具能在任何地方直接使用：

![](https://pic.yupi.icu/1/image-20260310145624520.png)

注意！执行完 `pnpm setup` 后，**一定要关闭当前 PowerShell 窗口，重新以管理员身份打开一个新的**。 这是为了让刚才配置的环境变量生效。

在新的 PowerShell 窗口中，用 pnpm 来安装 OpenClaw：

```powershell
pnpm add -g openclaw@latest
```

![](https://pic.yupi.icu/1/image-20260310145706609.png)

等待一段时间后，安装成功！但你可能会看到一条提示，说忽略了一些包的构建脚本（Ignored build scripts）：

![](https://pic.yupi.icu/1/image-20260310145800342.png)

这是因为 pnpm 出于安全考虑，默认不会自动执行第三方包的构建脚本，需要你手动批准。

按照 OpenClaw 官方的指引，需要执行下面这条命令，来批准这些构建脚本：

```bash
pnpm approve-builds -g
```

![](https://pic.yupi.icu/1/image-20260310145842863.png)

不过执行这条命令可能会报错：

![](https://pic.yupi.icu/1/image-20260310145930863.png)

鱼皮在网上搜了一大圈解决方案，也没能解决这个问题，期待官方后续修复。但好消息是，**这行命令不执行也几乎不影响正常使用**，直接忽略就行。

最后，验证一下 OpenClaw 是否安装成功，执行：

```bash
openclaw -v
```

能够看到版本号，表示大功告成！

![](https://pic.yupi.icu/1/image-20260310143618461.png)



## 二、安装配置 OpenClaw

环境装好了，接下来进入 OpenClaw 的新手引导程序，定制你的小龙虾 🦞。

在 PowerShell（Windows 系统）或终端（Mac / Linux 系统）中执行下列命令：

```bash
openclaw onboard --install-daemon
```

`onboard` 就是新手引导的意思，`--install-daemon` 是指 “顺便把后台服务也装上”，让 OpenClaw 在后台持续运行，关掉终端也不会停。

执行后，会进入一个交互式引导程序，一步步带你完成配置。

![](https://pic.yupi.icu/1/image-20260310150045929.png)

首先会弹出一个使用协议，需要你确认同意。

![](https://pic.yupi.icu/1/image-20260310150214119.png)

这里提醒一下，OpenClaw 是一个能操作你电脑的 AI 工具，理论上它可以执行任何终端命令，包括删除文件之类的敏感操作。**所以建议有条件的话在虚拟机或备用机里玩耍**，避免误操作影响到重要数据。

确认没问题，就选 Yes 进入下一步。



### 1、选择安装模式

引导程序会问你选择 Quickstart（快速开始）还是 Manual（人工）。

建议新手直接选 Quickstart，它会帮你用默认配置快速搞定，人工模式适合有一定养虾经验的同学。

![](https://pic.yupi.icu/1/image-20260310150255760.png)



### 2、配置 AI 大模型

这是最重要的一步，你要告诉 OpenClaw 用哪个 AI 大模型来思考，也就是给龙虾选脑子。

引导程序会列出一些 AI 平台供你选择，比如 Anthropic（Claude）、OpenAI（GPT）、Qwen（通义千问）等。

鱼皮推荐新手选择 Qwen，因为它支持 OAuth 授权登录，会自动弹出网页让你扫码验证，不用手动去申请和填写 API Key，而且可以直接免费使用。缺点是调用太频繁可能会被限流，所以只适合快速上手体验。

![](https://pic.yupi.icu/1/image-20260310150423382.png)

选择 Qwen 后，引导程序会自动打开浏览器让你登录授权：

![](https://pic.yupi.icu/1/image-20260310150610423.png)

完成登录授权后，选择默认的编程大模型：

![](https://pic.yupi.icu/1/image-20260310150731894.png)

当然，你也可以选择其他大模型平台。如果你想了解各模型在 OpenClaw 场景下的实际表现，可以参考 [PinchBench](https://pinchbench.com/) 排行榜，这是一个专门测试大模型做 OpenClaw 任务的评测网站。目前成功率最高的是 Claude Opus 4.6（成功率 82.5%），最便宜的是 Google 的 gemini-2.5-flash-lite（每次任务只要 1 毛钱）。

![](https://pic.yupi.icu/1/image-20260310164932093.png)

不太建议新手一上来就用国外大模型来玩 OpenClaw，价格非常贵，尤其是你让 AI 干复杂的活时，Tokens 会烧得嘎嘎猛，要做好心理准备。国产的智谱、Kimi 也是不错的选择。



### 3、配置聊天渠道

引导程序会问你要不要连接 Telegram、WhatsApp、Discord、飞书等聊天平台，更方便地跟龙虾对话。

建议直接跳过，我们先用网页界面聊天就好，后面可以再手动接入 QQ 和飞书。

![](https://pic.yupi.icu/1/image-20260310150813561.png)

接下来还会问你要不要配置搜索服务提供者（比如 Brave Search），也建议先跳过，这些都需要额外申请 API Key，后面有需要再配：

![](https://pic.yupi.icu/1/image-20260310150917416.png)



### 4、安装 Skills 技能包

Skills 是给 AI 装的能力扩展包。OpenClaw 本身只是一个框架，装了 Skills 之后 AI 才能解锁各种具体的能力，比如搜索网页、操作浏览器、制作 PPT 等。

先开启技能配置：

![](https://pic.yupi.icu/1/image-20260310150959049.png)

然后引导程序会列出一些推荐的技能包，这里建议至少添加 **ClawHub** 这一个。ClawHub 是 OpenClaw 的官方技能市场，装了它之后，你的小龙虾就可以随时搜索和安装社区里上千个技能包，快速扩展自己的能力，非常方便。其他的技能按需选择即可。

![](https://pic.yupi.icu/1/image-20260310151036714.png)

选择完技能后，还要选择安装技能的工具，用 npm 就行：

![](https://pic.yupi.icu/1/image-20260310151118779.png)

之后还会询问一些额外服务的配置，比如是否要配置 AI 生图大模型等，新手直接无脑全部选 No：

![](https://pic.yupi.icu/1/image-20260310151157689.png)



### 5、启动网关服务

接下来会自动安装并启动 OpenClaw 的 Gateway 网关服务。你可以把网关理解成 OpenClaw 的总调度中心，它负责接收你从各个渠道（网页、QQ、飞书等）发来的消息，分配给 AI 处理，再把结果返回给你。

![](https://pic.yupi.icu/1/image-20260310151301625.png)

这时候 Windows 可能会弹出防火墙提示，问你是否允许公共网络和专用网络访问，**一定要点允许！** 否则网关服务无法正常工作。

![](https://pic.yupi.icu/1/image-20260310151324961.png)

启动成功后，引导程序会问你是在终端界面（TUI）还是网页浏览器中使用 OpenClaw。

TUI 就是直接在命令行里跟 AI 聊天，适合喜欢敲命令、有一定编程基础的同学。新手当然选 Web UI 网页中使用：

![](https://pic.yupi.icu/1/image-20260310151428919.png)



### 开始使用

选择之后，浏览器会自动打开 OpenClaw 的网页控制面板。恭喜，你的龙虾 1 号准备就绪！

先跟它打个招呼吧，问问它是谁。它还会主动引导你通过对话来设置身份、职责等个性化信息：

![](https://pic.yupi.icu/1/image-20260310151625528.png)

OpenClaw 内置了很多工具，比如文件读写、终端命令执行、网页搜索等。

试试让它帮你读取电脑上的文件，比如查看下载目录里有什么：

![](https://pic.yupi.icu/1/image-20260310151946903.png)



## 写在最后

恭喜你成功在本地安装了 OpenClaw！不过这只是养虾之旅的第一步，接下来还有更多玩法等你解锁。

如果你嫌手动安装太麻烦，可以阅读下一篇《03 一键安装脚本》，一行命令搞定所有环境依赖和配置。

想把 OpenClaw 部署到云端 24 小时不间断运行，可以阅读《04 云端部署 OpenClaw》。

想接入 QQ 和飞书，随时随地用手机养虾，可以阅读《06 接入 QQ 和飞书》。

关于卸载：执行 `openclaw uninstall` 即可卸载 OpenClaw，详细的卸载命令可以参考 OpenClaw 官方文档。

加油！




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
