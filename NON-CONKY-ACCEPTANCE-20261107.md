# 非 Conky 项重登验收结果

2026-11-07，本次实际为 GNOME Wayland 会话。

## 已通过

- GPaste 扩展及后台正常启动。用户确认 Win+V 打开历史、Esc 关闭、文本记录/搜索/选择后 Ctrl+V 粘贴正常。
- 用户确认截图能从历史选回并粘贴。最初的“不正常”已澄清为菜单没有缩略图，图片粘贴本身正常。
- 原版 Conky 可见，顶栏文字完整；Dock 浅灰背景、白色运行提示条、全屏底边唤出、手动锁屏解锁及键盘输入均由用户确认正常。
- 配置回读：Inter 11、WhiteSur-light 图标、原生 Yaru GTK/光标与默认 Shell；Dock 底部32px、智能隐藏、#d0d3d8/0.65/FIXED、白色 DASHES；BMS 使用独立动态 pipeline_gy_dock_light。
- 原 Conky 模板 SHA-256 与恢复基线相同。原版自启未变；Conky候选仅在后续本次会话中并排预览。

## 功能限制与待验

GPaste 45 的已安装 Shell 菜单只显示文字条目：图片为 Image、尺寸和时间，没有缩略图组件。本轮保持发行版包代码，不升级桌面、不向 Shell 增加图片加载补丁。图片历史功能已经通过，缩略图不能记作已实现。

桌面项20分钟后台观察已经完成，最终结果见 post-login-desktop-verification.json，手工结果见 post-login-manual-acceptance.json。

Ubuntu Xorg、Manjaro及其他桌面仍待分别实机测试。本次通过仅针对当前 GNOME Wayland 会话。旧 Clipboard Indicator 继续停用，其原历史保留且没有迁移/清空。

Conky候选使用原版UI和排版，作为独立后续阶段并排预览；此桌面验收不代替候选验收。


## 20分钟观察已完成

自动观察1201秒完成，GPaste始终ACTIVE，RSS约26→27 MiB。相关JS错误、GC和对象销毁警告计数均0。结合用户已确认的文本/图片历史、Win+V/Esc、Dock全屏/锁屏及键盘输入，本次GNOME Wayland桌面验收通过。此结论不扩展到Xorg、其他发行版或永不卡死。
