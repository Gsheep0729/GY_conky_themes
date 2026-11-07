# Ubuntu 正式启用树线简约版

用户要求当前系统也采用已确认版本。此前左右对比已结束，旧原版和预览进程均已受控停止，仅保留当前用户的正式实例。使用树线简约显示 `a15f7dd`，没有重新采用已否决的无树线草稿。

运行配置位于 `~/.config/conky/classic-tree`，单一自启动为 `~/.config/autostart/conky-classic-tree.desktop`，正常登录延迟30秒。固定Xinerama 0号并校验eDP-1，不匹配时停止，不向外屏回退。源码和运行配置在用户目录，开机不依赖项目磁盘挂载。

当前会话已核对只有一个Conky窗口及一个受管理的采集器，数据缓存及时、采集诊断为空，窗口完整位于内屏。当前显示环境为3200×2000内屏，保留原Noto字体/树线/配色，未修改系统显示缩放。真正下次登录自启仍待验收。

旧 `~/.conky/conky/nvidia_conkyrc` 和30秒脚本保持原字节，旧desktop自启已由安装器备份移走。新旧配置及自启动均有本机/D盘双份写前备份。

恢复旧自启：
```bash
python3 ~/.config/conky/classic-tree/manage.py uninstall
```
下次登录使用旧主题；源码/日志/旧原件保留，不自动注销或结束其他应用。即时回退应按受控进程清单先停止本启动器，再启动原脚本，不使用killall。

Manjaro独立保留root原主题替换，仍待其目标会话验收。此次Ubuntu启用不更改Manjaro、字体/图标/Dock设置、网络或引导。
