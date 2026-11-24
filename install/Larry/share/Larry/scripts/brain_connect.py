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
import time


class AIBrainNode(Node):
    def __init__(self):
        super().__init__('ai_brain_node')

        self.IP_SERVER = "192.168.100.18"
        self.remote_client = Client(host=f"http://{self.IP_SERVER}:11434")
        self.MODEL_BRAIN = 'SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M'

        self.NUM_CTX = 10000
        self.TOKEN_THRESHOLD = 8500

        print("\n=== LARRY AI BRAIN ===")
        user_goal = input("1. Podaj cel robota: ")
        print("\nDostępne modele wizyjne:\n  1 - lfm3-vl:2b\n  2 - qwen3-vl:8b")
        model_choice = input("2. Wybierz model (1 lub 2): ").strip()

        self.is_qwen = (model_choice == "2")
        self.MODEL_VISION = 'qwen3-vl:8b' if self.is_qwen else 'lfm3-vl:2b'

        self.system_prompt = (
            "You are the brain of a mobile robot put on an obstacle course. "
            "Your task is to analyze the image and choose the best next move to reach the goal while avoiding obstacles. "
            "The image is gathered from a camera mounted directly on top of the robot."
        )
        self.strict_vision_prompt = self.setup_brain(user_goal)
        self.history = [{'role': 'system', 'content': self.system_prompt}]

        self.bridge = CvBridge()
        self.publisher_ = self.create_publisher(String, '/ai_command', 10)
        self.state_sub = self.create_subscription(String, '/robot_state', self.state_callback, 10)
        self.camera_sub = self.create_subscription(ROSImage, '/camera/image_raw', self.camera_callback, 10)

        self.latest_frame = None
        self.is_thinking = False

        self.get_logger().info(
            f"Mózg gotowy [{self.MODEL_VISION}], limit pamięci: {self.NUM_CTX} tokenów. "
            "Czekam na sygnał gotowości od sterownika..."
        )

    def setup_brain(self, polish_goal):
        print("\nBielik tłumaczy...")
        brain_response = self.remote_client.chat(
            model=self.MODEL_BRAIN,
            messages=[
                {
                    'role': 'system',
                    'content': 'Przetłumacz polecenie na język angielski, jeśli to możliwe bez straty informacji uprość. Pozbądź się zbędnych znaków, emocji czy emotek zawartych w poleceniu. Zwróć tylko JSON z kluczem "vision_prompt".'
                },
                {'role': 'user', 'content': polish_goal}
            ],
            format='json',
            keep_alive=0
        )
        brain_data = json.loads(brain_response.message.content)
        base_prompt = brain_data["vision_prompt"]

        if self.is_qwen:
            final_prompt = (
                f"Goal: {base_prompt}. Output exactly two words: [DIRECTION] [SECONDS]. "
                "Directions: DRIVE, STOP, LEFT, RIGHT. Time must be between 0.5 and 3.0. Example: DRIVE 1.5"
            )
        else:
            final_prompt = (
                f"Goal: {base_prompt}. Output exactly one word: DRIVE, STOP, LEFT, RIGHT."
            )

        print("\n" + "=" * 50)
        print("[BIELIK] PRZETŁUMACZONY SYSTEM PROMPT:")
        print(f"{final_prompt}")
        print("=" * 50 + "\n")

        return final_prompt

    def camera_callback(self, msg):
        self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")

    def state_callback(self, msg):
        if msg.data == "STOPPED" and not self.is_thinking:
            if self.latest_frame is not None:
                self.get_logger().info("Robot zatrzymany. Inicjuję analizę nowej klatki...")
                self.is_thinking = True

                thread = threading.Thread(
                    target=self.process_and_execute,
                    args=(self.latest_frame.copy(),)
                )
                thread.start()
            else:
                self.get_logger().warning("Robot zatrzymany, ale brak ramki wideo!")

    def cleanup_history(self, total_tokens):
        images_count = sum(1 for msg in self.history if 'images' in msg)
        self.get_logger().info(
            f"[Pamięć] Zużyto {total_tokens}/{self.NUM_CTX} tokenów (obrazy w historii: {images_count})"
        )

        if total_tokens > self.TOKEN_THRESHOLD:
            removed_image = False

            for msg in self.history[1:]:
                if 'images' in msg:
                    del msg['images']
                    removed_image = True
                    self.get_logger().warning(
                        f"[Pamięć] Przekroczono próg {self.TOKEN_THRESHOLD} tokenów ({total_tokens}). "
                        "Usunięto najstarszy obraz z historii."
                    )
                    break

            if not removed_image and len(self.history) > 3:
                del self.history[1:3]
                self.get_logger().warning(
                    f"[Pamięć] Brak obrazów do usunięcia przy {total_tokens} tokenach. "
                    "Usunięto najstarszą parę wpisów tekstowych z historii."
                )

    def process_and_execute(self, frame):
        success, buffer = cv2.imencode('.jpg', frame)
        if not success:
            self.is_thinking = False
            return

        img_bytes = buffer.tobytes()
        user_message = {
            'role': 'user',
            'content': self.strict_vision_prompt,
            'images': [img_bytes]
        }
        self.history.append(user_message)

        try:
            vision_response = self.remote_client.chat(
                model=self.MODEL_VISION,
                messages=self.history,
                options={
                    "temperature": 0.0,
                    "num_ctx": self.NUM_CTX,
                    "num_gpu": 99
                }
            )

            prompt_tokens = getattr(vision_response, 'prompt_eval_count', 0) or 0
            eval_tokens = getattr(vision_response, 'eval_count', 0) or 0
            total_tokens = prompt_tokens + eval_tokens

            raw_content = vision_response.message.content.strip()
            self.history.append({'role': 'assistant', 'content': raw_content})

            raw_output = raw_content.upper()
            print("\n" + "-" * 40)
            print(f"[{self.MODEL_VISION}] RAW OUTPUT: '{raw_output}'")
            print("-" * 40)

            self.cleanup_history(total_tokens)

            words = raw_output.split()
            decision, duration = "STOP", "1"

            if len(words) > 0:
                for move in ["DRIVE", "STOP", "LEFT", "RIGHT"]:
                    if move in words[0]:
                        decision = move
                        break

            if self.is_qwen and len(words) > 1:
                try:
                    duration_float = min(max(float(words[1]), 0.5), 3.0)
                    duration = str(duration_float)
                except ValueError:
                    pass

            final_cmd = f"{decision} {duration}"
            self.get_logger().info(f"AI zdecydowało: {final_cmd}")

            msg = String()
            msg.data = final_cmd
            self.publisher_.publish(msg)

        except Exception as e:
            if self.history and self.history[-1] is user_message:
                self.history.pop()
            self.get_logger().error(f"Ollama error: {e}")

        finally:
            self.is_thinking = False


def main(args=None):
    rclpy.init(args=args)
    node = AIBrainNode()

    timeout = time.time() + 2.0
    while node.latest_frame is None and time.time() < timeout:
        rclpy.spin_once(node, timeout_sec=0.1)

    msg = String()
    msg.data = "STOP"
    node.publisher_.publish(msg)


    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
