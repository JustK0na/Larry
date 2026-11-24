#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist

class MotorControllerNode(Node):
    def __init__(self):
        super().__init__('motor_controller_node')
        

        self.subscription = self.create_subscription(String, '/ai_command', self.command_callback, 10)
        

        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        

        self.state_publisher_ = self.create_publisher(String, '/robot_state', 10)
        
        self.LINEAR_SPEED = 0.3  
        self.ANGULAR_SPEED = 0.5
        self.current_twist = Twist()
        

        self.timer = self.create_timer(0.1, self.timer_callback)
        

        self.action_timer = None 
        self.is_moving = False
        
        self.get_logger().info("Motor Controller gotowy. Oczekuję na AI...")

    def command_callback(self, msg):
        #Odbiera komendę np. 'DRIVE 1.5' lub samo 'LEFT'."""
        parts = msg.data.upper().split()
        command = parts[0] if len(parts) > 0 else "STOP"
        
        # Domyślny czas jeśli model podał samo słowo bez liczby (np. LFM)
        duration = 1.5 
        if len(parts) > 1:
            try:
                duration = float(parts[1])
            except ValueError:
                pass

        if command == "DRIVE":
            self.current_twist.linear.x = self.LINEAR_SPEED
            self.current_twist.angular.z = 0.0
            self.start_movement(duration, command)
            
        elif command == "LEFT":
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = self.ANGULAR_SPEED
            self.start_movement(duration, command)
            
        elif command == "RIGHT":
            self.current_twist.linear.x = 0.0
            self.current_twist.angular.z = -self.ANGULAR_SPEED
            self.start_movement(duration, command)
            
        elif command == "STOP":
            self.stop_robot()
        else:
            self.get_logger().warning(f"Nieznana komenda: {command}")
            self.stop_robot()
            
    def start_movement(self, duration, cmd_name):
        #Uruchamia ruch i ustawia budzik (timer) na jego zakończenie
        self.get_logger().info(f"Wykonuję: {cmd_name} przez {duration}s")
        
        self.is_moving = True
        self.publish_state("MOVING")
        
        # Jeśli poprzedni timer jeszcze jest kasujemy go
        if self.action_timer is not None:
            self.action_timer.cancel()
            
        # Ustawiamy jednorazowy timer, który wywoła stop_robot po 'duration' sekundach
        self.action_timer = self.create_timer(duration, self.action_timer_callback)

    def action_timer_callback(self):
        #Po duration
        # Od razu kasujemy timer, żeby wywołał się tylko raz
        if self.action_timer is not None:
            self.action_timer.cancel()
            self.action_timer = None
            
        self.get_logger().info("Czas minął. Zatrzymuję...")
        self.stop_robot()

    def stop_robot(self):
        #Zatrzymuje silniki i wysyła sygnał STOPPED do /ai_command
        self.current_twist.linear.x = 0.0
        self.current_twist.angular.z = 0.0
        
        if self.action_timer is not None:
            self.action_timer.cancel()
            self.action_timer = None

        if self.is_moving:
            self.is_moving = False
            
        self.publish_state("STOPPED")

    def publish_state(self, state_str):
        msg = String()
        msg.data = state_str
        self.state_publisher_.publish(msg)

    def timer_callback(self):
        self.publisher_.publish(self.current_twist)

def main(args=None):
    rclpy.init(args=args)
    node = MotorControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.current_twist = Twist()
        node.publisher_.publish(node.current_twist)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
