# -*- coding: utf-8 -*-
# Start vLLM server with Qwen3-VL for mental health monitoring
# Usage: .\start_vllm.ps1

$model = "Qwen/Qwen3-VL-8B-Instruct"
$api_port = 8000
$gpu_memory = 0.85   # Use 85% of 24GB ≈ 20GB

Write-Host "[+] Starting vLLM with model: $model" -ForegroundColor Green
Write-Host "[+] API will be at http://localhost:$api_port/v1" -ForegroundColor Cyan
Write-Host "[+] Then update config.py vllm_api_url accordingly" -ForegroundColor Yellow

vllm serve $model `
    --port $api_port `
    --host 127.0.0.1 `
    --gpu-memory-utilization $gpu_memory `
    --max-model-len 16384 `
    --dtype bfloat16 `
    --enforce-eager `
    --trust-remote-code

# Notes:
# - config.py model_name should match this $model value
# - If you use a local model path instead, change $model to the full path
# - OOM? Try --gpu-memory-utilization 0.7
# - Smaller alternative: Qwen/Qwen3-VL-4B-Instruct
