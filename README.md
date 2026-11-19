# 西倉 / westbar.cn —— 博客迁移与本地写作手册

> 目标：把新浪博客的老文章搬到 GitHub Pages，并且以后在**本地**就能写新日记、一键发布。
> 工作目录：`E:\westbar`　生成时间：2026-11-19

> ✅ **已全部完成并上线（2026-11-19）**：43 篇（2008–2018）——38 篇从新浪新建、
> 5 篇旧站重复自动跳过、旧链接一字未变。源码备份在 GitHub `hexo` 分支（最新 `c496863`），
> 静态站发布在 `master`（最新 `4a21e15`，**普通 commit，2015 年提交历史完整保留**）。
> 线上 <https://www.westbar.cn> 已验证：抽查 2008/2009/2011/2018 四篇文章均返回 200，
> CNAME 正常跳转。逐篇清单见 `import/import-report.md`。
>
> **主题已换成 Fluid v1.9.9**（现代简约、单栏、移动端友好），替换原 Yilia。
> 头像换成漫画白兔（`source/img/rabbit-avatar.png`，由原白兔照片 AI 生成后裁成圆形去水印），
> 同时用作 favicon。43 篇文章和老链接全部保留。菜单在 `themes/fluid/_config.yml` 的 `menu` 定义
> （home / archive / category / tag）。新增依赖 `hexo-generator-search`、`@adobe/css-tools`、
> **`hexo-renderer-stylus`**（关键：Fluid 的 `.styl` 样式表靠它编译成浏览器要的 `/css/main.css`，
> 缺了会导致整站无样式，`npm install` 时务必保留）。
>
> **2026-11-19 晚间复查修复**：发现线上页面引用 `/css/main.css` 但返回 404（整站裸奔、
> 只有 HTML 骨架）。根因是换 Fluid 时漏装 `hexo-renderer-stylus`——Yilia 用预编译 CSS 不依赖它，
> Fluid 的样式是 Stylus 源码、必须现场编译。已安装并重建，`main.css` 生成 51KB，重新发布后
> 线上 CSS 返回 200（52017B），样式恢复正常。
>
> **favicon 已换成漫画头像（2026-11-19 22:10）**：浏览器标签图标原先是白兔原始照片
> （`source/favicon.png`，404×505 带背景）——因为根配置 `_config.yml` 的 `favicon: /favicon.png`
> 优先级高于主题配置。已用漫画白兔头像生成 128×128 透明圆底 PNG，覆盖
> `source/favicon.png` 与 `source/img/favicon.png`。注意：以后换头像要同时更新这两处 +
> `source/img/rabbit-avatar.png`，且根配置 `/favicon.png` 不能被主题配置覆盖。
>
> 以后日常：写日记 → 本地预览 → `.\bin\publish.ps1` 一条命令发布（详见第五节）。
> 首次在新机器用本手册时，按第三节配 SSH Key、并执行 `.\bin\setup.ps1` 一次。

---

## ⚠️ 第 0 件事：请先改 GitHub 密码

你在对话里把 GitHub 密码明文发出来了。**这套工程里没有任何凭据文件**，
`_config.yml`、发布脚本和 git remote 里都不含账号密码，所有推送都走 SSH Key，
因此密码也不会被提交到 GitHub。但请尽快：

1. GitHub → Settings → Password and authentication → **Change password**；
2. 顺手开启两步验证（2FA）；
3. 以后推送一律用 SSH Key 或 Personal Access Token，不要用账号密码
   （GitHub 早在 2021 年就禁用了密码推送 Git）。

---

## 一、我查到的现状（和你想的不太一样）

| 项目 | 实际情况 |
| --- | --- |
| 仓库 `hnustluyu/hnustluyu.github.io` | **只有编译后的静态站**，不是 Hexo 源码。master 分支，33 次提交，最后一次 2015-12-27。里面是 `index.html`、`css/`、`js/`、`2010/`、`2011/`、`archives/` 等 |
| Hexo 源码 | **GitHub 上没有**（`_config.yml`、`source/_posts`、主题都不在），原本只存在你 2015 年那台电脑里 |
| 线上站点 | `https://www.westbar.cn` 正常访问，标题「西倉」，主题已从 **Yilia** 换成 **Fluid**，permalink 形如 `/2011/09/09/文章标题/` |
| 现有文章 | 迁移前 **5 篇**（2010-10-29 ~ 2011-09-09），分类「扯淡」，标签完整；导入新浪导出后现为 **43 篇** |
| CNAME | 文件内容是 `www.westbar.cn` |
| 新浪博客 | 首页 <https://blog.sina.com.cn/u/1389586804> 现在返回 **「系统维护中，博文仅作者可见。登陆后可查看本人文章。」** |

**最关键的一点**：新浪博客对访客已经关闭，**任何爬虫、第三方工具、包括我都拿不到你的文章**。
只有你本人用微博账号登录新浪后台才能导出。所以搬家这件事必须你先做第 1 步，剩下的我全自动化了。

---

## 二、已经帮你做好的部分

`E:\westbar` 现在是一个**完整可跑的 Hexo 源码工程**：

```
E:\westbar\
├── _config.yml                 站点配置（url / permalink / 主题=fluid，与原站一致）
├── package.json                Hexo 7.3 + 依赖 + npm 快捷命令
├── .gitignore                  排除 node_modules / public / 私有导出文件
├── source/
│   ├── CNAME                   www.westbar.cn
│   ├── _posts/*.md             43 篇文章（5 篇旧站反提取 + 38 篇新浪导入）
│   ├── css/ js/ fancybox/
│   ├── img/
│   │   ├── rabbit-avatar.png   ★ 漫画白兔头像（favicon / 关于页头像也用它）
│   │   └── avatar.png          旧版头像副本（兼容）
│   ├── uploads/avatar.png      旧站头像副本（兼容）
│   ├── favicon.png             顺手补上（旧站 /favicon.png 原本是 404）
│   └── images/sina/            迁移时下载的图片放这里
├── themes/fluid/               ★ 当前主题 Fluid v1.9.9（菜单/标语/头像在其 _config.yml）
├── themes/yilia/               旧主题 Yilia（保留备用，未启用）
├── tools/
│   ├── restore_snapshot.py     旧站静态页 → Hexo Markdown（保留老链接与原日期）
│   └── import_sina.py          新浪导出文件 → Hexo Markdown（通用导入器）
├── bin/
│   ├── setup.ps1               一次性初始化（git / SSH / 源码分支）
│   ├── new-post.ps1            新建日记并自动打开编辑器
│   └── publish.ps1             一键发布（构建 + 推送，保留提交历史）
├── import/                     ★ 把新浪导出的文件放这里（已 gitignore）
├── .github/workflows/
│   └── deploy.yml.example      可选的 GitHub Actions 自动构建方案
└── _work/                      旧站快照、测试数据和报告（本地私有，不上传）
```

**已实测通过**：

- `npm install` → 231 个包，Node 22 / npm 10 下正常；
- `npm run build` → 导入 38 篇后 Yilia 版 `179 files generated`，
  **换成 Fluid 主题后 `195 files generated`（43 篇文章全部保留）**；
- 5 篇文章生成的路径与线上**逐字一致**：
  `/2010/10/29/谁也输不掉曾经付出过的爱/`、`/2011/01/18/我也不知道写的什么/`、
  `/2011/03/04/蛋炒饭里的事/`、`/2011/04/26/江城没有子/`、
  `/2011/09/09/你突然问：月亮为什么可以代表心？/`；
- 修掉了时区坑：旧站时间戳是 UTC，直接搬会导致归档页日期变成前一天
  （曾出现 `2011-09-08`），现已统一为不带时区的北京时间，归档页只剩 5 个正确日期；
- 导入器支持 10 种格式（xlsx / xls / csv / tsv / html / md / txt / xml / json / ndjson），
  全部实测通过；你给的 `文章.xls` 实际是 GBK 编码 Tab 分隔文本，已正确识别 43 篇；
- 38 篇新文保留了导出文件里的**完整发布时间**（`2018-06-10 20:22:11` 这种），
  正文里连续的 `&nbsp;` 已还原成段落；
- 导入前后都构建验证过：`179 files generated`，43 个文章页，归档覆盖 2008–2018，
  老链接依然可访问。

老文章的详细清单见 `_work/restore-report.md`。里面只有一张外链图片
`http://7xpjvd.com1.z0.glb.clouddn.com/IMG_2856.JPG`（早期七牛图床，大概率已失效），
如果你本地还留着原图，放到 `source/images/` 再把 md 里的链接改成 `/images/IMG_2856.JPG` 即可。

---

## 三、一次性配置（只做一次）

### 3.1 配置免密码推送（SSH Key）

**本机 SSH Key 已经生成好了**（ed25519，无口令，私钥只在
`C:\Users\lux\.ssh\id_ed25519`，不会上传任何地方），
`~/.ssh/config` 也已配好 `IdentityFile` 和 `StrictHostKeyChecking accept-new`。

**你只需做网页这一步**：把下面这串公钥复制到剪贴板，

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | Set-Clipboard
```

公钥全文（可直接复制）：

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICPwy4Ww3V8scgCwW8nkpP9f2g/M0400RE3dfIuX7YYo hnustluyu@westbar.cn
```

打开 <https://github.com/settings/keys> → **New SSH key** →
Title 填 `westbar-lux` → Key type 选 `Authentication Key` → 粘贴 → **Add SSH key**。
验证：

```powershell
ssh -T git@github.com
# 看到 "Hi hnustluyu! You've successfully authenticated..." 就成功了
# 报 "Permission denied (publickey)" 说明公钥没贴对，重贴一次
```

> 注：`ssh-agent` 服务在本机因权限无法启动，但**不影响使用**——
> 私钥无口令且位于默认路径，`ssh`/`git` 会自动读取，无需 agent。
>
> 若你想换机器重建 Key，用这两条命令（把旧的 `id_ed25519*` 删掉再生成）：
> ```powershell
> ssh-keygen -t ed25519 -C "hnustluyu@westbar.cn" -f "$env:USERPROFILE\.ssh\id_ed25519"
> Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | Set-Clipboard
> ```
>
> 若 22 端口被网络挡住，在 `$env:USERPROFILE\.ssh\config` 里加：
> ```
> Host github.com
>   HostName ssh.github.com
>   Port 443
>   User git
> ```
>
> 不想用 SSH 也可以用 **Fine-grained Personal Access Token**
> （Settings → Developer settings → Personal access tokens，权限给 Contents 读写），
> 把 remote 改成 `https://github.com/hnustluyu/hnustluyu.github.io.git`，
> 首次 push 时 Windows 的 Git Credential Manager 会弹窗让你输 token。**不要把 token 写进任何文件。**

### 3.2 让 PowerShell 能运行脚本（Windows 默认会拦）

Windows 默认执行策略是 `Restricted`，直接跑 `.ps1` 会报
「无法加载文件……因为在此系统上禁止运行脚本」。二选一：

```powershell
# 方案 A（推荐，只对当前用户生效，设置一次即可）
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 方案 B（不改系统设置，每次临时绕过）
powershell -ExecutionPolicy Bypass -File .\bin\publish.ps1
```

> 顺带一提：脚本放在 **`bin/`** 而不是 `scripts/`，是因为 `scripts/` 是 Hexo 的
> **保留目录**（用来放 Hexo 扩展脚本），在里面放 `.ps1` 会让 `hexo generate`
> 报 `Script load failed`。这个坑已经踩过并修好了，别把目录改回去。

### 3.3 初始化源码仓库（把 Hexo 源码也备份到 GitHub）

```powershell
cd E:\westbar
git config --global user.name  "hnustluyu"
git config --global user.email "luyu0088@126.com"

.\bin\setup.ps1          # 初始化、建 hexo 分支、检查 SSH
.\bin\setup.ps1 -Push    # 把源码推到 GitHub 的 hexo 分支（首次备份）
```

这样**源码在 `hexo` 分支，网站静态文件在 `master` 分支**，互不干扰：
换电脑时只要 `git clone -b hexo ...` 就有全套写作环境。

### 3.4 核对 GitHub Pages 设置

<https://github.com/hnustluyu/hnustluyu.github.io/settings/pages>

- Source：**Deploy from a branch** → Branch `master` / `/root`
- Custom domain：`www.westbar.cn`（与 `source/CNAME` 一致）

> 补充：CNAME 写的是 `www.westbar.cn`。如果你希望不带 www 的 `westbar.cn` 也直接打开，
> 需要把 CNAME 改成 `westbar.cn`，并在 DNS 加 4 条 A 记录指向 GitHub Pages 的 IP
> （185.199.108.153 / .109.153 / .110.153 / .111.153）。现在带 www 访问是正常的，
> 不改也能用，先保持原样最保险。

---

## 四、把新浪博客搬过来 —— 已完成

### 4.1 这次实际做了什么

你放进 `import/` 的是 `文章.xls`：扩展名像 Excel，实际是 **GBK 编码的 Tab 分隔纯文本**，
三列 `时间 / 标题 / 内容`，共 43 篇，时间跨度 **2008-05-22 ~ 2018-06-10**。

| 结果 | 数量 | 说明 |
| --- | --- | --- |
| 新建文章 | **38 篇** | 生成 `source/_posts/YYYY-MM-DD-标题.md`，带完整 front-matter |
| 跳过 | 5 篇 | 与旧站已有 5 篇同名，保留旧站精修版（含分类、标签、图片、老链接） |
| 图片 | **0 张** | 官方导出只有文字，配图没有随文件一起导出 |

导入器额外做了三件事：

- 把 `&nbsp;` / `&#65279;` 还原，连续的 `&nbsp;&nbsp;` 转成段落分隔，正文可读；
- 保留原始 `HH:MM:SS` 时间（日期正则曾吞掉空格导致全变 `00:00:00`，已修好并回填 38 篇）；
- 官方导出没有分类/标签列，统一填「随笔」/「新浪博客」方便筛选，可随时改。

新 URL 与旧站风格一致，例如 `/2009/03/16/风是暖的/`、`/2018/06/10/语短情长/`。
逐篇清单见 `import/import-report.md`。

### 4.2 ⚠️ 图片没搬过来

这份导出**只有文字**。如果老文章里原本有配图，需要另找：新浪相册 / 原图床 /
登录后的完整备份工具（如 [dature](https://github.com/junyiz/dature)），
把图片放到 `source/images/`，再把正文链接改成 `/images/xxx.jpg`。
早年新浪云上的图片在陆续失效，越早找越好。

### 4.3 如果以后又导出了一份

把新文件放进 `import/`（可以删掉旧的 `文章.xls`，`import-report.md` 会被覆盖）：

```powershell
cd E:\westbar
python tools/import_sina.py --dry-run            # 预览，不写文件
python tools/import_sina.py --download-images   # 正式导入（有外链图片时顺手抓回本地）
```

重复运行是安全的：同名文章自动跳过；想强制重新导入加 `--keep-duplicates`。
完整格式说明见 `import/README.md`。

### 4.4 发布前核对

```powershell
npm run build        # 本地生成，检查 public/
npm run preview      # 浏览器 http://localhost:4000 逐篇看
.\bin\publish.ps1 -Message "import sina blog archive"
```

重点抽查几篇长文的段落分隔——官方导出丢了排版，智能分段不可能 100% 还原，
个别地方可能需要手工加空行。
---

## 五、以后写新日记（日常就这 3 条命令）

```powershell
cd E:\westbar

.\bin\new-post.ps1 -Title "今天的日记"   # ① 新建 md 并自动打开编辑器
npm run preview                             # ②（可选）本地预览 http://localhost:4000
.\bin\publish.ps1                       # ③ 一键发布到 westbar.cn
```

`new-post.ps1` 会生成 `source/_posts/2026-11-19-今天的日记.md`，
front-matter 已自动填好日期；你只管写正文。新文章的 URL 会自动是
`https://www.westbar.cn/2026/11/19/今天的日记/`，和老文章风格一致。

发布脚本做了 4 件事：构建 → 同步到 `_deploy/`（master 工作副本）→
生成一个**普通 commit** → push。它**不会 force push**，所以 2015 年那 33 次提交历史会保留。
约 1 分钟后网站更新。

> 如果只想快速发布、不介意覆盖历史，也可以 `npm run deploy`
> （走 hexo-deployer-git，会用 force push 替换 master 历史）。**两种发布方式二选一，不要混用。**

### 命令速查

| 想做什么 | 命令 |
| --- | --- |
| 写新日记 | `.\bin\new-post.ps1 -Title "标题"` |
| 本地预览 | `npm run preview` |
| 仅生成 | `npm run build` |
| 发布（推荐） | `.\bin\publish.ps1` |
| 发布（快速，覆盖历史） | `npm run deploy` |
| 只构建不推送 | `.\bin\publish.ps1 -DryRun` |
| 导入新浪导出文件 | `python tools/import_sina.py --download-images` |
| 预览导入结果 | `python tools/import_sina.py --dry-run` |
| 重建 5 篇旧文 | `python tools/restore_snapshot.py --assets --force` |
| 备份源码到 GitHub | `git add -A; git commit -m "note"; git push origin hexo` |

---

## 六、换电脑 / 不想本地装环境（可选）

如果以后想在别的机器上也只写 Markdown 就发布：

1. 把 `.github/workflows/deploy.yml.example` 改名为 `deploy.yml`，
   推到 `hexo` 分支；
2. 之后只要 `git push origin hexo`，Actions 会自动 `npm ci && npm run build`
   并把 `public/` 发到 master；
3. **启用它之后就不要再跑 `publish.ps1`**，否则两边同时推 master 会打架。

该方案同样会覆盖 master 历史（Actions 的 gh-pages 动作默认 force push），
想保住历史就继续用本地 `publish.ps1`。

---

## 七、几个容易踩的坑

- **老链接不会变**：5 篇旧文的 md 里都显式写了 `permalink:`，
  即使以后改主题、改文件名，URL 仍是 2015 年那个。别删这一行。
- **日期别写成带 `Z` 的 UTC**：Hexo 7 会按本地时区解释，归档页会差一天。
  统一用 `date: 2011-09-09 15:16:26` 这种格式（`tools/` 里的脚本已按此生成）。
- **图片尽量本地化**：新浪图床和七牛老链接随时可能失效，
  统一放 `source/images/`，正文写 `/images/xxx.jpg`。
  本次官方导出是纯文字，38 篇新文里 **0 张图片**，需要另行找回。
- **`.xls` 不一定是 Excel**：新浪导出的这个文件其实是 GBK 编码的 Tab 分隔文本，
  用 Excel 打开可能乱码，但导入器能正确识别，不要手工另存反而弄乱编码。
- **重复运行导入器是安全的**：同名文章会跳过；但报告会被覆盖成「全部跳过」，
  那是正常的，不代表文件丢了。
- **私密/草稿**：任何服务端工具都拿不到，只能靠你登录后的浏览器导出；
  官方导出通常也不含它们。
- **发布前看一眼 `import/import-report.md`**：自动转换不可能 100% 完美，
  先挑几篇检查排版再批量发布，比发完才发现问题省事得多。
- **`_work/`、`import/`、`_deploy/` 都是本地私有目录**，已 gitignore，
  里面放原始数据没问题；`source/_posts/` 才是会公开的内容，导入后记得抽查一遍。

---

## 八、已完成，以后怎么维护

全部就绪并已上线：43 篇文章、Fluid 主题、漫画白兔头像、导入/写作/发布脚本、
核对报告都在 `E:\westbar`。源码在 `hexo` 分支，静态站在 `master`。

日常只剩两件事：

1. 写新日记 —— 第五节那 3 条命令；
2. **改头像 / 换主题** —— 见下方「九、主题与头像维护」。

还没做的可选事项：改 GitHub 密码 + 开两步验证（第 0 节）、找回老文配图。

---

## 九、主题与头像维护

**主题配置**：Fluid 的所有外观设置都在 `themes/fluid/_config.yml`（这是独立配置文件，
Hexo 不会和根目录 `_config.yml` 的 `theme_config` 合并）。常用项：

- `blog_title`：导航栏左侧站点名（当前「西倉」）；
- `menu`：导航栏菜单（home / archive / category / tag）；
- `index.slogan.text`：首页副标题；
- `index.banner_img` / `banner_img_height`：首页头图与高度；
- `about.avatar` / `about.name` / `about.intro`：关于页；
- 顶部 `favicon` / `apple_touch_icon`：浏览器标签图标。

改完跑 `npm run build` 看 `public/`，确认无误再 `.\bin\publish.ps1`。

**换头像**：把新图放到 `source/img/rabbit-avatar.png`（建议正方形、裁成圆形、512×512），
配置里所有头像引用都指向它，不用改其他文件。当前这张是白兔照片 AI 生成后裁圆去水印的版本。

**Fluid 依赖**：`hexo-generator-search`（站内搜索）、`@adobe/css-tools`（代码高亮）已装并写进
`package.json`。换机器时 `npm install` 会自动装好。

**老链接**：permalink 由根 `_config.yml` 的 `permalink: ':year/:month/:day/:title/'` 决定，
无论怎么换主题都不要改它，否则 2015 年以来的老链接会失效。

**还想继续做的可选事项**：

- 找回老文章的配图（给我图片文件或图床链接，我批量补进 `source/images/`）；
- 批量调整新导入 38 篇的分类 / 标签；
- 抽查并修正几篇长文的段落分隔；
- 或者你另有一份格式特殊的导出文件（`.doc` / `.chm` / 分卷 zip），我再给导入器加解析支持。
