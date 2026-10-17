# 搜书吧自动签到

使用 GitHub Actions 每天凌晨自动签到搜书吧。

## 配置

为了能够自动签到，需要设置几个 Actions secrets，如下：

| secrets           | 说明           | 例子                 |
| ----------------- | -------------- | -------------------- |
| SOUSHUBA_HOSTNAME | 搜书吧永久地址 | `www.soushu2030.com` |
| SOUSHUBA_USERNAME | 搜书吧用户名   |                      |
| SOUSHUBA_PASSWORD | 搜书吧密码     |                      |

## 运行与排查

定时任务和 `master` 分支的推送会执行签到。手动运行 Actions 时，勾选
`check_only` 可只登录并查询银币余额，不发布空间动态，适合验证账号配置。
三个 Secret 由 runner 注入；GitHub CLI 只能列出它们的名称，不能读取原值。
不要将密码、Cookie 或完整账户页面输出到运行日志。

本地已配置上述环境变量时，也可执行只读检查：

```sh
python soushuba.py --check-only
```

余额从完整积分页的“银币”字段读取，不再依赖顶部 AJAX 菜单的 `hcredit_2`。
登录成功需要有效的 Discuz 认证 Cookie，不能只凭 HTTP 200 判断。
登录失效、HTTP 错误、银币字段缺失或内容无效会明确报错，不会当作零余额。
若错误发生在发布动态之后，请先检查前面各次操作日志，避免盲目重跑导致重复发布。

运行本地回归测试（不访问网络，不需要 Secrets）：

```sh
python -m unittest -v test_soushuba
```
