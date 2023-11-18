---
layout:     post
title:      "使用 Hubble 实现 Kubernetes 服务可观测性（3）"
subtitle:   "Hubble 是一个用于云原生工作负载的完全分布式网络和安全可观察性平台。它建立在 Cilium 和 eBPF 之上，以完全透明的方式深入了解服务的通信和行为以及网络基础设施"
description: "Hubble - 使用 eBPF 的 Kubernetes 的网络、服务和安全可观测性。Hubble 则是 Cilium 的一个子项目，专注于提供网络可观察性。Hubble 可以收集和可视化 Cilium 网络的流量信息，帮助用户理解网络流量的模式，检测网络问题，理解应用的行为。Hubble 提供了一个丰富的可视化界面，可以显示网络流量的详细信息，包括源 IP、目标 IP、端口号、协议类型、数据包数量、字节数量等。"
author: "陈谭军"
date: 2023-10-14
published: true
tags:
    - kubernetes
    - hubble
    - eBPF
    - cilium
categories:
    - TECHNOLOGY
showtoc: true
---

# 介绍

Hubble - 使用 eBPF 的 Kubernetes 的网络、服务和安全可观测性。Hubble 则是 Cilium 的一个子项目，专注于提供网络可观察性。Hubble 可以收集和可视化 Cilium 网络的流量信息，帮助用户理解网络流量的模式，检测网络问题，理解应用的行为。Hubble 提供了一个丰富的可视化界面，可以显示网络流量的详细信息，包括源 IP、目标 IP、端口号、协议类型、数据包数量、字节数量等。

Hubble 是一个用于云原生工作负载的完全分布式网络和安全可观察性平台。它建立在 Cilium 和 eBPF 之上，以完全透明的方式深入了解服务的通信和行为以及网络基础设施。Hubble 通常可以解决下述问题，如下所示：
* 服务依赖关系和通信 Map
  * 哪些服务正在相互通信？多久一次？服务依赖关系图是什么样子的？
  * 正在进行哪些 HTTP 调用？
* 监控和告警
  * 是否有网络通信故障？为什么通信失败？是 DNS 吗？是应用程序问题还是网络问题？是4层（TCP）还是7层（HTTP）的通信中断？
  * 哪些服务在过去5分钟内遇到 DNS 解析问题？哪些服务最近经历了 TCP 连接中断或连接超时？未应答 TCP SYN 请求的速率是多少？
* 应用程序监控
  * 特定服务或所有集群的 5xx 或 4xx HTTP 响应代码的速率是多少？
  * HTTP 请求和响应之间的第 95 个百分比和第 99 个百分比的延迟是多少？哪些服务表现最差？两个服务之间的延迟是多少？
* 安全可观察性
  * 由于网络策略，哪些服务的连接被阻止？从集群外部访问了哪些服务？哪些服务解析了特定的DNS名称？


# 架构

官方地址，参见 [https://github.com/cilium/hubble](https://github.com/cilium/hubble)。使用 eBPF 实现 Kubernetes 网络、服务、安全等可观测性。
架构图如下所示：

![](/images/2023-10-14-cilium-hubble/1.png)


Hubble 是 Cilium 的一个组件，其核心功能主要包括： 
* 实时网络流量监控： Hubble 可以提供对容器网络流量的实时监控和分析，让用户能够了解容器之间的通信模式、流量和流向等信息。
* 网络可视化： 它能够以可视化的方式展现容器之间的网络拓扑，使用户能够更直观地理解整个容器网络的结构和连接方式。
* 安全审计： Hubble 可以帮助进行网络流量的审计和分析，有助于发现异常行为或潜在的安全威胁，并提供相应的数据支持进行故障排除或安全加固。
* 服务发现和定位： 它可以帮助发现容器之间的服务，并提供这些服务的定位信息，有助于在容器化环境中进行服务间通信和定位。

总的来说，Hubble 作为 Cilium 的一部分，提供了强大的网络可见性和安全性功能，有助于理解、监控和保护容器化环境中的网络通信。

# 示例

服务拓扑图如下所示：
![](/images/2023-10-14-cilium-hubble/2.png)

指标和监控提供了系统状态，示例如下所示：

网络：
![](/images/2023-10-14-cilium-hubble/3.png)

可观测性：
![](/images/2023-10-14-cilium-hubble/4.png)

HTTP Request/Response Rate & Latency：
![](/images/2023-10-14-cilium-hubble/5.png)

DNS Request/Response Monitoring：
![](/images/2023-10-14-cilium-hubble/6.png)

# 安装

安装 Cilium 参考示例如下所示：

```bash
helm repo add cilium https://helm.cilium.io/

helm install cilium cilium/cilium --version 1.14.0 \
    --namespace kube-system \
    --set kubeProxyReplacement=strict \
    --set-string extraConfig.enable-envoy-config=true  \
	# k8sServiceHost 表示 k8s apiServer 地址
    --set k8sServiceHost=xxx  \ 
    --set k8sServicePort=6443  \
    --set envoy.enabled=true  \
    --set hubble.relay.enabled=true \
    --set hubble.ui.enabled=false \
    --set prometheus.enabled=true  \
    --set operator.prometheus.enabled=true \
	# 镜像仓库地址
    --set image.repository=repo/cilium  \
    --set image.tag=v1.14.0 \
    --set image.useDigest=false \
	# 镜像仓库地址
    --set operator.image.repository=repo/operator \
    --set operator.image.tag=v1.14.0 \
    --set operator.image.useDigest=false   \
	# 镜像仓库地址
    --set envoy.image.repository=repo/cilium-envoy  \
    --set envoy.image.tag=v1.25.9   \
    --set envoy.image.useDigest=false \
	# 镜像仓库地址
    --set hubble.relay.image.repository=repo/hubble-relay  \
    --set hubble.relay.image.tag=v1.14.0  \
    --set hubble.relay.image.useDigest=false
```

# 参考

1. https://github.com/cilium/hubble
2. https://docs.cilium.io/en/stable/contributing/development/hubble/#hubble-contributing
