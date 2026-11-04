import json
from ollama import Client
import os

remote_client = Client(host="http://192.168.100.18:11434")
MODEL_BRAIN = 'SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M'
MODEL_VISION = 'lfm3-vl:2b'

# --- KROK 1: Bielik (Mózg) ustala zadanie ---
task_input = input("Podaj cel robota: ")
print("Bielik myśli...")

brain_response = remote_client.chat(
    model=MODEL_BRAIN, 
    messages=[
        {'role': 'system', 'content': 'Przetłumacz polecenie na krótki angielski prompt dla modelu wizyjnego. Odpowiedz TYLKO formatem JSON z kluczem "vision_prompt".'},
        {'role': 'user', 'content': task_input}
    ],
    format='json'
)

# Czytamy wynik prosto z JSONa (zakładamy, że Bielik się nie pomylił)
brain_data = json.loads(brain_response.message.content)
strict_vision_prompt = brain_data["vision_prompt"] + "\nOutput exactly one word: DRIVE, STOP, LEFT, or RIGHT."

print(f"Bielik wygenerował prompt: {strict_vision_prompt}\n")


# --- KROK 2: LFM3 (Oczy) działa w pętli ---
print("Wpisz 'koniec psot', aby zakończyć. Ścieżka do pliku: ")

while True:
    img_path = input("Ścieżka do obrazka: ")
    
    if img_path.lower() == 'koniec psot':
        break

    if not os.path.isfile(img_path):
        print("Nie znaleziono pliku. Spróbuj ponownie.")
        continue
    
    vision_response = remote_client.chat(
        model=MODEL_VISION, 
        messages=[{'role': 'user', 'content': strict_vision_prompt, 'images': [img_path]}],
        options={"temperature": 0.0}
    )
    
    # Drukujemy surową odpowiedź modelu
    print(f"Decyzja: {vision_response.message.content.strip()}")
