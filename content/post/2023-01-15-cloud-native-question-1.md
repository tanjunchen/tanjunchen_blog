---
layout:     post
title:      "在云原生实践与探索道路上遇到的常见问题与解决方法 - 常见脚本（一）"
subtitle:   "在云原生旅途中可能会碰到的棘手问题以及常见排查手段与解决方法"
description: ""
author: "chatGPT"
date: 2023-01-15
#image: "/img"
published: true
tags:
    - cloud native
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

云原生时代是指企业和开发者开始广泛采用云原生技术的时期。云原生技术是一种软件开发方法，它鼓励将应用作为小型、独立的服务来构建和部署，这些服务可以在公有云、私有云或混合云环境中运行。云原生时代的到来，使得企业和开发者可以更快、更灵活地开发和部署应用，更好地利用云计算资源，更有效地响应业务需求。如果我们在云原生时代遇见问题，我们如何才能快速定位问题以及处理呢？下面是一些常见排查手段、工具、脚本等。

# 常见问题列表

1. istio 常见 yaml 文件
1. 常见脚本与 yaml 文件
1. 容器常见命令
1. 批量删除 consul 不健康的 service
1. 批量同步与迁移镜像到其他镜像仓库
1. Kubernetes 集群登录到某个节点调试工具
1. 常见网络调试工具
1. nsenter 脚本
1. kubectl cp 拷贝文件
1. kind 搭建 Kubernetes 集群

# istio 常见 yaml 文件



# k8s 常见 yaml 文件



# 容器常见命令

```bash
# 等待 sidecar 就绪
while [[ \"$(curl -s -o /dev/null -w ''%{http_code}'' localhost:15020/healthz/ready)\" != '200' ]]; do echo waiting for sidecar;sleep 1; done; echo sidecar available; start-awesome-app-cmd

# k8s 批量删除状态为 Terminating 的 pod
kubectl  get pods | grep Terminating | awk '{print $1}' | xargs kubectl  delete pod --force --grace-period=0

# 拉取 gcr.io 镜像，如 Kubernetes，istio 等
# dockerhub根镜像代理
官方命令：docker pull nginx:latest
代理命令：docker pull dockerproxy.com/library/nginx:latest
# github常规镜像代理
官方命令：docker pull ghcr.io/username/image:tag
代理命令：docker pull ghcr.dockerproxy.com/username/image:tag
# gcr常规镜像代理
官方命令：docker pull gcr.io/username/image:tag 
代理命令：docker pull gcr.dockerproxy.com/username/image:tag 
# k8s gcr常规镜像代理
官方命令：docker pull k8s.gcr.io/coredns:1.6.5
代理命令：docker pull k8s.dockerproxy.com/coredns:1.6.5

# Kubernetes 命名空间不能被正确地删除
# 方法一
kubectl --kubeconfig=path/config  get namespace istio-system -o json | tr -d "\n" | sed "s/\"finalizers\": \[[^]]\+\]/\"finalizers\": []/" |  kubectl  --kubeconfig=path/config  replace --raw /api/v1/namespaces/istio-system/finalize -f -
# 方法二 
# 将命名空间 yaml 文件导出为 json 文件
kubectl get ns test -o json > test.json
# 以 test namespace 为例，编辑该 json文件，将 spec 内的内容全部删除，然后保存退出 
# 另开一个终端，启动 proxy
kubectl proxy --port=8081
# 使用以下命名强制删除 namespace，命令执行完成后就会发现 ns 删除成功 
curl -k -H "Content-Type: application/json" -X PUT --data-binary @test.json http://127.0.0.1:8081/api/v1/namespaces/test/finalize

```

# 批量删除 consul 不健康的 service

使用的脚本如下所示：
```bash
#!/bin/bash
CONSUL_ADDRESS="10.20.1.177:8500"
CONSUL_CRITICAL=`curl -H"X-Consul-Token:p2BE1AtpwPbrxZdC6k+eXA==" ${CONSUL_ADDRESS}/v1/health/state/critical | python -m json.tool | grep ServiceID | awk '{print $2}' |sed 's/"//g' | sed 's/,//g'`
for critical in ${CONSUL_CRITICAL}
do
  echo "${critical} 已删除"
  curl -XPUT -H"X-Consul-Token:p2BE1AtpwPbrxZdC6k+eXA==" http://${CONSUL_ADDRESS}/v1/agent/service/deregister/${critical}
done
```

# 批量同步与迁移镜像到其他镜像仓库

使用的脚本如下所示：
```bash
#!/bin/bash
set -e
dst_user=tanjunchen
dst_repo=docker.io

# image 示例
images=(
    "docker.io/library/nginx:1.14.2"
    "docker.io/library/nginx:1.15.1"
)

pull_tag_push_image(){
    for image in ${images[*]}
    do
        if [ -z "${image}" ]
        then
        continue
        fi
        echo "docker pull ${image}"
    
        docker pull ${image}
        echo "docker pull ${image} success!!!"
        
        array=(`echo ${image} | tr ':' ' '` )
        src_image=${array[0]}
        src_version=${array[1]}
        if [ ! ${src_image} ]; then
            echo "src_image is null, stop tag and push"
            continue
        fi
        if [ ! ${src_version} ]; then
            echo "src_version is null, set default value latest"
            src_version=latest
        fi
        echo "docker src images info ${src_image} ${src_version}"
        
        image_array=(`echo ${src_image} | tr '/' ' '` )
        image_name=${image_array[-1]}
        if [ ! ${image_name} ]; then
            echo "image_name is null, stop tag and push"
            continue
        fi
        dst_image=${dst_repo}/${dst_user}/${image_name}:${src_version}
 
        echo "docker destination images info ${dst_image}"
        
        docker tag ${src_image}:${src_version} ${dst_image}
 
        docker push ${dst_image}
    done
}
 
pull_tag_push_image
```

# Kubernetes 集群登录到某个节点调试工具

使用的 yaml 文件如下所示：
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-shell-debug
spec:
  selector:
    matchLabels:
      app: node-shell-debug
  template:
    metadata:
      labels:
        app: node-shell-debug
        sidecar.istio.io/inject: "false"
    spec:
      tolerations:
      - effect: NoSchedule
        key: node-role.kubernetes.io/master
        operator: Exists
      containers:
      - args:
        - -t
        - "1"
        - -m
        - -u
        - -i
        - -n
        - sleep
        - "140000000"
        command:
        - nsenter
        image: docker.io/tanjunchen/node-shell:dev
        imagePullPolicy: Always
        name: shell
        securityContext:
          privileged: true
      hostIPC: true
      hostNetwork: true
      hostPID: true
```

原始 dockerfile 文件如下所示：
```dockerfile
FROM ubuntu:latest

# 安装必要的软件包
RUN apt-get update && apt-get install -y \
    curl \
    dnsutils \
    iputils-ping \
    net-tools \
    util-linux \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /

# 启动容器时执行的命令
CMD ["/bin/bash"]
```

# 常见网络调试工具

network-multitool 网络调试 yaml 文件如下所示：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: network-multitool
  labels:
    app: network-multitool
spec:
  selector:
    matchLabels:
      app: network-multitool
  template:
    metadata:
      labels:
        app: network-multitool
    spec:
      containers:
      - name: network
        imagePullPolicy: Always
        image: registry.cn-hangzhou.aliyuncs.com/tanjunchen/network-multitool:v1
        env:
        - name: HTTP_PORT
          value: "1180"
        - name: HTTPS_PORT
          value: "11443"
        ports:
        - containerPort: 1180
          name: http-port
        - containerPort: 11443
          name: https-port
        resources:
          requests:
            cpu: "1m"
            memory: "20Mi"
          limits:
            cpu: "10m"
            memory: "20Mi"
        securityContext:
          runAsUser: 0
          capabilities:
            add: ["NET_ADMIN"]
```
更多的详情可参考 [Network-MultiTool](https://github.com/Praqma/Network-MultiTool)。

含 curl 版本的 busybox yaml 文件如下所示：
```yaml
apiVersion: v1 
kind: Pod 
metadata: 
  name: busybox 
  namespace: default 
spec: 
  containers: 
  - name: busybox 
    image: busybox:1.28.4 
    command: 
      - sleep 
      - "3600" 
    imagePullPolicy: IfNotPresent 
  restartPolicy: Always
```

# nsenter 脚本

以下脚本是在宿主机上使用 nsenter 根据容器名称或容器 id 进入容器执行相关网络配置。

docker 环境：
```bash
#/bin/bash

CTN=$1  # container ID or name
PID=$(sudo docker inspect --format "{{.State.Pid}}" $CTN)
shift 1 # remove the first argument, shift others to the left
nsenter -t $PID $@
```

# kubectl cp 拷贝文件

使用 kubectl 在宿主机与容器之间拷贝文件，主要命令如下所示：
```bash
# Copy /tmp/foo local file to /tmp/bar in a remote pod in namespace <some-namespace>
tar cf - /tmp/foo | kubectl exec -i -n <some-namespace> <some-pod> -- tar xf - -C /tmp/bar

# Copy /tmp/foo from a remote pod to /tmp/bar locally
kubectl exec -n <some-namespace> <some-pod> -- tar cf - /tmp/foo | tar xf - -C /tmp/bar

# Copy /tmp/foo_dir local directory to /tmp/bar_dir in a remote pod in the default namespace
kubectl cp /tmp/foo_dir <some-pod>:/tmp/bar_dir

# Copy /tmp/foo local file to /tmp/bar in a remote pod in a specific container
kubectl cp /tmp/foo <some-pod>:/tmp/bar -c <specific-container>

# Copy /tmp/foo local file to /tmp/bar in a remote pod in namespace <some-namespace>
kubectl cp /tmp/foo <some-namespace>/<some-pod>:/tmp/bar

# Copy /tmp/foo from a remote pod to /tmp/bar locally
kubectl cp <some-namespace>/<some-pod>:/tmp/foo /tmp/bar
```

# kind 搭建 Kubernetes 集群

安装 kind：
```bash
[ $(uname -m) = x86_64 ] && curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
```

搭建 Kubernetes 集群（没有 CNI 与 kube-proxy 组件）：
```bash
kind create cluster --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true   # do not install kindnet
  kubeProxyMode: none       # do not run kube-proxy
nodes:
- role: control-plane
- role: worker
- role: worker
- role: worker
EOF
```

搭建 Kubernetes 集群（指定 kind 镜像）：
```bash
kind create cluster  --image=kindest/node:v1.22.17 --name  tanjunchen
```


