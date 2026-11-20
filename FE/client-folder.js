// ================= QUẢN LÝ THƯ MỤC LƯU LOCAL TRÊN MÁY NGƯỜI DÙNG (CLIENT) =================
// Dùng File System Access API (Chrome/Edge) + IndexedDB để tự động tạo folder
// `AutoTC_Records/<Tên bài toán>/` và lưu file Word/Excel trực tiếp trên máy người dùng
// khi ứng dụng được host trên server.

(function () {
    const DB_NAME = 'AutoTC_ClientFS_v1';
    const STORE_NAME = 'handles';
    const ROOT_KEY = 'rootRecordsDir';
    const DEFAULT_ROOT_NAME = 'AutoTC_Records';

    function openHandleDb() {
        return new Promise((resolve, reject) => {
            if (!window.indexedDB) {
                reject(new Error('Trình duyệt không hỗ trợ IndexedDB'));
                return;
            }
            const req = window.indexedDB.open(DB_NAME, 1);
            req.onupgradeneeded = () => {
                const db = req.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME);
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error || new Error('Không thể mở IndexedDB'));
        });
    }

    async function loadSavedRootHandle() {
        try {
            const db = await openHandleDb();
            return await new Promise((resolve, reject) => {
                const tx = db.transaction(STORE_NAME, 'readonly');
                const req = tx.objectStore(STORE_NAME).get(ROOT_KEY);
                req.onsuccess = () => resolve(req.result || null);
                req.onerror = () => reject(req.error);
            });
        } catch (err) {
            console.warn('Không thể đọc handle thư mục lưu từ IndexedDB:', err);
            return null;
        }
    }

    async function persistRootHandle(handle) {
        try {
            const db = await openHandleDb();
            await new Promise((resolve, reject) => {
                const tx = db.transaction(STORE_NAME, 'readwrite');
                tx.objectStore(STORE_NAME).put(handle, ROOT_KEY);
                tx.oncomplete = () => resolve();
                tx.onerror = () => reject(tx.error);
            });
        } catch (err) {
            console.warn('Không thể lưu handle thư mục vào IndexedDB:', err);
        }
    }

    function sanitizeName(name) {
        const cleaned = String(name || '')
            .trim()
            .replace(/[<>:"/\\|?*\x00-\x1f]+/g, '_')
            .replace(/^[. ]+|[. ]+$/g, '');
        return cleaned.slice(0, 100) || 'unnamed';
    }

    function isLocalHostUrl(urlOrHost) {
        const raw = String(urlOrHost || '').trim().toLowerCase();
        if (!raw) return true;
        try {
            const host = raw.includes('://') ? new URL(raw).hostname.toLowerCase() : raw;
            return host === 'localhost' || host === '127.0.0.1' || host === '::1';
        } catch {
            return raw.startsWith('localhost') || raw.startsWith('127.0.0.1');
        }
    }

    function isRemoteHosted() {
        const pageHost = window.location.hostname || '';
        const backendUrl = typeof BACKEND_API_BASE !== 'undefined' ? BACKEND_API_BASE : '';
        return !isLocalHostUrl(pageHost) || (backendUrl && !isLocalHostUrl(backendUrl));
    }

    function isFsApiSupported() {
        return typeof window.showDirectoryPicker === 'function' && window.isSecureContext;
    }

    async function ensureWritePermission(handle, requestIfNeeded = true) {
        if (!handle) return false;
        const opts = { mode: 'readwrite' };
        if (typeof handle.queryPermission === 'function') {
            const current = await handle.queryPermission(opts);
            if (current === 'granted') return true;
        }
        if (requestIfNeeded && typeof handle.requestPermission === 'function') {
            const granted = await handle.requestPermission(opts);
            return granted === 'granted';
        }
        return false;
    }

    async function updateFolderButtonUI(handleOverride = undefined) {
        const btn = document.getElementById('btnClientFolder');
        const label = document.getElementById('clientFolderLabel');
        const dot = document.getElementById('clientFolderDot');
        if (!btn || !label || !dot) return;

        const handle = handleOverride !== undefined ? handleOverride : await loadSavedRootHandle();
        if (handle) {
            label.textContent = handle.name || DEFAULT_ROOT_NAME;
            dot.className = 'w-2 h-2 rounded-full bg-emerald-500 shrink-0';
            btn.title = `Đang tự động lưu bài toán vào thư mục "${handle.name}" trên máy của bạn. Bấm để đổi thư mục.`;
        } else {
            label.textContent = isFsApiSupported() ? 'Chọn folder lưu' : 'Tải về máy';
            dot.className = isRemoteHosted()
                ? 'w-2 h-2 rounded-full bg-amber-400 shrink-0'
                : 'w-2 h-2 rounded-full bg-slate-300 shrink-0';
            btn.title = isFsApiSupported()
                ? 'Chọn vị trí trên máy bạn để hệ thống tự tạo thư mục AutoTC_Records lưu file Word & Excel'
                : 'Trình duyệt không hỗ trợ ghi trực tiếp folder; hệ thống sẽ tự tải file về thư mục Downloads';
        }
    }

    async function chooseRootFolder() {
        if (!isFsApiSupported()) {
            throw new Error('Trình duyệt hiện tại không hỗ trợ chọn thư mục trực tiếp (hãy dùng Chrome/Edge qua HTTPS). Hệ thống sẽ tự tải file về Downloads.');
        }
        const picked = await window.showDirectoryPicker({
            id: 'autotc-records-root',
            mode: 'readwrite',
            startIn: 'documents',
        });
        // Nếu người dùng chọn đúng folder tên AutoTC_Records thì dùng luôn, ngược lại tự tạo folder con AutoTC_Records bên trong
        const rootHandle = picked.name.toLowerCase() === DEFAULT_ROOT_NAME.toLowerCase()
            ? picked
            : await picked.getDirectoryHandle(DEFAULT_ROOT_NAME, { create: true });

        await persistRootHandle(rootHandle);
        await updateFolderButtonUI(rootHandle);
        return rootHandle;
    }

    async function getVerifiedRootHandle({ promptIfMissing = false } = {}) {
        let handle = await loadSavedRootHandle();
        if (handle) {
            try {
                const ok = await ensureWritePermission(handle, true);
                if (ok) {
                    await updateFolderButtonUI(handle);
                    return handle;
                }
            } catch (err) {
                console.warn('Quyền truy cập thư mục đã lưu bị từ chối hoặc thư mục không còn tồn tại:', err);
            }
        }
        if (!promptIfMissing) return null;
        return await chooseRootFolder();
    }

    function extractFileNameFromResponse(resp, fallbackName) {
        const xName = resp.headers.get('X-File-Name');
        if (xName) {
            try { return decodeURIComponent(xName); } catch { return xName; }
        }
        const disp = resp.headers.get('Content-Disposition') || '';
        const utf8Match = disp.match(/filename\*=UTF-8''([^;\n]+)/i);
        if (utf8Match && utf8Match[1]) {
            try { return decodeURIComponent(utf8Match[1].trim()); } catch { return utf8Match[1].trim(); }
        }
        const plainMatch = disp.match(/filename="?([^";\n]+)"?/i);
        if (plainMatch && plainMatch[1]) return plainMatch[1].trim();
        return fallbackName;
    }

    async function fetchTaskFileFromServer(taskName, fileType) {
        if (typeof ensureAuthToken === 'function') {
            await ensureAuthToken();
        }
        const url = `${BACKEND_API_BASE}/local/download?taskName=${encodeURIComponent(taskName)}&type=${encodeURIComponent(fileType)}`;
        const headers = typeof getBackendHeaders === 'function' ? getBackendHeaders(false) : {};
        const resp = await fetch(url, { method: 'GET', headers });
        if (resp.status === 404) return null;
        if (!resp.ok) {
            const errText = await resp.text().catch(() => '');
            throw new Error(`Không thể tải file ${fileType} từ server (HTTP ${resp.status}) ${errText}`.trim());
        }
        const blob = await resp.blob();
        const safeTitle = sanitizeName(taskName);
        const fallbackName = fileType === 'excel'
            ? `[TC] ${safeTitle}.xlsx`
            : `Phân tích bài toán - ${safeTitle}.docx`;
        const fileName = sanitizeName(extractFileNameFromResponse(resp, fallbackName));
        return { blob, fileName, fileType };
    }

    function triggerBrowserDownload(blob, fileName) {
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = fileName;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);
        }, 2000);
    }

    async function writeBlobToDirectory(dirHandle, fileName, blob) {
        const fileHandle = await dirHandle.getFileHandle(fileName, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
    }

    async function saveTaskFilesToClient(taskName, fileTypes = ['excel', 'word'], options = {}) {
        const {
            promptIfMissing = true,
            fallbackDownload = true,
            alsoDownload = false,
        } = options;

        // 1. Lấy các file hiện có từ server trước
        const fetchedFiles = [];
        for (const fType of fileTypes) {
            const item = await fetchTaskFileFromServer(taskName, fType);
            if (item) fetchedFiles.push(item);
        }
        if (fetchedFiles.length === 0) {
            return { mode: 'empty', savedFiles: [], folderLabel: '' };
        }

        // 2. Nếu trình duyệt hỗ trợ File System Access API -> tự tạo folder con & ghi trực tiếp vào máy người dùng
        if (isFsApiSupported()) {
            let rootHandle = null;
            try {
                rootHandle = await getVerifiedRootHandle({ promptIfMissing });
            } catch (err) {
                if (err && err.name === 'AbortError') {
                    // Người dùng bấm Hủy hộp thoại chọn folder -> chuyển sang tải file thường nếu được bật
                    rootHandle = null;
                } else {
                    console.warn('Không thể mở thư mục lưu trên máy người dùng:', err);
                    rootHandle = null;
                }
            }

            if (rootHandle) {
                const safeFolderName = sanitizeName(taskName);
                const taskDirHandle = await rootHandle.getDirectoryHandle(safeFolderName, { create: true });
                const savedNames = [];
                for (const item of fetchedFiles) {
                    await writeBlobToDirectory(taskDirHandle, item.fileName, item.blob);
                    savedNames.push(item.fileName);
                    if (alsoDownload) {
                        triggerBrowserDownload(item.blob, item.fileName);
                    }
                }
                return {
                    mode: 'fs',
                    savedFiles: savedNames,
                    folderLabel: `${rootHandle.name}/${safeFolderName}`,
                };
            }
        }

        // 3. Fallback: tải trực tiếp về thư mục Downloads của trình duyệt
        if (fallbackDownload) {
            const savedNames = [];
            for (const item of fetchedFiles) {
                triggerBrowserDownload(item.blob, item.fileName);
                savedNames.push(item.fileName);
            }
            return {
                mode: 'download',
                savedFiles: savedNames,
                folderLabel: 'Downloads',
            };
        }

        return { mode: 'skipped', savedFiles: [], folderLabel: '' };
    }

    async function hasConfiguredFolder() {
        const h = await loadSavedRootHandle();
        return Boolean(h);
    }

    window.AutoTCClientFolder = {
        isRemoteHosted,
        isFsApiSupported,
        hasConfiguredFolder,
        chooseRootFolder,
        getVerifiedRootHandle,
        saveTaskFilesToClient,
        fetchTaskFileFromServer,
        triggerBrowserDownload,
        updateFolderButtonUI,
    };

    window.selectClientSaveFolder = async function () {
        if (!isFsApiSupported()) {
            if (typeof showToast === 'function') {
                showToast(
                    'Trình duyệt hiện tại không hỗ trợ chọn folder trực tiếp (hãy dùng Chrome/Edge qua HTTPS). File sẽ tự động tải về mục Downloads.',
                    'info',
                    7000
                );
            }
            return;
        }
        try {
            const handle = await chooseRootFolder();
            if (typeof showToast === 'function') {
                showToast(
                    `📁 Đã cấu hình thư mục lưu trên máy bạn: "${handle.name}". Từ giờ mỗi bài toán sẽ tự động tạo folder con và lưu Word/Excel vào đây!`,
                    'success',
                    8000
                );
            }
        } catch (err) {
            if (err && err.name === 'AbortError') return;
            if (typeof showToast === 'function') {
                showToast(`Không thể chọn thư mục lưu: ${err.message}`, 'error', 6000);
            }
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        updateFolderButtonUI();
    });
})();
