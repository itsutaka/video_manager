/**
 * 驗證工具函數
 * 提供各種數據驗證功能
 */

/**
 * 驗證 YouTube URL
 * @param {string} url - YouTube URL
 * @returns {boolean} - 是否為有效的 YouTube URL
 */
export function isValidYouTubeUrl(url) {
    if (!url) {
        return false;
    }

    const patterns = [
        /^https?:\/\/(www\.)?youtube\.com\/watch\?v=[\w-]+/,
        /^https?:\/\/youtu\.be\/[\w-]+/,
        /^https?:\/\/(www\.)?youtube\.com\/embed\/[\w-]+/,
        /^https?:\/\/(www\.)?youtube\.com\/v\/[\w-]+/
    ];

    return patterns.some(pattern => pattern.test(url));
}

/**
 * 驗證檔案類型
 * @param {File} file - 檔案對象
 * @param {Array<string>} allowedTypes - 允許的文件類型數組
 * @returns {boolean} - 是否為允許的類型
 */
export function isValidFileType(file, allowedTypes = ['.mp3', '.wav', '.m4a', '.flac', '.ogg']) {
    if (!file) {
        return false;
    }

    const fileName = file.name.toLowerCase();
    return allowedTypes.some(ext => fileName.endsWith(ext));
}

/**
 * 驗證檔案大小
 * @param {File} file - 檔案對象
 * @param {number} maxSize - 最大檔案大小（字節）
 * @returns {boolean} - 是否在允許的大小範圍內
 */
export function isValidFileSize(file, maxSize = 500 * 1024 * 1024) {
    if (!file) {
        return false;
    }

    return file.size <= maxSize;
}

/**
 * 驗證電子郵件地址
 * @param {string} email - 電子郵件地址
 * @returns {boolean} - 是否為有效的電子郵件
 */
export function isValidEmail(email) {
    if (!email) {
        return false;
    }

    const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return pattern.test(email);
}

/**
 * 驗證 URL
 * @param {string} url - URL 字符串
 * @returns {boolean} - 是否為有效的 URL
 */
export function isValidUrl(url) {
    if (!url) {
        return false;
    }

    try {
        new URL(url);
        return true;
    } catch (error) {
        return false;
    }
}

/**
 * 驗證數字範圍
 * @param {number} value - 數值
 * @param {number} min - 最小值
 * @param {number} max - 最大值
 * @returns {boolean} - 是否在範圍內
 */
export function isInRange(value, min, max) {
    if (value === null || value === undefined || isNaN(value)) {
        return false;
    }

    return value >= min && value <= max;
}

/**
 * 驗證任務 ID 格式
 * @param {string} taskId - 任務 ID
 * @returns {boolean} - 是否為有效的任務 ID
 */
export function isValidTaskId(taskId) {
    if (!taskId || typeof taskId !== 'string') {
        return false;
    }

    // UUID 格式或其他有效格式
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    return uuidPattern.test(taskId) || taskId.length >= 8;
}

/**
 * 驗證必填字段
 * @param {*} value - 值
 * @returns {boolean} - 是否為有效值
 */
export function isRequired(value) {
    if (value === null || value === undefined) {
        return false;
    }

    if (typeof value === 'string') {
        return value.trim().length > 0;
    }

    if (Array.isArray(value)) {
        return value.length > 0;
    }

    return true;
}

/**
 * 驗證最小長度
 * @param {string|Array} value - 值
 * @param {number} minLength - 最小長度
 * @returns {boolean} - 是否滿足最小長度
 */
export function hasMinLength(value, minLength) {
    if (!value) {
        return false;
    }

    return value.length >= minLength;
}

/**
 * 驗證最大長度
 * @param {string|Array} value - 值
 * @param {number} maxLength - 最大長度
 * @returns {boolean} - 是否滿足最大長度
 */
export function hasMaxLength(value, maxLength) {
    if (!value) {
        return true;
    }

    return value.length <= maxLength;
}

/**
 * 驗證日期範圍
 * @param {Date|string} date - 日期
 * @param {Date|string} startDate - 開始日期
 * @param {Date|string} endDate - 結束日期
 * @returns {boolean} - 是否在範圍內
 */
export function isDateInRange(date, startDate, endDate) {
    const d = new Date(date);
    const start = startDate ? new Date(startDate) : null;
    const end = endDate ? new Date(endDate) : null;

    if (isNaN(d.getTime())) {
        return false;
    }

    if (start && d < start) {
        return false;
    }

    if (end && d > end) {
        return false;
    }

    return true;
}

/**
 * 驗證 JSON 字符串
 * @param {string} str - JSON 字符串
 * @returns {boolean} - 是否為有效的 JSON
 */
export function isValidJson(str) {
    if (!str || typeof str !== 'string') {
        return false;
    }

    try {
        JSON.parse(str);
        return true;
    } catch (error) {
        return false;
    }
}

/**
 * 驗證十六進制顏色值
 * @param {string} color - 顏色值
 * @returns {boolean} - 是否為有效的十六進制顏色
 */
export function isValidHexColor(color) {
    if (!color) {
        return false;
    }

    const pattern = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
    return pattern.test(color);
}

/**
 * 驗證表單數據
 * @param {Object} formData - 表單數據
 * @param {Object} rules - 驗證規則
 * @returns {Object} - 驗證結果 { valid: boolean, errors: {} }
 */
export function validateForm(formData, rules) {
    const errors = {};
    let valid = true;

    for (const field in rules) {
        const value = formData[field];
        const fieldRules = rules[field];

        // 必填驗證
        if (fieldRules.required && !isRequired(value)) {
            errors[field] = fieldRules.requiredMessage || '此欄位為必填';
            valid = false;
            continue;
        }

        // 如果不是必填且值為空，跳過其他驗證
        if (!isRequired(value) && !fieldRules.required) {
            continue;
        }

        // 最小長度驗證
        if (fieldRules.minLength && !hasMinLength(value, fieldRules.minLength)) {
            errors[field] = fieldRules.minLengthMessage || `長度至少需要 ${fieldRules.minLength} 個字符`;
            valid = false;
            continue;
        }

        // 最大長度驗證
        if (fieldRules.maxLength && !hasMaxLength(value, fieldRules.maxLength)) {
            errors[field] = fieldRules.maxLengthMessage || `長度不能超過 ${fieldRules.maxLength} 個字符`;
            valid = false;
            continue;
        }

        // 自定義驗證函數
        if (fieldRules.validator && !fieldRules.validator(value)) {
            errors[field] = fieldRules.message || '驗證失敗';
            valid = false;
            continue;
        }
    }

    return { valid, errors };
}

// 預設匯出所有函數
export default {
    isValidYouTubeUrl,
    isValidFileType,
    isValidFileSize,
    isValidEmail,
    isValidUrl,
    isInRange,
    isValidTaskId,
    isRequired,
    hasMinLength,
    hasMaxLength,
    isDateInRange,
    isValidJson,
    isValidHexColor,
    validateForm
};
