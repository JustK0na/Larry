import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro

def generate_launch_description():
    pkg_name = 'Larry'
    pkg_share = get_package_share_directory(pkg_name)

    xacro_file = os.path.join(pkg_share, 'urdf', 'larry_bot.urdf.xacro')
    robot_desc = xacro.process_file(xacro_file).toxml()

    # Ścieżka do Twojego skopiowanego pliku świata
    world_file = os.path.join(pkg_share, 'worlds', 'empty_world.sdf')

    # Wywołanie domyślnego skryptu startowego Gazebo
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ),
        # Flaga -r uruchamia symulację od razu (bez pauzy)
        launch_arguments={'gz_args': f'-r {world_file}'}.items()
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-name', 'larry', '-string', robot_desc, '-z', '0.15'],
        output='screen'
    )
    ros_gz_bridge = Node (
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            # Zegar (Gazebo -> ROS 2)
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            # Prędkość (ROS 2 -> Gazebo)
            '/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist',
            # Odometria (Gazebo -> ROS 2)
            '/model/larry/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry',
        ],
        remappings=[
            # Zmiana długiej nazwy z Gazebo na standardowe /odom w ROS 2
            ('/model/larry/odometry', '/odom'),
        ],
        output='screen'
    )

    return LaunchDescription([
        gazebo,
        spawn_robot,
        ros_gz_bridge
    ])
#gemini generated
