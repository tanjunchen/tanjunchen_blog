---
layout:     post
title:      "使用 Istio 过程中遇到的常见问题与解决方法（五）"
subtitle:   "在使用 Istio 过程中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "陈谭军"
date: 2022-11-22
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
[使用 Istio 过程中遇到的常见问题与解决方法（五）](https://tanjunchen.github.io/post/2022-11-22-istio-questions-5/)  

# Istio 常见问题列表

1. 无法访问不带 sidecar 的 Pod
1. 使用 ab 压测服务失败
1. 服务使用 istio 保留端口导致 pod 启动失败
1. Envoy 报错: `gRPC config stream closed`
1. Pod 启动卡住 `MountVolume.SetUp failed for volume "istio-token"`
1. Istio 高频链接
1. 服务地域感知不生效
1. Istio 常见的调试技巧、方法、脚本
1. Envoy 常见异常状态码汇总
1. 如何编译 Istio 二进制与相关镜像

# 无法访问不带 sidecar 的 Pod

**现象**：不能从带 sidecar proxy 的 pod 访问不带 sidecar proxy 的服务。

**原因**：Istio 默认对服务会缺省启用 mTLS。带有 sidecar proxy 的 pod 出流量会使用 mTLS 加密，导致接受到流量的 Pod 解析失败，从而无法通信。

**解决办法**：使用 DestinationRule 规则禁用该服务的 mTLS，示例如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: nginx
spec:
  host: nginx
  trafficPolicy:
    loadBalancer:
      simple: ROUND_ROBIN
    tls:
      mode: DISABLE
```

# 使用 ab 压测服务失败

**现象**：为服务配置了 DestinationRule 和 VirtualService，且 VirtualService 绑好了 Gateway，DestinationRule 配置了 trafficPolicy，指定了熔断策略，但使用 ab 压测发现没有触发熔断 (ingressgateway 的 access_log 中 response_flags 没有 "UO")。

**原因**：ab 压测时发送的是 HTTP/1.0 请求，而 envoy 需要 HTTP/1.1，因此返回 `426 Upgrade Required`，根本不会进行转发，所以也就不会返回 503，response_flags 也不会有。

**解决办法**：使用其他压测工具，如 wrk、fortio 等，默认发送 HTTP/1.1 的请求，可以正常触发熔断。

# 服务使用 istio 保留端口导致 pod 启动失败

**现象**：有新启动的 Pod 无法 ready，sidecar 报错，如 `warning	envoy config	gRPC config for type.googleapis.com/envoy.config.listener.v3.Listener rejected: Error adding/updating listener(s) 0.0.0.0_15090: error adding listener: '0.0.0.0_15090' has duplicate address '0.0.0.0:15090' as existing listener`，同时 istiod 也报错，如 `ADS:LDS: ACK ERROR sidecar~172.18.0.185~reviews-v1-7d46f9dd-w5k8q.istio-test~istio-test.svc.cluster.local-20847 Internal:Error adding/updating listener(s) 0.0.0.0_15090: error adding listener: '0.0.0.0_15090' has duplicate address '0.0.0.0:15090' as existing listener`。

**原因**：是 dynamic 配置中也有 `0.0.0.0:15090` 监听导致的冲突，而 dynamic 中监听来源通常是 Kubernetes 的服务发现(Service, ServiceEntry)，检查一下是否有 Service 监听 15090，如下所示：
```
kubectl get service --all-namespaces -o yaml | grep 15090
```
最终发现确实有 Service 用到了 15090 端口，更改成其它端口即可恢复。Sidecar 启动时获取 LDS 规则，istiod 发现 `0.0.0.0:15090` 这个监听重复了，属于异常现象，下发 xDS 规则就会失败，导致 sidecar 一直无法 ready。但并不是所有 envoy 使用的端口都被加入到 static 配置中的监听，只有 15090 和 15021 这两个端口在 static 配置中有监听，也验证了 Service 使用 15021 端口也会有相同的问题。Service 使用其它 envoy 的端口不会造成 sidecar 不 ready 的问题，但至少要保证业务程序也不能去监听这些端口，因为会跟 envoy 冲突，istio 官网也说明了这一点: `To avoid port conflicts with sidecars, applications should not use any of the ports used by Envoy`。15090 端口是 istio 用于暴露 envoy prometheus 指标的端口，是 envoy 使用的端口之一。更多的 Istio 默认使用的端口可参见 [Application Requirements](https://istio.io/latest/docs/ops/deployment/requirements/)。

**最佳实践**：业务尽量不使用 Istio 默认占用的端口。
* Service/ServiceEntry 不能定义 15090 和 15021 端口，不然会导致 Pod 无法启动成功。
* 业务进程不能监听 envoy 使用到的所有端口: `15000, 15001, 15006, 15008, 15020, 15021, 15090`。

# Envoy 报错: `gRPC config stream closed`

**现象**：Envoy 中的日志出现报错 `gRPC config stream closed: 13` 或者 `gRPC config stream closed: 14`。如下所示：
![](/images/2022-11-22-istio-questions-5/1.png)

**原因**：因为控制面默认每 30 分钟强制断开 xDS 连接，然后数据面会自动重新连接控制平面。更多的详情可参考 [Common Issues](https://github.com/istio/istio/wiki/Troubleshooting-Istio#common-issues)。

# Pod 启动卡住 `MountVolume.SetUp failed for volume "istio-token"`

**现象**：Istio 相关的 Pod (注入 sidecar 的 Pod) 一直卡在 ContainerCreating，起不来，describe pod 报错 `MountVolume.SetUp failed for volume "istio-token" : failed to fetch token: the server could not find the requested resource:`。

**原因**：根据官方文档 [Configure third party service account tokens](https://istio.io/latest/docs/ops/best-practices/security/#configure-third-party-service-account-tokens) 的描述得知支持的列表信息如下所示：
* istio-proxy 需要使用 K8S 的 ServiceAccount token，而 K8S 支持 third party 和 first party 两种 token。
* third party token 安全性更高，istio 默认使用这种类型。
* 不是所有集群都支持这种 token，取决于 K8S 版本和 apiserver 配置。

如果集群不支持 third party token，就会导致 ServiceAccount token 不自动创建出来，从而出现上面这种报错。如何判断集群是否启用了该特性呢？可通过一下命令查询：
```bash
kubectl get --raw /api/v1 | jq '.resources[] | select(.name | index("serviceaccounts/token"))'
```
若返回空，说明不支持；若返回如下 json，说明支持：
```json
{
    "name": "serviceaccounts/token",
    "singularName": "",
    "namespaced": true,
    "group": "authentication.k8s.io",
    "version": "v1",
    "kind": "TokenRequest",
    "verbs": [
        "create"
    ]
}
```

什么是 third party token ? 其实就是 [ServiceAccountTokenVolumeProjection](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#service-account-token-volume-projection) 这个特性，在 1.12 beta，1.20 GA。该特性是为了增强 `ServiceAccount token` 的安全性，可以设置有效期(会自动轮转)，避免 token 泄露带来的安全风险，还可以控制 token 的受众。

**解决办法**：方案一：安装 istio 时不使用 `third party token`；方案二：集群启用 `ServiceAccountTokenVolumeProjection` 特性。

方案一：安装 istio 时不使用 `third party token`：使用 istioctl 安装会自动检测集群是否支持 `third party token`，建议强制指定用 `first party token`，用参数 `--set values.global.jwtPolicy=first-party-jwt` 来显示指定，示例如下所示：
```bash
istioctl manifest generate  --set profile=demo  --set values.global.jwtPolicy=first-party-jwtm > istio.yaml
```

方案二：集群启用 `ServiceAccountTokenVolumeProjection` 特性：如何启用 `ServiceAccountTokenVolumeProjection` 这个特性呢？需要给 apiserver 配置类似如下的参数：
```bash
--service-account-key-file=/etc/kubernetes/pki/sa.key 
--service-account-issuer=kubernetes.default.svc
--service-account-signing-key-file=/etc/kubernetes/pki/sa.key # 注意实际路径
--api-audiences=kubernetes.default.svc
```

# Istio 高频链接

* Istio 默认使用的端口，见 [ports-used-by-istio](https://istio.io/latest/docs/ops/deployment/requirements/#ports-used-by-istio)
* Istio 资源注解，见 [Resource Annotations](https://istio.io/latest/docs/reference/config/annotations/)
* [Istio 支持的 Kubernetes 版本](https://istio.io/latest/docs/releases/supported-releases/#support-status-of-istio-releases)
* [Istio 官网](https://istio.io/)
* [Kubernetes 官网](https://kubernetes.io/)
* [Envoy 官网](https://www.envoyproxy.io/)

# 服务地域感知不生效

**现象**：使用 istio 地域感知能力时，测试没生效。

**原因**：DestinationRule 未配置 outlierDetection；client 没配置 service；使用了 headless service 等等。

DestinationRule 未配置 outlierDetection：地域感知默认开启，但还需要配置 DestinationRule，且指定 outlierDetection 才会生效，指定这个配置的作用主要是让 istio 感知 endpoints 是否异常，当前 locality 的 endpoints 发生异常时会 failover 到其它地方的 endpoints。DestinationRule 的示例如下所示：
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: test
spec:
  host: test
  trafficPolicy:
    outlierDetection:
      consecutive5xxErrors: 3
      interval: 30s
      baseEjectionTime: 30s
```

使用 headless service：如果访问 headless service，headless service 本身是不支持地域感知的，因为 istio 会对 headless service 请求直接 passthrough，不做负载均衡，客户端会直接访问到 dns 解析出来的 pod ip。单独创建一个 service (非 headless)即可。

client 没配置 service：istio 控制面会为每个数据面单独下发 EDS，不同数据面实例(Envoy)的 locality 可能不一样，生成的 EDS 也就可能不一样。istio 会获取数据面的 locality 信息，获取方式主要是找到数据面对应的 endpoint 上保存的 region、zone 等信息，如果 client 没有任何 service，也就不会有 endpoint，控制面也就无法获取 client 的 locality 信息，也就无法实现地域感知。解决办法：为 client 配置 service，selector 选中 client 的 label；如果 client 本身不对外提供服务，service 的 ports 也可以随便定义。

# Istio 常见的调试技巧、方法、脚本

* 查看 sidecar 证书
```bash
# 查看证书
istioctl proxy-config secret productpage-v1-66756cddfd-shz6l.default
istioctl proxy-config secret productpage-v1-66756cddfd-shz6l.default -o json
# 查看证书
istioctl proxy-config secret productpage-v1-66756cddfd-shz6l.default -o json | jq '[.dynamicActiveSecrets[] | select(.name == "default")][0].secret.tlsCertificate.certificateChain.inlineBytes' -r | base64 -d | openssl x509 -noout -text
```
* 测试服务与 istiod 的连通性
```bash
# 测试与 istiod 的连通性
kubectl -n test exec test-6fd7477c9d-brqmq -c istio-proxy -- curl -sS istiod.istio-system:15014/debug/endpointz
```
* 查看 istio-proxy 指标
```bash
kubectl exec -it sleep-cdf8d68bc-t7gq5 -c istio-proxy -- curl localhost:15000/stats

kubectl exec -it sleep-cdf8d68bc-t7gq5 -c istio-proxy -- curl localhost:15000/stats/prometheus
```
* 为工作负载取消 sidecar 注入
```yaml
template:
  metadata:
    annotations:
      sidecar.istio.io/inject: "false"
```
* 自定义 proxy 参数
```yaml
template:
  metadata:
    annotations:
      "sidecar.istio.io/proxyCPU": "1000m"
      "sidecar.istio.io/proxyCPULimit": "2"
      "sidecar.istio.io/proxyMemory": "500Mi"
      "sidecar.istio.io/proxyMemoryLimit": "2Gi"
```
更多的注解参考 [annotations](https://istio.io/latest/docs/reference/config/annotations/)。
* 自定义日志级别
```yaml
template:
  metadata:
    annotations:
      # 可选: trace, debug, info, warning, error, critical, off
      "sidecar.istio.io/logLevel": debug 
      "sidecar.istio.io/componentLogLevel": "ext_authz:trace,filter:debug"
```
更多的日志级别调整参考 [cmdoption-component-log-level](https://www.envoyproxy.io/docs/envoy/latest/operations/cli#cmdoption-component-log-level)。
* 不劫持某些 ip 网段
```yaml
template:
  metadata:
    annotations:
      traffic.sidecar.istio.io/excludeOutboundIPRanges: "10.10.31.1/32,10.10.31.2/32"
```
* 全局禁用 mtls
```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: DISABLE
```
* `DestinationRule` 为某个服务启用地域感知
```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: nginx
spec:
  host: nginx
  trafficPolicy:
    outlierDetection:
      consecutive5xxErrors: 3
      interval: 30s
      baseEjectionTime: 30s
```
* 调大 Envoy 默认 header 与请求体大小
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: http-options
  namespace: istio-system
spec:
  configPatches:
  - applyTo: NETWORK_FILTER
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
          max_request_headers_kb: 96 # 96KB, 请求 header 最大限制
  - applyTo: HTTP_FILTER
    match:
      context: GATEWAY
      listener:
        filterChain:
          filter:
            name: "envoy.http_connection_manager"
    patch:
      operation: INSERT_BEFORE
      value:
        name: "envoy.filters.http.buffer"
        typed_config:
          '@type': "type.googleapis.com/envoy.extensions.filters.http.buffer.v3.Buffer"
          max_request_bytes: 10485760  # 10MB, 请求最大限制
```
* 将 Header 全部转为首字母大写
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: http-header-proper-case-words
  namespace: istio-system
spec:
  configPatches:
  # 配置保留 upstream 的 request header 大小写
  - applyTo: CLUSTER
    patch:
      operation: MERGE
      value:
        typed_extension_protocol_options:
          Envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
            '@type': type.googleapis.com/Envoy.extensions.upstreams.http.v3.HttpProtocolOptions
            use_downstream_protocol_config:
              http_protocol_options:
                header_key_format:
                  stateful_formatter:
                    name: preserve_case
                    typed_config:
                      '@type': type.googleapis.com/Envoy.extensions.http.header_formatters.preserve_case.v3.PreserveCaseFormatterConfig
  # 配置保留收到的 response header 大小写
  - applyTo: NETWORK_FILTER
    match:
      listener:
        filterChain:
          filter:
            name: Envoy.filters.network.http_connection_manager
    patch:
      operation: MERGE
      value:
        typed_config:
          '@type': type.googleapis.com/Envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          http_protocol_options:
            header_key_format:
              stateful_formatter:
                name: preserve_case
                typed_config:
                  '@type': type.googleapis.com/Envoy.extensions.http.header_formatters.preserve_case.v3.PreserveCaseFormatterConfig
```
* 为 ingressgateway 启用 gzip 压缩
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  namespace: istio-system
  name: ingressgateway-gzip
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
              name: envoy.filters.network.http_connection_manager
              subFilter:
                name: envoy.filters.http.router
      patch:
        operation: INSERT_BEFORE
        value:
          name: envoy.filters.http.compressor
          typed_config:
            "@type": type.googleapis.com/envoy.extensions.filters.http.compressor.v3.Compressor
            response_direction_config:
              common_config:
                min_content_length: 100
                content_type:
                  - 'application/javascript'
                  - 'application/json'
                  - 'application/xhtml+xml'
                  - 'image/svg+xml'
                  - 'text/css'
                  - 'text/html'
                  - 'text/plain'
                  - 'text/xml'
            compressor_library:
              name: text_optimized
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.compression.gzip.compressor.v3.Gzip
                memory_level: 9
                window_bits: 15
                compression_level: BEST_COMPRESSION
                compression_strategy: DEFAULT_STRATEGY
```
* 给指定 workload 出流量加上 header（全链路灰度）
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: label-outbound-traffic
spec:
  workloadSelector:
    labels:
      app: productpage
  configPatches:
    - applyTo: HTTP_FILTER
      match:
        context: SIDECAR_OUTBOUND
        listener:
          filterChain:
            filter:
              name: envoy.http_connection_manager
              subFilter:
                name: envoy.router
      patch:
        operation: INSERT_BEFORE
        value:
          name: envoy.lua
          typed_config:
            "@type": "type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua"
            inlineCode: |
              function envoy_on_request(request_handle)
                request_handle:headers():add("app-custom", os.getenv("ISTIO_META_WORKLOAD_NAME"))
              end
```

# Envoy 常见异常状态码汇总

* 431 Request Header Fields Too Large：此状态码说明 http 请求 header 大小超限，默认限制为 60 KiB，由 HttpConnectionManager 配置的 max_request_headers_kb 字段决定，最大可调整到 96 KiB。可以通过 EnvoyFilter 调整 max_request_headers_kb 字段来提升 header 大小限制。下述是 V3 版本的 Yaml 文件。（若 header 大小超过 96 KiB，这种情况本身也很不正常，建议将这部分数据放到 body）。
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: max-header
  namespace: istio-system
spec:
  configPatches:
  - applyTo: NETWORK_FILTER
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
          max_request_headers_kb: 96
```

* 访问 StatefulSet Pod IP 返回 404：在 istio 中业务容器访问同集群 Pod IP 返回 404，在 istio-proxy 中访问却正常。Pod 属于 StatefulSet，使用 headless svc，在 istio 中对 headless svc 的支持跟普通 svc 不太一样，如果 pod 用的普通 svc，对应的 listener 有兜底的 passthrough，即转发到报文对应的真实目的IP+Port，但 headless svc 的就没有，我们理解是因为 headless svc 没有 vip，它的路由是确定的，只指向后端固定的 pod，如果路由匹配不上就肯定出了问题，如果也用 passthrough 兜底路由，只会掩盖问题，所以就没有为 headless svc 创建 passthrough 兜底路由。同样的业务，上了 istio 才会有这个问题，也算是 istio 的设计或实现问题。在 istio 场景下 (kubernetes 之上)，请求 config service 就不需要不走 apollo meta server 获取 config service 的 ip 来实现高可用，直接用 kubernetes 的 service 做服务发现就行。幸运的是，apollo 也支持跳过 meta server 服务发现，这样访问 config service 时就可以直接请求 k8s service 了，也就可以解决此问题。

* 426 Upgrade Required：Istio 使用 Envoy 作为数据面转发 HTTP 请求，而 Envoy 默认要求使用 HTTP/1.1 或 HTTP/2，当客户端使用 HTTP/1.0 时就会返回 426 Upgrade Required。ab 压测时会发送 HTTP/1.0 的请求，Envoy 固定返回 426 Upgrade Required，根本不会进行转发，所以压测的结果也不会准确。有些 SDK 或框架可能会使用 HTTP/1.0 协议，比如使用 HTTP/1.0 去资源中心/配置中心拉取配置信息，在不想改动代码的情况下让服务跑在 istio 上，也可以修改 istiod 配置，加上 `PILOT_HTTP10: 1` 环境变量来启用 HTTP/1.0。更多的详情可参考 [envoy-won-t-connect-to-my-http-1-0-service](https://istio.io/latest/docs/ops/common-problems/network-issues/#envoy-won-t-connect-to-my-http-1-0-service)。


# 如何编译 Istio 二进制与相关镜像

本地能够拉取到编译镜像（需要翻墙），如本次实验使用的编译镜像工具是 `gcr.io/istio-testing/build-tools:master-7c2cba5679671f40312e6324d270a0d70ad097d0`；按照以下步骤即可编译与获取 istio 镜像，具体步骤如下所示：
* 克隆 istio 存储库到 `$GOPATH/src/istio.io/`；
* 设置环境变量；
  ```bash
  当前目录：~/opensource/istio
  export USER="tanjunchen"
  export HUB="docker.io/$USER"
  export TAG="06-25-dev"
  ```
* 进入 istio 根目录，编译与构建 istio 所有组件，如 pilot、istioctl 等；
  ```bash
  make build
  ```
* 构建与推送镜像；
  ```bash
  BUILD_WITH_CONTAINER=0 make docker.push
  ```
* 构建并推送特定的镜像；
  ```bash
  BUILD_WITH_CONTAINER=0 make push.docker.pilot
  ```
* 清理二进制与镜像
  ```bash
  make clean
  ```
更多的详细信息可参考 [Preparing for Development](https://github.com/istio/istio/wiki/Preparing-for-Development)。