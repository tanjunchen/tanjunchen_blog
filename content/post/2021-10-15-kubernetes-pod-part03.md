---
layout:     post
title:      "Kubernetes 中数据包的生命周期 Kube-Proxy（Part3）"
subtitle:   "本文我们将讨论 Kubernetes 的 kube-proxy 角色以及它如何使用 iptables 来控制流量。"
description: "主要内容如下所示：iptables 规则、Pod 到 Pod、Pod 到 External、Pod 到 Service、External Traffic Policy、Kube-Proxy等"
author: "陈谭军"
date: 2021-10-15
published: true
tags:
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

最近在深入学习 Kubernetes 基础知识，通过追踪 HTTP 请求到达 Kubernetes 集群上的服务过程来深入学习 Kubernetes 实现原理。
希望下列文章能够对我们熟悉 Kubernetes 有一定的帮助。
* Linux 网络、Namespace 与容器网络 CNI 基础知识
* Kubernetes CNI 大利器 - Calico
* [Kubernetes 流量核心组件 - kube-proxy](https://tanjunchen.github.io/post/2021-10-15-kubernetes-pod-part03/)
* Kubernetes 使用 Ingress 处理七层流量

本文我们将讨论 Kubernetes 的 kube-proxy 角色以及它如何使用 iptables 来控制流量。主要内容如下所示：
* iptables 规则
* Pod 到 Pod
* Pod 到 External
* Pod 到 Service
* External Traffic Policy
* Kube-Proxy

# Iptables 规则

在 Linux 操作系统中，防火墙功能由 netfilter 负责。Netfilter 是一个内核模块，用于决定哪些数据包可以进入或出去。而 iptables只是 netfilter 的接口。
这两者经常被认为是同一件事，但更好的角度是将其视为后端（netfilter）和前端（iptables）。

## chains

每一条链都负责一个特定的任务：
* PREROUTING：数据包一旦到达网络接口会发生什么。我们有几种不同的选择，例如修改数据包（可能用于 NAT），丢弃数据包，或者什么都不做，让数据包在后续的处理过程中被处理。
* INPUT：这是一条非常常见的链，因为它几乎总是包含严格的规则，以防止互联网上的恶意攻击者对我们的计算机造成伤害。
* FORWARD：负责数据包的转发。也就是说，我们可能想把一台计算机当作路由器，这里就可能需要应用一些规则来完成这项任务。
* OUTPUT：这条链负责所有网页浏览等操作。没有这条链的允许，你无法发送任何数据包。你有很多选择，比如是否允许一个端口进行通信。
* POSTROUTING：在数据包离开我们的计算机之前，这是数据包最后留下痕迹的地方。

![](/images/2021-10-15-kubernetes-pod-part03/1.png)

FORWARD 链只有在 Linux 服务器启用 ip_forward 时才工作，这就是安装 Kubernetes 集群时需要配置以下脚本的原因。
```bash
k8s-node1# sysctl -w net.ipv4.ip_forward=1
net.ipv4.ip_forward = 1
node-1# cat /proc/sys/net/ipv4/ip_forward
1
```

## tables

以下是可用的表，我们将重点关注 NAT 表。
* Filter：这是默认的表，在这个表中，决定是否允许数据包进入/出计算机。如果想阻塞一个端口以停止接收任何东西，可以在这里实现。
* Nat：这个表负责创建新的连接，这是网络地址转换的缩写。
* Mangle：只针对专门的数据包，这个表是在数据包进入或离开之前改变数据包内部的某些内容。
* Raw：处理原始的数据包，正如其名称所示，主要是用于跟踪连接状态。
* Security：负责在过滤表之后保护计算机，包括了 SELinux。

想要获取更多关于 iptables 的信息，请参考 [A Deep Dive into Iptables and Netfilter Architecture](https://www.digitalocean.com/community/tutorials/a-deep-dive-into-iptables-and-netfilter-architecture)。

# Pod 到 Pod

kube-proxy 不参与 Pod 到 Pod 的通信，因为 CNI 会配置节点 node 和 Pod 所需的路由。所有的容器都可以与所有其他容器进行通信，而不需要 NAT；所有节点都可以与所有容器（反之亦然）进行通信，而不需要 NAT。
注意：Pod 的 IP 地址不是静态的（有方法可以获取静态 IP，但默认配置不保证静态 IP 地址）。CNI 将在 Pod 重启时分配新的 IP 地址，因为 CNI 从不维护 IP 地址和 Pod 的映射。

![](/images/2021-10-15-kubernetes-pod-part03/2.png)

实际上，Pod应该使用负载均衡器来暴露自身应用。因为应用是无状态的，并且会有多个Pod。在Kubernetes中，负载均衡器类型被称为”Service 服务“。

# Pod 到 External

对于从 pod 到外部地址的流量，Kubernetes 使用 SNAT(https://en.wikipedia.org/wiki/Network_address_translation)进行地址转换。它的作用是将pod的内部源IP+端口替换为主机的IP+端口。当返回的数据包回到主机时，它将pod的IP+端口重写为目标，并将其发送回原始的pod。整个过程对原始的pod是透明的，它并不知道地址的转换。

# Pod 到 Service

## ClusterIP

Kubernetes 有一个称为“服务”的概念，它只是Pod前面的L4负载均衡器。有几种不同类型的服务。最基本的类型称为ClusterIP。这种类型的服务具有一个只能在集群内部路由的唯一VIP地址。Kubernetes 集群的动态性意味着可以移动、重启、升级或者扩展Pod。此外，一些服务会有许多副本，所以我们需要某种方式在它们之间进行负载均衡。仅仅使用Pod IP发送流量到特定应用并不容易。Kubernetes用服务解决了这个问题。服务是一个API对象，它将一个虚拟IP (VIP)映射到一组Pod IP。此外，Kubernetes 为每个服务的名称和虚拟IP提供了一个DNS条目，以便可以通过名称轻松地寻址服务。

虚拟VIP到集群内Pod IP的映射由每个节点上的 kube-proxy 进程调谐。此进程设置 iptables 或 IPVS 以在将数据包发送到集群网络之前自动将VIP转换成Pod IP。单个连接被跟踪，所以当它们返回时可以正确地进行反转换。IPVS和iptables可以将单个服务的虚拟IP负载均衡到多个Pod IP，虚拟IP实际上并不存在于系统接口中，它存在于iptables中。

![](/images/2021-10-15-kubernetes-pod-part03/3.png)

Pod通过ClusterIP或Kubernetes添加的DNS条目连接到后端。集群中的CoreDNS组件的DNS服务器会监视Kubernetes API的新服务，并为每个服务创建一组DNS记录。如果在整个集群中启用了DNS，那么所有的Pod应该都能通过它们的DNS名称自动解析服务。

![](/images/2021-10-15-kubernetes-pod-part03/4.png)

## NodePort

现在我们有了可以用于在集群中的服务之间进行通信的DNS。从外部服务器访问前端Pod的IP地址，无法访问Pod IP，因为它是一个无法路由的私有IP地址。

![](/images/2021-10-15-kubernetes-pod-part03/5.png)

让我们创建一个NodePort服务，将FrontEnd服务暴露给外部。如果将type字段设置为NodePort，Kubernetes控制平面会从 `–service-node-port-range` 标志指定的范围内分配一个端口（默认范围：30000-32767）。每个节点都会代理该端口（每个节点上的端口号都相同）到你的服务。你的服务会在其 `.spec.ports[*].nodePort` 字段中报告分配的端口。
```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  type: NodePort
  selector:
    app: webapp
  ports:
      # By default and for convenience, the `targetPort` is set to the same value as the `port` field.
    - port: 80
      targetPort: 80
      # Optional field
      # By default and for convenience, the Kubernetes control plane will allocate a port from a range (default: 30000-32767)
      nodePort: 31380
```

![](/images/2021-10-15-kubernetes-pod-part03/6.png)

现在我们可以通过 `<anyClusterNode>:<nodePort>` 访问前端服务。如果想要一个特定的端口号，可以在nodePort字段中指定一个值。控制平面将会分配给那个端口，或者分配失败。通常需要自己处理可能的端口冲突。还必须使用一个有效的端口号，这个端口号必须在为NodePort使用配置的范围内。

## Headless Services

有时，可能不需要负载均衡和单一的服务 IP。在这种情况下，可以通过明确指定集群 IP (.spec.clusterIP) 为 “None” 来创建所谓的“无头”服务。可以使用无头服务来与其他服务发现机制交互，而不受 Kubernetes 实现的限制。对于无头服务，不分配集群 IP，kube-proxy 不处理这些服务，平台不进行负载均衡或代理。

# Traffic Policy

ExternalTrafficPolicy 表示此服务是否希望将外部流量路由到节点本地或集群范围的端点。“Local”保留客户端源IP并避免NodePort类型服务的第二跳，但可能存在潜在的流量分布不均衡的风险。“Cluster”会隐藏客户端源IP，并可能导致第二次跳转到另一节点，但应该具有良好的整体负载均衡。

## Cluster Traffic Policy

这是Kubernetes服务的默认外部流量策略。总是希望将流量均匀地路由到运行服务的所有节点上的所有Pods。使用此策略的一个缺点是引入外部流量时，可能会在节点之间看到不必要的网络跳跃。例如，如果通过NodePort接收外部流量，NodePort SVC可能（随机地）将流量路由到另一台主机上的Pod，而不是将流量路由到同一主机上的Pod，从而避免了向网络的额外跳跃。

![](/images/2021-10-15-kubernetes-pod-part03/7.png)

在Cluster流量策略模式中，数据包流动如下：
1. 客户端将数据包发送到node2:31380；
2. node2在数据包中用自己的IP地址替换源IP地址（SNAT）；
3. node2在数据包上用Pod的IP地址替换目的IP；
4. 数据包被路由到node1或node3，然后再路由到端点；
5. pod的回复被路由回node2；
6. pod的回复被发送回客户端；

## Local Traffic Policy

使用此外部流量策略，kube-proxy将仅为存在于同一节点（本地）的Pod添加代理规则，而不是为无论放在何处的服务的每个Pod添加代理规则。如果试图在服务上设置 `externalTrafficPolicy: Local`，Kubernetes API会要求你使用LoadBalancer或NodePort类型。这是因为“Local”外部流量策略只适用于外部流量，这只适用于这两种类型。

如果将 service.spec.externalTrafficPolicy 设置为Local值，kube-proxy只代理对本地端点的请求，不转发到其他节点的流量。这种方法保留了原始源IP地址。如果没有本地端点，发送到节点的数据包将被丢弃，所以可以依赖于在任何可能通过到端点的数据包处理规则中应用的正确源IP。
```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  type: NodePort
  externalTrafficPolicy: Local
  selector:
    app: webapp
  ports:
      # By default and for convenience, the `targetPort` is set to the same value as the `port` field.
    - port: 80
      targetPort: 80
      # Optional field
      # By default and for convenience, the Kubernetes control plane will allocate a port from a range (default: 30000-32767)
      nodePort: 31380
```
![](/images/2021-10-15-kubernetes-pod-part03/8.png)

![](/images/2021-10-15-kubernetes-pod-part03/9.png)

在Local流量策略模式中，数据包流动如下：
1. 客户端将数据包发送到node1:31380，那里有端点；
2. node1将数据包与正确的源IP路由到端点；
3. node1不会将数据包路由到node3，因为策略是Local；
4. 客户端向node2:31380发送数据包，那里没有任何端点；
5. 数据包被丢弃；

## Local Traffic Policy（LoadBalancer）

如果在 GKE/GCE 等云厂商上将同样的 service.spec.externalTrafficPolicy 字段设置为Local会强制没有服务端点的节点通过故意失败的健康检查，从负载均衡流量的可选节点列表中移除自己。这种模型非常适合大量引入外部流量的应用程序，并避免网络上不必要的跳转以减少延迟。我们还可以保留真正的客户端IP，因为不再需要从代理节点SNAT流量。然而，使用“Local”外部流量策略的最大缺点，如Kubernetes文档所述，是应用程序的流量可能会不平衡。

![](/images/2021-10-15-kubernetes-pod-part03/10.png)

# Kube-Proxy （iptable 模式）

Kube-Proxy 位于 Kubernetes 每个节点上，同步配置复杂的 iptables 规则，以在 Pod 和服务之间进行各种过滤和 NAT。如果你进入一个 Kubernetes 节点并输入 iptables-save，你会看到 Kubernetes 或其他程序插入的规则。
在 Kubernetes 节点中最重要的链是 KUBE-SERVICES、KUBE-SVC-* 和 KUBE-SEP-*。
* KUBE-SERVICES 是服务数据包的入口点，它的工作是匹配目标 IP+Port，并将数据包分派到相应的 KUBE-SVC-* 链。
* KUBE-SVC-* 链充当负载均衡器，并将数据包均等地分发到 KUBE-SEP-链，每个 KUBE-SVC- 都有与其后端的端点数相同的 KUBE-SEP-* 链。
* KUBE-SEP-* 链代表一个服务端点，它简单地做 DNAT，将服务 IP+Port 替换为 Pod 的端点 IP+Port。

对于 DNAT，conntrack 表开始工作，并使用状态机跟踪连接状态。因为它需要记住它更改的目标地址，并在返回的数据包回来时将其改回。Iptables 也可以依赖 conntrack 状态（ctstate）来决定数据包的命运。以下是 4 种特别重要的 conntrack 状态：
* NEW：conntrack 对这个数据包一无所知，这发生在接收到 SYN 包。
* ESTABLISHED：conntrack 知道数据包属于一个已建立的连接，这发生在握手完成后。
* RELATED：数据包不属于任何连接，但它与另一个连接有关，这对于 FTP 之类的协议特别有用。
* INVALID：表示数据包有问题，conntrack 不知道如何处理。当一个数据包被标记为 INVALID 时，它通常会被防火墙规则丢弃，以防止可能的网络攻击或其他问题。然而，具体的处理方式取决于你的网络策略和配置。

Pod 和 Service 服务之间的 TCP 连接工作流程如下所示：
* 左侧的客户端 Pod 向 Service 服务发送一个数据包请求 2.2.2.10:80；
* 数据包通过客户端节点的 iptables 规则，目标被更改为 Pod IP 1.1.1.20:80；
* 服务器 Pod 处理数据包，并发送目标为 1.1.1.10 的返回数据包；
* 数据包返回到客户端节点，conntrack 识别出数据包，并将源地址重写回 2.2.2.10:80；
* 客户端 Pod 接收到响应数据包；

![](/images/2021-10-15-kubernetes-pod-part03/11.png)

![](/images/2021-10-15-kubernetes-pod-part03/12.png)

![](/images/2021-10-15-kubernetes-pod-part03/13.png)

![](/images/2021-10-15-kubernetes-pod-part03/14.png)

我们来探索下 Kubernetes 中 iptables 规则。使用 minikube 部署一个带有两个副本的Nginx应用，并输出iptables规则。
```bash
root@instance-frllxehj:~/tanjunchen# minikube start --network-plugin=cni --cni=calico
root@instance-frllxehj:~/tanjunchen# kubectl get node
NAME       STATUS   ROLES           AGE     VERSION
minikube   Ready    control-plane   3h14m   v1.20.3
```

ClusterIP并不存在于任何地方，它是一个虚拟IP，存在于Kubernetes的iptable中，Kubernetes在CoreDNS中添加了一个DNS条目。
```bash
root@instance-frllxehj:~/tanjunchen# kubectl exec -i -t  dnsutils -- nslookup frontend.default
Server:         10.96.0.10
Address:        10.96.0.10#53

Name:   frontend.default.svc.cluster.local
Address: 10.99.243.50
```

为了接入数据包过滤和NAT，Kubernetes会从iptables创建一个自定义链KUBE-SERVICES; 它将把所有的PREROUTING和OUTPUT流量重定向到自定义链KUBE-SERVICES，如下所示：
```bash
# 使用 minikube ssh 登录到 node 节点。 
docker@minikube:~$ sudo iptables -t nat -L PREROUTING            
Chain PREROUTING (policy ACCEPT)
target     prot opt source               destination         
KUBE-SERVICES  all  --  anywhere             anywhere             /* kubernetes service portals */
DOCKER_OUTPUT  all  --  anywhere             host.minikube.internal 
DOCKER     all  --  anywhere             anywhere             ADDRTYPE match dst-type LOCAL
```

在使用 KUBE-SERVICES 链接入数据包过滤和 NAT 后，Kubernetes 检查其服务的流量并相应地应用 SNAT/DNAT。在 KUBE-SERVICES 链的末尾，它将安装另一个自定义链 KUBE-NODEPORTS 来处理特定服务类型 NodePort 的流量。这种流量处理机制允许 Kubernetes 处理各种类型的服务流量，包括 ClusterIP 和 NodePort。
```bash
docker@minikube:~$ sudo iptables -t nat -L KUBE-SERVICES
Chain KUBE-SERVICES (2 references)
target     prot opt source               destination         
KUBE-SVC-ENODL3HWJ5BZY56Q  tcp  --  anywhere             10.99.243.50         /* default/frontend cluster IP */ tcp dpt:http
KUBE-SVC-NU7AD2CJVNXKF2GF  tcp  --  anywhere             10.97.17.233         /* default/backend cluster IP */ tcp dpt:http
KUBE-SVC-NPX46M4PTMTKRN6Y  tcp  --  anywhere             10.96.0.1            /* default/kubernetes:https cluster IP */ tcp dpt:https
KUBE-SVC-JD5MR3NA4I4DYORP  tcp  --  anywhere             10.96.0.10           /* kube-system/kube-dns:metrics cluster IP */ tcp dpt:9153
KUBE-SVC-TCOU7JCQXEZGVUNU  udp  --  anywhere             10.96.0.10           /* kube-system/kube-dns:dns cluster IP */ udp dpt:domain
KUBE-SVC-ERIFXISQEP7F7OF4  tcp  --  anywhere             10.96.0.10           /* kube-system/kube-dns:dns-tcp cluster IP */ tcp dpt:domain
KUBE-NODEPORTS  all  --  anywhere             anywhere             /* kubernetes service nodeports; NOTE: this must be the last rule in this chain */ ADDRTYPE match dst-type LOCAL
```

要查看KUBE-NODEPORTS的链条是什么，可以使用以下命令：
```bash
docker@minikube:~$ sudo iptables -t nat -L KUBE-NODEPORTS 
Chain KUBE-NODEPORTS (1 references)
target     prot opt source               destination         
KUBE-EXT-NU7AD2CJVNXKF2GF  tcp  --  anywhere             anywhere             /* default/backend */ tcp dpt:31151
```

从这一点开始，ClusterIP和NodePort的处理是相同的。
```bash
docker@minikube:~$ sudo iptables -t nat -L KUBE-SVC-NU7AD2CJVNXKF2GF 
Chain KUBE-SVC-NU7AD2CJVNXKF2GF (2 references)
target     prot opt source               destination         
KUBE-MARK-MASQ  tcp  -- !10.244.0.0/16        10.97.17.233         /* default/backend cluster IP */ tcp dpt:http
KUBE-SEP-Q23X5DI2CL4L6XNW  all  --  anywhere             anywhere             /* default/backend -> 10.244.0.5:80 */ statistic mode random probability 0.50000000000
KUBE-SEP-GQXAQRVZTNMNOKBF  all  --  anywhere             anywhere             /* default/backend -> 10.244.0.6:80 */
docker@minikube:~$ 
```

请看以下的 iptables 流程图：
* ClusterIP: KUBE-SERVICES → KUBE-SVC-XXX → KUBE-SEP-XXX
* NodePort: KUBE-SERVICES → KUBE-NODEPORTS → KUBE-SVC-XXX → KUBE-SEP-XXX

流量数据包整体请求流程如下所示：
![](/images/2021-10-15-kubernetes-pod-part03/15.png)

# 参考

1. https://kubernetes.io/
2. https://www.netfilter.org/
