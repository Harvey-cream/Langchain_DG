# OpenClaw 工具管理与多媒体能力

> 操控浏览器、文字转语音、发图片发视频

你好，我是鱼皮。OpenClaw 内置了很多工具，但默认并不是全部开启的。这篇教程教你怎么管理工具的开关，以及如何解锁文字转语音、发送图片视频等多媒体能力。



## 工具管理

OpenClaw 的工具分为多个类别，比如 EXEC（执行命令）、WRITE（写文件）、READ（读文件）、BROWSER（浏览器）、MESSAGE（消息发送）、TTS（文字转语音）等等。默认只开启了一部分，其他的需要你自己按需打开。

在 OpenClaw 控制台的代理模块，可以查看当前 Agent 的工具情况。

可以选择预设工具组合，也可以单独开关某个工具。比如担心 AI 误操作你电脑上的文件，可以关闭文件写入和修改等工具。

![](https://pic.yupi.icu/1/1773892633607-77e420a9-349d-431b-ac04-7d5db7fc03fc.png)

除了在 Web 控制台管理工具，你也可以通过配置文件 `openclaw.json` 的 `tools` 字段来控制工具的开关。工具权限控制是安全的重要环节，建议只开启你需要的工具，减少 AI 误操作的风险。

举个例子，我给小龙虾一个任务：

```markdown
你能帮我操作浏览器，访问 ai.codefather.cn 网站并进入 AI 知识库页面，然后截图么？
```

默认是不可以操作浏览器的：

![](https://pic.yupi.icu/1/1773892961341-974d02bb-485b-422a-98d1-b131196450ef.png)

开启 Browser 工具并保存：

![](https://pic.yupi.icu/1/1773893064239-70acdd34-62ec-4a31-8045-7e7651ea3404.png)

这次它成功操作了浏览器，帮我访问了网站、导航到了指定页面并完成了截图。

![](https://pic.yupi.icu/1/1773893427843-2aeafde7-4fb7-4e4e-b0dc-cf1b4a4c2e81.png)

有了浏览器工具，你还可以让 AI 帮你自动化各种网页操作，比如自动填表单、批量采集信息等。

如果你安装了插件，可能会获取到更多工具。比如安装飞书插件后，可以按需让 AI 使用飞书的功能，比如操作日历、多维表格、文档、任务等等：

![](https://pic.yupi.icu/1/1773893614509-a6488f29-7611-4d40-9fa9-de374718493d.png)



## TTS 文字转语音

OpenClaw 内置了微软免费的 Edge TTS 文字转语音服务，不需要额外的 API Key 就能用！

除了 Edge TTS，OpenClaw 还支持 OpenAI TTS、ElevenLabs 等其他 TTS 引擎。但 Edge TTS 免费且支持多种语言和声音，对大多数人来说完全够用了。常用的中文声音包括 zh-CN-XiaoxiaoNeural（女声）、zh-CN-YunxiNeural（男声）等，完整的 TTS 配置可以参考官方文档：https://docs.openclaw.ai/tools/tts

首先，在代理的工具管理中开启 `TTS`（文字转语音工具）和 `MESSAGE`（消息发送工具）并保存。TTS 负责把文字转成语音文件，MESSAGE 负责把语音文件发送给你。

![](https://pic.yupi.icu/1/1773903118851-c854ccc6-39b0-43ca-936e-6c848fd80caa.png)

注意，还需要做一些配置，否则生成的音频文件可能为空！

我们要指定 TTS 使用 Edge 引擎、并设置中文语音。

打开 OpenClaw 的核心配置文件 `openclaw.json`，追加这段配置：

```json
"messages": {
  "tts": {
    "auto": "off",
    "provider": "edge",
    "edge": {
      "enabled": true,
      "voice": "zh-CN-XiaoxiaoNeural",
      "lang": "zh-CN"
    }
  }
}
```

也可以直接在终端输入下列命令来配置：

```bash
openclaw config set messages.tts.edge.voice "zh-CN-XiaoxiaoNeural"
openclaw config set messages.tts.edge.lang "zh-CN"
openclaw gateway restart
```

开启工具并完成配置后，试一试：

```markdown
请用语音跟我打个招呼："鱼皮系狗"
```

小龙虾调用 TTS 工具获得了语音文件，但是 AI 就卡在这里了，大概率不会把音频文件发送给你：

![](https://pic.yupi.icu/1/1773899122840-7c362884-6949-4caa-bced-b3763b3d09bc.png)

因为 TTS 只负责文本转语音，如果要把语音文件以「语音气泡消息」的方式发送给飞书，还必须控制语音文件的输出格式为 `.opus` 格式。

飞书的底层代码是这样判断的：只有文件扩展名为 `.opus` 的音频，才会以语音气泡消息的方式发送，否则只会当作文件附件。

![](https://pic.yupi.icu/1/1773899350094-794b0801-223a-4674-9481-6236df070bbd-20260319211755133.png)

可以跟小龙虾说下面这句话，这是我目前跑出来成功率最高、配置最快的方法：

```markdown
如果要发语音消息，必须执行以下步骤：
1. 先用 TTS 工具生成音频（会得到一个 MEDIA: 路径）
2. 执行 ffmpeg 命令将音频文件转为 .opus 格式（首次需安装）
3. 调用 message 工具发送 .opus 文件，从而让我通过飞书收到语音气泡消息
请先用语音跟我打个招呼："鱼皮系狗"
如果任务正常执行，把这套流程保存到长期记忆中。
```

![](https://pic.yupi.icu/1/1773902948904-9c6ab1ed-537d-4e1b-9f90-ce9af94ab9a9.png)

如果命令执行卡住，可能是 ffmpeg 下载太慢了，可以到 [官网](https://ffmpeg.org/download.html) 手动下载。

发完这条消息后，记忆文件也更新了，下次发送语音就非常方便了：

![](https://pic.yupi.icu/1/1773902998684-9a548ed4-0b11-4012-b176-b09c0976c5b3.png)

爽用！

![](https://pic.yupi.icu/1/1773903216786-c30204ef-e51d-4d41-a6da-5d0ac4bc4d84.png)

对了，OpenClaw 在聊天中还支持 `/tts` 斜杠命令来控制语音行为（比如 `/tts on`、`/tts off`），但我感觉不是很好用，一般也不用每句话都回复语音，需要的时候直接跟 AI 说 “发语音” 就好了。



## 多媒体消息发送

除了语音，OpenClaw 还支持通过各个聊天渠道发送图片、音频、视频、文件等多媒体消息。

不过要注意，不同聊天渠道对多媒体的支持情况是不一样的。比如飞书支持发送图片和语音，WhatsApp 支持发送图片、音频和视频，QQ 的多媒体支持又有自己的一套规则。所以你在用的时候可能会遇到有些格式发不出去的情况，这很正常。

如果发送多媒体不成功，不用自己到处翻文档，可以直接让小龙虾自己去研究！它会读取对应渠道的技能文档来学习具体的发送方法。比如你可以跟它说：

```markdown
帮我研究一下怎么通过飞书发送图片，然后发一张测试图片给我看看。
```

小龙虾搞明白之后，推荐让它把学到的方法保存为技能或者写入长期记忆。这样以后再发多媒体消息就顺畅多了，不用每次都重新摸索。关于技能系统的用法，可以阅读本教程的《10 Skills 技能系统》。



## 写在最后

学会了工具管理和多媒体能力，接下来我们来学习给小龙虾装技能扩展包，让它能做更多事情。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
