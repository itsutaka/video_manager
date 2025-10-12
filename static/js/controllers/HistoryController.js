/**
 * 歷史記錄控制器
 * 處理轉換歷史記錄相關的 UI 事件和邏輯
 */

import { historyService } from '../services/HistoryService.js';
import { notificationSystem } from '../components/NotificationSystem.js';
import { formatDate, formatFileSize, formatDuration, truncateText } from '../utils/formatters.js';

export class HistoryController {
    constructor() {
        this.currentTaskId = null;
        this.deleteTaskId = null;
        this.searchTimeout = null;

        this.elements = {
            // 容器
            historyContainer: document.getElementById('historyContainer'),
            historyList: document.getElementById('historyList'),
            historyLoadingIndicator: document.getElementById('historyLoadingIndicator'),
            historyEmptyState: document.getElementById('historyEmptyState'),
            historyPagination: document.getElementById('historyPagination'),

            // 搜尋和篩選
            refreshHistoryBtn: document.getElementById('refreshHistoryBtn'),
            historySearch: document.getElementById('historySearch'),
            fileTypeFilter: document.getElementById('fileTypeFilter'),
            dateFrom: document.getElementById('dateFrom'),
            dateTo: document.getElementById('dateTo'),
            clearFiltersBtn: document.getElementById('clearFiltersBtn'),

            // 分頁
            prevPageBtn: document.getElementById('prevPageBtn'),
            nextPageBtn: document.getElementById('nextPageBtn'),
            pageNumbers: document.getElementById('pageNumbers'),
            currentPageInfo: document.getElementById('currentPageInfo'),
            totalItemsInfo: document.getElementById('totalItemsInfo'),

            // 影片預覽模態框
            videoPreviewModal: document.getElementById('videoPreviewModal'),
            closeVideoPreviewBtn: document.getElementById('closeVideoPreviewBtn'),
            videoPreviewTitle: document.getElementById('videoPreviewTitle'),
            videoPreviewThumbnail: document.getElementById('videoPreviewThumbnail'),
            videoPreviewFullTitle: document.getElementById('videoPreviewFullTitle'),
            videoPreviewUploader: document.getElementById('videoPreviewUploader'),
            videoPreviewUploadDate: document.getElementById('videoPreviewUploadDate'),
            videoPreviewDuration: document.getElementById('videoPreviewDuration'),
            videoPreviewViewCount: document.getElementById('videoPreviewViewCount'),
            videoPreviewCreatedAt: document.getElementById('videoPreviewCreatedAt'),
            videoPreviewStatus: document.getElementById('videoPreviewStatus'),
            videoPreviewDescription: document.getElementById('videoPreviewDescription'),
            videoPreviewFileSize: document.getElementById('videoPreviewFileSize'),
            videoPreviewModel: document.getElementById('videoPreviewModel'),
            videoPreviewLanguage: document.getElementById('videoPreviewLanguage'),
            videoPreviewDiarization: document.getElementById('videoPreviewDiarization'),
            previewDownloadVideo: document.getElementById('previewDownloadVideo'),
            previewDownloadAudio: document.getElementById('previewDownloadAudio'),
            previewDownloadThumbnail: document.getElementById('previewDownloadThumbnail'),

            // 刪除確認模態框
            deleteConfirmModal: document.getElementById('deleteConfirmModal'),
            cancelDeleteBtn: document.getElementById('cancelDeleteBtn'),
            confirmDeleteBtn: document.getElementById('confirmDeleteBtn'),

            // 【新增】下載檔案模態框
            downloadFilesModal: document.getElementById('downloadFilesModal'),
            closeDownloadModalBtn: document.getElementById('closeDownloadModalBtn'),
            downloadLinksContainer: document.getElementById('download-links-container'),
            downloadModalTitle: document.getElementById('downloadModalTitle')
        };
    }

    /**
     * 初始化控制器
     */
    init() {
        console.log('🔍 開始初始化 HistoryController');
        console.log('🔍 元素檢查:', {
            historyList: this.elements.historyList,
            historyContainer: this.elements.historyContainer
        });

        this.bindEvents();
        this.loadHistory();
        console.log('✅ HistoryController 已初始化');
        
        // 添加測試函數到全域
        window.testDownloadMenu = () => {
            console.log('🧪 測試下載選單功能');
            const allDownloadBtns = document.querySelectorAll('.download-btn');
            const allDownloadMenus = document.querySelectorAll('.download-menu');
            
            console.log('🧪 找到的下載按鈕數量:', allDownloadBtns.length);
            console.log('🧪 找到的下載選單數量:', allDownloadMenus.length);
            
            allDownloadBtns.forEach((btn, index) => {
                const menu = btn.nextElementSibling;
                console.log(`🧪 按鈕 ${index}:`, {
                    button: btn,
                    buttonClasses: btn.className,
                    nextSibling: menu,
                    isDownloadMenu: menu?.classList.contains('download-menu'),
                    menuClasses: menu?.className
                });
            });
        };
    }

    /**
     * 綁定所有事件
     */
    bindEvents() {
        console.log('🔍 開始綁定事件');
        console.log('🔍 歷史列表元素:', this.elements.historyList);

        if (!this.elements.historyList) {
            console.error('❌ 找不到歷史列表元素，無法綁定事件');
            return;
        }

        // ... (其他按鈕的事件綁定) ...

        // 使用事件委派處理歷史列表中的所有點擊事件
        console.log('🔍 綁定歷史列表點擊事件');
        this.elements.historyList.addEventListener('click', (e) => {
            console.log('🔍 點擊事件觸發:', {
                target: e.target,
                targetClass: e.target.className,
                targetTag: e.target.tagName,
                currentTarget: e.currentTarget
            });

            // 處理其他操作
            const actionTarget = e.target.closest('[data-action]');
            if (actionTarget) {
                e.preventDefault();
                e.stopPropagation();

                const action = actionTarget.dataset.action;
                const taskId = actionTarget.dataset.taskId;

                // 執行其他操作前，先關閉所有選單
                document.querySelectorAll('.download-menu').forEach(menu => menu.classList.add('hidden'));
                this.handleTaskAction(action, taskId);
            }
        });

        // 其他非列表的事件綁定
        this.elements.refreshHistoryBtn?.addEventListener('click', () => this.loadHistory());
        this.elements.historySearch?.addEventListener('input', () => this.handleSearchChange());
        this.elements.fileTypeFilter?.addEventListener('change', () => this.handleFilterChange());
        this.elements.dateFrom?.addEventListener('change', () => this.handleFilterChange());
        this.elements.dateTo?.addEventListener('change', () => this.handleFilterChange());
        this.elements.clearFiltersBtn?.addEventListener('click', () => this.clearFilters());
        this.elements.prevPageBtn?.addEventListener('click', () => this.goToPreviousPage());
        this.elements.nextPageBtn?.addEventListener('click', () => this.goToNextPage());
        this.elements.closeVideoPreviewBtn?.addEventListener('click', () => this.closeVideoPreview());
        this.elements.videoPreviewModal?.addEventListener('click', (e) => { if (e.target === this.elements.videoPreviewModal) this.closeVideoPreview(); });
        this.elements.cancelDeleteBtn?.addEventListener('click', () => this.closeDeleteConfirm());
        this.elements.confirmDeleteBtn?.addEventListener('click', () => this.confirmDelete());
        this.elements.deleteConfirmModal?.addEventListener('click', (e) => { if (e.target === this.elements.deleteConfirmModal) this.closeDeleteConfirm(); });

        // 新增：下載彈出框的關閉事件
        this.elements.closeDownloadModalBtn?.addEventListener('click', () => this.closeDownloadModal());
        this.elements.downloadFilesModal?.addEventListener('click', (e) => { if (e.target === this.elements.downloadFilesModal) this.closeDownloadModal(); });
        this.elements.downloadLinksContainer?.addEventListener('click', (e) => {
            const target = e.target.closest('button');
            if (target && target.dataset.action) {
                this.handleTaskAction(target.dataset.action, target.dataset.taskId);
                this.closeDownloadModal();
            }
        });
    }

    /**
     * 載入歷史記錄
     */
    async loadHistory(page = 1) {
        try {
            this.showLoading();
            const filters = {
                search: this.elements.historySearch?.value.trim() || '',
                fileType: this.elements.fileTypeFilter?.value || '',
                dateFrom: this.elements.dateFrom?.value || '',
                dateTo: this.elements.dateTo?.value || ''
            };
            const result = await historyService.loadHistory(page, filters);
            this.hideLoading();
            if (result.tasks.length === 0) {
                this.showEmptyState();
            } else {
                this.hideEmptyState();
                this.renderTaskList(result.tasks);
                this.renderPagination(result);
            }
        } catch (error) {
            console.error('載入歷史記錄失敗:', error);
            this.hideLoading();
            notificationSystem.showError('錯誤', '載入歷史記錄失敗');
        }
    }

    /**
     * 渲染任務列表
     */
    renderTaskList(tasks) {
        if (!this.elements.historyList) return;
        this.elements.historyList.innerHTML = '';
        tasks.forEach(task => {
            const formattedTask = historyService.formatTaskCard(task);
            const taskCard = this.createTaskCard(formattedTask);
            this.elements.historyList.appendChild(taskCard);
        });
    }

    /**
     * 創建任務卡片
     */
    createTaskCard(task) {
        console.log('🔍 創建任務卡片:', {
            taskId: task.id,
            sourceType: task.sourceType,
            status: task.status
        });

        const card = document.createElement('div');
        card.className = 'task-card';
        card.dataset.taskId = task.id;

        let youtubeBadge = task.sourceType === 'youtube' ? `<span class="inline-flex items-center px-2 py-1 text-xs font-semibold rounded bg-red-100 text-red-800"><i class="fab fa-youtube mr-1"></i>YouTube</span>` : '';
        const statusBadge = `<span class="status-badge ${task.statusClass}">${task.statusText}</span>`;
        let thumbnail = '';
        if (task.sourceType === 'youtube' && task.raw.files?.find(f => f.file_type === 'thumbnail')) {
            thumbnail = `<div class="task-thumbnail"><img src="/api/history/${task.id}/files/thumbnail" alt="縮圖" onerror="this.style.display='none'"></div>`;
        }

        const htmlContent = `
            ${thumbnail}
            <div class="task-content">
                <div class="task-header">
                    <div class="flex items-center space-x-2 flex-1 min-w-0">
                        ${youtubeBadge}
                        <h3 class="task-title" title="${task.title}">${task.truncatedTitle}</h3>
                    </div>
                    ${statusBadge}
                </div>
                <div class="task-meta">
                    <div class="meta-item"><i class="fas fa-calendar text-gray-400"></i><span>${task.createdAt}</span></div>
                    <div class="meta-item"><i class="fas fa-clock text-gray-400"></i><span>${task.duration}</span></div>
                    <div class="meta-item"><i class="fas fa-file-audio text-gray-400"></i><span>${task.fileSize}</span></div>
                    ${task.mp4FileSize ? `<div class="meta-item" title="影片檔案大小"><i class="fas fa-video text-gray-400"></i><span>${task.mp4FileSize}</span></div>` : ''}
                    ${task.hasDiarization ? '<div class="meta-item"><i class="fas fa-users text-blue-500"></i><span>說話者分離</span></div>' : ''}
                </div>
                <div class="task-actions">
                    <button class="task-action-btn info-btn" data-action="preview" data-task-id="${task.id}" title="任務詳情"><i class="fas fa-info-circle"></i></button>
                    <button class="task-action-btn download-btn" data-action="download" data-task-id="${task.id}" title="下載檔案"><i class="fas fa-download"></i></button>
                    <button class="task-action-btn delete-btn" data-action="delete" data-task-id="${task.id}" title="刪除任務"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `;

        card.innerHTML = htmlContent;

        // 調試：檢查生成的 HTML 結構
        const downloadBtn = card.querySelector('.download-btn');
        const downloadMenu = card.querySelector('.download-menu');
        const downloadFiles = card.querySelectorAll('.download-file');

        console.log('🔍 生成的 HTML 結構檢查:', {
            taskId: task.id,
            downloadBtn: downloadBtn,
            downloadBtnClasses: downloadBtn?.className,
            downloadMenu: downloadMenu,
            downloadMenuClasses: downloadMenu?.className,
            downloadFiles: downloadFiles.length,
            isNextSibling: downloadBtn?.nextElementSibling === downloadMenu
        });

        return card;
    }

    async handleTaskAction(action, taskId) {
        const fileTypeMap = {
            'download-txt': 'txt',
            'download-srt': 'srt',
            'download-audio': 'audio',
            'download-video': 'video',
            'download-thumbnail': 'thumbnail'
        };

        if (action.startsWith('download-')) {
            const fileType = action.replace('download-', '');
            await this.downloadFile(taskId, fileType);
        } else if (action === 'download') {
            await this.showDownloadModal(taskId);
        } else if (action === 'preview') {
            await this.showVideoPreview(taskId);
        } else if (action === 'delete') {
            this.showDeleteConfirm(taskId);
        }
    }

    async downloadFile(taskId, fileType) {
        try {
            this.showDownloadProgress(fileType);
            this.updateDownloadProgress('正在連接伺服器...', 10);
            const response = await fetch(`/api/history/${taskId}/files/${fileType}`);
            if (!response.ok) throw new Error('檔案下載失敗');
            this.updateDownloadProgress('正在準備檔案...', 30);
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `${taskId}_${fileType}`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) filename = filenameMatch[1];
            }
            this.updateDownloadProgress(filename, 50);
            const blob = await response.blob();
            this.updateDownloadProgress('正在下載檔案...', 80);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            this.updateDownloadProgress('下載完成', 100);
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            setTimeout(() => {
                this.hideDownloadProgress();
                notificationSystem.showSuccess(`${this.getFileTypeDisplayName(fileType)}下載完成`);
            }, 1000);
        } catch (error) {
            console.error('下載檔案錯誤:', error);
            this.hideDownloadProgress();
            notificationSystem.showError('錯誤', '檔案下載失敗，請稍後再試');
        }
    }

    showDownloadProgress(fileType) {
        const modal = document.getElementById('downloadProgressModal');
        const fileName = document.getElementById('downloadFileName');
        fileName.textContent = `準備下載 ${this.getFileTypeDisplayName(fileType)}...`;
        modal.classList.remove('hidden');
        const cancelBtn = document.getElementById('cancelDownloadBtn');
        cancelBtn.onclick = () => this.hideDownloadProgress();
    }

    updateDownloadProgress(fileName, progress) {
        document.getElementById('downloadFileName').textContent = fileName;
        document.getElementById('downloadProgress').textContent = `${progress}%`;
        document.getElementById('downloadProgressBar').style.width = `${progress}%`;
    }

    hideDownloadProgress() {
        const modal = document.getElementById('downloadProgressModal');
        modal.classList.add('hidden');
        this.updateDownloadProgress('準備中...', 0);
    }

    getFileTypeDisplayName(fileType) {
        const typeMap = { 'txt': '文字檔案', 'srt': '字幕檔案', 'audio': '音訊檔案', 'video': '影片檔案', 'thumbnail': '縮圖檔案' };
        return typeMap[fileType] || fileType;
    }

    /**
     * 顯示下載檔案彈出框
     */
    async showDownloadModal(taskId) {
        try {
            const task = await historyService.getTaskDetails(taskId);
            if (!task) {
                notificationSystem.showError('錯誤', '找不到任務詳情');
                return;
            }

            this.currentTaskId = taskId;
            this.elements.downloadModalTitle.textContent = `下載檔案: ${truncateText(historyService.extractDisplayTitle(task), 20)}`;
            
            const container = this.elements.downloadLinksContainer;
            container.innerHTML = ''; // 清空舊連結

            const files = historyService.getAvailableFiles(task);

            if (files.length === 0) {
                container.innerHTML = `<p class="text-center text-gray-500">沒有可下載的檔案。</p>`;
            } else {
                files.forEach(file => {
                    const button = document.createElement('button');
                    button.className = 'w-full px-4 py-3 text-left bg-gray-50 hover:bg-gray-100 rounded-lg border flex items-center transition-colors';
                    button.dataset.action = `download-${file.type}`;
                    button.dataset.taskId = taskId;
                    button.innerHTML = `<i class="fas ${file.icon} ${file.color} w-6 text-center mr-3"></i><span class="font-medium">${file.name}</span>`;
                    container.appendChild(button);
                });
            }

            this.elements.downloadFilesModal.classList.remove('hidden');
            document.body.style.overflow = 'hidden'; // 防止背景滾動

        } catch (error) {
            notificationSystem.showError('錯誤', '無法獲取檔案列表');
            console.error(error);
        }
    }

    /**
     * 關閉下載檔案彈出框
     */
    closeDownloadModal() {
        this.elements.downloadFilesModal.classList.add('hidden');
        document.body.style.overflow = ''; // 恢復背景滾動
    }

    // ... (其他方法如 showLoading, hideLoading, showVideoPreview, etc. 保持不變) ...
    showLoading() { if (this.elements.historyLoadingIndicator) { this.elements.historyLoadingIndicator.classList.remove('hidden'); } if (this.elements.historyList) { this.elements.historyList.innerHTML = ''; } if (this.elements.historyPagination) { this.elements.historyPagination.classList.add('hidden'); } }
    hideLoading() { if (this.elements.historyLoadingIndicator) { this.elements.historyLoadingIndicator.classList.add('hidden'); } }
    showEmptyState() { if (this.elements.historyEmptyState) { this.elements.historyEmptyState.classList.remove('hidden'); } if (this.elements.historyPagination) { this.elements.historyPagination.classList.add('hidden'); } }
    hideEmptyState() { if (this.elements.historyEmptyState) { this.elements.historyEmptyState.classList.add('hidden'); } }
    async showVideoPreview(taskId) { try { const task = await historyService.getTaskDetails(taskId); this.currentTaskId = taskId; if (this.elements.videoPreviewTitle) { this.elements.videoPreviewTitle.textContent = task.video_title || task.name || '影片預覽'; } if (this.elements.videoPreviewFullTitle) { this.elements.videoPreviewFullTitle.textContent = task.video_title || task.name || '未知標題'; } if (this.elements.videoPreviewUploader) { this.elements.videoPreviewUploader.textContent = task.video_uploader || '-'; } if (this.elements.videoPreviewUploadDate) { this.elements.videoPreviewUploadDate.textContent = task.video_upload_date || '-'; } if (this.elements.videoPreviewDuration) { this.elements.videoPreviewDuration.textContent = task.video_duration ? formatDuration(task.video_duration) : '-'; } if (this.elements.videoPreviewViewCount) { this.elements.videoPreviewViewCount.textContent = task.video_view_count ? task.video_view_count.toLocaleString() : '-'; } if (this.elements.videoPreviewCreatedAt) { this.elements.videoPreviewCreatedAt.textContent = formatDate(task.created_at); } if (this.elements.videoPreviewStatus) { this.elements.videoPreviewStatus.textContent = historyService.getStatusText(task.status); } if (this.elements.videoPreviewDescription) { this.elements.videoPreviewDescription.textContent = task.video_description || '無描述資訊'; } if (this.elements.videoPreviewFileSize) { this.elements.videoPreviewFileSize.textContent = task.file_size ? formatFileSize(task.file_size) : '-'; } if (this.elements.videoPreviewModel) { this.elements.videoPreviewModel.textContent = task.model_used || '-'; } if (this.elements.videoPreviewLanguage) { this.elements.videoPreviewLanguage.textContent = task.language || '自動檢測'; } if (this.elements.videoPreviewDiarization) { this.elements.videoPreviewDiarization.textContent = task.has_diarization ? '已啟用' : '未啟用'; } if (this.elements.videoPreviewThumbnail) { const thumbnailFile = task.files?.find(f => f.file_type === 'thumbnail'); if (thumbnailFile) { this.elements.videoPreviewThumbnail.src = `/api/history/${taskId}/files/thumbnail`; } else { this.elements.videoPreviewThumbnail.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="225"%3E%3Crect fill="%23ddd" width="400" height="225"/%3E%3C/svg%3E'; } } if (this.elements.previewDownloadVideo) { this.elements.previewDownloadVideo.onclick = () => this.downloadFile(taskId, 'video'); } if (this.elements.previewDownloadAudio) { this.elements.previewDownloadAudio.onclick = () => this.downloadFile(taskId, 'audio'); } if (this.elements.previewDownloadThumbnail) { this.elements.previewDownloadThumbnail.onclick = () => this.downloadFile(taskId, 'thumbnail'); } if (this.elements.videoPreviewModal) { this.elements.videoPreviewModal.classList.remove('hidden'); } } catch (error) { console.error('載入任務詳情失敗:', error); notificationSystem.showError('錯誤', '載入任務詳情失敗'); } }
    closeVideoPreview() { if (this.elements.videoPreviewModal) { this.elements.videoPreviewModal.classList.add('hidden'); } this.currentTaskId = null; }
    showDeleteConfirm(taskId) { this.deleteTaskId = taskId; if (this.elements.deleteConfirmModal) { this.elements.deleteConfirmModal.classList.remove('hidden'); } }
    closeDeleteConfirm() { if (this.elements.deleteConfirmModal) { this.elements.deleteConfirmModal.classList.add('hidden'); } this.deleteTaskId = null; }
    async confirmDelete() { if (!this.deleteTaskId) return; try { await historyService.deleteTask(this.deleteTaskId); notificationSystem.showSuccess('成功', '任務已刪除'); this.closeDeleteConfirm(); await this.loadHistory(historyService.currentPage); } catch (error) { console.error('刪除任務失敗:', error); notificationSystem.showError('錯誤', error.message || '刪除任務失敗'); } }
    handleSearchChange() { clearTimeout(this.searchTimeout); this.searchTimeout = setTimeout(() => { this.loadHistory(1); }, 500); }
    handleFilterChange() { this.loadHistory(1); }
    clearFilters() { if (this.elements.historySearch) { this.elements.historySearch.value = ''; } if (this.elements.fileTypeFilter) { this.elements.fileTypeFilter.value = ''; } if (this.elements.dateFrom) { this.elements.dateFrom.value = ''; } if (this.elements.dateTo) { this.elements.dateTo.value = ''; } historyService.clearFilters(); this.loadHistory(1); }
    renderPagination(result) { if (!this.elements.historyPagination) return; const paginationInfo = historyService.getPaginationInfo(); if (this.elements.currentPageInfo) { this.elements.currentPageInfo.textContent = `${paginationInfo.startItem}-${paginationInfo.endItem}`; } if (this.elements.totalItemsInfo) { this.elements.totalItemsInfo.textContent = paginationInfo.totalItems; } if (this.elements.prevPageBtn) { this.elements.prevPageBtn.disabled = !paginationInfo.hasPrevious; } if (this.elements.nextPageBtn) { this.elements.nextPageBtn.disabled = !paginationInfo.hasNext; } this.renderPageNumbers(paginationInfo); this.elements.historyPagination.classList.remove('hidden'); }
    renderPageNumbers(paginationInfo) { if (!this.elements.pageNumbers) return; this.elements.pageNumbers.innerHTML = ''; const { currentPage, totalPages } = paginationInfo; let startPage = Math.max(1, currentPage - 2); let endPage = Math.min(totalPages, currentPage + 2); for (let i = startPage; i <= endPage; i++) { const pageBtn = document.createElement('button'); pageBtn.className = 'page-number'; if (i === currentPage) { pageBtn.classList.add('active'); } pageBtn.textContent = i; pageBtn.addEventListener('click', () => this.goToPage(i)); this.elements.pageNumbers.appendChild(pageBtn); } }
    goToPage(page) { this.loadHistory(page); }
    goToPreviousPage() { if (historyService.currentPage > 1) { this.loadHistory(historyService.currentPage - 1); } }
    goToNextPage() { const paginationInfo = historyService.getPaginationInfo(); if (paginationInfo.hasNext) { this.loadHistory(historyService.currentPage + 1); } }
}

// 創建全局實例
export const historyController = new HistoryController();

// 預設匯出
export default HistoryController;