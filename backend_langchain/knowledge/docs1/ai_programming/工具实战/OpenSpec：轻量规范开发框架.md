# OpenSpec：轻量规范开发框架

> 让文档和代码始终保持同步



你好，我是程序员鱼皮。

在前面的文章中，我们学习了 Spec-kit 规范驱动开发框架。但你可能会觉得 Spec-kit 的流程太复杂了，有没有更轻量的选择呢？

这篇文章，我会介绍 **OpenSpec**，一个轻量的规范驱动开发框架，比 Spec-kit 更简单易用，适合在现有项目上迭代功能。



## 一、什么是 OpenSpec？

[OpenSpec](https://openspec.dev/) 是一个轻量的规范驱动开发框架，比 Spec-kit 更简单易用。

它的核心理念是把规范文档作为代码库的一部分，每次改功能都 **先写变更提案** => 确认后再实现 => 实现完再把变更归档到规范文档中，让文档和代码始终保持同步。

![](https://pic.yupi.icu/1/%E6%BC%AB%E7%94%BB%E5%9B%BE6%E5%A4%A7.jpeg)



## 二、快速上手 OpenSpec

让我通过一个实际例子，带你快速上手 OpenSpec。

### 1、安装 OpenSpec

访问 [OpenSpec 官方仓库](https://github.com/Fission-AI/OpenSpec/) 查看文档。

首先确保你的电脑安装了符合要求的 Node.js 版本（比如我这里要求 Node.js >= 20.19.0），然后全局安装 OpenSpec CLI：

```bash
npm install -g @fission-ai/openspec@latest
```

进入你的项目目录，运行初始化命令：

```bash
openspec init
```

初始化过程中会让你选择要集成的 AI 工具（比如 Claude Code、Cursor 等），我这里选择 Cursor。

![](https://pic.yupi.icu/1/image-20260116163202471.png)

运行命令后，OpenSpec 会自动在你的项目中生成一个 `openspec/` 目录，里面包含：

- `openspec/specs/`：存放主规范文档，记录了项目的完整现状
- `openspec/changes/`：存放变更提案，记录了每次修改的计划
- ⭐️ `openspec/AGENTS.md`：让 AI 编程助手使用 OpenSpec 进行规范驱动开发的操作指南，包含了如何创建变更提案、编写需求规范、验证和归档变更的完整工作流程。
- `openspec/project.md`：当前项目的上下文说明（用来记录项目的信息）

![](https://pic.yupi.icu/1/image-20260116164308965.png)

此外，还会根据你选择的 AI 编程工具，生成对应的命令文件，比如 Cursor 的：

![](https://pic.yupi.icu/1/image-20260116173814973.png)

有了这些文件，我们就可以开始规范化的开发流程了。



### 2、标准化开发流程

参考 [官方文档](https://github.com/Fission-AI/OpenSpec/)，主要分为 5 个步骤：

#### 1）Draft 起草变更提案

直接在 AI 编程工具中跟 AI 说，让它创建变更提案。比如我想添加用户搜索功能：

```markdown
创建一个 OpenSpec 的 change，添加功能：根据名称和邮箱搜索用户
```

也可以用 AI 编程工具（比如 Claude Code、Cursor）的斜杠命令：

```markdown
/openspec:proposal 添加功能：根据名称和邮箱搜索用户
```

![](https://pic.yupi.icu/1/image-20260116171714070.png)

AI 会给这个功能创建一个独立的目录 `openspec/changes/add-user-search/`，目录下创建一系列文档：

- `proposal.md`：描述要改什么、为什么改
- `tasks.md`：实施步骤的任务分解
- `specs/…/spec.md`：需求变更的具体内容

![](https://pic.yupi.icu/1/image-20260116171953809.png)



#### 2）Verify & Review 验证和审查

可以运行下列命令，查看 AI 创建的变更提案是否正确：

```bash
openspec list                        # 查看所有变更
openspec validate add-user-search    # 验证格式是否正确
openspec show add-user-search        # 查看详细内容
```

![](https://pic.yupi.icu/1/image-20260116172259055.png)



#### 3）和团队一起审查提案

如果需要完善，可以继续跟 AI 对话，比如：

```markdown
你能帮我添加更多搜索条件和限制么？
```

AI 会更新规范和任务列表，直到大家达成一致。



#### 4）Implement 实现变更

规范确认后，让 AI 开始实现：

```markdown
规范已经很完美了，开始生成代码吧
```

也可以用斜杠命令：

```markdown
/openspec:apply add-user-search
```

AI 会按照 `tasks.md` 中的任务列表逐一实现，并标记完成状态。

![](https://pic.yupi.icu/1/image-20260116172654371.png)

很快生成完成，AI 的输出非常整齐，所有改动一目了然：

![](https://pic.yupi.icu/1/image-20260116172905921.png)



#### 5）Archive 归档变更

所有任务完成后，让 AI 归档这次变更：

```markdown
请归档这次变更
```

也可以用斜杠命令：

```markdown
/openspec:archive add-user-search
```

或者在终端运行：

```bash
openspec archive add-user-search --yes
```

![](https://pic.yupi.icu/1/image-20260116172957759.png)

这个命令会：

- 将变更文件夹移动到 `openspec/changes/archive/` 归档区
- 将需求变更自动合并到 `openspec/specs/` 主规范中
- 保持文档和代码的同步

![](https://pic.yupi.icu/1/image-20260116174247313.png)

这样一来，通过 `openspec/changes/` 的历史记录，你可以随时追溯每次变更的来龙去脉。

此外，整个开发过程中，建议大家定期运行 `openspec validate` 验证命令， 确保规范的完整性。



## 三、OpenSpec 和 Spec-kit 的区别

到这里，相信大家也能感受到 OpenSpec 和 Spec-kit 的区别了。

- Spec-kit 需要完整的 7 步流程：制定准则 → 写需求 → 澄清疑问 → 定方案 → 拆任务 → 检查 → 写代码），适合从 0 开始做大型新项目
- OpenSpec 的流程更简化：起草提案 → 审查 → 实现 → 归档 → 验证，上手更快，适合在现有项目上迭代功能。

如果你是在现有项目上迭代功能，OpenSpec 会是更好的选择。如果你是从 0 开始做大型新项目，Spec-kit 的完整流程能帮你打好基础。



## 写在最后

看到这里，相信你已经对 OpenSpec 有了基本的了解。

**OpenSpec 比 Spec-kit 更轻量，更适合日常开发中的功能迭代。**

如果你觉得 Spec-kit 太重，可以试试 OpenSpec。它的流程更简单，但同样能保证文档和代码的同步，让团队协作更顺畅。

建议你亲自尝试在项目中使用 OpenSpec，体验一下规范驱动开发的好处。



## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
