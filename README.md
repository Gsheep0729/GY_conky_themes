# Conky：原版树状 UI 与兼容候选

当前保留左右对比：右侧原版，左侧为 `portable/` 候选。用户选择暂不替换，原运行配置和30秒自启动完全保留；下次登录仍只启动原版。原字体、时钟、颜色和右侧树干继续沿用。

候选核显只显示一行本用户渲染活动百分比；网络只显示下载/上传总速率，按物理网卡汇总，不列网卡/主机/IP/VPN信息。公网查询默认关闭。

- [候选说明与跨发行版安装、回退](portable/README.md)
- [实际原版运行快照](versions/original-20261107/README.md)：本地 Git 提交 `f15873e`，含校验清单。
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
