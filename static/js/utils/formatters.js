/**
 * 格式化工具函數
 * 提供各種數據格式化功能
 */

/**
 * 格式化時間（秒轉時分秒）
 * @param {number} seconds - 秒數
 * @returns {string} - 格式化後的時間字符串
 */
export function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) {
        return '00:00.00';
    }

    const date = new Date(seconds * 1000);
    const mm = date.getUTCMinutes().toString().padStart(2, '0');
    const ss = date.getUTCSeconds().toString().padStart(2, '0');
    const ms = Math.floor(date.getUTCMilliseconds() / 10).toString().padStart(2, '0');

    return `${mm}:${ss}.${ms}`;
}

/**
 * 格式化持續時間（秒轉時:分:秒）
 * @param {number} seconds - 秒數
 * @returns {string} - 格式化後的時間字符串
 */
export function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) {
        return '未知';
    }

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字節數
 * @returns {string} - 格式化後的文件大小字符串
 */
export function formatFileSize(bytes) {
    if (!bytes || bytes === 0) {
        return '0 Bytes';
    }

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化數字（添加千分位逗號）
 * @param {number} num - 數字
 * @returns {string} - 格式化後的數字字符串
 */
export function formatNumber(num) {
    if (!num || isNaN(num)) {
        return '0';
    }

    // 大數字使用 K/M 簡寫
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }

    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * 格式化日期時間
 * @param {Date|string|number} date - 日期對象、ISO 字符串或時間戳
 * @param {string} format - 格式選項: 'full', 'date', 'time', 'relative'
 * @returns {string} - 格式化後的日期字符串
 */
export function formatDate(date, format = 'full') {
    if (!date) {
        return '-';
    }

    const dateObj = date instanceof Date ? date : new Date(date);

    if (isNaN(dateObj.getTime())) {
        return '-';
    }

    switch (format) {
        case 'full':
            return dateObj.toLocaleString('zh-TW', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });

        case 'date':
            return dateObj.toLocaleDateString('zh-TW', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            });

        case 'time':
            return dateObj.toLocaleTimeString('zh-TW', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });

        case 'relative':
            return formatRelativeTime(dateObj);

        default:
            return dateObj.toLocaleString('zh-TW');
    }
}

/**
 * 格式化相對時間（幾分鐘前、幾小時前等）
 * @param {Date} date - 日期對象
 * @returns {string} - 相對時間字符串
 */
export function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) {
        return '剛剛';
    } else if (diffMins < 60) {
        return `${diffMins} 分鐘前`;
    } else if (diffHours < 24) {
        return `${diffHours} 小時前`;
    } else if (diffDays < 7) {
        return `${diffDays} 天前`;
    } else {
        return formatDate(date, 'date');
    }
}

/**
 * 截斷文本
 * @param {string} text - 原始文本
 * @param {number} maxLength - 最大長度
 * @param {string} suffix - 後綴（默認為 '...'）
 * @returns {string} - 截斷後的文本
 */
export function truncateText(text, maxLength, suffix = '...') {
    if (!text || text.length <= maxLength) {
        return text || '';
    }

    return text.substring(0, maxLength) + suffix;
}

/**
 * HTML 轉義
 * @param {string} text - 原始文本
 * @returns {string} - 轉義後的文本
 */
export function escapeHtml(text) {
    if (!text) {
        return '';
    }

    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 格式化百分比
 * @param {number} value - 數值
 * @param {number} total - 總數
 * @param {number} decimals - 小數位數
 * @returns {string} - 百分比字符串
 */
export function formatPercentage(value, total, decimals = 1) {
    if (!total || total === 0) {
        return '0%';
    }

    const percentage = (value / total) * 100;
    return percentage.toFixed(decimals) + '%';
}

/**
 * 格式化 YouTube 上傳日期（YYYYMMDD 格式）
 * @param {string} dateStr - YouTube 日期字符串
 * @returns {string} - 格式化後的日期
 */
export function formatYouTubeDate(dateStr) {
    if (!dateStr) {
        return '-';
    }

    // 將 YYYYMMDD 轉換為 YYYY-MM-DD
    const match = dateStr.match(/(\d{4})(\d{2})(\d{2})/);

    if (!match) {
        return dateStr;
    }

    const date = new Date(`${match[1]}-${match[2]}-${match[3]}`);
    return formatDate(date, 'date');
}

/**
 * 格式化語言代碼
 * @param {string} langCode - 語言代碼（如 'zh', 'en'）
 * @returns {string} - 語言名稱
 */
export function formatLanguage(langCode) {
    const languageMap = {
        '': '自動偵測',
        'zh': '中文',
        'en': '英文',
        'ja': '日文',
        'ko': '韓文',
        'fr': '法文',
        'de': '德文',
        'es': '西班牙文',
        'it': '義大利文',
        'pt': '葡萄牙文',
        'ru': '俄文'
    };

    return languageMap[langCode] || langCode;
}

/**
 * 格式化狀態文本
 * @param {string} status - 狀態代碼
 * @returns {string} - 狀態文本
 */
export function formatStatus(status) {
    const statusMap = {
        'completed': '已完成',
        'processing': '處理中',
        'failed': '失敗',
        'pending': '等待中',
        'cancelled': '已取消'
    };

    return statusMap[status] || status;
}

// 預設匯出所有函數
export default {
    formatTime,
    formatDuration,
    formatFileSize,
    formatNumber,
    formatDate,
    formatRelativeTime,
    truncateText,
    escapeHtml,
    formatPercentage,
    formatYouTubeDate,
    formatLanguage,
    formatStatus
};
