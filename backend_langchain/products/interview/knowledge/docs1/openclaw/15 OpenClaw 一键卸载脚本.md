# OpenClaw 一键卸载脚本

> 一行命令卸载干净，还送你一份养虾报告

你好，我是鱼皮。

前面这套教程教了大家怎么安装、配置、玩转 OpenClaw。但养了一段时间后，有些同学可能会觉得索然无味……

- 有人觉得龙虾是个肥物，干啥啥不行
- 有人发现这龙虾是个间谍，安全风险太大
- 还有人一看账单，好家伙，养不起了！这钱拿去吃真的小龙虾不香么？

总之就是各种原因，想把龙虾扔了。

官方文档虽然提供了 [卸载步骤](https://docs.openclaw.ai/install/uninstall#uninstall)，但大概率是没办法通过 1 条命令就删干净的。

![](https://pic.yupi.icu/1/image-20260307105935932-20260321130257839.png)

所以我做了这个 **一键卸载脚本**，不仅能帮你把龙虾吃得干干净净、虾壳都不剩，还会附带一份 **使用报告**，让你在告别龙虾之前，看看这段时间跟龙虾相处的回忆。



## 使用方法

一行命令即可完成 OpenClaw 的完整卸载，操作超简单~

### Windows 电脑

按 `Win + R` 键，唤起运行窗口，然后输入 `powershell` 并回车：

![](https://pic.yupi.icu/1/1773650695343-70d4ef97-6754-49c1-93e3-a230001f8171-20260321125946596.png)

输入以下命令，执行给大家准备好的卸载脚本：

```powershell
irm https://clawfather.cn/uninstall.ps1 | iex
```

如果遇到中文乱码，改用这条：

```powershell
& {$w=New-Object Net.WebClient;$w.Encoding=[Text.Encoding]::UTF8;iex $w.DownloadString('https://clawfather.cn/uninstall.ps1')}
```

然后等待脚本自动完成所有步骤即可，脚本会依次执行以下流程：

1）扫描本地 OpenClaw 相关的数据，为生成报告做准备：

![](https://pic.yupi.icu/1/1774068080605-a4c5e2b1-b7da-4d60-8623-aa9409552fd7.png)

整个过程只在本地进行，所以大家不需要担心自己的隐私问题~

2）生成养虾报告，包括你的养虾天数、跟龙虾聊了多少次、发了多少条消息、烧了多少 Token、大概花了多少钱、养了几只龙虾、装了多少 Skills、什么时候最爱跟龙虾交流等：

![](https://pic.yupi.icu/1/1774068186927-dd613e73-67fd-48c3-a3cf-c95dfdff3c32.png)

3）列出所有将被清理的组件，让你手动确认后再执行：

![](https://pic.yupi.icu/1/1774068218878-2c53308e-2462-4134-a580-3dd1916225e1.png)

4）开始吃龙虾 🦞！逐项清理 OpenClaw 相关内容，停止 Gateway 服务、卸载 CLI、删除状态数据和配置文件：

![](https://pic.yupi.icu/1/1774068299187-e6edc73f-9da4-4d30-8521-6e23ae6a93b9.png)

5）验证卸载结果，确保清理干净，虾壳都不剩：

![](https://pic.yupi.icu/1/1774017685135-434b4fe7-64c3-492a-9fc0-d6976d07f1b2.png)

怎么样，是不是简单的一皮？仿佛什么都没发生过。



### Mac 电脑

按 `Command + 空格`，唤起聚焦搜索，搜索「终端」，点击打开：

![](https://pic.yupi.icu/1/1773650769650-59007b90-463d-45f4-868a-fd4776890cac-20260321125946989.png)

输入以下命令：

```bash
curl -fsSL https://clawfather.cn/uninstall.sh | bash
```

然后脚本会自动完成下面的所有步骤：

1. 扫描本地 OpenClaw 数据并收集使用统计
2. 生成 Wrapped 使用报告
3. 列出将被清理的组件
4. 确认后逐项卸载
5. 验证卸载结果

这里跟 Windows 的流程类似，我们就不过多赘述了。



## 脚本亮点

为了尽可能提高大家的卸载体验，我还特意进行了一些优化。

比如前面提到的养虾报告，脚本会自动保存一份到桌面文件（`openclaw-wrapped.txt`），方便你截图发朋友圈晒一波。毕竟养过赛博龙虾也是一种人生经历嘛~

![](https://pic.yupi.icu/1/1774068647522-f46233fe-cab6-4654-b16b-72381715d4df.png)

而且卸载脚本的安全性有「双重保障」，不会像龙虾一样乱删你的东西：

- 删除之前会先列清单让你手动确认，避免误删
- 内置了多重安全检查，只动龙虾相关的文件，不碰你的其他数据

下面这个表里是脚本会检测并清理的主要内容：

| 组件         | Mac                             | Windows                             |
| ------------ | ------------------------------- | ----------------------------------- |
| OpenClaw CLI | npm/pnpm/bun 全局卸载           | npm/pnpm/bun 全局卸载               |
| Gateway 服务 | launchd (Mac) / systemd (Linux) | 计划任务 + gateway.cmd              |
| 状态数据     | `~/.openclaw`                   | `%USERPROFILE%\.openclaw`           |
| 工作区       | `~/.openclaw/workspace`         | `%USERPROFILE%\.openclaw\workspace` |
| Profile 目录 | `~/.openclaw-*`                 | `%USERPROFILE%\.openclaw-*`         |
| macOS App    | `/Applications/OpenClaw.app`    | —                                   |



## 写在最后

如果你卸载之后又想养回来了（别笑，真有人这样），随时可以回到本教程的《02 本地安装 OpenClaw》或《03 OpenClaw 一键安装脚本》重新开始。

如果你还没看过实战玩法，推荐阅读《OpenClaw 实战 | 用 GLM-5 打造你的 AI 伴侣》，说不定能找到新的养虾灵感。对 OpenClaw 背后的创始人故事感兴趣的话，可以阅读《番外 | OpenClaw 创始人的故事》。

祝大家养虾愉快，卸虾也愉快！



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)