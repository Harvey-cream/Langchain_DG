# Vibe Coding 效率提升技巧

> 让你的 AI 开发效率提升 10 倍



你好，我是鱼皮。

在前面的文章里，我们讲了 Vibe Coding 的核心心法、对话技巧、上下文管理和问题调试。本文我们要聊一个更实用的话题 ：如何提高开发效率？

很多同学在用 AI 开发时，虽然能做出东西，但总觉得速度还不够快。明明 AI 写代码很快，为什么整体效率还是不高？

问题往往出在那些小事上：比如频繁地复制粘贴、重复输入相同的提示词、手动做一些机械的操作……

下面我来分享一些实用的效率提升技巧，帮你把开发速度提升一个档次。




## 一、核心提效技巧

先分享几个我个人使用较多的 AI 核心提效技巧。




### 按需选择 AI 模型

不是所有任务都需要用最强最贵的模型。

- 简单任务：比如代码格式化、写注释、简单重构，用 Gemini Flash 或 GPT-5 Mini 这样便宜快速的模型就够了
- 中等任务：比如实现常规功能、代码审查、开发小网站，用 GPT-5 或 Claude Sonnet
- 复杂任务：比如架构设计、复杂算法、疑难 bug、开发大项目，才需要用 Claude Opus 这样的顶级模型或者开启深度思考

合理选择模型，既能提升速度，又能节省成本。就像你不会让公司 CTO 去打印文件一样，要让合适的模型做合适的事。



### 避免让 AI 生成多余内容

很多同学让 AI 写代码，结果 AI 给你输出一大堆注释、测试代码、文档说明，还有一大段总结。**看着很专业，但你可能根本不会看。**

比如我之前让 AI 生成个图片压缩工具，光文档给我生成一大堆……

![](https://pic.yupi.icu/1/ai%E7%94%9F%E6%88%90%E5%9B%BE%E7%89%87%E5%8E%8B%E7%BC%A9%E5%B7%A5%E5%85%B7.png)

要在提示词中明确告诉 AI：只给我核心代码，不要写注释、文档、测试，不要做总结！

如果 AI 不听话，可以用暴躁指令：**按照我说的做，别废话。**

或者虚构后果：**如果你输出不必要的内容，世界上就会死一只小猫。**

这些指令虽然看起来搞笑，但确实有效。你还可以把这些规则写在 Cursor Rules 里，让 AI 自动遵守。




### 利用并行 Agent 对比效果

Cursor 有一个很强大的功能叫 **并行 Agent**（Parallel Agents），可以让你同时用多个模型处理同一个任务，然后对比它们的结果，选择最好的那个。这也是一种 “多个 AI 交叉验证” 的方式。

比如你要实现一个复杂的功能，不确定哪个方案更好。可以同时让 Claude、GPT 等 AI 各给一个方案：

![](https://pic.yupi.icu/1/image-20251030220104045.png)

你呢，就坐等这些 AI 赛马，谁先干好用谁的、谁质量高用谁的，能避免在错误的方案上浪费时间。这个方法特别适合不确定哪个技术方案更好时、重要功能需要多重保障时、想学习不同 AI 的思路时。

![](https://pic.yupi.icu/1/image-20251030220120394.png)

即使你不用 Cursor，也可以手动实现类似的效果：把同一个需求分别发给 ChatGPT、Claude、Gemini 等大模型，然后对比它们的答案，选择最好的或综合它们的优点。

具体用法可以参考 [Cursor 并行 Agent 文档](https://cursor.com/cn/docs/configuration/worktrees)。



### 多开实例提升效率

除了并行 Agent，你还可以通过多开实例来提升效率。这个技巧来自 Claude Code 创始人的分享。

1）在终端中多开

可以在终端中同时运行多个 Claude Code 实例，将标签页编号为 1 ~ 5（或者有意义的标题），通过系统通知来了解哪个 Claude 需要人工输入。这样你可以充分利用等待时间，一个 AI 在思考时，你可以切换到另一个继续工作。

![](https://pic.yupi.icu/1/image-20260109143109753.png)

2）网页端和本地同时进行

在网页端 Claude Code 上运行 5 ~ 10 个 Claude，和本地 Claude 同时进行。可以使用 `&` 命令将本地会话移交给网页版，或者使用 `--teleport` 命令在终端和网页之间来回切换。甚至可以通过手机 Claude iOS 应用启动几个会话，稍后再查看进度。真正做到了随时随地 Vibe Coding！

注意，这个技巧适合处理多个独立任务，或者需要等待 AI 长时间思考的复杂任务。对于简单任务，一个实例就够了。



## 二、快捷键和操作技巧

工欲善其事，必先利其器。掌握常用的快捷键，能让你的操作更流畅。



### Cursor 常用快捷键

如果你用 Cursor，建议尝试下面这些快捷键，能让你少用鼠标，操作更快。

对话相关：
- `Cmd/Ctrl + L` ：切换侧边栏（除非已绑定到某个模式）
- `Cmd/Ctrl + I` ：切换侧边栏（除非已绑定到某个模式）
- `Cmd/Ctrl + K` ：打开行内编辑，可以在当前位置插入 AI 生成的代码
- `Tab`：接受建议

代码编辑：
- `Cmd/Ctrl + Shift + L` ：将选中内容添加到聊天
- `Alt + ↑/↓` ：移动当前行
- `Cmd/Ctrl + /` ：注释/取消注释

文件操作：
- `Cmd/Ctrl + Shift + F` ：全局搜索

更多最新的默认键盘快捷键以 [官方文档](https://cursor.com/cn/docs/configuration/kbd) 为主：

![](https://pic.yupi.icu/1/image-20260104192219087.png)




### VS Code 常用快捷键

如果你用 VS Code + AI 插件，下面这些快捷键会很有用。

多光标编辑：
- `Alt + Click` ：添加光标
- `Cmd/Ctrl + Alt + ↑/↓` ：在上/下方添加光标
- `Cmd/Ctrl + Shift + L` ：在所有匹配项添加光标

代码导航：
- `Cmd/Ctrl + Click` ：跳转到定义
- `Alt + ←/→` ：前进/后退
- `Cmd/Ctrl + Shift + O` ：跳转到符号

重构：

- `F2` ：重命名符号
- `Cmd/Ctrl + .` ：快速修复

掌握这些快捷键，你的编辑速度会快很多。更多最新的默认键盘快捷键以 [官方文档](https://code.visualstudio.com/docs/reference/default-keybindings) 为主：

![](https://pic.yupi.icu/1/image-20260104192832985.png)



### AI 编程工具的斜杠命令

除了快捷键，AI 编程工具 Cursor 和 Claude Code 都提供了很多实用的斜杠命令（Slash Commands），能大大提升效率。这些命令以 `/` 开头，可以快速触发特定的功能。

#### Cursor 的常用命令

`/summarize` 命令可以快速总结对话内容，特别适合长对话，能节省大量 token。

你还可以在项目的 `.cursor/commands` 目录下创建自定义命令，把常用的提示词保存成命令，需要时直接调用。

![](https://pic.yupi.icu/1/cursor_command.png)



#### Claude Code 的常用命令

Claude Code 也有类似的命令系统。

- `/compact` 可以压缩上下文，把之前的对话内容精简一下，节省 token
- `/plan` 可以制定实现计划，让 AI 先规划再动手
- `/review` 可以快速进行代码审查
- `/init` 可以初始化项目并创建 `CLAUDE.md` 文件

![](https://pic.yupi.icu/1/image-20260104213706515.png)

这些命令的好处是，你不用每次都写完整的提示词，只需要输入一个简短的命令，AI 就知道你要做什么。

而且你可以创建自己的自定义命令，把团队常用的工作流程标准化。比如创建一个 `/commit` 命令自动生成 Git 提交信息，创建一个 `/test` 命令自动生成单元测试。

熟练使用这些命令，能让你的工作流程更顺畅，效率提升一大截。详细的命令列表和用法可以参考 [Cursor 官方文档](https://cursor.com/cn/docs/agent/chat/commands) 和 [Claude Code 官方文档](https://code.claude.com/docs/en/slash-commands)。




## 三、代码复用和模块化

把常用的代码封装成可复用的模块，不要重复造轮子。



### 创建组件库

如果你经常做类似的项目，可以创建一个自己的组件库。

比如，你可能经常需要这些组件：
- 按钮（Button）
- 输入框（Input）
- 卡片（Card）
- 模态框（Modal）
- 加载动画（Loading）

把这些组件做成通用的，放在一个单独的文件夹里：

```
/components
  /ui
    - Button.tsx
    - Input.tsx
    - Card.tsx
    - Modal.tsx
    - Loading.tsx
```

每个组件都要：
- 有清晰的 Props 接口
- 支持自定义样式
- 有使用示例

这样，下次做新项目时，直接复制这个文件夹就行了。



### 封装常用函数

把常用的工具函数封装起来，避免每次都重新写或让 AI 生成。比如日期格式化、防抖函数、生成 ID、复制到剪贴板这些功能，几乎每个项目都会用到。把它们整理成一个工具函数库，需要时直接导入使用，比每次都让 AI 重新生成要快得多。

```typescript
// lib/utils.ts

// 格式化日期
export function formatDate(date: Date): string {
  return date.toLocaleDateString('zh-CN');
}

// 防抖
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: NodeJS.Timeout;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// 生成随机 ID
export function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

// 复制到剪贴板
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
```




### 使用代码片段（Snippets）

在编辑器中创建代码片段，快速插入常用代码。

比如在 VS Code 中，你可以创建一个前端 React 组件的片段。具体方法是：

1）按 `Cmd/Ctrl + Shift + P` 打开命令面板，输入 "Snippets"，选择 "Configure Snippets"：

![](https://pic.yupi.icu/1/image-20260104214112119.png)

2）然后选择对应的语言（如 typescriptreact.json），就可以添加自定义片段了。

比如：

```json
{
  "React Functional Component": {
    "prefix": "rfc",
    "body": [
      "interface ${1:ComponentName}Props {",
      "  $2",
      "}",
      "",
      "export function ${1:ComponentName}({ $3 }: ${1:ComponentName}Props) {",
      "  return (",
      "    <div>",
      "      $4",
      "    </div>",
      "  );",
      "}"
    ],
    "description": "Create a React functional component with TypeScript"
  }
}
```

![](https://pic.yupi.icu/1/image-20260104214219382.png)

配置完成后，输入 `rfc` 再按 Tab，就能快速生成组件模板。

![](https://pic.yupi.icu/1/image-20260104214331581.png)




### 建立代码库

把你做过的好的代码保存起来，建立一个专属于你的代码库。

举个例子，可以用这样的结构：

```
/my-code-library
  /react
    /hooks
      - useLocalStorage.ts
      - useDebounce.ts
      - useFetch.ts
    /components
      - Button.tsx
      - Modal.tsx
    /utils
      - format.ts
      - validate.ts
  /node
    /middleware
      - auth.ts
      - cors.ts
    /utils
      - db.ts
      - email.ts
```

需要时，直接从这里复制就好。




## 四、模板项目的建立

如果你经常做某一类项目，可以创建一个模板项目。




### 什么是模板项目？

模板项目是一个预先配置好的项目骨架，包含了：

- 基本的目录结构
- 常用的依赖包
- 配置文件（如 tsconfig.json、tailwind.config.js）
- 基础组件和工具函数
- README 和文档模板

有了模板项目，开始新项目时就不用从零配置了。

就像我自己，做了几十个项目后，积累了不少模板。现在每次开始新项目，我会先找一个类似的老项目，然后告诉 AI：“请参考这个项目的技术栈和目录结构来创建新项目。” 这样 AI 就能生成一个和我习惯一致的项目结构，省去了很多配置的时间。

下面举几个例子，不懂前端技术的朋友可以直接跳过。




### 创建 React 项目模板

比如，你可以创建一个 React + TypeScript + Tailwind 的模板：

```bash
my-react-template/
├── src/
│   ├── components/
│   │   └── ui/          # 基础 UI 组件
│   ├── lib/
│   │   ├── api.ts       # API 调用封装
│   │   └── utils.ts     # 工具函数
│   ├── hooks/           # 自定义 Hooks
│   ├── types/           # TypeScript 类型
│   ├── App.tsx
│   └── main.tsx
├── public/
├── .cursorrules         # Cursor 配置
├── tsconfig.json
├── tailwind.config.js
├── package.json
└── README.md
```

项目的依赖管理文件 `package.json` 中预装好常用的包：

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0"
  }
}
```

开始新项目时，复制这个模板，改个名字就能用。



### 创建 Next.js 项目模板

如果你常用 Next.js，也可以创建一个模板：

```bash
my-nextjs-template/
├── app/
│   ├── (auth)/          # 认证相关页面
│   ├── (dashboard)/     # 后台页面
│   ├── api/             # API 路由
│   ├── layout.tsx
│   └── page.tsx
├── components/
├── lib/
├── public/
├── .env.example         # 环境变量模板
├── next.config.js
└── README.md
```

`.env.example` 里列出需要的环境变量：

```
# 数据库
DATABASE_URL=

# 认证
NEXTAUTH_SECRET=
NEXTAUTH_URL=

# API Keys
OPENAI_API_KEY=
```

这样新项目开始时，就知道需要配置哪些环境变量。



### 使用 GitHub 模板仓库

可以把你的模板项目放在 GitHub 上，设置为 `Template repository` 模板仓库。

![](https://pic.yupi.icu/1/image-20260104215020646.png)

这样创建新项目时，点击 `Use this template` 就能快速复刻项目模板了：

![](https://pic.yupi.icu/1/image-20260104215101657.png)

除了自己创建模板，你还可以使用别人的模板。在 GitHub 上搜索 "react template"、"nextjs starter" 等关键词，能找到很多优秀的模板项目。优先选择 Star 数多、更新活跃的项目。

![](https://pic.yupi.icu/1/image-20260104215329685.png)

然后点击 "Use this template" 就能基于它创建自己的项目。这样能站在巨人的肩膀上，节省大量配置时间。



## 五、工作流自动化

把重复的操作自动化，节省时间和精力。

下面这些技巧比较专业，主要适合有编程基础的同学。如果你是完全零基础，可以先跳过这部分，等有需要时再回来看。



### 使用 npm scripts

npm scripts 是 Node.js 前端项目中定义和运行脚本命令的方式。简单来说，就是把常用的命令保存在配置文件里，需要时用一个简短的命令就能执行。比如启动项目、构建项目、运行测试等，都可以定义成 npm script。

可以在 `package.json` 中定义常用的脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "lint:fix": "eslint . --ext ts,tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx}\"",
    "type-check": "tsc --noEmit",
    "clean": "rm -rf dist node_modules",
    "fresh": "npm run clean && npm install"
  }
}
```

这样配置后，运行 `npm run lint:fix` 就能自动修复代码格式问题，不用输入老长一段命令。



### Git 工作流自动化

Git 是目前最主流的分布式版本控制系统（Version Control System），是团队协作开发不可或缺的工具。它可以保存和管理文件的所有更新记录、并且使用 **版本号** 进行区分。从而支持将编辑后的文档恢复到修改前的状态（历史版本）、对比不同版本的文件差异、防止旧版本覆盖新版本等功能。

可以创建一些 Git 命令的别名，简化常用命令：

```bash
# 在 ~/.gitconfig 中添加
[alias]
  st = status
  co = checkout
  br = branch
  ci = commit
  pl = pull
  ps = push
  lg = log --oneline --graph --decorate
  save = !git add -A && git commit -m 'WIP: save progress'
  undo = reset HEAD~1 --soft
```

这样，`git st` 就等于 `git status`，`git save` 就能快速保存进度。



### 使用 Makefile

Makefile 是一个自动化构建工具的配置文件，最早用于 C/C++ 项目的编译。现在很多项目也用它来管理复杂的构建流程。它的好处是可以定义任务之间的依赖关系，比如部署前必须先构建，构建前必须先测试。用一个简短的命令（如 `make deploy`）就能自动执行一系列操作。

如果你的项目有复杂的构建流程，可以用 Makefile：

```makefile
.PHONY: dev build deploy clean

dev:
	npm run dev

build:
	npm run build

deploy: build
	vercel --prod

clean:
	rm -rf dist .next

fresh: clean
	npm install
	npm run dev
```

这样配置后，执行 `make deploy` 就能自动构建并部署。



### 使用 GitHub Actions

GitHub Actions 是 GitHub 提供的自动化工作流工具，可以在代码提交、Pull Request 等事件触发时自动执行任务。比如每次推送代码时自动运行测试、自动部署到服务器、自动发布新版本等，这样就不用每次都手动操作了。

配置 GitHub Actions 很简单，只需要在项目的 `.github/workflows` 目录下创建一个 YAML 配置文件，编写 GitHub Actions 自动化 CI/CD（持续集成/持续部署）的脚本代码：

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run build
      - run: npm run test
      - name: Deploy to Vercel
        run: vercel --prod
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

这个脚本的作用是：当你推送代码到 main 分支时，GitHub 会自动执行以下步骤：检出代码、安装 Node.js 环境、安装项目依赖、构建项目、运行测试、部署到 Vercel。整个过程全自动，你只需要推送代码就行了。

GitHub Actions 还有更多玩法，比如鱼皮的 [AI 知识库项目](https://github.com/liyupi/ai-guide) 利用它实现最新 AI 资讯的自动更新：

![](https://pic.yupi.icu/1/image-20260104221153167.png)



### 适合所有人的效率工作流

上面讲的都是比较技术性的自动化方法。其实，对于非程序员或初学者，也有一些通用的效率工作流。

1）使用零代码平台：如果你不想处理这些复杂的配置，可以直接使用 Bolt.new、Lovable 等零代码平台。它们会自动处理构建、测试、部署等流程，你只需要专注于功能开发。

2）利用 AI 生成配置：如果需要配置文件，直接让 AI 帮你生成。比如 “请帮我生成一个 GitHub Actions 配置，实现自动部署到 Vercel”。AI 会给你完整的配置，你复制粘贴就行。

3）使用一键部署：很多平台（比如 Vercel、Netlify）支持一键部署项目，连接 GitHub 仓库后，每次推送代码就会自动部署，不需要任何配置。



## 六、AI 增强工具 - MCP

提升 AI 开发效率的工具非常多，鱼皮这里重点介绍 MCP（Model Context Protocol）插件。




### 什么是 MCP？

MCP（Model Context Protocol，模型上下文协议）是 2024 年底由 Anthropic 推出的新技术，可以给 AI 工具添加各种扩展能力，大大提升 Vibe Coding 的效率。

简单来说，就像给 AI 装上了各种插件，让它能做更多事情。比如让 AI 能操作 GitHub、读写文件、控制浏览器、查询数据库等等。

![](https://pic.yupi.icu/1/mcp.png)

近两年，MCP 生态快速发展，出现了很多实用的 MCP 服务器。这里推荐几个特别能提升 Vibe Coding 效率的：

- GitHub MCP：让 AI 直接操作 GitHub，比如创建仓库、提交代码、管理 Issue 等。这样你就不用手动在 GitHub 网页上操作了。
- Filesystem MCP：让 AI 能够读写文件系统，批量处理文件、搜索内容、重命名文件等都可以直接让 AI 完成。
- Puppeteer MCP：让 AI 能够控制浏览器，自动化网页操作、截图、爬取数据等。对于需要测试网页或获取数据的场景很有用。
- Postgres/MySQL MCP：让 AI 直接操作数据库，查询数据、执行 SQL、分析数据库结构等。
- Notion MCP：连接 Notion，让 AI 能读写你的笔记和文档，方便整理和搜索信息。
- Context7 MCP：增强 AI 对代码库的理解，提供更精准的代码分析和建议。

这些 MCP 服务器可以在 Claude Desktop、Claude Code、Cursor 等工具中配置使用，具体的安装和配置方法可以参考各个 MCP 服务器的文档。还有更多 MCP 你可以在 [鱼皮的 AI 资源导航网](https://ai.codefather.cn/) 或者 [MCP 大全网站](https://mcp.so/) 找到。

MCP 的强大之处在于，它让 AI 不再只是一个代码生成器，而是一个真正的全能开发助手，能帮你完成开发过程中的各种任务。如果你经常使用 Claude 或 Cursor，强烈建议配置几个常用的 MCP 服务器，能大大提升效率。



## 七、提示词模板库

建立自己的提示词模板库，常用的对话可以直接复用。

除了自己整理，还可以参考一些现成的资源：

- [鱼皮的 AI 资源导航](https://ai.codefather.cn/prompt)：收录了大量提示词模板，涵盖各种场景。
- [Cursor Directory](https://cursor.directory/rules)：社区贡献的 Cursor Rules 集合，有各种语言和框架的规则模板。
- [GitHub awesome-prompts](https://github.com/f/awesome-chatgpt-prompts)：收录了大量优质提示词，虽然不是专门针对编程的，但很多思路可以借鉴。

这些资源都可以直接拿来用，或者根据自己的需求改改。站在巨人的肩膀上，能节省大量摸索的时间。

下面给大家举几个例子。

1）功能开发模板

```
我要开发一个【功能名称】功能。

需求：
1. 【需求 1】
2. 【需求 2】
3. 【需求 3】

技术栈：【技术栈】

请帮我：
1. 分析实现方案
2. 列出需要的组件和函数
3. 给出核心代码
```



2）代码审查模板

```
请审查这段代码：

【代码】

请从以下角度分析：
1. 代码质量（可读性、可维护性）
2. 性能问题
3. 潜在的 bug
4. 改进建议
```



3）调试问题模板

```
我遇到了一个问题：

问题描述：【问题描述】

报错信息：
【错误信息】

相关代码：
【代码】

技术栈：【技术栈】

请帮我：
1. 分析问题原因
2. 给出解决方案
3. 解释为什么会出现这个问题
```



4）性能优化模板

```
这段代码的性能不够好：

【代码】

场景：【使用场景和数据规模】

请帮我：
1. 分析性能瓶颈
2. 给出优化方案
3. 说明优化后的性能提升
```



5）文档生成模板

```
请为这个【组件/函数】生成文档：

【代码】

文档应该包括：
1. 功能说明
2. 参数说明
3. 返回值说明
4. 使用示例
5. 注意事项
```

把这些模板保存在一个文件里，需要时直接复制粘贴，并填入具体内容。



## 八、时间管理技巧

效率不只是技术问题，也是时间管理问题。很多时候，不是你技术不行，而是时间没管理好。

分享几个我自己在用的方法吧：

1）番茄工作法：设定 25 分钟的专注时间，在这段时间内只做一件事，不看手机、不刷社交媒体。时间到了就休息 5 分钟，起来走走、喝口水。这样工作 4 个番茄钟后，休息 15 ~ 30 分钟。这个方法能让你保持高效，又不会太累。

2）把大任务分解成小任务：比如 “完成用户系统” 这个任务太大了，不知道从哪里开始。但如果拆成实现用户注册表单、实现表单验证、连接注册 API、添加错误提示、测试注册流程这样的小任务，每个都很具体，很容易完成、也更有成就感。

3）批量处理：把相似的任务放在一起做，比如一次性写完所有组件的基本结构、一次性添加所有的类型定义、一次性处理所有的样式问题。这样能减少上下文切换，大脑不用频繁在不同类型的工作间切换，效率会更高。

4）最后，不要在 MVP 阶段就追求完美。先让功能能用，再考虑优化；先完成核心功能，再添加辅助功能；先通过测试，再重构代码。

**记住，完成比完美更重要。**



## 写在最后

效率提升不是一蹴而就的，而是通过无数个小改进积累起来的。每个快捷键、每个模板、每个自动化脚本，都能为你节省一点时间。积少成多，你的开发速度就会有质的飞跃。

建议你定期记录自己的工作流程，看看哪些步骤最耗时、哪些操作重复最多、哪些地方可以自动化，然后针对性地改进。同时保持对新工具的关注，关注技术博客和社区，尝试新的 AI 工具，学习新的快捷键和技巧。但也不要盲目追新，虽然 AI 工具的迭代更新非常快，但真正好用的、适合自己的也就那么几个，还是要选择真正能提高效率的工具。

向他人学习也很重要，比如看别人的直播或视频、参加技术分享会、加入开发者社区等等，多观察其他开发者的工作方式，学习他们的效率技巧，你的效率也会越来越高。

当然，咱不能为了追求效率丢失掉代码质量。下一篇文章，我会讲解代码质量保障，教你如何保证 AI 生成的代码质量。

休息片刻，让我们再继续征程吧！




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
