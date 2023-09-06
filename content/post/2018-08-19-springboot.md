---
layout:     post
title:      "初识 Spring Boot"
subtitle:   ""
description: ""
author: "陈谭军"
date: 2018-08-19
published: true
tags:
    - java
    - spring
categories:
    - TECHNOLOGY
showtoc: true
---

最近接触到 Spring Boot，让我们一起探讨这个很火的家伙吧！！！

**什么是 Spring Boot?**

Spring Boot 是由 Pivotal 团队提供的全新框架，其设计目的是用来简化 Spring 应用的初始搭建以及开发过程。就像 maven 整合了所有的 jar 包，Spring Boot 整合了所有的框架。  
Spring Boot 的核心思想就是约定大于配置，多数 Spring Boot 应用只需要很少的 Spring 配置。采用 Spring Boot 可以大大的简化你的开发模式，所有你想集成的常用框架，它都有对应的组件支持。  
SpringBoot2.0 的推出又激起了一阵学习 SpringBoot 热潮。有缘接触到 spring boot，慢慢感受到了她的魅力。

**Spring Boot 的优势？**

使用 Spring 项目引导页面可以在几秒构建一个项目，方便对外输出各种形式的服务，如 REST API、WebSocket、Web。
1. 非常简洁的安全策略集成。
1. 支持关系数据库和非关系数据库。
1. 支持运行期内嵌容器，如 Tomcat、Jetty。
1. 强大的开发包，支持热启动。
1. 自动管理依赖。
1. 自带应用监控。
1. 支持各种 IED，如 IntelliJ IDEA 、Eclipse。

**Spring Boot 示例**

最好的方式就是看[官方文档](https://docs.spring.io/spring-boot/docs)。SpringBoot 入门小案例？基于 SpringBoot2.0.4.RELEASE 版本。

第一步：选择新建项目，选择 Spring Starter Project 项目。
![](/images/2018-08-19-springboot/1.jpeg)

第二步：填写相应的项目内容。
![](/images/2018-08-19-springboot/2.jpeg)

第三步：勾选相应的 pom.xml 的依赖包，入门选择 Web 即可，测试 web 小案例，点击下一步，然后点击完成。

第四步：maven 更新相应的 jar 包。
![](/images/2018-08-19-springboot/3.jpeg)

第五步：如果项目出现如下图的情况，可能是因为 eclipse 开发环境的原因，解决方案在 pom.xml 中加入如图内容。没有则跳过此步骤。
![](/images/2018-08-19-springboot/4.jpeg)

第六步：此时项目结构如下图。
![](/images/2018-08-19-springboot/5.jpeg)

第七步：新建一个 hello 入门类。
![](/images/2018-08-19-springboot/6.jpeg)

第八步：在 src/main/resources 下新建一个 application.yml 配置文件，内容如下：
![](/images/2018-08-19-springboot/7.jpeg)
简单来说就是配置服务器的端口，这里配置的是 8080。

第九步：运行 Spring Boot 项目，使用 postman 工具测试，是否可以得到预期效果。
![](/images/2018-08-19-springboot/8.jpeg)

第十步：浏览器的效果，达到预期效果。入门案例基本完成。
![](/images/2018-08-19-springboot/9.jpeg)

Spring Boot 网站，是最好的学习工具。
![](/images/2018-08-19-springboot/10.jpeg)
