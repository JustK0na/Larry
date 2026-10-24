#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.parameter import Parameter

import math


class sub(Node):
    def __init__(self):
        super().__init__('nasluch')
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0

        self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.start_time = self.get_clock().now().nanoseconds / 1e9
        self.timer = self.create_timer(0.05, self.control_loop)

        self.plik_bledow = open('bledy_sledzenia.dat', 'w')
        self.plik_bledow.write("# Czas xe ye theta_e\n")
        
    def odom_callback(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y

        q = msg.pose.pose.orientation
        self.theta = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        

    def control_loop(self):
        current_time = self.get_clock().now().nanoseconds / 1e9
        t = current_time - self.start_time
        #obliczanie trajektorii
        A = 2.0
        w = 0.2
        xd = A * math.sin(w * t)
        yd = A * math.sin(w * t) * math.cos(w * t)

        xd_dot = A * w * math.cos(w * t)
        yd_dot = A * w * (math.cos(w * t)**2 - math.sin(w * t)**2)
        xd_ddot = -A * w**2 * math.sin(w * t)
        yd_ddot = -A * w**2 * 4 * math.sin(w * t) * math.cos(w * t)
        
        vd = math.sqrt(xd_dot**2 + yd_dot**2)
        th_d = math.atan2(yd_dot, xd_dot)
        omega_d = (xd_dot * yd_ddot - yd_dot * xd_ddot) / (vd**2) if vd > 0.001 else 0.0


        #bledy
        dx = xd - self.x
        dy = yd - self.y
        dth = math.atan2(math.sin(th_d - self.theta), math.cos(th_d - self.theta))
        
        #do ukladu robota
        xe = math.cos(self.theta) * dx + math.sin(self.theta) * dy
        ye = -math.sin(self.theta) * dx + math.cos(self.theta) * dy
        the = dth
        
        self.plik_bledow.write(f"{t:.4f} {xe:.4f} {ye:.4f} {the:.4f}\n")
        
        if abs(the) < 1e-5:
            sinc_term = 1.0
        else:
            sinc_term = math.sin(the) / the
            

        k1 = 1.0
        k2 = 2.0
        
        v_r = k1 * xe + vd * math.cos(the)
        omega_r = omega_d + k2 * the + vd * ye * sinc_term
        

        cmd = Twist()
        cmd.linear.x = v_r
        cmd.angular.z = omega_r
        self.cmd_pub.publish(cmd)

    def destroy_node(self):
        self.plik_bledow.close()
        super().destroy_node()

def main():
    rclpy.init()
    wezel = sub()
    rclpy.spin(wezel)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
    



    
