# Manjaro Plasma：替换已有 root Conky

当前目标是 root 原主题 `/root/.config/conky/manjaro_conkyrc`，原启动脚本 `/root/.config/conky/start_conky.sh`，原自启动 `/root/.config/autostart/start_conky.sh.desktop`。SDDM实际自动登录root，用户已明确允许沿用该账户运行Conky。本次只处理Conky，不更改SDDM、登录账户、显示布局/缩放、驱动或引导。

此前误投到mjr账户的配置、自启、字体和应用状态已备份并移入目标系统的root替换事务quarantine，不再从原路径启动。这里记录实际替换，不能再将mjr那次新增部署当作原主题替换完成。

## 替换行为

本轮同步目标改为已接受的7.5pt顶部连通树：左侧树干、分支向右、五列共享主干，内存已用/总量。独立正式入口为`top_start.py`，不依赖Ubuntu预览缓存；同步结果见项目 `MANJARO-TOP-SYNC-20261108.md`。此前a15f7dd竖版保留作回退。原启动脚本和原自启条目继续进入 `root_session_start.py`，再进入顶部正式启动器；没有另加一份root自启条目。先准备同款Noto CJK用户字体，延迟30秒，再启动采集和Conky。

若KDE恢复上次会话的旧Conky命令，只对配置路径精确等于原 `manjaro_conkyrc` 的同账户Conky发送终止信号，使用pidfd避免PID重用；其他Conky配置和应用不受影响。

屏幕仍严格固定Xinerama 0号并校验eDP-1内屏。Plasma Wayland若使用XWAYLAND伪名称，读取KScreen的完整活动布局映射，支持整体2倍比例。0号是外屏、内屏关闭、镜像歧义或无法校验时停止，不自动改号/换屏。目标Conky 1.22.3显式使用X11/XWayland后端。

## 测试与验收

```bash
python3 platforms/manjaro-plasma/run_tests.py
```

在临时目录应用最小启动器适配，运行基础与Plasma/root入口测试。Ubuntu上的模拟测试和离线文件哈希不等同Manjaro会话验收。仍需进入Manjaro确认原主题已被替换、字体/透明/置底、固定0号匹配及实际数据。

## 回退

写前完整备份、原三份文件快照及新包在本次本机/D盘事务目录。目标系统 `/root/.local/state/conky-root-replacement/<时间戳>/rollback.py` 可恢复原配置、脚本和原自启；下次登录使用旧版。新源码/字体/日志保留，误装的mjr自启保持撤回。准确路径见部署记录。此原位替换不使用通用manage.py卸载入口。

`rollback_root.py` 会按自身路径定位目标根并确认Manjaro，限定恢复清单中的三份原文件，校验备份哈希并恢复原权限/所有权，不会写入当前Ubuntu的/root。

接口依据：[KScreen JSON](https://github.com/KDE/libkscreen/blob/master/src/configserializer.cpp)、[输出逻辑几何](https://github.com/KDE/libkscreen/blob/master/src/output.cpp)。

本轮7.5pt同步回退使用 `/root/.local/state/conky-top-sync/<事务时间>/rollback.py`，只恢复上一个已安装source；更早的root原主题回退工具仍保留，二者不要混用。
