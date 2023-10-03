---
layout:     post
title:      "使用 Istio 过程中遇到的常见问题与解决方法（三）"
subtitle:   "在使用 Istio 过程中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "陈谭军"
date: 2022-11-20
published: true
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

服务网格为微服务提供了一个服务通信的基础设施层，统一为上层的微服务提供了服务发现、负载均衡、重试、熔断等基础通信功能，以及服务路由、灰度发布等高级治理功能。如果我们在使用服务网格系统出现问题的话，我们如何才能快速定位问题以及处理呢？

[使用 Istio 过程中遇到的常见问题与解决方法（一）](https://tanjunchen.github.io/post/2022-11-18-istio-questions-1/)  
[使用 Istio 过程中遇到的常见问题与解决方法（二）](https://tanjunchen.github.io/post/2022-11-19-istio-questions-2/)  
[使用 Istio 过程中遇到的常见问题与解决方法（三）](https://tanjunchen.github.io/post/2022-11-20-istio-questions-3/)  
[使用 Istio 过程中遇到的常见问题与解决方法（四）](https://tanjunchen.github.io/post/2022-11-21-istio-questions-4/)  

# Istio 常见问题列表

1. Istio 实用安装选项
1. 多集群（跨集群应用）service 访问不通
1. gRPC 服务导致请求负载不均衡问题
1. Sidecar Inbound 与 OutBound 生效范围问题
1. Sidecar（优雅终止）服务停止导致请求失败问题 
1. 应用未监听 0.0.0.0 导致连接异常
1. Smart DNS 相关问题
1. virtualservice 路由匹配顺序问题
1. http Header 大写导致基于 Header 会话保持不生效
1. 支持 websocket 协议

# Istio 实用安装选项

我们在使用 Istio 时，如果想体验某个功能，往往需要在安装 Istio 时开启特性开关，因此我列举 Istio 安装时动态可选项，如下所示：
```bash
istioctl install \
  --set profile=demo \
  --set meshConfig.accessLogFile="/dev/stdout"  \
  --set meshConfig.accessLogEncoding="JSON"  \
  --set values.global.proxy.privileged=true \
  --set values.global.proxy.enableCoreDump=true \ 
  --set values.global.hub=docker.io/istio 

```

使用 `Istio Operator` 安装 Istio 使用的 Yaml 文件如下所示：
```yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: test-iop
  namespace: istio-system
spec:
  profile: default
  values:
    global:
      istioNamespace: istio-system
      logging:
        level: default:info # 日志级别
  meshConfig:
    enableTracing: true
    accessLogFile: /dev/stdout # 输出到终端
    enableAutoMtls: true
    accessLogFormat: "[%START_TIME%] %REQ(X-META-PROTOCOL-APPLICATION-PROTOCOL)%
     %RESPONSE_CODE% %RESPONSE_CODE_DETAILS% %CONNECTION_TERMINATION_DETAILS% \"%UPSTREAM_TRANSPORT_FAILURE_REASON%\"
     %BYTES_RECEIVED% %BYTES_SENT% %DURATION% \"%REQ(X-FORWARDED-FOR)%\" \"%REQ(X-REQUEST-ID)%\" %UPSTREAM_CLUSTER%
     %UPSTREAM_LOCAL_ADDRESS% %DOWNSTREAM_LOCAL_ADDRESS% %DOWNSTREAM_REMOTE_ADDRESS% %ROUTE_NAME%\n"
    defaultConfig:
      holdApplicationUntilProxyStarts: true  # sidecar 启动顺序
      proxyMetadata:
        # Enable basic DNS proxying
        ISTIO_META_DNS_CAPTURE: 'true'
        # Enable automatic address allocation
        ISTIO_META_DNS_AUTO_ALLOCATE: 'true'
      tracing:
        sampling: 100
        zipkin:
          address: zipkin.istio-system:9411
  components:
    pilot:
      hub: docker.io/istio  # hub
      tag: 1.16.5   # tag
      enabled: true
      namespace: istio-system
      k8s:
        overlays:
        - kind: Deployment
          name: istiod
          patches:
          - path: spec.template.spec.hostNetwork
            value: true   # istiod 使用主机模式
```

通过 istioctl 与 istio iop 文件安装 Istio，如下所示：
```bash
# 安装
istioctl install -f test-iop.yaml 

# 生成 Kubernetes 文件
istioctl manifest generate -f test-iop.yaml 
```

# 多集群（跨集群应用）service 访问不通

**现象**：同一网格实例的多个集群之间通过 service 调用，可能会发现跨集群服务访问不通。

**排查方式1**：可能是 pilot agent 没启用 smart DNS，无法自动解析其它集群的 service 域名，可以通过手动在本集群创建跟远程集群同样的 service 来解决，也可以启用 smart DNS 来自动解析。

**排查方式2**：如果底层容器网络 Pod IP 是互通的（集群 A 与 集群 B Pod 网络底层是互通的，此时不需要东西向网关进行转发），核实本集群与远程集群中的服务与应用是否保持一致。

**排查方式3**：如果底层容器网络 Pod IP 不是互通的，此时需要在集群中安装东西向网关进行转发，我们可以查看东西网关是否有报错日志。

**排查方式4**：查看主集群中的 istiod 纳管远程集群是否成功，主集群是否可以通过 secret 连接到远程集群获取 `Endpoint` 元数据，istiod 在多集群模式下是否有报错日志。

# gRPC 服务导致请求负载不均衡问题

**现象**：在使用 Istio 对 gRPC 协议的服务进行流量控制时，会出现流量负载不均衡的问题。同一个 client（gRPC 协议） 的请求始终只打到同一个 server 的 pod，造成负载不均衡。

**原因**：Istio 支持多种负载均衡策略，包括 ROUND_ROBIN、LEAST_CONN、RANDOM 等，如果配置不正确，可能会导致流量分配不均。gRPC 默认会复用长连接，这可能会导致流量都被路由到同一个 Pod，从而出现负载不均衡的问题。如果只使用普通的 k8s service，gRPC 协议会被当成 tcp 来转发，在连接层面做负载均衡，不会在请求层面做负载均衡。但在 istio 中默认会对 gRPC 的请求进行请求级别的负载均衡，如果发现负载不均衡，通常是 Istio 没有正确配置。要让 gRPC 在 Istio 中实现请求级别负载均衡，能够让 istio 正确识别是 gRPC 协议就行，用 tcp 的话就只能在连接级别进行负载均衡了，请求级别可能就会负载不均衡。

**解决方式**：部署服务的 service 的 port name 以 "grpc-" 开头定义，让 istio 能够正确识别，如下所示：
```yaml
apiVersion: v1
kind: Service
metadata:
  name: grpc
spec:
  ports:
  - name: grpc-9000 # 以 grpc- 开头
    port: 9000
    protocol: TCP
    targetPort: 9000
  selector:
    app: grpc
  type: ClusterIP
```

如果使用了 `VirtualService`，需要使用 http 而不用 tcp，如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: grpc
spec:
  gateways:
  - default/grpc-gw
  hosts:
  - '*'
  http: # 使用 http 不用 tcp
  - match:
    - port: 9000
    route:
    - destination:
        host: grpc.demo.svc.cluster.local
        port:
          number: 9000
      weight: 100
```

如果使用 ingress-gateway 暴露服务，protocal 配置 GRPC 不用 TCP，如下示例：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: grpc-gw
spec:
  selector:
    app: istio-ingressgateway
    istio: ingressgateway
  servers:
  - hosts:
    - '*'
    port:
      name: grpc-demo-server
      number: 9000
      protocol: GRPC # 使用 GRPC 不用 TCP
```

# Sidecar Inbound 与 OutBound 生效范围问题

1. inbound：主要处理进入 Pod 的流量，即从其他服务到达本服务的流量，在这个过程中，sidecar 代理会根据 Istio 的策略进行流量控制、安全认证等操作。
2. outbound：主要处理从 Pod 发出的流量，即从本服务到其他服务的流量，在这个过程中，sidecar 代理会根据 Istio 的策略进行流量路由、负载均衡等操作。

inbound 和 outbound 的主要区别在于处理的流量方向不同，但都是通过 Istio 的策略对流量进行控制。下图展示了 Istio proxy 作为代理在 inbound 和 outbound 所生效的功能列表。

![](/images/2022-11-20-istio-questions-3/1.png)

# Sidecar（优雅终止）服务停止导致请求失败问题 

**概念**：优雅终止（Graceful Termination）是指在关闭或重启服务时，允许服务完成当前正在处理的请求，而不是立即中断这些请求。这样可以避免因服务突然中断而导致的数据丢失或者系统错误。优雅终止的主要优点是可以保证服务的稳定性和数据的完整性，避免因服务突然中断而导致的问题。但是，优雅终止可能会使得服务的关闭或重启时间变长，因此需要根据实际情况进行权衡。

**现象**：当注入了 Sidecar 的 Pod 开始停止时，它将从服务的 endpoints 列表中被摘除掉，不再转发流量给它，同时 Sidecar 也会收到 SIGTERM 信号，立刻不在接受 inbound 新连接，但会保持存量 inbound 连接继续处理，outbound 方向流量仍然可以正常发起。缺省情况下，在收到 SIGTERM 后，Istio-Agent 会在等待 `terminationDrainDuration` 5S 后退出，由于 Envoy 是 Istio-agent 的子进程，Envoy 也会随之退出，上述现象可能会存在以下问题：  
1. 若停止的服务提供的接口耗时本身较长，存量 inbound 请求可能无法被处理完就被断开。
2. 若停止的过程需要调用其它服务(比如服务后置任务)，outbound 请求可能会调用失败。

**解决方式**：设置 `EXIT_ON_ZERO_ACTIVE_CONNECTIONS` （Istio 1.12+）设置为 `true`。  
当 `EXIT_ON_ZERO_ACTIVE_CONNECTIONS` 设置为 `true` 时，如果一个 Pod 中没有活跃的连接，那么 Istio 的 sidecar 代理会自动退出，从而允许 Kubernetes 删除该 Pod。这样可以确保在 Pod 删除时，不会中断任何活跃的连接，从而实现优雅地终止服务。该参数就是等待 Sidecar 退出时完成剩余请求，在响应时，也通知客户端去关闭长连接（对于 HTTP1 响应 "Connection: close" header，对于 HTTP2 响应 GOAWAY 这个帧）。

核心源码如下所示：
```go
// 配置了 EXIT_ON_ZERO_ACTIVE_CONNECTIONS 为 true 时，检查活动链接为 0 后再退出
if a.exitOnZeroActiveConnections {
    log.Infof("Agent draining proxy for %v, then waiting for active connections to terminate...", a.minDrainDuration)
    time.Sleep(a.minDrainDuration)
    log.Infof("Checking for active connections...")
    ticker := time.NewTicker(activeConnectionCheckDelay)
    for range ticker.C {
        if a.activeProxyConnections() == 0 {
            log.Info("There are no more active connections. terminating proxy...")
            a.abortCh <- errAbort
            return
        }
    }
} else { // 缺省情况下等待 5S 即退出
    log.Infof("Graceful termination period is %v, starting...", a.terminationDrainDuration)
    time.Sleep(a.terminationDrainDuration)
    log.Infof("Graceful termination period complete, terminating remaining proxies.")
    a.abortCh <- errAbort
}
```

如何开启该参数配置，可以修改全局配置的 istio configmap，在 `defaultConfig.proxyMetadata` 加上下面的环境变量：
```yaml
meshConfig:
  defaultConfig:
    proxyMetadata: 
      EXIT_ON_ZERO_ACTIVE_CONNECTIONS: 'true'
```

我们也可以单独给某个 Pod 添加下面的注解：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sleep
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sleep
  template:
    metadata:
      annotations:
        proxy.istio.io/config: |
          proxyMetadata: 
            EXIT_ON_ZERO_ACTIVE_CONNECTIONS: 'true' 
      labels:
        app: sleep
  ...
```

**解决方式**：通过 Kubernetes 的 Pod 生命周期管理来实现。在 Kubernetes 中，可以通过定义 Pod 的生命周期钩子来管理容器的启动和停止过程。preStop 钩子可以在容器停止前执行一些操作，这就可以用来实现 Istio Proxy 的优雅退出。Istio Proxy 实现优雅退出的示例 Yaml 文件如下所示：
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: test
    image: myapp
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh","-c","curl -XPOST localhost:15000/quitquitquit"]
  - name: istio-proxy
    image: docker.io/istio/proxyv2:1.16.5
```

**解决方式**：配置 pod 的 `terminationGracePeriodSeconds` 参数。
Kubernetes 在向 pod 发出 SIGTERM 信号后，会缺省等待 30S，如果 30S 后 pod 还未结束，Kubernetes 会向 pod 发出 SIGKILL 信号。
因此，即使我们设置了 `EXIT_ON_ZERO_ACTIVE_CONNECTIONS` 为 true，Envoy 最多也只能等待 30S。如果应用退出需要等待更长时间，则需要设置 pod 的 `terminationGracePeriodSeconds` 参数，将 `terminationGracePeriodSeconds` 从缺省的 30S 延长到了 60S 如下所示：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sleep
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sleep
  template:
    metadata:
      labels:
        app: sleep
    spec:
      containers:
      - image: busybox:latest
        imagePullPolicy: Always
        name: sleep
      terminationGracePeriodSeconds: 60
```

# 应用未监听 0.0.0.0 导致连接异常

通常，一个应用程序将同时绑定 lo 与 eth0。然而，具有内部逻辑的应用程序（如管理接口）可能会选择仅绑定到 lo 网络设备，以避免来自其他 pod 的访问。
此外，一些应用程序，通常是有状态的应用程序，选择只绑定到 eth0。在 istio 1.10 之前的版本，istio 要求应用提供服务时监听 `0.0.0.0`，因为 127 和 Pod IP 地址都被 envoy 占用了，有些应用启动时没有监听 `0.0.0.0` 或 `::` 的地址，就会导致无法正常通信。

在 Istio 1.10 之前的版本，Envoy 代理与应用程序在同一个 pod 中运行，绑定到 eth0 接口，并将所有入站流量重定向到 lo 接口，如下图所示：
![](/images/2022-11-20-istio-questions-3/2.svg)

上述行为与 Kubernetes 标准的使用方式不同，将可能导致以下异常行为：
1. 仅绑定到 lo 网络设备的应用程序将接收来自其他 pod 的流量，否则这是不允许的（某些应用程序是禁止此行为的）。
2. 仅绑定到 eth0 网络设备的应用程序将不会接收流量。

同时绑定 lo 网络设备和 eth0 网络设备的应用程序（这是典型的）不会受到影响。从 Istio 1.10 开始，proxy 模式被更改为与 Kubernetes 中的标准行为一致，如下所示：
![](/images/2022-11-20-istio-questions-3/3.svg)

在这里，我们可以看到代理不再将流量重定向到 lo 接口，而是将其转发到监听 eth0 的应用程序。因此，Kubernetes 的标准行为得到了保留，这一变化使 Istio 更接近其目标，即成为一个可在零配置的情况下处理现有工作负载的透明代理。此外，它还避免了只绑定到 lo 的应用程序的安全暴露问题。有关 proxy 劫持模式的变化请参考文档[Upcoming networking changes in Istio 1.10](https://istio.io/latest/blog/2021/upcoming-networking-changes/)。

# 启用 Smart DNS 后域名解析失败

**现象**：启用 Istio 的 Smart DNS (智能 DNS) 后，有些 Pod DNS 解析失败。具体情况可以参考[Smart DNS Proxy is breaking dns resolution on latest alpine-based image](https://github.com/istio/istio/issues/31295)。（Istio 1.9.2 以下版本存在该问题，高版本不会存在该问题）。目前主要的问题是：
1. 基于 alpine 镜像的容器内解析 dns 失败。
2. gRPC 服务解析 dns 失败。

**原因**：Smart DNS 初期实现存在一些问题，响应的 DNS 数据包格式跟普通 DNS 有些差别，走底层库 glibc 解析没问题，但使用其它 dns 客户端可能就会失败，如下所示：
1. alpine 镜像底层库使用 `musl libc`，解析行为跟 glibc 有些不一样，导致大部分应用解析失败。
2. 基于 c/c++ 的 gRPC 框架的服务，dns 解析默认使用 c-ares 库，导致部分场景会解析失败。

**解决方式1**：升级 Istio 版本。

**解决方式2**：替换 alpine 镜像到其他使用 glibc 底层库的镜像；c/c++ 的 gRPC 服务，指定 `GRPC_DNS_RESOLVER` 环境变量为 native，走底层库解析，不走默认的 c-ares 库。

# virtualservice 路由匹配顺序问题

**现象**：如下所示的 `VirtualService` 路由规则，将会导致第二个规则一直无法生效。
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: test
spec:
  gateways:
  - default/nginx-gw
  hosts:
  - 'nginx'
  http:
  - match:
    - uri:
        prefix: /nginx
    rewrite:
      uri: /
    route:
    - destination:
        host: nginx.default.svc.cluster.local
        port:
          number: 80
  - match:
    - uri:
        prefix: /nginx-2
    rewrite:
      uri: /
    route:
    - destination:
        host: nginx-2.default.svc.cluster.local
        port:
          number: 80
```

Istio 是按顺序匹配，不像 nginx 使用最长前缀匹配。这里使用 prefix 进行匹配，第一个是 `/nginx`，表示只要访问路径前缀含 `/nginx` 就会转发到第一个服务，由于第二个匹配路径 `/nginx-2` 本身也属于带 `nginx` 的前缀，所以永远不会转发到第二个匹配路径的服务。

**解决方式**：调整匹配顺序，如果前缀有包含关系，越长的放在越前面，如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: test
spec:
  gateways:
  - default/nginx-gw
  hosts:
  - 'nginx'
  http:
  - match:
    - uri:
        prefix: /nginx-2
    rewrite:
      uri: /
    route:
    - destination:
        host: nginx-2.default.svc.cluster.local
        port:
          number: 80
  - match:
    - uri:
        prefix: /nginx
    rewrite:
      uri: /
    route:
    - destination:
        host: nginx.default.svc.cluster.local
        port:
          number: 80
```
也可以使用正则匹配，如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: test
spec:
  gateways:
  - default/nginx-gw
  hosts:
  - 'nginx'
  http:
  - match:
    - uri:
        regex: "/nginx(/.*)?"
    rewrite:
      uri: /
    route:
    - destination:
        host: nginx.default.svc.cluster.local
        port:
          number: 80
  - match:
    - uri:
        regex: "/usrv-2(/.*)?"
    rewrite:
      uri: /
    route:
    - destination:
        host: nginx-2.default.svc.cluster.local
        port:
          number: 80
```

# http Header 大写导致 virtualservice 会话保持不生效

**现象**：在 `DestinationRule` 中配置了基于 `http header` 的会话保持，但是策略没有生效，测试 Yaml 如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: header
spec:
  host: nginx.default.svc.cluster.local
  trafficPolicy:
    loadBalancer:
      consistentHash:
        httpHeaderName: User
```
测试请求传入相同 Header (如 User: test) 却被转发了不同后端服务。

**原因**：Envoy 默认把 header 转成小写，导致路由规则没有生效。

**解决方式**：定义 `httpHeaderName` 时改成小写，如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: header
spec:
  host: nginx.default.svc.cluster.local
  trafficPolicy:
    loadBalancer:
      consistentHash:
        httpHeaderName: user
```

# 支持 websocket 协议

**现象**：业务使用的是 websocket 协议，那么在 istio 中如何配置 websocket 呢？

我们可以参考 Istio 社区中官网示例 [Tornado - Demo Websockets App](https://github.com/istio/istio/tree/master/samples/websockets)。

参考示例的 Yaml 文件如下所示：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: tornado-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
---
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: tornado
spec:
  hosts:
  - "*"
  gateways:
  - tornado-gateway
  http:
  - match:
    - uri:
        prefix: /
    route:
    - destination:
        host: tornado
      weight: 100
```
