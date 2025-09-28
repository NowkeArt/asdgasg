import express from 'express';
import sqlite3 from 'sqlite3';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import cors from 'cors';
import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const JWT_SECRET = 'your-secret-key-change-in-production';

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('dist'));
app.use('/uploads', express.static('uploads'));

// Multer для загрузки файлов
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'uploads/');
  },
  filename: (req, file, cb) => {
    cb(null, Date.now() + '-' + file.originalname);
  }
});
const upload = multer({ storage });

// База данных
const db = new sqlite3.Database('tasks.db');

// Инициализация БД
db.serialize(() => {
  // Пользователи
  db.run(`CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )`);

  // Админы (совместимость с Telegram ботом)
  db.run(`CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )`);

  // ТЗ
  db.run(`CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    author_username TEXT NOT NULL,
    description TEXT NOT NULL,
    media_file_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_admin_id INTEGER,
    assigned_admin_username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )`);

  // Баги
  db.run(`CREATE TABLE IF NOT EXISTS bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    author_username TEXT NOT NULL,
    description TEXT NOT NULL,
    media_file_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_admin_id INTEGER,
    assigned_admin_username TEXT,
    message_id_in_group INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )`);

  // Заявки
  db.run(`CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    position TEXT NOT NULL,
    timezone TEXT,
    moderation_experience TEXT,
    other_projects TEXT,
    cheat_check_knowledge TEXT,
    grif_experience TEXT,
    age TEXT,
    available_time TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    message_id_in_group INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )`);
});

// Middleware для проверки токена
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ error: 'Invalid token' });
    }
    req.user = user;
    next();
  });
};

// Регистрация
app.post('/api/register', async (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password) {
    return res.status(400).json({ error: 'All fields are required' });
  }

  try {
    const hashedPassword = await bcrypt.hash(password, 10);
    
    db.run(
      'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
      [username, email, hashedPassword],
      function(err) {
        if (err) {
          if (err.message.includes('UNIQUE constraint failed')) {
            return res.status(400).json({ error: 'Username or email already exists' });
          }
          return res.status(500).json({ error: 'Registration failed' });
        }
        
        const token = jwt.sign(
          { id: this.lastID, username, email, role: 'user' },
          JWT_SECRET,
          { expiresIn: '24h' }
        );
        
        res.json({ token, user: { id: this.lastID, username, email, role: 'user' } });
      }
    );
  } catch (error) {
    res.status(500).json({ error: 'Registration failed' });
  }
});

// Авторизация
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;

  db.get(
    'SELECT * FROM users WHERE username = ? OR email = ?',
    [username, username],
    async (err, user) => {
      if (err) {
        return res.status(500).json({ error: 'Login failed' });
      }
      
      if (!user || !(await bcrypt.compare(password, user.password))) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      const token = jwt.sign(
        { id: user.id, username: user.username, email: user.email, role: user.role },
        JWT_SECRET,
        { expiresIn: '24h' }
      );

      res.json({ 
        token, 
        user: { 
          id: user.id, 
          username: user.username, 
          email: user.email, 
          role: user.role 
        } 
      });
    }
  );
});

// Создание ТЗ
app.post('/api/tasks', authenticateToken, upload.single('media'), (req, res) => {
  const { description } = req.body;
  const mediaFile = req.file ? req.file.filename : null;

  db.run(
    'INSERT INTO tasks (author_id, author_username, description, media_file_id) VALUES (?, ?, ?, ?)',
    [req.user.id, req.user.username, description, mediaFile],
    function(err) {
      if (err) {
        return res.status(500).json({ error: 'Failed to create task' });
      }
      res.json({ id: this.lastID, message: 'Task created successfully' });
    }
  );
});

// Получение ТЗ
app.get('/api/tasks', authenticateToken, (req, res) => {
  const { status } = req.query;
  let query = 'SELECT * FROM tasks';
  let params = [];

  if (status) {
    query += ' WHERE status = ?';
    params.push(status);
  }

  query += ' ORDER BY created_at DESC';

  db.all(query, params, (err, tasks) => {
    if (err) {
      return res.status(500).json({ error: 'Failed to fetch tasks' });
    }
    res.json(tasks);
  });
});

// Обновление статуса ТЗ
app.put('/api/tasks/:id/status', authenticateToken, (req, res) => {
  const { status } = req.body;
  const taskId = req.params.id;

  db.run(
    'UPDATE tasks SET status = ?, assigned_admin_id = ?, assigned_admin_username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    [status, req.user.id, req.user.username, taskId],
    function(err) {
      if (err) {
        return res.status(500).json({ error: 'Failed to update task' });
      }
      res.json({ message: 'Task status updated' });
    }
  );
});

// Создание бага
app.post('/api/bugs', authenticateToken, upload.single('media'), (req, res) => {
  const { description } = req.body;
  const mediaFile = req.file ? req.file.filename : null;

  db.run(
    'INSERT INTO bugs (author_id, author_username, description, media_file_id) VALUES (?, ?, ?, ?)',
    [req.user.id, req.user.username, description, mediaFile],
    function(err) {
      if (err) {
        return res.status(500).json({ error: 'Failed to create bug report' });
      }
      res.json({ id: this.lastID, message: 'Bug report created successfully' });
    }
  );
});

// Получение багов
app.get('/api/bugs', authenticateToken, (req, res) => {
  db.all('SELECT * FROM bugs ORDER BY created_at DESC', (err, bugs) => {
    if (err) {
      return res.status(500).json({ error: 'Failed to fetch bugs' });
    }
    res.json(bugs);
  });
});

// Обновление статуса бага
app.put('/api/bugs/:id/status', authenticateToken, (req, res) => {
  const { status } = req.body;
  const bugId = req.params.id;

  db.run(
    'UPDATE bugs SET status = ?, assigned_admin_id = ?, assigned_admin_username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    [status, req.user.id, req.user.username, bugId],
    function(err) {
      if (err) {
        return res.status(500).json({ error: 'Failed to update bug status' });
      }
      res.json({ message: 'Bug status updated' });
    }
  );
});

// Создание заявки
app.post('/api/applications', authenticateToken, (req, res) => {
  const { position, answers } = req.body;
  const [timezone, moderation_experience, other_projects, cheat_check_knowledge, grif_experience, age, available_time] = answers;

  db.run(
    `INSERT INTO applications 
    (user_id, username, position, timezone, moderation_experience, other_projects, cheat_check_knowledge, grif_experience, age, available_time) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [req.user.id, req.user.username, position, timezone, moderation_experience, other_projects, cheat_check_knowledge, grif_experience, age, available_time],
    function(err) {
      if (err) {
        return res.status(500).json({ error: 'Failed to create application' });
      }
      res.json({ id: this.lastID, message: 'Application submitted successfully' });
    }
  );
});

// Получение заявок
app.get('/api/applications', authenticateToken, (req, res) => {
  db.all('SELECT * FROM applications ORDER BY created_at DESC', (err, applications) => {
    if (err) {
      return res.status(500).json({ error: 'Failed to fetch applications' });
    }
    res.json(applications);
  });
});

// Обновление статуса заявки
app.put('/api/applications/:id/status', authenticateToken, (req, res) => {
  const { status } = req.body;
  const appId = req.params.id;

  db.run(
    'UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
    [status, appId],
    function(err) {
      if (err) {
        return res.status(500).json({ error: 'Failed to update application status' });
      }
      res.json({ message: 'Application status updated' });
    }
  );
});

// Получение профиля пользователя
app.get('/api/profile', authenticateToken, (req, res) => {
  db.get('SELECT id, username, email, role, created_at FROM users WHERE id = ?', [req.user.id], (err, user) => {
    if (err) {
      return res.status(500).json({ error: 'Failed to fetch profile' });
    }
    res.json(user);
  });
});

// Создание папки uploads если не существует
import fs from 'fs';
if (!fs.existsSync('uploads')) {
  fs.mkdirSync('uploads');
}

// Обслуживание статических файлов
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});