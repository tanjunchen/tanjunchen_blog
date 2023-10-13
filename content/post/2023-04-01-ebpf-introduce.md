---
layout:     post
title:      "简单了解与学习 eBPF"
subtitle:   "eBPF 是一项革命性的技术，起源于 Linux 内核，可以在操作系统内核等特权上下文中运行沙盒程序。它用于安全有效地扩展内核的功能，而无需更改内核源代码或加载内核模块。"
description: "本文主要介绍什么是 eBPF？、介绍 eBPF、为什么使用 eBPF？、开发工具链等内容"
author: "陈谭军"
date: 2023-04-01
#image: "/img"
published: true
tags:
    - ebpf
    - kubernetes
categories:
    - TECHNOLOGY
showtoc: true
---

# 什么是 eBPF？

eBPF 是一项革命性的技术，起源于 Linux 内核，可以在操作系统内核等特权上下文中运行沙盒程序。它用于安全有效地扩展内核的功能，而无需更改内核源代码或加载内核模块。

从历史进程上看，操作系统一直是实现可观察性、安全性和网络功能的理想场所，因为内核具有监督和控制整个系统的权力。同时，操作系统内核由于其核心作用和对稳定性和安全性的强烈要求，很难迭代与演进。因此，与在操作系统之外实现的功能相比，操作系统级别的迭代效率比传统上在操作系统之外实现功能较低，eBPF 整体架构图如下所示：
<img src="/images/2023-04-01-ebpf-introduce/什么是eBPF.png" width="100%">

eBPF 允许沙盒程序在操作系统中运行，这意味着应用程序开发人员可以在运行时为操作系统运行 eBPF 程序添加其他的功能。然后，操作系统保证了安全性和执行效率，就像是在 JIT 编译器和验证引擎的帮助下以本机方式编译的一样。从而，衍生出了很多基于 eBPF 的项目，涵盖了下一代网络、可观察性和安全功能等领域。如今，eBPF 被广泛用于驱动各种各样的用例：在现代数据中心和云原生环境中提供高性能的网络和负载平衡、以低开销提取细粒度的安全可观测性数据、帮助应用程序开发人员跟踪应用程序、为性能故障排除提供参考、应用程序和容器运行时安全检查等等。

## 什么是 eBPF.io？

[ebpf.io](https://ebpf.io/) 是每个人就 eBPF 进行学习和合作的网站。eBPF 是一个开放的社区，每个人都可以参与和分享。无论你是想阅读 eBPF 的第一篇简介，还是想寻找更多的阅读材料，或者是迈出成为主要 eBPF 项目贡献者的第一步，eBPF.io 都会帮助你。

## eBPF 和 BPF 代表什么？

BPF 最初代表 Berkeley 数据包过滤器，但现在 eBPF（扩展BPF）可以做的远不止数据包过滤，这个缩写词不再有意义了。eBPF 现在被认为是一个独立的术语，不代表任何东西。在 Linux 源代码中，术语“BPF”仍然存在，在工具和文档中，术语 BPF 和 eBPF 通常可以互换使用。最初的 BPF 有时被称为cBPF（经典BPF），以区别于eBPF。

## bee 代表什么？

bee 是 eBPF 的官方 logo，最初由 Vadim Shchekoldin 创建。在 [第一届 eBPF 峰会](https://ebpf.io/summit-2020.html) 上进行了投票，bee 被命名为 eBee。（有关徽标可接受使用的详细信息，请参阅 [Linux 基金会品牌指南](https://www.linuxfoundation.org/brand-guidelines)\)。

# 介绍 eBPF

以下章节是 eBPF 的相关介绍。如果想了解有关 eBPF 的更多信息，请参阅 [eBPF&XDP 参考指南](https://docs.cilium.io/en/stable/bpf/)。无论是希望构建 eBPF 程序的开发人员，还是有兴趣利用使用 eBPF 的解决方案，了解基本概念和体系结构都很有用。

## Hook 视图

eBPF 程序是事件驱动的，当内核或应用程序通过某个 hook 点时运行。预定义的 hook 点包括系统调用（system calls）、函数进入/退出（function entry/exit）、内核跟踪点（kernel tracepoints）、网络事件（network events）和其他，示例如下所示：
<img src="/images/2023-04-01-ebpf-introduce/Hook视图.png" width="100%">
如果不存在用于特定需求的预定义 hook，则可以创建内核探针（kprobe）或用户探针（uprobe），将 eBPF 程序连接到内核或用户应用程序中的几乎任何位置，示例如下所示：
<img src="/images/2023-04-01-ebpf-introduce/Hook视图2.png" width="100%">

## 如何编写 eBPF 程序？

在许多场景中，eBPF 不是可以直接使用的，而是通过 [Cilium](https://ebpf.io/applications/#cilium)、[bcc](https://ebpf.io/applications/#bcc) 或 [bpftrace](https://ebpf.io/applications/#bpftrace) 等项目间接使用的，这些项目在 eBPF 之上提供了抽象，不需要直接编写程序，而是提供了基于意图的定义的能力，然后用 eBPF 实现。
<img src="/images/2023-04-01-ebpf-introduce/如何编写eBPF程序.png" width="100%">
如果不存在更高层次的抽象，则需要直接编写程序。Linux 内核期望 eBPF 程序以字节码的形式加载。虽然直接编写字节码当然是可能的，但更常见的开发实践是利用像 [LLVM](https://llvm.org/) 这样的编译器将伪 C 代码编译成 eBPF 字节码。

## 加载与验证 eBPF 程序？

当确定所需的 hook 后，可以使用 bpf 系统调用将 eBPF 程序加载到 Linux 内核中。这通常是使用一个可用的 eBPF 库来完成的。下一节介绍了可用的开发工具库，如下所示：
<img src="/images/2023-04-01-ebpf-introduce/加载与验证eBPF程序.png" width="100%">

## 验证

验证步骤确保 eBPF 程序可以安全运行，它验证程序是否满足以下几个条件，例如： 

* 加载 eBPF 程序的进程具有所需的功能（特权），除非启用了非特权 eBPF，否则只有特权进程才能加载 eBPF 程序。
* 该程序不会崩溃或以其他方式损害系统。
* 程序总是运行到完成（即程序不会永远处于循环中，从而阻碍进一步处理）。
<img src="/images/2023-04-01-ebpf-introduce/验证.png" width="100%">

## JIT 编译

JIT 编译步骤将程序的通用字节码转换为机器特定的指令集，以优化程序的执行速度。这使得 eBPF 程序的运行效率与本机编译的内核代码或作为内核模块加载的代码一样高。

## Maps

eBPF 程序的一个重要方面是共享收集的信息和存储状态的能力。为此，eBPF 程序可以利用 eBPF Map 的概念在一组广泛的数据结构中存储和检索数据。eBPF Map 可以通过系统调用从 eBPF 程序以及用户空间中的应用程序访问，示例如下所示：
<img src="/images/2023-04-01-ebpf-introduce/Maps.png" width="100%"> 
以下是支持的 Map 类型的不完整列表，对于各种 Map 类型，共享和每个CPU的变化都是可用的。

* 哈希表、数组（Hash tables, Arrays）
* LRU（最近最少使用）
* 环形缓冲器（Ring Buffer）
* 堆栈跟踪（Stack Trace）
* LPM（最长前缀匹配）
* ...

## 辅助调用（Helper Call）

eBPF 程序不能调用任意的内核函数，如果允许这样做会将 eBPF 程序绑定到特定的内核版本，并会使程序的兼容性复杂化。相反，eBPF 程序可以对 helper 函数进行函数调用，这是内核提供的一个众所周知且稳定的 API，如下所示：
<img src="/images/2023-04-01-ebpf-introduce/辅助调用.png" width="100%">   
可用的 helper 程序调用工具集不断发展，可用帮助程序调用的示例如下所示：  

* 生成随机数
* 获取当前时间和日期
* 访问 eBPF Map
* 获取进程/cgroup上下文
* 操作网络数据包和转发逻辑

## 尾调用（Tail & Function Calls）

eBPF 程序可以通过尾部和函数调用的概念进行组合。函数调用允许在 eBPF 程序中定义和调用函数。Tail 调用可以调用和执行另一个 eBPF 程序，并替换执行上下文，类似于 execve() 系统调用对常规进程的操作方式，示例如下所示：
<img src="/images/2023-04-01-ebpf-introduce/尾调用.png" width="100%">

## eBPF 安全性

eBPF 是一项非常强大的技术，现在运行在许多关键软件基础设施组件的核心。在 eBPF 的开发过程中，当考虑将 eBPF 纳入 Linux 内核时，eBPF 的安全性是最关键的方面。eBPF 的安全性通过以下几层来保证：<font color=red>**需要特权权限、验证器校验、程序加固、抽象运行时上下文**</font>等。

**特权模式：**   
除非启用了无特权 eBPF，否则所有打算将 eBPF 程序加载到 Linux 内核的进程都必须以特权模式（root）运行，或者需要 CAP_BPF 功能。这意味着不受信任的程序无法加载 eBPF 程序。
如果启用了无特权 eBPF，则无特权进程可以加载某些 eBPF 程序，这些程序的功能集减少，并且对内核的访问权限有限。

**验证器校验：**   
如果允许进程加载 eBPF 程序，则所有程序仍然通过 eBPF 验证器。eBPF 验证器确保程序本身的安全，如下所示：

* 程序经过验证，以确保它们始终运行到完成，例如 eBPF 程序可能永远不会阻塞或处于循环中。eBPF 程序可能包含所谓的有界循环，但只有当验证器能够确保循环包含一个保证为真的退出条件时，该程序才被接受。
* 程序不能使用任何未初始化的变量或越界访问内存。
* 程序必须符合系统的大小要求，不可能加载任意大的 eBPF 程序。
* 程序必须具有有限的复杂性，验证器将评估所有可能的执行路径，并且必须能够在配置的复杂性上限的限制内完成分析。

验证器是一种安全工具，用于检查程序是否可以安全运行。

**程序加固：**   
成功完成验证后，eBPF 程序将根据程序是从特权进程还是非特权进程加载来执行强化过程。此步骤包括：

* 程序执行保护：保存 eBPF 程序的内核内存受到保护并变为只读。如果出于任何原因，无论是内核错误还是恶意操作，试图修改 eBPF 程序，内核将崩溃，而不是允许它继续执行损坏/被操纵的程序。
* 针对 Spectre 的缓解措施：在猜测下，CPU 可能会预测失误分支，并留下可观察到的副作用，这些副作用可以通过侧通道提取。举几个例子：eBPF 程序屏蔽内存访问，以便将瞬态指令下的访问重定向到受控区域，验证器还遵循仅在推测执行下可访问的程序路径，JIT 编译器在尾调用无法转换为直接调用的情况下发出 Retpoline。
* 常量失效：代码中的所有常量都是失效的，以防止 JIT 喷射攻击。这可以防止攻击者将可执行代码作为常量注入，在存在另一个内核错误的情况下，攻击者可以跳到 eBPF 程序的内存部分来执行代码。

**抽象运行时上下文：**   
eBPF 程序无法直接访问任意内核内存。必须通过 eBPF helper 访问程序上下文之外的数据和数据结构。这保证了一致的数据访问，并使任何此类访问都受制于 eBPF 程序的权限，例如，只有与程序类型相关的数据结构才能被读取或（有时）修改，前提是验证器可以在加载时确保永远不会发生越界访问；或者只有在可以保证修改是安全的情况下，运行的 eBPF 程序才被允许修改某些数据结构的数据，eBPF 程序不能随机修改内核中的数据结构。

# 为什么使用 eBPF？

## 可编程性的优势

让我们从一个类比开始，你还记得 GeoCities 吗？20年前，网页几乎完全是用静态标记语言（HTML）编写的。网页基本上是一个带有应用程序（浏览器）的文档。纵观当今的网页，网页已经成为成熟的应用程序，基于网络的技术已经取代了绝大多数用需要编译的语言编写的应用程序。是什么促成了这种演变？
<img src="/images/2023-04-01-ebpf-introduce/可编程性的优势.png" width="100%">
简单的答案是引入 JavaScript 的可编程性。它开启了一场巨大的革命，导致浏览器进化为几乎独立的操作系统。

为什么会发生进化？程序员不再与运行特定浏览器版本的用户绑定。必要的构建块的可用性并没有让标准机构相信需要一个新的 HTML 标记，而是将底层浏览器的创新速度与运行在顶部的应用程序脱钩。这当然有点过于简单化了，因为 HTML 确实随着时间的推移而发展，并为成功做出了贡献，但 HTML 本身的发展还不够。在举这个例子并将其应用于eBPF之前，让我们看看在引入 JavaScript 时至关重要的几个关键方面：

* 安全：不受信任的代码在用户的浏览器中运行。这是通过沙盒 JavaScript 程序和抽象对浏览器数据的访问来解决的。
* 持续交付：程序逻辑的发展必须是可能的，而不需要不断推出新的浏览器版本。这是通过提供足够构建任意逻辑的正确底层构建块来解决的。
* 性能：必须以最小的开销提供可编程性。通过引入实时（JIT）编译器解决了这一问题。

对于以上所有内容，出于同样的原因，可以在 eBPF 中找到确切的对应项。

## eBPF 对 Linux 内核的影响

现在让我们回到 eBPF。为了理解 eBPF 在 Linux 内核上的可编程性影响，有助于对 Linux 内核的体系结构以及它如何与应用程序和硬件交互有更高的理解。如下所示：
<img src="/images/2023-04-01-ebpf-introduce/eBPF对Linux内核的影响.png" width="100%">

Linux 内核的主要目的是抽象硬件或虚拟硬件，并提供一致的 API（系统调用），允许应用程序运行和共享资源。为了实现这一点，需要维护一组广泛的子系统和层来分配这些职责。每个子系统通常允许某种级别的配置，以满足用户的不同需求。如果无法配置所需的行为，则需要从历史上更改内核，留下两个选项：

* 原生支持
    * 更改内核源代码并说服 Linux 内核社区需要进行更改。
    * 等待几年，新的内核版本可能满足要求。
* 内核模块
    * 编写内核模块
    * 定期修复它，因为每个内核版本都可能破坏它
    * 由于缺乏安全边界，有损坏 Linux 内核的风险

eBPF 提供了一个新的选项，可以重新编程 Linux 内核的行为，而无需更改内核源代码或加载内核模块。在很多方面，这与 JavaScript 和其他脚本语言解锁系统进化的方式非常相似，而系统的进化已经变得难以改变或代价高昂。

# 开发工具链

有几个开发工具链可以帮助我们实现 eBPF 项目的开发和管理。所有这些都满足了用户的不同需求：

## bcc

BCC 是一个框架，使用户可以编写内嵌 eBPF 程序的 python 程序。该框架主要针对涉及应用程序和系统分析/跟踪的用例，其中 eBPF 程序用于收集统计信息或生成事件，用户空间中的对应程序收集数据并以人类可读的形式显示。运行 python 程序将生成 eBPF 字节码并将其加载到内核中。
<img src="/images/2023-04-01-ebpf-introduce/bcc.png" width="100%">
BCC - 用于基于 BPF 的 Linux IO 分析、网络、监控等的工具，项目源代码见[iovisor
/
bcc](https://github.com/iovisor/bcc#bpf-compiler-collection-bcc)。以下示例表示 eBPF 应用程序，用于解析 HTTP 数据包并提取（并在屏幕上打印）GET/POST 请求中包含的 URL。

http-parse-complete.c
```c
#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <bcc/proto.h>

#define IP_TCP 	6
#define ETH_HLEN 14

struct Key {
	u32 src_ip;               //source ip
	u32 dst_ip;               //destination ip
	unsigned short src_port;  //source port
	unsigned short dst_port;  //destination port
};

struct Leaf {
	int timestamp;            //timestamp in ns
};

//BPF_TABLE(map_type, key_type, leaf_type, table_name, num_entry)
//map <Key, Leaf>
//tracing sessions having same Key(dst_ip, src_ip, dst_port,src_port)
BPF_HASH(sessions, struct Key, struct Leaf, 1024);

/*eBPF program.
  Filter IP and TCP packets, having payload not empty
  and containing "HTTP", "GET", "POST"  as first bytes of payload.
  AND ALL the other packets having same (src_ip,dst_ip,src_port,dst_port)
  this means belonging to the same "session"
  this additional check avoids url truncation, if url is too long
  userspace script, if necessary, reassembles urls split in 2 or more packets.
  if the program is loaded as PROG_TYPE_SOCKET_FILTER
  and attached to a socket
  return  0 -> DROP the packet
  return -1 -> KEEP the packet and return it to user space (userspace can read it from the socket_fd )
*/
int http_filter(struct __sk_buff *skb) {

	u8 *cursor = 0;

	struct ethernet_t *ethernet = cursor_advance(cursor, sizeof(*ethernet));
	//filter IP packets (ethernet type = 0x0800)
	if (!(ethernet->type == 0x0800)) {
		goto DROP;
	}

	struct ip_t *ip = cursor_advance(cursor, sizeof(*ip));
	//filter TCP packets (ip next protocol = 0x06)
	if (ip->nextp != IP_TCP) {
		goto DROP;
	}

	u32  tcp_header_length = 0;
	u32  ip_header_length = 0;
	u32  payload_offset = 0;
	u32  payload_length = 0;
	struct Key 	key;
	struct Leaf zero = {0};

        //calculate ip header length
        //value to multiply * 4
        //e.g. ip->hlen = 5 ; IP Header Length = 5 x 4 byte = 20 byte
        ip_header_length = ip->hlen << 2;    //SHL 2 -> *4 multiply

        //check ip header length against minimum
        if (ip_header_length < sizeof(*ip)) {
                goto DROP;
        }

        //shift cursor forward for dynamic ip header size
        void *_ = cursor_advance(cursor, (ip_header_length-sizeof(*ip)));

	struct tcp_t *tcp = cursor_advance(cursor, sizeof(*tcp));

	//retrieve ip src/dest and port src/dest of current packet
	//and save it into struct Key
	key.dst_ip = ip->dst;
	key.src_ip = ip->src;
	key.dst_port = tcp->dst_port;
	key.src_port = tcp->src_port;

	//calculate tcp header length
	//value to multiply *4
	//e.g. tcp->offset = 5 ; TCP Header Length = 5 x 4 byte = 20 byte
	tcp_header_length = tcp->offset << 2; //SHL 2 -> *4 multiply

	//calculate payload offset and length
	payload_offset = ETH_HLEN + ip_header_length + tcp_header_length;
	payload_length = ip->tlen - ip_header_length - tcp_header_length;

	//http://stackoverflow.com/questions/25047905/http-request-minimum-size-in-bytes
	//minimum length of http request is always geater than 7 bytes
	//avoid invalid access memory
	//include empty payload
	if(payload_length < 7) {
		goto DROP;
	}

	//load first 7 byte of payload into p (payload_array)
	//direct access to skb not allowed
	unsigned long p[7];
	int i = 0;
	for (i = 0; i < 7; i++) {
		p[i] = load_byte(skb, payload_offset + i);
	}

	//find a match with an HTTP message
	//HTTP
	if ((p[0] == 'H') && (p[1] == 'T') && (p[2] == 'T') && (p[3] == 'P')) {
		goto HTTP_MATCH;
	}
	//GET
	if ((p[0] == 'G') && (p[1] == 'E') && (p[2] == 'T')) {
		goto HTTP_MATCH;
	}
	//POST
	if ((p[0] == 'P') && (p[1] == 'O') && (p[2] == 'S') && (p[3] == 'T')) {
		goto HTTP_MATCH;
	}
	//PUT
	if ((p[0] == 'P') && (p[1] == 'U') && (p[2] == 'T')) {
		goto HTTP_MATCH;
	}
	//DELETE
	if ((p[0] == 'D') && (p[1] == 'E') && (p[2] == 'L') && (p[3] == 'E') && (p[4] == 'T') && (p[5] == 'E')) {
		goto HTTP_MATCH;
	}
	//HEAD
	if ((p[0] == 'H') && (p[1] == 'E') && (p[2] == 'A') && (p[3] == 'D')) {
		goto HTTP_MATCH;
	}

	//no HTTP match
	//check if packet belong to an HTTP session
	struct Leaf * lookup_leaf = sessions.lookup(&key);
	if(lookup_leaf) {
		//send packet to userspace
		goto KEEP;
	}
	goto DROP;

	//keep the packet and send it to userspace returning -1
	HTTP_MATCH:
	//if not already present, insert into map <Key, Leaf>
	sessions.lookup_or_try_init(&key,&zero);

	//send packet to userspace returning -1
	KEEP:
	return -1;

	//drop the packet returning 0
	DROP:
	return 0;
}
```
http-parse-complete.py
```python
#!/usr/bin/python
#
# Bertrone Matteo - Polytechnic of Turin
# November 2015
#
# eBPF application that parses HTTP packets
# and extracts (and prints on screen) the URL
# contained in the GET/POST request.
#
# eBPF program http_filter is used as SOCKET_FILTER attached to eth0 interface.
# Only packets of type ip and tcp containing HTTP GET/POST are
# returned to userspace, others dropped
#
# Python script uses bcc BPF Compiler Collection by
# iovisor (https://github.com/iovisor/bcc) and prints on stdout the first
# line of the HTTP GET/POST request containing the url

from __future__ import print_function
from bcc import BPF
from sys import argv

import socket
import os
import binascii
import time

CLEANUP_N_PACKETS = 50     # cleanup every CLEANUP_N_PACKETS packets received
MAX_URL_STRING_LEN = 8192  # max url string len (usually 8K)
MAX_AGE_SECONDS = 30       # max age entry in bpf_sessions map


# print str until CR+LF
def printUntilCRLF(s):
    print(s.split(b'\r\n')[0].decode())


# cleanup function
def cleanup():
    # get current time in seconds
    current_time = int(time.time())
    # looking for leaf having:
    # timestap  == 0        --> update with current timestamp
    # AGE > MAX_AGE_SECONDS --> delete item
    for key, leaf in bpf_sessions.items():
        try:
            current_leaf = bpf_sessions[key]
            # set timestamp if timestamp == 0
            if (current_leaf.timestamp == 0):
                bpf_sessions[key] = bpf_sessions.Leaf(current_time)
            else:
                # delete older entries
                if (current_time - current_leaf.timestamp > MAX_AGE_SECONDS):
                    del bpf_sessions[key]
        except:
            print("cleanup exception.")
    return


# args
def usage():
    print("USAGE: %s [-i <if_name>]" % argv[0])
    print("")
    print("Try '%s -h' for more options." % argv[0])
    exit()


# help
def help():
    print("USAGE: %s [-i <if_name>]" % argv[0])
    print("")
    print("optional arguments:")
    print("   -h                       print this help")
    print("   -i if_name               select interface if_name. Default is eth0")
    print("")
    print("examples:")
    print("    http-parse              # bind socket to eth0")
    print("    http-parse -i wlan0     # bind socket to wlan0")
    exit()


# arguments
interface = "eth0"

if len(argv) == 2:
    if str(argv[1]) == '-h':
        help()
    else:
        usage()

if len(argv) == 3:
    if str(argv[1]) == '-i':
        interface = argv[2]
    else:
        usage()

if len(argv) > 3:
    usage()

print("binding socket to '%s'" % interface)

# initialize BPF - load source code from http-parse-complete.c
bpf = BPF(src_file="http-parse-complete.c", debug=0)

# load eBPF program http_filter of type SOCKET_FILTER into the kernel eBPF vm
# more info about eBPF program types
# http://man7.org/linux/man-pages/man2/bpf.2.html
function_http_filter = bpf.load_func("http_filter", BPF.SOCKET_FILTER)

# create raw socket, bind it to interface
# attach bpf program to socket created
BPF.attach_raw_socket(function_http_filter, interface)

# get file descriptor of the socket previously
# created inside BPF.attach_raw_socket
socket_fd = function_http_filter.sock

# create python socket object, from the file descriptor
sock = socket.fromfd(socket_fd, socket.PF_PACKET,
                     socket.SOCK_RAW, socket.IPPROTO_IP)
# set it as blocking socket
sock.setblocking(True)

# get pointer to bpf map of type hash
bpf_sessions = bpf.get_table("sessions")

# packets counter
packet_count = 0

# dictionary containing association
# <key(ipsrc,ipdst,portsrc,portdst),payload_string>.
# if url is not entirely contained in only one packet,
# save the firt part of it in this local dict
# when I find \r\n in a next pkt, append and print the whole url
local_dictionary = {}

while 1:
    # retrieve raw packet from socket
    packet_str = os.read(socket_fd, 4096)  # set packet length to max packet length on the interface
    packet_count += 1

    # DEBUG - print raw packet in hex format
    # packet_hex = binascii.hexlify(packet_str)
    # print ("%s" % packet_hex)

    # convert packet into bytearray
    packet_bytearray = bytearray(packet_str)

    # ethernet header length
    ETH_HLEN = 14

    # IP HEADER
    # https://tools.ietf.org/html/rfc791
    # 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |Version|  IHL  |Type of Service|          Total Length         |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    #
    # IHL : Internet Header Length is the length of the internet header
    # value to multiply * 4 byte
    # e.g. IHL = 5 ; IP Header Length = 5 * 4 byte = 20 byte
    #
    # Total length: This 16-bit field defines the entire packet size,
    # including header and data, in bytes.

    # calculate packet total length
    total_length = packet_bytearray[ETH_HLEN + 2]                 # load MSB
    total_length = total_length << 8                              # shift MSB
    total_length = total_length + packet_bytearray[ETH_HLEN + 3]  # add LSB

    # calculate ip header length
    ip_header_length = packet_bytearray[ETH_HLEN]     # load Byte
    ip_header_length = ip_header_length & 0x0F        # mask bits 0..3
    ip_header_length = ip_header_length << 2          # shift to obtain length

    # retrieve ip source/dest
    ip_src_str = packet_str[ETH_HLEN + 12: ETH_HLEN + 16]  # ip source offset 12..15
    ip_dst_str = packet_str[ETH_HLEN + 16:ETH_HLEN + 20]   # ip dest   offset 16..19

    ip_src = int(binascii.hexlify(ip_src_str), 16)
    ip_dst = int(binascii.hexlify(ip_dst_str), 16)

    # TCP HEADER
    # https://www.rfc-editor.org/rfc/rfc793.txt
    #  12              13              14              15
    #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |  Data |           |U|A|P|R|S|F|                               |
    # | Offset| Reserved  |R|C|S|S|Y|I|            Window             |
    # |       |           |G|K|H|T|N|N|                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    #
    # Data Offset: This indicates where the data begins.
    # The TCP header is an integral number of 32 bits long.
    # value to multiply * 4 byte
    # e.g. DataOffset = 5 ; TCP Header Length = 5 * 4 byte = 20 byte

    # calculate tcp header length
    tcp_header_length = packet_bytearray[ETH_HLEN + ip_header_length + 12]  # load Byte
    tcp_header_length = tcp_header_length & 0xF0    # mask bit 4..7
    tcp_header_length = tcp_header_length >> 2      # SHR 4 ; SHL 2 -> SHR 2

    # retrieve port source/dest
    port_src_str = packet_str[ETH_HLEN + ip_header_length:ETH_HLEN + ip_header_length + 2]
    port_dst_str = packet_str[ETH_HLEN + ip_header_length + 2:ETH_HLEN + ip_header_length + 4]

    port_src = int(binascii.hexlify(port_src_str), 16)
    port_dst = int(binascii.hexlify(port_dst_str), 16)

    # calculate payload offset
    payload_offset = ETH_HLEN + ip_header_length + tcp_header_length

    # payload_string contains only packet payload
    payload_string = packet_str[(payload_offset):(len(packet_bytearray))]
    # CR + LF (substring to find)
    crlf = b'\r\n'

    # current_Key contains ip source/dest and port source/map
    # useful for direct bpf_sessions map access
    current_Key = bpf_sessions.Key(ip_src, ip_dst, port_src, port_dst)

    # looking for HTTP GET/POST request
    if ((payload_string[:3] == b'GET') or (payload_string[:4] == b'POST')
            or (payload_string[:4] == b'HTTP') or (payload_string[:3] == b'PUT')
            or (payload_string[:6] == b'DELETE') or (payload_string[:4] == b'HEAD')):
        # match: HTTP GET/POST packet found
        if (crlf in payload_string):
            # url entirely contained in first packet -> print it all
            printUntilCRLF(payload_string)

            # delete current_Key from bpf_sessions, url already printed.
            # current session not useful anymore
            try:
                del bpf_sessions[current_Key]
            except:
                print("error during delete from bpf map ")
        else:
            # url NOT entirely contained in first packet
            # not found \r\n in payload.
            # save current part of the payload_string in dictionary
            # <key(ips,ipd,ports,portd),payload_string>
            local_dictionary[binascii.hexlify(current_Key)] = payload_string
    else:
        # NO match: HTTP GET/POST  NOT found

        # check if the packet belong to a session saved in bpf_sessions
        if (current_Key in bpf_sessions):
            # check id the packet belong to a session saved in local_dictionary
            # (local_dictionary maintains HTTP GET/POST url not
            # printed yet because split in N packets)
            if (binascii.hexlify(current_Key) in local_dictionary):
                # first part of the HTTP GET/POST url is already present in
                # local dictionary (prev_payload_string)
                prev_payload_string = local_dictionary[binascii.hexlify(current_Key)]
                # looking for CR+LF in current packet.
                if (crlf in payload_string):
                    # last packet. containing last part of HTTP GET/POST
                    # url split in N packets. Append current payload
                    prev_payload_string += payload_string
                    # print HTTP GET/POST url
                    printUntilCRLF(prev_payload_string)
                    # clean bpf_sessions & local_dictionary
                    try:
                        del bpf_sessions[current_Key]
                        del local_dictionary[binascii.hexlify(current_Key)]
                    except:
                        print("error deleting from map or dictionary")
                else:
                    # NOT last packet. Containing part of HTTP GET/POST url
                    # split in N packets.
                    # Append current payload
                    prev_payload_string += payload_string
                    # check if not size exceeding
                    # (usually HTTP GET/POST url < 8K )
                    if (len(prev_payload_string) > MAX_URL_STRING_LEN):
                        print("url too long")
                        try:
                            del bpf_sessions[current_Key]
                            del local_dictionary[binascii.hexlify(current_Key)]
                        except:
                            print("error deleting from map or dict")
                    # update dictionary
                    local_dictionary[binascii.hexlify(current_Key)] = prev_payload_string
            else:
                # first part of the HTTP GET/POST url is
                # NOT present in local dictionary
                # bpf_sessions contains invalid entry -> delete it
                try:
                    del bpf_sessions[current_Key]
                except:
                    print("error del bpf_session")

    # check if dirty entry are present in bpf_sessions
    if (((packet_count) % CLEANUP_N_PACKETS) == 0):
        cleanup()
```

## bpftrace

bpftrace 是一种用于 Linux eBPF 的高级跟踪语言，在新的 Linux内核（4.x）中可用。bpftrace 使用 LLVM 作为后端，将脚本编译为 eBPF 字节码，并利用 BCC 与 Linux eBPF 子系统交互，以及现有的 Linux 跟踪功能如内核动态跟踪（kprobes）、用户级动态跟踪（uprobes）和跟踪点（tracepoints）。bpftrace 语言的灵感来自 awk、C 以及 DTrace 和 SystemTap 等跟踪器。
<img src="/images/2023-04-01-ebpf-introduce/bpftrace.png" width="100%">
用于 Linux eBPF 的高级跟踪语言（基于 BCC 与 libbpf），项目源代码见 [iovisor
/
bpftrace
](https://github.com/iovisor/bpftrace)。以下示例使用 bpftrace 跟踪 TCP 生命周期。

tcplife.bt
```bash
#!/usr/bin/env bpftrace
/*
 * tcplife - Trace TCP session lifespans with connection details.
 *
 * See BPF Performance Tools, Chapter 10, for an explanation of this tool.
 *
 * Copyright (c) 2019 Brendan Gregg.
 * Licensed under the Apache License, Version 2.0 (the "License").
 * This was originally created for the BPF Performance Tools book
 * published by Addison Wesley. ISBN-13: 9780136554820
 * When copying or porting, include this comment.
 *
 * 17-Apr-2019  Brendan Gregg   Created this.
 */

#ifndef BPFTRACE_HAVE_BTF
#include <net/tcp_states.h>
#include <net/sock.h>
#include <linux/socket.h>
#include <linux/tcp.h>
#else
#include <sys/socket.h>
#endif

BEGIN
{
	printf("%-5s %-10s %-15s %-5s %-15s %-5s ", "PID", "COMM",
	    "LADDR", "LPORT", "RADDR", "RPORT");
	printf("%5s %5s %s\n", "TX_KB", "RX_KB", "MS");
}

kprobe:tcp_set_state
{
	$sk = (struct sock *)arg0;
	$newstate = arg1;

	/*
	 * This tool includes PID and comm context. From TCP this is best
	 * effort, and may be wrong in some situations. It does this:
	 * - record timestamp on any state < TCP_FIN_WAIT1
	 *	note some state transitions may not be present via this kprobe
	 * - cache task context on:
	 *	TCP_SYN_SENT: tracing from client
	 *	TCP_LAST_ACK: client-closed from server
	 * - do output on TCP_CLOSE:
	 *	fetch task context if cached, or use current task
	 */

	// record first timestamp seen for this socket
	if ($newstate < TCP_FIN_WAIT1 && @birth[$sk] == 0) {
		@birth[$sk] = nsecs;
	}

	// record PID & comm on SYN_SENT
	if ($newstate == TCP_SYN_SENT || $newstate == TCP_LAST_ACK) {
		@skpid[$sk] = pid;
		@skcomm[$sk] = comm;
	}

	// session ended: calculate lifespan and print
	if ($newstate == TCP_CLOSE && @birth[$sk]) {
		$delta_ms = (nsecs - @birth[$sk]) / 1e6;
		$lport = $sk->__sk_common.skc_num;
		$dport = $sk->__sk_common.skc_dport;
		$dport = bswap($dport);
		$tp = (struct tcp_sock *)$sk;
		$pid = @skpid[$sk];
		$comm = @skcomm[$sk];
		if ($comm == "") {
			// not cached, use current task
			$pid = pid;
			$comm = comm;
		}

		$family = $sk->__sk_common.skc_family;
		$saddr = ntop(0);
		$daddr = ntop(0);
		if ($family == AF_INET) {
			$saddr = ntop(AF_INET, $sk->__sk_common.skc_rcv_saddr);
			$daddr = ntop(AF_INET, $sk->__sk_common.skc_daddr);
		} else {
			// AF_INET6
			$saddr = ntop(AF_INET6,
			    $sk->__sk_common.skc_v6_rcv_saddr.in6_u.u6_addr8);
			$daddr = ntop(AF_INET6,
			    $sk->__sk_common.skc_v6_daddr.in6_u.u6_addr8);
		}
		printf("%-5d %-10.10s %-15s %-5d %-15s %-6d ", $pid,
		    $comm, $saddr, $lport, $daddr, $dport);
		printf("%5d %5d %d\n", $tp->bytes_acked / 1024,
		    $tp->bytes_received / 1024, $delta_ms);

		delete(@birth[$sk]);
		delete(@skpid[$sk]);
		delete(@skcomm[$sk]);
	}
}

END
{
	clear(@birth); clear(@skpid); clear(@skcomm);
}
```
tcplife_example.txt
```bash
Demonstrations of tcplife, the Linux bpftrace/eBPF version.

This tool shows the lifespan of TCP sessions, including througphut statistics,
and for efficiency only instruments TCP state changes (rather than all packets).
For example:

# ./tcplife.bt
PID   COMM       LADDR           LPORT RADDR           RPORT TX_KB RX_KB MS
20976 ssh        127.0.0.1       56766 127.0.0.1       22         6 10584 3059
20977 sshd       127.0.0.1       22    127.0.0.1       56766  10584     6 3059
14519 monitord   127.0.0.1       44832 127.0.0.1       44444      0     0 0
4496  Chrome_IOT 7f00:6:5ea7::a00:0 42846 0:0:bb01::      443        0     3 12441
4496  Chrome_IOT 7f00:6:5aa7::a00:0 42842 0:0:bb01::      443        0     3 12436
4496  Chrome_IOT 7f00:6:62a7::a00:0 42850 0:0:bb01::      443        0     3 12436
4496  Chrome_IOT 7f00:6:5ca7::a00:0 42844 0:0:bb01::      443        0     3 12442
4496  Chrome_IOT 7f00:6:60a7::a00:0 42848 0:0:bb01::      443        0     3 12436
4496  Chrome_IOT 10.0.0.65       33342 54.241.2.241    443        0     3 10717
4496  Chrome_IOT 10.0.0.65       33350 54.241.2.241    443        0     3 10711
4496  Chrome_IOT 10.0.0.65       33352 54.241.2.241    443        0     3 10712
14519 monitord   127.0.0.1       44832 127.0.0.1       44444      0     0 0

The output begins with a localhost ssh connection, so both endpoints can be
seen: the ssh process (PID 20976) which received 10584 Kbytes, and the sshd
process (PID 20977) which transmitted 10584 Kbytes. This session lasted 3059
milliseconds. Other sessions can also be seen, including IPv6 connections.
```

## eBPF Go库

eBPF Go 库提供了一个通用的 eBPF 库，它将获取 eBPF 字节码的过程与 eBPF 程序的加载和管理解耦。eBPF 程序通常是通过编写更高级别的语言创建的，然后使用 clang/LLVM 编译器编译为 eBPF字节码。
<img src="/images/2023-04-01-ebpf-introduce/eBPFGo库.png" width="100%">
ebpf go 是一个纯 go 库，用于读取、修改和加载 ebpf 程序，并将它们连接到 Linux 内核中的各种 hook 点。以下是一个示例，使用 kprobe 监听 sys_execve 事件，如下所示：

kprobe_percpu.c
```C
//go:build ignore

#include "common.h"

char __license[] SEC("license") = "Dual MIT/GPL";

struct bpf_map_def SEC("maps") kprobe_map = {
	.type        = BPF_MAP_TYPE_PERCPU_ARRAY,
	.key_size    = sizeof(u32),
	.value_size  = sizeof(u64),
	.max_entries = 1,
};

SEC("kprobe/sys_execve")
int kprobe_execve() {
	u32 key     = 0;
	u64 initval = 1, *valp;

	valp = bpf_map_lookup_elem(&kprobe_map, &key);
	if (!valp) {
		bpf_map_update_elem(&kprobe_map, &key, &initval, BPF_ANY);
		return 0;
	}
	__sync_fetch_and_add(valp, 1);

	return 0;
}
```
```C
// This program demonstrates attaching an eBPF program to a kernel symbol and
// using percpu map to collect data. The eBPF program will be attached to the
// start of the sys_execve kernel function and prints out the number of called
// times on each cpu every second.
package main

import (
	"log"
	"time"

	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/rlimit"
)

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go bpf kprobe_percpu.c -- -I../headers

const mapKey uint32 = 0

func main() {

	// Name of the kernel function to trace.
	fn := "sys_execve"

	// Allow the current process to lock memory for eBPF resources.
	if err := rlimit.RemoveMemlock(); err != nil {
		log.Fatal(err)
	}

	// Load pre-compiled programs and maps into the kernel.
	objs := bpfObjects{}
	if err := loadBpfObjects(&objs, nil); err != nil {
		log.Fatalf("loading objects: %v", err)
	}
	defer objs.Close()

	// Open a Kprobe at the entry point of the kernel function and attach the
	// pre-compiled program. Each time the kernel function enters, the program
	// will increment the execution counter by 1. The read loop below polls this
	// map value once per second.
	kp, err := link.Kprobe(fn, objs.KprobeExecve, nil)
	if err != nil {
		log.Fatalf("opening kprobe: %s", err)
	}
	defer kp.Close()

	// Read loop reporting the total amount of times the kernel
	// function was entered, once per second.
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	log.Println("Waiting for events..")

	for range ticker.C {
		var all_cpu_value []uint64
		if err := objs.KprobeMap.Lookup(mapKey, &all_cpu_value); err != nil {
			log.Fatalf("reading map: %v", err)
		}
		for cpuid, cpuvalue := range all_cpu_value {
			log.Printf("%s called %d times on CPU%v\n", fn, cpuvalue, cpuid)
		}
		log.Printf("\n")
	}
}
```

## libbpf C/C++ 库

libbpf 库是一个基于 C/C++ 的通用 eBPF 库，它有助于将 clang/LLVM 编译器生成的 eBPF 对象文件加载到内核中，并且通常通过为应用程序提供易于使用的库 API 来抽象与 BPF 系统调用的交互。
<img src="/images/2023-04-01-ebpf-introduce/C++库.png" width="100%">
libbpf 支持构建启用 BPF CO-RE 的应用程序，与 BCC 相比，这些应用程序不需要将 Clang/LLVM 运行时部署到目标服务器，也不依赖于可用的内核开发头。不过，它确实依赖于使用 BTF 类型信息构建的内核，一些主要的 Linux 发行版已经内置了内核 BTF。代码源代码可参见 [libbpf
/
libbpf](https://github.com/libbpf/libbpf)，以下是一个参考示例：   

uprobe.c
```C
// SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
/* Copyright (c) 2020 Facebook */
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/resource.h>
#include <bpf/libbpf.h>
#include "uprobe.skel.h"

static int libbpf_print_fn(enum libbpf_print_level level, const char *format, va_list args)
{
	return vfprintf(stderr, format, args);
}

/* It's a global function to make sure compiler doesn't inline it. */
int uprobed_add(int a, int b)
{
	return a + b;
}

int uprobed_sub(int a, int b)
{
	return a - b;
}

int main(int argc, char **argv)
{
	struct uprobe_bpf *skel;
	int err, i;
	LIBBPF_OPTS(bpf_uprobe_opts, uprobe_opts);

	/* Set up libbpf errors and debug info callback */
	libbpf_set_print(libbpf_print_fn);

	/* Load and verify BPF application */
	skel = uprobe_bpf__open_and_load();
	if (!skel) {
		fprintf(stderr, "Failed to open and load BPF skeleton\n");
		return 1;
	}

	/* Attach tracepoint handler */
	uprobe_opts.func_name = "uprobed_add";
	uprobe_opts.retprobe = false;
	/* uprobe/uretprobe expects relative offset of the function to attach
	 * to. libbpf will automatically find the offset for us if we provide the
	 * function name. If the function name is not specified, libbpf will try
	 * to use the function offset instead.
	 */
	skel->links.uprobe_add = bpf_program__attach_uprobe_opts(skel->progs.uprobe_add,
								 0 /* self pid */, "/proc/self/exe",
								 0 /* offset for function */,
								 &uprobe_opts /* opts */);
	if (!skel->links.uprobe_add) {
		err = -errno;
		fprintf(stderr, "Failed to attach uprobe: %d\n", err);
		goto cleanup;
	}

	/* we can also attach uprobe/uretprobe to any existing or future
	 * processes that use the same binary executable; to do that we need
	 * to specify -1 as PID, as we do here
	 */
	uprobe_opts.func_name = "uprobed_add";
	uprobe_opts.retprobe = true;
	skel->links.uretprobe_add = bpf_program__attach_uprobe_opts(
		skel->progs.uretprobe_add, -1 /* self pid */, "/proc/self/exe",
		0 /* offset for function */, &uprobe_opts /* opts */);
	if (!skel->links.uretprobe_add) {
		err = -errno;
		fprintf(stderr, "Failed to attach uprobe: %d\n", err);
		goto cleanup;
	}

	/* Let libbpf perform auto-attach for uprobe_sub/uretprobe_sub
	 * NOTICE: we provide path and symbol info in SEC for BPF programs
	 */
	err = uprobe_bpf__attach(skel);
	if (err) {
		fprintf(stderr, "Failed to auto-attach BPF skeleton: %d\n", err);
		goto cleanup;
	}

	printf("Successfully started! Please run `sudo cat /sys/kernel/debug/tracing/trace_pipe` "
	       "to see output of the BPF programs.\n");

	for (i = 0;; i++) {
		/* trigger our BPF programs */
		fprintf(stderr, ".");
		uprobed_add(i, i + 1);
		uprobed_sub(i * i, i);
		sleep(1);
	}

cleanup:
	uprobe_bpf__destroy(skel);
	return -err;
}
```
进一步了解与学习 eBPF，如果你想了解更多关于 eBPF 的信息，可参见附录。

# 附录

1. 文档   
    * [BPF & XDP Reference Guide](https://docs.cilium.io/en/stable/bpf/), Cilium Documentation, Aug 2020
    * [BPF Documentation](https://www.kernel.org/doc/html/latest/bpf/index.html), BPF Documentation in the Linux Kernel
    * [BPF Design Q&A](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/bpf/bpf_design_QA.rst), FAQ for kernel-related eBPF questions

2. 教程   
    * [Learn eBPF Tracing: Tutorial and Examples](http://www.brendangregg.com/blog/2019-01-01/learn-ebpf-tracing.html), Brendan Gregg's Blog, Jan 2019
    * [XDP Hands-On Tutorials](https://github.com/xdp-project/xdp-tutorial), Various authors, 2019
    * [BCC, libbpf and BPF CO-RE Tutorials](https://facebookmicrosites.github.io/bpf/blog/), Facebook's BPF Blog, 2020

3. 纪要
    * 通用性
        * [eBPF and Kubernetes: Little Helper Minions for Scaling Microservices](https://www.youtube.com/watch?v=99jUcLt3rSk) ([Slides](https://kccnceu20.sched.com/event/ZemQ/ebpf-and-kubernetes-little-helper-minions-for-scaling-microservices-daniel-borkmann-cilium)), Daniel Borkmann, KubeCon EU, Aug 2020
        * [eBPF - Rethinking the Linux Kernel](https://www.infoq.com/presentations/facebook-google-bpf-linux-kernel/) ([Slides](https://docs.google.com/presentation/d/1AcB4x7JCWET0ysDr0gsX-EIdQSTyBtmi6OAW7bE0jm0/edit?pli=1#slide=id.g35f391192_00)), Thomas Graf, QCon London, April 2020
        * [BPF as a revolutionary technology for the container landscape](https://www.youtube.com/watch?v=U3PdyHlrG1o&t=7s) ([Slides](https://archive.fosdem.org/2020/schedule/event/containers_bpf/attachments/slides/4122/export/events/attachments/containers_bpf/slides/4122/BPF_as_a_revolutionary_technology_for_the_container_landscape.pdf)), Daniel Borkmann, FOSDEM, Feb 2020
        * [BPF at Facebook](https://www.youtube.com/watch?v=ZYBXZFKPS28), Alexei Starovoitov, Performance Summit, Dec 2019
        * [BPF: A New Type of Software](https://www.youtube.com/watch?t=8&v=7pmXdG8-7WU&feature=youtu.be) ([Slides](https://www.slideshare.net/brendangregg/um2019-bpf-a-new-type-of-software)), Brendan Gregg, Ubuntu Masters, Oct 2019
        * [The ubiquity but also the necessity of eBPF as a technology](https://www.youtube.com/watch?v=mFxs3VXABPU), David S. Miller, Kernel Recipes, Oct 2019

4. deep dive   
    * [BPF and Spectre: Mitigating transient execution attacks](https://www.youtube.com/watch?v=6N30Yp5f9c4) ([Slides](https://ebpf.io/summit-2021-slides/eBPF_Summit_2021-Keynote-Daniel_Borkmann-BPF_and_Spectre.pdf)) , Daniel Borkmann, eBPF Summit, Aug 2021
    * [BPF Internals](https://www.usenix.org/conference/lisa21/presentation/gregg-bpf) ([Slides](https://www.usenix.org/system/files/lisa21_slides_gregg_bpf.pdf)), Brendan Gregg, USENIX LISA, Jun 2021

5. Cilium
    * [Advanced BPF Kernel Features for the Container Age](https://www.youtube.com/watch?v=PJY-rN1EsVw) ([Slides](https://archive.fosdem.org/2021/schedule/event/containers_ebpf_kernel/attachments/slides/4358/export/events/attachments/containers_ebpf_kernel/slides/4358/Advanced_BPF_Kernel_Features_for_the_Container_Age_FOSDEM.pdf)), Daniel Borkmann, FOSDEM, Feb 2021
    * [Kubernetes Service Load-Balancing at Scale with BPF & XDP](https://www.youtube.com/watch?v=UkvxPyIJAko&t=21s) ([Slides](https://lpc.events/event/7/contributions/674/attachments/568/1002/plumbers_2020_cilium_load_balancer.pdf)), Daniel Borkmann & Martynas Pumputis, Linux Plumbers, Aug 2020
    * [Liberating Kubernetes from kube-proxy and iptables](https://www.youtube.com/watch?v=bIRwSIwNHC0) ([Slides](https://docs.google.com/presentation/d/1cZJ-pcwB9WG88wzhDm2jxQY4Sh8adYg0-N3qWQ8593I/edit#slide=id.g7055f48ba8_0_0)), Martynas Pumputis, KubeCon US 2019
    * [Understanding and Troubleshooting the eBPF Datapath in Cilium](https://www.youtube.com/watch?v=Kmm8Hl57WDU) ([Slides](https://static.sched.com/hosted_files/kccncna19/20/eBPF%20and%20the%20Cilium%20Datapath.pdf)), Nathan Sweet, KubeCon US 2019
    * [Transparent Chaos Testing with Envoy, Cilium and BPF](https://www.youtube.com/watch?v=gPvl2NDIWzY) ([Slides](https://static.sched.com/hosted_files/kccnceu19/54/Chaos%20Testing%20with%20Envoy%2C%20Cilium%20and%20eBPF.pdf)), Thomas Graf, KubeCon EU 2019
    * [Cilium - Bringing the BPF Revolution to Kubernetes Networking and Security](https://www.youtube.com/watch?v=QmmId1QEE5k) ([Slides](https://www.slideshare.net/ThomasGraf5/cilium-bringing-the-bpf-revolution-to-kubernetes-networking-and-security)), Thomas Graf, All Systems Go!, Berlin, Sep 2018
    * [How to Make Linux Microservice-Aware with eBPF](https://www.youtube.com/watch?v=_Iq1xxNZOAo) ([Slides](https://www.slideshare.net/InfoQ/how-to-make-linux-microserviceaware-with-cilium-and-ebpf)), Thomas Graf, QCon San Francisco, 2018
    * [Accelerating Envoy with the Linux Kernel](https://www.youtube.com/watch?v=ER9eIXL2_14), Thomas Graf, KubeCon EU 2018
    * [Cilium - Network and Application Security with BPF and XDP](https://www.youtube.com/watch?v=ilKlmTDdFgk) ([Slides](https://www.slideshare.net/ThomasGraf5/dockercon-2017-cilium-network-and-application-security-with-bpf-and-xdp)), Thomas Graf, DockerCon Austin, Apr 2017

6. Hubble
    * [Hubble - eBPF Based Observability for Kubernetes](https://static.sched.com/hosted_files/kccnceu20/1b/Aug19-Hubble-eBPF_Based_Observability_for_Kubernetes_Sebastian_Wicki.pdf), Sebastian Wicki, KubeCon EU, Aug 2020

7. 书籍
    * [Learning eBPF](https://isovalent.com/books/learning-ebpf/), Liz Rice, O'Reilly, 2023
    * [Security Observability with eBPF](https://isovalent.com/books/ebpf-security/), Natália Réka Ivánkó and Jed Salazar, O'Reilly, 2022
    * [What is eBPF?](https://isovalent.com/books/ebpf/), Liz Rice, O'Reilly, 2022
    * [Systems Performance: Enterprise and the Cloud, 2nd Edition](https://www.brendangregg.com/systems-performance-2nd-edition-book.html), Brendan Gregg, Addison-Wesley Professional Computing Series, 2020
    * [BPF Performance Tools](https://www.brendangregg.com/bpf-performance-tools-book.html), Brendan Gregg, Addison-Wesley Professional Computing Series, Dec 2019
    * [Linux Observability with BPF](https://www.oreilly.com/library/view/linux-observability-with/9781492050193/), David Calavera, Lorenzo Fontana, O'Reilly, Nov 2019

8. 博客
    * [BPF for security - and chaos - in Kubernetes](https://lwn.net/Articles/790684/), Sean Kerner, LWN, Jun 2019
    * [Linux Technology for the New Year: eBPF](https://thenewstack.io/linux-technology-for-the-new-year-ebpf/), Joab Jackson, Dec 2018
    * [A thorough introduction to eBPF](https://lwn.net/Articles/740157/), Matt Fleming, LWN, Dec 2017
    * [Cilium, BPF and XDP](https://opensource.googleblog.com/2016/11/cilium-networking-and-security.html), Google Open Source Blog, Nov 2016
    * [Archive of various articles on BPF](https://lwn.net/Kernel/Index/#Berkeley_Packet_Filter), LWN, since Apr 2011
    * [Various articles on BPF by Cloudflare](https://blog.cloudflare.com/tag/ebpf/), Cloudflare, since March 2018
    * [Various articles on BPF by Facebook](https://facebookmicrosites.github.io/bpf/blog/), Facebook, since August 2018
