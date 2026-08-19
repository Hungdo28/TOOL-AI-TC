// ================= KIỂM TRA ĐĂNG NHẬP =================
const currentUserJson = localStorage.getItem('currentUser');
if (!currentUserJson) {
    window.location.replace('login.html');
}
let currentUser = { role: 'viewer', fullName: 'Khách' };
let hasValidSession = false;
if (currentUserJson) {
    try {
        const parsedUser = JSON.parse(currentUserJson);
        if (
            !parsedUser
            || typeof parsedUser !== 'object'
            || typeof parsedUser.username !== 'string'
            || !parsedUser.username.trim()
            || !['admin', 'viewer'].includes(parsedUser.role)
        ) {
            throw new Error('Dữ liệu đăng nhập không hợp lệ');
        }
        currentUser = {
            username: parsedUser.username.trim(),
            role: parsedUser.role,
            fullName: typeof parsedUser.fullName === 'string' ? parsedUser.fullName : parsedUser.username.trim()
        };
        hasValidSession = true;
    } catch (error) {
        console.error('Không thể đọc thông tin đăng nhập:', error);
        localStorage.removeItem('currentUser');
        window.location.replace('login.html');
    }
}

// Khởi tạo Supabase để lấy danh sách User cho form Chuyển giao
const SUPABASE_URL = 'https://zrwlzthteixjxdhsevkh.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_yA_P7i5OXAffRJwHx3hGvw_Wyo02_u3';
let supabaseClient = null;
if (window.supabase) {
    supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

// Hàm xử lý đăng xuất
window.logout = function () {
    if (confirm('Bạn có chắc chắn muốn thoát?')) {
        localStorage.removeItem('currentUser');
        window.location.replace('login.html');
    }
};

function requireAdmin() {
    if (currentUser.role === 'admin') return true;
    alert('❌ Bạn không có quyền thực hiện thao tác này.');
    return false;
}

// ================= CẤU HÌNH API =================
const URL_GET_LIST = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/1981ca71-5359-43d7-94a4-aef5615653ea';
const URL_POST_RUN = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/luong-chuc-nang';
const URL_POST_ADD = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/7dea3b89-0dcf-4a98-b60b-191bdcb78e67';
const URL_POST_EDIT = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/sua-tai-lieu';
const URL_POST_DELETE = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/xoa-tai-lieu';
const URL_POST_UPDATE_STATUS = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/trang-thai';
const URL_POST_TRANSFER = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/chuyen-giao';
const REQUEST_TIMEOUT_MS = 30000;
const PROCESSING_TIMEOUT_MS = 60 * 60 * 1000;
const MAX_FILE_SIZE = 20 * 1024 * 1024;
const MAX_TOTAL_FILE_SIZE = 50 * 1024 * 1024;
const ALLOWED_FILE_EXTENSIONS = new Set(['doc', 'docx', 'xls', 'xlsx', 'pdf', 'txt']);


let dataRows = [];
let addMode = 'manual';
let pollingTimer = null;
let processingTasks = [];
let taskStartTime = {};
let runContextByTask = {};
let testcaseReviewQueue = [];
let activeTestcaseReview = null;
let taskExecutionInfo = {};
let elapsedTimeTimer = null;
let toastTimer = null;

function formatElapsedTime(startTime) {
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startTime) / 1000));
    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor((elapsedSeconds % 3600) / 60);
    const seconds = elapsedSeconds % 60;

    return hours > 0
        ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
        : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function updateRunningTaskTimers() {
    document.querySelectorAll('.task-elapsed-time').forEach(element => {
        const startTime = taskStartTime[element.dataset.taskName];
        if (startTime) element.textContent = formatElapsedTime(startTime);
    });

    if (processingTasks.length === 0 && elapsedTimeTimer) {
        clearInterval(elapsedTimeTimer);
        elapsedTimeTimer = null;
    }
}

function startElapsedTimeUpdates() {
    updateRunningTaskTimers();
    if (!elapsedTimeTimer) {
        elapsedTimeTimer = setInterval(updateRunningTaskTimers, 1000);
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('appToast');
    const toastMessage = document.getElementById('appToastMessage');
    if (!toast || !toastMessage) return;

    const colorClasses = type === 'success'
        ? ['border-emerald-200', 'bg-emerald-50', 'text-emerald-800']
        : ['border-blue-200', 'bg-blue-50', 'text-blue-800'];

    toast.className = `fixed top-5 left-5 right-5 sm:left-auto sm:w-full z-[80] max-w-sm rounded-xl border shadow-lg px-4 py-3 transition-all ${colorClasses.join(' ')}`;
    toastMessage.textContent = message;
    toast.classList.remove('hidden');

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 6000);
}

async function syncExecutionMetadataFromResponse(response, taskNames) {
    try {
        const responseBody = await response.clone().json();
        const data = Array.isArray(responseBody) ? responseBody[0] : responseBody;
        if (!data || typeof data !== 'object') return;

        const executionId = data.executionId || data.execution_id || data.execution?.id || '';
        const startedAtValue = data.startedAt || data.started_at || data.execution?.startedAt || '';
        const n8nStartedAt = Date.parse(startedAtValue);

        taskNames.forEach(taskName => {
            taskExecutionInfo[taskName] = { executionId, startedAt: startedAtValue };
            if (Number.isFinite(n8nStartedAt)) taskStartTime[taskName] = n8nStartedAt;
        });
        updateRunningTaskTimers();
    } catch (_) {
        // Webhook cũ không trả JSON metadata: tiếp tục dùng giờ bắt đầu tại frontend.
    }
}

function startPollingIfNeeded(runOnce = false) {
    // Đã tắt auto polling GET list. Chỉ chạy khi người dùng chủ động bấm Làm mới.
    if (!runOnce || pollingTimer) return;

    const poll = async () => {
        if (processingTasks.length === 0) {
            pollingTimer = null;
            return;
        }

        const loadedSuccessfully = await loadData();

        // Không kết luận trạng thái hoặc timeout dựa trên dữ liệu cũ khi API lỗi.
        if (!loadedSuccessfully) {
            return;
        }

        const now = Date.now();
        let newlyFinished = [];
        let newlyErrored = [];
        let newlyTimeout = [];

        processingTasks.forEach(tenBaiToan => {
            const row = dataRows.find(r => getColVal(r, 'Bài toán') === tenBaiToan);
            if (row) {
                const currentStatus = getColVal(row, 'Trạng thái') || '';
                const isDone = currentStatus === 'Đã xong';
                const isError = currentStatus.toLowerCase().includes('lỗi') || currentStatus.toLowerCase().includes('thất bại') || currentStatus.toLowerCase().includes('error');

                if (isDone) {
                    newlyFinished.push(tenBaiToan);
                } else if (isError) {
                    newlyErrored.push({ ten: tenBaiToan, status: currentStatus });
                } else if (now - (taskStartTime[tenBaiToan] || now) > PROCESSING_TIMEOUT_MS) {
                    newlyTimeout.push(tenBaiToan);
                }
            } else {
                // Task was deleted from sheet while running?
                newlyTimeout.push(tenBaiToan);
            }
        });

        const toRemove = [...newlyFinished, ...newlyErrored.map(e => e.ten), ...newlyTimeout];
        if (toRemove.length > 0) {
            processingTasks = processingTasks.filter(t => !toRemove.includes(t));
            toRemove.forEach(taskName => {
                delete taskStartTime[taskName];
                delete taskExecutionInfo[taskName];
            });
            renderTable();

            if (newlyFinished.length > 0) {
                const tasksNeedingReview = newlyFinished.filter(taskName => {
                    const context = runContextByTask[taskName];
                    return context && context.requiresTestcaseReview;
                });
                const tasksWithoutReview = newlyFinished.filter(taskName => !tasksNeedingReview.includes(taskName));

                tasksNeedingReview.forEach(queueTestcaseReview);
                tasksWithoutReview.forEach(taskName => delete runContextByTask[taskName]);

                if (tasksWithoutReview.length > 0) {
                    alert(`🎉 XUẤT SẮC! Đã xử lý xong: ${tasksWithoutReview.join(', ')}`);
                }
            }
            if (newlyErrored.length > 0) {
                const errMsgs = newlyErrored.map(e => `"${e.ten}": ${e.status}`).join('\n');
                alert(`❌ Lỗi xử lý:\n${errMsgs}`);
            }
            if (newlyTimeout.length > 0) {
                alert(`⏱️ Timeout: Quá 60 phút không phản hồi từ n8n cho:\n${newlyTimeout.join(', ')}\nVui lòng kiểm tra execution tương ứng trên n8n.`);
            }

            [...newlyErrored.map(item => item.ten), ...newlyTimeout]
                .forEach(taskName => delete runContextByTask[taskName]);
        }

        pollingTimer = null;
    };

    return poll();
}

async function refreshDataManually() {
    if (processingTasks.length > 0) {
        await startPollingIfNeeded(true);
    } else {
        await loadData();
    }
}

const getColVal = (row, colName) => {
    if (!row || typeof row !== 'object') return '';
    const key = Object.keys(row).find(k => k.trim() === colName);
    return key && row[key] ? row[key] : '';
};

function isValidHttpUrl(value) {
    try {
        const parsedUrl = new URL(String(value).trim());
        return parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:';
    } catch (_) {
        return false;
    }
}

function splitHttpLinks(value) {
    if (!value) return [];
    return String(value)
        .split(/[\n\s]+/)
        .map(url => url.trim())
        .filter(isValidHttpUrl);
}

async function fetchWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        return await fetch(url, { ...options, signal: controller.signal });
    } finally {
        clearTimeout(timeoutId);
    }
}

function setAddMode(mode) {
    addMode = mode;

    const manualBox = document.getElementById('manualUrlBox');
    const importBox = document.getElementById('importFileBox');
    const btnManual = document.getElementById('btnManualMode');
    const btnImport = document.getElementById('btnImportMode');

    if (mode === 'manual') {
        manualBox.classList.remove('hidden');
        importBox.classList.add('hidden');

        btnManual.className = 'px-3 py-2 rounded-xl bg-blue-600 text-white text-sm font-bold transition';
        btnImport.className = 'px-3 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-bold transition';
    } else {
        manualBox.classList.add('hidden');
        importBox.classList.remove('hidden');

        btnManual.className = 'px-3 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-bold transition';
        btnImport.className = 'px-3 py-2 rounded-xl bg-blue-600 text-white text-sm font-bold transition';
    }
}

function resetAddForm() {
    document.getElementById('formAddDoc').reset();

    document.getElementById('addUrlContainer').innerHTML = `
            <input
                type="url"
                class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none transition add-url-input-item"
                placeholder="https://docs.google.com/..."
            >
        `;

    setAddMode('manual');
}

// 1. TẢI DỮ LIỆU & RENDER BẢNG
async function loadData() {
    const tbody = document.getElementById('tableBody');

    if (!pollingTimer) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-10 text-center text-slate-500"><div class="flex flex-col items-center gap-2"><i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i> Đang tải dữ liệu...</div></td></tr>';
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    try {
        const res = await fetchWithTimeout(URL_GET_LIST + '?t=' + new Date().getTime());
        if (!res.ok) throw new Error('Network error');

        const responseData = await res.json();
        if (!Array.isArray(responseData)) {
            throw new Error('Dữ liệu danh sách từ n8n không hợp lệ');
        }

        dataRows = responseData;
        renderTable();
        return true;
    } catch (err) {
        console.error(err);
        if (!pollingTimer) {
            tbody.innerHTML = `<tr><td colspan="8" class="px-4 py-10 text-center text-red-500"><div class="flex flex-col items-center gap-2"><i data-lucide="alert-circle" class="w-5 h-5"></i> Lỗi kết nối n8n.</div></td></tr>`;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        return false;
    }
}

function renderTable() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    let displayRows = dataRows;

    // Nếu không phải admin, chỉ lấy các bài toán của người làm đó
    if (currentUser.role !== 'admin') {
        displayRows = dataRows.filter(row => {
            const creator = getColVal(row, 'Người làm') || getColVal(row, 'Username') || getColVal(row, 'Tài khoản');
            return String(creator).trim() === currentUser.username;
        });
    }

    if (!Array.isArray(displayRows) || displayRows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-10 text-center">Không có dữ liệu</td></tr>';
        return;
    }

    displayRows.forEach((row, _) => {
        const originalIndex = dataRows.indexOf(row);
        const ten = getColVal(row, 'Bài toán') || '-';
        const nguoiLam = getColVal(row, 'Người làm') || getColVal(row, 'Username') || getColVal(row, 'Tài khoản') || '-';
        let trangThai = getColVal(row, 'Trạng thái') || 'Chưa làm';
        const urlGoc = getColVal(row, 'URL');
        const linkTC = getColVal(row, 'Link Testcase');
        const linkPT = getColVal(row, 'Link tài liệu phân tích');

        const isErrorStatus = trangThai.toLowerCase().includes('lỗi') || trangThai.toLowerCase().includes('thất bại') || trangThai.toLowerCase().includes('error');
        const isDone = trangThai === 'Đã xong';
        const isActivelyProcessing = processingTasks.includes(ten);

        if (isActivelyProcessing) {
            trangThai = 'Đang xử lý AI...';
        }

        const escapeHtml = (value = '') => {
            return String(value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        };

        const shortenText = (text = '', maxLength = 28) => {
            const clean = String(text).trim();
            if (!clean) return '';
            return clean.length > maxLength ? clean.slice(0, maxLength - 1) + '…' : clean;
        };

        const getLinkIcon = (url = '', type = '') => {
            const lowerUrl = String(url).toLowerCase();
            if (type === 'testcase' || lowerUrl.includes('spreadsheets')) return '<i data-lucide="table" class="w-4 h-4 text-emerald-600"></i>';
            if (type === 'analysis') return '<i data-lucide="file-text" class="w-4 h-4 text-blue-600"></i>';
            if (lowerUrl.includes('figma.com')) return '<i data-lucide="figma" class="w-4 h-4 text-purple-600"></i>';
            if (lowerUrl.includes('document')) return '<i data-lucide="file-text" class="w-4 h-4 text-blue-600"></i>';
            return '<i data-lucide="link" class="w-4 h-4 text-slate-400"></i>';
        };

        const getLinkPrefix = (type = 'source', order = 1) => {
            if (type === 'testcase') return order > 1 ? `TC ${order}` : 'TC';
            if (type === 'analysis') return order > 1 ? `PT ${order}` : 'PT';
            return '';
        };

        const makeLink = (linkStr, tenBaiToan, type = 'source') => {
            const urls = splitHttpLinks(linkStr);

            if (urls.length === 0) {
                return '<span class="text-slate-400 italic">Trống</span>';
            }

            const shortTaskName = shortenText(tenBaiToan || 'Tài liệu', 26);

            return `<div class="flex flex-col gap-2 items-center">` + urls.map((url, linkIndex) => {
                const cleanUrl = url.trim();
                const icon = getLinkIcon(cleanUrl, type);
                const prefix = getLinkPrefix(type, linkIndex + 1);
                const label = prefix ? `${prefix} - ${shortTaskName}` : shortTaskName;
                const title = `${prefix ? prefix + ' - ' : ''}${tenBaiToan || 'Tài liệu'}\n${cleanUrl}`;

                let extraBtn = '';
                if (type === 'testcase') {
                    extraBtn = `<button type="button" data-review-url="${escapeHtml(cleanUrl)}" class="review-testcase-btn shrink-0 px-2.5 py-1.5 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded-lg text-xs font-semibold transition-all shadow-sm flex items-center gap-1 border border-blue-200" title="Nhờ AI Review"><i data-lucide="zap" class="w-3 h-3 fill-blue-600 text-blue-600"></i> Review</button>`;
                }

                return `
                        <div class="flex items-center gap-1.5">
                            <a href="${escapeHtml(cleanUrl)}"
                               target="_blank"
                               rel="noopener noreferrer"
                               title="${escapeHtml(title)}"
                               class="inline-flex max-w-[220px] items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/50 hover:text-blue-700 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-300 text-xs font-semibold text-slate-700">
                                <span class="shrink-0 text-sm">${icon}</span>
                                <span class="truncate">${escapeHtml(label)}</span>
                            </a>
                            ${extraBtn}
                        </div>`;
            }).join('') + `</div>`;
        };

        tbody.innerHTML += `
            <tr class="hover:bg-blue-50/30 transition-all duration-300 border-b border-slate-100 group">
                <td class="px-4 py-5 align-top text-center">
                    <div class="inline-flex items-center justify-center p-1 rounded-lg transition-colors group-hover:bg-blue-100/50">
                        <input type="checkbox" class="task-checkbox w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer transition-all" value="${escapeHtml(ten)}">
                    </div>
                </td>

                <td class="px-4 py-5 align-top font-bold text-slate-800 text-[13px] leading-relaxed">${escapeHtml(ten)}</td>

                <td class="px-4 py-5 align-top text-slate-600 font-medium text-xs">
                    <div class="inline-flex items-center gap-1.5 px-2 py-1 bg-slate-100 rounded-md">
                        <i data-lucide="user" class="w-3 h-3 text-slate-500"></i>
                        ${escapeHtml(nguoiLam)}
                    </div>
                </td>

                <td class="px-4 py-5 align-top">
                    ${isActivelyProcessing
                ? `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100 shadow-sm" title="Thời gian xử lý được cập nhật mỗi giây"><i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i><span>Đang chạy</span><span class="task-elapsed-time font-mono tabular-nums text-blue-800" data-task-name="${escapeHtml(ten)}">${formatElapsedTime(taskStartTime[ten] || Date.now())}</span></span>`
                : (currentUser.role === 'admin'
                    ? `<select onchange="updateStatus(${originalIndex}, this.value)" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 cursor-pointer font-semibold outline-none focus:ring-2 focus:ring-blue-500 transition-all shadow-sm appearance-none pr-7 relative bg-no-repeat bg-right hover:border-blue-300 ${trangThai === 'Đã xong' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : (trangThai.toLowerCase().includes('lỗi') || trangThai.toLowerCase().includes('thất bại') || trangThai.toLowerCase().includes('error') ? 'bg-red-50 text-red-600 border-red-200' : 'bg-slate-50 text-slate-600')}" style="background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2394a3b8%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E'); background-size: 8px; background-position: calc(100% - 8px) center;">
                            <option value="Chưa làm" ${trangThai === 'Chưa làm' ? 'selected' : ''}>Chưa làm</option>
                            <option value="Đã xong" ${trangThai === 'Đã xong' ? 'selected' : ''}>Đã xong</option>
                            ${(trangThai !== 'Chưa làm' && trangThai !== 'Đã xong') ? `<option value="${escapeHtml(trangThai)}" selected>${escapeHtml(trangThai)}</option>` : ''}
                        </select>`
                    : `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-sm border ${trangThai === 'Đã xong' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : (trangThai.toLowerCase().includes('lỗi') || trangThai.toLowerCase().includes('thất bại') || trangThai.toLowerCase().includes('error') ? 'bg-red-50 text-red-600 border-red-200' : 'bg-slate-50 text-slate-600 border-slate-200')}">${escapeHtml(trangThai)}</span>`)
            }
                </td>

                <td class="px-4 py-5 align-top min-w-[220px] text-center">${makeLink(urlGoc, ten, 'source')}</td>
                <td class="px-4 py-5 align-top min-w-[220px] text-center">${makeLink(linkTC, ten, 'testcase')}</td>
                <td class="px-4 py-5 align-top min-w-[220px] text-center">${makeLink(linkPT, ten, 'analysis')}</td>

                <!-- CỘT THAO TÁC -->
                <td class="px-4 py-5 align-top min-w-[170px] text-center">
                    <div class="flex items-center justify-center gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity duration-300">
                        <button onclick="downloadSingleTaskFiles(${originalIndex})" class="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 hover:bg-emerald-50 text-slate-600 hover:text-emerald-600 rounded-lg transition-all shadow-sm" title="Tải tài liệu"><i data-lucide="download" class="w-4 h-4"></i></button>
                        <button onclick="runSingleTask(${originalIndex})" class="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 hover:bg-blue-50 text-slate-600 hover:text-blue-600 rounded-lg transition-all shadow-sm" title="Chạy AI"><i data-lucide="play" class="w-4 h-4 fill-current"></i></button>
                        ${currentUser.role === 'admin' ? `
                        <button onclick="openTransferModal(${originalIndex})" class="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 hover:bg-orange-50 text-slate-600 hover:text-orange-600 rounded-lg transition-all shadow-sm" title="Chuyển giao"><i data-lucide="send" class="w-4 h-4"></i></button>
                        <button onclick="editDocument(${originalIndex})" class="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 hover:text-slate-900 rounded-lg transition-all shadow-sm" title="Sửa"><i data-lucide="edit-3" class="w-4 h-4"></i></button>
                        <button onclick="deleteDocument(${originalIndex})" class="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 hover:bg-red-50 text-slate-600 hover:text-red-600 rounded-lg transition-all shadow-sm" title="Xóa"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
                        ` : ''}
                    </div>
                </td>
            </tr>`;
    });

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    updateRunningTaskTimers();
}

// 2. TÌM KIẾM BÀI TOÁN
function searchTasks() {
    const input = document.getElementById("searchInput").value.toLowerCase();
    const tableBody = document.getElementById("tableBody");
    const rows = tableBody.getElementsByTagName("tr");

    for (let i = 0; i < rows.length; i++) {
        if (rows[i].getElementsByTagName("td").length < 2) continue;

        const tdName = rows[i].getElementsByTagName("td")[1];

        if (tdName) {
            const textValue = tdName.textContent || tdName.innerText;
            rows[i].style.display = textValue.toLowerCase().indexOf(input) > -1 ? "" : "none";
        }
    }
}

// 3. THÊM TÀI LIỆU MỚI
async function addDocument(e) {
    e.preventDefault();

    if (!requireAdmin()) return;

    const btnAdd = document.getElementById('btnAdd');
    btnAdd.innerText = 'Đang lưu...';
    btnAdd.disabled = true;

    try {
        const tenBaiToan = document.getElementById('newTenBaiToan').value.trim();

        if (!tenBaiToan) {
            alert("❌ Vui lòng nhập tên bài toán!");
            return;
        }

        const formData = new FormData();
        formData.append('baiToan', tenBaiToan);
        formData.append('mode', addMode);
        formData.append('username', currentUser.username); // Gửi thêm username để lưu trên DB/Google Sheet

        if (addMode === 'manual') {
            const urlInputs = document.querySelectorAll('.add-url-input-item');
            const newUrlsArray = Array.from(urlInputs)
                .map(input => input.value.trim())
                .filter(val => val !== '');

            if (newUrlsArray.length === 0) {
                alert("❌ Vui lòng nhập ít nhất 1 link tài liệu!");
                return;
            }

            if (newUrlsArray.some(url => !isValidHttpUrl(url))) {
                alert("❌ Danh sách có URL không hợp lệ. Chỉ chấp nhận địa chỉ http hoặc https.");
                return;
            }

            formData.append('urlGoc', newUrlsArray.join('\n'));
        } else {
            const files = document.getElementById('localFiles').files;

            if (!files || files.length === 0) {
                alert("❌ Vui lòng chọn ít nhất 1 file!");
                return;
            }

            const invalidFile = Array.from(files).find(file => {
                const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
                return !ALLOWED_FILE_EXTENSIONS.has(extension) || file.size > MAX_FILE_SIZE;
            });
            const totalSize = Array.from(files).reduce((sum, file) => sum + file.size, 0);

            if (invalidFile) {
                alert(`❌ File "${invalidFile.name}" sai định dạng hoặc lớn hơn 20 MB.`);
                return;
            }
            if (totalSize > MAX_TOTAL_FILE_SIZE) {
                alert('❌ Tổng dung lượng file không được vượt quá 50 MB.');
                return;
            }

            for (const file of files) {
                formData.append('files', file);
            }
        }

        const res = await fetchWithTimeout(URL_POST_ADD, {
            method: 'POST',
            body: formData
        }, 60000);

        if (res.ok) {
            resetAddForm();
            await loadData();
            alert("✅ Đã thêm tài liệu thành công vào Sheet!");
        } else {
            alert("❌ Lỗi n8n khi thêm dữ liệu.");
        }
    } catch (err) {
        console.error(err);
        alert("❌ Không thể kết nối tới Webhook thêm tài liệu.");
    } finally {
        btnAdd.innerText = 'Lưu vào Sheet';
        btnAdd.disabled = false;
    }
}

function addNewLinkInputForAdd() {
    const container = document.getElementById('addUrlContainer');

    const input = document.createElement('input');
    input.type = 'url';
    input.className = 'w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none transition add-url-input-item';
    input.placeholder = 'https://...';

    container.appendChild(input);
}

// 4. XÓA TÀI LIỆU
async function deleteDocument(index) {
    if (!requireAdmin()) return;

    const row = dataRows[index];
    const tenBaiToan = getColVal(row, 'Bài toán') || '';

    if (!confirm(`⚠️ Anh có chắc chắn muốn xóa bài toán: "${tenBaiToan}" không? Hành động này không thể hoàn tác!`)) return;

    document.getElementById('loadingText').innerText = 'Đang xóa...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetchWithTimeout(URL_POST_DELETE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ baiToan: tenBaiToan })
        });

        if (res.ok) {
            await loadData();
            alert("✅ Đã xóa thành công!");
        } else {
            alert("❌ Lỗi từ n8n khi xóa dữ liệu.");
        }
    } catch (err) {
        alert("❌ Lỗi mạng: Không thể kết nối tới Webhook xóa.");
    } finally {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
}

// ================= CHUYỂN GIAO BÀI TOÁN =================
let currentTransferTask = '';

async function openTransferModal(index) {
    if (!requireAdmin()) return;

    const row = dataRows[index];
    currentTransferTask = getColVal(row, 'Bài toán') || '';

    document.getElementById('transferTaskName').innerText = currentTransferTask;
    document.getElementById('transferModal').classList.remove('hidden');

    const select = document.getElementById('transferUserSelect');
    select.innerHTML = '<option value="">Đang tải danh sách...</option>';
    select.disabled = true;
    document.getElementById('btnConfirmTransfer').disabled = true;

    try {
        if (!supabaseClient) throw new Error("Chưa khởi tạo Supabase");
        const { data, error } = await supabaseClient.from('users').select('username, role');
        if (error) throw error;

        select.innerHTML = '<option value="">-- Chọn người nhận --</option>';
        data.forEach(u => {
            if (u.username !== currentUser.username) {
                const opt = document.createElement('option');
                opt.value = u.username;
                opt.text = u.username;
                select.appendChild(opt);
            }
        });
        select.disabled = false;

        select.onchange = function () {
            document.getElementById('btnConfirmTransfer').disabled = !this.value;
        };
    } catch (err) {
        console.error("Lỗi lấy user:", err);
        select.replaceChildren();
        const errorOption = document.createElement('option');
        errorOption.value = '';
        errorOption.textContent = `Lỗi: ${err.message || JSON.stringify(err)}`;
        select.appendChild(errorOption);
    }
}

function closeTransferModal() {
    document.getElementById('transferModal').classList.add('hidden');
}

async function confirmTransfer() {
    if (!requireAdmin()) return;

    const select = document.getElementById('transferUserSelect');
    const newUser = select.value;
    if (!newUser) return;

    closeTransferModal();
    document.getElementById('loadingText').innerText = 'Đang chuyển giao...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetchWithTimeout(URL_POST_TRANSFER, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                baiToan: currentTransferTask,
                nguoiNhanMoi: newUser
            })
        });

        if (res.ok) {
            await loadData();
            alert(`✅ Đã chuyển giao bài toán "${currentTransferTask}" cho ${newUser} thành công!`);
        } else {
            alert("❌ Lỗi từ n8n khi chuyển giao. Vui lòng kiểm tra lại Webhook.");
        }
    } catch (err) {
        alert("❌ Lỗi mạng: Không thể kết nối tới Webhook chuyển giao.");
    } finally {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
}

// 5. SỬA TÀI LIỆU
let currentEditOldName = '';
let currentEditOldUrl = '';

function editDocument(index) {
    if (!requireAdmin()) return;

    const row = dataRows[index];

    currentEditOldName = getColVal(row, 'Bài toán') || '';
    currentEditOldUrl = getColVal(row, 'URL') || '';

    document.getElementById('editTenBaiToan').value = currentEditOldName;

    const urlContainer = document.getElementById('editUrlContainer');
    urlContainer.innerHTML = '';

    let urls = currentEditOldUrl.split(/[\n\s]+/).filter(url => url.trim().startsWith('http'));
    if (urls.length === 0) urls = [''];

    urls.forEach(url => addNewLinkInput(url));
    document.getElementById('editModal').classList.remove('hidden');
}

function addNewLinkInput(value = '') {
    const container = document.getElementById('editUrlContainer');

    const input = document.createElement('input');
    input.type = 'url';
    input.value = value;
    input.className = 'w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none transition url-input-item';
    input.placeholder = 'https://...';

    container.appendChild(input);
}

function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
}

document.getElementById('btnSaveEdit').onclick = async function () {
    if (!requireAdmin()) return;

    const newTen = document.getElementById('editTenBaiToan').value.trim();

    const urlInputs = document.querySelectorAll('.url-input-item');
    const newUrlsArray = Array.from(urlInputs)
        .map(input => input.value.trim())
        .filter(val => val !== '');

    const newUrl = newUrlsArray.join('\n');

    if (!newTen) {
        alert("❌ Vui lòng nhập tên bài toán!");
        return;
    }

    if (newUrlsArray.some(url => !isValidHttpUrl(url))) {
        alert("❌ Danh sách có URL không hợp lệ. Chỉ chấp nhận địa chỉ http hoặc https.");
        return;
    }

    if (newTen === currentEditOldName && newUrl === currentEditOldUrl) {
        closeEditModal();
        return;
    }

    closeEditModal();
    document.getElementById('loadingText').innerText = 'Đang cập nhật...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetchWithTimeout(URL_POST_EDIT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                oldBaiToan: currentEditOldName,
                newBaiToan: newTen,
                newUrl: newUrl
            })
        });

        if (res.ok) {
            await loadData();
            alert("✅ Đã cập nhật thành công!");
        } else {
            alert("❌ Lỗi từ n8n khi cập nhật dữ liệu.");
        }
    } catch (err) {
        alert("❌ Lỗi mạng: Không thể kết nối tới Webhook sửa.");
    } finally {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
};

// 6. MỞ MODAL CHẠY AI
let currentRunMode = null; // 'single', 'multiple', 'phan_tich', 'testcase'
let currentRunTask = null;
let currentRunTasksList = [];
const TESTCASE_REVIEW_SUGGESTIONS = [
    {
        id: 'negative',
        label: 'Negative case',
        prompt: 'Bổ sung ít nhất 5 negative testcase cho dữ liệu sai, thiếu dữ liệu và thao tác không hợp lệ.'
    },
    {
        id: 'boundary',
        label: 'Boundary',
        prompt: 'Bổ sung các giá trị biên: nhỏ nhất, lớn nhất, ngay dưới biên, ngay trên biên và dữ liệu rỗng.'
    },
    {
        id: 'permission',
        label: 'Phân quyền',
        prompt: 'Bổ sung testcase cho từng vai trò người dùng, trường hợp không có quyền và truy cập trái phép.'
    },
    {
        id: 'exception',
        label: 'Lỗi hệ thống',
        prompt: 'Bổ sung testcase khi timeout, mất kết nối, API trả lỗi, dữ liệu không đồng bộ và người dùng thử lại.'
    },
    {
        id: 'expected',
        label: 'Expected Result',
        prompt: 'Viết lại Expected Result cụ thể, đo lường và kiểm chứng được; tránh các mô tả chung chung như hoạt động đúng.'
    },
    {
        id: 'duplicates',
        label: 'Loại bỏ trùng lặp',
        prompt: 'Rà soát và gộp các testcase trùng ý nghĩa, nhưng không làm mất phạm vi kiểm thử.'
    },
    {
        id: 'full_regeneration',
        label: 'Viết lại toàn bộ',
        prompt: 'Viết lại toàn bộ bộ testcase theo một cấu trúc rõ ràng hơn, không chỉ bổ sung vài testcase vào kết quả cũ.'
    }
];
let selectedTestcaseReviewSuggestions = new Set();

function renderTestcaseReviewSuggestions() {
    const container = document.getElementById('testcaseReviewSuggestions');
    if (!container) return;

    container.replaceChildren();
    TESTCASE_REVIEW_SUGGESTIONS.forEach(suggestion => {
        const isSelected = selectedTestcaseReviewSuggestions.has(suggestion.id);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = isSelected
            ? 'px-3 py-2 rounded-lg text-xs font-semibold border border-blue-300 bg-blue-50 text-blue-700 transition-all'
            : 'px-3 py-2 rounded-lg text-xs font-semibold border border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 transition-all';
        button.textContent = `${isSelected ? '✓ ' : '+ '}${suggestion.label}`;
        button.setAttribute('aria-pressed', String(isSelected));
        button.addEventListener('click', () => addTestcaseReviewSuggestion(suggestion.id));
        container.appendChild(button);
    });
}

function addTestcaseReviewSuggestion(suggestionId) {
    if (selectedTestcaseReviewSuggestions.has(suggestionId)) return;

    const suggestion = TESTCASE_REVIEW_SUGGESTIONS.find(item => item.id === suggestionId);
    if (!suggestion) return;

    const feedbackInput = document.getElementById('testcaseReviewFeedback');
    const currentFeedback = feedbackInput.value.trim();
    feedbackInput.value = `${currentFeedback}${currentFeedback ? '\n' : ''}- ${suggestion.prompt}`;
    selectedTestcaseReviewSuggestions.add(suggestionId);
    renderTestcaseReviewSuggestions();
    feedbackInput.focus();
}

function clearTestcaseReviewSuggestions() {
    selectedTestcaseReviewSuggestions.clear();
    document.getElementById('testcaseReviewFeedback').value = '';
    renderTestcaseReviewSuggestions();
}

function queueTestcaseReview(taskName) {
    const row = dataRows.find(item => getColVal(item, 'Bài toán') === taskName);
    const context = runContextByTask[taskName];
    if (!context) return;

    testcaseReviewQueue.push({
        taskName,
        testcaseUrls: splitHttpLinks(getColVal(row, 'Link Testcase')),
        prompt1: context.prompt1,
        prompt2: context.prompt2
    });
    openNextTestcaseReview();
}

function openNextTestcaseReview() {
    if (activeTestcaseReview || testcaseReviewQueue.length === 0) return;

    activeTestcaseReview = testcaseReviewQueue.shift();
    document.getElementById('testcaseReviewTaskName').textContent = activeTestcaseReview.taskName;
    document.getElementById('testcaseReviewFeedback').value = '';
    selectedTestcaseReviewSuggestions.clear();
    renderTestcaseReviewSuggestions();
    document.getElementById('testcaseReviewDecision').classList.remove('hidden');
    document.getElementById('testcaseReviewRevision').classList.add('hidden');

    const linksContainer = document.getElementById('testcaseReviewLinks');
    linksContainer.replaceChildren();

    if (activeTestcaseReview.testcaseUrls.length === 0) {
        const emptyMessage = document.createElement('p');
        emptyMessage.className = 'text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3';
        emptyMessage.textContent = 'Chưa tìm thấy link testcase. Bạn vẫn có thể yêu cầu AI điều chỉnh và chạy lại.';
        linksContainer.appendChild(emptyMessage);
    } else {
        activeTestcaseReview.testcaseUrls.forEach((url, index) => {
            const link = document.createElement('a');
            link.href = url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.className = 'inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-xl text-sm font-semibold transition-all';
            link.textContent = activeTestcaseReview.testcaseUrls.length > 1
                ? `Mở testcase ${index + 1}`
                : 'Mở testcase để xem lại';
            linksContainer.appendChild(link);
        });
    }

    document.getElementById('testcaseReviewModal').classList.remove('hidden');
}

function approveTestcaseReview() {
    if (!activeTestcaseReview) return;

    delete runContextByTask[activeTestcaseReview.taskName];
    activeTestcaseReview = null;
    document.getElementById('testcaseReviewModal').classList.add('hidden');
    openNextTestcaseReview();
}

function showTestcaseRevisionForm() {
    document.getElementById('testcaseReviewDecision').classList.add('hidden');
    document.getElementById('testcaseReviewRevision').classList.remove('hidden');
    document.getElementById('testcaseReviewFeedback').focus();
}

function cancelTestcaseRevision() {
    document.getElementById('testcaseReviewRevision').classList.add('hidden');
    document.getElementById('testcaseReviewDecision').classList.remove('hidden');
}

async function rerunTestcaseFromReview() {
    if (!activeTestcaseReview) return;

    const feedbackInput = document.getElementById('testcaseReviewFeedback');
    const additionalPrompt = feedbackInput.value.trim();
    if (!additionalPrompt) {
        feedbackInput.focus();
        alert('⚠️ Vui lòng nhập nội dung muốn AI điều chỉnh.');
        return;
    }

    const review = activeTestcaseReview;
    const revisedPrompt = [
        review.prompt2,
        review.testcaseUrls.length > 0 ? `TESTCASE HIỆN TẠI:\n${review.testcaseUrls.join('\n')}` : '',
        'YÊU CẦU ĐIỀU CHỈNH SAU KHI NGƯỜI DÙNG REVIEW:',
        additionalPrompt,
        'Các yêu cầu điều chỉnh trên là bắt buộc. Hãy đối chiếu với testcase hiện tại, cập nhật nội dung thực sự thay vì chỉ diễn đạt lại, loại bỏ testcase trùng và bảo đảm Expected Result có thể kiểm chứng.'
    ].filter(Boolean).join('\n\n');

    activeTestcaseReview = null;
    document.getElementById('testcaseReviewModal').classList.add('hidden');
    await doRunSingle(review.taskName, review.prompt1, revisedPrompt, 'testcase');
    openNextTestcaseReview();
}

function closeRunAIModal() {
    document.getElementById('runAIModal').classList.add('hidden');
}

function setRunAIModalTitle(title) {
    const titleElement = document.getElementById('runAIModalTitle');
    titleElement.replaceChildren();

    const icon = document.createElement('i');
    icon.setAttribute('data-lucide', 'bot');
    icon.className = 'w-5 h-5 text-blue-600 inline-block mr-2';

    titleElement.appendChild(icon);
    titleElement.appendChild(document.createTextNode(title));

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function runSingleTask(index) {
    const row = dataRows[index];
    if (!row) return;

    currentRunTask = getColVal(row, 'Bài toán');
    currentRunMode = 'single';
    setRunAIModalTitle(`Chạy AI - ${currentRunTask}`);
    document.getElementById('runAIModal').classList.remove('hidden');
}

function openPromptModal(taskName, type) {
    currentRunTask = taskName;
    currentRunMode = type; // 'phan_tich' or 'testcase'
    const typeLabel = type === 'phan_tich' ? 'Phân tích' : 'Testcase';
    setRunAIModalTitle(`Chạy AI (${typeLabel}) - ${currentRunTask}`);
    document.getElementById('runAIModal').classList.remove('hidden');
}

function toggleSelectAll(masterCheckbox) {
    const checkboxes = document.querySelectorAll('.task-checkbox:not([disabled])');
    checkboxes.forEach(cb => cb.checked = masterCheckbox.checked);
}

function runSelectedTasks() {
    const selectedBoxes = document.querySelectorAll('.task-checkbox:checked');
    const selectedTasks = Array.from(selectedBoxes).map(cb => cb.value);

    if (selectedTasks.length === 0) {
        alert("⚠️ Vui lòng tích chọn ít nhất một bài toán để chạy!");
        return;
    }

    const availableTasks = selectedTasks.filter(taskName => !processingTasks.includes(taskName));
    if (availableTasks.length === 0) {
        alert('⚠️ Các bài toán đã chọn đều đang được xử lý.');
        return;
    }

    currentRunTasksList = availableTasks;
    currentRunMode = 'multiple';
    setRunAIModalTitle(`Chạy AI - ${availableTasks.length} bài toán`);
    document.getElementById('runAIModal').classList.remove('hidden');
}

async function executeRunAI() {
    const prompt1 = document.getElementById('runPrompt1').value.trim();
    const prompt2 = document.getElementById('runPrompt2').value.trim();

    closeRunAIModal();

    if (currentRunMode === 'single' || currentRunMode === 'phan_tich' || currentRunMode === 'testcase') {
        await doRunSingle(currentRunTask, prompt1, prompt2, currentRunMode);
    } else if (currentRunMode === 'multiple') {
        await doRunMultiple(currentRunTasksList, prompt1, prompt2);
    }
}

// 7. THỰC THI CHẠY AI (API CALL)
async function doRunSingle(tenBaiToan, prompt1, prompt2, mode) {
    if (!tenBaiToan || processingTasks.includes(tenBaiToan)) {
        alert('⚠️ Bài toán này đang được xử lý. Vui lòng chờ hoàn thành.');
        return;
    }

    taskStartTime[tenBaiToan] = Date.now();
    processingTasks.push(tenBaiToan);
    startElapsedTimeUpdates();
    runContextByTask[tenBaiToan] = {
        prompt1,
        prompt2,
        requiresTestcaseReview: mode !== 'phan_tich'
    };
    renderTable();

    document.getElementById('loadingText').innerText = `Đang gửi lệnh sang n8n...`;
    document.getElementById('loadingOverlay').classList.remove('hidden');

    const payload = {
        baiToan: tenBaiToan,
        promptAI1: prompt1,
        promptAI2: prompt2,
        loaiChay: mode
    };

    try {
        const res = await fetchWithTimeout(URL_POST_RUN, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        document.getElementById('loadingOverlay').classList.add('hidden');

        if (res.ok) {
            await syncExecutionMetadataFromResponse(res, [tenBaiToan]);
            showToast('Đã gửi lệnh tới n8n. Bộ đếm vẫn chạy trực tiếp; bấm Làm mới để kiểm tra kết quả.', 'success');
        } else {
            processingTasks = processingTasks.filter(item => item !== tenBaiToan);
            delete taskStartTime[tenBaiToan];
            delete taskExecutionInfo[tenBaiToan];
            delete runContextByTask[tenBaiToan];
            renderTable();
            alert("❌ Lỗi: n8n từ chối yêu cầu.");
        }
    } catch (err) {
        processingTasks = processingTasks.filter(item => item !== tenBaiToan);
        delete taskStartTime[tenBaiToan];
        delete taskExecutionInfo[tenBaiToan];
        delete runContextByTask[tenBaiToan];
        renderTable();
        document.getElementById('loadingOverlay').classList.add('hidden');
        alert("❌ Lỗi kết nối n8n.");
    }
}

async function doRunMultiple(selectedTasks, prompt1, prompt2) {
    selectedTasks = [...new Set(selectedTasks)].filter(taskName => taskName && !processingTasks.includes(taskName));
    if (selectedTasks.length === 0) {
        alert('⚠️ Không có bài toán hợp lệ để chạy.');
        return;
    }

    selectedTasks.forEach(t => taskStartTime[t] = Date.now());
    processingTasks.push(...selectedTasks);
    startElapsedTimeUpdates();
    selectedTasks.forEach(taskName => {
        runContextByTask[taskName] = {
            prompt1,
            prompt2,
            requiresTestcaseReview: true
        };
    });
    renderTable();

    document.getElementById('loadingText').innerText = `Đang gửi lệnh sang n8n...`;
    document.getElementById('loadingOverlay').classList.remove('hidden');

    const payload = {
        danhSachBaiToan: selectedTasks,
        promptAI1: prompt1,
        promptAI2: prompt2
    };

    try {
        const res = await fetchWithTimeout(URL_POST_RUN, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        document.getElementById('loadingOverlay').classList.add('hidden');

        if (res.ok) {
            await syncExecutionMetadataFromResponse(res, selectedTasks);
            showToast(`Đã gửi ${selectedTasks.length} bài tới n8n. Bấm Làm mới để kiểm tra kết quả khi xử lý xong.`, 'success');
            document.getElementById('selectAll').checked = false;
        } else {
            processingTasks = processingTasks.filter(item => !selectedTasks.includes(item));
            selectedTasks.forEach(taskName => delete taskStartTime[taskName]);
            selectedTasks.forEach(taskName => delete taskExecutionInfo[taskName]);
            selectedTasks.forEach(taskName => delete runContextByTask[taskName]);
            renderTable();
            alert("❌ Lỗi: n8n từ chối yêu cầu.");
        }
    } catch (err) {
        processingTasks = processingTasks.filter(item => !selectedTasks.includes(item));
        selectedTasks.forEach(taskName => delete taskStartTime[taskName]);
        selectedTasks.forEach(taskName => delete taskExecutionInfo[taskName]);
        selectedTasks.forEach(taskName => delete runContextByTask[taskName]);
        renderTable();
        document.getElementById('loadingOverlay').classList.add('hidden');
        alert("❌ Lỗi kết nối n8n.");
    }
}

async function updateStatus(index, newStatus) {
    if (!requireAdmin()) {
        renderTable();
        return;
    }

    const row = dataRows[index];
    const tenBaiToan = getColVal(row, 'Bài toán') || '';

    if (!tenBaiToan) {
        alert("❌ Không tìm thấy tên bài toán.");
        return;
    }

    if (!confirm(`Đổi trạng thái "${tenBaiToan}" thành "${newStatus}"?`)) {
        renderTable();
        return;
    }

    document.getElementById('loadingText').innerText = 'Đang cập nhật trạng thái...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetchWithTimeout(URL_POST_UPDATE_STATUS, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                baiToan: tenBaiToan,
                trangThai: newStatus
            })
        });

        if (res.ok) {
            await loadData();
            alert("✅ Đã cập nhật trạng thái!");
        } else {
            renderTable();
            alert("❌ Lỗi n8n khi cập nhật trạng thái.");
        }
    } catch (err) {
        renderTable();
        alert("❌ Không thể kết nối webhook cập nhật trạng thái.");
    } finally {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
}

// 8. TẢI FILE CHO TỪNG BÀI TOÁN
function downloadSingleTaskFiles(index) {
    const row = dataRows[index];
    if (!row) return;

    const tenBaiToan = getColVal(row, 'Bài toán') || 'bài toán này';

    const urlGoc = getColVal(row, 'URL') || '';
    const linkTC = getColVal(row, 'Link Testcase') || '';
    const linkPT = getColVal(row, 'Link tài liệu phân tích') || '';

    const allLinks = [
        ...splitHttpLinks(urlGoc),
        ...splitHttpLinks(linkTC),
        ...splitHttpLinks(linkPT)
    ];

    if (allLinks.length === 0) {
        alert(`⚠️ Không có link tài liệu hợp lệ để tải cho: "${tenBaiToan}"`);
        return;
    }

    let downloadCount = 0;

    allLinks.forEach((url) => {
        let downloadUrl = '';

        if (url.includes('/spreadsheets/d/')) {
            const match = url.match(/\/d\/([a-zA-Z0-9-_]+)/);
            if (match) downloadUrl = `https://docs.google.com/spreadsheets/d/${match[1]}/export?format=xlsx`;
        } else if (url.includes('/document/d/')) {
            const match = url.match(/\/d\/([a-zA-Z0-9-_]+)/);
            if (match) downloadUrl = `https://docs.google.com/document/d/${match[1]}/export?format=docx`;
        }

        if (downloadUrl) {
            downloadCount++;

            // Dùng iframe để tải nhiều file cùng lúc không bị trình duyệt chặn
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = downloadUrl;
            document.body.appendChild(iframe);

            // Xóa iframe sau khi trình duyệt đã bắt đầu tải
            setTimeout(() => {
                document.body.removeChild(iframe);
            }, 5000);
        }
    });

    if (downloadCount > 0) {
        alert(`✅ Đang tải ${downloadCount} file tài liệu của bài:\n"${tenBaiToan}"`);
    } else {
        alert(`⚠️ Link có tồn tại nhưng không phải là Google Docs/Sheets (Có thể là link Figma hoặc link web khác).`);
    }
}
document.addEventListener("DOMContentLoaded", () => {
    const aiToggle = document.getElementById("aiToggle");
    const aiPanel = document.getElementById("aiPanel");
    const closeAI = document.getElementById("closeAI");

    if (!aiToggle || !aiPanel || !closeAI) return;

    aiToggle.addEventListener("click", () => {
        aiPanel.classList.remove("hidden");
        aiPanel.classList.add("flex");
    });

    closeAI.addEventListener("click", () => {
        aiPanel.classList.add("hidden");
        aiPanel.classList.remove("flex");
    });

    document.addEventListener('click', (event) => {
        const reviewButton = event.target.closest('.review-testcase-btn');
        if (!reviewButton) return;

        const reviewUrl = reviewButton.dataset.reviewUrl;
        if (reviewUrl) window.askAIToReview(reviewUrl);
    });
});

window.askAIToReview = function (url) {
    const prompt = `Review giúp tôi test case ở link sau. Hãy phân tích điểm mạnh, điểm yếu và đề xuất 3-5 kịch bản test bổ sung:\n\n${url}`;

    navigator.clipboard.writeText(prompt).then(() => {
        alert('✅ Đã copy yêu cầu review cùng link Testcase!\n\nHãy mở bảng AI và nhấn Ctrl+V (hoặc Chuột phải -> Paste) vào khung chat để gửi cho bot nhé!');

        // Mở bảng AI
        const aiPanel = document.getElementById("aiPanel");
        if (aiPanel) {
            aiPanel.classList.remove("hidden");
            aiPanel.classList.add("flex");
        }
    }).catch(err => {
        console.error('Lỗi copy:', err);
        alert('❌ Có lỗi xảy ra khi copy. Vui lòng copy link thủ công nhé!');
    });
};

window.addEventListener('load', () => {
    if (!hasValidSession) return;

    // Hiển thị thông tin user trên Header
    const displayFullName = document.getElementById('displayFullName');
    const displayRole = document.getElementById('displayRole');
    if (displayFullName) displayFullName.innerText = currentUser.fullName || 'Khách';
    if (displayRole) displayRole.innerText = currentUser.role === 'admin' ? 'Quản trị viên' : 'Người dùng';

    if (currentUser.role !== 'admin') {
        // Ẩn panel thêm bài toán
        const leftPanel = document.getElementById('leftPanel');
        if (leftPanel) leftPanel.style.display = 'none';

        // Mở rộng bảng ra toàn bộ
        const tablePanel = document.getElementById('tablePanel');
        if (tablePanel) {
            tablePanel.classList.remove('xl:col-span-3');
            tablePanel.classList.add('xl:col-span-4');
        }
    }

    loadData();
});
