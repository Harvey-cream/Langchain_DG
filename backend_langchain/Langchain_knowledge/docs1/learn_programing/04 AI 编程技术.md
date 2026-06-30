# AI 编程技术入门指南

> 掌握 AI 开发框架，成为企业招聘的香饽饽



你好，我是程序员鱼皮。

作为程序员，咱们不光要会用 AI 工具、能利用 AI 开发项目，还要能够自主开发 AI 项目，把 AI 的能力接入到自己的项目中。

有句话说得好：**AI 时代，所有的传统业务都值得利用 AI 重塑一遍。**

所以现在很多公司都在招能够开发 AI 项目的程序员，这也是我们的机会。那么我们要学习哪些知识和技术，才能成为企业招聘的香饽饽呢？

⭐️ 推荐观看视频版：https://www.bilibili.com/video/BV1i9Z8YhEja



## 一、AI 开发框架

首先从技术角度出发，我们要学习主流的 AI 开发框架。目前 Java 方向最火的就是 **Spring AI** 和 **LangChain4j**。


### Spring AI

[Spring AI](https://docs.spring.io/spring-ai/reference/getting-started.html) 是 Spring 官方推出的 AI 开发框架，经过 2 年的沉淀，在 2025 年 5 月正式发布了 1.0 版本。

![Spring AI 1.0 发布](https://pic.yupi.icu/1/1747881171718-91ac3eb5-049b-4510-8012-6736c40c9c95.png)

Spring AI 的优势在于 **更容易和主流 Java 开发框架 Spring 集成**，上手难度较低。它提供了很多现成的方法来帮我们提高开发 AI 应用的效率，比如快速对接大模型、保存会话上下文、对接向量数据库实现 RAG 等等。

![Spring AI 架构](https://pic.yupi.icu/1/1743563460857-95800757-867c-4e8a-ba7c-dd490d09fcbd.png)

Spring AI 的核心特性包括：

- 大模型调用能力：统一接口支持多种主流大模型（OpenAI、Claude、通义千问等）
- 提示工程：提供 Prompt 和 PromptTemplate 类，方便管理提示词
- 会话记忆：一行代码开启对话记忆，自动处理上下文
- RAG 检索增强生成：完整的 RAG 流程支持，包括文档加载、向量存储、检索优化
- 工具调用：通过注解快速定义工具，让 AI 调用外部服务
- MCP 支持：轻松接入和开发 MCP 服务

举个例子，使用 Spring AI 调用大模型，只需要几行代码：

```java
// 使用 Spring AI 调用大模型
@Bean
public ChatClient chatClient(ChatModel chatModel) {
    return ChatClient.builder(chatModel).build();
}

public String doChat(String message) {
    return chatClient.prompt(message).call().content();
}
```

如果不使用 Spring AI，你就需要自己编写 HTTP 请求、解析响应，麻烦很多。



### Spring AI Alibaba

[Spring AI Alibaba](https://java2ai.com/) 是阿里巴巴基于 Spring AI 推出的国内版本，专门针对国内的 AI 生态做了优化。

它的优势在于：

- 更好地支持国内的大模型（通义千问、百度文心一言等）
- 提供了中文文档和技术支持
- 针对国内网络环境做了优化
- 有阿里云的生态支持

如果你主要使用国内的 AI 服务，Spring AI Alibaba 会是更好的选择。



### LangChain4j

[LangChain4j](https://docs.langchain4j.dev/intro) 是另一个主流的 Java AI 开发框架，它的特点是 **更灵活，更适合开发复杂的智能体**。

比如在开发一个智能文档分析系统时，利用 LangChain4j，智能体能够自动读取文档内容，调用搜索引擎获取相关背景知识，然后根据任务需求，将文档信息与外部知识结合，生成分析报告。

LangChain4j 的核心特性包括：

- AI Service：声明式开发，通过注解快速构建 AI 服务
- 会话记忆：支持多种会话记忆策略和持久化
- 结构化输出：自动将 AI 输出转换为 Java 对象
- RAG 支持：完整的 RAG 流程，支持多种向量数据库
- 工具调用：灵活的工具定义和调用机制
- 护轨机制：输入输出拦截器，增强安全性

举个例子，使用 LangChain4j 的 AI Service：

```java
@AiService
public interface AiCodeHelperService {
    @SystemMessage(fromResource = "system-prompt.txt")
    String chat(String userMessage);
}
```

只需要定义接口和注解，框架会自动生成实现类，非常方便。



### 如何选择框架？

| 场景          | 推荐框架              | 优势                     |
| ------------- | --------------------- | ------------------------ |
| Java 企业应用 | Spring AI             | 无缝集成 Spring 生态     |
| 国内 AI 服务  | Spring AI Alibaba     | 更好支持国内大模型       |
| 智能体开发    | LangChain4j           | 完整 Agent 工具链        |
| 复杂工作流    | LangGraph（进阶）     | 可视化编排               |

我的建议是，**两个都要学，先从 Spring AI 学起，再学 LangChain4j 会更简单**。很多概念和用法是相通的，学会一个，另一个也能快速上手。



## 二、AI 集成

开发 AI 应用的前提是要有大模型，但是大模型要消耗算力才能运行，算力就是金钱。从哪儿搞来大模型呢？

有 2 种方法：使用 AI 云服务、或者本地部署大模型。



### AI 云服务

AI 云服务就是其他企业为我们部署了 AI 大模型，通过 API 接口的方式提供给我们使用，按量计费。

比如阿里云百炼、火山引擎、硅基流动、OpenAI 等等。

![AI 云服务](https://pic.yupi.icu/1/1743563631799-46ff94d5-d51b-4dc5-b6cf-dec28bdcdb39.png)

咱们程序员需要重点掌握的是：

1. 如何通过 API 接入云服务？
2. 如何使用 AI 云服务来创建智能体和配置参数？
3. 如何选择合适的云服务？这就需要关注各家云服务的计费模式和服务质量
4. 如何更低成本、更稳定地使用云服务？这就需要我们学习 Prompt 工程和高可用技术



### 本地部署大模型

本地部署大模型对于很多企业来说也是刚需，数据无需上传至云端，能够有效保障数据的安全性和隐私性，尤其适用于医疗、金融等对数据安全极为敏感的行业。

本地部署大模型其实并不难，只需要使用 [Ollama 工具](https://ollama.com/) 就可以一键部署各种主流的开源模型。

![Ollama](https://pic.yupi.icu/1/1743563719547-bbed1c54-d1f1-496f-afc2-d755c3538732.png)

唉，但部署大模型的难度不在于技术啊，主要是没算力啊！不然我也给我们团队的 [编程导航](https://codefather.cn) 和 [面试鸭](https://www.mianshiya.com) 都来一套鱼皮大模型了。



## 三、AI 领域业务

企业中的 AI 业务开发，可不仅仅是来个 AI 对话就够了，咱们还要掌握几种更复杂的业务开发，比如 RAG 知识库、多模态、MCP 服务、ReAct 智能体。


### RAG 知识库

很多公司都有属于自己的业务知识和文档，会构建自己的问答系统或客服，这就要用到 RAG 检索增强生成技术。

先通过文本嵌入模型，将企业各种文档转化为向量，存入向量数据库；当用户提问时，系统在向量数据库检索相关向量数据，找到最相似文档片段，和问题一起输入大模型处理。这样一来，大模型能够基于企业真实数据作答，更准确贴合实际。

![RAG 流程](https://pic.yupi.icu/1/1743563751814-4123230c-c4b8-458f-bf8b-070c7550dd54.png)

关于 RAG 能学的知识可太多了，比如主流的向量数据库 Milvus 和 PGVector、文档的抽取 / 转换 / 加载、索引的构建、查询策略的优化等等。**这也是 AI 企业面试的重点！**




### 多模态

多模态也是主流的 AI 业务场景，即融合文本、图像、音频、视频等多种不同类型的数据模态，从而提高产品使用的易用性，做出更多有创意的功能。

比如做个智能导购系统，顾客既可以输入文字描述想要的商品，系统也能识别顾客上传的商品图片，甚至可以理解顾客通过语音提出的购物需求。

![多模态](https://pic.yupi.icu/1/1743563981663-8c9f4746-03dc-4b32-8477-ba9a9042922c.png)

想开发多模态应用，咱们要学习模态转换技术，比如文本转语音（TTS）、语音转文本（STT）、光学字符识别（OCR）等。不过这些都有现成的工具库或者云服务，掌握调用方法就行。




### MCP 服务

MCP（Model Context Protocol，模型上下文协议）可以理解为提供给 AI 的各种服务，AI 利用这些服务能够实现更强大的功能。

![MCP](https://pic.yupi.icu/1/1743563832927-7a2df71f-acc1-47c4-9135-e7d888749dbc.png)

如何在项目中接入别人的 MCP 服务，来增强自己的项目能力；以及如何开发自己的 MCP 服务，让别人的项目使用，都是必须要学习的。

现在使用 Spring AI 等开发框架就可以开发 MCP 服务，而且甚至有高手做了个 [网站](http://mcpify.ai/)，能够一句话创建自己的 MCP 服务，这真的是泰裤辣。

![MCP 生成](https://pic.yupi.icu/1/1743563865750-bbd02b74-2a56-49a9-963f-e633c1484fe5.png)



### ReAct 智能体

ReAct 是一种构建智能体的开发范式，目的是打造能够依据推理结果自主采取行动的智能体。

它的开发过程会涉及到任务规划、工具调用、交互 I/O、异常处理等知识。尤其是工具调用，可以通过 Function Call 或 MCP 实现像天气查询、文件读写、网页运行、信息检索、终端命令执行等功能。

![ReAct 智能体](https://pic.yupi.icu/1/1743563922663-0096045d-8a99-4202-b30d-df77a341e697.png)

就拿开发视频网站为例，用户说了 “帮我开发一个 Dilidili 视频网站并部署上线” 的指令时，智能体首先会深入理解任务内容，通过推理梳理出一系列执行步骤，包括明确需求、设计方案、搭建框架、生成代码、部署上线等。接下来，智能体就会调用相应的工具来执行这些行动。

![智能体工作流](https://pic.yupi.icu/1/1743564028474-638e6414-9a22-4350-80f3-7bf174dd0f77.png)



## 四、AI 工具链

最后就是我们开发 AI 项目时可能会用到的一些平台、工具和类库了。




### 低代码平台

比如主流的低代码 AI 开发平台 [Dify](https://dify.ai/)，可以让我们通过拖拉拽的方式构建自己的 AI 智能体，创建知识库并导入自己的文档，搭建复杂的工作流等等。就哪怕你不会写代码，都能用它搞出复杂的 AI 应用。

![Dify](https://pic.yupi.icu/1/1743564064922-03f6365b-a712-47d9-be55-4867b848a269.png)



### 工具库

还有一些开发 AI 智能体时会用到的工具库，比如：

- Apache Tika：功能强大的文件解析器工具库，支持解析 PDF、Word、Excel、PowerPoint 等各种文档
- Playwright：用于模拟浏览器行为的工具库，AI 需要运行网页、抓取网页数据、自动化测试时都能派上用场
- JSON 格式解析库：GSON 和 Kryo
- HTML 文档解析库：jsoup

这些类库基本没什么学习成本，要用的时候看文档就好了。



### 部署工具

项目最终是要部署上线的嘛，所以我们还要掌握高效的部署工具。如果是个人学习使用、想快速上线自己的 AI 小应用，可以试试下面这些平台：

- [Vercel](https://vercel.com/)：适合前端应用的部署平台，支持自动构建、在线浏览、CDN 分发，而且还免费提供可访问的域名
- [Sealos](https://sealos.io/)：云原生应用管理平台，支持 Kubernetes 集群管理
- [Railway](https://railway.com/)：能让开发人员轻松部署 Docker 容器，无需操心服务器配置与运维

当然，想快速部署服务，Docker 容器化技术也是必须要学习的，就像 APP 的安装包一样，能够轻松分发和部署你的应用程序。

![Docker](https://pic.yupi.icu/1/1743564338228-ffc55f7b-7bcd-40df-a10b-4accfb666379.png)



## 五、学习资源推荐

怎么样，要学的东西还是挺多的吧。别担心，我也在持续学习这些内容并且会持续分享给大家。


### 1、AI 学习路线

完整的 AI 大模型应用开发学习路线可以在 [编程导航获取](https://www.codefather.cn/course/1789189862986850306/section/1912024009574629377)：

网址：https://www.codefather.cn/learn

![AI 学习路线](https://pic.yupi.icu/1/image-20250912152042459.png)


### 2、AI 项目实战

在 [编程导航](https://www.codefather.cn) 上，我带大家做了多套 AI 项目教程，涵盖了上面提到的几乎所有技术：

- AI 编程助手：LangChain4j 框架入门，实战对话记忆、结构化输出、RAG、工具调用、MCP、SSE 等
- AI 超级智能体：Spring AI 框架入门，实战 AI 恋爱大师应用 + 自主规划能力的超级智能体
- AI 零代码应用生成平台：LangChain4j AI 智能体、LangGraph4j 工作流、微服务架构
- AI 答题应用平台：React 跨端小程序、Vue3 AI 应用、分库分表、SSE 实时推送

这些项目都是企业级的真实项目，做完后可以直接写进简历。



### 3、开源项目

我也开源了不少 AI 应用开发项目，分享给大家：

- AI 应用生成平台：https://github.com/liyupi/yu-ai-code-mother
- AI 超级智能体：https://github.com/liyupi/yu-ai-agent
- AI 文献阅读助手：https://github.com/liyupi/literature-assistant
- AI 知识库：https://github.com/liyupi/ai-guide



### 4、AI 知识库

在我免费开源的 [AI 知识库](https://github.com/liyupi/ai-guide) 中，汇总收集了最新最全的 AI 知识，帮助大家更好地适应 AI 时代的到来。

网址：https://ai.codefather.cn

![](https://pic.yupi.icu/1/image-20260109121412266.png)

里面除了各种教程资料外，也重点给大家分享了很多 AI 工具的具体应用场景，比如接入办公软件提升效率、帮你做自媒体、AI 批量制作视频等，希望帮助大家举一反三，找到新的思路。



## 写在最后

AI 技术发展日新月异，对程序员的要求也在不断提高。**AI 相关知识不再只是算法工程师需要了解，而是每个程序员都必须掌握的基本技能。**

无论你是前端、后端还是全栈开发者，都需要了解 AI 应用开发的基本概念和实践方法。

因为未来的软件开发，AI 将无处不在。

如果你问我 AI 会淘汰程序员么？

我的答案仍然是 “会”。因为程序员本身就是需要持续学习和实践来保持竞争力的，只要大家能够学会我提到的这些知识，多关注 AI 的前沿资讯，相信 AI 不会抢走咱们程序员的饭碗，而是成为咱们改造世界的杠杆。




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
