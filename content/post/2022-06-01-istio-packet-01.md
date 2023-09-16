---
layout:     post
title:      "Istio 中数据包的生命周期 - 上篇"
subtitle:   "在本篇博客中，我们尝试跟踪 Istio 服务网格中的 HTTP 请求，深入理解 Istio Proxy 如何通过拦截流量来处理入站和出站流量。"
description: ""
author: "陈谭军"
date: 2022-06-01
published: true
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

如果你从事系统后端研发相关工作，“服务网格”一词你或许一定听说过。Istio 过往一直被批评为过于复杂，但今天的 Istio 更加简单易用。

在本篇博客中，我们尝试跟踪 Istio 服务网格中的 HTTP 请求，深入理解它如何通过拦截流量来处理入站和出站流量。

# 什么是 Service Mesh？

现代应用程序通常被设计为分布式微服务架构，每个微服务执行一些特定的业务功能。服务网格是一个专用的基础设施层，我们可以在应用程序中引入它。服务网格允许透明地添加可观察性、流量管理和安全性等功能，而无需将上述功能实现代码在自己的代码中实现。“service mesh” 描述了用于实现此功能的架构类型以及创建的安全或网络模型。

随着分布式服务部署（例如在基于 Kubernetes 的系统中）的规模和复杂性的增长，通常分布式功能（*服务发现、负载平衡、故障恢复、指标和监控*）可能会变得更难以实现和管理。服务网格可以解决上述问题，并且通常还可以解决更复杂的需求，例如 *A/B 测试、金丝雀部署、速率限制、访问控制、加解密、端到端身份验证*等。

# 什么是 Istio？

Istio 是一个开源服务网格，可以透明地分层到现有的分布式应用程序上。Istio 提供了一种统一且更有效的方式来保护、连接和监控服务的强大功能。 Istio 只需很少或无需更改服务代码就能实现负载平衡、服务间身份验证和监控。Istio 提供了完整的解决方案，通过提供对整个服务网格的行为洞察和操作控制来满足微服务应用程序的多样化需求，它在服务网络中统一提供许多重要功能，如下所示：
* 流量管理：控制服务之间的流量和 API 调用的流程，使调用更加可靠，使网络在面对复杂条件时更加健壮。
* 可观察性：了解服务之间的依赖关系以及它们之间的流量访问，从而能够快速识别问题。
* 策略增强：将组织策略应用于服务之间的交互，确保执行访问策略并在消费者之间公平分配资源。策略更改是通过配置网格来进行的，而不是通过更改应用程序代码来进行。
* 服务身份和安全性：为网格中的服务提供可验证的身份，并提供在服务流量流经不同可信度的网络时保护服务流量的能力。

# Istio 工作机制

Istio 有两个主要组件：数据平面和控制平面。
* 数据平面：数据平面或数据层由代理服务组成，这些代理服务表示为每个 Kubernetes pod 中的 sidecar 容器，使用扩展的 Envoy 代理。这些边车管理和控制微服务之间的所有网络通信，同时还收集和报告有用的遥测数据。
* 控制平面：控制平面或控制层由一个名为 istiod 的二进制文件组成，负责将高级路由规则和流量控制行为转换为 Envoy 特定的配置，然后在运行时将它们传送到 sidecar。此外，控制平面还提供安全措施，通过内置身份和凭证管理实现强大的服务到服务和最终用户身份验证，同时根据服务身份实施安全策略。

控制平面采用所需的配置及其服务视图，并对代理服务进行动态编程，并随着规则或环境的变化而更新它们。本文使用 Istio 官方文档中的 [BookInfo](https://istio.io/latest/docs/examples/bookinfo/?source=post_page) 应用程序作为示例来探索 Istio 中网络请求数据包生命周期。

## 没有 Istio 的流量路由

Kubernetes 服务可用于使用 Endpoint 轻松部署在一组 Pod 上的应用程序。服务跟踪 Pod 的 IP 地址和 DNS 名称的变化，并将它们作为单个 IP 或 DNS 暴露给最终用户，如下所示：

![](/images/2022-06-01-istio-packet-01/1.png)

## 使用 Istio 的流量路由

Envoy Proxy 作为 sidecar 部署到同一 Kubernetes pod 中的相关容器，sidecar 只是一个与应用程序容器运行在同一个 Pod 上的容器，流量都会通过 iptables 被劫持到 sidecar 容器，如下所示：

![](/images/2022-06-01-istio-packet-01/2.png)

## 注入 SideCar 

简单来说，sidecar 注入就是在 pod 模板中添加额外容器的配置，Istio 服务网格所需的添加容器是：istio-proxy (sideCar) ，istio-proxy 这是实际的 sidecar 代理（基于 Envoy），实例 Yaml 如下所示：
```yaml
    image: docker.io/istio/proxyv2:1.13.1
    imagePullPolicy: IfNotPresent
    name: istio-proxy
    ports:
    - containerPort: 15090
      name: http-envoy-prom
      protocol: TCP
    readinessProbe:
      failureThreshold: 30
      httpGet:
        path: /healthz/ready
        port: 15021
        scheme: HTTP
      initialDelaySeconds: 1
      periodSeconds: 2
      successThreshold: 1
      timeoutSeconds: 3
    resources:
      limits:
        cpu: "2"
        memory: 1Gi
      requests:
        cpu: 10m
        memory: 40Mi
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      privileged: false
      readOnlyRootFilesystem: true
      runAsGroup: 1337
      runAsNonRoot: true
      runAsUser: 1337
    terminationMessagePath: /dev/termination-log
    terminationMessagePolicy: File
    volumeMounts:
    - mountPath: /var/run/secrets/istio
      name: istiod-ca-cert
    - mountPath: /var/lib/istio/data
      name: istio-data
    - mountPath: /etc/istio/proxy
      name: istio-envoy
    - mountPath: /var/run/secrets/tokens
      name: istio-token
    - mountPath: /etc/istio/pod
      name: istio-podinfo
    - mountPath: /var/run/secrets/kubernetes.io/serviceaccount
      name: kube-api-access-nmjtq
      readOnly: true
```

istio-proxy 容器以用户 1337 的身份以受限权限运行。1337 由于这是为 istio-proxy 保留的，应用程序工作负载的 UID（用户 ID）必须不同，并且不能与 1337 冲突。1337 UID 是 Istio 团队任意选择的劫持流量重定向到 istio-proxy 容器。还可以看到在初始化 iptables 时，1337 被用作 istio-iptables 的参数。 由于 istio-proxy 容器与应用程序工作负载一起运行，Istio 还确保如果它受到漏洞威胁，它只能对根文件系统进行只读访问。

Istio Sidecar 注入主要分为自动注入与手动注入。  
在手动注入方式中，可以使用 [istioctl](https://istio.io/latest/docs/reference/commands/istioctl/) 修改 pod 模板，添加前面提到的两个容器的配置。对于手动和自动注入，Istio 都会从 istio-sidecar-injector 配置 (configmap) 和网格的 istio configmap 中获取配置。
```bash
istioctl kube-inject -f application.yaml | istioctl kube-inject -f application.yaml | kubectl -f
```

大多数时候不想在每次部署应用程序时使用 istioctl 命令手动注入 sidecar，而是希望 Istio 自动将 sidecar 注入到 pod 中。需要做的就是使用 istio-injection=enabled 标记要部署应用程序的命名空间，Istio 通过 Kubernetes Mutating Webhook 来注入 sidecar。
```bash
kubectl label namespace <namespaceName> istio-injection=enabled
```

以下是 Kubernetes Mutating Webhook 在 sidecar 注入中处理的过程：
1. 首先，在 Istio 安装过程中注入的 istio-sidecar-injector mutating 配置将包含所有 pod 信息的 webhook 请求发送到 istiod 控制器。
2. 其次，控制器在运行时修改 pod 模版，将 init 和 sidecar 容器代理引入到实际的 pod 模版规范中。
3. 然后，控制器将修改后的对象返回到 validation webhook 进行对象验证。
4. 最后，经过验证后，修改后的 pod 模版规范将与所有 sidecar 容器一起部署。
有关完整配置，使用命令 kubectl get mutatingwebhookconfiguration istio-sidecar-injector -o yaml 查看。

## iptables 管理

[init 容器](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/) 用于设置 iptables 规则，以便入站/出站流量被 sidecar 处理。init 容器与应用程序容器在以下方面有所不同：
* 它在应用程序容器启动之前运行，并且始终运行直到完成。
* 如果有许多 init 容器，则每个容器都应在启动下一个容器之前成功完成。

因此，可以看到这种类型的容器非常适合不需要成为实际应用程序容器一部分的设置或初始化作业。在这种情况下，istio-init 就是这样做的并设置 iptables 规则。
```yaml
  initContainers:
  - args:
    - istio-iptables
    - -p
    - "15001"
    - -z
    - "15006"
    - -u
    - "1337"
    - -m
    - REDIRECT
    - -i
    - '*'
    - -x
    - ""
    - -b
    - '*'
    - -d
    - 15090,15021,15020
    image: docker.io/istio/proxyv2:1.13.1
    imagePullPolicy: IfNotPresent
    name: istio-init
    resources:
      limits:
        cpu: "2"
        memory: 1Gi
      requests:
        cpu: 10m
        memory: 40Mi
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        add:
        - NET_ADMIN
        - NET_RAW
        drop:
        - ALL
      privileged: false
      readOnlyRootFilesystem: false
      runAsGroup: 0
      runAsNonRoot: false
      runAsUser: 0
    terminationMessagePath: /dev/termination-log
    terminationMessagePolicy: File
    volumeMounts:
    - mountPath: /var/run/secrets/kubernetes.io/serviceaccount
      name: kube-api-access-nmjtq
      readOnly: true

    - '*'
    - -d
    - 15090,15021,15020
    image: docker.io/istio/proxyv2:1.13.1
    imagePullPolicy: IfNotPresent
```

为了最大限度地减少漏洞攻击面，istio-init 容器中的 securityContext 表示该容器以 root 权限运行 (runAsUser: 0)，但除 NET_ADMIN 和 NET_RAW 功能外，所有 Linux 功能都不会被提供。这些功能为 istio-init init 容器提供了运行时权限来重写应用程序 pod 的 iptables。  
sidecar 代理如何劫持进出容器的入站和出站流量？ 它是通过 istio-init 容器命令创建的 iptable 规则来完成的，如下所示：
```bash
*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:ISTIO_INBOUND - [0:0]
:ISTIO_IN_REDIRECT - [0:0]
:ISTIO_OUTPUT - [0:0]
:ISTIO_REDIRECT - [0:0]
-A PREROUTING -p tcp -j ISTIO_INBOUND
-A OUTPUT -p tcp -j ISTIO_OUTPUT
-A ISTIO_INBOUND -p tcp -m tcp --dport 15008 -j RETURN
-A ISTIO_INBOUND -p tcp -m tcp --dport 15090 -j RETURN
-A ISTIO_INBOUND -p tcp -m tcp --dport 15021 -j RETURN
-A ISTIO_INBOUND -p tcp -m tcp --dport 15020 -j RETURN
-A ISTIO_INBOUND -p tcp -j ISTIO_IN_REDIRECT
-A ISTIO_IN_REDIRECT -p tcp -j REDIRECT --to-ports 15006
-A ISTIO_OUTPUT -s 127.0.0.6/32 -o lo -j RETURN
-A ISTIO_OUTPUT ! -d 127.0.0.1/32 -o lo -m owner --uid-owner 1337 -j ISTIO_IN_REDIRECT
-A ISTIO_OUTPUT -o lo -m owner ! --uid-owner 1337 -j RETURN
-A ISTIO_OUTPUT -m owner --uid-owner 1337 -j RETURN
-A ISTIO_OUTPUT ! -d 127.0.0.1/32 -o lo -m owner --gid-owner 1337 -j ISTIO_IN_REDIRECT
-A ISTIO_OUTPUT -o lo -m owner ! --gid-owner 1337 -j RETURN
-A ISTIO_OUTPUT -m owner --gid-owner 1337 -j RETURN
-A ISTIO_OUTPUT -d 127.0.0.1/32 -j RETURN
-A ISTIO_OUTPUT -j ISTIO_REDIRECT
-A ISTIO_REDIRECT -p tcp -j REDIRECT --to-ports 15001
COMMIT
```

## 流量劫持 - Inbound

从 Pod 发送或接收的 TCP 请求将被 iptables 劫持。入站流量被劫持后，经过 Inbound 处理后转发到应用容器进行处理，如下所示：

![](/images/2022-06-01-istio-packet-01/3.png)

在 1.10 版本之前的 Istio 中，Envoy 代理与应用程序在同一 pod 中运行，绑定到 eth0 网络设备并将所有入站流量重定向到 lo 网络设备。这有两个重要的不足之处，与标准 Kubernetes 不同：
* 仅绑定到 lo 的应用程序将接收来自其他 Pod 的流量，否则这是不允许的。
* 仅绑定到 eth0 的应用程序将不会接收流量。

绑定到两个网络设备（这是通用的）的应用程序不会受到影响。   
从 Istio 1.10 开始，网络行为发生了变化，与 Kubernetes 中存在的标准行为保持一致，如下所示：

![](/images/2022-06-01-istio-packet-01/4.png)

我们可以看到代理不再将流量重定向到 lo 网络设备，而是将其转发到 eth0 上的应用程序。因此，保留了 Kubernetes 的标准行为，但我们仍然获得了 Istio 的所有好处。这一变化使 Istio 更接近其目标，即成为一个可与[零配置](https://istio.io/latest/blog/2021/zero-config-istio/) 的现有工作负载一起使用的透明代理。此外，它还避免了仅绑定到 lo 的应用程序的问题。

## 流量劫持 - Outbound

出站流量被 iptables 劫持，然后转发到 istio-proxy Outbound 进行处理。在 Istio 1.10 版本之前，处理流程如下所示：

![](/images/2022-06-01-istio-packet-01/5.png)

在 Istio 1.10 版本之后，处理流程如下所示：

![](/images/2022-06-01-istio-packet-01/6.png)

以下是处理入站和出站流量路由的 iptables 表规则。
```bash
$ sudo -i
# docker top `docker ps|grep "istio-proxy_productpage"|cut -d " " -f1`
UID                 PID                 PPID                C                   STIME               TTY                 TIME                CMD
1337                8150                8104                0                   Mar05               ?                   00:00:13            /usr/local/bin/pilot-agent proxy sidecar --domain default.svc.cluster.local --proxyLogLevel=warning --proxyComponentLogLevel=misc:error --log_output_level=default:info --concurrency 2
1337                8389                8150                0                   Mar05               ?                   00:00:57            /usr/local/bin/envoy -c etc/istio/proxy/envoy-rev0.json --restart-epoch 0 --drain-time-s 45 --drain-strategy immediate --parent-shutdown-time-s 60 --local-address-ip-version v4 --file-flush-interval-msec 1000 --disable-hot-restart --log-format %Y-%m-%dT%T.%fZ.%l.envoy %n.%v -l warning --component-log-level misc:error --concurrency 2
# nsenter -n --target 8389 
# iptables -t nat -L -v
Chain PREROUTING (policy ACCEPT 10167 packets, 610K bytes)
 pkts bytes target     prot opt in     out     source               destination         
10167  610K ISTIO_INBOUND  tcp  --  any    any     anywhere             anywhere            

Chain INPUT (policy ACCEPT 10167 packets, 610K bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain OUTPUT (policy ACCEPT 841 packets, 74888 bytes)
 pkts bytes target     prot opt in     out     source               destination         
   41  2460 ISTIO_OUTPUT  tcp  --  any    any     anywhere             anywhere            

Chain POSTROUTING (policy ACCEPT 841 packets, 74888 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain ISTIO_INBOUND (1 references)
 pkts bytes target     prot opt in     out     source               destination         
    0     0 RETURN     tcp  --  any    any     anywhere             anywhere             tcp dpt:15008
    0     0 RETURN     tcp  --  any    any     anywhere             anywhere             tcp dpt:15090
10158  609K RETURN     tcp  --  any    any     anywhere             anywhere             tcp dpt:15021
    9   540 RETURN     tcp  --  any    any     anywhere             anywhere             tcp dpt:15020
    0     0 ISTIO_IN_REDIRECT  tcp  --  any    any     anywhere             anywhere            

Chain ISTIO_IN_REDIRECT (3 references)
 pkts bytes target     prot opt in     out     source               destination         
    0     0 REDIRECT   tcp  --  any    any     anywhere             anywhere             redir ports 15006

Chain ISTIO_OUTPUT (1 references)
 pkts bytes target     prot opt in     out     source               destination         
    0     0 RETURN     all  --  any    lo      127.0.0.6            anywhere            
    0     0 ISTIO_IN_REDIRECT  all  --  any    lo      anywhere            !localhost            owner UID match 1337
    0     0 RETURN     all  --  any    lo      anywhere             anywhere             ! owner UID match 1337
   41  2460 RETURN     all  --  any    any     anywhere             anywhere             owner UID match 1337
    0     0 ISTIO_IN_REDIRECT  all  --  any    lo      anywhere            !localhost            owner GID match 1337
    0     0 RETURN     all  --  any    lo      anywhere             anywhere             ! owner GID match 1337
    0     0 RETURN     all  --  any    any     anywhere             anywhere             owner GID match 1337
    0     0 RETURN     all  --  any    any     anywhere             localhost           
    0     0 ISTIO_REDIRECT  all  --  any    any     anywhere             anywhere            

Chain ISTIO_REDIRECT (1 references)
 pkts bytes target     prot opt in     out     source               destination         
    0     0 REDIRECT   tcp  --  any    any     anywhere             anywhere             redir ports 15001

# iptables -t filter -L -v
Chain INPUT (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain FORWARD (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain OUTPUT (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

# iptables -t mangle -L -v
Chain PREROUTING (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain INPUT (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain FORWARD (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain OUTPUT (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination         

Chain POSTROUTING (policy ACCEPT 0 packets, 0 bytes)
 pkts bytes target     prot opt in     out     source               destination   
```

![](/images/2022-06-01-istio-packet-01/7.png)

Outbound 流量处理过程如下所示：
1. Product Page 服务向 reviews 服务发送请求，被 netfilter 拦截并转发到出口流量 OUTPUT 链
1. OUTPUT 链将流量转发到 ISTIO_OUTPUT 链
1. 发送非 localhost 请求并且是 istio 代理用户空间的流量被转发到 ISTIO_REDIRECT 链
1. ISTIO_REDIRECT 链直接重定向到 envoy 监控的 15001 出口流量端口
1. 经过一系列出口流量治理动作后，Envoy 继续发送响应数据，这些数据将被 netfilter 拦截并转发到出口流量 OUTPUT 链
1. OUTPUT 链将流量转发到 ISTIO_OUTPUT 链
1. 流量直接返回到 POSTROUTING，然后到达 Reviews 服务。

Inbound 流量处理过程如下所示：
1. Product Page 服务向 reviews 服务发送 TCP 连接请求
1. 请求进入 reviews 服务所在的 Pod 内核空间，被 netfilter 拦截，经过 PREROUTING 链，然后转发到 ISTIO_INBOUND 链
1. ISTIO_INBOUND 链由此规则定义 ISTIO_INBOUND -p tcp -j ISTIO_IN_REDIRECT 拦截并转发到 ISTIO_IN_REDIRECT
1. ISTIO_IN_REDIRECT 链直接重定向到 Envoy 监控的 15006 入口流量端口。
1. 经过一系列入站流量治理操作后，发送 TCP 连接请求来校验服务。此步骤属于 Envoy 的出站流量，将被 netfilter 拦截并转发到出站流量 OUTPUT 链
1. OUTPUT 链将流量转发到 ISTIO_OUTPUT 链
1. 目的地为 localhost，无法匹配到转发规则链，直接返回到下一个链。
1. sidecar 的请求到达 reviews 服务 9080 端口

# 参考

1. https://istio.io/
1. https://www.solo.io/blog/
1. https://istio.io/latest/blog/
1. https://github.com/istio
1. https://github.com/istio/istio/wiki/Design-Doc-Links
1. https://github.com/istio/old_pilot_repo/blob/master/doc/design.md
1. https://dramasamy.medium.com/life-of-a-packet-in-istio-part-1-8221971d77de
