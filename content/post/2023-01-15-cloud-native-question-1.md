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

# 常见脚本与 yaml 文件

# 容器常见命令

```bash
# 等待 sidecar 就绪
while [[ \"$(curl -s -o /dev/null -w ''%{http_code}'' localhost:15020/healthz/ready)\" != '200' ]]; do echo waiting for sidecar; sleep 1; done; echo sidecar available; start-awesome-app-cmd"

# 
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


