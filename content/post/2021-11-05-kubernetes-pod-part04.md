---
layout:     post
title:      "Kubernetes 中数据包的生命周期 Ingress 等处理七层流量（Part4）"
subtitle:   "本文我们将讨论 Kubernetes 的 Ingress 资源和 Ingress 控制器。Ingress 控制器是一个控制器，它监视 Kubernetes API 服务器上 Ingress 资源的更新，并相应地重新配置 Ingress 负载均衡器。"
description: "本文我们将讨论 Kubernetes 的 Ingress 资源和 Ingress 控制器。Ingress 控制器是一个控制器，它监视 Kubernetes API 服务器上 Ingress 资源的更新，并相应地重新配置 Ingress 负载均衡器。"
author: "陈谭军"
date: 2021-11-05
published: true
tags:
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

最近在深入学习 Kubernetes 基础知识，通过追踪 HTTP 请求到达 Kubernetes 集群上的服务过程来深入学习 Kubernetes 实现原理。希望下列文章能够对我们熟悉 Kubernetes 有一定的帮助。

* [Linux 网络、Namespace 与容器网络 CNI 基础知识](https://tanjunchen.github.io/post/2021-10-22-kubernetes-pod-part01/)
* [Kubernetes CNI 大利器 - Calico](https://tanjunchen.github.io/post/2021-10-29-kubernetes-pod-part02/)
* [Kubernetes 流量核心组件 - kube-proxy](https://tanjunchen.github.io/post/2021-10-15-kubernetes-pod-part03/)
* [Kubernetes 使用 Ingress 处理七层流量](https://tanjunchen.github.io/post/2021-11-05-kubernetes-pod-part04/)


本文我们将讨论 Kubernetes 的 Ingress 资源和 Ingress 控制器。Ingress 控制器是一个控制器，它监视 Kubernetes API 服务器上 Ingress 资源的更新，并相应地重新配置 Ingress 负载均衡器。

# Nginx Controller 与 LoadBalancer/Proxy

Ingress Controller 通常是一个在 Kubernetes 集群中作为 Pod 运行的应用程序，它根据 Ingress 资源配置负载均衡器。负载均衡器可以是运行在集群中的软件负载均衡器，也可以是外部运行的硬件或云负载均衡器，不同的负载均衡器需要不同的 Ingress 控制器。

![](/images/2021-11-05-kubernetes-pod-part04/1.png)

Ingress 的基本原则是提供一种描述更高层次流量管理约束的方法，特别是针对 HTTP(S)。通过 Ingress，我们可以定义路由流量的规则，而不需要创建大量的负载均衡器或在每个节点上暴露每个服务。它可以配置为为服务提供外部可访问的 URL、负载均衡流量、终止 SSL/TLS，并提供基于名称的虚拟主机和基于内容的路由功能。

# 配置选项

Kubernetes Ingress 控制器使用 Ingress 类来筛选 Kubernetes Ingress 对象和其他资源，然后将它们转换为配置。这使得它可以与其他 Ingress 控制器和/或同一集群中其他部署的 Kubernetes Ingress 控制器共存：Kubernetes Ingress 控制器只会处理标记为其使用的配置。

## 基于前缀 Prefix

```bash
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: prefix-based
  annotations:
    kubernetes.io/ingress.class: "nginx-ingress-inst-1"
spec:
  rules:
  - http:
      paths:
      - path: /video
        pathType: Prefix
        backend:
          service:
            name: video
            port:
              number: 80
      - path: /store
        pathType: Prefix
        backend:
          service:
            name: store
            port:
              number: 80
```

## 基于 Host

```bash
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: host-based
  annotations:
    kubernetes.io/ingress.class: "nginx-ingress-inst-1"
spec:
  rules:
  - host: "video.example.com"
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: video
            port:
              number: 80
  - host: "store.example.com"
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: store
            port:
              number: 80
```

## 基于 Host 与 Prefix

```bash
apiVersion: extensions/v1beta1
kind: Ingress
metadata:
  name: host-prefix-based
  annotations:
    kubernetes.io/ingress.class: "nginx-ingress-inst-1"
spec:
  rules:
  - host: foo.com
    http:
      paths:
      - backend:
          serviceName: foovideo
          servicePort: 80
        path: /video
      - backend:
          serviceName: foostore
          servicePort: 80
        path: /store
  - host: bar.com
    http:
      paths:
      - backend:
          serviceName: barvideo
          servicePort: 80
        path: /video
      - backend:
          serviceName: barstore
          servicePort: 80
        path: /store
```

Ingress 是 Kubernetes 中的一个内置 API，但没有内置控制器，因此需要一个 Ingress 控制器来实际实现 Ingress API。目前有许多不同的 Ingress 控制器，常见的有 Nginx 和 Contour。

Ingress 由一个 Ingress API 对象和一个 Ingress 控制器组成。如前所述，Kubernetes Ingress 是一个 API 对象，用于描述暴露到 Kubernetes 集群的服务的期望状态。因此，为了使其作为一个 Ingress 控制器工作，需要实际实现 Ingress API 来读取和处理 Ingress 资源的信息。由于 Ingress API 本质上只是元数据，实际的工作由 Ingress 控制器承担。市面上有多种 Ingress 控制器，选择合适的控制器对于每个使用场景非常重要。

此外，在同一集群中可以有多个 Ingress 控制器，并且可以为每个 Ingress 设置所需的控制器。通常，我们会在同一个集群中针对不同的场景使用这些控制器的组合。例如，我们可能会使用一个控制器来处理进入集群的外部流量，该控制器绑定了 SSL 证书，而另一个控制器则用于处理集群内部的流量，并且没有 SSL 绑定。

# 部署选项

## Contour + Envoy

Contour Ingress 控制器是一个由以下两个组件协作组成的解决方案：
* Envoy：提供高性能的反向代理。
* Contour：作为 Envoy 的管理服务器，并为其提供配置。

这两个容器是分别部署的，Contour 作为一个 Deployment，Envoy 作为一个 DaemonSet。Contour 是 Kubernetes API 的客户端，它监视 Ingress、HTTPProxy、Secret、Service 和 Endpoint 对象，并通过将这些对象的缓存转化为相应的 JSON 配置段（如：Service 对象用于 CDS、Ingress 用于 RDS、Endpoint 对象用于 EDS 等），来充当 Envoy 的管理服务器。

以下示例展示了启用主机网络的 EnvoyProxy（监听地址为 0.0.0.0:80）。

![](/images/2021-11-05-kubernetes-pod-part04/2.png)

## Nginx

Nginx Ingress 控制器的目标是生成一个配置文件（nginx.conf）。这一要求的主要影响是每次配置文件发生变化时，都需要重新加载 NGINX。需要注意的是，对于仅影响上游配置（例如，当你部署应用时，Endpoints 发生变化）的更改，我们并不会重新加载 Nginx。为了实现这一点，我们使用了 [lua-nginx-module](https://github.com/openresty/lua-nginx-module)。

每当 Endpoints 发生变化时，控制器会从它所看到的所有服务中获取 Endpoints，并生成相应的 Backend 对象。然后，它将这些对象发送给在 Nginx 中运行的 Lua 处理程序。Lua 代码会将这些后端存储在共享内存区域中。接着，每当有请求时，运行在 [balancer_by_lua](https://github.com/openresty/lua-resty-core/blob/master/lib/ngx/balancer.md) 上下文中的 Lua 代码会检测应从哪些 Endpoints 选择上游节点，并应用配置的负载均衡算法来选择合适的节点。随后，Nginx 会处理其余的请求。这种方式避免了在 Endpoint 发生变化时重新加载 Nginx。在一个相对较大的集群中，应用频繁部署时，这一特性可以显著减少 Nginx 重新加载次数，从而避免影响响应延迟、负载均衡质量（每次重新加载时，Nginx 会重置负载均衡的状态）等问题。

## Nginx + Keepalived — 高可用部署

keepalived 守护进程可以用于监控服务或系统，并在发生问题时自动切换到备用节点。我们配置一个浮动 IP 地址，该地址可以在工作节点之间移动。如果某个工作节点宕机，浮动 IP 会自动迁移到另一个工作节点，从而允许 Nginx 绑定到新的 IP 地址。

这种配置通过使用 keepalived 实现了 Nginx 的高可用性，当某个节点出现故障时，Nginx 能够继续服务，避免单点故障影响整个系统。

![](/images/2021-11-05-kubernetes-pod-part04/3.png)

## MetalLB — Nginx with LoadBalancer Service (适用于具有小型公共 IP 地址池的私有集群)

MetalLB 将 Kubernetes 集群与网络负载均衡器功能连接起来。简单来说，它允许在没有云提供商支持的集群中创建类型为“LoadBalancer”的 Kubernetes 服务。在启用了云平台的 Kubernetes 集群中，可以请求负载均衡器，云平台会分配一个 IP 地址；而在裸金属集群中，MetalLB 负责此分配。一旦 MetalLB 为服务分配了外部 IP 地址，它需要确保集群外的网络知道该 IP 地址“存在”于集群中。为此，MetalLB 使用标准路由协议来实现这一目标：[ARP](https://en.wikipedia.org/wiki/Address_Resolution_Protocol)、[NDP](https://en.wikipedia.org/wiki/Neighbor_Discovery_Protocol) 或 [BGP](https://en.wikipedia.org/wiki/Border_Gateway_Protocol)。

* 在 Layer 2 模式下，集群中的一台机器负责服务，并使用标准的地址发现协议（对于 IPv4 使用 ARP，IPv6 使用 NDP）使这些 IP 在本地网络中可达。从局域网的角度来看，发布这些 IP 地址的机器看起来拥有多个 IP 地址。
* 在 BGP 模式下，集群中的所有机器与控制的附近路由器建立 BGP 对等会话，并告知这些路由器如何将流量转发到服务 IP。使用 BGP 可以实现跨多个节点的真正负载均衡，并通过 BGP 的策略机制提供精细的流量控制。

MetalLB Pods：
* controller：集群范围内的 MetalLB 控制器，负责 IP 分配（以 Deployment 方式部署）。
* speaker：每个节点的守护进程，使用不同的广告策略将已分配 IP 的服务进行广告宣传（以 DaemonSet 方式部署）。

通过 MetalLB，Kubernetes 集群可以在没有云服务的情况下提供类似云负载均衡器的功能，使得私有集群也能享受到高效的服务暴露和流量管理。

![](/images/2021-11-05-kubernetes-pod-part04/4.png)

注意：MetalLB 可以通过将服务类型定义为“LoadBalancer”来供集群中的任何服务使用，但实际上，获取一个大的公共 IP 地址池来与 MetalLB 一起使用并不实际。

# 参考

1. https://kubernetes.io/docs/concepts/services-networking/ingress/
2. https://www.nginx.com/products/nginx-ingress-controller/
3. https://www.keepalived.org/
4. https://www.envoyproxy.io/
5. https://projectcontour.io/
6. https://metallb.universe.tf/
