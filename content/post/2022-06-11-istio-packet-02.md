---
layout:     post
title:      "Istio 中数据包的生命周期 - 下篇"
subtitle:   "在这篇文章中，我们将深入了解 Envoy 配置，探讨组成 Envoy 配置文件的不同组件，以及它们如何协同工作。我们还将演示如何为不同用例配置 Envoy 以实现服务发现、路由、Tracing、UDP 等功能。"
description: ""
author: "陈谭军"
date: 2022-06-11
published: true
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

在《Istio 中数据包的生命周期 - 上篇》文章中，我们学习了服务网格和 Istio 相关概念，Istio 提供流量管理、可观察性、安全性等功能。然后，我们深入研究了 Istio 数据平面中的流量拦截工作机制，该数据平面由一组代理服务组成，这些代理服务使用扩展的 Envoy 在每个 Kubernetes Pod 中作为 sidecar 容器。接着，我们讨论了 sidecar 注入以及 istio-proxy 和 istio-init 作用。最后，我们介绍了入站和出站的流量劫持工作流程。

# 前言

在服务网格的世界里，Envoy 已经成为最受欢迎的代理之一，用于处理服务之间的流量。Envoy 由 Lyft 开发，现在是云原生计算基金会（CNCF）的一个毕业项目，它为处理服务之间的网络流量提供了一个可扩展、高性能和可扩展的解决方案。  
在这篇文章中，我们将深入了解 Envoy 配置，探讨组成 Envoy 配置文件的不同组件，以及它们如何协同工作。我们还将演示如何为不同用例配置 Envoy 以实现服务发现、路由、Tracing、UDP 等功能。

# Envoy Proxy 介绍

Envoy 被设计成一个 sidecar 代理，与服务网格中的每个服务实例一起运行。它拦截服务之间的所有流量，提供负载均衡、流量路由、流量管理和安全性等功能。Envoy 是一个强大的工具，可以通过多种不同的方式进行配置，以满足服务网格的特定需求。  
以下是 Envoy  在 Istio 中的一些重要功能：
* 流量管理：Envoy 的动态路由功能允许 Istio 在服务网格级别管理流量。这使 Istio 能够在不需要更改应用程序代码的情况下执行流量路由、负载均衡和服务发现。Istio 使用 Envoy 的高级路由功能，包括基于路径的路由、基于 header 的路由和故障注入，来实现高级流量管理策略。
* 安全性：Envoy 为 Istio 提供了强大的安全功能，包括加密和身份验证。Istio 使用 Envoy 的 TLS 和 mTLS 支持来保护服务网格中服务之间的通信。Envoy 还支持包括速率限制和 RBAC，允许 Istio 在服务网格中实施细粒度的安全策略等高级访问控制功能。
* 可观察性：Envoy 的可观察性功能使 Istio 能够监控服务网格并对其进行故障排除。Envoy 丰富的遥测数据，包括详细的指标和日志，可用于诊断问题和优化性能。Istio 使用 Envoy 的分布式跟踪功能在服务网格中提供端到端跟踪，让用户了解请求如何在网格中流动，并识别性能瓶颈。
* 可扩展性：Envoy 的模块化架构允许 Istio 轻松地向服务网格添加新功能。Istio 可以添加新的 Envoy 过滤器或配置现有过滤器来实现自定义逻辑，使用户可以根据需要扩展 Istio 的功能。

总体而言，Envoy 丰富的功能使其成为 Istio 服务网格平台的最佳选择。Envoy 的高级流量管理、安全性、可观察性和可扩展性使 Istio 能够提供一个强大而灵活的平台来大规模管理微服务。

# Envoy 处理 Packet 过程

![](/images/2022-06-11-istio-packet-02/1.svg)

当数据包到达 Envoy 时，它在到达最终目的地之前会经过一系列步骤，这些步骤包括以下内容：

* 在 ingress 阶段，Envoy listener 组件通过特定端口和协议（如TCP、HTTP或HTTPS）接受来自下游客户端的连接。Envoy listener filter 提供 SNI 和其他进入 TLS 之前的详细信息，并基于目的地 IP CIDR 范围、SNI、ALPN、源端口等匹配 Envoy network filter。传输套接字（如 TLS 传输套接字）与 filter 链相关联，用于安全通信。
* Envoy network filter 链在网络读取时使用 TLS 传输套接字解密 TCP 连接中的数据，HTTP 连接管理器（HTTP connection manager）过滤器是最后一个过滤链。HTTP 连接管理器中的 HTTP/2 编解码器将来自 TLS 连接的解密数据流解帧并解复用为独立的流，处理每个请求和响应。
* 对于每个 HTTP 流，都会创建并运行相应的 HTTP 过滤器链。请求通过可以读取和修改请求的自定义筛选器，路由器过滤器是最重要的 HTTP 过滤器，位于链的末尾，它根据传入请求的 header 选择路由（router）和集群（cluster）。然后将 header 转发到该集群中的上游端点（endpoint）。路由过滤器从匹配集群的集群管理器中获取 HTTP 连接池，以处理此请求。
* 执行特定集群的负载均衡（load balancer）来找到端点（endpoint），并检查熔断器确定是否允许该请求通过。如果端点（endpoint）的连接池为空或容量不足，则会创建与端点（endpoint）的新连接。上游端点（endpoint）连接的 HTTP/2 编解码器将请求的流与通过单个 TCP 连接到达该上游的任何其他流多路复用并成帧。上游端点（endpoint）连接的 TLS 传输套接字对这些字节进行加密，并将它们写入上游连接的 TCP 套接字。
* 由 headers、可选 body 和 trailers 组成的请求在上游代理，响应在下游代理。响应以与请求相反的顺序通过 HTTP 过滤器，从路由过滤器开始，在发送到下游之前通过自定义过滤器，当响应完成时，流将被销毁，并且完成其他其他操作，包括更新统计信息、写入访问日志等。
* 最后，egress 配置为下游客户端指定端点（endpoint）信息，包括传输协议、加密和其他设置。Envoy 可以配置为使用适当的协议和传输机制将响应转发到下游客户端，允许配置过滤器来处理来自上游服务的响应、添加响应 header、设置 cookie、执行缓存等，还可以配置访问日志过滤器来记录响应。

总体而言，通过配置数据包生命周期的每个阶段，我们可以为现代应用程序实现高级流量管理、可观察性和安全等功能，Envoy 代理配置是高度可定制的，可以根据应用程序架构的特定需求进行定制。

# Envoy 示例

## Envoy front proxy

![](/images/2022-06-11-istio-packet-02/2.svg)

让我们看一个使用 Envoy 代理的示例，在本例中，我们将侦听器配置为接受端口 8000 上的 ingress 流量，并使用 round-robin load balancing 策略将其转发到名为 “service” 的集群，集群被定义为 strict DNS 类型，有 2 个端点（endpoint），每个端点的地址为 version_v1、version_v2，所有端点都监听 9000 端口。
连接管理器（HTTP connection manager）被配置为生成请求 ID，使用自动编解码器类型检测，并使用 “ingress_http” 前缀统计信息。它还指定了一个名为 “service” 的 virtual_hosts，该主机接受任何域的流量，以及一个与前缀为 “/version” 请求匹配路由。然后，该路由被转发到 “service” 集群。  
为了确保 Envoy 与其客户端之间的通信安全，我们使用自签名证书对进行传输层安全性（TLS）身份验证。证书对作为内联字符串提供给 Envoy，但也可以作为文件提供，或者在动态配置场景中通过秘密发现服务（SDS）远程获取。  

总体而言，上述案例演示了如何将 Envoy 用作代理来处理 ingress 流量，并将其转发到具有负载均衡和安全功能的后端服务。Envoy 的配置文件如下所示：
```yaml
static_resources:
  listeners:
  - address:
      socket_address:
        address: 0.0.0.0
        port_value: 8000
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          generate_request_id: true
          codec_type: AUTO
          stat_prefix: ingress_http
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
          route_config:
            name: local_route
            virtual_hosts:
            - name: version
              domains:
              - "*"
              routes:
              - match:
                  prefix: "/version"
                route:
                  cluster: version
      transport_socket:
        name: envoy.transport_sockets.tls
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
          common_tls_context:
            tls_certificates:
            # The following self-signed certificate pair is generated using:
            # $ openssl req -x509 -newkey rsa:2048 -keyout a/front-proxy-key.pem -out  a/front-proxy-crt.pem -days 3650 -nodes -subj '/CN=front-envoy'
            #
            # Instead of feeding it as an inline_string, certificate pair can also be fed to Envoy
            # via filename. Reference: https://envoyproxy.io/docs/envoy/latest/api-v3/config/core/v3/base.proto#config-core-v3-datasource.
            #
            # Or in a dynamic configuration scenario, certificate pair can be fetched remotely via
            # Secret Discovery Service (SDS). Reference: https://envoyproxy.io/docs/envoy/latest/configuration/security/secret.
            - certificate_chain:
                inline_string: |
                  -----BEGIN CERTIFICATE-----
                  MIICqDCCAZACCQCquzpHNpqBcDANBgkqhkiG9w0BAQsFADAWMRQwEgYDVQQDDAtm
                  cm9udC1lbnZveTAeFw0yMDA3MDgwMTMxNDZaFw0zMDA3MDYwMTMxNDZaMBYxFDAS
                  BgNVBAMMC2Zyb250LWVudm95MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC
                  AQEAthnYkqVQBX+Wg7aQWyCCb87hBce1hAFhbRM8Y9dQTqxoMXZiA2n8G089hUou
                  oQpEdJgitXVS6YMFPFUUWfwcqxYAynLK4X5im26Yfa1eO8La8sZUS+4Bjao1gF5/
                  VJxSEo2yZ7fFBo8M4E44ZehIIocipCRS+YZehFs6dmHoq/MGvh2eAHIa+O9xssPt
                  ofFcQMR8rwBHVbKy484O10tNCouX4yUkyQXqCRy6HRu7kSjOjNKSGtjfG+h5M8bh
                  10W7ZrsJ1hWhzBulSaMZaUY3vh5ngpws1JATQVSK1Jm/dmMRciwlTK7KfzgxHlSX
                  58ENpS7yPTISkEICcLbXkkKGEQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQCmj6Hg
                  vwOxWz0xu+6fSfRL6PGJUGq6wghCfUvjfwZ7zppDUqU47fk+yqPIOzuGZMdAqi7N
                  v1DXkeO4A3hnMD22Rlqt25vfogAaZVToBeQxCPd/ALBLFrvLUFYuSlS3zXSBpQqQ
                  Ny2IKFYsMllz5RSROONHBjaJOn5OwqenJ91MPmTAG7ujXKN6INSBM0PjX9Jy4Xb9
                  zT+I85jRDQHnTFce1WICBDCYidTIvJtdSSokGSuy4/xyxAAc/BpZAfOjBQ4G1QRe
                  9XwOi790LyNUYFJVyeOvNJwveloWuPLHb9idmY5YABwikUY6QNcXwyHTbRCkPB2I
                  m+/R4XnmL4cKQ+5Z
                  -----END CERTIFICATE-----
              private_key:
                inline_string: |
                  -----BEGIN PRIVATE KEY-----
                  MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC2GdiSpVAFf5aD
                  tpBbIIJvzuEFx7WEAWFtEzxj11BOrGgxdmIDafwbTz2FSi6hCkR0mCK1dVLpgwU8
                  VRRZ/ByrFgDKcsrhfmKbbph9rV47wtryxlRL7gGNqjWAXn9UnFISjbJnt8UGjwzg
                  Tjhl6EgihyKkJFL5hl6EWzp2Yeir8wa+HZ4Achr473Gyw+2h8VxAxHyvAEdVsrLj
                  zg7XS00Ki5fjJSTJBeoJHLodG7uRKM6M0pIa2N8b6HkzxuHXRbtmuwnWFaHMG6VJ
                  oxlpRje+HmeCnCzUkBNBVIrUmb92YxFyLCVMrsp/ODEeVJfnwQ2lLvI9MhKQQgJw
                  tteSQoYRAgMBAAECggEAeDGdEkYNCGQLe8pvg8Z0ccoSGpeTxpqGrNEKhjfi6NrB
                  NwyVav10iq4FxEmPd3nobzDPkAftfvWc6hKaCT7vyTkPspCMOsQJ39/ixOk+jqFx
                  lNa1YxyoZ9IV2DIHR1iaj2Z5gB367PZUoGTgstrbafbaNY9IOSyojCIO935ubbcx
                  DWwL24XAf51ez6sXnI8V5tXmrFlNXhbhJdH8iIxNyM45HrnlUlOk0lCK4gmLJjy9
                  10IS2H2Wh3M5zsTpihH1JvM56oAH1ahrhMXs/rVFXXkg50yD1KV+HQiEbglYKUxO
                  eMYtfaY9i2CuLwhDnWp3oxP3HfgQQhD09OEN3e0IlQKBgQDZ/3poG9TiMZSjfKqL
                  xnCABMXGVQsfFWNC8THoW6RRx5Rqi8q08yJrmhCu32YKvccsOljDQJQQJdQO1g09
                  e/adJmCnTrqxNtjPkX9txV23Lp6Ak7emjiQ5ICu7iWxrcO3zf7hmKtj7z+av8sjO
                  mDI7NkX5vnlE74nztBEjp3eC0wKBgQDV2GeJV028RW3b/QyP3Gwmax2+cKLR9PKR
                  nJnmO5bxAT0nQ3xuJEAqMIss/Rfb/macWc2N/6CWJCRT6a2vgy6xBW+bqG6RdQMB
                  xEZXFZl+sSKhXPkc5Wjb4lQ14YWyRPrTjMlwez3k4UolIJhJmwl+D7OkMRrOUERO
                  EtUvc7odCwKBgBi+nhdZKWXveM7B5N3uzXBKmmRz3MpPdC/yDtcwJ8u8msUpTv4R
                  JxQNrd0bsIqBli0YBmFLYEMg+BwjAee7vXeDFq+HCTv6XMva2RsNryCO4yD3I359
                  XfE6DJzB8ZOUgv4Dvluie3TB2Y6ZQV/p+LGt7G13yG4hvofyJYvlg3RPAoGAcjDg
                  +OH5zLN2eqah8qBN0CYa9/rFt0AJ19+7/smLTJ7QvQq4g0gwS1couplcCEnNGWiK
                  72y1n/ckvvplmPeAE19HveMvR9UoCeV5ej86fACy8V/oVpnaaLBvL2aCMjPLjPP9
                  DWeCIZp8MV86cvOrGfngf6kJG2qZTueXl4NAuwkCgYEArKkhlZVXjwBoVvtHYmN2
                  o+F6cGMlRJTLhNc391WApsgDZfTZSdeJsBsvvzS/Nc0burrufJg0wYioTlpReSy4
                  ohhtprnQQAddfjHP7rh2LGt+irFzhdXXQ1ybGaGM9D764KUNCXLuwdly0vzXU4HU
                  q5sGxGrC1RECGB5Zwx2S2ZY=
                  -----END PRIVATE KEY-----
  clusters:
  - name: version
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: version
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: version_v1
                port_value: 9000
        - endpoint:
            address:
              socket_address:
                address: version_v2
                port_value: 9000
admin:
  address:
    socket_address:
      address: 0.0.0.0
      port_value: 8001
```

我们通过下述案例来演示 Envoy Proxy 转发流量功能，从 https://github.com/tanjunchen/cloud-native-travel 仓库中克隆源码。 

步骤1：通过在终端中运行以下命令克隆代码库： 
```bash
git clone https://github.com/tanjunchen/cloud-native-travel
```

步骤2：通过运行以下命令进入到 envoy 目录：  
```bash
cd envoy/front-proxy
```

步骤3：通过运行以下命令，执行 docker compose 启动容器：
```bash
➜  front-proxy git:(main) docker compose up -d

➜  front-proxy git:(main) docker ps
CONTAINER ID   IMAGE                           COMMAND                   CREATED          STATUS          PORTS                                         NAMES
2fbd74958af8   tanjunchen/version:v1           "./goapp"                 16 seconds ago   Up 14 seconds   9000/tcp                                      front-proxy-version_v1-1
f1f60cce7a87   envoyproxy/envoy:v1.26.4        "/docker-entrypoint.…"   16 seconds ago   Up 14 seconds   0.0.0.0:8000-8001->8000-8001/tcp, 10000/tcp   front-proxy-front-envoy-1
b70aafcac384   tanjunchen/version:v2           "./goapp"                 16 seconds ago   Up 14 seconds   9000/tcp                                      front-proxy-version_v2-1
```

步骤4：等待容器启动并就绪后，执行以下命令，如下所示：
```bash
➜  front-proxy git:(main) curl -k https://localhost:8000/version
v1
➜  front-proxy git:(main) curl -k https://localhost:8000/version
v2
➜  front-proxy git:(main) curl -k https://localhost:8000/version
v1
➜  front-proxy git:(main) curl -k https://localhost:8000/version
v2
```

步骤5：查看上述响应值，Envoy 轮询随机返回 v1 与 v2，符合预期。

## Envoy Jaeger Tracing 

当应用程序是分布式，并且请求可能跨越多个服务，这时很难理解网络中发生了什么。此刻，Tracing 是帮助开发人员了解不同服务如何相互通信的一个重要功能。我们本次示例演示 Envoy Tracing 功能，Envoy 配置如下所示：
```yaml
static_resources:
  listeners:
  - address:
      socket_address:
        address: 0.0.0.0
        port_value: 8000
    traffic_direction: OUTBOUND
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          generate_request_id: true
          tracing:
            provider:
              name: envoy.tracers.zipkin
              typed_config:
                "@type": type.googleapis.com/envoy.config.trace.v3.ZipkinConfig
                collector_cluster: jaeger
                collector_endpoint: "/api/v2/spans"
                shared_span_context: false
                collector_endpoint_version: HTTP_JSON
          codec_type: AUTO
          stat_prefix: ingress_http
          route_config:
            name: local_route
            virtual_hosts:
            - name: backend
              domains:
              - "*"
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: service1
                decorator:
                  operation: checkAvailability
          http_filters:
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
          use_remote_address: true
  clusters:
  - name: service1
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: service1
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: service1
                port_value: 8000
  - name: jaeger
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: jaeger
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: jaeger
                port_value: 9411
```

本案例提供的配置文件演示了如何在 Envoy 中启用 Zipkin 跟踪器。在该示例中，Envoy 充当前端代理并侦听端口 8000。traffic_direction 字段表示它是一个出站侦听器。tracing 字段已启用，并且将使用收集器的配置信息启用 Zipkin 跟踪器。收集器集群指定为 “jaeger”，收集器端点（endpoint）指定为 “/api/v2/span”，shared_span_context 字段设置为 false，表示 span 上下文不会在服务之间传播。在 virtual_hosts 下指定路由配置，decorator 字段用于设置跨度中的操作名称，在本例中，decorator 设置为 “checkAvailability”。use_remote_address 字段设置为 true，表示 Envoy 应该使用客户端的 IP 地址来确定请求的源地址。
集群（cluster）中定义了不同的后端服务及其关联的（endpoint）。在本例中，只有一个名为 service1 的后端服务，load_assignment 字段设置了（endpoint），端点被定义为 service1:8000。  

总体而言，该配置文件使 Envoy 能够使用 Zipkin 跟踪器捕获跟踪信息，并在服务之间传播调用上下文。开发人员可以使用这些信息深入了解不同服务的通信方式，并调试其分布式应用程序中的问题，总体流程如下所示：

![](/images/2022-06-11-istio-packet-02/3.svg)

步骤1：进入到 ”envoy/jaeger“ 目录：
```bash
cd envoy/jaeger/
```

步骤2：运行以下命令启动 docker 容器：
```bash
➜  jaeger git:(main) docker psdocker compose up -d

➜  jaeger git:(main) docker ps
CONTAINER ID   IMAGE                           COMMAND                   CREATED         STATUS                   PORTS                                                                               NAMES
bd6650e1ce77   jaeger-front-envoy              "/docker-entrypoint.…"   2 minutes ago   Up 2 minutes             0.0.0.0:8000->8000/tcp, 10000/tcp                                                   jaeger-front-envoy-1
e3557ab6a981   jaeger-service1                 "/usr/local/bin/star…"   2 minutes ago   Up 2 minutes (healthy)                                                                                       jaeger-service1-1
2e4d3ea57dcb   jaeger-service2                 "/usr/local/bin/star…"   2 minutes ago   Up 2 minutes (healthy)                                                                                       jaeger-service2-1
a072154fa8ca   jaeger-jaeger                   "/go/bin/all-in-one-…"   2 minutes ago   Up 2 minutes             5775/udp, 5778/tcp, 14250/tcp, 6831-6832/udp, 14268/tcp, 0.0.0.0:10000->16686/tcp   jaeger-jaeger-1
```

步骤3：在浏览器中打开 http://localhost:8000/trace/1。
```bash
Hello from behind Envoy (service 1)! hostname e3557ab6a981 resolved 192.168.0.3
```

步骤4：刷新页面或者通过以下命令产生一些流量。
```bash
➜  jaeger git:(main) curl http://localhost:8000/trace/1
Hello from behind Envoy (service 1)! hostname e3557ab6a981 resolved 192.168.0.3
➜  jaeger git:(main) curl http://localhost:8000/trace/1
Hello from behind Envoy (service 1)! hostname e3557ab6a981 resolved 192.168.0.3
➜  jaeger git:(main) curl http://localhost:8000/trace/1
Hello from behind Envoy (service 1)! hostname e3557ab6a981 resolved 192.168.0.3
```

步骤5：在浏览器中打开 http://localhost:10000/search 并且访问 Jaeger 的搜索页面。

步骤6：在 Jaeger 搜索页面中，从下拉菜单中选择“ front proxy” 服务，然后点击 “Find Traces” 按钮。

![](/images/2022-06-11-istio-packet-02/4.png)

步骤7：查看 http://localhost:8000/trace/1  详细信息，并探索 Envoy 的分布式跟踪功能。

![](/images/2022-06-11-istio-packet-02/5.png)

![](/images/2022-06-11-istio-packet-02/6.png)

Envoy Tracing 最重要的是它将 trace 数据传送到 Jaeger 集群。
然而，为了实现 tracing，应用程序在调用其他服务时必须传递 Envoy 生成的 trace header。
在测试应用程序中，service1 在对 service2 进行调用时传递了 header，如下所示：

```python
TRACE_HEADERS_TO_PROPAGATE = [
    'X-Ot-Span-Context',
    'X-Request-Id',

    # Zipkin headers
    'X-B3-TraceId',
    'X-B3-SpanId',
    'X-B3-ParentSpanId',
    'X-B3-Sampled',
    'X-B3-Flags',

    # Jaeger header (for native client)
    "uber-trace-id",

    # SkyWalking headers.
    "sw8"
]

if service_type == "trace" and int(service_name) == 1:
        # call service 2 from service 1
        headers = {}
        for header in TRACE_HEADERS_TO_PROPAGATE:
            if header in request.headers:
                headers[header] = request.headers[header]
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9000/trace/2", headers=headers) as resp:
                pass
```

## Envoy UDP Proxy

![](/images/2022-06-11-istio-packet-02/7.svg)

Envoy 中的用户数据报协议（UDP）示例简单演示了如何使用 Envoy 代理 UDP 流量。该示例包括侦听端口 5005 上的 UDP 流量的上游服务器和侦听端口 10000 上的 UDP 通信并将其代理到上游服务器的 Envoy 代理。此外，Envoy 在端口 10001 上提供了一个端点（endpoint），用于提供UDP 流量的统计信息。此示例演示了 Envoy 不仅能够用于处理 HTTP 流量，还用于处理 UDP 流量。Envoy 配置如下所示：
```yaml
static_resources:
  listeners:
  - name: listener_0
    address:
      socket_address:
        protocol: UDP
        address: 0.0.0.0
        port_value: 10000
    listener_filters:
    - name: envoy.filters.udp_listener.udp_proxy
      typed_config:
        '@type': type.googleapis.com/envoy.extensions.filters.udp.udp_proxy.v3.UdpProxyConfig
        stat_prefix: service
        matcher:
          on_no_match:
            action:
              name: route
              typed_config:
                '@type': type.googleapis.com/envoy.extensions.filters.udp.udp_proxy.v3.Route
                cluster: service_udp

  clusters:
  - name: service_udp
    type: STRICT_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: service_udp
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: service-udp
                port_value: 5005

admin:
  address:
    socket_address:
      address: 0.0.0.0
      port_value: 10001
```


步骤1：进入到 ”envoy/udp“ 目录：
```bash
cd envoy/udp
```

步骤2：运行以下命令启动 docker 容器，启动 Envoy 和 端口为 5005 的上游服务器：
```bash
➜  udp git:(main) docker-compose up -d

➜  udp git:(main) docker ps
CONTAINER ID   IMAGE                           COMMAND                   CREATED         STATUS         PORTS                                                           NAMES
70c9b8412b12   udp-testing                     "/docker-entrypoint.…"   5 seconds ago   Up 3 seconds   10000/tcp, 0.0.0.0:10000->10000/udp, 0.0.0.0:10001->10001/tcp   udp-testing-1
19add082ed4e   udp-service-udp                 "python -u /udpliste…"   5 seconds ago   Up 3 seconds   5005/tcp, 5005/udp                                              udp-service-udp-1
```

步骤3：发送 UDP 消息将数据包发送到上游服务器，运行以下命令：
```bash
➜  udp git:(main)echo -n OLEH | nc -u -w1 127.0.0.1 10000
➜  udp git:(main)echo -n OLEH | nc -4u -w1 127.0.0.1 10000

➜  udp git:(main) docker compose logs service-udp
udp-service-udp-1  | Listening on UDP port 5005
udp-service-udp-1  | HELO
udp-service-udp-1  | HELO
udp-service-udp-1  | OLEH
```

步骤4：查看 Envoy admin UDP 统计数据：
```bash
➜  udp git:(main) curl -s http://127.0.0.1:10001/stats | grep udp | grep -v "\: 0"
➜  udp git:(main) curl -s http://127.0.0.1:10001/stats | grep udp | grep -v "\: 0"
cluster.service_udp.default.total_match_count: 52
cluster.service_udp.max_host_weight: 1
cluster.service_udp.membership_change: 1
cluster.service_udp.membership_healthy: 1
cluster.service_udp.membership_total: 1
cluster.service_udp.udp.sess_tx_datagrams: 3
cluster.service_udp.update_attempt: 52
cluster.service_udp.update_no_rebuild: 51
cluster.service_udp.update_success: 52
cluster.service_udp.upstream_cx_tx_bytes_total: 12
udp.service.downstream_sess_rx_bytes: 12
udp.service.downstream_sess_rx_datagrams: 3
udp.service.downstream_sess_total: 3
udp.service.idle_timeout: 3
cluster.service_udp.upstream_cx_connect_ms: No recorded values
cluster.service_udp.upstream_cx_length_ms: No recorded values
```

## 动态 XDS

Envoy XDS 是 Istio 的核心功能，它为基于微服务的应用程序提供流量管理、安全性和可观察性等功能。
Envoy XDS 允许 Istio 动态修改 Envoy sidecar 配置。Envoy XDS 如何工作的原理流程图如下所示：

![](/images/2022-06-11-istio-packet-02/8.svg)

1. 配置服务器充当 Envoy 代理在服务网格中路由流量所需的所有配置信息的集中存储库。
2. 配置服务器通过 XDS（发现服务）协议向 Envoy 代理提供动态配置更新，XDS 协议使用 gRPC 来实现控制平面和数据平面之间的通信。
3. 当将新服务添加到服务网格或更新现有服务时，配置服务器会向 Envoy 代理发送新的配置。
4. Envoy 代理应用新的配置更新，并开始根据新规则路由流量。
5. 配置服务器还可以向 Envoy 提供健康检查信息，这使 Envoy 能够仅将流量路由到服务的健康实例。
6. 通过这种方式，控制平面和数据平面一起工作，在服务网格中提供动态服务发现和路由。

接下来给大家演示下 Envoy XDS 示例，Envoy 配置文件如下所示：

```yaml
node:
  cluster: test-cluster
  id: test-id

dynamic_resources:
  ads_config:
    api_type: GRPC
    transport_api_version: V3
    grpc_services:
    - envoy_grpc:
        cluster_name: xds_cluster
  cds_config:
    resource_api_version: V3
    ads: {}
  lds_config:
    resource_api_version: V3
    ads: {}

static_resources:
  clusters:
  - type: STRICT_DNS
    typed_extension_protocol_options:
      envoy.extensions.upstreams.http.v3.HttpProtocolOptions:
        "@type": type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions
        explicit_http_config:
          http2_protocol_options: {}
    name: xds_cluster
    load_assignment:
      cluster_name: xds_cluster
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: go-control-plane
                port_value: 18000

admin:
  address:
    socket_address:
      address: 0.0.0.0
      port_value: 19000
```

步骤1：进入到 ”envoy/dynamic-config-cp“ 目录：
```bash
cd envoy/dynamic-config-cp
```

步骤2：运行以下命令启动 docker 容器，启动代理容器以及两个上游 HTTP echo 服务器 service1 和 service2。
```bash
➜  dynamic-config-cp git:(main) docker-compose up -d proxy

➜  dynamic-config-cp git:(main) docker ps
CONTAINER ID   IMAGE                           COMMAND                   CREATED          STATUS          PORTS                                                NAMES
bd329d6b9f2e   dynamic-config-cp-proxy         "/docker-entrypoint.…"   15 seconds ago   Up 13 seconds   0.0.0.0:10000->10000/tcp, 0.0.0.0:19000->19000/tcp   dynamic-config-cp-proxy-1
8c596816f819   dynamic-config-cp-service2      "/bin/echo-server"        15 seconds ago   Up 13 seconds   8080/tcp                                             dynamic-config-cp-service2-1
8bbf2404e57b   dynamic-config-cp-service1      "/bin/echo-server"        15 seconds ago   Up 13 seconds   8080/tcp                                             dynamic-config-cp-service1-1
```

步骤3：由于控制平面尚未启动，10000 端口上此时应该没有任何响应值，运行以下命令进行检查。
```bash
➜  dynamic-config-cp git:(main) curl -s http://localhost:19000/config_dump | jq '.configs[1].static_clusters'
[
  {
    "cluster": {
      "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
      "name": "xds_cluster",
      "type": "STRICT_DNS",
      "load_assignment": {
        "cluster_name": "xds_cluster",
        "endpoints": [
          {
            "lb_endpoints": [
              {
                "endpoint": {
                  "address": {
                    "socket_address": {
                      "address": "go-control-plane",
                      "port_value": 18000
                    }
                  }
                }
              }
            ]
          }
        ]
      },
      "typed_extension_protocol_options": {
        "envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
          "@type": "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions",
          "explicit_http_config": {
            "http2_protocol_options": {}
          }
        }
      }
    }
  }
]
```

步骤4：执行以下命令检查是否配置 dynamic_active_cluster：
```bash
➜  dynamic-config-cp git:(main) curl -s http://localhost:19000/config_dump  | jq '.configs[1].dynamic_active_clusters'
null
```

步骤5：通过运行以下命令来启动控制平面。
```bash
➜  dynamic-config-cp git:(main) docker compose up --build -d go-control-plane

➜  dynamic-config-cp git:(main) docker ps
CONTAINER ID   IMAGE                                COMMAND                   CREATED          STATUS                    PORTS                                                NAMES
a552cba2a194   dynamic-config-cp-go-control-plane   "/usr/local/bin/exam…"   32 seconds ago   Up 30 seconds (healthy)                                                        dynamic-config-cp-go-control-plane-1
```

步骤6：一旦控制平面启动并处于健康状态，执行以下操作验证 service1 是否就绪：
```bash
➜  dynamic-config-cp git:(main) curl http://localhost:10000
Request served by service1
GET / HTTP/1.1
Host: localhost:10000
Accept: */*
User-Agent: curl/7.79.1
X-Envoy-Expected-Rq-Timeout-Ms: 15000
X-Forwarded-Proto: http
X-Request-Id: dc1704d2-c39b-41c2-888f-4fa5f36a862b
```

步骤7：要验证动态配置是否有效，请运行以下命令进行验证，输出显示 example_proxy_cluster 指向 service1，并且版本为 1，如下所示：
```bash
➜  dynamic-config-cp git:(main) curl -s http://localhost:19000/config_dump | jq '.configs[1].dynamic_active_clusters'

[
  {
    "version_info": "1",
    "cluster": {
      "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
      "name": "example_proxy_cluster",
      "type": "LOGICAL_DNS",
      "connect_timeout": "5s",
      "dns_lookup_family": "V4_ONLY",
      "load_assignment": {
        "cluster_name": "example_proxy_cluster",
        "endpoints": [
          {
            "lb_endpoints": [
              {
                "endpoint": {
                  "address": {
                    "socket_address": {
                      "address": "service1",
                      "port_value": 8080
                    }
                  }
                }
              }
            ]
          }
        ]
      }
    }
  }
]
```

# 总结

在本文中，我们讨论与学习了 Envoy Proxy 实现原理和Jaeger Tracing、UDP 协议、动态 XDS 示例等功能。

# 参考

1. https://www.envoyproxy.io/docs/envoy/latest/
2. https://github.com/envoyproxy/envoy
3. https://istio.io/latest/docs/
4. https://www.jaegertracing.io/docs/
