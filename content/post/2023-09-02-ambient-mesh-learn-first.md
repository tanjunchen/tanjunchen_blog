---
layout:     post
title:      "初识 Istio Ambient Mesh 新模式"
subtitle:   "初步了解 Istio 新数据平面 Ambient，目前 Ambient 尚处于 Alpha 阶段，Sidecar 模式依然是首选，但我相信 Ambient 模式是未来很好的选择。"
description: "Ambient Mesh，这是 Istio 提供的一种新的数据平面模式，旨在简化操作，提供更广泛的应用兼容性，并降低基础设施的成本。Ambient mesh 使得用户可以选择使用一种可以集成到其基础设施中的 Mesh 数据平面，而不是需要和应用一起部署的 sidecar。同时，该模式可以提供和 Sidecar 模式相同的零信任安全、遥测和流量管理等 Istio 的核心功能。目前 Ambient mesh 处于 alpha 阶段。"
author: "陈谭军"
date: 2023-09-02
published: true
tags:
    - ambient-mesh
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

Ambient Mesh，这是 Istio 提供的一种新的数据平面模式，旨在简化操作，提供更广泛的应用兼容性，并降低基础设施的成本。Ambient mesh 使得用户可以选择使用一种可以集成到其基础设施中的 Mesh 数据平面，而不是需要和应用一起部署的 sidecar。同时，该模式可以提供和 Sidecar 模式相同的零信任安全、遥测和流量管理等 Istio 的核心功能，目前 Ambient mesh 处于 alpha 阶段。

# 安装 Ambient Mesh

**前提条件**  
1. 要求 Kubernetes 版本 1.24, 1.25, 1.26, 1.27+。
2. istio 1.18+。

*Ambient 目前处于 alpha，alpha 版本中存在已知的性能、稳定性和安全问题，请不要在生产环境中使用。ambient 目前需要使用 istio-cni 来配置 Kubernetes 网络规则，istio-cni 模式目前不支持某些 CNI 类型（即不使用 veth 设备的 CN，如桥接模式）。*

下载最新版本的 [Istio](https://github.com/istio/istio/releases)，其中 alpha 版本提供对 ambient mesh 的支持。  
使用 Kind 部署 Kubernetes 集群。
```bash
kind create cluster --config=- <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ambient
nodes:
- role: control-plane
- role: worker
- role: worker
EOF
```
![](/images/2023-09-02-ambient-mesh-learn-first/1.png)

如果我们的 Kubernetes 集群不支持 Kubernetes Gateway CRDs，可以参考以下方式安装。

```bash
kubectl get crd gateways.gateway.networking.k8s.io &> /dev/null || \
 { kubectl kustomize "github.com/kubernetes-sigs/gateway-api/config/crd/experimental?ref=v0.6.1" | kubectl apply -f -; }
```

使用 istioctl 安装 Istio 集群

```bash
istioctl install --set profile=ambient --skip-confirmation
```

![](/images/2023-09-02-ambient-mesh-learn-first/2.png)

![](/images/2023-09-02-ambient-mesh-learn-first/3.png)

运行上述命令后，如下所示，相关组件（含 ztunnel）已成功安装。

![](/images/2023-09-02-ambient-mesh-learn-first/4.png)

ambient profile 在集群中安装了 Istiod, ingress gateway, ztunnel 和 istio-cni 组件。其中 ztunnel 和 istio-cni 以 daemonset 方式部署在每个 node 上。istio-cni 用于检测 pod 是否处于 ambient 模式，监听并且同步创建与更新 pod 出向流量和入向流量重定向到 node 的 ztunnel 的 iptables 规则。

# 部署 demo 应用

执行下面的命令，部署 demo 测试应用，我们使用 Istio 官网示例 bookinfo 应用程序。确保 default 命名空间不包含标签 `istio-injection=enabled`。

```bash
kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml
kubectl apply -f samples/sleep/sleep.yaml
kubectl apply -f samples/sleep/notsleep.yaml
```

应用列表如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/5-1.png)

部署入口网关，我们可以从集群外部访问 bookinfo 应用程序。

```bash
kubectl apply -f samples/bookinfo/networking/bookinfo-gateway.yaml
```

配置 Istio 入口网关环境变量。

```bash
export GATEWAY_HOST=istio-ingressgateway.istio-system
export GATEWAY_SERVICE_ACCOUNT=ns/istio-system/sa/istio-ingressgateway-service-account

kubectl exec deploy/sleep -- curl -s "http://$GATEWAY_HOST/productpage" | grep -o "<title>.*</title>"
kubectl exec deploy/sleep -- curl -s http://productpage:9080/ | grep -o "<title>.*</title>"
kubectl exec deploy/notsleep -- curl -s http://productpage:9080/ | grep -o "<title>.*</title>"
```

测试结果如下所示，bookinfo 应用程序可以在有或没有网关的情况下都能正确访问。

![](/images/2023-09-02-ambient-mesh-learn-first/6.png)

# 纳管 demo 应用到 Ambient Mesh

为 default namespace 打上标签来将该 namespace 中的所有应用加入 `ambient mesh` 中。
```bash
kubectl label namespace default istio.io/dataplane-mode=ambient
```

我们查看 `istio-cni` 的日志，可以看到 `istio-cni` 为 `default` 命名空间下的应用 pod 创建了相应的路由规则：
```bash
kubectl -n istio-system logs -f istio-cni-node-wf4rz
2023-08-28T10:57:57.293344Z	info	ambient	Namespace default is enabled in ambient mesh
2023-08-28T10:57:57.293403Z	info	ambient	Namespace istio-system is disabled from ambient mesh
2023-08-28T11:36:14.314354Z	info	cni	istio-cni cmdAdd podName: details-v1-5ffd6b64f7-zmcjx podIPs: [{IP:10.244.1.23 Mask:ffffff00}]
2023-08-28T11:36:14.314683Z	info	cni	Adding pod 'details-v1-5ffd6b64f7-zmcjx/default' (fdd0a7d4-b360-4df1-bc81-2a1808906233) to ipset
2023-08-28T11:36:14.314688Z	info	cni	Adding route for details-v1-5ffd6b64f7-zmcjx/default: [table 100 10.244.1.23/32 via 192.168.126.2 dev istioin src 10.244.1.1]
2023-08-28T11:36:14.356859Z	info	cni	istio-cni cmdAdd podName: productpage-v1-8b588bf6d-qrbnw podIPs: [{IP:10.244.1.24 Mask:ffffff00}]
2023-08-28T11:36:14.356927Z	info	cni	Adding pod 'productpage-v1-8b588bf6d-qrbnw/default' (44f702b9-98ae-4e78-b630-e0ae77428dd3) to ipset
2023-08-28T11:36:14.356935Z	info	cni	Adding route for productpage-v1-8b588bf6d-qrbnw/default: [table 100 10.244.1.24/32 via 192.168.126.2 dev istioin src 10.244.1.1]
2023-08-28T11:36:14.373139Z	info	cni	istio-cni cmdAdd podName: ratings-v1-5f9699cfdf-ncvqw podIPs: [{IP:10.244.1.22 Mask:ffffff00}]
2023-08-28T11:36:14.373186Z	info	cni	Adding pod 'ratings-v1-5f9699cfdf-ncvqw/default' (725b2415-0de4-4fd4-b3c4-47d6f60c2d5a) to ipset
2023-08-28T11:36:14.373206Z	info	cni	Adding route for ratings-v1-5f9699cfdf-ncvqw/default: [table 100 10.244.1.22/32 via 192.168.126.2 dev istioin src 10.244.1.1]
2023-08-28T11:36:14.673081Z	info	cni	istio-cni cmdAdd podName: reviews-v1-569db879f5-24l6k podIPs: [{IP:10.244.1.25 Mask:ffffff00}]
2023-08-28T11:36:14.673123Z	info	cni	Adding pod 'reviews-v1-569db879f5-24l6k/default' (abace4b5-872a-47e9-b3ae-9dacee882785) to ipset
2023-08-28T11:36:14.673130Z	info	cni	Adding route for reviews-v1-569db879f5-24l6k/default: [table 100 10.244.1.25/32 via 192.168.126.2 dev istioin src 10.244.1.1]
2023-08-28T11:36:14.993462Z	info	cni	istio-cni cmdAdd podName: reviews-v2-65c4dc6fdc-ncnjs podIPs: [{IP:10.244.1.27 Mask:ffffff00}]
2023-08-28T11:36:14.993618Z	info	cni	Adding pod 'reviews-v2-65c4dc6fdc-ncnjs/default' (967839fe-ad67-49b8-85ed-d9f4179da260) to ipset
2023-08-28T11:36:14.993626Z	info	cni	Adding route for reviews-v2-65c4dc6fdc-ncnjs/default: [table 100 10.244.1.27/32 via 192.168.126.2 dev istioin src 10.244.1.1]
2023-08-28T11:36:15.300465Z	info	cni	istio-cni cmdAdd podName: reviews-v3-c9c4fb987-4ft5g podIPs: [{IP:10.244.1.26 Mask:ffffff00}]
2023-08-28T11:36:15.300538Z	info	cni	Adding pod 'reviews-v3-c9c4fb987-4ft5g/default' (5f1119df-b3d6-47fd-b5c3-7bb15b2d7fdd) to ipset
2023-08-28T11:36:15.300542Z	info	cni	Adding route for reviews-v3-c9c4fb987-4ft5g/default: [table 100 10.244.1.26/32 via 192.168.126.2 dev istioin src 10.244.1.1]
```

发起测试请求，如下所示：
```bash
kubectl exec deploy/sleep -- curl -s "http://$GATEWAY_HOST/productpage" | grep -o "<title>.*</title>"
kubectl exec deploy/sleep -- curl -s http://productpage:9080/ | grep -o "<title>.*</title>"
kubectl exec deploy/notsleep -- curl -s http://productpage:9080/ | grep -o "<title>.*</title>"
```

测试结果，如下所示：
![](/images/2023-09-02-ambient-mesh-learn-first/6-1.png)

istio-system 命名空间下的 ztunnel Pod 列表如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/7.png)

![](/images/2023-09-02-ambient-mesh-learn-first/8.png)

查看 node 节点上的 sleep 与 productpage 对应的 ztunnel 访问日志，sleep 所在 node 上的 ztunnel 日志（outbound 请求），如下所示：
```bash
kubectl -n istio-system logs -f ztunnel-w5zvr
2023-08-28T11:39:33.716634Z  INFO outbound{id=86e9d44b9a866661edd61c102465805e}: ztunnel::proxy::outbound: proxy to 10.244.1.24:9080 using HBONE via 10.244.1.24:15008 type Direct
2023-08-28T11:39:33.756833Z  INFO outbound{id=86e9d44b9a866661edd61c102465805e}: ztunnel::proxy::outbound: complete dur=42.17475ms
```
![](/images/2023-09-02-ambient-mesh-learn-first/9.png)

productpage 所在 node 上的 ztunnel 日志（inbound 请求），如下所示：
```bash
kubectl -n istio-system logs -f ztunnel-8k6cp
2023-08-28T11:41:06.835522Z  INFO inbound{id=7fb5b4259eaf43c599f8d9f4fe2c5657 peer_ip=10.244.2.9 peer_id=spiffe://cluster.local/ns/default/sa/sleep}: ztunnel::proxy::inbound: got CONNECT request to 10.244.1.24:9080
```

因为 ambient 只开启了 L4，流量只会通过 ztunnel ，不会经过 waypoint proxy。此时应用程序的流量路径如下图所示：
![](/images/2023-09-02-ambient-mesh-learn-first/10.svg)

**使用 Prometheus**

按照文档 https://istio.io/latest/docs/ops/integrations/prometheus/#installation，部署 Prometheus。

**使用 Kiali**

按照文档 https://istio.io/latest/docs/ops/integrations/kiali/#installation，部署 Kiali。按照上述请求方式给 productpage 发送请求，kiali 流量拓扑图如下所示：
![](/images/2023-09-02-ambient-mesh-learn-first/11.png)

# 为 Ambient Mesh 启用安全策略

使用 L4 授权策略来保护应用程序访问，可以根据客户端工作负载身份来控制对服务的访问。以下案例只允许 sleep 和 gateway serviceaccount 调用 productpage 服务。
```yaml
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
 name: productpage-viewer
 namespace: default
spec:
 selector:
   matchLabels:
     app: productpage
 action: ALLOW
 rules:
 - from:
   - source:
       principals:
       - cluster.local/ns/default/sa/sleep
       - cluster.local/$GATEWAY_SERVICE_ACCOUNT
EOF
```
我们发现，sleep 服务可以访问 productpage，而 notsleep 不行，符合预期，访问结果如下所示：
![](/images/2023-09-02-ambient-mesh-learn-first/12.png)

# Ambient Mesh 启用 L7 功能

使用 Kubernetes Gateway API 来启用某个服务的 L7 功能，创建下面的 gateway，为 productpage 服务开启七层处理。任何流向 productpage 服务的流量都将由第 7 层(L7) 代理进行管理。为 productpage 部署 waypoint proxy，如下所示：
```bash
istioctl x waypoint apply --service-account bookinfo-productpage
```
![](/images/2023-09-02-ambient-mesh-learn-first/13.png)

istioctl x waypoint 默认生成的 Gateway 如下所示：
```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: Gateway
metadata:
  name: bookinfo-productpage
  namespace: default
spec:
  gatewayClassName: istio-waypoint
  listeners:
  - allowedRoutes:
      namespaces:
        from: Same
    name: mesh
    port: 15008
    protocol: ALL
```

istio-waypoint 会通过 Kubernetes Gateway 产生 bookinfo-productpage-istio-waypoint deploy 工作负载（istio-proxy 镜像），作为 productpage L7 流量管理的组件。此时可以查看到 Istio 创建的 waypoint proxy 如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/14.png)
![](/images/2023-09-02-ambient-mesh-learn-first/15.png)

重新使用 sleep 访问 productpage，如下所示：
![](/images/2023-09-02-ambient-mesh-learn-first/16.png)

```bash
kubectl exec deploy/sleep -- curl -s http://productpage:9080/ | grep -o "<title>.*</title>"
```

查看 node 节点上的 sleep 与 productpage 对应的 ztunnel 访问日志。

sleep 所在 node 上的 ztunnel 日志（outbound 请求）如下所示：
```bash
kubectl -n istio-system logs -f ztunnel-w5zvr
2023-08-28T11:48:01.666338Z  INFO outbound{id=e69949c7ec4f07f497e5fb9460f520d5}: ztunnel::proxy::outbound: proxy to 10.96.138.243:9080 using HBONE via 10.244.1.28:15008 type ToServerWaypoint
2023-08-28T11:48:01.708804Z  INFO outbound{id=e69949c7ec4f07f497e5fb9460f520d5}: ztunnel::proxy::outbound: complete dur=43.172542ms
```

productpage 所在 node 上的 ztunnel 日志（inbound 请求），如下所示：
```bash
kubectl -n istio-system logs -f ztunnel-8k6cp
2023-08-28T11:49:36.808574Z  INFO inbound{id=d691e6a37a21a781b30fee7d7401f4f3 peer_ip=10.244.1.28 peer_id=spiffe://cluster.local/ns/default/sa/bookinfo-productpage-istio-waypoint}: ztunnel::proxy::inbound: got CONNECT request to 10.244.1.24:9080
bookinfo-productpage-istio-waypoint-68cb5fb4d6-pxzbr Pod 中的日志如下所示：
{"start_time":"2023-08-28T11:59:07.644Z","upstream_host":"envoy://connect_originate/10.244.1.24:9080","authority":"productpage:9080","connection_termination_details":null,"response_code":200,"requested_server_name":null,"downstream_remote_address":"envoy://internal_client_address/","upstream_local_address":"envoy://internal_client_address/","method":"GET","user_agent":"curl/8.2.1","downstream_local_address":"10.96.138.243:9080","x_forwarded_for":null,"route_name":"default","bytes_sent":1683,"upstream_transport_failure_reason":null,"path":"/","upstream_cluster":"inbound-vip|9080|http|productpage.default.svc.cluster.local","bytes_received":0,"response_code_details":"via_upstream","response_flags":"-","upstream_service_time":"10","request_id":"66401a61-0656-4838-9d84-df03448355f9","protocol":"HTTP/1.1","duration":11}
{"duration":2,"route_name":"default","authority":"productpage:9080","bytes_sent":1683,"upstream_host":"envoy://connect_originate/10.244.1.24:9080","protocol":"HTTP/1.1","start_time":"2023-08-28T11:59:08.924Z","upstream_cluster":"inbound-vip|9080|http|productpage.default.svc.cluster.local","response_code":200,"request_id":"ab4922ee-f733-4625-84e3-f5c045d979e8","upstream_transport_failure_reason":null,"response_flags":"-","user_agent":"curl/8.2.1","x_forwarded_for":null,"bytes_received":0,"method":"GET","downstream_local_address":"10.96.138.243:9080","requested_server_name":null,"connection_termination_details":null,"downstream_remote_address":"envoy://internal_client_address/","upstream_service_time":"2","response_code_details":"via_upstream","path":"/","upstream_local_address":"envoy://internal_client_address/"}
```

可以从上面的日志中看到 (ToServerWaypoint) 标志，并且 bookinfo-productpage-istio-waypoint Envoy 有 access_log，说明请求经过 waypoint proxy，此时应用程序的流量路径如下图所示：

![](/images/2023-09-02-ambient-mesh-learn-first/17.svg)

使用 L7 授权策略来保护应用程序访问，可以根据客户端工作负载身份来控制对服务的访问。以下案例只允许 sleep 和 gateway serviceaccount 调用productpage 服务。
```bash
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
 name: productpage-viewer
 namespace: default
spec:
 selector:
   matchLabels:
     istio.io/gateway-name: bookinfo-productpage
 action: ALLOW
 rules:
 - from:
   - source:
       principals:
       - cluster.local/ns/default/sa/sleep
       - cluster.local/$GATEWAY_SERVICE_ACCOUNT
   to:
   - operation:
       methods: ["GET"]
EOF
```

我们发现，sleep 服务只支持 GET 方法访问 productpage，其他服务与方法都不行，符合预期，访问结果如下所示：
![](/images/2023-09-02-ambient-mesh-learn-first/18.png)

# Ambient Mesh 配置 L7 流量管理

同理，我们通过创建 gateway 为 review 服务启用 L7 能力。
```bash
istioctl x waypoint apply --service-account bookinfo-reviews
```

bookinfo-reviews Yaml 文件如下所示：
```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: Gateway
metadata:
  annotations:
    istio.io/for-service-account: bookinfo-reviews
  name: bookinfo-reviews
  namespace: default
spec:
  gatewayClassName: istio-waypoint
  listeners:
  - allowedRoutes:
      namespaces:
        from: Same
    name: mesh
    port: 15008
    protocol: ALL
```

分别通过 VirtualService 与 DestinationRule 创建路由策略，按 80/20 的比例将请求发送到 v1 和 v2 版本，如下所示：
```yaml
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:
    loadBalancer:
      simple: RANDOM
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
  - name: v3
    labels:
      version: v3
EOF

kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
    - reviews
  http:
  - route:
    - destination:
        host: reviews
        subset: v1
      weight: 80
    - destination:
        host: reviews
        subset: v2
      weight: 20
EOF
```

执行以下命令验证 10 个请求中大约 10% 的流量流向 Reviews-v2，测试结果符合预期，如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/19.png)

# 与其他 Mesh 对比 

我们简单来介绍 Mesh 周边生态（Istio、Ambient Mesh、Cilium Mesh等）与架构，并且做个对比。

Istio 架构如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/20.png)

Ambient Mesh 架构如下所示，L4 流程如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/21.png)

Ambient Mesh 架构如下所示，L7 流程如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/22.png)

Cilium Mesh 架构如下所示：

![](/images/2023-09-02-ambient-mesh-learn-first/23.png)

![](/images/2023-09-02-ambient-mesh-learn-first/24.png)

![](/images/2023-09-02-ambient-mesh-learn-first/24-2.png)

|     功能     |    Ambient Mesh     |   Istio Mesh  |  Cilium Mesh    |
| ----------- |      -----------     |   ----------- |----------- |
|   数据平面   |  No sidecar(ztunnel + waypoint-proxy 模式)    |  sidecar 模式  |  cilium-agent + Envoy  |
|      L4     |   ztunnel + istio-cni   |  istio-proxy                       |        cilium agent  |
|      L7     |  Ambient mesh 的每节点的 ztunnel 代理的固定开销较低，其 waypoint proxy 则可以动态伸缩，因此需要的资源预留总体上要少得多，资源开销较小，从而使集群的资源利用效率更高。 |  相比 Ambient Mesh，每个 Pod 需要单独为 istio-proxy 设置资源，资源开销较大    |  Envoy 是单节点部署，资源消耗较小   |
|  资源开销    |  ztunnel + waypoint-proxy     |  sidecar 模式  |  cilium-agent + Envoy  |
|  安全       |  较好    |  中等  |  较好  |
|  mtls       |  ztunnel    |  istio-proxy  |  cilium-agent + Envoy   |
|  per-proxy per-node 模式    |  否(部分)    |  否  |  是   |
|  支持 eBPF   |  支持    |  不支持  |  支持   |
|      ...    |                     |                  |            |

Cilium Mesh、Istio 和 Ambient Mesh 都是基于服务网格的解决方案，提供服务发现、负载均衡、流量管理、安全等功能，但技术实现和重点不同。Cilium Mesh 使用 Linux 内核 BPF 技术实现高效的数据包处理和过滤；Istio 使用 Envoy 代理实现流量管理、策略和认证授权等功能；Ambient Mesh 提供灵活的部署和扩容方案，并且支持基于社区标准的 API 协议。

# Ambient Mesh 总结

我们可以看到在 Ambient 模式下，我们不需要在对业务 Pod 注入 sidecar，将服务网格彻底下沉到了基础设施层面。原生 sidecar 功能由 ztunnel(L4) 与 waypoint proxy(L7) 提供支持，很好地解决了需要业务 pod template 增加 sidecar 模板问题。但是目前要为服务启用 L7 网格能力，必须显示创建一个 gateway(Kubernetes Gateway)，Istio 需要为每个服务账号创建一个 waypoint proxy deployment，步骤稍微繁琐，是个运维负担。目前 ambient 尚处于 alpha，sidecar 模式依然是首选，但我相信 ambient 模式是未来很好的选择。越来越多的产品 Mesh 化逐渐与 CNI 融合，使用 eBPF 进行网络加速。

# 卸载  Ambient Mesh

删除 default 命名空间 ambient-mesh 标识。
```bash
kubectl label namespace default istio.io/dataplane-mode-
```

删除 sleep 与 notsleep 应用。
```bash
kubectl delete -f samples/sleep/sleep.yaml
kubectl delete -f samples/sleep/notsleep.yaml
```

删除 Gateway API CRDs。
```bash
kubectl kustomize "github.com/kubernetes-sigs/gateway-api/config/crd/experimental?ref=v0.6.1" | kubectl delete -f -
```

删除 productpage-viewer 授权策略，waypoint 代理，卸载 istio。
```bash
kubectl delete authorizationpolicy productpage-viewer
istioctl x waypoint delete --service-account bookinfo-reviews
istioctl x waypoint delete --service-account bookinfo-productpage
istioctl uninstall -y --purge
kubectl delete namespace istio-system
```

# 为什么系列

**什么是 HBONE?**    
Ambient mesh 使用 HTTP CONNECT over mTLS 来实现其安全隧道，并在流量路径中插入 waypoint proxy，我们把这种模式称为 HBONE（HTTP-Based Overlay Network Environment）。HBONE 提供了比 TLS 本身更干净的流量封装，同时实现了与通用负载平衡器基础设施的互操作性。Ambient mesh 将默认使用 [FIPS](https://www.nist.gov/standardsgov/compliance-faqs-federal-information-processing-standards-fips#:~:text=are%20FIPS%20developed%3F-,What%20are%20Federal%20Information%20Processing%20Standards%20(FIPS)%3F,by%20the%20Secretary%20of%20Commerce.) 构建，以满足合规性需求。

![](/images/2023-09-02-ambient-mesh-learn-first/25.png)

ambient 模式采用了 [HTTP 的 CONNECT 方法](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/CONNECT)在 ztunnel 和 waypoint proxy 创建了一个隧道，通过该隧道来传输数据。

![](/images/2023-09-02-ambient-mesh-learn-first/26.png)

*备注：除了 HTTP CONNECT 以外，采用 HTTP GET 和 POST 也可以创建 HTTP 隧道，这种方式创建的隧道的原理是将 TCP 数据封装到 HTTP 数据包中发送到外部服务器，该外部服务器会提取并执行客户端的原始网络请求。外部服务器收到此请求的响应后，将其重新打包为 HTTP 响应，并发送回客户端。在这种方式中，客户端所有流量都封装在 HTTP GET 或者 POST 请求中。*

**Istio Ambient 是如何实现 HBONE?**    
采用 Envoy 来创建 HTTP CONNECT 隧道，并对隧道中的数据进行 HTTP 处理。
![](/images/2023-09-02-ambient-mesh-learn-first/27.png)

Istio HBONE 采用了上面介绍的方法来创建 HTTP CONNET 隧道，TCP 流量在进入隧道时会进行 mTLS 加密，在出隧道时进行 mTLS 卸载。一个采用 HBONE 创建的连接如下所示：
![](/images/2023-09-02-ambient-mesh-learn-first/28.png)

HBONE 由于采用了 HTTP CONNECT 创建隧道，还可以在 HTTP CONNECT 请求中加入一些 header 来很方便地在 downstream 和 upstream 之间传递上下文信息，包括：   
* authority - 请求的原始目的地址，例如 1.2.3.4:80。
* X-Forwarded-For（可选） - 请求的原始源地址，用于在多跳访问之间保留源地址。
* baggage (可选) - client/server 的一些元数据，在 telemetry 中使用。

具体可以参考 [Istio Ambient 模式流量管理实现机制详解 - HBONE 隧道原理](https://www.zhaohuabing.com/post/2022-09-11-ambient-deep-dive-1/)。

**什么是 ztunnel ？为什么 Istio 会使用 ztunnel？**  
ztunnel(Rust 编写) 实现了服务网格的核心功能：零信任。当为一个 namespace 启用 ambient 时，Istio 会创建一个安全覆盖层(secure overlay)，该安全覆盖层为工作负载提供 mTLS, 遥测和认证，以及 L4 权限控制，并不需要中断 HTTP 链接或者解析 HTTP 数据。  
![](/images/2023-09-02-ambient-mesh-learn-first/29.png)

**什么是 waypoint proxy？**  
当我们需要支持 L7 流量时，Istio 控制平面会配置集群中的 ztunnel，将所有需要进行 L7 处理的流量发送到 waypoint proxy。重要的是，从 Kubernetes 的角度来看，waypoint proxy（istio-proxy） 只是普通的 pod，可以像其他 Kubernetes 工作负载一样进行自动伸缩。由于 waypoint proxy 可以根据其服务的 namespace 的实时流量需求进行自动伸缩，而不是按照可能的最大工作负载进行配置，我们预计这将为用户节省大量资源。  
![](/images/2023-09-02-ambient-mesh-learn-first/30.png)

**abient mesh 为何不在本地节点（daemonset）上进行 L7 处理，而引入 waypoint?**    
* 多租户 -  Envoy 本质上并不支持多租户。因此如果共享 L7 代理，则需要在一个共享代理实例中对来自多个租户的 L7 流量一起进行复杂的规则处理，我们对这种做法有安全顾虑。通过严格限制只在共享代理中进行 L4 处理，我们大大减少了出现 CVE 的几率。
* 成本  -  与 waypoint proxy 所需的 L7 处理相比，ztunnel 所提供的 mTLS 和 L4 功能需要的 CPU 和内存占用要小得多。通过将 waypoint proxy 作为一个共享的 namespace 基本的资源来运行，我们可以根据该 namespace 的需求来对它们进独立伸缩，其成本不会不公平地分配给不相关的租户。
* 解耦  -  通过减少 ztunnel 的作用范围，我们可以很容易为 Istio 和 ztunnel 之间的互操作定义一个标准接口，并可以使用其他满足该标准接口的安全隧道的实现替换 ztunnel。

**在 ambient mesh 模式中，waypoint 与他服务的工作负载不在同一个 Node，增加的网络链路是不是成为性能问题？**  
* 事实上，Istio 的大部分网络延迟并不是来自于网络（现代的云供应商拥有极快的网络），而是来自于实现其复杂的功能特性所需的大量 L7 处理。sidecar 模式中每个连接需要两个 L7 处理步骤（both sidecar），而 ambient mesh 将这两个步骤合并成 one sidecar。在大多数情况下，我们认为这种减少的处理成本能够补偿额外的网络跳数带来的延迟。
* 在部署 Mesh 时，用户往往首先启用零信任安全，然后再根据需要选择性地启用 L7 功能。Ambient mesh 允许这些用户在不需要 L7 处理时完全避开其带来的成本。
 
**CNI ptp 与 bridge 网络模式是？**   
关于 bridge 桥接模式可以参考 [cni-bridge](https://www.cni.dev/plugins/current/main/bridge/)，关于 ptp 网络模型可以参考 [cni-ptp](https://www.cni.dev/plugins/current/main/ptp/)。ambient 目前还不支持 [bridige](https://www.cni.dev/plugins/current/main/bridge/) 模式。pod 和 node 通过 [ptp](https://www.cni.dev/plugins/current/main/ptp/) 方式连接，即 pod 和 node 之间通过一个 veth pair 连接，并通过设置 node 上的路由规则来打通 pod 和 node 之间的网络。

**ztunnel 是如何实现流量劫持的？**    
Istio 采用了 iptables 规则、策略路由[Policy-based Routing](https://en.wikipedia.org/wiki/Policy-based_routing)、TPROXY 等 linux 网络工具来将应用 pod 的流量转发到 ztunnel。Ambient 模式修改了 node 上的 iptables 规则和路由，和某些 k8s cni 插件可能出现冲突。相对而言，sidecar 模式只会影响到 pod 自身的 network namespace，和 k8s cni 的兼容性较好。ambient 模式目前只支持 ptp 类型的 k8s 网络，bridige 模式目前还不支持。

outbound 流量劫持  outbound 方向的流量劫持主要涉及两个步骤：
1. 采用 node 上的 iptables 规则和策略路由将应用 pod 的 outbound 流量路由到 ztunnel pod。
2. 采用 TPROXY 将进入 ztunnel pod 的 outbound 流量重定向到 envoy 的 15001 端口。   

![](/images/2023-09-02-ambient-mesh-learn-first/31.png)

inbound 流量劫持 inbound 方向的流量劫持和 outbound 类似，也主要涉及两个步骤：
1. 采用 node 上的策略路由将应用 pod 的 inbound 流量路由到 ztunnel pod。
2. 采用 TPROXY 将进入 ztunnel pod 的 inbound 流量重定向到 envoy 的 15006 和 15008 端口。其中 15006 处理 plain tcp 数据，15008 处理 tls 数据。  

![](/images/2023-09-02-ambient-mesh-learn-first/32.png)

*目前的 iptables 应该还会设置 mark 来跟踪，只有首包会走到 istioout 和 istioin，后续的包会走到 0x400 的 mark 直接走 veth pair 不封包了。抓包的话也可以看到只有 SYN 到了 istioin 的网卡。大家可以试试。* 具体可以参考 [Istio Ambient 模式流量管理实现机制详解 - ztunnel 流量劫持](https://www.zhaohuabing.com/post/2022-09-11-ambient-deep-dive-2/)

**什么是 istio-cni？为什么 Istio 提供 istio-cni？**    
默认情况下，Istio 需要在网格中部署的 pod 中注入一个 init 容器 istio-init。istio-init 容器初始化拦截 Pod 进出流量到 sidecar iptables 规则。istio-init 要求将 pod 部署到网格的用户或服务帐户拥有足够的 Kubernetes RBAC 权限来部署具有 NET_ADMIN 和 NET_RAW 功能的容器。  

*注意：Istio CNI 插件作为链式 CNI 插件运行，它设计与其他 CNI 插件（例如 PTP 或 Calico）一起使用。 有关详细信息，请参阅与其他 CNI 插件，见 [CNI 兼容性](https://istio.io/latest/docs/setup/additional-setup/cni/#compatibility-with-other-cni-plugins)。*

**什么是 geneve tunnel？为啥 ztunnel 不使用 veth-pair 而使用 geneve geneve？**  
![](/images/2023-09-02-ambient-mesh-learn-first/33.png)   
具体可参见 [Using Geneve Tunnels to Implement Istio Ambient Mesh Traffic Interception](https://jimmysong.io/en/blog/traffic-interception-with-geneve-tunnel-with-istio-ambient-mesh/) 或者[使用 Geneve 隧道实现 Istio Ambient Mesh 的流量拦截](https://jimmysong.io/blog/traffic-interception-with-geneve-tunnel-with-istio-ambient-mesh/)。

**Istio 支持 eBPF 作为 datapath?**

在 Istio 1.18 中，增加了 eBPF 选项，你可以选择使用 iptables 或 eBPF 来做流量劫持。使用 eBPF 方式避免了部分 iptables 规则和隧道封装，相比使用 iptables 和 Geneve 隧道更加高效。只需要在安装 Istio 时设置values.cni.ambient.redirectMode参数即可，如下：
```bash
istioctl install --set profile=ambient --set values.cni.ambient.redirectMode="ebpf"
```
......当然，Ambient Mesh 肯定不止这些内容需要我们去研究，如 L4 劫持过程、L7 劫持过程、ztunnel 实现原理，
这些内容后续在继续深入调研与研究。

# 参考与致谢

1. [2023-ambient-merged-istio-main](https://istio.io/latest/blog/2023/ambient-merged-istio-main/)
2. [Getting Started with Ambient Mesh](https://istio.io/latest/docs/ops/ambient/getting-started/#download)
3. [Envoy IP Transparency](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/other_features/ip_transparency.html)
4. [Introducing Ambient Mesh](https://istio.io/latest/blog/2022/introducing-ambient-mesh/)
5. [l7-traffic-path-in-ambient-mesh](https://tetrate.io/blog/l7-traffic-path-in-ambient-mesh/)
6. [zhaohubing-ambient-mesh](https://www.zhaohuabing.com/tags/ambient-mesh/)
