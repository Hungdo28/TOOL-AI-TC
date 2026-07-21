document.addEventListener('DOMContentLoaded', () => {
    // Nếu đã đăng nhập thì chuyển hướng về index
    const currentUser = localStorage.getItem('currentUser');
    if (currentUser) {
        window.location.href = 'index.html';
        return;
    }

    const loginForm = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');

    // TODO: THAY BẰNG KEY CỦA BẠN (Lấy trên supabase.com)
    const SUPABASE_URL = 'https://zrwlzthteixjxdhsevkh.supabase.co';
    const SUPABASE_ANON_KEY = 'sb_publishable_yA_P7i5OXAffRJwHx3hGvw_Wyo02_u3';

    // Khởi tạo Supabase
    const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

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
            // Đăng nhập trực tiếp qua Database (Bỏ qua Supabase Auth)
            const { data: dbUser, error: dbError } = await supabase
                .from('users')
                .select('*')
                .eq('username', usernameInput) // Chỉnh lại theo đúng tên cột trên Supabase của bạn
                .eq('password', passwordInput)
                .single();

            if (dbError) {
                console.error("Lỗi Supabase:", dbError);
                errorMessage.innerText = 'Lỗi DB: ' + (dbError.message || 'Hãy kiểm tra lại RLS hoặc tên bảng');
                errorMessage.classList.remove('hidden');
            } else if (!dbUser) {
                errorMessage.innerText = 'Sai tài khoản hoặc mật khẩu!';
                errorMessage.classList.remove('hidden');
            } else {
                // Đăng nhập thành công, lấy dữ liệu từ bảng
                const role = dbUser.role || 'viewer';
                const fullName = dbUser.full_name || usernameInput;

                // Lưu vào localStorage
                localStorage.setItem('currentUser', JSON.stringify({
                    username: usernameInput,
                    email: dbUser.username,
                    role: role,
                    fullName: fullName
                }));

                // Chuyển hướng
                window.location.href = 'index.html';
            }
        } catch (error) {
            errorMessage.innerText = 'Lỗi kết nối: ' + (error.message || JSON.stringify(error));
            errorMessage.classList.remove('hidden');
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = 'Đăng nhập <i data-lucide="arrow-right" class="w-4 h-4"></i>';
            lucide.createIcons();
        }
    });
});
