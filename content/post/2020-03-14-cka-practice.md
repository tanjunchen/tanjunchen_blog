---
layout:     post
title:      "高效通过 Kubernetes CKAD 考试"
subtitle:   ""
description: "为 Kubernetes 应用程序开发人员认证考试做好准备的练习题，高效通过 CKAD 考试"
author: "陈谭军"
date: 2020-03-14
published: true
tags:
    - ckad
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

# 介绍

Kubernetes 是一个开源系统，用于自动化和容器化部署、扩展和管理应用程序。CNCF/Linux 基金会针对 kubernetes 技能的开发人员提供职能考试，考试内容主要包括应用程序部署、应用程序配置、创建持久卷等。由于考试是理论与实操性相结合的，不仅仅是选择题，仅仅知道概念是不够的，所以我们在考试前需要大量的练习。我们不会在这里讨论任何概念，我们为 CKAD 考试创建一堆练习题，希望我们可以高效通过考试。本文帮助我们理解、练习并为考试做好准备。

# 主要内容

* 核心概念（13％）
* Pod 多个容器（10％）
* Pod 设计（20％）
* 状态持久性（8％）
* 配置（18％）
* 可观察性（18％）
* 服务和网络（13％）
 
# 习题

## 核心概念

了解 Kubernetes API，创建和配置基本 Pod 概念。可以点击中文题目，查看参考答案。

<!-- ![](/images/2020-03-14-cka-practice/1.png) -->
1. {{% details "列出集群中的所有命名空间" %}}
```
kubectl get namespaces
kubectl get ns
```
{{% /details %}}

1. {{% details "列出所有命名空间中的所有 Pod" %}}
```
kubectl get po --all-namespaces
```
{{% /details %}}

1. {{% details "列出特定命名空间中的所有 Pod" %}}
```
kubectl get pod -n kube-system
kubectl get pod -n 命名空间名称
```
{{% /details %}}

1. {{% details "列出特定命名空间中的所有 Service" %}}
```
kubectl get svc --all-namespaces
kubectl get svc -n 命名空间名称
kubectl get svc -n default
```
{{% /details %}}

1. {{% details "用 json 路径表达式列出所有显示名称和命名空间的 Pod" %}}
```
kubectl get pods -o=jsonpath="{.items[*]['metadata.name', 'metadata.namespace']}"
```
{{% /details %}}

1. {{% details "在默认命名空间中创建一个 Nginx Pod，并验证 Pod 是否正在运行" %}}
```
// 创建 Pod
kubectl run nginx --image=nginx --restart=Never
// Pod 列表
kubectl get po
```
{{% /details %}}

1. {{% details "使用 yaml 文件创建相同的 Nginx Pod" %}}
```
// get the yaml file with --dry-run flag
kubectl run nginx --image=nginx --restart=Never --dry-run -o yaml > nginx-pod.yaml
// cat nginx-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
spec:
  containers:
  - image: nginx
    name: nginx
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
// create a pod 
kubectl create -f nginx-pod.yaml
```
{{% /details %}}

1. {{% details "输出刚创建的 Pod 的 yaml 文件" %}}
```
kubectl get po nginx -o yaml
```
{{% /details %}}
 
1. {{% details "输出刚创建的 Pod 的 yaml 文件，并且其中不包含特定于集群的信息" %}}
```
kubectl get po nginx -o yaml --export
```
{{% /details %}}

1. {{% details "获取刚刚创建的 Pod 的完整详细信息" %}}
```
kubectl describe pod nginx
```
{{% /details %}}

1. {{% details "删除刚创建的 Pod" %}}
```
kubectl delete pod nginx
kubectl delete -f nginx-pod.yaml
```
{{% /details %}}

1. {{% details "强制删除刚创建的 Pod" %}}
```
kubectl delete po nginx --grace-period=0 --force
```
{{% /details %}}
 
1. {{% details "创建版本为 1.17.4 的 Nginx Pod，并将其暴露在端口 80 上" %}}
```
kubectl run nginx --image=nginx:1.17.4 --restart=Never --port=80
kubectl run nginx --image=nginx:1.17.4 --restart=Never --port=80 --dry-run -o yaml
```
{{% /details %}}

1. {{% details "将刚创建的容器的镜像更改为 1.15-alpine，并验证该镜像是否已更新" %}}
```
kubectl set image pod/nginx nginx=nginx:1.15-alpine
kubectl edit po nginx
kubectl get po nginx -w
```
{{% /details %}}

1. {{% details "对于刚刚更新的 Pod，将镜像版本改回 1.17.1，并观察变化" %}}
```
kubectl set image pod/nginx nginx=nginx:1.17.1
kubectl edit po nginx
kubectl get po nginx -w
```
{{% /details %}}
 
1. {{% details "在不用 describe 命令的情况下检查镜像版本" %}}
```
kubectl get po nginx -o=jsonpath='{.spec.containers[].image}{"\n"}'
```
{{% /details %}}

1. {{% details "创建 Nginx Pod 并在 Pod 上执行简单的 shell" %}}
```
kubectl run nginx --image=nginx --restart=Never
kubectl exec -it nginx /bin/bash
```
{{% /details %}}

1. {{% details "获取刚刚创建的 Pod 的 IP 地址" %}}
```
kubectl get po nginx -o wide
```
{{% /details %}}
 
1. {{% details "创建一个 busybox Pod，在创建它时运行命令 ls 并检查日志" %}}
```
kubectl run busybox --image=busybox --restart=Never -- ls
kubectl logs busybox
```
{{% /details %}}
 
1. {{% details "如果 Pod 崩溃了，请检查 Pod 的先前日志" %}}
```
kubectl logs busybox -p
```
{{% /details %}}

1. {{% details "创建一个带有命令 sleep 3600 的 busybox Pod" %}}
```
kubectl run busybox --image=busybox --restart=Never -- /bin/sh -c "sleep 3600"
```
{{% /details %}}

1. {{% details "从 busybox Pod 中检查 Nginx Pod 网络连接性" %}}
```
kubectl get pod nginx -o wide 
kubectl exec -it busybox -- wget -o- 上述命令列出的 ip 地址
```
{{% /details %}}

1. {{% details "创建一个 echo 消息 How are you 的 busybox Pod，并手动将其删除" %}}
```
kubectl run busybox --image=busybox --restart=Never -it -- echo "How are you"
kubectl delete po busybox
```
{{% /details %}}
 
1. {{% details "创建一个 Nginx Pod 并列出具有不同日志等级（verbosity）的 Pod" %}}
```
kubectl run nginx --image=nginx --restart=Never --port=80
kubectl get po nginx --v=7
{{% /details %}}

1. {{% details "使用自定义列 PODNAME 和 PODSTATUS 列出 Nginx Pod" %}}
```
kubectl get po nginx -o=custom-columns="POD_NAME:.metadata.name,POD_STATUS:.status.containerStatuses"
{{% /details %}}

1. {{% details "列出所有按名称排序的 Pod" %}}
```
kubectl get po --sort-by=.metadata.name
{{% /details %}}
 
1. {{% details "列出所有按创建时间排序的 Pod" %}}
```
kubectl get po --sort-by=.metadata.creationTimestamp
{{% /details %}}

## Pod 多个容器

了解 Pod 中多个容器设计模式（例如：Ambassador、Adapter、Sidecar）。

1. {{% details "用“ls; sleep 3600;”“echo Hello World; sleep 3600;”及“echo this is the third container; sleep 3600”三个命令创建一个包含三个 busybox 容器的 Pod，并观察其状态" %}}
```
kubectl run busybox --image=busybox --restart=Never --dry-run -o yaml -- bin/sh -c "sleep 3600; ls" > multi-container.yaml
kubectl create -f multi-container.yaml
kubectl get po busybox

apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: busybox
  name: busybox
spec:
  containers:
  - args:
    - bin/sh
    - -c
    - ls; sleep 3600
    image: busybox
    name: busybox1
    resources: {}
  - args:
    - bin/sh
    - -c
    - echo Hello world; sleep 3600
    image: busybox
    name: busybox2
    resources: {}
  - args:
    - bin/sh
    - -c
    - echo this is third container; sleep 3600
    image: busybox
    name: busybox3
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```
{{% /details %}}

1. {{% details "检查刚创建的每个容器的日志" %}}
```
kubectl logs busybox -c busybox1
kubectl logs busybox -c busybox2
kubectl logs busybox -c busybox3
```
{{% /details %}}

1. {{% details "检查第二个容器 busybox2 的先前日志（如果有）" %}}
```
kubectl logs busybox -c busybox2 --previous
```
{{% /details %}}

1. {{% details "在上述容器的第三个容器 busybox3 中运行命令 ls" %}}
```
kubectl exec busybox -c busybox3 -- ls
```
{{% /details %}}
 
1. {{% details "显示以上容器的 metrics，将其放入 file.log 中并进行验证" %}}
```
kubectl top pod busybox --containers > file.log && cat file.log
```
{{% /details %}}
 
1. {{% details "用主容器 busybox 创建一个 Pod，并执行“while true; do echo ‘Hi I am from Main container’ >> /var/log/index.html; sleep 5; done”，并带有暴露在端口 80 上的 Nginx 镜像的 sidecar 容器。用 emptyDir Volume 将该卷安装在 /var/log 路径（用于 busybox）和 /usr/share/nginx/html 路径（用于nginx容器）。验证两个容器都在运行。" %}}
```
kubectl run multi-cont-pod --image=busbox --restart=Never --dry-run -o yaml > multi-container.yaml
kubectl create -f multi-container.yaml
kubectl get po multi-cont-pod

apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: multi-cont-pod
  name: multi-cont-pod
spec:
  volumes:
  - name: var-logs
    emptyDir: {}
  containers:
  - image: busybox
    command: ["/bin/sh"]
    args: ["-c", "while true; do echo 'Hi I am from Main container' >> /var/log/index.html; sleep 5;done"]
    name: main-container
    resources: {}
    volumeMounts:
    - name: var-logs
      mountPath: /var/log
  - image: nginx
    name: sidecar-container
    resources: {}
    ports:
      - containerPort: 80
    volumeMounts:
    - name: var-logs
      mountPath: /usr/share/nginx/html
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```
{{% /details %}}

1. {{% details "进入两个容器并验证 main.txt 是否存在，并用 curl localhost 从 sidecar 容器中查询 main.txt" %}}
```
kubectl exec -it muilti-containers-pod -c main-container -- sh
cat var/log/index.html
kubectl exec -it muilti-containers-pod -c sidercar-container -- sh
cat /usr/share/nginx/html/index.html
kubectl exec -it  multi-cont-pod -c sidecar-container -- sh
# apt-get update && apt-get install -y curl
# curl localhost
```
{{% /details %}}

## Pod 设计

了解如何 Pod 使用标签、选择器和注释、了解 Pod 部署以及如何执行滚动更新、了解 Pod 部署以及如何执行回滚、了解 Pod 作业和 CronJobs 等。

1. {{% details "获取 Pod label 标签" %}}
```
kubectl get po --show-labels
```
{{% /details %}}
 
1. {{% details "创建 5 个 Nginx Pod，其中两个标签为 env=prod，另外三个标签为 env=dev" %}}
```
kubectl run nginx-dev1 --image=nginx --restart=Never --labels=env=dev
kubectl run nginx-dev2 --image=nginx --restart=Never --labels=env=dev
kubectl run nginx-dev3 --image=nginx --restart=Never --labels=env=dev

kubectl run nginx-pro1 --image=nginx --restart=Never --labels=env=pro
kubectl run nginx-pro2 --image=nginx --restart=Never --labels=env=pro
```
{{% /details %}}

1. {{% details "确认所有 Pod 都使用正确的标签创建" %}}
```
kubectl get po --show-labels
```
{{% /details %}}

1. {{% details "确认所有 Pod 都使用正确的标签创建" %}}
```
kubectl get po --show-labels
```
{{% /details %}}

1. {{% details "获得带有标签 env=dev 的 Pod" %}}
```
kubectl get pods -l env=dev
```
{{% /details %}}

1. {{% details "获得带标签 env=dev 的 Pod 并输出标签" %}}
```
kubectl get pods -l env=dev --show-labels
```
{{% /details %}}

1. {{% details "获得带有标签 env=pro 的 Pod" %}}
```
kubectl get pods -l env=pro
```
{{% /details %}}
 
1. {{% details "获取带有标签 env 的 Pod" %}}
```
kubectl get po -L env
```
{{% /details %}}
 
1. {{% details "获得带标签 env=dev、env=pro 的 Pod" %}}
```
kubectl get po -l 'env in (dev,pro)'
```
{{% /details %}}

1. {{% details "获取带有标签 env=dev 和 env=pro 的 Pod 并输出标签" %}}
```
kubectl get po -l 'env in (dev,pro)' --show-labels
```
{{% /details %}}

1. {{% details "将其中一个容器的标签更改为 env=uat 并列出所有要验证的容器" %}}
```
kubectl label pod/nginx-pro1 env=aa --overwrite
kubectl get pods --show-labels
```
{{% /details %}}
 
1. {{% details "删除刚才创建的 Pod 标签，并确认所有标签均已删除" %}}
```
kubectl label pod nginx-dev{1..3} env-
kubectl label pod nginx-pro{1..2} env-
kubectl get pods --show-labels
```
{{% /details %}}

1. {{% details "为所有 Pod 添加标签 app=nginx 并验证" %}}
```
kubectl label pod nginx-dev{1..3} app=nginx
kubectl label pod nginx-pro{1..2} app=nginx
kubectl get pods --show-labels
```
{{% /details %}}

1. {{% details "获取所有带有标签的节点（如果使用 minikube，则只会获得主节点）" %}}
```
kubectl get nodes --show-labels
```
{{% /details %}}
 
1. {{% details "标记节点（如果正在使用，则为 minikube）nodeName=nginxnode" %}}
```
kubectl label node minikube nodeName=nginxnode
```
{{% /details %}}
 
1. {{% details "建一个标签为 nginx=dev 的 Pod 并将其部署在此节点上" %}}
```
kubectl run nginx --image=nginx --restart=Never --dry-run -o yaml > pod.yaml
kubectl create -f pod.yaml

apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
spec:
  nodeSelector:
    nodeName: nginxnode
  containers:
  - image: nginx
    name: nginx
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```
{{% /details %}} 

1. {{% details "使用节点选择器验证已调度的 Pod" %}}
```
kubectl describe po nginx | grep Node-Selectors
```
{{% /details %}}

1. {{% details "验证我们刚刚创建的 Pod Nginx 是否具有 nginx=dev 这个标签" %}}
```
kubectl describe po nginx | grep Labels
```
{{% /details %}}

1. {{% details "用 name=webapp annotate 上述 Pod" %}}
```
kubectl annotate po nginx-dev{1..3} name=webapp
kubectl annotate po nginx-pro{1..2} name=webapp
```
{{% /details %}}

1. {{% details "验证已正确 annotate 的 Pod" %}}
```
kubectl describe po nginx-dev{1..3} | grep -i annotations
kubectl describe po nginx-pro{1..2} | grep -i annotations
```
{{% /details %}}

1. {{% details "删除 Pod 上的 annotate 并验证" %}}
```
kubectl annotate po nginx-dev{1..3} name-
kubectl annotate po nginx-pro{1..2} name-
kubectl describe po nginx-dev{1..3} | grep -i annotations
kubectl describe po nginx-pro{1..2} | grep -i annotations
```
{{% /details %}}

1. {{% details "删除到目前为止我们创建的所有 Pod" %}}
```
kubectl delete pod --all
```
{{% /details %}}

1. {{% details "创建一个名为 webapp 的 Deployment，它带有 5 个副本的镜像 Nginx" %}}
```
kubectl create deployment  webapp --image=nginx --dry-run -o yaml > webapp-deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  creationTimestamp: null
  labels:
    app: webapp
  name: webapp
spec:
  replicas: 5
  selector:
    matchLabels:
      app: webapp
  strategy: {}
  template:
    metadata:
      creationTimestamp: null
      labels:
        app: webapp
    spec:
      containers:
      - image: nginx
        name: nginx
        resources: {}
status: {}
```
{{% /details %}}

1. {{% details "用标签获取我们刚刚创建的 Deployment" %}}
```
kubectl get deploy webapp --show-labels
```
{{% /details %}}

1. {{% details "导出该 Deployment 的 yaml 文件" %}}
```
kubectl get deploy webapp -o yaml
```
{{% /details %}}
 
1. {{% details "获取该 Deployment 的 Pod" %}}
```
kubectl get po -l app=webapp
kubectl get pods -l app=webapp
```
{{% /details %}}

1. {{% details "将该 Deployment 从 5 个副本扩展到 20 个副本并验证" %}}
```
kubectl scale deploy webapp --replicas=20
kubectl get po -l app=webapp
```
{{% /details %}}

1. {{% details "获取该 Deployment 的 rollout 状态" %}}
```
kubectl rollout status deploy webapp
```
{{% /details %}}

1. {{% details "获取使用该 Deployment 创建的副本" %}}
```
kubectl get rs -l app=webapp
```
{{% /details %}}
 
1. {{% details "获取使用该 Deployment 创建的 replicaset" %}}
```
kubectl get rs -l app=webapp
```
{{% /details %}}
 
1. {{% details "获取该 Deployment 的 replicaset 和 Pod 的 yaml" %}}
```
kubectl get rs -l app=webapp -o yaml
kubectl get po -l app=webapp -o yaml
```
{{% /details %}}
 
1. {{% details "删除刚创建的 Deployment，并查看所有 Pod 是否已被删除" %}}
```
kubectl delete deploy webapp
kubectl get po -l app=webapp -w
```
{{% /details %}}
 
1. {{% details "使用镜像 nginx:1.17.1 和容器端口 80 创建 webapp Deployment，并验证镜像版本" %}}
```
kubectl create deploy webapp --image=nginx:1.17.1 --dry-run -o yaml > webapp.yaml
kubectl create -f webapp.yaml
kubectl describe deploy webapp | grep Image

apiVersion: apps/v1
kind: Deployment
metadata:
  creationTimestamp: null
  labels:
    app: webapp
  name: webapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: webapp
  strategy: {}
  template:
    metadata:
      creationTimestamp: null
      labels:
        app: webapp
    spec:
      containers:
      - image: nginx:1.17.1
        name: nginx
        ports:
        - containerPort: 80
        resources: {}
status: {}
```
{{% /details %}}

1. {{% details "检查 rollout 历史记录，并确保更新后一切正常" %}}
```
kubectl rollout history deploy webapp

kubectl get deploy webapp --show-labels
kubectl get rs -l app=webapp
kubectl get po -l app=webapp
```
{{% /details %}}

1. {{% details "撤消之前使用版本 1.17.1 的 Deployment，并验证镜像是否还有老版本" %}}
```
kubectl rollout undo deploy webapp
kubectl rollout history deploy webapp
```
{{% /details %}}
 
1. {{% details "使用镜像版本 1.16.1 更新 Deployment，并验证镜像、检查 rollout 历史记录" %}}
```
kubectl set image deploy/webapp nginx=nginx:1.16.1
kubectl describe deploy webapp | grep Image
kubectl rollout history deploy webapp
```
{{% /details %}}

1. {{% details "将 Deployment 更新到镜像 1.17.1 并确认一切正常" %}}
```
kubectl rollout undo deploy webapp --to-revision=3
kubectl describe deploy webapp | grep Image
kubectl rollout status deploy webapp
```
{{% /details %}}
 
1. {{% details "使用错误的镜像版本 1.100 更新 Deployment，并验证有问题" %}}
```
kubectl set image deploy/webapp nginx=nginx:1.100
kubectl rollout status deploy webapp (still pending state)
kubectl get pods (ImagePullErr)
```
{{% /details %}}

1. {{% details "撤消使用先前版本的 Deployment，并确认一切正常" %}}
```
kubectl rollout undo deploy webapp
kubectl rollout status deploy webapp
kubectl get pods
```
{{% /details %}}

1. {{% details "检查该 Deployment 的特定修订版本的历史记录" %}}
```
kubectl rollout history deploy webapp --revision=7
```
{{% /details %}}

1. {{% details "暂停 Deployment rollout" %}}
```
kubectl rollout pause deploy  webapp
```
{{% /details %}}
 
1. {{% details "用最新版本的镜像更新 Deployment，并检查历史记录" %}}
```
kubectl set image deploy/webapp nginx=nginx:latest
kubectl rollout history deploy webapp
```
{{% /details %}}

1. {{% details "检查 rollout 历史记录，确保是最新版本" %}}
```
kubectl rollout history deploy webapp
kubectl rollout history deploy webapp --revision=9
```
{{% /details %}}

1. {{% details "将自动伸缩应用到该 Deployment 中，最少副本数为 10，最大副本数为 20，目标 CPU 利用率 85%，并验证 hpa 已创建，将副本数从 1 个增加到 10 个" %}}
```
kubectl autoscale deploy webapp --min=10 --max=20 --cpu-percent=85
kubectl get hpa
kubectl get pod -l app=webapp
```
{{% /details %}}

1. {{% details "通过删除刚刚创建的 Deployment 和 hpa 来清理集群" %}}
```
kubectl delete deploy webapp
kubectl delete hpa webapp
```
{{% /details %}}
 
1. {{% details "用镜像 node 来创建一个 Job，并验证是否有对应的 Pod 创建" %}}
```
kubectl create job nodeversion --image=node -- node v
kubectl get job -w
kubectl get pod
```
{{% /details %}}

1. {{% details "获取刚刚创建的 Job 的日志" %}}
```
kubectl logs <pod name> // created from the job
```
{{% /details %}}
 
1. {{% details "用镜像 busybox 输出 Job 的 yaml 文件，并回显“Hello I am from job”" %}}
```
kubectl create job hello-job --image=busybox --dry-run -o yaml -- echo "Hello I am from job"
```
{{% /details %}}

1. {{% details "将上面的 yaml 文件复制到 hello-job.yaml 文件并创建 Job" %}}
```
kubectl create job hello-job --image=busybox --dry-run -o yaml -- echo "Hello I am from job" > hello-job.yaml
 
kubectl apply -f hello-job.yaml
```
{{% /details %}}

1. {{% details "验证 Job 并创建关联的容器，检查日志" %}}
```
kubectl get pod
kubectl get po
kubectl logs po pod-name
```
{{% /details %}}
 
1. {{% details "删除我们刚刚创建的 Job" %}}
```
kubectl delete job hello-job
```
{{% /details %}}

1. {{% details "创建一个相同的 Job，并使它一个接一个地运行 10 次" %}}
```
kubectl create job hello-job --image=busybox --dry-run -o yaml -- echo "Hello I am from job" > 10-job.yaml

apiVersion: batch/v1
kind: Job
metadata:
  creationTimestamp: null
  name: hello-job
spec:
  completions: 10
  template:
    metadata:
      creationTimestamp: null
    spec:
      containers:
      - command:
        - echo
        - Hello I am from job
        image: busybox
        name: hello-job
        resources: {}
      restartPolicy: Never
status: {}
```
{{% /details %}}

1. {{% details "运行 10 次，确认已创建 10 个 Pod，并在完成后删除它们" %}}
```
kubectl delete job hello-job
```
{{% /details %}}

1. {{% details "创建一个带有 busybox 镜像的 Cronjob，每分钟打印一次来自 Kubernetes 集群消息的日期和 hello" %}}
```
kubectl create cronjob date-job --image=busybox --schedule="*/1 * * * *" -- bin/sh -c "date; echo Hello from kubernetes cluster"
```
{{% /details %}}

1. {{% details "输出上述 cronjob 的 yaml 文件" %}}
```
kubectl get cj date-job -o yaml
```
{{% /details %}}

1. {{% details "验证 cronJob 为每分钟运行创建一个单独的 Job 和 Pod，并验证 Pod 的日志" %}}
```
kubectl get job
kubectl get po
kubectl logs date-job-<jobid>-<pod>
```
{{% /details %}}
 
1. {{% details "删除 cronJob，并验证所有关联的 Job 和 Pod 也都被删除" %}}
```
kubectl delete cj date-job
kubectl get po
kubectl get job
```
{{% /details %}}

## 状态持久性

了解存储的持久卷声明。
 
1. {{% details "列出集群中的持久卷" %}}
```
kubectl get pv
```
{{% /details %}}

1. {{% details "创建一个名为 task-pv-volume 的 PersistentVolume，其 storgeClassName 为 manual，storage 为 10Gi，accessModes 为 ReadWriteOnce，hostPath 为 /mnt/data" %}}
```
task-pv-volume.yaml

apiVersion: v1
kind: PersistentVolume
metadata:
  name: task-pv-volume
  labels: 
    type: local
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  hostPath: 
    path: "/mnt/data"
```
{{% /details %}}

1. {{% details "创建一个存储至少 3Gi、访问模式为 ReadWriteOnce 的 PersistentVolumeClaim，并确认它的状态是否是绑定的" %}}
```
kubectl create -f task-pv-claim.yaml
kubectl get pvc

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: task-pv-claim
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 3Gi
  storageClassName: manual
```
{{% /details %}}

1. {{% details "删除我们刚刚创建的持久卷和 PersistentVolumeClaim" %}}
```
kubectl delete pvc task-pv-claim
kubectl delete pv task-pv-volume
```
{{% /details %}}
 
1. {{% details "使用镜像 Redis 创建 Pod，并配置一个在 Pod 生命周期内可持续使用的卷" %}}
```
redis-storage.yaml

apiVersion: v1
kind: Pod
metadata:
  name: redis
spec:
  containers:
  - name: redis
    image: redis
    volumeMounts:
    - name: redis-storage
      mountPath: /data/redis
  volumes:
  - name: redis-storage
    emptyDir: {}
```
{{% /details %}}

1. {{% details "在上面的 Pod 中执行操作，并在 /data/redis 路径中创建一个名为 file.txt 的文件，其文本为“This is the file”，然后打开另一个选项卡，再次使用同一 Pod 执行，并验证文件是否在同一路径中" %}}
```
kubectl exec -it redis /bin/sh
cd /data/redis
echo "This is the file" > file.txt
```
{{% /details %}}

1. {{% details "删除上面的 Pod，然后从相同的 yaml 文件再次创建，并验证路径 /data/redis 中是否没有 file.txt" %}}
```
kubectl delete po redis
kubectl apply -f redis-storage.yaml
kubectl exec -it redis /bin/sh
cat /data/redis/file.txt
cat: /data/redis/file.txt: No such file or directory
```
{{% /details %}}
 
1. {{% details "创建一个名为 task-pv-volume 的 PersistentVolume，其 storgeClassName 为 manual，storage 为 10Gi，accessModes 为 ReadWriteOnce，hostPath 为 /mnt/data；并创建一个存储至少 3Gi、访问模式为 ReadWriteOnce 的 PersistentVolumeClaim，并确认它的状态是否是绑定的" %}}
```
kubectl create -f task-pv-volume.yaml
kubectl create -f task-pv-claim.yaml
kubectl get pv
kubectl get pvc

task-pv-volume.yaml：
apiVersion: v1
kind: PersistentVolume
metadata:
  name: task-pv-volume
  labels: 
    type: local
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  hostPath: 
    path: "/mnt/data"

task-pv-claim.yaml：
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: task-pv-claim
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 3Gi
  storageClassName: manual
```
{{% /details %}}

1. {{% details "用容器端口 80 和 PersistentVolumeClaim task-pv-claim 创建一个 Nginx 容器，且具有路径“/usr/share/nginx/html”" %}}
```
ask-pv-pod.yaml
 
apiVersion: v1
kind: Pod
metadata:
  name: task-pv-pod
spec:
  containers:
    - name: task-pv-container
      image: nginx
      ports:
        - containerPort: 80
          name: "http-server"
      volumeMounts:
      - mountPath: "/usr/share/nginx/html"
        name: task-pv-storage
  volumes:
    - name: task-pv-storage
      persistentVolumeClaim:
        claimName: task-pv-claim
```
{{% /details %}}

## 配置

了解 ConfigMap、了解安全上下文 SecurityContexts、定义应用程序的资源需求、创建和使用 Secrets、了解 ServiceAccounts等。

## 可观测性

了解 LivenessProbe 和 Readiness Probe、了解容器日志记录、了解如何监控 kubernetes 中的应用程序、了解如何调试 Kubernetes。

## 服务与网络

了解服务、NetworkPolicies 等。

# 总结

配置、可观测性、服务、网络等示例习题，请参考附录，CKAD 要求在 2 小时内完成 19 个问题。我们需要为此进行大量练习，这 150 个问题提供了足够的考试练习机会。更多内容可以参考 [cncf-curriculum](https://github.com/cncf/curriculum)，练习得越多，考试时就会感觉越舒服。

多练习、多练习、多练习。
 
# 附录

1. https://medium.com/bb-tutorials-and-thoughts/practice-enough-with-these-questions-for-the-ckad-exam-2f42d1228552
1. https://github.com/cncf/curriculum
