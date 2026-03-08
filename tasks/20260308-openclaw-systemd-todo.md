# Task: memolite openclaw 子命令补齐 + Linux systemd 托管

- Task-ID: memolite-20260308-01
- Owner: coco
- Priority: P0

## 目标
1. 补齐 `memolite openclaw`：status / doctor / uninstall / configure
2. 完成 Linux `systemd` 托管：install [--enable] / enable / disable / start / stop / restart / status / uninstall

## 关键约束
- 默认端口：18731
- `serve` 保持惰性 init
- 仅 `install --enable` 或 `enable` 改自启
- `start/restart` 不得隐式 enable
- 不误删非 memolite 插件与配置
- 结论可验证（命令输出/测试结果）

## 验收
- 命令入口可用：`memolite openclaw <subcmd>` 全部可执行
- Linux service 行为符合自启策略
- README 示例与真实行为一致
- 测试通过且无回归

## 交付
- 修改文件清单
- 验证命令及输出
- `git diff --stat`
- 风险与后续项
