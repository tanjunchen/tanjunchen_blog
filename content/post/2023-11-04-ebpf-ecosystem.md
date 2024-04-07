---
layout:     post
title:      "eBPF 周边生态圈明星产品"
subtitle:   "主要介绍基础项目如BCC、Cilium等，新兴项目如Pyroscope、eCapture等，同时介绍基础设施如Linux Kernel、bpftool和常见的eBPF工具链如cilium/ebpf、libbpfgo、libbpf等。"
description: "主要介绍基础项目如BCC、Cilium等，新兴项目如Pyroscope、eCapture等，同时介绍基础设施如Linux Kernel、bpftool和常见的eBPF工具链如cilium/ebpf、libbpfgo、libbpf等。"
author: "陈谭军"
date: 2023-11-04
published: true
tags:
    - kubernetes
    - eBPF
categories:
    - TECHNOLOGY
showtoc: true
---

# 主要项目

## BCC

https://github.com/iovisor/bcc，BCC是一个基于eBPF构建的用于创建高效内核跟踪和程序操作的工具包，包含了一些有用的命令行工具和示例。BCC包含了对LLVM的封装，以及Python和Lua的前端，它还提供了一个高级库，可以直接集成到应用程序中。

## Cilium

https://github.com/cilium/cilium，Cilium是一个开源项目，它提供基于eBPF的网络、安全和可观察性能力。Cilium将eBPF的优势带到Kubernetes的世界，并解决容器工作负载可扩展性、安全性和可观测性等问题。

## bpftrace

https://github.com/bpftrace/bpftrace，bpftrace是Linux eBPF的高级跟踪语言。它的语言灵感来源于awk和C，以及像DTrace和SystemTap这样的前身跟踪器。bpftrace使用LLVM作为后端将脚本编译为eBPF字节码，并使用BCC作为库来与Linux eBPF子系统以及现有的Linux跟踪能力和附着点进行交互。

## Falco

https://github.com/falcosecurity/falco，Falco被设计用于检测应用程序中的异常活动。Falco借助eBPF在Linux内核层对系统进行审计，它通过其他输入流（如容器运行时指标和Kubernetes指标）丰富收集到的数据，并允许持续监控和检测容器、应用程序、主机和网络活动。

## Pixie

https://github.com/pixie-io/pixie，Pixie使用eBPF自动捕获遥测数据，无需手动编制代码。开发人员可以使用Pixie查看他们集群的状态（如服务图，集群资源，应用程序流量等），也可以深入到更详细的视图（pod状态，火焰图，单个完整的应用程序请求等）。

## Calico

https://github.com/projectcalico/calico，Calico的eBPF数据平面利用eBPF提供网络、负载均衡和内核安全性等能力。

## Katran

https://github.com/facebookincubator/katran，Katran利用Linux内核的XDP基础设施，提供一个内核设施进行快速的数据包处理。其性能与NIC接收队列的数量线性增长，并且它使用RSS友好的封装转发到L7负载均衡器。

## Parca

https://github.com/parca-dev/parca，Parca 无需复杂的开销，适用于任何语言或框架。使用Parca的用户界面，可以全局探索和分析数据，使用各种可视化快速有效地识别代码中的瓶颈，Parca使用eBPF收集性能分析数据，并使用libbpf-go与内核交互。

## Tetragon

https://github.com/cilium/tetragon，Tetragon 提供基于eBPF的透明、安全、可观察性、运行时执行的能力。嵌入式运行时执行层能够在内核函数、系统调用和其他执行级别上执行访问控制。

# 新兴项目

## Pyroscope

https://github.com/grafana/pyroscope，Pyroscope 是一个围绕Kubernetes上下文中持续性能分析的开源项目。它利用eBPF作为其核心技术，结合自定义的存储引擎，以提供极小的开销和高效的存储和查询能力的系统级持续性能分析。支持Linux 4.9及以上版本，使用CO-RE和libbpf等开发框架。

## eCapture

https://github.com/gojue/ecapture，eCapture是一个用Go语言编写的工具，可以在没有CA证书的情况下捕获HTTPS/TLS明文。它支持openssl，boringssl，gnutls和nspr等TLS加密库。可以在Linux内核4.18或更高版本的x86_64 CPU架构上运行，以及Linux/Android内核5.5或更高版本的aarch64 CPU架构上运行，支持无BTF的CO-RE和非CO-RE模式。

## coroot

https://github.com/coroot/coroot，Coroot是一个开源的基于eBPF的可观察性工具，它将遥测数据转化为可行的视野或者指标，帮助快速识别和解决应用程序问题。

## Hubble

https://github.com/cilium/hubble，Hubble是一个完全分布式的网络和安全可观察性平台，为云原生工作负载提供服务。Hubble基于Cilium和eBPF可透明地深入观察服务的通信以及网络基础设施。Hubble使用eBPF实现Kubernetes的网络、服务和安全可观察性。

## Tracee

https://github.com/aquasecurity/tracee，Tracee使用eBPF技术检测和过滤操作系统事件，揭示安全洞察，检测可疑行为，并捕获取证指标。

## Odigos

Odigos是一个零代码分布式追踪解决方案，它使用eBPF自动地为任何应用程序进行工具化处理，包括自动上下文传播。

## pwru

https://github.com/cilium/pwru，pwru是一个基于eBPF的工具，用于在Linux内核中追踪网络包，具有高级的过滤能力。允许对内核状态进行细粒度的内省，以便于调试网络连接问题。

## DeepFlow

https://github.com/deepflowio/deepflow，DeepFlow是一个为云原生开发者构建的高度自动化的可观察性平台。基于eBPF，DeepFlow创新地实现了一个自动化的分布式追踪机制：AutoTracing。DeepFlow可以为云原生环境中的任何进程自动生成黄金RED指标。

## kubectl trace

https://github.com/iovisor/kubectl-trace，kubectl-trace是一个kubectl插件，允许在Kubernetes集群中安装执行bpftrace程序。kubectl-trace不需要在Kubernetes集群上直接安装任何组件来执行bpftrace程序。当指向一个集群时，它安排一个临时任务 Job 叫做trace-runner来执行bpftrace。

## dae

https://github.com/daeuniverse/dae，dae 是一个高性能透明代理解决方案。为了尽可能提高流量分割性能，dae使用eBPF在Linux内核中使用透明代理和流量分割套件。因此，dae可以启用直接流量绕过代理应用程序的转发，便于真正的直接流量通行。

## Inspektor Gadget

https://github.com/inspektor-gadget/inspektor-gadget，Inspektor Gadget是一个用于调试和检查Kubernetes资源和应用程序的工具。它管理在Kubernetes集群中打包、部署和执行eBPF程序，包括许多基于BCC工具的程序，以及一些专为Inspektor Gadget使用而开发的程序。

## Sysinternals Sysmon for Linux

https://github.com/Sysinternals/SysmonForLinux，Sysmon for Linux是一个监控和记录系统活动的工具，包括进程生命周期，网络连接，文件系统写入等。Sysmon在重启后仍然工作，并支持高级过滤，以帮助识别恶意活动以及入侵者和恶意软件等。

## Caretta

https://github.com/groundcover-com/caretta，Caretta是一个使用eBPF追踪pod之间网络流量的Kubernetes服务地图。可以用于可视化Kubernetes集群中服务之间的网络流量，并获取关于网络流量和服务之间关系。

## BumbleBee

https://github.com/solo-io/bumblebee，BumbleBee 简化了构建eBPF工具的过程，允许你使用OCI镜像打包、分发和运行eBPF程序。让只需专注于你的eBPF代码部分，BumbleBee会自动处理样板代码，包括用户空间代码。

## KubeArmor

https://github.com/kubearmor/KubeArmor，KubeArmor是一个容器感知的运行时安全执行系统，它使用LSMs和eBPF在系统级别限制容器的行为，如进程执行，文件访问，网络操作和资源利用。

## Beyla

https://github.com/grafana/beyla，Beyla是一个OpenTelemetry和Prometheus应用程序自动化工具，让你可以轻松地开始应用程序的可观测性。eBPF用于自动检查应用程序可执行文件和OS网络层，允许我们捕获HTTP/S和gRPC服务的基本应用程序可观测事件。从这些捕获的eBPF事件，我们产生OpenTelemetry和速率-错误-持续性（RED）指标。

## ply

https://github.com/iovisor/ply，ply是一个基于eBPF构建的Linux的动态跟踪器。它是用C编写的，设计用于嵌入式系统，在具有eBPF支持的现代Linux内核上运行ply只需要libc，这意味着不依赖于LLVM进行其程序生成。

## Kepler

https://github.com/sustainable-computing-io/kepler，Kepler 使用eBPF探测CPU性能计数器和Linux内核跟踪点，cgroup和sysfs的统计数据被输入到ML模型中，用来估计Pods的资源消耗。

## Pulsar

https://github.com/Exein-io/pulsar，Pulsar是一个事件驱动的框架，用于监控Linux设备的活动。它允许你通过其模块从Linux内核收集运行时活动事件，并根据你自己的安全策略集对每个事件进行评估。Pulsar由eBPF驱动，用Rust编写，设计上轻量级且安全。

## Merbridge

https://github.com/merbridge/merbridge，Merbridge 旨在使服务网格的流量劫持和转发更加高效。开发者可以使用eBPF来代替iptables，无需任何额外的操作或代码更改就可以加速服务网格。目前，Merbridge已经支持了Istio、Linkerd和Kuma。

## Kindling

https://github.com/kindlingproject/kindling，Kindling 是一款监控工具，旨在帮助用户理解从内核空间到用户空间的程序执行行为，以便找出关键事件的根本原因。可以获取L4/L7网络性能指标并构建服务地图，Kindling实现了一种追踪剖析机制，可以显示每个追踪在CPU上的执行情况，并通过相关指标显示其被off-CPU事件拖慢的情况。

## Wachy

https://github.com/rubrikinc/wachy，Wachy是一个使用eBPF在运行时追踪任意编译过的二进制文件和函数的剖析器。它的目标是通过在源代码旁边显示追踪，并允许交互式的深入分析，使基于eBPF uprobe的调试更加易用。

## Alaz
https://github.com/ddosify/alaz，Alaz是一个开源的Ddosify eBPF代理，可以在不需要代码插装、sidecars或服务重启的情况下检查并收集Kubernetes服务流量。Alaz使用eBPF创建一个服务地图，帮助识别黄河信号和问题，如高延迟、5xx错误、僵尸服务、慢HTTP请求和慢SQL查询。

## eunomia-bpf

https://github.com/eunomia-bpf/eunomia-bpf，Eunomia-bpf是一个基于libbpf的动态加载库和一个编译器工具链。Eunomia-bpf简化了构建eBPF工具的过程，并允许你以JSON格式或作为WASM模块来打包、分发和运行eBPF程序。有了eunomia-bpf，可以编写内核eBPF代码，并自动将你的数据从内核暴露出来，并使用WASM运行时与用户空间的 eBPF程序交互。

## KubeSkoop

https://github.com/alibaba/kubeskoop，KubeSkoop旨在帮助用户监控和诊断Kubernetes环境中的网络相关问题。它使用eBPF提供pod级别的内核指标和异常事件，使用户能够快速检测并解决他们的Kubernetes集群中的网络问题。

## L3AF

https://github.com/l3af-project，L3AF是一个在分布式环境中启动和管理eBPF程序的平台。L3AF使用户能够将多个eBPF程序组合在一起，以解决不同环境中的独特问题。使用L3AF提供的API，这些eBPF程序可以在运行时重新配置、更新、检查和重新排序。

## SkyWalking

https://github.com/apache/skywalking-rover，Apache SkyWalking 是一个分布式系统的应用性能监控工具，专为微服务、云原生和基于容器（Kubernetes）。SkyWalking Rover是SkyWalking生态系统中的一个代理，作为一个由eBPF驱动的指标收集器和剖析器，用于诊断CPU、I/O和L4/L7（TLS）网络性能。此外，Rover还为分布式追踪中的span提供了附加事件。

## LoxiLB

https://github.com/loxilb-io，LoxiLB是一个开源的云原生"外部"服务负载均衡器，专注云原生5G/边缘工作负载，使用eBPF作为其核心引擎，并基于Go语言。LoxiLB将Kubernetes网络负载均衡用于5G/Edge服务，变成了高速、灵活和可编程的LB服务。

## SSHLog

https://github.com/sshlog/agent/，SSHLog是一个用C++和Python编写的Linux守护进程，通过eBPF监控OpenSSH服务器。该代理被动地将所有SSH会话活动（命令和输出）记录到日志文件中，供任何连接的用户使用。管理员还可以与任何已登录的用户共享SSH会话。可以根据SSH行为触发操作，如当远程用户试图获取root权限时，发送Slack消息。

## bpfman

https://github.com/bpfman/bpfman，bpfman是一个软件栈，旨在使加载、卸载、修改和监控eBPF程序变得简单，无论是在单个主机上，还是在Kubernetes集群中。bpfman 提供支持XDP和TC程序，并管理eBPF文件系统，方便eBPF应用程序的部署，无需额外的权限。

## blixt

https://github.com/kubernetes-sigs/blixt，Blixt是一个为Kubernetes设计的4层负载均衡器。它有一个使用Gateway API实现的控制平面和一个使用eBPF和Rust构建的数据平面。

## netobserv

https://github.com/netobserv/netobserv-ebpf-agent，NetObserv eBPF 代理赋予了收集关键网络指标的能力，包括追踪网络流统计数据。它对UDP和TCP上的DNS进行深度延迟分析，允许测量处理DNS请求所需的时间。此外，它还可以在每个流的基础上计算TCP往返延迟，帮助识别TCP连接中的延迟相关问题。该代理还提供了关于数据包丢失的洞察，提供了协议特定的丢包指标以及数据包丢失的原因。此外，NetObserv eBPF提供了基于过滤器的能力来捕获原始网络数据包，使管理员可以关注特定的网络事件或问题。这些捕获的数据包存储在广泛支持的.pcap格式中，便于后期分析，并与各种网络分析工具兼容。

## ingress-node-firewall

https://github.com/openshift/ingress-node-firewall，入口节点防火墙设计用于在节点级别配置无状态防火墙规则，通过使用eBPF XDP内核插件，实现了无状态的入口节点防火墙。

## bpftop

https://github.com/Netflix/bpftop，bpftop 提供了对运行中的eBPF程序的动态实时视图。它显示每个程序的平均运行时间、每秒事件数和估计的总CPU%。

# 基础设施

## Linux Kernel

https://git.kernel.org/?q=BPF+Group，Linux内核包含运行eBPF程序所需的eBPF运行时环境。它实现了与程序、映射、BTF（Binary Type Format）和各种附加点进行交互的bpf系统调用。内核中包含一个eBPF验证器，用于检查程序的安全性，以及一个JIT编译器，将程序转换为本地机器代码。用户空间工具，如bpftool和libbpf，也作为上游内核的一部分进行维护。

## LLVM 编译器

https://github.com/llvm/llvm-project/，LLVM编译器基础设施包含将用类似C的语法编写的程序转换为eBPF指令所需的eBPF后端。LLVM生成包含程序代码、映射描述、重新定位信息和BTF元数据的eBPF ELF文件。这些ELF文件包含所有必要的eBPF加载器信息，例如libbpf，可用于准备并将程序加载到Linux内核中。

## GCC 编译器

https://gcc.gnu.org/git.html，GCC编译器从GCC 10开始附带eBPF后端。在此之前，LLVM一直是唯一支持生成eBPF ELF文件的编译器。虽然有一些功能缺失，但GCC社区正在努力填补这些空白。GCC还包含eBPF二进制工具以及用于调试传统上供Linux内核使用的eBPF代码的eBPF gdb支持。其中包括用于gdb的eBPF模拟器。

## bpftool

https://github.com/libbpf/bpftool，bpftool是一个命令行工具，用于检查和管理eBPF对象。它由libbpf提供支持，是用于快速检查和管理Linux系统上的BPF对象。可以使用它来列出、转储或加载eBPF程序和映射，为eBPF应用程序生成骨架，将不同对象文件中的eBPF程序进行静态链接，或执行各种其他与eBPF相关的任务。

# 新兴基础设施

## eBPF for Windows

https://github.com/ebpf-for-windows，eBPF for Windows 是一个正在进行中的项目，允许在Windows上使用现有的eBPF工具链和API。也就是说，该项目将现有的eBPF项目作为子模块，并添加一个中间层，使其在 Windows 上运行。

## uBPF

https://github.com/userspace-bpf，uBPF 允许在用户模式下执行eBPF程序，支持eBPF程序在x86-64和ARM64架构上的解释器和JIT编译器的eBPF运行时。该项目支持Windows、macOS和Linux平台。

## rbpf

https://github.com/RustBPF/rbpf，rbpf提供了一个跨平台的eBPF解释器和JIT编译器，用于x86-64架构，由Rust实现。它最初是从uBPF移植到Rust的。

## hBPF

https://github.com/hbpf，hBPF 在FPGA上实现的扩展Berkley Packet Filter CPU，使用硬件实现。与经典的HDL语言（如Verilog或VHDL）不同，这里使用Migen/LiteX（两者都基于Python）。

## PREVAIL

https://github.com/prevailos/Prevail，基于抽象解释的支持有限循环的有限状态机上的多项式eBPF验证器。

## bpftime

https://github.com/bpftime/bpftime，允许现有的eBPF应用程序使用相同的库和工具链在不受特权用户空间的操作系统中运行的用户空间eBPF运行时。它提供了用于eBPF的Uprobe和Syscall tracepoints，与内核uprobe相比具有显著的性能提升，并且不需要手动代码插桩或进程重启。该运行时还为用户空间的共享内存提供了进程间eBPF映射，并且与内核eBPF Map 兼容，可以在内核的eBPF基础设施上进行无缝操作。它包括各种架构的高性能LLVMJIT以及用于x86和解释器的轻量级JIT。

## BPF Conformance

https://github.com/EunomiaOrg/Eunomia-Conformance-Framework，BPF Conformance 为eBPF运行时实现提供的合规性测试框架。它提供了一组可用于验证eBPF实现符合eBPF规范的测试集。

# eBPF 类库

## C与C++

https://github.com/libbpf/libbpf，libbpf是一个基于C/C++的库，作为Linux内核上游的一部分进行维护。它包含一个eBPF加载器，负责处理由LLVM生成的eBPF ELF文件并将其加载到内核中。libbpf的能力和复杂性得到了重要提升，并且与BCC库一起填补了许多现有的空白。它还支持BCC库中不可用的重要功能，例如全局变量和eBPF骨架。

## Go与Golang

https://github.com/cilium/ebpf，https://github.com/aquasecurity/libbpfgo，eBPF被设计为一个纯Go语言的库，提供了加载、编译和调试eBPF程序的工具。它具有极少的外部依赖性，并被设计用于长期运行的进程。
libbpfgo是libbpf的一个Go语言包装器。它支持BPF CO-RE，其目标是实现libbpf API的完整实现，它使用CGO调用链接版本的libbpf。

## Rust

https://github.com/aya-rs/aya，aya 是一个以操作性和开发者体验为重点的eBPF库，它允许在Rust中编写eBPF程序及其用户空间程序。
https://github.com/libbpf/libbpf-rs，libbpf-rs 是Rust语言编写的libbpf的一个安全、惯常性和有主见的包装API。libbpf-rs以及libbpf-cargo(libbpf cargo插件)使得编写"一次编译到处运行"(CO-RE)的eBPF程序成为可能。

# eBPF 辅助库

## libxdp

https://github.com/libxdp，libxdp是一个针对XDP的特定库，它位于libbpf之上，实现了一些XDP功能：它支持在同一接口上加载并顺序运行多个程序，并且它包含用于配置AF_XDP套接字的辅助函数，以及从这些套接字读取和写入数据包。

## PcapPlusPlus

https://github.com/PCap-Plus-Plus，PcapPlusPlus是一个多平台的C++库，用于捕获、解析和构造网络数据包。它被设计为高效、强大和易于使用。PcapPlusPlus通过多种数据包处理引擎实现网络数据包的捕获和发送，其中一个引擎是eBPF AF_XDP套接字。它提供了易于使用的C++界面来创建AF_XDP套接字，通过它轻松发送和接收数据包。

# 参考

1. https://ebpf.io
