// ================= KIỂM TRA ĐĂNG NHẬP & QUẢN LÝ PHIÊN =================
const currentUserJson = localStorage.getItem('currentUser');
if (!currentUserJson) {
    window.location.replace('login.html');
}

let currentUser = { username: 'guest', role: 'viewer', fullName: 'Khách', token: null };
try {
    const parsed = JSON.parse(currentUserJson || '{}');
    if (parsed && parsed.username) {
        currentUser = {
            username: parsed.username.trim(),
            role: parsed.role || 'viewer',
            fullName: parsed.fullName || parsed.username.trim(),
            token: parsed.token || localStorage.getItem('authToken') || null,
        };
    }
} catch (_) {
    window.location.replace('login.html');
}

window.logout = function () {
    if (confirm('Bạn có chắc chắn muốn thoát?')) {
        localStorage.removeItem('currentUser');
        localStorage.removeItem('authToken');
        window.location.replace('login.html');
    }
};

function escapeHtml(value = '') {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ================= CẤU HÌNH API =================
const BACKEND_API_BASE = (
    window.AUTO_TC_API_BASE ||
    (window.location.hostname === 'quanlv.io.vn'
        ? 'https://tool-ai-tc.onrender.com/api'
        : `${window.location.origin}/api`)
).replace(/\/$/, '');

const BACKEND_ORIGIN = BACKEND_API_BASE.replace(/\/api$/, '');

function getBackendHeaders(json = true) {
    const headers = {};
    const token = (currentUser && currentUser.token) || localStorage.getItem('authToken');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    } else {
        if (currentUser && currentUser.username) headers['X-User-Name'] = currentUser.username;
        if (currentUser && currentUser.role) headers['X-User-Role'] = currentUser.role;
    }
    if (json) headers['Content-Type'] = 'application/json';
    return headers;
}

// ================= STATE QUẢN LÝ AUTO TEST =================
let autoTestMode = 'both'; // 'both' | 'api' | 'webui'
let currentFilter = 'ALL'; // 'ALL' | 'API' | 'WEB_UI' | 'PASS' | 'FAIL'
let autoTestCases = [];    // Danh sách kịch bản Auto Test
let executionResults = {}; // Map theo id -> kết quả chạy mới nhất
let expandedCards = new Set();
let runningIds = new Set();
let availableTasks = [];

// ================= KHỞI TẠO TRANG =================
window.addEventListener('DOMContentLoaded', async () => {
    const fullNameEl = document.getElementById('displayFullName');
    const roleEl = document.getElementById('displayRole');
    if (fullNameEl) fullNameEl.textContent = currentUser.fullName;
    if (roleEl) roleEl.textContent = currentUser.role === 'admin' ? 'Quản trị viên' : 'Kiểm thử viên';

    // Điền sẵn URL môi trường mặc định
    const baseUrlInput = document.getElementById('envBaseUrl');
    const webUrlInput = document.getElementById('envWebUrl');
    if (baseUrlInput && !baseUrlInput.value) {
        baseUrlInput.value = BACKEND_ORIGIN;
    }
    if (webUrlInput && !webUrlInput.value) {
        webUrlInput.value = 'https://customertest.giaothongso.com.vn/#/login';
    }
    const savedWebUser = localStorage.getItem('autotc:webLoginUser');
    if (savedWebUser && document.getElementById('envLoginUser')) {
        document.getElementById('envLoginUser').value = savedWebUser;
    }

    await loadTasksDropdown(false);

    // Kiểm tra nếu URL có ?task=... được chuyển sang từ Trang 1 hoặc trang Review
    const params = new URLSearchParams(window.location.search);
    const taskFromUrl = params.get('task') || params.get('problem_title') || '';
    if (taskFromUrl) {
        const taskInput = document.getElementById('autoTaskName');
        if (taskInput) taskInput.value = taskFromUrl;
        const sel = document.getElementById('taskSelect');
        if (sel) {
            for (const opt of sel.options) {
                if (opt.value === taskFromUrl || opt.textContent === taskFromUrl) {
                    sel.value = opt.value;
                    break;
                }
            }
        }
        await generateAutoTestcases();
    } else {
        // Nạp sẵn bộ mẫu để người dùng có thể bấm Chạy thử ngay lập tức
        loadSampleSuite(true);
    }

    if (window.lucide) window.lucide.createIcons();
});

function showToast(msg, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMsg');
    if (!toast || !toastMsg) return;

    toast.className = `fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-2xl shadow-xl text-sm font-semibold text-white transition-all ${
        type === 'error' ? 'bg-rose-600' : type === 'info' ? 'bg-blue-600' : 'bg-emerald-600'
    }`;
    toastMsg.textContent = msg;
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 4500);
}

async function loadTasksDropdown(notify = false) {
    const sel = document.getElementById('taskSelect');
    if (!sel) return;

    try {
        const resp = await fetch(`${BACKEND_API_BASE}/tasks`, {
            method: 'GET',
            headers: getBackendHeaders(false),
        });
        if (resp.ok) {
            const list = await resp.json();
            if (Array.isArray(list)) {
                availableTasks = list;
                const currentVal = sel.value;
                sel.innerHTML = '<option value="">-- Nhập bài toán mới hoặc chọn bài toán từ Trang 1 --</option>';
                list.forEach(item => {
                    const name = item['Bài toán'] || item.title || '';
                    if (name) {
                        const opt = document.createElement('option');
                        opt.value = name;
                        opt.dataset.problemId = item.id || item.problem_id || '';
                        opt.textContent = `${name} (${item['Trạng thái'] || 'Chưa làm'})`;
                        sel.appendChild(opt);
                    }
                });
                if (currentVal) sel.value = currentVal;
                if (notify) showToast('Đã làm mới danh sách bài toán!');
            }
        }
    } catch (err) {
        console.warn('Không thể tải danh sách bài toán:', err);
        if (notify) showToast('Không thể kết nối Backend để tải danh sách bài toán', 'error');
    }
}

window.onSelectExistingTask = function () {
    const sel = document.getElementById('taskSelect');
    const taskInput = document.getElementById('autoTaskName');
    if (sel && sel.value && taskInput) {
        taskInput.value = sel.value;
    }
};

window.setAutoTestMode = function (mode) {
    autoTestMode = mode;
    ['both', 'api', 'webui'].forEach(m => {
        const btn = document.getElementById(`modeBtn_${m}`);
        if (!btn) return;
        if (m === mode) {
            btn.className = 'px-2.5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold flex items-center justify-center gap-1 transition shadow-xs';
        } else {
            btn.className = 'px-2.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold flex items-center justify-center gap-1 transition';
        }
    });
};

window.fillCurrentSessionToken = async function () {
    const input = document.getElementById('envAuthToken');
    if (!input) return;
    let tok = currentUser.token || localStorage.getItem('authToken');
    if (!tok && currentUser.username) {
        try {
            const resp = await fetch(`${BACKEND_API_BASE}/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: currentUser.username }),
            });
            if (resp.ok) {
                const d = await resp.json();
                tok = d.token;
            }
        } catch (_) {}
    }
    if (tok) {
        input.value = `Bearer ${tok}`;
        showToast('Đã nạp Bearer Token của phiên hiện tại!');
    } else {
        showToast('Không tìm thấy Token phiên hiện tại', 'info');
    }
};

// ================= CHỌN NHANH 2 TRANG WEB GIAO THÔNG SỐ =================
window.applyWebsitePreset = function (presetKey) {
    const webUrlEl = document.getElementById('envWebUrl');
    const taskNameEl = document.getElementById('autoTaskName');
    setAutoTestMode('webui');

    if (presetKey === 'customer') {
        const url = 'https://customertest.giaothongso.com.vn/#/login';
        if (webUrlEl) webUrlEl.value = url;
        if (taskNameEl) taskNameEl.value = 'Customer Portal - Kiểm thử Đăng nhập (customertest)';

        autoTestCases = [
            {
                id: 'AUTO_001',
                test_suite: 'Customer Portal - Giao diện Đăng nhập',
                muc_dich: 'Kiểm tra mở trang Đăng nhập Customer Portal hiển thị đầy đủ ô Tài khoản, Mật khẩu và nút Đăng nhập',
                test_type: 'WEB_UI',
                priority: 'High',
                dieu_kien_tien_quyet: 'Mạng kết nối tới customertest.giaothongso.com.vn',
                cac_buoc: `1. Mở ${url}\n2. Chờ giao diện SPA tải xong\n3. Kiểm tra ô nhập Tài khoản, Mật khẩu và nút bấm hiển thị\n4. Chụp ảnh màn hình lưu vào folder`,
                ket_qua_mong_muon: 'Hiển thị đầy đủ form đăng nhập Customer Portal và lưu ảnh chụp màn hình',
                auto_spec: {
                    target_url: url,
                    actions: [
                        { action: 'goto', url, desc: 'Truy cập trang Customer Portal Login' },
                        { action: 'assert_visible', selector: 'input', desc: 'Kiểm tra ô nhập tài khoản hiển thị' },
                        { action: 'assert_visible', selector: 'input[type="password"]', desc: 'Kiểm tra ô nhập mật khẩu hiển thị' },
                        { action: 'assert_visible', selector: 'button', desc: 'Kiểm tra nút Đăng nhập hiển thị' }
                    ]
                }
            },
            {
                id: 'AUTO_002',
                test_suite: 'Customer Portal - Validate Đăng nhập',
                muc_dich: 'Kiểm tra nhập thử tài khoản/mật khẩu không hợp lệ trên Customer Portal và chụp ảnh thông báo lỗi',
                test_type: 'WEB_UI',
                priority: 'High',
                dieu_kien_tien_quyet: 'Đang ở màn hình Login Customer Portal',
                cac_buoc: `1. Mở ${url}\n2. Nhập tài khoản thử nghiệm và mật khẩu sai\n3. Bấm nút Đăng nhập\n4. Chờ phản hồi và chụp ảnh màn hình`,
                ket_qua_mong_muon: 'Hệ thống từ chối đăng nhập và hiển thị thông báo trên màn hình',
                auto_spec: {
                    target_url: url,
                    actions: [
                        { action: 'goto', url, desc: 'Mở trang Customer Portal Login' },
                        { action: 'fill', selector: 'input[type="text"]', value: '0987654321', desc: 'Nhập tài khoản test' },
                        { action: 'fill', selector: 'input[type="password"]', value: 'SaiMatKhau@123', desc: 'Nhập mật khẩu sai' },
                        { action: 'click', selector: 'button', desc: 'Bấm nút Đăng nhập' },
                        { action: 'wait', value: '1500', desc: 'Chờ thông báo phản hồi' }
                    ]
                }
            }
        ];
        executionResults = {};
        updateSummaryStats();
        renderAutoTestList();
        showToast('Đã chọn Preset 1: Customer Portal (customertest.giaothongso.com.vn)!');
    } else if (presetKey === 'crm') {
        const url = 'https://crmtest.giaothongso.com.vn/#/search-information/cust-regis';
        if (webUrlEl) webUrlEl.value = url;
        if (taskNameEl) taskNameEl.value = 'CRM Giao Thông Số - Tra cứu & Đăng ký KH (cust-regis)';

        autoTestCases = [
            {
                id: 'AUTO_001',
                test_suite: 'CRM - Màn hình Tra cứu / Đăng ký KH',
                muc_dich: 'Kiểm tra truy cập màn hình CRM cust-regis (tự động đăng nhập nếu cần) và chụp ảnh giao diện',
                test_type: 'WEB_UI',
                priority: 'High',
                dieu_kien_tien_quyet: 'Có kết nối tới crmtest.giaothongso.com.vn (điền Tài khoản/Mật khẩu ở mục 2 nếu trang yêu cầu Login)',
                cac_buoc: `1. Mở ${url}\n2. Tự động đăng nhập nếu hệ thống yêu cầu\n3. Kiểm tra giao diện hiển thị các trường thông tin và chụp ảnh lưu vào folder`,
                ket_qua_mong_muon: 'Màn hình CRM hiển thị thành công và lưu ảnh chụp màn hình vào folder',
                auto_spec: {
                    target_url: url,
                    actions: [
                        { action: 'goto', url, desc: 'Truy cập màn hình CRM cust-regis' },
                        { action: 'assert_visible', selector: 'input, button, form, body', desc: 'Kiểm tra giao diện CRM hiển thị' }
                    ]
                }
            }
        ];
        executionResults = {};
        updateSummaryStats();
        renderAutoTestList();
        showToast('Đã chọn Preset 2: CRM Giao Thông Số (crmtest.giaothongso.com.vn)!');
    }
};

// ================= NẠP BỘ MẪU CHẠY THỬ NGAY =================
window.loadSampleSuite = function (silent = false) {
    const webUrl = document.getElementById('envWebUrl')?.value || 'https://customertest.giaothongso.com.vn/#/login';
    document.getElementById('autoTaskName').value = 'Kiểm thử Tự động Hệ thống AutoTC & Giao Thông Số';

    autoTestCases = [
        {
            id: 'AUTO_001',
            test_suite: '1. Kiểm thử API Hệ thống',
            muc_dich: 'Kiểm tra API Health Check (/api/health) phản hồi HTTP 200 và status = ok',
            test_type: 'API',
            priority: 'High',
            dieu_kien_tien_quyet: 'Backend Server đang hoạt động tại cổng 8088',
            cac_buoc: '1. Gửi request GET tới /api/health\n2. Kiểm tra mã phản hồi HTTP = 200\n3. Kiểm tra JSON trả về có trường status = "ok"',
            ket_qua_mong_muon: 'HTTP 200 OK, JSON trả về {"status": "ok"}',
            auto_spec: {
                method: 'GET',
                endpoint: '/api/health',
                headers: { Accept: 'application/json' },
                body: null,
                expected_status: 200,
                assertions: [
                    { type: 'status_code', expected: 200 },
                    { type: 'json_equals', key: 'status', expected: 'ok' }
                ]
            }
        },
        {
            id: 'AUTO_002',
            test_suite: '2. Kiểm thử API Xác thực JWT',
            muc_dich: 'Kiểm tra cấp JWT Token thành công khi gửi username hợp lệ (Happy Path)',
            test_type: 'API',
            priority: 'High',
            dieu_kien_tien_quyet: 'Endpoint /api/auth/token sẵn sàng',
            cac_buoc: '1. Gửi request POST /api/auth/token với JSON body {"username": "hung"}\n2. Kiểm tra HTTP Status = 200 và response có chứa trường token',
            ket_qua_mong_muon: 'HTTP 200 OK, trả về JWT token hợp lệ',
            auto_spec: {
                method: 'POST',
                endpoint: '/api/auth/token',
                headers: { 'Content-Type': 'application/json' },
                body: { username: 'hung' },
                expected_status: 200,
                assertions: [
                    { type: 'status_code', expected: 200 },
                    { type: 'json_has_key', key: 'token' }
                ]
            }
        },
        {
            id: 'AUTO_003',
            test_suite: '2. Kiểm thử API Xác thực JWT',
            muc_dich: 'Kiểm tra API cấp Token trả về lỗi HTTP 400 khi thiếu username (Negative Case)',
            test_type: 'API',
            priority: 'Medium',
            dieu_kien_tien_quyet: 'Endpoint /api/auth/token sẵn sàng',
            cac_buoc: '1. Gửi request POST /api/auth/token với body rỗng {}\n2. Kiểm tra mã trạng thái trả về là 400 Bad Request',
            ket_qua_mong_muon: 'HTTP 400 Bad Request, từ chối cấp token',
            auto_spec: {
                method: 'POST',
                endpoint: '/api/auth/token',
                headers: { 'Content-Type': 'application/json' },
                body: {},
                expected_status: 400,
                assertions: [
                    { type: 'status_code', expected: 400 }
                ]
            }
        },
        {
            id: 'AUTO_004',
            test_suite: '3. Kiểm thử API Quản lý Bài toán',
            muc_dich: 'Kiểm tra lấy danh sách bài toán (/api/tasks) với quyền Admin',
            test_type: 'API',
            priority: 'High',
            dieu_kien_tien_quyet: 'Truyền Header xác thực Admin',
            cac_buoc: '1. Gửi GET /api/tasks kèm Header X-User-Name: hung, X-User-Role: admin\n2. Kiểm tra HTTP Status = 200',
            ket_qua_mong_muon: 'HTTP 200 OK, trả về danh sách bài toán',
            auto_spec: {
                method: 'GET',
                endpoint: '/api/tasks',
                headers: { 'X-User-Name': 'hung', 'X-User-Role': 'admin' },
                body: null,
                expected_status: 200,
                assertions: [
                    { type: 'status_code', expected: 200 }
                ]
            }
        },
        {
            id: 'AUTO_005',
            test_suite: '4. Kiểm thử Giao diện Web (UI)',
            muc_dich: 'Kiểm tra giao diện trang Đăng nhập hiển thị đầy đủ form và nút bấm',
            test_type: 'WEB_UI',
            priority: 'High',
            dieu_kien_tien_quyet: 'Web Server đang chạy',
            cac_buoc: `1. Mở trình duyệt truy cập ${webUrl}\n2. Kiểm tra phần tử input và button hiển thị trên DOM`,
            ket_qua_mong_muon: 'Trang tải thành công HTTP 200, có đầy đủ ô nhập liệu và nút đăng nhập',
            auto_spec: {
                target_url: webUrl,
                actions: [
                    { action: 'goto', url: webUrl, desc: 'Truy cập trang đăng nhập' },
                    { action: 'assert_visible', selector: 'input', desc: 'Kiểm tra ô input hiển thị' },
                    { action: 'assert_visible', selector: 'button', desc: 'Kiểm tra nút Submit hiển thị' }
                ]
            }
        }
    ];

    executionResults = {};
    updateSummaryStats();
    renderAutoTestList();
    if (!silent) {
        showToast('Đã nạp 5 kịch bản Auto Test mẫu (4 API + 1 Web UI). Bấm "Chạy Auto Test tất cả" để trải nghiệm!');
    }
};

// ================= GỌI AI SINH KỊCH BẢN AUTO TEST =================
window.generateAutoTestcases = async function () {
    const taskName = document.getElementById('autoTaskName')?.value.trim() || 'Bài toán Auto Test';
    const sel = document.getElementById('taskSelect');
    const selectedOption = sel?.selectedOptions?.[0];
    const problemId = selectedOption?.dataset?.problemId || '';
    const specText = document.getElementById('specText')?.value.trim() || '';
    const customPrompt = document.getElementById('customPrompt')?.value.trim() || '';
    const baseUrl = document.getElementById('envBaseUrl')?.value.trim() || BACKEND_ORIGIN;
    const webUrl = document.getElementById('envWebUrl')?.value.trim() || '';
    const loginUsername = document.getElementById('envLoginUser')?.value.trim() || '';
    const loginPassword = document.getElementById('envLoginPass')?.value || '';
    if (loginUsername) localStorage.setItem('autotc:webLoginUser', loginUsername);

    const btn = document.getElementById('btnGenerateAuto');
    const label = document.getElementById('btnGenerateAutoLabel');
    if (btn) btn.disabled = true;
    if (label) label.textContent = 'Đang quét Web & Sinh kịch bản...';

    try {
        const resp = await fetch(`${BACKEND_API_BASE}/autotest/generate`, {
            method: 'POST',
            headers: getBackendHeaders(true),
            body: JSON.stringify({
                taskName,
                problem_id: problemId,
                testMode: autoTestMode,
                baseUrl,
                webUrl,
                specText,
                customPrompt,
                inspectDom: true,
                loginUsername,
                loginPassword,
            }),
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !Array.isArray(data.testcases)) {
            throw new Error(data.message || `Lỗi HTTP ${resp.status}`);
        }

        autoTestCases = data.testcases;
        executionResults = {};
        updateSummaryStats();
        renderAutoTestList();
        const domMsg = data.dom_inspected ? ' (Đã quét phần tử thật trên trang Web)' : '';
        showToast(`Đã sinh thành công ${autoTestCases.length} kịch bản Auto Test${domMsg}!`);
        return true;
    } catch (err) {
        console.error('Lỗi khi sinh Auto Testcase:', err);
        showToast(`Không thể gọi Backend (${err.message}). Đã nạp bộ kịch bản mẫu để bạn thử nghiệm!`, 'info');
        loadSampleSuite(true);
        return false;
    } finally {
        if (btn) btn.disabled = false;
        if (label) label.textContent = 'AI Sinh Kịch bản Auto Test';
    }
};

// ================= LUỒNG TOÀN TRÌNH: VỪA SINH TC VỪA TEST LUÔN =================
window.generateAndRunFullFlow = async function () {
    const fullBtn = document.getElementById('btnFullFlowAuto');
    const fullLabel = document.getElementById('btnFullFlowAutoLabel');
    if (fullBtn) fullBtn.disabled = true;
    if (fullLabel) fullLabel.textContent = 'Bước 1/2: Đang quét Web & Sinh TC...';

    try {
        const ok = await window.generateAutoTestcases();
        if (ok && autoTestCases.length > 0) {
            if (fullLabel) fullLabel.textContent = `Bước 2/2: Đang chạy ${autoTestCases.length} kịch bản...`;
            await window.runAllAutoTests();
        }
    } finally {
        if (fullBtn) fullBtn.disabled = false;
        if (fullLabel) fullLabel.textContent = 'Chạy Toàn Trình (Sinh TC & Test luôn)';
    }
};

// ================= CHẠY AUTO TEST (TEST EXECUTION HARNESS) =================
function getEnvConfig() {
    const loginUsername = document.getElementById('envLoginUser')?.value.trim() || '';
    const loginPassword = document.getElementById('envLoginPass')?.value || '';
    if (loginUsername) localStorage.setItem('autotc:webLoginUser', loginUsername);

    return {
        taskName: document.getElementById('autoTaskName')?.value.trim() || 'AutoTest',
        baseUrl: document.getElementById('envBaseUrl')?.value.trim() || BACKEND_ORIGIN,
        webUrl: document.getElementById('envWebUrl')?.value.trim() || '',
        authToken: document.getElementById('envAuthToken')?.value.trim() || '',
        screenshotDir: document.getElementById('envScreenshotDir')?.value.trim() || 'AutoTC_Screenshots',
        timeoutSec: Number(document.getElementById('envTimeoutSec')?.value || 15),
        usePlaywright: document.getElementById('envUsePlaywright')?.checked ?? true,
        headless: document.getElementById('envHeadless')?.checked ?? true,
        loginUsername,
        loginPassword,
    };
}

window.runAllAutoTests = async function () {
    if (autoTestCases.length === 0) {
        showToast('Chưa có kịch bản nào để chạy!', 'error');
        return;
    }

    // Đồng bộ dữ liệu đang mở trong form chỉnh sửa trước khi chạy
    expandedCards.forEach(idx => saveCardEdits(idx, true));

    const btn = document.getElementById('btnRunAllAuto');
    const label = document.getElementById('btnRunAllLabel');
    if (btn) btn.disabled = true;
    if (label) label.textContent = `Đang chạy ${autoTestCases.length} kịch bản...`;

    autoTestCases.forEach(tc => runningIds.add(tc.id));
    renderAutoTestList();

    try {
        const resp = await fetch(`${BACKEND_API_BASE}/autotest/run`, {
            method: 'POST',
            headers: getBackendHeaders(true),
            body: JSON.stringify({
                testcases: autoTestCases,
                envConfig: getEnvConfig(),
            }),
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !Array.isArray(data.results)) {
            throw new Error(data.message || `Lỗi thực thi (${resp.status})`);
        }

        data.results.forEach(r => {
            executionResults[r.id] = r;
        });

        updateSummaryStats(data.summary);
        const s = data.summary || {};
        showToast(
            `Hoàn tất chạy Auto Test: ${s.passed || 0}/${s.total || 0} PASS (${s.pass_rate || 0}%) trong ${s.total_duration_ms || 0}ms!`,
            (s.failed || 0) + (s.error || 0) > 0 ? 'info' : 'success'
        );
    } catch (err) {
        console.error('Lỗi khi chạy Auto Test:', err);
        showToast(`Lỗi khi thực thi Auto Test: ${err.message}`, 'error');
    } finally {
        runningIds.clear();
        if (btn) btn.disabled = false;
        if (label) label.textContent = 'Chạy Auto Test tất cả';
        renderAutoTestList();
    }
};

window.runSingleAutoTest = async function (index) {
    const tc = autoTestCases[index];
    if (!tc) return;

    if (expandedCards.has(index)) {
        saveCardEdits(index, true);
    }

    runningIds.add(tc.id);
    renderAutoTestList();

    try {
        const resp = await fetch(`${BACKEND_API_BASE}/autotest/run`, {
            method: 'POST',
            headers: getBackendHeaders(true),
            body: JSON.stringify({
                testcases: [tc],
                envConfig: getEnvConfig(),
            }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !Array.isArray(data.results) || !data.results[0]) {
            throw new Error(data.message || `Lỗi HTTP ${resp.status}`);
        }

        const res = data.results[0];
        executionResults[tc.id] = res;
        updateSummaryStats();
        showToast(
            `[${tc.id}] ${res.status} (${res.duration_ms}ms)`,
            res.status === 'PASS' ? 'success' : 'error'
        );
    } catch (err) {
        showToast(`Chạy [${tc.id}] thất bại: ${err.message}`, 'error');
    } finally {
        runningIds.delete(tc.id);
        renderAutoTestList();
    }
};

// ================= CẬP NHẬT THỐNG KÊ & BỘ LỌC =================
function updateSummaryStats(serverSummary = null) {
    const total = autoTestCases.length;
    let passed = 0;
    let failed = 0;
    let totalMs = 0;

    autoTestCases.forEach(tc => {
        const r = executionResults[tc.id];
        if (r) {
            if (r.status === 'PASS') passed++;
            else failed++;
            totalMs += Number(r.duration_ms || 0);
        }
    });

    const executedCount = passed + failed;
    const passRate = executedCount > 0 ? Math.round((passed / executedCount) * 1000) / 10 : null;
    const durationText = serverSummary?.total_duration_ms ?? totalMs;

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statPassed').textContent = passed;
    document.getElementById('statFailed').textContent = failed;
    document.getElementById('statPassRate').textContent =
        passRate !== null ? `${passRate}% (${durationText}ms)` : 'Chưa chạy';
}

window.setFilter = function (filter) {
    currentFilter = filter;
    ['ALL', 'API', 'WEB_UI', 'PASS', 'FAIL'].forEach(f => {
        const btn = document.getElementById(`filter_${f}`);
        if (!btn) return;
        if (f === filter) {
            btn.className = 'px-2.5 py-1 rounded-lg bg-white text-slate-900 font-bold shadow-2xs';
        } else {
            btn.className = 'px-2.5 py-1 rounded-lg text-slate-600 hover:text-slate-900';
        }
    });
    renderAutoTestList();
};

// ================= RENDER DANH SÁCH THẺ AUTO TEST =================
function renderAutoTestList() {
    const container = document.getElementById('autoTestList');
    if (!container) return;

    const filtered = autoTestCases
        .map((tc, idx) => ({ tc, idx }))
        .filter(({ tc }) => {
            const res = executionResults[tc.id];
            if (currentFilter === 'API') return tc.test_type === 'API';
            if (currentFilter === 'WEB_UI') return tc.test_type === 'WEB_UI';
            if (currentFilter === 'PASS') return res && res.status === 'PASS';
            if (currentFilter === 'FAIL') return res && res.status !== 'PASS';
            return true;
        });

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="text-center py-16 px-4 border-2 border-dashed border-slate-200 rounded-2xl text-slate-400 space-y-2">
                <i data-lucide="inbox" class="w-10 h-10 mx-auto text-slate-300"></i>
                <div class="text-sm font-bold text-slate-600">Không có kịch bản nào khớp bộ lọc</div>
                <p class="text-xs">Hãy chọn "Nạp mẫu thử ngay" hoặc bấm "AI Sinh Kịch bản Auto Test" ở cột bên trái.</p>
            </div>
        `;
        if (window.lucide) window.lucide.createIcons();
        return;
    }

    container.innerHTML = filtered.map(({ tc, idx }) => {
        const res = executionResults[tc.id];
        const isRunning = runningIds.has(tc.id);
        const isExpanded = expandedCards.has(idx);
        const spec = tc.auto_spec || {};
        const isApi = tc.test_type === 'API';

        let statusBadge = `<span class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-100 text-slate-600 border border-slate-200">Chưa chạy</span>`;
        if (isRunning) {
            statusBadge = `<span class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-blue-50 text-blue-600 border border-blue-200 inline-flex items-center gap-1"><i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i> Đang chạy...</span>`;
        } else if (res) {
            if (res.status === 'PASS') {
                statusBadge = `<span class="px-2.5 py-1 rounded-lg text-[11px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200 inline-flex items-center gap-1">✓ PASS (${res.duration_ms}ms)</span>`;
            } else {
                statusBadge = `<span class="px-2.5 py-1 rounded-lg text-[11px] font-extrabold bg-rose-50 text-rose-700 border border-rose-200 inline-flex items-center gap-1">✕ ${escapeHtml(res.status)} (${res.duration_ms}ms)</span>`;
            }
        }

        const typeBadge = isApi
            ? `<span class="px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">API • ${escapeHtml(spec.method || 'GET')} ${escapeHtml(spec.endpoint || '')}</span>`
            : `<span class="px-2 py-0.5 rounded-md text-[11px] font-mono font-bold bg-purple-50 text-purple-700 border border-purple-200">WEB_UI • Playwright</span>`;

        const borderClass = res
            ? (res.status === 'PASS' ? 'border-emerald-300 bg-emerald-50/20' : 'border-rose-300 bg-rose-50/20')
            : 'border-slate-200 bg-white';

        return `
            <div class="rounded-2xl border ${borderClass} p-4 shadow-2xs transition-all space-y-3">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                    <div class="space-y-1 flex-1">
                        <div class="flex flex-wrap items-center gap-2">
                            <span class="font-mono text-xs font-extrabold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200">${escapeHtml(tc.id)}</span>
                            ${typeBadge}
                            <span class="text-xs font-semibold text-slate-500">${escapeHtml(tc.test_suite || 'General')}</span>
                        </div>
                        <h3 class="text-sm font-bold text-slate-800">${escapeHtml(tc.muc_dich)}</h3>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                        ${statusBadge}
                        <button type="button" onclick="runSingleAutoTest(${idx})" ${isRunning ? 'disabled' : ''}
                            class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition flex items-center gap-1 shadow-xs"
                            title="Chạy kịch bản này">
                            <i data-lucide="play" class="w-3.5 h-3.5 fill-current"></i> Chạy
                        </button>
                        <button type="button" onclick="toggleCardExpand(${idx})"
                            class="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl transition"
                            title="Xem / Sửa cấu hình Auto Spec">
                            <i data-lucide="${isExpanded ? 'chevron-up' : 'settings-2'}" class="w-4 h-4"></i>
                        </button>
                        <button type="button" onclick="deleteAutoCase(${idx})"
                            class="p-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded-xl transition"
                            title="Xóa kịch bản">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>

                <!-- TÓM TẮT KẾT QUẢ CHẠY THỰC TẾ NẾU ĐÃ CHẠY -->
                ${res ? `
                <div class="p-3 rounded-xl bg-slate-900 text-slate-100 text-xs font-mono space-y-1.5 overflow-x-auto">
                    <div class="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800 pb-1">
                        <span>KẾT QUẢ THỰC TẾ (ACTUAL RESULT)</span>
                        <span>HTTP Status: <strong class="${res.status === 'PASS' ? 'text-emerald-400' : 'text-rose-400'}">${res.actual_status_code || 'N/A'}</strong> | Thời gian: ${res.duration_ms}ms</span>
                    </div>
                    <div class="space-y-1">
                        ${(res.assertion_logs || []).map(log => `<div>${escapeHtml(log)}</div>`).join('')}
                    </div>
                    ${res.response_preview ? `
                    <div class="pt-1 border-t border-slate-800 text-[11px] text-slate-300">
                        <span class="text-slate-400">Response Body:</span> <code>${escapeHtml(res.response_preview)}</code>
                    </div>` : ''}
                    ${res.screenshot_path ? `
                    <div class="pt-1.5 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2 text-[11px] text-emerald-300">
                        <span>📁 Đã lưu ảnh vào folder: <code class="text-white bg-slate-800 px-1.5 py-0.5 rounded">${escapeHtml(res.screenshot_path)}</code></span>
                        <button type="button" onclick="navigator.clipboard.writeText(${JSON.stringify(res.screenshot_path).replace(/"/g, '&quot;')}); showToast('Đã copy đường dẫn ảnh!')"
                            class="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition">
                            Copy đường dẫn
                        </button>
                    </div>` : ''}
                    ${res.screenshot ? `
                    <div class="pt-2">
                        <div class="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                            <span>Ảnh chụp màn hình giao diện (UI Screenshot):</span>
                            <a href="${res.screenshot}" download="${escapeHtml(tc.id)}_${escapeHtml(res.status)}.png" class="text-emerald-400 hover:underline">⬇ Tải ảnh (.png)</a>
                        </div>
                        <img src="${res.screenshot}" alt="Screenshot" class="max-h-64 rounded-lg border border-slate-700" />
                    </div>` : ''}
                </div>
                ` : ''}

                <!-- KHUNG MỞ RỘNG CHỈNH SỬA CẤU HÌNH THỰC THI -->
                ${isExpanded ? `
                <div class="pt-3 border-t border-slate-200/80 space-y-3 text-xs bg-slate-50/70 p-3.5 rounded-xl">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div class="md:col-span-2">
                            <label class="block font-bold text-slate-600 mb-1">Mục đích kiểm thử</label>
                            <input type="text" id="edit_purpose_${idx}" value="${escapeHtml(tc.muc_dich)}"
                                class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs">
                        </div>
                        <div>
                            <label class="block font-bold text-slate-600 mb-1">Loại Auto Test</label>
                            <select id="edit_type_${idx}" onchange="onSwitchCardType(${idx}, this.value)"
                                class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-bold">
                                <option value="API" ${isApi ? 'selected' : ''}>API (HTTP Request)</option>
                                <option value="WEB_UI" ${!isApi ? 'selected' : ''}>WEB_UI (Playwright)</option>
                            </select>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block font-bold text-slate-600 mb-1">Các bước thực hiện</label>
                            <textarea id="edit_steps_${idx}" rows="3" class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs">${escapeHtml(tc.cac_buoc)}</textarea>
                        </div>
                        <div>
                            <label class="block font-bold text-slate-600 mb-1">Kết quả mong đợi (Expected Result)</label>
                            <textarea id="edit_expected_${idx}" rows="3" class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs">${escapeHtml(tc.ket_qua_mong_muon)}</textarea>
                        </div>
                    </div>

                    ${isApi ? `
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 pt-1">
                        <div>
                            <label class="block font-bold text-indigo-700 mb-1">HTTP Method</label>
                            <select id="edit_method_${idx}" class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono font-bold">
                                ${['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => `<option value="${m}" ${(spec.method || 'GET') === m ? 'selected' : ''}>${m}</option>`).join('')}
                            </select>
                        </div>
                        <div class="md:col-span-2">
                            <label class="block font-bold text-indigo-700 mb-1">Endpoint (hoặc Full URL)</label>
                            <input type="text" id="edit_endpoint_${idx}" value="${escapeHtml(spec.endpoint || '/api/health')}"
                                class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono">
                        </div>
                        <div>
                            <label class="block font-bold text-indigo-700 mb-1">Expected HTTP Status</label>
                            <input type="number" id="edit_status_${idx}" value="${Number(spec.expected_status || 200)}"
                                class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono font-bold">
                        </div>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block font-bold text-slate-600 mb-1">Request Body (JSON)</label>
                            <textarea id="edit_body_${idx}" rows="3" class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono">${escapeHtml(spec.body ? JSON.stringify(spec.body, null, 2) : '')}</textarea>
                        </div>
                        <div>
                            <label class="block font-bold text-slate-600 mb-1">Assertions (JSON Array)</label>
                            <textarea id="edit_assertions_${idx}" rows="3" class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono">${escapeHtml(JSON.stringify(spec.assertions || [{ type: 'status_code', expected: spec.expected_status || 200 }], null, 2))}</textarea>
                        </div>
                    </div>
                    ` : `
                    <div class="space-y-2 pt-1">
                        <div>
                            <label class="block font-bold text-purple-700 mb-1">Target Web URL</label>
                            <input type="text" id="edit_target_url_${idx}" value="${escapeHtml(spec.target_url || '')}"
                                class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono">
                        </div>
                        <div>
                            <label class="block font-bold text-purple-700 mb-1">Playwright Actions (JSON Array: goto, fill, click, assert_visible, assert_text)</label>
                            <textarea id="edit_actions_${idx}" rows="4" class="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-mono">${escapeHtml(JSON.stringify(spec.actions || [], null, 2))}</textarea>
                        </div>
                    </div>
                    `}

                    <div class="flex justify-end gap-2 pt-2">
                        <button type="button" onclick="saveCardEdits(${idx}, false)"
                            class="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold">
                            Lưu cấu hình kịch bản
                        </button>
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }).join('');

    if (window.lucide) window.lucide.createIcons();
}

window.toggleCardExpand = function (idx) {
    if (expandedCards.has(idx)) {
        saveCardEdits(idx, true);
        expandedCards.delete(idx);
    } else {
        expandedCards.add(idx);
    }
    renderAutoTestList();
};

window.onSwitchCardType = function (idx, newType) {
    const tc = autoTestCases[idx];
    if (!tc) return;
    tc.test_type = newType;
    if (newType === 'API') {
        tc.auto_spec = {
            method: 'GET',
            endpoint: '/api/health',
            headers: { Accept: 'application/json' },
            body: null,
            expected_status: 200,
            assertions: [{ type: 'status_code', expected: 200 }],
        };
    } else {
        const webUrl = document.getElementById('envWebUrl')?.value || `${window.location.origin}/login.html`;
        tc.auto_spec = {
            target_url: webUrl,
            actions: [
                { action: 'goto', url: webUrl, desc: 'Mở trang web' },
                { action: 'assert_visible', selector: 'body', desc: 'Kiểm tra trang hiển thị' },
            ],
        };
    }
    renderAutoTestList();
};

window.saveCardEdits = function (idx, silent = false) {
    const tc = autoTestCases[idx];
    if (!tc) return;

    const purposeEl = document.getElementById(`edit_purpose_${idx}`);
    const stepsEl = document.getElementById(`edit_steps_${idx}`);
    const expEl = document.getElementById(`edit_expected_${idx}`);
    if (purposeEl) tc.muc_dich = purposeEl.value.trim();
    if (stepsEl) tc.cac_buoc = stepsEl.value;
    if (expEl) tc.ket_qua_mong_muon = expEl.value;

    if (tc.test_type === 'API') {
        const method = document.getElementById(`edit_method_${idx}`)?.value || 'GET';
        const endpoint = document.getElementById(`edit_endpoint_${idx}`)?.value.trim() || '/api/health';
        const expectedStatus = Number(document.getElementById(`edit_status_${idx}`)?.value || 200);
        const bodyRaw = document.getElementById(`edit_body_${idx}`)?.value.trim() || '';
        const assertRaw = document.getElementById(`edit_assertions_${idx}`)?.value.trim() || '';

        let parsedBody = null;
        if (bodyRaw) {
            try {
                parsedBody = JSON.parse(bodyRaw);
            } catch (_) {
                parsedBody = bodyRaw;
            }
        }
        let parsedAssertions = [{ type: 'status_code', expected: expectedStatus }];
        if (assertRaw) {
            try {
                parsedAssertions = JSON.parse(assertRaw);
            } catch (_) {}
        }
        tc.auto_spec = {
            ...(tc.auto_spec || {}),
            method,
            endpoint,
            expected_status: expectedStatus,
            body: parsedBody,
            assertions: parsedAssertions,
        };
    } else {
        const targetUrl = document.getElementById(`edit_target_url_${idx}`)?.value.trim() || '';
        const actionsRaw = document.getElementById(`edit_actions_${idx}`)?.value.trim() || '[]';
        let parsedActions = tc.auto_spec?.actions || [];
        try {
            parsedActions = JSON.parse(actionsRaw);
        } catch (_) {}
        tc.auto_spec = {
            target_url: targetUrl,
            actions: parsedActions,
        };
    }

    if (!silent) {
        expandedCards.delete(idx);
        renderAutoTestList();
        showToast(`Đã lưu cấu hình cho ${tc.id}!`);
    }
};

window.addManualAutoCase = function () {
    const nextNum = autoTestCases.length + 1;
    const newId = `AUTO_${String(nextNum).padStart(3, '0')}`;
    autoTestCases.push({
        id: newId,
        test_suite: 'Kịch bản Bổ sung',
        muc_dich: `Kiểm tra tự động kịch bản mới #${nextNum}`,
        test_type: 'API',
        priority: 'High',
        dieu_kien_tien_quyet: 'Server sẵn sàng',
        cac_buoc: '1. Gửi HTTP request\n2. Kiểm tra phản hồi',
        ket_qua_mong_muon: 'HTTP 200 OK',
        auto_spec: {
            method: 'GET',
            endpoint: '/api/health',
            headers: { Accept: 'application/json' },
            body: null,
            expected_status: 200,
            assertions: [{ type: 'status_code', expected: 200 }],
        },
    });
    expandedCards.add(autoTestCases.length - 1);
    updateSummaryStats();
    renderAutoTestList();
};

window.deleteAutoCase = function (idx) {
    const tc = autoTestCases[idx];
    if (!tc) return;
    delete executionResults[tc.id];
    autoTestCases.splice(idx, 1);
    expandedCards.clear();
    updateSummaryStats();
    renderAutoTestList();
};

window.exportAutoTestReport = function () {
    const taskName = document.getElementById('autoTaskName')?.value.trim() || 'AutoTest_Report';
    const report = {
        taskName,
        exportedAt: new Date().toISOString(),
        environment: getEnvConfig(),
        testcases: autoTestCases.map(tc => ({
            ...tc,
            executionResult: executionResults[tc.id] || { status: 'NOT_RUN' },
        })),
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${taskName.replace(/\s+/g, '_')}_AutoTest_Report.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Đã xuất file Báo cáo kết quả Auto Test (.json)!');
};
