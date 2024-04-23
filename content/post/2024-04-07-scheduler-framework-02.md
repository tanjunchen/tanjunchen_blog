---
layout:     post
title:      "深入理解 Kubernetes Scheduler Framework 调度框架（Part 2）"
subtitle:   "Scheduler Framework 框架核心源码与 Pod 调度到 Node 流程"
description: ""
author: "陈谭军"
date: 2024-04-07
published: true
tags:
    - kubernetes
    - Scheduler Framework
categories:
    - TECHNOLOGY
showtoc: true
---

Scheduler 分两个 cycle：Scheduling Cycle 和 Binding Cycle。在 Scheduling Cycle 中为了提升效率的一个重要原则就是 Pod、 Node 等信息从本地缓存中获取，而具体的实现原理就是先使用 list 获取所有 Node、Pod 的信息，然后再 watch 他们的变化更新本地缓存。在 Bind Cycle 中，会有两次外部 api 调用：调用 pv controller 绑定 pv 和调用 kube-apiserver 绑定 Node，api 调用是耗时的，所以将 bind 扩展点拆分出来，另起一个 go 协程进行 bind。调度周期是串行，绑定周期是并行的。
本文主要介绍 Scheduler Framework 框架核心源码与 Pod 调度到 Node 流程。

[深入理解 Kubernetes Scheduler Framework 调度框架（Part 2）](https://tanjunchen.github.io/post/2024-04-07-scheduler-framework-02/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 1）](https://tanjunchen.github.io/post/2024-04-06-scheduler-framework-01/) 


# 核心源码

依据 Kubernetes 1.29 源码 [v1.29.3/pkg/scheduler/internal/cache/cache.go](https://github.com/kubernetes/kubernetes/blob/v1.29.3/pkg/scheduler/internal/cache/cache.go) 说说 scheduler 是怎么工作。我们来重点分析 SchedulerProfiles、SchedulerQueue、SchedulerCache、NextPod 和 SchedulePod、Informer 等核心组件是如何工作的。

## SchedulerProfiles

在上面的整体架构中，看到 Scheduler Framework 是按照如下顺利进行拓展的，在拓展点内按照插件注册的顺利执行插件，如下所示：

![](/images/2024-04-06-scheduler-framework-01/5.svg)

```go
// Scheduler watches for new unscheduled pods. It attempts to find
// nodes that they fit on and writes bindings back to the api server.
type Scheduler struct {
	// It is expected that changes made via Cache will be observed
	// by NodeLister and Algorithm.
	Cache internalcache.Cache

	Extenders []framework.Extender

	// NextPod should be a function that blocks until the next pod
	// is available. We don't use a channel for this, because scheduling
	// a pod may take some amount of time and we don't want pods to get
	// stale while they sit in a channel.
	NextPod func(logger klog.Logger) (*framework.QueuedPodInfo, error)

	// FailureHandler is called upon a scheduling failure.
	FailureHandler FailureHandlerFn

	// SchedulePod tries to schedule the given pod to one of the nodes in the node list.
	// Return a struct of ScheduleResult with the name of suggested host on success,
	// otherwise will return a FitError with reasons.
	SchedulePod func(ctx context.Context, fwk framework.Framework, state *framework.CycleState, pod *v1.Pod) (ScheduleResult, error)

	// Close this to shut down the scheduler.
	StopEverything <-chan struct{}

	// SchedulingQueue holds pods to be scheduled
	SchedulingQueue internalqueue.SchedulingQueue

	// Profiles are the scheduling profiles.
	Profiles profile.Map

	client clientset.Interface

	nodeInfoSnapshot *internalcache.Snapshot

	percentageOfNodesToScore int32

	nextStartNodeIndex int

	// logger *must* be initialized when creating a Scheduler,
	// otherwise logging functions will access a nil sink and
	// panic.
	logger klog.Logger

	// registeredHandlers contains the registrations of all handlers. It's used to check if all handlers have finished syncing before the scheduling cycles start.
	registeredHandlers []cache.ResourceEventHandlerRegistration
}
```

以 preFilter 为例，扩展点内的插件，你既可以调整插件的执行顺序，可以关闭某个内置插件，还可以增加自己开发的插件，如下所示：

![](/images/2024-04-06-scheduler-framework-01/6.svg)

那么自定义插件又是怎么注册的？Scheduler 里面有最重要的一个成员 Profiles profile.Map。从 pkg/scheduler/profile/profile.go#L46 中可以看到 Profiles 是一个 key 为 scheduler name，value 是 framework.Framework 的 map，表示根据 scheduler name 来获取 framework.Framework 类型的值，如下调度器配置文件：
```yaml
apiVersion: kubescheduler.config.k8s.io/v1beta2
kind: KubeSchedulerConfiguration
leaderElection:
  leaderElect: true
clientConnection:
  kubeconfig: "/etc/kubernetes/scheduler.conf"
profiles:
- schedulerName: my-scheduler-1
  plugins:
    preFilter:
      enabled:
        - name: ZoneNodeLabel
      disabled:
        - name: NodePorts
- schedulerName: my-scheduler-2
  plugins:
    queueSort:
      enabled:
        - name: MySort
```

通过配置文件，可以使用 enabled，disabled 开关来关闭或打开某个插件，还可以控制扩展点的调用顺序，规则如下：
* 如果某个扩展点没有配置对应的扩展，调度框架将使用默认插件中的扩展；
* 如果为某个扩展点配置且激活了扩展，则调度框架将先调用默认插件的扩展，再调用配置中的扩展；
* 默认插件的扩展始终被最先调用，然后按照 KubeSchedulerConfiguration 中扩展的激活 enabled 顺序逐个调用扩展点的扩展；
* 可以先禁用默认插件的扩展，然后在 enabled 列表中的某个位置激活默认插件的扩展，这种做法可以改变默认插件的扩展被调用时的顺序；
更多 profile 调度规则可参见 [https://v1-28.docs.kubernetes.io/docs/reference/scheduling/config/](https://v1-28.docs.kubernetes.io/docs/reference/scheduling/config/) 。

通过 profile 如何获取到具体的 framework 调度框架？当一个 Pod 需要被调度的时候，kube-scheduler 会先取出 Pod 的 schedulerName 字段的值，然后通过 Profiles[schedulerName]，拿到 framework.Framework 对象，进而使用这个对象开始调度。现在 Profiles 成员（一个map）包含了两个元素，{"my-scheduler-1": framework.Framework ,"my-scheduler-2": framework.Framework}，如下所示：

![](/images/2024-04-06-scheduler-framework-01/7.svg)

见 pkg/scheduler/framework/interface.go 源码，下面是 framework.Framework 的定义。
```go
// Framework manages the set of plugins in use by the scheduling framework.
// Configured plugins are called at specified points in a scheduling context.
type Framework interface {
	Handle

	// PreEnqueuePlugins returns the registered preEnqueue plugins.
	PreEnqueuePlugins() []PreEnqueuePlugin

	// EnqueueExtensions returns the registered Enqueue extensions.
	EnqueueExtensions() []EnqueueExtensions

	// QueueSortFunc returns the function to sort pods in scheduling queue
	QueueSortFunc() LessFunc

	// RunPreFilterPlugins runs the set of configured PreFilter plugins. It returns
	// *Status and its code is set to non-success if any of the plugins returns
	// anything but Success. If a non-success status is returned, then the scheduling
	// cycle is aborted.
	// It also returns a PreFilterResult, which may influence what or how many nodes to
	// evaluate downstream.
	RunPreFilterPlugins(ctx context.Context, state *CycleState, pod *v1.Pod) (*PreFilterResult, *Status)

	// RunPostFilterPlugins runs the set of configured PostFilter plugins.
	// PostFilter plugins can either be informational, in which case should be configured
	// to execute first and return Unschedulable status, or ones that try to change the
	// cluster state to make the pod potentially schedulable in a future scheduling cycle.
	RunPostFilterPlugins(ctx context.Context, state *CycleState, pod *v1.Pod, filteredNodeStatusMap NodeToStatusMap) (*PostFilterResult, *Status)
    ......
	// Close calls Close method of each plugin.
	Close() error
}
```

Framework 是一个接口，需要实现的方法大部分为 RunXXXPlugins()，也就是运行某个扩展点的插件，那么只要实现这个 Framework 接口就可以对 Pod 进行调度。kube-scheduler 目前已有接口实现 frameworkImpl，见 pkg/scheduler/framework/runtime/framework.go。frameworkImpl 包含每个扩展点插件数组，所以某个扩展点要被执行的时候，只要遍历这个数组里面的所有插件，然后执行这些插件就可以。
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

在 pkg/scheduler/framework/plugins 目录下包含了所有内置插件对 Plugin 接口的实现，framework.FilterPlugin 定义如下所示：
```go
// Plugin is the parent type for all the scheduling framework plugins.
type Plugin interface {
	Name() string
}

// FilterPlugin is an interface for Filter plugins. These plugins are called at the
// filter extension point for filtering out hosts that cannot run a pod.
// This concept used to be called 'predicate' in the original scheduler.
// These plugins should return "Success", "Unschedulable" or "Error" in Status.code.
// However, the scheduler accepts other valid codes as well.
// Anything other than "Success" will lead to exclusion of the given host from
// running the pod.
type FilterPlugin interface {
	Plugin
	// Filter is called by the scheduling framework.
	// All FilterPlugins should return "Success" to declare that
	// the given node fits the pod. If Filter doesn't return "Success",
	// it will return "Unschedulable", "UnschedulableAndUnresolvable" or "Error".
	// For the node being evaluated, Filter plugins should look at the passed
	// nodeInfo reference for this particular node's information (e.g., pods
	// considered to be running on the node) instead of looking it up in the
	// NodeInfoSnapshot because we don't guarantee that they will be the same.
	// For example, during preemption, we may pass a copy of the original
	// nodeInfo object that has some pods removed from it to evaluate the
	// possibility of preempting them to schedule the target pod.
	Filter(ctx context.Context, state *CycleState, pod *v1.Pod, nodeInfo *NodeInfo) *Status
}
```

这些默认插件是怎么加到 framework？主要步骤如下所示：
* 根据配置文件（--config 指定的）、系统默认插件，按照扩展点生成需要被加载的插件数组（包括插件名称，权重），也就是初始化 KubeSchedulerConfiguration 中的 Profiles 成员；
* 创建 registry 集合，这个集合内是每个插件实例化函数，也就是插件名称到插件实例化函数的映射；
* 将上述步骤1中每个扩展点的每个插件（就是插件名字）拿出来，去步骤2的映射（map）中获取实例化函数，然后运行这个实例化函数，最后把这个实例化出来的插件（可以被运行的）追加到上面提到过的 frameworkImpl 对应扩展点数组中，这样后面要运行某个扩展点插件的时候遍历运行就可以；

```go
// PluginFactory is a function that builds a plugin.
type PluginFactory = func(ctx context.Context, configuration runtime.Object, f framework.Handle) (framework.Plugin, error)

// PluginFactoryWithFts is a function that builds a plugin with certain feature gates.
type PluginFactoryWithFts func(context.Context, runtime.Object, framework.Handle, plfeature.Features) (framework.Plugin, error)

// Registry is a collection of all available plugins. The framework uses a
// registry to enable and initialize configured plugins.
// All plugins must be in the registry before initializing the framework.
type Registry map[string]PluginFactory
```
包含内置（叫inTree）默认的插件映射和用户自定义（outOfTree）插件映射，内置的映射通过下面函数创建（见源码 pkg/scheduler/framework/plugins/registry.go）。
```go
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

用户自定义插件见源码 pkg/scheduler/scheduler.go，如下所示：

```go
// pkg/scheduler/scheduler.go
registry := frameworkplugins.NewInTreeRegistry()

if err := registry.Merge(options.frameworkOutOfTreeRegistry); err != nil {
    return nil, err
}
```

## SchedulerQueue

SchedulerQueue 见源码 pkg/scheduler/scheduler.go 如下所示：
```go
podQueue := internalqueue.NewSchedulingQueue(
    profiles[options.profiles[0].SchedulerName].QueueSortFunc(),
    informerFactory,
    internalqueue.WithPodInitialBackoffDuration(time.Duration(options.podInitialBackoffSeconds)*time.Second),
    internalqueue.WithPodMaxBackoffDuration(time.Duration(options.podMaxBackoffSeconds)*time.Second),
    internalqueue.WithPodLister(podLister),
    internalqueue.WithPodMaxInUnschedulablePodsDuration(options.podMaxInUnschedulablePodsDuration),
    internalqueue.WithPreEnqueuePluginMap(preEnqueuePluginMap),
    internalqueue.WithQueueingHintMapPerProfile(queueingHintsPerProfile),
    internalqueue.WithPluginMetricsSamplePercent(pluginMetricsSamplePercent),
    internalqueue.WithMetricsRecorder(*metricsRecorder),
)

// NewSchedulingQueue initializes a priority queue as a new scheduling queue.
func NewSchedulingQueue(
	lessFn framework.LessFunc,
	informerFactory informers.SharedInformerFactory,
	opts ...Option) SchedulingQueue {
	return NewPriorityQueue(lessFn, informerFactory, opts...)
}

// PriorityQueue implements a scheduling queue.
// The head of PriorityQueue is the highest priority pending pod. This structure
// has two sub queues and a additional data structure, namely: activeQ,
// backoffQ and unschedulablePods.
//   - activeQ holds pods that are being considered for scheduling.
//   - backoffQ holds pods that moved from unschedulablePods and will move to
//     activeQ when their backoff periods complete.
//   - unschedulablePods holds pods that were already attempted for scheduling and
//     are currently determined to be unschedulable.
type PriorityQueue struct {
	*nominator

	stop  chan struct{}
	clock clock.Clock

	// pod initial backoff duration.
	podInitialBackoffDuration time.Duration
	// pod maximum backoff duration.
	podMaxBackoffDuration time.Duration
	// the maximum time a pod can stay in the unschedulablePods.
	podMaxInUnschedulablePodsDuration time.Duration

	cond sync.Cond

	// inFlightPods holds the UID of all pods which have been popped out for which Done
	// hasn't been called yet - in other words, all pods that are currently being
	// processed (being scheduled, in permit, or in the binding cycle).
	//
	// The values in the map are the entry of each pod in the inFlightEvents list.
	// The value of that entry is the *v1.Pod at the time that scheduling of that
	// pod started, which can be useful for logging or debugging.
	inFlightPods map[types.UID]*list.Element

	// inFlightEvents holds the events received by the scheduling queue
	// (entry value is clusterEvent) together with in-flight pods (entry
	// value is *v1.Pod). Entries get added at the end while the mutex is
	// locked, so they get serialized.
	//
	// The pod entries are added in Pop and used to track which events
	// occurred after the pod scheduling attempt for that pod started.
	// They get removed when the scheduling attempt is done, at which
	// point all events that occurred in the meantime are processed.
	//
	// After removal of a pod, events at the start of the list are no
	// longer needed because all of the other in-flight pods started
	// later. Those events can be removed.
	inFlightEvents *list.List

	// activeQ is heap structure that scheduler actively looks at to find pods to
	// schedule. Head of heap is the highest priority pod.
	activeQ *heap.Heap
	// podBackoffQ is a heap ordered by backoff expiry. Pods which have completed backoff
	// are popped from this heap before the scheduler looks at activeQ
	podBackoffQ *heap.Heap
	// unschedulablePods holds pods that have been tried and determined unschedulable.
	unschedulablePods *UnschedulablePods
	// schedulingCycle represents sequence number of scheduling cycle and is incremented
	// when a pod is popped.
	schedulingCycle int64
	// moveRequestCycle caches the sequence number of scheduling cycle when we
	// received a move request. Unschedulable pods in and before this scheduling
	// cycle will be put back to activeQueue if we were trying to schedule them
	// when we received move request.
	// TODO: this will be removed after SchedulingQueueHint goes to stable and the feature gate is removed.
	moveRequestCycle int64

	// preEnqueuePluginMap is keyed with profile name, valued with registered preEnqueue plugins.
	preEnqueuePluginMap map[string][]framework.PreEnqueuePlugin
	// queueingHintMap is keyed with profile name, valued with registered queueing hint functions.
	queueingHintMap QueueingHintMapPerProfile

	// closed indicates that the queue is closed.
	// It is mainly used to let Pop() exit its control loop while waiting for an item.
	closed bool

	nsLister listersv1.NamespaceLister

	metricsRecorder metrics.MetricAsyncRecorder
	// pluginMetricsSamplePercent is the percentage of plugin metrics to be sampled.
	pluginMetricsSamplePercent int

	// isSchedulingQueueHintEnabled indicates whether the feature gate for the scheduling queue is enabled.
	isSchedulingQueueHintEnabled bool
}
```

SchedulingQueue 是一个 internalqueue.SchedulingQueue 接口类型，PriorityQueue 对这个接口进行了实现，创建 Scheduler 的时候 SchedulingQueue 会被 PriorityQueue 类型对象赋值。SchedulerQueue 包含三个队列：activeQ、podBackoffQ、unschedulablePods。

* activeQ 是一个优先队列，基于堆实现，用于存放待调度的 Pod，优先级高的会放在队列头部，优先被调度。该队列存放的 Pod 可能的情况有：刚创建未被调度的Pod；backOffPod 队列中转移过来的Pod；unschedule 队列里转移过来的 Pod；
* podBackoffQ 也是一个优先队列，用于存放那些异常的Pod，这种 Pod 需要等待一定的时间才能够被再次调度，会有协程定期去读取这个队列，然后加入到 activeQ 队列然后重新调度；
* unschedulablePods 严格上来说不属于队列，用于存放调度失败的 Pod。这个队列也会有协程定期（默认30s）去读取，然后判断当前时间距离上次调度时间的差是否超过5min，如果超过这个时间则把 Pod 移动到 activeQ 重新调度；

PriorityQueue 还有两个方法 flushBackoffQCompleted 与 flushUnschedulablePodsLeftover。

* flushUnschedulablePodsLeftover：调度失败的 Pod 如果满足一定条件，这个函数会将这种 Pod 移动到 activeQ 或 podBackoffQ；
* flushBackoffQCompleted：运行异常的 Pod 等待时间完成后，flushBackoffQCompleted 将该 Pod 移动到 activeQ；
```go
// Run starts the goroutine to pump from podBackoffQ to activeQ
func (p *PriorityQueue) Run(logger klog.Logger) {
	go wait.Until(func() {
		p.flushBackoffQCompleted(logger)
	}, 1.0*time.Second, p.stop)
	go wait.Until(func() {
		p.flushUnschedulablePodsLeftover(logger)
	}, 30*time.Second, p.stop)
}
```

Scheduler 在启动的时候，会创建2个协程来定期运行这两个函数。除了周期性的执行上述函数，还有新节点加入集群、节点配置或状态发生变化、已经存在的 Pod 发生变化、集群内有Pod被删除等事件会触发。

## SchedulerCache

scheduler Cache 缓存 Pod，Node 等信息，各个扩展点的插件在计算时所需要的 Node 和 Pod 信息都是从 scheduler Cache 获取。Scheduler 在启动时首先会 list 一份全量的 Pod 和 Node 数据到上述的缓存中，后续通过 watch 的方式发现变化的 Node 和 Pod，然后将变化的 Node 或 Pod 更新到上述缓存中。scheduler Cache 具体在内部是一个实现了 Cache 接口的结构体 cacheImpl，如下所示：
```go
// Cache collects pods' information and provides node-level aggregated information.
// It's intended for generic scheduler to do efficient lookup.
// Cache's operations are pod centric. It does incremental updates based on pod events.
// Pod events are sent via network. We don't have guaranteed delivery of all events:
// We use Reflector to list and watch from remote.
// Reflector might be slow and do a relist, which would lead to missing events.
//
// State Machine of a pod's events in scheduler's cache:
//
//	+-------------------------------------------+  +----+
//	|                            Add            |  |    |
//	|                                           |  |    | Update
//	+      Assume                Add            v  v    |
//
// Initial +--------> Assumed +------------+---> Added <--+
//
//	^                +   +               |       +
//	|                |   |               |       |
//	|                |   |           Add |       | Remove
//	|                |   |               |       |
//	|                |   |               +       |
//	+----------------+   +-----------> Expired   +----> Deleted
//	      Forget             Expire
//
// Note that an assumed pod can expire, because if we haven't received Add event notifying us
// for a while, there might be some problems and we shouldn't keep the pod in cache anymore.
// Note that "Initial", "Expired", and "Deleted" pods do not actually exist in cache.
// Based on existing use cases, we are making the following assumptions:
//   - No pod would be assumed twice
//   - A pod could be added without going through scheduler. In this case, we will see Add but not Assume event.
//   - If a pod wasn't added, it wouldn't be removed or updated.
//   - Both "Expired" and "Deleted" are valid end states. In case of some problems, e.g. network issue,
//     a pod might have changed its state (e.g. added and deleted) without delivering notification to the cache.
type Cache interface {
	// NodeCount returns the number of nodes in the cache.
	// DO NOT use outside of tests.
	NodeCount() int

	// PodCount returns the number of pods in the cache (including those from deleted nodes).
	// DO NOT use outside of tests.
	PodCount() (int, error)

	// AssumePod assumes a pod scheduled and aggregates the pod's information into its node.
	// The implementation also decides the policy to expire pod before being confirmed (receiving Add event).
	// After expiration, its information would be subtracted.
	AssumePod(logger klog.Logger, pod *v1.Pod) error

	// FinishBinding signals that cache for assumed pod can be expired
	FinishBinding(logger klog.Logger, pod *v1.Pod) error

	// ForgetPod removes an assumed pod from cache.
	ForgetPod(logger klog.Logger, pod *v1.Pod) error

	// AddPod either confirms a pod if it's assumed, or adds it back if it's expired.
	// If added back, the pod's information would be added again.
	AddPod(logger klog.Logger, pod *v1.Pod) error

	// UpdatePod removes oldPod's information and adds newPod's information.
	UpdatePod(logger klog.Logger, oldPod, newPod *v1.Pod) error

	// RemovePod removes a pod. The pod's information would be subtracted from assigned node.
	RemovePod(logger klog.Logger, pod *v1.Pod) error

	// GetPod returns the pod from the cache with the same namespace and the
	// same name of the specified pod.
	GetPod(pod *v1.Pod) (*v1.Pod, error)

	// IsAssumedPod returns true if the pod is assumed and not expired.
	IsAssumedPod(pod *v1.Pod) (bool, error)

	// AddNode adds overall information about node.
	// It returns a clone of added NodeInfo object.
	AddNode(logger klog.Logger, node *v1.Node) *framework.NodeInfo

	// UpdateNode updates overall information about node.
	// It returns a clone of updated NodeInfo object.
	UpdateNode(logger klog.Logger, oldNode, newNode *v1.Node) *framework.NodeInfo

	// RemoveNode removes overall information about node.
	RemoveNode(logger klog.Logger, node *v1.Node) error

	// UpdateSnapshot updates the passed infoSnapshot to the current contents of Cache.
	// The node info contains aggregated information of pods scheduled (including assumed to be)
	// on this node.
	// The snapshot only includes Nodes that are not deleted at the time this function is called.
	// nodeinfo.Node() is guaranteed to be not nil for all the nodes in the snapshot.
	UpdateSnapshot(logger klog.Logger, nodeSnapshot *Snapshot) error

	// Dump produces a dump of the current cache.
	Dump() *Dump
}

type cacheImpl struct {
	stop   <-chan struct{}
	ttl    time.Duration
	period time.Duration

	// This mutex guards all fields within this cache struct.
	mu sync.RWMutex
	// a set of assumed pod keys.
	// The key could further be used to get an entry in podStates.
	assumedPods sets.Set[string]
	// a map from pod key to podState.
	podStates map[string]*podState
	nodes     map[string]*nodeInfoListItem
	// headNode points to the most recently updated NodeInfo in "nodes". It is the
	// head of the linked list.
	headNode *nodeInfoListItem
	nodeTree *nodeTree
	// A map from image name to its ImageStateSummary.
	imageStates map[string]*framework.ImageStateSummary
}
```

cacheImpl 中的 nodes 存放集群内所有 Node 信息，podStates 存放所有 Pod 信息。assumedPods 存放已经调度成功但是还没调用 kube-apiserver 的进行绑定的（也就是还没有执行 bind 插件）的Pod，需要这个缓存的原因也是为了提升调度效率，将绑定和调度分开，因为绑定需要调用 kube-apiserver，所以 Scheduler 乐观的假设调度已经成功，然后返回去调度其他 Pod，而这个 Pod 就会放入 assumedPods 中，并且也会放入到 podStates 中，后续其他 Pod 在进行调度的时候，这个 Pod 也会在插件的计算范围内（如亲和性），然后会新起协程进行最后的绑定，要是最后绑定失败了，那么这个 Pod 的信息会从 assumedPods 和 podStates 移除，并且把这个 Pod 重新放入 activeQ 中，重新被调度。

## NextPod 和 SchedulePod

Scheduler 中有个成员 NextPod 会从 activeQ 队列中尝试获取一个待调度的 Pod，该函数在 SchedulePod 中被调用，见源码 pkg/scheduler/scheduler.go，如下所示：
```go
// Run begins watching and scheduling. It starts scheduling and blocked until the context is done.
func (sched *Scheduler) Run(ctx context.Context) {
	logger := klog.FromContext(ctx)
	sched.SchedulingQueue.Run(logger)

	// We need to start scheduleOne loop in a dedicated goroutine,
	// because scheduleOne function hangs on getting the next item
	// from the SchedulingQueue.
	// If there are no new pods to schedule, it will be hanging there
	// and if done in this goroutine it will be blocking closing
	// SchedulingQueue, in effect causing a deadlock on shutdown.
	go wait.UntilWithContext(ctx, sched.ScheduleOne, 0)

	<-ctx.Done()
	sched.SchedulingQueue.Close()

	// If the plugins satisfy the io.Closer interface, they are closed.
	err := sched.Profiles.Close()
	if err != nil {
		logger.Error(err, "Failed to close plugins")
	}
}

// 尝试调度 Pod
// ScheduleOne does the entire scheduling workflow for a single pod. It is serialized on the scheduling algorithm's host fitting.
func (sched *Scheduler) ScheduleOne(ctx context.Context) {
	logger := klog.FromContext(ctx)
    // 会一直阻塞，直到获取到一个Pod
	podInfo, err := sched.NextPod(logger)
	if err != nil {
		logger.Error(err, "Error while retrieving next pod from scheduling queue")
		return
	}
	// pod could be nil when schedulerQueue is closed
	if podInfo == nil || podInfo.Pod == nil {
		return
	}

	pod := podInfo.Pod
	// TODO(knelasevero): Remove duplicated keys from log entry calls
	// When contextualized logging hits GA
	// https://github.com/kubernetes/kubernetes/issues/111672
	logger = klog.LoggerWithValues(logger, "pod", klog.KObj(pod))
	ctx = klog.NewContext(ctx, logger)
	logger.V(4).Info("About to try and schedule pod", "pod", klog.KObj(pod))

	fwk, err := sched.frameworkForPod(pod)
	if err != nil {
		// This shouldn't happen, because we only accept for scheduling the pods
		// which specify a scheduler name that matches one of the profiles.
		logger.Error(err, "Error occurred")
		return
	}
	if sched.skipPodSchedule(ctx, fwk, pod) {
		return
	}

	logger.V(3).Info("Attempting to schedule pod", "pod", klog.KObj(pod))

	// Synchronously attempt to find a fit for the pod.
	start := time.Now()
	state := framework.NewCycleState()
	state.SetRecordPluginMetrics(rand.Intn(100) < pluginMetricsSamplePercent)

	// Initialize an empty podsToActivate struct, which will be filled up by plugins or stay empty.
	podsToActivate := framework.NewPodsToActivate()
	state.Write(framework.PodsToActivateKey, podsToActivate)

	schedulingCycleCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	scheduleResult, assumedPodInfo, status := sched.schedulingCycle(schedulingCycleCtx, state, fwk, podInfo, start, podsToActivate)
	if !status.IsSuccess() {
		sched.FailureHandler(schedulingCycleCtx, fwk, assumedPodInfo, status, scheduleResult.nominatingInfo, start)
		return
	}

	// bind the pod to its host asynchronously (we can do this b/c of the assumption step above).
	go func() {
		bindingCycleCtx, cancel := context.WithCancel(ctx)
		defer cancel()

		metrics.Goroutines.WithLabelValues(metrics.Binding).Inc()
		defer metrics.Goroutines.WithLabelValues(metrics.Binding).Dec()

		status := sched.bindingCycle(bindingCycleCtx, state, fwk, scheduleResult, assumedPodInfo, start, podsToActivate)
		if !status.IsSuccess() {
			sched.handleBindingCycleError(bindingCycleCtx, state, fwk, assumedPodInfo, start, scheduleResult, status)
			return
		}
		// Usually, DonePod is called inside the scheduling queue,
		// but in this case, we need to call it here because this Pod won't go back to the scheduling queue.
		sched.SchedulingQueue.Done(assumedPodInfo.Pod.UID)
	}()
}
```

Pop 会一直阻塞，直到 activeQ 长度大于0，然后去取出一个 Pod 返回，Pod() 函数如下所示：
```go
// Pop removes the head of the active queue and returns it. It blocks if the
// activeQ is empty and waits until a new item is added to the queue. It
// increments scheduling cycle when a pod is popped.
func (p *PriorityQueue) Pop(logger klog.Logger) (*framework.QueuedPodInfo, error) {
	p.lock.Lock()
	defer p.lock.Unlock()
	for p.activeQ.Len() == 0 {
		// When the queue is empty, invocation of Pop() is blocked until new item is enqueued.
		// When Close() is called, the p.closed is set and the condition is broadcast,
		// which causes this loop to continue and return from the Pop().
		if p.closed {
			logger.V(2).Info("Scheduling queue is closed")
			return nil, nil
		}
		p.cond.Wait()
	}
	obj, err := p.activeQ.Pop()
	if err != nil {
		return nil, err
	}
	pInfo := obj.(*framework.QueuedPodInfo)
	pInfo.Attempts++
	p.schedulingCycle++
	// In flight, no concurrent events yet.
	if p.isSchedulingQueueHintEnabled {
		p.inFlightPods[pInfo.Pod.UID] = p.inFlightEvents.PushBack(pInfo.Pod)
	}

	// Update metrics and reset the set of unschedulable plugins for the next attempt.
	for plugin := range pInfo.UnschedulablePlugins.Union(pInfo.PendingPlugins) {
		metrics.UnschedulableReason(plugin, pInfo.Pod.Spec.SchedulerName).Dec()
	}
	pInfo.UnschedulablePlugins.Clear()
	pInfo.PendingPlugins.Clear()

	return pInfo, nil
}
```

## Informer

在 k8s 的所有组件包括 controller-manager，kube-proxy，kubelet 等都使用了 informer 来监听 kube-apiserver 来获取资源的变化。kube-scheduler 使用 informer 监听 Node, Pod, CSINode, CSIDriver, CSIStorageCapacity, PersistentVolume, PersistentVolumeClaim, StorageClass。为什么要监听后面那些资源呢？

后面的那些资源都是跟存储有关，在 preFilter 和 filter 扩展点的插件里面有 Volumebinding 这么一个插件，是检查系统当前是否能够满足 Pod 声明的 PVC，如果不能满足，那么只能把 Pod 放入 unscheduleableQ 里。但是如果系统可以满足 Pod 对存储的需要，Pod 需要第一时间能够被创建出来，所以系统必须要能够实时感知到系统 PVC 等资源的变化及时将 unscheduleableQ 里面调度失败的 Pod 进行重新调度。

# Pod 调度过程

Pod 是怎么被调度到某个 Node，主要步骤如下所示：
1. 【监听 Pod】从 activeQ 队列中获取需要被调度的 Pod；
2. 【取出 Pod】在调度周期（Scheduling Cycle）运行每个扩展点的所有插件，给 Pod 选择一个最合适的 Node；
3. 【调度 Pod】在绑定周期（Binding Cycle）将 Pod 绑定到选出来的 Node；

![](/images/2024-04-06-scheduler-framework-01/8.svg)

## 监听 Pod

kube-scheduler 会 list-watch Pod 事件，监测到 Pod 需要被调度后，将待调度的 Pod 分为两种情况：已经调度过的 Pod 和未调度的 Pod。
```go
// addAllEventHandlers is a helper function used in tests and in Scheduler
// to add event handlers for various informers.
func addAllEventHandlers(
	sched *Scheduler,
	informerFactory informers.SharedInformerFactory,
	dynInformerFactory dynamicinformer.DynamicSharedInformerFactory,
	gvkMap map[framework.GVK]framework.ActionType,
) error {
	var (
		handlerRegistration cache.ResourceEventHandlerRegistration
		err                 error
		handlers            []cache.ResourceEventHandlerRegistration
	)
	// scheduled pod cache
    // 已经调度过的 Pod 则加到本地缓存，并判断是加入到调度队列还是加入到backoff队列
	if handlerRegistration, err = informerFactory.Core().V1().Pods().Informer().AddEventHandler(
		cache.FilteringResourceEventHandler{
			FilterFunc: func(obj interface{}) bool {
				switch t := obj.(type) {
				case *v1.Pod:
					return assignedPod(t)
				case cache.DeletedFinalStateUnknown:
					if _, ok := t.Obj.(*v1.Pod); ok {
						// The carried object may be stale, so we don't use it to check if
						// it's assigned or not. Attempting to cleanup anyways.
						return true
					}
					utilruntime.HandleError(fmt.Errorf("unable to convert object %T to *v1.Pod in %T", obj, sched))
					return false
				default:
					utilruntime.HandleError(fmt.Errorf("unable to handle object in %T: %T", sched, obj))
					return false
				}
			},
			Handler: cache.ResourceEventHandlerFuncs{
				AddFunc:    sched.addPodToCache,
				UpdateFunc: sched.updatePodInCache,
				DeleteFunc: sched.deletePodFromCache,
			},
		},
	); err != nil {
		return err
	}
	handlers = append(handlers, handlerRegistration)

	// unscheduled pod queue
    // 没有调度过的 Pod，放到调度队列
	if handlerRegistration, err = informerFactory.Core().V1().Pods().Informer().AddEventHandler(
		cache.FilteringResourceEventHandler{
			FilterFunc: func(obj interface{}) bool {
				switch t := obj.(type) {
				case *v1.Pod:
					return !assignedPod(t) && responsibleForPod(t, sched.Profiles)
				case cache.DeletedFinalStateUnknown:
					if pod, ok := t.Obj.(*v1.Pod); ok {
						// The carried object may be stale, so we don't use it to check if
						// it's assigned or not.
						return responsibleForPod(pod, sched.Profiles)
					}
					utilruntime.HandleError(fmt.Errorf("unable to convert object %T to *v1.Pod in %T", obj, sched))
					return false
				default:
					utilruntime.HandleError(fmt.Errorf("unable to handle object in %T: %T", sched, obj))
					return false
				}
			},
			Handler: cache.ResourceEventHandlerFuncs{
				AddFunc:    sched.addPodToSchedulingQueue,
				UpdateFunc: sched.updatePodInSchedulingQueue,
				DeleteFunc: sched.deletePodFromSchedulingQueue,
			},
		},
	); err != nil {
		return err
	}
	handlers = append(handlers, handlerRegistration)

    // 监听 Node 事件
	if handlerRegistration, err = informerFactory.Core().V1().Nodes().Informer().AddEventHandler(
		cache.ResourceEventHandlerFuncs{
			AddFunc:    sched.addNodeToCache,
			UpdateFunc: sched.updateNodeInCache,
			DeleteFunc: sched.deleteNodeFromCache,
		},
	); err != nil {
		return err
	}
	handlers = append(handlers, handlerRegistration)

	logger := sched.logger
	buildEvtResHandler := func(at framework.ActionType, gvk framework.GVK, shortGVK string) cache.ResourceEventHandlerFuncs {
		funcs := cache.ResourceEventHandlerFuncs{}
		if at&framework.Add != 0 {
			evt := framework.ClusterEvent{Resource: gvk, ActionType: framework.Add, Label: fmt.Sprintf("%vAdd", shortGVK)}
			funcs.AddFunc = func(obj interface{}) {
                // 将 Pod 加入 Active 队列或者 Backoff 队列
				sched.SchedulingQueue.MoveAllToActiveOrBackoffQueue(logger, evt, nil, obj, nil)
			}
		}
		if at&framework.Update != 0 {
			evt := framework.ClusterEvent{Resource: gvk, ActionType: framework.Update, Label: fmt.Sprintf("%vUpdate", shortGVK)}
			funcs.UpdateFunc = func(old, obj interface{}) {
                // 将 Pod 加入 Active 队列或者 Backoff 队列
				sched.SchedulingQueue.MoveAllToActiveOrBackoffQueue(logger, evt, old, obj, nil)
			}
		}
		if at&framework.Delete != 0 {
			evt := framework.ClusterEvent{Resource: gvk, ActionType: framework.Delete, Label: fmt.Sprintf("%vDelete", shortGVK)}
			funcs.DeleteFunc = func(obj interface{}) {
                // 将 Pod 加入 Active 队列或者 Backoff 队列
				sched.SchedulingQueue.MoveAllToActiveOrBackoffQueue(logger, evt, obj, nil, nil)
			}
		}
		return funcs
	}

    // 监听 CSINode、CSIDriver、CSIStorageCapacity、PersistentVolume、PersistentVolumeClaim、PodSchedulingContext、
    // ResourceClaim、ResourceClass、ResourceClaimParameters、ResourceClassParameters、StorageClass 等事件
	for gvk, at := range gvkMap {
		switch gvk {
		case framework.Node, framework.Pod:
			// Do nothing.
		case framework.CSINode:
			...
		case framework.CSIDriver:
			...
		case framework.CSIStorageCapacity:
			...
		case framework.PersistentVolume:
			...
		case framework.PersistentVolumeClaim:
			...
		case framework.PodSchedulingContext:
			...
		case framework.ResourceClaim:
			...
		case framework.ResourceClass:
			...
		case framework.ResourceClaimParameters:
			...
		case framework.ResourceClassParameters:
			...
		case framework.StorageClass:
			...
		default:
			...
		}
	}
	sched.registeredHandlers = handlers
	return nil
}
```

## 已调度 Pod
```go
// assignedPod selects pods that are assigned (scheduled and running).
func assignedPod(pod *v1.Pod) bool {
	return len(pod.Spec.NodeName) != 0
}
```

通过代码 len(pod.Spec.NodeName) != 0 来判断是不是已调度过的 Pod，因为调度过的 Pod 这个字段总是会被赋予被选中的 Node 名称。但是，既然是调度过的 Pod，那代码中为什么还要区分 sched.addPodToCache 和 sched.updatePodInCache？原因在于可以在创建 Pod 时给它分配一个 Node（即给 pod.Spec.NodeName 赋值），kube-scheduler 在监听到该 Pod 后，判断这个 Pod 该字段不为空就会认为这个 Pod 已经被调度，就不太合理。

在监听到 Pod 后 sched.addPodToCache 和 sched.updatePodInCache 哪个会被调用，这是 Informer 所决定的，它会根据监听到变化的 Pod 和 Informer 的本地缓存做对比，要是缓存中没有这个 Pod，那么就调用 add 函数，否则就调用 update 函数。加入或更新缓存后，还需要去 unschedulablePods（调度失败的Pod） 中获取 Pod，这些 Pod 的亲和性和刚刚加入的这个 Pod 匹配，然后根据下面的规则判断是把 Pod 放入 backoffQ 还是放入 activeQ。

* 根据 Pod 尝试被调度的次数计算这个 Pod 下次调度应该等待的时间，计算规则为指数级增长，即按照1s、2s、4s、8s时间进行等待，但是等待时间也不会无限增加，会受到 podMaxBackoffDuration（默认10s） 限制，参数表示 Pod 处于 backoff 的最大时间，如果等待的时间如果超过了 podMaxBackoffDuration，那么就只等待 podMaxBackoffDuration 就会再次被调度；
* 当前时间 - 上次调度的时间 > 根据步骤 1 获取到的应该等待的时间，如果大于等待时间则把Pod放到activeQ里面，否则Pod被放入 backoff 队列里继续等待；

从上面可以看到，一个 Pod 的变更会触发此前调度失败的 Pod 被重新调度。

## 未调度 Pod

如果 pod.Spec.NodeName 为空，那么 Pod 可能是没有被调度过或者是此前调度过但是调度失败的，没有调度过的 Pod 直接加入到 activeQ，调度失败的 Pod 则根据上述规则判断是加入 backoffQ 队列还是 activeQ 队列，加入到 activeQ 会马上被取走，然后开始调度。因为调度失败而被放入 unscheduleable 的 Pod 还可以重新被调度么，有两种途径可以实现重新被调度。

* 定期将 unscheduleable 的 Pod 放入 backoffQ 或 activeQ，或者定期将 backoffQ 等待超时的 Pod 放入 activeQ；
* 集群内其他相关资源（Node、Pod、CSI等）发生变化时，判断 unscheduleable 中的 Pod 是不是要放入 backoffQ 或 activeQ；

对于第一种方式，在 kube-scheduler 启动的时候中会起两个协程，周期性将不可调度的 Pod 放入 backoffQ 或者 activeQ 队列，或者将 backoffQ 中超时的 Pod 放入 activeQ 队列；
```go
// Run starts the goroutine to pump from podBackoffQ to activeQ
func (p *PriorityQueue) Run(logger klog.Logger) {
	go wait.Until(func() {
		p.flushBackoffQCompleted(logger)
	}, 1.0*time.Second, p.stop)
	go wait.Until(func() {
		p.flushUnschedulablePodsLeftover(logger)
	}, 30*time.Second, p.stop)
}

// flushBackoffQCompleted Moves all pods from backoffQ which have completed backoff in to activeQ
func (p *PriorityQueue) flushBackoffQCompleted(logger klog.Logger) {
	p.lock.Lock()
	defer p.lock.Unlock()
	activated := false
	for {
		rawPodInfo := p.podBackoffQ.Peek()
		if rawPodInfo == nil {
			break
		}
		pInfo := rawPodInfo.(*framework.QueuedPodInfo)
		pod := pInfo.Pod
		if p.isPodBackingoff(pInfo) {
			break
		}
		_, err := p.podBackoffQ.Pop()
		if err != nil {
			logger.Error(err, "Unable to pop pod from backoff queue despite backoff completion", "pod", klog.KObj(pod))
			break
		}
		if added, _ := p.addToActiveQ(logger, pInfo); added {
			logger.V(5).Info("Pod moved to an internal scheduling queue", "pod", klog.KObj(pod), "event", BackoffComplete, "queue", activeQ)
			metrics.SchedulerQueueIncomingPods.WithLabelValues("active", BackoffComplete).Inc()
			activated = true
		}
	}

	if activated {
		p.cond.Broadcast()
	}
}

// flushUnschedulablePodsLeftover moves pods which stay in unschedulablePods
// longer than podMaxInUnschedulablePodsDuration to backoffQ or activeQ.
func (p *PriorityQueue) flushUnschedulablePodsLeftover(logger klog.Logger) {
	p.lock.Lock()
	defer p.lock.Unlock()

	var podsToMove []*framework.QueuedPodInfo
	currentTime := p.clock.Now()
	for _, pInfo := range p.unschedulablePods.podInfoMap {
		lastScheduleTime := pInfo.Timestamp
        
        // 	DefaultPodMaxInUnschedulablePodsDuration time.Duration = 5 * time.Minute
        
		if currentTime.Sub(lastScheduleTime) > p.podMaxInUnschedulablePodsDuration {
			podsToMove = append(podsToMove, pInfo)
		}
	}

	if len(podsToMove) > 0 {
		p.movePodsToActiveOrBackoffQueue(logger, podsToMove, UnschedulableTimeout, nil, nil)
	}
}
```

flushBackoffQCompleted 去 backoffQ 获取等待结束的 Pod，放入 activeQ 队列。将在 unscheduleable 里面停留时长超过 podMaxInUnschedulablePodsDuration（默认是 5min）的pod放入到 ActiveQ 或 BackoffQueue，具体是放到哪个队列里面，还是根据上文说的计算规则进行判断。

第二种方式，Kubernetes 集群中的资源发生变更会触发 Pod 被重新调度，如新增或者删除Node、Node 配置发生变更、已存在的 Pod 发生变更、新增或者删除 Pod、PV与PVC发生变更。Node 节点事件（新增 Node 节点、Node 节点配置更新等事件）。
```go
func addAllEventHandlers(
    sched *Scheduler,
    informerFactory informers.SharedInformerFactory,
    dynInformerFactory dynamicinformer.DynamicSharedInformerFactory,
    gvkMap map[framework.GVK]framework.ActionType,
) error {
if handlerRegistration, err = informerFactory.Core().V1().Nodes().Informer().AddEventHandler(
		cache.ResourceEventHandlerFuncs{
			AddFunc:    sched.addNodeToCache,
			UpdateFunc: sched.updateNodeInCache,
			DeleteFunc: sched.deleteNodeFromCache,
		},
	); err != nil {
		return err
	}
	handlers = append(handlers, handlerRegistration)
    ......
}

func (sched *Scheduler) addNodeToCache(obj interface{}) {
	logger := sched.logger
	node, ok := obj.(*v1.Node)
	if !ok {
		logger.Error(nil, "Cannot convert to *v1.Node", "obj", obj)
		return
	}

	logger.V(3).Info("Add event for node", "node", klog.KObj(node))
	nodeInfo := sched.Cache.AddNode(logger, node)
	sched.SchedulingQueue.MoveAllToActiveOrBackoffQueue(logger, queue.NodeAdd, nil, node, preCheckForNode(nodeInfo))
}

func preCheckForNode(nodeInfo *framework.NodeInfo) queue.PreEnqueueCheck {
	// Note: the following checks doesn't take preemption into considerations, in very rare
	// cases (e.g., node resizing), "pod" may still fail a check but preemption helps. We deliberately
	// chose to ignore those cases as unschedulable pods will be re-queued eventually.
	return func(pod *v1.Pod) bool {
		admissionResults := AdmissionCheck(pod, nodeInfo, false)
		if len(admissionResults) != 0 {
			return false
		}
		_, isUntolerated := corev1helpers.FindMatchingUntoleratedTaint(nodeInfo.Node().Spec.Taints, pod.Spec.Tolerations, func(t *v1.Taint) bool {
			return t.Effect == v1.TaintEffectNoSchedule
		})
		return !isUntolerated
	}
}

// AdmissionCheck calls the filtering logic of noderesources/nodeport/nodeAffinity/nodename
// and returns the failure reasons. It's used in kubelet(pkg/kubelet/lifecycle/predicate.go) and scheduler.
// It returns the first failure if `includeAllFailures` is set to false; otherwise
// returns all failures.
func AdmissionCheck(pod *v1.Pod, nodeInfo *framework.NodeInfo, includeAllFailures bool) []AdmissionResult {
    var admissionResults []AdmissionResult
    insufficientResources := noderesources.Fits(pod, nodeInfo)
    // 判断资源是否足够 
    if len(insufficientResources) != 0 {
        for i := range insufficientResources {
            admissionResults = append(admissionResults, AdmissionResult{InsufficientResource: &insufficientResources[i]})
        }
        if !includeAllFailures {
            return admissionResults
        }
    }
    // Node 节点亲和性
    if matches, _ := corev1nodeaffinity.GetRequiredNodeAffinity(pod).Match(nodeInfo.Node()); !matches {
        admissionResults = append(admissionResults, AdmissionResult{Name: nodeaffinity.Name, Reason: nodeaffinity.ErrReasonPod})
        if !includeAllFailures {
            return admissionResults
        }
    }
    // 判断 Node Name 是否匹配 
    if !nodename.Fits(pod, nodeInfo) {
        admissionResults = append(admissionResults, AdmissionResult{Name: nodename.Name, Reason: nodename.ErrReason})
        if !includeAllFailures {
            return admissionResults
        }
    }
    // 判断节点 port 端口是否匹配
    if !nodeports.Fits(pod, nodeInfo) {
        admissionResults = append(admissionResults, AdmissionResult{Name: nodeports.Name, Reason: nodeports.ErrReason})
        if !includeAllFailures {
            return admissionResults
        }
    }
    return admissionResults
}

func (sched *Scheduler) updateNodeInCache(oldObj, newObj interface{}) {
    logger := sched.logger
    oldNode, ok := oldObj.(*v1.Node)
    if !ok {
        logger.Error(nil, "Cannot convert oldObj to *v1.Node", "oldObj", oldObj)
        return
    }
    newNode, ok := newObj.(*v1.Node)
    if !ok {
        logger.Error(nil, "Cannot convert newObj to *v1.Node", "newObj", newObj)
        return
    }

    logger.V(4).Info("Update event for node", "node", klog.KObj(newNode))
    nodeInfo := sched.Cache.UpdateNode(logger, oldNode, newNode)
    // Only requeue unschedulable pods if the node became more schedulable.
    for _, evt := range nodeSchedulingPropertiesChange(newNode, oldNode) {
        sched.SchedulingQueue.MoveAllToActiveOrBackoffQueue(logger, evt, oldNode, newNode, preCheckForNode(nodeInfo))
    }
}

func nodeSchedulingPropertiesChange(newNode *v1.Node, oldNode *v1.Node) []framework.ClusterEvent {
	var events []framework.ClusterEvent
    // 节点可调度变更
	if nodeSpecUnschedulableChanged(newNode, oldNode) {
		events = append(events, queue.NodeSpecUnschedulableChange)
	}
    // 节点可分配资源变更
	if nodeAllocatableChanged(newNode, oldNode) {
		events = append(events, queue.NodeAllocatableChange)
	}
    // 节点标签变更
	if nodeLabelsChanged(newNode, oldNode) {
		events = append(events, queue.NodeLabelChange)
	}
    // 节点污点变更
	if nodeTaintsChanged(newNode, oldNode) {
		events = append(events, queue.NodeTaintChange)
	}
    // 节点状态变更
	if nodeConditionsChanged(newNode, oldNode) {
		events = append(events, queue.NodeConditionChange)
	}
    // 节点注解变更
	if nodeAnnotationsChanged(newNode, oldNode) {
		events = append(events, queue.NodeAnnotationChange)
	}
	return events
}
```

当新增 Node 节点时，以下因素可能会触发未被调度的Pod加入到 backoffQ 队列或者 activeQ 队列。
* Pod 对 Node 节点的亲和性；
* Pod 中 Nodename 不为空，判断新加入节点的 Name 与 pod Nodename 是否相等；
* 判断 Pod 中容器对端口的要求是否和新加入节点已经被使用的端口冲突；
* Pod 是否容忍了 Node 的已调度的 Pod；

当 Node 节点配置发生变更时，以下因素可能会触发未被调度的Pod加入到 backoffQ 队列或者 activeQ 队列。
* 节点可调度变更
* 节点可分配资源变更
* 节点标签变更
* 节点污点变更
* 节点状态变更
* 节点注解变更

Pod 事件（新增 Pod、删除 Pod 等事件）。已经存在的Pod发生变更后，会把这个Pod亲和性配置依次和 unscheduleable 里面的Pod匹配，如果能够匹配上，那么Pod更新这个事件才会触发这个未被调度的Pod加入到 backoffQ 队列或者 activeQ 队列。
```go
// addAllEventHandlers is a helper function used in tests and in Scheduler
// to add event handlers for various informers.
func addAllEventHandlers(
	sched *Scheduler,
	informerFactory informers.SharedInformerFactory,
	dynInformerFactory dynamicinformer.DynamicSharedInformerFactory,
	gvkMap map[framework.GVK]framework.ActionType,
) error {
	// scheduled pod cache
	if handlerRegistration, err = informerFactory.Core().V1().Pods().Informer().AddEventHandler(
		cache.FilteringResourceEventHandler{
			Handler: cache.ResourceEventHandlerFuncs{
				AddFunc:    sched.addPodToCache,
				UpdateFunc: sched.updatePodInCache,
				DeleteFunc: sched.deletePodFromCache,
			},
		},
	); err != nil {
		return err
	}
}

// 添加 Pod 事件
func (sched *Scheduler) addPodToCache(obj interface{}) {
	logger := sched.logger
	pod, ok := obj.(*v1.Pod)
	if !ok {
		logger.Error(nil, "Cannot convert to *v1.Pod", "obj", obj)
		return
	}

	logger.V(3).Info("Add event for scheduled pod", "pod", klog.KObj(pod))
	if err := sched.Cache.AddPod(logger, pod); err != nil {
		logger.Error(err, "Scheduler cache AddPod failed", "pod", klog.KObj(pod))
	}

	sched.SchedulingQueue.AssignedPodAdded(logger, pod)
}

// AssignedPodAdded is called when a bound pod is added. Creation of this pod
// may make pending pods with matching affinity terms schedulable.
func (p *PriorityQueue) AssignedPodAdded(logger klog.Logger, pod *v1.Pod) {
	p.lock.Lock()
	p.movePodsToActiveOrBackoffQueue(logger, p.getUnschedulablePodsWithMatchingAffinityTerm(logger, pod), AssignedPodAdd, nil, pod)
	p.lock.Unlock()
}

// 更新 Pod 事件
func (sched *Scheduler) updatePodInCache(oldObj, newObj interface{}) {
    logger := sched.logger
    oldPod, ok := oldObj.(*v1.Pod)
    if !ok {
        logger.Error(nil, "Cannot convert oldObj to *v1.Pod", "oldObj", oldObj)
        return
    }
    newPod, ok := newObj.(*v1.Pod)
    if !ok {
        logger.Error(nil, "Cannot convert newObj to *v1.Pod", "newObj", newObj)
        return
    }

    logger.V(4).Info("Update event for scheduled pod", "pod", klog.KObj(oldPod))
    if err := sched.Cache.UpdatePod(logger, oldPod, newPod); err != nil {
        logger.Error(err, "Scheduler cache UpdatePod failed", "pod", klog.KObj(oldPod))
    }

    sched.SchedulingQueue.AssignedPodUpdated(logger, oldPod, newPod)
}

// AssignedPodUpdated is called when a bound pod is updated. Change of labels
// may make pending pods with matching affinity terms schedulable.
func (p *PriorityQueue) AssignedPodUpdated(logger klog.Logger, oldPod, newPod *v1.Pod) {
    p.lock.Lock()
    if isPodResourcesResizedDown(newPod) {
        p.moveAllToActiveOrBackoffQueue(logger, AssignedPodUpdate, oldPod, newPod, nil)
    } else {
        p.movePodsToActiveOrBackoffQueue(logger, p.getUnschedulablePodsWithMatchingAffinityTerm(logger, newPod), AssignedPodUpdate, oldPod, newPod)
    }
    p.lock.Unlock()
}

// getUnschedulablePodsWithMatchingAffinityTerm returns unschedulable pods which have
// any affinity term that matches "pod".
// NOTE: this function assumes lock has been acquired in caller.
func (p *PriorityQueue) getUnschedulablePodsWithMatchingAffinityTerm(logger klog.Logger, pod *v1.Pod) []*framework.QueuedPodInfo {
	nsLabels := interpodaffinity.GetNamespaceLabelsSnapshot(logger, pod.Namespace, p.nsLister)

	var podsToMove []*framework.QueuedPodInfo
	for _, pInfo := range p.unschedulablePods.podInfoMap {
		for _, term := range pInfo.RequiredAffinityTerms {
			if term.Matches(pod, nsLabels) {
				podsToMove = append(podsToMove, pInfo)
				break
			}
		}

	}
	return podsToMove
}

// 删除 Pod 事件
func (sched *Scheduler) deletePodFromCache(obj interface{}) {
	logger := sched.logger
	var pod *v1.Pod
	switch t := obj.(type) {
	case *v1.Pod:
		pod = t
	case cache.DeletedFinalStateUnknown:
		var ok bool
		pod, ok = t.Obj.(*v1.Pod)
		if !ok {
			logger.Error(nil, "Cannot convert to *v1.Pod", "obj", t.Obj)
			return
		}
	default:
		logger.Error(nil, "Cannot convert to *v1.Pod", "obj", t)
		return
	}

	logger.V(3).Info("Delete event for scheduled pod", "pod", klog.KObj(pod))
	if err := sched.Cache.RemovePod(logger, pod); err != nil {
		logger.Error(err, "Scheduler cache RemovePod failed", "pod", klog.KObj(pod))
	}

    // preCheckForNode 为空
	sched.SchedulingQueue.MoveAllToActiveOrBackoffQueue(logger, queue.AssignedPodDelete, pod, nil, nil)
}
```

可以看到Pod删除事件不像其他事件需要做额外的判断，这个preCheck函数是空的，所有 unscheduleable 里面的Pod都会被放到 activeQ 队列或 backoffQ 队列中。

## 取出 Pod

Scheduler 中有个成员 NextPod 会从 activeQ 队列中尝试获取一个待调度的 Pod，该函数在 SchedulePod 中被调用。见源码 pkg/scheduler/scheduler.go，如下所示：
```go
// Run begins watching and scheduling. It starts scheduling and blocked until the context is done.
// 启动 Scheduler
func (sched *Scheduler) Run(ctx context.Context) {
    logger := klog.FromContext(ctx)
    sched.SchedulingQueue.Run(logger)

    // We need to start scheduleOne loop in a dedicated goroutine,
    // because scheduleOne function hangs on getting the next item
    // from the SchedulingQueue.
    // If there are no new pods to schedule, it will be hanging there
    // and if done in this goroutine it will be blocking closing
    // SchedulingQueue, in effect causing a deadlock on shutdown.
    go wait.UntilWithContext(ctx, sched.ScheduleOne, 0)

    <-ctx.Done()
    sched.SchedulingQueue.Close()

    // If the plugins satisfy the io.Closer interface, they are closed.
    err := sched.Profiles.Close()
    if err != nil {
        logger.Error(err, "Failed to close plugins")
    }
}

// 尝试调度 Pod
// ScheduleOne does the entire scheduling workflow for a single pod. It is serialized on the scheduling algorithm's host fitting.
func (sched *Scheduler) ScheduleOne(ctx context.Context) {
    // 会一直阻塞，直到获取到一个Pod
    ......
    // NextPod 对应于 PriorityQueue 的 Pop 函数
    podInfo, err := sched.NextPod(logger)
    if err != nil {
        logger.Error(err, "Error while retrieving next pod from scheduling queue")
        return
    }
    pod := podInfo.Pod
    ......
}
```

Pop 会一直阻塞，直到 activeQ 长度大于0，然后去取出一个 Pod 返回，Pod() 函数如下所示：
```go
// Pop removes the head of the active queue and returns it. It blocks if the
// activeQ is empty and waits until a new item is added to the queue. It
// increments scheduling cycle when a pod is popped.
func (p *PriorityQueue) Pop(logger klog.Logger) (*framework.QueuedPodInfo, error) {
	p.lock.Lock()
	defer p.lock.Unlock()
	for p.activeQ.Len() == 0 {
		// When the queue is empty, invocation of Pop() is blocked until new item is enqueued.
		// When Close() is called, the p.closed is set and the condition is broadcast,
		// which causes this loop to continue and return from the Pop().
		if p.closed {
			logger.V(2).Info("Scheduling queue is closed")
			return nil, nil
		}
		p.cond.Wait()
	}
	obj, err := p.activeQ.Pop()
	if err != nil {
		return nil, err
	}
	pInfo := obj.(*framework.QueuedPodInfo)
	pInfo.Attempts++
	p.schedulingCycle++
	// In flight, no concurrent events yet.
	if p.isSchedulingQueueHintEnabled {
		p.inFlightPods[pInfo.Pod.UID] = p.inFlightEvents.PushBack(pInfo.Pod)
	}

	// Update metrics and reset the set of unschedulable plugins for the next attempt.
	for plugin := range pInfo.UnschedulablePlugins.Union(pInfo.PendingPlugins) {
		metrics.UnschedulableReason(plugin, pInfo.Pod.Spec.SchedulerName).Dec()
	}
	pInfo.UnschedulablePlugins.Clear()
	pInfo.PendingPlugins.Clear()

	return pInfo, nil
}
```

## 调度 Pod

源码见 pkg/scheduler/schedule_one.go，调度 Pod 到 Node 的过程如下所示：
```go
// ScheduleOne does the entire scheduling workflow for a single pod. It is serialized on the scheduling algorithm's host fitting.
func (sched *Scheduler) ScheduleOne(ctx context.Context) {
	logger := klog.FromContext(ctx)
    // 取出 Pod
	podInfo, err := sched.NextPod(logger)
	if err != nil {
		logger.Error(err, "Error while retrieving next pod from scheduling queue")
		return
	}
	// pod could be nil when schedulerQueue is closed
	if podInfo == nil || podInfo.Pod == nil {
		return
	}

	pod := podInfo.Pod
	// TODO(knelasevero): Remove duplicated keys from log entry calls
	// When contextualized logging hits GA
	// https://github.com/kubernetes/kubernetes/issues/111672
	logger = klog.LoggerWithValues(logger, "pod", klog.KObj(pod))
	ctx = klog.NewContext(ctx, logger)
	logger.V(4).Info("About to try and schedule pod", "pod", klog.KObj(pod))

    // 根据 Pod 名称，获取初始化好的调度框架（framework）
	fwk, err := sched.frameworkForPod(pod)
	if err != nil {
		// This shouldn't happen, because we only accept for scheduling the pods
		// which specify a scheduler name that matches one of the profiles.
		logger.Error(err, "Error occurred")
		return
	}
	if sched.skipPodSchedule(ctx, fwk, pod) {
		return
	}

	logger.V(3).Info("Attempting to schedule pod", "pod", klog.KObj(pod))

	// Synchronously attempt to find a fit for the pod.
	start := time.Now()
	state := framework.NewCycleState()
    // 记录指标
	state.SetRecordPluginMetrics(rand.Intn(100) < pluginMetricsSamplePercent)

	// Initialize an empty podsToActivate struct, which will be filled up by plugins or stay empty.
	podsToActivate := framework.NewPodsToActivate()
	state.Write(framework.PodsToActivateKey, podsToActivate)

	schedulingCycleCtx, cancel := context.WithCancel(ctx)
	defer cancel()

    // 开始执行调度周期
	scheduleResult, assumedPodInfo, status := sched.schedulingCycle(schedulingCycleCtx, state, fwk, podInfo, start, podsToActivate)
	if !status.IsSuccess() {
        // 如果获取节点失败，则开始运行 postFilter 开始抢占 Pod
		sched.FailureHandler(schedulingCycleCtx, fwk, assumedPodInfo, status, scheduleResult.nominatingInfo, start)
		return
	}

	// bind the pod to its host asynchronously (we can do this b/c of the assumption step above).
    // 主流程到了这里就结束了，然后开始新的一轮调度; 启动一个协程，开始绑定;
	go func() {
		bindingCycleCtx, cancel := context.WithCancel(ctx)
		defer cancel()

		metrics.Goroutines.WithLabelValues(metrics.Binding).Inc()
		defer metrics.Goroutines.WithLabelValues(metrics.Binding).Dec()

        // 开始绑定周期 bindingCycle
		status := sched.bindingCycle(bindingCycleCtx, state, fwk, scheduleResult, assumedPodInfo, start, podsToActivate)
		if !status.IsSuccess() {
			sched.handleBindingCycleError(bindingCycleCtx, state, fwk, assumedPodInfo, start, scheduleResult, status)
			return
		}
		// Usually, DonePod is called inside the scheduling queue,
		// but in this case, we need to call it here because this Pod won't go back to the scheduling queue.
		sched.SchedulingQueue.Done(assumedPodInfo.Pod.UID)
	}()
}
```

源码见 pkg/scheduler/schedule_one.go，调度 Pod 到 Node 的调度周期如下所示：
```go
// schedulingCycle tries to schedule a single Pod.
func (sched *Scheduler) schedulingCycle(
	ctx context.Context,
	state *framework.CycleState,
	fwk framework.Framework,
	podInfo *framework.QueuedPodInfo,
	start time.Time,
	podsToActivate *framework.PodsToActivate,
) (ScheduleResult, *framework.QueuedPodInfo, *framework.Status) {
	logger := klog.FromContext(ctx)
	pod := podInfo.Pod
    // 开始执行插件，包括 filter, socre 两个扩展点内的所有插件，获取一个最合适 Pod 的节点
	scheduleResult, err := sched.SchedulePod(ctx, fwk, state, pod)
	if err != nil {
		defer func() {
			metrics.SchedulingAlgorithmLatency.Observe(metrics.SinceInSeconds(start))
		}()
		if err == ErrNoNodesAvailable {
			status := framework.NewStatus(framework.UnschedulableAndUnresolvable).WithError(err)
			return ScheduleResult{nominatingInfo: clearNominatedNode}, podInfo, status
		}

		fitError, ok := err.(*framework.FitError)
		if !ok {
			logger.Error(err, "Error selecting node for pod", "pod", klog.KObj(pod))
			return ScheduleResult{nominatingInfo: clearNominatedNode}, podInfo, framework.AsStatus(err)
		}

		// SchedulePod() may have failed because the pod would not fit on any host, so we try to
		// preempt, with the expectation that the next time the pod is tried for scheduling it
		// will fit due to the preemption. It is also possible that a different pod will schedule
		// into the resources that were preempted, but this is harmless.

		if !fwk.HasPostFilterPlugins() {
			logger.V(3).Info("No PostFilter plugins are registered, so no preemption will be performed")
			return ScheduleResult{}, podInfo, framework.NewStatus(framework.Unschedulable).WithError(err)
		}

		// Run PostFilter plugins to attempt to make the pod schedulable in a future scheduling cycle.
        // 如果获取节点失败，则开始运行 postFilter 开始抢占一个 Pod
		result, status := fwk.RunPostFilterPlugins(ctx, state, pod, fitError.Diagnosis.NodeToStatusMap)
		msg := status.Message()
		fitError.Diagnosis.PostFilterMsg = msg
		if status.Code() == framework.Error {
			logger.Error(nil, "Status after running PostFilter plugins for pod", "pod", klog.KObj(pod), "status", msg)
		} else {
			logger.V(5).Info("Status after running PostFilter plugins for pod", "pod", klog.KObj(pod), "status", msg)
		}

		var nominatingInfo *framework.NominatingInfo
		if result != nil {
			nominatingInfo = result.NominatingInfo
		}
		return ScheduleResult{nominatingInfo: nominatingInfo}, podInfo, framework.NewStatus(framework.Unschedulable).WithError(err)
	}

	metrics.SchedulingAlgorithmLatency.Observe(metrics.SinceInSeconds(start))
	// Tell the cache to assume that a pod now is running on a given node, even though it hasn't been bound yet.
	// This allows us to keep scheduling without waiting on binding to occur.
	assumedPodInfo := podInfo.DeepCopy()
	assumedPod := assumedPodInfo.Pod
	// assume modifies `assumedPod` by setting NodeName=scheduleResult.SuggestedHost
    
    // 将 Pod 放入 assumedPod，即乐观假设 Pod 已经调度成功
	err = sched.assume(logger, assumedPod, scheduleResult.SuggestedHost)
	if err != nil {
		// This is most probably result of a BUG in retrying logic.
		// We report an error here so that pod scheduling can be retried.
		// This relies on the fact that Error will check if the pod has been bound
		// to a node and if so will not add it back to the unscheduled pods queue
		// (otherwise this would cause an infinite loop).
		return ScheduleResult{nominatingInfo: clearNominatedNode}, assumedPodInfo, framework.AsStatus(err)
	}

	// Run the Reserve method of reserve plugins.
    // 运行 Reserve 插件
	if sts := fwk.RunReservePluginsReserve(ctx, state, assumedPod, scheduleResult.SuggestedHost); !sts.IsSuccess() {
		// trigger un-reserve to clean up state associated with the reserved Pod
		fwk.RunReservePluginsUnreserve(ctx, state, assumedPod, scheduleResult.SuggestedHost)
		if forgetErr := sched.Cache.ForgetPod(logger, assumedPod); forgetErr != nil {
			logger.Error(forgetErr, "Scheduler cache ForgetPod failed")
		}

		if sts.IsRejected() {
			fitErr := &framework.FitError{
				NumAllNodes: 1,
				Pod:         pod,
				Diagnosis: framework.Diagnosis{
					NodeToStatusMap: framework.NodeToStatusMap{scheduleResult.SuggestedHost: sts},
				},
			}
			fitErr.Diagnosis.AddPluginStatus(sts)
			return ScheduleResult{nominatingInfo: clearNominatedNode}, assumedPodInfo, framework.NewStatus(sts.Code()).WithError(fitErr)
		}
		return ScheduleResult{nominatingInfo: clearNominatedNode}, assumedPodInfo, sts
	}

	// Run "permit" plugins.
    // 运行 Permit 插件
	runPermitStatus := fwk.RunPermitPlugins(ctx, state, assumedPod, scheduleResult.SuggestedHost)
	if !runPermitStatus.IsWait() && !runPermitStatus.IsSuccess() {
		// trigger un-reserve to clean up state associated with the reserved Pod
		fwk.RunReservePluginsUnreserve(ctx, state, assumedPod, scheduleResult.SuggestedHost)
		if forgetErr := sched.Cache.ForgetPod(logger, assumedPod); forgetErr != nil {
			logger.Error(forgetErr, "Scheduler cache ForgetPod failed")
		}

		if runPermitStatus.IsRejected() {
			fitErr := &framework.FitError{
				NumAllNodes: 1,
				Pod:         pod,
				Diagnosis: framework.Diagnosis{
					NodeToStatusMap: framework.NodeToStatusMap{scheduleResult.SuggestedHost: runPermitStatus},
				},
			}
			fitErr.Diagnosis.AddPluginStatus(runPermitStatus)
			return ScheduleResult{nominatingInfo: clearNominatedNode}, assumedPodInfo, framework.NewStatus(runPermitStatus.Code()).WithError(fitErr)
		}

		return ScheduleResult{nominatingInfo: clearNominatedNode}, assumedPodInfo, runPermitStatus
	}

	// At the end of a successful scheduling cycle, pop and move up Pods if needed.
	if len(podsToActivate.Map) != 0 {
		sched.SchedulingQueue.Activate(logger, podsToActivate.Map)
		// Clear the entries after activation.
		podsToActivate.Map = make(map[string]*v1.Pod)
	}

	return scheduleResult, assumedPodInfo, nil
}
```

源码见 pkg/scheduler/schedule_one.go，调度 Pod 到 Node 的绑定周期如下所示：
```go
// bindingCycle tries to bind an assumed Pod.
func (sched *Scheduler) bindingCycle(
	ctx context.Context,
	state *framework.CycleState,
	fwk framework.Framework,
	scheduleResult ScheduleResult,
	assumedPodInfo *framework.QueuedPodInfo,
	start time.Time,
	podsToActivate *framework.PodsToActivate) *framework.Status {
	logger := klog.FromContext(ctx)

	assumedPod := assumedPodInfo.Pod

	// Run "permit" plugins.
    // 执行 permit 插件
	if status := fwk.WaitOnPermit(ctx, assumedPod); !status.IsSuccess() {
		if status.IsRejected() {
			fitErr := &framework.FitError{
				NumAllNodes: 1,
				Pod:         assumedPodInfo.Pod,
				Diagnosis: framework.Diagnosis{
					NodeToStatusMap:      framework.NodeToStatusMap{scheduleResult.SuggestedHost: status},
					UnschedulablePlugins: sets.New(status.Plugin()),
				},
			}
			return framework.NewStatus(status.Code()).WithError(fitErr)
		}
		return status
	}

	// Run "prebind" plugins.
    // 执行 preBind 插件
	if status := fwk.RunPreBindPlugins(ctx, state, assumedPod, scheduleResult.SuggestedHost); !status.IsSuccess() {
		return status
	}

	// Run "bind" plugins.
    // 执行 bind 插件，会调用 kube-apiserver 把调度结果写入 etcd，就是给 Pod 赋予 NodeName
	if status := sched.bind(ctx, fwk, assumedPod, scheduleResult.SuggestedHost, state); !status.IsSuccess() {
		return status
	}

	// Calculating nodeResourceString can be heavy. Avoid it if klog verbosity is below 2.
	logger.V(2).Info("Successfully bound pod to node", "pod", klog.KObj(assumedPod), "node", scheduleResult.SuggestedHost, "evaluatedNodes", scheduleResult.EvaluatedNodes, "feasibleNodes", scheduleResult.FeasibleNodes)
	metrics.PodScheduled(fwk.ProfileName(), metrics.SinceInSeconds(start))
	metrics.PodSchedulingAttempts.Observe(float64(assumedPodInfo.Attempts))
	if assumedPodInfo.InitialAttemptTimestamp != nil {
		metrics.PodSchedulingDuration.WithLabelValues(getAttemptsLabel(assumedPodInfo)).Observe(metrics.SinceInSeconds(*assumedPodInfo.InitialAttemptTimestamp))
		metrics.PodSchedulingSLIDuration.WithLabelValues(getAttemptsLabel(assumedPodInfo)).Observe(metrics.SinceInSeconds(*assumedPodInfo.InitialAttemptTimestamp))
	}
	// Run "postbind" plugins.
    // 执行 postbind 插件
	fwk.RunPostBindPlugins(ctx, state, assumedPod, scheduleResult.SuggestedHost)

	// At the end of a successful binding cycle, move up Pods if needed.
	if len(podsToActivate.Map) != 0 {
		sched.SchedulingQueue.Activate(logger, podsToActivate.Map)
		// Unlike the logic in schedulingCycle(), we don't bother deleting the entries
		// as `podsToActivate.Map` is no longer consumed.
	}

	return nil
}
```

Pod 调度到 Node 上的流程可以简述如下：
* informer 监听到了有新建 Pod，根据 Pod 的优先级把 Pod 加入到 activeQ 中适当位置（即执行sort插件）；
* scheduler 从 activeQ 队头取一个Pod（如果队列没有Pod可取，则会一直阻塞）；
* 执行 filter 类型扩展点（包括preFilter、filter、postFilter）插件，选出所有符合 Pod 的 Node，如果无法找到符合的 Node， 则把 Pod 加入 unscheduleableQ 中，此次调度结束；
* 执行 score 扩展点插件，找出最符合 Pod 的 那个Node；
* assume Pod 这一步就是乐观假设 Pod 已经调度成功，更新缓存中 Node 和 PodStats 信息，scheduling cycle 周期就已经结束，然后会开启新的一轮调度；至于真正的绑定，则会新起一个协程；
* 执行 reserve 插件；
* 启动协程绑定 Pod 到 Node上。实际上就是修改 Pod.spec.nodeName，然后调用 kube-apiserver 接口写入 etcd。如果绑定失败，那么移除缓存中此前加入的信息，然后把 Pod 放入activeQ 中，后续重新调度；
* 执行 postBinding；

# 常见问题

1、preFilter 与 Filter 有什么区别？

像我们常见的 nodeSelector/Pod Affinity 等使用的是 PreFilter，而像 nodeName 使用的是 Filter。

2、直接在 Pod Spec 模板下填写 nodeName 字段，Pod 调度还会经过 Scheduler 调度周期与绑定周期？

会经过 Scheduler Framework 调度周期，以 Kubernetes 1.26.9 源码为例，见 [https://github.com/kubernetes/kubernetes/blob/v1.26.9/pkg/scheduler/eventhandlers.go#L186](https://github.com/kubernetes/kubernetes/blob/v1.26.9/pkg/scheduler/eventhandlers.go#L186)，当调整 kube-scheduler 日志等级 v=10 时，kube-scheduler 日志依然可以监听 Add/Update/Delete Pod 事件，如下所示：

```bash
I0417 11:40:02.160555       1 eventhandlers.go:186] "Add event for scheduled pod" pod="default/nginx-cb8956d5f-g6zzq"
I0417 11:40:02.185169       1 eventhandlers.go:206] "Update event for scheduled pod" pod="default/nginx-cb8956d5f-g6zzq"
I0417 11:40:02.757130       1 eventhandlers.go:206] "Update event for scheduled pod" pod="default/nginx-cb8956d5f-g6zzq"
```

kubelet 的日志如下所示：
```bash
kubelet 的日志如下所示：
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.298368    4170 kubelet.go:2199] "SyncLoop ADD" source="api" pods="[default/nginx-cb8956d5f-c5zh8]"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.298414    4170 topology_manager.go:210] "Topology Admit Handler" podUID=d054e76b-1d9b-4788-9fc7-b35165ab02fb podNamespace="default" podName="nginx-cb8956d5f-c5zh8"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: E0417 19:46:19.298465    4170 cpu_manager.go:395] "RemoveStaleState: removing container" podUID="2e6143f6-fb20-4707-8497-5613b46f6292" containerName="nginx"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.298475    4170 state_mem.go:107] "Deleted CPUSet assignment" podUID="2e6143f6-fb20-4707-8497-5613b46f6292" containerName="nginx"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.298521    4170 memory_manager.go:346] "RemoveStaleState removing state" podUID="2e6143f6-fb20-4707-8497-5613b46f6292" containerName="nginx"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.419170    4170 reconciler_common.go:253] "operationExecutor.VerifyControllerAttachedVolume started for volume \"kube-api-access-kq8x5\" (UniqueName: \"kubernetes.io/projected/d054e76b-1d9b-4788-9fc7-b35165ab02fb-kube-api-access-kq8x5\") pod \"nginx-cb8956d5f-c5zh8\" (UID: \"d054e76b-1d9b-4788-9fc7-b35165ab02fb\") " pod="default/nginx-cb8956d5f-c5zh8"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.520363    4170 reconciler_common.go:228] "operationExecutor.MountVolume started for volume \"kube-api-access-kq8x5\" (UniqueName: \"kubernetes.io/projected/d054e76b-1d9b-4788-9fc7-b35165ab02fb-kube-api-access-kq8x5\") pod \"nginx-cb8956d5f-c5zh8\" (UID: \"d054e76b-1d9b-4788-9fc7-b35165ab02fb\") " pod="default/nginx-cb8956d5f-c5zh8"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.534007    4170 operation_generator.go:740] "MountVolume.SetUp succeeded for volume \"kube-api-access-kq8x5\" (UniqueName: \"kubernetes.io/projected/d054e76b-1d9b-4788-9fc7-b35165ab02fb-kube-api-access-kq8x5\") pod \"nginx-cb8956d5f-c5zh8\" (UID: \"d054e76b-1d9b-4788-9fc7-b35165ab02fb\") " pod="default/nginx-cb8956d5f-c5zh8"
Apr 17 19:46:19 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:19.618021    4170 util.go:30] "No sandbox for pod can be found. Need to start a new one" pod="default/nginx-cb8956d5f-c5zh8"
Apr 17 19:46:20 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:20.280279    4170 kubelet.go:2231] "SyncLoop (PLEG): event for pod" pod="default/nginx-cb8956d5f-c5zh8" event=&{ID:d054e76b-1d9b-4788-9fc7-b35165ab02fb Type:ContainerStarted Data:007c2d8915cce53c32d6c4e3b1496fe80441e7a0abbbb3baa4802c7e14cd61f6}
Apr 17 19:46:20 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:20.280307    4170 kubelet.go:2231] "SyncLoop (PLEG): event for pod" pod="default/nginx-cb8956d5f-c5zh8" event=&{ID:d054e76b-1d9b-4788-9fc7-b35165ab02fb Type:ContainerStarted Data:644d543bd5d5b89412fdd5b2c36ab961749391f99cbdcb5602a2bd9ee1a042d7}
Apr 17 19:46:20 8rnr7mhj-nhcz55ua kubelet[4170]: I0417 19:46:20.296305    4170 pod_startup_latency_tracker.go:102] "Observed pod startup duration" pod="default/nginx-cb8956d5f-c5zh8" podStartSLOduration=1.296279865 pod.CreationTimestamp="2024-04-17 19:46:19 +0800 CST" firstStartedPulling="0001-01-01 00:00:00 +0000 UTC" lastFinishedPulling="0001-01-01 00:00:00 +0000 UTC" observedRunningTime="2024-04-17 19:46:20.295142614 +0800 CST m=+465268.893586305" watchObservedRunningTime="2024-04-17 19:46:20.296279865 +0800 CST m=+465268.894723600"exit
```
