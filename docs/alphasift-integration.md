# AlphaSift 选股集成

AlphaSift 以最小方式接入 DSA：默认关闭，开启后 Web 侧显示“选股”页签，并通过后端直接调用本地 Python 包的 `alphasift.screen()`。关闭后左侧导航不显示“选股”页签，直接访问 `/screening` 时仍会显示未开启提示。

## 开启

可以直接设置环境变量：

```bash
ALPHASIFT_ENABLED=true
ALPHASIFT_INSTALL_SPEC=git+https://github.com/ZhuLinsen/alphasift.git
```

也可以在 Web 设置页的 AlphaSift 选股卡片中点击“开启选股”，该操作会写入
`ALPHASIFT_ENABLED=true`、重新加载运行时配置，并按 `ALPHASIFT_INSTALL_SPEC`
执行一次自动安装或可用性检查。

`ALPHASIFT_INSTALL_SPEC` 是传给 pip 的安装参数，默认从 GitHub 安装：

```bash
python -m pip install git+https://github.com/ZhuLinsen/alphasift.git
```

如需使用本地开发版本，也可以改成本地路径或 wheel 文件，例如：

```bash
python -m pip install -e /path/to/alphasift
```

## 接口

```text
GET  /api/v1/alphasift/status
POST /api/v1/alphasift/screen
```

请求示例：

```json
{
  "market": "cn",
  "strategy": "dual_low",
  "max_results": 20
}
```

当前不做通用插件系统、插件市场、CLI/Bot/Scheduler/MCP 集成，也不新增持久化表。DSA 只负责开关、页签、接口透传和结果展示；策略、数据处理与排序逻辑仍由 AlphaSift 自身负责。

## 风险提示

AlphaSift 选股结果仅用于研究和辅助判断，不构成投资建议；市场有风险，交易决策和损益由使用者自行承担。
