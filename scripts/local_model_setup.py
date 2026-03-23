#!/usr/bin/env python3
"""
本地模型评估 & 微调入门脚本
适用于：Mac Studio 128GB 统一内存
目标：找到最适合 AgentOffice 项目的 Qwen 本地模型
"""

import subprocess
import sys
import json
from dataclasses import dataclass

# ============================================================
# 1. Mac Studio 128GB 可用模型清单（Qwen3.5 最新系列）
# ============================================================

@dataclass
class ModelOption:
    name: str           # 模型名称
    params: str         # 参数量
    memory_q4: str      # Q4量化内存占用
    memory_bf16: str    # BF16精度内存占用（微调用）
    can_finetune: bool  # 128GB内能否微调
    best_for: str       # 适合的任务

QWEN_MODELS = [
    ModelOption(
        name="Qwen3.5-4B-Instruct",
        params="4B",
        memory_q4="~3GB",
        memory_bf16="~8GB",
        can_finetune=True,
        best_for="快速测试、低延迟场景"
    ),
    ModelOption(
        name="Qwen3.5-9B-Instruct",
        params="9B",
        memory_q4="~6GB",
        memory_bf16="~18GB",
        can_finetune=True,
        best_for="质量与速度平衡，推荐起步"
    ),
    ModelOption(
        name="Qwen3.5-27B-Instruct",
        params="27B",
        memory_q4="~17GB",
        memory_bf16="~54GB",
        can_finetune=True,  # 128GB 可以做 LoRA 微调
        best_for="高质量分析，电商报告生成【推荐】"
    ),
    ModelOption(
        name="Qwen3.5-35B-A3B-Instruct",  # MoE 架构
        params="35B(MoE, 3B激活)",
        memory_q4="~22GB",
        memory_bf16="~70GB",
        can_finetune=True,
        best_for="MoE架构，速度接近3B但质量接近35B"
    ),
    ModelOption(
        name="Qwen3.5-122B-A10B-Instruct",  # MoE 架构
        params="122B(MoE, 10B激活)",
        memory_q4="~75GB",
        memory_bf16="超出范围",
        can_finetune=False,  # 仅推理
        best_for="最高质量推理，但只能做推理不能微调"
    ),
]

def print_model_table():
    print("\n" + "="*70)
    print("  Mac Studio 128GB 可用 Qwen3.5 模型清单")
    print("="*70)
    print(f"{'模型':<35} {'Q4推理':<10} {'BF16微调':<12} {'可微调':<8}")
    print("-"*70)
    for m in QWEN_MODELS:
        finetune_mark = "✅" if m.can_finetune else "❌"
        print(f"{m.name:<35} {m.memory_q4:<10} {m.memory_bf16:<12} {finetune_mark}")
    print("-"*70)
    print("\n💡 推荐：Qwen3.5-27B 微调 + Qwen3.5-122B 推理验证\n")


# ============================================================
# 2. 检查环境
# ============================================================

def check_environment():
    print("🔍 检查本地环境...\n")

    # 检查 Ollama
    result = subprocess.run(["which", "ollama"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Ollama 已安装")
        # 查看已有模型
        models = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        print(f"   已有模型:\n{models.stdout or '   (无)'}")
    else:
        print("❌ Ollama 未安装")
        print("   安装命令: brew install ollama")
        print("   或访问: https://ollama.ai\n")

    # 检查 mlx-lm（微调工具）
    result = subprocess.run(
        [sys.executable, "-c", "import mlx_lm; print(mlx_lm.__version__)"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"✅ mlx-lm 已安装 (版本: {result.stdout.strip()})")
    else:
        print("❌ mlx-lm 未安装（微调需要）")
        print("   安装命令: pip install mlx-lm\n")

    # 检查 unsloth（另一个微调选项，对 Qwen3.5 支持更好）
    result = subprocess.run(
        [sys.executable, "-c", "import unsloth; print('ok')"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("✅ Unsloth 已安装（Qwen3.5 微调推荐工具）")
    else:
        print("❌ Unsloth 未安装（可选，对 Qwen3.5 微调支持更好）")
        print("   安装命令: pip install unsloth\n")


# ============================================================
# 3. 生成电商场景训练数据样本
# ============================================================

SAMPLE_TRAINING_DATA = [
    {
        "messages": [
            {
                "role": "user",
                "content": "分析以下商品数据的竞争力：\n商品：无线蓝牙耳机\n价格：299元\n月销量：8500\n好评率：96.2%\n差评关键词：['续航时间', '音质一般']"
            },
            {
                "role": "assistant",
                "content": (
                    "## 竞争力分析报告\n\n"
                    "**综合评分：7.8/10**\n\n"
                    "### 优势\n"
                    "- 月销8500属于类目TOP 20%，市场认可度高\n"
                    "- 好评率96.2%超类目均值（约93%），质量口碑稳定\n"
                    "- 299元价格带竞争激烈，但已形成销量护城河\n\n"
                    "### 风险点\n"
                    "- 续航差评集中，建议在详情页明确标注实际续航时长，降低预期落差\n"
                    "- 音质问题为产品硬伤，建议定位场景化（通勤/运动）而非强调音质\n\n"
                    "### 建议行动\n"
                    "1. 短期：优化主图突出续航场景（如'通勤8小时'），减少因预期不符产生的差评\n"
                    "2. 中期：测试299→279价格梯度，观察销量弹性\n"
                    "3. 长期：考虑推出主打音质的高端款（399+），形成产品矩阵"
                )
            }
        ]
    },
    {
        "messages": [
            {
                "role": "user",
                "content": "竞品分析：我的商品A月销3000，竞品B月销12000，两者价格都是198元，如何提升？"
            },
            {
                "role": "assistant",
                "content": (
                    "## 竞品差距分析\n\n"
                    "**当前状态**：同价格带，销量差距4倍，需找到核心差异点\n\n"
                    "### 排查优先级\n\n"
                    "**第一步：主图点击率对比**\n"
                    "- 竞品B主图是否更具视觉冲击力？\n"
                    "- 建议：同一关键词搜索，截图对比首屏展示效果\n\n"
                    "**第二步：详情页转化率**\n"
                    "- 相同访客量下，转化率差距反映详情页质量\n"
                    "- 重点检查：卖点提炼、买家秀数量、问答丰富度\n\n"
                    "**第三步：评论质量**\n"
                    "- 竞品B的高分评论主要夸什么？这就是用户真实需求\n"
                    "- 将竞品好评的关键词植入自身商品文案\n\n"
                    "### 快速行动方案\n"
                    "本周内可执行：更换3版主图A/B测试，重点突出竞品差评中用户抱怨的痛点"
                )
            }
        ]
    },
]

def generate_sample_data(output_path: str = "training_data_sample.jsonl"):
    """生成训练数据样本文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for item in SAMPLE_TRAINING_DATA:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"✅ 训练数据样本已生成：{output_path}")
    print(f"   共 {len(SAMPLE_TRAINING_DATA)} 条样本")
    print("   💡 你需要积累 300-500 条类似数据才能开始微调\n")


# ============================================================
# 4. 生成微调命令
# ============================================================

def print_finetune_commands():
    print("\n" + "="*70)
    print("  微调命令参考（选择其一）")
    print("="*70)

    print("\n【方案A】mlx-lm（Apple 官方，Mac 原生）")
    print("""
  # 第一步：下载模型
  mlx_lm.convert --hf-path Qwen/Qwen3.5-9B-Instruct --mlx-path ./models/qwen3.5-9b

  # 第二步：LoRA 微调（适合 9B 模型，约需 2-3 小时）
  mlx_lm.lora \\
    --model ./models/qwen3.5-9b \\
    --train \\
    --data ./training_data/ \\
    --iters 1000 \\
    --batch-size 4 \\
    --lora-layers 16

  # 第三步：合并权重
  mlx_lm.fuse --model ./models/qwen3.5-9b --adapter-path ./adapters
""")

    print("【方案B】Unsloth（对 Qwen3.5 支持更好，速度更快）")
    print("""
  # 参考：https://unsloth.ai/docs/models/qwen3.5/fine-tune
  # Unsloth 对 Qwen3.5 有专门优化，显存占用减少 60%
  pip install unsloth
  # 然后使用 Unsloth 的 Qwen3.5 微调脚本
""")

    print("【接入项目】微调完成后，通过 Ollama 加载：")
    print("""
  # 将微调模型导入 Ollama
  ollama create ecommerce-qwen -f ./Modelfile

  # 在项目 agent runner 中使用
  # app/services/agents/runner.py 修改 model_config:
  model_config = {
      "base_url": "http://localhost:11434/v1",
      "api_key": "ollama",
      "model": "ecommerce-qwen"  # 你微调的电商专属模型
  }
""")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print("\n🤖 AgentOffice - 本地模型方案评估")
    print("   Mac Studio 128GB | Qwen3.5 系列\n")

    print_model_table()
    check_environment()

    import os
    data_path = os.path.join(os.path.dirname(__file__), "training_data_sample.jsonl")
    generate_sample_data(data_path)

    print_finetune_commands()

    print("\n" + "="*70)
    print("  推荐起步路径")
    print("="*70)
    print("""
  第一步（今天）：
    brew install ollama
    ollama pull qwen3.5:9b          ← 先跑起来看效果

  第二步（本周）：
    修改项目 runner.py 接入本地模型
    测试各个 Agent 任务的输出质量

  第三步（积累数据后）：
    收集 300+ 条电商分析样本
    用 mlx-lm 或 Unsloth 微调 Qwen3.5-9B
    部署专属模型到项目
""")
