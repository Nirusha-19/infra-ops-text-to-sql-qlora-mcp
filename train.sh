#!/bin/bash
# Runs LoRA fine-tuning using MLX.
# Usage: bash train.sh
#
# NOTE: mlx_lm's CLI flags occasionally change between versions.
# If a flag below is rejected, run:  python -m mlx_lm.lora --help

set -e

MODEL="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
DATA_DIR="./data"
ADAPTER_DIR="./adapters"
ITERS=600
BATCH_SIZE=4
LORA_LAYERS=8

mkdir -p "$ADAPTER_DIR"

echo "Starting LoRA fine-tuning..."
echo "Model: $MODEL"
echo "Data: $DATA_DIR (1875 train / 250 valid examples, tiered easy/medium/hard)"
echo "Adapters will be saved to: $ADAPTER_DIR"
echo ""

python -m mlx_lm.lora \
  --model "$MODEL" \
  --train \
  --data "$DATA_DIR" \
  --iters $ITERS \
  --batch-size $BATCH_SIZE \
  --num-layers $LORA_LAYERS \
  --adapter-path "$ADAPTER_DIR" \
  --save-every 100 \
  --steps-per-report 20 \
  --steps-per-eval 100

echo ""
echo "Training complete. Adapter weights saved in $ADAPTER_DIR"
