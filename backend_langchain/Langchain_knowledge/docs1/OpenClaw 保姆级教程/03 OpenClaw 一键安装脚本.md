# OpenClaw 一键安装脚本

> 一行命令搞定 OpenClaw 的所有依赖和配置

你好，我是鱼皮。上一篇教程手把手教了大家本地安装 OpenClaw 的完整流程，但有不少同学觉得手动装 Node.js、Git、配镜像太麻烦了。所以我做了个 **一键安装脚本**，自动搞定所有环境依赖和配置，只需要复制粘贴一行命令，即可愉快使用小龙虾~

⭐️ 视频演示：https://bilibili.com/video/BV1UWw9zHE67



## 使用方法

一行命令就可以完成 OpenClaw 的安装，Windows 和 Mac 电脑都支持，可以火速体验起来，操作超简单，打开命令行输入就行~

### Windows 电脑

按 `Win + R`，唤起运行窗口，然后输入 `powershell` 并回车：

![](https://pic.yupi.icu/1/1773650695343-70d4ef97-6754-49c1-93e3-a230001f8171.png)

输入以下命令：

```powershell
irm https://codefather.cn/openclaw_install/install-openclaw.ps1 | iex
```

如果遇到中文乱码，改用这条：

```powershell
& {$w=New-Object Net.WebClient;$w.Encoding=[Text.Encoding]::UTF8;iex $w.DownloadString('https://codefather.cn/openclaw_install/install-openclaw.ps1')}
```

然后等待脚本自动完成所有步骤即可，脚本会依次执行以下步骤：

1）检测并安装 Node.js v22+，支持 nvm-windows 或直接下载，而且会通过国内镜像加速：

![](https://pic.yupi.icu/1/1773649977323-8202eb12-a705-4a5a-bde2-e529d60e93f2.png)

2）检测并安装 Git：

![](https://pic.yupi.icu/1/1773650014622-e36e9846-368d-40b6-abd9-5141fc10d003.png)

3）设置 npm 国内镜像：

![](https://pic.yupi.icu/1/1773650306616-3bebe398-9d60-42c4-82c4-675e290ff670.png)

4）安装 pnpm：

![](https://pic.yupi.icu/1/1773650330327-4a4f0ca1-2f65-4c7e-b516-c2b37141f4da.png)

5）安装 OpenClaw，GitHub 连不上的时候还会提供镜像方案供小伙伴们选择：

![](https://pic.yupi.icu/1/1773650526366-27f8a36a-6406-4d0b-9db0-ea88d996d5a9.png)

6）验证安装结果：

![](https://pic.yupi.icu/1/1773650512181-7b5e92ea-cfe7-4043-ab7b-ee9b3393a500.png)

7）交互式配置，脚本会引导选择 AI 厂商、输入 API Key、选择默认模型，一步搞定：

![](https://pic.yupi.icu/1/1773650629769-7358a04d-b1ec-44c8-849d-654605afc672.png)



### Mac 电脑

按 `Command + 空格`，唤起聚焦搜索，搜索「终端」，点击打开：

![](https://pic.yupi.icu/1/1773650769650-59007b90-463d-45f4-868a-fd4776890cac.png)

输入以下命令：

```bash
curl -fsSL https://codefather.cn/openclaw_install/install-openclaw.sh | bash
```

然后脚本会自动完成下面的所有步骤：

1. 检测并安装 Node.js v22+，脚本会依次尝试 nvm → Homebrew → 直接下载 方式来安装
2. 检测并安装 Git
3. 设置 npm 国内镜像
4. 安装 OpenClaw
5. 验证安装结果
6. 交互式配置

这里跟 Windows 的流程类似，就不过多赘述了。



## 脚本优势

为了尽可能降低大家的使用门槛，我还特意进行了一些优化，比如：

1）已有合格版本的 Node.js / Git 会直接使用，不会重复安装：

![](https://pic.yupi.icu/1/1773651732963-ecbf3099-196e-4009-a698-f100c01138d3.png)

2）npm 镜像、Node.js 下载源、Git 下载源全部走国内镜像，下载速度嘎嘎快

3）脚本内置了多个 GitHub 社区镜像的自动探测和回退机制

4）支持 OpenAI、Anthropic、Gemini、智谱、Moonshot、Kimi Coding、百度千帆、小米等多家 AI 厂商，选完即用：

![](https://pic.yupi.icu/1/1773651814048-3a28ee57-b93e-4bbd-8c95-a89282fcf870.png)

5）如果已经装过 OpenClaw，脚本会跳过安装流程，直接提供重新配置的入口：

![](https://pic.yupi.icu/1/1773651858739-4b3083bc-ebbe-4c43-9686-10798f9db0e5.png)

6）配置完成后自动启动 OpenClaw 控制面板，无门槛开始使用：

![](https://pic.yupi.icu/1/1773651943494-09d95e45-75d9-4bcf-9b66-42bf8a9acbf8.png)

怎么样，是不是简单的一皮？

其实这个脚本并不复杂，大家借助 AI 都能梭出来。如果之后面试官问你 “怎么安装小龙虾？”，不要直接说 “复制官方提供的命令” 了，改为 “自己封装了个一键脚本” 才是更符合技术人的做法。



## 写在最后

如果你想把 OpenClaw 部署到云服务器上 24 小时运行，可以阅读下一篇《04 云端部署 OpenClaw》。如果你已经安装好了，想接入 QQ 和飞书，可以直接跳到《06 接入 QQ 和飞书》。

加油！




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
