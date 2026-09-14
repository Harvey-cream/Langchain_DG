# OpenClaw 接入 QQ 和飞书

> 把 OpenClaw 接入手机聊天软件，随时随地养虾

你好，我是鱼皮。

安装好 OpenClaw 之后，总不能每次都打开电脑上的网页控制台才能跟小龙虾对话吧？把它接入你常用的聊天软件，掏出手机就能给龙虾下达任务，这才是 OpenClaw 的正确使用方式。

这篇教程教你接入 QQ 和飞书两大平台。



## 接入 QQ

腾讯专门为 OpenClaw 搞了一个快捷接入通道，几步就能搞定！

打开 QQ 机器人 OpenClaw 接入页面，用 QQ 扫码登录：

> 指路：https://q.qq.com/qqbot/openclaw/index.html

![](https://pic.yupi.icu/1/image-20260310152123827.png)

点击「创建机器人」，直接秒出！

![](https://pic.yupi.icu/1/image-20260310152325274.png)

创建完成后，手机 QQ 立刻就会收到小龙虾打招呼的消息：

![](https://pic.yupi.icu/1/image-20260310153005879.png)

然后可以修改机器人的头像、昵称等信息，给你的龙虾起个好听的名字吧~

![](https://pic.yupi.icu/1/image-20260310152409339.png)

接下来是最关键的一步。页面上会显示三条配置命令，你只需要依次复制这 3 条命令到终端（PowerShell）中执行就可以了。

注意命令中包含你的密钥信息，不要泄露给别人！

![](https://pic.yupi.icu/1/image-20260310152443829.png)

到终端中依次执行命令：

![](https://pic.yupi.icu/1/image-20260310152544861.png)

接入成功后，你可以在 OpenClaw 的网页控制台的「频道」（Channels）板块看到已经接入了 QQ 机器人渠道：

![](https://pic.yupi.icu/1/image-20260310152846134.png)

现在，掏出手机试试吧！

直接在 QQ 上给小龙虾发消息下达任务，比如让它查看电脑配置、或者帮你写一篇文章。完成速度很快，而且支持 Markdown 格式输出，阅读体验不错：

![](https://pic.yupi.icu/1/image-20260310153115908.png)

如果你好奇它背后做了些什么，可以在 OpenClaw 的网页控制台中查看跟 QQ 机器人的完整对话记录：

![](https://pic.yupi.icu/1/image-20260310152754120.png)



## 接入飞书

飞书有两种接入方式。推荐使用更简单的官方插件方式，几分钟就能搞定；如果官方插件不适用，也可以手动在飞书开放平台创建机器人。



### 方式一：官方插件扫码接入（推荐）

官方提供了对接飞书的插件，先在终端输入一行命令安装：

```bash
npx -y @larksuite/openclaw-lark-tools install
```

![](https://pic.yupi.icu/1/1773815583908-7eaec4f6-7f56-47f2-9e12-45d0d2a329ae.png)

然后直接在命令行中用飞书扫码对接机器人（Windows 的 PowerShell 无法正常显示二维码，需要改为使用自带的 CMD 命令行）。

通过手机操作来创建机器人就好，整个流程非常傻瓜式：

![](https://pic.yupi.icu/1/1773815929716-12c2bc15-90e2-4409-ac3f-c4cab84c1167.png)

操作完成后，在命令行能看到配置飞书机器人成功，在 OpenClaw 网页控制台的频道模块也能看到新增了 Feishu 频道：

![](https://pic.yupi.icu/1/1773815823665-dd4a0c51-09cb-4476-9173-e4a45b9de00f.png)

你会在飞书收到应用审批的消息，进入管理后台审核即可：

![](https://pic.yupi.icu/1/1773815955358-857f8503-79c6-42bf-8938-c2f35eb64e0d.png)

点击审核通过，通过后机器人会自动发布上线：

![](https://pic.yupi.icu/1/1773816002775-07a84fbf-e296-4d46-bca8-da9d0eb73a74.png)

然后在飞书搜索你的机器人名称：

![](https://pic.yupi.icu/1/1773816125248-a6eb33dd-986e-4aa9-8f81-29dc7ca6642f.png)

进入聊天，先发送 `/feishu auth` 授权，傻瓜式操作：

![](https://pic.yupi.icu/1/1773816193729-5290671b-02be-4cae-9f44-a2efce40c77e.png)

然后跟小龙虾打个招呼，能够成功收到小龙虾回复的消息：

![](https://pic.yupi.icu/1/1773816269856-bd61502c-0b6d-4d75-aea1-810838cbe4d4.png)

飞书插件还支持开启流式响应，实现打字机效果。打开终端，执行命令：

```bash
openclaw config set channels.feishu.streaming true
```

![](https://pic.yupi.icu/1/1773816381282-45c2d6e2-8c82-46d9-9682-0bfab7d0e1a2.png)

配置之后，体验比之前好了不少：

![](https://pic.yupi.icu/1/1773816481362-bfbdd84f-8385-4174-8c81-34dbc2e0ee3b.png)



### 方式二：手动创建飞书机器人

如果方式一不适用（比如企业飞书有权限限制），可以手动在飞书开放平台创建机器人应用。

📺 本方式对应视频教程：https://www.bilibili.com/video/BV1QPcDz1ECF

整个流程分为 5 步：飞书创建机器人应用 → OpenClaw 添加飞书频道 → 配置飞书事件 → 私聊配对 → 解锁多媒体能力。

**1）飞书创建机器人应用**

登录飞书开放平台，进入开发者后台，点击「创建企业自建应用」：

> 指路：https://open.feishu.cn/app

![](https://pic.yupi.icu/1/1773296607372-9fd70bce-3491-4704-8905-9d3ea4de6242.png)

填写应用名称和描述，给你的机器人起个好听的名字：

![](https://pic.yupi.icu/1/1773296500510-ea79d7b3-bb4b-403b-bcdc-d9a05eb38490.png)

创建完成后进入应用详情页，在「添加应用能力」中点击添加机器人能力：

![](https://pic.yupi.icu/1/1773296726095-512cdb41-f5fb-428e-9ed8-69bb1347d51c.png)

然后进入左侧「权限管理」页面开通权限：

![](https://pic.yupi.icu/1/1773296803932-ec256465-793c-4c2d-92f7-74badd59a1f2.png)

如果你的飞书里没有敏感信息，可以直接把 `im:`、`contact:`、`file:` 等相关的权限全勾上。如果需要精细控制权限，最少只需要开通 `im:message`、`im:chat`、`contact:user.base:readonly` 这 3 个。

也可以通过批量导入 JSON 配置一键搞定权限，在权限管理页面选择批量导入，把下面的 JSON 粘贴进去：

```json
{
  "scopes": {
    "tenant": [
      "aily:file:read",
      "aily:file:write",
      "application:application.app_message_stats.overview:readonly",
      "application:application:self_manage",
      "application:bot.menu:write",
      "cardkit:card:read",
      "cardkit:card:write",
      "contact:user.employee_id:readonly",
      "corehr:file:download",
      "event:ip_list",
      "im:chat.access_event.bot_p2p_chat:read",
      "im:chat.members:bot_access",
      "im:message",
      "im:message.group_at_msg:readonly",
      "im:message.p2p_msg:readonly",
      "im:message:readonly",
      "im:message:send_as_bot",
      "im:resource"
    ],
    "user": [
      "aily:file:read",
      "aily:file:write",
      "im:chat.access_event.bot_p2p_chat:read"
    ]
  }
}
```

![](https://pic.yupi.icu/1/1773298009798-41cb86da-b623-4473-aa4e-2dd9841c8836.png)

权限配置完成后，点击「创建版本」发布应用：

![](https://pic.yupi.icu/1/1773298097229-3cea39d0-3ad3-45d5-863f-cc026b5ea53d.png)

填写版本号和更新说明、按需选择是否对外共享，然后申请线上发布：

![](https://pic.yupi.icu/1/1773298202460-f8a03417-88dc-4d2d-8f2b-281930136c0d.png)

进入飞书管理后台审核通过即可：

![](https://pic.yupi.icu/1/1773298275930-0bd44fab-0947-4df9-8dda-f60cf5e41ce2.png)

审核通过后，回到应用的「凭证与基础信息」页面，获取 App ID 和 App Secret，复制保存好，下一步要用。注意这俩是你机器人的钥匙，千万不要泄露给别人！

![](https://pic.yupi.icu/1/1773298520178-5a6bdfd0-a8f0-41e4-8ad6-5ab762e44060.png)

**2）OpenClaw 添加飞书频道**

拿到 App ID 和 App Secret 之后，打开终端执行命令：

```bash
openclaw channels add
```

![](https://pic.yupi.icu/1/1773299051612-cb1dfc8a-df1d-4bca-9509-e73e57363924.png)

跟着向导一步步操作就好。先选择 Feishu 频道，然后输入 App Secret 和 App ID，连接模式选择 WebSocket 长连接，国内用户选择 Feishu 频道：

![](https://pic.yupi.icu/1/1773299210452-5c321afe-a7ce-4299-963a-4d0e49a81cd1.png)

然后配置私聊的访问控制方式，建议选择配对码模式，更安全：

![](https://pic.yupi.icu/1/1773299304526-e041393a-a688-4b70-b33c-4ab5be46d5db.png)

对接完成后，在 OpenClaw 网页控制台的频道列表中就能看到飞书了：

![](https://pic.yupi.icu/1/1773299448414-826b13d2-768a-46e4-bdb0-c2b10449ec5a.png)

**3）配置飞书事件**

频道接好了，还需要在飞书侧配置事件订阅，不然飞书不知道该把哪些消息推给 OpenClaw。

回到飞书开发者后台，进入「事件与回调」配置，开启长连接的事件订阅方式：

![](https://pic.yupi.icu/1/1773299570311-6142efd0-a693-413b-a377-8be1dc06b6ae.png)

然后添加事件，至少要添加「接收消息」（`im.message.receive_v1`）这一项：

![](https://pic.yupi.icu/1/1773299742014-c26249e1-54f9-484f-a478-0c44755648f6.png)

配置好事件后，别忘了最关键的一步 —— 发布新版本！改了配置不发布是不会生效的，很多人就卡在这一步：

![](https://pic.yupi.icu/1/1773299833600-04aad379-5b84-4b8d-a766-1fad16990586.png)

**4）私聊配对**

在飞书中搜索你创建的机器人，进入私聊，随便说一句话。发送第一条消息后，机器人会返回一个配对码：

![](https://pic.yupi.icu/1/1773300030650-4dfd39ba-4ed0-49c8-ba59-d530ba3f59b2.png)

在终端中执行命令完成配对，把 `<配对码>` 替换成你自己收到的那串配对码：

```bash
openclaw pairing approve feishu <配对码>
```

执行成功后会提示配对完成：

![](https://pic.yupi.icu/1/1773300229629-5037724e-ef68-40fb-b60e-8a30b5769a64.png)

配对成功后，再发一条消息试试，这次 AI 就能成功回复了！

![](https://pic.yupi.icu/1/1773300290276-39d7d920-1692-4335-afde-2099a52131f1.png)

**5）解锁多媒体能力**

基础对话搞定了，但飞书支持丰富的消息类型，可以让小龙虾给你发送图片、音视频、文件。

你只需要给小龙虾一句引导，让 AI 自己学习怎么发送多媒体消息：

```markdown
飞书支持给用户发送图片、文件、音频、视频并直接浏览，请你详细了解具体的发送方法，并且必须要把需要发送的文件放到 workspace 工作空间中。你必须记住这些方法，之后快速地给我发送想要的内容。
```

AI 会去读取飞书技能文档，学习怎么发送多媒体消息，之后你就可以让它拍照、录音、找文件，通通发到飞书：

![](https://pic.yupi.icu/1/1773300442755-f6111ee9-d521-402d-8d3b-418e94952486.png)



## 实用小技巧

在飞书对话框里可以直接输入斜杠命令来控制 OpenClaw 的行为，不需要打开网页控制台，非常方便。



### 1、斜杠命令 /new 新开一个对话

直接在对话框里输入 `/new`，可以清空上下文开启一段新对话，让 AI 更专注当前任务，还能节省 Tokens 费用。

![](https://pic.yupi.icu/1/1773302809726-13ddf456-ca4a-4efa-b755-6fce84f1ae4a.png)



### 2、斜杠命令 /verbose 开启调试模式

输入 `/verbose on` 后，AI 会输出更多执行细节，方便你了解它到底在干什么，排查问题也更方便。

比如让 AI 打开网站并截图，能够看到它通过编写 JS 脚本、打开了浏览器并执行截图的过程：

![](https://pic.yupi.icu/1/1773303846475-f9662a4e-377b-43d1-95ed-16c789948ee2.png)



## 写在最后

恭喜完成基础安装和接入！从现在开始，你可以掏出手机就跟你的小龙虾聊天、让它帮你干活了。

如果你想把 OpenClaw 接入微信，可以阅读《OpenClaw 接入微信保姆级教程》。

从下一篇开始进入进阶玩法，首先学习如何初始化和配置你的小龙虾。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
