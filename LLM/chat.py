from ollama import chat
from ollama import Client
IP_SERVER = "192.168.100.18"
remote_client = Client(host=f"http://{IP_SERVER}:11434")

MODEL_NAME = 'qwen3-vl:8b'
context = "You are the brain of mobile robot put on an obstacle course, your task is to analyse image and choose best next move. Image is gathered from camera that is mounted directly on top of the mobile robot. Your decision and resonoing shout be short and concise without"
history = [{'role': 'system', 'content': context}]




print(f"rozpoczeto czat z {MODEL_NAME}")
print(f"Wpisz 'koniec psot', aby zakonczyc czat")


while True:
    user_input = input("Ty: ")
    if user_input.lower() == "koniec psot":
        break

    img_path = input("(opcjonalne)ściezka do obrazka: ").strip()
    user_message = {'role': 'user', 'content':user_input}
    if img_path:
        user_message['images'] = [img_path]
        
    
    history.append(user_message)
    for i, msg in enumerate(history):
        if 'images' in msg and i< len(history) - 4:
            del msg['images']

    stream = remote_client.chat(model=MODEL_NAME, messages=history, stream=True)
    print("EjAj: ", end="", flush=True)
    full_response = ""

    for n in stream:
        token = n.message.content
        print(token, end="", flush=True)
        full_response += token
    print("\n")

    history.append({'role': 'assistant', 'content':full_response})
    
