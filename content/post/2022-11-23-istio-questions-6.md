---
layout:     post
title:      "使用 Istio 过程中遇到的常见问题与解决方法（六）"
subtitle:   "在使用 Istio 过程中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "陈谭军"
date: 2022-11-23
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
[使用 Istio 过程中遇到的常见问题与解决方法（六）](https://tanjunchen.github.io/post/2022-11-23-istio-questions-6/) 

# Istio 常见问题列表

1. sidecar 常见排查手段
1. 配置完 DestinationRule 后出现 503
1. 控制平面出现 pilot_eds_no_instances 指标
1. 控制平面出现 pilot_conflict_inbound_listener 指标
1. 在灰度发布的场景时，流量未按照预期的配置进行流量治理
1. 配置的 ServiceEnvoy 将外部服务注册到网格内部时，未生效
1. sidecar 自动注入失败
1. 控制平面出现 pilot_total_rejected_configs 指标
1. Envoy 日志中出现 headers size exceeds limit 错误
1. 强制删除命名空间

# sidecar 常见排查手段

变更 istio 网关 ingress-gateway 日志等级，查看网关更详细的日志，编辑 ingress-gateway deploy 日志等级，如下所示：

![](/images/2022-11-23-istio-questions-6/1.png)

更改业务 Pod 中的 istio-proxy 日志等级，便于查看 envoy 的日志

```bash
# 修改日志级别（包含none、error、warn、info、debug）
istioctl -n namespace proxy-config log <Pod> --level 日志级别
kubectl -n default exec -it  Pod名称 -c istio-proxy bash

# 变更 envoy 中的所有组件的日志级别
curl -s -X POST 127.1:15000/logging?level=trace

# 变更 envoy 中的 lua 日志级别
curl -s -X POST 127.1:15000/logging?lua=debug
```

查看 Envoy 的 xds 配置
```bash
在 istio-proxy 容器中 curl localhost:15000/config_dump > config_dump
```

获取 istiod 控制平面中的所有的 CRD 信息
```bash
curl -s 127.1:15014/debug/configz
```

获取控制平面的内部状态与指标信息
```bash
curl -s 127.1:15014/metrics
```

获取数据平面 Envoy 收取到服务发现的实例信息及状态指标
```bash
curl -s 127.1:15000/clusters
```

istioctl 自身提供的工具，istioctl ps 与 istioctl pc
```bash
istioctl ps
NAME                                                  CLUSTER        CDS        LDS        EDS        RDS          ECDS         ISTIOD                     VERSION
details-v1-7d88846999-wtjct.default                   Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
istio-egressgateway-79c57f9f64-b49zs.istio-system     Kubernetes     SYNCED     SYNCED     SYNCED     NOT SENT     NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
istio-ingressgateway-fd7c86d97-4bbsp.istio-system     Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
productpage-v1-7795568889-npt8f.default               Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
ratings-v1-754f9c4975-cvp2h.default                   Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
reviews-v1-55b668fc65-vhdsf.default                   Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
reviews-v2-858f99c99-kdlcj.default                    Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
reviews-v3-7886dd86b9-zs89p.default                   Kubernetes     SYNCED     SYNCED     SYNCED     SYNCED       NOT SENT     istiod-cdb755b69-7x4tl     1.15.0
istioctl ps productpage-v1-7795568889-npt8f.default
Clusters Match
Listeners Match
Routes Match (RDS last loaded at Tue, 01 Nov 2022 19:29:14 CST)
```

# 配置完 DestinationRule 后出现 503

可以查看是否由于 DestinationRule 与全局的 TLS 策略有冲突导致，此错误只有在安装期间禁用了自动双向 TLS 时，才会看到。任何时候应用 DestinationRule，都要确保 trafficPolicy TLS mode 和全局的配置一致。

# 出现 pilot_eds_no_instances 指标

**原因：**
可能原因是 service selector 标签没有匹配到相关联的 Pod，或者 service 与之关联的 Pod 没有启动。

**排查：**
可以排查 Pod 的标签与 Service selector 字段是否匹配，或 DestinationRule 子集标签是否配置正确，或者查看 ep 是否关联了这个 Pod。

**案例：**
手动编辑 DestinationRule review name v1 的 version 为 v1-bug。

![](/images/2022-11-23-istio-questions-6/2.png)

![](/images/2022-11-23-istio-questions-6/3.png)

重新从浏览器打开页面，review 页面出现报错。
![](/images/2022-11-23-istio-questions-6/4.png)

**快速定位：**

1、查看 istiod 控制平面的日志，出现 pilot_eds_no_instances 异常指标。

![](/images/2022-11-23-istio-questions-6/5.png)

2、查看 productpage Pod 中的业务 istio-proxy 日志。

![](/images/2022-11-23-istio-questions-6/6.png)

3、进入到 productpage Pod 中的 istio-proxy 中，查看 clusters。可以查看到 envoy 没有 reviews v1 相关的 cluster，v2/v3 而是有相关的 cluster。执行 ``curl localhost:15000/clusters | grep reviews`` 命令，结果如下所示：

![](/images/2022-11-23-istio-questions-6/7.png)

4、查看 productpage Pod 中的 istio-proxy 的 config_dump
```bash
kubectl -n default exec -it productpage-v1-7795568889-npt8f -c istio-proxy --  curl localhost:15000/config_dump > config_dump
```

5、使用 istioctl 工具，pc、ps 查看 all、bootstrap、cluster、endpoint、listener、log、route、secret 等 envoy 运行时的参数。
![](/images/2022-11-23-istio-questions-6/8.png)

6、编辑 Destinationrule reviews 恢复正常
![](/images/2022-11-23-istio-questions-6/9.png)

# 出现 pilot_conflict_inbound_listener 指标

**原因：** 这个指标的是由于协议冲突导致的

**排查：** 重点排查 k8s Service 资源，是否存在相同端口上配置了不同协议的情况。

# 流量灰度发布失效

**排查：**

1. 可以排查 VirtualService 的 host 字段是否配置错误，match 字段的匹配规则是否错误，和关于子集的配置是否错误，还有 DestinationRule 下关于标签和子集是否匹配等方面排查。
2. 添加或删除配置时候，可能出现 503 错误，这是由于配置传播未到达导致。为确保不出现此情况，在添加配置时，应当先更新 DestinationRule，等配置传播到 envoy，再更新 VirtualService 的配置对新添加的子集进行引用。当删除子集时，应当先删除 VirtualService 对任何子集的引用，等配置传播到 envoy，再更新 DestinationRule ，删除不用的子集。还可能出现配有故障注入和重试/超时策略的 VirtualService 未按预期工作。由于 Istio 不支持在同一个 VirtualService 上配置故障注入和重试或超时策略，如果有此需求，可以通过 EnvoyFilter 注入故障。

# ServiceEnvoy 外部服务功能未生效

**排查：**
可能是网格内部未开启对 DNS 的相关配置，可以检查下 istio-system 命名空间下的 configmap istio proxyMetadata 字段。
![](/images/2022-11-23-istio-questions-6/10.png)

# Sidecar 自动注入失败

**排查：**

1. 首先确保 Pod 不在 kube-system 或 kube-public命名空间中。 这些命名空间中的 Pod 将忽略 Sidecar 自动注入
2. 确保 Pod 定义中没有 hostNetwork：true。`hostNetwork：true` 的 Pod 将忽略 Sidecar 自动注入。
3. 检查 webhook 是否关于自动注入的标签出现问题或者 istio-system 命名空间下的 configmap istio-sidecar-injector 的默认注入策略是否有误。
4. 排查是否 Pod 中的标签 `sidecar.istio.io/inject: "true"` 设置有误，true 为强制注入，false 则不会强制注入 sidecar。
5. 在注入失败的 Pod 的 Deployment 上运行 `kubectl -n namespace describe deployment name`。通常能在事件中看到调用注入 webhook 失败的原因。

# 出现 pilot_total_rejected_configs 指标

**现象：**
网格中同时存在以下两个 Gateway
![](/images/2022-11-23-istio-questions-6/11.png)

![](/images/2022-11-23-istio-questions-6/12.png)

请求 `https://test1.example.com` 正常返回 404，说明访问到了，请求 `https://test2.example.com` 出现异常。

通过 istiod 监控发现 pilot_total_rejected_configs 指标异常，显示 default/test2 配置被拒绝，导致被拒绝的原因是 **每个域名在同一端口上只能配置一次 TLS**，我们这里 `test1.example.com` 在 2 个 Gateway 的 443 端口都配置了 TLS， 导致其中一个被拒绝，通过监控确认被拒绝的是 test2，`test2.example.com` 和 `test1.example.com` 配置在 test2 的同一个 Server，Server 配置被拒绝导致请求异常，解决此问题可以把 test1 删除后，恢复正常。

# 出现 headers size exceeds limit 错误

**背景：**
某个客户接入 mesh 后，有个 API 接口调用失败，envoy 包含(inbound、outbound 两个方向)，具体报错详情参考如下所示。

**报错日志：**
```bash
2022-12-31T14:24:27.501043Z     debug   envoy client    [C4689] protocol error: headers size exceeds limit
```

**相关问题：** https://github.com/envoyproxy/envoy/issues/13827

**解决方案：** 通过 envoyfilter 调大默认限制值。

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
          max_request_headers_kb: 80
          common_http_protocol_options:
            max_headers_count: 500
  - applyTo: CLUSTER
    match:
      context: ANY
      cluster: 
        portNumber: 5000 
    patch:
      operation: MERGE
      value: # cluster specification
        common_http_protocol_options:
          max_headers_count: 500
```

**总结：**
1. Pod 中监听的端口与程序启动监听的端口不匹配，会导致出现 503 问题
1. envoy 自身对于 header 数量的限制，会出现 502 协议问题。可参见：https://github.com/envoyproxy/envoy/issues/13827。

**排错思路：**
1. 503 错误可以考虑 **程序监听的端口与 Pod 配置的端口不一致**
1. 502 错误可以考虑 **header 数量过大导致**，通过 istio-proxy debug 日志可以观察

# 强制删除命名空间

强制删除 namespace 命令空间的命令如下所示：
```bash
kubectl --kubeconfig=path/config  get namespace istio-system -o json | tr -d "\n" | sed "s/\"finalizers\": \[[^]]\+\]/\"finalizers\": []/" |  kubectl  --kubeconfig=path/config  replace --raw /api/v1/namespaces/istio-system/finalize -f - 
```
