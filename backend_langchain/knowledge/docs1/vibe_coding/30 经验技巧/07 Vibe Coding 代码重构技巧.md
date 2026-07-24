# Vibe Coding 代码重构技巧

> 避免 AI 生成混乱的意大利面代码



你好，我是鱼皮。

你可能遇到过这样的情况：刚开始用 AI 做项目时，代码清晰简洁，看起来很舒服。但随着功能越加越多，代码开始变得混乱。最后，你自己都不敢动这些代码了，因为改一个地方，可能会影响到其他地方。

这种情况在 Vibe Coding 中特别常见，因为 AI 可能只关注 “能不能跑”，忽略了 “好不好维护”。下面我就来教你如何识别和偿还技术债，让你的代码始终保持优雅。




## 一、什么是技术债？

技术债是一个很形象的比喻。

想象一下，你要盖一栋房子。为了快速完工，你用了一些临时的方案：地基没打牢，墙没砌直，电线随便拉。房子是盖起来了，也能住人，但隐患很多。如果不及时修复，以后问题会越来越大，修复的成本也会越来越高。

技术债就是这样。为了快速实现功能，你（或 AI）采用了一些不够好的方案。这些方案当时能用，但会给未来埋下隐患。随着项目发展，这些隐患会变成实际的问题，拖慢你的开发速度。

在今年的研究中发现，AI 生成的代码特别容易产生技术债。因为 AI 擅长快速实现功能，但不擅长考虑长远的架构和可维护性。它会给你一个 “高度功能化但系统性缺乏架构判断” 的代码。



### 技术债的表现

那么，如何判断你的项目有没有技术债呢？最明显的信号是：改代码变得越来越困难，你开始害怕修改代码，因为不知道会影响到哪里。如果你发现自己经常觉得 “这个地方不敢动”、“改了这里可能会影响那里”，那就说明技术债已经比较严重了。



### 技术债的危害

技术债的危害是累积的。刚开始可能只是代码有点乱，不影响功能。但随着时间推移，问题会越来越严重。

- 开发速度变慢，因为要花更多时间理解和修改代码。
- Bug 越来越多，因为代码太复杂，容易出错。
- 新功能难以添加，因为现有架构不支持。
- 团队协作困难，因为没人能完全理解代码。

最糟糕的是，到了某个临界点，你可能不得不重写整个项目。这就是技术债的 “破产”。




## 二、AI 生成代码的常见问题

用 AI 做 Vibe Coding 时，如果上下文管理不当、需求描述不够清晰，或者让 AI 一次性实现太复杂的功能，生成的代码可能会出现一些质量问题。下面是几个典型场景，了解它们能帮你更好地引导 AI。



### 过度嵌套

AI 为了确保代码能运行，有时会生成嵌套很深的代码。

什么是嵌套？

就是 if 里面套 if，循环里面套循环，像俄罗斯套娃一样。比如：

```typescript
function processData(data: any) {
  if (data) {
    if (data.items) {
      if (data.items.length > 0) {
        data.items.forEach(item => {
          if (item.active) {
            if (item.price > 0) {
              // 实际逻辑
            }
          }
        });
      }
    }
  }
}
```

这种代码很难读，也很难维护。更好的写法是提前返回：

```typescript
function processData(data: any) {
  if (!data?.items?.length) return;
  
  const activeItems = data.items.filter(item => 
    item.active && item.price > 0
  );
  
  activeItems.forEach(item => {
    // 实际逻辑
  });
}
```

显然，第二种写法更清晰，也更容易理解。



### 重复代码

AI 可能不会主动复用代码，而是为每个需求生成新的代码。

举个例子，假设你让 AI 分别实现用户列表页、文章列表页、评论列表页。AI 会给你三套几乎一样的代码，只是数据字段不同。或者你可能在多个组件里都有这样的代码：

```typescript
const handleSubmit = async () => {
  setLoading(true);
  try {
    const response = await fetch('/api/data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await response.json();
    setData(result);
  } catch (error) {
    console.error(error);
  } finally {
    setLoading(false);
  }
};
```

这些重复代码应该提取成一个公共函数或自定义 Hook。



### 缺少抽象

AI 倾向于写具体的、直接的代码，而不是抽象的、可复用的代码。

比如，你要显示用户列表和文章列表，AI 可能会给你两个完全独立的组件，即使它们的结构几乎一样。

更好的做法是创建一个通用的列表组件，然后用不同的数据和渲染函数来复用。



### 命名随意

AI 有时候会用相对随意的命名，比如 `data`、`result`、`temp`、`handleClick`。这些名字不能准确表达意图，会让代码难以理解。

出现这种情况可能是因为你的需求描述不够具体，AI 不知道这个变量或函数的真实用途。

好的命名应该是 **见名知意** 的，比如 `userData`、`apiResponse`、`temporaryBuffer`、`handleLoginButtonClick`。

如果你发现 AI 生成的命名太随意，可以在需求中明确说明：请使用有意义的变量名和函数名，能清楚表达它们的用途。



## 三、如何利用 AI 重构代码？

既然 AI 会产生技术债，那能不能用 AI 来偿还技术债呢？

答案是可以的。这也是 Vibe Coding 的一大优势 —— **AI 既能快速写代码，也能快速改代码**。



### 让 AI 识别问题

你可以把代码贴给 AI，让它从专业的角度审查，帮你找出代码中的问题。

````markdown
请审查这段代码，找出可以改进的地方：
```typescript
【贴上你的代码】
```

请从以下角度分析：
1. 有没有重复代码？
2. 函数是否太长？
3. 命名是否清晰？
4. 有没有过度嵌套？
5. 能否提取公共逻辑？
````

AI 会给你一份详细的分析报告。



### 让 AI 提供重构方案

找到问题后，让 AI 给你重构方案，比如：

- 你提到了这段代码有重复逻辑。请给我一个重构方案，把重复的部分提取成公共函数。
- 这个函数太长了。请帮我把它拆分成几个小函数，每个函数只做一件事。

AI 会给你具体的重构代码。



### 小步重构

注意，不建议一次性重构整个项目，这样风险太大，说不定重构完你整个项目都无法运行了。

正确的做法是小步重构，每次只改一小部分。

比如，你发现一个函数太长了，不要一次性把它拆成 10 个小函数。先拆成 2 个，测试通过了，再继续拆。每一步都要确保功能不变，测试都通过。

这样即使出了问题，也容易回退。




### 重构的时机

什么时候应该重构？

我的建议是：

1）不要专门安排时间重构，而是在日常开发中随时重构。当你发现代码有问题时，立刻改掉，不要拖到以后。

2）完成功能后重构。功能做完了，测试通过了，花 10 ~ 15 分钟看看代码，有没有可以改进的地方。

3）添加新功能前重构。如果你发现现有代码不适合添加新功能，先重构一下，让代码更容易扩展。

4）定期集中重构。每个月或每个大版本，花半天时间集中重构，处理积累的技术债。



## 四、模块化和代码复用

模块化是避免技术债的关键。而且，模块化的代码对 AI 也更友好 —— 当你需要修改某个功能时，AI 只需要阅读相关的小模块，而不是整个几百行的大文件，这样 AI 能更准确地理解和修改代码。




### 什么是模块化？

模块化就是把代码分成独立的、可复用的模块。每个模块只做一件事，做好一件事。模块之间通过清晰的接口通信，互不干扰。

好的模块化有这些特点：

- 高内聚：模块内部的代码紧密相关
- 低耦合：模块之间的依赖尽可能少
- 单一职责：每个模块只负责一件事
- 接口清晰：模块的输入输出明确




### 组件的拆分

在前端开发框架 React 中，组件是最基本的模块。你可以把组件理解为页面上的一个个独立部分，比如导航栏、搜索框、用户卡片等。

但很多人（包括 AI）会写出很 “笨重” 的组件。

比如，一个用户资料页面，AI 可能会把所有逻辑都写在一个组件里：获取数据、表单验证、提交处理、错误提示…… 结果就是一个几百行的巨型组件。

更好的做法是拆分成多个小组件：

```typescript
// 主组件，负责协调
function ProfilePage() {
  const { user, loading, error } = useUser();
  
  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  
  return (
    <div>
      <ProfileHeader user={user} />
      <ProfileForm user={user} />
    </div>
  );
}

// 子组件，各司其职
function ProfileHeader({ user }) {
  return (
    <div>
      <Avatar src={user.avatar} />
      <h1>{user.name}</h1>
    </div>
  );
}

function ProfileForm({ user }) {
  // 表单逻辑
}
```

这样一来，每个组件都很小，很容易理解和测试。

即使你不了解前端或 React，也能理解这个思想 —— 把大的功能拆成小的、独立的部分，每个部分只做一件事。这个原则适用于所有编程语言和框架。




### 函数的提取

当你发现一段代码在多个地方重复出现时，就应该提取成函数。

比如，你在多个地方都需要格式化日期：

```typescript
// 重复的代码
const formattedDate1 = new Date(date1).toLocaleDateString('zh-CN');
const formattedDate2 = new Date(date2).toLocaleDateString('zh-CN');
const formattedDate3 = new Date(date3).toLocaleDateString('zh-CN');

// 提取成函数
function formatDate(date: Date | string): string {
  return new Date(date).toLocaleDateString('zh-CN');
}

const formattedDate1 = formatDate(date1);
const formattedDate2 = formatDate(date2);
const formattedDate3 = formatDate(date3);
```

这样不仅减少了重复，还让代码更容易维护。如果以后要改日期格式，只需要改一个地方。



### 自定义 Hook 的使用

在前端开发框架 React 中，自定义 Hook 是复用逻辑的好方法。Hook 是一种特殊的函数，用来管理状态和副作用。

💡 你不需要理解什么是 Hook、组件、状态管理这些专业术语。只需要告诉 AI：

```markdown
这段逻辑在多个地方重复了，请帮我提取成可复用的模块。
```

然后 AI 会自动帮你做好抽象和复用。

举个例子，你在多个组件里都需要获取用户数据，可以把获取用户数据这部分代码提取成 Hook，在其他地方复用：

```typescript
// 提取前：每个组件都重复这些逻辑
function ProfilePage() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetchUser().then(setUser).catch(setError).finally(() => setLoading(false));
  }, []);
  
  // ...
}

// 提取后：创建自定义 Hook
function useUser() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetchUser().then(setUser).catch(setError).finally(() => setLoading(false));
  }, []);
  
  return { user, loading, error };
}

// 使用时很简单
function ProfilePage() {
  const { user, loading, error } = useUser();
  // ...
}
```

自定义 Hook 让代码更简洁，也更容易测试。




## 五、从玩具项目到商业产品

很多人用 AI 做出来的是玩具项目 —— 能用，但不够专业、或者赚不了钱。

这时你可能会思考：如何把它变成可扩展的商业产品呢？



### 玩具项目的特征

玩具项目一般有这些特征：

- 所有代码都在一个文件里，或者文件组织很混乱
- 没有明确的架构，代码想到哪写到哪
- 缺少错误处理，只考虑了正常情况
- 没有测试，全靠手动测试
- 硬编码很多，配置和代码混在一起。

这样的项目可以用来演示或学习，但不适合作为商业产品长期维护和扩展。



### 商业产品的特征

商业产品应该是这样的：

- 清晰的目录结构，一眼就能看出哪里放什么
- 明确的架构，比如 MVC、MVVM 或其他模式
- 完善的错误处理，考虑了各种异常情况
- 充足的测试，核心功能都有测试覆盖
- 配置分离，环境变量、配置文件和代码分开
- 文档完善，有 README、API 文档、注释等

从玩具到商业产品，需要你有意识地提升代码质量和重构。

![](https://pic.yupi.icu/1/projectpk%E5%A4%A7.jpeg)




### 重构的步骤

如何把玩具项目重构成商业产品？

我建议分步进行：

1）整理目录结构。把代码按功能或类型分类，放到不同的文件夹里。比如组件放 `components`，工具函数放 `lib`，类型定义放 `types`。

2）提取重复代码。找出重复的逻辑，提取成公共函数或组件。这一步能大大减少代码量。

3）拆分大文件。把大的文件拆成小的文件，每个文件只负责一件事。比如一个大的 `utils.ts` 可以拆成 `format.ts`、`validate.ts`、`storage.ts` 等。

4）添加类型定义。如果用 TypeScript，给所有函数和组件加上完整的类型。这能帮你发现很多潜在问题。

5）改进命名。把不清晰的变量名、函数名改成描述性的名字。这能让代码更容易理解。

6）添加测试和文档。为核心功能写测试，为项目写 README，为复杂逻辑加注释。

以上这些步骤也都可以通过 AI 主导 + 人工校验来完成。关键是每一步都要确保功能不变、顺利通过测试。不要贪多，一步一步来。



## 六、实战案例 - 重构一个混乱的项目

让我用一个真实的例子，展示如何重构一个混乱的项目。



### 初始状态

假设你用 AI 做了一个待办事项应用，所有代码都在一个 `App.tsx` 文件里，大概 500 行。

```typescript
// App.tsx (500 行)
function App() {
  const [todos, setTodos] = useState([]);
  const [input, setInput] = useState('');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  
  // 100 行的数据获取逻辑
  useEffect(() => { /* ... */ }, []);
  
  // 50 行的添加逻辑
  const handleAdd = () => { /* ... */ };
  
  // 50 行的删除逻辑
  const handleDelete = () => { /* ... */ };
  
  // 50 行的编辑逻辑
  const handleEdit = () => { /* ... */ };
  
  // 50 行的过滤逻辑
  const filteredTodos = todos.filter(/* ... */);
  
  // 200 行的 JSX
  return (
    <div>
      {/* 很多很多代码 */}
    </div>
  );
}
```

虽然代码能用，但是所有功能逻辑都写到一起，不利于阅读和维护。




### 重构步骤

#### 第一步、提取自定义 Hook

首先，我们把所有和待办事项数据相关的逻辑（获取、添加、删除、更新）都提取到一个独立的 Hook 里。这样主组件就不用关心数据是怎么管理的，只需要调用这些方法就行。

```typescript
// hooks/useTodos.ts
function useTodos() {
  const [todos, setTodos] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const addTodo = async (text: string) => { /* ... */ };
  const deleteTodo = async (id: string) => { /* ... */ };
  const updateTodo = async (id: string, text: string) => { /* ... */ };
  
  useEffect(() => {
    // 获取数据
  }, []);
  
  return { todos, loading, addTodo, deleteTodo, updateTodo };
}
```



#### 第二步、拆分组件

接下来，把 UI 部分拆分成多个小组件。每个组件只负责显示和处理自己那一部分的逻辑，比如输入框只管输入、列表只管显示、过滤器只管筛选。这样每个组件都很简单，容易理解和修改。

```typescript
// components/TodoList.tsx
function TodoList({ todos, onDelete, onEdit }) {
  return (
    <div>
      {todos.map(todo => (
        <TodoItem 
          key={todo.id} 
          todo={todo} 
          onDelete={onDelete}
          onEdit={onEdit}
        />
      ))}
    </div>
  );
}

// components/TodoItem.tsx
function TodoItem({ todo, onDelete, onEdit }) {
  // 单个待办项的逻辑
}

// components/TodoInput.tsx
function TodoInput({ onAdd }) {
  // 输入框的逻辑
}

// components/TodoFilter.tsx
function TodoFilter({ filter, onChange }) {
  // 过滤器的逻辑
}
```



#### 第三步、重组主组件

最后，把提取出来的 Hook 和拆分好的组件组装起来。现在主组件只需要协调这些部分，告诉它们该做什么，而不用关心具体怎么做。

```typescript
// App.tsx (50 行)
function App() {
  const { todos, loading, addTodo, deleteTodo, updateTodo } = useTodos();
  const [filter, setFilter] = useState('all');
  
  const filteredTodos = useFilteredTodos(todos, filter);
  
  if (loading) return <LoadingSpinner />;
  
  return (
    <div>
      <TodoInput onAdd={addTodo} />
      <TodoFilter filter={filter} onChange={setFilter} />
      <TodoList 
        todos={filteredTodos} 
        onDelete={deleteTodo}
        onEdit={updateTodo}
      />
    </div>
  );
}
```

看到区别了么？代码一下子从 500 行变成了 50 行，而且每个部分都很清晰。



### 重构的效果

重构后的代码有这些优势：

- 每个文件都很小，容易理解
- 职责清晰，每个组件只做一件事
- 容易测试，可以单独测试每个组件和 Hook
- 容易扩展，要加新功能只需要添加新组件
- 容易维护，改一个地方不会影响其他地方
- AI 更好理解：当你需要修改某个功能时，AI 只需要阅读相关的小文件（比如 50 行的 `TodoInput.tsx`），而不是整整 500 行的 `App.tsx`。这样 AI 能更准确地理解上下文，生成更好的代码。

这就是从玩具项目代码到商业产品代码的转变。



## 写在最后

重构和技术债管理是 Vibe Coding 中需要人工介入的环节。AI 能帮你快速写代码，但不能始终帮你保持代码的优雅，需要你有意识地去做。

让我总结一下今天的要点：

- 理解技术债：知道什么是技术债，它是如何产生的，有什么危害。
- 识别 AI 代码的问题：过度嵌套、重复代码、缺少抽象、命名随意，这些都是常见问题。
- 利用 AI 重构：AI 既能产生技术债，也能帮你偿还技术债。
- 小步重构：不要一次改太多，每次只改一小部分，确保功能不变。
- 模块化思维：把代码拆成独立的、可复用的模块，保持高内聚、低耦合。
- 及时重构：不要拖延，发现问题立刻改，不要让技术债积累。

记住，优雅的代码是需要用心维护、不断重构出来的。

希望这些重构技巧能帮你避免代码变成依托屎山，让你的 Vibe Coding 项目始终保持优雅。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
