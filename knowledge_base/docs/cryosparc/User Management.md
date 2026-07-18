# cryoSPARC 用户管理(User Management)官方教程

> 官方来源：https://guide.cryosparc.com/setup-configuration-and-management/software-system-guides/tutorial-user-management

**摘要**：通过 cryoSPARC 用户界面创建用户、管理角色与密码重置。适用于 CryoSPARC ≤v3.3；v4.0+ 见 Admin Panel。v2.12+ 提供 UI 用户管理工具，管理员可创建用户、提升/降级角色、用户通过 UI 重置密码。

**关键步骤**：
1. 创建用户：点击用户名→Admin 进入用户管理页（须 admin）；填写 Add a New User 表单（email+username+姓名）；新用户出现在表中，Tokens 列点击 4 位注册 token 复制发送
2. 新用户用登录页 New Account 链接，输入 email+token+新密码完成注册并自动登录
3. 改角色：Admin 页 Role 列点击用户角色确认，非 admin→提升为 admin，admin→转为普通用户
4. 重置密码：登录页 Reset Password→选 I need a reset token 输入 email；admin 在用户管理页获取 4 位 reset token 发给用户；用户用 I have a reset token 填 email+token+新密码登录

**质控要点**：
- 安装时第一个通过 CLI 创建的用户为 admin
- Structura Biotechnology 无法重置密码，仅本地 admin 可重置
- reset token 须安全传达给用户

**注意事项**：
- v4.0+ 用户管理移至 Admin Panel，旧教程仅适用于 ≤v3.3
- 非 admin 用户无法访问用户管理页
- 密码重置须通过 admin 获取的 reset token，非命令行
