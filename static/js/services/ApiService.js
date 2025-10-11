/**
 * API 服務
 * 封裝所有 API 請求，提供統一的錯誤處理和請求配置
 */

export class ApiService {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl || window.location.origin;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
        this.requestInterceptors = [];
        this.responseInterceptors = [];
    }

    /**
     * 通用請求方法
     * @param {string} url - 請求 URL
     * @param {Object} options - 請求選項
     * @returns {Promise} - 請求結果
     */
    async request(url, options = {}) {
        const config = {
            ...options,
            headers: {
                ...this.defaultHeaders,
                ...options.headers
            }
        };

        // 執行請求攔截器
        for (const interceptor of this.requestInterceptors) {
            await interceptor(config);
        }

        // 如果是 FormData，移除 Content-Type，讓瀏覽器自動設定
        if (config.body instanceof FormData) {
            delete config.headers['Content-Type'];
        }

        try {
            const response = await fetch(this.baseUrl + url, config);

            // 執行響應攔截器
            for (const interceptor of this.responseInterceptors) {
                await interceptor(response);
            }

            if (!response.ok) {
                throw await this.handleError(response);
            }

            return await response.json();
        } catch (error) {
            console.error('API 請求錯誤:', error);
            throw error;
        }
    }

    /**
     * GET 請求
     * @param {string} url - 請求 URL
     * @param {Object} params - 查詢參數
     * @returns {Promise} - 請求結果
     */
    async get(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;

        return this.request(fullUrl, {
            method: 'GET'
        });
    }

    /**
     * POST 請求
     * @param {string} url - 請求 URL
     * @param {Object} data - 請求數據
     * @returns {Promise} - 請求結果
     */
    async post(url, data = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * POST 表單數據
     * @param {string} url - 請求 URL
     * @param {FormData} formData - 表單數據
     * @returns {Promise} - 請求結果
     */
    async postForm(url, formData) {
        return this.request(url, {
            method: 'POST',
            headers: {}, // 讓瀏覽器自動設置 Content-Type
            body: formData
        });
    }

    /**
     * PUT 請求
     * @param {string} url - 請求 URL
     * @param {Object} data - 請求數據
     * @returns {Promise} - 請求結果
     */
    async put(url, data = {}) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE 請求
     * @param {string} url - 請求 URL
     * @returns {Promise} - 請求結果
     */
    async delete(url) {
        return this.request(url, {
            method: 'DELETE'
        });
    }

    /**
     * 下載文件
     * @param {string} url - 文件 URL
     * @param {string} filename - 文件名稱
     */
    async downloadFile(url, filename) {
        try {
            const response = await fetch(this.baseUrl + url);

            if (!response.ok) {
                throw new Error('文件下載失敗');
            }

            // 從響應頭獲取文件名
            const contentDisposition = response.headers.get('content-disposition');
            let finalFilename = filename;

            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    finalFilename = filenameMatch[1];
                }
            }

            // 下載文件
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = finalFilename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(blobUrl);
            document.body.removeChild(a);

            return { success: true, filename: finalFilename };
        } catch (error) {
            console.error('下載文件錯誤:', error);
            throw error;
        }
    }

    /**
     * 處理錯誤
     * @param {Response} response - 響應對象
     * @returns {Error} - 錯誤對象
     */
    async handleError(response) {
        let errorMessage = '請求失敗';

        try {
            const data = await response.json();
            errorMessage = data.detail || data.message || errorMessage;
        } catch (e) {
            errorMessage = response.statusText || errorMessage;
        }

        const error = new Error(errorMessage);
        error.status = response.status;
        error.response = response;

        return error;
    }

    /**
     * 添加請求攔截器
     * @param {Function} interceptor - 攔截器函數
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * 添加響應攔截器
     * @param {Function} interceptor - 攔截器函數
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }

    /**
     * 設置默認請求頭
     * @param {Object} headers - 請求頭
     */
    setDefaultHeaders(headers) {
        this.defaultHeaders = {
            ...this.defaultHeaders,
            ...headers
        };
    }

    /**
     * 歷史記錄相關 API
     */
    history = {
        /**
         * 獲取歷史記錄列表
         * @param {Object} params - 查詢參數
         */
        getList: (params = {}) => {
            return this.get('/api/history', params);
        },

        /**
         * 搜索歷史記錄
         * @param {Object} params - 搜索參數
         */
        search: (params = {}) => {
            return this.get('/api/history/search', params);
        },

        /**
         * 獲取任務詳情
         * @param {string} taskId - 任務 ID
         */
        getTask: (taskId) => {
            return this.get(`/api/history/${taskId}`);
        },

        /**
         * 刪除任務
         * @param {string} taskId - 任務 ID
         */
        deleteTask: (taskId) => {
            return this.delete(`/api/history/${taskId}`);
        },

        /**
         * 下載文件
         * @param {string} taskId - 任務 ID
         * @param {string} fileType - 文件類型
         */
        downloadFile: (taskId, fileType) => {
            return this.downloadFile(`/api/history/${taskId}/files/${fileType}`, `${taskId}_${fileType}`);
        }
    };

    /**
     * 轉錄相關 API
     */
    transcription = {
        /**
         * 提交轉錄任務
         * @param {FormData} formData - 表單數據
         */
        submit: (formData) => {
            return this.postForm('/v1/audio/transcriptions', formData);
        }
    };

    /**
     * 維護相關 API
     */
    maintenance = {
        /**
         * 獲取維護狀態
         */
        getStatus: () => {
            return this.get('/api/maintenance/status');
        },

        /**
         * 強制清理
         * @param {Object} options - 清理選項
         */
        cleanup: (options = {}) => {
            return this.post('/api/maintenance/cleanup', options);
        },

        /**
         * 優化資料庫
         */
        optimizeDatabase: () => {
            return this.post('/api/maintenance/optimize-database');
        },

        /**
         * 啟動排程器
         */
        startScheduler: () => {
            return this.post('/api/maintenance/start-scheduler');
        },

        /**
         * 停止排程器
         */
        stopScheduler: () => {
            return this.post('/api/maintenance/stop-scheduler');
        },

        /**
         * 獲取維護報告
         * @param {Object} params - 查詢參數
         */
        getReports: (params = {}) => {
            return this.get('/api/maintenance/reports', params);
        }
    };
}

// 創建全局 API 服務實例
export const apiService = new ApiService();

// 預設匯出
export default ApiService;
