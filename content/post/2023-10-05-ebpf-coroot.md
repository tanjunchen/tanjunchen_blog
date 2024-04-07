---
layout:     post
title:      "使用 coroot 实现 Kubernetes 服务可观测性（2）"
subtitle:   "coroot 是针对微服务架构的可观测性和故障分析工具，它基于 eBPF 来可视化展示服务之间的拓扑关系，并对七层与四层的可观测性进行了强化，可以帮助你快速定位七层与四层的故障。"
description: "本篇文章主要介绍 Coroot 架构、核心功能、示例、核心源码、示例等。"
author: "陈谭军"
date: 2023-10-05
published: true
tags:
    - kubernetes
    - coroot
    - eBPF
    - opentelemetry
categories:
    - TECHNOLOGY
showtoc: true
---

核心实现思路：  
[coroot](https://github.com/coroot/coroot) 使用数据库 SQLite（生产环境 Click House）+ Prometheus + Opentelemetry 去做应用（网络、IO、磁盘、文件等）可视化。  
[coroot-node-agent](https://github.com/coroot/coroot-node-agent) 使用 eBPF（tracepoint + uprobe）+ 容器网络工具（cgroup + namespace）收集节点及其上运行的容器相关的信息，并以 Prometheus 暴露指标，支持的最低 Linux 内核版本为 4.16+。

# 介绍

## 前置条件

* Coroot 依赖 eBPF，支持的最小 Linux 版本 4.16+；
* 基于 eBPF 的持续性能分析（profiling）利用了 CO-RE。大多数现代Linux发行版都支持 CO-RE，如下所示：
  * Ubuntu 20.10及以上版本
  * Debian 11及以上版本
  * RHEL 8.2及以上版本
* Coroot 收集指标（Metrics）、日志（Logs）、跟踪（Traces）和性能分析数据（Profiling），每个遥测 telemetry 都与容器相关联。在这个上下文中，容器指的是在专用 cgroup 中运行的一组进程。支持以下类型的容器：
  * 使用Docker、Containerd 或 CRI-O 作为运行时环境的 Kubernetes Pods 等
  * 独立容器：Docker、Containerd、CRI-O 等
  * Docker Swarm 等
  * Systemd units：任何systemd服务也被视为容器。
* 支持的容器编排系统如下所示：
  * Kubernetes：自建 Kubernetes 集群、EKS（支持 AWS Fargate）、GKE、AKS、OKE
  * OpenShift
  * K3s
  * MicroK8s
  * Docker Swarm
* 限制
  * 由于 eBPF 限制，Coroot 不支持 Docker-in-Docker环境，如MiniKube
  * 目前还不支持WSL（Windows Subsystem for Linux）

## coroot

https://github.com/coroot/coroot 是一款基于 eBPF 的开源可观测性工具，可将遥测数据转化为可操作视图，帮助快速识别和解决应用程序问题。官方示例可参考 https://community-demo.coroot.com/p/qcih204s。coroot 的架构设计基于 prometheus，同时也依赖了 eBPF，同时官方也开源了不少 exporter，比如 node，pg，aws 等。

**重点功能**
* [Zero-instrumentation observability](https://github.com/coroot/coroot#zero-instrumentation-observability)
* [Distributed systems are no longer blackboxes](https://github.com/coroot/coroot#distributed-systems-are-no-longer-blackboxes)
* [Built-in expertise](https://github.com/coroot/coroot#built-in-expertise)
* [Explore any outlier requests with distributed tracing](https://github.com/coroot/coroot#explore-any-outlier-requests-with-distributed-tracing)
* [Grasp insights from logs with just a quick glance](https://github.com/coroot/coroot#grasp-insights-from-logs-with-just-a-quick-glance)
* [Profile any application in 1 click](https://github.com/coroot/coroot#profile-any-application-in-1-click)
* [Deployment Tracking](https://github.com/coroot/coroot#deployment-tracking)
* [Cost Monitoring](https://github.com/coroot/coroot#cost-monitoring)

## coroot-node-agent 

https://github.com/coroot/coroot-node-agent ，使用 eBPF 与 network 相关工具收集节点及其上运行的容器相关的信息，并以 Prometheus 格式公开这些指标。它使用 eBPF 来跟踪与容器相关的事件，如 TCP 连接，因此支持的最低Linux内核版本为 **4.16+**。

**重点功能**
* [TCP connection tracing](https://github.com/coroot/coroot-node-agent#tcp-connection-tracing)
* [Log patterns extraction](https://github.com/coroot/coroot-node-agent#log-patterns-extraction)
* [Delay accounting](https://github.com/coroot/coroot-node-agent#delay-accounting)
* [Out-of-memory events tracing](https://github.com/coroot/coroot-node-agent#out-of-memory-events-tracing)
* [Instance meta information](https://github.com/coroot/coroot-node-agent#instance-meta-information)

架构图如下所示：
<img src="/images/2023-10-05-ebpf-coroot/coroot-node-agent.png" width="100%">

片段 C 代码如下所示：
```C
struct trace_event_raw_args_with_fd__stub {
    __u64 unused;
    long int id;
    __u64 fd;
};

SEC("tracepoint/syscalls/sys_enter_connect")
int sys_enter_connect(void *ctx) {
    struct trace_event_raw_args_with_fd__stub args = {};
    if (bpf_probe_read(&args, sizeof(args), ctx) < 0) {
        return 0;
    }
    __u64 id = bpf_get_current_pid_tgid();
    bpf_map_update_elem(&fd_by_pid_tgid, &id, &args.fd, BPF_ANY);
    return 0;
}

SEC("tracepoint/syscalls/sys_exit_connect")
int sys_exit_connect(void *ctx) {
    __u64 id = bpf_get_current_pid_tgid();
    bpf_map_delete_elem(&fd_by_pid_tgid, &id);
    return 0;
}
```

**指标**：coroot 暴露的 metrics 指标，可参考：[metric-exporters](https://coroot.com/docs/metric-exporters/node-agent/metrics)。核心网络、IO、磁盘、文件等指标如下所示：
```shell
root@cce-lo9d0ykc-lq252ra3:/# curl  http://10.2.1.243/metrics
# HELP container_application_type Type of the application running in the container (e.g. memcached, postgres, mysql)
# TYPE container_application_type gauge
container_application_type{application_type="envoy",container_id="/k8s/istio-system/istio-egressgateway-6664b79cb7-ch98h/istio-proxy",machine_id="8a79accec39b4434969f48d0d837c935"} 1
container_application_type{application_type="envoy",container_id="/k8s/istio-system/istio-ingressgateway-787dc49b87-w4lw8/istio-proxy",machine_id="8a79accec39b4434969f48d0d837c935"} 1
container_application_type{application_type="kubelet",container_id="/system.slice/kubelet.service",machine_id="8a79accec39b4434969f48d0d837c935"} 1
# HELP node_net_received_packets_total The total number of packets received
# TYPE node_net_received_packets_total counter
node_net_received_packets_total{interface="eth0",machine_id="8a79accec39b4434969f48d0d837c935"} 1.20680598e+08
# HELP node_net_transmitted_bytes_total The total number of bytes transmitted
# TYPE node_net_transmitted_bytes_total counter
node_net_transmitted_bytes_total{interface="eth0",machine_id="8a79accec39b4434969f48d0d837c935"} 9.801357895e+09
# HELP node_net_transmitted_packets_total The total number of packets transmitted
# TYPE node_net_transmitted_packets_total counter
node_net_transmitted_packets_total{interface="eth0",machine_id="8a79accec39b4434969f48d0d837c935"} 9.4272602e+07
# HELP node_resources_cpu_logical_cores The number of logical CPU cores
# TYPE node_resources_cpu_logical_cores gauge
node_resources_cpu_logical_cores{machine_id="8a79accec39b4434969f48d0d837c935"} 2
# HELP node_resources_cpu_usage_seconds_total The amount of CPU time spent in each mode
# TYPE node_resources_cpu_usage_seconds_total counter
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="idle"} 4.22894521e+06
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="iowait"} 1582.97
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="irq"} 0
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="nice"} 349.25
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="softirq"} 4837.57
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="steal"} 0
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="system"} 25167.31
node_resources_cpu_usage_seconds_total{machine_id="8a79accec39b4434969f48d0d837c935",mode="user"} 56604.1
# HELP node_resources_disk_io_time_seconds_total The total number of seconds the disk spent doing I/O
# TYPE node_resources_disk_io_time_seconds_total counter
node_resources_disk_io_time_seconds_total{device="vda",machine_id="8a79accec39b4434969f48d0d837c935"} 4896.908
......
```

<font color=red>**核心实现思路：tracepoint （uprobe） + cilium/ebpf**</font>

* SEC(<font color=green>"tracepoint/sock/inet_sock_set_state"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_connect"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_connect"</font>)
* SEC(<font color=green>"tracepoint/tcp/tcp_retransmit_skb"</font>)
* SEC(<font color=green>"tracepoint/syscalls/sys_enter_open"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_open"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_openat"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_openat"</font>)
* SEC(<font color=green>"tracepoint/task/task_newtask"</font>)、SEC(<font color=green>"tracepoint/sched/sched_process_exit"</font>)、SEC(<font color=green>"tracepoint/oom/mark_victim"</font>)
* SEC(<font color=green>"uprobe/go_crypto_tls_write_enter"</font>)、SEC(<font color=green>"uprobe/go_crypto_tls_read_enter"</font>)、SEC(<font color=green>"uprobe/go_crypto_tls_read_exit"</font>)
* SEC(<font color=green>"tracepoint/syscalls/sys_enter_write"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_writev"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_sendmsg"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_sendto"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_read"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_readv"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_recvmsg"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_enter_recvfrom"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_read"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_readv"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_recvmsg"</font>)、SEC(<font color=green>"tracepoint/syscalls/sys_exit_recvfrom"</font>)
* SEC(<font color=green>"uprobe/openssl_SSL_write_enter"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_write_enter_v1_1_1"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_write_enter_v3_0"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_enter"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_ex_enter"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_enter_v1_1_1"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_ex_enter_v1_1_1"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_enter_v3_0"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_ex_enter_v3_0"</font>)、SEC(<font color=green>"uprobe/openssl_SSL_read_exit"</font>)

# demo 演示

## 安装

参考 [coroot部署文档](https://coroot.com/docs/coroot-community-edition/getting-started/installation#manual_k8s) 安装 coroot。 

1. 部署并创建 StorageClass，用于动态创建 pv
<!-- <img src="/images/2023-10-05-ebpf-coroot/插件.png" width="100%">   -->

2. 创建两个 sc
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: cds-hp
parameters:
  cdsSizeInGB: "100"
  dynamicVolume: "true"
  paymentTiming: Prepaid
  reservationLength: "3"
  storageType: hdd
provisioner: csi-cdsplugin
reclaimPolicy: Retain
volumeBindingMode: Immediate
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: cds-hp-test
parameters:
  cdsSizeInGB: "100"
  dynamicVolume: "true"
  paymentTiming: Prepaid
  reservationLength: "3"
  storageType: hdd
provisioner: csi-cdsplugin
reclaimPolicy: Retain
volumeBindingMode: Immediate
```

3. 安装 coroot
```bash
helm repo add coroot https://coroot.github.io/helm-charts
helm repo update 

helm install --namespace coroot --create-namespace coroot coroot/coroot
```

4. 在 pvc 指定 sc，先删除 coroot 空间下所有的 pvc，再使用下面的文件创建，在 `storageClassNamestorageClassName` 字段声明让 pvc 与 sc 绑定。

```yaml
apiVersion: v1
items:
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    annotations:
      meta.helm.sh/release-name: coroot
      meta.helm.sh/release-namespace: coroot
    finalizers:
    - kubernetes.io/pvc-protection
    labels:
      app.kubernetes.io/instance: coroot
      app.kubernetes.io/managed-by: Helm
      app.kubernetes.io/name: coroot
      app.kubernetes.io/version: 0.19.2
      helm.sh/chart: coroot-0.4.7
    name: coroot-data
    namespace: coroot
  spec:
    accessModes:
    - ReadWriteOnce
    storageClassName: cds-hp-test
    resources:
      requests:
        storage: 10Gi
    volumeMode: Filesystem
  status:
    phase: Pending
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    annotations:
      meta.helm.sh/release-name: coroot
      meta.helm.sh/release-namespace: coroot
    finalizers:
    - kubernetes.io/pvc-protection
    labels:
      app: prometheus
      app.kubernetes.io/managed-by: Helm
      chart: prometheus-15.16.1
      component: server
      heritage: Helm
      release: coroot
    name: coroot-prometheus-server
    namespace: coroot
  spec:
    accessModes:
    - ReadWriteOnce
    storageClassName: cds-hp-test
    resources:
      requests:
        storage: 10Gi
    volumeMode: Filesystem
  status:
    phase: Pending
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    annotations:
      meta.helm.sh/release-name: coroot
      meta.helm.sh/release-namespace: coroot
    finalizers:
    - kubernetes.io/pvc-protection
    labels:
      app.kubernetes.io/instance: coroot
      app.kubernetes.io/managed-by: Helm
      app.kubernetes.io/name: pyroscope
      app.kubernetes.io/version: 0.37.2
      helm.sh/chart: pyroscope-0.2.92
    name: coroot-pyroscope
    namespace: coroot
  spec:
    accessModes:
    - ReadWriteOnce
    storageClassName: cds-hp-test
    resources:
      requests:
        storage: 30Gi
    volumeMode: Filesystem
  status:
    phase: Pending
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    finalizers:
    - kubernetes.io/pvc-protection
    labels:
      app.kubernetes.io/component: clickhouse
      app.kubernetes.io/instance: coroot
      app.kubernetes.io/managed-by: Helm
      app.kubernetes.io/name: clickhouse
      helm.sh/chart: clickhouse-3.1.6
    name: data-coroot-clickhouse-shard0-0
    namespace: coroot
  spec:
    accessModes:
    - ReadWriteOnce
    storageClassName: cds-hp
    resources:
      requests:
        storage: 50Gi
    volumeMode: Filesystem
  status:
    phase: Pending
kind: List
metadata:
  resourceVersion: ""
```

5. 重启所有有问题的 pod
<!-- <img src="/images/2023-10-05-ebpf-coroot/重启pod.png" width="100%">   -->

6. 查看效果 http://localhost:8080/ 。
```bash
kubectl port-forward -n coroot service/coroot 8080:8080
```

<img src="/images/2023-10-05-ebpf-coroot/查看效果.png" width="100%">  

## 示例
<img src="/images/2023-10-05-ebpf-coroot/示例1.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例2.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例3.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例4.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例5.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例6.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例7.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例8.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例9.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例10.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例11.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例12.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例13.png" width="100%">
<img src="/images/2023-10-05-ebpf-coroot/示例14.png" width="100%">

Pyroscope 是一个开源的持续分析系统，使用 Go 语言实现。服务端使用 web 页面查看，提供丰富的分析的功能，客户端提供 Go、Java、Python、Ruby、PHP、.NET 等多种语言的支持，并且支持 PUSH、PULL 两种采集方式。

<img src="/images/2023-10-05-ebpf-coroot/Pyroscope.png" width="100%">

# 代码

registry.go
```Go
func NewRegistry(reg prometheus.Registerer, kernelVersion string) (*Registry, error) {
	ns, err := proc.GetSelfNetNs()
	if err != nil {
		return nil, err
	}
	selfNetNs = ns
	hostNetNs, err := proc.GetHostNetNs()
	if err != nil {
		return nil, err
	}
	defer hostNetNs.Close()
	hostNetNsId = hostNetNs.UniqueId()

	err = proc.ExecuteInNetNs(hostNetNs, selfNetNs, func() error {
		if err := TaskstatsInit(); err != nil {
			return err
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
    // 初始化某些 ns 命名空间
	if err := cgroup.Init(); err != nil {
		return nil, err
	}
    // 初始化 docker
	if err := DockerdInit(); err != nil {
		klog.Warningln(err)
	}
    // 初始化 containerd
	if err := ContainerdInit(); err != nil {
		klog.Warningln(err)
	}
    // 初始化 crio
	if err := CrioInit(); err != nil {
		klog.Warningln(err)
	}
    // 初始化 journal
	if err := JournaldInit(); err != nil {
		klog.Warningln(err)
	}
    // 初始化 journal
	ct, err := NewConntrack(hostNetNs)
	if err != nil {
		return nil, err
	}

	r := &Registry{
		reg:    reg,
		events: make(chan ebpftracer.Event, 10000),

		hostConntrack: ct,

		containersById:       map[ContainerID]*Container{},
		containersByCgroupId: map[string]*Container{},
		containersByPid:      map[uint32]*Container{},

		tracer: ebpftracer.NewTracer(kernelVersion, *flags.DisableL7Tracing),
	}
    // 处理事件 收集容器、主机等指标
	go r.handleEvents(r.events)
    
    // eBPF 数据与程序收集器交换媒介
	if err = r.tracer.Run(r.events); err != nil {
		close(r.events)
		return nil, err
	}

	return r, nil
}
```

cgroup_linux.go
```Go
func Init() error {
	selfNs, err := netns.GetFromPath("/proc/self/ns/cgroup")
	if err != nil {
		return err
	}
	defer selfNs.Close()
	hostNs, err := netns.GetFromPath("/proc/1/ns/cgroup")
	if err != nil {
		return err
	}
	defer hostNs.Close()
	if selfNs.Equal(hostNs) {
		return nil
	}

	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	if err := unix.Setns(int(hostNs), unix.CLONE_NEWCGROUP); err != nil {
		return err
	}

	cg, err := NewFromProcessCgroupFile("/proc/self/cgroup")
	if err != nil {
		return err
	}
	baseCgroupPath = cg.Id

	if err := unix.Setns(int(selfNs), unix.CLONE_NEWCGROUP); err != nil {
		return err
	}

	return nil
}
```

handleEvents.go
```Go
func (r *Registry) handleEvents(ch <-chan ebpftracer.Event) {
	gcTicker := time.NewTicker(gcInterval)
	defer gcTicker.Stop()
	for {
		select {
		case now := <-gcTicker.C:
			for pid, c := range r.containersByPid {
				cg, err := proc.ReadCgroup(pid)
				if err != nil {
					delete(r.containersByPid, pid)
					if c != nil {
						c.onProcessExit(pid, false)
					}
					continue
				}
				if c != nil && cg.Id != c.cgroup.Id {
					delete(r.containersByPid, pid)
					c.onProcessExit(pid, false)
				}
			}

			for id, c := range r.containersById {
				if !c.Dead(now) {
					continue
				}
				klog.Infoln("deleting dead container:", id)
				for cg, cc := range r.containersByCgroupId {
					if cc == c {
						delete(r.containersByCgroupId, cg)
					}
				}
				for pid, cc := range r.containersByPid {
					if cc == c {
						delete(r.containersByPid, pid)
					}
				}
				if ok := prometheus.WrapRegistererWith(prometheus.Labels{"container_id": string(id)}, r.reg).Unregister(c); !ok {
					klog.Warningln("failed to unregister container:", id)
				}
				delete(r.containersById, id)
				c.Close()
			}

		case e, more := <-ch:
			if !more {
				return
			}
			switch e.Type {
			case ebpftracer.EventTypeProcessStart:
				c, seen := r.containersByPid[e.Pid]
				switch { // possible pids wraparound + missed `process-exit` event
				case c == nil && seen: // ignored
					delete(r.containersByPid, e.Pid)
				case c != nil: // revalidating by cgroup
					cg, err := proc.ReadCgroup(e.Pid)
					if err != nil || cg.Id != c.cgroup.Id {
						delete(r.containersByPid, e.Pid)
						c.onProcessExit(e.Pid, false)
					}
				}
				if c := r.getOrCreateContainer(e.Pid); c != nil {
					c.onProcessStart(e.Pid)
				}
			case ebpftracer.EventTypeProcessExit:
				if c := r.containersByPid[e.Pid]; c != nil {
					c.onProcessExit(e.Pid, e.Reason == ebpftracer.EventReasonOOMKill)
				}
				delete(r.containersByPid, e.Pid)

			case ebpftracer.EventTypeFileOpen:
				if c := r.getOrCreateContainer(e.Pid); c != nil {
					c.onFileOpen(e.Pid, e.Fd)
				}

			case ebpftracer.EventTypeListenOpen:
				if c := r.getOrCreateContainer(e.Pid); c != nil {
					c.onListenOpen(e.Pid, e.SrcAddr, false)
				} else {
					klog.Infoln("TCP listen open from unknown container", e)
				}
			case ebpftracer.EventTypeListenClose:
				if c := r.containersByPid[e.Pid]; c != nil {
					c.onListenClose(e.Pid, e.SrcAddr)
				}

			case ebpftracer.EventTypeConnectionOpen:
				if c := r.getOrCreateContainer(e.Pid); c != nil {
					c.onConnectionOpen(e.Pid, e.Fd, e.SrcAddr, e.DstAddr, e.Timestamp, false)
					c.attachTlsUprobes(r.tracer, e.Pid)
				} else {
					klog.Infoln("TCP connection from unknown container", e)
				}
			case ebpftracer.EventTypeConnectionError:
				if c := r.getOrCreateContainer(e.Pid); c != nil {
					c.onConnectionOpen(e.Pid, e.Fd, e.SrcAddr, e.DstAddr, 0, true)
				} else {
					klog.Infoln("TCP connection error from unknown container", e)
				}
			case ebpftracer.EventTypeConnectionClose:
				srcDst := AddrPair{src: e.SrcAddr, dst: e.DstAddr}
				for _, c := range r.containersById {
					if c.onConnectionClose(srcDst) {
						break
					}
				}
			case ebpftracer.EventTypeTCPRetransmit:
				srcDst := AddrPair{src: e.SrcAddr, dst: e.DstAddr}
				for _, c := range r.containersById {
					if c.onRetransmit(srcDst) {
						break
					}
				}
			case ebpftracer.EventTypeL7Request:
				if e.L7Request == nil {
					continue
				}
				if c := r.containersByPid[e.Pid]; c != nil {
					c.onL7Request(e.Pid, e.Fd, e.Timestamp, e.L7Request)
				}
			}
		}
	}
}
```

onL7Request.go
```Go
func (c *Container) onL7Request(pid uint32, fd uint64, timestamp uint64, r *l7.RequestData) {
	c.lock.Lock()
	defer c.lock.Unlock()

	var dest AddrPair
	var conn *ActiveConnection
	var found bool
	for dest, conn = range c.connectionsActive {
		if conn.Pid == pid && conn.Fd == fd && (timestamp == 0 || conn.Timestamp == timestamp) {
			found = true
			break
		}
	}
	if !found {
		return
	}

	stats := c.l7Stats.get(r.Protocol, dest.dst, conn.ActualDest)
	trace := tracing.NewTrace(string(c.id), conn.ActualDest)
	switch r.Protocol {
	case l7.ProtocolHTTP:
		stats.observe(r.Status.Http(), "", r.Duration)
		method, path := l7.ParseHttp(r.Payload)
		trace.HttpRequest(method, path, r.Status, r.Duration)
	case l7.ProtocolHTTP2:
		if conn.http2Parser == nil {
			conn.http2Parser = l7.NewHttp2Parser()
		}
		requests := conn.http2Parser.Parse(r.Method, r.Payload, uint64(r.Duration))
		for _, req := range requests {
			stats.observe(req.Status.Http(), "", req.Duration)
			trace.Http2Request(req.Method, req.Path, req.Scheme, req.Status, req.Duration)
		}
	case l7.ProtocolPostgres:
		if r.Method != l7.MethodStatementClose {
			stats.observe(r.Status.String(), "", r.Duration)
		}
		if conn.postgresParser == nil {
			conn.postgresParser = l7.NewPostgresParser()
		}
		query := conn.postgresParser.Parse(r.Payload)
		trace.PostgresQuery(query, r.Status.Error(), r.Duration)
	case l7.ProtocolMysql:
		if r.Method != l7.MethodStatementClose {
			stats.observe(r.Status.String(), "", r.Duration)
		}
		if conn.mysqlParser == nil {
			conn.mysqlParser = l7.NewMysqlParser()
		}
		query := conn.mysqlParser.Parse(r.Payload, r.StatementId)
		trace.MysqlQuery(query, r.Status.Error(), r.Duration)
	case l7.ProtocolMemcached:
		stats.observe(r.Status.String(), "", r.Duration)
		cmd, items := l7.ParseMemcached(r.Payload)
		trace.MemcachedQuery(cmd, items, r.Status.Error(), r.Duration)
	case l7.ProtocolRedis:
		stats.observe(r.Status.String(), "", r.Duration)
		cmd, args := l7.ParseRedis(r.Payload)
		trace.RedisQuery(cmd, args, r.Status.Error(), r.Duration)
	case l7.ProtocolMongo:
		stats.observe(r.Status.String(), "", r.Duration)
		query := l7.ParseMongo(r.Payload)
		trace.MongoQuery(query, r.Status.Error(), r.Duration)
	case l7.ProtocolKafka, l7.ProtocolCassandra:
		stats.observe(r.Status.String(), "", r.Duration)
	case l7.ProtocolRabbitmq, l7.ProtocolNats:
		stats.observe(r.Status.String(), r.Method.String(), 0)
	}
}
```

container 如何收集数据？Collect.go 代码如下所示：
```Go
func (c *Container) Collect(ch chan<- prometheus.Metric) {
	c.lock.RLock()
	defer c.lock.RUnlock()

	if c.metadata.image != "" {
		ch <- gauge(metrics.ContainerInfo, 1, c.metadata.image)
	}

	ch <- counter(metrics.Restarts, float64(c.restarts))

	if cpu, err := c.cgroup.CpuStat(); err == nil {
		if cpu.LimitCores > 0 {
			ch <- gauge(metrics.CPULimit, cpu.LimitCores)
		}
		ch <- counter(metrics.CPUUsage, cpu.UsageSeconds)
		ch <- counter(metrics.ThrottledTime, cpu.ThrottledTimeSeconds)
	}

	if taskstatsClient != nil {
		c.updateDelays()
		ch <- counter(metrics.CPUDelay, float64(c.delays.cpu)/float64(time.Second))
		ch <- counter(metrics.DiskDelay, float64(c.delays.disk)/float64(time.Second))
	}

	if s, err := c.cgroup.MemoryStat(); err == nil {
		ch <- gauge(metrics.MemoryRss, float64(s.RSS))
		ch <- gauge(metrics.MemoryCache, float64(s.Cache))
		if s.Limit > 0 {
			ch <- gauge(metrics.MemoryLimit, float64(s.Limit))
		}
	}

	if c.oomKills > 0 {
		ch <- counter(metrics.OOMKills, float64(c.oomKills))
	}

	if disks, err := node.GetDisks(); err == nil {
		ioStat, _ := c.cgroup.IOStat()
		for majorMinor, mounts := range c.getMounts() {
			dev := disks.GetParentBlockDevice(majorMinor)
			if dev == nil {
				continue
			}
			for mountPoint, fsStat := range mounts {
				dls := []string{mountPoint, dev.Name, c.metadata.volumes[mountPoint]}
				ch <- gauge(metrics.DiskSize, float64(fsStat.CapacityBytes), dls...)
				ch <- gauge(metrics.DiskUsed, float64(fsStat.UsedBytes), dls...)
				ch <- gauge(metrics.DiskReserved, float64(fsStat.ReservedBytes), dls...)
				if io, ok := ioStat[majorMinor]; ok {
					ch <- counter(metrics.DiskReadOps, float64(io.ReadOps), dls...)
					ch <- counter(metrics.DiskReadBytes, float64(io.ReadBytes), dls...)
					ch <- counter(metrics.DiskWriteOps, float64(io.WriteOps), dls...)
					ch <- counter(metrics.DiskWriteBytes, float64(io.WrittenBytes), dls...)
				}
			}
		}
	}

	for addr, open := range c.getListens() {
		ch <- gauge(metrics.NetListenInfo, float64(open), addr.String(), "")
	}
	for proxy, addrs := range c.getProxiedListens() {
		for addr := range addrs {
			ch <- gauge(metrics.NetListenInfo, 1, addr.String(), proxy)
		}
	}

	for d, count := range c.connectsSuccessful {
		ch <- counter(metrics.NetConnectsSuccessful, float64(count), d.src.String(), d.dst.String())
	}
	for dst, count := range c.connectsFailed {
		ch <- counter(metrics.NetConnectsFailed, float64(count), dst.String())
	}
	for d, count := range c.retransmits {
		ch <- counter(metrics.NetRetransmits, float64(count), d.src.String(), d.dst.String())
	}

	connections := map[AddrPair]int{}
	for c, conn := range c.connectionsActive {
		if !conn.Closed.IsZero() {
			continue
		}
		connections[AddrPair{src: c.dst, dst: conn.ActualDest}]++
	}
	for d, count := range connections {
		ch <- gauge(metrics.NetConnectionsActive, float64(count), d.src.String(), d.dst.String())
	}

	for source, p := range c.logParsers {
		for _, c := range p.parser.GetCounters() {
			ch <- counter(metrics.LogMessages, float64(c.Messages), source, c.Level.String(), c.Hash, c.Sample)
		}
	}

	appTypes := map[string]struct{}{}
	seenJvms := map[string]bool{}
	for pid := range c.processes {
		cmdline := proc.GetCmdline(pid)
		if len(cmdline) == 0 {
			continue
		}
		appType := guessApplicationType(cmdline)
		if appType != "" {
			appTypes[appType] = struct{}{}
		}
		if isJvm(cmdline) {
			jvm, jMetrics := jvmMetrics(pid)
			if len(jMetrics) > 0 && !seenJvms[jvm] {
				seenJvms[jvm] = true
				for _, m := range jMetrics {
					ch <- m
				}
			}
		}
	}
	for appType := range appTypes {
		ch <- gauge(metrics.ApplicationType, 1, appType)
	}

	c.l7Stats.collect(ch)

	if !*flags.DisablePinger {
		for ip, rtt := range c.ping() {
			ch <- gauge(metrics.NetLatency, rtt, ip.String())
		}
	}
}
```

coroot-node-agent 暴露了哪些指标？metric.go 代码如下所示：
```Go
package containers

import (
	"github.com/coroot/coroot-node-agent/ebpftracer/l7"
	"github.com/prometheus/client_golang/prometheus"
)

var metrics = struct {
	ContainerInfo *prometheus.Desc
	Restarts      *prometheus.Desc

	CPULimit      *prometheus.Desc
	CPUUsage      *prometheus.Desc
	CPUDelay      *prometheus.Desc
	ThrottledTime *prometheus.Desc

	MemoryLimit *prometheus.Desc
	MemoryRss   *prometheus.Desc
	MemoryCache *prometheus.Desc
	OOMKills    *prometheus.Desc

	DiskDelay      *prometheus.Desc
	DiskSize       *prometheus.Desc
	DiskUsed       *prometheus.Desc
	DiskReserved   *prometheus.Desc
	DiskReadOps    *prometheus.Desc
	DiskReadBytes  *prometheus.Desc
	DiskWriteOps   *prometheus.Desc
	DiskWriteBytes *prometheus.Desc

	NetListenInfo         *prometheus.Desc
	NetConnectsSuccessful *prometheus.Desc
	NetConnectsFailed     *prometheus.Desc
	NetConnectionsActive  *prometheus.Desc
	NetRetransmits        *prometheus.Desc
	NetLatency            *prometheus.Desc

	LogMessages *prometheus.Desc

	ApplicationType *prometheus.Desc

	JvmInfo              *prometheus.Desc
	JvmHeapSize          *prometheus.Desc
	JvmHeapUsed          *prometheus.Desc
	JvmGCTime            *prometheus.Desc
	JvmSafepointTime     *prometheus.Desc
	JvmSafepointSyncTime *prometheus.Desc
}{
	ContainerInfo: metric("container_info", "Meta information about the container", "image"),

	Restarts: metric("container_restarts_total", "Number of times the container was restarted"),

	CPULimit:      metric("container_resources_cpu_limit_cores", "CPU limit of the container"),
	CPUUsage:      metric("container_resources_cpu_usage_seconds_total", "Total CPU time consumed by the container"),
	CPUDelay:      metric("container_resources_cpu_delay_seconds_total", "Total time duration processes of the container have been waiting for a CPU (while being runnable)"),
	ThrottledTime: metric("container_resources_cpu_throttled_seconds_total", "Total time duration the container has been throttled"),

	MemoryLimit: metric("container_resources_memory_limit_bytes", "Memory limit of the container"),
	MemoryRss:   metric("container_resources_memory_rss_bytes", "Amount of physical memory used by the container (doesn't include page cache)"),
	MemoryCache: metric("container_resources_memory_cache_bytes", "Amount of page cache memory allocated by the container"),
	OOMKills:    metric("container_oom_kills_total", "Total number of times the container was terminated by the OOM killer"),

	DiskDelay:      metric("container_resources_disk_delay_seconds_total", "Total time duration processes of the container have been waiting fot I/Os to complete"),
	DiskSize:       metric("container_resources_disk_size_bytes", "Total capacity of the volume", "mount_point", "device", "volume"),
	DiskUsed:       metric("container_resources_disk_used_bytes", "Used capacity of the volume", "mount_point", "device", "volume"),
	DiskReserved:   metric("container_resources_disk_reserved_bytes", "Reserved capacity of the volume", "mount_point", "device", "volume"),
	DiskReadOps:    metric("container_resources_disk_reads_total", "Total number of reads completed successfully by the container", "mount_point", "device", "volume"),
	DiskReadBytes:  metric("container_resources_disk_read_bytes_total", "Total number of bytes read from the disk by the container", "mount_point", "device", "volume"),
	DiskWriteOps:   metric("container_resources_disk_writes_total", "Total number of writes completed successfully by the container", "mount_point", "device", "volume"),
	DiskWriteBytes: metric("container_resources_disk_written_bytes_total", "Total number of bytes written to the disk by the container", "mount_point", "device", "volume"),

	NetListenInfo:         metric("container_net_tcp_listen_info", "Listen address of the container", "listen_addr", "proxy"),
	NetConnectsSuccessful: metric("container_net_tcp_successful_connects_total", "Total number of successful TCP connects", "destination", "actual_destination"),
	NetConnectsFailed:     metric("container_net_tcp_failed_connects_total", "Total number of failed TCP connects", "destination"),
	NetConnectionsActive:  metric("container_net_tcp_active_connections", "Number of active outbound connections used by the container", "destination", "actual_destination"),
	NetRetransmits:        metric("container_net_tcp_retransmits_total", "Total number of retransmitted TCP segments", "destination", "actual_destination"),
	NetLatency:            metric("container_net_latency_seconds", "Round-trip time between the container and a remote IP", "destination_ip"),

	LogMessages: metric("container_log_messages_total", "Number of messages grouped by the automatically extracted repeated pattern", "source", "level", "pattern_hash", "sample"),

	ApplicationType: metric("container_application_type", "Type of the application running in the container (e.g. memcached, postgres, mysql)", "application_type"),

	JvmInfo:              metric("container_jvm_info", "Meta information about the JVM", "jvm", "java_version"),
	JvmHeapSize:          metric("container_jvm_heap_size_bytes", "Total heap size in bytes", "jvm"),
	JvmHeapUsed:          metric("container_jvm_heap_used_bytes", "Used heap size in bytes", "jvm"),
	JvmGCTime:            metric("container_jvm_gc_time_seconds", "Time spent in the given JVM garbage collector in seconds", "jvm", "gc"),
	JvmSafepointTime:     metric("container_jvm_safepoint_time_seconds", "Time the application has been stopped for safepoint operations in seconds", "jvm"),
	JvmSafepointSyncTime: metric("container_jvm_safepoint_sync_time_seconds", "Time spent getting to safepoints in seconds", "jvm"),
}

var (
	L7Requests = map[l7.Protocol]prometheus.CounterOpts{
		l7.ProtocolHTTP:      {Name: "container_http_requests_total", Help: "Total number of outbound HTTP requests"},
		l7.ProtocolPostgres:  {Name: "container_postgres_queries_total", Help: "Total number of outbound Postgres queries"},
		l7.ProtocolRedis:     {Name: "container_redis_queries_total", Help: "Total number of outbound Redis queries"},
		l7.ProtocolMemcached: {Name: "container_memcached_queries_total", Help: "Total number of outbound Memcached queries"},
		l7.ProtocolMysql:     {Name: "container_mysql_queries_total", Help: "Total number of outbound Mysql queries"},
		l7.ProtocolMongo:     {Name: "container_mongo_queries_total", Help: "Total number of outbound Mongo queries"},
		l7.ProtocolKafka:     {Name: "container_kafka_requests_total", Help: "Total number of outbound Kafka requests"},
		l7.ProtocolCassandra: {Name: "container_cassandra_queries_total", Help: "Total number of outbound Cassandra requests"},
		l7.ProtocolRabbitmq:  {Name: "container_rabbitmq_messages_total", Help: "Total number of Rabbitmq messages produced or consumed by the container"},
		l7.ProtocolNats:      {Name: "container_nats_messages_total", Help: "Total number of NATS messages produced or consumed by the container"},
	}
	L7Latency = map[l7.Protocol]prometheus.HistogramOpts{
		l7.ProtocolHTTP:      {Name: "container_http_requests_duration_seconds_total", Help: "Histogram of the response time for each outbound HTTP request"},
		l7.ProtocolPostgres:  {Name: "container_postgres_queries_duration_seconds_total", Help: "Histogram of the execution time for each outbound Postgres query"},
		l7.ProtocolRedis:     {Name: "container_redis_queries_duration_seconds_total", Help: "Histogram of the execution time for each outbound Redis query"},
		l7.ProtocolMemcached: {Name: "container_memcached_queries_duration_seconds_total", Help: "Histogram of the execution time for each outbound Memcached query"},
		l7.ProtocolMysql:     {Name: "container_mysql_queries_duration_seconds_total", Help: "Histogram of the execution time for each outbound Mysql query"},
		l7.ProtocolMongo:     {Name: "container_mongo_queries_duration_seconds_total", Help: "Histogram of the execution time for each outbound Mongo query"},
		l7.ProtocolKafka:     {Name: "container_kafka_requests_duration_seconds_total", Help: "Histogram of the execution time for each outbound Kafka request"},
		l7.ProtocolCassandra: {Name: "container_cassandra_queries_duration_seconds_total", Help: "Histogram of the execution time for each outbound Cassandra request"},
	}
)

func metric(name, help string, labels ...string) *prometheus.Desc {
	return prometheus.NewDesc(name, help, labels, nil)
}
```

ebpftracer.go
```Go
package ebpftracer

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/perf"
	"github.com/coroot/coroot-node-agent/common"
	"github.com/coroot/coroot-node-agent/ebpftracer/l7"
	"github.com/coroot/coroot-node-agent/proc"
	"golang.org/x/mod/semver"
	"golang.org/x/sys/unix"
	"inet.af/netaddr"
	"k8s.io/klog/v2"
	"os"
	"runtime"
	"strconv"
	"strings"
	"time"
)

const MaxPayloadSize = 1024

type EventType uint32
type EventReason uint32

const (
	EventTypeProcessStart    EventType = 1
	EventTypeProcessExit     EventType = 2
	EventTypeConnectionOpen  EventType = 3
	EventTypeConnectionClose EventType = 4
	EventTypeConnectionError EventType = 5
	EventTypeListenOpen      EventType = 6
	EventTypeListenClose     EventType = 7
	EventTypeFileOpen        EventType = 8
	EventTypeTCPRetransmit   EventType = 9
	EventTypeL7Request       EventType = 10

	EventReasonNone    EventReason = 0
	EventReasonOOMKill EventReason = 1
)

type Event struct {
	Type      EventType
	Reason    EventReason
	Pid       uint32
	SrcAddr   netaddr.IPPort
	DstAddr   netaddr.IPPort
	Fd        uint64
	Timestamp uint64
	L7Request *l7.RequestData
}

type Tracer struct {
	kernelVersion    string
	disableL7Tracing bool

	collection *ebpf.Collection
	readers    map[string]*perf.Reader
	links      []link.Link
	uprobes    map[string]*ebpf.Program
}

func NewTracer(kernelVersion string, disableL7Tracing bool) *Tracer {
	if disableL7Tracing {
		klog.Infoln("L7 tracing is disabled")
	}
	return &Tracer{
		kernelVersion:    kernelVersion,
		disableL7Tracing: disableL7Tracing,

		readers: map[string]*perf.Reader{},
		uprobes: map[string]*ebpf.Program{},
	}
}

func (t *Tracer) Run(events chan<- Event) error {
	if err := t.ebpf(events); err != nil {
		return err
	}
	if err := t.init(events); err != nil {
		return err
	}
	return nil
}

func (t *Tracer) Close() {
	for _, p := range t.uprobes {
		_ = p.Close()
	}
	for _, l := range t.links {
		_ = l.Close()
	}
	for _, r := range t.readers {
		_ = r.Close()
	}
	t.collection.Close()
}

func (t *Tracer) init(ch chan<- Event) error {
	pids, err := proc.ListPids()
	if err != nil {
		return fmt.Errorf("failed to list pids: %w", err)
	}
	for _, pid := range pids {
		ch <- Event{Type: EventTypeProcessStart, Pid: pid}
	}

	fds, sockets := readFds(pids)
	for _, fd := range fds {
		ch <- Event{Type: EventTypeFileOpen, Pid: fd.pid, Fd: fd.fd}
	}

	listens := map[uint64]bool{}
	for _, s := range sockets {
		if s.Listen {
			listens[uint64(s.pid)<<32|uint64(s.SAddr.Port())] = true
		}
	}

	for _, s := range sockets {
		typ := EventTypeConnectionOpen
		if s.Listen {
			typ = EventTypeListenOpen
		} else if listens[uint64(s.pid)<<32|uint64(s.SAddr.Port())] || s.DAddr.Port() > s.SAddr.Port() { // inbound
			continue
		}
		ch <- Event{
			Type:    typ,
			Pid:     s.pid,
			Fd:      s.fd,
			SrcAddr: s.SAddr,
			DstAddr: s.DAddr,
		}
	}
	return nil
}

type perfMap struct {
	name                  string
	perCPUBufferSizePages int
	event                 rawEvent
}

func (t *Tracer) ebpf(ch chan<- Event) error {
	if _, ok := ebpfProg[runtime.GOARCH]; !ok {
		return fmt.Errorf("unsupported architecture: %s", runtime.GOARCH)
	}
	kv := "v" + common.KernelMajorMinor(t.kernelVersion)
	var prg []byte
	for _, p := range ebpfProg[runtime.GOARCH] {
		if semver.Compare(kv, p.v) >= 0 {
			prg = p.p
			break
		}
	}
	if len(prg) == 0 {
		return fmt.Errorf("unsupported kernel version: %s", t.kernelVersion)
	}

	if _, err := os.Stat("/sys/kernel/debug/tracing"); err != nil {
		return fmt.Errorf("kernel tracing is not available: %w", err)
	}

	collectionSpec, err := ebpf.LoadCollectionSpecFromReader(bytes.NewReader(prg))
	if err != nil {
		return fmt.Errorf("failed to load collection spec: %w", err)
	}
	_ = unix.Setrlimit(unix.RLIMIT_MEMLOCK, &unix.Rlimit{Cur: unix.RLIM_INFINITY, Max: unix.RLIM_INFINITY})
	c, err := ebpf.NewCollectionWithOptions(collectionSpec, ebpf.CollectionOptions{
		//Programs: ebpf.ProgramOptions{LogLevel: 2, LogSize: 20 * 1024 * 1024},
	})
	if err != nil {
		var verr *ebpf.VerifierError
		if errors.As(err, &verr) {
			klog.Errorf("%+v", verr)
		}
		return fmt.Errorf("failed to load collection: %w", err)
	}
	t.collection = c

    // 核心部分，name 的值对应于 C 代码中的 map 名称，可见下述示例中的 C 代码
	perfMaps := []perfMap{
		{name: "proc_events", event: &procEvent{}, perCPUBufferSizePages: 4},
		{name: "tcp_listen_events", event: &tcpEvent{}, perCPUBufferSizePages: 4},
		{name: "tcp_connect_events", event: &tcpEvent{}, perCPUBufferSizePages: 8},
		{name: "tcp_retransmit_events", event: &tcpEvent{}, perCPUBufferSizePages: 4},
		{name: "file_events", event: &fileEvent{}, perCPUBufferSizePages: 4},
	}

	if !t.disableL7Tracing {
		perfMaps = append(perfMaps, perfMap{name: "l7_events", event: &l7Event{}, perCPUBufferSizePages: 32})
	}

	for _, pm := range perfMaps {
		r, err := perf.NewReader(t.collection.Maps[pm.name], pm.perCPUBufferSizePages*os.Getpagesize())
		if err != nil {
			t.Close()
			return fmt.Errorf("failed to create ebpf reader: %w", err)
		}
		t.readers[pm.name] = r
		go runEventsReader(pm.name, r, ch, pm.event)
	}

	for _, programSpec := range collectionSpec.Programs {
		program := t.collection.Programs[programSpec.Name]
		if t.disableL7Tracing {
			switch programSpec.Name {
			case "sys_enter_writev", "sys_enter_write", "sys_enter_sendto", "sys_enter_sendmsg":
				continue
			case "sys_enter_read", "sys_enter_readv", "sys_enter_recvfrom", "sys_enter_recvmsg":
				continue
			case "sys_exit_read", "sys_exit_readv", "sys_exit_recvfrom", "sys_exit_recvmsg":
				continue
			}
		}
		var l link.Link
		switch programSpec.Type {
		case ebpf.TracePoint:
			parts := strings.SplitN(programSpec.AttachTo, "/", 2)
			l, err = link.Tracepoint(parts[0], parts[1], program, nil)
		case ebpf.Kprobe:
			if strings.HasPrefix(programSpec.SectionName, "uprobe/") {
				t.uprobes[programSpec.Name] = program
				continue
			}
			l, err = link.Kprobe(programSpec.AttachTo, program, nil)
		}
		if err != nil {
			t.Close()
			return fmt.Errorf("failed to link program: %w", err)
		}
		t.links = append(t.links, l)
	}

	return nil
}

func (t EventType) String() string {
	switch t {
	case EventTypeProcessStart:
		return "process-start"
	case EventTypeProcessExit:
		return "process-exit"
	case EventTypeConnectionOpen:
		return "connection-open"
	case EventTypeConnectionClose:
		return "connection-close"
	case EventTypeConnectionError:
		return "connection-error"
	case EventTypeListenOpen:
		return "listen-open"
	case EventTypeListenClose:
		return "listen-close"
	case EventTypeFileOpen:
		return "file-open"
	case EventTypeTCPRetransmit:
		return "tcp-retransmit"
	case EventTypeL7Request:
		return "l7-request"
	}
	return "unknown: " + strconv.Itoa(int(t))
}

func (t EventReason) String() string {
	switch t {
	case EventReasonNone:
		return "none"
	case EventReasonOOMKill:
		return "oom-kill"
	}
	return "unknown: " + strconv.Itoa(int(t))
}

type rawEvent interface {
	Event() Event
}

type procEvent struct {
	Type   uint32
	Pid    uint32
	Reason uint32
}

func (e procEvent) Event() Event {
	return Event{Type: EventType(e.Type), Reason: EventReason(e.Reason), Pid: e.Pid}
}

type tcpEvent struct {
	Fd        uint64
	Timestamp uint64
	Type      uint32
	Pid       uint32
	SPort     uint16
	DPort     uint16
	SAddr     [16]byte
	DAddr     [16]byte
}

func (e tcpEvent) Event() Event {
	return Event{
		Type:      EventType(e.Type),
		Pid:       e.Pid,
		SrcAddr:   ipPort(e.SAddr, e.SPort),
		DstAddr:   ipPort(e.DAddr, e.DPort),
		Fd:        e.Fd,
		Timestamp: e.Timestamp,
	}
}

type fileEvent struct {
	Type uint32
	Pid  uint32
	Fd   uint64
}

func (e fileEvent) Event() Event {
	return Event{Type: EventType(e.Type), Pid: e.Pid, Fd: e.Fd}
}

type l7Event struct {
	Fd                  uint64
	ConnectionTimestamp uint64
	Pid                 uint32
	Status              uint32
	Duration            uint64
	Protocol            uint8
	Method              uint8
	Padding             uint16
	StatementId         uint32
	PayloadSize         uint64
	Payload             [MaxPayloadSize]byte
}

func (e l7Event) Event() Event {
	r := &l7.RequestData{
		Protocol:    l7.Protocol(e.Protocol),
		Status:      l7.Status(e.Status),
		Duration:    time.Duration(e.Duration),
		Method:      l7.Method(e.Method),
		StatementId: e.StatementId,
	}
	switch {
	case e.PayloadSize == 0:
	case e.PayloadSize > MaxPayloadSize:
		r.Payload = e.Payload[:MaxPayloadSize]
	default:
		r.Payload = e.Payload[:e.PayloadSize]
	}
	return Event{Type: EventTypeL7Request, Pid: e.Pid, Fd: e.Fd, Timestamp: e.ConnectionTimestamp, L7Request: r}
}

func runEventsReader(name string, r *perf.Reader, ch chan<- Event, e rawEvent) {
	for {
		rec, err := r.Read()
		if err != nil {
			if errors.Is(err, perf.ErrClosed) {
				break
			}
			continue
		}
		if rec.LostSamples > 0 {
			klog.Errorln(name, "lost samples:", rec.LostSamples)
			continue
		}
		if err := binary.Read(bytes.NewBuffer(rec.RawSample), binary.LittleEndian, e); err != nil {
			klog.Warningln("failed to read msg:", err)
			continue
		}
		ch <- e.Event()
	}
}

func ipPort(ip [16]byte, port uint16) netaddr.IPPort {
	i, _ := netaddr.FromStdIP(ip[:])
	return netaddr.IPPortFrom(i, port)
}

```

retransmit.c 重传代码如下所示：
```C
struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(key_size, sizeof(int));
    __uint(value_size, sizeof(int));
} tcp_retransmit_events SEC(".maps");

struct trace_event_raw_tcp_event_sk_skb__stub {
    __u64 unused;
    void *sbkaddr;
    void *skaddr;
#if __KERNEL_FROM >= 420
    int state;
#endif
    __u16 sport;
    __u16 dport;
#if __KERNEL_FROM >= 512
    __u16 family;
#endif
    __u8 saddr[4];
    __u8 daddr[4];
    __u8 saddr_v6[16];
    __u8 daddr_v6[16];
};

SEC("tracepoint/tcp/tcp_retransmit_skb")
int tcp_retransmit_skb(struct trace_event_raw_tcp_event_sk_skb__stub *args)
{
    struct tcp_event e = {
        .type = EVENT_TYPE_TCP_RETRANSMIT,
        .sport = args->sport,
        .dport = args->dport,
    };
    __builtin_memcpy(&e.saddr, &args->saddr_v6, sizeof(e.saddr));
    __builtin_memcpy(&e.daddr, &args->daddr_v6, sizeof(e.daddr));

    bpf_perf_event_output(args, &tcp_retransmit_events, BPF_F_CURRENT_CPU, &e, sizeof(e));

    return 0;
}
```

# 参考

1. https://github.com/coroot/coroot
