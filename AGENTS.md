# AGENTS.md — Conky 项目执行入口

## 当前定稿与状态（2026-11-08）

用户暂时接受顶部五列 **7.5pt** 版本，要求提交Git并同步Manjaro。不要退回被否决的无树线列表、五棵分离的小树或5pt版本。

- 五列从左到右：系统、CPU/GPU、内存/网络、硬盘1、硬盘2；所有左侧树干连接同一根横向主干，分支朝右，文字左对齐。根分区是共同主干最后一条分支，不冒充某块物理盘的子项。
- Noto Sans CJK SC粗体7.5pt，青色标题、白色正文、透明且位于桌面底层。当前Ubuntu两倍缩放实测1750×180px，顶栏下8px、右侧30px；其他环境必须重新测量，不能硬编码这组像素。
- 保留现有信息：运行时间、系统/内核、CPU占用、GPU可见状态及占用、内存已用GB/总GB、硬盘型号/读写/温度/根分区、物理网卡总上下速率。无时钟日期、CPU型号/温度、额外GPU细项或IP。
- Ubuntu：已安装的竖版和自启动仍保留；横向版是独立对照预览，复用竖版缓存，不新增采集器。用户本次要求Git提交和Manjaro同步，未要求结束Ubuntu对照或修改其自启动。
- Manjaro：用户已明确授权沿用现有root桌面运行Conky。目标是root现有入口，不是mjr。同步完成与否以 `MANJARO-TOP-SYNC-20261108.md` 及事务结果为准；离线文件部署不等于目标桌面实测。

## 实现与兼容边界

`portable/classic.py` 保留旧竖版；`top_tree.py`负责7.5pt横向显示，`preview_top.py`只负责对照。`top_start.py`是独立正式启动器，拥有一个采集器和一个Conky，和竖版共用单实例锁，不能依赖Ubuntu的预览缓存。

既有配置字段 `layout` 支持classic/top，默认classic不变；top采集只写JSON，由顶部显示器渲染。`start.py`可将top配置转交正式顶部入口。Manjaro的root_session_start.py先准备已有字体缓存、延迟30秒，再进入top_start.py并显式使用X11/XWayland后端。

固定Xinerama 0号且必须对应eDP-1；不匹配就停止，不改号或向外屏回退。Plasma Wayland保留已有KScreen几何校验。字体、DPI和列宽用Xft实测；长内容换行，不丢字段，不用空格凑列，不改变监控口径。

核显fdinfo仍是本用户渲染活动，不能称整卡利用率；不相加引擎、不用频率冒充占用、不填假0。独显挂起不唤醒读取。内存用原MemAvailable口径、十进制GB，两位小数。网络排除VPN/虚拟设备重复计数，公网查询默认关闭。Ubuntu不以root运行；root例外只适用于用户已授权的Manjaro目标。

## 路径与操作

- 项目：`/media/gy_ubuntu/铠侠D/ubuntu/ubuntu美化macos/conky-fedora-tree/conky`；原版文件、媒体和Git历史保留。
- Ubuntu运行源：`/home/gy_ubuntu/.config/conky/classic-tree`。当前横向预览副本和截图：`/home/gy_ubuntu/Conky顶部五列预览备份-20261108-033019`。
- Manjaro分区UUID：`8da176d5-670d-4459-8019-336431ea9c85`，通常挂载于`/media/gy_ubuntu/plasma5`。写前重新核对真实挂载、UUID、rw和os-release；不能只信目录名。
- 目标运行源：`/root/.config/conky/classic-tree`。保留原 `/root/.config/conky/start_conky.sh` 和 `/root/.config/autostart/start_conky.sh.desktop` 入口；不再向mjr部署第二份自启。
- 本轮发布备份：`/home/gy_ubuntu/Conky7p5发布与Manjaro同步备份-20261108-050233`；D盘副本为项目`backups/release-top-7p5-20261108-050233`。具体文件清单、SHA-256和回退随事务保存，不提交备份/运行缓存/个人数据到Git。

## 备份、权限与验证

真实写入前说明目标和差异，先做本机与D盘双份备份并校验。目标root文件需要的最小写入合并为一次有终点的管理员事务；不收集密码、不设置免密sudo、不为普通读写反复提权。

只修改Conky；不改登录账户、SDDM、字体全局设置、Dock/扩展、网络、显示缩放、引导、EFI、驱动或分区。不自动重启或注销。Manjaro同步只在离线目标执行文件替换，不在Ubuntu启动目标root程序。

验证命令：`python3 platforms/manjaro-plasma/run_tests.py`；同时验证正式顶部入口能用隔离运行目录独立采集、生成配置并清理子进程。当前Ubuntu视觉、模拟Plasma测试、离线哈希分别记录，不能互相冒充。目标登录后仍须实测0号屏、顶栏间距、透明/置底、字体和完整信息。

Git使用独立提交，不重写历史或覆盖旧标签；本次提交/推送已由用户授权。后续重大视觉更改继续先做候选对照。既有版本：原版f15873e、兼容候选457197a、简约竖版a15f7dd、Ubuntu启用b4468be、内存已用/总量修正c7b352d。

本文件是项目唯一agent指令入口；不要另建小写agent.md。其他工作区的macOS/GRUB历史不属于本项目任务。
