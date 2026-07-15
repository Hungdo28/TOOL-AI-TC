// ================= CẤU HÌNH API =================
const URL_MASTER_SHEET = 'https://docs.google.com/spreadsheets/d/1oyWC0Z12SjiAVH8P023HjQtnHFprKFCQgmBCqqytZW0/edit?gid=0#gid=0';
const URL_GET_LIST = 'https://vdtc-hungdv.tailfb2503.ts.net:8443/webhook/1981ca71-5359-43d7-94a4-aef5615653ea';
const URL_POST_RUN = 'https://vdtc-hungdv.tailfb2503.ts.net/webhook/luong-chuc-nang';
const URL_POST_ADD = 'https://vdtc-hungdv.tailfb2503.ts.net/webhook/7dea3b89-0dcf-4a98-b60b-191bdcb78e67';
const URL_POST_EDIT = 'https://vdtc-hungdv.tailfb2503.ts.net/webhook/sua-tai-lieu';
const URL_POST_DELETE = 'https://vdtc-hungdv.tailfb2503.ts.net/webhook/xoa-tai-lieu';
const URL_POST_UPDATE_STATUS = 'https://vdtc-hungdv.tailfb2503.ts.net/webhook/trang-thai';

document.getElementById('btnOpenSheet').href = URL_MASTER_SHEET;

let dataRows = [];
let addMode = 'manual';
let pollingTimer = null;
let processingTasks = [];

const getColVal = (row, colName) => {
    const key = Object.keys(row).find(k => k.trim() === colName);
    return key && row[key] ? row[key] : '';
};

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
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-10 text-center text-slate-400">🔄 Đang tải dữ liệu...</td></tr>';
    }

    try {
        const res = await fetch(URL_GET_LIST + '?t=' + new Date().getTime());
        if (!res.ok) throw new Error('Network error');

        dataRows = await res.json();
        renderTable();
    } catch (err) {
        console.error(err);
        if (!pollingTimer) {
            tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-10 text-center text-red-500">❌ Lỗi kết nối n8n.</td></tr>`;
        }
    }
}

function renderTable() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    if (!Array.isArray(dataRows) || dataRows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-10 text-center">Không có dữ liệu</td></tr>';
        return;
    }

    dataRows.forEach((row, index) => {
        const ten = getColVal(row, 'Bài toán') || '-';
        let trangThai = getColVal(row, 'Trạng thái') || 'Chưa làm';
        const urlGoc = getColVal(row, 'URL');
        const linkTC = getColVal(row, 'Link Testcase');
        const linkPT = getColVal(row, 'Link tài liệu phân tích');

        if (processingTasks.includes(ten) && trangThai !== 'Đã xong') {
            trangThai = '⏳ Đang xử lý AI...';
        }

        if (trangThai === 'Đã xong') {
            processingTasks = processingTasks.filter(item => item !== ten);
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

        const splitLinks = (linkStr) => {
            if (!linkStr) return [];
            return String(linkStr)
                .split(/[\n\s]+/)
                .map(url => url.trim())
                .filter(url => url.startsWith('http'));
        };

        const getLinkIcon = (url = '', type = '') => {
            const lowerUrl = String(url).toLowerCase();
            if (type === 'testcase' || lowerUrl.includes('spreadsheets')) return '📊';
            if (type === 'analysis') return '📋';
            if (lowerUrl.includes('figma.com')) return '🎨';
            if (lowerUrl.includes('document')) return '📄';
            return '🔗';
        };

        const getLinkPrefix = (type = 'source', order = 1) => {
            if (type === 'testcase') return order > 1 ? `TC ${order}` : 'TC';
            if (type === 'analysis') return order > 1 ? `PT ${order}` : 'PT';
            return '';
        };

        const makeLink = (linkStr, tenBaiToan, type = 'source') => {
            const urls = splitLinks(linkStr);

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
                    extraBtn = `<button onclick="askAIToReview('${escapeHtml(cleanUrl)}')" class="shrink-0 px-2.5 py-1.5 bg-gradient-to-r from-purple-500 to-fuchsia-500 hover:from-purple-600 hover:to-fuchsia-600 text-white rounded-xl text-xs font-bold transition-all shadow-sm hover:shadow-md hover:-translate-y-0.5 flex items-center gap-1" title="Nhờ AI Review">🤖 Review</button>`;
                }

                return `
                        <div class="flex items-center gap-1.5">
                            <a href="${escapeHtml(cleanUrl)}"
                               target="_blank"
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
                        <input type="checkbox" class="task-checkbox w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer transition-all">
                    </div>
                </td>

                <td class="px-4 py-5 align-top font-bold text-slate-800 text-[13px] leading-relaxed">${escapeHtml(ten)}</td>

                <td class="px-4 py-5 align-top">
                    ${processingTasks.includes(ten) && trangThai !== 'Đã xong'
                ? `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-blue-100 text-blue-700 animate-pulse border border-blue-200 shadow-sm">⏳ Đang xử lý...</span>`
                : `<select onchange="updateStatus(${index}, this.value)" class="px-3 py-1.5 text-xs rounded-xl border border-slate-200/80 cursor-pointer font-bold outline-none focus:ring-2 focus:ring-blue-500 transition-all shadow-sm appearance-none pr-7 relative bg-no-repeat bg-right hover:border-blue-300 ${trangThai === 'Đã xong' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-50 text-slate-600'}" style="background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2394a3b8%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E'); background-size: 8px; background-position: calc(100% - 8px) center;">
                            <option value="Chưa làm" ${trangThai === 'Chưa làm' ? 'selected' : ''}>🔴 Chưa làm</option>
                            <option value="Đã xong" ${trangThai === 'Đã xong' ? 'selected' : ''}>🟢 Đã xong</option>
                        </select>`
            }
                </td>

                <td class="px-4 py-5 align-top min-w-[220px] text-center">${makeLink(urlGoc, ten, 'source')}</td>
                <td class="px-4 py-5 align-top min-w-[220px] text-center">${makeLink(linkTC, ten, 'testcase')}</td>
                <td class="px-4 py-5 align-top min-w-[220px] text-center">${makeLink(linkPT, ten, 'analysis')}</td>

                <!-- CỘT THAO TÁC -->
                <td class="px-4 py-5 align-top min-w-[150px] text-center">
                    <div class="flex items-center justify-center gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity duration-300">
                        <button onclick="runSingleTask(${index})" class="w-8 h-8 flex items-center justify-center bg-blue-50 hover:bg-blue-600 text-blue-600 hover:text-white rounded-lg transition-all shadow-sm hover:shadow-md hover:-translate-y-0.5" title="Chạy AI">▶️</button>
                        <button onclick="editDocument(${index})" class="w-8 h-8 flex items-center justify-center bg-amber-50 hover:bg-amber-500 text-amber-600 hover:text-white rounded-lg transition-all shadow-sm hover:shadow-md hover:-translate-y-0.5" title="Sửa">✏️</button>
                        <button onclick="deleteDocument(${index})" class="w-8 h-8 flex items-center justify-center bg-red-50 hover:bg-red-500 text-red-600 hover:text-white rounded-lg transition-all shadow-sm hover:shadow-md hover:-translate-y-0.5" title="Xóa">🗑️</button>
                    </div>
                </td>
            </tr>`;
    });
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

        if (addMode === 'manual') {
            const urlInputs = document.querySelectorAll('.add-url-input-item');
            const newUrlsArray = Array.from(urlInputs)
                .map(input => input.value.trim())
                .filter(val => val !== '');

            if (newUrlsArray.length === 0) {
                alert("❌ Vui lòng nhập ít nhất 1 link tài liệu!");
                return;
            }

            formData.append('urlGoc', newUrlsArray.join('\n'));
        } else {
            const files = document.getElementById('localFiles').files;

            if (!files || files.length === 0) {
                alert("❌ Vui lòng chọn ít nhất 1 file!");
                return;
            }

            for (const file of files) {
                formData.append('files', file);
            }
        }

        const res = await fetch(URL_POST_ADD, {
            method: 'POST',
            body: formData
        });

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
    const row = dataRows[index];
    const tenBaiToan = getColVal(row, 'Bài toán') || '';

    if (!confirm(`⚠️ Anh có chắc chắn muốn xóa bài toán: "${tenBaiToan}" không? Hành động này không thể hoàn tác!`)) return;

    document.getElementById('loadingText').innerText = 'Đang xóa...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetch(URL_POST_DELETE, {
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

// 5. SỬA TÀI LIỆU
let currentEditOldName = '';
let currentEditOldUrl = '';

function editDocument(index) {
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

    if (newTen === currentEditOldName && newUrl === currentEditOldUrl) {
        closeEditModal();
        return;
    }

    closeEditModal();
    document.getElementById('loadingText').innerText = 'Đang cập nhật...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetch(URL_POST_EDIT, {
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

function closeRunAIModal() {
    document.getElementById('runAIModal').classList.add('hidden');
}

function runSingleTask(index) {
    const row = dataRows[index];
    currentRunTask = getColVal(row, 'Bài toán');
    currentRunMode = 'single';
    document.getElementById('runAIModalTitle').innerHTML = `<span>🚀</span> Chạy AI - ${currentRunTask}`;
    document.getElementById('runAIModal').classList.remove('hidden');
}

function openPromptModal(taskName, type) {
    currentRunTask = taskName;
    currentRunMode = type; // 'phan_tich' or 'testcase'
    const typeLabel = type === 'phan_tich' ? 'Phân tích' : 'Testcase';
    document.getElementById('runAIModalTitle').innerHTML = `<span>🚀</span> Chạy AI (${typeLabel}) - ${currentRunTask}`;
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

    currentRunTasksList = selectedTasks;
    currentRunMode = 'multiple';
    document.getElementById('runAIModalTitle').innerHTML = `<span>🚀</span> Chạy AI - ${selectedTasks.length} bài toán`;
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
    processingTasks.push(tenBaiToan);
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
        const res = await fetch(URL_POST_RUN, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        document.getElementById('loadingOverlay').classList.add('hidden');

        if (res.ok) {
            alert(`✅ Đã gửi lệnh thành công!\nHệ thống đang xử lý ngầm, anh cứ làm việc khác nhé.`);

            if (!pollingTimer) {
                pollingTimer = setInterval(async () => {
                    await loadData();

                    const currentRow = dataRows.find(r => getColVal(r, 'Bài toán') === tenBaiToan);

                    if (currentRow && getColVal(currentRow, 'Trạng thái') === 'Đã xong') {
                        clearInterval(pollingTimer);
                        pollingTimer = null;
                        alert(`🎉 XUẤT SẮC! Bài toán "${tenBaiToan}" đã phân tích xong!`);
                    }
                }, 100000);
            }
        } else {
            processingTasks = processingTasks.filter(item => item !== tenBaiToan);
            renderTable();
            alert("❌ Lỗi: n8n từ chối yêu cầu.");
        }
    } catch (err) {
        processingTasks = processingTasks.filter(item => item !== tenBaiToan);
        renderTable();
        document.getElementById('loadingOverlay').classList.add('hidden');
        alert("❌ Lỗi kết nối n8n.");
    }
}

async function doRunMultiple(selectedTasks, prompt1, prompt2) {
    processingTasks.push(...selectedTasks);
    renderTable();

    document.getElementById('loadingText').innerText = `Đang gửi lệnh sang n8n...`;
    document.getElementById('loadingOverlay').classList.remove('hidden');

    const payload = {
        danhSachBaiToan: selectedTasks,
        promptAI1: prompt1,
        promptAI2: prompt2
    };

    try {
        const res = await fetch(URL_POST_RUN, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        document.getElementById('loadingOverlay').classList.add('hidden');

        if (res.ok) {
            alert(`✅ Đã gửi lệnh thành công!\nHệ thống đang xử lý ngầm các bài toán này...`);
            document.getElementById('selectAll').checked = false;

            if (!pollingTimer) {
                pollingTimer = setInterval(async () => {
                    await loadData();

                    const stillUnfinished = dataRows.filter(r =>
                        selectedTasks.includes(getColVal(r, 'Bài toán')) &&
                        getColVal(r, 'Trạng thái') !== 'Đã xong'
                    );

                    if (stillUnfinished.length === 0) {
                        clearInterval(pollingTimer);
                        pollingTimer = null;
                        alert(`🎉 XUẤT SẮC! Toàn bộ ${selectedTasks.length} bài toán anh chọn đã phân tích xong!`);
                    }
                }, 100000);
            }
        } else {
            processingTasks = processingTasks.filter(item => !selectedTasks.includes(item));
            renderTable();
            alert("❌ Lỗi: n8n từ chối yêu cầu.");
        }
    } catch (err) {
        processingTasks = processingTasks.filter(item => !selectedTasks.includes(item));
        renderTable();
        document.getElementById('loadingOverlay').classList.add('hidden');
        alert("❌ Lỗi kết nối n8n.");
    }
}

async function updateStatus(index, newStatus) {
    const row = dataRows[index];
    const tenBaiToan = getColVal(row, 'Bài toán') || '';

    if (!tenBaiToan) {
        alert("❌ Không tìm thấy tên bài toán.");
        return;
    }

    if (!confirm(`Đổi trạng thái "${tenBaiToan}" thành "${newStatus}"?`)) return;

    document.getElementById('loadingText').innerText = 'Đang cập nhật trạng thái...';
    document.getElementById('loadingOverlay').classList.remove('hidden');

    try {
        const res = await fetch(URL_POST_UPDATE_STATUS, {
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
            alert("❌ Lỗi n8n khi cập nhật trạng thái.");
        }
    } catch (err) {
        alert("❌ Không thể kết nối webhook cập nhật trạng thái.");
    } finally {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
}

// 8. TẢI FILE CHO TỪNG BÀI TOÁN
function downloadSingleTaskFiles(index) {
    const row = dataRows[index];
    const tenBaiToan = getColVal(row, 'Bài toán') || 'bài toán này';

    if (!row) return;

    const linkTC = getColVal(row, 'Link Testcase') || '';
    const linkPT = getColVal(row, 'Link tài liệu phân tích') || '';

    const allLinks = [
        ...linkTC.split(/[\n\s]+/),
        ...linkPT.split(/[\n\s]+/)
    ].filter(url => url.startsWith('http'));

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

            setTimeout(() => {
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.target = '_blank';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }, downloadCount * 800);
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

    aiToggle.addEventListener("click", () => {
        aiPanel.classList.remove("hidden");
        aiPanel.classList.add("flex");
    });

    closeAI.addEventListener("click", () => {
        aiPanel.classList.add("hidden");
        aiPanel.classList.remove("flex");
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

window.onload = loadData;
