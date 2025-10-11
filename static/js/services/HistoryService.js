/**
 * 歷史記錄服務
 * 管理轉換歷史記錄的業務邏輯
 */

import { apiService } from './ApiService.js';
import { formatDuration, formatFileSize, formatDate, truncateText, escapeHtml, formatNumber } from '../utils/formatters.js';

export class HistoryService {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 10;
        this.totalItems = 0;
        this.currentFilters = {
            search: '',
            fileType: '',
            dateFrom: '',
            dateTo: ''
        };
        this.cache = new Map();
        this.cacheTimeout = 60000; // 1 分鐘快取
    }

    /**
     * 載入歷史記錄列表
     * @param {number} page - 頁碼
     * @param {Object} filters - 篩選條件
     * @returns {Promise} - 歷史記錄數據
     */
    async loadHistory(page = this.currentPage, filters = this.currentFilters) {
        this.currentPage = page;
        this.currentFilters = filters;

        const params = {
            limit: this.pageSize,
            offset: (page - 1) * this.pageSize
        };

        // 添加篩選參數
        if (filters.search) {
            params.q = filters.search;
        }
        if (filters.fileType) {
            params.source_type = filters.fileType;
        }
        if (filters.dateFrom) {
            params.date_from = filters.dateFrom;
        }
        if (filters.dateTo) {
            params.date_to = filters.dateTo;
        }

        try {
            // 判斷使用搜索還是列表 API
            const hasFilters = filters.search || filters.fileType || filters.dateFrom || filters.dateTo;
            const data = hasFilters
                ? await apiService.history.search(params)
                : await apiService.history.getList(params);

            // 處理不同的 API 回應格式
            let tasks = [];
            let total = 0;

            if (data.tasks) {
                tasks = data.tasks;
                total = data.total || data.tasks.length;
            } else if (Array.isArray(data)) {
                tasks = data;
                total = data.length;
            }

            this.totalItems = total;

            return {
                tasks,
                total,
                currentPage: page,
                totalPages: Math.ceil(total / this.pageSize)
            };
        } catch (error) {
            console.error('載入歷史記錄失敗:', error);
            throw error;
        }
    }

    /**
     * 獲取任務詳情
     * @param {string} taskId - 任務 ID
     * @returns {Promise} - 任務詳情
     */
    async getTaskDetails(taskId) {
        // 檢查快取
        const cacheKey = `task_${taskId}`;
        const cached = this.cache.get(cacheKey);

        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }

        try {
            const result = await apiService.history.getTask(taskId);
            const task = result.task || result;

            // 更新快取
            this.cache.set(cacheKey, {
                data: task,
                timestamp: Date.now()
            });

            return task;
        } catch (error) {
            console.error('獲取任務詳情失敗:', error);
            throw error;
        }
    }

    /**
     * 刪除任務
     * @param {string} taskId - 任務 ID
     * @returns {Promise} - 刪除結果
     */
    async deleteTask(taskId) {
        try {
            const result = await apiService.history.deleteTask(taskId);

            // 清除快取
            this.cache.delete(`task_${taskId}`);

            return result;
        } catch (error) {
            console.error('刪除任務失敗:', error);
            throw error;
        }
    }

    /**
     * 下載文件
     * @param {string} taskId - 任務 ID
     * @param {string} fileType - 文件類型
     * @returns {Promise} - 下載結果
     */
    async downloadFile(taskId, fileType) {
        try {
            return await apiService.history.downloadFile(taskId, fileType);
        } catch (error) {
            console.error('下載文件失敗:', error);
            throw error;
        }
    }

    /**
     * 清除篩選條件
     */
    clearFilters() {
        this.currentFilters = {
            search: '',
            fileType: '',
            dateFrom: '',
            dateTo: ''
        };
        this.currentPage = 1;
    }

    /**
     * 設置分頁大小
     * @param {number} size - 每頁數量
     */
    setPageSize(size) {
        this.pageSize = size;
        this.currentPage = 1;
    }

    /**
     * 跳轉到指定頁面
     * @param {number} page - 頁碼
     */
    goToPage(page) {
        const totalPages = Math.ceil(this.totalItems / this.pageSize);

        if (page < 1) {
            page = 1;
        } else if (page > totalPages) {
            page = totalPages;
        }

        this.currentPage = page;
    }

    /**
     * 上一頁
     */
    previousPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
        }
    }

    /**
     * 下一頁
     */
    nextPage() {
        const totalPages = Math.ceil(this.totalItems / this.pageSize);

        if (this.currentPage < totalPages) {
            this.currentPage++;
        }
    }

    /**
     * 提取顯示標題
     * @param {Object} task - 任務對象
     * @returns {string} - 顯示標題
     */
    extractDisplayTitle(task) {
        // 如果有 video_title，直接使用
        if (task.video_title) {
            return task.video_title;
        }

        // 從檔案名稱中提取標題
        if (task.files && task.files.length > 0) {
            for (const file of task.files) {
                if (file.file_name && (file.file_name.endsWith('.srt') || file.file_name.endsWith('.txt'))) {
                    let title = file.file_name;

                    // 移除檔案副檔名
                    title = title.replace(/\.(srt|txt)$/, '');

                    // 移除 "YouTube_" 前綴
                    title = title.replace(/^YouTube_\s*/, '');

                    // 移除頻道名稱（@開頭的部分）
                    title = title.replace(/\s*@[^\s]*$/, '');

                    return title.trim();
                }
            }
        }

        return task.name || '未知任務';
    }

    /**
     * 格式化任務卡片數據
     * @param {Object} task - 原始任務數據
     * @returns {Object} - 格式化後的數據
     */
    formatTaskCard(task) {
        return {
            id: task.id,
            title: this.extractDisplayTitle(task),
            truncatedTitle: truncateText(this.extractDisplayTitle(task), 60),

            // 狀態
            status: task.status,
            statusText: this.getStatusText(task.status),
            statusClass: this.getStatusClass(task.status),

            // 類型
            sourceType: task.source_type,
            fileTypeText: task.source_type === 'youtube' ? 'YouTube' : '上傳檔案',
            fileTypeClass: task.source_type === 'youtube' ? 'youtube' : 'file',

            // 時間
            createdAt: formatDate(task.created_at),
            completedAt: task.completed_at ? formatDate(task.completed_at) : null,

            // 元數據
            duration: task.duration ? formatDuration(task.duration) : '未知',
            videoDuration: task.video_duration ? formatDuration(task.video_duration) : null,
            fileSize: task.file_size ? formatFileSize(task.file_size) : '未知',

            // YouTube 資料
            videoTitle: task.video_title,
            videoUploader: task.video_uploader,
            videoViewCount: task.video_view_count ? formatNumber(task.video_view_count) : null,

            // 其他
            hasDiarization: task.has_diarization,
            modelUsed: task.model_used,
            language: task.language,
            errorMessage: task.error_message,

            // 原始數據
            raw: task
        };
    }

    /**
     * 獲取狀態文本
     * @param {string} status - 狀態碼
     * @returns {string} - 狀態文本
     */
    getStatusText(status) {
        const statusMap = {
            'completed': '已完成',
            'processing': '處理中',
            'failed': '失敗',
            'pending': '等待中'
        };
        return statusMap[status] || status;
    }

    /**
     * 獲取狀態樣式類
     * @param {string} status - 狀態碼
     * @returns {string} - 樣式類名
     */
    getStatusClass(status) {
        const classMap = {
            'completed': 'completed',
            'processing': 'processing',
            'failed': 'failed',
            'pending': 'processing'
        };
        return classMap[status] || 'processing';
    }

    /**
     * 清除快取
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * 獲取分頁資訊
     * @returns {Object} - 分頁資訊
     */
    getPaginationInfo() {
        const totalPages = Math.ceil(this.totalItems / this.pageSize);
        const startItem = (this.currentPage - 1) * this.pageSize + 1;
        const endItem = Math.min(this.currentPage * this.pageSize, this.totalItems);

        return {
            currentPage: this.currentPage,
            totalPages,
            startItem,
            endItem,
            totalItems: this.totalItems,
            pageSize: this.pageSize,
            hasPrevious: this.currentPage > 1,
            hasNext: this.currentPage < totalPages
        };
    }

    getAvailableFiles(task) {
        const files = [];
        const hasFile = (type) => task.files?.some(f => f.file_type === type);

        if (hasFile('txt')) {
            files.push({ type: 'txt', name: '文字檔案 (.txt)', icon: 'fa-file-alt', color: 'text-blue-500' });
        }
        if (hasFile('srt')) {
            files.push({ type: 'srt', name: '字幕檔案 (.srt)', icon: 'fa-file-video', color: 'text-green-500' });
        }
        if (hasFile('audio')) {
            files.push({ type: 'audio', name: '音訊檔案', icon: 'fa-file-audio', color: 'text-purple-500' });
        }
        if (task.source_type === 'youtube') {
            if (hasFile('video')) {
                files.push({ type: 'video', name: '影片檔案', icon: 'fa-video', color: 'text-red-500' });
            }
            if (hasFile('thumbnail')) {
                files.push({ type: 'thumbnail', name: '縮圖檔案', icon: 'fa-image', color: 'text-yellow-500' });
            }
        }
        return files;
    }
}

// 創建全局歷史記錄服務實例
export const historyService = new HistoryService();

// 預設匯出
export default HistoryService;
