# wrv-extraction-diff-api

## Question ID: l1-083

## Task Type: feature

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

数据提取结果对比功能。同一份文档可能被不同的提取配置提取多次，需要能对比两次提取结果的差异。帮我新建一个对比接口：传入两个 ExtractionExecutions 的 ID，比对两次提取的所有 ExtractionResult 记录，输出字段级别的 diff。对比结果存到新的 extraction_diff 表里，API 返回结构化的 JSON 给前端。
