# 原版树状 UI：跨 Linux 兼容候选

当前运行配置仍是原版。此前重排的 UI 已撤回；本候选直接继承 `original-template.conf` 的中文粗体、大时钟、运行时间标题、颜色、透明窗口、边距和右侧树干，不再应用 Inter 或等宽字体，也不自动缩小字体。核显按用户最新反馈只保留一行百分比，原有模块顺序保持。

## 已完成的改动

- 一个普通用户 Python 采集进程写入缓存，Conky 用内置 `catp` 读取，不在绘图时运行 sudo、smartctl、sensors、curl 或 nvidia-smi。
- CPU/NVMe 温度读取用户可读 hwmon，跳过故障/停用传感器；AMD优先Tdie，多CPU包取最高包温，常见ARM CPU thermal zone可降级读取。没有可靠传感器显示不可用。磁盘按当前sysfs自动识别，以型号/稳定ID排序；设备重连、diskseq变化或计数回退后重新建立速率基线。支持NVMe、SATA、virtio、Xen及eMMC常见名称，排除loop和dm/md聚合层避免重复。
- GPU 按 PCI 实际枚举，不把模块加载状态当作 MUX 模式。核显界面只显示一行“核显渲染（本用户）”百分比；详细引擎计数仍保留在诊断缓存，不在界面展开。该值不是完整整卡利用率。别名 fdinfo 去重，处理进程退出、计数回退和权限不足。
- iGPU 目标约5秒（电池10秒），受2秒采集循环影响有不足2秒的调度延迟。NVIDIA 单独限频至少10秒，先确认设备 active 才查询，挂起/未接管时不会调用 nvidia-smi；活动/挂起/无驱动使用相同固定行数。
- 网络按最新选择只显示一行下载/上传总速率。按sysfs中带device的物理网卡汇总，排除VPN/TUN、veth、bridge、bond聚合及回环；不列网卡、主机名和IP。网卡发现/计数不依赖ip、ifconfig或NetworkManager。接口重建/计数回退重新采样；缺任一接口计数时相应方向显示“—”，不冒充完整总速率。纯容器没有物理接口时显示不可用。
- 公网IP查询默认关闭。界面不显示IP；相关可选查询仅供主动开启时的诊断缓存。
- CPU计数兼容常见旧字段及ARM型号格式，guest不重复计入；内存缺MemAvailable时使用旧字段估算。单个采集模块异常只影响该模块，其余继续，错误种类写入诊断。
- 固定 Xinerama 编号且校验连接器；内屏关闭或编号不再对应时停止，不移到外屏。采集超过15秒不更新时启动器停止自己的子进程，不展示失效指标、不循环重启。

## 先诊断、预览

依赖 Python 3.9+、Conky（X11/Xft/Xinerama 与 Lua 新配置格式）、fontconfig、Noto Sans CJK SC、X11 或 XWayland；可选 `pciutils` 提供友好的GPU型号。没有 DISPLAY 的纯 Wayland 不能运行这份 X11 配置。包名请以目标发行版仓库为准，不以 root 运行 Conky。

Ubuntu 常见包：`conky-all python3 pciutils fontconfig fonts-noto-cjk x11-xserver-utils`。
Manjaro/Arch 常见包：`conky python pciutils fontconfig noto-fonts-cjk xorg-xrandr`。

```bash
python3 start.py --doctor
python3 start.py --check --delay 0
python3 start.py --preview --delay 0 --preview-seconds 300
```

预览放在内屏原版左侧，默认5分钟自动关闭；使用 `--preview-seconds 0` 则保留到手动停止或注销。不停止原版、不创建自启。预览可能临时增加 Conky/采集进程数，这是对比专用，正式启动单实例。原有阴影/描边按模板继承；本候选不另外修改它们。

每台机器先看 doctor 列出的编号。将 config.example.json 复制为 config.local.json，设置 `monitor_index` 和 `expected_connector`；本机编号0对应 eDP-1，不可照搬为其他机器的保证。没有内屏的设备应指定实际目标连接器。AMD 等角色无法可靠判断时，在 `gpu_roles` 按 PCI 地址填写 integrated/discrete，未指定则如实显示未知角色。

## 安装及回退

只有接受预览后再运行安装命令。源代码会复制到用户主目录，开机不依赖 D 盘。安装不会替换当前正在运行的 Conky；切换会话或运行进程须另行处理。

```bash
python3 manage.py install --monitor-index 0 --connector eDP-1
python3 ~/.config/conky/classic-tree/start.py --doctor
```

安装备份并移走明确启动 Conky 的旧 desktop 自启项，写一个30秒延迟启动项。诊断/日志在 `~/.local/state/conky-classic-tree`，运行数据在 `$XDG_RUNTIME_DIR/conky-classic-tree`。向本启动器发送 TERM 会清理它自己的采集和 Conky 子进程；不使用 killall。

```bash
python3 ~/.config/conky/classic-tree/manage.py uninstall
```

回退恢复安装前自启，拒绝覆盖安装后用户另改的启动项；保留源码和日志。原 `~/.conky` 文件不被安装程序覆盖。已存在安装时程序拒绝整份覆盖，需先备份、比较版本。

## 验证与边界

```bash
python3 -m unittest discover -s tests -v
```

已在 Ubuntu GNOME Wayland/XWayland 做普通用户 i915 采样。混合/独显挂起、计数异常、权限不足及内屏不匹配有模拟测试，不能冒充这些硬件模式的实测。Manjaro GNOME/KDE/Xfce、Ubuntu Xorg 的置底、透明、显示桌面及注销启动仍待实机验收。

配置视觉值回归测试只允许改变 background（由启动器管理前台进程）、text_buffer_size（容纳完整缓存）和显式 xinerama_head；字体、颜色、位置、尺寸与窗口样式均和原模板逐项比对。短时采集与预览不能代替20分钟日用验收。

接口参考：[Conky catp](https://conky.cc/variables#catp)、[内核 DRM 客户端统计](https://docs.kernel.org/gpu/drm-usage-stats.html)。
