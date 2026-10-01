---
layout:     post
title:      "一文看懂 KV Cache（上）：从自回归原理到优化思路"
subtitle:   "为什么大模型推理离不开 KV Cache，以及围绕显存公式的一整套优化方法论"
description: "KV Cache 科普（上篇）：先讲清自回归推理的冗余计算问题、KV Cache 的原理与显存占用；再从 token 级 / 模型级 / 系统级三个层次，以及显存公式的每个因子（序列长度、头数、比特、头维度、层数、显存管理）梳理优化思路。下篇继续讲两大框架的工程落地与业界未来趋势。"
author: "tanjunchen"
date: 2026-09-30
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

# 写在前面

本文分**上、下**两篇，把 KV Cache 从原理到工程串起来：**是什么 → 怎么优化 → 框架怎么落地 → 未来往哪走**。

- **上篇（本文）**：KV Cache 是什么、为什么省显存又提速、以及优化思路的三套视角；
- **下篇**：SGLang / vLLM 两大框架的工程实践，以及业界未来发展趋势。

如果下面两个问题你都能答上来，上篇可以快速略过：

1. **KV Cache 为什么能提升推理性能？**
2. **围绕显存公式，主流的优化方向有哪些？**

> 本文为科普综述，理论基础主要参考公开论文《A Survey on Large Language Model Acceleration based on KV Cache Management》、rossiXYZ《探秘 Transformer 系列之 KV Cache》系列博客，以及 vLLM / SGLang / Mooncake 等开源项目的公开设计，配图为笔者自绘示意图。完整延伸阅读见下篇附录。

---

# 1. KV Cache 介绍

## 1.1 背景：自回归推理的「重复劳动」

大模型（Transformer 解码器）生成文本是**自回归**的：一个 token 一个 token 地吐，每生成一个新 token，都要拿它去和**前面所有 token**做自注意力（Self-Attention）。

随着输入的 token 列表变长，自注意力阶段会成为性能瓶颈——token 越多，相乘的矩阵越大，而这些浮点运算（FLOPs）受限于 GPU 的算力。于是推理就出现两个老大难：**延迟高**、**吞吐低**。根子在于：

- 生成的**序列自回归特性**：朴素实现里，每一步都要为所有历史 token 重新计算 Key、Value 向量；
- 注意力与序列长度呈**二次方关系**，序列越长，延迟开销越大。

![自回归生成与 KV Cache 原理](/images/2026-10-01-kv-cache-explained/1-autoregressive.svg)

## 1.2 总体思路：用空间换时间

**KV Cache 的本质，就是「用空间换时间」**：把已经算过的 Key / Value 矩阵缓存下来，避免在自回归生成中反复重算。它很像人脑的「短期记忆」，让模型高效复用历史信息。

**为什么可以缓存？—— 因果注意力（Causal Mask）**：生成是单向的，前面的 token 看不到后面的 token，所以已生成 token 的 Key/Value 不会受后续影响。也就是说，`i=3` 时算出的 `k₂`，和 `i=4` 时的 `k₂` **完全相同**。既然每一层的历史 K/V 都不变，那就没必要重算——**算一次，存起来，后面直接读**。

朴素实现里的冗余点遍布各处：Embedding、K/V 生成、`QKᵀ`、`softmax·V` 全都在重复计算，自注意力复杂度是 `O(n²·d)`（`d` 为向量维度）。KV Cache 把历史 K/V 固化下来后，每一步只需为**新 token** 计算：全量的 `QKᵀ` 退化为 `qKᵀ`，复杂度降到 `O(n·d)`，FLOPs 大幅削减。

> **一个隐含前提**：只有满足「因果性」的模型才适用 KV Cache。GPT 类 decoder 用了 causal mask，天然满足；而 BERT 类 encoder 是双向注意力，当前 token 依赖未来 token，不满足因果性，也就无法使用 KV Cache。

## 1.3 资源占用：KV Cache 是隐形吃显存大户

LLM 推理分两个阶段，显存与关注的指标各不相同：

![两阶段推理与显存占用](/images/2026-10-01-kv-cache-explained/2-memory.svg)

- **Prefill（预填充）**：一次性处理完整 Prompt，并行度高、**计算密集**（compute-bound），产出第一个 token 和全量 KV Cache。关注 **TTFT（首字延迟）**。
- **Decode（解码）**：自回归逐个生成后续 token，单步计算量小，但每一步都要**读取全部历史 KV Cache**，因此**访存密集**（memory-bound）。关注 **TPOT / TBT（吐字间隔）**。

显存这边有个关键认知：

- **模型权重**是固定的，不随序列长度变化；
- **KV Cache** 随 `batch × 序列长度`**线性增长**，聊得越久、并发越大，吃得越多；
- **峰值显存 ≈ 模型权重 + KV Cache**。

KV Cache 的显存可以这样估算：

```text
显存 ≈ 2 × batch × seq_len × num_layers × num_kv_heads × head_dim × dtype_bytes
```

其中系数 `2` 代表 Key + Value。**记住这个公式——后文几乎所有优化，都是在对这 6 个因子「逐个下手」。**

![KV Cache 显存公式与逐因子优化](/images/2026-10-01-kv-cache-explained/5-formula.svg)

**算一笔账更直观**（以类 Qwen-7B 的参数量级为例：`num_layers=32`、`num_kv_heads=32`、`head_dim=128`、FP16）：

- 单个 token 的 KV ≈ `2 × 32 × 32 × 128 × 2 B ≈ 512 KB`；
- 上下文从 **4K** 涨到 **100K**，仅 KV Cache 就从约 **2 GB** 膨胀到约 **50 GB**——这还只是 `batch=1`。

序列越长、并发越大，KV Cache 增长得越凶，很多场景下它才是显存真正的「头号杀手」，而非模型权重本身。这也解释了后文为何有如此多的优化都围着它打转。

## 1.4 几个容易被忽略的点

- **KV Cache 省的主要是 Decode 阶段**：Prefill 要算完整 attention 并填充缓存，计算量并没减少；真正省下来的是 Decode 阶段——前 `n-1` 个 token 的 K/V 无需重算，且每步只输出一个 token 的 logits，FFN 的计算量也随之下降。
- **跨请求复用也能省 Prefill**：上一条针对单个请求；但当多个请求**共享前缀**（相同 system prompt、多轮对话历史）时，缓存的前缀 K/V 可跨请求复用，直接跳过这部分 Prefill 重算，显著降低 **TTFT**——这正是下篇 RadixAttention / Prefix Caching 的立足点。
- **为什么没有 Q-Cache？** 因为每一步只用到「当前 token 的 Q」去和「全部历史 K/V」做注意力，历史的 Q 在后续步骤里不再被使用，缓存它没有意义；而历史 K/V 每一步都要被读取，所以只缓存 K/V。
- **每一层都有独立的 KV Cache**：Transformer 每个 block 维护自己的 K/V 缓存，通常表示为 `[B, L, H, D]` 的 4D 张量（批量、长度、头数、头维度）。
- **适用前提**：KV Cache 成立依赖两个前提——**因果注意力**（历史 K/V 不受未来影响）与**推理时权重固定**（同一 token 的 Embedding + 位置编码固定，算出的 Q/K/V 也固定）。数学上，「缓存前缀 K/V 再拼接计算」与「整段序列重新计算」结果**完全等价**，但计算量大幅下降。此外，**位置编码也必须满足因果性**：若像 ReRope 那样在新增 token 时重新调整整段序列的位置编码，同一个 token 两次算出的 embedding 就不同，缓存条件即被破坏。也正因 KV 是**位置相关**的，文本中重复出现的同一个 token 并不能共享同一份 KV Cache。

---

# 2. KV Cache 优化思路

## 2.1 先明确优化目标：吞吐与延迟

推理加速一般从两个层面衡量：

- **吞吐量（Throughput）**：系统视角的成本指标，如 tokens per second（tps），代表单位时间能为所有用户生成多少 token。吞吐越高，单 token 成本越低。
- **延迟（Latency）**：用户视角的体验指标，主要是 **TTFT**（首 token 生成时间）和 **TPOT**（每个输出 token 的时间），以及 token 间隔 **TBT**。生成总耗时 ≈ `TTFT + TPOT × 生成 token 数`。

由于 **Prefill 是计算瓶颈**（compute-bound，耗时随输入长度**超线性**增长）、**Decode 是访存/传输瓶颈**（memory-bound，需要更大 batch 才能喂饱算力），**两个阶段的优化手段往往不同**，这也是后面「按阶段优化」的由来。

## 2.2 三套视角：按层次分类 + 按公式下手 + 按阶段划分

![KV Cache 优化的两套视角](/images/2026-10-01-kv-cache-explained/3-taxonomy.svg)

### 视角一：token 级 / 模型级 / 系统级

综述《A Survey on LLM Acceleration based on KV Cache Management》把优化划成三个层次，越往下越「治本」，但改动成本也越大（另一篇《Thus Spake Long-Context Large Language Model》则按 Token Dropping / Token Merging / Layer-wise Sharing 分类，角度更贴近「公式因子」，可与视角二对照看）：

- **Token 级优化**：不改模型结构、不动系统并行，只在 token 粒度做精细化管理。五类方法：**选择、预算分配、合并、量化、低秩分解**。特点是即插即用（如 H2O、SnapKV、KIVI 量化）。
- **模型级优化**：从架构层面减少 KV 的生成与依赖。包括**注意力分组共享**（MQA/GQA/MLA）、**新注意力机制**、**非 Transformer 架构**（RNN 类的 Mamba、RWKV）。治本，但通常要重训。
- **系统级优化**：从底层硬件与调度入手。包括**内存管理**（PagedAttention、虚拟内存适配）、**调度策略**（前缀感知、抢占式上下文切换）、**硬件感知设计**（多 GPU、I/O、异构、SSD offload）。无损、工程收益最直接。

### 视角二：对着显存公式，逐因子优化

把 §1.3 的公式拆开，每个因子都是一个优化方向：

- **↓ 序列长度 `seq_len`**：这是最大的一块，分两条路——
  - **稀疏化（丢弃不重要的 token）**：按「丢掉的 KV 还能不能找回」可分两类——**不可召回**（Non-recallable，判定不重要就永久丢弃，如只保留 attention sink + 近期窗口）与**可召回**（Recallable，考虑到 token 重要性会动态变化，先换出、需要时再载回）。常见落地形态：
    - *静态稀疏*：固定窗口。**Window Attention**（滑窗，窗口外永久驱逐）、**StreamingLLM**（利用"注意力沉积"效应，保留最早几个 token + 近期窗口，支持"无限"长度）；线性注意力（Linear Transformer、RWKV、Mamba）把复杂度降到线性，但可能损失表达能力。
    - *动态稀疏*：算法挑选"最相关的历史 token"。**H2O**（Heavy-Hitter，靠累积注意力分挑高影响力 token）、**Keyformer**（近期 token + 关键 token 混合）、**SnapKV**。
    - *面向 Prefill 的稀疏*：RAG / 长文档场景「输入长、输出短」，在 Prefill 阶段就 drop 掉不重要的 prompt token。
    - *按层 / 按头的稀疏*：**PyramidKV / PyramidInfer**（金字塔式分配，低层多、高层少）、**AdaKV / DuoAttention / RazorAttention**（区分"检索头"和"流式头"，差异化分配）。
    - *聚类 / 检索式*：**InfLLM、Quest** 以块/簇为粒度组织 KV，只取 Top-K 块参与计算；**InfiniGen** 更进一步——在算第 `i-1` 层时就**预测**第 `i` 层需要哪些 KV，把 KV 池放在 CPU、只把关键条目预取回 GPU，从而缓解长文本下的显存与 PCIe 带宽压力。
  - **复用（无损，工程优化）**：复用 system prompt、多轮对话历史等。**Prompt Cache**（预定义可复用文本段）、**ChunkAttention**（前缀树分块共享）、**RadixAttention**（SGLang，基数树，Prefix 和 Generate 都缓存）。这是**算法无损、无需训练**的优化。
- **↓ KV 头数 `num_kv_heads`**：**MQA**（多个 Query 头共享一组 K/V）、**GQA**（分组共享，MQA 与 MHA 的折中，已成主流）。
- **↓ 每值比特 `dtype_bytes`**：**量化**，把 KV 从 FP16 压到 FP8 / INT8 / INT4，在保持 slot 数不变的前提下直接砍显存（需平衡精度损失）。
- **↓ 头维度 `head_dim`**：**MLA**（DeepSeek，类 LoRA 的低秩压缩，大幅减小 KV 大小）、**Double Sparsity**（Token 稀疏 + Channel 稀疏结合）。
- **↓ 缓存的层数 `num_layers`**：不是真减层，而是**只缓存部分层的 KV**。跨层共享的 **YOCO**（只用前几层产生 KV）、**CLA**（相邻层共享 K/V 头）、**MLKV**（跨层共享，MQA 的极端扩展）；以及 **LayerSkip**（早退 + 自投机解码，后续层不需要 KV）。
- **↑ 显存利用率**：GPU 上 KV Cache 的有效存储率其实不高，用 **PagedAttention** 这类分页管理来消除碎片。

### 视角三：按阶段优化

- **Prefill 阶段**：主要压缩 prompt 序列长度，挑出重要 token；
- **Decode 阶段**：稀疏读取（只读 Top-K 页）、offload 到 CPU/SSD 等。

> 小结：**模型级**（MQA/GQA/MLA）从源头减少 KV，**token 级**（稀疏/量化）压缩已有 KV，**系统级**（分页/复用/offload）把 KV「装得下、传得快、用得省」。三者正交，实践中往往组合使用。

---

# 上篇小结

到这里，上篇讲清了两件事：**KV Cache 为什么有效**（因果注意力 + 权重固定，让历史 K/V 可缓存复用，把 `O(n²)` 逼近 `O(n)`），以及**优化的三套视角**（按层次、按公式因子、按阶段）。

**下篇**继续落地：看 SGLang（RadixAttention）与 vLLM（PagedAttention）两大框架怎么把这些思路做进工程，以及从单机走向集群（PD 分离 + 多级缓存）的业界未来趋势。
