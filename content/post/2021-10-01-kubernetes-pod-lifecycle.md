---
layout:     post
title:      "Kubernetes 中 Pod 生命周期"
subtitle:   ""
description: "Pod 是 Kubernetes 集群中可以调度的最小工作单位。Pod 封装了应用程序容器、存储资源、唯一的网络 IP 和决定容器应如何运行的选项。理想情况下，Pod 并不直接在集群上部署，而是使用更高级的抽象资源，比如 DeployMent、StatefulSet 等。深入理解 Pod 对于排查问题是很重要的。"
author: "陈谭军"
date: 2021-10-01
published: true
tags:
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

Pod 是 Kubernetes 集群中可以调度的最小工作单位。Pod 封装了应用程序容器、存储资源、唯一的网络 IP 和决定容器应如何运行的选项。理想情况下，Pod 并不直接在集群上部署，而是使用更高级的抽象资源，比如 DeployMent、StatefulSet 等。深入理解 Pod 对于排查问题是很重要的。

# Pod 状态

在 Pod 生命周期中，有以下状态：
* Pending：Pod 已被 Kubernetes 调度器接受，但其容器尚未创建。
* Running：Pod 已在节点上调度，并且所有容器都已创建，至少有一个容器处于运行状态。
* Succeeded：Pod 中的所有容器都已以状态 0 退出，并且不会重启。
* Failed：Pod 的所有容器都已退出，并且至少有一个容器返回了非零状态。
* CrashLoopBackoff：容器启动失败，并反复尝试。

# Pod 生命周期

![](/images/2021-10-01-kubernetes-pod-lifecycle/1.png)

现在让我们来看看 Pod 创建流程：
* kubectl或任何其他API客户端将Pod提交给API服务器。
* API服务器将Pod对象写入etcd。一旦写操作成功，就会向API服务器和客户端发送确认信号。
* API服务器反映了etcd的状态变化。
* 所有Kubernetes组件都使用list+watch来持续检查API服务器的相关资源变化。
* 在这种情况下，kube-scheduler（list+watch）看到API服务器上创建了一个新的Pod对象，但没有绑定到任何节点。
* kube-scheduler为pod分配一个节点并更新API服务器。
* 此更改然后传播到etcd。API服务器也在其Pod对象上反映此节点分配。
* 每个节点上的Kubelet也通过（list+watch）API服务器，目标节点上的Kubelet看到一个新的Pod被分配给它。
* Kubelet通过调用docker/containerd在其节点上启动pod，并将容器状态更新回API服务器。
* API服务器将pod状态持久化到etcd。
* 一旦etcd发送了成功写入的确认，API服务器会向kubelet发送确认，表明该事件已被成功接受。

# Pod 生命周期中的活动

## Init Containers

init 初始化容器是在主应用程序容器启动之前运行的容器。它们有两个重要特性：
* 它们总是运行到完成。
* 每个初始化容器必须在下一个开始之前完成。

当在Pod的主容器开始之前需要运行一些初始操作时，初始化容器很有作用。比如复制配置文件和更新配置值，初始化容器使用不同的Linux命名空间，这可能不适合在应用程序容器内部共享。因为它们有一个不同的文件系统视图，所以它们可以被赋予访问 secrets 的权限。

## Lifecycle Hooks

kubelet 可以运行由容器生命周期 hook 钩子触发的代码。这允许用户在容器生命周期的特定事件期间运行特定的代码。比如在终止容器之前运行一个优雅的关闭脚本。有以下类型的 Hook 点。
* PostStart：这个钩子在容器创建时执行，但是不能保证它会在容器的 ENTRYPOINT 之后运行。
* PreStop：这个钩子在容器终止之前执行。这是一个阻塞调用，这意味着必须在发送删除容器的调用之前完成钩子执行。
上述两个钩子都不需要任何参数。在钩子实现中可以实现两种类型的处理器：
* Exec：在容器内部运行特定的命令，命令消耗的资源将计入容器。
* HTTP：对容器上的特定服务执行HTTP请求。

## Container Probes

除了生命周期 Hook 钩子外，在 Pod 生命周期中另一件重要事情是执行容器探针。容器探针是 kubelet 对容器进行的诊断，kubelet 可以在运行中的容器上运行两种探针：
* livenessProbe：表示容器是否在运行。如果存活性探针失败，kubelet 会杀死容器，容器将受到其重启策略的影响。
* readinessProbe：表示容器是否准备好处理请求。如果这个探针失败，端点控制器（Endpoint Controller）会从匹配Pod的所有服务的端点列表中删除容器IP。

有三种方式可以实现容器探针探测：
* ExecAction：在容器内执行命令，如果命令返回0，诊断被认为是成功的。
* TCPSocketAction：对容器IP和指定端口执行TCP套接字检查，如果端口是开放的，诊断被认为是成功的。
* HTTPGetAction：对容器IP执行HTTP GET操作，并指定端口和路径，如果响应的状态码在200到400之间，诊断被认为是成功的。

# Termination of a Pod

Pod 终止的流程如下所示：
* 用户发送一个删除Pod的命令。
* API服务器中的Pod对象更新了Pod被认为是“死亡”的时间（默认为30秒）以及宽限期。
* 以下操作并行进行：
  * 当在客户端命令中列出Pod显示为“Terminating”。
  * 当Kubelet看到一个Pod已经被标记为终止，因为在2中设置的时间，它开始Pod关闭过程。
  * 端点控制器（Endpoint Controller）监视即将被删除的pod，因此从所有由Pod服务的端点中删除Pod。
* 如果Pod定义了一个preStop钩子，它将在Pod内部被调用。如果preStop钩子在宽限期过期后仍在运行，步骤2将在宽限期稍微延长（2秒）后被调用。
* Pod中的进程被发送TERM信号。
* 当宽限期到期时，Pod中仍在运行的任何进程都会被SIGKILL杀死。
* Kubelet将通过设置宽限期0（立即删除）在API服务器上完成对Pod的删除。
* Pod从API被永久删除，客户端无法再看到它。

# 总结

我们可以看到有多种方法可以控制Pod生命周期内发生的事件。初始化容器可以帮助消除与容器引导相关大量复杂性工作，从而帮助保持主容器中的逻辑简单。同样，postStart生命周期钩子可以帮助运行任何代码（如注册到监控系统或服务网格）需要在容器开始运行后执行。存活性和就绪性探针可以帮助在Pod开始影响之前移除不良Pod。优雅的关机可以作为一个预停止生命周期钩子运行，允许更优雅的退出。了解上述机制可以帮助更好地理解 Kubernetes。

# 参考

1. https://blog.heptio.com/core-kubernetes-jazz-improv-over-orchestration-a7903ea92ca