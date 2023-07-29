---
layout:     post
title:      "使用 Golang 扩展 Envoy 代理 - WASM 过滤器"
subtitle:   ""
description: "Envoy 是一个开源的服务代理，Envoy 专为云原生应用而设计。 Envoy具有很多的特性，如连接池、重试机制、TLS 管理、压缩、健康检查、故障注入、速率限制、授权等。而这些功能都是通过内置的 http 过滤器 实现的。现在，我们我们介绍一个特殊的过滤器 - WASM 过滤器。"
author: "陈谭军"
date: 2021-11-28
published: true
tags:
    - wasm
    - istio
    - wasm
categories:
    - TECHNOLOGY
showtoc: true
---

# 介绍

Envoy 是一个开源的服务代理，Envoy 专为云原生应用而设计。 Envoy具有很多的特性，如连接池、重试机制、TLS 管理、压缩、健康检查、故障注入、速率限制、授权等。而这些功能都是通过内置的 http 过滤器 实现的。现在，我们我们介绍一个特殊的过滤器 - WASM 过滤器。

![](/images/2021-11-28-golang-envoy-wam/1.png)

# 为什么使用 WASM 过滤器

这篇文章不会解释什么是 WASM，所以对 WASM 不做过多的介绍，而是在文章末尾添加相关资源链接。

在 Trendyol 科技公司。我们使用 Istio 作为服务网格。我们团队 (DevX) 的职责是通过开发满足微服务常见要求的应用程序来改善开发人员体验，例如缓存、授权、速率限制、跨集群服务发现等。既然我们已经在使用 Istio，为什么不利用 Envoy Proxy 的可扩展性的优势呢？

我们的案例 demo 是获取用于标识该微服务应用程序的微服务的 JWT 令牌。当我们想避免每个团队用不同的语言编写相同的代码时，我们可以创建一个 WASM Filter 并将其注入 Envoy Proxies 来实现上述功能。

WASM 过滤器的优点：
1. 它允许用任何支持 WASM 的语言编写代码。
1. 动态加载代码到 Envoy。
1. WASM 代码与 Envoy 隔离，因此 WASM 中的崩溃不会影响 Envoy。

# 说明

在 Envoy Proxy 中有专门处理传入请求的工作线程。每个工作线程都有自己的 WASM VM(WASM 虚拟机)。因此，如果想编写基于时间的操作代码，它会为每个线程单独工作。 

在 Envoy Proxy 中，每个工作线程彼此隔离，并且拥有一个或多个 WASM VM。还有一个叫做 WASM Service 的概念，用于线程间通信和数据共享（我们不涉及这个）。

![](/images/2021-11-28-golang-envoy-wam/2.png)

# 用 Go 编写 WASM  

我们将使用 tetratelabs/proxy-wasm-go-sdk 在 Go 中编写 WASM。我们还需要 TinyGo 将我们的 Go 代码构建为 WASM。

我们的案例 demo 非常简单，我们编写了一个代码，每 15 秒向 JWT API 发送一次请求。它提取授权 header 并将其值设置为全局变量，并将该值放入每个请求的响应 header 中。我们还将 "hello from wasm" 值设置为另一个名为 "x-wasm-filter" 的 header 中。在 OnTick 函数中，我们对 Envoy 中称为集群的服务进行 http 调用。  
```go
package main
 
import (
  "github.com/tetratelabs/proxy-wasm-go-sdk/proxywasm"
  "github.com/tetratelabs/proxy-wasm-go-sdk/proxywasm/types"
)
const tickMilliseconds uint32 = 15000
 
var authHeader string
 
func main() {
  proxywasm.SetVMContext(&vmContext{})
}
 
type vmContext struct {
  // Embed the default VM context here,
  // so that we don't need to reimplement all the methods.
  types.DefaultVMContext
}
 
// Override types.DefaultVMContext.
func (*vmContext) NewPluginContext(contextID uint32) types.PluginContext {
  return &pluginContext{contextID: contextID}
}
 
type pluginContext struct {
  // Embed the default plugin context here,
  // so that we don't need to reimplement all the methods.
  types.DefaultPluginContext
  contextID uint32
  callBack  func(numHeaders, bodySize, numTrailers int)
}
 
// Override types.DefaultPluginContext.
func (*pluginContext) NewHttpContext(contextID uint32) types.HttpContext {
  return &httpAuthRandom{contextID: contextID}
}
 
type httpAuthRandom struct {
  // Embed the default http context here,
  // so that we don't need to reimplement all the methods.
  types.DefaultHttpContext
  contextID uint32
}
 
// Override types.DefaultPluginContext.
func (ctx *pluginContext) OnPluginStart(pluginConfigurationSize int) types.OnPluginStartStatus {
  if err := proxywasm.SetTickPeriodMilliSeconds(tickMilliseconds); err != nil {
    proxywasm.LogCriticalf("failed to set tick period: %v", err)
    return types.OnPluginStartStatusFailed
  }
  proxywasm.LogInfof("set tick period milliseconds: %d", tickMilliseconds)
  ctx.callBack = func(numHeaders, bodySize, numTrailers int) {
    respHeaders, _ := proxywasm.GetHttpCallResponseHeaders()
    proxywasm.LogInfof("respHeaders: %v", respHeaders)
 
    for _, headerPairs := range respHeaders {
      if headerPairs[0] == "authorization" {
        authHeader = headerPairs[1]
      }
    }
  }
  return types.OnPluginStartStatusOK
}
 
func (ctx *httpAuthRandom) OnHttpResponseHeaders(int, bool) types.Action {
  proxywasm.AddHttpResponseHeader("x-wasm-filter", "hello from wasm")
  proxywasm.AddHttpResponseHeader("x-auth", authHeader)
 
  return types.ActionContinue
}
 
// Override types.DefaultPluginContext.
func (ctx *pluginContext) OnTick() {
  hs := [][2]string{
    {":method", "GET"}, {":authority", "some_authority"}, {":path", "/auth"}, {"accept", "*/*"},
  }
  if _, err := proxywasm.DispatchHttpCall("my_custom_svc", hs, nil, nil, 5000, ctx.callBack); err != nil {
    proxywasm.LogCriticalf("dispatch httpcall failed: %v", err)
  }
}
```

让我们将 Go 代码编译成 WASM：
```
tinygo build -o optimized.wasm -scheduler=none -target=wasi ./main.go
```
现在我们需要配置 Envoy 代理以对传入请求使用 WASM 过滤器。
我们将为我们的 WASM 代码定义一个路由规则和一个 WASM 过滤器，我们还将定义一个代表我们服务的集群。
```
# cat /etc/envoy/envoy.yaml
admin:
  access_log_path: /tmp/admin_access.log
  address:
    socket_address:
      protocol: TCP
      address: 0.0.0.0
      port_value: 9901
static_resources:
  listeners:
  - name: listener_0
    address:
      socket_address:
        protocol: TCP
        address: 0.0.0.0
        port_value: 10000
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          route_config:
            name: local_route
            virtual_hosts:
            - name: local_service
              domains: ["*"]
              routes:
              - match:
                  prefix: "/"
                route:
                  cluster: my_custom_svc
          http_filters:
          - name: envoy.filters.http.wasm
            typed_config:
              "@type": type.googleapis.com/udpa.type.v1.TypedStruct
              type_url: type.googleapis.com/envoy.extensions.filters.http.wasm.v3.Wasm
              value:
                config:
                  name: "my_plugin"
                  root_id: "my_root_id"
                  configuration:
                    "@type": "type.googleapis.com/google.protobuf.StringValue"
                    value: |
                      {}
                  vm_config:
                    runtime: "envoy.wasm.runtime.v8"
                    vm_id: "my_vm_id"
                    code:
                      local:
                        filename: "/etc/envoy/optimized.wasm"
                    configuration: { }
          - name: envoy.filters.http.router
            typed_config: { }
  clusters:
  - name: my_custom_svc
    connect_timeout: 30s
    type: static
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: service1
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 192.168.1.4
                port_value: 8080
```

我把所有的文件放在同一个目录下。现在让我们使用 Docker 运行 Envoy 代理：
```
docker run -it  --rm -v "$PWD"/envoy.yaml:/etc/envoy/envoy.yaml -v "$PWD"/optimized.wasm:/etc/envoy/optimized.wasm -p 9901:9901 -p 10000:10000 envoyproxy/envoy:v1.17.0
```
正如我们从日志中看到的，我们的 WASM 过滤器开始工作，并每 15 秒向 JWT API 发送请求。

![](/images/2021-11-28-golang-envoy-wam/3.png)

现在让我们向 Envoy Proxy 发送请求。我们将 Envoy 配置为侦听来自 10000 端口的传入请求，并使用端口映射启动容器。
所以我们可以向 localhost:10000 发送请求：

![](/images/2021-11-28-golang-envoy-wam/4.png)

在响应头中，我们可以看到 "x-wasm-filter: hello from wasm" 和 "x-auth" 值。

感谢阅读。我希望这篇文章能让大家了解如何以及为什么在 Envoy Proxy 中使用 WASM。

# 参考 

1. https://github.com/mstrYoda/envoy-proxy-wasm-filter-golang
1. https://github.com/tetratelabs/proxy-wasm-go-sdk
1. https://medium.com/trendyol-tech/extending-envoy-proxy-wasm-filter-with-golang-9080017f28ea
