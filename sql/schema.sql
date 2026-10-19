-- 登录模块防御性建表脚本
-- 由 app/db.py 的 init_db() 执行；重复执行安全（IF NOT EXISTS）

-- ============ 1. 管理员 ============
CREATE TABLE IF NOT EXISTS admin (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键，表内部用
    username     TEXT    NOT NULL UNIQUE,            -- 登录名，唯一
    display_name TEXT    NOT NULL,                   -- 显示名（界面右上角那个 "ZH"）
    password     TEXT    NOT NULL,                   -- 密码（明文存储，课程设计演示用）
    role         TEXT    NOT NULL DEFAULT 'admin',   -- 角色：admin / super（预留）
    status       INTEGER NOT NULL DEFAULT 1,         -- 1 启用 / 0 停用
    created_at   TEXT    NOT NULL                    -- 创建时间 'YYYY-MM-DD HH:MM:SS'
);

-- ============ 2. 登录会话 ============
-- 一行 = 一次登录。token 就是发给浏览器的那个字符串（明文存储，按约定简化）
CREATE TABLE IF NOT EXISTS admin_session (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    token      TEXT    NOT NULL UNIQUE,              -- 会话令牌，UNIQUE 自带索引
    admin_id   INTEGER NOT NULL,                     -- 属于哪个管理员
    created_at TEXT    NOT NULL,                     -- 登录时间
    expires_at TEXT    NOT NULL,                     -- 过期时间（默认登录后 8 小时）
    FOREIGN KEY (admin_id) REFERENCES admin(id) ON DELETE CASCADE
);

-- 按管理员查会话（"踢下线"、看某人登录了哪些地方时会用到）
CREATE INDEX IF NOT EXISTS idx_session_admin ON admin_session(admin_id);
