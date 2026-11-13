import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist

class MotorControllerNode(Node):
    def __init__(self):
        super().__init__('motor_controller_node')
        
        self.subscription = self.create_subscription(
            String,
            '/ai_command',
            self.command_callback,
            10
        )
        
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.LINEAR_SPEED = 0.3  
        self.ANGULAR_SPEED = 0.5

        self.current_twist = Twist()
        self.timer = self.create_timer(0.1, self.timer_callback)
        
        self.get_logger().info("Motor Controller gotowy. Oczekuję na komendy tekstowe z warstwy AI...")

    def command_callback(self, msg):
        command = msg.data.upper()
        
        # Zmieniamy BEZPOŚREDNIO self.current_twist
        if command == "DRIVE":
            self.current_twist.linear.x = self.LINEAR_SPEED
            self.current_twist.angular.z = 0.0
        elif command == "LEFT":
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = self.ANGULAR_SPEED
        elif command == "RIGHT":
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = -self.ANGULAR_SPEED
        elif command == "STOP":
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = 0.0
        else:
            self.get_logger().warning(f"Nieznana komenda: {command}")
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = 0.0
            
        # Poprawione logowanie - teraz poprawnie czyta z self.current_twist
        self.get_logger().info(f"Przekonwertowano: {command} -> v: {self.current_twist.linear.x}, w: {self.current_twist.angular.z}")
        
    def timer_callback(self):
        # Timer nieprzerwanie publikuje ostatnio zapamiętany stan
        self.publisher_.publish(self.current_twist)

def main(args=None):
    rclpy.init(args=args)
    node = MotorControllerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop_msg = Twist()
        node.publisher_.publish(stop_msg)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
