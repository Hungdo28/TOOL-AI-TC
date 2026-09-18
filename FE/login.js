document.addEventListener('DOMContentLoaded', () => {
    const SESSION_DURATION_MS = 7 * 24 * 60 * 60 * 1000; // 7 ngày

    const loginForm = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');
    const btnSubmit = loginForm?.querySelector('button[type="submit"]');

    const showError = (message) => {
        if (!errorMessage) return;
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    };

    const refreshIcons = () => {
        if (window.lucide) window.lucide.createIcons();
    };

    // Kiểm tra thông báo hết hạn từ redirect
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('expired') === '1') {
        showError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    }

    // Kiểm tra phiên đăng nhập hiện tại
    const storedUser = localStorage.getItem('currentUser');
    if (storedUser) {
        try {
            const parsedUser = JSON.parse(storedUser);
            if (
                parsedUser
                && typeof parsedUser === 'object'
                && typeof parsedUser.username === 'string'
                && parsedUser.username.trim()
                && ['admin', 'viewer'].includes(parsedUser.role)
            ) {
                const now = Date.now();
                if (parsedUser.expiresAt && typeof parsedUser.expiresAt === 'number' && now > parsedUser.expiresAt) {
                    localStorage.removeItem('currentUser');
                    showError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
                } else {
                    // Tương thích ngược cho phiên cũ chưa có expiresAt
                    if (!parsedUser.expiresAt) {
                        parsedUser.loggedInAt = now;
                        parsedUser.expiresAt = now + SESSION_DURATION_MS;
                        localStorage.setItem('currentUser', JSON.stringify(parsedUser));
                    }
                    window.location.replace('index.html');
                    return;
                }
            } else {
                localStorage.removeItem('currentUser');
            }
        } catch (error) {
            console.warn('Thông tin đăng nhập cũ không hợp lệ:', error);
            localStorage.removeItem('currentUser');
        }
    }

    if (!loginForm || !errorMessage || !btnSubmit) {
        console.error('Trang đăng nhập thiếu thành phần bắt buộc.');
        return;
    }

    const SUPABASE_URL = 'https://zrwlzthteixjxdhsevkh.supabase.co';
    const SUPABASE_ANON_KEY = 'sb_publishable_yA_P7i5OXAffRJwHx3hGvw_Wyo02_u3';

    if (!window.supabase) {
        showError('Không thể tải dịch vụ đăng nhập. Vui lòng kiểm tra kết nối mạng và thử lại.');
        btnSubmit.disabled = true;
        return;
    }

    const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const usernameInput = document.getElementById('username').value.trim();
        // Không trim mật khẩu vì khoảng trắng có thể là một phần hợp lệ của mật khẩu.
        const passwordInput = document.getElementById('password').value;

        if (!usernameInput || !passwordInput) {
            showError('Vui lòng nhập đầy đủ tài khoản và mật khẩu.');
            return;
        }

        errorMessage.classList.add('hidden');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Đang đăng nhập...';
        refreshIcons();

        try {
            // Giữ tương thích với dữ liệu hiện tại. Nên chuyển sang Supabase Auth ở backend.
            const { data: matchedUsers, error: dbError } = await supabaseClient
                .from('users')
                // Không trả cột password hoặc các trường riêng tư khác về trình duyệt.
                .select('username, role')
                .eq('username', usernameInput)
                .eq('password', passwordInput)
                .limit(1);

            const dbUser = Array.isArray(matchedUsers) ? matchedUsers[0] : null;

            if (dbError) {
                console.error("Lỗi Supabase:", dbError);
                showError('Không thể đăng nhập lúc này. Vui lòng thử lại sau.');
            } else if (!dbUser) {
                showError('Sai tài khoản hoặc mật khẩu!');
            } else {
                const role = dbUser.role === 'admin' ? 'admin' : 'viewer';
                // Schema hiện tại không đảm bảo có cột full_name.
                const fullName = usernameInput;
                const now = Date.now();

                localStorage.setItem('currentUser', JSON.stringify({
                    username: usernameInput,
                    email: dbUser.username,
                    role: role,
                    fullName: fullName,
                    loggedInAt: now,
                    expiresAt: now + SESSION_DURATION_MS
                }));

                window.location.replace('index.html');
            }
        } catch (error) {
            console.error('Lỗi kết nối đăng nhập:', error);
            showError('Không thể kết nối dịch vụ đăng nhập. Vui lòng thử lại sau.');
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = 'Đăng nhập <i data-lucide="arrow-right" class="w-4 h-4"></i>';
            refreshIcons();
        }
    });
});
