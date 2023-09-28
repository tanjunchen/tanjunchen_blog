---
layout:     post
title:      "使用 Istio 过程中遇到的常见问题与解决方法（四）"
subtitle:   "在使用 Istio 过程中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "陈谭军"
date: 2022-11-21
published: true
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

# Istio 常见问题列表

1. 使用 corsPolicy 解决跨域问题
1. 如何使用 iphash 进行负载均衡
1. 动态设置 max_body_size
1. 动态调整 header 数量与大小
1. 利用 VirtualService 实现基于 Header 的授权策略
1. Istio 最好使用默认路由
1. 服务 service 显式指定协议
1. Istio 控制平面与数据平面性能优化
1. Istio 常见的调试技巧与方法
1. Envoy 常见异常状态码汇总

# 使用 corsPolicy 解决跨域问题

**背景**：使用 istio 后我们可以将跨域问题转交给 istio 处理，业务与 web 框架不需要关心。本文介绍如何利用 Istio 配置来支持 HTTP 跨域。

跨源资源共享（[CORS](https://developer.mozilla.org/zh-CN/docs/Glossary/CORS)，或通俗地译为跨域资源共享）是一种基于 [HTTP](https://developer.mozilla.org/zh-CN/docs/Glossary/HTTP) 头的机制，该机制通过允许服务器标示除了它自己以外的其他[源](https://developer.mozilla.org/zh-CN/docs/Glossary/Origin)（域、协议或端口），使得浏览器允许这些源访问加载自己的资源。跨源资源共享还通过一种机制来检查服务器是否会允许要发送的真实请求，该机制通过浏览器发起一个到服务器托管的跨源资源的“预检”请求。在预检中，浏览器发送的头中标示有 HTTP 方法和真实请求中会用到的头。

**解决方式**：Istio 可以通过配置 `VirtualService` 的 `corsPolicy` 字段来实现跨域，示例的 Yaml 文件如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: nginx
spec:
  gateways:
  - default/nginx-gw
  hosts:
  - nginx.example.com
  http:
  - corsPolicy:
      allowOrigins:
      - regex: "https?://nginx.example.com"
    route:
    - destination:
        host: nginx.default.svc.cluster.local
        port:
          number: 80
```

关于 `corsPolicy` 配置，参考 Istio [CorsPolicy 官方文档](https://istio.io/latest/docs/reference/config/networking/virtual-service/#CorsPolicy)。

**注意事项**：控制请求能否跨域的逻辑核心在于浏览器，浏览器通过判断请求响应的 `access-control-allow-origin` header 中是否有当前页面的地址，来判断该跨域请求能否被允许。通常一些 web 框架支持跨域主要是为响应自动加上 `access-control-allow-origin` header，istio 也是同样的道理。

# 如何使用 iphash 进行负载均衡

在 Istio 中，可以通过配置 DestinationRule 来实现基于源 IP 的负载均衡，如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: bookinfo-ratings
spec:
  host: ratings.default.svc.cluster.local
  trafficPolicy:
    loadBalancer:
      consistentHash:
        httpHeaderName: X-Forwarded-For
```
需要注意的是，这种方法需要你的服务能够正确地设置 `X-Forwarded-For` 头部。如果你的服务位于一个支持这个头部的代理后面（例如 Istio 的 Ingress Gateway 或者 Envoy 代理），那么这个头部应该已经被正确地设置。如果你的服务直接接收来自客户端的请求，那么你可能需要在你的服务中添加代码来设置这个头部。此外，这种方法只适用于 HTTP 和 HTTP/2 的流量。对于 TCP 和 UDP 的流量，Istio 目前还不支持基于源 IP 的负载均衡。

配置 DestinationRule，指定 useSourceIp 负载均衡策略，如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: bookinfo-ratings
spec:
  host: ratings.prod.svc.cluster.local
  trafficPolicy:
    loadBalancer:
      consistentHash:
        useSourceIp: true
```

更多的详细配置，可以参考官方文档 [LoadBalancerSettings-ConsistentHashLB](https://istio.io/latest/docs/reference/config/networking/destination-rule/#LoadBalancerSettings-ConsistentHashLB)。

# 动态设置 Envoy max_body_size

**背景**：Nginx 可以通过 `client_max_body_size` 参数来设置 HTTP 请求体的最大大小。这个参数定义了服务器接受的请求体的最大字节数，超过这个值的请求将被拒绝并返回 `413 Request Entity Too Large` 错误，如下所示：
```conf
server {
    ...
    client_max_body_size 50m;
    ...
    location /upload {
        client_max_body_size 200m;
        ...
    }
}
```

在 istio 中如何调整客户端的最大请求大小，我们通过 EnvoyFilter 调整 Envoy 能够接受的最大请求大小，如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: limit-request-size
  namespace: istio-system
spec:
  workloadSelector:
    labels:
      istio: ingressgateway
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: GATEWAY
      listener:
        filterChain:
          filter:
            name: envoy.http_connection_manager
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.buffer
        typed_config:
          '@type': type.googleapis.com/udpa.type.v1.TypedStruct
          value:
            maxRequestBytes: 104857600  # 100 MB
```

# 动态调整 header 数量与大小

Envoy 默认会限制请求与响应的 header 数量与大小（默认 100 左右），有相关的 Issue，参见 [How to set max resposne header limit](https://github.com/envoyproxy/envoy/issues/13827)。

Envoy 报错日志，可能如下所示：
```bash
2022-12-31T14:24:27.501043Z     debug   envoy client    [C4689] protocol error: headers size exceeds limit

2023-01-01T13:29:07.022454Z	info	xdsproxy	connected to upstream XDS server: istiod.istio-system.svc:15012
[2023-01-01T13:29:06.662Z] "- - HTTP/1.1" 431 DPE http1.headers_too_large - "-" 0 31 0 - "-" "-" "-" "-" "-" - - 192.168.36.246:5000 10.1.2.24:56864 - -

not supporting multiuse
HTTP/1.1 431 Request Header Fields Too Large

[2023-01-02T07:40:56.459Z] "GET /headers HTTP/1.1" 502 UPE upstream_reset_before_response_started{protocol_error} - "-" 0 87 7 - "-" "curl/7.87.0-DEV" "3b7caa0b-9626-946d-b4ef-36c5ddf790bc" "helloworld:5000" "10.1.2.42:5000" inbound|5000|| 127.0.0.6:44336 10.1.2.42:5000 172.16.9.8:44408 - default

upstream connect error or disconnect/reset before headers. reset reason: connection failure, transport failure reason: delayed connect error: 111

[2023-01-01T14:47:26.285Z] "GET /hello HTTP/1.1" 503 UF upstream_reset_before_response_started{connection_failure,delayed_connect_error:_111} - "delayed_connect_error:_111" 0 145 0 - "-" "curl/7.87.0-DEV" "35e82df8-1262-9404-8ad2-303b8613955c" "helloworld:5000" "10.1.2.31:5000" inbound|5000|| - 10.1.2.31:5000 172.16.9.8:5067 - default
```

**解决方式**：通过 envoyfilter 调大 header 的最大限制值，测试 Yaml 如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: max-header
  namespace: istio-system
spec:
  configPatches:
  - applyTo: NETWORK_FILTER # http connection manager is a filter in Envoy
    match:
      context: ANY
      listener:
        filterChain:
          filter:
            name: "envoy.http_connection_manager"
    patch:
      operation: MERGE
      value:
        typed_config:
          "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager"
          max_request_headers_kb: 80   # 80
          common_http_protocol_options:
            max_headers_count: 200  # 200 条
  - applyTo: CLUSTER
    match:
      context: ANY
      cluster: 
        portNumber: 5000
    patch:
      operation: MERGE
      value: # cluster specification
        common_http_protocol_options:
          max_headers_count: 300  # cluster 300
```

**最佳实践**：优化业务 header 数目，header 为啥需要这么多，会超过 Envoy (默认值 100) 限制值。





# 使用 VirtualService 实现基于 Header 的授权

**背景**：业务在 http header 或 grpc metadata 中会有用户信息，想通过 Istio 来实现基于 header 来对请求进行授权，如果不满足条件则返回 401。但是 `AuthorizationPolicy` CRD 不支持基于 Header 的授权，但是我们可以使用 `VirtualService headers` 来实现业务基于 header 的授权功能。测试使用的 Yaml 文件如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: helloworld
spec:
  hosts:
  - helloworld
  http:
  - name: whitelist
    match:
    - headers:
        end-user:
          regex: "istio"
    route:
    - destination:
        host: helloworld
        port:
          number: 5000
  - name: default
    route:
    - destination:
        host: helloworld
        port:
          number: 5000
    fault:
      abort:
        percentage:
          value: 100
        httpStatus: 401
```

# Istio 最好使用默认路由

默认路由规则可以指定流量应该如何在服务间路由，例如，将所有流量路由到某个特定的版本，或者根据某种比例将流量分配到不同的版本。使用默认路由的场景如下所示： 
1. 蓝绿部署：创建两个版本的服务（例如，蓝色版本和绿色版本），然后通过修改默认路由规则来切换流量。
1. 金丝雀发布：创建一个新的服务版本（例如，金丝雀版本），然后通过修改默认路由规则来逐渐将流量引入新版本。
1. 故障注入和恢复：通过修改默认路由规则来模拟故障，然后观察服务如何响应，当故障解决后，可以恢复默认路由规则。
1. A/B 测试：创建两个或更多版本的服务，然后通过修改默认路由规则来将不同的用户流量路由到不同的版本。

刚开始我们的服务没有多个版本，也没配置 vs，只有一个 deployment 和一个 svc，如果我们要为业务配置默认流量策略，可以直接创建 dr，给对应 host 设置 trafficPolicy，yaml 文件如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
  subsets:
  - name: v1
    labels:
      version: v1
```

虽然 `DestinationRule` CRD 的 subsets 可以设置 `trafficPolicy`，但 subsets 下设置的不是默认策略，而且 vs 没有明确指定路由到对应 subset 时，即便我们的服务只有一个版本，istio 也不会使用 subset 下指定的 `trafficPolicy`，所以我们最好创建一个全局默认 `trafficPolicy`。

**最佳实践**：我们最好为服务不同版本创建 `DestinationRule` 与 `VirtualService`，后续就可以对不同版本配置不同的流量策略，测试 yaml 如下所示：
```yaml
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
```

# 给 Service 显式指定协议

**背景**：协议嗅探，也称为协议自动检测，是网络设备或软件自动确定数据包所使用协议的过程。例如，它可以自动区分一个数据包是使用 HTTP 还是 HTTPS 协议。协议嗅探的主要目的是简化网络配置和管理。如果没有协议嗅探，网络管理员可能需要为每种协议单独配置和管理网络设备或软件。通过协议嗅探，网络设备或软件可以自动处理多种协议，从而减少了配置和管理的复杂性。

协议嗅探的好处包括：
* 简化配置：不需要为每种协议单独配置网络设备或软件。
* 提高灵活性：可以自动处理新的或未知的协议。
* 提高效率：可以根据协议的特性进行优化，例如，对 HTTP 流量进行缓存或压缩。

然而，协议嗅探也有一些潜在的问题：
* 安全风险：如果协议嗅探被误用，可能会导致数据泄露或被篡改。例如，如果一个网络设备错误地将 HTTPS 流量识别为 HTTP 流量，可能会导致敏感信息被明文传输。
* 性能开销：协议嗅探需要对每个数据包进行深度分析，这可能会增加处理延迟和 CPU 使用率。
* 不准确：协议嗅探可能会误识别协议，特别是对于使用非标准端口或封装在其他协议中的协议。

istio 需要知道服务提供什么七层协议，从而来为其配置相应协议的 filter chain 链，通常最好是显式声明协议，如果没有声明，istio 会自动开启协议探测，这个探测能力比较有限，导致无法正常工作。那么如何给 service 指定显示协议呢？这可以通过两种方式进行配置：  
* 按端口名称格式，`name: <protocol>[-<suffix>]`。
* 在 Kubernetes 1.18+ 版本中，通过 `appProtocol` 字段 `appProtocol: <protocol>`。

**解决方式**：给集群内 Service 指定 port name 时加上相应的前缀或指定 appProtocol 字段可以显示声明协议，如下所示：
```yaml
kind: Service
metadata:
  name: nginx
spec:
  ports:
  - number: 8080
    name: rpc
    appProtocol: grpc # 指定该端口提供 grpc 协议的服务
  - number: 80
    name: http-web # 指定该端口提供 http 协议的服务
```

**解决方式**：使用 ServiceEntry 指定协议，如果外部服务可以被 DNS 解析，可以定义 ServiceEntry 来指定协议，如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: external-mysql
spec:
  hosts:
  - mysql.test.com
  location: MESH_EXTERNAL
  ports:
  - number: 3306
    name: mysql
    protocol: mysql
  resolution: DNS
```

更多的详细信息可参考 [explicit-protocol-selection](https://istio.io/latest/docs/ops/configuration/traffic-management/protocol-selection/#explicit-protocol-selection)。

# Istio 控制平面与数据平面性能优化

**背景**：Istio 提供了丰富的功能，如流量管理、安全、观察性等，这些功能的实现和运行可能会对系统性能产生一定影响，因此，对 Istio 进行优化是必要的。如下所示：
* 提高性能：随着 Envoy 代理的注入，会增加网络延迟和 CPU 使用率。
* 提升可扩展性：随着服务数量的增加，Istio 的控制平面可能会面临更大的压力。
* 降低资源消耗：Istio 的运行需要消耗一定的系统资源，如 CPU、内存。
* 提高稳定性：优化可以帮助减少 Istio 的错误和故障，提高系统的稳定性。

我们可以分别从控制平面与数据平面对 Istio 进行优化。

**控制平面**：
* 使用参数 `ENABLE_ENHANCED_RESOURCE_SCOPING` 开启 Istio CRD 隔离，`meshConfig.discoverySelectors` 将限制 CRD 配置（如Gateway、VirtualService、DestinationRule、Ingress等），在 Kubernetes 集群中新建多个 Istio 网格实例，此选项很有意思，能够实现 CRD 隔离，降低 Pilot 资源消耗与提升控制平面的稳定性。
* Istiod 减少 Kubernetes 元数据（尤其是大规模集群）对 CPU、内存等资源消耗。相关代码提交可参考 [Istio Bump k8s dependencies to v0.26](https://github.com/istio/istio/commit/3fcff36ddc5e69ed20755c6385d44eb1a0e50505#diff-f5208fc7b2fabcbd75534363ac5e26deaccd9cefcf75e92722407c9a96de3f68)。要求 Istio 1.14+。Istiod 内存能在大规模集群下降低 40% 以上。主要是不使用 Kubernetes 无效的字段 `unused field`。
* 使用选择性服务发现 [discovery selectors](https://istio.io/v1.14/blog/2021/discovery-selectors/)。要求 Istio 1.10+。选择性服务发现可以减少 Envoy 代理需要处理的服务信息的数量。
* istiod 保持负载均衡。Envoy 提供了一个定时重连的机制。通过这个机制，Envoy 会定期断开与 Istiod 的连接，然后重新建立连接。在重新建立连接时，Envoy 会根据负载均衡策略选择一个 Istiod 实例，这样就可以保证 Istiod 的负载均衡。
* istiod HPA。istiod 是无状态的，我们可以通过 HPA 进行负载均衡，提升 istiod 稳定性。
* xDS 按需下发。增量 xDS 推送，可参见 [Delta xDS](https://docs.google.com/document/d/1hwC81_jS8qARBDcDE6VTxx6fA31In96xAZWqfwnKhpQ/edit#heading=h.xw1gqgyqs5b)。[Slime](https://github.com/slime-io/slime) 是网易开源的一个项目，它实现了 Istio 的 lazyXDS 机制。
* 控制平面参数优化。开启 `PILOT_ENABLE_EDS_DEBOUNCE` 参数，默认情况下，此功能已启用。`PILOT_PUSH_THROTTLE`(默认值 100ms)，限制允许的并发推送数量，在较大的机器上，可以增加此限制以实现更快的推送。`PILOT_DEBOUNCE_AFTER`(默认值 100ms)、`PILOT_DEBOUNCE_MAX`(默认值 10s)，用于防抖动的配置/注册事件的延迟，其他参数优化。
* 关闭 mtls。如果认为集群内是安全的，可以关掉 mtls 以提升性能。示例的 yaml 文件如下所示：
```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  # istiod 所在的命名空间
  namespace: istio-system
spec:
  mtls:
    mode: DISABLE
```

**数据平面**：

* 使用 Sidecar CRD 以减少 Envoy 资源消耗。istio 默认会下发 mesh 内集群服务所有可能需要的信息，以便让 sidecar 能够与任意 workload 通信。当集群规模较大，可能就会导致 sidecar 占用资源非常高。如果只有部分 namespace 使用了 istio，而网格中的服务与其它 namespace 没有注入 sidecar 的服务没有多大关系，可以配置下 istio 的 Sidecar 资源，避免 sidecar 加载大量无用 outbound 的规则。如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Sidecar
metadata:
  name: default
  namespace: istio-system
spec:
  egress:
  - hosts:
    - "dev/*"
    - "test/*"
```

**说明**：定义在 istio-system 命名空间下表示 Sidecar 配置针对所有 namespace 生效。在 egress 的 hosts 配置中加入开启了 sidecar 自动注入的 namespace，表示只下发跟这些 namespace 相关的服务给 Envoy。

# Istio 常见的调试技巧与方法



# Envoy 常见异常状态码汇总


