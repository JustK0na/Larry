% Skrypt: controller_figure8.m
% Upewnij się, że nie ma starych węzłów
clear node;

% 1. Inicjalizacja węzła ROS 2
node = ros2node("/matlab_figure8_controller");

% 2. Utworzenie subskrybenta (odometria) i publikatora (prędkość)
odomSub = ros2subscriber(node, "/odom", "nav_msgs/Odometry");
cmdPub = ros2publisher(node, "/cmd_vel", "geometry_msgs/Twist");
cmdMsg = ros2message(cmdPub);

% 3. Parametry sterownika i trajektorii
A = 2.0;            % Rozmiar ósemki
omega_traj = 0.2;   % Szybkość ruchu po trajektorii
kx = 1.0; ky = 5.0; kth = 2.0; % Zyski kontrolera Samsona

% Ustawienie częstotliwości pętli na 20 Hz
rate = ros2rate(node, 20); 

disp('Rozpoczynam jazdę po ósemce... (Wciśnij Ctrl+C, aby zatrzymać)');
tic; % Start stopera

try
    % 4. Główna pętla sterowania
    while true
        % Pobierz najnowszą wiadomość z odometrii
        odomMsg = odomSub.LatestMessage;

        if ~isempty(odomMsg)
            % Odczyt pozycji
            x = odomMsg.pose.pose.position.x;
            y = odomMsg.pose.pose.position.y;

            % Konwersja kwaternionu na kąty Eulera (Yaw)
            quat = [odomMsg.pose.pose.orientation.w, ...
                odomMsg.pose.pose.orientation.x, ...
                odomMsg.pose.pose.orientation.y, ...
                odomMsg.pose.pose.orientation.z];
            angles = quat2eul(quat);
            theta = angles(1); % Kąt obrotu wokół osi Z

            % Czas trwania
            t = toc;

            % --- GENEROWANIE TRAJEKTORII (Lemniskata) ---
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

            % --- OBLICZANIE UCHYBU ---
            dx = xd - x;
            dy = yd - y;
            dth = angdiff(theta, th_d); % Różnica kątów

            % Transformacja błędu do lokalnego układu współrzędnych robota
            ex = cos(theta) * dx + sin(theta) * dy;
            ey = -sin(theta) * dx + cos(theta) * dy;
            eth = dth;

            % --- PRAWO STEROWANIA SAMSONA ---
            v = vd * cos(eth) + kx * ex;
            omega = omega_d + vd * (ky * ey + kth * sin(eth));

            % --- WYSYŁANIE KOMENDY ---
            cmdMsg.linear.x = v;
            cmdMsg.angular.z = omega;
            send(cmdPub, cmdMsg);
        end

        % Czekaj, aby utrzymać 20 Hz
        waitfor(rate); 
    end
catch
    % Wykonuje się po wciśnięciu Ctrl+C w konsoli MATLABa
    disp('Zatrzymano skrypt. Zatrzymywanie robota...');
    cmdMsg.linear.x = 0.0;
    cmdMsg.angular.z = 0.0;
    send(cmdPub, cmdMsg);
    clear node; % Czyszczenie węzła z sieci ROS
end