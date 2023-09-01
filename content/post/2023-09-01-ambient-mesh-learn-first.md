---
layout:     post
title:      "初始 Istio Ambient Mesh 新模式"
subtitle:   ""
description: "Ambient Mesh，这是 Istio 提供的一种新的数据平面模式，旨在简化操作，提供更广泛的应用兼容性，并降低基础设施的成本。Ambient mesh 使得用户可以选择使用一种可以集成到其基础设施中的 Mesh 数据平面，而不是需要和应用一起部署的 sidecar。同时，该模式可以提供和 Sidecar 模式相同的零信任安全、遥测和流量管理等 Istio 的核心功能。目前 Ambient mesh 处于 alpha 阶段。"
author: "陈谭军"
date: 2023-09-01
published: true
tags:
    - ambient mesh
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

Ambient Mesh，这是 Istio 提供的一种新的数据平面模式，旨在简化操作，提供更广泛的应用兼容性，并降低基础设施的成本。Ambient mesh 使得用户可以选择使用一种可以集成到其基础设施中的 Mesh 数据平面，而不是需要和应用一起部署的 sidecar。同时，该模式可以提供和 Sidecar 模式相同的零信任安全、遥测和流量管理等 Istio 的核心功能，目前 Ambient mesh 处于 alpha 阶段。

![](/images/2023-09-01-ambient-mesh-learn-first/1.png)

# 安装 Ambient Mesh

**前提条件**
1. 要求 Kubernetes 版本 1.24, 1.25, 1.26, 1.27+。
1. istio 1.18+。

**提示**
1. Ambient 目前处于 alpha，alpha 版本中存在已知的性能、稳定性和安全问题，请不要在生产环境中使用。
1. Ambient 目前需要使用 istio-cni 来配置 Kubernetes 网络规则，istio-cni 模式目前不支持某些 CNI 类型（即不使用 veth 设备的 CN，如桥接模式）。

下载最新版本的 [Istio](https://github.com/istio/istio/releases/tag/1.18.0-alpha.0)，其中 alpha 版本提供对 ambient mesh 的支持。

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

![](/images/2023-09-01-ambient-mesh-learn-first/2.png)

如果我们的 Kubernetes 集群不支持 Kubernetes Gateway CRDs，可以参考以下方式安装。

```bash
kubectl get crd gateways.gateway.networking.k8s.io &> /dev/null || \
 { kubectl kustomize "github.com/kubernetes-sigs/gateway-api/config/crd/experimental?ref=v0.6.1" | kubectl apply -f -; }
```

使用 istioctl 安装 Istio 集群

```
istioctl install --set profile=ambient --skip-confirmation
```

![](/images/2023-09-01-ambient-mesh-learn-first/3.png)

运行上述命令后，如下所示，相关组件（含 ztunnel）已成功安装。

![](/images/2023-09-01-ambient-mesh-learn-first/4.png)

ambient profile 在集群中安装了 Istiod, ingress gateway, ztunnel 和 istio-cni 组件。其中 ztunnel 和 istio-cni 以 daemonset 方式部署在每个 node 上。istio-cni 用于检测 pod 是否处于 ambient 模式，监听并且同步创建与更新 pod 出向流量和入向流量重定向到 node 的 ztunnel 的 iptables 规则。

# 部署 demo 应用

执行下面的命令，部署 demo 测试应用，我们使用 Istio 官网示例 bookinfo 应用程序。确保 default 命名空间不包含标签 istio-injection=enabled。

```bash
kubectl apply -f samples/bookinfo/platform/kube/bookinfo.yaml
kubectl apply -f samples/sleep/sleep.yaml
kubectl apply -f samples/sleep/notsleep.yaml
```

应用列表如下所示：

![](/images/2023-09-01-ambient-mesh-learn-first/5.png)

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

![](/images/2023-09-01-ambient-mesh-learn-first/6.png)

# 纳管 demo 应用到 Ambient Mesh

为 default namespace 打上标签来将该 namespace 中的所有应用加入 ambient mesh 中。
```bash
kubectl label namespace default istio.io/dataplane-mode=ambient
```

我们查看 istio-cni 的日志，可以看到 istio-cni 为 default 命名空间下的应用 pod 创建了相应的路由规则：
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
![](/images/2023-09-01-ambient-mesh-learn-first/7.png)

istio-system 命名空间下的 ztunnel Pod 列表如下所示：
![](/images/2023-09-01-ambient-mesh-learn-first/8.png)

查看 node 节点上的 sleep 与 productpage 对应的 ztunnel 访问日志，sleep 所在 node 上的 ztunnel 日志（outbound 请求），如下所示：
```bash
kubectl -n istio-system logs -f ztunnel-w5zvr
2023-08-28T11:39:33.716634Z  INFO outbound{id=86e9d44b9a866661edd61c102465805e}: ztunnel::proxy::outbound: proxy to 10.244.1.24:9080 using HBONE via 10.244.1.24:15008 type Direct
2023-08-28T11:39:33.756833Z  INFO outbound{id=86e9d44b9a866661edd61c102465805e}: ztunnel::proxy::outbound: complete dur=42.17475ms
```
![](/images/2023-09-01-ambient-mesh-learn-first/9.png)

productpage 所在 node 上的 ztunnel 日志（inbound 请求），如下所示：
```bash
kubectl -n istio-system logs -f ztunnel-8k6cp
2023-08-28T11:41:06.835522Z  INFO inbound{id=7fb5b4259eaf43c599f8d9f4fe2c5657 peer_ip=10.244.2.9 peer_id=spiffe://cluster.local/ns/default/sa/sleep}: ztunnel::proxy::inbound: got CONNECT request to 10.244.1.24:9080
```

因为 ambient 只开启了 L4，流量只会通过 ztunnel ，不会经过 waypoint proxy。此时应用程序的流量路径如下图所示：
![](/images/2023-09-01-ambient-mesh-learn-first/10.svg)

**使用 Prometheus**

按照文档 https://istio.io/latest/docs/ops/integrations/prometheus/#installation，部署 Prometheus。

**使用 Kiali**

按照文档 https://istio.io/latest/docs/ops/integrations/kiali/#installation，部署 Kiali。按照上述请求方式给 productpage 发送请求，kiali 流量拓扑图如下所示：
![](/images/2023-09-01-ambient-mesh-learn-first/11.png)

# 为 Ambient Mesh 启用安全策略

使用 Kubernetes Gateway API 来启用某个服务的 L7 功能，创建下面的 gateway，为 productpage 服务开启七层处理。任何流向 productpage 服务的流量都将由第 7 层(L7) 代理进行管理。为 productpage 部署 waypoint proxy，如下所示：
```bash
istioctl x waypoint apply --service-account bookinfo-productpage
```

![](/images/2023-09-01-ambient-mesh-learn-first/12.png)

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
![](/images/2023-09-01-ambient-mesh-learn-first/13.png)

![](/images/2023-09-01-ambient-mesh-learn-first/14.png)

istio-waypoint 会通过 Kubernetes Gateway 产生 bookinfo-productpage-istio-waypoint deploy 工作负载（istio-proxy 镜像），作为 productpage L7 流量管理的组件。此时可以查看到 Istio 创建的 waypoint proxy 如下所示：

![](/images/2023-09-01-ambient-mesh-learn-first/15.png)

重新使用 sleep 访问 productpage，如下所示：
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

可以从上面的日志中看到 (ToServerWaypoint) 标志，并且  bookinfo-productpage-istio-waypoint Envoy 有 access_log，说明请求经过 waypoint proxy，此时应用程序的流量路径如下图所示：

![](/images/2023-09-01-ambient-mesh-learn-first/16.png)

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
![](/images/2023-09-01-ambient-mesh-learn-first/17.png)

# Ambient Mesh 启用 L7 功能


# Ambient Mesh 配置 L7 流量管理


# Ambient Mesh 总结


# 卸载  Ambient Mesh



# 为什么与问题答疑


# 参考与致谢


