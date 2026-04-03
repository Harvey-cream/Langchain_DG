# MCP 服务开发保姆级教程

> 从零开始开发 MCP 服务



你好，我是程序员鱼皮。

有个 AI 相关的概念特别火，叫 MCP，全称模型上下文协议（Model Context Protocol）。这是由 Anthropic 推出的一项开放标准，目标是为大型语言模型和 AI 助手提供一个统一、标准化的接口，使 AI 能够轻松操作外部工具并完成更复杂的任务。

这篇文章，就带大家速通 MCP，了解其核心概念，并且以我们给自己产品 [面试鸭](https://www.mianshiya.com/) 开发的面试搜题 MCP 服务为例，带大家实战 MCP 服务端和客户端的开发！

开源指路：https://github.com/yuyuanweb/mcp-mianshiya-server

![MCP 服务](https://pic.yupi.icu/1/1744008993525-16f07f5b-e3b4-4f1a-97dd-ea886c8d945d.png)



## 一、MCP 为啥如此重要？

以前，如果想让 AI 处理我们的数据，基本只能靠预训练数据或者上传数据，既麻烦又低效。而且，就算是很强大的 AI 模型，也会有数据隔离的问题，无法直接访问新数据。

现在，MCP 解决了这个问题，它突破了模型对静态知识库的依赖，使其具备更强的动态交互能力，能够像人类一样调用搜索引擎、访问本地文件、连接 API 服务，甚至直接操作第三方库。

更重要的是，只要大家都遵循 MCP 这套协议，AI 就能无缝连接本地数据、互联网资源、开发工具、生产力软件，甚至整个社区生态，实现真正的 "万物互联"，这将极大提升 AI 的协作和工作能力，价值不可估量。

![MCP 架构](https://pic.yupi.icu/1/1744006127873-09bedb4a-5c7c-4cd0-9c4d-3620f319eac7.png)



## 二、MCP 总体架构

MCP 的核心是 "客户端 - 服务器" 架构，其中 MCP 客户端主机可以连接到多个服务器。客户端主机是指希望通过 MCP 访问数据的程序，比如 Claude Desktop、IDE 或 AI 工具。

![MCP 架构图](https://pic.yupi.icu/1/1742979138403-f9f03e19-3537-461e-95d5-6f8a9a413c3a.jpeg)



## 三、MCP 开发

MCP 的使用分为两种模式，STDIO 模式（本地运行）和 SSE 模式（远程服务）。



### MCP 服务端（基于 stdio 标准流）

基于 stdio 的实现是最常见的 MCP 客户端方案，它通过标准输入输出流与 MCP 服务器进行通信。特别适用于本地部署的 MCP 服务器。

**1、引入依赖**

```xml
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-mcp-server-spring-boot-starter</artifactId>
  <version>1.0.0-M6</version>
</dependency>
```

**2、配置 MCP 服务端**

```yaml
spring:
  application:
    name: mcp-server
  main:
    web-application-type: none # 必须禁用web应用类型
    banner-mode: off # 禁用banner
  ai:
    mcp:
      server:
        stdio: true # 启用stdio模式
        name: mcp-server # 服务器名称
        version: 0.0.1 # 服务器版本
```

**3、实现 MCP 工具**

`@Tool` 是 Spring AI MCP 框架中用于快速暴露业务能力为 AI 工具的核心注解。下面是一段示例代码：

```java
/**
 * 根据搜索词搜索面试鸭面试题目
 */
@Tool(description = "根据搜索词搜索面试鸭面试题目")
public String callMianshiya(String searchText) {
    // 执行从面试鸭数据库中搜索题目的逻辑
    System.out.println("用户要搜索：" + searchText);
}
```

**4、注册 MCP 工具**

```java
@Bean
public ToolCallbackProvider serverTools(MianshiyaService mianshiyaService) {
    return MethodToolCallbackProvider.builder()
             .toolObjects(mianshiyaService)
             .build();
}
```

**5、运行服务端**

```bash
mvn clean package -DskipTests
```



### MCP 客户端（基于 stdio 标准流）

**1、引入依赖**

```xml
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-mcp-client-spring-boot-starter</artifactId>
  <version>1.0.0-M6</version>
</dependency>
```

**2、配置 MCP 服务器**

```yaml
spring:
  ai:
    mcp:
      client:
        stdio:
          servers-configuration: classpath:/mcp-servers-config.json
```

其中 `mcp-servers-config.json` 的配置如下：

```json
{
  "mcpServers": {
    "mianshiyaServer": {
      "command": "java",
      "args": [
        "-Dspring.ai.mcp.server.stdio=true",
        "-Dspring.main.web-application-type=none",
        "-Dlogging.pattern.console=",
        "-jar",
        "/yourPath/mcp-server-0.0.1-SNAPSHOT.jar"
      ]
    }
  }
}
```

**3、初始化聊天客户端**

```java
@Bean
public ChatClient initChatClient(ChatClient.Builder chatClientBuilder,
                                 ToolCallbackProvider mcpTools) {
    return chatClientBuilder.defaultTools(mcpTools).build();
}
```

**4、接口调用**

```java
@PostMapping(value = "/ai/answer")
public String generate(@RequestBody AskRequest request) {
    return chatClient.prompt()
            .user(request.getContent())
            .call()
            .content();
}
```



### MCP 服务端（基于 SSE）

除了基于 stdio 的实现外，Spring AI 还提供了基于 Server-Sent Events (SSE) 的 MCP 方案。相较于 stdio 方式，SSE 更适用于远程部署的 MCP 服务器。

**1、引入依赖**

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-mcp-server-webflux-spring-boot-starter</artifactId>
    <version>1.0.0-M6</version>
</dependency>
```

**2、配置 MCP 服务端**

```yaml
server:
  port: 8090
spring:
  ai:
    mcp:
      server:
        name: mcp-server
        version: 0.0.1
```

**3、运行服务端**

```bash
mvn clean package -DskipTests
java -jar target/mcp-server-0.0.1-SNAPSHOT.jar
```



## 四、软件使用 MCP

除了利用程序去调用 MCP 服务外，MCP 服务端还支持任意支持 MCP 协议的智能体助手，比如 Claude、Cursor 以及 Cherry Studio 等，都可以快速接入。

以 Cherry Studio 为例：

1、打开 Cherry Studio 的 "设置"，点击 "MCP 服务器"

![Cherry Studio 设置](https://pic.yupi.icu/1/1743063238632-2156707f-cfa4-4493-bf3e-68279f3972b9.png)

2、点击 "编辑 JSON"，将 MCP 配置添加到配置文件中

3、在 "设置 => 模型服务" 里选择一个模型，勾选工具函数调用功能

4、进入聊天页面，在输入框下面勾选开启 MCP 服务

![开启 MCP](https://pic.yupi.icu/1/1743063248363-b3a09c97-1bb9-4f97-ab0a-2cee5a641c83.png)

配置完成，尝试搜索下面试题目，效果不戳！

![搜索效果](https://pic.yupi.icu/1/1743063251268-145a5d00-4495-49e8-91db-f5536efca436.png)

甚至还进行面经解析，返回多个面试题目与答案的链接！

![面经解析](https://pic.yupi.icu/1/1743143537320-1fca3955-3128-42a6-bd32-0cace3bab2ab.png)

当然这个功能我们 [面试鸭官方](https://www.mianshiya.com/) 也实现了，帮助大家面试复盘：

![面试鸭面经解析](https://pic.yupi.icu/1/1744008304237-fdfb2b99-9038-43de-94ed-ca0760afdf40.png)



## 五、上传 MCP 服务

和开发一个 APP 一样，我们也可以把做好的 MCP 服务分享到第三方 MCP 服务平台。比如 MCP.so，可以理解为 MCP 服务的应用市场。

![MCP.so](https://pic.yupi.icu/1/1744008425870-c5b7958e-98cc-4a14-a4af-cba3af01fcde.png)

直接点击头像左侧的提交按钮，然后填写 MCP 服务的项目地址、以及服务器配置实例，点击提交即可。

![提交 MCP](https://pic.yupi.icu/1/1744008547763-70effe90-c0aa-4683-bbc8-060639266529.png)

提交完成后就可以在平台搜索到了：

![搜索 MCP](https://pic.yupi.icu/1/1744008638998-003207ee-8394-4ded-9ea6-83dbf189477c.png)



---



OK 就分享到这里，学会的话记得点赞收藏哦。也欢迎大家在评论区交流你对 MCP 的看法和理解~




## 推荐资源

1）鱼皮 AI 导航网站：[AI 资源大全、最新 AI 资讯、免费 AI 教程](https://ai.codefather.cn)

2）编程导航学习圈：[学习路线、编程教程、实战项目、求职宝典、交流答疑](https://www.codefather.cn)

3）程序员面试八股文：[实习/校招/社招高频考点、企业真题解析](https://www.mianshiya.com)

4）程序员写简历神器：[专业模板、丰富例句、直通面试](https://www.laoyujianli.com)

5）1 对 1 模拟面试：[实习/校招/社招面试拿 Offer 必备](https://ai.mianshiya.com)
