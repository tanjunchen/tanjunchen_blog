---
layout:     post
title:      "Linux 是如何处理网络数据包？"
subtitle:   "当网络数据包到达网卡时，数据包从网卡是如何到 Linux（以内核4.19举例） 网络协议栈？"
description: ""
author: "陈谭军"
date: 2023-07-25
published: true
tags:
    - Linux
    - network
categories:
    - TECHNOLOGY
showtoc: true
---

当网络数据包到达网卡时，数据包从网卡是如何到 Linux（以内核4.19举例） 网络协议栈？先回顾 OSI 七层模型与 TCP/IP 五层模型，如下所示：

![](/images/2023-07-25-network-package/1.png)

TCP/IP 应用层数据包的格式如下所示：

![](/images/2023-07-25-network-package/2.png)

我们先来了解一下 Linux 中的网络协议模型和网络子系统。

* 网络协议模型（网络协议栈）
    * 应用层提供 socket 接口来供用户进程访问内核空间的网络协议栈
    * 传输层、网络层协议由 Linux 内核网络协议栈实现
    * 链路层协议靠网卡驱动来实现
    * 物理层协议由硬件网卡实现

* 网络子系统（网络子系统是 Linux 内核中的一部分，由多个模块和驱动程序组成，它负责管理和控制系统的网络功能以实现网络通信）
    * System call interface：为应用程序获取内核的网络系统提供了接口，例如 socket
    * Protocol agnostic interface：为和各种传输层协议的网络交互提供的一层公共接口
    * Network protocals：对各种传输层协议的实现，如 TCP、UDP、IP 等
    * Device agnostic interface：为各种底层网络设备抽象出的公共接口，与各种网络设备驱动连接在一起
    * Device drivers：与各种网络设备交互的驱动

当 Linux 接收一个数据包的时候，这个包是怎么经过 Linux 的内核从而被应用程序拿到的呢？如下所示：

![](/images/2023-07-25-network-package/3.png)

1、数据到达网卡（NIC，Network Interface Card）

首先数据包到达网卡之后，网卡会校验接收到的数据包中的目的 MAC 地址是不是自己的 MAC 地址，如果不是的话通常就会丢弃掉。这种只接受发送给自己的数据包（其余的扔掉）的工作模式称为非混杂模式（Non-Promiscuous Mode）。混杂模式（Promiscuous Mode）则是网卡会接收通过网络传输的所有数据包，而不仅仅是发送给它自己的数据包。非混杂模式是网卡默认的工作模式，可以尽可能的保护网络安全和减少网络负载。网卡在校验完 MAC 地址之后还会校验数据帧（Data Frame）中校验字段 FCS 来一次确保接收到的数据包是正确的。

2、网卡硬件缓冲区 -> 系统内存（Ring Buffer）

当网卡接收到数据包时，它将数据包的内容存储在硬件缓冲区中，然后通过 DMA 将接收到的数据从硬件缓冲区传输到系统内存中的指定位置，这个位置通常是一个环形缓冲区（Ring Buffer）。

3、触发硬中断

当网卡将数据包 DMA 到用于接收的环形缓冲区（Ring Buffer）之后，就会触发一个硬中断来告诉 CPU 已经收到数据包。什么时候会触发一个硬中断，可以通过下面的参数来进行配置：
* rx-usecs：当过这么长时间过后，一个中断就会被产生。
* rx-frames：当累计接收到这么多个数据帧后，一个中断就会被产生。

当 Ring Buffer 满了之后，新来的数据包将给丢弃。CPU 收到硬中断之后就会停止手中的活，保存上下文，然后去调用网卡驱动注册的硬中断处理函数。为数据包分配 skb_buff，并将接收到的数据拷贝到 skb_buff 缓冲区中。当一个数据包经过了网卡引起中断之后，每一个包都会在内存中分配一块区域，称为 skb_buff (套接字缓存，socket buffer) skb_buff是 Linux 网络的一个核心数据结构。

4、触发软中断

1. 网卡的硬中断处理函数处理完之后驱动先关闭硬中断，然后开启软中断。待 Ring Buffer 中的所有数据包被处理完成后，开启网卡的硬中断，这样下次网卡再收到数据的时候就会通知 CPU。
2. 调用 net_rx_action 函数，它会通过 poll 函数去 rx_ring 中拿数据帧，获取的时候顺便把 rx_ring 上的数据给删除。
```c
static void net_rx_action(struct softirq_action *h)
{
    struct softnet_data *sd = &__get_cpu_var(softnet_data);
    unsigned long time_limit = jiffies + 2;
    int budget = netdev_budget;
    void *have;

    local_irq_disable();

    while (!list_empty(&sd->poll_list)) {
        ......
        n = list_first_entry(&sd->poll_list, struct napi_struct, poll_list);

        work = 0;
        if (test_bit(NAPI_STATE_SCHED, &n->state)) {
            work = n->poll(n, weight);
            trace_napi_poll(n);
        }

        budget -= work;
    }
}
```
3. 除此之外，poll 函数会把 Ring Buffer 中的数据包转换成内核网络模块能够识别的 skb 格式（即 socket kernel buffer）。
4. 最后进入 netif_receive_skb 处理流程，它是数据链路层接收数据帧的最后一关。根据注册在全局数组 ptype_all 和 ptype_base 里的网络层数据帧类型去调用第三层协议的接收函数处理。例如对于 ip 包来讲，就会进入到 ip_rcv；如果是 arp 包的话，会进入到 arp_rcv。

5、到达网络层（以 IP 协议为例）

IP 层的入口函数在 ip_rcv 函数，调用 ip_rcv 函数进入三层协议栈。首先会对数据包进行各种检查（检查 IP Header），然后调用 netfilter 中的钩子函数：NF_INET_PRE_ROUTING。NF_INET_PRE_ROUTING 会根据预设的规则对数据包进行判断并根据判断结果做相关的处理（修改或者丢弃数据包）。处理完成后，数据包交由 ip_rcv_finish 处理，该函数根据路由判决结果，决定数据包是交由本机上层应用处理，还是需要进行转发。如果是交由本机处理，则会交由 ip_local_deliver 本地上交流程；如果需要转发，则交由 ip_forward 函数走转发流程。

6、到达传输层（以 TCP 为例）

传输层 TCP 处理入口在 tcp_v4_rcv 函数，首先检查数据包的 TCP 头部等信息，确保数据包的完整性和正确性。然后去查找该数据包对应的已经打开的 socket，如果找不到匹配的 socket，表示该数据包不属于任何一个已建立的连接，因此该数据包会被丢弃。如果找到了匹配的 socket，TCP 会进一步检查该 socket 和连接的状态，如果状态正常，TCP 会将数据包从内核传输到用户空间，放入 socket 的接收缓冲区（socket receive buffer）。

7、应用层

当数据包到达操作系统内核的传输层时，应用程序可以从套接字的接收缓冲区（socket receive buffer）中读取数据包。一般有两种方式读取数据，一种是 recvfrom 函数阻塞在那里等着数据来，这种情况下当 socket 收到通知后，recvfrom 就会被唤醒，然后读取接收队列的数据。另一种是通过 epoll 或者 select 监听相应的 socket，当收到通知后，再调用 recvfrom 函数去读取接收队列的数据。

总结一下 Linux 网络收包流程：
* 数据到达网卡之后，网卡通过 DMA 将数据放到内存分配好的一块 Ring Buffer 中，然后触发硬中断；
* CPU 收到硬中断之后简单的处理了一下（分配 skb_buffer），然后触发软中断；
* 软中断进程 ksoftirqd 执行一系列操作（例如把数据帧从 ring ruffer 上取下来）然后将数据送到三层协议栈中；
* 在三层协议栈中数据被进一步处理发送到四层协议栈；
* 在四层协议栈中，数据会从内核拷贝到用户空间，供应用程序读取；
* 最后被处在应用层的应用程序去读取；
