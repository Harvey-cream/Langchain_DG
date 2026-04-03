# Spec-kit：规范驱动开发框架

> 让 AI 按照专业流程开发项目

你好，我是程序员鱼皮。

在前面的文章中，我们学习了如何用 AI 快速生成代码。但你可能会发现，AI 有时候会 “想到哪写到哪”，生成的代码可能不符合预期，或者项目做到一半就乱套了。

有没有办法让 AI 按照专业的流程来开发项目呢？

这篇文章，我会介绍 **Spec-kit**，一个由 GitHub 推出的规范驱动开发框架，让 AI 像专业程序员一样工作。

让我们开始吧！



## 一、什么是 Spec-kit？

[Spec-kit](https://github.com/github/spec-kit) 是 GitHub 推出的规范驱动开发（SDD）框架。

什么是规范驱动开发呢？

传统开发流程是：想到什么写什么，边写边改，最后再补文档。这样容易导致需求不清晰、代码和文档对不上。

而规范驱动开发的思路正好相反：**先把需求写成规范文档，并且把规范文档当作代码的唯一真相来源**。你可以把规范文档理解为 "法律条文"，它包含了详细的需求描述、系统设计和接口定义。AI 必须严格遵守这些条文来生成代码，确保产出完全符合预期。

![](https://pic.yupi.icu/1/%E6%BC%AB%E7%94%BB%E5%9B%BE4%E5%A4%A7.jpeg)



## 二、快速上手 Spec-kit

让我通过一个实际例子，带你快速上手 Spec-kit。

### 1、安装 Spec-kit

首先打开终端，利用 uvx 命令直接安装运行 Specify 工具，并初始化一个项目：

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init my-project
```

![](https://pic.yupi.icu/1/image-20260116141308958.png)

选择你使用的 AI 编程工具，Spec-kit 支持 Claude Code、GitHub Copilot 等几乎所有主流编程工具。这里我选 Claude Code：

![](https://pic.yupi.icu/1/image-20260116141507190.png)

根据操作系统选择脚本类型，Windows 选下面的，其他选上面的：

![](https://pic.yupi.icu/1/image-20260116141537030.png)

执行完这个命令后，会在当前目录下创建一个 `my-project` 文件夹：

![](https://pic.yupi.icu/1/image-20260116141613246.png)

文件夹里面包含了这些核心文件：

- `.specify/memory/constitution.md`：项目的基本准则和约定
- `.specify/scripts/`：一些可执行脚本
- `.specify/templates/`：模板文件
- `.claude/commands/`：定义了一套内置的斜杠命令，让你在 AI 编程工具中可以直接调用

![](https://pic.yupi.icu/1/image-20260116142528820.png)

初始化程序还给了我们一些指引，告诉我们接下来如何运用这些命令来开发项目。

![](https://pic.yupi.icu/1/image-20260116141715310.png)

用 Claude Code 打开这个项目文件夹，就可以在对话中使用定义好的命令了。

![](https://pic.yupi.icu/1/image-20260116142740271.png)



### 2、标准化开发流程

接下来就是标准化的开发流程，参考 [官方文档](https://github.com/github/spec-kit)，主要分为 7 个步骤：

#### 1）Constitution 制定项目准则

运行 `/speckit.constitution` 命令，定义项目的基本原则、代码规范、性能标准等。这是项目的 "宪法"，后续所有开发都要遵守。

比如：

```markdown
/speckit.constitution 禁止使用蓝紫渐变色风格的 UI
```

💡 如果你要做中文项目，最好在制定项目准则时就明确告诉 AI “整个网站使用中文”。

![](https://pic.yupi.icu/1/image-20260116160508054.png)

AI 更新了项目准则文档：

![](https://pic.yupi.icu/1/image-20260116160610169.png)

建议每一步我们都用 Git 提交一个版本，这样出了问题后能及时回滚，也便于我们看到每一步改动的文件。

![](https://pic.yupi.icu/1/image-20260116160745548.png)



#### 2）Specify 编写功能规范

运行 `/speckit.specify` 命令，描述要做什么功能、为什么做、用户需求是什么。比如：

```markdown
/speckit.specify 我想做个【自动提醒我喝水的网站】
```

![](https://pic.yupi.icu/1/image-20260116161231223.png)

AI 为这次的需求创建了一个新的 Git 分支，防止污染现有项目。在这个分支下创建了一个需求规格文档（spec.md） + 一个需求检查文档（requirements.md）。

![](https://pic.yupi.icu/1/image-20260116161307642.png)

需求规格文档非常详细，还包含了边缘测试用例，针对用户各种可能的操作进行处理。

![](https://pic.yupi.icu/1/image-20260116161926017.png)

需求检查文档中记录了 AI 对于需求的理解，打钩表示 AI 理解并确认了：

![](https://pic.yupi.icu/1/image-20260116161500358.png)



#### 3）Clarify 澄清不明确的地方（可选）

如果你发现需求检查文档中有的条目没有打钩，那你需要通过 Clarify 命令来让 AI 引导你进一步明确需求，直到所有的条目都打上勾。

运行 `/speckit.clarify` 命令，AI 会提出结构化的问题，让你来回答。从而帮你填补需求中的空白，比如边界情况、错误处理等。

![](https://pic.yupi.icu/1/image-20260116162702812.png)



#### 4）Plan 制定技术方案

运行 `/speckit.plan` 命令，让 AI 决定用什么技术栈、系统架构、数据模型、API 接口等。

![](https://pic.yupi.icu/1/image-20260116163506902.png)

制定技术方案完成，这次生成了一大堆文档，简单了解一下：

- CLAUDE.md 项目开发指南，记录技术栈和项目结构，用于指导 Claude Code 接下来如何开发
- quickstart.md 快速入门指南，包含 6 个实施阶段和部署方案
- plan.md 实施方案，定义了纯客户端架构、存储策略、宪法合规性检查等
- data-model.md 数据模型设计，定义了 4 个核心实体（提醒设置、水量日志、每日进度、历史记录）和存储结构
- research.md 技术研究文档，记录了 8 项关键技术决策
- contracts/api-contract.md API 接口文档

![](https://pic.yupi.icu/1/image-20260116164021646.png)

接下来，我们就可以准备开发实现了。

![](https://pic.yupi.icu/1/image-20260116163553725.png)



#### 5）Tasks 拆解任务

运行 `/speckit.tasks` 命令，把计划拆解成可执行的任务列表，并标注依赖关系和优先级。

![](https://pic.yupi.icu/1/image-20260116164537006.png)

生成了一个任务列表文档，每一步要做什么都非常清晰：

![](https://pic.yupi.icu/1/image-20260116164612533.png)



#### 6）Analyze 分析检查（可选）

运行 `/speckit.analyze` 命令，检查规范、计划、任务是否完整一致，提前发现设计缺陷。

![](https://pic.yupi.icu/1/image-20260116164936733.png)

可以看到，AI 没有检查出问题，还让我自信地进行下一步，真爽死了！



#### 7）Implement 执行实现

最后，运行 `/speckit.implement` 命令，让 AI 按照任务列表生成代码。

![](https://pic.yupi.icu/1/image-20260116170006815.png)

大功告成，看一下效果~

![](https://pic.yupi.icu/1/image-20260116170146827.png)

因为我这里始终没有提到使用中文输出，所以网站内容都是英文的，不过我感觉效果还可以。



## 三、Spec-kit 的优缺点

到这里，我们已经学会了如何用 Spec-kit 开发完整项目，再复习一下完整流程：

![](https://pic.yupi.icu/1/%25E6%25BC%25AB%25E7%2594%25BB%25E5%259B%25BE5%25E5%25A4%25A7.jpeg)

即使不用 Spec-kit，我们开发完整项目时也可以人工遵循这些步骤。

这种模式最大的好处是 **对齐**。所有人都基于同一份清晰的规范文档工作，大家对需求的理解高度一致，既减少了沟通中的误解，又能确保代码质量。

不过缺点也很明显，对于小项目，本来直接写代码几分钟就能搞定了，上面这套流程走下来差不多要半个小时！

所以这套流程比较适合团队从 0 开始做完整的新项目，虽然流程比直接写代码慢一些，但能大大降低返工的风险，长远来看反而更高效。



## 写在最后

看到这里，相信你已经对 Spec-kit 有了基本的了解。

**Spec-kit 不是万能的，但在合适的场景下，它能帮你大幅提升项目质量。**

如果你正在做大型项目、需要团队协作、对代码质量要求高，那么可以试试 Spec-kit。但如果你只是想写个简单的脚本或者快速验证一个想法，直接让 AI 生成代码会更快。

选择合适的工具，才能事半功倍。

在接下来的文章中，我会继续介绍其他规范化开发工具，帮你找到最适合自己的开发方式。



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
