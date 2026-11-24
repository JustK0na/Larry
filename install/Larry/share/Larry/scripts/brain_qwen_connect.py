#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image as ROSImage
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
from ollama import Client
import json
import threading

class AIBrainNode(Node):
    def __init__(self):
        super().__init__('ai_brain_node')
        
        # --- Konfiguracja Ollamy ---
        self.IP_SERVER = "192.168.100.18"
        self.remote_client = Client(host=f"http://{self.IP_SERVER}:11434")
        self.MODEL_BRAIN = 'SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M'
        
        print("\n=== LARRY AI BRAIN ===")
        user_goal = input("1. Podaj cel robota (po polsku): ")
        print("\nDostępne modele wizyjne:\n  1 - lfm3-vl:2b\n  2 - qwen3-vl:8b")
        model_choice = input("2. Wybierz model (1 lub 2): ").strip()
        
        self.is_qwen = (model_choice == "2")
        self.MODEL_VISION = 'qwen3-vl:8b' if self.is_qwen else 'lfm3-vl:2b'
        
        # --- Setup Mózgu ---
        self.system_prompt = (
            "You are the brain of a mobile robot put on an obstacle course. "
            "Your task is to analyze the image and choose the best next move to reach the goal while avoiding obstacles. "
            "The image is gathered from a camera mounted directly on top of the robot."
        )
        self.strict_vision_prompt = self.setup_brain(user_goal)

        
        self.bridge = CvBridge()
        self.publisher_ = self.create_publisher(String, '/ai_command', 10)
        
        # NOWE: Nasłuchiwanie stanu od Sterownika
        self.state_sub = self.create_subscription(String, '/robot_state', self.state_callback, 10)
        self.camera_sub = self.create_subscription(ROSImage, '/camera/image_raw', self.camera_callback, 10)
        
        self.latest_frame = None
        self.is_thinking = False
        
        self.get_logger().info(f"Mózg gotowy [{self.MODEL_VISION}]. Czekam na sygnał gotowości od sterownika...")

    def setup_brain(self, polish_goal):
        print("\nBielik tłumaczy...")
        brain_response = self.remote_client.chat(
            model=self.MODEL_BRAIN, 
            messages=[
                {'role': 'system', 'content': 'Przetłumacz polecenie na język na angielski, jeśli to możliwe bez straty informacji uprość. Pozbądź się zbędnych znaków, emocji czy emotek zawartych w poleceniu. Zwróć tylko JSON z kluczem "vision_prompt".'},
                {'role': 'user', 'content': polish_goal}
            ],
            format='json',
            keep_alive=0 # Wyrzuca Bielika!
        )
        brain_data = json.loads(brain_response.message.content)
        base_prompt = brain_data["vision_prompt"]
        
        if self.is_qwen:
            return (f"Goal: {base_prompt}. Output exactly two words: [DIRECTION] [SECONDS]. "
                    "Directions: DRIVE, STOP, LEFT, RIGHT. Time must be between 0.5 and 3.0. Example: DRIVE 1.5")
        else:
            return f"Goal: {base_prompt}. Output exactly one word: DRIVE, STOP, LEFT, RIGHT."

    def camera_callback(self, msg):
        self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")

    def state_callback(self, msg):
        """Odpala się, gdy Motor Controller zamelduje zmianę stanu."""
        state = msg.data
        if state == "STOPPED" and not self.is_thinking:
            if self.latest_frame is not None:
                self.get_logger().info("Robot zatrzymany. Inicjuję analizę nowej klatki...")
                self.is_thinking = True
                
                # Odpalamy inferencję w wątku, by nie zablokować ROS-a
                thread = threading.Thread(target=self.process_and_execute, args=(self.latest_frame.copy(),))
                thread.start()
            else:
                self.get_logger().warning("Robot zatrzymany, ale brak ramki wideo!")

    def process_and_execute(self, frame):
        success, buffer = cv2.imencode('.jpg', frame)
        if not success:
            self.is_thinking = False
            return
            
        img_bytes = buffer.tobytes()
        
        try:
            vision_response = self.remote_client.chat(
                model=self.MODEL_VISION,
                messages=[
                    {'role': 'system', 'content': self.system_prompt},
                    {'role': 'user', 'content': self.strict_vision_prompt, 'images': [img_bytes]}
                ],
                options={"temperature": 0.0}
            )
            
            raw_output = vision_response.message.content.strip().upper()
            words = raw_output.split()
            decision, duration = "STOP", "1.5"
            
            if len(words) > 0:
                for move in ["DRIVE", "STOP", "LEFT", "RIGHT"]:
                    if move in words[0]:
                        decision = move
                        break
                        
            if self.is_qwen and len(words) > 1:
                # Jeśli Qwen podał czas, dodajemy go do komendy dla kontrolera
                try:
                    duration_float = min(max(float(words[1]), 0.5), 3.0)
                    duration = str(duration_float)
                except ValueError:
                    pass

            # Budujemy i wysyłamy komendę, np. "DRIVE 2.0"
            final_cmd = f"{decision} {duration}"
            self.get_logger().info(f"AI zdecydowało: {final_cmd}")
            
            msg = String()
            msg.data = final_cmd
            self.publisher_.publish(msg)
            
        except Exception as e:
            self.get_logger().error(f"Ollama error: {e}")
            
        finally:
            # Flaga jest zdejmowana. Od teraz czekamy na powiadomienie "STOPPED" z kontrolera
            self.is_thinking = False

def main(args=None):
    rclpy.init(args=args)
    node = AIBrainNode()
    
    msg = String()
    msg.data = "STOP"
    node.publisher_.publish(msg)
    

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
