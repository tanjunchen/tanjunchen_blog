---
layout:     post
title:      "使用 wasm 拓展 istio-proxy 数据面"
subtitle:   ""
description: "Solo.io 团队发布了 WebAssembly Hub，这是一套为 Envoy 和 Istio 准备的，用于构建、部署、共享和发现 Envoy Proxy WASM 扩展的工具和仓库。"
author: "陈谭军"
date: 2021-05-01
published: true
tags:
    - istio
categories:
    - TECHNOLOGY
showtoc: true
---

[Solo.io](https://www.solo.io/) 团队发布了 WebAssembly Hub，这是一套为 Envoy 和 Istio 准备的，用于构建、部署、共享和发现 Envoy Proxy WASM 扩展的工具和仓库。

**使用 wasme 拓展 istio-proxy 数据平面**

安装 wasme 构建工具
```bash
curl -sL https://run.solo.io/wasme/install | sh
export PATH=$HOME/.wasme/bin:$PATH
```

查看版本号
```bash
wasme --version
[root@dev-10 ~]# wasme --version
wasme version 0.0.33
```

如果出现网络原因，安装脚本不太好用。则可以到 solo.io/wasm 官网下载镜像包，以及配置环境即可。

创建一个 cpp filter 项目
```bash
wasme init ./new-filter
  cpp
  rust
▸ assemblyscript
  tinygo

✔ assemblyscript
✔ gloo:1.3.x, gloo:1.5.x, gloo:1.6.x, istio:1.5.x, istio:1.6.x, istio:1.7.x, istio:1.8.x, istio:1.9.x
```

filter 增加 header (最新 0.0.33 版本增加了默认 header 值)
```bash
onResponseHeaders(a: u32): FilterHeadersStatusValues {
const root_context = this.root_context;
if (root_context.configuration == "") {
    stream_context.headers.response.add("hello", "world!");
} else {
    stream_context.headers.response.add("hello", root_context.configuration);
}
return FilterHeadersStatusValues.Continue;
}
```

编译 filter
```bash
wasme build cpp -t webassemblyhub.io/tanjunchen20/add-header:v0.1 .
```

查看本地的 filter 镜像
```bash
[root@mesh-10-20-11-190 wasme]# wasme list
NAME                                      TAG  SIZE    SHA      UPDATED
webassemblyhub.io/tanjunchen20/add-header v0.1 12.6 kB 0295d929 02 Apr 21 13:06 CST
```

推送到 `WebAssembly hub`，`wasme login -u $YOUR_USERNAME -p $YOUR_PASSWORD`，推送镜像 `wasme push webassemblyhub.io/tanjunchen20/add-header:v0.1`。

查找我的远程镜像
```bash
wasme list --search $YOUR_USERNAME
```

安装 istio
```bash
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.8.1 sh -
cd istio-1.8.1
istioctl install --set profile=demo
```

部署应用

```bash
kubectl create ns bookinfo
kubectl label namespace bookinfo istio-injection=enabled --overwrite
kubectl apply -n bookinfo -f samples/bookinfo/platform/kube/bookinfo.yaml 
```

部署 WASM filter 到 istio 中的应用
```bash
wasme deploy istio webassemblyhub.io/tanjunchen20/add-header:v0.1
--id=myfilter
--namespace bookinfo
--config 'tanjunchen20'
INFO[0000] cache namespace created                       cache=wasme-cache.wasme image="quay.io/solo-io/wasme:0.0.33"
INFO[0000] cache configmap created                       cache=wasme-cache.wasme image="quay.io/solo-io/wasme:0.0.33"
INFO[0000] cache service account created                 cache=wasme-cache.wasme image="quay.io/solo-io/wasme:0.0.33"
INFO[0000] cache role created                            cache=wasme-cache.wasme image="quay.io/solo-io/wasme:0.0.33"
INFO[0000] cache rolebinding created                     cache=wasme-cache.wasme image="quay.io/solo-io/wasme:0.0.33"
INFO[0000] cache daemonset created                       cache=wasme-cache.wasme image="quay.io/solo-io/wasme:0.0.33"
INFO[0006] added image to cache config...                cache="{wasme-cache wasme}" image="webassemblyhub.io/tanjunchen20/add-header:v0.1"
INFO[0006] waiting for event with timeout 1m0s          
WARN[0007] event err: expected 1 image-ready events for image webassemblyhub.io/tanjunchen20/add-header:v0.1, only found map[] 
WARN[0008] event err: expected 1 image-ready events for image webassemblyhub.io/tanjunchen20/add-header:v0.1, only found map[] 
WARN[0009] event err: expected 1 image-ready events for image webassemblyhub.io/tanjunchen20/add-header:v0.1, only found map[] 
WARN[0010] event err: expected 1 image-ready events for image webassemblyhub.io/tanjunchen20/add-header:v0.1, only found map[] 
WARN[0011] event err: expected 1 image-ready events for image webassemblyhub.io/tanjunchen20/add-header:v0.1, only found map[] 
INFO[0012] cleaning up cache events for image webassemblyhub.io/tanjunchen20/add-header:v0.1 
INFO[0012] updated workload sidecar annotations          filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=details-v1
INFO[0012] created Istio EnvoyFilter resource            envoy_filter_resource=details-v1-myfilter.bookinfo filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=details-v1
INFO[0012] updated workload sidecar annotations          filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=productpage-v1
INFO[0012] created Istio EnvoyFilter resource            envoy_filter_resource=productpage-v1-myfilter.bookinfo filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=productpage-v1
INFO[0012] updated workload sidecar annotations          filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=ratings-v1
INFO[0013] created Istio EnvoyFilter resource            envoy_filter_resource=ratings-v1-myfilter.bookinfo filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=ratings-v1
INFO[0013] updated workload sidecar annotations          filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=reviews-v1
INFO[0013] created Istio EnvoyFilter resource            envoy_filter_resource=reviews-v1-myfilter.bookinfo filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=reviews-v1
INFO[0013] updated workload sidecar annotations          filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=reviews-v2
INFO[0013] created Istio EnvoyFilter resource            envoy_filter_resource=reviews-v2-myfilter.bookinfo filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=reviews-v2
INFO[0013] updated workload sidecar annotations          filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=reviews-v3
INFO[0014] created Istio EnvoyFilter resource            envoy_filter_resource=reviews-v3-myfilter.bookinfo filter="id:\"myfilter\" image:\"webassemblyhub.io/tanjunchen20/add-header:v0.1\" config:<type_url:\"type.googleapis.com/google.protobuf.StringValue\" value:\"\\n\\014tanjunchen20\" > rootID:\"add_header\" patchContext:\"inbound\" " workload=reviews-v3
```

我在测试镜像 `webassemblyhub.io/tanjunchen20/add-header:v0.1` 添加了 `header tanjunchen: tanjunchen20`，所以，响应的 header 中会有 `tanjunchen: tanjunchen20`。

```bash
[root@mesh-10-20-11-190 istio-1.8.1]# kubectl exec -ti -n bookinfo deploy/productpage-v1 -c istio-proxy -- curl -v http://details.bookinfo:9080/details/123
*   Trying 10.108.222.151...
* TCP_NODELAY set
* Connected to details.bookinfo (10.108.222.151) port 9080 (#0)
> GET /details/123 HTTP/1.1
> Host: details.bookinfo:9080
> User-Agent: curl/7.58.0
> Accept: */*
> 
< HTTP/1.1 200 OK
< content-type: application/json
< server: istio-envoy
< date: Sat, 03 Apr 2021 09:30:56 GMT
< content-length: 180
< x-envoy-upstream-service-time: 2
< tanjunchen: tanjunchen20
< x-envoy-decorator-operation: details.bookinfo.svc.cluster.local:9080/*
< 
{"id":123,"author":"William Shakespeare","year":1595,"type":"paperback","pages":200,"publisher":"PublisherA","language":"English","ISBN-10":"1234567890","ISBN-13":"123-1234567890"}
```

移除 wasm filter 链
```bash
wasme undeploy istio --id myfilter --namespace bookinfo
INFO[0000] removing filter from one or more workloads...  filter=myfilter params="{map[] bookinfo deployment}"
INFO[0000] removing sidecar annotations from workload    filter=myfilter workload=details-v1
INFO[0000] removing sidecar annotations from workload    filter=myfilter workload=productpage-v1
INFO[0000] removing sidecar annotations from workload    filter=myfilter workload=ratings-v1
INFO[0000] removing sidecar annotations from workload    filter=myfilter workload=reviews-v1
INFO[0000] removing sidecar annotations from workload    filter=myfilter workload=reviews-v2
INFO[0000] removing sidecar annotations from workload    filter=myfilter workload=reviews-v3
INFO[0000] deleted Istio EnvoyFilter resource            filter=details-v1-myfilter
INFO[0001] deleted Istio EnvoyFilter resource            filter=productpage-v1-myfilter
INFO[0001] deleted Istio EnvoyFilter resource            filter=ratings-v1-myfilter
INFO[0002] deleted Istio EnvoyFilter resource            filter=reviews-v1-myfilter
INFO[0002] deleted Istio EnvoyFilter resource            filter=reviews-v2-myfilter
INFO[0002] deleted Istio EnvoyFilter resource            filter=reviews-v3-myfilter
如果使用了 revision 字段安装的 istio, 部署 webassembly 时需要增加 istiod-name 参数即可。
wasme deploy istio webassemblyhub.io/tanjunchen20/add-header:v0.1 --id=myfilter --namespace bookinfo --config 'tanjunchen20' --istiod-name istiod的 deployment 名称
```

**使用 Wasme Operator 拓展 istio-proxy 数据面**

```bash
kubectl apply -f https://github.com/solo-io/wasm/releases/latest/download/wasme.io_v1_crds.yaml
# Code generated by skv2. DO NOT EDIT.
apiVersion: apiextensions.k8s.io/v1beta1
kind: CustomResourceDefinition
metadata:
  labels:
    app: wasme
    app.kubernetes.io/name: wasme
  name: filterdeployments.wasme.io
spec:
  group: wasme.io
  names:
    kind: FilterDeployment
    listKind: FilterDeploymentList
    plural: filterdeployments
    singular: filterdeployment
  scope: Namespaced
  subresources:
    status: {}
  versions:
  - name: v1
    served: true
    storage: true
```

```bash
kubectl apply -f https://github.com/solo-io/wasm/releases/latest/download/wasme-default.yaml
```

部署 bookinfo 案例
```bash
kubectl create ns bookinfo
kubectl label namespace bookinfo istio-injection=enabled --overwrite
kubectl apply -n bookinfo -f https://raw.githubusercontent.com/solo-io/wasm/master/tools/wasme/cli/test/e2e/operator/bookinfo.yaml
```

创建 filterdeployment 实例
```bash
cat <<EOF | kubectl apply -f -
apiVersion: wasme.io/v1
kind: FilterDeployment
metadata:
  name: bookinfo-custom-filter
  namespace: bookinfo
spec:
  deployment:
    istio:
      kind: Deployment
  filter:
    config:
      '@type': type.googleapis.com/google.protobuf.StringValue
      value: world
    image: webassemblyhub.io/sodman/istio-1-7:v0.3
EOF
kubectl get filterdeployments.wasme.io -n bookinfo -o yaml bookinfo-custom-filter
```

更新 filterdeployment 实例中 header 中的值
```bash
cat <<EOF | kubectl apply -f -
apiVersion: wasme.io/v1
kind: FilterDeployment
metadata:
  name: bookinfo-custom-filter
  namespace: bookinfo
spec:
  deployment:
    istio:
      kind: Deployment
  filter:
    config:
      '@type': type.googleapis.com/google.protobuf.StringValue
      value: goodbye
    image: webassemblyhub.io/sodman/istio-1-7:v0.3
EOF
```

可以查看相应的 envoyfilter 值已经更改
```bash
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  creationTimestamp: "2021-04-03T14:12:16Z"
  generation: 2
  name: details-v1-bookinfo-custom-filter.bookinfo
  namespace: bookinfo
  ownerReferences:
  - apiVersion: wasme.io/v1
    blockOwnerDeletion: true
    controller: true
    kind: FilterDeployment
    name: bookinfo-custom-filter
    uid: 64f08103-3492-4e1b-a463-668e398204f6
  resourceVersion: "7768328"
  selfLink: /apis/networking.istio.io/v1alpha3/namespaces/bookinfo/envoyfilters/details-v1-bookinfo-custom-filter.bookinfo
  uid: c749b91c-02d6-491c-8314-b7f6faf02f8b
spec:
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: envoy.http_connection_manager
            subFilter:
              name: envoy.router
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.wasm
        typedConfig:
          '@type': type.googleapis.com/udpa.type.v1.TypedStruct
          typeUrl: type.googleapis.com/envoy.extensions.filters.http.wasm.v3.Wasm
          value:
            config:
              configuration:
                '@type': type.googleapis.com/google.protobuf.StringValue
                value: goodbye
              name: bookinfo-custom-filter.bookinfo
              rootId: add_header_root_id
              vmConfig:
                code:
                  local:
                    filename: /var/local/lib/wasme-cache/d2bc5bea58499684981fda875101ac18a69923cea4a4153958dad08065aa1e74
                runtime: envoy.wasm.runtime.v8
                vmId: bookinfo-custom-filter.bookinfo
  workloadSelector:
    labels:
      app: details
      version: v1
```

测试验证 header 是否有新增值，如下所示，我们在 response 中找到了 `hello: goodbye`。
```bash
kubectl exec -ti -n bookinfo deploy/productpage-v1 -c istio-proxy -- curl -v http://details.bookinfo:9080/details/123
*   Trying 10.102.94.69...
* TCP_NODELAY set
* Connected to details.bookinfo (10.102.94.69) port 9080 (#0)
> GET /details/123 HTTP/1.1
> Host: details.bookinfo:9080
> User-Agent: curl/7.58.0
> Accept: */*
> 
< HTTP/1.1 200 OK
< content-type: application/json
< server: istio-envoy
< date: Sat, 03 Apr 2021 14:49:32 GMT
< content-length: 180
< x-envoy-upstream-service-time: 1
< hello: goodbye
< location: envoy-wasm
< x-envoy-decorator-operation: details.bookinfo.svc.cluster.local:9080/*
Connection #0 to host details.bookinfo left intact
{"id":123,"author":"William Shakespeare","year":1595,"type":"paperback","pages":200,"publisher":"PublisherA","language":"English","ISBN-10":"1234567890","ISBN-13":"123-1234567890"}
```

**FAQ**

如果在部署测试的过程中遇到了 pod 中的 istio-proxy 出现以下这种日志：
```bash
Internal:Error adding/updating listener(s) virtualInbound: Invalid path: /var/local/lib/wasme-cache/0295d929353976266ab721389ec859b2fe012d63ce2e58815469ab85c123b510
```
原因：可能是由于 /var/local/lib/wasme-cache/ 不存在这个文件。
```bash
/var/local/lib/wasme-cache/
├── 0295d929353976266ab721389ec859b2fe012d63ce2e58815469ab85c123b510
└── a515a5d244b021c753f2e36c744e03a109cff6f5988e34714dbe725c904fa917
```
需要在 wasme 命名空间下删除 wasme pod ，这个应该是由于 `webassemblyhub.io/tanjunchen20/add-header:v0.1`` 镜像变更了 SHA，但是在 `/var/local/lib/wasme-cache/` 目录下没有生成相应的二进制文件导致的。

**总结**

通过使用 WebAssembly，可以在 Istio 数据平面中实现动态的、基于自定义逻辑的功能增强，提升灵活性、安全性和性能。
