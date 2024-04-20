---
layout:     post
title:      "Linux 常见故障定位与性能分析操作命令"
subtitle:   ""
description: "Linux 命令主要用于系统故障定位和性能分析，包括监控系统运行状态、报告虚拟内存、CPU、网络、磁盘 IO 等各类资源的使用情况，以及查看进程状态、系统调用、网络流量、文件系统空间使用等信息，有助于及时发现并解决系统问题"
author: "陈谭军"
date: 2022-10-02
published: true
tags:
    - Linux
categories:
    - TECHNOLOGY
showtoc: true
---

# 序言

Linux 命令主要用于系统故障定位和性能分析，包括监控系统运行状态、报告虚拟内存、CPU、网络、磁盘 IO 等各类资源的使用情况，以及查看进程状态、系统调用、网络流量、文件系统空间使用等信息，有助于及时发现并解决系统问题。

以下是 Linux 常见故障定位与性能分析操作命令，包括：
1. top：监测系统运行状态，包括CPU使用率、内存使用量、进程状态等。
1. vmstat：报告虚拟内存统计信息，包括交换、缓冲区、io、系统和CPU活动。
1. iostat：报告CPU统计信息和输入/输出统计信息。
1. netstat：显示网络状态信息，如网络连接、路由表、接口统计等。
1. dmesg：查看内核启动信息和硬件错误。
1. ps：查看当前进程状态。
1. lsof：列出打开的文件描述符。
1. strace：跟踪系统调用和信号。
1. tcpdump：抓取并分析网络流量。
1. free：显示系统内存使用情况。
1. df：检查文件系统的磁盘空间占用情况。
1. du：估算和显示目录或文件的空间使用情况。
1. htop：比top更强大的系统监控工具，可以更直观地显示各种状态。
1. sar：收集并报告系统活动信息。
1. uptime：显示系统运行时间和负载。
1. nmon：综合性能监控工具，包括CPU、内存、网络、磁盘、文件系统、NFS等。
1. iftop：显示网络接口的带宽使用。
1. iotop：显示磁盘I/O使用情况。
1. mpstat：报告关于处理器的统计信息。
1. pidstat：报告关于进程的统计信息。

# iostat

iostat（输入/输出统计）是一个用于监控系统输入/输出设备活动负载并显示设备利用率的系统监视工具。可以帮助系统管理员找出性能瓶颈的存在。iostat 提供了关于 cpu 利用率和磁盘 I/O 统计的报告，包括磁盘吞吐量、读写速度、平均服务时间等信息。
```bash
root@instance-7codjqds:~# iostat
Linux 5.15.0-72-generic (instance-7codjqds)     01/29/24        _x86_64_        (2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           0.64    0.09    0.65    0.37    0.00   98.24

Device             tps    kB_read/s    kB_wrtn/s    kB_dscd/s    kB_read    kB_wrtn    kB_dscd
loop0             0.01         0.23         0.00         0.00       1263          0          0
loop1             0.05         0.44         0.00         0.00       2467          0          0
loop2             0.02         0.23         0.00         0.00       1297          0          0
loop3             0.01         0.09         0.00         0.00        527          0          0
loop4             0.58        25.45         0.00         0.00     142821          0          0
loop5             0.00         0.00         0.00         0.00         28          0          0
vda              17.44       189.56      1223.13         0.00    1063864    6864644          0
```
* avg-cpu: 这部分是关于CPU使用的统计数据。
  * %user: 用户空间程序占用的CPU百分比。
  * %nice: 用于nice操作的用户空间程序占用的CPU百分比。
  * %system: 内核空间程序占用的CPU百分比。
  * %iowait: CPU等待I/O完成的时间百分比。
  * %steal: 虚拟环境中等待虚拟CPU的时间百分比。
  * %idle: CPU空闲的时间百分比。
* Device: 这部分是关于磁盘I/O的统计数据。
  * tps: 每秒的传输次数，显示设备每秒的I/O请求数量。
  * kB_read/s: 每秒读取的数据量（KB）。
  * kB_wrtn/s: 每秒写入的数据量（KB）。
  * kB_dscd/s: 每秒丢弃的数据量（KB）。
  * kB_read: 读取的总数据量（KB）。
  * kB_wrtn: 写入的总数据量（KB）。
  * kB_dscd: 丢弃的总数据量（KB）。
  
# strace

strace 是一个在 Linux 中用于诊断、调试和指导应用程序的强大工具。它提供了一种检查进程和系统调用的方式，包括如何执行、调试进程以及管理系统等方面。通过 strace，你可以监控和拦截系统调用和信号，这对于调试和分析软件的行为非常有用。例如，它可以让你看到一个程序为什么读写特定的文件，或者它为什么没有按期望的方式运行等。在使用 strace 时，你可以指定一个正在运行的进程 ID，或者一个新的程序来运行。然后 strace 将打印出所有的系统调用、接收和发送的信号等信息。

下面是一些主要的 strace 参数解析：
* -e：指定要跟踪的事件类型。可以指定多个事件类型，用逗号分隔。例如，-e trace=read,write 表示只跟踪读取和写入操作。
* -p：指定要跟踪的进程 ID。
* -s：设置最大输出大小。这个参数可以用来控制跟踪输出的文件大小，以避免生成过大的文件。
* -f：跟踪到子进程。这个参数会使得 strace 跟踪到所有子进程的创建和退出。
* -o：指定输出文件名。使用这个参数可以将跟踪输出写入文件，方便后续查看和分析。
* -t：在跟踪过程中显示时间戳。
* -p 和 -e 可以组合使用，用于指定要跟踪的特定进程或事件类型。
* -t 和 -f 可以同时使用，用于在跟踪过程中显示时间戳并跟踪到子进程。

strace 示例如下所示：
```bash
root@instance-frllxehj:~# strace  nginx -s 100 -f
execve("/usr/sbin/nginx", ["nginx", "-s", "20", "-f"], 0x7ffd4d636d68 /* 34 vars */) = 0
brk(NULL)                               = 0x562fa70f7000
arch_prctl(0x3001 /* ARCH_??? */, 0x7ffd36ca5a00) = -1 EINVAL (Invalid argument)
access("/etc/ld.so.preload", R_OK)      = -1 ENOENT (No such file or directory)
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
fstat(3, {st_mode=S_IFREG|0644, st_size=54454, ...}) = 0
mmap(NULL, 54454, PROT_READ, MAP_PRIVATE, 3, 0) = 0x7f3621481000
close(3)                                = 0
openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libdl.so.2", O_RDONLY|O_CLOEXEC) = 3
read(3, "\177ELF\2\1\1\0\0\0\0\0\0\0\0\0\3\0>\0\1\0\0\0 \22\0\0\0\0\0\0"..., 832) = 832
fstat(3, {st_mode=S_IFREG|0644, st_size=18848, ...}) = 0
mmap(NULL, 8192, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0x7f362147f000
mmap(NULL, 20752, PROT_READ, MAP_PRIVATE|MAP_DENYWRITE, 3, 0) = 0x7f3621479000
mmap(0x7f362147a000, 8192, PROT_READ|PROT_EXEC, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x1000) = 0x7f362147a000
fstat(3, {st_mode=S_IFREG|0755, st_size=2029592, ...}) = 0
pread64(3, "\6\0\0\0\4\0\0\0@\0\0\0\0\0\0\0@\0\0\0\0\0\0\0@\0\0\0\0\0\0\0"..., 784, 64) = 784
pread64(3, "\4\0\0\0\20\0\0\0\5\0\0\0GNU\0\2\0\0\300\4\0\0\0\3\0\0\0\0\0\0\0", 32, 848) = 32
pread64(3, "\4\0\0\0\24\0\0\0\3\0\0\0GNU\0\356\276]_K`\213\212S\354Dkc\230\33\272"..., 68, 880) = 68
rt_sigaction(SIGRTMIN, {sa_handler=0x7f362145cbf0, sa_mask=[], sa_flags=SA_RESTORER|SA_SIGINFO, sa_restorer=0x7f362146a420}, NULL, 8) = 0
rt_sigaction(SIGRT_1, {sa_handler=0x7f362145cc90, sa_mask=[], sa_flags=SA_RESTORER|SA_RESTART|SA_SIGINFO, sa_restorer=0x7f362146a420}, NULL, 8) = 0
rt_sigprocmask(SIG_UNBLOCK, [RTMIN RT_1], NULL, 8) = 0
prlimit64(0, RLIMIT_STACK, NULL, {rlim_cur=8192*1024, rlim_max=RLIM64_INFINITY}) = 0
brk(NULL)                               = 0x562fa70f7000
brk(0x562fa7118000)                     = 0x562fa7118000
write(2, "nginx: invalid option: \"-s 20\"\n", 31nginx: invalid option: "-s 20"
) = 31
exit_group(1)                           = ?
+++ exited with 1 +++
```

# dtrace

dtrace 是一个在 Unix-like 系统上使用的性能分析工具，用于监视系统调用、内存分配、文件访问等事件。它提供了一个强大的方式来跟踪应用程序的行为，并帮助开发者诊断和优化性能问题。
![](/images/2022-10-02-linux-command/1.png)

```bash
root@instance-frllxehj:~/tanjunchen# dtrace --help
Usage /usr/bin/dtrace [--help] [-h | -G] [-C [-I<Path>]] -s File.d [-o <File>]
Where -h builds a systemtap header file from the .d file
      -C when used with -h, also run cpp preprocessor
      -o specifies an explicit output file name,
         the default for -G is file.o and -h is file.h
      -I when running cpp pass through this -I include Path
      -s specifies the name of the .d input file
      -G builds a stub file.o from file.d,
         which is required by some packages that use dtrace.
```
SystemTap 启动比较缓慢，并且依赖于完整的调试符号表，如下所示：
![](/images/2022-10-02-linux-command/2.png)

总的来说，为了追踪内核或用户空间的事件，Dtrace 和 SystemTap 都会把用户传入的追踪处理函数（一般称为 Action），关联到被称为探针的检测点上。这些探针，实际上也就是各种动态追踪技术所依赖的事件源。

根据事件类型的不同，动态追踪所使用的事件源可以分为静态探针、动态探针以及硬件事件等三类，如下图所示：
![](/images/2022-10-02-linux-command/3.png)

硬件事件通常由性能监控计数器 PMC（Performance Monitoring Counter）产生，包括了各种硬件的性能情况，比如 CPU 的缓存、指令周期、分支预测等等。
静态探针，是指事先在代码中定义好，并编译到应用程序或者内核中的探针。这些探针只有在开启探测功能时，才会被执行到；未开启时并不会执行。常见的静态探针包括内核中的跟踪点（tracepoints）和 USDT（Userland Statically Defined Tracing）探针。
* 跟踪点（tracepoints），实际上就是在源码中插入的一些带有控制条件的探测点，这些探测点允许事后再添加处理函数。比如在内核中，最常见的静态跟踪方法就是 printk，即输出日志。Linux 内核定义了大量的跟踪点，可以通过内核编译选项，来开启或者关闭。
* USDT 探针，全称是用户级静态定义跟踪，需要在源码中插入 DTRACE_PROBE() 代码，并编译到应用程序中。不过，也有很多应用程序内置了 USDT 探针，比如MySQL、PostgreSQL 等。
动态探针，则是指没有事先在代码中定义，但却可以在运行时动态添加的探针，比如函数的调用和返回等。动态探针支持按需在内核或者应用程序中添加探测点，具有更高的灵活性。常见的动态探针有两种，即用于内核态的 kprobes 和用于用户态的 uprobes。
* kprobes 用来跟踪内核态的函数，包括用于函数调用的 kprobe 和用于函数返回的 kretprobe。
* uprobes 用来跟踪用户态的函数，包括用于函数调用的 uprobe 和用于函数返回的 uretprobe。
* kprobes 需要内核编译时开启 CONFIG_KPROBE_EVENTS；而 uprobes 则需要内核编译时开启 CONFIG_UPROBE_EVENTS。

# dmesg

dmesg 是 Linux 中的一个命令，它用于显示内核消息日志。内核消息日志包含了系统启动过程中发生的各种事件，如设备检测、驱动加载、系统调用等。这对于诊断系统问题、理解系统行为和调试驱动程序非常有用。

要查看内核消息日志，只需在终端中运行 dmesg 命令。这将显示从系统启动以来的所有内核消息。
```bash
root@instance-frllxehj:~/tanjunchen# dmesg | grep rdma
[    8.999152] systemd[1]: /etc/systemd/system/rdma.service:15: Unknown key name 'Default-Start' in section 'Unit', ignoring.
[    9.000360] systemd[1]: /etc/systemd/system/rdma.service:26: Unknown key name 'ExecStatus' in section 'Service', ignoring.
[    9.341073] systemd[1]: Starting rdma - configure rdma devices...
```

主要测试
1. 驱动调试：如果你正在开发或调试某个特定设备或驱动程序，dmesg 可以帮助你了解驱动程序加载和初始化的过程，以及设备检测和配置的情况。
2. 系统性能分析：通过查看内核消息日志，你可以了解系统资源的使用情况，如内存、CPU 和磁盘 I/O。这对于分析系统性能瓶颈和优化系统性能非常有用。
3. 故障排查：在系统出现故障时，dmesg 可以帮助你了解故障发生时的系统状态，从而帮助你诊断和解决问题。
4. 安全审计：在安全审计过程中，dmesg 可以用于检查潜在的安全漏洞或恶意行为。它可以帮助你了解系统在特定时间点的状态，并识别可能的问题。

# fsck

fsck 是 Linux 系统中用于文件系统一致性检查和修复的命令。它可以帮助你检查文件系统的错误，并尝试修复它们，以确保数据的安全性。

fsck 主要用于检查和修复文件系统错误，包括但不限于：
* 文件和目录损坏
* 文件系统元数据损坏（如 inode、超级块等）
* 磁盘空间问题
* 文件系统不匹配（例如，某些文件可能被意外截断或截尾）
* 其他与文件系统相关的错误

主要参数说明：
* -a 或 --automatic：自动修复所有发现的问题，不需要用户交互。这可能不适用于所有情况，因为它可能误修复问题。
* -r 或 --repair：修复发现的错误，无论是否严重。这是默认选项。
* -f 或 --force：强制执行检查和修复，即使某些错误无法修复。这可能会导致数据丢失。
* -y 或 --yes：在提示是否确认修复时自动选择 “yes”。这可以提高检查和修复过程的效率，但也可能导致误修复问题。
* -q 或 --quiet：仅显示进度信息，不显示详细输出。这对于快速检查很有用。
* -d 或 --diagnose：显示诊断信息，但不进行任何修复。这可能有助于确定错误的类型和位置。

# lsof

lsof 是 Linux 操作系统中的一个命令，用于列出当前系统中打开的所有文件和进程。它提供了一种查看当前系统打开的文件和进程列表的方法，对于调试和排查系统问题非常有用。
```bash
root@instance-frllxehj:~/tanjunchen# lsof -h
lsof 4.93.2
 latest revision: https://github.com/lsof-org/lsof
 latest FAQ: https://github.com/lsof-org/lsof/blob/master/00FAQ
 latest (non-formatted) man page: https://github.com/lsof-org/lsof/blob/master/Lsof.8
 usage: [-?abhKlnNoOPRtUvVX] [+|-c c] [+|-d s] [+D D] [+|-E] [+|-e s] [+|-f[gG]]
 [-F [f]] [-g [s]] [-i [i]] [+|-L [l]] [+m [m]] [+|-M] [-o [o]] [-p s]
 [+|-r [t]] [-s [p:s]] [-S [t]] [-T [t]] [-u s] [+|-w] [-x [fl]] [--] [names]
Defaults in parentheses; comma-separated set (s) items; dash-separated ranges.
  -?|-h list help          -a AND selections (OR)     -b avoid kernel blocks
  -c c  cmd c ^c /c/[bix]  +c w  COMMAND width (9)    +d s  dir s files
  -d s  select by FD set   +D D  dir D tree *SLOW?*   +|-e s  exempt s *RISKY*
  -i select IPv[46] files  -K [i] list|(i)gn tasKs    -l list UID numbers
  -n no host names         -N select NFS files        -o list file offset
  -O no overhead *RISKY*   -P no port names           -R list paRent PID
  -s list file size        -t terse listing           -T disable TCP/TPI info
  -U select Unix socket    -v list version info       -V verbose search
  +|-w  Warnings (+)       -X skip TCP&UDP* files     -Z Z  context [Z]
  -- end option scan     
  -E display endpoint info              +E display endpoint info and files
  +f|-f  +filesystem or -file names     +|-f[gG] flaGs 
  -F [f] select fields; -F? for help  
  +|-L [l] list (+) suppress (-) link counts < l (0 = all; default = 0)
                                        +m [m] use|create mount supplement
  +|-M   portMap registration (-)       -o o   o 0t offset digits (8)
  -p s   exclude(^)|select PIDs         -S [t] t second stat timeout (15)
  -T qs TCP/TPI Q,St (s) info
  -g [s] exclude(^)|select and print process group IDs
  -i i   select by IPv[46] address: [46][proto][@host|addr][:svc_list|port_list]
  +|-r [t[m<fmt>]] repeat every t seconds (15);  + until no files, - forever.
       An optional suffix to t is m<fmt>; m must separate t from <fmt> and
      <fmt> is an strftime(3) format for the marker line.
  -s p:s  exclude(^)|select protocol (p = TCP|UDP) states by name(s).
  -u s   exclude(^)|select login|UID set s
  -x [fl] cross over +d|+D File systems or symbolic Links
  names  select named files or files on named file systems
Anyone can list all files; /dev warnings disabled; kernel ID check disabled.
root@instance-frllxehj:~/tanjunchen# lsof -i:80
COMMAND     PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
nginx     50615     root    6u  IPv4 194487      0t0  TCP *:http (LISTEN)
nginx     50615     root    7u  IPv6 194488      0t0  TCP *:http (LISTEN)
nginx     50616 www-data    6u  IPv4 194487      0t0  TCP *:http (LISTEN)
nginx     50616 www-data    7u  IPv6 194488      0t0  TCP *:http (LISTEN)
nginx     50617 www-data    6u  IPv4 194487      0t0  TCP *:http (LISTEN)
nginx     50617 www-data    7u  IPv6 194488      0t0  TCP *:http (LISTEN)
```

功能：
* lsof可以帮助你了解当前系统中有哪些进程正在使用文件，以及这些文件被哪些进程打开。这对于排查系统问题、监视文件使用情况以及调试程序非常有用。
* 它还可以用于文件和进程的同步操作，例如在文件被写入后立即关闭相关进程，或者在进程结束前确保文件已被正确关闭。
* lsof还提供了一些高级功能，如过滤和排序结果，以及与数据库和其他工具的集成。

主要参数说明：
* -p：指定要查看的进程ID。
* -c：指定要监视的文件类型，如 “r”（只读）、“w”（写入）、“a”（附加）等。
* -n：指定要查找的文件名或文件路径，可以精确匹配或使用通配符进行模糊匹配。
* -w：以宽格式显示详细信息，以便于查看大型文件的内容。
* less或nl：对结果进行分页或排序。这对于显示大型文件非常有用。

# dstat

dstat 是一个用于监控系统性能和资源利用情况的开源命令行工具，它提供了大量统计信息和可视化图表，以便管理员和开发人员监视系统和应用程序的性能。

```bash
root@instance-frllxehj:~/tanjunchen# dstat
You did not select any stats, using -cdngy by default.
--total-cpu-usage-- -dsk/total- -net/total- ---paging-- ---system--
usr sys idl wai stl| read  writ| recv  send|  in   out | int   csw 
 15   1  83   0   0| 227k 1170k|   0     0 |   0     0 | 612   521 
  0   0 100   0   0|   0     0 | 450B  964B|   0     0 | 543   132 
  0   0  99   0   0|   0   180k| 396B  554B|   0     0 | 564   234 
  0   0 100   0   0|   0     0 | 438B  578B|   0     0 | 540   123
```

dstat 提供以下主要功能：
* 资源监控：它可以监测 CPU、内存、磁盘 I/O、网络等资源的利用率，帮助了解系统的性能状况。
* 自定义输出：可以使用 dstat 的许多选项来过滤和指定要监控的特定资源类型和指标。
* 可视化图表：dstat 可以将监控数据以图表的形式呈现，使结果更易于理解和分析。
* 实时更新：dstat 可以实时更新监控数据，以便能够实时监视系统性能的变化。
* 跨平台支持：dstat 可在多种操作系统上使用，包括 Linux、BSD 和 macOS 等。

主要参数说明：
* -c：显示 CPU 使用情况。
* -m：显示内存使用情况。
* -D：显示磁盘 I/O 使用情况。
* -n：显示网络使用情况。
* -a：显示附加统计信息，如交换空间使用情况等。
* -b：显示带宽统计信息（仅适用于网络和磁盘 I/O）。
* -p <PID>：仅显示指定进程的统计信息。
* -T <设备>：仅显示指定设备的统计信息（如网络接口）。
* -l：以列表形式显示统计信息，而不是图表形式。
* -u：显示用户进程的 CPU 使用情况。
* -r：以相对值显示资源使用情况（相对于系统资源限制）。
* --text：以文本形式显示结果，而不是图表形式。
* --csv：以 CSV 格式输出结果，方便数据导入和分析。

示例如下所示：
```bash
root@instance-frllxehj:~/tanjunchen# dstat -cmDdn
--total-cpu-usage-- ------memory-usage-----
usr sys idl wai stl| used  free  buff  cach
 15   1  83   0   0| 229M 1926M  118M 5408M

  0   0 100   0   0| 229M 1926M  118M 5408M
  0   0 100   0   0| 229M 1926M  118M 5408M
  0   0 100   0   0| 229M 1926M  118M 5408M
```

# iotop

iotop 是一个用于监控 Linux 系统上设备 I/O 使用情况的命令行工具。它可以帮助管理员和开发人员监视系统上各个进程的磁盘和网络 I/O 流量，以便了解系统的性能和资源利用情况。

```bash
Total DISK READ:         0.00 B/s | Total DISK WRITE:         0.00 B/s
Current DISK READ:       0.00 B/s | Current DISK WRITE:      47.92 K/s
    TID  PRIO  USER     DISK READ  DISK WRITE  SWAPIN     IO>    COMMAND                                                                                                              
  50615 be/4 root        0.00 B/s    0.00 B/s  ?unavailable?  nginx: master process /usr/sbin/nginx -g daemon on; master_process on;
```

iotop 提供以下主要功能：
* 实时监测：它可以实时显示系统上各个进程的磁盘和网络 I/O 流量，让您能够及时了解系统的性能和资源利用情况。
* 按需排序：您可以按照不同的排序方式（如进程 ID、进程名、I/O 流量等）来查看结果。
* 过滤选项：iotop 提供了多种过滤选项，例如只显示活动进程、只显示高 I/O 进程等。这些选项可以帮助您更快速地找到需要关注的进程。
* 交互式模式：在交互式模式下，iotop 会显示一个菜单，让您可以选择要查看的统计信息。

主要参数说明：
* -o：按照进程 ID 排序显示结果。
* -p <进程ID>：仅显示指定进程的磁盘 I/O 使用情况。
* -t：显示进程的详细信息，包括用户、终端、CPU 使用率等。
* -d <延迟时间>：设置更新频率（以秒为单位）。
* -u：显示用户名而不是用户 ID。
* --no-pager：不使用页面浏览器显示结果。
* --color：启用颜色输出（可选）。
