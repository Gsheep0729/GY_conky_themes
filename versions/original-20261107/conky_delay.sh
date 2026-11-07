#!/bin/bash
# 给 GNOME 桌面和 XWayland 留出初始化时间；不改变 Conky 显示配置。
sleep 30
exec /usr/bin/conky -c /home/gy_ubuntu/.conky/conky/nvidia_conkyrc
