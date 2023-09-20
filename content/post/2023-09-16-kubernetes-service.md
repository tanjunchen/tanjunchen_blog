---
layout:     post
title:      "深入研究 Kubernetes 集群中的 Service 通信机制"
subtitle:   "Kubernetes 中的服务是一种简单的抽象，但与任何抽象层类似，它增加了系统的复杂性，并使故障排除变得更具挑战性。本文我们来研究下在 Kubernetes 集群中，Service 之间是如何通信的。"
description: "在我们的学习过程中，首先我们探讨了在 Docker Swarm 集群模式下，服务之间是如何进行通信的。我们了解到，Docker Swarm 使用内置的服务发现和负载均衡机制来实现服务间的通信。然后，我们转向 Kubernetes，研究了在 kube-proxy、Istio Service Mesh 和 Cilium 三种模式下服务到服务的通信机制。在 kube-proxy 模式下，我们了解到它使用 Iptables 或者 IPVS 来实现服务的负载均衡。而在 Istio Service Mesh 模式下，服务间的通信是通过 Envoy 代理来实现的，它提供了丰富的流量控制和安全策略。最后，在 Cilium 模式下，我们学习了它是如何利用 BPF（Berkeley Packet Filter）来实现服务通信的。这三种模式各有特点，为我们提供了丰富的选择来满足不同的服务通信需求。"
author: "陈谭军"
date: 2023-09-16
published: true
tags:
    - kubernetes
    - istio
    - cilium
    - cni
categories:
    - TECHNOLOGY
showtoc: true
---

我们将应用程序部署到 Kubernetes 集群时，比较重要的一步是创建 Service，它允许集群内的应用程序或外部客户端通过 Service 访问。
Kubernetes 中的服务是一种简单的抽象，但与任何抽象层类似，它增加了系统的复杂性，并使故障排除变得更具挑战性。本文我们来研究下在 Kubernetes 集群中，Service 之间是如何通信的。

# 目标

集群中的服务是如何通信的？在本文中，我们将使用以下示例来深入了解与学习 Kubernetes Service 通信的工作原理。

# 序言

在我们开始研究 Kubernetes 集群中的 Service 通信原理之前，先简单了解与学习 Docker Swarm 模式下的 Service 是如何通信的？让我们探索一下服务到服务通信是如何在 Docker Swarm 集群中工作的！！！
通过应用下述配置，Docker 创建一组容器并建立包含负载均衡器的 [overlay network](https://docs.docker.com/network/drivers/overlay/)。

```yaml
version: "3.8"

services:
  nginx:
    image: nginx
    ports:
      - target: 80
        published: 80
        protocol: tcp
    deploy:
      mode: replicated
      replicas: 2

  client:
    image: arunvelsriram/utils:latest
    command: ['sleep', '100500']
    deploy:
      mode: replicated
      replicas: 1
```

基本信息如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service#
root@instance-00qqerhq:~/learn-k8s-service# docker stack deploy -c demo.yaml demo
Updating service demo_client (id: b8e7l5ji49ernu82ztn1nbo3z)
Updating service demo_nginx (id: s5ipvpa1ba5beb30upotdne76)
root@instance-00qqerhq:~/learn-k8s-service# docker ps
CONTAINER ID   IMAGE                        COMMAND                  CREATED          STATUS          PORTS     NAMES
26941a6b9e4d   nginx:latest                 "/docker-entrypoint.…"   31 seconds ago   Up 29 seconds   80/tcp    demo_nginx.1.kob19ablrceyzwhq1f1nf5aoi
ffe0d8ceee5c   nginx:latest                 "/docker-entrypoint.…"   31 seconds ago   Up 29 seconds   80/tcp    demo_nginx.2.rhlsd9qk0e28jomsu06pbgql0
0306c3860864   arunvelsriram/utils:latest:latest   "sleep 100500"           46 seconds ago   Up 43 seconds             demo_client.1.dgjvk7xvktsocf91mme1uport
root@instance-00qqerhq:~/learn-k8s-service# docker network inspect demo_default
[
    {
        "Name": "demo_default",
        "Id": "12uyuotr1nedpuelmtmktli9h",
        "Created": "2023-09-20T13:47:11.65538148+08:00",
        "Scope": "swarm",
        "Driver": "overlay",
        "EnableIPv6": false,
        "IPAM": {
            "Driver": "default",
            "Options": null,
            "Config": [
                {
                    "Subnet": "10.0.1.0/24",
                    "Gateway": "10.0.1.1"
                }
            ]
        },
        "Internal": false,
        "Attachable": false,
        "Ingress": false,
        "ConfigFrom": {
            "Network": ""
        },
        "ConfigOnly": false,
        "Containers": {
            "0306c386086416765907d4c42d345c4d18c725af921bc5eca751f6c10f4829a1": {
                "Name": "demo_client.1.dgjvk7xvktsocf91mme1uport",
                "EndpointID": "e86cef54cd8d7e5ec2473536da48cd34e29f57d30b2e8824294869cf06e40054",
                "MacAddress": "02:42:0a:00:01:03",
                "IPv4Address": "10.0.1.3/24",
                "IPv6Address": ""
            },
            "26941a6b9e4d7247f63b47a6a82dd1f69248f2e548b5ee8ebf01b201b497854c": {
                "Name": "demo_nginx.1.kob19ablrceyzwhq1f1nf5aoi",
                "EndpointID": "51f57e98bb2b63c5524b65e6d32b0bd86fbc04f3c444d34a4a24e5b276931be8",
                "MacAddress": "02:42:0a:00:01:06",
                "IPv4Address": "10.0.1.6/24",
                "IPv6Address": ""
            },
            "ffe0d8ceee5ce02c703a3bc6fff3682920417c3811169dc6a1f960b8caaa89f5": {
                "Name": "demo_nginx.2.rhlsd9qk0e28jomsu06pbgql0",
                "EndpointID": "1e01ead7205062ae98dc1ac1800ef08be34b468c332c73a7c62795c88d8a081d",
                "MacAddress": "02:42:0a:00:01:07",
                "IPv4Address": "10.0.1.7/24",
                "IPv6Address": ""
            },
            "lb-demo_default": {
                "Name": "demo_default-endpoint",
                "EndpointID": "2b7573d673d6096d8273af928164565465d9ca8e39c3808a9969749b037e0a89",
                "MacAddress": "02:42:0a:00:01:04",
                "IPv4Address": "10.0.1.4/24",
                "IPv6Address": ""
            }
        },
        "Options": {
            "com.docker.network.driver.overlay.vxlanid_list": "4097"
        },
        "Labels": {
            "com.docker.stack.namespace": "demo"
        },
        "Peers": [
            {
                "Name": "39709c0a8f2e",
                "IP": "192.168.0.2"
            }
        ]
    }
]
```

负载均衡器 (lb-demo_default) 是一个专用网络命名空间，使用 [IPVS](https://en.wikipedia.org/wiki/IP_Virtual_Server) 在容器之间分配流量，整体的网络架构如下所示：

![](/images/2023-09-16-kubernetes-service/1.svg)

其中，上图中的 IP 地址 10.0.1.5 是分配给负载均衡器网络命名空间的，现在我们从客户端容器运行 telnet 到 nginx 服务命令，如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service# docker ps
CONTAINER ID   IMAGE                        COMMAND                  CREATED              STATUS              PORTS     NAMES
26941a6b9e4d   nginx:latest                 "/docker-entrypoint.…"   About a minute ago   Up About a minute   80/tcp    demo_nginx.1.kob19ablrceyzwhq1f1nf5aoi
ffe0d8ceee5c   nginx:latest                 "/docker-entrypoint.…"   About a minute ago   Up About a minute   80/tcp    demo_nginx.2.rhlsd9qk0e28jomsu06pbgql0
0306c3860864   arunvelsriram/utils:latest   "sleep 100500"           About a minute ago   Up About a minute             demo_client.1.dgjvk7xvktsocf91mme1uport
root@instance-00qqerhq:~/learn-k8s-service# docker exec -it demo_client.1.dgjvk7xvktsocf91mme1uport  telnet nginx 80
Trying 10.0.1.5...
Connected to nginx.
Escape character is '^]'.
^CConnection closed by foreign host.
root@instance-00qqerhq:~/learn-k8s-service# nsenter --net=/run/docker/netns/lb_12uyuotr1  ip a l
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
25: eth0@if26: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450 qdisc noqueue state UP group default
    link/ether 02:42:0a:00:01:04 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 10.0.1.4/24 brd 10.0.1.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 10.0.1.2/32 scope global eth0
       valid_lft forever preferred_lft forever
    inet 10.0.1.5/32 scope global eth0
       valid_lft forever preferred_lft forever
```

在某个终端中使用命令  docker exec -it demo_client.1.dgjvk7xvktsocf91mme1uport  telnet nginx 80 从 client 访问 nginx service 服务，同时在另一个终端监听 TCP 已经建立的连接，如下所示：

![](/images/2023-09-16-kubernetes-service/2.png)

由于 IPVS 还在 conntrack 表中维护连接状态，因此我们可以在 conntrack 表中找到连接的实际目的地址，如下所示：
```bash
# one terminal
root@instance-00qqerhq:~/learn-k8s-service# docker exec -it demo_client.1.dgjvk7xvktsocf91mme1uport  telnet nginx 80
Trying 10.0.1.5...
Connected to nginx.
Escape character is '^]'.

# another terminal
root@instance-00qqerhq:~/learn-k8s-service# ls /run/docker/netns/
1-12uyuotr1n  1ee4c32438f9  1-vjce63xv8u  2ceed1c3dd11  d9fb8bb00f1a  ingress_sbox  lb_12uyuotr1
root@instance-00qqerhq:~/learn-k8s-service# nsenter -t 262318 -n netstat -an |grep EST
tcp        0      0 10.0.1.3:60744          10.0.1.5:80             ESTABLISHED
root@instance-00qqerhq:~/learn-k8s-service# nsenter --net=/run/docker/netns/lb_12uyuotr1 conntrack -L |grep 60744
conntrack v1.4.5 (conntrack-tools): 2 flow entries have been shown.
tcp      6 431990 ESTABLISHED src=10.0.1.3 dst=10.0.1.5 sport=60744 dport=80 src=10.0.1.7 dst=10.0.1.4 sport=80 dport=60744 [ASSURED] mark=0 use=1
```
![](/images/2023-09-16-kubernetes-service/3.png)

在上图中，telnet 连接到的是 10.0.1.7:80 (nginx-2)。
上述实现原理是首先为每个容器识别特定的 overlay 网络，然后找到负载均衡器网络命名空间。然后，它在 conntrack 表中查找最终要连接的实际目标地址。

# 基于 Kubernetes Kube Proxy

搭建 Kubernetes 集群，如下所示：
```bash
kind create cluster  --image=kindest/node:v1.22.17 --name  tanjunchen
```

部署 nginx 应用与服务，如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service# kubectl create deployment nginx --image=nginx --replicas=2
root@instance-00qqerhq:~/learn-k8s-service# kubectl expose deployment nginx --port=80
root@instance-00qqerhq:~/learn-k8s-service# kubectl get pods -l app=nginx -o wide
NAME                     READY   STATUS    RESTARTS   AGE   IP           NODE                       NOMINATED NODE   READINESS GATES
nginx-6799fc88d8-jzpgb   1/1     Running   0          94s   10.244.0.6   tanjunchen-control-plane   <none>           <none>
nginx-6799fc88d8-xddbz   1/1     Running   0          94s   10.244.0.5   tanjunchen-control-plane   <none>           <none>
root@instance-00qqerhq:~/learn-k8s-service# kubectl get services -l app=nginx
NAME    TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
nginx   ClusterIP   10.96.72.53   <none>        80/TCP    44s
root@instance-00qqerhq:~/learn-k8s-service#  kubectl get endpoints -l app=nginx
NAME    ENDPOINTS                     AGE
nginx   10.244.0.5:80,10.244.0.6:80   49s
```

运行另一个 pod 并通过 telnet 调用 nginx，如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service# kubectl run --rm client -it --image arunvelsriram/utils sh
If you don't see a command prompt, try pressing enter.
telnet nginx 80
Trying 10.96.72.53...
Connected to nginx.default.svc.cluster.local.
Escape character is '^]'.

root@instance-00qqerhq:~/learn-k8s-service# kubectl exec -it client --  netstat -an |grep EST
tcp        0      0 10.244.0.11:35408       10.96.72.53:80          ESTABLISHED
```

从客户端 Pod 的角度来看，它连接到 10.96.72.53:80。客户端实际上连接到我们的某个 nginx pod。然而问题来了：这是怎么发生的，我们如何确定客户端连接到的具体 nginx pod？
创建服务时，Kubernetes（特别是 kube-proxy）建立了 iptables 规则，便于流量导向到具体的 nginx pod，这些规则将传入流量的目标 IP 地址更改为某个 nginx pod 的 Pod IP 地址，整体的网络架构如下所示：

![](/images/2023-09-16-kubernetes-service/4.svg)

因此，我们可以在 node 节点上 root 网络命名空间内的 conntrack 表中识别连接的转换地址，如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service# kubectl exec -it client --  netstat -an |grep EST
tcp        0      0 10.244.0.13:52372       10.96.72.53:80          ESTABLISHED
root@tanjunchen-control-plane:/# conntrack -L | grep 52372
tcp      6 86374 ESTABLISHED src=10.244.0.13 dst=10.96.72.53 sport=52372 dport=80 src=10.244.0.6 dst=10.244.0.13 sport=80 dport=52372 [ASSURED] mark=0 use=1
conntrack v1.4.6 (conntrack-tools): 194 flow entries have been shown.
```

当数据包从服务器传输到客户端时，Linux 内核会在 conntrack 表中查找相应的连接，这就是 conntrack 表中第二个 IP:PORT 以相反顺序出现的原因。在本场景中，client 已建立到 10.244.0.6:80 (nginx-pod-2) 的连接。

# 基于 Istio Service Mesh

现在让我们看看相同的场景，在 Istio Service Mesh 下 client 访问 nginx service 是如何通信的。安装 istio，具体安装教程可参考 [istio-install](https://istio.io/latest/docs/setup/getting-started/)。

nginx 服务注入 sidecar，环境如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service# kubectl label namespace default istio-injection=enabled --overwrite
namespace/default not labeled
root@instance-00qqerhq:~/learn-k8s-service# kubectl get pod -owide
NAME                     READY   STATUS        RESTARTS   AGE     IP            NODE                       NOMINATED NODE   READINESS GATES
client                   2/2     Running       0          5m20s   10.244.0.20   tanjunchen-control-plane   <none>           <none>
nginx-6799fc88d8-8cqzc   2/2     Running       0          10m     10.244.0.17   tanjunchen-control-plane   <none>           <none>
nginx-6799fc88d8-gslqf   2/2     Running       0          10m     10.244.0.18   tanjunchen-control-plane   <none>           <none>
node-shell-debug-7fld8   1/1     Running       0          10m     172.18.0.2    tanjunchen-control-plane   <none>           <none>
root@instance-00qqerhq:~/learn-k8s-service# kubectl get svc
NAME         TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)   AGE
kubernetes   ClusterIP   10.96.0.1     <none>        443/TCP   50m
nginx        ClusterIP   10.96.72.53   <none>        80/TCP    48m
```

现在让我们运行一个客户端 pod 并连接到 nginx 服务，如下所示：

![](/images/2023-09-16-kubernetes-service/5.png)

从 client 的角度来看，一切都没有改变，和之前一样连接到 nginx 服务 IP。iptables 规则继续存在于 Node 上的 root 网络命名空间中，但是 conntrack 表中不再有相关记录，这是因为来自客户端的出站数据包现在直接在 Pod 的当前网络命名空间内被拦截，整体的网络架构如下所示：

![](/images/2023-09-16-kubernetes-service/6.svg)

Istio 会将 sidecar 代理注入 pod，其组件 Pilot-agent 会配置 iptables 并将所有出站流量重定向到同一网络命名空间内的 Envoy 代理，以进行进一步处理。如上述测试得知，我们可以在客户端 Pod 的网络命名空间中查找相关的 conntrack 表条目，我们实际看到的连接目的地是 127.0.0.1:15001（envoy），如下图所示：

![](/images/2023-09-16-kubernetes-service/7.png)

# 基于 Cilium

Cilium 是 Kubernetes 最强大的 CNI 网络插件之一，它不仅提供基本的网络和安全功能，还提供基于 eBPF 替代 Kubernetes 的 kube-proxy 实现 Service通信功能。搭建 Cilium 环境，更多详情参考 [cilium-install](https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/#k8s-install-quick)。

搭建 Kubernetes 集群（没有 CNI 与 kube-proxy 组件），如下所示：
```bash
kind create cluster --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true   # do not install kindnet
  kubeProxyMode: none       # do not run kube-proxy
nodes:
- role: control-plane
- role: worker
- role: worker
- role: worker
EOF
```
![](/images/2023-09-16-kubernetes-service/8.png)

查看 k8s 集群中的 kube-apiserver 的地址，如下所示：

![](/images/2023-09-16-kubernetes-service/9.png)

安装 Cilium。
```bash
helm repo add cilium https://helm.cilium.io/

helm repo update
 
helm install cilium cilium/cilium \
  --set k8sServiceHost=172.18.0.5 \ # k8s api-server 地址
  --set k8sServicePort=6443 \  # k8s api-server 端口
  --set global.kubeProxyReplacement="strict" \
  --namespace kube-system
```

![](/images/2023-09-16-kubernetes-service/10.png)

![](/images/2023-09-16-kubernetes-service/11.png)

现在，我们再次使用 nginx 服务和 telnet 命令进行测试。
```bash
# one terminal
root@instance-00qqerhq:~/learn-k8s-service# kubectl run --rm client -it --image arunvelsriram/utils sh
$ telnet nginx 80
Trying 10.96.43.209...
Connected to nginx.default.svc.cluster.local.
Escape character is '^]'.

# another terminal
root@instance-00qqerhq:~/learn-k8s-service# kubectl exec -it client --  netstat -an|grep EST
tcp        0      0 10.0.1.90:59668         10.96.43.209:80         ESTABLISHED
root@instance-00qqerhq:~/learn-k8s-service# kubectl  exec -ti cilium-bb22l  -n kube-system -- cilium bpf ct list global|grep 59668
Defaulted container "cilium-agent" out of: cilium-agent, config (init), mount-cgroup (init), apply-sysctl-overwrites (init), mount-bpf-fs (init), clean-cilium-state (init), install-cni-binaries (init)
TCP OUT 10.96.43.209:80 -> 10.0.1.90:59668 service expires=475561 RxPackets=0 RxBytes=7 RxFlagsSeen=0x00 LastRxReport=0 TxPackets=0 TxBytes=0 TxFlagsSeen=0x12 LastTxReport=453961 Flags=0x0010 [ SeenNonSyn ] RevNAT=5 SourceSecurityID=0 IfIndex=0
TCP IN 10.0.1.90:59668 -> 10.0.1.108:80 expires=475561 RxPackets=2 RxBytes=140 RxFlagsSeen=0x12 LastRxReport=453961 TxPackets=1 TxBytes=74 TxFlagsSeen=0x12 LastTxReport=453961 Flags=0x0010 [ SeenNonSyn ] RevNAT=0 SourceSecurityID=27453 IfIndex=0
TCP OUT 10.0.1.90:59668 -> 10.0.1.108:80 expires=475561 RxPackets=1 RxBytes=74 RxFlagsSeen=0x12 LastRxReport=453961 TxPackets=2 TxBytes=140 TxFlagsSeen=0x12 LastTxReport=453961 Flags=0x0010 [ SeenNonSyn ] RevNAT=5 SourceSecurityID=27453 IfIndex=0
root@instance-00qqerhq:~/learn-k8s-service# kubectl get pod -owide
NAME                    READY   STATUS    RESTARTS   AGE     IP           NODE           NOMINATED NODE   READINESS GATES
client                  1/1     Running   0          3m30s   10.0.1.90    kind-worker2   <none>           <none>
nginx-76d6c9b8c-6d6fz   1/1     Running   0          14m     10.0.3.202   kind-worker3   <none>           <none>
nginx-76d6c9b8c-84qkd   1/1     Running   0          14m     10.0.1.108   kind-worker2   <none>           <none>
root@instance-00qqerhq:~/learn-k8s-service# kubectl get svc
NAME         TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
kubernetes   ClusterIP   10.96.0.1      <none>        443/TCP   34m
nginx        ClusterIP   10.96.43.209   <none>        80/TCP    15m
```

从 client 的角度来看，一切都没有改变，和之前一样连接到服务 IP。由于我们搭建的 Kubernetes 集群没有安装 kube-proxy，因此 conntrack 表中没有与此连接相关的条目，整体的网络架构如下所示：

![](/images/2023-09-16-kubernetes-service/12.svg)

Cilium 拦截所有请求 nginx 服务 IP 的流量，并将其转发到 eBPF Map 中对应的 pod IP。为了执行反向网络地址转换功能，Cilium 在 eBPF Map 上维护自己的连接跟踪表。检查此表，我们可以使用 cilium pod 中的 cilium CLI 工具，如下所示：
```bash
root@instance-00qqerhq:~/learn-k8s-service# kubectl  exec -ti cilium-bb22l  -n kube-system -- cilium bpf ct list global |  grep 59668
Defaulted container "cilium-agent" out of: cilium-agent, config (init), mount-cgroup (init), apply-sysctl-overwrites (init), mount-bpf-fs (init), clean-cilium-state (init), install-cni-binaries (init)
TCP OUT 10.96.43.209:80 -> 10.0.1.90:59668 service expires=475561 RxPackets=0 RxBytes=7 RxFlagsSeen=0x00 LastRxReport=0 TxPackets=0 TxBytes=0 TxFlagsSeen=0x12 LastTxReport=453961 Flags=0x0010 [ SeenNonSyn ] RevNAT=5 SourceSecurityID=0 IfIndex=0
TCP IN 10.0.1.90:59668 -> 10.0.1.108:80 expires=475561 RxPackets=2 RxBytes=140 RxFlagsSeen=0x12 LastRxReport=453961 TxPackets=1 TxBytes=74 TxFlagsSeen=0x12 LastTxReport=453961 Flags=0x0010 [ SeenNonSyn ] RevNAT=0 SourceSecurityID=27453 IfIndex=0
TCP OUT 10.0.1.90:59668 -> 10.0.1.108:80 expires=475561 RxPackets=1 RxBytes=74 RxFlagsSeen=0x12 LastRxReport=453961 TxPackets=2 TxBytes=140 TxFlagsSeen=0x12 LastTxReport=453961 Flags=0x0010 [ SeenNonSyn ] RevNAT=5 SourceSecurityID=27453 IfIndex=0
```

如图所示，客户端 client pod 连接到 10.0.1.108:80 (nginx-pod-2)。

# 总结

在我们的学习过程中，首先我们探讨了在 Docker Swarm 集群模式下，服务之间是如何进行通信的。我们了解到，Docker Swarm 使用内置的服务发现和负载均衡机制来实现服务间的通信。然后，我们转向 Kubernetes，研究了在 kube-proxy、Istio Service Mesh 和 Cilium 三种模式下服务到服务的通信机制。在 kube-proxy 模式下，我们了解到它使用 Iptables 或者 IPVS 来实现服务的负载均衡。而在 Istio Service Mesh 模式下，服务间的通信是通过 Envoy 代理来实现的，它提供了丰富的流量控制和安全策略。最后，在 Cilium 模式下，我们学习了它是如何利用 BPF（Berkeley Packet Filter）来实现服务通信的。这三种模式各有特点，为我们提供了丰富的选择来满足不同的服务通信需求。

# 参考

1. https://docs.docker.com/network/drivers/overlay/
2. https://istio.io/latest/docs/setup/getting-started/
3. https://cilium.io/
 