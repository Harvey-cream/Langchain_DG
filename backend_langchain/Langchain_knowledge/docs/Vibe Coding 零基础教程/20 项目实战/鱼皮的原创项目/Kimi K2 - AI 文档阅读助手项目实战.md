# Kimi K2 - AI 文档阅读助手项目实战

本项目是一个 AI 文档阅读助手网站，可以帮你快速读懂各种复杂的文档（论文、技术文档、PDF 等），还能帮你管理文档。

项目包含完整的前端和后端，全程通过和 AI 对话完成开发，不写一行代码，适合想快速实践完整 Vibe Coding 开发流程、想学习如何用 AI 开发实用工具的同学。



---



大家好，我是程序员鱼皮。开学季到了，想必很多朋友要开始收集和阅读论文，像我自己学习新技术知识也会去阅读文档，我深知阅读文档的痛苦。明明每个词拆开都知道什么意思，连一起就看不懂。

![](https://pic.yupi.icu/1/1757559057843-b9d37369-49bf-4eec-878a-c70ac945cbd9.png)

为了帮助大家免受文档的折磨，我用 AI 开发了个 AI 文档助手网站，可以帮你快速读懂各种复杂的文档、还帮你管理文档。

![](https://pic.yupi.icu/1/1757561248387-205bf672-7a6c-452a-a283-698fb526601c.png)

网站完全免费，代码完全开源！

开源仓库：[github.com/liyupi/literature-assistant](https://github.com/liyupi/literature-assistant)

![](https://pic.yupi.icu/1/1757829143308-d5bfdac6-847a-4061-9194-4821bdf3d3dc.png)

下面先教大家如何使用网站，再分享这个网站的制作过程，还有国内使用 Claude Code 的方法哦。

⭐️ 推荐观看视频版，2 分钟学会：[bilibili.com/video/BV1MnpVzdETW](https://www.bilibili.com/video/BV1MnpVzdETW/)



## 如何使用？

先下载开源代码到自己电脑，然后直接运行我提供的快速启动脚本，打开网页就能看到效果了。

💡 要确保你的电脑有 Node.js 和 Java 环境，可以参考 README.md 文档安装。

![](https://pic.yupi.icu/1/1757567928358-ad506045-faaf-47b1-b742-190c83c94ad3.png)



当你要阅读文档时，点击 “单个导入” 按钮，上传文档文件，然后需要填写 Kimi AI 的 API Key。

![](https://pic.yupi.icu/1/1757560732751-de713284-c039-41c1-b9f4-0af34e4c703c.png)



选择 Kimi 是因为他们刚刚发布了新版本的 K2 模型，在编程、推理和文档理解方面都很不错；

而且支持 256K 的上下文，几十万字的论文也能搞定。

![](https://pic.yupi.icu/1/1757560219469-2eab0801-a9b3-49dd-b680-d1d27c1850cf.png)



在侧重考察真实软件工程任务的 SWE-bench Verified 等基准测试中，新版 Kimi K2 模型的表现也很不错：

![](https://pic.yupi.icu/1/1757560161782-1c78bd3c-a3a5-42f9-b79b-a0b07d808e6b.png)



只需要登录 [Kimi 的开发控制台](https://platform.moonshot.cn/)，然后进入 API Key 管理来获取一个调用大模型的密钥。

![](https://pic.yupi.icu/1/1757560312832-cfd4158d-8c31-4c22-8b42-573551334863.png)



虽然新人有免费额度，但是不要泄露自己的密钥哦！

![](https://pic.yupi.icu/1/1757560674974-180d8475-e83e-4b35-ba9b-2ded866aa730.png)



填写好 API Key，就可以生成文档阅读指南啦，生成速度非常快。

![](https://pic.yupi.icu/1/1757560771758-4c3df93e-889d-4c74-afa2-90e69347f286.png)



AI 生成的效果还是不错的，图文并茂，能帮你更快理解复杂的文档。

![](https://pic.yupi.icu/1/1757560820325-87111dd8-cd82-49d0-9385-24ea9a33e885.png)



你还可以批量导入多个文档，同时调用 AI 生成阅读指南，提高效率。

![](https://pic.yupi.icu/1/1757560886812-1706415c-cff5-4475-872f-ba66891563f7.png)



此外，你还可以把这个网站当做自己的智能文档收藏夹，可以分类检索已经导入的文档、下载原始文件、随时查看文档阅读指南。**不要再让自己收藏过的文档找不到啦~**

![](https://pic.yupi.icu/1/1757560925975-079ad961-7cc8-498b-99e2-84a4a534023f.png)



## 怎么实现？

如果是以前，这种网站可能要做个好几天。但现在 AI 编程技术已经很成熟了，我选用 Claude Code AI 开发工具，轻轻松松一天搞定，而且一行代码都不用自己写。

首先在终端输入一行命令来安装 Claude Code：

```bash
npm install -g @anthropic-ai/claude-code
```

然后执行 `claude` 命令，就可以向它提问了~

结果，报错啦！

![](https://pic.yupi.icu/1/1756451588360-37620a0b-bc2f-4ad5-adf9-4efde87f17ed.png)

**可恶啊，这破玩意还不支持国内使用！**

不过没关系，我们可以更换为 Kimi。在终端内输入命令来配置一段环境变量（注意区分操作系统）：

```bash
# Linux/macOS 启动高速版 kimi-k2-turbo-preview 模型
export ANTHROPIC_BASE_URL=https://api.moonshot.cn/anthropic
export ANTHROPIC_AUTH_TOKEN=<你的 API 密钥>
export ANTHROPIC_MODEL=kimi-k2-turbo-preview
export ANTHROPIC_SMALL_FAST_MODEL=kimi-k2-turbo-preview

# Windows Powershell 启动高速版 kimi-k2-turbo-preview 模型
$env:ANTHROPIC_BASE_URL="https://api.moonshot.cn/anthropic";
$env:ANTHROPIC_AUTH_TOKEN=<你的 API 密钥>
$env:ANTHROPIC_MODEL="kimi-k2-turbo-preview"
$env:ANTHROPIC_SMALL_FAST_MODEL="kimi-k2-turbo-preview"
```



然后就可以愉快地使用 Claude Code 生成代码了~

![](https://pic.yupi.icu/1/1756451713145-29e5ba15-76b2-4848-903a-f098b942e2f9.png)



对于包含完整前后端的网站，很难用一段提示词就让 AI 生成出满意的效果，因此我们需要像企业真实开发一样 **分解工作步骤**。先后端、再前端、最后前后端对接联调，而且最好一个一个地开发功能，出了问题及时调整。

分享一些参考的提示词：

![](https://pic.yupi.icu/1/1757567728565-5724de3e-7863-457b-9866-368c1535bd2c.png)



------



以上就是本期分享，希望这个工具对大家有帮助，也不要忘记给鱼皮三连支持，谢谢大家~

![](https://pic.yupi.icu/1/1757829315038-73ef4fd7-7fef-4fa2-859d-11bb28381933.webp)


## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
