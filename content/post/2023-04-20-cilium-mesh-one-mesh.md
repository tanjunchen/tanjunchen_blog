---
layout:     post
title:      "译文：Cilium Mesh - Mesh 连接所有应用"
subtitle:   "简单介绍 Cilium Mesh，什么是 Cilium Mesh、为什么使用 Cilium Mesh、如何配置 Cilium Mesh？"
description: "我们有令人兴奋的消息要和大家分享。由于其先进的安全性、性能和卓越的可扩展性，Cilium 已迅速成为 Kubernetes 容器网络的标准。随着 Cilium 的使用率不断提高，越来越多的客户要求提供 Cilium 功能。"
author: "陈谭军"
date: 2023-04-20
#image: "/img"
published: true
tags:
    - ebpf
    - kubernetes
    - cilium mesh
    - cilium
categories:
    - TECHNOLOGY
showtoc: true
---

![](/images/2023-04-20-cilium-mesh-one-mesh/1.png)

我们有令人兴奋的消息要和大家分享。由于其先进的安全性、性能和卓越的可扩展性，Cilium 已迅速成为 Kubernetes 容器网络的标准。随着 Cilium 的使用率不断提高，越来越多的客户要求提供 Cilium 功能。

今天，我们很高兴地给大家介绍 Cilium Mesh。Cilium Mesh 连接在云、本地或边缘运行的 Kubernetes 工作负载、虚拟机和物理服务器。Cilium Mesh 建立在强大的 Kubernetes 网络基础之上，具有基于身份的安全性和可观察性，并将其与高度可扩展的多集群控制平面 Cilium Cluster Mesh 相结合。一个新的中转网关，可以作为虚拟设备部署到任何网络中，以将现有网络中的工作负载与 Kubernetes 或其他中转网关后面的工作负载连接起来。

# 什么是 Cilium Mesh

Cilium Mesh 是一个新的通用网络层，通常用于跨云、本地和边缘连接工作负载和机器。它由 Kubernetes 网络组件（CNI）、多集群连接平面（Cluster Mesh）和连接现有网络的中转网关 Gateway 组成，如下所示：
![](/images/2023-04-20-cilium-mesh-one-mesh/2.png)

Cilium Mesh 将所有现有的 Cilium 组件组合成一个功能性网格，用于跨云、本地和边缘连接工作负载，组件如下所示：
* Kubernetes Networking (CNI)：Cilium 的 CNI 插件可以在任何 Kubernetes Worker 节点上运行，并且与在云端、本地和边缘运行的 Kubernetes 兼容。富含 Cilium 的 Kubernetes 节点会自动获得与所有其他 Kubernetes 节点以及网格中任何网关的连接。
* Cluster Mesh：Cluster Mesh充当控制平面，并提供将多个集群网格化在一起的能力。它提供跨所有集群的网络安全、加密、服务发现、负载平衡和可观察性服务的功能。
* Ingress & Egress Gateway：Cilium 的入口和出口功能与 Cilium Mesh 兼容。富含 Cilium 的 Kubernetes 节点可以充当外部流量进入网格的入口或网关 API 节点。同样，Cilium 丰富的 Kubernetes 节点可以充当流量的出口网关，通过特定节点和定义的源 IP 地址离开网格。
* Service Mesh：所有 Cilium 节点和网关都能够执行 L7 功能，以提供服务网格功能，包括 L7 负载平衡、Canary Rollouts、mTLS (Cilium 1.14) 和 Tracing。可以使用以下 API 配置服务网格功能：Ingress、Gateway API、Kubernetes Services 和 Envoy CRD。

# 为什么使用 Cilium Mesh

Cilium Mesh 旨在扩展基于 Cilium 的网络和安全性的使用范围。Cilium 的数据路径始终是通用的，适用于 Kubernetes 之外的用例。事实上，一些用户已经在 OpenStack 等环境中使用 Cilium 作为纯 vSwitch。借助 Cilium Mesh，我们正式将 Cilium 的范围扩展到 Kubernetes 之外，如下所示：
![](/images/2023-04-20-cilium-mesh-one-mesh/3.png)

Cilium Mesh 为多云和混合云网络带来了什么？将 Kubernetes 和云原生网络解决方案引入企业和云网络会带来以下优势：
* 现代零信任安全：分布式防火墙和微分段、透明加密以及基于 mTLS 的端到端身份验证构成了现代云原生安全原则，用于构建基于零信任的安全性。 Cilium Mesh 不仅可以在 Kubernetes 中建立这些安全原则，而且可以将它们扩展到现有的基础设施中。此外，基于 eBPF 的现代运行时安全层 Tetragon 通过网络和运行时的深度安全可观测数据丰富了 SIEM。
* 深度端到端可观测性：Cilium 的 Hubble 为网络可观测性和监控制定了新标准。借助 Cilium Mesh，基于 eBPF 的 Cilium 可观测性堆栈可在现有网络中使用。可观测性数据可使用 Prometheus 等现代标准获得，并且可以使用 Grafana 等强大工具进行可视化。仍根据需要支持 sFLo 和 NetFlow 等传统标准。
* 多云统一：所有主要云提供商都选择 Cilium 作为其至少一个托管 Kubernetes 平台网络标准。它是一种逻辑抽象，因此提供了跨所有云提供商和本地网络的可移植性。Cilium 符合开源标准，因此非常适合作为未来的基础网络层。
* 协同 DevOps 和 GitOps：Cilium Mesh 的各个方面都针对现代平台工程和 DevOps 团队进行了优化。所有组件都可以以完全自动化的方式部署，并且网格的所有方面都可以使用 API 进行配置。
* 控制平面具有可拓展性：现代 Cilium 控制平面是完全分布式的，专为容器工作负载而构建，可轻松水平扩展。

# 如何配置 Cilium Mesh？

对于熟悉 Cilium 的人来说，Cilium Mesh 是建立在其基础上的。它使用 Kubernetes API 作为其控制平面，该控制平面经过充分验证，为现代平台工程团队所熟悉，并为分布式控制平面提供了理想的属性。
支持中转网关（Ingress、Gateway等）的 API 仍在开发中。以下示例显示了如何通过中转网关暴露 Kubernetes 中运行的 nginx 的示例。之后，可以通过服务 VIP 或服务 DNS 名称访问该 pod：
```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
  annotations:
    io.cilium/global-service: "true"
    io.cilium/portal: "true"
spec:
  type: LoadBalancer
  ports:
  - port: 80
  selector:
    run: nginx
```
对 nginx 配置如下容器网络策略，只允许 client 是 good 的 pod 访问 nginx。
```yaml
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "l3-rule"
spec:
  endpointSelector:
    matchLabels:
      run: nginx
  ingress:
  - fromEndpoints:
    - matchLabels:
      client: good
```

# Cilium Mesh 可观测性

Cilium 提供了广泛的可观测性功能，如将可观测性数据流式传输到 Hubble UI、Prometheus 和 Grafana 以及大多数 SIEM。上述功能也可以扩展到 Cilium Mesh，提供跨云和本地基础设施的所有工作负载的可见性。
![](/images/2023-04-20-cilium-mesh-one-mesh/4.png)


# 参考

* [Join the Cilium Mesh AMA](https://isovalent.com/events/2023-05-17-cilium-mesh-ama/) – Thomas Graf 和 Martynas Pumputis 将介绍 Cilium Mesh 并回答所有问题
* [Cilium Mesh – One Mesh to Connect Them All](https://isovalent.com/blog/post/introducing-cilium-mesh/)
