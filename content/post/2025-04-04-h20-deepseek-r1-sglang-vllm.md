---
layout:     post
title:      "单机H20(8*96GiB)部署满血DeepSeek-R1(fp8)验证过程"
subtitle:   "单机H20(8*96GiB)部署满血DeepSeek-R1(fp8)验证过程、vllm 验证过程、sglang 验证过程"
description: ""
author: "陈谭军"
date: 2025-04-04
published: true
tags:
    - AI
    - 大模型
    - DeepSeek
    - NVIDIA H20 性能测试
categories:
    - TECHNOLOGY
showtoc: true
---

# 环境信息

## 机器配置

```bash
OS：CentOS Linux release 7.6 (Final)
Kernel：4.19.0-1.0.0.9
驱动： Driver Version: 535.216.03   CUDA Version: 12.2
GPU：NVIDIA  H20
vLLM：https://docs.vllm.ai/en/stable/
Docker：v1.5.4
nvidia-container-runtime：1.0.2-dev
vllm 测试镜像：vllm/vllm-openai:v0.8.2
sglang 测试镜像：lmsysorg/sglang:ea52b45be1a7 
配置与模型根目录  /mnt/models
```

<span style="color:red">⚠️ 注意：模型文件可能分为多个部分，一定要验证所有文件的完整性，避免因文件损坏导致的启动失败</span>

## 下载权重 

从 [DeepSeek-R1](https://huggingface.co/deepseek-ai/DeepSeek-R1) 下载 DeepSeek-R1 FP8 模型文件；

# vllm 单机测试

## 启动环境

```bash
 docker run -itd --privileged     \
     --net=host                   \
     --cap-add=SYS_PTRACE \
     --security-opt seccomp=unconfined     \
     --tmpfs /dev/shm:rw,nosuid,nodev,exec,size=128g     \
     -v /ssd1/models:/mnt/models              \
     --gpus all \
     --name vllm-test          \
     --entrypoint "" \
     -w /workspace     \
     vllm/vllm-openai:v0.8.2 \
     /bin/bash
```

## 启动 deepseek r1 模型

<span style="color:red">注：如果机器开启ipv6双栈网络，强烈建议配置该参数；</span>
```bash
export VLLM_HOST_IP=$(hostname -I | awk '{print $1}')
export HOST_IP=$(hostname -I | awk '{print $1}')
```

```bash
docker exec -it vllm-test bash

export VLLM_HOST_IP=$(hostname -I | awk '{print $1}')
export HOST_IP=$(hostname -I | awk '{print $1}')


nohup python3 -m vllm.entrypoints.openai.api_server --model /mnt/models/DeepSeek-R1 --gpu-memory-utilization 0.95 --tensor-parallel-size 8 --host 0.0.0.0 --trust-remote-code --port 8000  --max_num_seqs 256  --max-num-batched-tokens 16384  --max_model_len 4096  --max_seq_len_to_capture 16384   --tokenizer-mode auto  --enable-chunked-prefill=False  --enable-reasoning --reasoning-parser deepseek_r1  --enforce-eager  > vllm-server.log 2>&1 & 
```

参数说明：
* --model 模型路径，加载 /workspace/DeepSeek-R1 目录下的模型。
* --host 0.0.0.0监听所有网络接口的请求（允许外部访问）。
* --port 服务端口号设为 8000。
* --tokenizer-mode auto 自动选择分词器模式（优先使用 HuggingFace 的 auto 配置）。
* --gpu-memory-utilization 0.90  GPU 显存利用率上限设为 90%（避免 OOM）。如果高并发服务运行异常，建议调低此值。
* --tensor-parallel-size 16  使用 16 路张量并行（需 GPU 数量支持，适合超大模型）。
* --enforce-eager  强制启用 PyTorch 的 eager 模式（可能牺牲性能以提升兼容性）。
* --max_num_seqs 256 单次批处理的最大序列数（并发请求数上限）。vLLM 会动态调整，一般默认值设置为256。
* --max-num-batched-tokens 16384 批处理的最大总 token 数（影响吞吐量）。最大输入长度要小于这个数值。
* --max_model_len 16384 模型支持的最大上下文长度（16K tokens）。
* --max_seq_len_to_capture 16384 捕获的序列最大长度（用于优化 CUDA 内核）。框架默认超参，当前版本需要与 max_model_len 保持一致。
* --enable-chunked-prefill=False 禁用分块预填充（可能减少延迟但增加显存压力）。
* --enable-reasoning 启用推理模式（需配合 --reasoning-parser）。
* --reasoning-parser deepseek_r1 指定推理解析器为 deepseek_r1（自定义逻辑）。
* --trust-remote-code 允许加载远程代码（如自定义模型或分词器）。

出现如下文字表示启动成功：
```bash
api_server.py:1028] Starting vLLM API server on http://0.0.0.0:8000
```

## 性能测试

参考官方 vLLM 链接：[vllm-benchmarks](https://github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_serving.py)

测试脚本如下所示：
```bash
#!/bin/bash

output_dir=$1

declare -A test_cases=(
     ["128 128"]="128"
     ["256 256"]="256"
)

numprt_values=(1 2 4 8 16 32 64 128 200 256 512 1024)

for case in "${!test_cases[@]}"; do
    IFS=' ' read inlen outlen <<< "${case}"
    for numprt in "${numprt_values[@]}"; do
        log_filename="${output_dir}/serving_benchmark_${numprt}_${inlen}_${outlen}.log"
        result_file="${output_dir}/serving_benchmark_${numprt}_${inlen}_${outlen}.json"
        python3 benchmark_serving.py \
            --host 0.0.0.0 \
            --port 8000 \
            --backend vllm \
            --model /mnt/models/DeepSeek-R1 \
            --dataset-name random \
            --num-prompts "$numprt" \
            --random-input-len "$inlen" \
            --save-result \
            --random-range-ratio 1.0 \
            --result-filename "$result_file" \
            --random-output-len "$outlen" > "$log_filename" 2>&1
        echo "Executed command for num-prompts=$numprt, inlen=$inlen, outlen=$outlen. Output saved to $log_filename"
    done
done
```

测试结果收集脚本如下所示：
```bash
import json
import os
import csv
import re
import argparse

#fieldnames = ["tp", "concurrency", "mean TTFT(ms)", "p90_tpot_ms", 
#              "output_throughput(tokens/s)", "total_throughput(tokens/s)", 
#              "mean TPOT(ms)", "mean e2e(ms)", "mean_input_len", "mean_output_len"]

fieldnames = ["concurrency", "mean TTFT(ms)", "input_throughput(tokens/s)", 
              "output_throughput(tokens/s)", "mean TPOT(ms)", "mean_input_len", 
              "mean_output_len"]


def main(args):
    data = []

    for _, _, files in os.walk(args.dir):
        for file in files:
            if file.endswith(".json"):
                # tp${TENSOR_PARALLEL}_CON${i}_in${INPUT_LENGTH}_out${OUTPUT_LENGTH}.json
                # pattern = r'tp(\d+)_CON(\d+)_in(\d+)_out(\d+)\.json'
                pattern = r'serving_benchmark_(\d+)_(\d+)_(\d+).json'
                # 使用正则表达式匹配文件名
                match = re.match(pattern, file)
                if match:
                    # tp = int(match.group(1))
                    # con = int(match.group(2))
                    # input_length = int(match.group(3))
                    # output_length = int(match.group(4))
                    con = int(match.group(1))
                    input_length = int(match.group(2))
                    output_length = int(match.group(3))
                else:
                    print("not match")

                with open(os.path.join(args.dir, file), 'r') as f:
                    result = json.load(f)
                    data.append(
                        {
                            # "tp": tp, 
                            "concurrency": con, 
                            "mean TTFT(ms)": result['mean_ttft_ms'],
                            # "p90_tpot_ms": result["p90_tpot_ms"],
                            "input_throughput(tokens/s)": result["input_throughput"],
                            "output_throughput(tokens/s)": result['output_throughput'],
                            # "total_throughput(tokens/s)": result["total_token_throughput"],
                            "mean TPOT(ms)": result['mean_tpot_ms'],
                            # "mean e2e(ms)": result['mean_e2el_ms'],
                            "mean_input_len": sum(result['input_lens']) / len(result['input_lens']),
                            "mean_output_len": sum(result['output_lens']) / len(result['output_lens'])
                        }
                    )

    with open(os.path.join(args.dir, 'summary.csv'), 'w') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, help="")

    args = parser.parse_args()
    main(args)
```

## 测试数据

| Concurrency | Mean TTFT (ms) | Input Throughput (tokens/s) | Output Throughput (tokens/s) | Mean TPOT (ms) | Mean Input Len | Mean Output Len |
|-------------|----------------|-----------------------------|------------------------------|----------------|----------------|-----------------|
| 1           | 377.24         | 8.97                        | 8.97                         | 110.40         | 256            | 256             |
| 1           | 137.49         | 9.04                        | 9.04                         | 110.35         | 128            | 128             |
| 2           | 220.46         | 17.19                       | 17.19                        | 115.10         | 128            | 128             |
| 2           | 209.63         | 17.37                       | 17.37                        | 114.58         | 256            | 256             |
| 4           | 577.66         | 34.55                       | 32.66                        | 114.34         | 256            | 242             |
| 4           | 273.70         | 34.37                       | 34.37                        | 114.89         | 128            | 128             |
| 8           | 541.72         | 69.82                       | 54.79                        | 113.49         | 256            | 200.88          |
| 8           | 283.15         | 69.96                       | 69.90                        | 112.99         | 128            | 127.88          |
| 16          | 311.16         | 136.80                      | 118.03                       | 115.77         | 128            | 110.44          |
| 16          | 804.60         | 137.17                      | 108.03                       | 116.83         | 256            | 201.63          |
| 32          | 1154.97        | 264.47                      | 223.66                       | 118.56         | 256            | 216.50          |
| 32          | 406.02         | 272.43                      | 259.52                       | 115.50         | 128            | 121.94          |
| 64          | 1037.10        | 490.31                      | 441.89                       | 120.80         | 256            | 230.72          |
| 64          | 638.28         | 533.76                      | 505.68                       | 116.10         | 128            | 121.27          |
| 128         | 12775.06       | 523.47                      | 467.29                       | 127.68         | 256            | 228.52          |
| 128         | 1691.78        | 535.46                      | 496.57                       | 123.48         | 128            | 118.70          |
| 200         | 27349.28       | 536.20                      | 471.17                       | 133.32         | 256            | 224.95          |
| 200         | 8098.16        | 750.38                      | 692.81                       | 125.01         | 128            | 118.18          |
| 256         | 10997.02       | 736.63                      | 675.69                       | 124.53         | 128            | 117.41          |
| 256         | 42065.50       | 508.52                      | 464.55                       | 137.75         | 256            | 233.87          |
| 512         | 95793.97       | 525.61                      | 471.70                       | 137.59         | 256            | 229.74          |
| 512         | 28965.09       | 787.83                      | 738.58                       | 127.15         | 128            | 120.00          |
| 1024        | 64294.62       | 863.69                      | 799.89                       | 130.09         | 128            | 118.54          |
| 1024        | 216813.43      | 541.80                      | 496.40                       | 136.48         | 256            | 234.55          |

## FAQ

使用 vllm/vllm-openai:v0.7.2 镜像，以下命令启动会失败，具体可参考 https://github.com/vllm-project/vllm/issues/13294 。
```bash
python3 -m vllm.entrypoints.openai.api_server --model /mnt/models/DeepSeek-R1 --gpu-memory-utilization 0.95 --tensor-parallel-size 8 --host 0.0.0.0 --trust-remote-code --port 8000  --max_num_seqs 256  --max-num-batched-tokens 16384  --max_model_len 4096  --max_seq_len_to_capture 16384   --tokenizer-mode auto  --enable-chunked-prefill=False  --enable-reasoning --reasoning-parser deepseek_r1  --enforce-eager 
```

```bash
WARNING 03-29 21：10：39 fused moe.py:806] Using default MoE config. Performance might be sub-optimal! Config file not found at /usr/local
11ib/python3.12/dist-packages/v1lm/model executor/layers/fused moe/configs/E=256,N=256,device name=NVIDIA H20,dtype=fp8 w8a8,block shape
=[128,128].json
(VllmMorkerProcess pid=518) WARNING 03-29 21：10：39 fused moe.py:806] Using default MoE config. Performance might be sub-optimal! Config
file not found at /usr/local/lib/python3.12/dist-packages/vllm/model executor/layers/fused moe/configs/E=256,N=256,device name=NVIDIA H2
0,dtype=fp8_w8a8,block_shape=[128,128].json
0,dtype=fp8 w8a8,block shape=[128,128].json
ERROR 03-29 21：10：47 engine. py: 389] NCCL Error 1： unhandled cuda error (run with NCCL_DEBUG=INFO for details)
ERROR 03-29 21：10：47 engine.py:389] Traceback (most recent call last):
ERROR 03-29 21： 10： 47 engine.py: 389]
499
File"/usr/local/lib/python3.12/dist-packages/vllm/engine/multiprocessing/engine.py",line 380，in
run mp engine
ERROR 03-29 21： 10：47 engine.py: 389
engine = MQLLMEngine.from_engine_args(engine_args=engine_args,
ERROR 03-29 21：10：47 engine.py: 389]
AAAAAAAAAAAAAAAAAAAAAAAAAAAAa
ERROR 03-29 21： 10： 47 engine.py: 389]
File "/usr/local/lib/python3.12/dist-packages/vllm/engine/multiprocessing/engine.py",line 123，in
from engine args
ERROR 03-29 21： 10： 47 engine.py: 389
return cls(ipc_path=ipc_path,
ERROR 03-29 21： 10：47 engine.py: 389
ERROR 03-29 21：10：47 engine.py: 389
File "/usr/local/lib/python3.12/dist-packages/vllm/engine/multiprocessing/engine.py", line 75， in
init
ERROR 03-29 21： 10： 47 engine.py: 389]
self.engine = LLMEngine(*args, **kwargs)
ERROR 03-29 21： 10： 47 engine.py: 389]
^^^^^^^^^^^^^^^^
^^^^^^
ERROR 03-29 21： 10：47 engine.py: 389
File "/usr/local/lib/python3.12/dist-packages/vllm/engine/llm_engine.py", line 276， in _init
ERROR 03-29 21： 10：47 engine.py: 389
self. _initialize_kv_caches()
ERROR 03-29 21：10：47 engine.py: 389
File "/usr/local/lib/python3.12/dist-packages/vllm/engine/llm_engine.py", line 416， in _initialize
kv caches
ERROR 03-29 21： 10： 47 engine.py: 389]
self.model executor.determine num available blocks())
```


# sglang 单机测试

## 启动环境

```bash
docker run -itd --privileged     \
     --net=host                   \
     --cap-add=SYS_PTRACE \
     --security-opt seccomp=unconfined     \
     --tmpfs /dev/shm:rw,nosuid,nodev,exec,size=128g     \
     -v /ssd1/models:/mnt/models            \
     --gpus all \
     --name sglang-test          \
     --entrypoint "" \
     -w /workspace     \
     lmsysorg/sglang:ea52b45be1a7  \
     /bin/bash

docker exec -it sglang-test bash
```


## 启动 deepseek r1 模型

```bash
nohup python3 -m sglang.launch_server \
    --model-path /mnt/models/DeepSeek-R1 \
    --host 0.0.0.0 \
    --port 8000 \
    --tensor-parallel-size 8 \
    --trust-remote-code \
    --tokenizer-mode auto \
    --mem-fraction-static 0.90 \
    --context-length  65536 \
    --quantization fp8  \
    --reasoning-parser deepseek-r1 \
    --chunked-prefill-size  4096 > sglang-server.log 2>&1 & 
```

出现如下文字表示启动成功：
```bash
Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

以下命令启动失败，需要单机H200或者H20（8*141GiB显存）机器才能运行DeepSeek-R1（fp8权重）。
```bash
python3 -m sglang.launch_server --model-path /mnt/models/DeepSeek-R1 --tp 8 --trust-remote-code --host 0.0.0.0 --port 8000
```

```bash
Loading safetensors checkpoint shards: 98% Completed
160/163[00:55<00:01, 2.90it/s]
Loading safetensors checkpoint shards: 99% Completed
161/163[00:55<00:00,2.93it/s]
Loading safetensors checkpoint shards: 99% Completed
162/163[00:55<00:00,2.97it/s]
Loading safetensors checkpoint shards: 100% Completed
163/163[00:56<00:00,2.94it/s]
Loading safetensors checkpoint shards: 100% Completed
163/163[00:56<00:00,2.91it/s]
[2025-03-29 11：31：03 TP5] Scheduler hit an exception: Traceback (most recent call last):
File"/sgl-workspace/sglang/python/sglang/srt/managers/scheduler.py",line 1748，in run_scheduler_process
scheduler = Scheduler(server_args, port_args, gpu_id, tp_rank, dp_rank)
File"/sgl-workspace/sglang/python/sglang/srt/managers/scheduler.py",line 218，in _init
self.tp_worker = TpWorkerClass(
File"/sgl-workspace/sglang/python/sglang/srt/managers/tp_worker_overlap_thread.py",line 63，in _init
self.worker = TpModelWorker（server_args， gpu_id， tp_rank， dp_rank， nccl_port）
File"/sgl-workspace/sglang/python/sglang/srt/managers/tp_worker.py",line 74，in_init_
self.model_runner = ModelRunner(
File"/sgl-workspace/sglang/python/sglang/srt/model_executor/model_runner.py",line 166， in_init_
self.initialize(min_per_gpu_memory)
File"/sgl-workspace/sglang/python/sglang/srt/model_executor/model_runner.py",line 199，in initialize
self.init_memory_pool(
File"/sgl-workspace/sglang/python/sglang/srt/model_executor/model_runner.py",line 715，in init_memory_pool
RuntimeError: Not enough memory. Please try to increase --mem-fraction-static.
```

## 性能测试

测试脚本：
```bash
#!/bin/bash

output_dir=$1

declare -A test_cases=(
    # 格式: "输入长度 输出长度 numprt"="描述"
    ["128 128 1"]="128"
    ["128 128 2"]="128"
    ["128 128 4"]="128"
    ["128 128 8"]="128"
    ["128 128 16"]="128"
    ["128 128 32"]="128"
    ["128 128 64"]="128"
    ["128 128 128"]="128"
    ["128 128 256"]="128"
    ["128 128 512"]="128"
    ["128 128 1024"]="128"

    ["256 256 1"]="256"
    ["256 256 2"]="256"
    ["256 256 4"]="256"
    ["256 256 8"]="256"
    ["256 256 16"]="256"
    ["256 256 32"]="256"
    ["256 256 64"]="256"
    ["256 256 128"]="256"
    ["256 256 256"]="256"
    ["256 256 512"]="256"
    ["256 256 1024"]="256"
)

random_range_ratios=(1.0)

# 循环遍历所有测试用例
for case in "${!test_cases[@]}"; do
    # 分割输入长度、输出长度和numprt
    IFS=' ' read inlen outlen numprt <<< "${case}"
    
    # 构建日志文件名和结果文件名
    result_file="${output_dir}/serving_benchmark_${numprt}_${inlen}_${outlen}.json"

     for ratio in "${random_range_ratios[@]}"
        do
            python3 -m sglang.bench_serving \
                --backend sglang \
                --dataset-name random \
                --dataset-path /mnt/models/sglang/ShareGPT_V3_unfiltered_cleaned_split.json \
                --model /mnt/models/DeepSeek-R1 \
                --random-input ${inlen} \
                --random-output ${outlen} \
                --random-range-ratio ${ratio} \
                --num-prompts ${numprt} \
                --host 0.0.0.0 \
                --port 8000 \
                --output-file "$result_file" \
                --max-concurrency ${numprt}
        done
        echo "Executed command for num-prompts=$numprt, inlen=$input_len, outlen=$output_len. Output saved to $result_file"

done
```

收集测试结果脚本：
```bash
import json
import os
import csv
import re
import argparse

#fieldnames = ["tp", "concurrency", "mean TTFT(ms)", "p90_tpot_ms", 
#              "output_throughput(tokens/s)", "total_throughput(tokens/s)", 
#              "mean TPOT(ms)", "mean e2e(ms)", "mean_input_len", "mean_output_len"]

fieldnames = ["concurrency", "mean TTFT(ms)", "input_throughput(tokens/s)", 
              "output_throughput(tokens/s)", "mean TPOT(ms)", "mean_input_len", 
              "mean_output_len"]


def main(args):
    data = []

    for _, _, files in os.walk(args.dir):
        for file in files:
            if file.endswith(".json"):
                # tp${TENSOR_PARALLEL}_CON${i}_in${INPUT_LENGTH}_out${OUTPUT_LENGTH}.json
                # pattern = r'tp(\d+)_CON(\d+)_in(\d+)_out(\d+)\.json'
                pattern = r'serving_benchmark_(\d+)_(\d+)_(\d+).json'
                # 使用正则表达式匹配文件名
                match = re.match(pattern, file)
                if match:
                    # tp = int(match.group(1))
                    # con = int(match.group(2))
                    # input_length = int(match.group(3))
                    # output_length = int(match.group(4))
                    con = int(match.group(1))
                    input_length = int(match.group(2))
                    output_length = int(match.group(3))
                else:
                    print("not match")

                with open(os.path.join(args.dir, file), 'r') as f:
                    result = json.load(f)
                    data.append(
                        {
                            # "tp": tp, 
                            "concurrency": con, 
                            "mean TTFT(ms)": result['mean_ttft_ms'],
                            # "p90_tpot_ms": result["p90_tpot_ms"],
                            "input_throughput(tokens/s)": result["input_throughput"],
                            "output_throughput(tokens/s)": result['output_throughput'],
                            # "total_throughput(tokens/s)": result["total_token_throughput"],
                            "mean TPOT(ms)": result['mean_tpot_ms'],
                            # "mean e2e(ms)": result['mean_e2el_ms'],
                            "mean_input_len": result['random_input_len'],
                            "mean_output_len": result['random_output_len']
                        }
                    )

    with open(os.path.join(args.dir, 'summary.csv'), 'w') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, help="")

    args = parser.parse_args()
    main(args)
```

## 测试数据

| Concurrency | Mean TTFT (ms) | Input Throughput (tokens/s) | Output Throughput (tokens/s) | Mean TPOT (ms) | Mean Input Len | Mean Output Len |
|-------------|------------|------------|-------------|----------|----------|-----------|
| 1           | 194.20     | 23.23      | 23.23       | 42.24    | 256      | 256       |
| 1           | 182.48     | 23.02      | 23.02       | 42.00    | 128      | 128       |
| 2           | 224.36     | 49.47      | 49.47       | 39.55    | 256      | 256       |
| 2           | 403.36     | 47.01      | 47.01       | 39.36    | 128      | 128       |
| 4           | 522.17     | 90.16      | 90.16       | 42.32    | 256      | 256       |
| 4           | 337.92     | 88.69      | 88.69       | 42.43    | 128      | 128       |
| 8           | 454.64     | 141.60     | 141.60      | 52.94    | 128      | 128       |
| 8           | 556.54     | 143.92     | 143.92      | 53.36    | 256      | 256       |
| 16          | 798.92     | 228.58     | 228.58      | 66.88    | 256      | 256       |
| 16          | 761.36     | 221.29     | 221.29      | 66.34    | 128      | 128       |
| 32          | 1413.67    | 356.98     | 356.98      | 84.12    | 256      | 256       |
| 32          | 2746.37    | 298.55     | 298.55      | 85.71    | 128      | 128       |
| 64          | 2194.33    | 525.62     | 525.62      | 104.64   | 128      | 128       |
| 64          | 2066.74    | 554.94     | 554.94      | 107.27   | 256      | 256       |
| 128         | 1947.21    | 905.80     | 905.80      | 126.22   | 128      | 128       |
| 128         | 4998.13    | 755.78     | 755.78      | 134.56   | 256      | 256       |
| 256         | 22308.28   | 726.58     | 726.58      | 139.63   | 256      | 256       |
| 256         | 3240.90    | 1126.60    | 1126.60     | 182.61   | 128      | 128       |
| 512         | 60348.03   | 778.92     | 778.92      | 146.90   | 256      | 256       |
| 512         | 17057.59   | 1017.13    | 1017.13     | 201.92   | 128      | 128       |
| 1024        | 43769.94   | 1100.93    | 1100.93     | 209.22   | 128      | 128       |
| 1024        | 135037.16  | 813.92     | 813.92      | 175.95   | 256      | 256       |

# 总结

## 对比分析

* 吞吐量（Throughput）
  * SGLang 显著更高：
    * 最高达1100 tokens/s（vLLM 仅 ~800 tokens/s），提升约 37%。
    * 在16-256 并发区间扩展性更好，吞吐增长更接近线性，而 vLLM 在高并发时下降明显。
* 延迟（Latency）
  * 首 Token 延迟（TTFT）：
    * vLLM 更低（最低137ms，SGLang 最低182ms），适合实时交互场景。
    * 但SGLang 在高并发时更稳定（vLLM 的 TTFT 在 1024 并发时飙升至12.7s+）。
  * 每 Token 生成时间（TPOT）：
    * SGLang 大幅优化（最低仅39ms，vLLM 最低 110ms），提速 64%，更适合长文本流式输出。
* 输入长度影响
  * SGLang 对短序列（128 tokens）优化极佳：
    * 在 256 并发时，128-length 吞吐1126 tokens/s（vLLM 仅 737 tokens/s），提升 53%。
  * vLLM 对 256-length 序列更均衡，但 SGLang 在短序列上优势明显。

## 核心要素

* SGLang 更适合高并发、短文本场景，吞吐和 TPOT 表现更优，但首 Token 延迟略高。
* vLLM 在低延迟需求（如实时交互）和长文本场景更稳定。
* 如果业务允许稍高的首 Token 延迟，SGLang 的综合性能更优，尤其适合需要高并发的生产环境。
