import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraViewerNode(Node):
    def __init__(self):
        super().__init__('camera_viewer_node')
        
        # Narzędzie do tłumaczenia obrazów ROS 2 na format OpenCV
        self.bridge = CvBridge()
        
        # Subskrypcja na topic z kamery
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10 # Rozmiar kolejki
        )
        self.get_logger().info('Węzeł uruchomiony. Oczekiwanie na obraz z kamery Gazebo...')

    def image_callback(self, msg):

        # Konwersja surowej wiadomości ROS (msg) na macierz pikseli (cv_image)
        cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            
        # Wyświetlenie obrazu w oknie
        cv2.imshow("Kamera Robota (Gazebo)", cv_image)
            
        # Funkcja waitKey(1) jest niezbędna, aby OpenCV mogło odświeżyć GUI okna
        cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = CameraViewerNode()
    
    rclpy.spin(node)

    cv2.destroyAllWindows() # Bezpieczne zamknięcie okna kamery
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
            

