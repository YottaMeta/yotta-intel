# 更新日志

## v0.2.0 (2026-09-09)

- 评测完善批 2：新增 references/faq.md（12 条常见问题 + 速查索引 + 安装排障）；SKILL.md 增加 FAQ 速查节。
- 安装器错误处理：用法/目标/安装错误统一退出码与修复建议；新增 test/install.test.js。
- package.json 补 npm test 脚本；版本对齐 0.2.0（package / SKILL / CHANGELOG / CLI）。

## v0.1.1 (2026-08-29)

- 安装方式统一为四方式（对齐发布规范 §3.3.1）：方式一 `npx -y @yottameta/yotta-intel --agent <name>` / `--dir <dir>`（推荐，走 npm 源）；方式二 `git clone https://github.com/YottaMeta/yotta-intel.git`；方式三 GitHub Download ZIP；方式四 `bash install.sh --agent/--dir/--list`。移除 `npx skills` 与 `-g` 推荐；中英双 README 安装节同步。
- 版本对齐：package.json / SKILL.md / CHANGELOG / 引擎 VERSION / 测试断言 / README 锚点 = 0.1.1。
- 无功能变更（仅文档与版本同步）。

## v0.1.0 (2026-08-27)

初始发布：

- 引擎：零依赖（Python 3.8+ 标准库）威胁情报 IOC 提取与规范化。
- 七类 IOC：IPv4 / IPv6 / 域名 / URL / 邮箱 / 哈希（MD5/SHA1/SHA256/SHA512）/ CVE 编号。
- defang / refang：识别 `hxxp`、`[.]`、`(.)`、`[dot]`、`[:]`、`[@]`、`[/]` 等常见去活性写法并还原；
  每条结果自带统一 defang 安全形态。
- 归一化：域名小写 + IDN punycode、URL 去默认端口 / 去 fragment / 保留 userinfo、哈希小写、IPv6 压缩写法。
- 去重计数：`(类型, 规范值)` 为键合并，记录 count / first_line / snippet。
- 误报控制：域名 TLD 白名单 + 文件名过滤（README.md / test.py 不算域名）+ 中文标点截断 + 哈希长度校验。
- 四种输出：text / JSON / CSV / STIX-lite（STIX 2.1 Bundle + indicator pattern，uuid5 确定性）。
- 测试：103 个用例全绿；含 CLI 端到端（stdin / 文件 / 退出码）。
- 文档：SKILL.md + README 中英双版 + references（ioc-spec / defang-rules / stix-lite-spec）。
