# Manjaro 7.5pt顶部版同步

状态：7.5pt顶部版已提交并完成Manjaro离线同步；写后清单回读和双份备份校验通过，目标桌面仍待实际登录验收。

目标分区UUID为8da176d5-670d-4459-8019-336431ea9c85，当前挂载/media/gy_ubuntu/plasma5。沿用用户已授权的root桌面，更新/root/.config/conky/classic-tree；不向mjr再次部署、不改SDDM、显示缩放、驱动或引导。

顶部版使用7.5pt中文粗体、左侧树干向右分支、五列共享主干。root_session_start.py保持字体准备与30秒登录延迟，之后运行top_start.py，拥有自己的单一采集器和Conky，与旧竖版共用单实例锁。target配置layout设为top，其余本地设置保留；固定Xinerama0并校验eDP-1，Plasma Wayland继续使用KScreen映射，失败不换屏。

保留目标原主题脚本及自启动入口，指向相同root_session_start.py路径。字体文件和日志不变。同步前将旧source整份备份到本机、D盘及目标事务目录，校验后再原子替换；失败恢复旧source。正式回退入口位于目标/root/.local/state/conky-top-sync/<事务时间>/rollback.py，恢复本轮前source；若源文件已被用户另行修改则停止而不覆盖。

Ubuntu当前对照继续，不因Manjaro部署而改其安装或自启。基础、顶部及Plasma模拟测试和独立采集/清理检查在Ubuntu通过；Manjaro仅做离线校验，须下次进入后验收字体、完整信息、顶栏间距、固定0号屏和窗口置底。

## 本次部署结果

- 源码检查点：`cba7341`（布局功能提交`9be7374`）。85项回归通过，正式顶部入口独立采集/生成配置/清理子进程检查通过。
- 事务：`20261108-050233`。27份payload文件逐一回读匹配；目标本地配置仅将layout从classic改为top，其他值保留。
- 原三个启动/主题文件和Noto字体散列前后相同；仅原子替换root的classic-tree程序目录。未启动目标程序或重启系统。
- 本机备份：`/home/gy_ubuntu/Conky7p5发布与Manjaro同步备份-20261108-050233`；D盘：项目`backups/release-top-7p5-20261108-050233`。原目标源码归档SHA-256在两处一致，验证记录为final-verification.json。
- 本轮回退：在Manjaro root终端运行 `python3 /root/.local/state/conky-top-sync/20261108-050233/rollback.py`。只恢复本轮前source；遇到后续用户修改会停止，原字体/自启动和其他桌面设置不动，仍由用户手动重登。

实际进入Manjaro后，首先检查原自启动是否只产生一个顶部窗口、固定0号匹配、7.5pt可读性和顶栏间距，再核对GPU/内存/硬盘/网络。当前Ubuntu1750×180px只作为该Ubuntu会话的实测，不能直接写成Manjaro已显示的尺寸。

## 2026-11-22 内存 GiB 同步

已将源码提交 `ee7fa3c` 中的 `classic.py` 与 `top_tree.py` 同步到 Manjaro root 现有安装，内存已用与总量均显示GiB。写入前核对原 `cba7341` 文件散列，写后两文件散列回读匹配；原本地配置、旧启动脚本和自启动条目不变。85项跨平台模拟测试通过。

目标写前文件双份备份并校验：`/home/gy_ubuntu/Conky-Manjaro-GiB同步备份-20261122-001835` 和项目 `backups/manjaro-gib-20261122-001835`。目标回退仅恢复这两个文件：`python3 /root/.local/state/conky-gib-sync/20261122-001835/rollback.py`；若文件后来被修改则停止，不覆盖用户修改。

此次是离线同步，尚未进入 Manjaro 桌面验证显示或自启动，不改变固定0号及eDP-1约束。
