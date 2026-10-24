clear node;
node = ros2node("/matlab_figure8_controller");
odomSub = ros2subscriber(node, "/odom", "nav_msgs/Odometry");
cmdPub = ros2publisher(node, "/cmd_vel", "geometry_msgs/Twist");
cmdMsg = ros2message(cmdPub);
A = 2.0;            
omega_traj = 0.2;   
K1 = 1.0; 
K2 = 2.0; 
rate = ros2rate(node, 20); 
tic; 

while true
    odomMsg = odomSub.LatestMessage;
    if ~isempty(odomMsg)
        x = odomMsg.pose.pose.position.x;
        y = odomMsg.pose.pose.position.y;

        quat = [odomMsg.pose.pose.orientation.w, ...
            odomMsg.pose.pose.orientation.x, ...
            odomMsg.pose.pose.orientation.y, ...
            odomMsg.pose.pose.orientation.z];
        angles = quat2eul(quat);
        theta = angles(1);

        t = toc;

        xd = A * sin(omega_traj * t);
        yd = A * sin(omega_traj * t) * cos(omega_traj * t);

        xd_dot = A * omega_traj * cos(omega_traj * t);
        yd_dot = A * omega_traj * (cos(omega_traj * t)^2 - sin(omega_traj * t)^2);

        xd_ddot = -A * omega_traj^2 * sin(omega_traj * t);
        yd_ddot = -A * omega_traj^2 * 4 * sin(omega_traj * t) * cos(omega_traj * t);

        vd = sqrt(xd_dot^2 + yd_dot^2);
        th_d = atan2(yd_dot, xd_dot);

        if vd > 0.001
             omega_d = (xd_dot * yd_ddot - yd_dot * xd_ddot) / (vd^2);
        else
            omega_d = 0.0;
        end

        dx = x - xd;
        dy = y - yd;
        dth = angdiff(th_d, theta);

        Eref_1 = cos(theta) * dx + sin(theta) * dy;
        Eref_2 = -sin(theta) * dx + cos(theta) * dy;
        Eref_3 = dth;

        if abs(Eref_3) < 1e-5
            sinc_term = 1.0;
        else
            sinc_term = sin(Eref_3) / Eref_3;
        end

        v = vd * cos(Eref_3) - K1 * Eref_1;
        omega = omega_d - vd * Eref_2 * sinc_term - K2 * Eref_3;

        cmdMsg.linear.x = v;
        cmdMsg.angular.z = omega;
        send(cmdPub, cmdMsg);
    end
    waitfor(rate); 
end