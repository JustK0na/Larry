#!/usr/bin/env python3
import json
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

        # Twarde ograniczenia sprzętowe 
        self.MAX_LINEAR_SPEED = 5
        self.MAX_ANGULAR_SPEED = 5.0
        self.MIN_DURATION = 0.5
        self.MAX_DURATION = 3.0

        self.current_twist = Twist()
        self.timer = self.create_timer(0.1, self.timer_callback)

        self.action_timer = None
        self.is_moving = False

        self.get_logger().info("Motor Controller (JSON) gotowy. Oczekuję na AI...")

    def command_callback(self, msg):
        raw_data = msg.data.strip()

        # Próba parsowania JSON (nowy protokół dla Qwena i LFM)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            # Kompatybilność wsteczna np. dla ręcznego wysłania "STOP" z terminala
            if raw_data.upper().startswith("STOP"):
                self.stop_robot()
                return
            self.get_logger().error(f"Niepoprawny JSON na /ai_command: '{raw_data}'")
            self.stop_robot()
            return

        action = str(data.get("action", "stop")).lower()

        if action == "move":
            try:
                linear_x = float(data.get("linear_x", 0.0))
                angular_z = float(data.get("angular_z", 0.0))
                duration = float(data.get("duration", 1.0))
            except (TypeError, ValueError) as e:
                self.get_logger().error(f"Błędne wartości liczbowe w komendzie: {data} ({e})")
                self.stop_robot()
                return

            # Sprzętowy clamping
            linear_x = max(-self.MAX_LINEAR_SPEED, min(self.MAX_LINEAR_SPEED, linear_x))
            angular_z = max(-self.MAX_ANGULAR_SPEED, min(self.MAX_ANGULAR_SPEED, angular_z))
            duration = max(self.MIN_DURATION, min(self.MAX_DURATION, duration))

            self.current_twist.linear.x = linear_x
            self.current_twist.angular.z = angular_z
            self.start_movement(duration, f"MOVE(v={linear_x:.2f}, w={angular_z:.2f})")

        elif action == "stop":
            self.stop_robot()
        else:
            self.get_logger().warning(f"Nieznana akcja w JSON: {action}")
            self.stop_robot()

    def start_movement(self, duration, cmd_name):
        self.get_logger().info(f"Wykonuję: {cmd_name} przez {duration:.2f}s")

        self.is_moving = True
        self.publish_state("MOVING")

        if self.action_timer is not None:
            self.action_timer.cancel()

        self.action_timer = self.create_timer(duration, self.action_timer_callback)

    def action_timer_callback(self):
        if self.action_timer is not None:
            self.action_timer.cancel()
            self.action_timer = None

        self.get_logger().info("Czas minął. Zatrzymuję...")
        self.stop_robot()

    def stop_robot(self):
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
