---
layout:     post
title:      "一文吃透分布式通信原语：从点对点到集合通信（原理 + PyTorch 实战）"
subtitle:   "Send/Recv 到 AllReduce/All2All，看懂 NCCL 集合通信如何由点对点拼装而成，以及它们在 DP/TP/PP/EP 中的角色"
description: "面向大模型训练与推理的通信原语深度科普：先讲点对点基础层（Send/Recv、ISend/IRecv、SendRecv、Barrier），再讲集合通信（Broadcast、Scatter/Gather、AllGather、Reduce/AllReduce、ReduceScatter、All2All/AllToAllv）。每个原语给出语义 ASCII 图、底层算法与通信复杂度（Ring/Tree/Halving-Doubling）、原语之间的组合关系（AllReduce = ReduceScatter + AllGather、Ring 本质是一圈 SendRecv），以及在数据并行/张量并行/流水线并行/专家并行中的真实应用场景。配可运行的 torch.distributed 代码（NCCL/gloo 后端），并附一段用 Send/Recv 从零实现 Ring-AllReduce 的教学代码。"
author: "tanjunchen"
date: 2026-10-04
published: true
tags:
    - AI Infra
    - 分布式训练
    - 集合通信
    - NCCL
    - PyTorch
categories:
    - TECHNOLOGY
showtoc: true
---

# 写在前面

训练一个大模型，GPU 真正在「算」的时间往往没你想的那么多——很大一部分卡在「等数据」上。几十上百张卡要协同工作，就必须频繁地互相交换张量：梯度要同步、激活值要跨 stage 传递、MoE 的 token 要路由到对应专家。这些「交换」动作，底层都归结为一组**通信原语（Communication Primitives）**。

通信原语分两大类：

- **点对点（Point-to-Point，P2P）**：两个 rank 之间点对点收发。`Send` / `Recv` / `ISend` / `IRecv` / `SendRecv` / `Barrier`。这是**一切通信的基础层**。
- **集合通信（Collective Communication）**：一组 rank 共同参与的集体操作。`Broadcast` / `Scatter` / `Gather` / `AllGather` / `Reduce` / `AllReduce` / `ReduceScatter` / `All2All`。

关键认知：**集合通信底层正是由点对点原语拼装而成的**。一次 Ring-AllReduce，本质就是一圈 `SendRecv`。所以这篇文章**先讲点对点，再讲集合通信**——理解了点对点，集合通信就不再是黑盒。

> **术语约定**：
> - **rank**：参与通信的一个进程，通常绑定一张 GPU。`world_size` = 总进程数 = N。
> - **buffer**：参与收发的张量缓冲区。
> - 代码一律用 PyTorch 的 `torch.distributed`，有 GPU 时用 **NCCL** 后端，无 GPU 时退化到 **gloo**（部分原语如 `scatter`/`gather` 在老版本 NCCL 上不支持，示例里会标注）。
> - 通信量用 `S` 表示单份数据的字节数，`N` 表示参与的 rank 数。

## 一图速览（TL;DR）

> 字母=不同内容的数据块，数字=数值，`★10`=归约和；`r0~r3` 为 4 个 rank。先扫一眼建立直觉，细节看后文。

点对点（两个 rank 之间收发）：

![点对点原语：Send/Recv、ISend/IRecv、SendRecv、Barrier](/images/2026-10-04-communication-primitives-explained/3-p2p.svg)

集合通信（一组 rank 一起做，操作前 → 操作后）：

![集合通信操作前后一图速览](/images/2026-10-04-communication-primitives-explained/2-collectives.svg)

**三句话抓住全文**：

1. **点对点是积木**：`Send/Recv`（阻塞）、`ISend/IRecv`（异步 overlap）、`SendRecv`（环形不死锁）、`Barrier`（对齐）。
2. **集合通信都由点对点拼成**：`AllReduce = ReduceScatter + AllGather`，Ring 的每一步就是一次 `SendRecv`；Ring-AllReduce 单卡通信量 `≈2S`，几乎与卡数无关。
3. **各管一摊并行策略**：PP 用 `Send/Recv`、DP 用 `AllReduce(AVG)`、TP 用 `AllReduce(SUM)`、ZeRO/FSDP 用 `AllGather + ReduceScatter`、MoE 用变长 `AllToAllv`。

---

# 0. 全局对比表：先建立全景

![通信原语全局对比：类别/通信量/典型场景](/images/2026-10-04-communication-primitives-explained/0-overview-table.svg)

下表为完整版（含输入/输出），可对照速查：

| 原语 | 类别 | 输入（每 rank） | 输出（每 rank） | 单 rank 通信量（量级） | 典型场景 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `Send` / `Recv` | 点对点 | 一个 buffer | 对端的 buffer | `S`（单向） | 流水线并行 stage 间传激活/梯度 |
| `ISend` / `IRecv` | 点对点 | 一个 buffer | 对端的 buffer | `S`（单向，异步） | 计算-通信 overlap |
| `SendRecv` | 点对点 | 发 1 份 + 收 1 份 | 收到对端数据 | `S`（双向各 `S`） | Ring 算法的基本步、环形移位 |
| `Barrier` | 点对点/集合 | 无数据 | 无数据 | ~0（仅信令） | 阶段对齐、计时、调试 |
| `Broadcast` | 集合 | root 有数据 | 所有 rank 拿到 root 的数据 | `S`（树状 `~S·logN` 延迟） | 参数初始化、权重同步 |
| `Scatter` | 集合 | root 有 N 份 | 每 rank 拿第 i 份 | `(N-1)/N·S`（root 发出） | 把数据分片下发 |
| `Gather` | 集合 | 每 rank 1 份 | root 收齐 N 份 | `(N-1)/N·S`（root 收齐） | 结果汇总到主 rank |
| `AllGather` | 集合 | 每 rank 1 份 | 每 rank 都拿到全部 N 份 | `(N-1)/N·S` | ZeRO/FSDP 参数聚合 |
| `Reduce` | 集合 | 每 rank 1 份 | root 拿到归约结果 | `(N-1)/N·S` | 汇总 loss/统计量到主 rank |
| `AllReduce` | 集合 | 每 rank 1 份 | 每 rank 都拿到归约结果 | `2(N-1)/N·S` | **数据并行梯度同步** |
| `ReduceScatter` | 集合 | 每 rank 1 份（N 块） | 每 rank 拿到自己那块的归约和 | `(N-1)/N·S` | ZeRO/FSDP 梯度切分 |
| `All2All` | 集合 | 每 rank 发 N 份不同数据 | 每 rank 收 N 份不同数据 | `(N-1)/N·S` | **MoE 专家并行 token 路由** |

> 下面逐个展开。每个原语都遵循同一套结构：**定义与语义 → 底层算法与复杂度 → 组合关系 → 应用场景 → 可运行代码**。

---

# 1. 点对点原语：一切通信的基础

点对点只涉及**两个** rank：一个发、一个收。它简单，却是所有集合通信的「积木」。

## 1.1 `Send` / `Recv`：阻塞式收发

### 1. 定义与语义

- `Send(tensor, dst)`：把 `tensor` 发给 rank `dst`，**阻塞**直到数据被对端的通信层接收。
- `Recv(tensor, src)`：从 rank `src` 接收数据写入 `tensor`，**阻塞**直到收完。

N=2 时（rank0 发给 rank1）操作前后状态：

```
            操作前                       操作后
rank0:  send_buf = [1,2,3]   ──send──►  send_buf = [1,2,3] (不变)
rank1:  recv_buf = [0,0,0]   ◄──recv──  recv_buf = [1,2,3]
```

### 2. 底层原理与算法

`Send`/`Recv` 直接映射到底层网络的一次点对点传输（NVLink / PCIe / IB / RoCE 上的一次 RDMA write 或 copy）。

- **通信量**：单向 `S` 字节，没有额外归约或复制。
- **延迟 / 带宽**：延迟 = 一次链路 RTT 的一半量级 + 启动开销；带宽受限于两 rank 之间的物理链路（NVLink TB/s 级 vs 跨机 IB 0.1 TB/s 级，差一个数量级）。
- **死锁风险**：阻塞语义下，如果两个 rank 都先 `Send` 再 `Recv`，且底层无足够缓冲，就可能互相等待对方收 → **死锁**。解决办法见 1.3 `SendRecv`。

### 3. 原语之间的组合关系

`Send`/`Recv` 是**最底层积木**，所有集合通信最终都能拆成一串 `Send`/`Recv`。例如 Ring-AllReduce 的每一步，都是「我把一块发给右邻居、同时从左邻居收一块」。

### 4. 在大模型中的实际应用场景

**流水线并行（PP）stage 间传递激活值 / 梯度**，直接依赖 `Send`/`Recv`：

- 模型被切成若干 stage，分布在不同卡上。前向时，stage k 算完的**激活值**要 `Send` 给 stage k+1；反向时，stage k+1 的**梯度**要 `Send` 回 stage k。
- **为什么选它**：PP 的通信是**点对点、有明确方向的**（相邻 stage 之间），不是一组 rank 的集体操作，用集合通信反而是杀鸡用牛刀。1F1B（One Forward One Backward，一前一后：每个 stage 交替地做一次前向、一次反向，让各 stage 的流水线气泡最小、显存占用稳定）调度下，激活值的收发时序是精心编排的，天然就是 `Send`/`Recv` 的活。

### 5. 实例代码

```python
# send_recv.py
# 启动：torchrun --nproc_per_node=2 send_recv.py
import os
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    assert world_size == 2, "本示例需要 2 个 rank"

    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    if rank == 0:
        send_buf = torch.tensor([1.0, 2.0, 3.0], device=device)
        print(f"[rank0] 操作前 send_buf = {send_buf.tolist()}")
        dist.send(tensor=send_buf, dst=1)          # 阻塞发送给 rank1
        print(f"[rank0] 操作后 send_buf = {send_buf.tolist()} (发送方数据不变)")
    else:
        recv_buf = torch.zeros(3, device=device)
        print(f"[rank1] 操作前 recv_buf = {recv_buf.tolist()}")
        dist.recv(tensor=recv_buf, src=0)          # 阻塞接收来自 rank0
        print(f"[rank1] 操作后 recv_buf = {recv_buf.tolist()}")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=2 --rdzv-endpoint=127.0.0.1:29502 send_recv.py
```

真实输出（顺序可能交错）：

```
[rank0] 操作前 send_buf = [1.0, 2.0, 3.0]
[rank1] 操作前 recv_buf = [0.0, 0.0, 0.0]
[rank0] 操作后 send_buf = [1.0, 2.0, 3.0] (发送方数据不变)
[rank1] 操作后 recv_buf = [1.0, 2.0, 3.0]
```

> **macOS 本地小坑**：若直接 `torchrun --nproc_per_node=2 send_recv.py`，默认的 c10d 动态 rendezvous 会用「本机 hostname 的反向 DNS」建 TCPStore，可能解析成 `...in-addr.arpa` / `...ip6.arpa` 导致连接超时（仅设 `MASTER_ADDR=127.0.0.1` 无效，该变量不被动态 rendezvous 采用）。显式加 `--rdzv-endpoint=127.0.0.1:<port>` 即可绕开。

---

## 1.2 `ISend` / `IRecv`：非阻塞收发，用于计算-通信 overlap

### 1. 定义与语义

- `isend(tensor, dst)` / `irecv(tensor, src)`：**立即返回**一个 `Work` 句柄（future），不等传输完成。调用方可以先去干别的（比如算下一层），等真正需要用到数据时再 `work.wait()`。

```
rank0:  work = isend(buf, dst=1)   # 立即返回，buf 正在后台传
        ...做其它计算（与通信 overlap）...
        work.wait()                # 这里才确保发送完成，之后才能复用 buf
```

### 2. 底层原理与算法

- **通信量**：同 `Send`/`Recv`，单向 `S`。差别只在**时序**：传输在后台 DMA 引擎 / 通信线程里进行，与计算流水线重叠。
- **关键价值**：现代 GPU 的 copy 引擎与 compute 引擎可并行。把通信「藏」到计算背后，**有效地把通信延迟从关键路径上抹掉**。
- **注意**：`wait()` 之前**不能复用/修改正在传输的 buffer**，否则数据竞争。

### 3. 原语之间的组合关系

非阻塞版本是构建**高效集合通信**和 **PP overlap 调度**的关键。Ring 算法里，一个 rank 可以「一边异步发右边、一边异步收左边、同时对上一块做归约计算」，三者重叠 → 这正是 `batch_isend_irecv` 的用武之地。

### 4. 应用场景

- **PP 的 1F1B overlap**：异步发送激活值的同时，继续做本 stage 的计算。
- **TP/DP 的梯度通信 overlap**：反向传播中，某一层梯度一算完就异步 `all_reduce`（底层是异步 P2P），不等它完成就继续算前一层——通信与反向计算重叠。

### 5. 实例代码

```python
# isend_irecv.py
# 启动：torchrun --nproc_per_node=2 isend_irecv.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    if rank == 0:
        buf = torch.tensor([10.0, 20.0, 30.0], device=device)
        print(f"[rank0] 操作前 buf = {buf.tolist()}")
        work = dist.isend(tensor=buf, dst=1)   # 非阻塞：立即返回
        # —— 这里可以插入与通信重叠的计算 ——
        dummy = torch.randn(1024, 1024, device=device)
        _ = dummy @ dummy                      # 模拟计算，与发送 overlap
        work.wait()                            # 确保发送完成后才复用 buf
        print(f"[rank0] 发送完成")
    else:
        buf = torch.zeros(3, device=device)
        print(f"[rank1] 操作前 buf = {buf.tolist()}")
        work = dist.irecv(tensor=buf, src=0)   # 非阻塞接收
        work.wait()                            # 用到数据前必须 wait
        print(f"[rank1] 操作后 buf = {buf.tolist()}")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=2 --rdzv-endpoint=127.0.0.1:29503 isend_irecv.py
```

真实输出（顺序可能交错）：

```
[rank1] 操作前 buf = [0.0, 0.0, 0.0]
[rank0] 操作前 buf = [10.0, 20.0, 30.0]
[rank1] 操作后 buf = [10.0, 20.0, 30.0]
[rank0] 发送完成
```

rank0 发起非阻塞 `isend` 后立刻去做矩阵乘（与通信 overlap），`work.wait()` 后才确认发送完成；rank1 的 `buf` 经 `irecv` + `wait` 被填成 `[10,20,30]`。

---

## 1.3 `SendRecv`：收发合体，避免死锁

### 1. 定义与语义

一个 rank **同时**向 `dst` 发、从 `src` 收，由通信库统一调度，不会出现「大家都在发、没人在收」的互锁。最常见形态是**环形移位**：每个 rank 把数据发给右邻居，同时从左邻居收。

N=4 的环形移位（每 rank 把自己的值发给右边 (rank+1)%4）：

```
操作前:  rank0=[A]  rank1=[B]  rank2=[C]  rank3=[D]
         └──►──┘    └──►──┘    └──►──┘    └────►────┐
                                                     ▼
操作后:  rank0=[D]  rank1=[A]  rank2=[B]  rank3=[C]
         (收自 r3)  (收自 r0)  (收自 r1)  (收自 r2)
```

### 2. 底层原理与算法

- **通信量**：每 rank 双向各 `S`。
- **为什么不死锁**：通信库（NCCL/MPI）把「发」和「收」作为一个原子请求提交，底层能同时推进两个方向的传输，不存在「阻塞发等阻塞收」的循环依赖。
- PyTorch 里推荐用 `dist.batch_isend_irecv([...])` 批量提交一组 P2P 操作，由库统一调度——这是实现 `SendRecv` / 环形通信最安全的方式。

### 3. 原语之间的组合关系

**`SendRecv` 是 Ring 类集合通信（Ring-AllReduce / Ring-AllGather）的「基本步」**。整个 Ring-AllReduce 就是执行 `2(N-1)` 轮 `SendRecv`。理解了这一点，就理解了集合通信的本质。

### 4. 应用场景

- Ring-AllReduce / Ring-AllGather 的每一步。
- 需要在 rank 间做「环形流水」的任意场景（如序列并行里 KV 的环形传递、Ring-Attention）。

### 5. 实例代码

```python
# sendrecv_ring.py
# 启动：torchrun --nproc_per_node=4 sendrecv_ring.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    send_buf = torch.tensor([float(rank)], device=device)   # 每个 rank 持有自己的编号
    recv_buf = torch.zeros(1, device=device)

    left  = (rank - 1 + world) % world    # 左邻居（数据来源）
    right = (rank + 1) % world            # 右邻居（发送目标）

    print(f"[rank{rank}] 操作前 send_buf = {send_buf.tolist()}")

    # 用 batch_isend_irecv 同时提交「发给右边 + 从左边收」，由库统一调度，不死锁
    ops = [
        dist.P2POp(dist.isend, send_buf, right),
        dist.P2POp(dist.irecv, recv_buf, left),
    ]
    works = dist.batch_isend_irecv(ops)
    for w in works:
        w.wait()

    print(f"[rank{rank}] 操作后 recv_buf = {recv_buf.tolist()} (收自 rank{left})")
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29504 sendrecv_ring.py
```

真实输出（多进程打印顺序可能交错，这里按 rank 整理，与「rank i 收到 rank (i-1) 的值」完全一致）：

```
[rank0] 操作后 recv_buf = [3.0] (收自 rank3)
[rank1] 操作后 recv_buf = [0.0] (收自 rank0)
[rank2] 操作后 recv_buf = [1.0] (收自 rank1)
[rank3] 操作后 recv_buf = [2.0] (收自 rank2)
```

---

## 1.4 `Barrier`：屏障同步，不传数据但对齐时序

### 1. 定义与语义

`barrier()`：所有 rank 在此处等待，**直到每一个 rank 都到达**，才一起继续。不传输业务数据，只传同步信令。

```
rank0 ──●·········┐
rank1 ──────●·····│
rank2 ────●·······├──►  全部到齐后，一起放行继续
rank3 ────────●···┘
```

> `●` 表示各 rank 先后到达 barrier，先到的在此空等（省略号），直到最后一个 rank 到达，才一起放行。

### 2. 底层原理与算法

- **通信量**：≈ 0（只有少量控制信令），通常用一次小规模 all-reduce 或 tree 信令实现，延迟 `~logN` 量级。
- 它保证的是**时序**而非**数据**：确保「某个时间点之前，所有 rank 都完成了之前的工作」。

### 3. 组合关系

`Barrier` 可以看成「一次不带数据的 AllReduce」——它的信令传播结构和 AllReduce 的树/环一致，只是载荷为空。

### 4. 应用场景

- **阶段对齐**：确保所有 rank 都加载完 checkpoint 再开始训练。
- **计时**：benchmark 通信/计算耗时前后各加一次 barrier，排除「有的 rank 还没开始」造成的测量误差。
- **调试**：定位到底哪个 rank 卡住了。
- ⚠️ **不要滥用**：barrier 会把所有 rank 拉齐到最慢的那个，频繁使用会放大 straggler（掉队者）效应、拖垮吞吐。生产训练里能不用就不用。

### 5. 实例代码

```python
# barrier.py
# 启动：torchrun --nproc_per_node=4 barrier.py
import time
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    if torch.cuda.is_available():
        torch.cuda.set_device(rank)

    time.sleep(rank * 0.5)                        # 人为制造各 rank 到达时间差
    print(f"[rank{rank}] 到达 barrier 之前，t={time.time():.2f}")

    dist.barrier()                                # 所有 rank 在此对齐

    print(f"[rank{rank}] 通过 barrier 之后，t={time.time():.2f}")
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29505 barrier.py
```

真实输出（按 rank 整理，时间戳取自某次运行）：

```
[rank0] 到达 barrier 之前，t=...997.16
[rank1] 到达 barrier 之前，t=...997.66
[rank2] 到达 barrier 之前，t=...998.16
[rank3] 到达 barrier 之前，t=...998.66
[rank0] 通过 barrier 之后，t=...998.68
[rank1] 通过 barrier 之后，t=...998.68
[rank2] 通过 barrier 之后，t=...998.68
[rank3] 通过 barrier 之后，t=...998.68
```

现象：各 rank「到达」时间相差 0.5s 的倍数（997.16 → 998.66），但「通过」时间几乎一致（都是 998.68）——barrier 把它们拉齐到最后一个到达的 rank（rank3）之后才一起放行。

---

# 2. 集合通信原语：由点对点拼装的集体操作

集合通信是**一组 rank 共同完成**的操作。记住一句话：**它们底层都是一串 `Send`/`Recv`，只是组织方式（环 / 树 / 蝶形）不同，带来不同的延迟-带宽权衡。**

两类主流算法先打个底：

- **Ring（环状）**：N 个 rank 串成环，数据分成 N 块，每步每个 rank 发一块给右邻居、收一块。**带宽最优**（充分利用每条链路），延迟随 N 线性增长，适合大数据。
- **Tree（树状）/ Halving-Doubling / Recursive Doubling**：用树或蝶形结构，**延迟最优**（`~logN` 步），适合小数据或延迟敏感场景。

NCCL 会根据数据量、拓扑自动在 Ring 和 Tree 之间选择。

## 2.1 `Broadcast`：广播

### 1. 定义与语义

`broadcast(tensor, src)`：把 root（src）的数据复制到**所有** rank。

```
            操作前                         操作后
rank0(root): [1,2,3]        ──►   rank0: [1,2,3]
rank1:       [0,0,0]              rank1: [1,2,3]
rank2:       [0,0,0]              rank2: [1,2,3]
rank3:       [0,0,0]              rank3: [1,2,3]
```

### 2. 底层原理与算法

- **朴素实现**：root 依次 `Send` 给每个 rank → N-1 次串行发送，延迟 `O(N)`。
- **树状广播**：root 发给 2 个，这 2 个再各发 2 个……`logN` 步完成，延迟 `O(logN)`。
- **通信量**：每个非 root rank 收 `S`；树状下延迟 `~S·logN` 量级。

### 3. 组合关系

树状 Broadcast 本质是一棵由 `Send`/`Recv` 构成的转发树。`Scatter` 可视为「广播的不同分片版本」（每个 rank 拿不同的一块，而非同一份）。

### 4. 应用场景

- **参数初始化 / 权重同步**：训练开始时，把 rank0 随机初始化（或从 checkpoint 加载）的权重广播给所有 rank，保证各 DP 副本初始一致。
- **为什么选它**：目标是「所有人拿到同一份数据」，正是 Broadcast 的语义。

### 5. 实例代码

```python
# broadcast.py
# 启动：torchrun --nproc_per_node=4 broadcast.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    if rank == 0:
        tensor = torch.tensor([1.0, 2.0, 3.0], device=device)   # root 有数据
    else:
        tensor = torch.zeros(3, device=device)                  # 其它 rank 待填充
    print(f"[rank{rank}] 操作前 = {tensor.tolist()}")

    dist.broadcast(tensor, src=0)                               # 从 rank0 广播

    print(f"[rank{rank}] 操作后 = {tensor.tolist()}")
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29506 broadcast.py
```

真实输出（按 rank 整理，打印顺序可能交错）：

```
[rank0] 操作前 = [1.0, 2.0, 3.0]
[rank1] 操作前 = [0.0, 0.0, 0.0]
[rank2] 操作前 = [0.0, 0.0, 0.0]
[rank3] 操作前 = [0.0, 0.0, 0.0]
[rank0] 操作后 = [1.0, 2.0, 3.0]
[rank1] 操作后 = [1.0, 2.0, 3.0]
[rank2] 操作后 = [1.0, 2.0, 3.0]
[rank3] 操作后 = [1.0, 2.0, 3.0]
```

rank0（root）的 `[1,2,3]` 被广播到所有 rank，其余 rank 从全 0 变成 `[1,2,3]`。

---

## 2.2 `Scatter` / `Gather`：分发 / 收集

### 1. 定义与语义

- `Scatter`：root 持有 N 份数据，把第 i 份发给 rank i。（**分发**，各 rank 拿到不同片）
- `Gather`：每个 rank 持有 1 份，root 把 N 份按 rank 顺序收齐。（**收集**，Scatter 的逆操作）

```
Scatter（root=rank0 持 [A,B,C,D]）:
  操作前  rank0:[A,B,C,D]  rank1:[]  rank2:[]  rank3:[]
  操作后  rank0:[A]        rank1:[B] rank2:[C] rank3:[D]

Gather（收集到 root=rank0）:
  操作前  rank0:[A]        rank1:[B] rank2:[C] rank3:[D]
  操作后  rank0:[A,B,C,D]  rank1:[B] rank2:[C] rank3:[D]
```

### 2. 底层原理与算法

- **通信量**：root 侧发出 / 收齐约 `(N-1)/N·S`（自己那份不走网络），其余每 rank 收/发 `S/N`。
- 朴素实现是 root 对每个 rank 一次 `Send` / `Recv`，延迟 `O(N)`。
- ⚠️ **后端限制**：`scatter` / `gather` 在 NCCL 后端上支持有限（老版本不支持），**用 gloo 后端最稳**。GPU 上通常用 `AllGather` + 切片，或 `all_to_all` 替代。

### 3. 组合关系

- `Gather` 是 `Scatter` 的逆。
- `AllGather` = `Gather` 到所有 rank（而非只到 root）= `Gather` + `Broadcast` 的效果。

### 4. 应用场景

- `Scatter`：把一批样本 / 一个大张量的不同分片下发给各 rank 处理。
- `Gather`：推理/评测时把各 rank 的局部结果汇总到主 rank 统一输出或落盘。

### 5. 实例代码

```python
# scatter_gather.py
# 启动：torchrun --nproc_per_node=4 scatter_gather.py   （建议 gloo 后端）
import torch
import torch.distributed as dist

def main():
    # scatter/gather 用 gloo 最稳
    dist.init_process_group(backend="gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()

    # ---------- Scatter ----------
    recv = torch.zeros(1)
    if rank == 0:
        # root 准备 N 份数据：[10],[11],[12],[13]
        scatter_list = [torch.tensor([10.0 + i]) for i in range(world)]
    else:
        scatter_list = None
    dist.scatter(recv, scatter_list=scatter_list, src=0)
    print(f"[rank{rank}] scatter 后收到 = {recv.tolist()}")

    # ---------- Gather ----------
    send = torch.tensor([float(rank)])          # 每 rank 发自己的编号
    if rank == 0:
        gather_list = [torch.zeros(1) for _ in range(world)]
    else:
        gather_list = None
    dist.gather(send, gather_list=gather_list, dst=0)
    if rank == 0:
        print(f"[rank0] gather 收齐 = {[t.tolist() for t in gather_list]}")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（scatter/gather 用 gloo 后端最稳）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29507 scatter_gather.py
```

真实输出（按 rank 整理，打印顺序可能交错）：

```
[rank0] scatter 后收到 = [10.0]
[rank1] scatter 后收到 = [11.0]
[rank2] scatter 后收到 = [12.0]
[rank3] scatter 后收到 = [13.0]
[rank0] gather 收齐 = [[0.0], [1.0], [2.0], [3.0]]
```

Scatter：root 把 `[10,11,12,13]` 第 i 份分发给 rank i；Gather：root 把各 rank 的编号 `0/1/2/3` 按序收齐。

### 6. 对比补充：`Scatter` / `Gather` 与 `AllGather` 真的没区别吗

有区别，而且关键。三者数据流向完全不同（N=4，root=rank0）：

```
Scatter（一对多·分发，各拿不同片）
操作前  rank0:[A,B,C,D]  rank1:[·]  rank2:[·]  rank3:[·]
操作后  rank0:[A]        rank1:[B]  rank2:[C]  rank3:[D]

Gather（多对一·收集，只有 root 拿到全部）
操作前  rank0:[A]        rank1:[B]  rank2:[C]  rank3:[D]
操作后  rank0:[A,B,C,D]  rank1:[B]  rank2:[C]  rank3:[D]

AllGather（多对多·全收集，人手一份全部）
操作前  rank0:[A]        rank1:[B]        rank2:[C]        rank3:[D]
操作后  rank0:[A,B,C,D]  rank1:[A,B,C,D]  rank2:[A,B,C,D]  rank3:[A,B,C,D]
```

- **Scatter**：root 把 N 份**不同**数据，一人分一份（分发）。
- **Gather**：各 rank 的 1 份汇总，**只到 root**（收集）；非 root 拿不到完整结果。
- **AllGather**：各 rank 的 1 份汇总，**人手一份完整的**（多对多）。

组合关系与方向：

```
AllGather = Gather（先收集到 root） + Broadcast（再广播给所有人）
Scatter   = Gather 的逆方向（分发 vs 收集）
```

本文两段实跑输出正是最直接的佐证——Gather 只有 `rank0` 打印完整结果，而 AllGather 每个 rank 都打印 `[0,1,2,3]`：

```
# Gather：只有 rank0 齐
[rank0] gather 收齐 = [[0.0], [1.0], [2.0], [3.0]]

# AllGather：人手一份
[rank0] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
[rank1] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
[rank2] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
[rank3] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
```

**一句话结论**：Gather「只汇到 root」，AllGather「人人都拿到」，Scatter 则是反过来「分发不同片」——三者并不等价。也正因为 AllGather 要「人人都有」，通信比 Gather 重，常用 Ring 算法做到带宽最优。

---

## 2.3 `AllGather`：全收集

### 1. 定义与语义

`all_gather`：每个 rank 持有 1 份，操作后**每个 rank 都拿到全部 N 份**（按 rank 顺序拼接）。

```
操作前  rank0:[A]  rank1:[B]  rank2:[C]  rank3:[D]
操作后  rank0:[A,B,C,D]  rank1:[A,B,C,D]  rank2:[A,B,C,D]  rank3:[A,B,C,D]
```

### 2. 底层原理与算法

- **Ring-AllGather**：N-1 步，每步每个 rank 把「当前手里最新的一块」发给右邻居、从左邻居收一块。N-1 步后所有块转遍整个环。
- **通信量**：每个 rank 发送 / 接收约 `(N-1)/N·S`（`S` 为聚合后总大小）。带宽最优，几乎与朴素广播无关。

### 3. 组合关系

**`AllReduce = ReduceScatter + AllGather`**——这是最重要的组合等式，后面 AllReduce 会详述。`AllGather` 负责「把各自算好的分片拼回完整结果并人手一份」。

### 4. 应用场景

- **ZeRO / FSDP 的参数聚合**：FSDP 把模型参数按 rank 切分存储（每 rank 只存 1/N）。前向 / 反向用到某层时，临时 `AllGather` 把该层完整参数拼回来算，算完立刻释放。**用显存换通信**，让单卡能放下超大模型。
- **为什么选它**：需要「每个 rank 都临时拿到完整参数」，正是 AllGather 语义。

### 5. 实例代码

```python
# all_gather.py
# 启动：torchrun --nproc_per_node=4 all_gather.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    local = torch.tensor([float(rank)], device=device)       # 每 rank 1 份
    gather_list = [torch.zeros(1, device=device) for _ in range(world)]
    print(f"[rank{rank}] 操作前 local = {local.tolist()}")

    dist.all_gather(gather_list, local)                      # 全收集

    result = [t.item() for t in gather_list]
    print(f"[rank{rank}] 操作后 收齐 = {result}")
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

每个 rank 操作后都打印 `[0.0, 1.0, 2.0, 3.0]`。

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29508 all_gather.py
```

真实输出（按 rank 整理，打印顺序可能交错）：

```
[rank0] 操作前 local = [0.0]
[rank1] 操作前 local = [1.0]
[rank2] 操作前 local = [2.0]
[rank3] 操作前 local = [3.0]
[rank0] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
[rank1] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
[rank2] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
[rank3] 操作后 收齐 = [0.0, 1.0, 2.0, 3.0]
```

每个 rank 各持 1 份编号，AllGather 后人手一份完整的 `[0,1,2,3]`。

---

## 2.4 `Reduce` / `AllReduce`：归约 / 全归约

### 1. 定义与语义

- `Reduce(op)`：把所有 rank 的数据按 `op`（SUM/MAX/...）**逐元素归约**，结果只放到 root。
- `AllReduce(op)`：同样归约，但**结果人手一份**（所有 rank 都拿到）。

归约操作符覆盖：`SUM`（求和）/ `AVG`（求平均）/ `MAX` / `MIN` / `PROD`（求积）。

```
AllReduce + SUM，N=4，每 rank 持一个标量:
操作前  rank0:[1]  rank1:[2]  rank2:[3]  rank3:[4]
操作后  rank0:[10] rank1:[10] rank2:[10] rank3:[10]   (1+2+3+4=10，人手一份)

AllReduce + AVG:
操作后  每 rank 都是 10/4 = 2.5
```

### 2. 底层原理与算法：为什么 Ring-AllReduce 通信量与 N 几乎无关

**Ring-AllReduce = ReduceScatter + AllGather 两阶段**，这是带宽最优算法：

把每个 rank 的数据切成 N 块，环上 N 个 rank：

- **阶段一 ReduceScatter（N-1 步）**：每步每个 rank 把一块「加」到右邻居对应块上并传递。N-1 步后，**每个 rank 手里有「某一块的全局归约和」**（第 i 块的总和落在某个 rank 上）。
- **阶段二 AllGather（N-1 步）**：把这些「已归约好的块」沿环转一圈，让每个 rank 都集齐所有块。

**通信量推导**：每个 rank 在每一步收发一块（大小 `S/N`）。两阶段各 N-1 步：

```
单 rank 通信量 = 2 × (N-1) × (S/N) = 2(N-1)/N · S  ──(N→∞)──►  2S
```

**结论**：当 N 很大时，每个 rank 的通信量趋近于常数 `2S`，**几乎与 N 无关**。这就是 Ring-AllReduce 能扩展到上千卡仍高效的根本原因——加再多卡，单卡要搬的字节数不变（代价是延迟随 N 线性增长，所以超大 N 时 NCCL 会切到 Tree）。

- **Tree-AllReduce**：延迟 `~2·logN` 步，小数据更快。
- **拓扑敏感度**：Ring 对带宽敏感、吃满 NVLink；跨机走 IB 时延迟放大，NCCL 会分层（机内 Ring + 机间 Tree）。

### 3. 组合关系

- **AllReduce = ReduceScatter + AllGather**（本文 2.5 的 ReduceScatter + 本文 2.3 的 AllGather）。
- `Reduce` = AllReduce 后只保留 root 的那份（或归约树只汇到 root，不再广播回去）。

### 4. 应用场景

- **数据并行（DP）的梯度同步**，用的正是 **`AllReduce + AVG`**：
  - 每个 DP 副本在不同数据上算出各自的梯度，要把它们平均后让所有副本用同一个平均梯度更新 → 保证参数始终一致。
  - **为什么是 AVG 而不是 SUM**：loss 通常是 batch 内样本的平均，梯度要对「全局 batch」求平均才无偏；SUM 会让梯度放大 N 倍，等价于学习率被偷偷乘了 N。（实现上也可先 SUM 再除以 N，效果等同 AVG。）
- **张量并行（TP）的层内同步**，用的是 **`AllReduce + SUM`**：一层（如 Megatron 把一个 MLP/Attention 的权重按列或行切到多卡）被切开后，每张卡只算出**部分和**，前向要 `AllReduce` 把各卡的部分结果加起来得到完整输出，反向同理对输入梯度再做一次 `AllReduce`。所以 TP 每层都有 1~2 次 AllReduce，通信极频繁——这也是 TP 通常只在**机内高带宽**（NVLink）范围内用、不跨机的原因。
- `Reduce`：把各 rank 的 loss / 统计量汇总到主 rank 打印或记录（不需要人手一份时用 Reduce 比 AllReduce 省一半通信）。

### 5. 实例代码

```python
# all_reduce.py
# 启动：torchrun --nproc_per_node=4 all_reduce.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    # 每个 rank 持有自己的「梯度」（这里用 rank+1 模拟：1,2,3,4）
    grad = torch.tensor([float(rank + 1)], device=device)
    print(f"[rank{rank}] 操作前 grad = {grad.tolist()}")

    # ---- AllReduce + SUM ----
    s = grad.clone()
    dist.all_reduce(s, op=dist.ReduceOp.SUM)
    # ---- AllReduce + AVG：梯度同步真正用的（无 AVG 时先 SUM 再除以 world）----
    avg = grad.clone()
    dist.all_reduce(avg, op=dist.ReduceOp.SUM)
    avg /= world

    print(f"[rank{rank}] SUM = {s.tolist()}  AVG(梯度同步) = {avg.tolist()}")
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

预期：每个 rank 都打印 `SUM = [10.0]  AVG = [2.5]`。

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29509 all_reduce.py
```

真实输出（按 rank 整理，打印顺序可能交错）：

```
[rank0] 操作前 grad = [1.0]
[rank1] 操作前 grad = [2.0]
[rank2] 操作前 grad = [3.0]
[rank3] 操作前 grad = [4.0]
[rank0] SUM = [10.0]  AVG(梯度同步) = [2.5]
[rank1] SUM = [10.0]  AVG(梯度同步) = [2.5]
[rank2] SUM = [10.0]  AVG(梯度同步) = [2.5]
[rank3] SUM = [10.0]  AVG(梯度同步) = [2.5]
```

四个 rank 的梯度 `1/2/3/4`，SUM 后人手一份 `10`，除以 world=4 得平均 `2.5`——这正是数据并行梯度同步的做法。

> 其它归约符：把 `op` 换成 `dist.ReduceOp.MAX / MIN / PRODUCT` 即可。注意 NCCL 对 `AVG` 的原生支持见版本，稳妥做法是「SUM 后除以 world」。

---

## 2.5 `ReduceScatter`：归约分散

### 1. 定义与语义

`reduce_scatter`：先把所有 rank 的数据**逐元素归约**，再把结果**按块切开分散**——每个 rank 只拿到归约结果的「自己那一块」。

```
每 rank 持 N=4 块数据，ReduceScatter + SUM:

操作前  rank0: [a0, a1, a2, a3]
        rank1: [b0, b1, b2, b3]
        rank2: [c0, c1, c2, c3]
        rank3: [d0, d1, d2, d3]

操作后  rank0: [a0+b0+c0+d0]   ← 只拿第 0 块的全局和
        rank1: [a1+b1+c1+d1]   ← 只拿第 1 块
        rank2: [a2+b2+c2+d2]   ← 只拿第 2 块
        rank3: [a3+b3+c3+d3]   ← 只拿第 3 块
```

### 2. 底层原理与算法

- **Ring-ReduceScatter（N-1 步）**：就是 Ring-AllReduce 的前半段。
- **通信量**：单 rank `(N-1)/N·S`（恰为 AllReduce 的一半）。

### 3. 组合关系

**`AllReduce = ReduceScatter + AllGather`**：ReduceScatter 让每人拿到「一块的全局和」，AllGather 再把这些块拼齐并人手一份。

### 4. 应用场景

- **ZeRO / FSDP 的梯度切分**：反向算出梯度后，不做完整 AllReduce，而是 `ReduceScatter` —— 每个 rank 只保留并更新自己负责的那 1/N 参数对应的梯度。配合参数也切分（AllGather 临时取回），显存占用降到 1/N 量级。
- **为什么选它**：FSDP 下每个 rank 只需要「自己那片参数的归约梯度」，不需要完整梯度，用 ReduceScatter 比 AllReduce 省一半通信。

### 5. 实例代码

```python
# reduce_scatter.py
# 启动：torchrun --nproc_per_node=4 reduce_scatter.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    # 每个 rank 持 world 块；第 j 块的值 = rank*10 + j
    input_list = [torch.tensor([float(rank * 10 + j)], device=device) for j in range(world)]
    output = torch.zeros(1, device=device)
    print(f"[rank{rank}] 操作前 = {[t.item() for t in input_list]}")

    dist.reduce_scatter(output, input_list, op=dist.ReduceOp.SUM)

    # rank i 应拿到「所有 rank 的第 i 块」之和 = Σ_r (r*10 + i)
    print(f"[rank{rank}] 操作后 只拿第{rank}块的全局和 = {output.tolist()}")
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

N=4 时，rank i 的结果 = `Σ(10r+i), r=0..3 = 60 + 4i` → rank0:60, rank1:64, rank2:68, rank3:72。

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29510 reduce_scatter.py
```

真实输出（按 rank 整理，打印顺序可能交错）：

```
[rank0] 操作前 = [0.0, 1.0, 2.0, 3.0]
[rank1] 操作前 = [10.0, 11.0, 12.0, 13.0]
[rank2] 操作前 = [20.0, 21.0, 22.0, 23.0]
[rank3] 操作前 = [30.0, 31.0, 32.0, 33.0]
[rank0] 操作后 只拿第0块的全局和 = [60.0]
[rank1] 操作后 只拿第1块的全局和 = [64.0]
[rank2] 操作后 只拿第2块的全局和 = [68.0]
[rank3] 操作后 只拿第3块的全局和 = [72.0]
```

rank i 只拿到「所有 rank 第 i 块之和」：60/64/68/72，与推导 `60+4i` 完全一致。

---

## 2.6 `All2All` / `AllToAllv`：全交换

### 1. 定义与语义

**`All2All` 与 `AllGather` 的本质区别：AllGather 中每个 rank 发给所有人的是「同一份」数据；All2All 中每个 rank 发给不同人的是「不同」数据。** 相当于一次分布式的「矩阵转置」。

- **等长 All2All**：每个 rank 发给每个 rank 的块大小相同。
- **变长 AllToAllv**：各块大小可以不同（variable）。

```
All2All，N=3，用 r_sX 表示「rank r 要发给 rank X 的数据」:
操作前  rank0:[0_s0, 0_s1, 0_s2]   # 第 j 项准备发给 rank j
        rank1:[1_s0, 1_s1, 1_s2]
        rank2:[2_s0, 2_s1, 2_s2]
操作后  rank0:[0_s0, 1_s0, 2_s0]   # 第 i 项收自 rank i，内容是「发给我 rank0 的」
        rank1:[0_s1, 1_s1, 2_s1]
        rank2:[0_s2, 1_s2, 2_s2]
```

即：发送矩阵 M[i][j] = rank i 发给 rank j 的数据，操作后 rank j 收到的是 M[:, j] 这一列——**转置**。

### 2. 底层原理与算法

- **通信量**：每个 rank 发出 `(N-1)/N·S`（给别人的部分），收入同量。是所有集合通信里最「重」的——因为每对 rank 之间都有独立数据流。
- **拓扑敏感度极高**：N×N 的全连接流量，对互联带宽、对分带宽（bisection bandwidth）要求极高。这也是为什么 MoE 对超节点的高带宽全互联如此依赖。
- **变长（v）版本**：需要先交换各段长度（通常先一次小 All2All 交换 count），再按长度做数据交换。

### 3. 组合关系

- `All2All` 可由 N 轮 `SendRecv`（或 `Scatter`）拼成：第 k 轮，每个 rank i 把「发给 rank (i+k)%N 的块」发出去。
- 和 `AllGather` 的区别已在上面点明：**是否每个 rank 发送不同数据**。

### 4. 应用场景

- **MoE 专家并行（EP）的 token 路由（dispatch / combine）**，用的是**变长 AllToAllv**：
  - **dispatch**：每个 rank 上的 token 经过 gating 要被送到它选中的专家所在的 rank。由于每个 token 的选择不同，**每个 rank 发给各专家 rank 的 token 数量不等** → 必须用变长 AllToAllv。
  - **combine**：专家算完后，把结果按原路由送回 token 原来的 rank，又是一次（反向的）AllToAllv。
  - **为什么是变长**：路由是数据相关的，负载天然不均衡——专家 A 可能收到 100 个 token，专家 B 只收到 10 个。等长 All2All 无法表达这种不均衡。

### 5. 实例代码

```python
# all_to_all.py
# 启动：torchrun --nproc_per_node=4 all_to_all.py
import torch
import torch.distributed as dist

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    # ---------- 等长 All2All ----------
    # rank i 的第 j 个元素 = i*10 + j，准备发给 rank j
    send = torch.arange(world, device=device, dtype=torch.float32) + rank * 10
    recv = torch.zeros(world, device=device)
    print(f"[rank{rank}] 等长 操作前 send = {send.tolist()}")
    dist.all_to_all_single(recv, send)       # 等长全交换（本质是转置）
    print(f"[rank{rank}] 等长 操作后 recv = {recv.tolist()}")

    # ---------- 变长 AllToAllv（MoE 真实场景）----------
    # 构造各 rank 发给各 rank 的「不等长」token 数：发给 rank j 的个数 = (rank + j) % 3 + 1
    out_splits = [((rank + j) % 3 + 1) for j in range(world)]
    # 对端要收多少，需要先交换 split（这里直接按规则算出 in_splits）
    in_splits = [((j + rank) % 3 + 1) for j in range(world)]   # rank j 发给我 rank 的个数
    send_v = torch.full((sum(out_splits),), float(rank), device=device)
    recv_v = torch.zeros(sum(in_splits), device=device)
    print(f"[rank{rank}] 变长 发送量={out_splits} 接收量={in_splits}")
    dist.all_to_all_single(recv_v, send_v,
                           output_split_sizes=in_splits,
                           input_split_sizes=out_splits)
    print(f"[rank{rank}] 变长 操作后 recv_v = {recv_v.tolist()} (值=来源rank)")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29511 all_to_all.py
```

真实输出（按 rank 整理，打印顺序可能交错）：

```
# 等长 All2All（本质是转置）
[rank0] 等长 操作前 send = [0.0, 1.0, 2.0, 3.0]    操作后 recv = [0.0, 10.0, 20.0, 30.0]
[rank1] 等长 操作前 send = [10.0, 11.0, 12.0, 13.0] 操作后 recv = [1.0, 11.0, 21.0, 31.0]
[rank2] 等长 操作前 send = [20.0, 21.0, 22.0, 23.0] 操作后 recv = [2.0, 12.0, 22.0, 32.0]
[rank3] 等长 操作前 send = [30.0, 31.0, 32.0, 33.0] 操作后 recv = [3.0, 13.0, 23.0, 33.0]

# 变长 AllToAllv（recv_v 的值 = 来源 rank，个数由 in_splits 决定）
[rank0] 发送量=[1,2,3,1] 接收量=[1,2,3,1] recv_v = [0, 1,1, 2,2,2, 3]
[rank1] 发送量=[2,3,1,2] 接收量=[2,3,1,2] recv_v = [0,0, 1,1,1, 2, 3,3]
[rank2] 发送量=[3,1,2,3] 接收量=[3,1,2,3] recv_v = [0,0,0, 1, 2,2, 3,3,3]
[rank3] 发送量=[1,2,3,1] 接收量=[1,2,3,1] recv_v = [0, 1,1, 2,2,2, 3]
```

等长版把发送矩阵「转置」：rank j 收到的第 i 项是「rank i 发给它的」。变长版里 rank0 收到 1 个来自 r0、2 个来自 r1、3 个来自 r2、1 个来自 r3 → `[0,1,1,2,2,2,3]`，个数与 `in_splits` 完全对应，正是 MoE token 路由的负载不均衡形态。

> 变长版本的关键：`input_split_sizes` / `output_split_sizes` 分别告诉库「我发给每个 rank 多少、从每个 rank 收多少」。真实 MoE 里，这两个 split 本身也要先用一次小 All2All 交换 token 计数才能得到。

---

# 3. 加餐：用 `Send`/`Recv` 从零实现 Ring-AllReduce

前面反复说「集合通信底层是点对点拼的」「AllReduce = ReduceScatter + AllGather」。下面这段教学代码**只用 `batch_isend_irecv`（即 SendRecv）** 从零实现 Ring-AllReduce，并和 `dist.all_reduce` 对拍验证。读懂它，就真正打通了点对点与集合通信的任督二脉。

```python
# ring_allreduce_from_scratch.py
# 启动：torchrun --nproc_per_node=4 ring_allreduce_from_scratch.py
import torch
import torch.distributed as dist

def ring_all_reduce(tensor: torch.Tensor):
    """只用 SendRecv 实现 Ring-AllReduce（SUM）。
    分两阶段：ReduceScatter(N-1 步) + AllGather(N-1 步)。
    要求 tensor 长度能被 world 整除。"""
    rank = dist.get_rank()
    world = dist.get_world_size()
    left  = (rank - 1 + world) % world     # 从左邻居收
    right = (rank + 1) % world             # 发给右邻居

    chunks = list(tensor.chunk(world))     # 切成 world 块（view，原地可改）

    def sendrecv(send_chunk, recv_like):
        """发一块给右邻居，同时从左邻居收一块（SendRecv，不死锁）。"""
        recv_buf = torch.empty_like(recv_like)
        ops = [dist.P2POp(dist.isend, send_chunk.contiguous(), right),
               dist.P2POp(dist.irecv, recv_buf, left)]
        for w in dist.batch_isend_irecv(ops):
            w.wait()
        return recv_buf

    # ---------- 阶段一：ReduceScatter ----------
    # 第 step 步，发出块索引 (rank-step)，把收到的累加到块索引 (rank-step-1)
    for step in range(world - 1):
        send_idx = (rank - step + world) % world
        recv_idx = (rank - step - 1 + world) % world
        recv_buf = sendrecv(chunks[send_idx], chunks[recv_idx])
        chunks[recv_idx] += recv_buf        # 归约：累加
    # 此时 chunks[(rank+1)%world] 持有「该块的全局和」

    # ---------- 阶段二：AllGather ----------
    # 把已归约好的块沿环转一圈，覆盖式填满每个 rank
    for step in range(world - 1):
        send_idx = (rank + 1 - step + world) % world
        recv_idx = (rank - step + world) % world
        recv_buf = sendrecv(chunks[send_idx], chunks[recv_idx])
        chunks[recv_idx].copy_(recv_buf)    # 覆盖：拷贝（不是累加）

def main():
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank = dist.get_rank()
    world = dist.get_world_size()
    device = torch.device(f"cuda:{rank}") if torch.cuda.is_available() else torch.device("cpu")

    n = world * 2                                   # 长度能被 world 整除
    x = torch.arange(n, dtype=torch.float32, device=device) + rank * 100
    ref = x.clone()
    dist.all_reduce(ref, op=dist.ReduceOp.SUM)      # 官方实现作为参照

    mine = x.clone()
    ring_all_reduce(mine)                           # 我们从零实现的

    ok = torch.allclose(mine, ref)
    print(f"[rank{rank}] 自实现 == 官方AllReduce ? {ok}")
    if rank == 0:
        print(f"[rank0] 官方结果   = {ref.tolist()}")
        print(f"[rank0] 自实现结果 = {mine.tolist()}")

    dist.destroy_process_group()

if __name__ == "__main__":
    main()
```

跑通后每个 rank 都应打印 `== 官方AllReduce ? True`。这段代码把「`2(N-1)` 轮 SendRecv」的内部过程完全摊开：前 N-1 轮边传边加（ReduceScatter），后 N-1 轮边传边盖（AllGather）。

实测执行（本机无 GPU，走 gloo 后端）：

```bash
torchrun --nproc_per_node=4 --rdzv-endpoint=127.0.0.1:29512 ring_allreduce_from_scratch.py
```

真实输出（按 rank 整理）：

```
[rank0] 自实现 == 官方AllReduce ? True
[rank1] 自实现 == 官方AllReduce ? True
[rank2] 自实现 == 官方AllReduce ? True
[rank3] 自实现 == 官方AllReduce ? True

# 官方结果与自实现结果完全一致：
[600.0, 604.0, 608.0, 612.0, 616.0, 620.0, 624.0, 628.0]
```

四个 rank 全部 `True`——只用 `batch_isend_irecv`（SendRecv）拼出的 Ring-AllReduce，结果与官方 `dist.all_reduce` 逐元素一致（每个元素 = `4i + 600`，正是 4 个 rank 对应位置之和）。至此「集合通信底层由点对点拼装」得到实证。

---

# 小结

一条自底向上的逻辑链：**点对点是积木 → 拼成集合通信 → 服务于并行策略**。

![通信原语全景：点对点→集合通信→并行策略](/images/2026-10-04-communication-primitives-explained/1-overview.svg)

几个要记住的结论：

- **集合通信都是点对点拼的**。Ring 类算法的每一步就是一次 `SendRecv`；`AllReduce = ReduceScatter + AllGather`。
- **Ring-AllReduce 带宽最优**：单卡通信量 `2(N-1)/N·S → 2S`，**几乎与卡数无关**，这是它能扩展到千卡的根本；小数据时 Tree 延迟更优，NCCL 自动择优。
- **原语各司其职**：DP 用 `AllReduce+AVG`；TP 用 `AllReduce+SUM`（层内，仅机内）；FSDP 用 `AllGather`+`ReduceScatter`；PP 用 `Send/Recv`；MoE 用变长 `AllToAllv`；初始化用 `Broadcast`；对齐/调试用 `Barrier`。
- **All2All 是最重的通信**，N×N 全连接流量，对带宽/对分带宽要求极高——这也正是 MoE 场景强烈依赖超节点高带宽全互联的原因。

把这组原语的语义、复杂度、组合关系吃透，再看任何分布式训练框架（Megatron / DeepSpeed / FSDP / vLLM）的通信代码，都只是这几块积木的不同拼法而已。
