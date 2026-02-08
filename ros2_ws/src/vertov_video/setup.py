from setuptools import find_packages, setup
import os

package_name = 'vertov_video'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/srv', ['srv/StartRecording.srv']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    author='User',
    author_email='user@example.com',
    maintainer='User',
    maintainer_email='user@example.com',
    description='Vertov distributed video recording agent',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'video_agent = vertov_video.video_agent:main',
        ],
    },
)