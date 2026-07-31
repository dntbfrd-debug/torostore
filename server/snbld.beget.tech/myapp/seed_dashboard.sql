-- Запустить на сервере: sqlite3 users.db < seed_dashboard.sql
-- Или: sqlite3 users.db ".read seed_dashboard.sql"

-- Создаём таблицы если нет
CREATE TABLE IF NOT EXISTS employee (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(80) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES user(id)
);
CREATE TABLE IF NOT EXISTS shift_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employee(id),
    date DATE NOT NULL,
    shift_type VARCHAR(10),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES user(id),
    UNIQUE(employee_id, date)
);
CREATE TABLE IF NOT EXISTS daily_revenue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    amount FLOAT DEFAULT 0.0,
    entered_by INTEGER REFERENCES user(id),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS daily_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    text TEXT DEFAULT '',
    created_by INTEGER REFERENCES user(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS arrival_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    text TEXT DEFAULT '',
    created_by INTEGER REFERENCES user(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS arrival_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arrival_id INTEGER NOT NULL REFERENCES arrival_notes(id),
    filename VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS special_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    day_type VARCHAR(20) NOT NULL,
    employee_id INTEGER REFERENCES employee(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, employee_id)
);

-- Добавляем колонки если нет
ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'worker';
ALTER TABLE user ADD COLUMN token_created DATETIME;
ALTER TABLE employee ADD COLUMN avatar VARCHAR(255);

-- Обновляем token_created для существующих токенов чтобы не истекли сразу
UPDATE user SET token_created = datetime('now') WHERE token_created IS NULL;

-- Создаём аккаунты (пароль 123) + сотрудников + смены
-- Используем хеш SHA256 от "123"
-- Хеш SHA256("123"): a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3
-- Хеш SHA256("admin123"): 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9

-- Артем
INSERT OR IGNORE INTO user (login, password_hash, token, hwid, role, status, reg_date)
VALUES ('Артем', 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
        'token_' || hex(randomblob(16)), 'dashboard_Артем', 'worker', 'Активен', datetime('now'));
INSERT OR IGNORE INTO employee (name, is_active, user_id)
SELECT 'Артем', 1, id FROM user WHERE login = 'Артем';

-- Максим
INSERT OR IGNORE INTO user (login, password_hash, token, hwid, role, status, reg_date)
VALUES ('Максим', 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
        'token_' || hex(randomblob(16)), 'dashboard_Максим', 'worker', 'Активен', datetime('now'));
INSERT OR IGNORE INTO employee (name, is_active, user_id)
SELECT 'Максим', 1, id FROM user WHERE login = 'Максим';

-- Дима
INSERT OR IGNORE INTO user (login, password_hash, token, hwid, role, status, reg_date)
VALUES ('Дима', 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
        'token_' || hex(randomblob(16)), 'dashboard_Дима', 'worker', 'Активен', datetime('now'));
INSERT OR IGNORE INTO employee (name, is_active, user_id)
SELECT 'Дима', 1, id FROM user WHERE login = 'Дима';

-- Повышаем первого пользователя до админа (если есть snbld)
UPDATE user SET role = 'admin' WHERE login = 'snbld' AND role != 'admin';

-- Создаём админа если нет ни одного (пароль admin123)
INSERT OR IGNORE INTO user (login, password_hash, token, hwid, role, status, reg_date)
SELECT 'admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
        'token_' || hex(randomblob(16)), 'web_admin', 'admin', 'Активен', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM user WHERE role = 'admin');

-- Смены (июнь 2026)
INSERT OR IGNORE INTO shift_entry (employee_id, date, shift_type)
VALUES
  ((SELECT id FROM employee WHERE name='Артем'), '2026-06-08', 'full'),
  ((SELECT id FROM employee WHERE name='Артем'), '2026-06-11', 'full'),
  ((SELECT id FROM employee WHERE name='Артем'), '2026-06-12', 'full'),
  ((SELECT id FROM employee WHERE name='Артем'), '2026-06-14', 'full'),
  ((SELECT id FROM employee WHERE name='Максим'), '2026-06-09', 'full'),
  ((SELECT id FROM employee WHERE name='Максим'), '2026-06-10', 'full'),
  ((SELECT id FROM employee WHERE name='Максим'), '2026-06-13', 'full'),
  ((SELECT id FROM employee WHERE name='Максим'), '2026-06-14', 'full'),
  ((SELECT id FROM employee WHERE name='Дима'), '2026-06-10', 'full'),
  ((SELECT id FROM employee WHERE name='Дима'), '2026-06-12', 'half'),
  ((SELECT id FROM employee WHERE name='Дима'), '2026-06-13', 'full');
