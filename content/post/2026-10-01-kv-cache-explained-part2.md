---
layout:     post
title:      "一文看懂 KV Cache（下）：工程实践与未来趋势"
subtitle:   "SGLang（RadixAttention）与 vLLM（PagedAttention）如何管理 KV Cache，以及业界演进方向"
description: "KV Cache 科普（下篇）：拆解 SGLang（RadixAttention）与 vLLM（PagedAttention）两大主流框架的工程实践，以及连续批处理、Chunked Prefill、缓存感知调度、PD 分离与多级缓存等系统方案；最后展望 MLA、原生稀疏、低比特 KV、集群级 KV 调度等业界未来发展趋势。上篇讲原理与优化思路。"
author: "tanjunchen"
date: 2026-10-01
published: true
tags:
    - AI Infra
    - LLM
    - 推理加速
    - KV Cache
categories:
    - TECHNOLOGY
showtoc: true
---

# 承上启下

上篇讲清了 **KV Cache 是什么、为什么有效**，以及优化的三套视角（token 级 / 模型级 / 系统级、按显存公式逐因子、按阶段）。下篇接着看**工程怎么落地**：两大主流框架如何管理 KV Cache，如何从单机走向集群，以及业界未来往哪走。

> 若还没看过上篇《一文看懂 KV Cache（上）：从自回归原理到优化思路》，建议先读，再看本篇的工程实现。

---

# 3. KV Cache 工程实践管理

理论说完，来看两大主流开源框架怎么把这些落到实处。

![工程落地：两大框架 + PD 分离 + 多级缓存](/images/2026-10-01-kv-cache-explained/4-system.svg)

## 3.1 SGLang：RadixAttention

SGLang 的 KV Cache 管理贯穿在 Scheduler 的各个流程里，核心是 **RadixAttention**：

![SGLang RadixAttention 基数树前缀共享与 HiCache](/images/2026-10-01-kv-cache-explained/6-radix.svg)

- **基数树（Radix Tree）组织前缀**：用一棵基数树实现 KV 缓存的快速匹配、插入与替换。与"请求结束就丢弃 KV"的系统不同，**RadixAttention 会把 Prefix 和 Generate 阶段产生的 KV 都缓存下来**，最大程度提升 KV 被新请求复用的概率（对比之下，ChunkAttention 只聚焦在 prefix 本身）。
- **HiCache 多级缓存**：把 KV 在 **GPU ↔ CPU ↔ 远端存储**之间分层管理。关键设计：
  - **HiRadixTree**：GPU/CPU 双层前缀缓存树，原生支持 KV 在两级间自动同步；
  - **可插拔存储后端**：对接 3FS、Mooncake、NIXL 等，统一 `batch_get/batch_set` 接口、零拷贝；
  - **预取与等待并行**：请求入队即触发 `prefetch_from_storage`，把命中的 KV 在排队等待期间异步加载到 Host 内存，把排队的"空闲时间"利用起来；
  - **加载与计算 Overlap**：KV 逐层加载（独立 CUDA Stream），第 i 层 KV 就绪即可开始该层前向，无需等全部层加载完，从而把 I/O 开销隐藏在计算里，显著降低 TTFT。
- **稀疏化**：
  - **SWA（滑动窗口注意力）**：用"双池（full/swa）+ 滑窗即时释放 + tombstone 保留前缀命中"的组合，让窗口外的 KV 真正被回收，同时前缀仍可共享——这是稀疏里少数**真正缩小 KV 占用**的方案。
  - **DeepSeek NSA（原生稀疏注意力）**：KV 全存、attention 只读一部分。Indexer 给每个 page 打分，融合 Compressed(历史摘要页)+ Selected(Top-K 页)+ Sliding(近期窗口) 三路，把注意力从 `O(seq)` 降到 `O(K·page + W)`，长序列下算力和带宽都大幅下降。

## 3.2 vLLM：PagedAttention

vLLM 的 KV Cache 管理以 **PagedAttention** 为基石，思想**类比操作系统的虚拟内存**：

![vLLM PagedAttention 分页映射机制](/images/2026-10-01-kv-cache-explained/7-paged.svg)

- **分页管理**：把每个序列的 KV Cache 切成**固定大小的物理 Block**，每个 Block 存若干 token 的 KV。用一张 **Block Table**（类比 OS 页表）记录逻辑 KV 分布在哪些物理 Block 上。**逻辑连续、物理不连续**，从而消除显存碎片、大幅提升利用率。
- **初始化预分配**：启动时用 dummy 数据跑一次前向，度量激活显存，**估算能分配多少 KV Block**，然后一次性预分配 GPU 显存池（避免运行时频繁申请）。
- **Block 管理机制**：`KVCacheBlock` 数据结构 + `BlockPool` 统一管理，空闲块用 **FreeKVCacheBlockQueue**（LRU 双向链表）组织，方便驱逐最久未用的块。
- **Prefix Caching（自动前缀缓存）**：给 Block 算 hash，相同前缀的 Block 直接命中复用，跨请求共享 system prompt / 公共上下文。
- **KV Connector**：把 KV 的跨节点传输抽象出来，支撑 **PD 分离**（Prefill / Decode 分别部署）下的 KV 搬运。

> 一句话对比：**SGLang 的 RadixAttention 追求"KV 被复用的概率最大"，vLLM 的 PagedAttention 追求"显存装得下的效率最高"**——两者思路互补，如今也在互相借鉴（vLLM 也有 prefix caching，SGLang 也做分页）。

## 3.3 调度与批处理：让 KV Cache 用得更满

KV Cache 的管理离不开**调度**——怎么把多个请求高效地塞进 GPU，直接决定显存和算力的利用率。

![连续批处理与 Chunked Prefill 调度](/images/2026-10-01-kv-cache-explained/8-batching.svg)

- **Continuous Batching（连续批处理）/ 迭代级调度**：源自 **ORCA**。传统静态批处理要等整批请求都生成完才能换下一批，GPU 大量空转；ORCA 改成**以「迭代」为粒度**调度——每做完一次 iteration（一步 prefill 或 decode），调度器就检查一遍：哪个序列生成完了就移出、新请求立刻补位。配合选择性批处理（selective batching），显著提升 GPU 利用率。这也是 vLLM / SGLang 的调度基石。
- **Chunked Prefill（分块预填充）**：源自 **SARATHI**。把长 prompt 的 Prefill 切成小块，并「搭车」到 Decode 批次里一起算，平滑掉 Prefill 的算力尖峰，避免长 prompt 把其他请求的 Decode 卡住，兼顾 TTFT 与 TPOT。
- **缓存感知调度（Cache-aware Scheduling）**：给每个请求的输入分块算 hash，与各实例已有的缓存键比对，找出**前缀匹配最长**的节点优先调度——把请求分到「能命中缓存」的实例，避免无谓的 Prefill 重算。

## 3.4 从单机到集群：PD 分离 + 多级缓存

当上下文越来越长、并发越来越大，KV Cache 早已装不下单卡显存，工程上出现两条关键主线：

- **PD 分离**：Prefill（compute-bound）与 Decode（memory-bound）分开部署、各自扩缩容，中间通过 **KV 传输**（Mooncake、NIXL、LMCache 等）把 Prefill 产出的 KV 送到 Decode 节点。
- **多级缓存 / KV Offload**：把历史 KV 从昂贵的 HBM，逐级下沉到 **DRAM → 本地 SSD → 分布式存储**（如 3FS，提供 TiB/s 级聚合带宽），会话延续时按需加载复用。理论基础可参考公开论文 [CachedAttention（*Cost-Efficient LLM Serving for Multi-turn Conversations*）](https://arxiv.org/abs/2403.19708)。

两个代表性的公开系统，把这套思路讲得很透：

- **Mooncake（以 KVCache 为中心的分离式架构）**：由全局调度器 **Conductor** 统一编排，请求携带「可复用前缀块 ID + 完整缓存块 ID」；由 **Messenger** 以独立进程**逐层流式传输** KV，并与增量 Prefill **重叠**执行。它还给出了「远端传 KV 划不划算」的判据：只要单卡算力 / 单卡通信带宽的比值小于 `hidden_dim × 常数`，那么**从远端传 KVCache 比原地重算更省**——既省算力又降 TTFT，这正是全局 KV 调度的理论依据。
- **MemServe（弹性内存池 MemPool）**：把集群里所有 CPU DRAM 与 GPU HBM 统一成分布式内存池，用**全局 prompt 树 + 基数树索引**（token / session / document 三类）管理「活跃 KV」与「历史 KV」，一套机制同时支撑上下文缓存、分离式推理与序列并行。

这类方案要真正跑好，还得解决三件事：**调度要能感知缓存分布**（否则请求被分到无缓存节点，白白触发 Prefill 重算）、**跨介质搬运要够快**（HBM–DRAM–SSD 之间的传输别把复用收益吃掉）、**缓存要够稳**（推理进程重启不能丢 KV）。

---

# 4. KV Cache 优化：业界未来发展趋势

把上面的脉络往前延伸，可以看到几条正在发生的趋势：

- **模型级"原生优化"成为标配**：**MLA**（DeepSeek）已证明低秩压缩能在几乎不损精度的前提下大砍 KV，正被越来越多模型采纳；**NSA**（原生稀疏注意力）把稀疏从"推理期补丁"变成"训练即内建"，长上下文下的算力/带宽收益更稳。GQA 早已是默认选择。
- **低比特 KV 常态化**：FP8 KV 逐步落地，INT4/更激进的量化在探索中；量化 + 稀疏 + 低秩「组合拳」会成为标准配置。
- **PD 分离与 KV 传输标准化**：Prefill/Decode 解耦已是大规模服务的主流架构，围绕 KV 传输的生态（Mooncake、NIXL、LMCache、框架内置 KV Connector）正在快速成熟，KV 逐渐变成一种**可在集群里自由流动的"数据"**。
- **分层缓存 / 存算分离**：HBM–DRAM–SSD–分布式存储的多级 KV 池，配合高性能存储（3FS 等）与 RDMA 网络，把"显存装不下"的长上下文问题，转化为"存储 + 调度"问题。
- **集群级 KV 调度与全局复用**：从"单卡显存技巧"走向"集群级存算调度"——构建**全局 KV 索引**、让调度器**感知缓存命中**、把请求优先分到"命中率高、加载快"的节点，最大化多轮对话/RAG 场景的前缀复用。
- **长上下文是核心驱动力**：面向 100K–1M 级上下文，稀疏（少读）+ 复用（少算）+ offload（多存）+ 硬件协同（快传）会长期组合演进。
- **与投机解码、硬件协同**：LayerSkip / 自投机等与 KV 优化正交，可叠加；同时访存带宽、互联（NVLink/RDMA）、近存计算等硬件能力，也在反过来决定 KV 方案的上限。

> **一句话收尾**：KV Cache 正在从一个「省显存的小技巧」，长成一整套贯穿**模型架构—推理框架—集群存算调度**的系统工程。理解它，基本就理解了大模型推理性能优化的半壁江山。

---

# 附录：延伸阅读

**综述与系列博客**

- [A Survey on Large Language Model Acceleration based on KV Cache Management](https://arxiv.org/abs/2412.19442)（KV Cache 管理综述）
- rossiXYZ《探秘 Transformer 系列之（20）—— KV Cache》及后续篇：
  - <https://www.cnblogs.com/rossiXYZ/p/18799503>
  - <https://www.cnblogs.com/rossiXYZ/p/18811723>
  - <https://www.cnblogs.com/rossiXYZ/p/18811785>
  - <https://www.cnblogs.com/rossiXYZ/p/18815541>
- [A Survey on Efficient Inference for Large Language Models](https://arxiv.org/abs/2404.14294)

**模型级 / 稀疏 / 量化**

- [GQA: Training Generalized Multi-Query Transformer Models](https://arxiv.org/abs/2305.13245)
- [H2O: Heavy-Hitter Oracle for Efficient Generative Inference](https://arxiv.org/abs/2306.14048)
- [StreamingLLM: Efficient Streaming Language Models with Attention Sinks](https://arxiv.org/abs/2309.17453)
- [YOCO: You Only Cache Once](https://arxiv.org/abs/2405.05254)

**系统 / 调度 / 分离式**

- [Orca: A Distributed Serving System for Transformer-Based Generative Models](https://www.usenix.org/conference/osdi22/presentation/yu)（迭代级调度 / Continuous Batching）
- [SARATHI: Efficient LLM Inference by Piggybacking Decodes with Chunked Prefills](https://arxiv.org/abs/2308.16369)
- [Efficient Memory Management for LLM Serving with PagedAttention（vLLM）](https://arxiv.org/abs/2309.06180)
- [Mooncake: A KVCache-centric Disaggregated Architecture for LLM Serving](https://arxiv.org/abs/2407.00079)
- [MemServe: Context Caching for Disaggregated LLM Serving with Elastic Memory Pool](https://arxiv.org/abs/2406.17565)
- [CachedAttention（多轮对话 KV 复用）](https://arxiv.org/abs/2403.19708)
  - vLLM：<https://github.com/vllm-project/vllm>　
  - SGLang：<https://github.com/sgl-project/sglang>
  - LMCache：<https://github.com/LMCache/LMCache>

> 本文为学习性科普，理论与框架细节以各论文与开源项目官方文档为准；实现随版本迭代较快，请以最新源码为准。
