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

from robot_tools import ROBOT_TOOLS, validate_tool_call, build_lfm_command


class AIBrainNode(Node):
    def __init__(self):
        super().__init__('ai_brain_node')

        self.IP_SERVER = "192.168.100.18"
        self.remote_client = Client(host=f"http://{self.IP_SERVER}:11434")
        self.MODEL_BRAIN = 'SpeakLeash/bielik-11b-v3.0-instruct:Q4_K_M'
        
        self.NUM_CTX = 16384 
        self.TOKEN_THRESHOLD = int(self.NUM_CTX * 0.85)
        self.ENABLE_THINKING = False

        print("\n=== LARRY AI BRAIN ===")
        user_goal = input("1. Podaj cel robota: ")
        print("\nDostępne modele wizyjne:\n  1 - lfm3-vl:2b (kierunki)\n  2 - qwen3-vl:8b (narzędzia JSON)")
        model_choice = input("2. Wybierz model (1 lub 2): ").strip()

        self.is_qwen = (model_choice == "2")
        self.MODEL_VISION = 'qwen3-vl:8b' if self.is_qwen else 'lfm3-vl:2b'

        if self.is_qwen:
            self.system_prompt = (
                "You are the brain of a mobile robot on an obstacle course. "
                "The image comes from a camera mounted directly on top of the robot looking forward. "
                "Analyze each new camera frame and ALWAYS respond by calling either `move_robot` or `stop_robot`. "
                "Choose velocity and duration carefully based on free space and obstacles ahead."
            )
        else:
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

        mode_name = "TOOLS (JSON)" if self.is_qwen else "DISCRETE (1 słowo)"
        self.get_logger().info(
            f"Mózg gotowy [{self.MODEL_VISION} | {mode_name}], limit pamięci: {self.NUM_CTX} tokenów. "
            "Czekam na sygnał gotowości od sterownika..."
        )

        self.mission_finished = False

    def setup_brain(self, polish_goal):
        print("\nBielik tłumaczy...")
        brain_response = self.remote_client.chat(
            model=self.MODEL_BRAIN,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Przetłumacz polecenie na język angielski, jeśli to możliwe bez straty informacji uprość. '
                        'Pozbądź się zbędnych znaków, emocji czy emotek zawartych w poleceniu. '
                        'Zwróć tylko JSON z kluczem "vision_prompt".'
                    )
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
                f"Goal: {base_prompt}. Inspect the current camera image and call `move_robot` "
                "with appropriate linear_x, angular_z, and duration, or call `stop_robot`."
            )
        else:
            final_prompt = (
                f"Goal: {base_prompt}. Output exactly one word: DRIVE, STOP, LEFT, RIGHT."
            )

        print("\n" + "=" * 50)
        print("[BIELIK] PRZETŁUMACZONY PROMPT:")
        print(f"{final_prompt}")
        print("=" * 50 + "\n")

        return final_prompt

    def camera_callback(self, msg):
        self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")

    def state_callback(self, msg):
        if msg.data == "STOPPED" and not self.is_thinking and not self.mission_finished:
            if self.latest_frame is not None:
                self.get_logger().info("Robot zatrzymany. Inicjuję analizę nowej klatki...")
                self.is_thinking = True

                thread = threading.Thread(
                    target=self.process_and_execute,
                    args=(self.latest_frame.copy(),),
                    daemon=True
                )
                thread.start()
            else:
                self.get_logger().warning("Robot zatrzymany, ale brak ramki wideo!")

    def cleanup_history(self, total_tokens):
        images_count = sum(1 for msg in self.history if isinstance(msg, dict) and 'images' in msg)
        self.get_logger().info(
            f"[Pamięć] Zużyto {total_tokens}/{self.NUM_CTX} tokenów (obrazy w historii: {images_count})"
        )

        if total_tokens <= self.TOKEN_THRESHOLD:
            return

        # 1. Najpierw usuwamy najstarszy obraz, zostawiając tekst i historię decyzji
        for msg in self.history[1:]:
            if isinstance(msg, dict) and 'images' in msg:
                del msg['images']
                self.get_logger().warning(
                    f"[Pamięć] Przekroczono próg {self.TOKEN_THRESHOLD} tokenów ({total_tokens}). "
                    "Usunięto najstarszy obraz z historii."
                )
                return

        # 2. Jeśli nie ma już obrazów, usuwamy całą najstarszą turę (user + assistant + ewentualne tool)
        if len(self.history) > 4:
            end_idx = 2
            while end_idx < len(self.history) and self.history[end_idx].get('role') != 'user':
                end_idx += 1

            # Zostawiamy przynajmniej system prompt + ostatnią turę
            if end_idx < len(self.history):
                del self.history[1:end_idx]
                self.get_logger().warning(
                    f"[Pamięć] Brak obrazów do usunięcia przy {total_tokens} tokenach. "
                    f"Usunięto najstarszą turę ({end_idx - 1} wpisów) z historii."
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
            chat_kwargs = {
                "model": self.MODEL_VISION,
                "messages": self.history,
                "options": {
                    "temperature": 0.5,
                    "repeat_penalty": 1.1,
                    "num_ctx": self.NUM_CTX,
                    "num_gpu": 99
                }
            }

            if self.is_qwen:
                chat_kwargs["tools"] = ROBOT_TOOLS
                chat_kwargs["think"] = self.ENABLE_THINKING

            vision_response = self.remote_client.chat(**chat_kwargs)

            prompt_tokens = getattr(vision_response, 'prompt_eval_count', 0) or 0
            eval_tokens = getattr(vision_response, 'eval_count', 0) or 0
            total_tokens = prompt_tokens + eval_tokens

            # Konwersja odpowiedzi na dict dla spójności z cleanup_history
            assistant_msg = vision_response.message.model_dump(exclude_none=True)
            self.history.append(assistant_msg)

            if self.is_qwen:
                cmd_payload = self._handle_qwen_response(vision_response.message)
            else:
                cmd_payload = self._handle_lfm_response(vision_response.message)

            self.cleanup_history(total_tokens)

            msg = String()
            msg.data = json.dumps(cmd_payload)
            self.publisher_.publish(msg)

        except Exception as e:
            if self.history and self.history[-1] is user_message:
                self.history.pop()
            self.get_logger().error(f"Ollama error: {e}")

        finally:
            self.is_thinking = False

    def _handle_qwen_response(self, message):
        tool_calls = getattr(message, 'tool_calls', None)

        print("\n" + "-" * 50)
        if tool_calls:
            tool_call = tool_calls[0]
            func_name = tool_call.function.name
            raw_args = tool_call.function.arguments
            print(f"[{self.MODEL_VISION}] TOOL CALL: {func_name}({raw_args})")
            print("-" * 50)

            cmd_payload, tool_feedback, log_msg = validate_tool_call(func_name, raw_args)
            self.get_logger().info(log_msg)

            if func_name == "stop_robot" and cmd_payload.get("action") == "stop":
                self.mission_finished = True
                self.get_logger().info("Misja zakończona przez Qwena (stop_robot). Wstrzymuję dalszą analizę.")

            # Zapisujemy wynik narzędzia w historii, żeby Qwen widział rezultat w kolejnym kroku
            self.history.append({
                'role': 'tool',
                'tool_name': func_name,
                'content': tool_feedback
            })
            return cmd_payload

        raw_text = (message.content or "").strip()
        print(f"[{self.MODEL_VISION}] BRAK TOOL CALL! Tekst: '{raw_text}'")
        print("-" * 50)
        self.get_logger().warning("Qwen nie wywołał żadnego narzędzia – zatrzymuję robota.")
        return {"action": "stop"}

    def _handle_lfm_response(self, message):
        raw_output = (message.content or "").strip().upper()
        print("\n" + "-" * 50)
        print(f"[{self.MODEL_VISION}] RAW OUTPUT: '{raw_output}'")
        print("-" * 50)

        cmd_payload, decision = build_lfm_command(raw_output)
        self.get_logger().info(f"[LFM] Decyzja: {decision} -> {cmd_payload}")
        return cmd_payload


def main(args=None):
    rclpy.init(args=args)
    node = AIBrainNode()

    timeout = time.time() + 2.0
    while node.latest_frame is None and time.time() < timeout:
        rclpy.spin_once(node, timeout_sec=0.1)

    # Sygnał startowy w nowym formacie JSON, żeby sterownik odpowiedział STOPPED
    msg = String()
    msg.data = json.dumps({"action": "stop"})
    node.publisher_.publish(msg)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
