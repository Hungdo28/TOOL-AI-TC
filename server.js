const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Phục vụ các file tĩnh (Frontend)
app.use(express.static(path.join(__dirname, '')));

// Đường dẫn file DB
const dbPath = path.join(__dirname, 'db', 'users.json');

// Đọc dữ liệu từ DB
function readDB() {
    try {
        const data = fs.readFileSync(dbPath, 'utf8');
        return JSON.parse(data);
    } catch (err) {
        console.error("Lỗi đọc file users.json:", err);
        return { users: [] };
    }
}

// API Đăng nhập
app.post('/api/login', (req, res) => {
    const { username, password } = req.body;
    const db = readDB();

    const user = db.users.find(u => u.username === username && u.password === password);

    if (user) {
        // Không trả về password cho Frontend
        const { password, ...userInfo } = user;
        res.json({ success: true, user: userInfo });
    } else {
        res.status(401).json({ success: false, message: 'Sai tài khoản hoặc mật khẩu' });
    }
});

app.listen(PORT, () => {
    console.log(`===========================================`);
    console.log(`🚀 Server đang chạy tại: http://localhost:${PORT}`);
    console.log(`===========================================`);
});
