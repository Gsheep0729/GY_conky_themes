# Conky：原版树状 UI 与兼容候选

当前Ubuntu已正式启用 `portable/` 的树线简约版，左右对比结束，仅保留一个实例及单一30秒自启。原中文粗体、运行时间标题、颜色和右侧树干沿用，大时钟和日期已移除。旧配置及原自启已备份，可逐项回退。

候选CPU只显示占用率，GPU显示可见状态与各卡占用，内存仅显示已用GB；核显使用本用户渲染活动百分比。网络只显示下载/上传总速率，按物理网卡汇总，不列网卡/主机/IP/VPN信息。公网查询默认关闭。

- [候选说明与跨发行版安装、回退](portable/README.md)
- [实际原版运行快照](versions/original-20261107/README.md)：本地 Git 提交 `f15873e`，含校验清单。
- [Ubuntu正式启用与回退](UBUNTU-ACTIVATION-20261108.md)
- [实施与验收记录](IMPLEMENTATION-20261107.md)
- [已完成的字体、Dock、GPaste 验收](NON-CONKY-ACCEPTANCE-20261107.md)

`nvidia_conkyrc`、`manjaro_conkyrc.txt`、旧 `start_conky.sh`、主题视频/图片、原始ZIP及既有Git历史均保留。旧配置包含固定设备名、sudo smartctl和公网查询命令，作为历史参考；新机器使用候选说明，不以root运行Conky。

```bash
cd portable
python3 start.py --doctor
python3 start.py --preview --delay 0 --preview-seconds 0
python3 -m unittest discover -s tests -v
```

其他机器先确认 Xinerama 编号和目标连接器。Manjaro、KDE、Xfce和Ubuntu Xorg仍需实机验收，不能把当前Ubuntu Wayland和模拟测试当作全部平台通过。

源码、原版快照和说明使用Git管理；生成的发行归档、双份事务备份与运行诊断不纳入Git。没有向远端推送。

本轮简约显示是在上一候选 `457197a` 上的独立提交，采集器/启动器未改。54项测试及实际窗口检查通过；硬盘和网络输出保持一致，左侧窗口由721px缩短至529px。此前该阶段仅做预览；2026-11-08用户已授权并完成Ubuntu正式替换及自启切换。

Manjaro Plasma 实际自动登录root，已按用户明确授权原位替换/root中的旧主题/启动脚本/原自启，并撤回此前误装的mjr版本。固定0号屏和回退见 [专用说明](platforms/manjaro-plasma/README.md)。目标会话仍待实机验收。
