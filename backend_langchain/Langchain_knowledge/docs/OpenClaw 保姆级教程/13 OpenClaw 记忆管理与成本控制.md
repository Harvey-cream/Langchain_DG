# OpenClaw 记忆管理与成本控制

> 管理 AI 的记忆、用 Git 备份、省钱技巧大全

你好，我是鱼皮。

养龙虾时间长了，你会发现两个问题：一是小龙虾的记忆越来越乱，二是大模型的账单越来越高。

这篇教程教你怎么管理记忆、备份配置、控制成本。



## 记忆系统

OpenClaw 的记忆系统是基于纯 Markdown 文件的，非常直观。

主要有两层记忆：

1. 长期记忆 `MEMORY.md`：存放持久的重要信息，比如用户偏好、关键决策、重要流程，这个文件会在每次会话开始时加载。
2. 每日日记 `memory/YYYY-MM-DD.md`：每天一个文件，记录当天的对话要点和运行笔记，AI 会在会话开始时加载今天和昨天的日记。

你可以在 Web 控制台的代理模块中查看这些记忆文件，也可以直接到 `~/.openclaw/workspace/` 目录下用文本编辑器打开查看。

![](https://pic.yupi.icu/1/image-20260319205651111.png)

如果想让小龙虾失忆，方法也很简单：删除对应的记忆文件就好了。

比如删掉 `MEMORY.md` 就会清空长期记忆，删掉 `memory/` 目录下的日记文件就会清空对应日期的记忆。当然也可以直接跟小龙虾说 “把你的记忆文件清空”。

你还可以通过命令行来管理记忆：

- `openclaw memory list`：查看所有记忆文件列表
- `openclaw memory show`：查看记忆文件的具体内容

如果你想优化记忆管理的质量，可以安装 ontology 技能，它会帮你的小龙虾建立一个结构化的本地知识图谱，让记忆更有条理，而不是一股脑全塞在一个文件里。

![](https://pic.yupi.icu/1/1773915071507-4fb69789-7878-4ec4-b369-b08b01ac4003.png)



## Git 管理配置文件

养龙虾的过程中，很容易出现一些问题，比如不小心改错了文件、把龙虾人格损坏了等等。因此建议利用 Git 代码版本控制工具来托管整个 `.openclaw` 目录。

很多非程序员朋友应该是不了解 Git 的，建议直接让一个靠谱的 AI 编程工具（比如 Claude Code 或者 Cursor）帮你做：

```markdown
你是 OpenClaw 专家，我正在学习使用 OpenClaw，请你完整分析官方文档 https://docs.openclaw.ai/，然后帮我利用 Git 来管理 ~/.openclaw 目录，起到备份的作用，注意要合理忽略一些不需要管理的文件
```

![](https://pic.yupi.icu/1/1773914094278-80768659-0a00-4b26-83a2-04b224c47e1b.png)

可以看到重要配置被 Git 托管了，出了问题可以快速还原：

![](https://pic.yupi.icu/1/1773914374267-a3ddcc59-2f29-4a19-8301-4bb06337e205.png)

当然你也可以自己进入目录，手动执行命令完成初始化。

需要注意的是，一定要先配好 `.gitignore` 文件来忽略不需要管理的内容（比如浏览器数据、媒体文件、会话日志、node_modules 等），避免提交太多无用文件。

![](https://pic.yupi.icu/1/1773914135096-0cc52de9-0731-4b2e-a0d4-19c1a9bc91d3-20260319211801170.png)

核心步骤如下（看不懂的同学跳过即可）：

```bash
cd ~/.openclaw

# 先创建 .gitignore 文件，忽略不需要管理的内容
cat > .gitignore << 'EOF'
# 浏览器数据（体积大，可重建）
browser/
# 媒体文件（收发的图片/音频/视频）
media/
# 日志文件
logs/
# 配置备份文件
openclaw.json.bak
# node_modules
**/node_modules/
# 会话数据（频繁变化的对话记录）
agents/*/sessions/*.jsonl
agents/*/sessions/sessions.json
# 更新检查状态
update-check.json
EOF

# 初始化 Git 仓库并首次提交
git init
git add .
git commit -m "init: OpenClaw 配置备份"
```

注意，这个目录自己看就好了。千万别这么好心，开源自己的 OpenClaw 目录到 GitHub 上，搞不好把你的各种敏感配置（API Key、App Secret 之类的）全泄露出去。

已经完成一次 Git 提交之后，就可以让小龙虾帮你定时提交备份了：

```markdown
我已经用 Git 托管了整个 openclaw 的工作目录，请你创建定时任务，之后每天凌晨 3 点进行一次提交，起到备份的作用
```

![](https://pic.yupi.icu/1/1773914556135-f5b13e85-b9a9-4923-9100-d169b64dc37a.png)

之后每天凌晨小龙虾会自动帮你提交一次配置快照，再也不怕 AI 手滑把配置搞崩了，随时可以通过 Git 回滚到任意历史版本。



## 成本控制技巧

注意，养龙虾是要花钱的！大模型 API 按照 Token 收费。所以这里鱼皮再把省钱技巧汇总一下：

1. 选对模型：不需要每次都用最贵的模型，简单聊天用国产免费模型（如智谱 GLM），复杂任务再切到能力更强的模型
2. 及时开新会话：聊完一个话题就 `/new`，避免上下文越积越多
3. 善用压缩：对话太长了就 `/compact` 一下，能大幅减少 Token 消耗
4. 开启快速模式：`/fast on` 让 AI 回答更简短
5. 关闭不需要的技能：技能越多，注入到上下文的信息越多，Tokens 消耗越大
6. 子智能体用便宜模型：`openclaw config set agents.defaults.subagents.model "zai/glm-4.7-flash"`
7. 心跳降频或关闭：如果用不到心跳功能，设置 `agents.defaults.heartbeat.every: "0m"` 关闭
8. 查看用量：`/usage full` 或 `/status` 随时关注 Token 消耗情况
9. 定时任务用独立会话 + 便宜模型：避免定时任务加载整个主会话的上下文

除了上面这些日常省钱技巧，还有几个值得了解的进阶信息：

- API 费用参考：不同模型的价格差异很大，建议参考 [OpenClaw 官方的 API 费用文档](https://docs.openclaw.ai/reference/api-usage-costs)，进一步了解计费规则
- 提示词缓存（Prompt Caching）：部分模型支持提示词缓存，可以显著降低重复内容的费用。如果你的使用场景中有大量重复的系统提示词，这个功能能帮你省不少钱。参考：https://docs.openclaw.ai/reference/prompt-caching
- Token 消耗追踪：想知道你的龙虾每天到底花了多少钱，可以参考官方的用量追踪文档：https://docs.openclaw.ai/concepts/usage-tracking



## 问题自检和修复

OpenClaw 提供了很多命令和方法，可以帮你检查 OpenClaw 的状态，尤其是在小龙虾抽抽、无法运行的时候。

1）优先运行 `openclaw doctor` 健康检查，它会帮你扫描配置、频道、模型认证等各方面的问题：

![](https://pic.yupi.icu/1/1773912981576-08e5d6a4-56e0-41bc-9780-f1b05a4d6cf0.png)

然后输入 `openclaw doctor --fix` 可以自动修复发现的问题。

2）`openclaw status` 查看运行状态，包括网关、频道、会话等所有信息：

![](https://pic.yupi.icu/1/1773913110926-ce687f86-2724-4d4f-9b43-3e8de19d84b5.png)

3）`openclaw gateway start|stop|restart` 管理网关服务。

很多时候无法打开网页控制台、或者没办法和小龙虾对话，大概率是网关服务挂了。

需要注意几种不同命令的区别：

- `gateway run` 是在前台运行（关闭终端就停了）
- `gateway start` 是作为后台服务运行（关闭终端也不影响）
- `gateway restart` 是重启后台服务

日常使用中，改完配置后 `restart` 一下就好。

4）`openclaw dashboard` 打开 Web 管理界面，可以查看对话记录、技能管理、频道管理、Agent 状态等。

前面我们也看到了，尤其是在玩多智能体的时候，了解 AI 的状态还是很重要的。万一某个 AI 执行卡住了，可以看下它到底在干神魔：

![](https://pic.yupi.icu/1/1773913207492-38e2fea6-75d8-4577-ac3a-54322a52d552.png)

5）`openclaw logs --follow` 实时查看日志。

估计大多数同学用不到，真出了控制台搞不定的问题后，再来看实时日志，然后把日志发给 AI，让 AI 帮你分析和解决吧~

![](https://pic.yupi.icu/1/1773913345897-7e4a61cb-c2f1-488d-a469-c10bbfee496c.png)

对了，如果你还能跟小龙虾对话，也可以直接让它自我检查和修复问题。这也是使用 AI 智能体的小技巧：完成任务后让 AI 检查自己的输出，找边界情况和潜在问题。

比如你可以跟它说：帮我检查一下 OpenClaw 的配置有没有什么问题。

它会自己去读配置文件、验证连接状态、修复异常，不过能不能修复成功，就看运气了。



## 写在最后

配置备份好了，钱包也保住了。最后一篇正式教程，我们来聊聊安全，这可能是最重要的一篇。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
