# SeedGrid Audit：中文使用说明

**它能做什么？** 当你有多个模型 × 多个数据集 × 多个随机种子的实验时，自动检查每一组对应的权重文件、指标 JSON 是否存在，是否大小异常、JSON 是否损坏、指标是否超出指定范围，并输出缺失实验列表。

它不会训练模型、下载数据、上传隐私文件，也不会 `torch.load` 读取不可信 `.pt` 权重。它只做文件层面的审计，并不证明模型权重正确、论文实验真实可靠或无数据泄漏。

## 3 分钟上手

解压仓库后，在终端进入项目目录：

```bash
python -m pip install -e .
seedgrid demo example_workspace
seedgrid check -m example_workspace/manifest.json --markdown example_workspace/report.md
```

演示会生成 8 个**虚构**实验组合。这里的 `checkpoint.bin` 只是用于测试的字符，不是真正的模型权重。

## 真实科研场景

复制 `examples/manifest.example.json` 到你自己的实验文件夹，修改：

- `root`：保存实验的根目录（相对于清单 JSON 的目录，也可以是绝对路径）。
- `axes`：你实际运行的模型、数据集和随机种子列表；可自由增加例如 `variant`（消融变体）。
- `artifacts`：对应文件相对于 `root` 的路径模板；`{model}`、`{seed}` 等代表轴变量。
- `min_bytes`：文件最小字节数（可用于防止把空文件当作已完成训练）。
- `required_numeric`：指标 JSON 中必须出现的数值字段及上下界。

例如，一篇论文有主模型、五种消融、五个数据集、五个随机种子，添加 `variant` 轴就可以系统检查 150 组任务的文件覆盖情况。

执行：

```bash
seedgrid check -m manifest.json --json report.json --markdown report.md --csv report.csv
```

退出码 0 表示**基础文件检查全部通过**；1 表示有缺失或格式错误；2 表示配置无效或输入输出异常。`--sha256` 会计算已找到文件的哈希，适合留档，大模型权重计算哈希可能较慢。

## 关于开源

这个工具是一个初始版本，目前**不应宣称它已有实际用户、下载量、社区贡献或 Star**。建议先用于你自己的真实实验，收集可公开的匿名示例，修复实际遇到的问题，再发布版本、接受 Issue/PR。项目是否满足任何开源资助或优惠申请条件，以官方审核为准。
