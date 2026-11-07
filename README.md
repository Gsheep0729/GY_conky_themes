# Conky：7.5pt顶部连通树与跨Linux采集

用户暂时接受当前顶部五列版：**7.5pt中文粗体、文字左对齐、左侧树干向右分支、五列共用一根主干**。当前Ubuntu两倍缩放实测1750×180像素；列宽随实际字体测量，不硬编码到其他机器。

显示运行时间、系统/内核、CPU占用、GPU可见状态和占用、内存已用/总GB、两块硬盘型号/读写/温度及根分区、物理网卡总上下速率。核显标注本用户渲染活动；不显示IP，不主动唤醒挂起独显。

Ubuntu仍保留原竖版和横向对照；本轮提交源码并同步Manjaro，不替换Ubuntu自启动。Manjaro使用现有root桌面和原自启入口，独立启动采集器与顶部窗口；离线同步状态见记录，目标会话仍待实测。

- [项目执行入口](AGENTS.md)
- [顶部版与通用安装说明](portable/README.md)
- [顶部布局验证](TOP-FIVE-PREVIEW-20261108.md)
- [Manjaro同步与回退](MANJARO-TOP-SYNC-20261108.md)
- [Manjaro Plasma专用说明](platforms/manjaro-plasma/README.md)
- [旧Ubuntu竖版启用及回退](UBUNTU-ACTIVATION-20261108.md)
- [原版快照](versions/original-20261107/README.md)

```bash
python3 platforms/manjaro-plasma/run_tests.py
python3 portable/start.py --doctor
```

正式顶部入口为`portable/top_start.py`，比较入口为`portable/preview_top.py`。既有配置字段layout支持classic/top，默认classic不变。采集依赖Python标准库，显示依赖现有Conky、X11/XWayland、Xft和Noto CJK；无DISPLAY的纯Wayland不支持。固定0号屏匹配失败时停止，不能自动换到外屏。

原始主题、图片/视频/ZIP和既有Git历史保留。历史配置中的sudo smartctl、公网查询与固定硬件名只作参考，不恢复到新运行流程。新机器默认普通用户运行，Manjaro现有root桌面是本用户明确授权的例外。

源码及说明纳入Git；备份、截图、运行日志和生成发行归档不纳入Git。当前Manjaro实际显示及其他发行版/桌面组合仍需实机验收。
