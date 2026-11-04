from ollama import chat
from ollama import Client

IP_SERVER = "192.168.100.18"
remote_client = Client(host=f"http://{IP_SERVER}:11434")

# Update to 8-bit model if you downloaded it, otherwise leave as is
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

    stream = remote_client.chat(
        model=MODEL_NAME, 
        messages=history, 
        stream=True, 
        options={"num_ctx": 49152, "num_gpu": 99}
    )
    
    print("EjAj: ", end="", flush=True)
    full_response = ""
    total_tokens = 0

    for n in stream:
        token = n.message.content
        print(token, end="", flush=True)
        full_response += token
        
        # Capture token usage on the final chunk
        if n.done:
            # Safely handle missing attributes if the server response varies
            prompt_tokens = getattr(n, 'prompt_eval_count', 0)
            eval_tokens = getattr(n, 'eval_count', 0)
            total_tokens = prompt_tokens + eval_tokens

    print("\n")

    history.append({'role': 'assistant', 'content':full_response})

    # Dynamic cleanup: Delete the oldest image if threshold is crossed
    TOKEN_THRESHOLD = 40000 
    if total_tokens > TOKEN_THRESHOLD:
        print(f"[System] Użyto {total_tokens} tokenów. Usuwanie najstarszego obrazka aby zapobiec przepełnieniu VRAM...")
        for msg in history:
            if 'images' in msg:
                del msg['images']
                break 


#gemini helped            
