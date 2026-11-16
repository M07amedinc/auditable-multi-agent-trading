"""Stage B - SELF-TRAINING via DPO. Learns from wins AND losses.
chosen = winning argument, rejected = losing argument (same situation).
Colab: pip install unsloth trl datasets, then: python train_model.py
"""
import os
from datasets import load_dataset
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import DPOTrainer, DPOConfig

MODEL = "unsloth/Qwen2.5-7B-Instruct"
OUT = "models/bull_bear_dpo_v1"

def train(dataset_path="logs/dpo_pairs.jsonl"):
    model, tokenizer = FastLanguageModel.from_pretrained(MODEL, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(model)
    ds = load_dataset("json", data_files=dataset_path, split="train")
    n = len(ds)
    holdout = max(1, int(n * 0.1))
    train_ds, eval_ds = ds.select(range(n - holdout)), ds.select(range(n - holdout, n))
    print(f"train: {n-holdout} pairs | eval: {holdout} pairs")

    trainer = DPOTrainer(
        model=model, args=DPOConfig(
            per_device_train_batch_size=1, gradient_accumulation_steps=8,
            max_steps=200, learning_rate=5e-5, beta=0.1,
            fp16=not is_bfloat16_supported(),
            output_dir=OUT, report_to="none",
            max_length=2048, max_prompt_length=1024,
        ),
        train_dataset=train_ds, eval_dataset=eval_ds,
        processing_class=tokenizer,
    )
    trainer.train()
    model.save_pretrained(OUT)
    tokenizer.save_pretrained(OUT)
    print("saved ->", OUT)

if __name__ == "__main__":
    train()