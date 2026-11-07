# Manjaro Plasma：固定0号内屏适配

基于已选定的树线简约显示 `a15f7dd`，不改变 `portable/classic.py` 或采集器。目标部署到用户目录，自动启动先补用户字体缓存，再执行原30秒延迟启动器。

## 行为

用户明确选择固定 Xinerama 0号，不自动识别后换号。正常 Xorg 名称校验保持；Plasma Wayland 的 XWayland 若没有真实 eDP-1 名称，则只读 `kscreen-doctor -j`，将完整活动输出布局映射到 Xinerama 坐标，支持整体2倍比例。只有0号与eDP-1内屏一致才启动；内屏关闭、镜像歧义、解析失败或0号是外屏都停止。不会修改KWin布局/缩放/主屏。

目标 Conky 1.22.3 同时提供X11/Wayland后端，适配明确开启X11并关闭原生Wayland输出，使用XWayland承载现有配置。不启用其他扩展或服务，不改驱动或引导。

`session_start.py` 仅首次为 `~/.local/share/fonts/conky-noto-cjk` 的同款 Noto CJK 字体刷新用户缓存，随后 exec 原启动器，不增加常驻服务。字体及许可证部署在用户字体目录，不更改系统字体设置。

## 重现测试

```bash
python3 platforms/manjaro-plasma/run_tests.py
```

在临时目录应用 `build_profile.py` 的最小启动器补丁，再运行原54项及Plasma10项测试。当前64项通过是在Ubuntu执行的模拟/回归测试，不能当作Manjaro实际显示验收。

本次已离线部署到挂载根 `/media/gy_ubuntu/plasma5` 的 `mjr` 用户，运行时路径使用 `/home/mjr`，不依赖该挂载名或D盘。源码/字体/配置哈希已回读；实际登录、自启、固定0号匹配、透明/置底、GPU及传感器仍待进入Manjaro验收。

在Manjaro诊断：`python3 ~/.config/conky/classic-tree/start.py --doctor`。若0号不是内屏，按用户选择停止；不要据此去掉安全匹配或自动改屏。

撤销自启：在Manjaro运行 `python3 ~/.config/conky/classic-tree/manage.py uninstall`，保留源码/字体/日志。不要从Ubuntu直接运行目标用户的安装/回退程序，以免误用当前HOME。

接口依据：[KScreen JSON序列化](https://github.com/KDE/libkscreen/blob/master/src/configserializer.cpp)、[输出逻辑几何](https://github.com/KDE/libkscreen/blob/master/src/output.cpp)。
