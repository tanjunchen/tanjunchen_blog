---
layout:     post
title:      "Wasm C++ Filter 拓展 Envoy"
subtitle:   ""
description: "这篇博客演示了一个用 C++ 编写的入门 Envoy Wasm Filter，它将返回值注入到 HTTP 响应的 body 中，并且更新与添加 header。"
author: "陈谭军"
date: 2021-12-04
published: true
tags:
    - wasm
    - istio
    - envoyfilter
categories:
    - TECHNOLOGY
showtoc: true
---

# Wasm C++ Filter

这篇博客演示了一个用 C++ 编写的入门 Envoy Wasm Filter，它将返回值注入到 HTTP 响应的 body 中，并且更新与添加 header。

通过该文章完成构建我们的 C++ Wasm Filter 所需的步骤，并使用 Envoy 运行它。

# 示例

**启动所有的应用进程，首先让我们启动容器应用**

一个使用 Wasm 过滤器的 Envoy 代理服务，以及一个响应我们请求的后端服务，克隆下载 envoy。
```
git clone https://github.com/envoyproxy/envoy
```

切换到 Envoy 仓库中的 examples/wasm-cc 目录下，运行如下命令：
```bash
pwd
envoy/examples/wasm-cc
docker-compose build --pull
docker-compose up -d
docker-compose ps
 
    Name                     Command                State             Ports
-----------------------------------------------------------------------------------------------
wasm_proxy_1         /docker-entrypoint.sh /usr ... Up      10000/tcp, 0.0.0.0:8000->8000/tcp
wasm_web_service_1   node ./index.js                Up
```

检查 web 响应，向 envoy 代理发出请求时，Wasm 过滤器应该在响应正文的末尾注入“Hello, world”。

![](/images/2021-12-04-wasm-envoyfilter/2.png)

过滤器还将内容类型 header 设置为 text/plain，并添加自定义 x-wasm-custom header。

![](/images/2021-12-04-wasm-envoyfilter/3.png)

**编译一个新的 wasm 可执行二进制文件**

Wasm 过滤器提供了两个源代码文件，envoy_filter_http_wasm_example.cc 提供了包含的预构建二进制文件的源代码。envoy_filter_http_wasm_updated_example.cc 对原始文件进行了一些更改，以下差异显示了所做的更改：

```lua
--- /tmp/tmp1lcx0q03/generated/rst/start/sandboxes/_include/wasm-cc/envoy_filter_http_wasm_example.cc
+++ /tmp/tmp1lcx0q03/generated/rst/start/sandboxes/_include/wasm-cc/envoy_filter_http_wasm_updated_example.cc
@@ -65,8 +65,8 @@
   for (auto& p : pairs) {
     LOG_INFO(std::string(p.first) + std::string(" -> ") + std::string(p.second));
   }
-  addResponseHeader("X-Wasm-custom", "FOO");
-  replaceResponseHeader("content-type", "text/plain; charset=utf-8");
+  addResponseHeader("X-Wasm-custom", "BAR");
+  replaceResponseHeader("content-type", "text/html; charset=utf-8");
   removeResponseHeader("content-length");
   return FilterHeadersStatus::Continue;
 }
@@ -78,9 +78,9 @@
   return FilterDataStatus::Continue;
 }
 
-FilterDataStatus ExampleContext::onResponseBody(size_t body_buffer_length,
+FilterDataStatus ExampleContext::onResponseBody(size_t /* body_buffer_length */,
                                                 bool /* end_of_stream */) {
-  setBuffer(WasmBufferType::HttpResponseBody, 0, body_buffer_length, "Hello, world\n");
+  setBuffer(WasmBufferType::HttpResponseBody, 0, 17, "Hello, Wasm world");
   return FilterDataSta
```

使用 envoyproxy/envoy-build-ubuntu 镜像编译更新的 Wasm 二进制文件，将需要 4-5GB 的磁盘空间来存储该镜像，停止 envoy 代理服务并使用更新后的代码编译 Wasm 二进制可执行文件： 

```bash
docker-compose stop proxy
docker-compose -f docker-compose-wasm.yaml up --remove-orphans wasm_compile_update
```

编译后的二进制文件现在应该在 lib 文件夹中。
```bash
ls -l lib
total 120
-r-xr-xr-x 1 envoy_filter_http_wasm_example.wasm
-r-xr-xr-x 1 envoy_filter_http_wasm_updated_example.wasm
```

编辑 Dockerfile 并重启 Envoy 代理，编辑示例中提供的 Dockerfile-proxy 文件，使用在步骤 3 中创建的更新的二进制文件。将 Wasm 二进制文件添加到 Dockerfile 中。

```bash
FROM envoyproxy/envoy-dev:latest
COPY ./envoy.yaml /etc/envoy.yaml
COPY ./lib/envoy_filter_http_wasm_example.wasm /lib/envoy_filter_http_wasm_example.wasm
RUN chmod go+r /etc/envoy.yaml /lib/envoy_filter_http_wasm_example.wasm
CMD ["/usr/local/bin/envoy", "-c", "/etc/envoy.yaml", "--service-cluster", "proxy"]
```

替换 COPY ./lib/envoy_filter_http_wasm_example.wasm /lib/envoy_filter_http_wasm_example.wasm 行。

```bash
COPY ./lib/envoy_filter_http_wasm_updated_example.wasm /lib/envoy_filter_http_wasm_example.wasm
```

现在重启 Envoy 服务代理

```bash
docker-compose up --build -d proxy
```

检验服务代理是否已被更新，Wasm 过滤器应该在响应主体的末尾注入“Hello, Wasm world”。

```
curl -s http://localhost:8000 | grep "Hello, Wasm world"
Hello, Wasm world
```

content-type 和 x-wasm-custom header 也应该改变了。

```
curl -v http://localhost:8000 | grep "content-type: "
content-type: text/html; charset=utf-8
```

```
curl -v http://localhost:8000 | grep "x-wasm-custom: "
x-wasm-custom: BAR
```

![](/images/2021-12-04-wasm-envoyfilter/1.png)
