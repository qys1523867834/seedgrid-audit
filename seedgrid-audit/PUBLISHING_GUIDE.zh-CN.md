# 上传 GitHub 与真实运营操作手册

> 本仓库尚未发布到 GitHub。请用你自己真实的账户发布，不要虚构维护时间、使用人数、Star 或外部贡献者。

## 先本地验收

在解压后的项目目录：

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
seedgrid demo demo_workspace
seedgrid check -m demo_workspace/manifest.json
```

如遇安装问题可尝试 `python -m pip install --upgrade setuptools`（需要能连接 Python 包索引）。不要把 `demo_workspace` 加入 Git，它在 `.gitignore` 中。

## 发布到 GitHub

### 直接网页上传（适合第一次操作）

1. 在浏览器打开 https://github.com/new ，仓库名填写 `seedgrid-audit`，Visibility 选择 **Public**，不要勾选初始化 README、.gitignore 或 LICENSE，然后创建仓库。
2. 解压本 ZIP，**进入**其中的 `seedgrid-audit` 目录，将里面的文件和子文件夹拖到 GitHub 的 **uploading an existing file / Add file → Upload files** 页面。**不要上传 ZIP 本身**，也不要让 README 藏在二级子目录。
3. 确认预览中包含根目录 `README.md`、`pyproject.toml`、`src/`、`tests/` 与 `.github/workflows/ci.yml`。如果浏览器未能上传点号开头的目录或文件，可使用 GitHub Desktop 或命令行上传。
4. Commit message 填 `Initial open-source release` 并点击 **Commit changes**。上传后到 **Actions** 检查 CI。

请如实描述项目的实际使用情况与维护历史；新建仓库不能保证活动审核通过。

1. 登录 GitHub 并确认个人资料公开，创建一个名为 `seedgrid-audit` 的 **Public** repository。不要自动生成 README、License、.gitignore（源码包已经包含）。
2. 将本目录内容放入本机 Git 仓库，使用 Git Bash / PowerShell 执行：

```bash
git init
git add .
git commit -m "Initial public source: experiment coverage auditor"
git branch -M main
git remote add origin https://github.com/qys1523867834/seedgrid-audit.git
git push -u origin main
```

当前示例地址已经按照 GitHub 用户名 `qys1523867834` 填写。若没有安装 Git，先通过 https://git-scm.com/ 安装，也可以通过 GitHub 网站上传文件（注意隐藏文件 `.github`）。

3. 在 Actions 页面确认 CI 真实通过之后，更新 README 里的测试徽章描述；不要在运行之前宣称 GitHub CI 已通过。
4. 修复真实 bug，写更新说明，再在 GitHub 创建 `v0.1.0` release。首次发布前可以将 CHANGELOG 的“尚未发布”说明更新为真实状态。

## 持续维护的实际工作

- 把工具用在你**自己的真实实验**上，记录并修复路径命名、JSON 指标格式等兼容问题；不要上传私有研究数据。
- 收集同行的实际反馈，并根据需要新增功能或完善使用文档。
- 如有真实 Issue、PR，要公开及时回复；功能升级应有对应测试和 Release 记录。
- 分享可用的操作演示或技术教程，而不是购买假 Star 或编造下载量。

## 关于 Codex for Open Source 申请

申请网页：https://openai.com/zh-Hans-CN/form/codex-for-oss/

OpenAI 关注活跃开源维护记录、真实使用和对开发者生态的价值。**新建一个仓库不构成保证**，也没有可核实的“几天后必过”规则。这个项目最初只是可用于建立真实维护记录的起点；是否能够获得优惠，由 OpenAI 官方审核决定。

真实提交申请时，需要个人 GitHub 用户名、公开仓库 URL、维护者角色说明、项目生态价值证明、ChatGPT 账户邮箱及 OpenAI Organization ID。若还没有足够实际使用与维护证据，先开展真实维护工作；申请材料务必如实描述项目阶段，不要假装已经被他人广泛使用。
