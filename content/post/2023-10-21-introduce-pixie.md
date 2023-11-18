---
layout:     post
title:      "使用 Pixie 实现 Kubernetes 服务可观测性（4）"
subtitle:   "Pixie 是一个开源的观测和调试平台，旨在实时捕获、查询和可视化云原生应用程序的数据。它提供了一种轻量级的方式来收集和分析 Kubernetes 集群中的数据，以便进行实时观察、调试和监控。"
description: "Pixie 是一个用于 Kubernetes 应用程序的开源可观察性平台。Pixie 使用 eBPF 自动捕获遥测数据，可以使用 Pixie 查看集群的状态（服务映射、集群资源、应用程序流量），还可以深入查看更详细的视图（pod 状态、火焰图、应用程序单个请求生命周期）。Pixie 由 New Relic 公司于 2021 年 6 月捐赠给 [CNCF](https://www.cncf.io/) 作为孵化项目。"
author: "陈谭军"
date: 2023-10-21
published: true
tags:
    - kubernetes
    - pixie
    - eBPF
categories:
    - TECHNOLOGY
showtoc: true
---

# bpftrace

bpftrace 是 Linux eBPF 的高级跟踪语言。
它的语言受到 awk 和 C 以及其他跟踪器（例如 DTrace 和 SystemTap）的启发。bpftrace 开发语言是 shell，支持 x86_64、arm64和s390x 架构，要求 linux>=4.x（视功能而定）以上，依赖 BCC 和 LLVM 等基础环境。bpftrace 是一个基于 BPF (Berkley Packet Filter) 技术的高级、安全的跟踪工具。它提供了一种简单而强大的方式来观察和分析系统的运行时行为，特别是对于 Linux 系统的内核和用户空间的活动进行监视和跟踪。

这个工具有几个关键的特点和功能：
* 简单易用： bpftrace 使用一种类似于 AWK 的语法，让用户能够快速编写简洁的脚本来跟踪系统活动。
* 灵活性： 它支持在不需要重新编译内核的情况下，动态地加载和执行 BPF 程序，从而可以实时地监视系统的各种活动。
* 强大的观察能力： bpftrace 可以监视和跟踪诸如函数调用、系统调用、硬件事件等系统级别的行为。它可以用于分析性能瓶颈、调试问题以及收集各种指标。
* 安全性： BPF 技术的设计使得 bpftrace 是一个安全的工具，因为它可以执行内核级别的跟踪和监视，同时确保对系统的影响最小化。
* 社区支持和持续更新： bpftrace 是一个活跃的开源项目，有一个积极的社区不断更新和改进这个工具，增加新的功能和改善性能

# 介绍

Pixie 是一个用于 Kubernetes 应用程序的开源可观察性平台。Pixie 使用 eBPF 自动捕获遥测数据，可以使用 Pixie 查看集群的状态（服务映射、集群资源、应用程序流量），还可以深入查看更详细的视图（pod 状态、火焰图、应用程序单个请求生命周期）。Pixie 由 [New Relic](https://newrelic.com/) 公司于 2021 年 6 月捐赠给 [CNCF](https://www.cncf.io/) 作为孵化项目。

# 架构

![](/images/2023-10-21-introduce-pixie/1.png)

pixie 提供以下主要功能：
* 自动遥测：Pixie 使用 eBPF 自动收集遥测数据，如整个请求、资源和网络指标、应用程序配置文件等。
* 集群边缘计算：Pixie 在集群中本地收集、存储和查询所有遥测数据，Pixie 使用的集群 CPU 不到 5%，在大多数情况下不到 2%。
* 可脚本化：PxL 是 Pixie 灵活的 Python 查询语言，可以在 Pixie 的 UI、CLI 和客户端 API 中使用。Pixie 提供了一组[社区脚本](https://docs.px.dev/tutorials/pixie-101/)常见示例。

## 简介

Pixie 由以下组件组成：
* Pixie 边缘模块（PEM）：Pixie 的代理，在每个节点安装，PEM 使用 eBPF 来收集数据，这些数据存储在节点的本地。
* Vizier：Pixie 的收集器，按集群粒度进行安装，负责查询执行和 PEM 管理。
* Pixie Cloud：用于用户管理、身份验证和数据代理，可以托管或自托管。
* Pixie CLI: 用于部署 Pixie，还可以用于运行查询和管理资源，如 API keys。
* Pixie Client API：用于对 Pixie 进行编程访问（例如集成、Slackbots 和需要 Pixie 数据作为输入的自定义用户逻辑）。

主要核心组件：
* Vizier：Pixie 的数据面，用于进行数据收集和处理，每个需要监控的集群都会部署一个 Vizier 实例。
* Cloud：Pixie 的控制面，用于服务 Pixie 的 API 和 UI，以及管理和跟踪元数据（例如组织、用户、Viziers）。
* Vizier Operator：Pixie 的 [Kubernetes Operator](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)，用于帮助在集群上部署和管理 Vizier，如保持所有组件运行和同步最新版本。

按照具体功能划分如下所示：

![](/images/2023-10-21-introduce-pixie/2.png)

## Vizier

Vizier 数据平面主要包含以下部分：

1. Pixie Edge Moudle(PEM）：
    * 数据收集，通过守护进程部署到每个节点；
    * 短期存储，所有数据最多存储 24 小时；
    * 执行脚本，在收到脚本执行请求时进行脚本处理。
2. Collector（Kelvin）：
    * 处理数据：将 PEM 预处理的数据聚合成集群级视图；
    * 聚合连接数据：完成所有数据的预处理执行步骤。
3. Metadata：
    * 元数据中心，存储所有 Vizer 的元数据。
4. Cloud Connector
    * Vizer 和 Pixie Cloud 进行消息传递；
    * Vizer 整体状态：包括心跳以及脚本执行请求结果。
5. Query Broker：
    * 编译脚本：处理所有脚本执行，并分发到 PEM；
    * 代理数据：将编译脚本的结果代理回云端。

## Cloud

Cloud 控制平面为 Pixie 的 API 和 UI 提供服务，以便轻松查询和访问 Viziers 的数据。
它还管理系统中的元数据，例如组织、用户和 Vizier，按照功能划分为以下四类：

1. 用户准入：
    * Nginx & Envoy 代理
    * Auth 鉴权
    * API 服务
2. 组件通讯：
    * Vizier 连接器
3. 管理版本：
    * Vizier 管理器：管理 Vizier 状态；
    * Artifact Tracker：管理所有 Pixie 组件版本；
    * Plugin：管理插件信息。
4. 数据存储：
    * 索引器：以 Elastic 为索引引擎，NATS/STAN 为消息总线
    * 配置文件

## Vizier Operator

Vizier Operator 用于管理集群上的 Vizier：

1. 最佳部署：Operator执行 Vizier 的初始部署，决定未指定的 Vizier 的最适合环境；
2. 监视 Vizier 的整体状态：这包括根据 Pixie Cloud 的最新版本信息重新启动任何失败的依赖项并使 Vizier 保持最新状态。

## 数据源

Pixie 可以由用户配置为从 Go 应用程序代码中收集动态日志，并运行自定义的 BPFTrace 脚本，Pixie 默认附带了一组数据源，用户也可以对其进行扩展，Pixie 会自动收集以下数据：

* 协议 Trace：应用程序 pod 之间的整个请求生命周期，跟踪当前支持以下协议列表。
* 资源指标：pod 的 CPU、内存和 I/O 指标。
* 网络度量：网络层和连接级别的 RX/TX 统计信息。
* JVM 度量：Java 应用程序的 JVM 内存管理度量。
* 应用程序 CPU 配置文件：从应用程序中采样堆栈跟踪。Pixie 的持续分析器始终在运行，帮助在需要时识别应用程序性能瓶颈。目前支持编译语言（Go、Rust、C/C++）。

Pixie 自动支持跟踪的协议如下所示：

|Protocol|Support|Notes|
|-----|----|----|
|HTTP|Supported||
|HTTP2|Supported for [Golang gRPC](https://github.com/grpc/grpc-go)(with and without TLS).|Golang apps must have [debug information](https://docs.px.dev/reference/admin/debug-info/).|
|DNS|Supported||
|NATS|Supported|Requires a NATS build with [debug information](https://docs.px.dev/reference/admin/debug-info/).|
|MySQL|Supported||
|PostgreSQL|Supported||
|Cassandra|Supported||
|Redis|Supported||
|Kafka|Supported||
|AMQP|Supported||

# 初识 Pixie 的 eBPF 

## pxl 与 bpftrace

Pixie eBPF 的功能主要分为两部分，自带的 pxl 格式以及分发的 bpftrace 格式。

* 自带的 eBPF 功能包括：
    * 协议追踪：网络调用 send() 和 recv()；
    * 跟踪：TSL/SSL 连接，通过 TLS 库 API 直接截获加密之前的数据；
    * 应用程序 CPU 采样；
    * 分发分布式 bpftrace 脚本。
* PxL 格式使用说明：
    * Pixie Language  (PxL) ，是 pixie 自己的语言，是一种流数据语言。
    * PxL 可以通过 Pixie 平台使用基于 Web 的 UI、API 或 CLI 来执行。
    * PxL 的支持类型：

        |Type|Description|
        |-----|----|
        |INT64|64-bit integer|
        |UINT128|Unsigned 128-bit integer|
        |FLOAT64|Double precision floating point|
        |TIME64NS|Time represented as 64-bit integer in nanoseconds since UNIX epoch|
        |STRING|UTF-8 encoded string value|
        |BOOLEAN|Bool|

    * PxL 的设计理念：
        * Pxl 是一种声明语言，声明程序要执行的操作；
        * 所有 PxL 的值类型不可变；
        * PxL 的每个复制会创建一个隐式副本（引擎会自动优化）
        * PxL 的基本操作单元是数据帧，数据帧是元数据表和相关操作。

* eBPF 每一个功能的架构是：
    * data.pxl 
    * manifest.yaml
    * vis.json

* 直接使用 bpftrace：
    * 【printf 捕获】Pixie 的分布式，bpftrace 部署功能捕获通过 `bpftrace printf` 语句生成的输出，并将参数推送到自动创建的表中
    * 要求：
        * 该程序必须至少有 1 条 printf 语句。
        * 如果程序有超过 1 个 printf 语句，则所有语句的格式字符串 printfs 必须完全相同，因为它定义了表输出列。
        * BEGIN 与 END 块中不应有任何 printf 语句。
        * 如果希望指定列名称，则必须通过在格式说明符前添加冒号（例如：name:%d）来完成，列名不能包含任何空格。
        * 要以 Pixie 可识别的方式输出时间，请标记该列 time_ 并传递参数 nsecs。

## CPU 内核栈调用原理

实现逻辑：
* 采样逻辑：
    * 程序经过固定时间对 CPU 进行采样，触发 CPU 中断并收集此刻内核堆栈信息，包括当前上下文中的进程 pid、内核栈 id、用户栈 id。用户态收到内核态传入的上述信息后，将对应的堆栈地址转换为对应符号，进行可视化统计。
* 触发条件：
    * CPU 时钟触发器 `PERF_TYPE_SOFTWARE/PERF_COUNT_SW_CPU_CLOCK` 到达指定时间 `sampling_period_millis` 的倍数。

关键内核数据结构及函数说明：

![](/images/2023-10-21-introduce-pixie/4.png)

stack_traces 与 histogram 存储的数据结构示意图说明：

![](/images/2023-10-21-introduce-pixie/3.png)

eBPF 内核函数

* 功能：
    * 获取当前上下文中用户 pid、内核栈 id、用户栈 id。
    * 将用户 pid、内核栈 id、用户栈 id作为键值 key，统计出现次数。
* 内核函数源代码：

```C
int sample_stack_trace(struct bpf_perf_event_data* ctx) {

// Sample the user stack trace, and record in the
stack_traces structure.

int user_stack_id = stack_traces.get_stackid(&ctx->regs, BPF_F_USER_STACK);

// Sample the kernel stack trace, and record in the
stack_traces structure.

int kernel_stack_id = stack_traces.get_stackid(&ctx->regs, 0);

// Update the counters for this user+kernel stack trace
pair.

struct stack_trace_key_t key = {};
key.pid = bpf_get_current_pid_tgid() >> 32;
key.user_stack_id = user_stack_id;
key.kernel_stack_id = kernel_stack_id;
histogram.increment(key); //map.increment()的功能是将key对应的value的值增加1

return 0;
}
```
用户态：
1. 设置定期运行的触发条件
2. 从 BPF map 中提取收集数据
3. 将堆栈收集到的地址从机器语言转化为符号（human readable symbols）

时钟触发器：
* 使用 BCC 自带的 `attach_perf_event` 功能，将 CPU 事件进行绑定，生成 CPU 触发事件代码。

```C
bcc->attach_perf_event(PERF_TYPE_SOFTWARE,
PERF_COUNT_SW_CPU_CLOCK, std::string(probe_fn),sampling_period_millis
* kNanosPerMilli, 0);
```

收集内核映射的 map 数据：
```C
ebpf::BPFStackTable stack_traces = bcc->get_stack_table(kStackTracesMapName);

ebpf::BPFHashTable<stack_trace_key_t, uint64_t> histogram = bcc->get_hash_table<stack_trace_key_t, uint64_t>(kHistogramMapName);
```

将内核堆栈地址转化为符号：
* BCC 自带功能 `stack_traces.get_stack_symbol`，它将堆栈跟踪中的地址列表转换为符号列表。

```C
std::map<std::string, int> result;

 for (const auto& [key, count] : histogram.get_table_offline()) {
   if (key.pid != target_pid) {
     continue;
   }

   std::string stack_trace_str;

   if (key.user_stack_id >= 0) {
     std::vector<std::string> user_stack_symbols =
         stack_traces.get_stack_symbol(key.user_stack_id, key.pid);
     for (const auto& sym : user_stack_symbols) {
       stack_trace_str += sym;
       stack_trace_str += ";";
     }
   }

   if (key.kernel_stack_id >= 0) {
     std::vector<std::string> user_stack_symbols =
         stack_traces.get_stack_symbol(key.kernel_stack_id, -1);
     for (const auto& sym : user_stack_symbols) {
       stack_trace_str += sym;
       stack_trace_str += ";";
     }
   }

   result[stack_trace_str] += 1;
 }
```

# 示例

官网的演示实例如下所示：[https://youtu.be/5oY_ova5GrA](https://youtu.be/5oY_ova5GrA)。

其中 pixie 的示例界面如下所示：

![](/images/2023-10-21-introduce-pixie/5.png)

![](/images/2023-10-21-introduce-pixie/6.png)

![](/images/2023-10-21-introduce-pixie/7.png)

![](/images/2023-10-21-introduce-pixie/8.png)

![](/images/2023-10-21-introduce-pixie/9.png)

![](/images/2023-10-21-introduce-pixie/10.png)

# 安装

具体安装 Pixie 可参见官网 [https://docs.px.dev/installing-pixie/](https://docs.px.dev/installing-pixie/)，下次分享 Pixie 安装过程。

# 参考

1. https://docs.px.dev/
