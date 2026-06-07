# wrr-infer-gpu-leak

## Question ID: l1-020

## Task Type: bug-fix

## App Domain: ai_ml

## Language: python

## Model: qwen

## Query

模型推理服务最近经常 OOM，看监控是显存没释放干净，推理完一批之后显存没回到基线。帮我查下哪里泄漏了。
