# wrr-ab-test-routing

## Question ID: l1-030

## Task Type: feature

## App Domain: ai_ml

## Language: python

## Model: qwen

## Query

模型服务要加A/B测试，但不是简单的随机分流——要按用户特征分流（新用户走A、老用户走B），而且实验组和对照组的流量要能动态调整不能停服务。实验数据要能自动统计显著性，跑够样本量自动出结论。
