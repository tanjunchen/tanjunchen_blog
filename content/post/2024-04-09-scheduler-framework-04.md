---
layout:     post
title:      "深入理解 Kubernetes Scheduler Framework 调度框架（Part 4）"
subtitle:   "Scheduler Framework 内置调度算法与 out-of-tree 插件示例调度算法"
description: ""
author: "陈谭军"
date: 2024-04-09
published: true
tags:
    - kubernetes
    - Scheduler Framework
categories:
    - TECHNOLOGY
showtoc: true
---

Scheduler 分两个 cycle：Scheduling Cycle 和 Binding Cycle。在 Scheduling Cycle 中为了提升效率的一个重要原则就是 Pod、 Node 等信息从本地缓存中获取，而具体的实现原理就是先使用 list 获取所有 Node、Pod 的信息，然后再 watch 他们的变化更新本地缓存。在 Bind Cycle 中，会有两次外部 api 调用：调用 pv controller 绑定 pv 和调用 kube-apiserver 绑定 Node，api 调用是耗时的，所以将 bind 扩展点拆分出来，另起一个 go 协程进行 bind。调度周期是串行，绑定周期是并行的。Scheduler Framework 内置调度算法与 out-of-tree 插件示例调度算法。

[深入理解 Kubernetes Scheduler Framework 调度框架（Part 4）](https://tanjunchen.github.io/post/2024-04-09-scheduler-framework-04/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 3）](https://tanjunchen.github.io/post/2024-04-08-scheduler-framework-03/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 2）](https://tanjunchen.github.io/post/2024-04-07-scheduler-framework-02/)  
[深入理解 Kubernetes Scheduler Framework 调度框架（Part 1）](https://tanjunchen.github.io/post/2024-04-06-scheduler-framework-01/) 

# in-tree 内置调度算法

## noderesources

在 pkg/scheduler/framework/plugins/noderesources.go 文件下存在以下资源调度策略，如下所示：
```go
// scorer is decorator for resourceAllocationScorer
// 资源分配打分装饰器 
type scorer func(args *config.NodeResourcesFitArgs) *resourceAllocationScorer

// resourceAllocationScorer contains information to calculate resource allocation score.
type resourceAllocationScorer struct {
	Name string
	// used to decide whether to use Requested or NonZeroRequested for
	// cpu and memory.
    // 根据 cpu 与内存判断使用 Requested 或者 NonZeroRequested 
	useRequested bool
	scorer       func(requested, allocable []int64) int64
	resources    []config.ResourceSpec
}

// score will use `scorer` function to calculate the score.
func (r *resourceAllocationScorer) score(
	ctx context.Context,
	pod *v1.Pod,
	nodeInfo *framework.NodeInfo,
	podRequests []int64) (int64, *framework.Status) {
	logger := klog.FromContext(ctx)
	node := nodeInfo.Node()

	// resources not set, nothing scheduled,
    // 没有配置资源，配置 0 得分
	if len(r.resources) == 0 {
		return 0, framework.NewStatus(framework.Error, "resources not found")
	}

	requested := make([]int64, len(r.resources))
	allocatable := make([]int64, len(r.resources))
	for i := range r.resources {
		alloc, req := r.calculateResourceAllocatableRequest(logger, nodeInfo, v1.ResourceName(r.resources[i].Name), podRequests[i])
		// Only fill the extended resource entry when it's non-zero.
		if alloc == 0 {
			continue
		}
		allocatable[i] = alloc
		requested[i] = req
	}

	score := r.scorer(requested, allocatable)

	if loggerV := logger.V(10); loggerV.Enabled() { // Serializing these maps is costly.
		loggerV.Info("Listed internal info for allocatable resources, requested resources and score", "pod",
			klog.KObj(pod), "node", klog.KObj(node), "resourceAllocationScorer", r.Name,
			"allocatableResource", allocatable, "requestedResource", requested, "resourceScore", score,
		)
	}

	return score, nil
}

// calculateResourceAllocatableRequest returns 2 parameters:
// - 1st param: quantity of allocatable resource on the node.
// - 2nd param: aggregated quantity of requested resource on the node.
// Note: if it's an extended resource, and the pod doesn't request it, (0, 0) is returned.
// 第一个返回值：节点上可分配资源的数量
// 第二个返回值：节点上请求资源的聚合数量
func (r *resourceAllocationScorer) calculateResourceAllocatableRequest(logger klog.Logger, nodeInfo *framework.NodeInfo, resource v1.ResourceName, podRequest int64) (int64, int64) {
    // 节点可请求资源
	requested := nodeInfo.NonZeroRequested
	if r.useRequested {
		requested = nodeInfo.Requested
	}

	// If it's an extended resource, and the pod doesn't request it. We return (0, 0)
	// as an implication to bypass scoring on this resource.
	if podRequest == 0 && schedutil.IsScalarResourceName(resource) {
		return 0, 0
	}
	switch resource {
    // CPU
	case v1.ResourceCPU:
		return nodeInfo.Allocatable.MilliCPU, (requested.MilliCPU + podRequest)
    // Memory 内存
	case v1.ResourceMemory:
		return nodeInfo.Allocatable.Memory, (requested.Memory + podRequest)
    // ResourceEphemeralStorage 存储资源
	case v1.ResourceEphemeralStorage:
		return nodeInfo.Allocatable.EphemeralStorage, (nodeInfo.Requested.EphemeralStorage + podRequest)
	default:
    // 默认情况 
		if _, exists := nodeInfo.Allocatable.ScalarResources[resource]; exists {
			return nodeInfo.Allocatable.ScalarResources[resource], (nodeInfo.Requested.ScalarResources[resource] + podRequest)
		}
	}
	logger.V(10).Info("Requested resource is omitted for node score calculation", "resourceName", resource)
	return 0, 0
}

// calculatePodResourceRequest returns the total non-zero requests. If Overhead is defined for the pod
// the Overhead is added to the result.
func (r *resourceAllocationScorer) calculatePodResourceRequest(pod *v1.Pod, resourceName v1.ResourceName) int64 {
    // owner: @vinaykul
    // kep: http://kep.k8s.io/1287
    // alpha: v1.27
    // Enables In-Place Pod Vertical Scaling
    // InPlacePodVerticalScaling featuregate.Feature = "InPlacePodVerticalScaling"
    // 是否开启 Pod 

	opts := resourcehelper.PodResourcesOptions{
		InPlacePodVerticalScalingEnabled: utilfeature.DefaultFeatureGate.Enabled(features.InPlacePodVerticalScaling),
	}
    
    // const (
    //	// DefaultMilliCPURequest defines default milli cpu request number.
    //	DefaultMilliCPURequest int64 = 100 // 0.1 core
    //	// DefaultMemoryRequest defines default memory request size.
    //	DefaultMemoryRequest int64 = 200 * 1024 * 1024 // 200 MB
    //)

    // Pod 没有配置资源请求，默认给 0.1 core、200MB
	if !r.useRequested {
		opts.NonMissingContainerRequests = v1.ResourceList{
			v1.ResourceCPU:    *resource.NewMilliQuantity(schedutil.DefaultMilliCPURequest, resource.DecimalSI),
			v1.ResourceMemory: *resource.NewQuantity(schedutil.DefaultMemoryRequest, resource.DecimalSI),
		}
	}

	requests := resourcehelper.PodRequests(pod, opts)

	quantity := requests[resourceName]
	if resourceName == v1.ResourceCPU {
		return quantity.MilliValue()
	}
	return quantity.Value()
}

func (r *resourceAllocationScorer) calculatePodResourceRequestList(pod *v1.Pod, resources []config.ResourceSpec) []int64 {
	podRequests := make([]int64, len(resources))
	for i := range resources {
		podRequests[i] = r.calculatePodResourceRequest(pod, v1.ResourceName(resources[i].Name))
	}
	return podRequests
}
```

注册内置插件，如下所示：
```go
registry := runtime.Registry{
	...
	noderesources.Name:                   runtime.FactoryAdapter(fts, noderesources.NewFit),
	noderesources.BalancedAllocationName: runtime.FactoryAdapter(fts, noderesources.NewBalancedAllocation),
	...
}
```

pkg/scheduler/framework/plugins/noderesources/balanced_allocation.go 表示资源（CPU与内存）使用是否均衡（标准差），如下所示：
```go
// BalancedAllocation is a score plugin that calculates the difference between the cpu and memory fraction
// of capacity, and prioritizes the host based on how close the two metrics are to each other.
type BalancedAllocation struct {
	handle framework.Handle
	resourceAllocationScorer
}

var _ framework.PreScorePlugin = &BalancedAllocation{}
var _ framework.ScorePlugin = &BalancedAllocation{}

// BalancedAllocationName is the name of the plugin used in the plugin registry and configurations.
const (
	BalancedAllocationName = names.NodeResourcesBalancedAllocation

	// balancedAllocationPreScoreStateKey is the key in CycleState to NodeResourcesBalancedAllocation pre-computed data for Scoring.
	balancedAllocationPreScoreStateKey = "PreScore" + BalancedAllocationName
)

// balancedAllocationPreScoreState computed at PreScore and used at Score.
// balancedAllocationPreScoreState 在 PreScore 与 Score 打分生效
type balancedAllocationPreScoreState struct {
	// podRequests have the same order of the resources defined in NodeResourcesFitArgs.Resources,
	// same for other place we store a list like that.
	podRequests []int64
}

// Clone implements the mandatory Clone interface. We don't really copy the data since
// there is no need for that.
func (s *balancedAllocationPreScoreState) Clone() framework.StateData {
	return s
}

// PreScore calculates incoming pod's resource requests and writes them to the cycle state used.
// PreScore 计算传入 pod 的资源请求并将其写入到使用的周期状态中
func (ba *BalancedAllocation) PreScore(ctx context.Context, cycleState *framework.CycleState, pod *v1.Pod, nodes []*v1.Node) *framework.Status {
	state := &balancedAllocationPreScoreState{
		podRequests: ba.calculatePodResourceRequestList(pod, ba.resources),
	}
	cycleState.Write(balancedAllocationPreScoreStateKey, state)
	return nil
}

// getBalancedAllocationPreScoreState 获取负载均衡打分策略
func getBalancedAllocationPreScoreState(cycleState *framework.CycleState) (*balancedAllocationPreScoreState, error) {
	c, err := cycleState.Read(balancedAllocationPreScoreStateKey)
	if err != nil {
		return nil, fmt.Errorf("reading %q from cycleState: %w", balancedAllocationPreScoreStateKey, err)
	}

	s, ok := c.(*balancedAllocationPreScoreState)
	if !ok {
		return nil, fmt.Errorf("invalid PreScore state, got type %T", c)
	}
	return s, nil
}

// Name returns name of the plugin. It is used in logs, etc.
func (ba *BalancedAllocation) Name() string {
	return BalancedAllocationName
}

// Score invoked at the score extension point.
// Score 拓展点
func (ba *BalancedAllocation) Score(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) (int64, *framework.Status) {
	nodeInfo, err := ba.handle.SnapshotSharedLister().NodeInfos().Get(nodeName)
	if err != nil {
		return 0, framework.AsStatus(fmt.Errorf("getting node %q from Snapshot: %w", nodeName, err))
	}

	s, err := getBalancedAllocationPreScoreState(state)
	if err != nil {
		s = &balancedAllocationPreScoreState{podRequests: ba.calculatePodResourceRequestList(pod, ba.resources)}
	}

	// ba.score favors nodes with balanced resource usage rate.
	// It calculates the standard deviation for those resources and prioritizes the node based on how close the usage of those resources is to each other.
	// Detail: score = (1 - std) * MaxNodeScore, where std is calculated by the root square of Σ((fraction(i)-mean)^2)/len(resources)
	// The algorithm is partly inspired by:
	// "Wei Huang et al. An Energy Efficient Virtual Machine Placement Algorithm with Balanced Resource Utilization"
	return ba.score(ctx, pod, nodeInfo, s.podRequests)
}

// ScoreExtensions of the Score plugin.
func (ba *BalancedAllocation) ScoreExtensions() framework.ScoreExtensions {
	return nil
}

// NewBalancedAllocation initializes a new plugin and returns it.
// NewBalancedAllocation 初始化 
func NewBalancedAllocation(_ context.Context, baArgs runtime.Object, h framework.Handle, fts feature.Features) (framework.Plugin, error) {
	args, ok := baArgs.(*config.NodeResourcesBalancedAllocationArgs)
	if !ok {
		return nil, fmt.Errorf("want args to be of type NodeResourcesBalancedAllocationArgs, got %T", baArgs)
	}

	if err := validation.ValidateNodeResourcesBalancedAllocationArgs(nil, args); err != nil {
		return nil, err
	}

	return &BalancedAllocation{
		handle: h,
		resourceAllocationScorer: resourceAllocationScorer{
			Name:         BalancedAllocationName,
            // balancedResourceScorer 表示资源得分机制 
			scorer:       balancedResourceScorer,
			useRequested: true,
			resources:    args.Resources,
		},
	}, nil
}

// balancedResourceScorer 计算每种资源请求的比例（请求/可分配），然后计算了这些比例的标准差。
// 标准差衡量了请求资源的比例与平均值之间的偏差程度，如果标准差越小，说明节点上各资源类型的利用率更均衡，这种节点更适合调度。
// 最后，它返回一个分数，分数越高表示节点的资源分配越均衡。
func balancedResourceScorer(requested, allocable []int64) int64 {
	var resourceToFractions []float64
	var totalFraction float64
    
    // 对于每种资源，计算请求的资源和可分配资源的比例，并将比例加入到 resourceToFractions 数组中。
    // 计算 resourceToFractions 数组中所有元素的总和 totalFraction。
	for i := range requested {
		if allocable[i] == 0 {
			continue
		}
		fraction := float64(requested[i]) / float64(allocable[i])
		if fraction > 1 {
			fraction = 1
		}
		totalFraction += fraction
		resourceToFractions = append(resourceToFractions, fraction)
	}

    // 标准差
	std := 0.0

	// For most cases, resources are limited to cpu and memory, the std could be simplified to std := (fraction1-fraction2)/2
	// len(fractions) > 2: calculate std based on the well-known formula - root square of Σ((fraction(i)-mean)^2)/len(fractions)
	// Otherwise, set the std to zero is enough.
    // 计算 resourceToFractions 数组的标准差
	if len(resourceToFractions) == 2 {
		std = math.Abs((resourceToFractions[0] - resourceToFractions[1]) / 2)

	} else if len(resourceToFractions) > 2 {
		mean := totalFraction / float64(len(resourceToFractions))
		var sum float64
		for _, fraction := range resourceToFractions {
			sum = sum + (fraction-mean)*(fraction-mean)
		}
		std = math.Sqrt(sum / float64(len(resourceToFractions)))
	}
    
    // 返回一个分数，该分数等于 (1 - 标准差) * MaxNodeScore
    // 这意味着，如果标准差越小（即资源利用更均衡），则返回的分数越高
	// STD (standard deviation) is always a positive value. 1-deviation lets the score to be higher for node which has least deviation and
	// multiplying it with `MaxNodeScore` provides the scaling factor needed.
	return int64((1 - std) * float64(framework.MaxNodeScore))
}
```

在 pkg/scheduler/framework/plugins/noderesources/fit.go 文件下初始化打分机制（最少资源使用、最多资源使用、资源占用比例等），如下所示：
```go
// NewFit initializes a new plugin and returns it.
func NewFit(_ context.Context, plArgs runtime.Object, h framework.Handle, fts feature.Features) (framework.Plugin, error) {
	args, ok := plArgs.(*config.NodeResourcesFitArgs)
	if !ok {
		return nil, fmt.Errorf("want args to be of type NodeResourcesFitArgs, got %T", plArgs)
	}
	if err := validation.ValidateNodeResourcesFitArgs(nil, args); err != nil {
		return nil, err
	}

	if args.ScoringStrategy == nil {
		return nil, fmt.Errorf("scoring strategy not specified")
	}

	strategy := args.ScoringStrategy.Type
    // Node 节点资源调度策略 
	scorePlugin, exists := nodeResourceStrategyTypeMap[strategy]
	if !exists {
		return nil, fmt.Errorf("scoring strategy %s is not supported", strategy)
	}

	return &Fit{
		ignoredResources:                sets.New(args.IgnoredResources...),
		ignoredResourceGroups:           sets.New(args.IgnoredResourceGroups...),
		enableInPlacePodVerticalScaling: fts.EnableInPlacePodVerticalScaling,
		enableSidecarContainers:         fts.EnableSidecarContainers,
		handle:                          h,
        // 打分机制
		resourceAllocationScorer:        *scorePlugin(args),
	}, nil
}

// nodeResourceStrategyTypeMap maps strategy to scorer implementation
var nodeResourceStrategyTypeMap = map[config.ScoringStrategyType]scorer{
	config.LeastAllocated: func(args *config.NodeResourcesFitArgs) *resourceAllocationScorer {
		resources := args.ScoringStrategy.Resources
		return &resourceAllocationScorer{
			Name:      string(config.LeastAllocated),
            // 最少使用资源
			scorer:    leastResourceScorer(resources),
			resources: resources,
		}
	},
	config.MostAllocated: func(args *config.NodeResourcesFitArgs) *resourceAllocationScorer {
		resources := args.ScoringStrategy.Resources
		return &resourceAllocationScorer{
			Name:      string(config.MostAllocated),
            // 最多使用资源
			scorer:    mostResourceScorer(resources),
			resources: resources,
		}
	},
	config.RequestedToCapacityRatio: func(args *config.NodeResourcesFitArgs) *resourceAllocationScorer {
		resources := args.ScoringStrategy.Resources
		return &resourceAllocationScorer{
			Name:      string(config.RequestedToCapacityRatio),
            // 资源利用率
			scorer:    requestedToCapacityRatioScorer(resources, args.ScoringStrategy.RequestedToCapacityRatio.Shape),
			resources: resources,
		}
	},
}
```

pkg/scheduler/framework/plugins/noderesources/least_allocated.go 如下所示：
```go
// leastResourceScorer favors nodes with fewer requested resources.
// It calculates the percentage of memory, CPU and other resources requested by pods scheduled on the node, and
// prioritizes based on the minimum of the average of the fraction of requested to capacity.
//
// Details:
// (cpu((capacity-requested)*MaxNodeScore*cpuWeight/capacity) + memory((capacity-requested)*MaxNodeScore*memoryWeight/capacity) + ...)/weightSum

// 计算了每种资源的未使用量（可分配-请求），然后根据每种资源的权重计算出一个加权平均分。
// 最后，它返回一个分数，分数越高表示节点上未使用的资源越多。
func leastResourceScorer(resources []config.ResourceSpec) func([]int64, []int64) int64 {
	return func(requested, allocable []int64) int64 {
		var nodeScore, weightSum int64
        // 对于每种资源，计算未使用的资源量，并乘以该资源的权重和一个最大分数（framework.MaxNodeScore），得到每种资源的得分;
        // 将所有资源的得分相加，然后除以所有资源权重的总和，得到一个平均分;
        // 返回这个平均分;
        
		for i := range requested {
			if allocable[i] == 0 {
				continue
			}
			weight := resources[i].Weight
			resourceScore := leastRequestedScore(requested[i], allocable[i])
			nodeScore += resourceScore * weight
			weightSum += weight
		}
		if weightSum == 0 {
			return 0
		}
		return nodeScore / weightSum
	}
}

// The unused capacity is calculated on a scale of 0-MaxNodeScore
// 0 being the lowest priority and `MaxNodeScore` being the highest.
// The more unused resources the higher the score is.
func leastRequestedScore(requested, capacity int64) int64 {
	if capacity == 0 {
		return 0
	}
	if requested > capacity {
		return 0
	}

	return ((capacity - requested) * framework.MaxNodeScore) / capacity
}
```

pkg/scheduler/framework/plugins/noderesources/most_allocated.go 如下所示：
```go
// mostResourceScorer favors nodes with most requested resources.
// It calculates the percentage of memory and CPU requested by pods scheduled on the node, and prioritizes
// based on the maximum of the average of the fraction of requested to capacity.
//
// Details:
// (cpu(MaxNodeScore * requested * cpuWeight / capacity) + memory(MaxNodeScore * requested * memoryWeight / capacity) + ...) / weightSum

// 它计算了每种资源已被请求的量（请求/可分配），然后根据每种资源的权重计算出一个加权平均分。
// 最后，它返回一个分数，分数越高表示节点上已被请求使用的资源越多。
func mostResourceScorer(resources []config.ResourceSpec) func(requested, allocable []int64) int64 {
	return func(requested, allocable []int64) int64 {
		var nodeScore, weightSum int64
        // 对于每种资源，计算已被请求的资源量，并乘以该资源的权重和一个最大分数（framework.MaxNodeScore），得到每种资源的得分;
        // 将所有资源的得分相加，然后除以所有资源权重的总和，得到一个平均分;
        // 返回这个平均分;
		for i := range requested {
			if allocable[i] == 0 {
				continue
			}
			weight := resources[i].Weight
			resourceScore := mostRequestedScore(requested[i], allocable[i])
			nodeScore += resourceScore * weight
			weightSum += weight
		}
		if weightSum == 0 {
			return 0
		}
		return nodeScore / weightSum
	}
}

// The used capacity is calculated on a scale of 0-MaxNodeScore (MaxNodeScore is
// constant with value set to 100).
// 0 being the lowest priority and 100 being the highest.
// The more resources are used the higher the score is. This function
// is almost a reversed version of noderesources.leastRequestedScore.
func mostRequestedScore(requested, capacity int64) int64 {
	if capacity == 0 {
		return 0
	}
	if requested > capacity {
		// `requested` might be greater than `capacity` because pods with no
		// requests get minimum values.
		requested = capacity
	}

	return (requested * framework.MaxNodeScore) / capacity
}
```

折线函数（Broken Linear Function）是一种分段线性函数，即这个函数是由多个线性函数（或称为线性段）组成的。在每个分段上，函数的形式都是线性的，即 y = ax + b 的形式，每个线性段在其端点处与相邻的线性段相接。在具体的应用场景中，在 Kubernetes 资源调度的例子中，折线函数可以用来表示不同资源利用率下对应的资源调度得分。利用率点（Utilization）是函数的参数，得分（Score）是函数的值。根据资源的利用率，可以在折线函数上找到对应的得分，从而实现根据资源使用情况的动态调整调度策略。

```go
pkg/scheduler/framework/plugins/noderesources/requested_to_capacity_ratio.go 如下所示：
const maxUtilization = 100

// buildRequestedToCapacityRatioScorerFunction allows users to apply bin packing
// on core resources like CPU, Memory as well as extended resources like accelerators.
// buildRequestedToCapacityRatioScorerFunction 函数接收一个打分函数形状（scoringFunctionShape）和资源规格列表（resources），返回一个接收请求资源和可分配资源的函数，该函数会计算出每种资源的得分，然后根据资源的权重进行加权平均，得出最终的节点得分。
func buildRequestedToCapacityRatioScorerFunction(scoringFunctionShape helper.FunctionShape, resources []config.ResourceSpec) func([]int64, []int64) int64 {
	rawScoringFunction := helper.BuildBrokenLinearFunction(scoringFunctionShape)
	resourceScoringFunction := func(requested, capacity int64) int64 {
		if capacity == 0 || requested > capacity {
			return rawScoringFunction(maxUtilization)
		}

		return rawScoringFunction(requested * maxUtilization / capacity)
	}
	return func(requested, allocable []int64) int64 {
		var nodeScore, weightSum int64
		for i := range requested {
			if allocable[i] == 0 {
				continue
			}
			weight := resources[i].Weight
			resourceScore := resourceScoringFunction(requested[i], allocable[i])
			if resourceScore > 0 {
				nodeScore += resourceScore * weight
				weightSum += weight
			}
		}
		if weightSum == 0 {
			return 0
		}
		return int64(math.Round(float64(nodeScore) / float64(weightSum)))
	}
}

// requestedToCapacityRatioScorer 函数接收资源规格列表和利用率形状点列表（shape），构造出打分函数形状，然后调用buildRequestedToCapacityRatioScorerFunction 函数，返回一个打分函数。
func requestedToCapacityRatioScorer(resources []config.ResourceSpec, shape []config.UtilizationShapePoint) func([]int64, []int64) int64 {
	shapes := make([]helper.FunctionShapePoint, 0, len(shape))
	for _, point := range shape {
		shapes = append(shapes, helper.FunctionShapePoint{
			Utilization: int64(point.Utilization),
			// MaxCustomPriorityScore may diverge from the max score used in the scheduler and defined by MaxNodeScore,
			// therefore we need to scale the score returned by requested to capacity ratio to the score range
			// used by the scheduler.
			Score: int64(point.Score) * (framework.MaxNodeScore / config.MaxCustomPriorityScore),
		})
	}

	return buildRequestedToCapacityRatioScorerFunction(shapes, resources)
}

// FunctionShapePoint represents a shape point.
type FunctionShapePoint struct {
	// Utilization is function argument.
	Utilization int64
	// Score is function value.
	Score int64
}

// 构建一种被称为"折线函数"（Broken Linear Function）的函数。
// 这种函数由多个线性段组成，每个线性段在不同的利用率点上相交。具体的函数值取决于输入值在哪个线性段范围内。
// FunctionShapePoint结构体表示一个形状点，包含两个字段：Utilization和Score。
// Utilization表示函数参数，即资源的利用率，而Score表示函数值，即根据资源利用率计算出的得分。

// BuildBrokenLinearFunction creates a function which is built using linear segments. Segments are defined via shape array.
// Shape[i].Utilization slice represents points on "Utilization" axis where different segments meet.
// Shape[i].Score represents function values at meeting points.

// BuildBrokenLinearFunction 函数接收一个形状数组shape，返回一个函数，这个函数根据输入的资源利用率计算得分。函数的计算规则如下：
// 如果资源利用率小于shape[0].Utilization，则返回shape[0].Score;
// 如果资源利用率大于shape[n-1].Utilization，则返回shape[n-1].Score;
// 如果资源利用率在shape[i-1].Utilization和shape[i].Utilization之间，则返回对应的线性插值得分;

// function f(p) is defined as:
//	shape[0].Score for p < shape[0].Utilization
//	shape[n-1].Score for p > shape[n-1].Utilization
//
// and linear between points (p < shape[i].Utilization)
func BuildBrokenLinearFunction(shape FunctionShape) func(int64) int64 {
	return func(p int64) int64 {
		for i := 0; i < len(shape); i++ {
			if p <= int64(shape[i].Utilization) {
				if i == 0 {
					return shape[0].Score
				}
				return shape[i-1].Score + (shape[i].Score-shape[i-1].Score)*(p-shape[i-1].Utilization)/(shape[i].Utilization-shape[i-1].Utilization)
			}
		}
		return shape[len(shape)-1].Score
	}
}
```

## imagelocality

```go
// NewInTreeRegistry builds the registry with all the in-tree plugins.
// A scheduler that runs out of tree plugins can register additional plugins
// through the WithFrameworkOutOfTreeRegistry option.
func NewInTreeRegistry() runtime.Registry {
    registry := runtime.Registry{
        ......
        imagelocality.Name:                   imagelocality.New,
        ......
    }
    return registry
}
```

ImageLocality 是一个评分插件，它倾向于选择那些已经拥有请求的 pod 容器镜像的节点。
```go
// The two thresholds are used as bounds for the image score range. They correspond to a reasonable size range for
// container images compressed and stored in registries; 90%ile of images on dockerhub drops into this range.

// 这两个阈值被用作镜像分数范围的界限。
// 它们对应于压缩并存储在注册表中的容器镜像的合理大小范围；
// Docker Hub上的90%的镜像都落在这个范围内 230MB - 1GB
const (
	mb                    int64 = 1024 * 1024
	minThreshold          int64 = 23 * mb
	maxContainerThreshold int64 = 1000 * mb
)

// ImageLocality is a score plugin that favors nodes that already have requested pod container's images.
// ImageLocality 是一个评分插件，它倾向于选择那些已经拥有请求的 pod 容器镜像的节点
type ImageLocality struct {
	handle framework.Handle
}

var _ framework.ScorePlugin = &ImageLocality{}

// Name is the name of the plugin used in the plugin registry and configurations.
const Name = names.ImageLocality

// Name returns name of the plugin. It is used in logs, etc.
func (pl *ImageLocality) Name() string {
	return Name
}

// Score invoked at the score extension point.
func (pl *ImageLocality) Score(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) (int64, *framework.Status) {
	nodeInfo, err := pl.handle.SnapshotSharedLister().NodeInfos().Get(nodeName)
	if err != nil {
		return 0, framework.AsStatus(fmt.Errorf("getting node %q from Snapshot: %w", nodeName, err))
	}

	nodeInfos, err := pl.handle.SnapshotSharedLister().NodeInfos().List()
	if err != nil {
		return 0, framework.AsStatus(err)
	}
	totalNumNodes := len(nodeInfos)
    // 给定一个节点上请求镜像的总分数（sumScores），节点的优先级是通过用与总分数成比例的比率来缩放最大优先级值来获得的。
	imageScores := sumImageScores(nodeInfo, pod, totalNumNodes)
	score := calculatePriority(imageScores, len(pod.Spec.InitContainers)+len(pod.Spec.Containers))

	return score, nil
}

// ScoreExtensions of the Score plugin.
func (pl *ImageLocality) ScoreExtensions() framework.ScoreExtensions {
	return nil
}

// New initializes a new plugin and returns it.
func New(_ context.Context, _ runtime.Object, h framework.Handle) (framework.Plugin, error) {
	return &ImageLocality{handle: h}, nil
}

// calculatePriority returns the priority of a node. Given the sumScores of requested images on the node, the node's
// priority is obtained by scaling the maximum priority value with a ratio proportional to the sumScores.
func calculatePriority(sumScores int64, numContainers int) int64 {
    // 函数 calculatePriority 首先计算了一个最大阈值（maxThreshold），这个阈值是容器数量（numContainers）与设定的最大容器阈值（maxContainerThreshold）的乘积。
    // 然后，它会检查总分数（sumScores）是否在最小阈值（minThreshold）和最大阈值之间，如果不在这个范围，就会被调整到这个范围内。
    
	maxThreshold := maxContainerThreshold * int64(numContainers)
	if sumScores < minThreshold {
		sumScores = minThreshold
	} else if sumScores > maxThreshold {
		sumScores = maxThreshold
	}
    // 然后，函数使用这个调整后的总分数，根据公式 (sumScores - minThreshold) / (maxThreshold - minThreshold) 计算出一个比率
    // 然后用这个比率来缩放最大优先级值（framework.MaxNodeScore），得到最终的节点优先级。
	return framework.MaxNodeScore * (sumScores - minThreshold) / (maxThreshold - minThreshold)
}

// 计算并返回一个节点上所有已存在的容器镜像的总分 
// sumImageScores returns the sum of image scores of all the containers that are already on the node.
// Each image receives a raw score of its size, scaled by scaledImageScore. The raw scores are later used to calculate
// the final score.

// 函数 sumImageScores 遍历 pod 中的初始化容器 InitContainers 和其他容器 Containers，
// 对于每一个容器，它都会检查该容器的镜像是否已经存在于目标节点上。
// 如果存在，它会调用 scaledImageScore 函数来计算这个镜像的得分，并将其累加到总分中。
func sumImageScores(nodeInfo *framework.NodeInfo, pod *v1.Pod, totalNumNodes int) int64 {
	var sum int64
	for _, container := range pod.Spec.InitContainers {
		if state, ok := nodeInfo.ImageStates[normalizedImageName(container.Image)]; ok {
			sum += scaledImageScore(state, totalNumNodes)
		}
	}
	for _, container := range pod.Spec.Containers {
		if state, ok := nodeInfo.ImageStates[normalizedImageName(container.Image)]; ok {
			sum += scaledImageScore(state, totalNumNodes)
		}
	}
	return sum
}

// 这个得分是基于镜像的大小计算的，并且会根据节点的总数进行缩放。这样一来，镜像的大小和节点的数量都会影响到最终的得分。
// 这有助于在进行 pod 调度时，优先选择那些已经拥有所需镜像的节点，从而可以减少镜像拉取的时间，加快 pod 的启动速度。
// scaledImageScore returns an adaptively scaled score for the given state of an image.
// The size of the image is used as the base score, scaled by a factor which considers how much nodes the image has "spread" to.
// This heuristic aims to mitigate the undesirable "node heating problem", i.e., pods get assigned to the same or
// a few nodes due to image locality.
func scaledImageScore(imageState *framework.ImageStateSummary, totalNumNodes int) int64 {
	spread := float64(imageState.NumNodes) / float64(totalNumNodes)
	return int64(float64(imageState.Size) * spread)
}

// normalizedImageName returns the CRI compliant name for a given image.
// TODO: cover the corner cases of missed matches, e.g,
// 1. Using Docker as runtime and docker.io/library/test:tag in pod spec, but only test:tag will present in node status
// 2. Using the implicit registry, i.e., test:tag or library/test:tag in pod spec but only docker.io/library/test:tag
// in node status; note that if users consistently use one registry format, this should not happen.
func normalizedImageName(name string) string {
	if strings.LastIndex(name, ":") <= strings.LastIndex(name, "/") {
		name = name + ":latest"
	}
	return name
}
```

# out-of-tree 外置算法

[scheduler-plugins](https://github.com/kubernetes-sigs/scheduler-plugins) 是基于 Scheduler Framework 调度框架的 out-of-tree 插件实现。scheduler-plugins 提供了在大规模 Kubernetes 集群中使用的调度器插件，这些插件可以作为Golang SDK库进行引用，或者通过预构建的镜像或 Helm 进行开箱即用。此外，这个仓库还整合了编写高质量调度器插件的最佳实践和实用工具。

kube-scheduler 二进制文件包含以下插件列表，可以通过创建一个或多个调度器配置文件来配置它们。
* Capacity Scheduling
* Coscheduling
* Node Resources
* Node Resource Topology
* Preemption Toleration
* Trimaran
* Network-Aware Scheduling

此外，kube-scheduler二进制文件还包含以下示例插件列表（不推荐生产环境使用）。
* Cross Node Preemption
* Pod State
* Quality of Service

[Network-Aware](https://github.com/kubernetes-sigs/scheduler-plugins/pull/282) 是 KEP 设计文档。
物联网（IoT）、多层次的网络服务和视频流服务这样的应用，将最大程度地从网络感知的调度策略中受益，
这些策略除了考虑调度器使用的默认资源（CPU和内存）外，还考虑延迟和带宽等。

# 进阶调度算法

## Capacity Scheduling

越来越多的需求希望使用Kubernetes来管理批处理工作负载（ML/DL）。在这些情况下，一个挑战是在确保每个用户有合理的资源量的同时，提高集群的利用率。这个问题可以通过Kubernetes的ResourceQuota部分解决。原生的Kubernetes ResourceQuota API可以用来指定每个命名空间的最大总资源分配。配额的执行是通过准入检查完成的。如果累计的资源分配超过了配额限制，就不能创建配额消费者（例如，Pod）。换句话说，当Pod创建时，整体资源使用是根据Pod的规格（即，cpu/mem请求）进行聚合的。Kubernetes配额设计存在的限制是：配额资源使用是基于资源配置（例如，Pod规格中指定的Pod cpu/mem请求）进行聚合的。虽然这种机制可以保证实际的资源消耗永远不会超过ResourceQuota限制，但可能会导致资源利用率低，因为一些Pod可能已经申请了资源，但未能被调度。例如，实际资源消耗可能远小于限制。

由于上述限制，批处理工作负载（ML/DL）在Kubernetes集群中的运行效率可能不如在其他容器编排平台（如Yarn）中高。为了克服上述限制，可以将Yarn容量调度器中使用的“ElasticQuota”概念引入Kubernetes。基本上，“ElasticQuota”有“最大”和“最小”的概念。可参见 [Capacity Scheduling](https://github.com/kubernetes-sigs/scheduler-plugins/tree/master/kep/9-capacity-scheduling)。

## Coscheduling

目前，通过Kubernetes的默认调度器，我们无法确保一组Pods可以全部被调度。在某些情况下，由于整个应用程序不能仅依赖部分Pods运行，这将浪费资源，如Spark作业，TensorFlow作业等。这个提议旨在通过引入PodGroup CRD来解决这个问题，来完成将一组Pods连接在一起的重要工作。可参见 [Coscheduling](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/coscheduling/README.md)。

## Node Resources

基于插件参数资源参数，资源被赋予权重。CPU的基本单位是毫核，而内存的基本单位是字节。可参见 [Node Resources](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/noderesources/README.md)。

## Node Resource Topology

在引入拓扑管理器后，集群中启动pod的问题在工作节点拥有不同NUMA拓扑和该拓扑中的资源量不同时就变得实际起来。Pod可能会被调度到资源总量足够的节点上，但资源分布可能无法满足相应的拓扑策略。在这种情况下，Pod将无法启动。对于调度器来说，更好的行为是选择合适的节点，kubelet准入处理器可能会通过。可参见 [Node Resource Topology](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/noderesourcetopology/README.md)。

## Preemption Toleration

Kubernetes调度器提供了Pod优先级和抢占特性。用户（通常是集群管理员）可以定义几个PriorityClass以在集群中分类优先级。如果集群的弹性较差（例如On-Premise集群），那么设计优先级类和抢占规则对于计算资源的利用率非常重要。

PriorityClass可以有PreemptionPolicy配置，用于自定义该优先级类的抢占者行为。允许的值有PreemptLowerPriority（默认）和Never。如果设置为Never，优先级类将变成非抢占优先级类，它不能抢占任何Pod，但可能被更高优先级的Pod抢占。PreemptionPolicy API非常简单易懂。然而，这个策略只关注抢占者侧的行为。这个插件通过在PriorityClass中添加抢占者（也称为受害者）侧策略，提供了更灵活的抢占行为配置。特别是，集群管理员可以定义抢占容忍策略，该策略定义了优先级类将免除抢占的标准。可参见 [Preemption Toleration](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/preemptiontoleration/README.md)。

## Trimaran

Kubernetes 提供了一种声明性资源模型，核心组件（调度器和kubelet）会遵守这种模型以保持一致性并满足QoS保证。然而，使用这种模型可能会导致集群的低利用率，原因如下：用户很难为应用程序估计准确的资源使用情况。此外，用户可能不理解资源模型，也不会设置它。Kubernetes提供的默认的树形调度插件（Score）不考虑实时节点利用率值。这个提案利用实时资源使用情况来通过提议的插件调度pod。最终的目标是在不破坏Kubernetes资源模型契约的情况下，提高集群利用率并降低集群管理的成本。可参见 [Trimaran](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/trimaran/README.md)。

* TargetLoadPacking：实现了一种打包策略，直到配置的CPU利用率，然后在热节点之间切换到扩展策略，支持CPU资源。
* LoadVariationRiskBalancing：在节点之间平衡风险，风险被定义为平均利用率和利用率变化的组合测量，支持CPU和内存资源。
* LowRiskOverCommitment：评估过度承诺的性能风险，并通过考虑（1）Pod的资源限制值（限制意识）和（2）节点上的实际负载（利用率）（负载意识），选择风险最低的节点。因此，它为Pod提供了一个低风险环境，缓解了过度承诺的问题，同时允许Pod使用他们的限制。

## Network-Aware Scheduling

许多应用程序对延迟敏感，要求应用程序中的微服务之间的延迟更低。对于端到端延迟成为主要目标的应用程序，旨在降低成本或提高资源效率的调度策略是不够的。
像物联网（IoT）、多层次web服务和视频流服务这样的应用程序将最大限度地从网络感知的调度策略中受益，这些策略除了考虑调度器使用的默认资源（如CPU和内存）外，还考虑延迟和带宽。

用户在使用多层次应用程序时经常遇到延迟问题。这些应用程序通常包括数十个到数百个具有复杂相互依赖关系的微服务。服务器的距离通常是主要的罪魁祸首。根据关于服务功能链（SFC）的先前工作，最好的策略是减少同一应用程序中链式微服务之间的延迟。此外，对于那些微服务之间有大量数据传输的应用程序，带宽起着至关重要的作用。例如，数据库应用程序中的多个副本可能需要频繁的复制以确保数据一致性。Spark作业可能在map和reduce节点之间有频繁的数据传输。节点中的网络容量不足可能会导致延迟增加或数据包丢失，这将降低应用程序的服务质量(QoS)。可参见 [Network-Aware Scheduling](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/networkaware/README.md)。

## Cross Node Preemption

PostFilter扩展点自1.19版本起在Kubernetes调度器中引入，上游的默认实现是在同一节点上抢占Pods，为无法调度的Pod腾出空间。与"同节点抢占"策略相反，我们可以提出一个"跨节点抢占"策略，通过跨多个节点抢占Pods，这在由于"跨节点"约束（如PodTopologySpread和PodAntiAffinity）导致Pod无法调度时非常有用。这也在抢占的原始设计文档中提到过。

此插件是作为一个示例构建的，演示了如何使用PostFilter扩展点，同时也启发用户构建他们自己的创新策略，如抢占一组Pods。可参见 [Cross Node Preemption](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/crossnodepreemption/README.md)。

## Pod State

这是一个评分插件，它以以下方式考虑终止和提名的Pods：拥有更多终止Pods的节点将获得更高的分数，因为这些终止的Pods最终将从节点中物理删除拥有更多被提名的Pods（携带.status.nominatedNodeName）的节点将获得较低的分数，因为这些被提名的节点预计在未来的调度周期中将容纳一些抢占者Pod。可参见 [Pod State](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/podstate/README.md)。

## Quality of Service

按照.spec.priority对Pods进行排序。默认情况下，插件按以下顺序对Pods进行排队：
* Guaranteed (requests == limits)
* Burstable (requests < limits)
* BestEffort (requests and limits not set)

可参见 [Quality of Service](https://github.com/kubernetes-sigs/scheduler-plugins/blob/master/pkg/qos/README.md)。

## disk-io-aware-scheduling

磁盘IO资源是云原生环境中保证工作负载性能的重要资源。当前的Kubernetes调度器不支持磁盘IO资源感知调度。可能会发生在一个节点上调度的pods争夺磁盘IO资源，导致性能下降（嘈杂的邻居问题）。越来越多的需求希望在Kubernetes中添加磁盘IO资源感知调度，以避免或减轻嘈杂的邻居问题。为了支持磁盘IO资源感知调度，我们添加了一个调度插件，该插件跟踪每个pod的磁盘IO资源需求，并在做出调度决策时对每个节点上可用的磁盘IO资源进行核算。可参见 [disk-io-aware-scheduling](https://github.com/kubernetes-sigs/scheduler-plugins/tree/master/kep/624-disk-io-aware-scheduling)。
