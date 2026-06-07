import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

class InferenceService:
    def __init__(self, model_name: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.eval()

    def generate(self, prompt: str, max_new_tokens: int = 100) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        # BUG: tensors not moved to correct device after inference
        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
        # BUG: intermediate tensors not explicitly deleted
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def batch_generate(self, prompts: list, max_new_tokens: int = 100) -> list:
        results = []
        for prompt in prompts:
            results.append(self.generate(prompt, max_new_tokens))
            # BUG: GPU memory accumulates across batch items
        return results
