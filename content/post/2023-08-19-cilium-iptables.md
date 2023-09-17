---
layout:     post
title:      "浅析 Cilium 与 iptables"
subtitle:   "浅析 Cilium 为什么仍然使用 iptables。"
description: "似乎大家都不太喜欢 iptables，Cilium 好像也是一样的。使用了 Cilium 一段时间，对于 Cilium 使用 eBPF 构建高性能、可扩展的容器网络印象深刻，并且还具备 L7 策略和可观测性能力。如果你之前还没有听说过 Cilium，可以去了解与试用一下！"
author: "陈谭军"
date: 2023-08-19
published: true
tags:
    - cilium
    - iptables
categories:
    - TECHNOLOGY
showtoc: true
---
 
# 目的

浅析 Cilium 为什么仍然使用 iptables。

# 前言

似乎大家都不太喜欢 iptables，[Cilium](https://cilium.io/) 好像也是一样的。使用了 Cilium 一段时间，对于 Cilium 使用 eBPF 构建高性能、可扩展的容器网络印象深刻，并且还具备 L7 策略和可观测性能力。如果你之前还没有听说过 Cilium，可以去了解与试用一下！

![](/images/2023-08-19-cilium-iptables/1.png)

如上图所示：这是 Cilium 目前正在做的事情。一方面因为基于 iptables 的 kube-proxy 当前的实现存在可拓展性与性能问题，另一方面，基于 eBPF 替换 kube-proxy 组件展现出高吞吐量、低延迟、更少的资源消耗优势。当前 Cilium 作为容器网络在 Kubernetes 领域大放异彩。  
在当前的内核版本（4.19）中，Cilium 仍需要 iptables 来执行其代理重定向任务，为什么 Cilium 还在使用 iptables？

# 简述 iptables？

iptables 是 Linux 系统中的一个命令行工具，它允许系统管理员配置 Linux 内核防火墙的规则。它可以用来创建、修改、删除防火墙规则，以控制进出 Linux 系统的网络流量。  
iptables 主要有五个表，分别是：filter、nat、mangle、raw 和 security，每个表有自己的特定功能和责任链。

![](/images/2023-08-19-cilium-iptables/2.png)

1. Filter 表：这是 iptables 的默认表，主要用于数据包过滤。它包含三个内置链，分别是 INPUT、FORWARD 和 OUTPUT。INPUT 链：处理进入本机的数据包、FORWARD 链：处理通过本机转发的数据包、OUTPUT 链：处理本机产生的出站数据包。
1. NAT 表：用于网络地址转换（NAT）。它包含三个内置链，分别是 PREROUTING、OUTPUT 和 POSTROUTING。PREROUTING 链：用于目标地址转换（DNAT）、OUTPUT 链：处理本机产生的数据包，用于本地生成的数据包的目标地址转换、POSTROUTING 链：用于源地址转换（SNAT）。
1. Mangle 表：用于特殊的数据包修改。它包含五个内置链，分别是 PREROUTING、OUTPUT、INPUT、FORWARD 和 POSTROUTING。
1. Raw 表：主要用于配置 exemptions，即免除某些数据包不被 stateful tracking system 追踪，它包含两个内置链，分别是 PREROUTING 和 OUTPUT。
1. Security 表：主要用于 SELinux 安全策略的设置。它包含三个内置链，分别是 INPUT、OUTPUT 和 FORWARD。

# 为什么 Cilium 仍然使用 iptables？

有两个主要原因：
1. 确保 Cilium 数据平面与现有的 iptables 可以良好兼容。无论 Cilium 对 iptables 有何看法，它仍然是 Linux 网络的一部分，数据包仍会通过它，只是影响要小得多。
1. 实现旧内核版本（4.x）中的关键功能，例如 L7 网络策略（TPROXY），这些功能无法由基于 eBPF 的解决方案实现，因为旧内核不支持它。

关键核心：  
Cilium 成功地通过其基于 eBPF 的解决方案替换了 kube-proxy，它解决了基于 iptables 的 kube-proxy 不可扩展与性能问题，在所有节点上不再有大量的 iptables 规则了，这是一个巨大的进步。

# Cilium 如何使用 iptables？

Cilium 使用 iptables 流程如下所示：
* Cilium Agent 在启动或创建新的 L7 策略时初始化规则（将基于随机选择的端口号生成一些带有 [fwmark](https://github.com/cilium/cilium/blob/1108684e354d2b6ecf66cbaf1cd82de5fa88b70f/pkg/datapath/iptables/iptables.go#L560) 的规则）
* Cilium 并不像 kube-proxy 那样定期同步这些规则。如果以某种方式删除了自定义链中的规则，则必须手动将其添加回来或重新启动 Cilium Agent。 这里比较有意思，不知是个 bug 还是 feature?
* 如上所述，规则包含两个主要部分：
  * 确保流量顺利通过默认 iptables table/chain，而不会被默认策略丢弃。（例如：接受来自自定义 veth 的流量，例如 FORWARD chain, filter table 中的 lxc_* 或 cilium_* ）。 
  * 将流量重定向到其 Envoy 代理（在 mangle 表中标记数据包并使用 [TPROXY](https://docs.kernel.org/networking/tproxy.html)，在 raw table 中匹配 [magic mark](https://github.com/cilium/cilium/blob/main/pkg/datapath/linux/linux_defaults/mark.go) 以避免被跟踪），这些规则在每个节点上略有不同。
* 更多关于 L7 策略相关规则，它需要一些外部配置才能正常运行。
  * TPROXY 需要用于转发标记流量的策略路由。
  * [标记](https://github.com/cilium/cilium/blob/main/pkg/datapath/linux/linux_defaults/mark.go#L51) 由 [bpf hooks](https://docs.cilium.io/en/v1.9/concepts/ebpf/intro/) 设置。
  * 需要一个应用程序代理，并带有 IP_TRANSPARENT 套接字选项。
* 默认情况下，Cilium Agent 通过 iptables 管理 conntrack ( install-no-conntrack-iptables-rules=false )，nat 表中会有一些额外的规则，并在每个节点上设置 1 个名为 cilium_node_set_v4 的 ipset，用于处理各种 NAT 操作 ( 如允许节点连接到互联网）。在 4.19 内核中，Cilium Agent 使用 enable-bpf-masquerade 选项可以达到相同的效果。
* 最后但并非最不重要的一点：规则的数量不会随着 endpoints 或 services（如 kube-proxy ）的数量线性增加，它们是相当固定的。在此过程中唯一可以添加的一件事是每种类型的 L7 策略（到目前为止，dns、http、kafka）的 2 条规则（入口/出口）规则。

Cilium 会在每个 Node 节点上生成 iptables 规则，更多详细信息可参见附录中的 iptables 规则。

# 结语

在接触 Cilium 之前，我认为我们根本不需要 iptables，但事实并非如此，至少对于使用的内核版本（4.19）来说是这样。Cilium 提供了许多厉害的能力，但其中许多仍处于测试阶段或需要更新的内核，这很遗憾。所以，有时我们仍然不得不坚持使用 iptables。

# 附录

```bash
# mangle 表
*mangle
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:CILIUM_POST_mangle - [0:0]
:CILIUM_PRE_mangle - [0:0]
:KUBE-IPTABLES-HINT - [0:0]
:KUBE-KUBELET-CANARY - [0:0]
-A PREROUTING -m comment --comment "cilium-feeder: CILIUM_PRE_mangle" -j CILIUM_PRE_mangle
# PREROUTING链的第一条规则是通过注释指定的CILIUM_PRE_mangle链。这个链是Cilium提供的一个自定义链，用于重定向代理流量或其他网络功能。
-A PREROUTING -d 10.164.251.0/24 -m mark ! --mark 0x23 -j MARK --set-xmark 0x21/0xffffffff
-A PREROUTING -d 11.254.0.0/16 -m mark ! --mark 0x23 -j MARK --set-xmark 0x21/0xffffffff
# PREROUTING 链对特定的网络IP地址段进行了标记。如果输入流量的目标IP地址在10.164.251.0/24或11.254.0.0/16范围内，且标记比0x23小，就会对这个流量进行标记（set-xmark），标记值是0x21。
-A POSTROUTING -m comment --comment "cilium-feeder: CILIUM_POST_mangle" -j CILIUM_POST_mangle
# POSTROUTING链的第一条规则与PREROUTING链的第一条规则类似，使用了注释标记的CILIUM_POST_mangle自定义链。
-A POSTROUTING -s 11.254.0.0/16 -j MARK --set-xmark 0x21/0xffffffff
-A POSTROUTING -s 10.164.251.0/24 -j MARK --set-xmark 0x21/0xffffffff
# POSTROUTING链也对特定的网络IP地址段进行了标记。如果输出流量的源IP地址与10.164.251.0/24或11.254.0.0/16匹配，则会对这个流量进行标记，标记值是0x21。
-A CILIUM_PRE_mangle -m socket --transparent -m comment --comment "cilium: any->pod redirect proxied traffic to host proxy" -j MARK --set-xmark 0x200/0xffffffff
-A CILIUM_PRE_mangle -p tcp -m mark --mark 0x23420200 -m comment --comment "cilium: TPROXY to host cilium-dns-egress proxy" -j TPROXY --on-port 16931 --on-ip 127.0.0.1 --tproxy-mark 0x200/0xffffffff
-A CILIUM_PRE_mangle -p udp -m mark --mark 0x23420200 -m comment --comment "cilium: TPROXY to host cilium-dns-egress proxy" -j TPROXY --on-port 16931 --on-ip 127.0.0.1 --tproxy-mark 0x200/0xffffffff
-A CILIUM_PRE_mangle -p tcp -m mark --mark 0x19420200 -m comment --comment "cilium: TPROXY to host /tanjunchen/envoy-lb-listener proxy" -j TPROXY --on-port 16921 --on-ip 127.0.0.1 --tproxy-mark 0x200/0xffffffff
-A CILIUM_PRE_mangle -p udp -m mark --mark 0x19420200 -m comment --comment "cilium: TPROXY to host /tanjunchen/envoy-lb-listener proxy" -j TPROXY --on-port 16921 --on-ip 127.0.0.1 --tproxy-mark 0x200/0xffffffff
# 自定义链CILIUM_PRE_mangle包含4条规则，他们的目的是将代理请求流量重定向到主机代理。这些规则基于TCP和udp协议，通过mark匹配特定的标记值（0x23420200和0x19420200），并使用TPROXY命令将流量定向到本地IP地址127.0.0.1上的特定端口（16931和16921）。

# raw 表
*raw
:PREROUTING ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:CILIUM_OUTPUT_raw - [0:0]
:CILIUM_PRE_raw - [0:0]
-A PREROUTING -m comment --comment "cilium-feeder: CILIUM_PRE_raw" -j CILIUM_PRE_raw
# 在 PREROUTING 链上，CILIUM_PRE_raw 规则是一条自定义链规则。当满足 PREROUTING 的流量到达时，该规则调用 CILIUM_PRE_raw 自定义链。
-A OUTPUT -m comment --comment "cilium-feeder: CILIUM_OUTPUT_raw" -j CILIUM_OUTPUT_raw
# 在 OUTPUT 链上，CILIUM_OUTPUT_raw 规则是一条自定义链规则。当满足 OUTPUT 的流量到达时，该规则调用 CILIUM_OUTPUT_raw 自定义链。

-A CILIUM_OUTPUT_raw -o lxc+ -m mark --mark 0xa00/0xfffffeff -m comment --comment "cilium: NOTRACK for proxy return traffic" -j CT --notrack
-A CILIUM_OUTPUT_raw -o cilium_host -m mark --mark 0xa00/0xfffffeff -m comment --comment "cilium: NOTRACK for proxy return traffic" -j CT --notrack
-A CILIUM_OUTPUT_raw -o lxc+ -m mark --mark 0x800/0xe00 -m comment --comment "cilium: NOTRACK for L7 proxy upstream traffic" -j CT --notrack
-A CILIUM_OUTPUT_raw -o cilium_host -m mark --mark 0x800/0xe00 -m comment --comment "cilium: NOTRACK for L7 proxy upstream traffic" -j CT --notrack
# 对于匹配输出路径的流量（-o lxc+ 或 -o cilium_host）和满足特定标记（0xa00/0xfffffeff 或 0x800/0xe00）的流量，将会应用 ct 模块（Connection Tracking）的 notrack 功能，以便不会被 conntrack 提取并添加到链接跟踪表中。notrack 规则的作用是使得操作系统不跟踪这些连接，不对其进行连接追踪和状态检查，从而可以避免对其进行 NAT 原地址改写的操作。
-A CILIUM_PRE_raw -m mark --mark 0x200/0xf00 -m comment --comment "cilium: NOTRACK for proxy traffic" -j CT --notrack
# 对于满足特定标记（0x200/0xf00）的流量，同样会应用 ct 模块的 notrack 功能。这个规则可能用于不需要被 cilium 代理的流量，此时操作系统不会对这些连接进行状态追踪和状态检查，从而提高网络性能。

# filter 表
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:CILIUM_FORWARD - [0:0]
:CILIUM_INPUT - [0:0]
:CILIUM_OUTPUT - [0:0]
:KUBE-FIREWALL - [0:0]
:KUBE-FORWARD - [0:0]
:KUBE-KUBELET-CANARY - [0:0]
:KUBE-NODE-PORT - [0:0]
-A INPUT -m comment --comment "cilium-feeder: CILIUM_INPUT" -j CILIUM_INPUT
# 对于匹配 INPUT 的流量，将会应用 CILIUM_INPUT 规则。这是一条自定义链规则。
-A INPUT -j KUBE-FIREWALL
# 匹配 INPUT 链的其他流量将会转到 KUBE-FIREWALL 规则链。
-A INPUT -m comment --comment "kubernetes health check rules" -j KUBE-NODE-PORT
# 对于需要进行 Kubernetes 健康检查的流量，将会被应用 KUBE-NODE-PORT 规则。
-A FORWARD -m comment --comment "cilium-feeder: CILIUM_FORWARD" -j CILIUM_FORWARD
# 对于匹配 FORWARD 的流量，将会应用 CILIUM_FORWARD 规则。这是一条自定义链规则。
-A FORWARD -m comment --comment "kubernetes forwarding rules" -j KUBE-FORWARD
# 对于其他需要进行 Kubernetes 转发的流量，将会应用 KUBE-FORWARD 规则链。
-A OUTPUT -m comment --comment "cilium-feeder: CILIUM_OUTPUT" -j CILIUM_OUTPUT
# 对于匹配 OUTPUT 的流量，将会应用 CILIUM_OUTPUT 规则。这是一条自定义链规则。
-A OUTPUT -j KUBE-FIREWALL
# 匹配 OUTPUT 链的其他流量将会转到 KUBE-FIREWALL 规则链。
-A CILIUM_FORWARD -o cilium_host -m comment --comment "cilium: any->cluster on cilium_host forward accept" -j ACCEPT
# 对于流向 cilium_host 接口并需要进行转发的流量，将会被允许通过 CILIUM_FORWARD 规则链的第一个规则。
-A CILIUM_FORWARD -i cilium_host -m comment --comment "cilium: cluster->any on cilium_host forward accept (nodeport)" -j ACCEPT
# 对于从 cilium_host 接口流向 cluster 并需要进行转发的流量，将会被允许通过 CILIUM_FORWARD 规则链的第二个规则。
-A CILIUM_FORWARD -i lxc+ -m comment --comment "cilium: cluster->any on lxc+ forward accept" -j ACCEPT
# 对于从 lxc+ 接口流向 cluster 并需要进行转发的流量，将会被允许通过 CILIUM_FORWARD 规则链的第三个规则。
-A CILIUM_FORWARD -i cilium_net -m comment --comment "cilium: cluster->any on cilium_net forward accept (nodeport)" -j ACCEPT
# 对于从 cilium_net 接口流向 cluster 并需要进行转发的流量，将会被允许通过 CILIUM_FORWARD 规则链的第四个规则。
-A CILIUM_INPUT -m mark --mark 0x200/0xf00 -m comment --comment "cilium: ACCEPT for proxy traffic" -j ACCEPT
# 对于被标记为 0x200/0xf00 的流量，将会被允许通过 CILIUM_INPUT 规则链的第一个规则。
-A CILIUM_OUTPUT -m mark --mark 0xa00/0xfffffeff -m comment --comment "cilium: ACCEPT for proxy return traffic" -j ACCEPT
# 对于被标记为 0xa00/0xfffffeff 的流量，将会被允许通过 CILIUM_OUTPUT 规则链的第一个规则。
-A CILIUM_OUTPUT -m mark --mark 0x800/0xe00 -m comment --comment "cilium: ACCEPT for l7 proxy upstream traffic" -j ACCEPT
# 对于被标记为 0x800/0xe00 的流量，将会被允许通过 CILIUM_OUTPUT 规则链的第二个规则。
-A CILIUM_OUTPUT -m mark ! --mark 0xe00/0xf00 -m mark ! --mark 0xd00/0xf00 -m mark ! --mark 0xa00/0xe00 -m mark ! --mark 0x800/0xe00 -m mark ! --mark 0xf00/0xf00 -m comment --comment "cilium: host->any mark as from host" -j MARK --set-xmark 0xc00/0xf00
# 对于从 host 发起的流量，并不属于代理流量或 L7 代理上游流量，将会被标记为 0xc00/0xf00，并允许通过 CILIUM_OUTPUT 规则链的第五个规则。
-A KUBE-FIREWALL -m comment --comment "kubernetes firewall for dropping marked packets" -m mark --mark 0x8000/0x8000 -j DROP
# 对于被标记为 0x8000/0x8000 的流量，将被 KUBE-FIREWALL 规则链的第一个规则丢弃。
-A KUBE-FIREWALL ! -s 127.0.0.0/8 -d 127.0.0.0/8 -m comment --comment "block incoming localnet connections" -m conntrack ! --ctstate RELATED,ESTABLISHED,DNAT -j DROP
# 对于不允许从本地网络（127.0.0.0/8）建立的未被跟踪状态的连接，将会被 KUBE-FIREWALL 规则链的第二个规则丢弃。
-A KUBE-FORWARD -m comment --comment "kubernetes forwarding rules" -m mark --mark 0x4000/0x4000 -j ACCEPT
-A KUBE-FORWARD -m comment --comment "kubernetes forwarding conntrack rule" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
# 对于需要转发的已建立连接，将被允许通过 KUBE-FORWARD 规则链的第二个规则。
-A KUBE-NODE-PORT -m comment --comment "Kubernetes health check node port" -m set --match-set KUBE-HEALTH-CHECK-NODE-PORT dst -j ACCEPT
# 对于匹配 KUBE-HEALTH-CHECK-NODE-PORT 的流量，将会被允许通过 KUBE-NODE-PORT 规则链的第一个规则。

# nat 表
*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:CILIUM_OUTPUT_nat - [0:0]
:CILIUM_POST_nat - [0:0]
:CILIUM_PRE_nat - [0:0]
:KUBE-FIREWALL - [0:0]
:KUBE-KUBELET-CANARY - [0:0]
:KUBE-LOAD-BALANCER - [0:0]
:KUBE-MARK-DROP - [0:0]
:KUBE-MARK-MASQ - [0:0]
:KUBE-NODE-PORT - [0:0]
:KUBE-POSTROUTING - [0:0]
:KUBE-SERVICES - [0:0]
-A PREROUTING -m comment --comment "cilium-feeder: CILIUM_PRE_nat" -j CILIUM_PRE_nat
# 对于匹配 PREROUTING 链的流量，将会应用 CILIUM_PRE_nat 规则。这是一个自定义链规则。
-A PREROUTING -m comment --comment "kubernetes service portals" -j KUBE-SERVICES
# 对于需要进行 Kubernetes 服务暴露的流量，将会应用 KUBE-SERVICES 规则链。
-A OUTPUT -m comment --comment "cilium-feeder: CILIUM_OUTPUT_nat" -j CILIUM_OUTPUT_nat
# 对于匹配 OUTPUT 链的流量，将会应用 CILIUM_OUTPUT_nat 规则。这是一个自定义链规则。
-A OUTPUT -m comment --comment "kubernetes service portals" -j KUBE-SERVICES
# 对于需要进行 Kubernetes 服务暴露的流量，将会应用 KUBE-SERVICES 规则链。
-A POSTROUTING -m comment --comment "cilium-feeder: CILIUM_POST_nat" -j CILIUM_POST_nat
# 对于匹配 POSTROUTING 链的流量，将会应用 CILIUM_POST_nat 规则。这是一个自定义链规则。
-A POSTROUTING -m comment --comment "kubernetes postrouting rules" -j KUBE-POSTROUTING
# 对于需要进行 Kubernetes 集群内转发的流量，将会应用 KUBE-POSTROUTING 规则链。
-A POSTROUTING -s 33.0.0.0/8 ! -d 33.0.0.0/8 -j MASQUERADE
# 对于来自 33.0.0.0/8 子网的流量（但不是目标地址为该子网的流量），将会进行地址伪装。
-A POSTROUTING -s 192.168.0.0/16 ! -d 192.168.0.0/16 -j MASQUERADE
# 对于来自 192.168.0.0/16 子网的流量（但不是目标地址为该子网的流量），将会进行地址伪装。
-A POSTROUTING -m mark --mark 0x21 -j MASQUERADE
-A POSTROUTING -m mark --mark 0x21 -j MASQUERADE
# 对于被标记为 0x21 的流量，将会进行地址伪装。
-A POSTROUTING -s 100.65.0.0/16 ! -d 100.65.0.0/16 -j MASQUERADE
# 对于来自 100.65.0.0/16 子网的、不属于该子网的目标地址的流量，将会进行地址伪装。
-A POSTROUTING -s 100.64.0.0/10 ! -d 100.64.0.0/10 -j MASQUERADE
# 对于来自 100.64.0.0/10 子网的、不属于该子网的目标地址的流量，也将会进行地址伪装。
-A POSTROUTING -o ol+ -m mark ! --mark 0x23 -j MASQUERADE
# 对于在 ol+ 接口流出的被标记为不是 0x23 的流量，将会进行地址伪装。
-A CILIUM_POST_nat -s 100.64.64.0/24 ! -d 100.64.64.0/24 ! -o cilium_+ -m comment --comment "cilium masquerade non-cluster" -j MASQUERADE
# 对于来自 100.64.64.0/24 子网的、不属于该子网的目标地址的流量（且不是从 cilium_host 接口发送出去），将会进行地址伪装。
-A CILIUM_POST_nat -m mark --mark 0xa00/0xe00 -m comment --comment "exclude proxy return traffic from masquerade" -j ACCEPT
# 对于被标记为 0xa00/0xe00 的流量，将会排除不进行地址伪装的规则。
-A CILIUM_POST_nat ! -s 100.64.64.0/24 ! -d 100.64.64.0/24 -o cilium_host -m comment --comment "cilium host->cluster masquerade" -j SNAT --to-source 100.64.64.84
# 对于从 cilium_host 接口发送出去的、不属于 100.64.64.0/24 子网的目标地址的流量，将会进行地址伪装（源地址为 100.64.64.84）。
-A CILIUM_POST_nat -s 127.0.0.1/32 -o cilium_host -m comment --comment "cilium host->cluster from 127.0.0.1 masquerade" -j SNAT --to-source 100.64.64.84
# 对于从 127.0.0.1 发送出去的、不属于 100.64.64.0/24 子网的目标地址的流量，将会进行地址伪装（源地址为 100.64.64.84）。
-A CILIUM_POST_nat -o cilium_host -m mark --mark 0xf00/0xf00 -m conntrack --ctstate DNAT -m comment --comment "hairpin traffic that originated from a local pod" -j SNAT --to-source 100.64.64.84
# 对于从 cilium_host 接口发送出去的、被标记为 0xf00/0xf00 并且正在进行 DNAT 的流量，将会进行地址伪装（源地址为 100.64.64.84）。
-A KUBE-FIREWALL -j KUBE-MARK-DROP
# 对于被匹配到 KUBE-FIREWALL 的流量，将会被标记为 0x8000/0x8000 进行丢弃。
-A KUBE-LOAD-BALANCER -j KUBE-MARK-MASQ
# 对于需要进行负载均衡的流量，将会被标记为 0x4000/0x4000 进行地址伪装。
-A KUBE-MARK-DROP -j MARK --set-xmark 0x8000/0x8000
# 对于需要被丢弃的流量，将会被标记为 0x8000/0x8000 然后直接丢弃。
-A KUBE-MARK-MASQ -j MARK --set-xmark 0x4000/0x4000
# 对于需要进行地址伪装的流量，将会被标记为 0x4000/0x4000 进行地址伪装。
-A KUBE-NODE-PORT -p tcp -m comment --comment "Kubernetes nodeport TCP port for masquerade purpose" -m set --match-set KUBE-NODE-PORT-TCP dst -j KUBE-MARK-MASQ
# 对于需要进行负载均衡的 TCP 流量，将会匹配到 Kubernetes 节点的端口上，并进行地址伪装。
-A KUBE-POSTROUTING -m mark ! --mark 0x4000/0x4000 -j RETURN
# 对于没有匹配到前面规则的流量，将会直接返回。
-A KUBE-POSTROUTING -j MARK --set-xmark 0x4000/0x0
# 对于需要进行地址伪装的流量，将会被标记为 0x4000/0x0 进行地址伪装。
-A KUBE-POSTROUTING -m comment --comment "kubernetes service traffic requiring SNAT" -j MASQUERADE --random-fully
# 对于需要进行 Kubernetes 服务的 SNAT 处理的流量，将会进行地址伪装。
-A KUBE-SERVICES ! -s 100.64.64.0/18 -m comment --comment "Kubernetes service cluster ip + port for masquerade purpose" -m set --match-set KUBE-CLUSTER-IP dst,dst -j KUBE-MARK-MASQ
# 对于需要进行地址伪装的流量，如果目标地址不属于 100.64.64.0/18 子网，则进行地址伪装和标记。
-A KUBE-SERVICES -m comment --comment "Kubernetes service external ip + port for masquerade and filter purpose" -m set --match-set KUBE-EXTERNAL-IP dst,dst -j KUBE-MARK-MASQ
# 对于需要进行地址伪装的、目标地址为本地 IP 的流量，将直接被接受（不需要进行地址伪装）。
-A KUBE-SERVICES -m comment --comment "Kubernetes service external ip + port for masquerade and filter purpose" -m set --match-set KUBE-EXTERNAL-IP dst,dst -m physdev ! --physdev-is-in -m addrtype ! --src-type LOCAL -j ACCEPT
# 对于需要进行地址伪装的、目标地址为本地节点的 Kubernetes 服务流量，将会匹配到 Kubernetes 节点的端口上进行处理。
-A KUBE-SERVICES -m comment --comment "Kubernetes service external ip + port for masquerade and filter purpose" -m set --match-set KUBE-EXTERNAL-IP dst,dst -m addrtype --dst-type LOCAL -j ACCEPT
# 对于需要进行地址伪装的、目标地址为 Kubernetes 服务的流量，并且流量的目标地址属于当前集群，则直接接受（不需要进行地址伪装）。
-A KUBE-SERVICES -m addrtype --dst-type LOCAL -j KUBE-NODE-PORT
# 如果流量的目标地址为本地地址，则需要匹配到 Kubernetes 节点的端口上进行处理。这里的本地地址指的是本地主机上的 IP 地址。
-A KUBE-SERVICES -m set --match-set KUBE-CLUSTER-IP dst,dst -j ACCEPT
# 如果流量的目标地址为 Kubernetes 服务的集群 IP 地址，则直接接受该流量，不需要进行地址伪装。这里的集群 IP 地址是指由 Kubernetes 控制平面分配给服务的虚拟 IP 地址。
```
