# Manjaro 7.5pt顶部版同步

状态：源码已准备并测试，目标离线同步待执行；完成后在本记录补充事务结果。

目标分区UUID为8da176d5-670d-4459-8019-336431ea9c85，当前挂载/media/gy_ubuntu/plasma5。沿用用户已授权的root桌面，更新/root/.config/conky/classic-tree；不向mjr再次部署、不改SDDM、显示缩放、驱动或引导。

顶部版使用7.5pt中文粗体、左侧树干向右分支、五列共享主干。root_session_start.py保持字体准备与30秒登录延迟，之后运行top_start.py，拥有自己的单一采集器和Conky，与旧竖版共用单实例锁。target配置layout设为top，其余本地设置保留；固定Xinerama0并校验eDP-1，Plasma Wayland继续使用KScreen映射，失败不换屏。

保留目标原主题脚本及自启动入口，指向相同root_session_start.py路径。字体文件和日志不变。同步前将旧source整份备份到本机、D盘及目标事务目录，校验后再原子替换；失败恢复旧source。正式回退入口位于目标/root/.local/state/conky-top-sync/<事务时间>/rollback.py，恢复本轮前source；若源文件已被用户另行修改则停止而不覆盖。

Ubuntu当前对照继续，不因Manjaro部署而改其安装或自启。基础、顶部及Plasma模拟测试和独立采集/清理检查在Ubuntu通过；Manjaro仅做离线校验，须下次进入后验收字体、完整信息、顶栏间距、固定0号屏和窗口置底。
