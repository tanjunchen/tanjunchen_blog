---
layout:     post
title:      "使用 Istio 过程中遇到的常见问题与解决方法（一）"
subtitle:   "在使用 Istio 过程中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "陈谭军"
date: 2022-11-18
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

1. 注入 sidecar 后，应用程序启动失败
1. Istio Proxy 开启 accesslog 日志
1. 使用 Sidecar CRD 降低 Istio Proxy 资源消耗
1. Istio Proxy 响应值删除指定的 header
1. Envoy 默认暴露的 Metrics 指标使网络进出口流量增大
1. Istio Proxy 响应值返回 502
1. Istio 跨集群下服务所关联的 endpoint 不全问题（no healthy upstream）
1. 使用 lua 给 Istio Proxy 添加自定义 header
1. 使用 lua 与 envoyfilter 打印 header
1. istio-ingressgateway 启动失败，出现文件描述符报错

# 注入 sidecar 后，应用程序启动失败

**现象**：应用在启动时可能会从一些外部服务中获取数据，并采用这些数据对自身进行初始化，如从配置中心读取程序配置，从数据库中初始化程序用户信息等。初始化 init 容器已经在 Pod 中创建了 iptables rule 规则，因此应用向外发送的网络流量会被重定向到 Envoy，Envoy 启动后会通过 xDS 协议向 Pilot 请求服务和路由配置信息，当 Pilot 通过 xDS 协议给 Envoy 下发配置较慢时，Envoy 没有对上述应用请求进行处理的监听器和路由规则，无法对此进行处理，导致网络请求失败。

**解决方案**：参考 [ProxyConfig 文档](https://istio.io/latest/docs/reference/config/istio.mesh.v1alpha1/#ProxyConfig)，设置 `holdApplicationUntilProxyStarts` 为 `true`。备注：Istio 要求 1.7+。

实现原理如下所示：

![](/images/2022-11-18-istio-questions-1/1.png)

在开启 `holdApplicationUntilProxyStarts` 选项后，`Istio Sidecar Injector Webhook` 会在 Pod 中插入下面的 yaml 片段。该 yaml 在 sidecar proxy 的 postStart 生命周期时间中执行了 pilot-agent wait 命令。该命令会检测 Proxy 的状态，待 Proxy 初始化完成后再启动 Pod 中的下一个容器。这样，在应用容器启动时，sidecar proxy 已经完成了配置初始化，可以正确代理应用容器的对外网络请求。

```yaml
spec:
  containers:
  - name: istio-proxy
    lifecycle:
      postStart:
        exec:
          command:
          - pilot-agent
          - wait
```

全局设置方式如下所示：
```yaml
apiVersion: install.istio.io/v1alpha2
kind: IstioOperator
spec:
  meshConfig:
    defaultConfig:
      holdApplicationUntilProxyStarts: true
```

Pod 设置方式如下所示：
```yaml
annotations:
  proxy.istio.io/config: '{ "holdApplicationUntilProxyStarts": true }'
```

在 istio-system/istio ConfigMap 中将 `holdApplicationUntilProxyStarts` 这个全局配置项设置为 `true`。
```yaml
apiVersion: v1
data:
  mesh: |-
    defaultConfig:
      holdApplicationUntilProxyStarts: true 
```

# Istio Proxy 开启 accesslog 日志

我们可以通过 Telemetry API、Mesh Config、EnvoyFilter 等三种方式支持开启 istio-proxy 的 accesslog 日志。

**Telemetry**：使用 Telemetry CRD 开启 access log 日志。
```yaml
cat <<EOF > ./telemtry-example.yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: mesh-default
spec:
  selector:
    matchLabels:
      app: helloworld  # 工作负载 label
  accessLogging:
    - providers:
      - name: envoy
EOF
```

```bash
kubectl apply -f ./telemtry-example.yaml
```

**全局配置 Mesh Config**：在 istio-system/istio ConfigMap 中添加如下配置。

```yaml
apiVersion: v1
data:
  mesh: |-
    # 全局修改 Envoy 输出 accesslog
    accessLogEncoding: JSON
    accessLogFile: /dev/stdout
    accessLogFormat: ""
    defaultConfig:
      holdApplicationUntilProxyStarts: true
    rootNamespace: istio-system
kind: ConfigMap
metadata:
  name: istio
```

* accessLogEncoding: 表示 accesslog 输出格式，istio 预定义了 TEXT 和 JSON 两种日志输出格式。默认使用 TEXT，通常我们习惯改成 JSON 以提升可读性，同时也利于日志采集。
* accessLogFile: 表示 accesslog 输出到哪里，通常我们指定到 /dev/stdout (标准输出)，以便使用 kubectl logs 来查看日志，同时也利于日志采集。
* accessLogFormat: 如果不想使用 istio 预定义的 accessLogEncoding，我们也可以使用这个配置来自定义日志输出格式。

**EnvoyFilter**：使用 EnvoyFilter CRD 开启 access log 日志。
```yaml
cat <<EOF > ./envoyfilter-example.yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: enable-accesslog
spec:
  configPatches:
  - applyTo: NETWORK_FILTER
    match:
      context: ANY
      listener:
        filterChain:
          filter:
            #name: envoy.http_connection_manager
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: MERGE
      value:
        typed_config:
          "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager"
          access_log:
          - name: envoy.access_loggers.file
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.access_loggers.file.v3.FileAccessLog
              path: "/dev/stdout"
              log_format:
                json_format:
                  authority: "%REQ(:AUTHORITY)%"
                  bytes_received: "%BYTES_RECEIVED%"
                  bytes_sent: "%BYTES_SENT%"
                  downstream_local_address: "%DOWNSTREAM_LOCAL_ADDRESS%"
                  downstream_remote_address: "%DOWNSTREAM_REMOTE_ADDRESS%"
                  duration: "%DURATION%"
                  method: "%REQ(:METHOD)%"
                  path: "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%"
                  protocol: "%PROTOCOL%"
                  request_id: "%REQ(X-REQUEST-ID)%"
                  requested_server_name: "%REQUESTED_SERVER_NAME%"
                  response_code: "%RESPONSE_CODE%"
                  response_flags: "%RESPONSE_FLAGS%"
                  route_name: "%ROUTE_NAME%"
                  start_time: "%START_TIME%"
                  upstream_cluster: "%UPSTREAM_CLUSTER%"
                  upstream_host: "%UPSTREAM_HOST%"
                  upstream_local_address: "%UPSTREAM_LOCAL_ADDRESS%"
                  upstream_service_time: "%RESP(X-ENVOY-UPSTREAM-SERVICE-TIME)%"
                  upstream_transport_failure_reason: "%UPSTREAM_TRANSPORT_FAILURE_REASON%"
                  user_agent: "%REQ(USER-AGENT)%"
                  x_forwarded_for: "%REQ(X-FORWARDED-FOR)%"
EOF
```

```bash
kubectl apply -f ./telemtry-example.yaml
```

如果只想要为指定的 workload 启用 accesslog，可以在 EnvoyFilter 上加一下 workloadSelector，如下所示：
```yaml
spec:
  workloadSelector:
    labels:
      app: nginx
```

# 使用 Sidecar CRD 降低 Istio Proxy 资源消耗

根据 Istio 官方文档，Envoy 占用的内存大小和其配置相关，和请求处理速率无关。在一个微服务应用中，一个服务访问的其他服务一般不会超过 10 个，而一个 namespace 中可能部署多达上百个微服务，导致 Envoy 中存在大量冗余配置，导致不必要的内存消耗。最合理的做法是只为一个 sidecar 配置该 sidecar 所代理服务需要访问的外部服务相关的配置。 

Sidecar 描述 sidecar 代理的配置，其可协调与其连接的工作负载实例的入站和出站流量。Sidecar CRD 可以让用户更细粒度地控制 Envoy 的行为，包括限制 Envoy 可以访问的服务、控制 Envoy 的路由配置等。通过这种方式，可以减少 Envoy 需要处理的服务和配置的数量，从而降低其资源消耗。

**Sidecar CRD 示例**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Sidecar
metadata:
  name: test-sidecar
  namespace: test
spec:
  egress:
  - hosts:
    - test/*  # 业务所在的命名空间
    - test-1/*  # 业务所在的命名空间
    - istio-system/*   # istiod 所在的命名空间
```

# Istio Proxy 响应值删除指定的 header

**现象**：业务注入 Envoy 后，响应返回的 Header 中会有 envoy 信息，业务需要删除 x-envoy-decorator-operation 等相关的 header，默认 Envoy 会自动生成这些特定的 header，如下所示：
```bash
➜  learn kubectl exec -it reviews-v1-777df99c6d-dmdvr  -- curl -I productpage:9080
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8
content-length: 1683
server: istio-envoy
x-envoy-upstream-service-time: 3
```

**解决方案**：我们可以通过 envoyfilter 移除这些 header。
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: response-headers-filter
spec:
  configPatches:
  - applyTo: NETWORK_FILTER
    match:
      context: ANY
      listener:
        filterChain:
          filter:
            name: "envoy.filters.network.http_connection_manager"
    patch:
      operation: MERGE
      value:
        typed_config:
          "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager"
          server_header_transformation: PASS_THROUGH
  - applyTo: HTTP_ROUTE
    match:
      context: SIDECAR_INBOUND
    patch:
      operation: MERGE
      value:
        decorator:
          propagate: false # removes the decorator header
        response_headers_to_remove:
        - x-envoy-upstream-service-time
        - x-powered-by
        - server
```

配置上述 envoyfilter 后，返回的 header 示例如下所示：
```
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8
content-length: 1683
x-envoy-upstream-service-time: 4
```

# Envoy 默认暴露的 Metrics 指标使网络进出口流量增大

**现象**：注入了 enovy 的 pod，发现网络流出流量增加了 xmb/s，如下所示：

![](/images/2022-11-18-istio-questions-1/2.png)

**原因**：istio 安装时默认会在 istio-system 命名空间下生成 `stats-filter-*、tcp-stats-filter*` envoyfilter，
这些 envoyfilter 会使 envoy 产生 metrics 指标，而 Prometheus 会从 envoy 中轮询拉取指标，从而造成出入口网络流量增大。

**删除 istio-system 系统命名空间下的 envoyfilter**，删除后结果如下所示：

![](/images/2022-11-18-istio-questions-1/3.png)

**telemetry 或者 envoyfilter**：
* 使用 telemetry crd 定义 Metircs、Logging、Trace 配置信息。telemetry 如果不生效，则可能是与 envoyfilter crd 冲突了，这两个 crd 只能选择其一，具体原因可参见[https://github.com/istio/istio/issues/44266](https://github.com/istio/istio/issues/44266)。
* 单独使用 envoyfilter workSelector 针对某个 Pod 生效(merge 覆盖 istio-system 下面的 envoyfilter 即可)。

# Istio Proxy 响应值返回 502

**现象**：内部某个业务接入 Mesh 后，某个接口出现 502，接口访问方式如下所示：
```bash
curl -I 'http://x.x.x.:8080/test/card3/?word=%E8%A5%BF%E5%AE%89%E5%86%A0%E5%BF%83%E7%97%85' -H 'host: xxx.com' 
```

其中 Envoy 的报错日志如下所示：
```
2022-09-31T02:56:51.929765Z     trace   envoy filter    [C5806] upstream connection received 14240 bytes, end_stream=false
2022-09-31T02:56:51.929785Z     trace   envoy connection        [C5806] writing 14240 bytes, end_stream false
2022-09-31T02:56:51.929795Z     trace   envoy connection        [C5807] socket event: 2
2022-09-31T02:56:51.929798Z     trace   envoy connection        [C5807] write ready
2022-09-31T02:56:51.929801Z     trace   envoy connection        [C5806] socket event: 2
2022-09-31T02:56:51.929802Z     trace   envoy connection        [C5806] write ready
2022-09-31T02:56:51.929844Z     trace   envoy connection        [C5806] write returns: 14240
2022-09-31T02:56:51.930000Z     trace   envoy connection        [C5805] socket event: 3
2022-09-31T02:56:51.930015Z     trace   envoy connection        [C5805] write ready
2022-09-31T02:56:51.930020Z     trace   envoy connection        [C5805] read ready. dispatch_buffered_data=false
2022-09-31T02:56:51.930039Z     trace   envoy connection        [C5805] read returns: 14333
2022-09-31T02:56:51.930049Z     trace   envoy connection        [C5805] read error: Resource temporarily unavailable
2022-09-31T02:56:51.930055Z     trace   envoy http      [C5805] parsing 14333 bytes
2022-09-31T02:56:51.930063Z     trace   envoy http      [C5805] message begin
2022-09-31T02:56:51.930076Z     trace   envoy http      [C5805] completed header: key=Content-Type value=text/html;charset=utf-8
2022-09-31T02:56:51.930089Z     trace   envoy http      [C5805] completed header: key=Transfer-Encoding value=chunked
2022-09-31T02:56:51.930107Z     trace   envoy http      [C5805] completed header: key=Connection value=close
2022-09-31T02:56:51.930118Z     trace   envoy http      [C5805] completed header: key=Vary value=Accept-Encoding
2022-09-31T02:56:51.930129Z     trace   envoy http      [C5805] completed header: key=Server value=nginx/1.8.0
2022-09-31T02:56:51.930143Z     trace   envoy http      [C5805] completed header: key=Vary value=Accept-Encoding
2022-09-31T02:56:51.930146Z     trace   envoy http      [C5805] completed header: key=Set-Cookie value=ID=58D4878A25DC3F9C0E2FB62870D096D3:FG=1; max-age=31536000; expires=Sat, 30-Mar-24 02:56:50 GMT; domain=.xxx.com; path=/; version=1; comment=bd
2022-09-31T02:56:51.930156Z     debug   envoy client    [C5805] Error dispatching received data: http/1.1 protocol error: HPE_INVALID_HEADER_TOKEN
2022-09-31T02:56:51.930160Z     debug   envoy connection        [C5805] closing data_to_write=0 type=1
2022-09-31T02:56:51.930162Z     debug   envoy connection        [C5805] closing socket: 1
2022-09-31T02:56:51.930199Z     trace   envoy connection        [C5805] raising connection event 1
2022-09-31T02:56:51.930206Z     debug   envoy client    [C5805] disconnect. resetting 1 pending requests
2022-09-31T02:56:51.930210Z     debug   envoy client    [C5805] request reset
2022-09-31T02:56:51.930213Z     trace   envoy main      item added to deferred deletion list (size=1)
2022-09-31T02:56:51.930222Z     debug   envoy router    [C5804][S6039679106682162641] upstream reset: reset reason: protocol error, transport failure reason:
2022-09-31T02:56:51.930231Z     trace   envoy connection        [C5806] socket event: 3
2022-09-31T02:56:51.930244Z     trace   envoy connection        [C5806] write ready
2022-09-31T02:56:51.930247Z     trace   envoy connection        [C5806] read ready. dispatch_buffered_data=false
```

从上述的报错日志中，我们可以看到有 error 日志，如下所示：
```
2022-09-31T02:56:51.930156Z     debug   envoy client    [C5805] Error dispatching received data: http/1.1 protocol error: HPE_INVALID_HEADER_TOKEN
......
2022-09-31T02:56:51.930222Z     debug   envoy router    [C5804][S6039679106682162641] upstream reset: reset reason: protocol error, transport failure reason:
```

**排查**：我们使用 tcpdump 抓取业务的 header 值，值如下所示：
```
0x03d0:  7061 7468 3d2f 0d0a 5374 7269 6374 2d54  path=/..Strict-T
0x03e0:  7261 6e73 706f 7274 2d53 6563 7572 6974  ransport-Securit
0x03f0:  793a 206d 6178 2d61 6765 3d31 3732 3830  y:.max-age=17280
0x0400:  300d 0a54 696d 6520 3a20 5475 6520 4f63  0..Time.:.Tue.Oc
0x0410:  7420 3138 2031 313a 3234 3a35 3020 4353  t.18.11:24:50.CS
0x0420:  5420 3230 3232 0d0a 5472 6163 6569 643a  T.2022..Traceid:
0x0430:  2031 3638 3033 3535 3131 3530 3537 3335  .168035511505735
0x0440:  3937 3435 3038 3739 3139 3332 3734 3131  9745087919327411
0x0450:  3330 3639 3832 3438 0d0a 5661 7279 3a20  30698248..Vary:.
0x0460:  4163 6365 7074 2d45 6e63 6f64 696e 670d  Accept-Encoding.
0x0470:  0a58 2d47 732d 466c 6167 3a20 3078 300d  .X-Gs-Flag:.0x0.
```
![](/images/2022-11-18-istio-questions-1/4.png)
![](/images/2022-11-18-istio-questions-1/5.png)

其中，上述的 `0x0400:  300d 0a54 696d 6520 3a20 5475 6520 4f63  0..Time.:.Tue.Oc` **得知 `Time :`**有个空格不符合 envoy header 规范，
触发 envoy 校验失败 `Error dispatching received data: http/1.1 protocol error:HPE_INVALID_HEADER_TOKEN`。Envoy 校验 header 位置的代码位置参考[http_parser.c](https://github.com/nodejs/http-parser/blob/5c5b3ac62662736de9e71640a8dc16da45b32503/http_parser.c)。如下所示：

![](/images/2022-11-18-istio-questions-1/6.png)
![](/images/2022-11-18-istio-questions-1/7.png)
![](/images/2022-11-18-istio-questions-1/8.png)

**解决方式**：业务中相关的接口修改代码，将 header 中的 key 设置正确，不使用带有空格的值作为 header 的 key。

# Istio 跨集群下服务所关联的 endpoint 不全问题（no healthy upstream）

**现象**：集群 A（北京地域）与集群 B（苏州地域）在同一个命令空间 test 下，服务 test（跨集群应用） 所对应的后端 endpoint 只存在北京地域，
苏州地域的 Pod 实例在 envoy 的 clusters 接口 `curl localhost:15000/clusters` 中获取不到。

**原因**：业务使用方在北京和苏州两个集群都在同一个命名空间下定义了同一个服务，但是两个 svc 信息 `selector` 不一致。
在 `selector` 中携带了地域信息，控制面随机获取某个 svc，用该 svc 信息去获取 endpoint，导致控制面获取 endpoint 会出现遗漏问题。

**解决方式**：重新定义 svc，保证两个集群的 svc 信息一致即可解决问题。

# 使用 lua 给 Istio Proxy 添加自定义 header

在 Istio 中，可以使用 Envoy 的 Lua filter 来添加自定义的 HTTP header。需要在 Istio 配置中启用 EnvoyFilter，以下是一个示例配置：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: add-header-filter
spec:
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_OUTBOUND
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
            subFilter:
              name: envoy.filters.http.router
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.lua
        typed_config:
          '@type': type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua
          inlineCode: |
            function envoy_on_request(request_handle)
               request_handle:headers():add("test-request", "hello")
            end
            function envoy_on_response(response_handle)
              response_handle:headers():add("test-response", "hello")
            end
```

在 inlineCode 部分，我们定义了一个 Lua 函数，该函数在接收到请求时被调用，并添加了自定义的 header。

# 使用 lua 与 envoyfilter 打印 header

HTTP 请求和响应中的 header 包含了很多重要的信息，例如客户端信息、服务端信息、请求方法、响应状态码等。这些信息对于理解和调试服务的行为非常有用。使用 envoyFilter + lua 打印 HTTP header 是一种在微服务环境中进行调试和监控的有效方法。

以下是一个示例，展示如何使用 lua + envoyfilter 脚本打印 HTTP 请求的 header：
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: print-headers
spec:
  configPatches:
    - applyTo: HTTP_FILTER
      match:
        context: ANY
        listener:
          filterChain:
            filter:
              name: 'envoy.filters.network.http_connection_manager'
              subFilter:
                name: 'envoy.filters.http.router'
      patch:
        operation: INSERT_BEFORE
        value:
          name: envoy.lua
          typed_config:
            '@type': 'type.googleapis.com/envoy.extensions.filters.http.lua.v3.Lua'
            inlineCode: |
              local function print_headers(headers)
                for key, value in pairs(headers) do
                    print(string.format("==> %s: %s", tostring(key), tostring(value)))
                end
                print("")
              end

              function envoy_on_request(request_handle)
                local request_headers = request_handle:headers()
                  print_headers(request_headers)
              end

              function envoy_on_response(response_handle)
                local response_headers = response_handle:headers()
                  print_headers(response_headers)
              end
```

# istio-ingressgateway 启动失败，出现文件描述符报错

**现象**：istio-ingressgateway 启动失败，出现文件描述符报错，如下所示：
```
2022-08-09T09:21:21.296349Z debug envoy config new fc_contexts has 1 filter chains, including 1 newly built 2022-08-09T09:21:21.296382Z debug envoy config Create listen socket for listener 0.0.0.0_8084 on address 0.0.0.0:8084 
2022-08-09T09:21:21.296387Z debug envoy config Set listener 0.0.0.0_8084 socket factory local address to 0.0.0.0:8084 
2022-08-09T09:21:21.296390Z debug envoy config add warming listener: name=0.0.0.0_8084, hash=12189484017075021375, address=0.0.0.0:8084 
2022-08-09T09:21:21.296394Z debug envoy misc Initialize listener 0.0.0.0_8084 local-init-manager. 2022-08-09T09:21:21.296399Z debug envoy init init manager Listener-local-init-manager 0.0.0.0_8084 12189484017075021375 initializing 
2022-08-09T09:21:21.296402Z debug envoy init init manager Listener-local-init-manager 0.0.0.0_8084 12189484017075021375 initializing shared target RdsRouteConfigSubscription init http.8084 
2022-08-09T09:21:21.296409Z debug envoy init init manager RDS local-init-manager http.8084 initializing 2022-08-09T09:21:21.296414Z debug envoy init init manager RDS local-init-manager http.8084 initializing target RdsRouteConfigSubscription local-init-target http.8084 
2022-08-09T09:21:21.296423Z debug envoy config gRPC mux addWatch for type.googleapis.com/envoy.config.route.v3.RouteConfiguration 
2022-08-09T09:21:21.296428Z info envoy upstream lds: add/update listener '0.0.0.0_8084' 
2022-08-09T09:21:21.296435Z debug envoy config Resuming discovery requests for type.googleapis.com/envoy.config.route.v3.RouteConfiguration (previous count 1) 
2022-08-09T09:21:21.296457Z debug envoy config Resuming discovery requests for type.googleapis.com/envoy.api.v2.RouteConfiguration (previous count 1) 
2022-08-09T09:21:21.296466Z debug envoy config gRPC config for type.googleapis.com/envoy.config.listener.v3.Listener accepted with 2 resources with version 
2022-08-09T09:21:21Z/117 2022-08-09T09:21:21.296504Z debug envoy config Resuming discovery requests for type.googleapis.com/envoy.config.listener.v3.Listener (previous count 1) 
```
其中，在 Istio 社区中有类似的 issue，见[https://github.com/envoyproxy/envoy/issues/18038](https://github.com/envoyproxy/envoy/issues/18038)、[https://github.com/envoyproxy/envoy/issues/13852](https://github.com/envoyproxy/envoy/issues/13852)。

**原因**：`K8s Node ulimit` 文件句柄参数配置与 `CRI ulimit` 配置参数过小。

**解决方式**：正确配置 `k8s node` 节点与节点的 `CRI ulimit` 参数。
