import argparse
from fastapi import FastAPI, UploadFile, File, Form
from transformers import AutoProcessor, AutoModelForCausalLM, BitsAndBytesConfig, AutoModel
from PIL import Image
import torch
import io
import uvicorn
from collections import deque


# Konfiguracja argumentów startowych
parser = argparse.ArgumentParser()
parser.add_argument('--model', type=str, default='lfm', choices=['lfm', 'basal'])
args = parser.parse_args()

# 1. Ścieżki do lokalnych folderów z pobranymi modelami
models_map = {
    'lfm': r'X:\ollama\models\custom\LFM3-VL-2B', 
    'basal': r'X:\ollama\models\custom\Basal-omni-1.0-mini'
}
image_token_map = {
    'lfm': '<image>', 
    'basal': '<|image|>'
}
MODEL_PATH = models_map[args.model]
IMAGE_TOKEN = image_token_map[args.model]

print(f"[{MODEL_PATH}] Ładowanie modelu do VRAM...")

# 2. Konfiguracja kwantyzacji 4-bitowej (wymagana dla 16GB modelu na RTX 3060)
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16
)

# 3. Ładowanie procesora i modelu z lokalnego dysku
processor = AutoProcessor.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    trust_remote_code=True
)

try:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map="cuda:0",
        local_files_only=True,
        trust_remote_code=True
    )
except ValueError:
    print(f"[{MODEL_PATH}] Model odrzucił klasę CausalLM. Awaryjne ładowanie przez AutoModel...")
    model = AutoModel.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map="cuda:0",
        local_files_only=True,
        trust_remote_code=True
    )

app = FastAPI()
MAX_FRAMES = 4
frame_history = deque(maxlen=MAX_FRAMES)

print("Serwer gotowy! Nasłuchiwanie na klatki...")

@app.post("/vision")
async def analyze_frame(prompt: str = Form(...), image: UploadFile = File(...)):
    # 1. Odczyt obrazu z sieci
    image_data = await image.read()
    pil_image = Image.open(io.BytesIO(image_data)).convert("RGB")

    frame_history.append(pil_image)
    image_tags = f"{IMAGE_TOKEN}\n" * len(frame_history)
    formatted_prompt = f"{image_tags}{prompt}\nDecision:" 
    inputs = processor(text=formatted_prompt, images=list(frame_history), return_tensors="pt").to("cuda")
   # 3. Inferencja na karcie graficznej (wyłączamy losowość parametrem do_sample)
    output = model.generate(**inputs, max_new_tokens=10, do_sample=False)
    full_text = processor.decode(output[0], skip_special_tokens=True)

    # Odcięcie długości oryginalnego promptu, aby czytać tylko odpowiedź modelu
    input_length = inputs["input_ids"].shape[1]
    generated_tokens = output[0][input_length:]
    raw_text = processor.decode(generated_tokens, skip_special_tokens=True).strip()
    
    # 4. Wyciągnięcie tylko odpowiedzi modelu (tego co po słowie "Decision:")
    if "Decision:" in full_text:
        raw_text = full_text.split("Decision:")[-1].strip()
    else:
        raw_text = full_text.strip()
    
    # 5. Wyciągnięcie komendy (z bezpiecznym parsowaniem)
    clean_decision = "STOP"
    for move in ["DRIVE", "STOP", "LEFT", "RIGHT"]:
        if move in raw_text.upper():
            clean_decision = move
            break
            
    return {"status": "ok", "decision": clean_decision, "raw_output": raw_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)