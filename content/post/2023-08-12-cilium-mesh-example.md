---
layout:     post
title:      "Cilium Mesh 常见场景与示例"
subtitle:   "Cilium Mesh 流量治理功能，如限流、熔断、负载均衡、灰度、Admin等"
description: "从早期开始，Cilium 就通过网络和应用程序协议层来提供连接、负载平衡、安全性和可观察性，从而与服务网格概念保持良好一致。对于所有网络处理，包括 IP、TCP 和 UDP 等协议，Cilium 使用 eBPF 作为高效的内核数据路径。HTTP、Kafka、gRPC、DNS 等应用层协议通过 Envoy 等代理进行解析。"
author: "陈谭军"
date: 2023-08-12
#image: "/img"
published: true
tags:
    - eBPF
    - cilium
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

Cilium 官方版本给出的 Service Mesh 全景图，不同于其它 Service Mesh 开源项目设计了很多 CRD 概念，Cilium Service Mesh 当前专注实现了 mesh data plane，通过开放、包容的设计，能够对接其它 control plane，当前版本已实现了对 Envoy CRD、Kubernetes ingress、Istio、Spiffe、Gateway API 的支持。

![](/images/2023-08-12-cilium-mesh-example/1.png)

# 前言

Cilium Service Mesh 与其它 ServiceMesh 显著对比：
* 当前 Service Mesh 领域中， per-pod proxy (即 sidecar) 大行其道，Cilium 走出了 per-node proxy 路线的项目，其规避了 sidecar 资源开销多、网络延时高等弊端。
* 其它 Service Mesh 项目几乎都是借助 Linux 内核网络协议栈劫持流量，而 Cilium Service Mesh 基于 eBPF datapath，有着天生的加速效果。
* Cilium Service Mesh 承载于 Cilium CNI 的底座能力，Cilium CNI 本身提供的网络 policy、多集群 cluster mesh、eBPF 加速、观察性 hubble 等能力，其功能非常丰富。

Cilium 实现了 2个新的 CRD，CiliumEnvoyConfig 和 CiliumClusterwideEnvoyConfig，两者的写法和作用几乎相同，唯一区别是，CiliumEnvoyConfig 是 namespace scope，而 CiliumClusterwideEnvoyConfig 是 cluster scope。

本篇文章通过 Cilium Mesh 示例来了解如何配置 CiliumEnvoyConfig、CiliumClusterwideEnvoyConfig。

# 搭建 Kubernetes 集群

使用 Kind 构建 k8s 集群，具体如下所示：

```bash
kind create cluster  --image=kindest/node:v1.22.17 --name  tanjunchen
Creating cluster "tanjunchen" ...
⢀⡱ Ensuring node image (kindest/node:v1.22.17) 🖼
⢎⡀ Ensuring node image (kindest/node:v1.22.17) 🖼
⠎⠁ Ensuring node image (kindest/node:v1.22.17) 🖼
 ✓ Ensuring node image (kindest/node:v1.22.17) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-tanjunchen"
You can now use your cluster with:
kubectl cluster-info --context kind-tanjunchen
Thanks for using kind! 😊

root@instance-00qqerhq:~/cilium-mesh# kubectl get nodes
NAME                       STATUS   ROLES                  AGE   VERSION
tanjunchen-control-plane   Ready    control-plane,master   61s   v1.22.17
root@instance-00qqerhq:~/cilium-mesh# kubectl version --short
Flag --short has been deprecated, and will be removed in the future. The --short output will become the default.
Client Version: v1.27.2
Kustomize Version: v5.0.1
Server Version: v1.22.17
WARNING: version difference between client (1.27) and server (1.22) exceeds the supported minor version skew of +/-1
```

# 部署测试应用

部署测试应用 wrk 与 nginx，具体如下所示：

```bash
root@instance-00qqerhq:~/cilium-mesh# kubectl apply -f wrk-nginx.yaml
deployment.apps/wrk unchanged
service/nginx unchanged
deployment.apps/nginx configured
root@instance-00qqerhq:~/cilium-mesh# kubectl get pod
NAME                     READY   STATUS    RESTARTS   AGE
nginx-699bb76bb4-p26v7   1/1     Running   0          2m16s
wrk-64884c57d7-vpml8     1/1     Running   0          2m16s
```

# Cilium Mesh

## 前提条件

* Cilium 必须使用 kubeProxyReplacement 模式为 partial 或 strict。
* 支持的最低 Kubernetes 版本是 1.19。

## 安装

安装 Cilium Mesh

```bash
helm repo add cilium https://helm.cilium.io/
helm install cilium cilium/cilium --version 1.14.0  --namespace kube-system --set kubeProxyReplacement=strict --set-string extraConfig.enable-envoy-config=true  --set envoy.enabled=true --set hubble.relay.enabled=true --set hubble.ui.enabled=true
```

![](/images/2023-08-12-cilium-mesh-example/2.png)

![](/images/2023-08-12-cilium-mesh-example/3.png)

## Envoy 配置

目前仅支持 Envoy API v3。Cilium 节点部署 Envoy 来支持 Cilium HTTP 网络策略和可观察性。Cilium Mesh 中使用的 Envoy 已经针对 Cilium Agent 的需求进行了优化，并且不包含 Envoy 代码库中可用的许多 Envoy 扩展。Envoy 文档中引用的标准类型（type.googleapis.com/envoy.config.listener.v3.Listener 和 type.googleapis.com/envoy.config.route.v3.RouteConfiguration）始终可用。具体拓展如下所示：

```bash
envoy.clusters.dynamic_forward_proxy
envoy.filters.http.dynamic_forward_proxy
envoy.filters.http.ext_authz
envoy.filters.http.jwt_authn
envoy.filters.http.local_ratelimit
envoy.filters.http.oauth2
envoy.filters.http.ratelimit
envoy.filters.http.router
envoy.filters.http.set_metadata
envoy.filters.listener.tls_inspector
envoy.filters.network.connection_limit
envoy.filters.network.ext_authz
envoy.filters.network.http_connection_manager
envoy.filters.network.local_ratelimit
envoy.filters.network.mongo_proxy
envoy.filters.network.mysql_proxy
envoy.filters.network.ratelimit
envoy.filters.network.tcp_proxy
envoy.filters.network.sni_cluster
envoy.filters.network.sni_dynamic_forward_proxy
envoy.stat_sinks.metrics_service
envoy.transport_sockets.raw_buffer
envoy.upstreams.http.http
envoy.upstreams.http.tcp
```

# 场景

Cilium 提供了通过 CRD CiliumEnvoyConfig 和 CiliumClusterwideEnvoyConfig 控制 L7 流量。

**这些 Envoy CRD 配置根本没有经过 K8s 验证，因此 Envoy 资源中的任何错误只会在 Cilium Agent 看到。kubectl apply 将报告成功，而解析和/或安装节点本地 Envoy 实例的资源可能会失败。目前验证这一点的唯一方法是观察 Cilium Agent 日志中的错误和警告。**

## 配置 Admin

给 envoy 下发 admin 配置，使其暴露 admin 管理界面。
```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideEnvoyConfig
metadata:
  name: envoy-admin-listener
spec:
  resources:
  - "@type": type.googleapis.com/envoy.config.listener.v3.Listener
    name: envoy-admin-listener
    address:
      socket_address:
        address: "::"
        ipv4_compat: true
        port_value: 9901
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: envoy-admin-listener
          route_config:
            name: admin_route
            virtual_hosts:
            - name: "admin_route"
              domains: ["*"]
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: "envoy-admin"
          use_remote_address: true
          skip_xff_append: true
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
```

查看 envoy 的 config_dump 接口，如下所示：

![](/images/2023-08-12-cilium-mesh-example/4.png)

## 重写

部署应用

```bash
kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/1.14.0/examples/kubernetes/servicemesh/envoy/test-application.yaml
```

![](/images/2023-08-12-cilium-mesh-example/5.png)

测试应用工作负载包括：两个客户端 client 和 client2，两个服务 echo-service-1 和 echo-service-2。

![](/images/2023-08-12-cilium-mesh-example/6.png)

配置环境变量

```bash
export CLIENT2=$(kubectl get pods -l name=client2 -o jsonpath='{.items[0].metadata.name}')
export CLIENT=$(kubectl get pods -l name=client -o jsonpath='{.items[0].metadata.name}')
```

我们将使用 Envoy 配置来请求服务 echo-service-1 和 echo-service-2。我们可以请求 /，但是请求 /foo 路径，就会报 404。

```bash
kubectl exec -it $CLIENT2 -- curl -I echo-service-1:8080/foo
kubectl exec -it $CLIENT2 -- curl -I echo-service-1:8080
kubectl exec -it $CLIENT2 -- curl -I echo-service-2:8080
```

![](/images/2023-08-12-cilium-mesh-example/7.png)

部署 envoy-lb-listener.yaml ，该文件定义了 CiliumClusterwideEnvoyConfig，如下所示：
```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideEnvoyConfig
metadata:
  name: envoy-lb-listener
spec:
  services:
    - name: echo-service-1
      namespace: default
    - name: echo-service-2
      namespace: default
  resources:
    - "@type": type.googleapis.com/envoy.config.listener.v3.Listener
      name: envoy-lb-listener
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: envoy-lb-listener
                rds:
                  route_config_name: lb_route
                use_remote_address: true
                skip_xff_append: true
                http_filters:
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
    - "@type": type.googleapis.com/envoy.config.route.v3.RouteConfiguration
      name: lb_route
      virtual_hosts:
        - name: "lb_route"
          domains: [ "*" ]
          routes:
            - match:
                prefix: "/"
              route:
                weighted_clusters:
                  clusters:
                    - name: "default/echo-service-1"
                      weight: 50
                    - name: "default/echo-service-2"
                      weight: 50
                retry_policy:
                  retry_on: 5xx
                  num_retries: 3
                  per_try_timeout: 1s
                regex_rewrite:
                  pattern:
                    google_re2: { }
                    regex: "^/foo.*$"
                  substitution: "/"
    - "@type": type.googleapis.com/envoy.config.cluster.v3.Cluster
      name: "default/echo-service-1"
      connect_timeout: 5s
      lb_policy: ROUND_ROBIN
      type: EDS
      outlier_detection:
        split_external_local_origin_errors: true
        consecutive_local_origin_failure: 2
    - "@type": type.googleapis.com/envoy.config.cluster.v3.Cluster
      name: "default/echo-service-2"
      connect_timeout: 3s
      lb_policy: ROUND_ROBIN
      type: EDS
      outlier_detection:
        split_external_local_origin_errors: true
        consecutive_local_origin_failure: 2
```
上述配置两个后端 echo 服务之间的请求比例为 50/50，并且将路径 /foo 重写为 /，由于路径重写，对 /foo 的请求现在应该会成功。我们发现服务重写成功，原本 /foo 是请求响应 404，配置策略后是可以成功的，如下所示：

![](/images/2023-08-12-cilium-mesh-example/8.png)

## 限流

针对 echo-service-1 配置 CiliumClusterwideEnvoyConfig 限流策略，如下所示：
```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideEnvoyConfig
metadata:
  name: envoy-lb-listener
spec:
  services:
    - name: echo-service-1
      namespace: default
  resources:
    - "@type": type.googleapis.com/envoy.config.listener.v3.Listener
      name: envoy-lb-listener
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: envoy-ratelimit
                rds:
                  route_config_name: lb_route
                use_remote_address: true
                skip_xff_append: true
                http_filters:
                - name: envoy.filters.http.local_ratelimit
                  typed_config:
                    "@type": type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                    stat_prefix: http_local_rate_limiter
                    token_bucket:
                      max_tokens: 2
                      tokens_per_fill: 2
                      fill_interval: 5s
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
                    - append_action: OVERWRITE_IF_EXISTS_OR_ADD
                      header:
                        key: x-local-rate-limit
                        value: 'true'
                    local_rate_limit_per_downstream_connection: false
                - name: envoy.filters.http.router
                  typed_config:
                    "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
    - "@type": type.googleapis.com/envoy.config.route.v3.RouteConfiguration
      name: lb_route
      virtual_hosts:
        - name: "lb_route"
          domains: [ "*" ]
          routes:
            - match:
                prefix: "/"
              route:
                weighted_clusters:
                  clusters:
                    - name: "default/echo-service-1"
                      weight: 100
                retry_policy:
                  retry_on: 5xx
                  num_retries: 3
                  per_try_timeout: 1s
    - "@type": type.googleapis.com/envoy.config.cluster.v3.Cluster
      name: "default/echo-service-1"
      connect_timeout: 5s
      lb_policy: ROUND_ROBIN
      type: EDS
      outlier_detection:
        split_external_local_origin_errors: true
        consecutive_local_origin_failure: 2
```
![](/images/2023-08-12-cilium-mesh-example/9.png)

执行以下操作，触发限流。
```bash
export CLIENT2=$(kubectl get pods -l name=client2 -o jsonpath='{.items[0].metadata.name}')
for i in {1..5}; do  kubectl exec -it $CLIENT2 -- curl -I echo-service-1:8080 | grep -E "x-local-rate-limit|429|local_rate_limited"; done
```

![](/images/2023-08-12-cilium-mesh-example/10.png)

![](/images/2023-08-12-cilium-mesh-example/11.png)

因为 echo-service-2 没有配置限流策略，所以请求 echo-service-2 没有触发限流。

![](/images/2023-08-12-cilium-mesh-example/12.png)

## 熔断

部署 fortio 压测工具。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: fortio
  labels:
    app: fortio
    service: fortio
spec:
  ports:
  - port: 8080
    name: http
  selector:
    app: fortio
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fortio-deploy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fortio
  template:
    metadata:
      labels:
        app: fortio
    spec:
      containers:
      - name: fortio
        image: fortio/fortio:latest_release
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
          name: http-fortio
        - containerPort: 8079
          name: grpc-ping
```

给 echo-service-1 配置 CiliumClusterwideEnvoyConfig 或者 CiliumEnvoyConfig 熔断策略。
![](/images/2023-08-12-cilium-mesh-example/13.png)

```yaml
apiVersion: cilium.io/v2
kind: CiliumEnvoyConfig
metadata:
  name: envoy-circuit-breaker
spec:
  services:
    - name: echo-service-1
      namespace: default
  resources:
    - "@type": type.googleapis.com/envoy.config.listener.v3.Listener
      name: envoy-lb-listener
      filter_chains:
        - filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                stat_prefix: envoy-lb-listener
                rds:
                  route_config_name: lb_route
                use_remote_address: true
                skip_xff_append: true
                http_filters:
                  - name: envoy.filters.http.router
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
    - "@type": type.googleapis.com/envoy.config.route.v3.RouteConfiguration
      name: lb_route
      virtual_hosts:
        - name: "lb_route"
          domains: [ "*" ]
          routes:
            - match:
                prefix: "/"
              route:
                weighted_clusters:
                  clusters:
                    - name: "default/echo-service-1"
                      weight: 100
    - "@type": type.googleapis.com/envoy.config.cluster.v3.Cluster
      name: "default/echo-service-1"
      connect_timeout: 5s
      lb_policy: ROUND_ROBIN
      type: EDS
      circuit_breakers:
        thresholds:
        - priority: "DEFAULT"
          max_requests: 2
          max_pending_requests: 1
      outlier_detection:
        split_external_local_origin_errors: true
        consecutive_local_origin_failure: 2
```
![](/images/2023-08-12-cilium-mesh-example/14.png)

使用两个并发连接 (-c 2) 调用服务并发送 20 个请求 (-n 20)。
```bash
kubectl exec "$FORTIO_POD" -c fortio -- /usr/bin/fortio load -c 2 -qps 0 -n 20 http://echo-service-1:8080 
```
如下所示，当并发请求 echo-service-1 压力较大时，会触发熔断策略。
```bash
root@instance-00qqerhq:~/cilium-mesh/strateges# kubectl exec "$FORTIO_POD" -c fortio -- /usr/bin/fortio load -c 2 -qps 0 -n 20 http://echo-service-1:8080
{"ts":1691997950.946896,"level":"info","file":"scli.go","line":107,"msg":"Starting Φορτίο 1.57.3 h1:kdPlBiws3cFsLcssZxCt2opFmHj14C3yPBokFhMWzmg= go1.20.6 amd64 linux"}
Fortio 1.57.3 running at 0 queries per second, 4->4 procs, for 20 calls: http://echo-service-1:8080
{"ts":1691997950.947488,"level":"info","file":"httprunner.go","line":100,"msg":"Starting http test","run":"0","url":"http://echo-service-1:8080","threads":"2","qps":"-1.0","warmup":"parallel","conn-reuse":""}
Starting at max qps with 2 thread(s) [gomax 4] for exactly 20 calls (10 per thread + 0)
{"ts":1691997950.950205,"level":"warn","file":"http_client.go","line":1104,"msg":"Non ok http code","code":"503","status":"HTTP/1.1 503","thread":"0","run":"0"}
{"ts":1691997950.976027,"level":"info","file":"periodic.go","line":832,"msg":"T001 ended after 27.10868ms : 10 calls. qps=368.8855377687147"}
{"ts":1691997950.976465,"level":"info","file":"periodic.go","line":832,"msg":"T000 ended after 27.547964ms : 10 calls. qps=363.0032331971974"}
Ended after 27.591205ms : 20 calls. qps=724.87
{"ts":1691997950.976519,"level":"info","file":"periodic.go","line":564,"msg":"Run ended","run":"0","elapsed":"27.591205ms","calls":"20","qps":"724.8686673887566"}
Aggregated Function Time : count 20 avg 0.0027248375 +/- 0.002902 min 0.001064346 max 0.010990329 sum 0.05449675
# range, mid point, percentile, count
>= 0.00106435 <= 0.002 , 0.00153217 , 70.00, 14
> 0.002 <= 0.003 , 0.0025 , 80.00, 2
> 0.003 <= 0.004 , 0.0035 , 85.00, 1
> 0.006 <= 0.007 , 0.0065 , 90.00, 1
> 0.01 <= 0.0109903 , 0.0104952 , 100.00, 2
# target 50% 0.00171211
# target 75% 0.0025
# target 90% 0.007
# target 99% 0.0108913
# target 99.9% 0.0109804
Error cases : count 1 avg 0.001306888 +/- 0 min 0.001306888 max 0.001306888 sum 0.001306888
# range, mid point, percentile, count
>= 0.00130689 <= 0.00130689 , 0.00130689 , 100.00, 1
# target 50% 0.00130689
# target 75% 0.00130689
# target 90% 0.00130689
# target 99% 0.00130689
# target 99.9% 0.00130689
# Socket and IP used for each connection:
[0]   2 socket used, resolved to 10.96.39.34:8080, connection timing : count 2 avg 0.0002502065 +/- 6.296e-05 min 0.000187245 max 0.000313168 sum 0.000500413
[1]   1 socket used, resolved to 10.96.39.34:8080, connection timing : count 1 avg 0.00018792 +/- 0 min 0.00018792 max 0.00018792 sum 0.00018792
Connection time histogram (s) : count 3 avg 0.00022944433 +/- 5.92e-05 min 0.000187245 max 0.000313168 sum 0.000688333
# range, mid point, percentile, count
>= 0.000187245 <= 0.000313168 , 0.000250207 , 100.00, 3
# target 50% 0.000218726
# target 75% 0.000265947
# target 90% 0.00029428
# target 99% 0.000311279
# target 99.9% 0.000312979
Sockets used: 3 (for perfect keepalive, would be 2)
Uniform: false, Jitter: false, Catchup allowed: true
IP addresses distribution:
10.96.39.34:8080: 3
Code 200 : 19 (95.0 %)
Code 503 : 1 (5.0 %)
Response Header Sizes : count 20 avg 370.55 +/- 85.01 min 0 max 391 sum 7411
Response Body/Total Sizes : count 20 avg 2336.75 +/- 480.8 min 241 max 2448 sum 46735
All done 20 calls (plus 0 warmup) 2.725 ms avg, 724.9 qps
root@instance-00qqerhq:~/cilium-mesh/strateges#
```

## Metric 

给 envoy 下发 Prometheus 配置，使其暴露 Metric 指标。
```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideEnvoyConfig
metadata:
  name: envoy-prometheus-metrics-listener
spec:
  resources:
  - "@type": type.googleapis.com/envoy.config.listener.v3.Listener
    name: envoy-prometheus-metrics-listener
    address:
      socket_address:
        address: "::"
        ipv4_compat: true
        port_value: 9090
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: envoy-prometheus-metrics-listener
          rds:
            route_config_name: prometheus_route
          use_remote_address: true
          skip_xff_append: true
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
  - "@type": type.googleapis.com/envoy.config.route.v3.RouteConfiguration
    name: prometheus_route
    virtual_hosts:
    - name: "prometheus_metrics_route"
      domains: ["*"]
      routes:
      - match:
          path: "/metrics"
        route:
          cluster: "envoy-admin"
          prefix_rewrite: "/stats/prometheus"
```
查看指标
```bash
http://xxx/stats/prometheus
```
![](/images/2023-08-12-cilium-mesh-example/15.png)

# 总结

本文我带你部署了 Cilium Mesh，并通过功能示例，带你体验了 Cilium Mesh。总之，这种方式能带来一定的便利性，但是流量治理配置主要依靠于 CiliumEnvoyConfig 或者 CiliumClusterwideEnvoyConfig，对于使用者而言不太友好。
