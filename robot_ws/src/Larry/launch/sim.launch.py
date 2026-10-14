import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    pkg_name = 'Larry'
    pkg_share = get_package_share_directory(pkg_name)
    
    # Ścieżka do Twojego skopiowanego pliku świata
    world_file = os.path.join(pkg_share, 'worlds', 'diff_drive.sdf')

    # Wywołanie domyślnego skryptu startowego Gazebo
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ),
        # Flaga -r uruchamia symulację od razu (bez pauzy)
        launch_arguments={'gz_args': f'-r {world_file}'}.items()
    )

    return LaunchDescription([
        gazebo
    ])
#gemini generated
