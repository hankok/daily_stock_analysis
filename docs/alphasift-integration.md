# AlphaSift 选股集成

AlphaSift 以最小方式接入 DSA：默认关闭，开启后 Web 侧显示“选股”页签，并通过后端直接调用本地 Python 包的 `alphasift.screen()`。关闭后左侧导航不显示“选股”页签，直接访问 `/screening` 时仍会显示未开启提示。

## 开启

可以直接设置环境变量：

```bash
ALPHASIFT_ENABLED=true
ALPHASIFT_INSTALL_SPEC=git+https://github.com/ZhuLinsen/alphasift.git@2c76b2b6074ae3bae01d52e5e830a4af3e3246b2
```

也可以在 Web 设置页的 AlphaSift 选股卡片中点击“开启选股”，该操作会写入
`ALPHASIFT_ENABLED=true`、重新加载运行时配置，并按 `ALPHASIFT_INSTALL_SPEC`
执行一次自动安装或可用性检查。

`ALPHASIFT_INSTALL_SPEC` 是传给 pip 的安装参数。为避免未认证调用触发任意 pip 安装，并保证部署可复现，默认值固定到当前兼容验证的 AlphaSift commit：

```bash
python -m pip install git+https://github.com/ZhuLinsen/alphasift.git@2c76b2b6074ae3bae01d52e5e830a4af3e3246b2
```

后端自动安装只接受上述受信任来源。如需使用本地开发版本、其他 commit 或 wheel 文件，请先在同一个 Python 环境中手动安装，然后再开启 `ALPHASIFT_ENABLED`：

```bash
python -m pip install -e /path/to/alphasift
```

DSA 调用的 AlphaSift 接口固定为：

```python
alphasift.screen(strategy, market=market, max_output=max_results, use_llm=False)
```

## 契约与兼容验证

后端 `/api/v1/alphasift/status` 与 `/api/v1/alphasift/install` 只返回非敏感字段，不会回传原始 `ALPHASIFT_INSTALL_SPEC`，并在响应中给出 `install_spec_is_default` 是否为默认可信来源。
在自动化测试中通过 `tests/test_alphasift_api.py` 固化以下约束（以便将该 commit 与 DSA 调用契约解耦验证）：

- 状态接口不返回 `install_spec` 明文。
- 安装接口返回 `installed`/`already_installed`/`install_spec_is_default`，不返回 `install_spec` 明文。
- `alphasift.screen` 必须使用固定签名 `screen(strategy, market=..., max_output=..., use_llm=False)` 调用。

当前自动化环境不执行联网安装与运行时真库验收；若需线上复核，请在可访问目标提交的同一 Python 环境手动完成 `pip install` 并访问 `/api/v1/alphasift/screen`，确认上述签名仍可成功执行。

若 AlphaSift 接口不兼容或自动安装失败，可将 `ALPHASIFT_ENABLED=false` 回退为关闭状态；已手动安装的包由运行环境自行管理。

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
