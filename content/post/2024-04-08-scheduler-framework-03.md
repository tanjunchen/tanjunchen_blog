---
layout:     post
title:      "深入理解 Kubernetes Scheduler Framework 调度框架（Part 3）"
subtitle:   "基于 Scheduler Framework 进行插件拓展的案例"
description: ""
author: "陈谭军"
date: 2024-04-08
published: true
tags:
    - kubernetes
    - Scheduler Framework
categories:
    - TECHNOLOGY
showtoc: true
---

Scheduler 分两个 cycle：Scheduling Cycle 和 Binding Cycle。在 Scheduling Cycle 中为了提升效率的一个重要原则就是 Pod、 Node 等信息从本地缓存中获取，而具体的实现原理就是先使用 list 获取所有 Node、Pod 的信息，然后再 watch 他们的变化更新本地缓存。在 Bind Cycle 中，会有两次外部 api 调用：调用 pv controller 绑定 pv 和调用 kube-apiserver 绑定 Node，api 调用是耗时的，所以将 bind 扩展点拆分出来，另起一个 go 协程进行 bind。调度周期是串行，绑定周期是并行的。本文主要介绍基于 Scheduler Framework 进行插件拓展的案例。

[深入理解 Kubernetes Scheduler Framework 调度框架（Part 4）](https://tanjunchen.github.io/post/2024-04-09-scheduler-framework-04/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 3）](https://tanjunchen.github.io/post/2024-04-08-scheduler-framework-03/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 2）](https://tanjunchen.github.io/post/2024-04-07-scheduler-framework-02/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 1）](https://tanjunchen.github.io/post/2024-04-06-scheduler-framework-01/) 

# 自定义拓展点

Framework 是一个接口，里面定义了一系列方法。frameworkImpl 的成员主要是各个扩展点插件数组，用来存放该扩展点插件。
frameworkImpl 实现 Framework 这个接口，可以通过 RunxxPlugins() 这样的方法来执行 frameworkImpl 中的插件。
```go
// frameworkImpl is the component responsible for initializing and running scheduler
// plugins.
type frameworkImpl struct {
	registry             Registry
	snapshotSharedLister framework.SharedLister
	waitingPods          *waitingPodsMap
	scorePluginWeight    map[string]int
	preEnqueuePlugins    []framework.PreEnqueuePlugin
	enqueueExtensions    []framework.EnqueueExtensions
	queueSortPlugins     []framework.QueueSortPlugin
	preFilterPlugins     []framework.PreFilterPlugin
	filterPlugins        []framework.FilterPlugin
	postFilterPlugins    []framework.PostFilterPlugin
	preScorePlugins      []framework.PreScorePlugin
	scorePlugins         []framework.ScorePlugin
	reservePlugins       []framework.ReservePlugin
	preBindPlugins       []framework.PreBindPlugin
	bindPlugins          []framework.BindPlugin
	postBindPlugins      []framework.PostBindPlugin
	permitPlugins        []framework.PermitPlugin

	// pluginsMap contains all plugins, by name.
	pluginsMap map[string]framework.Plugin

	clientSet       clientset.Interface
	kubeConfig      *restclient.Config
	eventRecorder   events.EventRecorder
	informerFactory informers.SharedInformerFactory
	logger          klog.Logger

	metricsRecorder          *metrics.MetricAsyncRecorder
	profileName              string
	percentageOfNodesToScore *int32

	extenders []framework.Extender
	framework.PodNominator

	parallelizer parallelize.Parallelizer
}
```

看下 ScorePlugin 拓展点数组类型，如以下代码，要实现一个 ScorePlugin 扩展点插件，只需要实现 Score、Name、ScoreExtensions 方法即可，其他插件类似。
```go
// Plugin is the parent type for all the scheduling framework plugins.
type Plugin interface {
	Name() string
}

// ScorePlugin is an interface that must be implemented by "Score" plugins to rank
// nodes that passed the filtering phase.
type ScorePlugin interface {
	Plugin
	// Score is called on each filtered node. It must return success and an integer
	// indicating the rank of the node. All scoring plugins must return success or
	// the pod will be rejected.
	Score(ctx context.Context, state *CycleState, p *v1.Pod, nodeName string) (int64, *Status)

	// ScoreExtensions returns a ScoreExtensions interface if it implements one, or nil if does not.
	ScoreExtensions() ScoreExtensions
}
```

# Registry 注册

Registry 是一个 map: key 是插件的名称，value 是 PluginFactory 类型的函数，这个函数返回 framework.Plugin。
这个 Plugin 就是上面说接口，实现这个接口的对象就可以作为插件被调用。所以 PluginFactory 的作用就是新建一个 Plugin 类型的对象。
```go
// pkg/scheduler/apis/config/types.go#L192
// Plugin specifies a plugin name and its weight when applicable. Weight is used only for Score plugins.
type Plugin struct {
	// Name defines the name of plugin
	Name string
	// Weight defines the weight of plugin, only used for Score plugins.
	Weight int32
}

// PluginFactory is a function that builds a plugin.
type PluginFactory = func(ctx context.Context, configuration runtime.Object, f framework.Handle) (framework.Plugin, error)

// PluginFactoryWithFts is a function that builds a plugin with certain feature gates.
type PluginFactoryWithFts func(context.Context, runtime.Object, framework.Handle, plfeature.Features) (framework.Plugin, error)
```

Scheduler 启动前会遍历这个 map，执行这个 map 的 value 代表的函数，将函数返回值写入 frameworkImpl 对应的扩展点数组。
执行某个扩展点插件流程：遍历 frameworkImpl 中这个扩展点数组的所有对象，执行它即可。
内置插件的注册叫 InTreeRegistry, 用户自定义插件的注册叫 OutOfTreeRegistry。
```go
// New returns a Scheduler
func New(ctx context.Context,
	client clientset.Interface,
	informerFactory informers.SharedInformerFactory,
	dynInformerFactory dynamicinformer.DynamicSharedInformerFactory,
	recorderFactory profile.RecorderFactory,
	opts ...Option) (*Scheduler, error) {
    ......
    // 内置插件
    registry := frameworkplugins.NewInTreeRegistry()
    
    // 合并用户自定义插件
	if err := registry.Merge(options.frameworkOutOfTreeRegistry); err != nil {
		return nil, err
	}
    ......
}

/ Registry is a collection of all available plugins. The framework uses a
// registry to enable and initialize configured plugins.
// All plugins must be in the registry before initializing the framework.
type Registry map[string]PluginFactory

// Register adds a new plugin to the registry. If a plugin with the same name
// exists, it returns an error.
func (r Registry) Register(name string, factory PluginFactory) error {
	if _, ok := r[name]; ok {
		return fmt.Errorf("a plugin named %v already exists", name)
	}
	r[name] = factory
	return nil
}

// Unregister removes an existing plugin from the registry. If no plugin with
// the provided name exists, it returns an error.
func (r Registry) Unregister(name string) error {
	if _, ok := r[name]; !ok {
		return fmt.Errorf("no plugin named %v exists", name)
	}
	delete(r, name)
	return nil
}

// Merge merges the provided registry to the current one.
func (r Registry) Merge(in Registry) error {
	for name, factory := range in {
		if err := r.Register(name, factory); err != nil {
			return err
		}
	}
	return nil
}

// NewInTreeRegistry builds the registry with all the in-tree plugins.
// A scheduler that runs out of tree plugins can register additional plugins
// through the WithFrameworkOutOfTreeRegistry option.
func NewInTreeRegistry() runtime.Registry {
	fts := plfeature.Features{
		EnableDynamicResourceAllocation:              feature.DefaultFeatureGate.Enabled(features.DynamicResourceAllocation),
		EnableVolumeCapacityPriority:                 feature.DefaultFeatureGate.Enabled(features.VolumeCapacityPriority),
		EnableNodeInclusionPolicyInPodTopologySpread: feature.DefaultFeatureGate.Enabled(features.NodeInclusionPolicyInPodTopologySpread),
		EnableMatchLabelKeysInPodTopologySpread:      feature.DefaultFeatureGate.Enabled(features.MatchLabelKeysInPodTopologySpread),
		EnablePodDisruptionConditions:                feature.DefaultFeatureGate.Enabled(features.PodDisruptionConditions),
		EnableInPlacePodVerticalScaling:              feature.DefaultFeatureGate.Enabled(features.InPlacePodVerticalScaling),
		EnableSidecarContainers:                      feature.DefaultFeatureGate.Enabled(features.SidecarContainers),
	}

	registry := runtime.Registry{
		dynamicresources.Name:                runtime.FactoryAdapter(fts, dynamicresources.New),
		imagelocality.Name:                   imagelocality.New,
		tainttoleration.Name:                 tainttoleration.New,
		nodename.Name:                        nodename.New,
		nodeports.Name:                       nodeports.New,
		nodeaffinity.Name:                    nodeaffinity.New,
		podtopologyspread.Name:               runtime.FactoryAdapter(fts, podtopologyspread.New),
		nodeunschedulable.Name:               nodeunschedulable.New,
		noderesources.Name:                   runtime.FactoryAdapter(fts, noderesources.NewFit),
		noderesources.BalancedAllocationName: runtime.FactoryAdapter(fts, noderesources.NewBalancedAllocation),
		volumebinding.Name:                   runtime.FactoryAdapter(fts, volumebinding.New),
		volumerestrictions.Name:              runtime.FactoryAdapter(fts, volumerestrictions.New),
		volumezone.Name:                      volumezone.New,
		nodevolumelimits.CSIName:             runtime.FactoryAdapter(fts, nodevolumelimits.NewCSI),
		nodevolumelimits.EBSName:             runtime.FactoryAdapter(fts, nodevolumelimits.NewEBS),
		nodevolumelimits.GCEPDName:           runtime.FactoryAdapter(fts, nodevolumelimits.NewGCEPD),
		nodevolumelimits.AzureDiskName:       runtime.FactoryAdapter(fts, nodevolumelimits.NewAzureDisk),
		nodevolumelimits.CinderName:          runtime.FactoryAdapter(fts, nodevolumelimits.NewCinder),
		interpodaffinity.Name:                interpodaffinity.New,
		queuesort.Name:                       queuesort.New,
		defaultbinder.Name:                   defaultbinder.New,
		defaultpreemption.Name:               runtime.FactoryAdapter(fts, defaultpreemption.New),
		schedulinggates.Name:                 schedulinggates.New,
	}

	return registry
}
```

函数 NewInTreeRegistry 返回一个 registry，这个 registry 包含了所有内置插件对象的创建方法。
Merge 函数将 NewInTreeRegistry 返回的 registry 和 options.frameworkOutOfTreeRegistry 合并。
其中 registry.Merge(options.frameworkOutOfTreeRegistry) 表示的是 Registry 自定义插件。

```go
// PluginFactory is a function that builds a plugin.
type PluginFactory = func(ctx context.Context, configuration runtime.Object, f framework.Handle) (framework.Plugin, error)

// Registry is a collection of all available plugins. The framework uses a
// registry to enable and initialize configured plugins.
// All plugins must be in the registry before initializing the framework.
type Registry map[string]PluginFactory
```

pkg/scheduler/scheduler.go 中的 frameworkOutOfTreeRegistry() 是通过 cmd/kube-scheduler/app/server.go 中的 NewSchedulerCommand 函数的入参进行初始化的。
```go
// NewSchedulerCommand creates a *cobra.Command object with default parameters and registryOptions
func NewSchedulerCommand(registryOptions ...Option) *cobra.Command {
	opts := options.NewOptions()
    cmd := &cobra.Command{
		Use: "kube-scheduler",
        ......
		RunE: func(cmd *cobra.Command, args []string) error {
			return runCommand(cmd, opts, registryOptions...)
		},
		Args: func(cmd *cobra.Command, args []string) error {
			for _, arg := range args {
				if len(arg) > 0 {
					return fmt.Errorf("%q does not take any arguments, got %q", cmd.CommandPath(), args)
				}
			}
			return nil
		},
	}
    ......       
}

// runCommand runs the scheduler.
func runCommand(cmd *cobra.Command, opts *options.Options, registryOptions ...Option) error {
    ......
	cc, sched, err := Setup(ctx, opts, registryOptions...)
	if err != nil {
		return err
	}
    ......
}

func Setup(ctx context.Context, opts *options.Options, outOfTreeRegistryOptions ...Option) (*schedulerserverconfig.CompletedConfig, *scheduler.Scheduler, error) {
    outOfTreeRegistry := make(runtime.Registry)
    for _, option := range outOfTreeRegistryOptions {
        if err := option(outOfTreeRegistry); err != nil {
            return nil, nil, err
        }
    }
    ......
}
    
// WithFrameworkOutOfTreeRegistry sets the registry for out-of-tree plugins. Those plugins
// will be appended to the default registry.
func WithFrameworkOutOfTreeRegistry(registry frameworkruntime.Registry) Option {
    return func(o *schedulerOptions) {
        o.frameworkOutOfTreeRegistry = registry
    }
}
```

我们有两种方式可以拓展原生 Scheduler Framework，in-tree（直接修改源码）、out-of-tree（外置调度算法）。

# in-tree 自定义插件

在 k8s 代码目录 pkg/scheduler/framework/plugins 中， 跟内置调度器一起编译。
```bash
➜  kubernetes git:(v1.26.9-filter) ✗ ls pkg/scheduler/framework/plugins
defaultbinder
defaultpreemption
imagelocality
interpodaffinity
legacy_registry
nodeaffinity
nodelabel
nodename
nodeports
nodepreferavoidpods
noderesources
nodeunschedulable
nodevolumelimits
podtopologyspread
queuesort
selectorspread
serviceaffinity
tainttoleration
volumebinding
volumerestrictions
volumezone
```

默认启用的插件实现了这些扩展点中的一个或多个:
* ImageLocality: 优先考虑已经拥有 Pod 运行的容器镜像的节点；扩展点：score。
* TaintToleration: 实现污点和容忍；实现扩展点：filter, preScore, score。
* NodeName: 检查Pod规格节点名称是否与当前节点匹配；扩展点：filter。
* NodePorts: 检查节点是否有Pod请求的端口的空闲端口；扩展点：preFilter, filter。
* NodeAffinity: 实现节点选择器和节点亲和性；扩展点：filter, score。
* PodTopologySpread: 实现Pod拓扑扩展；扩展点：preFilter, filter, preScore, score。
* NodeUnschedulable: 过滤出spec.unschedulable设置为true的节点；扩展点：filter。
* NodeResourcesFit: 检查节点是否具有Pod请求的所有资源；得分可以使用三种策略之一：LeastAllocated（默认）、MostAllocated和RequestedToCapacityRatio；扩展点：preFilter, filter, score。
* NodeResourcesBalancedAllocation: 偏向于如果Pod在那里调度，将获得更平衡资源使用的节点；扩展点：score。
* VolumeBinding: 检查节点是否有或是否可以绑定请求的卷；扩展点：preFilter, filter, reserve, preBind, score。
* VolumeRestrictions: 检查节点中安装的卷是否满足特定于卷提供程序的限制；扩展点：filter。
* VolumeZone: 检查请求的卷是否满足它们可能具有的任何区域需求；扩展点：filter。
* NodeVolumeLimits: 检查节点是否可以满足CSI卷限制；扩展点：filter。
* EBSLimits: 检查节点是否可以满足AWS EBS卷限制；扩展点：filter。
* GCEPDLimits: 检查节点是否可以满足GCP-PD卷限制；扩展点：filter。
* AzureDiskLimits: 检查节点是否可以满足Azure磁盘卷限制；扩展点：filter。
* InterPodAffinity: 实现Pod间的亲和性和反亲和性；扩展点：preFilter, filter, preScore, score。
* PrioritySort: 提供默认的基于优先级的排序；扩展点：queueSort。
* DefaultBinder: 提供默认的绑定机制；扩展点：bind。
* DefaultPreemption: 提供默认的抢占机制；扩展点：postFilter。

总结：in-tree 方式每次要添加新插件，或者修改原有插件，都需要修改 kube-scheduler 代码然后编译和重新部署 kube-scheduler，比较重量级。接下来，我们以 in-tree 的方式实现一个自定义插件，实现 Filter 扩展点。

1、克隆 Kubernetes Scheduler 源码
```bash
git clone https://github.com/kubernetes/kubernetes.git -b v1.26.9
```

2、然后进入 plugins 目录下创建自己的插件
```bash
cd kubernetes/pkg/scheduler/framework/plugins
mkdir nodefilter
cd nodefilter
touch nodefilter.go
```

Filter 插件就是要过滤掉那些不符合 Pod 的 Node，留下符合的 Node，Filer 方法就是通过返回值 Status 来标识某个 Node 是否通过了这个插件的过滤，只要插件返回 nil 就表示 Node 通过了这个插件的过滤。如果 Node 无法通过这个插件的过滤，插件可以调用 framework.NewStatus 方法返回过滤失败详情。

3、实现 nodefilter 插件
```go
package nodefilter

import (
	"context"
	"fmt"

	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/klog/v2"
	"k8s.io/kubernetes/pkg/scheduler/framework"
)

const Name = "nodeFilter"

// 定义这个插件的结构体
type NodeFilter struct{}

// 实现 Name 方法
func (nodeFilter *NodeFilter) Name() string {
	return Name
}

// 实现 Filter 方法
func (nodeFilter *NodeFilter) Filter(ctx context.Context, _ *framework.CycleState, pod *v1.Pod, nodeInfo *framework.NodeInfo) *framework.Status {
	cpu := nodeInfo.Allocatable.MilliCPU
	memory := nodeInfo.Allocatable.Memory
	fmt.Println("====nodeFilter filter===")
	klog.InfoS("nodeFilter filter", "pod_name", pod.Name, "current node", nodeInfo.Node().Name, "cpu", cpu, "memory", memory)
	return nil
}

// 编写 New 函数
func New(_ runtime.Object, _ framework.Handle) (framework.Plugin, error) {
	return &NodeFilter{}, nil
}
```
* 定义插件的结构体，实现插件需要实现的方法；
* 实现 Name 方法；
* 实现 Filter 方法，打印 Node  的 CPU 与内存资源；
* 编写 New 函数，这个函数会初始化的时候被注册在 framework 中，告诉 framework 怎么创建这个插件对象；

4、在 main 函数中传递定义的插件的 nodefilter New 函数

使用 app.WithPlugin 方法返回一个 Option 类型的对象，Option 类型正好是 NewSchedulerCommand 方法的参数类型，这样就传递了自定义的插件对象新建方法。在后续初始化 scheduler 的过程中，这个 New 方法会被调用， New 返回的结果存放在 frameworkImpl 对象的 Filter 扩展点插件数组中，以便后续遍历 Filter 扩展点插件数组时调用插件对象上的 Filter 方法。在 Kubernetes Scheduler（cmd/kube-scheduler/scheduler.go）启动时添加自定义插件。
```go
package main

import (
	"os"

	"k8s.io/component-base/cli"
	_ "k8s.io/component-base/logs/json/register" // for JSON log format registration
	_ "k8s.io/component-base/metrics/prometheus/clientgo"
	_ "k8s.io/component-base/metrics/prometheus/version" // for version metric registration
	"k8s.io/kubernetes/cmd/kube-scheduler/app"
	"k8s.io/kubernetes/pkg/scheduler/framework/plugins/nodefilter"
)

func main() {
	// 自定义插件
	myPlugin := app.WithPlugin(nodefilter.Name, nodefilter.New)
	command := app.NewSchedulerCommand(myPlugin)
	code := cli.Run(command)
	os.Exit(code)
}
```

5、在 Kubernetes root 根目录下重新编译Kubernetes Scheduler 调度器。
```bash
// 镜像
root@instance-820epr0w:~/tanjunchen/kubernetes# make clean
root@instance-820epr0w:~/tanjunchen/kubernetes# KUBE_DOCKER_REGISTRY=docker.io/tanjunchen  KUBE_BUILD_PLATFORMS=linux/amd64 KUBE_BUILD_CONFORMANCE=n KUBE_BUILD_HYPERKUBE=n make  WHAT=cmd/kube-scheduler release-images GOFLAGS=-v GOGCFLAGS="-N -l"

// 在 /root/tanjunchen/kubernetes/_output/release-images/amd64 目录下存在以下文件
root@instance-820epr0w:~/tanjunchen/kubernetes/_output/release-images/amd64# ls
kube-apiserver.tar  kube-controller-manager.tar  kube-proxy.tar  kube-scheduler.tar

root@instance-820epr0w:~/tanjunchen/kubernetes/_output/release-images/amd64# docker load -i kube-scheduler.tar 
Loaded image: k8s.gcr.io/kube-scheduler-amd64:v1.26.9-filter
Loaded image: docker.io/tanjunchen/kube-scheduler-amd64:v1.26.9-filter

// 二进制
root@instance-820epr0w:~/tanjunchen/kubernetes# KUBE_BUILD_PLATFORMS=linux/amd64 make WHAT=cmd/kube-apiserver  quick-release
root@instance-820epr0w:~/tanjunchen/kubernetes# KUBE_BUILD_PLATFORMS=linux/amd64 make WHAT=cmd/kube-apiserver GOFLAGS=-v GOGCFLAGS="-N -l"
```

6、在配置文件中添加我们的自定义插件，kube-scheduler 启动命令配置文件路径，如下所示：
```yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
clientConnection:
  acceptContentTypes: ""
  burst: 100
  contentType: application/vnd.kubernetes.protobuf
  kubeconfig: /etc/kubernetes/scheduler.conf
  qps: 100
profiles:
- schedulerName: my-scheduler
  plugins:
    filter:
      enabled:
      - name: nodeFilter
```

更改 Kubernetes Scheduler 静态 Static Pod 部署 kube-scheduler yaml 文件，如下所示：
```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    scheduler.alpha.kubernetes.io/critical-pod: ""
  creationTimestamp: null
  labels:
    component: kube-scheduler
    tier: control-plane
  name: kube-scheduler
  namespace: kube-system
spec:
  containers:
    - command:
        - kube-scheduler
        - --master=https://192.168.0.198:6443
        - --feature-gates=MixedProtocolLBService=true
        - --kubeconfig=/etc/kubernetes/scheduler.conf
        - --authorization-always-allow-paths=/metrics,/healthz,/readyz,/livez
        - --leader-elect=true
        - --kube-api-qps=100
        - --kube-api-burst=100
        - --bind-address=0.0.0.0
        - --profiling
        - --v=2
        #增加的配置文件
        - --config=/etc/kubernetes/scheduler_config.yaml
      image: docker.io/tanjunchen/kube-scheduler-amd64:v1.26.9-scheduler
      imagePullPolicy: Always
      name: kube-scheduler
      volumeMounts:
        - mountPath: /etc/kubernetes
          name: kubernetes
        - mountPath: /etc/localtime
          name: localtime
  hostNetwork: true
  priorityClassName: system-cluster-critical
  volumes:
    - hostPath:
        path: /etc/kubernetes
        type: DirectoryOrCreate
      name: kubernetes
    - hostPath:
        path: /etc/localtime
        type: File
      name: localtime
```

7、部署测试示例 nginx
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      schedulerName: my-scheduler
      containers:
        - name: nginx
          image: nginx:1.17.3
          ports:
            - containerPort: 80
```

8、查看 scheduler 调度日志，终端打印了我们插件中编写的代码逻辑。
```bash
➜  ~ kubectl -n kube-system logs -f kube-scheduler-192.168.0.198
W0415 19:07:28.009796       1 feature_gate.go:241] Setting GA feature gate MixedProtocolLBService=true. It will be removed in a future release. 
I0415 19:07:28.010048       1 flags.go:64] FLAG: --allow-metric-labels="[]"
I0415 19:07:28.010071       1 flags.go:64] FLAG: --authentication-kubeconfig=""
I0415 19:07:28.010121       1 flags.go:64] FLAG: --authentication-skip-lookup="false"
I0415 19:07:28.010129       1 flags.go:64] FLAG: --authentication-token-webhook-cache-ttl="10s"
I0415 19:07:28.010166       1 flags.go:64] FLAG: --authentication-tolerate-lookup-failure="true"
I0415 19:07:28.010208       1 flags.go:64] FLAG: --authorization-always-allow-paths="[/metrics,/healthz,/readyz,/livez]"
I0415 19:07:28.010239       1 flags.go:64] FLAG: --authorization-kubeconfig=""
I0415 19:07:28.010278       1 flags.go:64] FLAG: --authorization-webhook-cache-authorized-ttl="10s"
I0415 19:07:28.010303       1 flags.go:64] FLAG: --authorization-webhook-cache-unauthorized-ttl="10s"
I0415 19:07:28.010329       1 flags.go:64] FLAG: --bind-address="0.0.0.0"
I0415 19:07:28.010362       1 flags.go:64] FLAG: --cert-dir=""
I0415 19:07:28.010390       1 flags.go:64] FLAG: --client-ca-file=""
I0415 19:07:28.010413       1 flags.go:64] FLAG: --config="/etc/kubernetes/scheduler_config.yaml"
......
W0415 19:07:29.246961       1 authorization.go:226] failed to read in-cluster kubeconfig for delegated authorization: open /var/run/secrets/kubernetes.io/serviceaccount/token: no such file or directory
W0415 19:07:29.246975       1 authorization.go:194] No authorization-kubeconfig provided, so SubjectAccessReview of authorization tokens won't work.
I0415 19:07:29.265066       1 configfile.go:105] "Using component config" config=<
	apiVersion: kubescheduler.config.k8s.io/v1
	clientConnection:
	  acceptContentTypes: ""
	  burst: 100
	  contentType: application/vnd.kubernetes.protobuf
	  kubeconfig: /etc/kubernetes/scheduler.conf
	  qps: 100
	enableContentionProfiling: true
	enableProfiling: true
	kind: KubeSchedulerConfiguration
	leaderElection:
	  leaderElect: true
	  leaseDuration: 15s
	  renewDeadline: 10s
	  resourceLock: leases
	  resourceName: kube-scheduler
	  resourceNamespace: kube-system
	  retryPeriod: 2s
	parallelism: 16
	percentageOfNodesToScore: 0
	podInitialBackoffSeconds: 1
	podMaxBackoffSeconds: 10
	profiles:
	- pluginConfig:
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: DefaultPreemptionArgs
	      minCandidateNodesAbsolute: 100
	      minCandidateNodesPercentage: 10
	    name: DefaultPreemption
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      hardPodAffinityWeight: 1
	      kind: InterPodAffinityArgs
	    name: InterPodAffinity
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeAffinityArgs
	    name: NodeAffinity
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeResourcesBalancedAllocationArgs
	      resources:
	      - name: cpu
	        weight: 1
	      - name: memory
	        weight: 1
	    name: NodeResourcesBalancedAllocation
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeResourcesFitArgs
	      scoringStrategy:
	        resources:
	        - name: cpu
	          weight: 1
	        - name: memory
	          weight: 1
	        type: LeastAllocated
	    name: NodeResourcesFit
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      defaultingType: System
	      kind: PodTopologySpreadArgs
	    name: PodTopologySpread
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      bindTimeoutSeconds: 600
	      kind: VolumeBindingArgs
	    name: VolumeBinding
	  plugins:
	    bind: {}
	    filter:
	      enabled:
	      - name: nodeFilter
	        weight: 0
	    multiPoint:
	      enabled:
	      - name: PrioritySort
	        weight: 0
	      - name: NodeUnschedulable
	        weight: 0
	      - name: NodeName
	        weight: 0
	      - name: TaintToleration
	        weight: 3
	      - name: NodeAffinity
	        weight: 2
	      - name: NodePorts
	        weight: 0
	      - name: NodeResourcesFit
	        weight: 1
	      - name: VolumeRestrictions
	        weight: 0
	      - name: EBSLimits
	        weight: 0
	      - name: GCEPDLimits
	        weight: 0
	      - name: NodeVolumeLimits
	        weight: 0
	      - name: AzureDiskLimits
	        weight: 0
	      - name: VolumeBinding
	        weight: 0
	      - name: VolumeZone
	        weight: 0
	      - name: PodTopologySpread
	        weight: 2
	      - name: InterPodAffinity
	        weight: 2
	      - name: DefaultPreemption
	        weight: 0
	      - name: NodeResourcesBalancedAllocation
	        weight: 1
	      - name: ImageLocality
	        weight: 1
	      - name: DefaultBinder
	        weight: 0
	    permit: {}
	    postBind: {}
	    postFilter: {}
	    preBind: {}
	    preEnqueue: {}
	    preFilter: {}
	    preScore: {}
	    queueSort: {}
	    reserve: {}
	    score: {}
	  schedulerName: my-scheduler
 >
I0415 19:07:29.267567       1 server.go:152] "Starting Kubernetes Scheduler" version="v1.26.9-scheduler"
I0415 19:07:29.267603       1 server.go:154] "Golang settings" GOGC="" GOMAXPROCS="" GOTRACEBACK=""
I0415 19:07:29.270604       1 tlsconfig.go:200] "Loaded serving cert" certName="Generated self signed cert" certDetail="\"localhost@1713179248\" [serving] validServingFor=[127.0.0.1,localhost,localhost] issuer=\"localhost-ca@1713179248\" (2024-04-15 10:07:28 +0000 UTC to 2025-04-15 10:07:28 +0000 UTC (now=2024-04-15 11:07:29.27057216 +0000 UTC))"
I0415 19:07:29.271646       1 named_certificates.go:53] "Loaded SNI cert" index=0 certName="self-signed loopback" certDetail="\"apiserver-loopback-client@1713179249\" [serving] validServingFor=[apiserver-loopback-client] issuer=\"apiserver-loopback-client-ca@1713179248\" (2024-04-15 10:07:28 +0000 UTC to 2025-04-15 10:07:28 +0000 UTC (now=2024-04-15 11:07:29.271614794 +0000 UTC))"
I0415 19:07:29.271701       1 secure_serving.go:210] Serving securely on [::]:10259
I0415 19:07:29.272116       1 tlsconfig.go:240] "Starting DynamicServingCertificateController"
I0415 19:07:29.294827       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.198" zone="gz:\x00:zoneC"
I0415 19:07:29.296534       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.199" zone="gz:\x00:zoneC"
I0415 19:07:29.296661       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.200" zone="gz:\x00:zoneC"
I0415 19:07:29.296739       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.201" zone="gz:\x00:zoneC"
I0415 19:07:29.372008       1 leaderelection.go:248] attempting to acquire leader lease kube-system/kube-scheduler...
I0415 19:07:29.377329       1 leaderelection.go:258] successfully acquired lease kube-system/kube-scheduler
====nodeFilter filter===
I0415 19:10:21.748791       1 nodefilter.go:28] "nodeFilter filter" pod_name="nginx-6497887b7c-2mdmd" current node="192.168.0.199" cpu=1900 memory=8020500480
I0415 19:10:21.748942       1 nodefilter.go:28] "nodeFilter filter" pod_name="nginx-6497887b7c-2mdmd" current node="192.168.0.200" cpu=1900 memory=8020508672
I0415 19:10:21.748980       1 nodefilter.go:28] "nodeFilter filter" pod_name="nginx-6497887b7c-2mdmd" current node="192.168.0.201" cpu=1900 memory=8020508672
====nodeFilter filter===
====nodeFilter filter===
I0415 19:10:21.756151       1 schedule_one.go:252] "Successfully bound pod to node" pod="default/nginx-6497887b7c-2mdmd" node="192.168.0.199" evaluatedNodes=4 feasibleNodes=3
```

上述内容，可参见 [源码](https://github.com/tanjunchen/kubernetes/commit/b411c1886d0c5013e824d9ca83a33dad44b1c8e8) 。

# out-of-tree 自定义插件

out-of-tree plugins 由用户自己编写和维护，独立部署，不需要对 k8s 做任何代码或配置改动。本质上 out-of-tree plugins 也是跟 kube-scheduler 代码一起编译的，不过 kube-scheduler 相关代码已经抽出来作为一个独立项 [scheduler-plugins](github.com/kubernetes-sigs/scheduler-plugins)。 用户只需要引用这个包，编写自己的调度器插件，然后以普通 pod 方式部署就行（binary 部署也行）。编译之后是个包含默认调度器和所有 out-of-tree 插件的总调度器程序。它有内置调度器的功能，也包括了 out-of-tree 调度器的功能。

两种部署方式：
* 跟现有调度器并行部署，只管理特定的某些 pods；
* 取代现有调度器，因为它功能也是全的；

## 单调度器

1、克隆 https://github.com/tanjunchen/tanjunchen-scheduler.git 源码（是基于 Kubernetes 1.26.9 实现的）
```bash
git clone https://github.com/tanjunchen/tanjunchen-scheduler.git
cd tanjunchen-scheduler
```

2、在 tanjunchen-scheduler 根目录下重新编译 Kubernetes Scheduler 调度器。
```bash
root@instance-820epr0w:~/tanjunchen/tanjunchen-scheduler# make image
mkdir -p _output/bin
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o=_output/bin/tanjunchen-scheduler ./cmd/scheduler
docker build --no-cache . -t tanjunchen-scheduler:v1.26.9-scheduler
[+] Building 3.8s (8/8) FINISHED                                                                                                                                       docker:default
 => [internal] load build definition from Dockerfile                                                                                                                             0.0s
 => => transferring dockerfile: 173B                                                                                                                                             0.0s
 => [internal] load .dockerignore                                                                                                                                                0.0s
 => => transferring context: 2B                                                                                                                                                  0.0s
 => [internal] load metadata for docker.io/library/debian:stretch-slim                                                                                                           2.1s
 => [auth] library/debian:pull token for registry-1.docker.io                                                                                                                    0.0s
 => [internal] load build context                                                                                                                                                0.4s
 => => transferring context: 77.56MB                                                                                                                                             0.4s
 => CACHED [1/3] FROM docker.io/library/debian:stretch-slim@sha256:abaa313c7e1dfe16069a1a42fa254014780f165d4fd084844602edbe29915e70                                              0.0s
 => [2/3] COPY _output/bin/tanjunchen-scheduler /usr/local/bin                                                                                                                   0.9s
 => exporting to image                                                                                                                                                           0.3s
 => => exporting layers                                                                                                                                                          0.3s
 => => writing image sha256:77e0c775f8fa19f941fe178d5bb52cce4873bc75935a18f29ef931c62dd03008                                                                                     0.0s
 => => naming to docker.io/library/tanjunchen-scheduler:v1.26.9-scheduler    
```

3、在配置文件中添加我们的自定义插件，kube-scheduler 启动命令配置文件路径，如下所示：
```yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
clientConnection:
  acceptContentTypes: ""
  burst: 100
  contentType: application/vnd.kubernetes.protobuf
  kubeconfig: /etc/kubernetes/scheduler.conf
  qps: 100
profiles:
- schedulerName: tanjunchen-scheduler
  plugins:
    filter:
      enabled:
      - name: nodeFilter
```

4、更改 Kubernetes Scheduler 静态 Static Pod 部署 kube-scheduler yaml 文件，如下所示：
```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    scheduler.alpha.kubernetes.io/critical-pod: ""
  creationTimestamp: null
  labels:
    component: kube-scheduler
    tier: control-plane
  name: kube-scheduler
  namespace: kube-system
spec:
  containers:
    - command:
        - tanjunchen-scheduler
        - --master=https://192.168.0.198:6443
        - --feature-gates=MixedProtocolLBService=true
        - --kubeconfig=/etc/kubernetes/scheduler.conf
        - --authorization-always-allow-paths=/metrics,/healthz,/readyz,/livez
        - --leader-elect=true
        - --kube-api-qps=100
        - --kube-api-burst=100
        - --bind-address=0.0.0.0
        - --profiling
        - --v=2
        - --config=/etc/kubernetes/scheduler_config.yaml
      image: docker.io/tanjunchen/kube-scheduler-amd64-out-of-tree:v1.26.9-scheduler
      imagePullPolicy: Always
      name: kube-scheduler
      volumeMounts:
        - mountPath: /etc/kubernetes
          name: kubernetes
        - mountPath: /etc/localtime
          name: localtime
  hostNetwork: true
  priorityClassName: system-cluster-critical
  volumes:
    - hostPath:
        path: /etc/kubernetes
        type: DirectoryOrCreate
      name: kubernetes
    - hostPath:
        path: /etc/localtime
        type: File
      name: localtime
```

5、部署测试示例 nginx
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      schedulerName: tanjunchen-scheduler
      containers:
        - name: nginx
          image: docker.io/tanjunchen/nginx:1.17.3
          ports:
            - containerPort: 80
```

6、查看 scheduler 调度日志，终端打印了我们插件中编写的代码逻辑。
```bash
➜  ~ kubectl -n kube-system  logs -f kube-scheduler-192.168.0.198
W0416 15:42:35.308144       1 feature_gate.go:241] Setting GA feature gate MixedProtocolLBService=true. It will be removed in a future release.
I0416 15:42:35.308258       1 flags.go:64] FLAG: --allow-metric-labels="[]"
I0416 15:42:35.308273       1 flags.go:64] FLAG: --authentication-kubeconfig=""
I0416 15:42:35.308279       1 flags.go:64] FLAG: --authentication-skip-lookup="false"
I0416 15:42:35.308284       1 flags.go:64] FLAG: --authentication-token-webhook-cache-ttl="10s"
I0416 15:42:35.308290       1 flags.go:64] FLAG: --authentication-tolerate-lookup-failure="true"
I0416 15:42:35.308293       1 flags.go:64] FLAG: --authorization-always-allow-paths="[/metrics,/healthz,/readyz,/livez]"
I0416 15:42:35.308354       1 flags.go:64] FLAG: --authorization-kubeconfig=""
I0416 15:42:35.308359       1 flags.go:64] FLAG: --authorization-webhook-cache-authorized-ttl="10s"
I0416 15:42:35.308363       1 flags.go:64] FLAG: --authorization-webhook-cache-unauthorized-ttl="10s"
I0416 15:42:35.308366       1 flags.go:64] FLAG: --bind-address="0.0.0.0"
I0416 15:42:35.308372       1 flags.go:64] FLAG: --cert-dir=""
I0416 15:42:35.308375       1 flags.go:64] FLAG: --client-ca-file=""
I0416 15:42:35.308378       1 flags.go:64] FLAG: --config="/etc/kubernetes/scheduler_config.yaml"
......
W0416 15:42:35.960902       1 authorization.go:194] No authorization-kubeconfig provided, so SubjectAccessReview of authorization tokens won't work.
I0416 15:42:35.970916       1 configfile.go:105] "Using component config" config=<
	apiVersion: kubescheduler.config.k8s.io/v1
	clientConnection:
	  acceptContentTypes: ""
	  burst: 100
	  contentType: application/vnd.kubernetes.protobuf
	  kubeconfig: /etc/kubernetes/scheduler.conf
	  qps: 100
	enableContentionProfiling: true
	enableProfiling: true
	kind: KubeSchedulerConfiguration
	leaderElection:
	  leaderElect: true
	  leaseDuration: 15s
	  renewDeadline: 10s
	  resourceLock: leases
	  resourceName: kube-scheduler
	  resourceNamespace: kube-system
	  retryPeriod: 2s
	parallelism: 16
	percentageOfNodesToScore: 0
	podInitialBackoffSeconds: 1
	podMaxBackoffSeconds: 10
	profiles:
	- pluginConfig:
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: DefaultPreemptionArgs
	      minCandidateNodesAbsolute: 100
	      minCandidateNodesPercentage: 10
	    name: DefaultPreemption
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      hardPodAffinityWeight: 1
	      kind: InterPodAffinityArgs
	    name: InterPodAffinity
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeAffinityArgs
	    name: NodeAffinity
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeResourcesBalancedAllocationArgs
	      resources:
	      - name: cpu
	        weight: 1
	      - name: memory
	        weight: 1
	    name: NodeResourcesBalancedAllocation
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeResourcesFitArgs
	      scoringStrategy:
	        resources:
	        - name: cpu
	          weight: 1
	        - name: memory
	          weight: 1
	        type: LeastAllocated
	    name: NodeResourcesFit
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      defaultingType: System
	      kind: PodTopologySpreadArgs
	    name: PodTopologySpread
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      bindTimeoutSeconds: 600
	      kind: VolumeBindingArgs
	    name: VolumeBinding
	  plugins:
	    bind: {}
	    filter:
	      enabled:
	      - name: nodeFilter
	        weight: 0
	    multiPoint:
	      enabled:
	      - name: PrioritySort
	        weight: 0
	      - name: NodeUnschedulable
	        weight: 0
	      - name: NodeName
	        weight: 0
	      - name: TaintToleration
	        weight: 3
	      - name: NodeAffinity
	        weight: 2
	      - name: NodePorts
	        weight: 0
	      - name: NodeResourcesFit
	        weight: 1
	      - name: VolumeRestrictions
	        weight: 0
	      - name: EBSLimits
	        weight: 0
	      - name: GCEPDLimits
	        weight: 0
	      - name: NodeVolumeLimits
	        weight: 0
	      - name: AzureDiskLimits
	        weight: 0
	      - name: VolumeBinding
	        weight: 0
	      - name: VolumeZone
	        weight: 0
	      - name: PodTopologySpread
	        weight: 2
	      - name: InterPodAffinity
	        weight: 2
	      - name: DefaultPreemption
	        weight: 0
	      - name: NodeResourcesBalancedAllocation
	        weight: 1
	      - name: ImageLocality
	        weight: 1
	      - name: DefaultBinder
	        weight: 0
	    permit: {}
	    postBind: {}
	    postFilter: {}
	    preBind: {}
	    preEnqueue: {}
	    preFilter: {}
	    preScore: {}
	    queueSort: {}
	    reserve: {}
	    score: {}
	  schedulerName: tanjunchen-scheduler
 >
I0416 15:42:35.971419       1 server.go:152] "Starting Kubernetes Scheduler" version="v0.0.0-master+$Format:%H$"
I0416 15:42:35.971429       1 server.go:154] "Golang settings" GOGC="" GOMAXPROCS="" GOTRACEBACK=""
I0416 15:42:35.972506       1 tlsconfig.go:200] "Loaded serving cert" certName="Generated self signed cert" certDetail="\"localhost@1713253355\" [serving] validServingFor=[127.0.0.1,localhost,localhost] issuer=\"localhost-ca@1713253355\" (2024-04-16 06:42:35 +0000 UTC to 2025-04-16 06:42:35 +0000 UTC (now=2024-04-16 07:42:35.972474703 +0000 UTC))"
I0416 15:42:35.972669       1 named_certificates.go:53] "Loaded SNI cert" index=0 certName="self-signed loopback" certDetail="\"apiserver-loopback-client@1713253355\" [serving] validServingFor=[apiserver-loopback-client] issuer=\"apiserver-loopback-client-ca@1713253355\" (2024-04-16 06:42:35 +0000 UTC to 2025-04-16 06:42:35 +0000 UTC (now=2024-04-16 07:42:35.972648501 +0000 UTC))"
I0416 15:42:35.972717       1 secure_serving.go:210] Serving securely on [::]:10259
I0416 15:42:35.973029       1 tlsconfig.go:240] "Starting DynamicServingCertificateController"
I0416 15:42:35.993626       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.201" zone="gz:\x00:zoneC"
I0416 15:42:35.993816       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.198" zone="gz:\x00:zoneC"
I0416 15:42:35.993979       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.199" zone="gz:\x00:zoneC"
I0416 15:42:35.994063       1 node_tree.go:65] "Added node in listed group to NodeTree" node="192.168.0.200" zone="gz:\x00:zoneC"
I0416 15:42:36.073746       1 leaderelection.go:248] attempting to acquire leader lease kube-system/kube-scheduler...
I0416 15:42:36.079082       1 leaderelection.go:258] successfully acquired lease kube-system/kube-scheduler
I0416 16:15:31.233364       1 nodefilter.go:26] "tanjunchen-scheduler nodeFilter filter" pod_name="nginx-58c5764c9f-lwcsr" current node="192.168.0.201" cpu=1900 memory=8020508672
I0416 16:15:31.233416       1 nodefilter.go:26] "tanjunchen-scheduler nodeFilter filter" pod_name="nginx-58c5764c9f-lwcsr" current node="192.168.0.199" cpu=1900 memory=8020500480
I0416 16:15:31.233433       1 nodefilter.go:26] "tanjunchen-scheduler nodeFilter filter" pod_name="nginx-58c5764c9f-lwcsr" current node="192.168.0.200" cpu=1900 memory=8020508672
I0416 16:15:31.246951       1 schedule_one.go:252] "Successfully bound pod to node" pod="default/nginx-58c5764c9f-lwcsr" node="192.168.0.199" evaluatedNodes=4 feasibleNodes=3
```

## 多调度器

1、克隆源码（是基于 Kubernetes 1.26.9 实现的）
```bash
git clone https://github.com/tanjunchen/tanjunchen-scheduler.git
cd multiple-tanjunchen-scheduler
```

2、在 tanjunchen-scheduler 根目录下重新编译 Kubernetes Scheduler 调度器。
```bash
➜  multiple-tanjunchen-scheduler git:(main) ✗ make image
mkdir -p _output/bin
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o=_output/bin/tanjunchen-scheduler ./cmd/scheduler
docker build --no-cache . -t docker.io/tanjunchen/tanjunchen-scheduler:multiple-v1.26.9-scheduler
[+] Building 8.2s (8/8) FINISHED                                                                          
 => [internal] load .dockerignore                                                                    0.0s
 => => transferring context: 2B                                                                      0.0s
 => [internal] load build definition from Dockerfile                                                 0.0s
 => => transferring dockerfile: 173B                                                                 0.0s
 => [internal] load metadata for docker.io/library/debian:stretch-slim                               6.3s
 => [auth] library/debian:pull token for registry-1.docker.io                                        0.0s
 => [internal] load build context                                                                    1.3s
 => => transferring context: 77.67MB                                                                 1.3s
 => CACHED [1/3] FROM docker.io/library/debian:stretch-slim@sha256:abaa313c7e1dfe16069a1a42fa254014  0.0s
 => [2/3] COPY _output/bin/tanjunchen-scheduler /usr/local/bin                                       0.4s
 => exporting to image                                                                               0.1s
 => => exporting layers                                                                              0.1s
 => => writing image sha256:b37612f90ef806188cfca443456054c1f81ef8073c4eac824bab64bc4aa9556a         0.0s
 => => naming to docker.io/tanjunchen/tanjunchen-scheduler:multiple-v1.26.9-scheduler  
```

3、在配置文件中添加我们的自定义插件，kube-scheduler 启动命令配置文件路径，如下所示：
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tanjunchen-scheduler-config
  namespace: kube-system
data:
  scheduler-config.yaml: |
    apiVersion: kubescheduler.config.k8s.io/v1
    kind: KubeSchedulerConfiguration
    leaderElection:
      leaderElect: false
    clientConnection:
      acceptContentTypes: ""
      burst: 100
      contentType: application/vnd.kubernetes.protobuf
      qps: 100
    profiles:
    - schedulerName: tanjunchen-scheduler
      plugins:
        preFilter:
          enabled:
          - name: "example"
        filter:
          enabled:
          - name: "example"
        preBind:
          enabled:
          - name: "example"
```

4、部署 kube-scheduler yaml 文件，如下所示：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tanjunchen-scheduler
  namespace: kube-system
  labels:
    component: tanjunchen-scheduler
spec:
  replicas: 1
  selector:
    matchLabels:
      component: tanjunchen-scheduler
  template:
    metadata:
      labels:
        component: tanjunchen-scheduler
    spec:
      serviceAccount: tanjunchen-scheduler-sa
      priorityClassName: system-cluster-critical
      volumes:
        - name: scheduler-config
          configMap:
            name: tanjunchen-scheduler-config
      containers:
        - name: scheduler-ctrl
          image: docker.io/tanjunchen/kube-scheduler-amd64-out-of-tree:multiple-v1.26.9-scheduler
          imagePullPolicy: Always
          args:
            - tanjunchen-scheduler
            - --config=/etc/kubernetes/scheduler-config.yaml
            - --v=3
          resources:
            requests:
              cpu: "50m"
          volumeMounts:
            - name: scheduler-config
              mountPath: /etc/kubernetes
```

5、部署测试示例 nginx（tanjunchen-scheduler 调度器）
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      schedulerName: tanjunchen-scheduler
      containers:
        - name: nginx
          image: docker.io/tanjunchen/nginx:1.17.3
          ports:
            - containerPort: 80
```

6、查看 tanjunchen scheduler 调度日志，终端打印了我们插件中编写的代码逻辑。
```bash
➜  tanjunchen-scheduler git:(main) ✗ kubectl -n kube-system logs -f tanjunchen-scheduler-75456df696-4xzfg
I0416 12:54:53.922028       1 flags.go:64] FLAG: --allow-metric-labels="[]"
I0416 12:54:53.922087       1 flags.go:64] FLAG: --authentication-kubeconfig=""
I0416 12:54:53.922092       1 flags.go:64] FLAG: --authentication-skip-lookup="false"
W0416 12:54:54.188278       1 client_config.go:618] Neither --kubeconfig nor --master was specified.  Using the inClusterConfig.  This might not work.
I0416 12:54:54.587616       1 requestheader_controller.go:244] Loaded a new request header values for RequestHeaderAuthRequestController
I0416 12:54:54.593957       1 configfile.go:105] "Using component config" config=<
	apiVersion: kubescheduler.config.k8s.io/v1
	clientConnection:
	  acceptContentTypes: ""
	  burst: 100
	  contentType: application/vnd.kubernetes.protobuf
	  kubeconfig: ""
	  qps: 100
	enableContentionProfiling: true
	enableProfiling: true
	kind: KubeSchedulerConfiguration
	leaderElection:
	  leaderElect: false
	  leaseDuration: 15s
	  renewDeadline: 10s
	  resourceLock: leases
	  resourceName: kube-scheduler
	  resourceNamespace: kube-system
	  retryPeriod: 2s
	parallelism: 16
	percentageOfNodesToScore: 0
	podInitialBackoffSeconds: 1
	podMaxBackoffSeconds: 10
	profiles:
	- pluginConfig:
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: DefaultPreemptionArgs
	      minCandidateNodesAbsolute: 100
	      minCandidateNodesPercentage: 10
	    name: DefaultPreemption
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      hardPodAffinityWeight: 1
	      kind: InterPodAffinityArgs
	    name: InterPodAffinity
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeAffinityArgs
	    name: NodeAffinity
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeResourcesBalancedAllocationArgs
	      resources:
	      - name: cpu
	        weight: 1
	      - name: memory
	        weight: 1
	    name: NodeResourcesBalancedAllocation
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      kind: NodeResourcesFitArgs
	      scoringStrategy:
	        resources:
	        - name: cpu
	          weight: 1
	        - name: memory
	          weight: 1
	        type: LeastAllocated
	    name: NodeResourcesFit
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      defaultingType: System
	      kind: PodTopologySpreadArgs
	    name: PodTopologySpread
	  - args:
	      apiVersion: kubescheduler.config.k8s.io/v1
	      bindTimeoutSeconds: 600
	      kind: VolumeBindingArgs
	    name: VolumeBinding
	  plugins:
	    bind: {}
	    filter:
	      enabled:
	      - name: example
	        weight: 0
	    multiPoint:
	      enabled:
	      - name: PrioritySort
	        weight: 0
	      - name: NodeUnschedulable
	        weight: 0
	      - name: NodeName
	        weight: 0
	      - name: TaintToleration
	        weight: 3
	      - name: NodeAffinity
	        weight: 2
	      - name: NodePorts
	        weight: 0
	      - name: NodeResourcesFit
	        weight: 1
	      - name: VolumeRestrictions
	        weight: 0
	      - name: EBSLimits
	        weight: 0
	      - name: GCEPDLimits
	        weight: 0
	      - name: NodeVolumeLimits
	        weight: 0
	      - name: AzureDiskLimits
	        weight: 0
	      - name: VolumeBinding
	        weight: 0
	      - name: VolumeZone
	        weight: 0
	      - name: PodTopologySpread
	        weight: 2
	      - name: InterPodAffinity
	        weight: 2
	      - name: DefaultPreemption
	        weight: 0
	      - name: NodeResourcesBalancedAllocation
	        weight: 1
	      - name: ImageLocality
	        weight: 1
	      - name: DefaultBinder
	        weight: 0
	    permit: {}
	    postBind: {}
	    postFilter: {}
	    preBind:
	      enabled:
	      - name: example
	        weight: 0
	    preEnqueue: {}
	    preFilter:
	      enabled:
	      - name: example
	        weight: 0
	    preScore: {}
	    queueSort: {}
	    reserve: {}
	    score: {}
	  schedulerName: tanjunchen-scheduler
 >
I0416 12:54:54.594392       1 server.go:152] "Starting Kubernetes Scheduler" version="v0.0.0-master+$Format:%H$"
I0416 12:54:54.594407       1 server.go:154] "Golang settings" GOGC="" GOMAXPROCS="" GOTRACEBACK=""
I0416 14:24:00.786590       1 example.go:27] "tanjunchen-scheduler PreFilter pod: %v, node name: %v" nginx-58c5764c9f-q5ngg="(MISSING)"
I0416 14:24:00.786667       1 example.go:34] "tanjunchen-scheduler Filter" pod_name="nginx-58c5764c9f-q5ngg" current node="192.168.0.199" cpu=1900 memory=8020500480
I0416 14:24:00.786690       1 example.go:34] "tanjunchen-scheduler Filter" pod_name="nginx-58c5764c9f-q5ngg" current node="192.168.0.201" cpu=1900 memory=8020508672
I0416 14:24:00.786708       1 example.go:34] "tanjunchen-scheduler Filter" pod_name="nginx-58c5764c9f-q5ngg" current node="192.168.0.200" cpu=1900 memory=8020508672
I0416 14:24:00.787004       1 example.go:46] "tanjunchen-scheduler PreBind pod: %v, node name: %v" nginx-58c5764c9f-q5ngg="192.168.0.199"
I0416 14:24:00.792801       1 schedule_one.go:252] "Successfully bound pod to node" pod="default/nginx-58c5764c9f-q5ngg" node="192.168.0.199" evaluatedNodes=4 feasibleNodes=3
```

7、部署测试示例 nginx（default-scheduler 调度器）
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: default-nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      schedulerName: tanjunchen-scheduler
      containers:
        - name: nginx
          image: docker.io/tanjunchen/nginx:1.17.3
          ports:
            - containerPort: 80
```

8、查看 default scheduler 调度日志，日志如下所示：
```bash
kubectl -n kube-system logs -f kube-scheduler-192.168.0.198
W0416 19:13:11.987494       1 feature_gate.go:241] Setting GA feature gate MixedProtocolLBService=true. It will be removed in a future release.
I0416 22:29:40.953225       1 schedule_one.go:252] "Successfully bound pod to node" pod="default/nginx-84bfdb5dc4-9v84j" node="192.168.0.199" evaluatedNodes=4 feasibleNodes=3
```
