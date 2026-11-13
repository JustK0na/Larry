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
MODEL_PATH = models_map[args.model]

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
    image_tags = "<image>\n" * len(frame_history)
    # 2. Przygotowanie wejścia dla modelu
    formatted_prompt = f"{image_tags}{prompt}"
    inputs = processor(formatted_prompt, list(frame_history), return_tensors="pt").to("cuda")
    
    # 3. Inferencja na karcie graficznej
    output = model.generate(**inputs, max_new_tokens=10)
    raw_text = processor.decode(output[0], skip_special_tokens=True)
    
    # 4. Wyciągnięcie komendy
    clean_decision = "STOP"
    for move in ["DRIVE", "STOP", "LEFT", "RIGHT"]:
        if move in raw_text.upper():
            clean_decision = move
            break
            
    return {"status": "ok", "decision": clean_decision, "raw_output": raw_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)