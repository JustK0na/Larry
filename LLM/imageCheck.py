from pathlib import Path
from ollama import Client

# Konfiguracja klienta zdalnego
IP_SERVER = "192.168.100.18"
remote_client = Client(host=f"http://{IP_SERVER}:11434")

# Pobranie ścieżki od użytkownika
image_path_input = input('Please enter the path to the image: ')
image_path = Path(image_path_input)

# Sprawdzenie, czy plik istnieje, zanim wyślemy go do serwera
if not image_path.exists():
    print(f"Error: File not found at {image_path}")
else:
    # Wczytanie obrazu jako surowe bajty
    image_bytes = image_path.read_bytes()

    # Wywołanie czatu przy użyciu skonfigurowanego klienta zdalnego (remote_client)
    response = remote_client.chat(
        model='qwen3-vl:8b',
        messages=[
            {
                'role': 'user',
                'content': 'Co znajduje sie na obrazie? gdzie może dziać się taka scena? zwięźle.',
                'images': [image_bytes],  # Przekazujemy bajty, nie ścieżkę tekstową
            }
        ],
    )

    # Wyświetlenie odpowiedzi modelu
    print("\nModel response:")
    print(response.message.content)