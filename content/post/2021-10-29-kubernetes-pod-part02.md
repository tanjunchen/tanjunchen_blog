---
layout:     post
title:      "Kubernetes 中数据包的生命周期 CNI Calico（Part2）"
subtitle:   "本文我们将讨论 Kubernetes CNI Calico 核心组件 CNI 的基础知识，如核心模块、路由模式、demo 示例、要求等"
description: "本文我们将讨论 Kubernetes CNI Calico 核心组件 CNI 的基础知识，如核心模块、路由模式、demo 示例、要求等"
author: "陈谭军"
date: 2021-10-29
published: true
tags:
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---


最近在深入学习 Kubernetes 基础知识，通过追踪 HTTP 请求到达 Kubernetes 集群上的服务过程来深入学习 Kubernetes 实现原理。
希望下列文章能够对我们熟悉 Kubernetes 有一定的帮助。
* [Linux 网络、Namespace 与容器网络 CNI 基础知识](https://tanjunchen.github.io/post/2021-10-22-kubernetes-pod-part01/)
* [Kubernetes CNI 大利器 - Calico](https://tanjunchen.github.io/post/2021-10-29-kubernetes-pod-part02/)
* [Kubernetes 流量核心组件 - kube-proxy](https://tanjunchen.github.io/post/2021-10-15-kubernetes-pod-part03/)
* Kubernetes 使用 Ingress 处理七层流量

本文我们将讨论 Kubernetes CNI Calico 核心组件 CNI 的基础知识。

* 要求
* 核心模块
* 路由模式
* demo 示例

正如我们在第一部分中讨论的，CNI插件在Kubernetes网络中起着至关重要的作用。现在有许多第三方CNI插件可用，Calico就是其中之一。但是我们一般更喜欢Calico，主要原因之一就是它的易用性以及它塑造网络的架构。

Calico支持很多的平台，包括Kubernetes、OpenShift、Docker EE、OpenStack和裸机服务。Calico在Kubernetes主节点和每个Kubernetes工作节点的以Docker容器的方式运行。Calico CNI 插件直接与每个节点上的Kubernetes kubelet进程集成，以发现创建的Pod并将它们添加到Calico网络。

# CNI 要求

要实现 CNI，需要支持以下特性（也许有其他的需求，但以下的内容是最基本的要求）：

* 创建veth-pair。将veth-pair移动到容器内，veth-pair是一对虚拟网络接口，其两端可以通过网络堆栈相互连接。在Kubernetes中，我们可以使用veth-pair将Pod连接到主机节点的网络。
* 识别正确的 POD CIDR。CIDR（无类别域间路由）是用于在IP网络中分配IP地址的方法。在Kubernetes中，每个Node都会被分配一个POD CIDR范围，用于为在该Node上运行的Pod分配IP地址。
* 创建CNI配置文件。CNI配置文件定义了如何为Pod设置网络，该文件通常包含关于网络的详细信息，如使用哪种类型的网络插件、网络的名称、IP地址分配等。
* 分配和管理IP地址。Calico会自动为每个Pod分配IP地址，并确保每个Pod的IP地址在整个集群中是唯一的。
* 在容器内添加默认路由。默认路由是网络路由表中的一条特殊条目，用于指向在路由表中找不到更具体条目的目标的网络接口。
* 向所有对等节点广播路由（对于VxLan不适用）。在Kubernetes网络中，每个节点需要知道如何将流量路由到其他节点上的Pod。Calico使用BIRD路由守护进程来完成这项任务。
* 在HOST服务器中添加路由。为了能够将流量路由到在其他节点上运行的Pod，每个节点需要在其路由表中添加相应的条目。
* 执行网络策略。网络策略是一种规定允许哪些Pod可以相互通信的规则，Calico允许用户定义精细的网络策略，以提供更高级别的安全性。

让我们看一下Master和Worker节点中的路由表。每个节点都有一个带有IP地址和默认路由的容器。

![](/images/2021-10-29-kubernetes-pod-part02/1.png)

通过查看路由表，得知Pods可以通过L3网络进行通信的。那么，是哪个模块负责添加这个路由，它如何知道远程路由呢？为什么会有一个以169.254.1.1 为网关的默认路由？

Calico 核心组件包括 Bird、Felix、ConfD、Etcd 和 Kubernetes APIServer。数据存储用于存储配置信息（如ip-pool、endpoints、网络策略等）。在我们的示例中，我们将使用Kubernetes作为Calico的数据存储。

# 核心模块

## BIRD (BGP)

Bird是每个节点上的BGP守护程序，它与在其他节点上运行的BGP守护程序交换路由信息。常见的拓扑结构可能是节点到节点的网状结构，其中每个BGP与其他所有节点建立对等关系。

![](/images/2021-10-29-kubernetes-pod-part02/2.png)

对于大规模场景，网络路由可能会变得混乱。有路由反射器（Route Reflectors）用于完成路由传播（某些BGP节点可以配置为路由反射器）以减少BGP-BGP连接的数量。与其让每个BGP系统都与AS中的每个其他BGP系统对等，每个BGP发言者反而与路由反射器（Route Reflectors）对等。发送到路由反射器（Route Reflectors）的路由广播然后被反射出去，发给所有其他的BGP发言者。更多信息，请参考 RFC4456 https://datatracker.ietf.org/doc/html/rfc4456。

![](/images/2021-10-29-kubernetes-pod-part02/3.png)

BIRD实例负责将路由传播到其他BIRD实例。默认配置是“BGP网状”，这可以用于小规模部署。在大规模部署中，建议使用路由反射器（Route Reflectors）避免此问题。可以有多个RR以获得高可用性，此外，还可以使用外部机架RR代替BIRD。

## ConfD

ConfD是一个在Calico节点容器中运行的简单配置管理工具。它从etcd读取值（Calico的BIRD配置），并将它们写入磁盘文件。它循环遍历池（网络和子网）来应用配置数据（CIDR 键），并以BIRD可以使用的方式组装它们。因此，当网络发生变化时，BIRD可以检测并将路由传播到其他节点。

## Felix

Calico Felix 守护进程运行在Calico节点容器中，执行流程主要如下所示：

* 从Kubernetes etcd读取信息
* 构建路由表
* 配置IPTables（kube-proxy iptables 模式）
* 配置IPVS（kube-proxy ipvs 模式）

让我们来看看拥有所有Calico模块的集群，如下所示：

![](/images/2021-10-29-kubernetes-pod-part02/4.png)

注意：veth的一端悬挂着，没有连接到任何地方，它位于内核空间。数据包是如何被路由到对等节点？

* 主节点中的Pod尝试ping IP地址10.0.2.11
* Pod向网关发送ARP请求。
* 得到带有MAC地址的ARP响应。

让我们详细解析一下这个过程。可能有些读者已经注意到169.254.1.1是一个IPv4的链路本地地址。容器有一个默认路由指向一个链路本地地址。容器期望在其直接连接的接口上能够到达这个IP地址，在这种情况下，是容器的eth0地址。当容器希望通过默认路由路由出去时，它会尝试对该IP地址进行ARP。
如果我们捕获ARP响应，它将显示veth另一端的MAC地址（cali123）。所以你可能会想知道，主机是如何回复一个它没有IP的接口ARP请求的。答案是 proxy_arp，如果我们检查主机侧veth接口，我们会看到proxy_arp已被启用。
```bash
master $ cat /proc/sys/net/ipv4/conf/cali123/proxy_arp
1
```

“Proxy ARP 是一种技术，通过这种技术给网络上的代理设备回答对不在该网络上的IP地址 https://en.wikipedia.org/wiki/IP_address 的ARP https://en.wikipedia.org/wiki/Address_Resolution_Protocol 查询请求。代理知道流量目的地的位置，并提供其自己的MAC地址 https://en.wikipedia.org/wiki/MAC_address 作为（表面上的最终）目的地。然后，通常通过代理将定向到代理地址的流量通过另一个接口或通过 https://en.wikipedia.org/wiki/Tunneling_protocol tunnel 隧道路由到预期的目的地。这个过程，即节点以其自己的MAC地址回应对其他IP地址的ARP请求进行代理，被称为发布。”
让我们看看工作节点 work 的网络配置，如下所示：

![](/images/2021-10-29-kubernetes-pod-part02/5.png)

一旦数据包到达内核，它会根据路由表条目对数据包进行路由。传入的流量处理流程如下所示：

* 数据包到达工作节点内核。
* 内核将数据包放入cali123。

# 路由模式

Calico支持3种路由模式，如下所示：

* IP-in-IP：默认；封装。
* Direct/无封装模式：未封装（首选）
* VXLAN：封装（无BGP）

## IP-in-IP (默认)

IP-in-IP 是一种简单的封装形式，通过将一个IP包放入另一个IP包来实现。一个传输的数据包包含一个带有主机源和目标IP的外部头，和一个带有pod源和目标IP的内部头。

## 无封装模式

在这种模式下，发送的数据包就像直接来自pod一样。由于没有封装和解封装的开销，直接模式具有高性能。

## VXLAN模式

Calico 3.7+开始支持VXLAN路由。VXLAN 不适合支持IP-in-IP的网络。

VXLAN 代表虚拟可扩展局域网。VXLAN是一种封装技术，其中第二层以太网帧被封装在UDP数据包中。VXLAN是一种网络虚拟化技术。当设备在软件定义的数据中心中通信时，会在这些设备之间建立一个VXLAN隧道。这些隧道可以在物理和虚拟交换机上设置。交换机端口被称为VXLAN隧道端点（VTEPs），负责VXLAN数据包的封装和解封装。没有VXLAN支持的设备会连接到具有VTEP功能的交换机。交换机将提供从VXLAN到VXLAN的转换。

![](/images/2021-10-29-kubernetes-pod-part02/6.png)

# demo 示例

## ipip（非封装模式）

我们使用 kind 搭建一个未安装 Calico 的 Kubernetes 集群，如下所示：
```bash
kind create cluster --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true   # do not install kindnet
nodes:
- role: control-plane
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
- role: worker
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
- role: worker
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
- role: worker
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
EOF
```

```bash
root@instance-820epr0w:~# kubectl get nodes
NAME                 STATUS     ROLES                  AGE     VERSION
kind-control-plane   NotReady   control-plane,master   8m23s   v1.20.15
kind-worker          NotReady   <none>                 7m7s    v1.20.15
kind-worker2         NotReady   <none>                 7m8s    v1.20.15
kind-worker3         NotReady   <none>                 7m7s    v1.20.15
```

```bash
root@instance-820epr0w:~# kubectl get pods -A
NAMESPACE            NAME                                         READY   STATUS    RESTARTS   AGE
kube-system          coredns-74ff55c5b-lgf56                      0/1     Pending   0          8m18s
kube-system          coredns-74ff55c5b-qh62n                      0/1     Pending   0          8m18s
kube-system          etcd-kind-control-plane                      1/1     Running   0          8m29s
kube-system          kube-apiserver-kind-control-plane            1/1     Running   0          8m29s
kube-system          kube-controller-manager-kind-control-plane   1/1     Running   0          8m29s
kube-system          kube-proxy-7hp9g                             1/1     Running   0          7m17s
kube-system          kube-proxy-bghhf                             1/1     Running   0          7m17s
kube-system          kube-proxy-dqjtc                             1/1     Running   0          7m18s
kube-system          kube-proxy-rh2xz                             1/1     Running   0          8m18s
kube-system          kube-scheduler-kind-control-plane            1/1     Running   0          8m29s
local-path-storage   local-path-provisioner-58c8ccd54c-lk46k      0/1     Pending   0          8m18s
```

在Node节点上检查CNI的bin和conf目录，将不会有任何配置文件或calico二进制文件。

```bash
root@instance-820epr0w:~# docker ps
CONTAINER ID   IMAGE                   COMMAND                  CREATED         STATUS         PORTS                       NAMES
98b22509f530   kindest/node:v1.20.15   "/usr/local/bin/entr…"   9 minutes ago   Up 9 minutes                               kind-worker3
2ff124662d21   kindest/node:v1.20.15   "/usr/local/bin/entr…"   9 minutes ago   Up 9 minutes   127.0.0.1:41775->6443/tcp   kind-control-plane
aa61c697c5a3   kindest/node:v1.20.15   "/usr/local/bin/entr…"   9 minutes ago   Up 9 minutes                               kind-worker2
c1d7fd8cfd4c   kindest/node:v1.20.15   "/usr/local/bin/entr…"   9 minutes ago   Up 9 minutes                               kind-worker
```

```bash
root@instance-820epr0w:~# docker exec -it 2ff124662d21 bash
root@kind-control-plane:/# cd /etc/cni/
root@kind-control-plane:/etc/cni# ls
net.d
root@kind-control-plane:/etc/cni# cd net.d/
root@kind-control-plane:/etc/cni/net.d# ls
root@kind-control-plane:/etc/cni/net.d# pwd
/etc/cni/net.d
```

检查 master/node 节点上的 IP 路由规则，如下所示：

```bash
root@instance-820epr0w:~# docker exec -it 2ff124662d21 bash
root@kind-control-plane:/etc/cni/net.d# ip route
default via 172.18.0.1 dev eth0 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.5 

root@kind-worker:/# ip route
default via 172.18.0.1 dev eth0 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.3
```

按照文档 https://docs.tigera.io/archive/v3.16/getting-started/kubernetes/quickstart 下载并安装 calico 文件，如下所示：

```bash
kubectl create -f https://docs.projectcalico.org/archive/v3.16/manifests/tigera-operator.yaml

kubectl create -f custom-resources.yaml

apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  # Configures Calico networking.
  calicoNetwork:
    # Note: The ipPools section cannot be modified post-install.
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16   # service cidr 值
      encapsulation: IPIP      # IPIP、VXLAN、IPIPCrossSubnet、VXLANCrossSubnet、None 等
      natOutgoing: Enabled
      nodeSelector: all()

kubectl get pods -n calico-system
```

在 Calico 3.16 版本中 encapsulation 有 IPIP、VXLAN、IPIPCrossSubnet、VXLANCrossSubnet、None 等类型的参数。

* “IPIP”：将CALICO_IPV4POOL_IPIP设置为"Always"，并将CALICO_IPV4POOL_VXLAN设置为"Never"。
* “VXLAN”：将CALICO_IPV4POOL_IPIP设置为"Never"，并将CALICO_IPV4POOL_VXLAN设置为"Always"。
* “IPIPCrossSubnet”：将CALICO_IPV4POOL_IPIP设置为"CrossSubnet"，并将CALICO_IPV4POOL_VXLAN设置为"Never"。
* “VXLANCrossSubnet”：将CALICO_IPV4POOL_IPIP设置为"Never"，并将CALICO_IPV4POOL_VXLAN设置为"CrossSubnet"。
* “None”：将CALICO_IPV4POOL_IPIP和CALICO_IPV4POOL_VXLAN都设置为"Never"。

部署完成后，我们查看下 Configmap cni-config 网络配置，如下所示：
```bash
root@instance-820epr0w:~# kubectl -n calico-system get cm cni-config -oyaml
apiVersion: v1
data:
  config: |-
    {
      "name": "k8s-pod-network",
      "cniVersion": "0.3.1",
      "plugins": [
        {
          "type": "calico",
          "datastore_type": "kubernetes",
          "mtu": 1410,
          "nodename_file_optional": false,
          "log_file_path": "/var/log/calico/cni/cni.log",
          "ipam": {
              "type": "calico-ipam",
              "assign_ipv4" : "true",
              "assign_ipv6" : "false"
          },
          "container_settings": {
              "allow_ip_forwarding": false
          },
          "policy": {
              "type": "k8s"
          },
          "kubernetes": {
              "kubeconfig": "__KUBECONFIG_FILEPATH__"
          }
        },
        {"type": "portmap", "snat": true, "capabilities": {"portMappings": true}}
      ]
    }
kind: ConfigMap
```

在安装Calico后，检查Pod和Node的状态。
```bash
root@instance-820epr0w:~# kubectl get nodes
NAME                 STATUS   ROLES                  AGE   VERSION
kind-control-plane   Ready    control-plane,master   27m   v1.20.15
kind-worker          Ready    <none>                 26m   v1.20.15
kind-worker2         Ready    <none>                 26m   v1.20.15
kind-worker3         Ready    <none>                 26m   v1.20.15
```

```bash
root@instance-820epr0w:~# kubectl -n calico-system get pod
NAME                                       READY   STATUS    RESTARTS   AGE
calico-kube-controllers-569b4c5cb7-8zmlp   1/1     Running   0          5m20s
calico-node-5kphx                          1/1     Running   0          5m20s
calico-node-9rt2x                          1/1     Running   0          5m20s
calico-node-bc24n                          1/1     Running   0          5m20s
calico-node-szr86                          1/1     Running   0          5m20s
calico-typha-5655555b44-dks5w              1/1     Running   0          5m20s
calico-typha-5655555b44-drjnk              1/1     Running   0          5m20s
calico-typha-5655555b44-qq26k              1/1     Running   0          5m20s
calico-typha-5655555b44-t6zg2              1/1     Running   0          5m20s
```

因为Kubelet需要CNI配置网络，我们查看控制节点的网络配置如下所示：

```bash
root@instance-820epr0w:~# docker exec -it 2ff124662d21 bash
root@kind-control-plane:/etc/cni/net.d# ls
10-calico.conflist  calico-kubeconfig
root@kind-control-plane:/etc/cni/net.d# cat 10-calico.conflist 
{
  "name": "k8s-pod-network",
  "cniVersion": "0.3.1",
  "plugins": [
    {
      "type": "calico",
      "datastore_type": "kubernetes",
      "mtu": 1410,
      "nodename_file_optional": false,
      "log_file_path": "/var/log/calico/cni/cni.log",
      "ipam": {
          "type": "calico-ipam",
          "assign_ipv4" : "true",
          "assign_ipv6" : "false"
      },
      "container_settings": {
          "allow_ip_forwarding": false
      },
      "policy": {
          "type": "k8s"
      },
      "kubernetes": {
          "kubeconfig": "/etc/cni/net.d/calico-kubeconfig"
      }
    },
    {"type": "portmap", "snat": true, "capabilities": {"portMappings": true}}
  ]
}
```

我们在 kind-control-plane 节点查看 cni 二进制文件，如下所示：

```bash
root@kind-control-plane:/opt/cni/bin# pwd
/opt/cni/bin
root@kind-control-plane:/opt/cni/bin# ls
bandwidth  calico  calico-ipam  flannel  host-local  install  loopback  portmap  ptp  tuning
```

* bandwidth: 用于控制Pod间网络通信的带宽限制。
* bridge: 为容器创建网络桥接，使其能够与主机网络通信。
* calico: 实现了Calico的网络方案，提供了网络路由和策略控制功能。
* calico-ipam: 实现了Calico的IP地址管理(IPAM)功能。
* dhcp: 为Pod提供动态主机配置协议(DHCP)服务。
* flannel: 实现了Flannel的网络方案，提供了简单的网络覆盖功能。
* host-device: 将主机的网络设备直接映射到Pod中。
* host-local: 实现了一个基本的静态IP地址管理(IPAM)方案。
* install: 通常用于安装或更新CNI插件。
* ipvlan: 实现了IPvlan网络模式，允许Pod直接使用主机的IP地址。
* loopback: 创建一个回环网络设备，用于Pod的本地回环通信。
* macvlan: 实现了Macvlan网络模式，允许Pod直接使用主机的MAC地址。
* portmap: 提供了端口映射功能，允许Pod通过主机的端口与外部网络通信。
* ptp: 实现了点对点(PTP)网络模式，允许Pod直接与主机进行网络通信。
* sample: 通常是示例或测试用的CNI插件。
* tuning: 提供了网络参数调整功能，允许更细粒度地控制Pod的网络行为。
* vlan: 实现了虚拟局域网(VLAN)网络模式，允许Pod在隔离的网络空间中运行。

让我们安装 calicoctl，它可以提供有关Calico的详细信息，并允许我们修改Calico配置。

```bash
root@kind-control-plane:/opt/cni/bin# cd /usr/local/bin/
root@kind-control-plane:/usr/local/bin# curl -O -L  https://github.com/projectcalico/calicoctl/releases/download/v3.16.3/calicoctl
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
100 38.4M  100 38.4M    0     0  1238k      0  0:00:31  0:00:31 --:--:-- 1204k
root@kind-control-plane:/usr/local/bin# chmod +x calicoctl
root@kind-control-plane:/usr/local/bin# export DATASTORE_TYPE=kubernetes
root@kind-control-plane:/usr/local/bin# echo $KUBECONFIG
/etc/kubernetes/admin.conf
root@kind-control-plane:/usr/local/bin# calicoctl get workloadendpoints
WORKLOAD   NODE   NETWORKS   INTERFACE
```

检查 BGP（边界网关协议）对等体状态，这将显示’worker’节点作为一个对等体。

```bash
root@kind-control-plane:/usr/local/bin# calicoctl node status
Calico process is running.

IPv4 BGP status
+--------------+-------------------+-------+----------+-------------+
| PEER ADDRESS |     PEER TYPE     | STATE |  SINCE   |    INFO     |
+--------------+-------------------+-------+----------+-------------+
| 172.18.0.2   | node-to-node mesh | up    | 08:06:37 | Established |
| 172.18.0.3   | node-to-node mesh | up    | 08:07:33 | Established |
| 172.18.0.4   | node-to-node mesh | up    | 08:07:56 | Established |
+--------------+-------------------+-------+----------+-------------+

IPv6 BGP status
No IPv6 peers found.
```

这是 BGP（边界网关协议）对等体的状态信息。对于每一个对等体，都有一个状态来描述它当前的连接状态。这里有三个状态：start，up和Established。

* start： 这是BGP会话初始建立的状态，在这个状态下，BGP会尝试建立连接。
* up： 这是BGP会话正在进行的状态，表示连接已经建立，但还没达到完全稳定（Established）。
* Established： 这是BGP对等体连接已经完全建立并且稳定的状态，能够正常交换路由信息。

创建一个带有两个副本和主节点容忍度的 busybox。
```bash
cat > busybox.yaml <<"EOF"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: busybox-deployment
spec:
  selector:
    matchLabels:
      app: busybox
  replicas: 2
  template:
    metadata:
      labels:
        app: busybox
    spec:
      tolerations:
      - key: "node-role.kubernetes.io/master"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: busybox
        image: busybox
        command: ["sleep"]
        args: ["10000"]
EOF
kubectl apply -f busybox.yaml
```

获取Pod和端点状态。
```bash
root@kind-control-plane:/usr/local/bin# kubectl get pods -o wide 
NAME                                  READY   STATUS    RESTARTS   AGE   IP               NODE           NOMINATED NODE   READINESS GATES
busybox-deployment-654565d6ff-gbmnj   1/1     Running   0          84s   10.244.195.194   kind-worker3   <none>           <none>
busybox-deployment-654565d6ff-lm5nf   1/1     Running   0          84s   10.244.110.129   kind-worker2   <none>           <none>

root@kind-control-plane:/usr/local/bin# calicoctl get workloadendpoints
WORKLOAD                              NODE           NETWORKS            INTERFACE         
busybox-deployment-654565d6ff-gbmnj   kind-worker3   10.244.195.194/32   cali6ad45a7cd51   
busybox-deployment-654565d6ff-lm5nf   kind-worker2   10.244.110.129/32   calie4f3c781c5e   
```

获取 Master 节点所在主机详细信息，如下所示：
```bash
root@kind-control-plane:/# ifconfig
cali38bd23d7943: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1410
        ether ee:ee:ee:ee:ee:ee  txqueuelen 0  (Ethernet)
        RX packets 1480  bytes 140599 (140.5 KB)
        RX errors 0  dropped 1  overruns 0  frame 0
        TX packets 1457  bytes 153780 (153.7 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

calia4307b0e305: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1410
        ether ee:ee:ee:ee:ee:ee  txqueuelen 0  (Ethernet)
        RX packets 158  bytes 12443 (12.4 KB)
        RX errors 0  dropped 1  overruns 0  frame 0
        TX packets 134  bytes 14196 (14.1 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

calid50353acbd9: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1410
        ether ee:ee:ee:ee:ee:ee  txqueuelen 0  (Ethernet)
        RX packets 1489  bytes 141483 (141.4 KB)
        RX errors 0  dropped 1  overruns 0  frame 0
        TX packets 1464  bytes 154968 (154.9 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.18.0.5  netmask 255.255.0.0  broadcast 172.18.255.255
        inet6 fe80::42:acff:fe12:5  prefixlen 64  scopeid 0x20<link>
        inet6 fc00:f853:ccd:e793::5  prefixlen 64  scopeid 0x0<global>
        ether 02:42:ac:12:00:05  txqueuelen 0  (Ethernet)
        RX packets 116976  bytes 272380205 (272.3 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 96570  bytes 37176929 (37.1 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
        inet6 ::1  prefixlen 128  scopeid 0x10<host>
        loop  txqueuelen 1000  (Local Loopback)
        RX packets 430506  bytes 114320499 (114.3 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 430506  bytes 114320499 (114.3 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

tunl0: flags=193<UP,RUNNING,NOARP>  mtu 1440
        inet 10.244.82.0  netmask 255.255.255.255
        tunnel   txqueuelen 1000  (IPIP Tunnel)
        RX packets 0  bytes 0 (0.0 B)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 0  bytes 0 (0.0 B)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

root@kind-control-plane:/# ip link 
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: calia4307b0e305@if3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1410 qdisc noqueue state UP mode DEFAULT group default 
    link/ether ee:ee:ee:ee:ee:ee brd ff:ff:ff:ff:ff:ff link-netns cni-eb831c53-7ee0-61da-0106-fa3092bffec7
3: tunl0@NONE: <NOARP,UP,LOWER_UP> mtu 1440 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
6: calid50353acbd9@if4: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1410 qdisc noqueue state UP mode DEFAULT group default 
    link/ether ee:ee:ee:ee:ee:ee brd ff:ff:ff:ff:ff:ff link-netns cni-441fa6ff-7b2a-32bf-a142-902bd66f855b
7: cali38bd23d7943@if4: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1410 qdisc noqueue state UP mode DEFAULT group default 
    link/ether ee:ee:ee:ee:ee:ee brd ff:ff:ff:ff:ff:ff link-netns cni-f235c16c-cd2c-e28c-b308-04919c22e186
11: eth0@if12: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default 
    link/ether 02:42:ac:12:00:05 brd ff:ff:ff:ff:ff:ff link-netnsid 0

root@kind-control-plane:/# ip route
default via 172.18.0.1 dev eth0 
blackhole 10.244.82.0/26 proto bird 
10.244.82.1 dev calia4307b0e305 scope link 
10.244.82.2 dev calid50353acbd9 scope link 
10.244.82.3 dev cali38bd23d7943 scope link 
10.244.110.128/26 via 172.18.0.2 dev tunl0 proto bird onlink 
10.244.162.128/26 via 172.18.0.3 dev tunl0 proto bird onlink 
10.244.195.192/26 via 172.18.0.4 dev tunl0 proto bird onlink 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.5 
```

获取 busybox Pod （kind-worker3）所在的主机节点上的网络配置，如下所示：
```bash
root@kind-worker3:/# ifconfig
cali15c1d999844: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1410
        ether ee:ee:ee:ee:ee:ee  txqueuelen 0  (Ethernet)
        RX packets 1670  bytes 145288 (145.2 KB)
        RX errors 0  dropped 1  overruns 0  frame 0
        TX packets 1647  bytes 1275171 (1.2 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

cali6ad45a7cd51: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1410
        ether ee:ee:ee:ee:ee:ee  txqueuelen 0  (Ethernet)
        RX packets 35  bytes 2951 (2.9 KB)
        RX errors 0  dropped 1  overruns 0  frame 0
        TX packets 20  bytes 1897 (1.8 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.18.0.4  netmask 255.255.0.0  broadcast 172.18.255.255
        inet6 fc00:f853:ccd:e793::4  prefixlen 64  scopeid 0x0<global>
        inet6 fe80::42:acff:fe12:4  prefixlen 64  scopeid 0x20<link>
        ether 02:42:ac:12:00:04  txqueuelen 0  (Ethernet)
        RX packets 89950  bytes 240361353 (240.3 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 74909  bytes 6516500 (6.5 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
        inet6 ::1  prefixlen 128  scopeid 0x10<host>
        loop  txqueuelen 1000  (Local Loopback)
        RX packets 20706  bytes 1448963 (1.4 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 20706  bytes 1448963 (1.4 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

tunl0: flags=193<UP,RUNNING,NOARP>  mtu 1440
        inet 10.244.195.192  netmask 255.255.255.255
        tunnel   txqueuelen 1000  (IPIP Tunnel)
        RX packets 18  bytes 1561 (1.5 KB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 18  bytes 1469 (1.4 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

root@kind-worker3:/# ip route
default via 172.18.0.1 dev eth0 
10.244.82.0/26 via 172.18.0.5 dev tunl0 proto bird onlink 
10.244.110.128/26 via 172.18.0.2 dev tunl0 proto bird onlink 
10.244.162.128/26 via 172.18.0.3 dev tunl0 proto bird onlink 
blackhole 10.244.195.192/26 proto bird 
10.244.195.193 dev cali15c1d999844 scope link 
10.244.195.194 dev cali6ad45a7cd51 scope link 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.4 
```

获取 busybox Pod （kind-worker2）所在的主机节点上的网络配置，如下所示：
```bash
root@kind-worker2:/# ifconfig 
calie4f3c781c5e: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1410
        ether ee:ee:ee:ee:ee:ee  txqueuelen 0  (Ethernet)
        RX packets 32  bytes 2700 (2.7 KB)
        RX errors 0  dropped 1  overruns 0  frame 0
        TX packets 17  bytes 1554 (1.5 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.18.0.2  netmask 255.255.0.0  broadcast 172.18.255.255
        inet6 fc00:f853:ccd:e793::2  prefixlen 64  scopeid 0x0<global>
        inet6 fe80::42:acff:fe12:2  prefixlen 64  scopeid 0x20<link>
        ether 02:42:ac:12:00:02  txqueuelen 0  (Ethernet)
        RX packets 82210  bytes 217292086 (217.2 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 67612  bytes 5847063 (5.8 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
        inet6 ::1  prefixlen 128  scopeid 0x10<host>
        loop  txqueuelen 1000  (Local Loopback)
        RX packets 19083  bytes 1372255 (1.3 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 19083  bytes 1372255 (1.3 MB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

tunl0: flags=193<UP,RUNNING,NOARP>  mtu 1440
        inet 10.244.110.128  netmask 255.255.255.255
        tunnel   txqueuelen 1000  (IPIP Tunnel)
        RX packets 15  bytes 1260 (1.2 KB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 15  bytes 1260 (1.2 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
```

获取 Pod 网络接口的详细信息，如下所示：
```bash
root@kind-control-plane:/# kubectl exec -it busybox-deployment-654565d6ff-gbmnj -- ifconfig 
eth0      Link encap:Ethernet  HWaddr 0E:10:D4:06:AA:F9  
          inet addr:10.244.195.194  Bcast:10.244.195.194  Mask:255.255.255.255
          inet6 addr: fe80::c10:d4ff:fe06:aaf9/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1410  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:13 errors:0 dropped:1 overruns:0 carrier:0
          collisions:0 txqueuelen:0 
          RX bytes:0 (0.0 B)  TX bytes:1006 (1006.0 B)

lo        Link encap:Local Loopback  
          inet addr:127.0.0.1  Mask:255.0.0.0
          inet6 addr: ::1/128 Scope:Host
          UP LOOPBACK RUNNING  MTU:65536  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000 
          RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

root@kind-control-plane:/# kubectl exec -it busybox-deployment-654565d6ff-gbmnj --  ip link 
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
4: eth0@if5: <BROADCAST,MULTICAST,UP,LOWER_UP,M-DOWN> mtu 1410 qdisc noqueue 
    link/ether 0e:10:d4:06:aa:f9 brd ff:ff:ff:ff:ff:ff

root@kind-control-plane:/# kubectl exec -it busybox-deployment-654565d6ff-gbmnj -- ip a     
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
4: eth0@if5: <BROADCAST,MULTICAST,UP,LOWER_UP,M-DOWN> mtu 1410 qdisc noqueue 
    link/ether 0e:10:d4:06:aa:f9 brd ff:ff:ff:ff:ff:ff
    inet 10.244.195.194/32 brd 10.244.195.194 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::c10:d4ff:fe06:aaf9/64 scope link 
       valid_lft forever preferred_lft forever
root@kind-control-plane:/# kubectl exec -it busybox-deployment-654565d6ff-gbmnj -- ip route
default via 169.254.1.1 dev eth0 
169.254.1.1 dev eth0 scope link 
root@kind-control-plane:/# kubectl exec -it busybox-deployment-654565d6ff-gbmnj -- arp 
root@kind-control-plane:/# 
```

注意我们在 calico 中获取的 workloadendpoints 如下所示：
```bash
root@kind-control-plane:/usr/local/bin# calicoctl get workloadendpoints
WORKLOAD                              NODE           NETWORKS            INTERFACE         
busybox-deployment-654565d6ff-gbmnj   kind-worker3   10.244.195.194/32   cali6ad45a7cd51   
busybox-deployment-654565d6ff-lm5nf   kind-worker2   10.244.110.129/32   calie4f3c781c5e   
root@kind-control-plane:/proc/sys/net/ipv4/conf/cali38bd23d7943# kubectl get pod -owide
NAME                                  READY   STATUS    RESTARTS   AGE   IP               NODE           NOMINATED NODE   READINESS GATES
busybox-deployment-654565d6ff-gbmnj   1/1     Running   0          35m   10.244.195.194   kind-worker3   <none>           <none>
busybox-deployment-654565d6ff-lm5nf   1/1     Running   0          35m   10.244.110.129   kind-worker2   <none>           <none>
```

让我们尝试ping工作节点的Pod以触发ARP。在一个终端执行以下操作：
```bash
root@instance-820epr0w:~# kubectl exec -it busybox-deployment-654565d6ff-gbmnj -- ping 10.244.110.129
PING 10.244.110.129 (10.244.110.129): 56 data bytes
64 bytes from 10.244.110.129: seq=0 ttl=62 time=0.235 ms
64 bytes from 10.244.110.129: seq=1 ttl=62 time=0.122 ms
64 bytes from 10.244.110.129: seq=2 ttl=62 time=0.107 ms
64 bytes from 10.244.110.129: seq=3 ttl=62 time=0.116 ms
```

在另一个终端执行以下操作：
```bash
root@kind-worker3:/# ip route
default via 172.18.0.1 dev eth0 
10.244.82.0/26 via 172.18.0.5 dev tunl0 proto bird onlink 
10.244.110.128/26 via 172.18.0.2 dev tunl0 proto bird onlink 
10.244.162.128/26 via 172.18.0.3 dev tunl0 proto bird onlink 
blackhole 10.244.195.192/26 proto bird 
10.244.195.193 dev cali15c1d999844 scope link 

  dev cali6ad45a7cd51 scope link 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.4 

root@instance-820epr0w:~# kubectl exec -it busybox-deployment-654565d6ff-gbmnj -- arp
172-18-0-4.calico-typha.calico-system.svc.cluster.local (172.18.0.4) at ee:ee:ee:ee:ee:ee [ether]  on eth0
? (169.254.1.1) at ee:ee:ee:ee:ee:ee [ether]  on eth0
```

网关的 MAC 地址就是 cali6ad45a7cd51:。从现在开始，只要有流量出去，它就会直接打到内核上；内核知道它必须根据 IP 路由将数据包写入tunl0。Proxy ARP 配置如下所示：
```bash
root@kind-worker3:/# cat /proc/sys/net/ipv4/conf/cali6ad45a7cd51/proxy_arp
1
```

那么目标节点如何处理数据包？
```bash
root@kind-worker2:/# ip route
default via 172.18.0.1 dev eth0 
10.244.82.0/26 via 172.18.0.5 dev tunl0 proto bird onlink 
blackhole 10.244.110.128/26 proto bird 
10.244.110.129 dev calie4f3c781c5e scope link 
10.244.162.128/26 via 172.18.0.3 dev tunl0 proto bird onlink 
10.244.195.192/26 via 172.18.0.4 dev tunl0 proto bird onlink 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.2 
```

在接收到数据包后，内核会根据路由表将数据包发送到正确的 veth。如果我们抓取数据包，如下所示：
```bash
root@kind-worker2:/# crictl ps | grep busybox
3ccd405036ae5       3f57d9401f8d4       About an hour ago   Running             busybox             0                   c819af069a3a4       busybox-deployment-654565d6ff-lm5nf
root@kind-worker2:/# crictl inspect 3ccd405036ae5 | grep pid
    "pid": 5466,
            "pid": 1
            "type": "pid"
root@kind-worker2:/# nsenter -t 5466 -n tcpdump -n -i any
tcpdump: data link type LINUX_SLL2
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on any, link-type LINUX_SLL2 (Linux cooked v2), snapshot length 262144 bytes
09:24:48.870719 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 0, length 64
09:24:48.870728 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 0, length 64
09:24:49.870853 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 1, length 64
09:24:49.870861 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 1, length 64
09:24:50.870995 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 2, length 64
09:24:50.871004 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 2, length 64
09:24:51.871127 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 3, length 64
09:24:51.871138 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 3, length 64
09:24:52.871264 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 4, length 64
09:24:52.871285 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 4, length 64
09:24:53.871410 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 5, length 64
09:24:53.871419 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 5, length 64
09:24:54.055279 eth0  Out ARP, Request who-has 169.254.1.1 tell 10.244.110.129, length 28
09:24:54.055307 eth0  In  ARP, Reply 169.254.1.1 is-at ee:ee:ee:ee:ee:ee, length 28
09:24:54.871536 eth0  In  IP 10.244.195.194 > 10.244.110.129: ICMP echo request, id 236, seq 6, length 64
09:24:54.871544 eth0  Out IP 10.244.110.129 > 10.244.195.194: ICMP echo reply, id 236, seq 6, length 64
09:24:55.075282 eth0  In  ARP, Request who-has 10.244.110.129 tell 172.18.0.2, length 28
09:24:55.075303 eth0  Out ARP, Reply 10.244.110.129 is-at 0a:d9:c9:76:e7:d4, length 28
```

为了获得更好的性能，最好禁用IP-IP。

## 禁用 ipip

更新 ipPool 配置禁用 IPIP。打开 ippool.yaml 文件，将 IPIP 设置为 ‘Never’，然后通过 calicoctl 应用该 yaml 文件。

```bash
root@kind-control-plane:/# calicoctl get ippool default-ipv4-ippool -o yaml 
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  creationTimestamp: "2024-02-07T08:04:33Z"
  name: default-ipv4-ippool
  resourceVersion: "12460"
  uid: 0a42dc66-b743-4b82-a715-4a5b8172e2a2
spec:
  blockSize: 26
  cidr: 10.244.0.0/16
  ipipMode: Never
  natOutgoing: true
  nodeSelector: all()
  vxlanMode: Never
root@kind-control-plane:/# calicoctl apply -f ippool.yaml
Successfully applied 1 'IPPool' resource(s)

root@kind-control-plane:/# ip route
default via 172.18.0.1 dev eth0 
blackhole 10.244.82.0/26 proto bird 
10.244.82.1 dev calia4307b0e305 scope link 
10.244.82.2 dev calid50353acbd9 scope link 
10.244.82.3 dev cali38bd23d7943 scope link 
10.244.110.128/26 via 172.18.0.2 dev eth0 proto bird 
10.244.162.128/26 via 172.18.0.3 dev eth0 proto bird 
10.244.195.192/26 via 172.18.0.4 dev eth0 proto bird 
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.5 
```

设备不再是 tunl0；它被设置为节点的管理（eth0）接口。让我们重新执行上述 ping 操作，确保一切正常运行。从现在开始，将不再涉及到任何IPIP协议。

## vxlan

重新创建一个 k8s 集群，如下所示：
```bash
kind create cluster --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true   # do not install kindnet
nodes:
- role: control-plane
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
- role: worker
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
- role: worker
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
- role: worker
  image: kindest/node:v1.20.15@sha256:a32bf55309294120616886b5338f95dd98a2f7231519c7dedcec32ba29699394
EOF
```

```bash
kubectl create -f https://docs.projectcalico.org/archive/v3.16/manifests/tigera-operator.yaml

kubectl create -f custom-resources-vxlan.yaml

apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  # Configures Calico networking.
  calicoNetwork:
    # Note: The ipPools section cannot be modified post-install.
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16   # service cidr 值
      encapsulation: VXLAN      # IPIP、VXLAN、IPIPCrossSubnet、VXLANCrossSubnet、None 等
      natOutgoing: Enabled
      nodeSelector: all()
```

集群信息如下所示：
```bash
➜  cni-calico  kubectl get pods -A -owide
NAMESPACE            NAME                                         READY   STATUS    RESTARTS   AGE   IP               NODE                 NOMINATED NODE   READINESS GATES
calico-system        calico-kube-controllers-569b4c5cb7-5c2x6     1/1     Running   0          12m   10.244.110.129   kind-worker2         <none>           <none>
calico-system        calico-node-4pg8w                            1/1     Running   0          12m   172.18.0.4       kind-worker3         <none>           <none>
calico-system        calico-node-7ffjr                            1/1     Running   0          12m   172.18.0.2       kind-worker          <none>           <none>
calico-system        calico-node-mt7nh                            1/1     Running   0          12m   172.18.0.3       kind-worker2         <none>           <none>
calico-system        calico-node-rc4xk                            0/1     Running   0          12m   172.18.0.5       kind-control-plane   <none>           <none>
calico-system        calico-typha-c47c58b89-8x8z4                 1/1     Running   0          11m   172.18.0.3       kind-worker2         <none>           <none>
calico-system        calico-typha-c47c58b89-qcn96                 1/1     Running   0          11m   172.18.0.4       kind-worker3         <none>           <none>
calico-system        calico-typha-c47c58b89-vbg79                 1/1     Running   0          12m   172.18.0.2       kind-worker          <none>           <none>
calico-system        calico-typha-c47c58b89-xqf7w                 1/1     Running   0          11m   172.18.0.5       kind-control-plane   <none>           <none>
default              busybox-deployment-654565d6ff-7lj4t          1/1     Running   0          74s   10.244.162.129   kind-worker          <none>           <none>
default              busybox-deployment-654565d6ff-h4xw2          1/1     Running   0          74s   10.244.110.131   kind-worker2         <none>           <none>
kube-system          coredns-74ff55c5b-glltq                      1/1     Running   0          19m   10.244.110.130   kind-worker2         <none>           <none>
kube-system          coredns-74ff55c5b-s68bf                      1/1     Running   0          19m   10.244.195.193   kind-worker3         <none>           <none>
kube-system          etcd-kind-control-plane                      1/1     Running   0          19m   172.18.0.5       kind-control-plane   <none>           <none>
kube-system          kube-apiserver-kind-control-plane            1/1     Running   0          19m   172.18.0.5       kind-control-plane   <none>           <none>
kube-system          kube-controller-manager-kind-control-plane   1/1     Running   0          19m   172.18.0.5       kind-control-plane   <none>           <none>
kube-system          kube-proxy-5g952                             1/1     Running   0          19m   172.18.0.5       kind-control-plane   <none>           <none>
kube-system          kube-proxy-fmctx                             1/1     Running   0          18m   172.18.0.3       kind-worker2         <none>           <none>
kube-system          kube-proxy-lklns                             1/1     Running   0          18m   172.18.0.4       kind-worker3         <none>           <none>
kube-system          kube-proxy-rzk29                             1/1     Running   0          18m   172.18.0.2       kind-worker          <none>           <none>
kube-system          kube-scheduler-kind-control-plane            1/1     Running   0          19m   172.18.0.5       kind-control-plane   <none>           <none>
local-path-storage   local-path-provisioner-58c8ccd54c-nffsc      1/1     Running   0          19m   10.244.195.194   kind-worker3         <none>           <none>
tigera-operator      tigera-operator-655db97ccb-cd6xb             1/1     Running   0          13m   172.18.0.4       kind-worker3         <none>           <none>
```

查看 calico 配置
```bash
➜  cni-calico  kubectl -n calico-system  get ds -oyaml | grep -i -C2  vxlan
          - name: CALICO_IPV4POOL_CIDR
            value: 10.244.0.0/16
          - name: CALICO_IPV4POOL_VXLAN
            value: Always
          - name: CALICO_IPV4POOL_BLOCK_SIZE
--
          - name: CALICO_IPV4POOL_NODE_SELECTOR
            value: all()
          - name: FELIX_VXLANMTU
            value: "1410"
          - name: FELIX_WIREGUARDMTU
```

在 master 节点查看网络配置：
```bash
➜  cni-calico  docker ps
CONTAINER ID   IMAGE                   COMMAND                   CREATED          STATUS          PORTS                       NAMES
5e55184a6fd5   kindest/node:v1.20.15   "/usr/local/bin/entr…"   23 minutes ago   Up 23 minutes                               kind-worker
23cb30dd696d   kindest/node:v1.20.15   "/usr/local/bin/entr…"   23 minutes ago   Up 23 minutes   127.0.0.1:58782->6443/tcp   kind-control-plane
5221920dc5e5   kindest/node:v1.20.15   "/usr/local/bin/entr…"   23 minutes ago   Up 23 minutes                               kind-worker3
e626537d9d0f   kindest/node:v1.20.15   "/usr/local/bin/entr…"   23 minutes ago   Up 23 minutes                               kind-worker2
➜  cni-calico  docker exec -it 23cb30dd696d bash
root@kind-control-plane:/# ip route
default via 172.18.0.1 dev eth0
10.244.110.128/26 via 10.244.110.128 dev vxlan.calico onlink
10.244.162.128/26 via 10.244.162.128 dev vxlan.calico onlink
10.244.195.192/26 via 10.244.195.192 dev vxlan.calico onlink
172.18.0.0/16 dev eth0 proto kernel scope link src 172.18.0.5
```

创建一个带有两个副本和主节点容忍度的 busybox。
```bash
cat > busybox.yaml <<"EOF"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: busybox-deployment
spec:
  selector:
    matchLabels:
      app: busybox
  replicas: 2
  template:
    metadata:
      labels:
        app: busybox
    spec:
      tolerations:
      - key: "node-role.kubernetes.io/master"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: busybox
        image: busybox
        command: ["sleep"]
        args: ["10000"]
EOF
```

```bash
kubectl apply -f busybox.yaml
➜  cni-calico  kubectl get pod
NAME                                  READY   STATUS    RESTARTS   AGE
busybox-deployment-654565d6ff-7lj4t   1/1     Running   0          7m5s
busybox-deployment-654565d6ff-h4xw2   1/1     Running   0          7m5s
```

在 busybox pod 触发 arp 请求

```bash
➜  cni-calico  kubectl exec -it busybox-deployment-654565d6ff-7lj4t -- arp
172-18-0-2.calico-typha.calico-system.svc.cluster.local (172.18.0.2) at ee:ee:ee:ee:ee:ee [ether]  on eth0
^Ccommand terminated with exit code 130
➜  cni-calico  kubectl exec -it busybox-deployment-654565d6ff-7lj4t -- ping  8.8.8.8
PING 8.8.8.8 (8.8.8.8): 56 data bytes
64 bytes from 8.8.8.8: seq=0 ttl=62 time=105.489 ms
^C
--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 packets received, 0% packet loss
round-trip min/avg/max = 105.489/105.489/105.489 ms
➜  cni-calico  kubectl exec -it busybox-deployment-654565d6ff-7lj4t -- ip route
default via 169.254.1.1 dev eth0
169.254.1.1 dev eth0 scope link
```

这个概念与之前的模式类似，但唯一的区别在于，数据包到达 VXLAN 时，VXLAN 会将数据包封装，并在内层头部中加入节点的 IP 和 MAC 地址，然后发送出去。此外，VXLAN 协议的 UDP 端口为 4789。在此过程中，etcd 提供了可用节点及其支持的 IP 范围的详细信息，以便 VXLAN-Calico 构建数据包。

![](/images/2021-10-29-kubernetes-pod-part02/7.png)
