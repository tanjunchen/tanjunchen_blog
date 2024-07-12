---
layout:     post
title:      "监测 Linux 内存缺页中断事件"
subtitle:   "监测 Linux 内存缺页中断事件"
description: "监测 Linux 内存缺页中断事件"
author: "陈谭军"
date: 2024-05-02
published: true
tags:
    - kubernetes
    - eBPF
categories:
    - TECHNOLOGY
showtoc: true
---

# 内存缺页中断概念

内存缺页中断（page fault）是一种由于程序试图访问的内存页不在物理内存中而产生的一种中断。这通常发生在以下几种情况：
* 内存页在物理内存中不存在。当程序试图访问的内存页被交换（swapped）到硬盘上时，就会发生这种情况。在这种情况下，操作系统会将这个内存页从硬盘上交换回物理内存，然后让程序继续执行。
* 内存页存在，但是不在程序的地址空间中。当程序试图访问一个并未分配给它的内存地址时，就会发生这种情况。在这种情况下，操作系统通常会终止这个程序，因为这通常是程序的一个bug。
* 内存页存在，但是权限不匹配。当程序试图以一种并未被允许的方式（例如，写入一个只读的内存页）访问内存页时，就会发生这种情况。在这种情况下，操作系统通常会更改内存页的权限，或者终止这个程序。

总的来说，内存缺页中断是操作系统虚拟内存管理的一部分。通过内存缺页中断，操作系统可以在有限的物理内存中运行需要更多内存的程序，以及保护程序之间不会相互干扰。

# 内存缺页中断原因

在Linux系统中，产生内存缺页中断的原因主要有以下几种：
* 请求的页面不在内存中：Linux使用了虚拟内存机制，一部分内存数据会被交换到硬盘上，当程序试图访问的页面不在内存中，而在硬盘上时，就会触发缺页中断，此时，操作系统会从硬盘加载页面到内存中。
* 访问权限不符：当程序试图写入一个只读的内存页，或者试图访问一个没有访问权限的内存页时，也会触发缺页中断。这种情况下，Linux会根据具体情况，要么更改页面的访问权限，要么结束程序的运行。
* 地址未映射：当程序访问一个未被映射的内存地址时，也会触发缺页中断。这种情况通常是由于程序的bug，例如，使用了未初始化的指针。此时，Linux通常会结束程序的运行。
* 内存耗尽：当系统内存不足，无法分配新的内存页面时，也会触发缺页中断。在这种情况下，Linux会尝试释放一些不常用的内存页面，或者使用交换空间（swap space）来获取更多的内存。如果这些方法都无法解决问题，Linux可能会触发OOM（Out of Memory）机制，强制结束一些进程来释放内存。

以上这些情况都可能引发内存缺页中断，系统会根据具体情况进行处理。

# 内存缺页中断排查工具

在Linux系统中，可以使用以下工具来帮助排查是否存在内存缺页中断：
* vmstat：vmstat是一个系统报告虚拟内存统计信息的工具。其中si和so列表示每秒从磁盘调入和换出内存的数量，这可以用来观察是否存在频繁的缺页中断。
* sar：sar是一个系统性能工具，可以报告各种系统资源的使用情况。sar -B命令可以查看每秒发生的主存和交换空间的页面交换情况。
* top/htop：这两个命令行工具可以实时查看系统和进程的资源使用情况，包括内存使用量、CPU使用率等，也可以查看进程的缺页中断情况。
* perf：perf工具可以用来监控和分析系统和应用程序的性能，包括CPU使用情况、内存使用情况、缺页中断等。
* dstat：dstat是一个用来查看所有系统资源的实时统计信息的工具，它可以查看磁盘I/O、网络、CPU、内存等资源的使用情况。

```bash
root@instance-frllxehj:~# vmstat 1
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 0  0      0 3307124 691580 3891544    0    0     1     8    1    1  0  0 100  0  0
 0  0      0 3307148 691580 3891544    0    0     0     0  553  205  0  0 100  0  0
 0  0      0 3307148 691580 3891544    0    0     0     0  567  269  0  0 100  0  0
 0  0      0 3307084 691580 3891544    0    0     0     0  562  235  0  0 100  0  0
 
# Procs
# r: 正在运行和等待运行的进程数量。
# b: 处在不可中断睡眠状态的进程数量。

# Memory
# swpd: 使用的虚拟内存数量（以KB为单位）。
# free: 空闲的物理内存数量（以KB为单位）。
# buff: 用作缓冲的内存数量（以KB为单位）。
# cache: 用作缓存的内存数量（以KB为单位）。

# Swap
# si: 从磁盘换入内存的数量（以KB/s为单位）。
# so: 从内存换出到磁盘的数量（以KB/s为单位）。

# IO
# bi: 从块设备（如硬盘）读取的数据量（以块/秒为单位）。
# bo: 写入块设备的数据量（以块/秒为单位）。

# System
# in: 每秒的中断次数，包括时间中断。
# cs: 每秒的上下文切换次数。

# CPU
# us: 用户进程的CPU时间百分比，不包括优先级调整的那部分。
# sy: 内核进程的CPU时间百分比。
# id: 空闲时间百分比。
# wa: 等待IO的CPU时间百分比。
# st: 被虚拟机偷走的CPU时间百分比（如果存在）。

root@instance-frllxehj:~# sar -B 1
Linux 5.10.0-051000-generic (instance-frllxehj)         02/28/2024      _x86_64_        (2 CPU)

11:38:46 AM  pgpgin/s pgpgout/s   fault/s  majflt/s  pgfree/s pgscank/s pgscand/s pgsteal/s    %vmeff
11:38:47 AM      0.00     48.00    294.00      0.00    217.00      0.00      0.00      0.00      0.00
11:38:48 AM      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
11:38:49 AM      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00

# pgpgin/s: 每秒从磁盘读取到内存的页面数。这通常发生在进程尝试访问它们的私有内存区域中的页面，但是发现页面并不在内存中，因此需要从磁盘中读取。
# pgpgout/s: 每秒从内存写回到磁盘的页面数。这通常发生在系统需要释放内存空间时，会选择一些内存中的页面写回到磁盘。
# fault/s: 每秒发生的总页故障数。页故障发生在进程访问到一个并不在内存中的页面时。
# majflt/s: 每秒发生的主要页故障数。主要页故障发生在处理页面故障需要从磁盘中读取数据时。
# pgfree/s: 操作系统每秒释放的页面数。
# pgscank/s: 每秒由kswapd守护进程扫描的页面数。
# pgscand/s: 每秒由直接页面扫描回收器扫描的页面数。
# pgsteal/s: 每秒被成功回收的页面数。
# %vmeff: 显示了页面回收的效率百分比，计算公式为100*pgsteal/(pgscand+pgscank)。

root@instance-frllxehj:~# top
WARNING: perf not found for kernel 5.10.0-051000

top - 11:39:06 up 23 days, 25 min,  2 users,  load average: 0.00, 0.00, 0.00
Tasks: 423 total,   1 running, 422 sleeping,   0 stopped,   0 zombie
%Cpu(s):  0.2 us,  0.2 sy,  0.0 ni, 99.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :  6.9/7953.2   [|||||||                                                                                             ]
MiB Swap:  0.0/0.0      [                                                                                                    ]
    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND                                                                                                        
 817172 root      20   0       0      0      0 I   0.3   0.0   0:07.84 kworker/0:0-mm_percpu_wq                                                                                       
 839275 root      20   0   13916   8912   7456 S   0.3   0.1   0:00.04 sshd                                                                                                           
 840314 root      20   0   15216   4084   3284 R   0.3   0.1   0:00.01 top                                                                                                            
      1 root      20   0  103600  12780   8544 S   0.0   0.2   0:15.80 systemd                                                                                                        
      2 root      20   0       0      0      0 S   0.0   0.0   0:00.17 kthreadd                                                                                                       
      3 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 rcu_gp                                                                                                         
      4 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 rcu_par_gp                                                                                                     
      6 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 kworker/0:0H-kblockd                                                                                           
      9 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 mm_percpu_wq                                                                                                   
     10 root      20   0       0      0      0 S   0.0   0.0   0:01.01 ksoftirqd/0                                                                                                    
     11 root      20   0       0      0      0 I   0.0   0.0   0:21.87 rcu_sched                                                                                                      
     12 root      rt   0       0      0      0 S   0.0   0.0   0:01.07 migration/0            

# PID：进程标识符（Process ID），是一个唯一标识进程的数字。
# USER：运行该进程的用户的用户名。
# PR：进程的优先级。
# NI：进程的"nice"值。这是一个用户可以控制的值，用来调整进程的优先级。
# VIRT：进程使用的虚拟内存总量，单位是kb。
# RES：进程使用的、未被交换出去的物理内存大小，单位是kb。
# SHR：进程使用的共享内存大小，单位是kb。
# S：进程的状态。常见的状态有：S（休眠），R（运行），Z（僵尸进程），T（跟踪/停止进程），D（不可中断的睡眠状态）。
# %CPU：进程使用的CPU时间百分比。
# %MEM：进程使用的物理内存百分比。
# TIME+：进程使用的CPU时间总计，单位是秒。
# COMMAND：启动进程的命令行命令。
    
root@instance-frllxehj:~# dstat
You did not select any stats, using -cdngy by default.
--total-cpu-usage-- -dsk/total- -net/total- ---paging-- ---system--
usr sys idl wai stl| read  writ| recv  send|  in   out | int   csw 
  0   0 100   0   0|1240B   15k|   0     0 |   0     0 | 564   240 
  0   0 100   0   0|   0     0 | 288B  852B|   0     0 | 560   246 
  0   0 100   0   0|   0     0 | 330B  504B|   0     0 | 559   201 
  0   0 100   0   0|   0     0 | 552B  880B|   0     0 | 561   228 
  0   0 100   0   0|   0     0 | 222B  388B|   0     0 | 556   219
  
# –total-cpu-usage–：显示CPU的使用情况，包含用户空间使用量（usr），系统空间使用量（sys），空闲时间（idl），等待I/O的时间（wait），硬件中断（hiq）和软件中断（siq）。
# -dsk/total-：显示磁盘的使用情况，包含读取（read）和写入（writ）的数据量。
# -net/total-：显示网络的使用情况，包含接收（recv）和发送（send）的数据量。
# —paging–：显示页面交换情况，包含从磁盘读入（in）和写入到磁盘的页面（out）。
# —system–：显示系统级别的统计，包含中断（int）和上下文切换（csw）的次数。
```

# 内存缺页中断流程

本次流程分析以内核 5.10 版本为准，可参见[fault.c#L240](https://elixir.bootlin.com/linux/v5.10/source/arch/arm/mm/fault.c#L240) 。缺页异常处理首先是用do_page_fault()函数读取缺页的虚地址，如果没有找到则访问了非法虚地址，将会发出SIGSEGV信号终止当前进程。否则进行缺页类型检查，地址越界或者段错误同样终止此次进程。
do_page_fault 源码如下所示：
```bash
// 具体见 https://elixir.bootlin.com/linux/v5.10/source/arch/arm/mm/fault.c#L240
static int __kprobes
do_page_fault(unsigned long addr, unsigned int fsr, struct pt_regs *regs)
{
    // 入参：regs: 指向保存在堆栈中的寄存器；
    // code: 异常的错误码
	struct task_struct *tsk;
	struct mm_struct *mm;
	int sig, code;
	vm_fault_t fault;
	unsigned int flags = FAULT_FLAG_DEFAULT;

	if (kprobe_page_fault(regs, fsr))
		return 0;

	tsk = current;
	mm  = tsk->mm;

	/* Enable interrupts if they were enabled in the parent context. */
	if (interrupts_enabled(regs))
		local_irq_enable();

	/*
	 * If we're in an interrupt or have no user
	 * context, we must not take the fault..
	 */
    // 判断当前状态是否处于中断上下文或者禁止抢占，如果是跳转到no_context；
    // 如果当前进程没有mm，说明是一个内核线程，跳转到no_context；
	if (faulthandler_disabled() || !mm)
		goto no_context;

    
	if (user_mode(regs))
		flags |= FAULT_FLAG_USER;
	if ((fsr & FSR_WRITE) && !(fsr & FSR_CM))
		flags |= FAULT_FLAG_WRITE;

	perf_sw_event(PERF_COUNT_SW_PAGE_FAULTS, 1, regs, addr);

	/*
	 * As per x86, we may deadlock here.  However, since the kernel only
	 * validly references user space from well defined areas of the code,
	 * we can bug out early if this is from code which shouldn't.
	 */
	if (!mmap_read_trylock(mm)) {
        // 获取锁失败，如果在内核态且在exception table查询不到该地址，则跳转到no_context 
		if (!user_mode(regs) && !search_exception_tables(regs->ARM_pc))
			goto no_context;
retry:
        // 用户态则睡眠等待锁持有者释放锁
		mmap_read_lock(mm);
	} else {
		/*
		 * The above down_read_trylock() might have succeeded in
		 * which case, we'll have missed the might_sleep() from
		 * down_read()
		 */
		might_sleep();
#ifdef CONFIG_DEBUG_VM
		if (!user_mode(regs) &&
		    !search_exception_tables(regs->ARM_pc))
			goto no_context;
#endif
	}

	fault = __do_page_fault(mm, addr, fsr, flags, tsk, regs);

	/* If we need to retry but a fatal signal is pending, handle the
	 * signal first. We do not need to release the mmap_lock because
	 * it would already be released in __lock_page_or_retry in
	 * mm/filemap.c. */
	if (fault_signal_pending(fault, regs)) {
		if (!user_mode(regs))
			goto no_context;
		return 0;
	}

	if (!(fault & VM_FAULT_ERROR) && flags & FAULT_FLAG_ALLOW_RETRY) {
		if (fault & VM_FAULT_RETRY) {
			flags |= FAULT_FLAG_TRIED;
			goto retry;
		}
	}

	mmap_read_unlock(mm);

	/*
	 * Handle the "normal" case first - VM_FAULT_MAJOR
	 */
    // 如果没有返回(VM_FAULT_ERROR | VM_FAULT_BADMAP | VM_FAULT_BADACCESS)，则缺页中断处理完成
	if (likely(!(fault & (VM_FAULT_ERROR | VM_FAULT_BADMAP | VM_FAULT_BADACCESS))))
		return 0;

	/*
	 * If we are in kernel mode at this point, we
	 * have no context to handle this fault with.
	 */
	if (!user_mode(regs))
		goto no_context;

	if (fault & VM_FAULT_OOM) {
        // 如果错误类型为OOM，则当前系统无足够内存，触发OOM机制
		/*
		 * We ran out of memory, call the OOM killer, and return to
		 * userspace (which will retry the fault, or kill us if we
		 * got oom-killed)
		 */
		pagefault_out_of_memory();
		return 0;
	}

	if (fault & VM_FAULT_SIGBUS) {
		/*
		 * We had some memory, but were unable to
		 * successfully fix up this page fault.
		 */
		sig = SIGBUS;
		code = BUS_ADRERR;
	} else {
		/*
		 * Something tried to access memory that
		 * isn't in our memory map..
		 */
		sig = SIGSEGV;
		code = fault == VM_FAULT_BADACCESS ?
			SEGV_ACCERR : SEGV_MAPERR;
	}
    // 给用户进程发送信号，错误内核无法妥善处理
	__do_user_fault(addr, fsr, sig, code, regs);
	return 0;

no_context:
    // 错误发生在内核态；发送oops错误
	__do_kernel_fault(mm, addr, fsr, regs);
	return 0;
}
#else					/* CONFIG_MMU */
static int
do_page_fault(unsigned long addr, unsigned int fsr, struct pt_regs *regs)
{
	return 0;
}
#endif					/* CONFIG_MMU */
```

__do_page_fault 处理页面异常具体函数，处理页错误，源码如下所示：
* 通过find_vma查找虚拟地址addr后的最近vma，如果没找到，则方位地址错误，因为它不在所分配的任何一个vma线性区；
* 如果找到vma，但addr并未落入这个区间，则可能是栈中vma；
* 经检查一切正常后，调用handle_mm_fault分配物理页框
* 异常情况：VM_FAULT_BADACCESS，严重错误，内核会直接kill该进程；

```bash
static vm_fault_t __kprobes
__do_page_fault(struct mm_struct *mm, unsigned long addr, unsigned int fsr,
		unsigned int flags, struct task_struct *tsk,
		struct pt_regs *regs)
{
	struct vm_area_struct *vma;
	vm_fault_t fault;

    // 搜索出现异常的地址前向最近的的vma
	vma = find_vma(mm, addr);
	fault = VM_FAULT_BADMAP;
    // 如果vma为NULL，说明addr之后没有vma，所以这个addr是个错误地址
	if (unlikely(!vma))
		goto out;
    // 如果addr之后有vma，但不包含addr，不能断定addr是错误地址，还需检查
	if (unlikely(vma->vm_start > addr))
		goto check_stack;

	/*
	 * Ok, we have a good vm_area for this
	 * memory access, so we can handle it.
	 */
good_area:
	if (access_error(fsr, vma)) {
		fault = VM_FAULT_BADACCESS;
		goto out;
	}
    // 分配新页
	return handle_mm_fault(vma, addr & PAGE_MASK, flags, regs);

check_stack:
   	 // addr后面的vma的vm_flags含有VM_GROWSDOWN标志，说明这个vma属于栈的vma
	 // 即addr在栈中，有可能是栈空间不够时再进栈导致的访问错误
	 // 同时检查栈是否还能扩展，如果不能扩展则确认确实是栈溢出导致，即addr确实是栈中地址，不是非法地址
	 // 应进入缺页中断请求
	/* Don't allow expansion below FIRST_USER_ADDRESS */
	if (vma->vm_flags & VM_GROWSDOWN &&
	    addr >= FIRST_USER_ADDRESS && !expand_stack(vma, addr))
		goto good_area;
out:
	return fault;
}
```

如果虚存区访问权限与引起缺页异常访问类型匹配，引入handle_mm_fault()函数实现页面分配与交换，触发缺页异常的地址address分配各级的页目录，那么每个address就会拥有配对的pte， __handle_mm_fault核心处理函数。
* 如果被访问的页不在内存，那么内核就会分配一个新的页面并适当初始化即请求调页。
* 如果被访问的页在内存中但是被标记为可读，也就是已经被存放在一个页面中，那么内核就会分配一个新的页面，并将旧页面数据复制到新的页面即写时复制。

handle_mm_fault 源码如下所示：
```bash
/*
 * By the time we get here, we already hold the mm semaphore
 *
 * The mmap_lock may have been released depending on flags and our
 * return value.  See filemap_fault() and __lock_page_or_retry().
 */
// 为引发缺页的进程分配一个物理页框
vm_fault_t handle_mm_fault(struct vm_area_struct *vma, unsigned long address,
			   unsigned int flags, struct pt_regs *regs)
{
	vm_fault_t ret;

	__set_current_state(TASK_RUNNING);

	count_vm_event(PGFAULT);
	count_memcg_event_mm(vma->vm_mm, PGFAULT);

	/* do counter updates before entering really critical section. */
	check_sync_rss_stat(current);

    // /* 
	//  * 1. vma向下增长，且addr==vma->vm_start，则要向下扩展一页保护页
	//  * 2. vma向上增长，且addr==vma->end，则要向上扩展一页保护页
	//  */
	if (!arch_vma_access_permitted(vma, flags & FAULT_FLAG_WRITE,
					    flags & FAULT_FLAG_INSTRUCTION,
					    flags & FAULT_FLAG_REMOTE))
		return VM_FAULT_SIGSEGV;

	/*
	 * Enable the memcg OOM handling for faults triggered in user
	 * space.  Kernel faults are handled more gracefully.
	 */
	if (flags & FAULT_FLAG_USER)
		mem_cgroup_enter_user_fault();

    // 如果开启了巨页，则使用hugetlb_fault分配内存
	if (unlikely(is_vm_hugetlb_page(vma)))
		ret = hugetlb_fault(vma->vm_mm, vma, address, flags);
	else
		ret = __handle_mm_fault(vma, address, flags);

	if (flags & FAULT_FLAG_USER) {
		mem_cgroup_exit_user_fault();
		/*
		 * The task may have entered a memcg OOM situation but
		 * if the allocation error was handled gracefully (no
		 * VM_FAULT_OOM), there is no need to kill anything.
		 * Just clean up the OOM state peacefully.
		 */
		if (task_in_memcg_oom(current) && !(ret & VM_FAULT_OOM))
			mem_cgroup_oom_synchronize(false);
	}

	mm_account_fault(regs, address, flags, ret);

	return ret;
}
```

在__handle_mm_fault中依次查找或创建页表，直到pte项，最后调用handle_pte_fault来处理，__handle_mm_fault 源码如下所示：
```bash
/*
 * By the time we get here, we already hold the mm semaphore
 *
 * The mmap_lock may have been released depending on flags and our
 * return value.  See filemap_fault() and __lock_page_or_retry().
 */
static vm_fault_t __handle_mm_fault(struct vm_area_struct *vma,
		unsigned long address, unsigned int flags)
{
	struct vm_fault vmf = {
		.vma = vma,
		.address = address & PAGE_MASK,
		.flags = flags,
		.pgoff = linear_page_index(vma, address),
		.gfp_mask = __get_fault_gfp_mask(vma),
	};
	unsigned int dirty = flags & FAULT_FLAG_WRITE;
	struct mm_struct *mm = vma->vm_mm;
	pgd_t *pgd;
	p4d_t *p4d;
	vm_fault_t ret;

    // 获取addr对应在当前进程页表的PGD页面目录项
	pgd = pgd_offset(mm, address);
	p4d = p4d_alloc(mm, pgd, address);
	if (!p4d)
		return VM_FAULT_OOM;

	vmf.pud = pud_alloc(mm, p4d, address);
	if (!vmf.pud)
		return VM_FAULT_OOM;
retry_pud:
	if (pud_none(*vmf.pud) && __transparent_hugepage_enabled(vma)) {
		ret = create_huge_pud(&vmf);
		if (!(ret & VM_FAULT_FALLBACK))
			return ret;
	} else {
		pud_t orig_pud = *vmf.pud;

		barrier();
		if (pud_trans_huge(orig_pud) || pud_devmap(orig_pud)) {

			/* NUMA case for anonymous PUDs would go here */

			if (dirty && !pud_write(orig_pud)) {
				ret = wp_huge_pud(&vmf, orig_pud);
				if (!(ret & VM_FAULT_FALLBACK))
					return ret;
			} else {
				huge_pud_set_accessed(&vmf, orig_pud);
				return 0;
			}
		}
	}

    // 获取对应的PUD表项，如果PUD表项为空，则返回VM_FAULT_OOM错误
	vmf.pmd = pmd_alloc(mm, vmf.pud, address);
	if (!vmf.pmd)
		return VM_FAULT_OOM;

	/* Huge pud page fault raced with pmd_alloc? */
	if (pud_trans_unstable(vmf.pud))
		goto retry_pud;

	if (pmd_none(*vmf.pmd) && __transparent_hugepage_enabled(vma)) {
		ret = create_huge_pmd(&vmf);
		if (!(ret & VM_FAULT_FALLBACK))
			return ret;
	} else {
		pmd_t orig_pmd = *vmf.pmd;

		barrier();
		if (unlikely(is_swap_pmd(orig_pmd))) {
			VM_BUG_ON(thp_migration_supported() &&
					  !is_pmd_migration_entry(orig_pmd));
			if (is_pmd_migration_entry(orig_pmd))
				pmd_migration_entry_wait(mm, vmf.pmd);
			return 0;
		}
		if (pmd_trans_huge(orig_pmd) || pmd_devmap(orig_pmd)) {
			if (pmd_protnone(orig_pmd) && vma_is_accessible(vma))
				return do_huge_pmd_numa_page(&vmf, orig_pmd);

			if (dirty && !pmd_write(orig_pmd)) {
				ret = wp_huge_pmd(&vmf, orig_pmd);
				if (!(ret & VM_FAULT_FALLBACK))
					return ret;
			} else {
				huge_pmd_set_accessed(&vmf, orig_pmd);
				return 0;
			}
		}
	}

	return handle_pte_fault(&vmf);
}
```

handle_pte_fault 源码如下所示：
* 根据页表项pte所描述的物理页框是否在物理内存中，分为两大类，由pte_present(*pte)区分。
* 调页请求(物理页不存在)：分配一个页框，根据pte页表项是否为空分为两种情况：
  * pte为空：pte中尚未写入物理地址，文件映射缺页中断、匿名映射缺页中断。
  * pte不为空，但(PTE_VALID | PTE_PROT_NONE)未置位：相关物理地址已经被交换到外存。
* 写时复制(物理页存在)：被访问的页存在，但该页是只读，内核需要对该页进行写操作；则此时内核将这个已存在的只读页中数据复制到一个新页框中。

```bash
/*
 * These routines also need to handle stuff like marking pages dirty
 * and/or accessed for architectures that don't do it in hardware (most
 * RISC architectures).  The early dirtying is also good on the i386.
 *
 * There is also a hook called "update_mmu_cache()" that architectures
 * with external mmu caches can use to update those (ie the Sparc or
 * PowerPC hashed page tables that act as extended TLBs).
 *
 * We enter with non-exclusive mmap_lock (to exclude vma changes, but allow
 * concurrent faults).
 *
 * The mmap_lock may have been released depending on flags and our return value.
 * See filemap_fault() and __lock_page_or_retry().
 */
static vm_fault_t handle_pte_fault(struct vm_fault *vmf)
{
	pte_t entry;

	if (unlikely(pmd_none(*vmf->pmd))) {
		/*
		 * Leave __pte_alloc() until later: because vm_ops->fault may
		 * want to allocate huge page, and if we expose page table
		 * for an instant, it will be difficult to retract from
		 * concurrent faults and from rmap lookups.
		 */
		vmf->pte = NULL;
	} else {
		/* See comment in pte_alloc_one_map() */
		if (pmd_devmap_trans_unstable(vmf->pmd))
			return 0;
		/*
		 * A regular pmd is established and it can't morph into a huge
		 * pmd from under us anymore at this point because we hold the
		 * mmap_lock read mode and khugepaged takes it in write mode.
		 * So now it's safe to run pte_offset_map().
		 */
		vmf->pte = pte_offset_map(vmf->pmd, vmf->address);
		vmf->orig_pte = *vmf->pte;

		/*
		 * some architectures can have larger ptes than wordsize,
		 * e.g.ppc44x-defconfig has CONFIG_PTE_64BIT=y and
		 * CONFIG_32BIT=y, so READ_ONCE cannot guarantee atomic
		 * accesses.  The code below just needs a consistent view
		 * for the ifs and we later double check anyway with the
		 * ptl lock held. So here a barrier will do.
		 */
        
        // pte表项不同处理器可能会大于word size， 此时READ_ONCE和ACCESS_ONCE不保证访问原子性，因此需要内存屏障以保证正确读取了pte表项内容
        
		barrier();
        // 说明尚未写入任何物理地址 
		if (pte_none(vmf->orig_pte)) {
			pte_unmap(vmf->pte);
			vmf->pte = NULL;
		}
	}

	if (!vmf->pte) {
		if (vma_is_anonymous(vmf->vma))
            // 匿名映射缺页中断，最终会调用alloc_pages从伙伴系统分配页面
			return do_anonymous_page(vmf);
		else
            // 如果该vma定义了操作函数集合，说明是文件映射页面缺页中断，将调用do_fault分配物理页
			return do_fault(vmf);
	}
    
    // PTE_PRESENT没有置位，说明pte实际指向的物理地址不存在，可能是调页请求有两种情况：
	// 1. *pte为空；
	// 2. *pte不为空，但是(PTE_VALID | PTE_PROT_NONE)标志位未置位
	if (!pte_present(vmf->orig_pte))
		return do_swap_page(vmf);

    // 到这应该是写时复制触发的缺页中断；即被访问的页面不可写，有两种情况：
    // 1. 之前给vma映射的是零页(zero-pfn)
    // 2. 访问fork得到的进程空间(子进程、父进程共享父进程的内存，均为只读页)
	if (pte_protnone(vmf->orig_pte) && vma_is_accessible(vmf->vma))
		return do_numa_page(vmf);

	vmf->ptl = pte_lockptr(vmf->vma->vm_mm, vmf->pmd);
	spin_lock(vmf->ptl);
	entry = vmf->orig_pte;
	if (unlikely(!pte_same(*vmf->pte, entry))) {
		update_mmu_tlb(vmf->vma, vmf->address, vmf->pte);
		goto unlock;
	}
    // 写操作时发生的缺页异常
	if (vmf->flags & FAULT_FLAG_WRITE) {
        // 第二种情况：pte页表项标识不可写，引发COW
		if (!pte_write(entry))
            // 进行写时复制操作
			return do_wp_page(vmf);
        // vma映射的是zero-pfn，设置pte_dirty位，标识页内容已被修改
		entry = pte_mkdirty(entry);
	}
    // 设置访问位，通常是_PAGE_ACCESSD
	entry = pte_mkyoung(entry);
	if (ptep_set_access_flags(vmf->vma, vmf->address, vmf->pte, entry,
				vmf->flags & FAULT_FLAG_WRITE)) {
        // pte内容发生变化，需要把新的内容写入pte页表项中，并刷新TLB和cache 
		update_mmu_cache(vmf->vma, vmf->address, vmf->pte);
	} else {
		/* Skip spurious TLB flush for retried page fault */
		if (vmf->flags & FAULT_FLAG_TRIED)
			goto unlock;
		/*
		 * This is needed only for protection faults but the arch code
		 * is not yet telling us if this is a protection fault or not.
		 * This still avoids useless tlb flushes for .text page faults
		 * with threads.
		 */
		if (vmf->flags & FAULT_FLAG_WRITE)
			flush_tlb_fix_spurious_fault(vmf->vma, vmf->address);
	}
unlock:
	pte_unmap_unlock(vmf->pte, vmf->ptl);
	return 0;
}
```

文件映射缺页中断处理函数，do_fault 源码如下所示：
```bash
/*
 * We enter with non-exclusive mmap_lock (to exclude vma changes,
 * but allow concurrent faults).
 * The mmap_lock may have been released depending on flags and our
 * return value.  See filemap_fault() and __lock_page_or_retry().
 * If mmap_lock is released, vma may become invalid (for example
 * by other thread calling munmap()).
 */
static vm_fault_t do_fault(struct vm_fault *vmf)
{
	struct vm_area_struct *vma = vmf->vma;
	struct mm_struct *vm_mm = vma->vm_mm;
	vm_fault_t ret;

	/*
	 * The VMA was not fully populated on mmap() or missing VM_DONTEXPAND
	 */
	if (!vma->vm_ops->fault) {
		/*
		 * If we find a migration pmd entry or a none pmd entry, which
		 * should never happen, return SIGBUS
		 */
		if (unlikely(!pmd_present(*vmf->pmd)))
			ret = VM_FAULT_SIGBUS;
		else {
			vmf->pte = pte_offset_map_lock(vmf->vma->vm_mm,
						       vmf->pmd,
						       vmf->address,
						       &vmf->ptl);
			/*
			 * Make sure this is not a temporary clearing of pte
			 * by holding ptl and checking again. A R/M/W update
			 * of pte involves: take ptl, clearing the pte so that
			 * we don't have concurrent modification by hardware
			 * followed by an update.
			 */
			if (unlikely(pte_none(*vmf->pte)))
				ret = VM_FAULT_SIGBUS;
			else
				ret = VM_FAULT_NOPAGE;

			pte_unmap_unlock(vmf->pte, vmf->ptl);
		}
	} else if (!(vmf->flags & FAULT_FLAG_WRITE))
        // 如果为读中断
		ret = do_read_fault(vmf);
	else if (!(vma->vm_flags & VM_SHARED))
        // 没有定义VM_SHARED, 是一个私有映射且发生了写时复制
		ret = do_cow_fault(vmf);
	else
        // 共享映射中发生了缺页异常
		ret = do_shared_fault(vmf);

	/* preallocated pagetable is unused: free it */
	if (vmf->prealloc_pte) {
		pte_free(vm_mm, vmf->prealloc_pte);
		vmf->prealloc_pte = NULL;
	}
	return ret;
}
```

匿名页缺页中断，一般为malloc触发，do_anonymous_page 源码如下所示：
* 调用anon_vma_prepare()获取一个anon_vma结构，这个结构可能属于此vma，也可能属于此vma能够合并的前后一个vma。
* 通过伙伴系统分配一个页(在32位上，会优先从高端内存分配) 
* 根据vma默认页表项参数vm_page_prot创建一个页表项，这个页表项用于加入到address对应的页表中
* 调用page_add_new_anon_rmap()给此page添加一个反向映射
* 将页表项和页表还有此页进行关联，由于页表已经在调用前分配好页了，只需要将页表项与新匿名页进行关联，然后将设置好的页表项写入address在此页表中的偏移地址即可。
```bash
/*
 * We enter with non-exclusive mmap_lock (to exclude vma changes,
 * but allow concurrent faults), and pte mapped but not yet locked.
 * We return with mmap_lock still held, but pte unmapped and unlocked.
 */
static vm_fault_t do_anonymous_page(struct vm_fault *vmf)
{
	struct vm_area_struct *vma = vmf->vma;
	struct page *page;
	vm_fault_t ret = 0;
	pte_t entry;

	/* File mapping without ->vm_ops ? */
	if (vma->vm_flags & VM_SHARED)
		return VM_FAULT_SIGBUS;

	/*
	 * Use pte_alloc() instead of pte_alloc_map().  We can't run
	 * pte_offset_map() on pmds where a huge pmd might be created
	 * from a different thread.
	 *
	 * pte_alloc_map() is safe to use under mmap_write_lock(mm) or when
	 * parallel threads are excluded by other means.
	 *
	 * Here we only have mmap_read_lock(mm).
	 */
	if (pte_alloc(vma->vm_mm, vmf->pmd))
		return VM_FAULT_OOM;

	/* See the comment in pte_alloc_one_map() */
	if (unlikely(pmd_trans_unstable(vmf->pmd)))
		return 0;

	/* Use the zero-page for reads */
    // /* 
	// * 如果不是写操作且允许使用Zero page, 则把zero_pfn的页表条目赋给entry
   	// * 因为这里已经是缺页异常的请求调页的处理，又是读操作，所以肯定是本进程第一次访问这个页
	// * 所以这个页里面是什么内容无所谓，分配个默认全零页就好，进一步推迟物理页的分配，这就会让entry带着zero_pfn跳到标号setpte
	// */
	if (!(vmf->flags & FAULT_FLAG_WRITE) &&
			!mm_forbids_zeropage(vma->vm_mm)) {
		entry = pte_mkspecial(pfn_pte(my_zero_pfn(vmf->address),
						vma->vm_page_prot));
		vmf->pte = pte_offset_map_lock(vma->vm_mm, vmf->pmd,
				vmf->address, &vmf->ptl);
		if (!pte_none(*vmf->pte)) {
			update_mmu_tlb(vma, vmf->address, vmf->pte);
			goto unlock;
		}
		ret = check_stable_address_space(vma->vm_mm);
		if (ret)
			goto unlock;
		/* Deliver the page fault to userland, check inside PT lock */
		if (userfaultfd_missing(vma)) {
			pte_unmap_unlock(vmf->pte, vmf->ptl);
			return handle_userfault(vmf, VM_UFFD_MISSING);
		}
		goto setpte;
	}
    
    // 处理带FAULT_FLAG_WRITE写标志的缺页中断
    
	/* Allocate our own private page. */
    // /* 为vma准备反向映射条件 
    // * find_mergeable_anon_vma 检查此vma能与前后的vma进行合并吗，如果可以，则使用能够合并的那个vma的anon_vma，如果不能够合并，则申请一个空闲的anon_vma
    // * 新建一个 anon_vma_chain
    // * 将avc->anon_vma指向获得的vma，avc->vma指向vma，并把avc加入到vma的anon_vma_chain中
    // */
	if (unlikely(anon_vma_prepare(vma)))
		goto oom;
    // 调用伙伴系统分配一个可写的匿名页面
	page = alloc_zeroed_user_highpage_movable(vma, vmf->address);
	if (!page)
		goto oom;
    
	if (mem_cgroup_charge(page, vma->vm_mm, GFP_KERNEL))
		goto oom_free_page;
    // 更新memcg中的计数，如果超过了memcg中的限制值，则会把这个页释放掉，并返回VM_FAULT_OOM 
	cgroup_throttle_swaprate(page, GFP_KERNEL);

	/*
	 * The memory barrier inside __SetPageUptodate makes sure that
	 * preceding stores to the page contents become visible before
	 * the set_pte_at() write.
	 */
    // 调用内存屏障，设置page->flag中更新标志位PG_uptodate
	__SetPageUptodate(page);

    // 根据vma页参数及pages地址创建pte页表项
	entry = mk_pte(page, vma->vm_page_prot);
	entry = pte_sw_mkyoung(entry);
    // 如果vma区是可写的，则给页表项添加可写标志
	if (vma->vm_flags & VM_WRITE)
		entry = pte_mkwrite(pte_mkdirty(entry));

	vmf->pte = pte_offset_map_lock(vma->vm_mm, vmf->pmd, vmf->address,
			&vmf->ptl);
	if (!pte_none(*vmf->pte)) {
		update_mmu_cache(vma, vmf->address, vmf->pte);
		goto release;
	}

	ret = check_stable_address_space(vma->vm_mm);
	if (ret)
		goto release;

	/* Deliver the page fault to userland, check inside PT lock */
	if (userfaultfd_missing(vma)) {
		pte_unmap_unlock(vmf->pte, vmf->ptl);
        // 获取addr对应的pte页表项；由于要修改，所以要上锁，只读是不需要上锁的
		put_page(page);
		return handle_userfault(vmf, VM_UFFD_MISSING);
	}

    // 增加mm_struct中匿名页(MM_ANONPAGES)的统计计数
	inc_mm_counter_fast(vma->vm_mm, MM_ANONPAGES);
    // /* 对这个新页进行反向映射 
    // * 主要工作是:
    // * 设置此页的_mapcount = 0，说明此页正在使用，但是是非共享的(>0是共享)
    // * 统计:
    // * 设置page->mapping最低位为1
    // * page->mapping指向此vma->anon_vma
    // * page->index存放此page在vma中的第几页
    // */
	page_add_new_anon_rmap(page, vma, vmf->address, false);
    /* 把匿名页面添加到LRU链表中，在kswap内核模块会使用LRU链表 */
	lru_cache_add_inactive_or_unevictable(page, vma);
setpte:
    /* 将上面配置好的页表项写入页表 */
	set_pte_at(vma->vm_mm, vmf->address, vmf->pte, entry);

	/* No need to invalidate - it was non-present before */
    /* 让mmu更新页表项，应该会清除tlb */
	update_mmu_cache(vma, vmf->address, vmf->pte);
unlock:
	pte_unmap_unlock(vmf->pte, vmf->ptl);
	return ret;
release:
    // 取消此page在memcg中的计数
    // 将申请的页释放到每CPU页高速缓存中
	put_page(page);
	goto unlock;
oom_free_page:
	put_page(page);
oom:
	return VM_FAULT_OOM;
}
```

do_swap_page 源码如下所示：
* 先由pte得到swap entry,再得到page，再有pte以及pte entry添加到硬件pte页表。swap cache: 系统中有多少匿名页曾经被swap-out、现在又被swap-in并且swap-in之后页面中的内容一直没发生变化。
* 为了防止页面在swap in/out时，进程有同步问题；即在swap out操作时，进程访问了换出页面。
* 如果页面数据没有完全写入磁盘，page frame是在swap cache。
* 等数据完全写入磁盘后，且没有进程对page frame进行访问，则swap cache会释放page frame，将其交给buddy system。
* swap cache 只存在很短暂时间，page out完成后就删除。
* 曾经被swap out现在又被swap in的匿名页会在swap cache，知道页面中内容发生变化，或者原来用过的交换区空间被回收为止。
```bash
/*
 * We enter with non-exclusive mmap_lock (to exclude vma changes,
 * but allow concurrent faults), and pte mapped but not yet locked.
 * We return with pte unmapped and unlocked.
 *
 * We return with the mmap_lock locked or unlocked in the same cases
 * as does filemap_fault().
 */
vm_fault_t do_swap_page(struct vm_fault *vmf)
{
	struct vm_area_struct *vma = vmf->vma;
	struct page *page = NULL, *swapcache;
	swp_entry_t entry;
	pte_t pte;
	int locked;
	int exclusive = 0;
	vm_fault_t ret = 0;
	void *shadow = NULL;

	if (!pte_unmap_same(vma->vm_mm, vmf->pmd, vmf->pte, vmf->orig_pte))
		goto out;

    /* 根据pte来获取swap的entry, swap entry和pte有一个对应关系 */
	entry = pte_to_swp_entry(vmf->orig_pte);
	if (unlikely(non_swap_entry(entry))) {
		if (is_migration_entry(entry)) {
			migration_entry_wait(vma->vm_mm, vmf->pmd,
					     vmf->address);
		} else if (is_device_private_entry(entry)) {
			vmf->page = device_private_entry_to_page(entry);
			ret = vmf->page->pgmap->ops->migrate_to_ram(vmf);
		} else if (is_hwpoison_entry(entry)) {
			ret = VM_FAULT_HWPOISON;
		} else {
			print_bad_pte(vma, vmf->address, vmf->orig_pte, NULL);
			ret = VM_FAULT_SIGBUS;
		}
		goto out;
	}


	delayacct_set_flag(DELAYACCT_PF_SWAPIN);
    /* 在swapcache里面寻找entry对应的page */
	page = lookup_swap_cache(entry, vma, vmf->address);
	swapcache = page;

	if (!page) {
        /* 如果swapcache里面找不到就在swap area里面找 */
		struct swap_info_struct *si = swp_swap_info(entry);

		if (data_race(si->flags & SWP_SYNCHRONOUS_IO) &&
		    __swap_count(entry) == 1) {
			/* skip swapcache */
			page = alloc_page_vma(GFP_HIGHUSER_MOVABLE, vma,
							vmf->address);
			if (page) {
				int err;

				__SetPageLocked(page);
				__SetPageSwapBacked(page);
				set_page_private(page, entry.val);

				/* Tell memcg to use swap ownership records */
				SetPageSwapCache(page);
				err = mem_cgroup_charge(page, vma->vm_mm,
							GFP_KERNEL);
				ClearPageSwapCache(page);
				if (err) {
					ret = VM_FAULT_OOM;
					goto out_page;
				}

				shadow = get_shadow_from_swap_cache(entry);
				if (shadow)
					workingset_refault(page, shadow);

				lru_cache_add(page);
				swap_readpage(page, true);
			}
		} else {
			page = swapin_readahead(entry, GFP_HIGHUSER_MOVABLE,
						vmf);
			swapcache = page;
		}

		if (!page) {
			/*
			 * Back out if somebody else faulted in this pte
			 * while we released the pte lock.
			 */
			vmf->pte = pte_offset_map_lock(vma->vm_mm, vmf->pmd,
					vmf->address, &vmf->ptl);
			if (likely(pte_same(*vmf->pte, vmf->orig_pte)))
				ret = VM_FAULT_OOM;
			delayacct_clear_flag(DELAYACCT_PF_SWAPIN);
			goto unlock;
		}

		/* Had to read the page from swap area: Major fault */
		ret = VM_FAULT_MAJOR;
		count_vm_event(PGMAJFAULT);
		count_memcg_event_mm(vma->vm_mm, PGMAJFAULT);
	} else if (PageHWPoison(page)) {
		/*
		 * hwpoisoned dirty swapcache pages are kept for killing
		 * owner processes (which may be unknown at hwpoison time)
		 */
		ret = VM_FAULT_HWPOISON;
		delayacct_clear_flag(DELAYACCT_PF_SWAPIN);
		goto out_release;
	}

	locked = lock_page_or_retry(page, vma->vm_mm, vmf->flags);

	delayacct_clear_flag(DELAYACCT_PF_SWAPIN);
	if (!locked) {
		ret |= VM_FAULT_RETRY;
		goto out_release;
	}

	/*
	 * Make sure try_to_free_swap or reuse_swap_page or swapoff did not
	 * release the swapcache from under us.  The page pin, and pte_same
	 * test below, are not enough to exclude that.  Even if it is still
	 * swapcache, we need to check that the page's swap has not changed.
	 */
	if (unlikely((!PageSwapCache(page) ||
			page_private(page) != entry.val)) && swapcache)
		goto out_page;

	page = ksm_might_need_to_copy(page, vma, vmf->address);
	if (unlikely(!page)) {
		ret = VM_FAULT_OOM;
		page = swapcache;
		goto out_page;
	}

	cgroup_throttle_swaprate(page, GFP_KERNEL);

	/*
	 * Back out if somebody else already faulted in this pte.
	 */
	vmf->pte = pte_offset_map_lock(vma->vm_mm, vmf->pmd, vmf->address,
			&vmf->ptl);
	if (unlikely(!pte_same(*vmf->pte, vmf->orig_pte)))
		goto out_nomap;

	if (unlikely(!PageUptodate(page))) {
		ret = VM_FAULT_SIGBUS;
		goto out_nomap;
	}

	/*
	 * The page isn't present yet, go ahead with the fault.
	 *
	 * Be careful about the sequence of operations here.
	 * To get its accounting right, reuse_swap_page() must be called
	 * while the page is counted on swap but not yet in mapcount i.e.
	 * before page_add_anon_rmap() and swap_free(); try_to_free_swap()
	 * must be called after the swap_free(), or it will never succeed.
	 */
    /* anonpage数加1，匿名页从swap空间交换出来，所以加1 */
	inc_mm_counter_fast(vma->vm_mm, MM_ANONPAGES);
    /* swap page个数减1 */
	dec_mm_counter_fast(vma->vm_mm, MM_SWAPENTS);
    /* 由page和VMA属性创建一个新的pte */
	pte = mk_pte(page, vma->vm_page_prot);
	if ((vmf->flags & FAULT_FLAG_WRITE) && reuse_swap_page(page, NULL)) {
		pte = maybe_mkwrite(pte_mkdirty(pte), vma);
		vmf->flags &= ~FAULT_FLAG_WRITE;
		ret |= VM_FAULT_WRITE;
		exclusive = RMAP_EXCLUSIVE;
	}
	flush_icache_page(vma, page);
	if (pte_swp_soft_dirty(vmf->orig_pte))
		pte = pte_mksoft_dirty(pte);
	if (pte_swp_uffd_wp(vmf->orig_pte)) {
		pte = pte_mkuffd_wp(pte);
		pte = pte_wrprotect(pte);
	}
    /* 将新生成的PTE entry添加到硬件页表 */
	set_pte_at(vma->vm_mm, vmf->address, vmf->pte, pte);
	arch_do_swap_page(vma->vm_mm, vma, vmf->address, pte, vmf->orig_pte);
	vmf->orig_pte = pte;

	/* ksm created a completely new copy */
    /* 根据page是否为swapcache，如果是，则只为page创建rmap，如果不是则创建rmap还要将page添加到LRU链表 */
	if (unlikely(page != swapcache && swapcache)) {
		page_add_new_anon_rmap(page, vma, vmf->address, false);
		lru_cache_add_inactive_or_unevictable(page, vma);
	} else {
		do_page_add_anon_rmap(page, vma, vmf->address, exclusive);
	}

	swap_free(entry);
	if (mem_cgroup_swap_full(page) ||
	    (vma->vm_flags & VM_LOCKED) || PageMlocked(page))
		try_to_free_swap(page);
	unlock_page(page);
	if (page != swapcache && swapcache) {
		/*
		 * Hold the lock to avoid the swap entry to be reused
		 * until we take the PT lock for the pte_same() check
		 * (to avoid false positives from pte_same). For
		 * further safety release the lock after the swap_free
		 * so that the swap count won't change under a
		 * parallel locked swapcache.
		 */
		unlock_page(swapcache);
		put_page(swapcache);
	}

	if (vmf->flags & FAULT_FLAG_WRITE) {
		ret |= do_wp_page(vmf);
		if (ret & VM_FAULT_ERROR)
			ret &= VM_FAULT_ERROR;
		goto out;
	}

	/* No need to invalidate - it was non-present before */
	update_mmu_cache(vma, vmf->address, vmf->pte);
unlock:
	pte_unmap_unlock(vmf->pte, vmf->ptl);
out:
	return ret;
out_nomap:
	pte_unmap_unlock(vmf->pte, vmf->ptl);
out_page:
	unlock_page(page);
out_release:
	put_page(page);
	if (page != swapcache && swapcache) {
		unlock_page(swapcache);
		put_page(swapcache);
	}
	return ret;
}
```

写时复制，一般出现在fork后子进程修改内存数据，do_wp_page 源码如下所示：
```bash
/*
 * This routine handles present pages, when users try to write
 * to a shared page. It is done by copying the page to a new address
 * and decrementing the shared-page counter for the old page.
 *
 * Note that this routine assumes that the protection checks have been
 * done by the caller (the low-level page fault routine in most cases).
 * Thus we can safely just mark it writable once we've done any necessary
 * COW.
 *
 * We also mark the page dirty at this point even though the page will
 * change only once the write actually happens. This avoids a few races,
 * and potentially makes it more efficient.
 *
 * We enter with non-exclusive mmap_lock (to exclude vma changes,
 * but allow concurrent faults), with pte both mapped and locked.
 * We return with mmap_lock still held, but pte unmapped and unlocked.
 */
static vm_fault_t do_wp_page(struct vm_fault *vmf)
	__releases(vmf->ptl)
{
	struct vm_area_struct *vma = vmf->vma;

	if (userfaultfd_pte_wp(vma, *vmf->pte)) {
		pte_unmap_unlock(vmf->pte, vmf->ptl);
		return handle_userfault(vmf, VM_UFFD_WP);
	}

	vmf->page = vm_normal_page(vma, vmf->address, vmf->orig_pte);
	if (!vmf->page) {
		/*
		 * VM_MIXEDMAP !pfn_valid() case, or VM_SOFTDIRTY clear on a
		 * VM_PFNMAP VMA.
		 *
		 * We should not cow pages in a shared writeable mapping.
		 * Just mark the pages writable and/or call ops->pfn_mkwrite.
		 */
		if ((vma->vm_flags & (VM_WRITE|VM_SHARED)) ==
				     (VM_WRITE|VM_SHARED))
			return wp_pfn_shared(vmf);

		pte_unmap_unlock(vmf->pte, vmf->ptl);
		return wp_page_copy(vmf);
	}

	/*
	 * Take out anonymous pages first, anonymous shared vmas are
	 * not dirty accountable.
	 */
	if (PageAnon(vmf->page)) {
		struct page *page = vmf->page;

		/* PageKsm() doesn't necessarily raise the page refcount */
		if (PageKsm(page) || page_count(page) != 1)
			goto copy;
		if (!trylock_page(page))
			goto copy;
		if (PageKsm(page) || page_mapcount(page) != 1 || page_count(page) != 1) {
			unlock_page(page);
			goto copy;
		}
		/*
		 * Ok, we've got the only map reference, and the only
		 * page count reference, and the page is locked,
		 * it's dark out, and we're wearing sunglasses. Hit it.
		 */
		unlock_page(page);
		wp_page_reuse(vmf);
		return VM_FAULT_WRITE;
	} else if (unlikely((vma->vm_flags & (VM_WRITE|VM_SHARED)) ==
					(VM_WRITE|VM_SHARED))) {
		return wp_page_shared(vmf);
	}
copy:
	/*
	 * Ok, we need to copy. Oh, well..
	 */
	get_page(vmf->page);

	pte_unmap_unlock(vmf->pte, vmf->ptl);
	return wp_page_copy(vmf);
}
```

整体流程如下所示：

![](/images/2024-05-02-linux-page-fault/1.svg)


主要通过do_page_fault()函数读取缺页虚地址，调用handle_mm_fault()函数具体处理进程访问用户虚拟地址生成的页错误异常，当进程通过系统调用进入内核模式，系统调用传入用户空间的缓冲区，进程在内核模式下访问用户空间的缓冲区。如果页错误异常处理程序确认虚拟地址属于分配给进程的虚拟内存区域，并且虚拟内存区域授予触发页错误异常的访问权限，就会运行到函数handle_mm_fault，最终具体实现由handle_pte_fault函数完成。

# eBPF 排查缺页中断

```bash
root@instance-frllxehj:~# bpftrace -e 'kprobe:handle_mm_fault { printf("pid: %d, comm: %s called handle_mm_fault\n", pid, comm); }'
Attaching 1 probe...
pid: 855417, comm: bcm-si called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855416, comm: bpftrace called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
pid: 855417, comm: gpu.sh called handle_mm_fault
```

```bash
root@instance-frllxehj:~# bpftrace -e 'kretprobe:handle_mm_fault { printf("Return value: %d\n", retval); }'
Attaching 1 probe...
Return value: 0
Return value: 0
Return value: 0
Return value: 1032
Return value: 0
Return value: 0
Return value: 0
Return value: 1032
Return value: 0
Return value: 512
Return value: 512
Return value: 0
Return value: 256
Return value: 512
Return value: 256
Return value: 256
Return value: 0
Return value: 256
Return value: 256
Return value: 256
Return value: 256
```

# 参考

1. https://github.com/0voice/kernel_memory_management/tree/main
2. https://blog.csdn.net/weixin_48405654/article/details/134006072
