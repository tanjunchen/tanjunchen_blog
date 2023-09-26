---
layout:     post
title:      "使用 Istio 过程中可能会遇到的常见问题与解决方法（二）"
subtitle:   "在使用 Istio 过程中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "陈谭军"
date: 2022-11-19
published: false
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

# Istio 常见问题列表

## 在 Istio 中指定 HTTP Header 大小写

Envoy 缺省会把 http header 的 key 转换为小写，例如有一个 http header `Content-Type: text/html; charset=utf-8`，经过 envoy 代理后会变成 `content-type: text/html; charset=utf-8`。根据 [RFC 2616 规范](https://www.ietf.org/rfc/rfc2616.txt)，在正常情况下，HTTP Header 大小写不会影响结果。

但是在某些情况下，如业务解析 header 依赖大小写、使用的 SDK 对 Header 大小写敏感，上述默认配置会有问题。目前 Envoy 只支持两种规则：全小写（默认使用的规则）、首字母大写（默认没有启用）。我们如何统一 Envoy 中的 Header 小写或者大写呢？。

需要依赖大写 Header 的服务对应的集群中添加规则，将 Header 全部转为首字母大写的形式，如下所示：
```yaml
# 依赖 istio 1.10+ 版本
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
          envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
            '@type': type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
            use_downstream_protocol_config:
              http_protocol_options:
                header_key_format:
                  stateful_formatter:
                    name: preserve_case
                    typed_config:
                      '@type': type.googleapis.com/envoy.extensions.http.header_formatters.preserve_case.v3.PreserveCaseFormatterConfig
  # 配置保留收到的 response header 大小写
  - applyTo: NETWORK_FILTER
    match:
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: MERGE
      value:
        typed_config:
          '@type': type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          http_protocol_options:
            header_key_format:
              stateful_formatter:
                name: preserve_case
                typed_config:
                  '@type': type.googleapis.com/envoy.extensions.http.header_formatters.preserve_case.v3.PreserveCaseFormatterConfig
```
部署上述配置前，Header 的响应如下所示：
```bash
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8
content-length: 1683
date: Mon, 25 Sep 2023 05:48:46 GMT
x-envoy-upstream-service-time: 6
```

部署上述配置后，Header 的响应如下所示：
```bash
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 1683
Date: Mon, 25 Sep 2023 05:44:35 GMT
x-envoy-upstream-service-time: 6
```

**最佳实践**：应用程序应遵循 [RFC 2616 规范](https://www.ietf.org/rfc/rfc2616.txt)，对 Http Header 的处理采用大小写不敏感的原则。有关更多详细的信息可参考[envoy config-http-conn-man-header-casing](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_conn_man/header_casing#config-http-conn-man-header-casing)。

## 业务注入 Sidecar 后 pod 处于 CrashLoopBackOff 状态

**现象**：业务注入 Sidecar 后，Istio Proxy 一直处于 `CrashLoopBackOff` 状态，查看 `istio-proxy` 容器，发现启动失败。
查看 `istio-init` 容器的日志，报错日志如下所示：
```bash
error Command error output: xtables parameter problem: iptables-restore: 
unable to initialize table 'nat' Error occurred at line: 1 
Try `iptables-restore -h' or 'iptables-restore --help' for more information.
2023-09-21T03:33:15.489511Z error Failed to execute: iptables-restore --noflush /tmp/iptables-rules-1695267195488162269.txt828466854, exit status 2
```
出现上述现象的原因是 Kubernetes Pod 所在的 Node 节点上内核缺少 `iptables` 模块，内核模块要求如下所示：
![](/images/2022-11-19-istio-questions-2/1.png)
![](/images/2022-11-19-istio-questions-2/2.png)

具体详细信息可参考：[istio prerequisites](https://istio.io/latest/docs/setup/platform-setup/prerequisites/)。

**解决方式**：因为 istio-proxy 劫持流量需要使用 `iptables`，所以我们需要 Kubernetes Node 节点满足上述 [istio prerequisites](https://istio.io/latest/docs/setup/platform-setup/prerequisites/) 条件。

## Istio Proxy 如何使用 tcpdump 或 iptables

**现象**：在 Kubernetes 集群中，Istio 通过 sidecar 模式将 Envoy 代理注入到每个 Pod 中，所有的入站和出站流量都会经过这个代理。
当流量访问不通或者需要抓取 istio-proxy 中的网络包时，我们需要在容器中执行 `iptables` 或 `tcpdump` 命令，但是会遇到以下类似错误：
```
istio-proxy@ratings-v1-85cc46b6d4-bsg94:/$ iptables -t nat -L
Fatal: can't open lock file /run/xtables.lock: Read-only file system

istio-proxy@ratings-v1-85cc46b6d4-bsg94:/$ sudo iptables -t nat -L
sudo: The "no new privileges" flag is set, which prevents sudo from running as root.
sudo: If sudo is running in a container, you may need to adjust the container configuration to disable the flag.

istio-proxy@ratings-v1-85cc46b6d4-bsg94:/$ tcpdump
tcpdump: eth0: You don't have permission to capture on that device
(socket: Operation not permitted)
istio-proxy@ratings-v1-85cc46b6d4-bsg94:/$ sudo tcpdump
sudo: The "no new privileges" flag is set, which prevents sudo from running as root.
sudo: If sudo is running in a container, you may need to adjust the container configuration to disable the flag.
```

**解决方式**：  
方式1：我们需要给 istio 开启特权模式，并且需要给应用加上 `sidecar.istio.io/enableCoreDump: true` 注解，如下所示：
应用添加 annotations 注解 `sidecar.istio.io/enableCoreDump: "true"`。
```
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
        sidecar.istio.io/enableCoreDump: "true" # 注解
      labels:
        app: sleep
  ...
```
istio-system 命名空间下的 configmap istio-sidecar-injector 设置 privileged 为 true。（需要 Pod 重启重新注入 Sidecar 才会生效）。
```
values: |-
    {
      "global": {
         "proxy": {
            "image": "proxyv2",
            "includeIPRanges": "*",
            "includeInboundPorts": "*",
            "includeOutboundPorts": "",
            "logLevel": "warning",
            "privileged": true,   # 特权模式
            "readinessFailureThreshold": 30,
            "readinessInitialDelaySeconds": 1,
            "readinessPeriodSeconds": 2,
         }
      }
    }
```

方式2：安装 Istio 时就开启特权模式与 `sidecar.istio.io/enableCoreDump`，安装 Istio 命令如下所示：
```
istioctl install --set  values.global.proxy.privileged=true --set values.global.proxy.enableCoreDump=true --set profile=demo
```
其中，`values.global.proxy.privileged=true` 对应上面的特权模式，`values.global.proxy.enableCoreDump=true` 对应上面的只读权限。更多的详细细心可参考 [https://github.com/istio/istio/issues/37769](https://github.com/istio/istio/issues/37769)。

方式3：使用 node 调试工具进入 Pod 所在的 Node 节点，使用 `sudo nsenter -t $PID_OF_SIDECAR_ENVOY -n tcpdump` 或者 `sudo nsenter -t $PID_OF_SIDECAR_ENVOY -n `。

使用 tcpdump 抓取 istio-proxy 中的网络数据包时，有以下命令可以参考。  
```bash
export ETH0_IP=$(ip addr show eth0 | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)
export LOCAL_IP=$(ip addr show lo | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)

# inbound mTLS
sudo tcpdump -i eth0 -n -vvvv  "(dst port 8080 and dst $ETH0_IP) or (src port 8080 and src $ETH0_IP)"
# inbound 明文
sudo tcpdump -i any -n -vvvv -A "(dst port 8080 and dst $ETH0_IP) or (src port 8080 and src $ETH0_IP)"

# outbound 明文
sudo tcpdump -i any -n -vvvv -A  "((dst port 15001 and dst 127.0.0.1) or (dst portrange 20000-65535 and dst $ETH0_IP))"
# outbound mTLS
sudo tcpdump -i eth0 -n -vvvv -A  "((src portrange 20000-65535 and src $ETH0_IP) or (dst portrange 20000-65535 and dst $ETH0_IP))"

# mtls 加密报文
sudo tcpdump -ni eth0 "tcp port 8500 and (tcp[((tcp[12] & 0xf0) >> 2)] = 0x16)
```

## 开启 Istio Proxy 本地局部限流

tcp 限流 ratelimit 过滤器创建在 listener，Envoy 为每个连接调用 ratelimit 限流服务，这样能限制每秒该 listener 上建立的连接数。http 级别限流，ratelimit 过滤器创建在 router，既可以限制到目标 upstream cluster 的所有请求速率，也可以限制不同来源的到目标 upstream cluster 的请求限流。限流中的相关概念，Domain: domain 是一组限流的容器，限流服务所有的 domain 必须是全局唯一的。Descriptor: Descriptor(描述符)是 Domain 拥有的 key/val 列表，限流服务使用它来选择是否进行限流。每一个配置都会包含一个 Descriptor 并且区分大小写和支持嵌套。

当请求的路由或者虚拟主机各自具有过滤器的"本地限流配置"时，http 本地限流过滤器将使用令牌桶限流，服务限流是实例级别限流，这就意味着会为每一个 pod 开启限流，如果存在限流规则每分钟允许 100 个请求，并且存在 3 个 pod 副本，实际测试 1 分钟内则需要发起 300 个请求才可以触发限流。

下面我们就以本地限流举例，探讨如何使用 envoyfilter 给 istio proxy 开启本地限流：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: filter-local-ratelimit-svc
  namespace: istio-system
spec:
  workloadSelector:
    labels:
      app: productpage
  configPatches:
    - applyTo: HTTP_FILTER
      match:
        context: SIDECAR_INBOUND
        listener:
          filterChain:
            filter:
              name: "envoy.filters.network.http_connection_manager"
      patch:
        operation: INSERT_BEFORE
        value:
          name: envoy.filters.http.local_ratelimit
          typed_config:
            "@type": type.googleapis.com/udpa.type.v1.TypedStruct
            type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
            value:
              stat_prefix: http_local_rate_limiter
              token_bucket:
                max_tokens: 10
                tokens_per_fill: 10
                fill_interval: 60s
              filter_enabled:
                runtime_key: local_rate_limit_enabled
                default_value:
                  numerator: 100
                  denominator: HUNDRED
              filter_enforced:
                runtime_key: local_rate_limit_enforced
                default_value:
                  numerator: 100
                  denominator: HUNDRED
              response_headers_to_add:
                - append: false
                  header:
                    key: x-local-rate-limit
                    value: 'true'
```
配置上述 envoyfilter，productpage 实例允许通过的 req/min 不超过 10 次，超过 10 次会触发 429 限流，结果如下所示：
```bash
➜  learn kubectl exec "$(kubectl get pod -l app=ratings -o jsonpath='{.items[0].metadata.name}')" -c ratings -- curl -s productpage:9080/productpage -o /dev/null -w "%{http_code}\n"
200
➜  learn kubectl exec "$(kubectl get pod -l app=ratings -o jsonpath='{.items[0].metadata.name}')" -c ratings -- curl -s productpage:9080/productpage -o /dev/null -w "%{http_code}\n"
429
```

## Trace 链路追踪信息不完整

**现象**：通过 UI 展示的 Trace 链路追踪显示不完整，缺失上下游的链路调用关系。

istio 要使用 trace 链路追踪，并不是说业务完全无侵入，需要业务收到 tracing 相关的 header 后要将其传递给下一个被调用服务。该步骤是无法让 istio 实现的，因为 istio 不知道业务中调用其它服务的请求到底是该对应前面哪个请求，所以需要业务来传递 header，最终才能将链路完整串起来。

**原因**：绝大多数情况下都是因为业务没将 tracing 所需要的 http header 正确传递或根本没有传递。

bookinfo 案例中的 reviews 服务会调用 ratings 服务，其中传递 header 的代码如下所示：
```java
// HTTP headers to propagate for distributed tracing are documented at
// https://istio.io/docs/tasks/telemetry/distributed-tracing/overview/#trace-context-propagation
private final static String[] headers_to_propagate = {
    // All applications should propagate x-request-id. This header is
    // included in access log statements and is used for consistent trace
    // sampling and log sampling decisions in Istio.
    "x-request-id",

    // Lightstep tracing header. Propagate this if you use lightstep tracing
    // in Istio (see
    // https://istio.io/latest/docs/tasks/observability/distributed-tracing/lightstep/)
    // Note: this should probably be changed to use B3 or W3C TRACE_CONTEXT.
    // Lightstep recommends using B3 or TRACE_CONTEXT and most application
    // libraries from lightstep do not support x-ot-span-context.
    "x-ot-span-context",

    // Datadog tracing header. Propagate these headers if you use Datadog
    // tracing.
    "x-datadog-trace-id",
    "x-datadog-parent-id",
    "x-datadog-sampling-priority",

    // W3C Trace Context. Compatible with OpenCensusAgent and Stackdriver Istio
    // configurations.
    "traceparent",
    "tracestate",

    // Cloud trace context. Compatible with OpenCensusAgent and Stackdriver Istio
    // configurations.
    "x-cloud-trace-context",

    // Grpc binary trace context. Compatible with OpenCensusAgent nad
    // Stackdriver Istio configurations.
    "grpc-trace-bin",

    // b3 trace headers. Compatible with Zipkin, OpenCensusAgent, and
    // Stackdriver Istio configurations. Commented out since they are
    // propagated by the OpenTracing tracer above.
    "x-b3-traceid",
    "x-b3-spanid",
    "x-b3-parentspanid",
    "x-b3-sampled",
    "x-b3-flags",

    // SkyWalking trace headers.
    "sw8",

    // Application-specific headers to forward.
    "end-user",
    "user-agent",

    // Context and session specific headers
    "cookie",
    "authorization",
    "jwt",
};

private JsonObject getRatings(String productId, HttpHeaders requestHeaders) {
  ClientBuilder cb = ClientBuilder.newBuilder();
  Integer timeout = star_color.equals("black") ? 10000 : 2500;
  cb.property("com.ibm.ws.jaxrs.client.connection.timeout", timeout);
  cb.property("com.ibm.ws.jaxrs.client.receive.timeout", timeout);
  Client client = cb.build();
  WebTarget ratingsTarget = client.target(ratings_service + "/" + productId);
  Invocation.Builder builder = ratingsTarget.request(MediaType.APPLICATION_JSON);
  for (String header : headers_to_propagate) {
    String value = requestHeaders.getHeaderString(header);
    if (value != null) {
      builder.header(header,value);
    }
  }
  ...
}
```

**解决方式**：在业务中正确地传递 trace 链路追踪中所需要的 header。

## 调整 istio-proxy 日志级别

在 istio 中如何自定义数据面 (proxy) 的日志级别，方便我们排查问题时进行调试。
调低 proxy 日志级别进行 debug 有助于排查问题，但输出内容较多且耗资源，不建议在生产环境开启。

**istioctl**：  
```bash
# 全局设置日志格式
istioctl -n test proxy-config log productpage-v1-xxx --level debug

# 细粒度设置日志格式
istioctl -n test proxy-config log productpage-v1-xxx --level grpc:trace,lua:debug
```
更多 level 可选项参考: `istioctl proxy-config log --help`。

**Pilot Agent HTTP 接口**：  
如果没有 istioctl，直接使用 kubectl 进入 istio-proxy 容器调用 envoy HTTP 接口来动态调整日志级别：
```bash
usage: /logging?<name>=<level> (change single level)
usage: /logging?paths=name1:level1,name2:level2,... (change multiple levels)
usage: /logging?level=<level> (change all levels)
levels: trace debug info warning error critical off

# HTTP 接口
kubectl exec -n test productpage-v1-xxx -c istio-proxy -- curl -XPOST http://localhost:15000/logging?level=debug

# 细粒度 HTTP 接口
kubectl exec -n test productpage-v1-xxx -c istio-proxy -- curl -XPOST http://localhost:15000/logging?paths=grpc:trace,lua:debug
```

**使用 annotation 注解**：  
在部署 Pod（业务） 时配置 annotation 来指定 proxy 日志级别，Yaml 如下所示：
```yaml
template:
  metadata:
    annotations:
      "sidecar.istio.io/logLevel": debug # 可选: trace, debug, info, warning, error, critical, off
```
如何细粒度的调整 envoy 日志级别呢？可以给 Pod（业务） 指定 annotation 来配置，如下所示：
```yaml
template:
  metadata:
    annotations:
      "sidecar.istio.io/componentLogLevel": "ext_authz:trace,lua:debug"
```
该配置最终会作为 envoy 的 `--component-log-level` 启动参数，更多的详细信息可参见 [component-log-level](https://www.envoyproxy.io/docs/envoy/latest/operations/cli#cmdoption-component-log-level)。

**全局配置**：  
可以全局配置 proxy 日志级别（测试集群使用，生产集群不推荐使用），修改 values 里面的 global.proxy.logLevel 字段即可。
```bash
kubectl -n istio-system edit configmap istio-sidecar-injector
```
如果使用 istioctl 安装 istio，使用类似以下命令配置全局 proxy 日志级别：
```bash
istioctl install --set profile=demo --set values.global.proxy.logLevel=debug
```

## Envoy 默认重试策略导致服务异常

## Envoy 默认熔断不生效

## 长链接导致 Envoy CPU 负载不均衡

## Metrics 导致 Envoy 内存爆炸增长
