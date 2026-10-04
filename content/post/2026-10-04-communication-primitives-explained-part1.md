---
layout:     post
title:      "一文吃透分布式通信原语（上）：点对点基础与全局图谱"
subtitle:   "Send/Recv、ISend/IRecv、SendRecv、Barrier —— 一切集合通信的积木，附全局对比表与可运行 PyTorch 代码"
description: "分布式通信原语深度科普（上篇）：先建立全局图谱（一图速览 + 全局对比表），再把点对点基础层讲透——Send/Recv（阻塞）、ISend/IRecv（非阻塞·计算通信 overlap）、SendRecv（环形不死锁）、Barrier（屏障对齐）。每个原语给出语义图、通信复杂度、原语组合关系，以及在流水线并行（PP）等场景的真实应用，配可运行的 torch.distributed 代码（NCCL/gloo）并附实跑输出。下篇讲集合通信与从零实现 Ring-AllReduce。"
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

本系列分上下两篇：

- **上篇（本文）**：先用「一图速览 + 全局对比表」建立全局图谱，再把**点对点基础层**（Send/Recv、ISend/IRecv、SendRecv、Barrier）讲透。
- **下篇**：讲**集合通信**（Broadcast / Scatter / Gather / AllGather / Reduce / AllReduce / ReduceScatter / All2All），并用 Send/Recv 从零实现 Ring-AllReduce 与官方对拍。

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

# 上篇小结与下篇预告

上篇我们打好了地基：

- **全局图谱**：12 个原语分点对点与集合两类，用一张对比表看清各自的「输入 / 输出 / 通信量 / 典型场景」。
- **点对点四件套**：`Send/Recv`（阻塞收发，PP 传激活/梯度的主力）、`ISend/IRecv`（非阻塞，用来做计算-通信 overlap）、`SendRecv`（发右收左，环形不死锁，是 Ring 算法的基本步）、`Barrier`（不传数据，只对齐时序）。
- **一个贯穿全文的核心认知**：所有集合通信最终都能拆成一串 `Send`/`Recv`——点对点就是积木。

> **下篇**将把这些积木拼起来：详解 **Broadcast / Scatter / Gather / AllGather / Reduce / AllReduce / ReduceScatter / All2All**，讲清 Ring-AllReduce 为什么「单卡通信量 ≈2S、几乎与卡数无关」、`AllReduce = ReduceScatter + AllGather` 的组合关系，以及它们在 DP / TP / FSDP / MoE 中的真实角色；最后用一段**只靠 Send/Recv 从零实现 Ring-AllReduce** 的教学代码与官方实现对拍，把「集合通信由点对点拼装」彻底讲透。
