# Vibe Coding 安全防护技巧

> 保护你的项目和 API 密钥



你好，我是鱼皮。

很多没有编程基础的同学在用 AI 做项目时，完全不考虑安全问题。反正代码能跑就行，至于安全不安全，等出了问题再说。但实际上，一个安全问题可能会毁掉整个项目。

我见过有人因为 API Key 泄露，一夜之间被刷了几千。也见过有人的数据库被删，所有用户数据都没了。至于那些大公司的项目，但凡出点儿问题，都会引起轩然大波。

这篇文章，我就来讲讲 Vibe Coding 中最容易忽视的安全问题，以及如何避免它们。




## 一、致命问题 - API Key 泄露

在所有安全问题中，API Key 泄露是最常见、也是最致命的之一。



### 什么是 API Key？

API Key 就像你家的钥匙，有了它，就能使用某个服务。比如 OpenAI 的 API Key 能让你调用 ChatGPT，Supabase 的 API Key 能让你访问数据库。

问题是，如果这个钥匙被别人拿到了，他们就能冒充你使用这些服务。如果是付费服务，他们会花你的钱；如果是数据库，他们可能会读取、修改甚至删除你的数据。




### 泄露的常见方式

API Key 最常见的泄露方式是：**直接写在代码里，然后上传到 GitHub**。

很多同学可能会这样写调用 AI 大模型的代码：

```typescript
// ❌ 千万不要这样做！
const OPENAI_API_KEY = 'sb-yupi-abc123def456...';

const response = await fetch('https://xxx/v1/chat/completions', {
  headers: {
    'Authorization': `Bearer ${OPENAI_API_KEY}`
  }
});
```

然后把代码推送到 GitHub。

结果呢？

由于你的 GitHub 项目选择了公开，任何人都能看到你的代码，也就能看到你的 API Key。更糟糕的是，有很多自动化脚本专门在 GitHub 上扫描 API Key，一旦发现就会立刻使用。

我听说过有位老哥把 OpenAI 的 API Key 直接写在了前端代码里，然后别人直接从浏览器的开发者工具里找到了他的 API Key，几个小时内就被刷了上千。等他发现时，钱已经花光了。

这个教训告诉我们：**API Key 泄露不是小事，一定要重视。**




## 二、如何正确管理敏感信息？

既然不能把 API Key 写在代码里，那应该怎么做呢？



### 使用环境变量

正确的做法是使用环境变量。

环境变量是存储在系统或运行环境中的配置信息，不会被包含在代码里。

#### 第一步、创建 .env 文件

在项目根目录创建一个 `.env` 文件：

```
OPENAI_API_KEY=sb-yupi-abc123def456...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
DATABASE_URL=postgresql://...
```



#### 第二步、在代码中使用

在代码里通过 `process.env` 访问这些变量：

```typescript
// ✅ 正确的做法
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

const response = await fetch('https://xxx/v1/chat/completions', {
  headers: {
    'Authorization': `Bearer ${OPENAI_API_KEY}`
  }
});
```



#### 第三步、添加到 .gitignore

确保 `.env` 文件不会被上传到 GitHub：

```
# .gitignore
.env
.env.local
.env.*.local
```



#### 第四步、创建 .env.example

为了让其他人知道需要哪些环境变量，创建一个 `.env.example` 文件：

```
OPENAI_API_KEY=your_openai_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_key_here
DATABASE_URL=your_database_url_here
```

这个文件可以上传到 GitHub，因为它不包含真实的密钥。



### 前端和后端的区别

这里有一个重要的区别：**前端代码是公开的，后端代码是私密的。**

在前端（浏览器中运行的代码）中，即使你用了环境变量，最终这些值还是会被打包到 JavaScript 文件里，用户可以通过开发者工具看到。所以，**绝对不要在前端代码中使用敏感的 API Key**！

正确的做法是：

- 敏感的 API 调用放在后端
- 前端只调用你自己的后端 API
- 后端验证用户身份后，再调用第三方 API

通过代码举一些例子：

```typescript
// ❌ 不要在前端直接调用 OpenAI
// 前端代码
const response = await fetch('https://api.openai.com/v1/chat/completions', {
  headers: { 'Authorization': `Bearer ${OPENAI_API_KEY}` }
});

// ✅ 应该这样做
// 前端代码：调用自己的后端
const response = await fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({ message: userMessage })
});

// 后端代码：调用 OpenAI
export async function POST(request: Request) {
  const { message } = await request.json();
  
  // 在后端使用 API Key
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    headers: { 'Authorization': `Bearer ${process.env.OPENAI_API_KEY}` },
    body: JSON.stringify({ messages: [{ role: 'user', content: message }] })
  });
  
  return response;
}
```



### 使用密钥管理服务

如果是生产环境，建议使用专门的密钥管理服务，比如 Vercel 的环境变量管理、AWS Secrets Manager、HashiCorp Vault 等。这些服务提供了更安全的密钥存储和访问控制，大公司一般会这么做。



## 三、其他常见安全问题

除了 API Key 泄露，还有一些常见的安全问题。



### SQL 注入

SQL 注入是最经典的安全漏洞之一。如果你直接把用户输入拼接到 SQL 查询里，攻击者可以通过特殊的输入来执行恶意的 SQL 语句。

```typescript
// ❌ 危险：SQL 注入风险
const query = `SELECT * FROM users WHERE email = '${userEmail}'`;

// ✅ 安全：使用参数化查询
const query = 'SELECT * FROM users WHERE email = ?';
const result = await db.execute(query, [userEmail]);
```

好在，如果你用的是 Supabase、Prisma 等现代工具，它们会自动帮你防止 SQL 注入。但如果你写原始 SQL，一定要注意这个问题。



### XSS 攻击

XSS（跨站脚本攻击）是指攻击者在你的网站上注入恶意脚本。

比如，如果你直接把用户输入的内容显示在页面上：

```typescript
// ❌ 危险：XSS 风险
function Comment({ text }) {
  return <div dangerouslySetInnerHTML={{ __html: text }} />;
}
```

攻击者可以输入 `<script>alert('鱼皮是狗')</script>`，这段脚本就会在其他用户的浏览器中执行。

![](https://pic.yupi.icu/1/image-20260105155517608.png)

正确的做法是：

```typescript
// ✅ 安全：React 会自动转义
function Comment({ text }) {
  return <div>{text}</div>;
}
```

React 默认会转义所有内容，除非你用 `dangerouslySetInnerHTML`。所以，**除非必要，否则不要使用 `dangerouslySetInnerHTML`**。



### CSRF 攻击

CSRF（跨站请求伪造）是指攻击者诱导用户在已登录的网站上执行非预期的操作。

比如你登录了银行网站，然后在另一个标签页打开了一个恶意网站。这个恶意网站里有一段代码，会自动向银行网站发送转账请求。因为你还在登录状态，银行网站会认为这是你本人的操作，就执行了转账。这就是 CSRF 攻击。

防御 CSRF 有 3 种常用方法：

1）使用 CSRF Token：服务器生成一个随机令牌，每次表单提交时都要带上这个令牌，服务器验证令牌是否正确。

2）使用 SameSite Cookie 属性：设置 Cookie 的 SameSite 属性，让浏览器只在同站请求时发送 Cookie。

3）验证请求的 Referer 头：检查请求是从哪个网站发起的，如果不是自己的网站就拒绝。

如果你用的是 Next.js、Nuxt.js 等现代框架，它们一般会自动处理 CSRF 防护。




### 身份验证和授权

不要相信前端的任何验证！

**前端验证只是为了用户体验，真正的验证必须在后端做。**

举一些代码例子：

```typescript
// ❌ 不安全：只在前端检查
function AdminPanel() {
  const isAdmin = localStorage.getItem('isAdmin') === 'true';
  if (!isAdmin) return <div>无权访问</div>;
  return <div>管理面板</div>;
}

// ✅ 安全：在后端验证
// 前端
function AdminPanel() {
  const { data, error } = useFetch('/api/admin/data');
  if (error) return <div>无权访问</div>;
  return <div>管理面板</div>;
}

// 后端
export async function GET(request: Request) {
  const user = await verifyToken(request);
  if (!user.isAdmin) {
    return new Response('Forbidden', { status: 403 });
  }
  // 返回数据
}
```



### 依赖包的安全

如果你的项目用了很多第三方包，这些包也可能有安全漏洞。

城门失火殃及池鱼，建议定期运行 `npm audit` 命令检查漏洞。

如果发现漏洞，运行下列命令，它会自动更新有漏洞的包。

```bash
npm audit fix
```

对于无法自动修复的漏洞，要手动检查并决定是否需要更换包。



## 四、安全检查清单

每次发布项目前，建议结合 AI + 人工过一遍这个清单。




### 密钥和敏感信息

- [ ] 所有 API Key 都使用环境变量
- [ ] .env 文件已添加到 .gitignore
- [ ] 创建了 .env.example 文件
- [ ] 敏感的 API 调用都在后端进行
- [ ] 没有在前端代码中暴露密钥
- [ ] 生产环境的密钥和开发环境不同


### 用户输入验证

- [ ] 所有用户输入都经过验证
- [ ] 前端和后端都做了验证
- [ ] 使用了参数化查询，防止 SQL 注入
- [ ] 避免使用 dangerouslySetInnerHTML
- [ ] 对用户上传的文件进行了类型和大小检查


### 身份验证和授权

- [ ] 使用了安全的身份验证方案（如 JWT、OAuth）
- [ ] 密码经过加密存储（使用 bcrypt 等）
- [ ] 敏感操作需要重新验证
- [ ] 实现了权限控制，不同用户有不同权限
- [ ] Session 有过期时间


### HTTPS 和传输安全

- [ ] 生产环境使用 HTTPS
- [ ] Cookie 设置了 Secure 和 HttpOnly 标志
- [ ] 使用了 SameSite Cookie 防止 CSRF
- [ ] 敏感数据传输时加密


### 依赖和第三方服务

- [ ] 定期运行 npm audit 检查漏洞
- [ ] 只使用可信的第三方包
- [ ] 定期更新依赖包
- [ ] 审查第三方包的权限


### 错误处理和日志

- [ ] 错误信息不暴露敏感信息
- [ ] 生产环境不显示详细的错误堆栈
- [ ] 日志不记录密码等敏感信息
- [ ] 实现了错误监控和告警



## 五、让 AI 帮你做安全检查

毫无疑问，AI 也能帮你发现并修复安全问题。

你可以让 AI 帮你审查代码的安全性：

```markdown
请从安全角度审查这段代码，找出潜在的安全问题：
【贴上你的代码】
重点检查：
1. 有没有 SQL 注入风险？
2. 有没有 XSS 攻击风险？
3. 用户输入是否经过验证？
4. 敏感信息是否暴露？
5. 错误处理是否安全？
```

AI 会给你详细的安全分析。

发现问题后，让 AI 帮你修复：

```markdown
你提到了这段代码有 SQL 注入风险。请给我一个安全的实现方案，使用参数化查询。
这里的用户输入没有验证。请添加验证逻辑，确保邮箱格式正确，密码长度至少 8 位。
```

但要注意，**不要完全依赖 AI 的安全建议**。AI 可能会遗漏一些问题，或者给出不够安全的方案。你要结合自己的判断，必要时查阅官方文档或者找多个 AI 大模型确认。




### 使用安全扫描工具

除了 AI，还可以使用专门的安全扫描工具：

- Snyk：扫描依赖包的漏洞
- SonarQube：代码质量和安全分析
- OWASP ZAP：Web 应用安全测试

![](https://pic.yupi.icu/1/evo-by-snyk-hp-image_j0acql.png)

这些工具能自动发现很多安全问题。



## 六、安全开发的习惯

安全不是一次性的工作，而是要养成习惯，时刻铭记着。



### 最小权限原则

给每个用户、每个服务只分配必要的权限，不要给多余的权限。

比如，如果一个 API Key 只需要读取数据，就不要给它写入权限。如果一个用户只是普通用户，就不要给他管理员权限。

这样，即使某个密钥或账户被盗，损失也会小一些。




### 定期轮换密钥

不要一个 API Key 用到天荒地老。定期更换密钥，比如每 3 个月或每 6 个月换一次。

大多数服务都支持创建多个 API Key。你可以先创建新的 Key，更新到项目中，确认没问题后，再删除旧的 Key。



### 监控异常活动

很多 API 服务都提供了使用量监控和告警功能，记得开启，及时发现异常。

如果你的 API 调用量突然暴增，可能是 Key 被盗用了。如果有人尝试多次登录失败，可能是在暴力破解密码。



### 保持更新

安全漏洞会不断被发现，软件包也会不断更新修复漏洞。定期更新你的依赖包，关注安全公告，及时修复已知的安全问题。



### 备份数据

即使做了所有防护，还是可能出问题。建议定期备份数据，能让你在最坏的情况下也能恢复。

如果你使用了 Supabase 等第三方后端服务，可能会自动备份。如果是自己的数据库，要设置定期备份。



## 写在最后

安全问题往往是最容易被忽视的，因为它不像功能或性能那样直观。但一旦出了安全问题，后果可能是灾难性的。

最后总结一下本文的要点：

1. API Key 泄露是最大的风险：绝对不要把 API Key 写在代码里，要使用环境变量。
2. 前端和后端要区分：敏感的操作必须在后端进行，不要相信前端的任何验证。
3. 了解常见漏洞：SQL 注入、XSS、CSRF 等都是要防范的。
4. 使用安全检查清单：每次发布前过一遍清单，确保没有遗漏。
5. 养成安全习惯：最小权限、定期轮换密钥、监控异常、保持更新、备份数据。
6. 善用工具：AI 和安全扫描工具能帮你发现问题，但不要完全依赖它们。

安全是一个持续的过程，不是一劳永逸的。保持警惕，定期检查，才能保护好你的项目和用户。

希望这些安全防护技巧能帮你避免常见的安全问题，让你的 Vibe Coding 项目更加安全可靠。

学习辛苦了，给自己加个鸡腿 🍗，吃完就出发！




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
