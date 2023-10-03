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

# Istio 高频链接

* Istio 默认使用的端口，见 [ports-used-by-istio](https://istio.io/latest/docs/ops/deployment/requirements/#ports-used-by-istio)
* Istio 资源注解，见 [Resource Annotations](https://istio.io/latest/docs/reference/config/annotations/)
* [Istio 支持的 Kubernetes 版本](https://istio.io/latest/docs/releases/supported-releases/#support-status-of-istio-releases)
* [Istio 官网](https://istio.io/)
* [Kubernetes 官网](https://kubernetes.io/)
* [Envoy 官网](https://www.envoyproxy.io/)

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



# 如何编译 Istio 二进制与相关镜像



# 解读 Istio 代码目录与核心功能

