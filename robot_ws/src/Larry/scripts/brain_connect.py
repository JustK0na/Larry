import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image as ROSImage
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import requests

class AIBrainNode(Node):
    def __init__(self):
        super().__init__('ai_brain_node')
        
        PC_IP = "192.168.100.18"
        self.CUSTOM_VISION_URL = f"http://{PC_IP}:8000/vision"
        
        self.bridge = CvBridge()
        self.publisher_ = self.create_publisher(String, '/ai_command', 10)
        self.subscription = self.create_subscription(
            ROSImage, '/camera/image_raw', self.camera_callback, 10
        )
        
        self.latest_frame = None
        self.is_thinking = False # Flaga zapobiegająca kolejkowaniu żądań
        
        # System prompt zamiast bielika.
        user_goal = input("Enter the robot's goal (e.g., 'Go to the red ball'): ")
        self.strict_vision_prompt = (
            f"You are the brain of an autonomous mobile robot. Your task is: {user_goal}. "
            "Analyze the current camera frame and decide the immediate next movement to accomplish this task. "
            "Output exactly one word from this list: DRIVE, STOP, LEFT, RIGHT. "
            "Do not provide any explanations or additional text."
        )
        
        self.get_logger().info("Ejaj gotowy. Oczekiwanie na klatki z kamery Gazebo...")
        
        # Pętla decyzyjna sprawdzająca co 0.5 sekundy, czy można wysłać nową klatkę
        self.timer = self.create_timer(0.5, self.control_loop)

    def camera_callback(self, msg):
        self.latest_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")

    def control_loop(self):
        """Wysyła najnowszą klatkę do modelu VLM na PC, jeśli ten nie jest zajęty."""
        if self.is_thinking or self.latest_frame is None:
            return
            
        self.is_thinking = True
        
        # 1. Kompresja klatki do pamięci RAM (zapobiega zapisywaniu na dysk)
        frame_copy = self.latest_frame.copy()
        success, buffer = cv2.imencode('.jpg', frame_copy)
        if not success:
            self.is_thinking = False
            return
            
        img_bytes = buffer.tobytes()
        
        try:
            files = {'image': ('frame.jpg', img_bytes, 'image/jpeg')}
            data = {'prompt': self.strict_vision_prompt}
            
            response = requests.post(self.CUSTOM_VISION_URL, files=files, data=data, timeout=10.0)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    decision = result.get("decision")
                    self.get_logger().info(f"Decyzja VLM: {decision},  {result.get('raw_output')})")
                    
                    # Publikacja polecenia dla robot_driver.py
                    msg = String()
                    msg.data = decision
                    self.publisher_.publish(msg)
                else:
                    self.get_logger().error(f"Błąd przetwarzania modelu: {result.get('message')}")
            else:
                self.get_logger().error(f"Błąd sieci: {response.status_code}")
                
        except Exception as e:
            self.get_logger().error(f"Brak połączenia z serwerem ): {e}")
            
        finally:

            self.is_thinking = False

def main(args=None):
    rclpy.init(args=args)
    node = AIBrainNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
