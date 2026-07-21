document.addEventListener('DOMContentLoaded', () => {
    // Nếu đã đăng nhập thì chuyển hướng về index
    const currentUser = localStorage.getItem('currentUser');
    if (currentUser) {
        window.location.href = 'index.html';
        return;
    }

    const loginForm = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const usernameInput = document.getElementById('username').value.trim();
        const passwordInput = document.getElementById('password').value.trim();
        const btnSubmit = loginForm.querySelector('button[type="submit"]');

        errorMessage.classList.add('hidden');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Đang đăng nhập...';
        lucide.createIcons();

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username: usernameInput, password: passwordInput })
            });

            const data = await response.json();

            if (data.success) {
                // Lưu vào localStorage
                localStorage.setItem('currentUser', JSON.stringify(data.user));
                
                // Chuyển hướng
                window.location.href = 'index.html';
            } else {
                errorMessage.innerText = data.message || 'Đăng nhập thất bại!';
                errorMessage.classList.remove('hidden');
            }
        } catch (error) {
            errorMessage.innerText = 'Lỗi kết nối máy chủ!';
            errorMessage.classList.remove('hidden');
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = 'Đăng nhập <i data-lucide="arrow-right" class="w-4 h-4"></i>';
            lucide.createIcons();
        }
    });
});
