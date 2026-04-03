# Superpowers：核心技能库

> 让 AI 像专业程序员一样工作



你好，我是程序员鱼皮。

在前面的文章中，我们学习了各种 AI 编程工具和规范化开发框架。但你可能会想：有没有一套完整的开发流程，能让 AI 像专业程序员一样工作呢？

这篇文章，我会介绍 **Superpowers**，一套让 AI 编程助手变得更专业的软件开发流程。



## 一、什么是 Superpowers？

[Superpowers](https://github.com/obra/superpowers) 是一套让 AI 编程助手变得更专业的 **软件开发流程**。它不仅为 Claude Code 提供了一套可组合的 **编程技能包**，还提供了规范和指令，确保 AI 能够正确使用这些技能。

传统的 AI 编程，你一说需求它就开始噼里啪啦地写，结果可能并不是你想要的。而装了 Superpowers 之后，AI 会先问清楚你到底想做什么，然后出设计方案让你确认，接着制定详细的执行计划，最后才分步骤去实现，每一步还会自我检查。

就像给一个刚进公司啥都不懂的 AI 加上了超能力，瞬间让它有了专业程序员的开发习惯。

![](https://pic.yupi.icu/1/%E6%BC%AB%E7%94%BB%E5%9B%BE8%E5%A4%A7.jpeg)



## 二、快速上手 Superpowers

让我通过一个实际例子，带你快速上手 Superpowers。

### 1、安装 Superpowers

参考 [Superpowers 官方文档](https://github.com/obra/superpowers)，在 Claude Code 中运行以下命令安装。

先注册市场：

```bash
/plugin marketplace add obra/superpowers-marketplace
```

![](https://pic.yupi.icu/1/image-20260116171109190.png)

再从市场安装插件：

```bash
/plugin install superpowers@superpowers-marketplace
```

![](https://pic.yupi.icu/1/image-20260116171125164.png)

安装后运行 `/help` 查看可用命令，你会看到这 3 个命令

- `/superpowers:brainstorm` 通过和用户交互来不断改进设计
- `/superpowers:write-plan` 创建实现方案
- `/superpowers:execute-plan` 批量执行方案

![](https://pic.yupi.icu/1/image-20260116171300633.png)



### 2、标准工作流程

下面以开发一个 "用户注册模块" 为例，演示 Superpowers 官方的标准工作流程。

首先，在终端中运行 `claude` 命令来启动 Claude Code，然后按照下面的 7 个步骤操作：

#### 1）Brainstorming 头脑风暴 => 对齐需求

选择 `/superpowers:brainstorm` 命令并输入需求：

![](https://pic.yupi.icu/1/image-20260116175524611.png)

Superpowers 不会急着写代码，而是先通过多轮问答和你对齐需求，比如：

- 用户注册模块的主要场景是什么？
- 希望支持哪些注册方式？

![](https://pic.yupi.icu/1/image-20260116175456666.png)

通过交互问答，AI 会探索不同方案、不断改进设计。

![](https://pic.yupi.icu/1/image-20260116175907783.png)

当需求和方案确认无误后，它会自动将详细的设计文档保存到 `docs/plans/` 目录。

![](https://pic.yupi.icu/1/image-20260116180740987.png)



#### 2）Using Git Worktrees 创建独立工作空间（可选）

设计方案通过后，Superpowers 会帮你创建一个 Git 工作树（worktree），在新分支上建立隔离的工作空间，运行项目初始化，并验证测试基线是否干净。这样可以避免污染主分支。

这一步是可选的，我这里直接让 AI 继续执行，看看会发生什么：

![](https://pic.yupi.icu/1/image-20260116181020601.png)



#### 3）Writing Plans 制定实施计划

运行 `/superpowers:write-plan` 命令，让 Superpowers 生成一份详细的实施计划，把开发任务拆解成多个原子级步骤（每个任务控制在 2 ~ 5 分钟）。

我这里 AI 直接自动执行了，省了一步命令~

![](https://pic.yupi.icu/1/image-20260116180907360-20260116180953363-20260116181058928-20260116181118631.png)

查看 AI 生成的实施计划文档，每个任务都包含：

- 精确的文件路径
- 完整的代码内容
- 验证步骤

![](https://pic.yupi.icu/1/image-20260116181910011.png)

好家伙，这哪里是实施计划文档啊，感觉大多数代码都写出来了！

![](https://pic.yupi.icu/1/image-20260116181959589.png)



#### 4）执行任务

运行 `/superpowers:execute-plan` 命令，Superpowers 会采用以下方式之一执行：
- 子代理驱动开发（Subagent-Driven Development）：为每个任务分配一个全新的子代理，经过两阶段审查（规范合规性检查 + 代码质量检查）
- 批量执行（Executing Plans）：分批执行任务，在关键节点暂停让人工检查

我这里 AI 直接问我想要哪种方式：

![](https://pic.yupi.icu/1/image-20260116182128737.png)

我盲选一手 Subagent-Driven 方式，AI 自动选择了对应的开发技能：

![](https://pic.yupi.icu/1/image-20260116182244311.png)

然后 AI 就开始干活了：

![](https://pic.yupi.icu/1/image-20260116182445078.png)



#### 5）Test-Driven Development 测试驱动开发

在实现过程中，Superpowers 会强制执行 `红-绿-重构` 流程：
- 先写失败的测试
- 运行测试，确认失败
- 写最小化的代码让测试通过
- 运行测试，确认通过
- 提交代码

![](https://pic.yupi.icu/1/image-20260116183728764.png)

如果发现有代码是在测试之前写的，Superpowers 会删除它，强制你先写测试。



#### 6）Code Review 代码审查

每完成一批任务后，Superpowers 会自动触发代码审查，对照计划检查代码，按严重程度报告问题。如果发现严重问题（Critical），会阻止继续进行。

![](https://pic.yupi.icu/1/image-20260116182947482.png)



#### 7）完成开发

所有任务完成后，Superpowers 会验证所有测试是否通过：

![](https://pic.yupi.icu/1/image-20260116194339313.png)

然后 AI 可能会提供几个选项，比如合并到主分支 / 创建 PR / 保留分支 / 丢弃更改。

如果你确定功能没有问题，可以利用 Superpowers 内置的技能来完成开发分支的清理工作。

![](https://pic.yupi.icu/1/image-20260116194520921.png)



## 三、Superpowers 的优缺点

这套 “先设计后编码” 的规范流程走下来，代码质量会更有保障，不过代价就是速度确实比让 AI 直接生成代码会慢很多。真的是慢很多！就这么个需求我搞了半个多小时！！！

![](https://pic.yupi.icu/1/image-20260116183405162.png)

如果你正在开发大型项目，需要团队协作，那么可以试试 Superpowers，前期多花的时间会在后期省回来。但是如果你只是想写个简单的脚本或者快速验证一个想法，用它就有点儿牛刀杀鸡了，真没必要。



## 写在最后

看到这里，相信你已经对 Superpowers 有了基本的了解。

**Superpowers 能让 AI 像专业程序员一样工作，但代价是开发速度会变慢。**

如果你正在做大型项目、需要高质量的代码、团队协作，那么 Superpowers 会是不错的选择。但如果你只是做简单的个人项目，直接让 AI 生成代码会更快。

选择合适的工具，才能事半功倍。

到这里，我们已经学习了多种规范化开发工具，希望你能找到最适合自己的开发方式。



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
