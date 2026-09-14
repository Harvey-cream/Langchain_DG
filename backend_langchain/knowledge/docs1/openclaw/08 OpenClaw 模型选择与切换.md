# OpenClaw 模型选择与切换

> 给龙虾选脑子，全局切换和临时切换一网打尽

你好，我是鱼皮。选一个好模型非常重要，它直接决定了你的小龙虾有多聪明。这篇教程教你怎么选模型、怎么切换模型。



## 怎么选模型

OpenClaw 支持几十家模型服务商，包括 Anthropic（Claude）、OpenAI、Google（Gemini）、Qwen（通义千问）、GLM（智谱）、Moonshot（Kimi）、Volcengine（豆包）、百度千帆等等，详见官方文档的模型列表页面：https://docs.openclaw.ai/providers/models

如果模型太多不知道选哪个？

可以到 [PinchBench](https://pinchbench.com/) 查看 OpenClaw 模型排行榜，看看各模型在 OpenClaw 场景下的实际表现，不过仅供参考。

![](https://pic.yupi.icu/1/image-20260310164932093.png)

不太建议新手一上来就用国外大模型，价格贵，而且网络访问也不太稳定。国产的智谱（GLM）、Kimi、Qwen 是不错的选择，价格便宜、速度快、中文能力也够用，先拿这些练手，等玩熟了再按需切换到更强的模型。



## 全局切换模型

我会给大家分享多种模型切换方法，强烈推荐第一种。


### 推荐方法 - 命令行工具

输入 `openclaw config` 命令，选择配置 Model 模型，选择相应的大模型即可，比如我这里用 Moonshot AI 的 Kimi-k2.5 模型：

![](https://pic.yupi.icu/1/1773813259463-5c6e94bf-edde-4fef-8643-cea4d1f02b0c.png)

这就配置完成了，还可以通过 config 继续修改其他配置：

![](https://pic.yupi.icu/1/1773813033619-ab5b7715-5281-4e76-9676-0c9f43e3410d.png)

回到界面验证一下，切换模型成功生效了：

![](https://pic.yupi.icu/1/1773813527996-e90b63ea-1412-47f8-b1aa-f3d3da214073.png)

可以通过命令查看模型的状态：

```bash
openclaw models status
```

![](https://pic.yupi.icu/1/1773814465973-33bc05c3-3656-47fe-9fdc-3e7415758a0b.png)

其实命令本质上就是帮你修改了 OpenClaw 工作空间的核心配置文件 `openclaw.json`，添加了新模型，并且设置为了小龙虾的默认模型，还把之前的模型设置为了降级模型。

![](https://pic.yupi.icu/1/1773813576949-88548239-e52a-46be-a124-6d810e545c95.png)

还有一些其他的命令，按需使用即可：

```bash
# 配置默认文本模型
openclaw models set zai/glm-5

# 用 config 命令直接写配置
openclaw config set agents.defaults.model.primary "moonshot/kimi-k2.5"

# 设置图片理解模型（看图用的）
openclaw models set-image zai/glm-5

# 添加备用降级模型
openclaw models fallbacks add 提供商/模型
```

![](https://pic.yupi.icu/1/1773815234026-a4b9af0d-a0b6-4ecc-820e-ea6de86eb76e.png)



### 其他方法 - 不推荐

还有其他切换模型的方法。你可以通过 Web UI 界面修改，或者手动修改这个配置文件：

![](https://pic.yupi.icu/1/1773813700732-2a6faa56-3f91-4da0-bc7f-d6d4dd4810bf.png)

但是要重启网关，否则可能不会生效：

```bash
openclaw gateway restart
```

![](https://pic.yupi.icu/1/1773813866547-9f2d57b8-21ca-4fd1-a766-20dfe8072a01.png)

个人不推荐使用这些方式，麻烦，还容易出错。

你还可以直接跟小龙虾对话让它帮你修改，但我建议不要这么做，一些明确的、简单的操作就不要交给 AI 这种随机生物来折腾了。

比如我的小龙虾直接把配置文件搞崩了，它还感觉挺美的！

![](https://pic.yupi.icu/1/1773814311334-9c308e07-4125-4d02-9279-f2d736df2f95.png)

![改错了配置文件](https://pic.yupi.icu/1/1773814246339-ae621fc5-774d-49bc-aa3e-3d97c8d4824b.png)



## 临时切换模型

比如你正在用国外的 Claude Sonnet 模型聊天，突然欠费了，想临时切到国产模型。

可以直接在聊天框中输入 `/model list` 查看可用的模型列表：

![](https://pic.yupi.icu/1/1773816609174-e77da8bd-6569-4c80-aae6-86c15a98ef0f.png)

然后输入 `/model <模型服务商/模型名称>` 切换模型：

![](https://pic.yupi.icu/1/1773816655106-bf00f0af-042f-4f9f-a277-2c2cef2b934d.png)

这样切换模型只会影响当前会话，不改全局默认配置，其他会话不受影响。



## 模型降级（Fallback）

什么是降级模型呢？简单来说就是备胎模型。当你的主力模型出问题（比如欠费、服务挂了、被限流了），OpenClaw 会自动切到降级模型继续工作，保证小龙虾不会突然失联。

前面用命令行切换模型的时候，OpenClaw 会自动把旧模型设为降级模型，挺贴心的。你也可以手动添加降级模型：

```bash
openclaw models fallbacks add 提供商/模型
```

OpenClaw 内置了智能降级（failover）机制，支持多级降级链。也就是说你可以配置多个备胎模型，排成一条链，第一个不行就换第二个，第二个不行就换第三个，以此类推。

可以通过命令配置降级链：

```bash
openclaw config set agents.defaults.model.fallbacks '["zai/glm-5", "qwen/qwen-max"]' --strict-json
```

这样设置之后，主力模型挂了会先切到智谱 GLM-5，GLM-5 也挂了就切到通义千问 Qwen-Max，最大程度保证小龙虾不掉线。



## 写在最后

模型搞定了，接下来学习 OpenClaw 的工具管理和多媒体能力，比如操控浏览器、文字转语音等功能。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)

