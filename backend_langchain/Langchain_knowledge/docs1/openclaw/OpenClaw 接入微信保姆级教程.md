# OpenClaw 接入微信保姆级教程

> 微信终于能养龙虾了！安卓 iOS 都能用，1 分钟搞定

你好，我是鱼皮。

几天前，微信官方推出了 OpenClaw 小龙虾接入微信的插件「微信 ClawBot」，直接杀死了 “争夺养虾入口” 的比赛！

![](https://pic.yupi.icu/1/%25E5%25BE%25AE%25E4%25BF%25A1%25E4%25BB%258B%25E5%2585%25A5openclaw.png)

但是刚开始只有 IOS 苹果手机才能用，我还跟同事开玩笑说：俺不是高贵的 “苹果人”，只能先望虾莫及了……

结果，今天早上打开手机一看，我去，明明没有升级微信版本，竟然能够使用微信 ClawBot 插件了！

我试了一下，接入非常简单，真的可以说是有手就行，直接在微信里跟小龙虾聊天、发图片、下任务，丝滑得一皮~

![](https://pic.yupi.icu/1/image-20260324150329933.png)

下面，我来教大家如何把 OpenClaw 小龙虾接入微信，保姆皮已上线 ✅



## 一、认养一只小龙虾 🦞

微信 ClawBot 插件的作用是连接 OpenClaw 和微信，让你能通过手机跟小龙虾聊天和下发任务，所以首先你要有一只小龙虾。

之前我写了一整套《OpenClaw 保姆级教程》，从安装到进阶玩法全覆盖，帮不少朋友成功养上了自己的小龙虾。

![](https://pic.yupi.icu/1/%E5%9B%BE2-16%E6%AF%949OpenClaw%E7%9F%A5%E8%AF%86%E5%BA%93%E5%9C%A8%E7%BA%BF%E9%98%85%E8%AF%BB.png)

你可以通过下面 3 种方法，快速安装 OpenClaw 并获取自己的小龙虾，每种方法在本教程中都有傻瓜式教程：

- 本地一键安装：可以阅读本教程的《03 OpenClaw 一键安装脚本》
- 本地手动安装：可以阅读本教程的《02 本地安装 OpenClaw》
- 云服务器一键安装：可以阅读本教程的《04 云端部署 OpenClaw》

推荐新手先尝试本地一键安装，1 分钟搞定！

1）无论你是 Windows 还是 Mac 系统，要先打开命令行终端。

Windows 可以搜索 PowerShell，并 **以管理员身份运行**；Mac 直接搜索 “终端” 并打开即可：

![](https://pic.yupi.icu/1/image-20260324102432835.png)

2）然后根据操作系统，在终端中输入一行命令，运行我给大家提供的「全自动安装脚本」：

```powershell
# Windows 输入
$env:OPENCLAW_VERSION='2026.3.13'; irm https://codefather.cn/openclaw_install/install-openclaw.ps1 | iex

# Mac 输入
curl -fsSL https://codefather.cn/openclaw_install/install-openclaw.sh | bash -s -- --version 2026.3.13
```

细心的同学会发现，我在命令中添加了版本参数，指定安装 `2026.3.13` 这个版本。

⚠️ 这里千万要注意！**不要安装 >= 3.22 的 OpenClaw 版本！**否则无法兼容微信 ClawBot 等插件！都怪官方更新地太快太粗暴了！

3）接下来只需要等待片刻，脚本会自动帮你检测和安装环境，并安装 OpenClaw 程序本身。

![](https://pic.yupi.icu/1/image-20260324115344988.png)

4）安装成功后，会引导你配置 AI 的大模型 API Key 密钥。

推荐先用国产模型，比如智谱（zai）或者 Kimi（moonshot），用哪家的大模型，就到哪家的开放平台获取 API Key 即可。

![](https://pic.yupi.icu/1/image-20260324140749942.png)

5）最后，正常情况下，会自动打开 OpenClaw 管理网页，你的小龙虾前来报到：

![](https://pic.yupi.icu/1/image-20260324102805104.png)

如果你运行一键安装脚本出错了，可以尝试本教程的《02 本地安装 OpenClaw》手动安装。

如果你担心小龙虾在自己的电脑里胡作非为，或者想让它 7 x 24 小时不间断运行，可以阅读本教程的《04 云端部署 OpenClaw》。



## 二、接入微信 ClawBot 插件

首先打开微信，依次点击：我 → 设置 → 插件，能够看到微信 ClawBot 插件：

![](https://pic.yupi.icu/1/image-20260324134224548.png)

不是哥们？这么多年了，就这一个插件嘛？

也足以看出腾讯这波想拿下 AI 入口流量的野心了。

![](https://pic.yupi.icu/1/HDnaD6IbEAMKVS0-20260322141650228.jpeg)

进入插件详情，可以看到官方给出了接入微信 ClawBot 的指引：

![](https://pic.yupi.icu/1/Screenshot_20260324_094406_com.tencent_%E5%89%AF%E6%9C%AC.mm.jpg)

下面我们开始操作，依然是 1 分钟搞定！

1）首先在安装了 OpenClaw 小龙虾的电脑上打开 CMD 终端。Windows 按 `Win + R` 键，然后输入 `cmd` 并回车：

![](https://pic.yupi.icu/1/image-20260324113126474.png)

2）打开终端后，执行这行命令，安装微信接入 OpenClaw 的插件：

```bash
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

正常情况下，会显示一个连接码：

![](https://pic.yupi.icu/1/image-20260324141342230.png)

3）用手机扫一下，然后同意连接就好。操作完成后，终端会显示 “与微信连接成功”，就已经搞定了~

![](https://pic.yupi.icu/1/image-20260324141941525.png)

试一试通过微信和 OpenClaw 小龙虾对话吧，而且不需要什么配置，就能让它帮你分析图片、给你发送图片：

![](https://pic.yupi.icu/1/image-20260324143907284.png)



### 常见错误

安装过程中，可能会出现一些错误，这是正常的。（没出错的同学运气真的非常好了~）

1）插件安装失败

这是因为 OpenClaw 官方插件仓库太火爆了，导致安装时可能会被限流：

![](https://pic.yupi.icu/1/image-20260324104016363.png)

解决方法是重试几次，或者等大家都睡着了再安装~

2）插件加载失败

如果你前面没有认真看我的教程，不小心安装了 >= 3.22 的版本，就会看到下面这个错误：

![](https://pic.yupi.icu/1/image-20260324110402003.png)

此时可以按照文档来回滚到之前的版本，执行几个命令就好：

> 指路：https://clawfather.cn/install/updating

![](https://pic.yupi.icu/1/image-20260324124003675.png)



### 手动安装

如果一键安装命令跑不通，也可以手动一步步来，就 4 条命令的事儿：

1）安装插件：

```bash
openclaw plugins install "@tencent-weixin/openclaw-weixin"
```

2）启用插件：

```bash
openclaw config set plugins.entries.openclaw-weixin.enabled true
```

3）扫码登录，终端会弹出二维码，用手机扫码并确认授权就行，登录凭证会自动保存到本地：

```bash
openclaw channels login --channel openclaw-weixin
```

4）重启网关，让插件生效：

```bash
openclaw gateway restart
```

如果你想让多个微信号都能跟龙虾聊天，再执行一次 `openclaw channels login --channel openclaw-weixin` 扫码就行，每次扫码会创建一个新的账号，支持多个微信号同时在线。



## 三、更多玩法

安装完插件后，你可以在 OpenClaw 的插件目录下找到 `openclaw-weixin` 相关的源码和 README.md 介绍文档，感兴趣的同学可以翻一翻：

![](https://pic.yupi.icu/1/image-20260324143134753.png)

通过阅读这个文档，你可以了解到更多高级用法，比如多账号上下文隔离（让每个微信号的对话记忆互不干扰）、后端 API 协议（方便二次开发对接自己的服务）、CDN 媒体上传流程等：

![](https://pic.yupi.icu/1/image-20260324144620649.png)

接入微信只是第一步，想把小龙虾玩出花来，本教程的进阶部分（07-14 篇）涵盖了：

- 初始化配置与模型切换（全局 / 临时）
- 高频斜杠命令与工具管理
- TTS 文字转语音
- 定时任务与心跳机制
- Skills 技能系统（内置技能 / 第三方技能 / AI 自建技能）
- 子 Agent 与多 Agent 协作
- 问题自检修复与 Git 配置管理
- 记忆系统、成本控制、安全防护

按需选学就好，从《07 OpenClaw 初始化和基础使用》开始即可。



## 写在最后

OpenClaw 的迭代速度实在太快了，从只能在终端聊天到现在微信直连，也就几个月的事。谁也不知道下一个版本又会蹦出什么新花样，但有一件事是确定的 —— 使用 AI Agent 的成本一定会越来越低，所以不必焦虑，需要用到的时候再学也完全来得及。

接入微信只是开始，想把小龙虾玩出更多花样，可以阅读本教程的《07 OpenClaw 初始化和基础使用》开始进阶之旅。想看完整的实战案例，可以阅读《OpenClaw 实战 | 用 GLM-5 打造你的 AI 伴侣》。

祝大家养虾愉快！



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)