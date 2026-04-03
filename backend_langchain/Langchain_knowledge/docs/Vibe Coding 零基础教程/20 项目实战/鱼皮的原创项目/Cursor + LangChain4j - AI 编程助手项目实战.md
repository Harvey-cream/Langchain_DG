# Cursor + LangChain4j - AI 编程助手项目实战

这是一套完整的全栈 AI 编程助手项目教程。本项目采用人工编码 + Vibe Coding 结合的方式开发，通过写 Java 代码来调用 AI、使用 Cursor 等 AI 工具辅助编码。重点在于学习如何在 Java 项目中集成 AI 能力，带你系统学习 LangChain4j 框架的几乎所有主流用法和特性。适合有一定 Java 后端开发基础的同学，快速入门 AI 应用开发，并且在简历上添加 AI 项目。

预计要学习 1 ~ 5 小时。



---



大家好，我是程序员鱼皮。现在 AI 应用开发可以说是程序员必备的技能了，求职时能够大幅增加竞争力。之前我用 Spring AI 带大家做过一个 [开源的 AI 超级智能体项目](https://github.com/liyupi/yu-ai-agent)，这次我来带大家快速掌握另一个主流的 Java AI 应用开发框架 LangChain4j。

这个教程也是我精心设计，拒绝枯燥的理论，而是用一个编程小助手项目带大家在实战中依次学习 LangChain 几乎所有主流的用法和特性。看完这个教程，你不仅学会了 LangChain，还直接多了一段项目经历，岂不美哉？

**文章近一万字，有点长，建议收藏，观看视频版体验更佳~**

> 完整视频教程：https://bilibili.com/video/BV1X4GGziEyr
>
> 项目代码开源：https://github.com/liyupi/ai-code-helper



## 需求分析

我们要实现一个 AI 编程小助手，可以帮助用户答疑解惑，并且给出编程学习的指导建议，比如：

- 编程学习路线
- 项目学习建议
- 程序员求职指南
- 程序员常见面试题



![](https://pic.yupi.icu/1/1752027043776-cd6d17ed-175f-4c7e-8b25-aee81a5296b2-20250710114302208.png)



要实现这个需求，我们首先要能够调用 AI 完成 **基础对话**，而且要支持实现 **多轮对话记忆**。此外，如果想进一步增强 AI 的能力，需要让它能够 **使用工具** 来联网搜索内容；还可以让 AI 基于我们自己的 **知识库回答**，给用户提供我们在编程领域沉淀的资源和经验。

![](https://pic.yupi.icu/1/1752028612444-351672a3-3725-4850-82b5-57d63d0ba866.png)

如果要从 0 开始实现上述功能，还是很麻烦的，因此我们要使用 AI 开发框架来提高效率。

## 什么是 LangChain4j？

目前主流的 Java AI 开发框架有 [Spring AI](https://spring.io/projects/spring-ai) 和 [LangChain4j](https://docs.langchain4j.dev/intro)，它们都提供了很多 **开箱即用的 API** 来帮你调用大模型、实现 AI 开发常用的功能，比如我们今天要学的：

- 对话记忆
- 结构化输出
- RAG 知识库
- 工具调用
- MCP
- SSE 流式输出

就我个人体验下来，这两个框架的很多概念和用法都是类似的，也都提供了很多插件扩展，都支持和 Spring Boot 项目集成。虽然有一些编码上的区别，但孰好孰坏，使用感受也是因人而异的。

**实际开发中应该如何选择呢？**

我想先带你用 LangChain4j 开发完一个项目，最后再揭晓答案，因为那个时候你自己也会有一些想法。

## AI 应用开发

### 新建项目

打开 IDEA 开发工具，新建一个 Spring Boot 项目，**Java 版本选择 21**（因为 LangChain4j 最低支持 17 版本）：

![](https://pic.yupi.icu/1/1751944012715-3ac04ad2-42e9-4c41-b998-a5318050e27c.png)

选择依赖，使用 3.5.x 版本的 Spring Boot，引入 Spring MVC 和 Lombok 注解库：

![](https://pic.yupi.icu/1/1751944035875-83da11bb-e5fa-4a19-ae57-9c214cc0f523.png)

新建项目后，先修改配置文件后缀为 `yml`，便于后面填写配置。

![](https://pic.yupi.icu/1/1751944110301-93054763-76d8-4686-ac6e-971e81b4acd4.png)

这里我会建议大家创建一个 `application-local.yml` 配置文件，将开发时用到的敏感配置写到这里，并且添加到 `.gitignore` 中，防止不小心开源出来。

### AI 对话 - ChatModel

ChatModel 是最基础的概念，负责和 AI 大模型交互。

首先需要引入至少一个 [AI 大模型依赖](https://mvnrepository.com/artifact/dev.langchain4j/langchain4j-community-dashscope-spring-boot-starter)，这里选择国内的阿里云大模型，提供了和 Spring Boot 项目的整合依赖包，比较方便：

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-community-dashscope-spring-boot-starter</artifactId>
    <version>1.1.0-beta7</version>
</dependency>
```

需要到 [阿里云百炼平台](https://bailian.console.aliyun.com/?tab=model#/api-key) 获取大模型调用 key，注意不要泄露！

![](https://pic.yupi.icu/1/1752030336360-af14dd92-7708-45dd-8420-fe87727726f3.png)

回到项目，在配置文件中添加大模型配置，指定模型名称和 API Key：

```yaml
langchain4j:
  community:
    dashscope:
      chat-model:
        model-name: qwen-max
        api-key: <You API Key here>
```

可以 [按需选择模型名称](https://bailian.console.aliyun.com/?tab=doc#/doc/?type=model)，追求效果可以用 qwen-max，否则可以选择效果、速度、成本均衡的 qwen-plus。

![](https://pic.yupi.icu/1/1752030577658-2b939caa-cf27-4065-aac5-e4f3234646b6.png)

除了编写配置让 Spring Boot 自动构建 ChatModel 外，也可以通过构造器自己创建 ChatModel 对象。这种方式更灵活，在 LangChain4j 中我们会经常用到这种方式来构造对象。

```java
ChatModel qwenModel = QwenChatModel.builder()
                    .apiKey("You API key here")
                    .modelName("qwen-max")
                    .enableSearch(true)
                    .temperature(0.7)
                    .maxTokens(4096)
                    .stops(List.of("Hello"))
                    .build();
```

有了 ChatModel 后，创建一个 AiCodeHelper 类，引入自动注入的 qwenChatModel，编写简单的对话代码，并利用 Lombok 注解打印输出结果日志：

```java
@Service
@Slf4j
public class AiCodeHelper {

    @Resource
    private ChatModel qwenChatModel;

    public String chat(String message) {
        UserMessage userMessage = UserMessage.from(message);
        ChatResponse chatResponse = qwenChatModel.chat(userMessage);
        AiMessage aiMessage = chatResponse.aiMessage();
        log.info("AI 输出：" + aiMessage.toString());
        return aiMessage.text();
    }
}
```

编写单元测试，向 AI 打个招呼吧：

```java
@SpringBootTest
class AiCodeHelperTest {

    @Resource
    private AiCodeHelper aiCodeHelper;

    @Test
    void chat() {
        aiCodeHelper.chat("你好，我是程序员鱼皮");
    }
}
```

以 Debug 模式运行单元测试，成功运行并查看输出：

![](https://pic.yupi.icu/1/1751947565712-9e3c0a68-930b-4968-8a54-19eb8beb48c9.png)

如果遇到找不到符号的 lombok 报错：

![](https://pic.yupi.icu/1/1751947096901-ca5ec0a7-ecd1-4447-9f7e-b679ad56dcde.png)
可以修改 IDEA 的注解处理器配置，改为使用项目中的 lombok：

![](https://pic.yupi.icu/1/1751947494173-01ebf704-c87b-4c6b-96a3-58aafccd5458.png)



### 多模态 - Multimodality

多模态是指能够同时处理、理解和生成多种不同类型数据的能力，比如文本、图像、音频、视频、PDF 等等。

![](https://pic.yupi.icu/1/1752051068307-72038162-f759-4fce-a0d8-0b5eec4cc59e.png)

LangChain4j 中使用多模态的方法很简单，用户消息中是可以添加图片、音视频、PDF 等媒体资源的。

![](https://pic.yupi.icu/1/1752031262335-7dda9965-faa8-44e9-8a18-f748549299fa.png)

我们先编写一个支持传入自定义 UserMessage 的方法：

```java
public String chatWithMessage(UserMessage userMessage) {
    ChatResponse chatResponse = qwenChatModel.chat(userMessage);
    AiMessage aiMessage = chatResponse.aiMessage();
    log.info("AI 输出：" + aiMessage.toString());
    return aiMessage.text();
}
```

然后编写单元测试，传入一张图片：

```java
@Test
void chatWithMessage() {
    UserMessage userMessage = UserMessage.from(
            TextContent.from("描述图片"),
            ImageContent.from("https://www.codefather.cn/logo.png")
    );
    aiCodeHelper.chatWithMessage(userMessage);
}
```

但是效果不理想，qwen-max 模型无法直接查看或分析图片：

![](https://pic.yupi.icu/1/1751948068455-4a25e7b7-9186-4148-bf42-de66b10ecef1.png)

![](https://pic.yupi.icu/1/1751949077879-32103f89-88f4-45b0-8609-77bc9ad8403d.png)



这也是目前多模态开发最关键的问题，虽然编码不难，但需要大模型本身支持多模态。可以在 LangChain 官网看到 [大模型能力支持表](https://docs.langchain4j.dev/integrations/language-models/)，不过一切以实际测试为准。

![](https://pic.yupi.icu/1/1752031226164-9a0cf728-a4d7-4005-8bbf-3f43c0479c01.png)



目前框架对多模态的适配度也没有那么好，一不留神就报错了，所以我们先了解这种用法就好了，感兴趣的同学也可以用 OpenAI 等其他模型实现多模态。



### 系统提示词 - SystemMessage

系统提示词是设置 AI 模型行为规则和角色定位的隐藏指令，用户通常不能直接看到。系统 Prompt 相当于给 AI 设定人格和能力边界，也就是告诉 AI “你是谁？你能做什么？”。

根据我们的需求，编写一段系统提示词：

```markdown
你是编程领域的小助手，帮助用户解答编程学习和求职面试相关的问题，并给出建议。重点关注 4 个方向：
1. 规划清晰的编程学习路线
2. 提供项目学习建议
3. 给出程序员求职全流程指南（比如简历优化、投递技巧）
4. 分享高频面试题和面试技巧
请用简洁易懂的语言回答，助力用户高效学习与求职。
```

编程导航的同学可以看 [AI 超级智能体项目第 3 期](https://www.codefather.cn/course/1915010091721236482/section/1916676331948027906)，有讲解过提示词优化技巧。

![](https://pic.yupi.icu/1/1752031662526-ffba01f1-3358-4d6b-a6e3-e293781cc77c.png)

想要使用系统提示词，最直接的方法是创建一个系统消息，把它和用户消息一起发送给 AI。

修改 chat 方法，代码如下：

```java
private static final String SYSTEM_MESSAGE = """
        你是编程领域的小助手，帮助用户解答编程学习和求职面试相关的问题，并给出建议。重点关注 4 个方向：
        1. 规划清晰的编程学习路线
        2. 提供项目学习建议
        3. 给出程序员求职全流程指南（比如简历优化、投递技巧）
        4. 分享高频面试题和面试技巧
        请用简洁易懂的语言回答，助力用户高效学习与求职。
        """;

public String chat(String message) {
    SystemMessage systemMessage = SystemMessage.from(SYSTEM_MESSAGE);
    UserMessage userMessage = UserMessage.from(message);
    ChatResponse chatResponse = qwenChatModel.chat(systemMessage, userMessage);
    AiMessage aiMessage = chatResponse.aiMessage();
    log.info("AI 输出：" + aiMessage.toString());
    return aiMessage.text();
}
```

再次运行单元测试和 AI 对话，显然系统预设生效了：

![](https://pic.yupi.icu/1/1751949397794-26716439-7ccb-46f2-add4-ff299989b10e.png)



### AI 服务 - AI Service

在学习更多特性前，我们要了解 LangChain4j 最重要的开发模式 —— AI Service，提供了很多高层抽象的、用起来更方便的 API，把 AI 应用当做服务来开发。

#### 使用 AI Service

首先引入 langchain4j 依赖：

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j</artifactId>
    <version>1.1.0</version>
</dependency>
```

然后创建一个编程助手 AI Service 服务，采用声明式开发方法，编写一个对话方法，然后可以直接通过 `@SystemMessage` 注解定义系统提示词。

```java
public interface AiCodeHelperService {

    @SystemMessage("你是一位编程小助手")
    String chat(String userMessage);
}
```

不过由于我们提示词较长，写到注解里很不优雅，所以单独在 resources 目录下新建文件 `system-prompt.txt` 来存储系统提示词。

`@SystemMessage` 注解支持从文件中读取系统提示词：

```java
public interface AiCodeHelperService {

    @SystemMessage(fromResource = "system-prompt.txt")
    String chat(String userMessage);
}
```

然后我们需要编写工厂类，用于创建 AI Service：

```java
@Configuration
public class AiCodeHelperServiceFactory {

    @Resource
    private ChatModel qwenChatModel;

    @Bean
    public AiCodeHelperService aiCodeHelperService() {
        return AiServices.create(AiCodeHelperService.class, qwenChatModel);
    }
}
```

调用 `AiServices.create` 方法就可以创建出 AI Service 的实现类了，背后的原理是利用 Java 反射机制创建了一个实现接口的代理对象，代理对象负责输入和输出的转换，比如把 String 类型的用户消息参数转为 UserMessage 类型并调用 ChatModel，再将 AI 返回的 AiMessage 类型转换为 String 类型作为返回值。

但我们不用关心这么多，直接写接口和注解来开发就好。你喜欢这种开发方式么？

编写单元测试，调用我们开发的 AI Service：

```java
@SpringBootTest
class AiCodeHelperServiceTest {

    @Resource
    private AiCodeHelperService aiCodeHelperService;

    @Test
    void chat() {
        String result = aiCodeHelperService.chat("你好，我是程序员鱼皮");
        System.out.println(result);
    }
}
```

Debug 运行，发现生成了 AI Service 的代理类，并且系统提示词生效了。是不是比之前自己拼接系统消息要方便多了？

![](https://pic.yupi.icu/1/1751953464452-273ae8c5-4354-467e-b14b-668d64c3b1f3.png)

#### Spring Boot 项目中使用

如果你觉得手动调用 create 方法来创建 Service 比较麻烦，在 Spring Boot 项目中可以引入依赖：

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-spring-boot-starter</artifactId>
    <version>1.1.0-beta7</version>
</dependency>
```

然后给 AI Service 加上 `@AiService` 注解，就能自动创建出服务实例了：

```java
@AiService
public interface AiCodeHelperService {

    @SystemMessage(fromResource = "system-prompt.txt")
    String chat(String userMessage);
}
```

记得注释掉之前工厂类的 @Configuration 注解，否则会出现 Bean 冲突

再次运行单元测试，也是可以正常对话的：

![](https://pic.yupi.icu/1/1751953748624-64447a00-d43c-4f8e-9fd1-805efa910753.png)

这种方式虽然更方便了，但是缺少了自主构建的灵活性（可以自由设置很多参数），所以我建议还是采用自主构建。之后的功能特性，我们也会基于这种 AI Service 开发模式来实现。

### 会话记忆 - ChatMemory

会话记忆是指让 AI 能够记住用户之前的对话内容，并保持上下文连贯性，这是实现 AI 应用的核心特性。

怎么实现对话记忆？最传统的方式是自己维护消息列表，不仅要手动添加消息，消息多了还要考虑淘汰、不同用户的消息还要隔离，想想都头疼！

```java
// 自己实现会话记忆
Map<String, List<Message>> conversationHistory = new HashMap<>();

public String chat(String message, String userId) {
    // 获取用户历史记录
    List<Message> history = conversationHistory.getOrDefault(userId, new ArrayList<>());
    
    // 添加用户新消息
    Message userMessage = new Message("user", message);
    history.add(userMessage);
    
    // 构建完整历史上下文
    StringBuilder contextBuilder = new StringBuilder();
    for (Message msg : history) {
        contextBuilder.append(msg.getRole()).append(": ").append(msg.getContent()).append("\n");
    }
    
    // 调用 AI API
    String response = callAiApi(contextBuilder.toString());
    
    // 保存 AI 回复到历史
    Message aiMessage = new Message("assistant", response);
    history.add(aiMessage);
    conversationHistory.put(userId, history);
    
    return response;
}
```

#### 使用会话记忆

LangChain4j 为我们提供了开箱即用的 `MessageWindowChatMemory` 会话记忆，最多保存 N 条消息，多余的会自动淘汰。创建会话记忆后，在构造 AI Service 设置 chatMemory：

```java
@Configuration
public class AiCodeHelperServiceFactory {

    @Resource
    private ChatModel qwenChatModel;

    @Bean
    public AiCodeHelperService aiCodeHelperService() {
        // 会话记忆
        ChatMemory chatMemory = MessageWindowChatMemory.withMaxMessages(10);
        AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
                .chatModel(qwenChatModel)
                .chatMemory(chatMemory)
                .build();
        return aiCodeHelperService;
    }
}
```

编写单元测试，测试会话记忆是否生效：

```java
@Test
void chatWithMemory() {
    String result = aiCodeHelperService.chat("你好，我是程序员鱼皮");
    System.out.println(result);
    result = aiCodeHelperService.chat("你好，我是谁来着？");
    System.out.println(result);
}
```

Debug 运行单元测试，可以看到会话记忆存储的消息列表：

![](https://pic.yupi.icu/1/1751954519469-e2f60419-ad5d-41fd-945d-c13d9861fe0f.png)

查看输出结果，会话记忆生效：

![](https://pic.yupi.icu/1/1751954654615-b4efd4d5-b87a-4980-9c65-0e252c4dd379.png)

#### 进阶用法

会话记忆默认是存储在内存的，重启后会丢失，可以通过自定义 [ChatMemoryStore](https://docs.langchain4j.dev/tutorials/chat-memory#persistence) 接口的实现类，将消息保存到 MySQL 等其他数据源中。

![](https://pic.yupi.icu/1/1752040734375-fa8362f4-c2d2-4ecd-9f3d-f328f0459b58.png)

如果有多个用户，希望每个用户之间的消息隔离，可以通过给对话方法增加 memoryId 参数和注解，在调用对话时传入 memoryId 即可（类似聊天室的房间号）：

```java
String chat(@MemoryId int memoryId, @UserMessage String userMessage);
```

构造 AI Service 时，可以通过 chatMemoryProvider 来指定 **每个 memoryId 单独创建会话记忆**：

```java
// 构造 AI Service
AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
        .chatModel(qwenChatModel)
        .chatMemoryProvider(memoryId -> MessageWindowChatMemory.withMaxMessages(10))
        .build();
```



### 结构化输出

结构化输出是指将大模型返回的文本输出转换为结构化的数据格式，比如一段 JSON、一个对象、或者是复杂的对象列表。

![](https://pic.yupi.icu/1/1752051496139-a403e8ad-9b0d-4b1c-924a-cd572f872b05.png)

结构化输出有 3 种实现方式：

- 利用大模型的 JSON schema
- 利用 Prompt + JSON Mode
- 利用 Prompt

默认是 Prompt 模式，也就是在原本的用户提示词下 **拼接一段内容** 来指定大模型强制输出包含特定字段的 JSON 文本。

```markdown
你是一个专业的信息提取助手。请从给定文本中提取人员信息，
并严格按照以下 JSON 格式返回结果：

{
    "name": "人员姓名",
    "age": 年龄数字,
    "height": 身高（米），
    "married": true/false,
    "occupation": "职业"
}

重要规则：
1. 只返回 JSON 格式，不要添加任何解释
2. 如果信息不明确，使用 null
3. age 必须是数字，不是字符串
4. married 必须是布尔值
```

感兴趣的同学可以 [阅读这篇文章](https://glaforge.dev/posts/2024/11/18/data-extraction-the-many-ways-to-get-llms-to-spit-json-content/) 了解更多，不过我们开发时无需关心这些，只要修改对话方法的返回值，框架就会自动帮我们实现结构化输出，非常爽！

![](https://pic.yupi.icu/1/1752051189479-456a7016-ab27-4a18-8927-088724ac5ddb.png)

比如我们增加一个 **让 AI 生成学习报告** 的方法，AI 需要输出学习报告对象，包含名称和建议列表：

```java
@SystemMessage(fromResource = "system-prompt.txt")
Report chatForReport(String userMessage);

// 学习报告
record Report(String name, List<String> suggestionList){}
```

编写单元测试：

```java
@Test
void chatForReport() {
    String userMessage = "你好，我是程序员鱼皮，学编程两年半，请帮我制定学习报告";
    AiCodeHelperService.Report report = aiCodeHelperService.chatForReport(userMessage);
    System.out.println(report);
}
```

运行单元测试，效果很不错：

![](https://pic.yupi.icu/1/1751955304297-a26adf70-eda0-4ebc-ae2e-aa5a8e67cf02.png)

如果你发现 AI 有时无法生成准确的 JSON，那么可以采用 JSON Schema 模式，直接在请求中约束 LLM 的输出格式。这是目前最可靠、精确度最高的结构化输出实现。

```java
ResponseFormat responseFormat = ResponseFormat.builder()
        .type(JSON)
        .jsonSchema(JsonSchema.builder()
                .name("Person")
                .rootElement(JsonObjectSchema.builder()
                        .addStringProperty("name")
                        .addIntegerProperty("age")
                        .addNumberProperty("height")
                        .addBooleanProperty("married")
                        .required("name", "age", "height", "married") 
                        .build())
                .build())
        .build();
ChatRequest chatRequest = ChatRequest.builder()
        .responseFormat(responseFormat)
        .messages(userMessage)
        .build();
```



### 检索增强生成 - RAG

RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合信息检索技术和 AI 内容生成的混合架构，可以解决大模型的知识时效性限制和幻觉问题。

简单来说，RAG 就像给 AI 配了一个 “小抄本”，让 AI 回答问题前先查一查特定的知识库来获取知识，确保回答是基于真实资料而不是凭空想象。很多企业也基于 RAG 搭建了自己的智能客服，可以用自己积累的领域知识回复用户。

RAG 的完整工作流程如下：

![](https://pic.yupi.icu/1/1752052410659-f9a142b9-0c2a-4a99-9c8c-8339970c96eb.png)

让我们来实操一下，首先我准备了 4 个文档，放在了 `resources/docs` 目录下：

![](https://pic.yupi.icu/1/1752041906112-ac985734-3a43-44a7-b13d-a1632e426828.png)

LangChain 提供了 3 种 RAG 的实现方式，我把它称为：极简版、标准版、进阶版。

#### 极简版 RAG

**极简版适合快速查看效果**，首先需要引入额外的依赖，里面包含了内置的离线 Embedding 模型，开箱即用：

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-easy-rag</artifactId>
    <version>1.1.0-beta7</version>
</dependency>
```

示例代码如下，使用内置的文档加载器读取文档，然后利用内置的 Embedding 模型将文档转换成向量，并存储在内置的 Embedding 内存存储中，最后给 AI Service 绑定默认的内容检索器。

```java
// RAG
// 1. 加载文档
List<Document> documents = FileSystemDocumentLoader.loadDocuments("src/main/resources/docs");
// 2. 使用内置的 EmbeddingModel 转换文本为向量，然后存储到自动注入的内存 embeddingStore 中
EmbeddingStoreIngestor.ingest(documents, embeddingStore);
// 构造 AI Service
AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
        .chatModel(qwenChatModel)
        .chatMemory(chatMemory)
        // RAG：从内存 embeddingStore 中检索匹配的文本片段
        .contentRetriever(EmbeddingStoreContentRetriever.from(embeddingStore))
        .build();
```

可以看到，极简版的特点是 “一切皆默认”，实际开发中，为了更好的效果，建议采用标准版或进阶版。

#### 标准版 RAG

下面来试试标准版 RAG 实现，为了更好地效果，我们需要：

- 加载 Markdown 文档并按需切割
- Markdown 文档补充文件名信息
- 自定义 Embedding 模型
- 自定义内容检索器

在 Spring Boot 配置文件中添加 Embedding 模型配置，使用阿里云提供的 `text-embedding-v4` 模型：

```yaml
langchain4j:
  community:
    dashscope:
      chat-model:
        model-name: qwen-max
        api-key: <You API Key here>
      embedding-model:
        model-name: text-embedding-v4
        api-key: <You API Key here>
```

新建 `rag.RagConfig`，编写 RAG 相关的代码，执行 RAG 的初始流程并返回了一个定制的内容检索器 Bean：

```java
/**
 * 加载 RAG
 */
@Configuration
public class RagConfig {

    @Resource
    private EmbeddingModel qwenEmbeddingModel;

    @Resource
    private EmbeddingStore<TextSegment> embeddingStore;

    @Bean
    public ContentRetriever contentRetriever() {
        // ------ RAG ------
        // 1. 加载文档
        List<Document> documents = FileSystemDocumentLoader.loadDocuments("src/main/resources/docs");
        // 2. 文档切割：将每个文档按每段进行分割，最大 1000 字符，每次重叠最多 200 个字符
        DocumentByParagraphSplitter paragraphSplitter = new DocumentByParagraphSplitter(1000, 200);
        // 3. 自定义文档加载器
        EmbeddingStoreIngestor ingestor = EmbeddingStoreIngestor.builder()
                .documentSplitter(paragraphSplitter)
                // 为了提高搜索质量，为每个 TextSegment 添加文档名称
                .textSegmentTransformer(textSegment -> TextSegment.from(
                        textSegment.metadata().getString("file_name") + "\n" + textSegment.text(),
                        textSegment.metadata()
                ))
                // 使用指定的向量模型
                .embeddingModel(qwenEmbeddingModel)
                .embeddingStore(embeddingStore)
                .build();
        // 加载文档
        ingestor.ingest(documents);
        // 4. 自定义内容查询器
        ContentRetriever contentRetriever = EmbeddingStoreContentRetriever.builder()
                .embeddingStore(embeddingStore)
                .embeddingModel(qwenEmbeddingModel)
                .maxResults(5) // 最多 5 个检索结果
                .minScore(0.75) // 过滤掉分数小于 0.75 的结果
                .build();
        return contentRetriever;
    }
}
```

然后在构建 AI Service 时绑定内容检索器：

```java
@Resource
private ContentRetriever contentRetriever;

@Bean
public AiCodeHelperService aiCodeHelperService() {
    // 会话记忆
    ChatMemory chatMemory = MessageWindowChatMemory.withMaxMessages(10);
    // 构造 AI Service
    AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
            .chatModel(qwenChatModel)
            .chatMemory(chatMemory)
            .contentRetriever(contentRetriever) // RAG 检索增强生成
            .build();
    return aiCodeHelperService;
}
```

编写单元测试：

```java
@Test
void chatWithRag() {
    Result<String> result = aiCodeHelperService.chatWithRag("怎么学习 Java？有哪些常见面试题？");
    System.out.println(result.content());
    System.out.println(result.sources());
}
```

Debug 运行，能够看到分割的文档片段，部分文档片段有内容重叠：

![](https://pic.yupi.icu/1/1751962218145-1291831b-be55-44d8-9d73-af3e4bbe3dff.png)

可以在对话记忆中看到实际发送的、增强后的 Prompt：

![](https://pic.yupi.icu/1/1751962545347-a358cb1b-94d8-47ec-b9e1-c72234aeff4a.png)

![](https://pic.yupi.icu/1/1751962597654-e87d90cc-3240-4982-9c8e-a5228468b1e7.png)

回答效果也是符合预期的：

![](https://pic.yupi.icu/1/1751962714819-a74a07e9-2f0b-44ce-b4ee-db4a4041966c.png)



#### 获取引用源文档

如果能够给 AI 的回答下面展示回答来源，更容易增加内容的可信度：

![](https://pic.yupi.icu/1/1752042954244-609fbce6-beb7-4d4b-87a5-c26cd3b8bb9a.png)

在 LangChain4j 中，实现这个功能很简单。在 AI Service 中新增方法，在原本的返回类型外封装一层 Result 类，就可以获得封装后的结果，从中能够获取到 RAG 引用的源文档、以及 Token 的消耗情况等等。

```java
@SystemMessage(fromResource = "system-prompt.txt")
Result<String> chatWithRag(String userMessage);
```

修改单元测试，输出更多信息：

```java
@Test
void chatWithRag() {
    Result<String> result = aiCodeHelperService.chatWithRag("怎么学习 Java？有哪些常见面试题？");
    String content = result.content();
    List<Content> sources = result.sources();
    System.out.println(content);
    System.out.println(sources);
}
```

执行效果如图，获取到了引用的源文档信息：

![](https://pic.yupi.icu/1/1751973326587-f0a61ddc-a0b7-4eb8-949b-d19e257262fc.png)

#### 进阶版 RAG

这就是一套标准的 RAG 实现了，大多数时候，使用标准版就够了。进阶版会更加灵活，额外支持查询转换器、查询路由、内容聚合器、内容注入器等特性，将整个 RAG 的流程流水线化（RAG pipeline）。

![](https://pic.yupi.icu/1/1752043947317-362c8de1-26e4-4657-ada0-fb414a2dab13.png)

定义好 RAG 流程后，最后通过 RetrievalAugmentor 提供给 AI Service：

```java
AiServices.builder(xxx.class)
    ...
    .retrievalAugmentor(retrievalAugmentor)
    .build();
```

此外，之前我们使用的是内存向量存储，每次启动都要重新加载文档、调用嵌入模型，比较耗时，所以实际开发中建议使用独立的存储，[官方支持很多第三方存储](https://docs.langchain4j.dev/integrations/embedding-stores/)，但是个人比较推荐 PG Vector，在原有关系库的基础上安装插件来支持向量存储，而且支持的特性很多。

![](https://pic.yupi.icu/1/1752044157711-6b5a9190-93ff-4a97-aa43-c42c519a2a0b.png)

### 工具调用 - Tools

工具调用（Tool Calling）可以理解为让 AI 大模型 **借用外部工具** 来完成它自己做不到的事情。

跟人类一样，如果只凭手脚完成不了工作，那么就可以利用工具箱来完成。

工具可以是任何东西，比如网页搜索、对外部 API 的调用、访问外部数据、或执行特定的代码等。

比如用户提问 “帮我查询上海最新的天气”，AI 本身并没有这些知识，它就可以调用 “查询天气工具”，来完成任务。

需要注意的是，工具调用的本质 **并不是 AI 服务器自己调用这些工具、也不是把工具的代码发送给 AI 服务器让它执行**，它只能提出要求，表示 “我需要执行 XX 工具完成任务”。而真正执行工具的是我们自己的应用程序，执行后再把结果告诉 AI，让它继续工作。

![](https://pic.yupi.icu/1/1752051591909-adecdfe5-87d0-4801-b556-58beea244ebe.png)



我们需要的网络搜索能力，就可以通过工具调用来实现。这里我们细化下需求：让 AI 能够通过我的 [面试鸭刷题网站](https://www.mianshiya.com/) 来搜索面试题。

实现方案很简单，因为面试鸭网站的搜索页面 **支持通过 URL 参数传入不同的搜索关键词**，我们只需要利用 **Jsoup 库** 抓取面试鸭搜索页面的题目列表就可以了。

好家伙，我爬我自己？不过大家不要尝试，很容易被封号。

![](https://pic.yupi.icu/1/1752044504400-9b3b8719-dff6-4071-a084-e1236434b0c0.png)



先引入 Jsoup 库：

```xml
<dependency>
    <groupId>org.jsoup</groupId>
    <artifactId>jsoup</artifactId>
    <version>1.20.1</version>
</dependency>
```

然后在 `tools` 包下编写工具，通过 `@Tool` 注解就能声明工具了，注意 **要认真编写工具和工具参数的描述**，这直接决定了 AI 能否正确地调用工具。

```java
@Slf4j
public class InterviewQuestionTool {

    /**
     * 从面试鸭网站获取关键词相关的面试题列表
     *
     * @param keyword 搜索关键词（如"redis"、"java多线程"）
     * @return 面试题列表，若失败则返回错误信息
     */
    @Tool(name = "interviewQuestionSearch", value = """
            Retrieves relevant interview questions from mianshiya.com based on a keyword.
            Use this tool when the user asks for interview questions about specific technologies,
            programming concepts, or job-related topics. The input should be a clear search term.
            """
    )
    public String searchInterviewQuestions(@P(value = "the keyword to search") String keyword) {
        List<String> questions = new ArrayList<>();
        // 构建搜索URL（编码关键词以支持中文）
        String encodedKeyword = URLEncoder.encode(keyword, StandardCharsets.UTF_8);
        String url = "https://www.mianshiya.com/search/all?searchText=" + encodedKeyword;
        // 发送请求并解析页面
        Document doc;
        try {
            doc = Jsoup.connect(url)
                    .userAgent("Mozilla/5.0")
                    .timeout(5000)
                    .get();
        } catch (IOException e) {
            log.error("get web error", e);
            return e.getMessage();
        }
        // 提取面试题
        Elements questionElements = doc.select(".ant-table-cell > a");
        questionElements.forEach(el -> questions.add(el.text().trim()));
        return String.join("\n", questions);
    }
}
```

给 AI Service 绑定工具：

```java
// 构造 AI Service
AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
        .chatModel(qwenChatModel)
        .chatMemory(chatMemory)
        .contentRetriever(contentRetriever) // RAG 检索增强生成
        .tools(new InterviewQuestionTool()) // 工具调用
        .build();
```

编写单元测试，验证工具的效果：

```java
@Test
void chatWithTools() {
    String result = aiCodeHelperService.chat("有哪些常见的计算机网络面试题？");
    System.out.println(result);
}
```

Debug 运行，发现 AI 调用了工具：

![](https://pic.yupi.icu/1/1751964854933-395ecc9e-0fb6-4788-b8e2-ae5ef1d094a7.png)

工具检索到了题目列表：

![](https://pic.yupi.icu/1/1751964893075-84d0ac23-fe02-47c0-95c3-e422d1305448.png)

可以通过 Debug 看到 AI Service 加载了工具：

![](https://pic.yupi.icu/1/1751964979312-65f04b40-9554-438b-83ff-025009f30a1c.png)

可以通过会话记忆查看工具的调用过程：

![](https://pic.yupi.icu/1/1751965074185-165ed1b9-a50f-4d21-ae85-b8c439f5065c.png)

输出结果符合预期：

![](https://pic.yupi.icu/1/1751965104933-af4b3181-4dc0-40bb-9ef9-5e1c0e26b389.png)

前面只演示了最简单的工具定义方法 —— 声明式，LangChain4j 也提供了编程式的工具定义方法，不过我相信你不会想这么做的（除非是动态创建工具）。

![](https://pic.yupi.icu/1/1752045043475-a61743d1-e1ea-4912-bfac-d77ce6e43858.png)

除了联网搜索外，还有一些经典的工具，比如文件读写、PDF 生成、调用终端、输出图表等等。这些工具我们可以自己开发，也可以通过 MCP 直接使用别人开发好的工具。



### 模型上下文协议 - MCP

MCP（Model Context Protocol，模型上下文协议）是一种开放标准，目的是增强 AI 与外部系统的交互能力。MCP 为 AI 提供了与外部工具、资源和服务交互的标准化方式，让 AI 能够访问最新数据、执行复杂操作，并与现有系统集成。

可以将 MCP 想象成 AI 应用的 USB 接口。就像 USB 为设备连接各种外设和配件提供了标准化方式一样，MCP 为 AI 模型连接不同的数据源和工具提供了标准化的方法。

![](https://pic.yupi.icu/1/1752051649523-398e66d6-87fa-4cc4-8c9d-951939844405.png)

简单来说，通过 MCP 协议，AI 应用可以轻松接入别人提供的服务来实现更多功能，比如查询地理位置、操作数据库、部署网站、甚至是支付等等。

刚刚我们通过工具调用实现了面试题的搜索，下面我们利用 MCP 实现 **全网搜索内容**，这也是一个典型的 MCP 应用场景了。

首先从 MCP 服务市场搜索 Web Search 服务，推荐 [下面这个](https://mcp.so/server/zhipu-web-search/BigModel?tab=content)，因为它提供了 SSE 在线调用服务，不用我们自己在本地安装启动，很方便。

![](https://pic.yupi.icu/1/1752045285371-fd70d350-80bd-4037-9b57-ff8d3a37ccf5.png)

但也要注意，用别人的服务可能是需要 API Key 的，一般是按量付费。

需要先去 [平台官方获取 API Key](https://www.bigmodel.cn/usercenter/proj-mgmt/apikeys)，等会儿会用到：

![](https://pic.yupi.icu/1/1752045399400-4e8fe95f-5d5c-47dc-aa6e-4225f2df23aa.png)

然后我们要在程序中使用这个 MCP 服务。比较坑的是，感觉 LangChain 对 MCP 的支持没有那么好，官方文档甚至都没有提到要引入的 MCP 依赖包。我还是从开源仓库中找到的依赖：

![](https://pic.yupi.icu/1/1751967113982-099b0b9a-d5a3-43e0-bdf1-1ccfb8d093b2.png)

引入依赖：

```xml
<!-- https://mvnrepository.com/artifact/dev.langchain4j/langchain4j-mcp -->
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-mcp</artifactId>
    <version>1.1.0-beta7</version>
</dependency>
```

在配置文件中新增 API Key 的配置：

```yaml
bigmodel:
  api-key: <Your Api Key>
```

新建 `mcp.McpConfig`，按照官方的开发方式，初始化和 MCP 服务的通讯，并创建 McpToolProvider 的 Bean：

```java
@Configuration
public class McpConfig {

    @Value("${bigmodel.api-key}")
    private String apiKey;

    @Bean
    public McpToolProvider mcpToolProvider() {
        // 和 MCP 服务通讯
        McpTransport transport = new HttpMcpTransport.Builder()
                .sseUrl("https://open.bigmodel.cn/api/mcp/web_search/sse?Authorization=" + apiKey)
                .logRequests(true) // 开启日志，查看更多信息
                .logResponses(true)
                .build();
        // 创建 MCP 客户端
        McpClient mcpClient = new DefaultMcpClient.Builder()
                .key("yupiMcpClient")
                .transport(transport)
                .build();
        // 从 MCP 客户端获取工具
        McpToolProvider toolProvider = McpToolProvider.builder()
                .mcpClients(mcpClient)
                .build();
        return toolProvider;
    }
}
```

注意，上面我们是通过 SSE 的方式调用 MCP。如果你是通过 npx 或 uvx 本地启动 MCP 服务，需要先安装对应的工具，并且利用下面的配置建立通讯：

```java
McpTransport transport = new StdioMcpTransport.Builder()
    .command(List.of("/usr/bin/npm", "exec", "@modelcontextprotocol/server-everything@0.6.2"))
    .logEvents(true) // only if you want to see the traffic in the log
    .build();
```

在 AI Service 中应用 MCP 工具：

```java
@Resource
private McpToolProvider mcpToolProvider;

// 构造 AI Service
AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
        .chatModel(qwenChatModel)
        .chatMemory(chatMemory)
        .contentRetriever(contentRetriever) // RAG 检索增强生成
        .tools(new InterviewQuestionTool()) // 工具调用
        .toolProvider(mcpToolProvider) // MCP 工具调用
        .build();
```

编写单元测试：

```java
@Test
void chatWithMcp() {
    String result = aiCodeHelperService.chat("什么是程序员鱼皮的编程导航？");
    System.out.println(result);
}
```

执行单元测试，通过日志查看到了搜索过程：

![](https://pic.yupi.icu/1/1751967601320-5242e432-ea07-4038-bc6f-7364aefe3d6a.png)

MCP 服务生效，从网上检索到了内容作为答案：

![](https://pic.yupi.icu/1/1751967705158-c4591073-858c-4584-a5ee-7d2ecb5261d6.png)

目前，文档中并没有提到利用 LangChain4j 开发 MCP 的方法，不过目前也不建议用 Java 开发 MCP。

### 护轨 - Guardrail

其实我感觉护轨这个名字起的不太好，其实我们把它理解为拦截器就好了。分为输入护轨（input guardrails）和输出护轨（output guardrails），可以在请求 AI 前和接收到 AI 的响应后执行一些额外操作，比如调用 AI 前鉴权、调用 AI 后记录日志。

![](https://pic.yupi.icu/1/1752051765814-ca0a709d-216e-4f84-8a05-0a8b9a3a6b66.png)

让我们小试一把，在调用 AI 前进行敏感词检测，如果用户提示词包含敏感词，则直接拒绝。

新建 `guardrail.SafeInputGuardrail`，实现 InputGuardrail 接口：

```java
/**
 * 安全检测输入护轨
 */
public class SafeInputGuardrail implements InputGuardrail {

    private static final Set<String> sensitiveWords = Set.of("kill", "evil");

    /**
     * 检测用户输入是否安全
     */
    @Override
    public InputGuardrailResult validate(UserMessage userMessage) {
        // 获取用户输入并转换为小写以确保大小写不敏感
        String inputText = userMessage.singleText().toLowerCase();
        // 使用正则表达式分割输入文本为单词
        String[] words = inputText.split("\\W+");
        // 遍历所有单词，检查是否存在敏感词
        for (String word : words) {
            if (sensitiveWords.contains(word)) {
                return fatal("Sensitive word detected: " + word);
            }
        }
        return success();
    }
}
```

LangChain4j 提供了几种快速返回的方法，简单来说，想继续调用 AI 就返回 success、否则就返回 fatal。

![](https://pic.yupi.icu/1/1751968291132-96a670ce-6551-4726-8c62-045021303af1.png)

修改 AI Service，使用输入护轨：

```java
@InputGuardrails({SafeInputGuardrail.class})
public interface AiCodeHelperService {

    @SystemMessage(fromResource = "system-prompt.txt")
    String chat(String userMessage);

    @SystemMessage(fromResource = "system-prompt.txt")
    Report chatForReport(String userMessage);

    // 学习报告
    record Report(String name, List<String> suggestionList) {
    }
}
```

编写单元测试，写一个包含敏感词的提示词：

```java
@Test
void chatWithGuardrail() {
    String result = aiCodeHelperService.chat("kill the game");
    System.out.println(result);
}
```

运行并查看效果，会触发输入检测，直接抛出异常：

![](https://pic.yupi.icu/1/1751968796339-ebf23753-55ad-4123-a4dc-e599859a28a1.png)

如果不包含敏感词，则会顺利通过。

![](https://pic.yupi.icu/1/1751968877451-3ac9f488-0b78-4c04-a227-3c89b54847c8.png)

当然，除了输入护轨，也可以编写输出护轨，对 AI 的响应结果进行检测。

### 日志和可观测性

之前我们都是通过 Debug 查看运行信息，不仅不便于调试，而且生产环境肯定不能这么做。

官方提供了 [日志](https://docs.langchain4j.dev/tutorials/logging) 和 [可观测性](https://docs.langchain4j.dev/tutorials/observability)，来帮我们更好地调试程序、发现问题。

#### 日志

开启日志的方法很简单，直接构造模型时指定开启、或者直接编写 Spring Boot 配置，支持打印 AI 请求和响应日志。

```java
OpenAiChatModel.builder()
    ...
    .logRequests(true)
    .logResponses(true)
    .build();
langchain4j.open-ai.chat-model.log-requests = true
langchain4j.open-ai.chat-model.log-responses = true
logging.level.dev.langchain4j = DEBUG
```

但并不是所有的 ChatModel 都支持，比如我测试下来 QwenChatModel 就不支持。这时只能把希望交给可观测性了。

#### 可观测性

可以通过自定义 Listener 获取 ChatModel 的调用信息，比较灵活。

新建 `listener.ChatModelListenerConfig`，输出请求、响应、错误信息：

```java
@Configuration
@Slf4j
public class ChatModelListenerConfig {
    
    @Bean
    ChatModelListener chatModelListener() {
        return new ChatModelListener() {
            @Override
            public void onRequest(ChatModelRequestContext requestContext) {
                log.info("onRequest(): {}", requestContext.chatRequest());
            }

            @Override
            public void onResponse(ChatModelResponseContext responseContext) {
                log.info("onResponse(): {}", responseContext.chatResponse());
            }

            @Override
            public void onError(ChatModelErrorContext errorContext) {
                log.info("onError(): {}", errorContext.error().getMessage());
            }
        };
    }
}
```

但是只定义 Listener 好像对 QwenChatModel 不起作用，所以我们需要手动构造自定义的 QwenChatModel。

新建 `model.QwenChatModelConfig`，构造 ChatModel 对象并绑定 Listener：

```java
@Configuration
@ConfigurationProperties(prefix = "langchain4j.community.dashscope.chat-model")
@Data
public class QwenChatModelConfig {

    private String modelName;

    private String apiKey;

    @Resource
    private ChatModelListener chatModelListener;

    @Bean
    public ChatModel myQwenChatModel() {
        return QwenChatModel.builder()
                .apiKey(apiKey)
                .modelName(modelName)
                .listeners(List.of(chatModelListener))
                .build();
    }
}
```

然后，可以将原本引用 ChatModel 的名称改为 `myQwenChatModel`，防止和 Spring Boot 自动注入的 ChatModel 冲突。

再次调用 AI，就能看到很多信息了：

![](https://pic.yupi.icu/1/1751974020940-84059541-3935-4505-b114-6fcc809b04f5.png)

### AI 服务化

至此，AI 的能力基本开发完成，但是目前只支持本地运行，需要编写一个接口提供给前端调用，让 AI 能够成为一个服务。

我们平时开发的大多数接口都是同步接口，也就是等后端处理完再返回。但是对于 AI 应用，特别是响应时间较长的对话类应用，可能会让用户失去耐心等待，因此推荐使用 SSE（Server-Sent Events）技术实现实时流式输出，类似打字机效果，大幅提升用户体验。

#### SSE 流式接口开发

LangChain 提供了 2 种方式来支持流式响应（注意，流式响应不支持结构化输出）。

一种方法是 [TokenStream](https://docs.langchain4j.dev/tutorials/ai-services#streaming)，先让 AI 对话方法返回 TokenStream，然后创建 AI Service 时指定流式对话模型 StreamingChatModel：

```java
interface Assistant {

    TokenStream chat(String message);
}

StreamingChatModel model = OpenAiStreamingChatModel.builder()
    .apiKey(System.getenv("OPENAI_API_KEY"))
    .modelName(GPT_4_O_MINI)
    .build();

Assistant assistant = AiServices.create(Assistant.class, model);

TokenStream tokenStream = assistant.chat("Tell me a joke");

tokenStream.onPartialResponse((String partialResponse) -> System.out.println(partialResponse))
    .onRetrieved((List<Content> contents) -> System.out.println(contents))
    .onToolExecuted((ToolExecution toolExecution) -> System.out.println(toolExecution))
    .onCompleteResponse((ChatResponse response) -> System.out.println(response))
    .onError((Throwable error) -> error.printStackTrace())
    .start();
```

我个人会更喜欢另一种方法，[使用 Flux](https://docs.langchain4j.dev/tutorials/ai-services/#flux) 代替 TokenStream，熟悉响应式编程的同学应该对 Flux 不陌生吧？让 AI 对话方法返回 Flux 响应式对象即可。示例代码：

```java
interface Assistant {

  Flux<String> chat(String message);
}
```

让我们试一下，首先需要引入响应式包依赖：

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-reactor</artifactId>
    <version>1.1.0-beta7</version>
</dependency>
```

然后给 AI Service 增加流式对话方法，这里顺便支持下多用户的会话记忆：

```java
// 流式对话
Flux<String> chatStream(@MemoryId int memoryId, @UserMessage String userMessage);
```

由于要用到流式模型，需要增加流式模型配置：

```yaml
langchain4j:
  community:
    dashscope:
      streaming-chat-model:
        model-name: qwen-max
        api-key: <Your Api Key>
```

构造 AI Service 时指定流式对话模型（自动注入即可），并且补充会话记忆提供者：

```java
@Resource
private StreamingChatModel qwenStreamingChatModel;

AiCodeHelperService aiCodeHelperService = AiServices.builder(AiCodeHelperService.class)
        .chatModel(myQwenChatModel)
        .streamingChatModel(qwenStreamingChatModel)
        .chatMemory(chatMemory)
        .chatMemoryProvider(memoryId ->
                MessageWindowChatMemory.withMaxMessages(10)) // 每个会话独立存储
        .contentRetriever(contentRetriever) // RAG 检索增强生成
        .tools(new InterviewQuestionTool()) // 工具调用
        .toolProvider(mcpToolProvider) // MCP 工具调用
        .build();
```

最后，编写 Controller 接口。为了方便测试，这里使用 Get 请求：

```java
@RestController
@RequestMapping("/ai")
public class AiController {

    @Resource
    private AiCodeHelperService aiCodeHelperService;

    @GetMapping("/chat")
    public Flux<ServerSentEvent<String>> chat(int memoryId, String message) {
        return aiCodeHelperService.chatStream(memoryId, message)
                .map(chunk -> ServerSentEvent.<String>builder()
                        .data(chunk)
                        .build());
    }
}
```

增加服务器配置，指定后端端口和接口路径前缀：

```yaml
server:
  port: 8081
  servlet:
    context-path: /api
```

启动服务器，用 CURL 工具测试调用：

```bash
curl -G 'http://localhost:8081/api/ai/chat' \
  --data-urlencode 'message=我是程序员鱼皮' \
  --data-urlencode 'memoryId=1'
```

可以看到流式的输出结果：

![](https://pic.yupi.icu/1/1751975773168-c4ddd770-abd7-4555-90b6-8d487630aee4.png)



#### 后端支持跨域

为了让前端项目能够顺利调用后端接口，我们需要在后端配置跨域支持。在 config 包下创建跨域配置类，代码如下：

```java
/**
 * 全局跨域配置
 */
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        // 覆盖所有请求
        registry.addMapping("/**")
                // 允许发送 Cookie
                .allowCredentials(true)
                // 放行哪些域名（必须用 patterns，否则 * 会和 allowCredentials 冲突）
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .exposedHeaders("*");
    }
}
```

注意，如果 `.allowedOrigins("*")` 与 `.allowCredentials(true)` 同时配置会导致冲突，因为出于安全考虑，跨域请求不能同时允许所有域名访问和发送认证信息（比如 Cookie）。



## AI 生成前端

由于这个项目不需要很复杂的页面，我们可以利用 AI 来快速生成前端代码，极大提高开发效率。这里鱼皮使用 [主流 AI 开发工具 Cursor](https://www.cursor.com/)，挑战不写一行代码，生成符合要求的前端项目。

### 提示词

首先准备一段详细的 Prompt，一般要包括需求、技术选型、后端接口信息，还可以提供一些原型图、后端代码等。

```markdown
你是一位专业的前端开发，请帮我根据下列信息来生成对应的前端项目代码。

## 需求

应用为《AI 编程小助手》，帮助用户解答编程学习和求职面试相关的问题，并给出建议。

只有一个页面，就是主页：页面风格为聊天室，上方是聊天记录（用户信息在右边，AI 信息在左边），下方是输入框，进入页面后自动生成一个聊天室 id，用于区分不同的会话。通过 SSE 的方式调用 chat 接口，实时显示对话内容。

## 技术选型

1. Vue3 项目
2. Axios 请求库

## 后端接口信息

接口地址前缀：http://localhost:8081/api

## SpringBoot 后端接口代码

@RestController
@RequestMapping("/ai")
public class AiController {

    @GetMapping("/chat")
    public Flux<ServerSentEvent<String>> chat(int memoryId, String message) {
        return aiCodeHelperService.chatStream(memoryId, message)
                .map(chunk -> ServerSentEvent.<String>builder()
                        .data(chunk)
                        .build());
    }
}
```

注意，如果使用的是 Windows 系统，最好在 prompt 中补充“你应该使用 Windows 支持的命令来完成任务”。



### 开发

在项目根目录下创建新的前端项目文件夹 `ai-code-helper-frontend`，使用 Cursor 工具打开该目录，输入 Prompt 执行。注意要选择 Agent 模式、Thinking 深度思考模型（推荐 Claude）：

![](https://pic.yupi.icu/1/1751976145149-beefc903-31e1-4a4f-8bbe-edf41a3a4806.png)

除了源代码外，鱼皮这里连项目介绍文档 `README.md` 都生成了，确实很爽！

![](https://pic.yupi.icu/1/1752025773338-e87a94c7-db0b-4213-9cc8-f643b14f5182.png)

生成完代码后，打开终端执行 `npm run dev` 命令，或者打开 `package.json` 文件并利用 Debug 按钮启动项目：

![](https://pic.yupi.icu/1/1752026474929-cd4a7225-1e48-4e95-a08e-6f69ea256d45.png)

### 查看效果

运行前端项目后，首先验证功能是否正常，再验证样式。如果发现功能不可用（比如发送消息后没有回复），可以按 F12 打开浏览器控制台查看前端错误信息、或者看后端项目控制台的错误信息，具体报错信息具体分析。这块就会涉及到一些前端相关的知识了，不懂前端的同学尽量多问 AI，让它帮忙修复 Bug 就好。**如果实在搞不定，也别瞎折腾了！**用鱼皮的代码就好。

比如我遇到了连接后端 SSE 服务报错的问题，直接复制报错信息给 AI 解决：

![](https://pic.yupi.icu/1/1752025968566-ab2c2d53-59e4-4519-bf55-e07b095f1e5d.png)

成功运行，查看效果：

![](https://pic.yupi.icu/1/1752026740589-5b4670c8-3f5c-470e-afba-4cfd469c31ee.png)

![](https://pic.yupi.icu/1/1752026767000-6599f85f-5926-4174-a06e-55e30e4df667.png)

确保功能和样式没问题后，记得先提交代码（防止后续被 AI 生成的代码污染），然后你可以按需增加更多功能，比如用 Markdown 展示 AI 的回复消息。

![](https://pic.yupi.icu/1/1752027043776-cd6d17ed-175f-4c7e-8b25-aee81a5296b2-20250710114303496.png)



## 总结

OK，以上就是 LangChain4j 实战项目教程，怎么样，大家学会了还是学废了？

回到开头的那个问题：**实际开发中应该如何选择 AI 开发框架呢？**

就拿 Spring AI 和 LangChain4j 来说，不知道大家更喜欢哪个框架？我其实会更喜欢 Spring AI 的开发模式，而且 Spring AI 目前支持的能力更多，还有国内 Spring AI Alibaba 的巨头加持，生态更好，遇到问题更容易解决；LangChain4j 的优势在于可以独立于 Spring 项目使用，更自由灵活一些。

不过这类框架大家重点学习一个就好了，很多概念和用法是相通的：

![](https://pic.yupi.icu/1/1752050425995-3b2b8cf4-ad48-41ec-a1e5-154ae6cd8526.png)




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
