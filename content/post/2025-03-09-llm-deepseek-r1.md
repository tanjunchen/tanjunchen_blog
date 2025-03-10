---
layout:     post
title:      "LLM 教程（3）- DeepSeek R1 论文精读"
subtitle:   "LLM 教程（3）- 精读 DeepSeek-R1 的论文 [《DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning》](https://arxiv.org/abs/2501.12948) 了解现象级 R1 模型是怎么做出来的。"
description: ""
author: "陈谭军"
date: 2025-03-09
published: true
tags:
    - AI
    - 大模型
    - DeepSeek
categories:
    - TECHNOLOGY
showtoc: true
---

# 1. 序言

下图展示了 OpenAI（公开文献） 从预训练开始逐步训练出一个 GPT 助手的步骤；pre-training -> SFT -> RM -> RL 是典型的大模型训练过程。 

![](/images/2025-03-09-llm-deepseek-r1/1.png)

# 2. DeepSeek R1 论文精读

接下来精读下 DeepSeek-R1 的论文 [《DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning》](https://arxiv.org/abs/2501.12948) 了解现象级 R1 模型是怎么做出来的。

## 2.1 摘要

DeepSeek 推出了他们的第一代推理模型，DeepSeek-R1-Zero和DeepSeek-R1；
* DeepSeek-R1-Zero
  * 这是一个跳过监督微调（SFT）步骤， 直接通过大规模强化学习（RL）训练得到的模型，具备卓越的推理能力。R1-Zero 是在 DeepSeek-V3 基座大模型上直接进行 RM+RL，跳过中间的 SFT；
  * 通过大规模 RL，DeepSeek-R1-Zero 自然地涌现出许多强大且有趣的推理行为。不过，它也存在可读性差、混用语言等问题。
* DeepSeek-R1
  * 为了解决以上提到的 R1-Zero 存在的问题，并进一步提升推理性能， 在 RL 阶段之前引入了多阶段训练和冷启动数据，训练得到的模型称为 DeepSeek-R1。
  * DeepSeek-R1 在推理任务上的表现与OpenAI-o1-1217不相上下，如下是测试数据；

![](/images/2025-03-09-llm-deepseek-r1/2.png)

为了支持研究社区，deepseek 此次开源了8 个推理模型：
1. DeepSeek-R1
2. DeepSeek-R1-Zero
3. DeepSeek-R1-Distill-Llama-70B
4. DeepSeek-R1-Distill-Qwen-32B
5. DeepSeek-R1-Distill-Qwen-14B
6. DeepSeek-R1-Distill-Llama-8B
7. DeepSeek-R1-Distill-Qwen-7B
8. DeepSeek-R1-Distill-Qwen-1.5B

其中，后面 6 个是以 Qwen/Llama 作为基座模型，利用 DeepSeek-R1蒸馏出来的 dense 模型。

## 2.2 引言

近年来，大模型的迭代与演进速度非常快，DeepSeek 的整体训练过程如下图所示：

![](/images/2025-03-09-llm-deepseek-r1/3.png)

### 2.2.1 Post-Training：完整 training pipeline 的重要组成部分

现在，post-training已成为完整 training pipeline 的一个重要组成部分。

#### 作用

Post-Training 的好处：
1. 提高推理任务的准确性；
2. 与人类社会价值观对齐；
3. 能适应用户偏好；
4. 相对于预训练，所需的计算资源极少；

#### 提高推理能力：与 OpenAI-o1 的思路区别

具体到提高推理能力方面：
* OpenAI 的 o1系列模型首次通过增加推理过程中的思维链长度（Chain-of-Thought, CoT） 来引入inference-time scaling。 这种方法在数学、编码和科学推理等推理任务上取得了显著的效果。
* 但是，有效的test-time scaling仍然是社区的一个开放性问题。 此前，业界已经探索了很多方法，包括 process-based reward models、reinforcement learning 等，但这些方法都没有达到与 OpenAI o1 相当的通用推理性能

deepseek 迈出了通过纯强化学习（pure RL）提高模型推理能力的第一步。

* deepseek 的目标是探索大模型在没有任何监督数据的情况下 —— 单纯通过 RL 过程自我进化 —— 发展出推理能力的潜力。
* 具体来说，deepseek 使用DeepSeek-V3-Base作为基础模型，采用 GRPO 作为 RL 框架，来提高模型在推理方面的表现。
* 在训练过程中，DeepSeek-R1-Zero 自然地涌现出许多强大且有趣的推理行为。经过几千步的 RL 训练后， DeepSeek-R1-Zero 在推理基准测试中表现出色。例如，AIME 2024 的 pass@1 得分从 15.6% 提高到 71.0%，加上多数投票，得分进一步提高到 86.7%，与 OpenAI-o1-0912 表现相当。

然而，DeepSeek-R1-Zero 面临着诸如可读性差、语言混用等挑战。为了解决这些问题并进一步提升推理性能， deepseek 引入了少量的冷启动数据和一个 multi-stage training pipeline，训练得到 DeepSeek-R1， 其性能与 OpenAI-o1-1217 相当。

最后，deepseek 还进一步探索了从 DeepSeek-R1 蒸馏较小的 dense models。 例如，使用 Qwen2.5-32B（Qwen, 2024b）作为基础模型，两种思路：
* 直接在 Qwen-32B 上进行强化学习（RL），得到一个推理模型；
* 从 DeepSeek-R1 进行蒸馏（把 DeepSeek-R1 的知识“传授”给 Qwen2.5-32B），得到一个推理模型；

deepseek 发现后者（蒸馏）的性能优于前者（直接 RL）。 这表明尺寸更大的基础模型发现的推理模式对于提高推理能力至关重要。deepseek 开源了基于 Qwen/Llama 的蒸馏模型。 值得注意的是，deepseek 蒸馏出的 14B 模型在 AIME 上的表现大幅超过了现有的开源模型 QwQ-32B-Preview ， 而蒸馏出的 32B 和 70B 模型在针对 dense models 的推理基准测试中创下了新纪录。

### 2.2.2 贡献

#### post-training：在基础模型上进行大规模强化学习

deepseek 跳过监督微调（SFT）步骤，直接在基础模型（base model）上应用 RL。 这会使模型去探索解决复杂问题时的思维链（CoT），用这种方式训练得到的就是 DeepSeek-R1-Zero。
* DeepSeek-R1-Zero 展现出自我验证、反思和生成长 CoT等能力，为社区研究树立了一个重要的里程碑。
* 值得注意的是，这是首个证实大模型的推理能力可以通过纯 RL 激励实现（无需 SFT）的公开研究，这一突破为该领域的未来发展铺平了道路。

此外，deepseek 还介绍了开发 DeepSeek-R1 的 pipeline，该 pipeline 包含：
1. 两个 RL stage
  * 一个用于发现更强的推理模式（stage 2）
  * 一个用于与人类偏好对齐（stage 4）
2. 两个 SFT stage：用于激发出模型的 reasoning and non-reasoning 能力。

#### 蒸馏：小型模型也可以很强大

deepseek 证明了大型模型的推理模式可以被蒸馏到小型模型中，
* 与在小型模型上进行 RL 发现的推理模式相比，蒸馏可以取得更好的性能。
* 开源的 DeepSeek-R1 及其 API 将有助于社区在未来蒸馏出更好的小模型。

利用 DeepSeek-R1 生成的推理数据，deepseek 微调了几个在社区中广泛使用的小型 dense 模型。 结果显示，这些经过蒸馏的小型 dense model 在基准测试中表现非常好。

## 2.3 方法

### 2.3.1 概述

以往的研究重度依赖于大量的监督数据（人类标注数据）来提升模型性能。 本文的研究证明：
* 不使用监督微调（SFT），单纯通过大规模强化学习（RL）也能显著提升推理能力。R1-Zero 证明了对已预训练好的模型，不需要经过 SFT，只需要纯粹的 RL，就能让模型涌现 CoT 推理能力。
* 通过引入少量冷启动数据（SFT 训练数据），还可以进一步增强性能。

备注：
* SFT是监督式微调，也就是准备好一堆标注好的数据，让模型去学习拟合，可以粗略理解为刷题，大量的刷题学习能解决类似的题目；
* RL是强化学习，只告诉模型什么是好的什么是不好的，过程中模型自己学习怎么达到目标，可以理解为不靠刷题，自己去理解探索数学和世界的规律，理论上灵活性强，上限更高，还有可能探索出人类未知的能力。

**强化学习首次出圈是 AlphaGo，AlphaGo 先学习人类棋谱，再用强化学习自我对弈进化，而随后的 AlphaGo Zero 没有人类棋谱，只定义好围棋奖励规则，模型自己学习怎么下，达到更高的水平。R1-Zero 这命名也是致敬 Alpha-Zero，因为它们非常类似，脱离人类的指导自主发现规律提升智能。**

为什么之前没人做到？
1. 模型能力没达到一定阈值，仅通过强化学习没法涌现；
2. 强化学习是种方法，过程中用什么算法做价值判定也很大程度影响效果；
3. o1 可能已经做了同样的探索和结果，也可能没有，它闭源不公开，而 DeepSeek 首次探索并公开了；

DeepSeek-R1-Zero 强化学习训练过程如下所示：

![](/images/2025-03-09-llm-deepseek-r1/4.png)

### 2.3.2 DeepSeek-R1-Zero：在基础模型（base model）上进行强化学习

之前的研究已经证明，强化学习对提高推理性能非常有用。 但是，这些前期研究都重度依赖监督数据，而收集监督数据是个费事费力的过程。
deepseek 探索在没有任何监督数据的情况下（单纯通过 RL 过程自我进化），大模型发展出推理能力的过程。

#### 2.3.2.1 强化学习算法：Group Relative Policy Optimization (GRPO)

为了降低 RL 训练成本，deepseek 采用了GRPO（组相对策略优化）算法， 该方法放弃了 critic model（通常尺寸与 policy model 大小相同），而是用 group scores 来估计基线。
具体来说，对于每个问题q, GRPO 从老的 policyπθold中采样得到一组输出o1,o2,⋯,oG， 然后用下面的目标函数优化 policy modelπθ：

![](/images/2025-03-09-llm-deepseek-r1/5.png)

GRPO vs PPO：

R1-Zero 最大的不同，是在强化学习中使用 GRPO 算法代替 PPO。GRPO 算法也是 DeepSeek 团队在 24 年 2 月[《DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models》](https://arxiv.org/abs/2402.03300)这篇论文提出的，其核心思想可以理解为两个字：**内卷**；

简单来说，PPO 是用一个模型去评估当前输出的收益，模型觉得这个输出好，就更新参数往这方向靠近，类似四六级考试的判定，有个分数线，过了就好，不过就不好；GRPO 是让模型一次性输出一组数据，在这组数据中选得分最高的，让模型逐步靠近得分高的输出，类似高考的内卷选拔，你只要比同龄人好，就是好。更具体的可以看这张图：

![](/images/2025-03-09-llm-deepseek-r1/6.png)

图上的一些概念：
* Reference Model：预训练的大语言模型
* Reward Model：奖励模型，给定输入和输出，给出得分。可以是基于神经网络训练的模型，使用人类标注数据做训练；也可以是规则模型，定死一些规则做打分。这里的输入是大语言模型一次完整的输出。
* Value Model：对模型输出的每一步做一个预测，预测当前状态下后续能得到的收益。这里的输入是大语言模型每一次 token 的输出。
* Policy Model：我们正在训练的大语言模型。base 是 Reference Model，训练过程中会不断更新参数，得到我们最终需要的模型。
* GAE：Generalized Advantage Estimation 广义优势估计，评估每一个动作的好坏程度
* q：输入 question
* o：输出 output
* r：模型完整的输出经过 Reward Model 计算后的分数
* v：模型每一步的输出后的状态，经过 Value Model 计算后的价值估计值，用于评估当前 token 输出的好坏。
* KL：Kullback-Leibler divergence KL散度，衡量新策略(当前训练中的模型输出的结果)和旧策略(base模型输出的结果)之间的差异，保障训练中策略更新幅度不要过大，保证稳定性。

PPO 用 Reward Model 计算大模型完整输出的奖励分数(r)，过程中会跟原始模型的输出做对比(KL)，避免偏离太远。大模型每步 token 输出，都会经过 Value Model 判定输出对后续奖励的期望值(v)，经过 GAE 函数计算每步动作的好坏程度，更新我们在训练的大模型 Policy Model 参数。

GRPO 去掉了 Value Model，对每个输入(q)输出多个结果o1 o2 o3 …，奖励模型判断这些结果的好坏，从中选出最好的，更新模型参数。GRPO 去掉 Value Model，带来了一些好处：
* 大大降低计算成本，少了价值模型，训练过程的内存占用、计算量、整体效率都更好。
* 更适合开放式的问题推理，不受限于价值模型判断的准确性。
* 整个流程也更简洁优美了。

#### 2.3.2.2 奖励建模（Reward Modeling）：rule-based reward system

奖励是 training signal 的来源，它决定了强化学习的优化方向。 训练 DeepSeek-R1-Zero 时，deepseek 采用了一个基于规则的奖励系统（rule-based reward system）， 该系统主要由两种类型的奖励组成。

类型一：准确性奖励（Accuracy rewards）

准确性奖励模型评估响应是否正确（whether the response is correct）。例如：
1. 对于具有确定性结果的数学问题，要求模型以指定格式提供最终答案，从而能可靠地基于规则验证正确性。
2. 对于LeetCode问题，可以使用编译器对生成的程序进行编译，然后运行预定义的测试用例。

类型二：格式奖励（Format rewards）

deepseek 还采用了一个格式奖励模型，强制推理模型将其思考过程放在<think>和</think>tag 内。
这里没有使用结果或过程神经奖励模型（outcome or process neural reward model）， 因为 deepseek 发现神经奖励模型可能会在大规模强化学习过程中出现 reward hacking 行为， 并且重新训练奖励模型需要额外的训练资源，也会使整个训练流程变得更加复杂。

#### 2.3.2.3 训练模板（提示词模板）

deepseek 设计了一个简单直白的模板，指导基础模型遵循具体指令。这个模板有意设置得很简单，避免带偏模型，也不会告诉模型要进行反思性推理或者其他推理策略，确保可以观察到模型在强化学习过程中自发去发现怎样的推理方式才是更有效的。这个模板要求 DeepSeek-R1-Zero 首先生产一个推理过程，然后再给出最终答案。 deepseek 有意将约束限制在这一结构内，避免任何 content-specific biases，以确保能够准确地观察模型在 RL 过程中的自然进化，如下所示：

![](/images/2025-03-09-llm-deepseek-r1/7.png)

```bash
推理过程和答案分别用 <think> 和 <answer> 标签括起来，例如：
<think> 推理过程 </think>
<answer> 答案 </answer>
```

#### 2.3.2.4 DeepSeek-R1-Zero 的性能、自我进化过程和顿悟时刻

性能：

下图展示了 DeepSeek-R1-Zero 在 AIME 2024 基准测试中的性能轨迹：

![](/images/2025-03-09-llm-deepseek-r1/8.png)

可以看到，随着 RL 训练的进行，DeepSeek-R1-Zero 的性能稳步提升。 AIME 2024 pass@1 得分从 15.6% 跃升至 71.0%，达到了与 OpenAI-o1-0912 相当的性能水平， 说明了 deepseek 的 RL 算法在优化模型性能方面的有效性。

下表是 DeepSeek-R1-Zero 与 OpenAI o1-0912 在多种推理基准测试上的性能对比：

![](/images/2025-03-09-llm-deepseek-r1/9.png)

总结：
* 通过 RL，DeepSeek-R1-Zero 能够在无需任何监督微调数据的情况下获得强大的推理能力， 也就是说模型仅通过 RL 就能有效学习和泛化。
* DeepSeek-R1-Zero 的性能还可以通过多数投票（majority voting）进一步提升。 例如，在 AIME 基准测试中采用多数投票时，DeepSeek-R1-Zero 的性能从 71.0% 上升至 86.7%，超过了 OpenAI-o1-0912 的性能。
* DeepSeek-R1-Zero 在有无多数投票的情况下都能取得如此高的性能，突显了其强大的基础能力以及在推理任务中进一步发展的潜力。

自我进化过程：

DeepSeek-R1-Zero 的自我进化过程非常好地展示了强化学习是如何驱动模型自主提升推理能力的。
* 直接从基础模型启动 RL 训练，使得免受监督微调（SFT）阶段的影响，从而能直观监测模型的进化过程。
* 这种方法提供了一个观察模型随时间演变的清晰视角，特别是在处理复杂推理任务方面。

![](/images/2025-03-09-llm-deepseek-r1/10.png)

如图所示，DeepSeek-R1-Zero 的思考时间在整个训练过程中呈现出持续改进（增加）的趋势。
* 这种进步并非外部调整的结果，而是模型内部的自然发展。
* DeepSeek-R1-Zero 自然获得了通过增加 test-time computation 来解决越来越复杂的推理任务的能力。随着训练量的推进，输出的长度稳步加长，推理能力也随之提升。这也验证了 OpenAI o1 里提到的 test-time scaling，也就是更长的推理输出能更好提升模型推理能力，模型在强化学习过程中自主发现了这个规律。
* 这里所说的 computation 是指生成几百到几千个不等的推理 token，使模型能够更深入地探索和完善其思考过程。
随着 test-time computation 的增加，这种自我进化过程中最显著的方面之一是出现了复杂行为。 例如，观察到下面两个行为同时自发出现：
* 反思行为：模型重新审视和评估自己先前的步骤；
* 模型主动探索解决问题的替代方法；

这些行为并非明确编程的结果，而是模型与强化学习环境互动的结果。 这种自发的发展显著增强了 DeepSeek-R1-Zero 的推理能力，使其能够以更高的效率和准确性应对更具挑战性的任务。

顿悟时刻（Aha）：

在 DeepSeek-R1-Zero 的训练过程中，观察到的一个奇特现象是所谓的 “顿悟时刻”，训练过程中模型学会了停下来重新评估前面的思考，而且使用拟人的口气进行了反思。强化学习过程中人类没有输入任何类似的反思引导，模型能自主进行这种反思，十分有趣。在预训练的模型里，模型已经有这样的反思意识潜力，在训练的某次输出过程中偶然出现，而出现后的结果对复杂推理有帮助，强化学习的机制会持续鼓励这样的输出。如下所示：

![](/images/2025-03-09-llm-deepseek-r1/11.png)

这一时刻出现在模型的一个中间版本中。在这个阶段，DeepSeek-R1-Zero 学会了通过重新评估其初始处理方法，为问题分配更多的思考时间。 这种行为不仅是模型逐步增长的推理能力的证明，也是强化学习能够带来意外且复杂结果的一个迷人例证。

这对于模型和观察其行为的研究者来说都是一个 “顿悟时刻”，它凸显了强化学习的力量和美感：
* 并没有明确地教导模型如何解决问题，而是仅仅提供了正确的激励，模型便能够自主地发展出高级的问题解决策略。
* “顿悟时刻” 有力地提醒了 RL 激发人工智能系统新智能水平的潜力，为未来更具自主性和适应性的模型铺平了道路。

缺点：

尽管 DeepSeek-R1-Zero 展示了强大的推理能力，并且能够自主发展出意外且强大的推理行为，但它也面临一些问题。例如，DeepSeek-R1-Zero 遇到了诸如可读性差、语言混用等挑战。 为了使推理过程更具可读性，deepseek 探索了 DeepSeek-R1。

**总结：R1-Zero 有非常有趣的发现，即不做监督学习，仅对预训练模型进行强化学习这条路是 OK 的，最终的模型有媲美o1的推理能力，但当前这种方式训练出的 R1-Zero 实际对外使用会有些问题，主要是对人不友好，比如输出的内容中英文混杂，猜测是奖励模型并没有做这种人类阅读友好的奖励判定，模型没理由能做好这块。**

### 2.3.3 DeepSeek-R1：带冷启动的强化学习

DeepSeek-R1-Zero 的结果令人鼓舞，关于如何进一步提升性能，自然会产生两个问题：
* 引入少量高质量数据作为冷启动，是否可以进一步提升推理性能或加速收敛？
* 如何训练一个用户友好的模型，该模型不仅能够产生清晰连贯的思维链（CoT），而且还能展现出强大的通用能力？

为了回答这些问题，deepseek 设计了一个新的 pipeline，训练得到的模型称为DeepSeek-R1。该 pipeline 包含四个阶段，DeepSeek-R1 的训练过程如下所示：

![](/images/2025-03-09-llm-deepseek-r1/12.png)

#### 2.3.3.1 阶段一：冷启动

为了避免从基础模型直接开始 RL 训练导致的不稳定冷启动阶段， deepseek 构建了一定量的长 CoT 数据集并对模型进行微调（SFT）， 得到一个 initial RL actor。

数据源：

几种方式：
1. 提供一个 CoT 作为示例，然后使用few-shot prompting生成更多例子；
2. 直接提示模型（directly prompting models），让它生成带有反思和验证过程的详细回答；
3. 收集 DeepSeek-R1-Zero 输出的一些回答，并通过人工标注对输出的质量进行增强。

deepseek 收集了几千个冷启动数据，拿来微调 DeepSeek-V3-Base，得到的模型作为接下来的 RL 过程的起点。

冷启动数据的好处：

冷启动数据的好处包括：
1. 提升输出的可读性 DeepSeek-R1-Zero 的主要问题之一是输出的内容经常可读性很差。可能会混杂多种语言，或者不是 markdown 格式，无法高亮一些重点。因此，在为 DeepSeek-R1 创建冷启动数据时，deepseek 设计了一种可读性很好的格式，在每个响应的末尾包含一个总结，并过滤出对读者不友好的响应。 在这里，deepseek 定义输出格式为|special_token|<reasoning_process>|special_token|<summary>，其中<reasoning_process>是用户输入的 query 对应的 CoT（推理过程），而<summary>用于总结推理结果。
2. 潜力
  * 基于人的先验知识（human priors）精心设计冷启动数据，观察到训练出来的模型比 DeepSeek-R1-Zero 表现更好。
  * deepseek 相信迭代式训练（iterative training）是很好的训练推理模型的方式。

#### 2.3.3.2 阶段二：面向 reasoning 的强化学习

在使用冷启动数据对 DeepSeek-V3-Base 进行微调后，第二阶段的训练过程与 DeepSeek-R1-Zero 相同： 使用大规模强化学习进行后训练。 这一阶段专注于提升模型的 reasoning 能力，特别是在推理密集型任务中，如编码、数学、科学和逻辑推理，这些任务具有明确定义的问题和解决方案。

在训练过程中，deepseek 观察到 CoT 经常出现语言混用（language mixing），特别是在 RL 提示词涉及多种语言时。 为了缓解这个问题，deepseek 在 RL 训练中引入了一种语言一致性奖励（language consistency reward），计算方式是 CoT 中目标语言单词的比例（proportion of target language words in the CoT）。 尽管消融实验表明，这种对齐会导致模型性能略有下降，但这种奖励与人类偏好一致，使其更具可读性。

最后，deepseek 直接将推理任务的准确性与语言一致性奖励相加来形成最终奖励。 然后，deepseek 在微调后的模型上应用 RL 训练，直到它在推理任务上收敛。

这个阶段的 RL 收敛时，保存一个 checkpoint 供第三阶段使用；

#### 2.3.3.3 阶段三：拒绝采样和监督微调

利用第二阶段的 checkpoint 收集 SFT（监督微调）数据。

初始冷启动数据主要关注推理，而这一阶段则纳入了来自其他领域的数据， 以增强模型在写作、角色扮演和其他通用任务中的能力。具体来说，deepseek 按照以下方式生成数据并微调模型。

推理数据（Reasoning data）：600k：

人工整理一批推理提示词，从上述 RL 训练的 checkpoint 进行拒绝采样来生成推理轨迹。在第二阶段，deepseek 只纳入了可以使用基于规则的奖励进行评估的数据。

在这一阶段：
* 引入额外数据来扩展数据集，其中一些数据使用生成式奖励模型 —— 将事实和模型预测输入 DeepSeek-V3 进行判断。
* 由于模型输出有时会杂乱无章且难以阅读，deepseek 会过滤掉带有混合语言、冗长段落和代码块的思维链。
* 对于每个提示，deepseek 采样多个响应，并且只保留正确的响应。

总共，deepseek 收集了大约600k个与推理相关的训练样本。

非推理数据（Non-Reasoning data）：200k：

对于非推理数据，如写作、事实问答、自我认知和翻译，deepseek 采用 DeepSeek-V3 pipeline， 并复用 DeepSeek-V3 的一部分 SFT 数据集。

* 对于某些非推理任务，deepseek 调用 DeepSeek-V3 来生成一个潜在的思维链，然后通过提示回答问题。
* 对于更简单的查询，如 “hello”，deepseek 不会在响应中提供 CoT。

最终，deepseek 收集了总共大约200k个与推理无关的训练样本。R1 的中文输出很强，更大可能是跟这 20w 数据的质量高相关。
deepseek 使用上述整理的数据集（约 800k 样本）对 DeepSeek-V3-Base 进行了两个 epoch 的微调。

#### 2.3.3.4 阶段四：所有场景的强化学习

为了进一步使模型与人类偏好对齐，deepseek 又进行了一轮强化学习，在完善模型推理能力的同时， 提高模型的有用性和无害性（helpfulness and harmlessness）。

这次强化学习具体没有展开，主要是引导模型安全输出，过滤有害输出，以及再次提升推理能力的一次训练。这次的奖励模型额外再加上了对通用内容的奖励，在文科内容、日常问答上，应该也准备了一些质量比较高的 case 和奖励规则模型。

具体来说，deepseek 组合使用 reward signals 和多样化的 prompt distributions 来训练模型。
* 对于推理数据，遵循 DeepSeek-R1-Zero 中的方法，利用基于规则的奖励来指导数学、编码和逻辑推理领域的学习过程。
* 对于通用数据，借助奖励模型，以捕捉复杂微妙场景中的人类偏好。deepseek 基于 DeepSeek-V3 pipeline，并采用类似的偏好对和训练提示分布。
* 对于有用性，仅关注最终总结，确保评估强调响应对用户的实用性和相关性，同时尽量减少对底层推理过程的干扰。
* 对于无害性，评估模型的整个响应，包括推理过程和总结，以识别和减轻在生成过程中可能出现的任何潜在风险、偏见或有害内容。

这几个步骤后，R1 就训练完成了，可以看到这个基于 V3 模型的后训练过程成本是很低的，数据量不大，但效果非常显著，特别是在编码和数学问题上，R1 相对 V3 提升了几个档次，测试数据如下所示：

![](/images/2025-03-09-llm-deepseek-r1/13.png)

而这个过程，看起来也是可以 scale 的，可以用这个训好的模型继续多步生成一些case，择优组成新的数据，继续进行 SFT 和强化学习。这条显著提升模型推理能力的后训练路跑通了，公开解了 o1 一直遮遮掩掩的强化学习路线，也展现了很好的低成本持续 scale up 的潜力。沿着这条路走能 scale 到什么程度还不太清楚，拭目以待。

### 2.3.4 蒸馏：赋予小型模型推理能力

DeepSeek 的同学发现用上述 R1 训练过程中生成的 60w 推理相关的数据，以及 20w 的额外数据去对小模型做 SFT，小模型性能的提升非常明显。看起来这一步纯粹是用质量更好的数据对小模型做SFT，只是这些数据大部分是 R1 生成的，相当于是蒸馏提取了 R1 的能力精华，拟合了 R1 的能力，这样也能给小模型带来较好的推理能力提升。

deepseek 使用的基础模型包括：
* Qwen2.5-Math-1.5B
* Qwen2.5-Math-7B
* Qwen2.5-14B
* Qwen2.5-32B
* Llama-3.1-8B
* Llama-3.3-70B-Instruct。选择 Llama-3.3 是因为其推理能力略优于 Llama-3.1。

![](/images/2025-03-09-llm-deepseek-r1/14.png)

从分数看，这些小模型在数学和 coding 上的性能是不错的，如果1.5b在部分场景上能有媲美4o的效果，那端上大模型会迎来一波应用潮。但实际用起来没那么理想，试过 1.5B 模型基本不遵循指令，有些刷分的感觉，但这仅是做了初步的SFT 后的效果，在这基础上对小模型继续进行强化学习，可能整体能力能有提升，也是值得期待的点。

这里论文上还额外做了另一个实验，用类似 R1-Zero 的方法直接对小模型做强化学习，实验效果是相对用蒸馏数据做 SFT 的方式，效果差很多。一个猜测是小模型就是能力有限，直接用强化学习达到顿悟和性能提升，得基于模型本身能力足够才行。

## 2.4 讨论

### 2.4.1 蒸馏与强化学习的性能对比

前面已经看到，通过蒸馏 DeepSeek-R1，小型模型可以取得非常好的效果。 但这里还有一个问题待解答：通过本文讨论的大规模 RL 对小模型训练，和蒸馏方式相比，哪个效果来的更好？

为了回答这个问题，deepseek 在 Qwen-32B-Base 上进行了大规模 RL 训练，使用数学、编码和 STEM 数据，训练了超过 10K 步， 得到了DeepSeek-R1-Zero-Qwen-32B。 两种方式得到的模型，性能对比如下：

![](/images/2025-03-09-llm-deepseek-r1/15.png)

* 大规模 RL 训练的 32B 基础模型，在性能上与 QwQ-32B-Preview 相当；
* 从 DeepSeek-R1 蒸馏而来的模型，在所有基准测试中都显著优于 DeepSeek-R1-Zero-Qwen-32B；
因此，deepseek 可以得出两个结论：
* 将更强大的模型蒸馏到小型模型中，可以让小模型获得出色的性能。 对小型模型进行大规模 RL 也能取得不错的性能，但需要的算力比蒸馏要多很多，而且可能无法达到蒸馏取得的效果。
* 蒸馏是一种既经济又高效的方式，但要突破智能边界，可能仍需要更强大的基础模型和更大规模的强化学习。

### 2.4.2 失败的尝试

在开发 DeepSeek-R1 早期，deepseek 也遇到了一些失败和挫折。 这里分享一些失败经验，提供一些见解，但这并不意味着这些方法无法开发出有效的推理模型。

#### Process Reward Model (PRM)

PRM 是一种合理的方法，可以引导模型采用更好的方式来解决推理任务。然而，在实践中，PRM 存在三个主要限制，可能会阻碍其最终的成功。
* 首先，在一般推理任务中，明确定义细粒度的推理步骤是具有挑战性的。
* 其次，判断当前的中间步骤是否正确是一个困难的任务。使用模型进行自动标注可能无法得到理想的结果，而人工标注又不利于大规模扩展。
* 第三，一旦引入基于模型的 PRM，不可避免地会导致奖励篡改，而重新训练奖励模型需要额外的训练资源，并使整个训练流程更加复杂。

总之，尽管 PRM 在重新排序模型生成的前 N 个候选答案或辅助引导搜索方面表现良好，但在 deepseek 的实验中，相较于其在大规模强化学习过程中引入的额外计算开销，其优势仍然有限。

#### Monte Carlo Tree Search (MCTS)

受到 AlphaGo 和 AlphaZero 的启发，deepseek 探索了使用蒙特卡洛树搜索（MCTS）来增强测试阶段的计算可扩展性。这种方法将答案拆分为更小的部分，使模型能够系统地探索解空间。为此，deepseek 提示模型生成多个标签，这些标签对应于搜索过程中所需的特定推理步骤。
* 在训练阶段，deepseek 首先使用收集的提示，通过 MCTS 结合预训练的价值模型来寻找答案。随后，deepseek 利用生成的问答对来训练演员模型（actor model）和价值模型（value model），并通过迭代优化整个过程。
* 然而，在扩展训练时，这种方法面临多个挑战。首先，与搜索空间相对明确的国际象棋不同，生成文本时的搜索空间呈指数级增长。为了解决这一问题，deepseek 为每个节点设置了最大扩展限制，但这可能导致模型陷入局部最优解。其次，价值模型直接影响生成质量，因为它决定了搜索过程中的每一步。然而，训练一个细粒度的价值模型本身就极具挑战性，这使得模型难以通过迭代方式持续改进。虽然 AlphaGo 的成功核心在于训练价值模型以逐步提升性能，但由于文本生成的复杂性，在 deepseek 的设置下难以复制这一原则。

总之，尽管 MCTS 在推理时结合预训练价值模型可以提升性能，但通过自搜索（self-search）迭代提升模型表现仍然是一个重大挑战。

## 2.5 结论、局限性和未来工作

deepseek 通过强化学习（RL）增强模型推理能力的探索过程。DeepSeek-R1-Zero 采用纯 RL 方法，不依赖冷启动数据，在多个任务上取得了出色的性能。而 DeepSeek-R1 更加强大，它结合了冷启动数据与迭代 RL 微调，最终在多个任务上达到了与 OpenAI-o1-1217 相当的表现。

此外，deepseek 进一步探索了如何将推理能力蒸馏到小型稠密模型中。deepseek 使用 DeepSeek-R1 作为教师模型，生成了 80 万条训练样本，并对多个小型稠密模型进行微调。实验结果令人鼓舞：DeepSeek-R1-Distill-Qwen-1.5B 在数学基准测试中表现优异，在 AIME 上取得 28.9%，在 MATH 上取得 83.9%，超越了 GPT-4o 和 Claude-3.5-Sonnet。其他稠密模型的表现也十分亮眼，显著优于基于相同底层检查点的指令微调模型。

未来，deepseek 计划在以下方向对 DeepSeek-R1 进行进一步研究：
* 通用能力：目前，DeepSeek-R1 在函数调用、多轮对话、复杂角色扮演以及 JSON 输出等任务上的能力仍不及 DeepSeek-V3。deepseek 计划进一步探索如何利用长链式思维（CoT）来提升这些任务的表现。
* 语言混合：DeepSeek-R1 主要针对中英文优化，在处理其他语言的查询时可能会出现语言混合问题。例如，即使查询是非中英文，DeepSeek-R1 仍可能使用英文进行推理和回答。deepseek 计划在未来版本中解决这一局限性。
* 提示工程：在评估 DeepSeek-R1 时，deepseek 发现其对提示（prompt）较为敏感，少样本（few-shot）提示往往会降低其性能。因此，deepseek 建议用户采用零样本（zero-shot）设置，直接描述问题并指定输出格式，以获得最佳效果。
* 软件工程任务：由于评估时间较长，影响了 RL 过程的效率，目前大规模 RL 尚未广泛应用于软件工程任务。因此，在软件工程基准测试上，DeepSeek-R1 并未表现出相较于 DeepSeek-V3 的巨大提升。未来版本将通过在软件工程数据上引入拒绝采样（rejection sampling）或在 RL 过程中结合异步评估，以提升训练效率。

# 3. 思考 
这篇论文介绍了 R1 整个算法、训练流程和结果，但最核心的应该是数据，包括用于 R1-Zero 的数据是什么，数据量有多大，生成的 60w 数据具体是什么样的，标注的 20w 文科数据是什么，这是决定模型效果的另一个核心因素，DeepSeek 的中文效果出圈，应该很大程度还是标注的 20w 文科数据质量高，不确定 RL 带来的推理能力提升在文科这块上的帮助有多大。这些数据没有公开，友商要复刻出 DeepSeek 的效果没那么容易。

网上有不少开始复现 R1 和 R1-Zero 的开源项目研究，最大的是 huggingface 的 open-r1，也有学生在 3B 模型上小规模复现 R1-Zero 的开源项目 TinyZero。

# 4. 总结

* DeepSeek APP 上线 20天 DAU 超过 2000w，成为历史用户增长最快的 APP，搜索是有技术积累的壁垒，社交有关系链，内容平台有内容壁垒，基于 chatbot 形态的产品，没看到有什么壁垒，用户数据没有作用，曾以为模型领先就是壁垒，OpenAI 可以凭借领先收高额费用和大部分用户的忠诚，DeepSeek 这波又打破了这种壁垒，领先者无法保证自己一直领先。
* DeepSeek 带来中国自信，曾经认为，类似 AICoding 这种全球无差异竞争的产品，国内同学们怎么搞得过海外那些清一色 MIT 天才搞的产品？DeepSeek 的成功给了这些直面竞争产品很大的信心，中国科技在未来还是很期待的！！！

# 5. 附录

论文文献：
* https://github.com/deepseek-ai/DeepSeek-V3/blob/main/DeepSeek_V3.pdf
* https://github.com/deepseek-ai/DeepSeek-R1/blob/main/DeepSeek_R1.pdf
* https://github.com/deepseek-ai/DeepSeek-V2/blob/main/deepseek-v2-tech-report.pdf
* https://github.com/deepseek-ai/DeepSeek-MoE/blob/main/DeepSeekMoE.pdf
