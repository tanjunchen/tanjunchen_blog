---
layout:     post
title:      "快手万擎大模型推理系统 kLLM 全栈优化解析与深度点评"
subtitle:   "从 MLA 混合并行、分级 KV Cache 到 SLO 驱动大 PD 弹性分离"
description: "深度剖析快手万擎大模型推理引擎 kLLM 核心优化体系，包含个人实战点评：解读 MLA+DP Attention/MoE EP 混合并行、Ring Attention 分块流水、DSpark 投机解码、三级 KV Cache 增量前缀树与 SLO 驱动的大 PD 弹性分层架构，提炼大模型规模化落地的系统工程方法论。"
author: "tanjunchen"
date: 2026-08-01
published: true
tags:
    - AI Infra
    - LLM
    - 推理加速
    - DeepSeek
    - 分布式系统
categories:
    - TECHNOLOGY
showtoc: true
---

# 0. 背景：推理系统决定大模型能否规模化落地

大模型能力快速提升之后，真正决定其能否规模化落地的，不再只是模型参数和榜单分数，而是**推理系统能否在高并发、长上下文和复杂 Agent 场景下，持续提供低延时、低成本、稳定可靠的 Token 服务**。对线上业务而言，推理优化不是单纯“把模型跑快”，而是在模型能力基本不损失的前提下，同时压低单位 Token 成本、提升吞吐、保障 TTFT/TPOT 等服务体验指标。

本文将以 GLM-5.2、DeepSeek-V4 等新一代大模型的推理优化实践为例，系统解析快手万擎（StreamLake 官方 Provider 底层系统）在并行策略、PD 分离、KV cache、投机解码和调度系统上的全链路优化方法，并融入个人在 AI Infra 领域的技术点评与思考。

**两个核心判断：**
1. **推理优化是大模型规模化落地的关键。**
2. **优化不能以模型能力损失为代价。**

*产品官方地址：[https://www.streamlake.com/](https://www.streamlake.com/)*

---

# 1. 推理优化：大模型规模化落地的关键

随着大模型从能力验证走向规模化应用，系统关注点已从“能否完成任务”转向“能否稳定、低成本地服务真实业务”。训练决定能力上限，推理则直接影响吞吐、时延和单位调用成本，是模型能力转化为产品价值的关键。

不同于可复制、分发和缓存的传统互联网内容，大模型每次请求都需持续计算并占用 GPU。Agent 多轮规划与工具调用、百万级长上下文及长推理输出，进一步放大了 Token 消耗，使成本、吞吐和时延成为规模化落地的主要约束。

为此，推理优化需在保持模型能力的同时，降低单位 Token 成本、提升有限算力下的吞吐，并稳定满足 TTFT、TPOT 等指标。快手系统软件团队围绕 GLM-5.2、DeepSeek-V4 等新一代模型，从**并行执行、算子与通信、KV Cache、量化、调度及弹性服务**等方面开展全链路优化，构建高性价比推理方案。

---

# 2. 不以模型能力损失为代价做优化

推理服务的价值不能只看 Token 单价。过度量化、精度裁剪或推理参数调整，虽然能够降低成本，却可能损害复杂推理、工具调用和长上下文能力。因此，我们关注的不是绝对低价，而是在模型能力基本保持的前提下，降低单位 Token 成本。

作为快手技术商业化品牌，StreamLake 是“快手万擎”大模型平台对外提供推理服务的官方 Provider。本文介绍的推理引擎 **kLLM**，包含并行执行、PD 弹性、分级 KV cache、算子与编译等能力，是支撑其高性能、低成本推理服务的底层系统能力。

![OpenRouter AutoExacto Benchmark 的 Provider 级能力对比](/images/2026-08-01-kuaishou-kllm-inference-analysis/1.png)
*OpenRouter AutoExacto Benchmark 的 Provider 级能力对比（截图时点 32 日滚动均值）*

![计入 Prompt Cache 后的实际 Token 价格](/images/2026-08-01-kuaishou-kllm-inference-analysis/2.png)
*计入 Prompt Cache 后的实际 Token 价格对比*

如图所示，在 OpenRouter 的同模型 Provider 对比中，StreamLake 的 GPQA Diamond 和 TAU-Bench Airline 表现与模型官方及其他头部 Provider 处于相近水平；与此同时，在计入 Prompt Cache 后，StreamLake 仍保持具有竞争力的实际 Token 价格。公开结果表明，我们并非通过牺牲模型能力换取低价，而是通过系统级推理优化实现能力与成本的兼顾。

---

# 3. 模型结构演进与推理挑战

以 GLM-5.2 和 DeepSeek-V4 为代表的新一代大模型，并非单纯扩大参数规模，而是在**巨量参数与稀疏激活、稀疏/压缩注意力、百万级上下文**三个方向同步演进。模型结构在降低理论计算与存储成本的同时，也改变了推理系统的执行形态：

![模型结构演进带来的系统挑战](/images/2026-08-01-kuaishou-kllm-inference-analysis/3.png)

1. **巨量参数与稀疏激活（MoE）**：使模型能够通过更大的总参数量提升容量，同时将单 Token 激活参数控制在较小比例。但动态专家路由也引入了专家负载不均、小矩阵计算和跨卡 All-to-All 通信。
2. **稀疏注意力（MLA/DSA）与百万上下文**：降低了长序列 Attention 的理论计算成本，但超长上下文仍会显著放大长 Prefill、KV cache 容量、不规则访存和数据搬运压力。

由此带来的推理挑战是：**模型侧降本并不等于系统侧同比提效**。推理瓶颈已经从单一算力问题，转化为计算、通信、显存与调度相互耦合的系统问题。系统既要提升吞吐和资源利用率，又要满足 TTFT、TPOT 和尾延迟等服务目标，最终将模型结构的理论收益转化为真实的吞吐、时延与单 Token 成本收益。

---

# 4. 核心技术全景图

系统软件推理引擎 **kLLM** 是一个覆盖业务接入、调度、推理引擎、硬件资源全链路的高性能推理平台。

![快手万擎 kLLM 核心技术全景图](/images/2026-08-01-kuaishou-kllm-inference-analysis/4.png)

其核心引擎层通过以下技术构筑全栈能力：
* **PD/AF 解耦分离** 与 **TP/PP/EP/CP 多维并行策略**；
* **DeepEP / Mooncake** 高效异构通信；
* **FlashAttention-4 / FlashInfer** 高性能算子；
* **L1 GPU / L2 CPU / L3 Remote** 三级 KV cache 体系；
* **FP8 / INT8 / NVFP4** 多精度量化压缩；
* **MTP / EAGLE-3 / DSpark** 投机解码；
* **SLO 感知调度、Prefix 亲和路由、10秒级弹性伸缩与全链路 Metrics/Trace 监控**。

---

# 5. 关键技术攻坚与深度点评

## 5.1. MLA + DP Attention：Attention DP 与 MoE EP 的混合并行

### 5.1.1 从降低单 Token 开销到扩展节点有效 KV 容量
在百万级长上下文场景中，Attention 计算量与 KV Cache 占用会随上下文长度快速增长。GLM-5.2 通过 DSA 从历史上下文中筛选 Top-k Token 参与 Attention，降低计算量；同时利用 MLA 的压缩表示 cKV，减少单 Token 的缓存开销。

然而，DSA 和 MLA 主要优化计算量与单 Token KV 大小，并未解决多卡部署中的状态分布问题。随着上下文和并发持续增长，瓶颈将进一步转向：节点内多张 GPU 的显存能否共同扩展有效 KV 容量。

### 5.1.2 纯 TP：切分了 Attention 计算，却复制了 cKV
GQA 包含多个独立 KV Head，可沿 Head 维度进行 TP 切分；MLA 的 cKV 则是跨 Head 共享的压缩状态，无法采用相同方式切分。

当 Attention 直接沿用 TP Group 时，各 Rank 虽共同完成计算，却需要处理相同请求并保存相同的 cKV。以 TP=8 为例，同一批请求的 KV Cache 会在节点内复制 8 份。增加 GPU 只能扩展计算能力，无法等比例提升有效 KV 容量。

在长上下文、高并发场景下，即使系统仍有剩余算力，也可能因 KV Cache 空间不足而无法扩大 Batch 或接收新请求。此时，真正的瓶颈已从 Attention 算力转为 TP Group 内重复存储的请求状态。

### 5.1.3 并行策略重构：Attention 按请求并行，MoE 按专家并行
针对 MLA 与 MoE 不同的结构特征，重新划分 Attention 与 MoE 之间的并行边界：
* **Attention 采用 Request DP**：不同 Rank 处理不同请求，仅保存所属请求的 cKV、Token 历史和索引状态；Attention 阶段不再进行跨 DP Rank 的结果同步。
* **MoE 采用 EP**：Router 为每个 Token 选择 Top-k Experts，通过 All-to-All Dispatch 将 Token 发送至专家所在 Rank，专家计算完成后再通过 All-to-All Combine 将结果返回原 Request Rank。
* **Dense/Shared FFN 按需保留 TP**：若非路由计算仍按模型维度切分，则只在对应子路径执行 Gather/Reduce-Scatter，不与 EP 的 Dispatch/Combine 混为一套通信。

![MLA 场景下 Attention DP 与 MoE EP 的并行边界重构](/images/2026-08-01-kuaishou-kllm-inference-analysis/5.png)

让不同状态遵循各自最合适的分布方式：Attention 从 TP8 调整为 Request DP8，每张 GPU 只保存所属请求的 cKV；MoE 继续采用 EP8，通过 All-to-All Dispatch/Combine 完成 Token 与专家之间的路由。

### 5.1.4 收益与边界
在 8 卡配置中，DP Attention 使各 GPU 分别保存不同请求的 cKV，节点有效 KV 容量由纯 TP 的 2.9M Tokens 提升至 21.2M Tokens，增长约 **7.3 倍**，平均 TTFT 下降 **25%**。

> 💡 **个人点评（并行策略与状态分布）**：
> - **按“状态语义”划分并行策略**：并行策略应该按“状态语义”划定边界，而不是按层数或工程惯性照抄。对于 MLA 而言，GQA 有多个独立 KV Head 可沿 Head 切分 TP，而 MLA 的 cKV 是跨 Head 共享的压缩状态，切不动——导致 TP=8 时 KV 在节点内被重复复制 8 份，加卡只加算力而不增加节点有效 KV 容量。kLLM 没有盲目把整个模型换成 DP，而是重画了 Attention 与 MoE 之间的并行边界：Attention 走 Request DP（每卡只存自己请求的 cKV），MoE 走 EP，Dense/Shared FFN 按需保留 TP。这种方法论可直接复用：**先问“这份状态是 per-request 的还是 per-parameter 的”，再决定它应该被切分还是被分发**。
> - **明确性能调优的“收益与失效边界”**：每一次优化都会把系统瓶颈搬到新位置，必须预判瓶颈搬到了哪里。文中明确写出了 DP Attention 的适用边界：优化后系统瓶颈从“KV 复制”转为“Request DP 负载均衡 + EP 的 All-to-All 通信”；在小 Batch、低并发场景下，数据布局转换和 EP 通信开销可能吃掉收益。这种“收益与边界成对给出”的工程洞察，比单纯报好处的 Benchmark 更有指导价值。在做技术选型时，每一项优化都应当附带其失效区间。

---

## 5.2. Ring Attention：将同步聚合改造成分块流水

### 5.2.1 百万上下文下的 CP 扩展
当上下文长度从 200K 扩展到 1M，KV cache 容量随序列长度线性增长，Prefill 阶段的 Attention 计算和显存压力也快速上升。引入 Context Parallelism（CP），沿序列维度将 Context Token 切分到多个 CP Rank，使每张 GPU 只处理部分 Query，并持有对应的 KV 分片。

### 5.2.2 分块式 Ring Attention 实现
对于 CP Rank $i$，本地 Query $Q_i$ 在整个计算过程中保持不动，本地 KV 分片 $K_i, V_i$ 则与其他 Rank 的 KV Block 一同沿 Ring 拓扑逐跳传递。每一轮中，GPU 使用当前 KV Block 计算一部分 Block Attention，同时异步接收下一轮 KV Block；当前计算结束后，直接切换到已经到达的下一 Block。

![Ring Attention 的序列切分与环形计算机制](/images/2026-08-01-kuaishou-kllm-inference-analysis/6.png)

使用 **Online Softmax** 跨轮维护最大值、归一化分母和输出累积状态 $(m, \ell, O)$，不需要物化完整 Attention Matrix。

### 5.2.3 与 All-Gather CP 的执行路径对比
![All-Gather CP 与 Ring Attention 执行路径对比](/images/2026-08-01-kuaishou-kllm-inference-analysis/7.png)

### 5.2.4 实际收益
在相同模型、Batch、CP Degree、KV 精度和硬件配置下，ISL 512K 场景中，Ring Attention CP 相比 All-Gather CP 吞吐提升 **16.9%**。

> 💡 **个人点评（Ring Attention 通用范式与通信参考）**：
> - **“一次性同步聚合 → 分块流水”是可反复套用的通用范式**：Ring Attention 没有改变 Attention 的数学结果，只改变了 K/V 的组织方式和通信时序：本地 Q 不动，KV Block 沿环逐跳传递，计算当前块的同时异步接收下一块，用 Online Softmax 跨轮维护 $(m, \ell, O)$ 状态，从而完全不物化全量 Attention 矩阵。这与 FlashAttention 的 Tiling 思想同源。在系统工程中，**凡是遇到“必须等全量数据到齐才能计算”的瓶颈环节，都值得问一句：能不能拆块、能不能重叠、能不能用在线累积替代全量物化**？
> - **相关技术扩展参考**：
>   - [Ring All-reduce vs. Tree All-reduce 拓扑演进机制对比](https://zhuanlan.zhihu.com/p/432732768)
>   - [Ring Attention 论文与其在长上下文中的系统突破](https://arxiv.org/html/2503.04398v1)

---

## 5.3. DSpark：从前沿架构到在线收益

### 5.3.1 主流投机解码架构的性能权衡
围绕 DeepSeek V4 Flash 的生成时延优化，团队跟进 Eagle3、DFlash 和 DSpark 等路线。DSpark 通过半自回归结构在自回归与并行草稿之间建立了平衡，并进一步以置信调度控制目标模型的验证开销。

![主流投机解码架构在草稿时延、接受长度和验证开销上的性能特征](/images/2026-08-01-kuaishou-kllm-inference-analysis/8.png)

### 5.3.2 完整解码链路
DSpark 首先通过并行网络一次产生多个位置的 logits，再由轻量序列模块逐位置采样。每个位置在采样前，根据前一个已采样 token 计算 Bias 并修正当前位置的 logits。串行部分只执行 Bias 修正与采样，不重复完整模型前向。

![DSpark 半自回归草稿生成示例](/images/2026-08-01-kuaishou-kllm-inference-analysis/9.png)

### 5.3.3 端到端性能收益
在 DeepSeek V4 Flash 的线上典型场景中（ISL 约为 3K–6K、OSL 约为 0.5K），接入 DSpark 后平均 TPOT 降低 **15%**。

> 💡 **个人点评（投机解码选型）**：
> - 投机解码正从单一的草稿模型性能竞争走向“草稿生成 + 目标验证 + 硬件调度”的系统协同。DSpark 不以离线接受率作为唯一指标，而是平衡了草稿延迟、接受长度和动态验证开销，对于长输入场景下的在线服务而言更符合成本与时延平衡。

---

## 5.4. 分级 KV Cache：从容量扩展到高效复用

### 5.4.1 三级缓存与 Cache-Aware 路由
* **L1 · GPU HBM**：保存实例内最热的 KV；
* **L2 · CPU DRAM**：承接从 L1 下沉的数据，在实例内提供低延迟回填；
* **L3 · SSD/分布式存储**：跨实例共享 Prefix KV，持久化高复用前缀。

![L1/L2/L3 分级 KV Cache 与跨实例复用机制](/images/2026-08-01-kuaishou-kllm-inference-analysis/10.png)

首次 Prefill 生成的 Prefix KV 由 L1 下沉至 L2/L3。后续同前缀请求由网关结合匹配长度、缓存位置和负载进行 Cache-Aware 路由；命中后将 KV 回填至 L1，仅计算未命中后缀。

![分级 KV Cache 线上命中率统计表现](/images/2026-08-01-kuaishou-kllm-inference-analysis/11.png)

### 5.4.2 增量前缀树优化
通过火焰图分析发现，传统的全量前缀匹配/插入算法在 Chunked Prefill 分块请求下存在大量冗余计算，导致 GPU Bubble。

![增量前缀匹配/插入优化算法](/images/2026-08-01-kuaishou-kllm-inference-analysis/12.png)

提出基于中间状态缓存的**增量前缀匹配/插入优化算法**后，GPU Bubble 从平均 **400ms 锐减至 30ms**，长请求端到端 Prefill 性能提升约 **40%**。

![前缀复用优化前 GPU Bubble (400ms)](/images/2026-08-01-kuaishou-kllm-inference-analysis/13.png)
*优化前：平均 Bubble 400ms*

![前缀复用优化后 GPU Bubble (30ms)](/images/2026-08-01-kuaishou-kllm-inference-analysis/14.png)
*优化后：平均 Bubble 30ms*

总体而言，完整的分级缓存与 Cache-Aware 路由使缓存命中率提升 **20 个百分点**，SLO 约束下吞吐提升 **30%**。

> 💡 **个人点评（分级缓存与系统层冗余消除）**：
> - **缓存收益源于“缓存 + 路由”的协同**：单独扩充存储容量意义有限。三级 KV Cache 只有配合 Cache Event 实时同步位置信息、以及网关按匹配长度/缓存位置/负载进行 Cache-Aware 路由，才能发挥出额外的 +20pp 命中率。反之，若把 KV 存到了 SSD，后续请求却被路由到了没有该前缀的实例上，就等于白存。存储层次结构本身是经典技术，**核心创新在于将缓存位置提升为了调度的一等输入（First-class Input）**。
> - **切忌假设开源框架已优化过关键路径**：前缀树优化这一节给出了极具落地价值的收益经验：通过火焰图定位热点 + 深读源码，发现分块请求每轮都在用全量 Token 序列重复做匹配和插入。改成基于中间状态的增量算法后，GPU Bubble 从 400ms 锐减至 30ms。**这类系统层框架冗余往往比单算子级的微调回报更高得多**，且经常隐藏在“社区默认实现应该没问题”的假设背后，非常值得在 AI Infra 工程中普及排查！

---

## 5.5. PD 分离：从固定配比到 SLO 驱动

![Cache Aware 与负载感知的智能路由](/images/2026-08-01-kuaishou-kllm-inference-analysis/15.png)

### 5.5.1 SLO Load 与 10 秒级快速启动
以 TTFT 和 TPOT 相对 SLO 的背离程度统一度量 P（Prefill）、D（Decode）两侧压力（Load=1 表示达到目标边界）。

![SLO Load 度量关系曲线](/images/2026-08-01-kuaishou-kllm-inference-analysis/16.png)

启动优化：
* 通过 RDMA 直接从运行中实例加载模型权重；
* 共享 JIT Cache 复用算子编译；
* 基于 CUDA VMM 通过 `unmap/remap` 复用显存布局。

将推理实例启动时间由约 10 分钟降低到 **10 秒以内**（生效速度提升约 60 倍）。

### 5.5.2 大 PD 架构（全局资源池）
![大 PD 架构：从固定 xPyD 服务组到 P/D 全局资源池](/images/2026-08-01-kuaishou-kllm-inference-analysis/17.png)

解除了传统的固定 $x\text{P}y\text{D}$ 服务组绑定，拆分为全局 Prefill Pool 和 Decode Pool：
* 请求到达后，根据 KV cache-aware 和负载均衡选择 P 实例；
* Prefill 完成后，结合 D 侧负载与传输成本选择 D 实例；
* P、D 实例独立根据两侧压力弹性扩缩。

近 30 天 Provider Uptime 达到 **99%+**。

> 💡 **个人点评（弹性控制系统设计）**：
> - **弹性能力应该作为“闭环控制系统”来设计，而非简单的运维扩展脚本**。PD 弹性这一节展现了极高的工程成熟度，三件事环环相扣、缺一不可：
>   1. **度量指标**：弃用传统的 GPU 利用率（设备忙不忙无法直接等价于用户体验好不好），而采用相对 SLO 的背离度，并取预测值与真实值的上界来兼顾及时性与可靠性；
>   2. **执行速度**：打造 10 秒级快速启动（RDMA 直取权重 + JIT Cache + CUDA VMM unmap/remap）。控制算法再聪明，若底层扩容生效慢一个数量级也无法应对流量突发；
>   3. **架构自由度**：升级大 PD 架构打散固定服务组，P/D 各自成池并支持请求级动态组对，使扩容精准加在瓶颈侧。

---

## 5.6. 长请求稳定性优化

![长请求引擎与全局调度协作机制](/images/2026-08-01-kuaishou-kllm-inference-analysis/18.png)

### 5.6.1 Chunk Prefill 公平调度
以 Chunk 为调度粒度，结合 KV 预算分配执行配额；短请求优先，长请求在 Chunk 边界让出资源并保留断点前缀，恢复配额随让出次数递增避免饥饿。

![Chunk Prefill 公平调度机制对比](/images/2026-08-01-kuaishou-kllm-inference-analysis/19.png)

测试显示平均 TTFT 下降 **17.8%**，P50 下降 **26.0%**。

![公平调度前后的整体 TTFT 分布](/images/2026-08-01-kuaishou-kllm-inference-analysis/20.png)
*公平调度前后的整体 TTFT 分布*

---

# 6. 未来演进与架构思考

团队规划了四个代表性演进方向：
1. **异构 PD 架构升级**：用高性能算力/国产卡承载 Prefill 密集计算，用大显存高带宽卡承载 Decode 迭代，通过统一调度中台实现异构协同。
2. **Program-Aware 全生命周期调度**：将调度单元提升至 Program（一次 Agent 会话/工作流），结合“最短程序优先”驱逐与等待 tool-call 时的 KV 卸载/预取。
3. **SLO 感知 QoS 优先级调度**：紧急度优先级调度 + 延迟敏感请求的 QoS 保护与限流。
4. **全栈智能化自适应调优与 Kernel 优化**：引入 RL 模型实时感知流量与负载，自适应优化 PD 配比与分片粒度，并结合 Agentic RL 自动编写 Kernel 算子。

> 💡 **个人点评（未来演进落地优先级判别）**：
> - 在规划的未来演进方向中，**异构 PD 架构**（国产卡承载 Prefill 计算、高带宽 N 卡承载 Decode 访存）与 **Program-Aware 全生命周期调度**（将调度单元从单请求升级到 Agent 会话，利用 tool-call 等待窗口卸载/预取 KV）**确定性最高、落地价值最大**。前者直接契合当前的算力供给现状，后者精准响应了 Agent 化之后的实际负载形态变化。而基于 Agentic RL 的自动写 Kernel 算子则更偏探索性质。

---

# 7. 总结

快手万擎 kLLM 推理引擎面向 GLM-5.2、DeepSeek-V4 等新一代大模型，构建了覆盖并行执行、运行时调度、KV Cache、算子编译、量化与投机解码的全栈推理优化体系。通过模型结构与系统工程的协同优化，将模型侧的理论降本转化为实际的吞吐、时延、资源利用率和单位 Token 成本收益，为大模型服务的规模化部署提供了可复用的工程实践。

---

# 8. 原文参考与来源

* 原文链接：[https://www.6aiq.com/article/kuai-shou-wan-qing-da-mo-xing-tui-li-cheng-ben-he-xing-neng-you-hua-shi-jian-1785484680329](https://www.6aiq.com/article/kuai-shou-wan-qing-da-mo-xing-tui-li-cheng-ben-he-xing-neng-you-hua-shi-jian-1785484680329)
