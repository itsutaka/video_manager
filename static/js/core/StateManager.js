/**
 * 狀態管理器
 * 集中管理應用狀態，實現響應式數據綁定
 */

export class StateManager {
    constructor(initialState = {}) {
        this.state = this.createReactiveState(initialState);
        this.listeners = new Map();
        this.history = [];
        this.maxHistorySize = 50;
    }

    /**
     * 創建響應式狀態
     * @param {Object} obj - 原始狀態對象
     * @returns {Proxy} - 響應式代理對象
     */
    createReactiveState(obj) {
        const self = this;

        return new Proxy(obj, {
            set(target, property, value) {
                const oldValue = target[property];

                // 如果值沒有變化，直接返回
                if (oldValue === value) {
                    return true;
                }

                // 保存歷史記錄
                self.addHistory({
                    property,
                    oldValue,
                    newValue: value,
                    timestamp: Date.now()
                });

                // 設置新值
                target[property] = value;

                // 觸發監聽器
                self.notify(property, value, oldValue);

                return true;
            },

            deleteProperty(target, property) {
                const oldValue = target[property];

                // 保存歷史記錄
                self.addHistory({
                    property,
                    oldValue,
                    newValue: undefined,
                    timestamp: Date.now(),
                    action: 'delete'
                });

                delete target[property];

                // 觸發監聽器
                self.notify(property, undefined, oldValue);

                return true;
            }
        });
    }

    /**
     * 獲取狀態值
     * @param {string} key - 狀態鍵
     * @returns {*} - 狀態值
     */
    get(key) {
        return this.state[key];
    }

    /**
     * 設置狀態值
     * @param {string|Object} key - 狀態鍵或狀態對象
     * @param {*} value - 狀態值
     */
    set(key, value) {
        if (typeof key === 'object') {
            // 批量設置
            Object.assign(this.state, key);
        } else {
            this.state[key] = value;
        }
    }

    /**
     * 更新狀態（合併對象）
     * @param {string} key - 狀態鍵
     * @param {Object} updates - 更新內容
     */
    update(key, updates) {
        const current = this.state[key];

        if (typeof current === 'object' && current !== null) {
            this.state[key] = { ...current, ...updates };
        } else {
            this.state[key] = updates;
        }
    }

    /**
     * 監聽狀態變化
     * @param {string} key - 狀態鍵
     * @param {Function} callback - 回調函數
     * @returns {Function} - 取消監聽函數
     */
    watch(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, []);
        }

        this.listeners.get(key).push(callback);

        // 返回取消監聽函數
        return () => this.unwatch(key, callback);
    }

    /**
     * 取消監聽
     * @param {string} key - 狀態鍵
     * @param {Function} callback - 回調函數
     */
    unwatch(key, callback) {
        if (!this.listeners.has(key)) {
            return;
        }

        const callbacks = this.listeners.get(key);
        const index = callbacks.indexOf(callback);

        if (index > -1) {
            callbacks.splice(index, 1);
        }

        if (callbacks.length === 0) {
            this.listeners.delete(key);
        }
    }

    /**
     * 通知監聽器
     * @param {string} key - 狀態鍵
     * @param {*} newValue - 新值
     * @param {*} oldValue - 舊值
     */
    notify(key, newValue, oldValue) {
        if (!this.listeners.has(key)) {
            return;
        }

        const callbacks = this.listeners.get(key);

        [...callbacks].forEach(callback => {
            try {
                callback(newValue, oldValue);
            } catch (error) {
                console.error(`狀態 ${key} 的監聽器執行錯誤:`, error);
            }
        });
    }

    /**
     * 添加歷史記錄
     * @param {Object} record - 歷史記錄
     */
    addHistory(record) {
        this.history.push(record);

        // 限制歷史記錄大小
        if (this.history.length > this.maxHistorySize) {
            this.history.shift();
        }
    }

    /**
     * 獲取歷史記錄
     * @param {number} limit - 返回記錄數量
     * @returns {Array} - 歷史記錄數組
     */
    getHistory(limit = 10) {
        return this.history.slice(-limit);
    }

    /**
     * 清空歷史記錄
     */
    clearHistory() {
        this.history = [];
    }

    /**
     * 重置狀態
     * @param {Object} newState - 新狀態
     */
    reset(newState = {}) {
        // 清空舊狀態
        Object.keys(this.state).forEach(key => {
            delete this.state[key];
        });

        // 設置新狀態
        Object.assign(this.state, newState);

        // 清空歷史
        this.clearHistory();
    }

    /**
     * 獲取所有狀態
     * @returns {Object} - 狀態快照
     */
    getState() {
        return { ...this.state };
    }

    /**
     * 清除所有監聽器
     */
    clearListeners() {
        this.listeners.clear();
    }

    /**
     * 銷毀狀態管理器
     */
    destroy() {
        this.clearListeners();
        this.clearHistory();
        Object.keys(this.state).forEach(key => {
            delete this.state[key];
        });
    }
}

// 創建全局狀態管理器實例
export const globalState = new StateManager({
    // 應用狀態
    isLoading: false,
    currentTask: null,

    // 用戶狀態
    clientId: null,

    // UI 狀態
    activeTab: 'upload',
    showNotifications: true,

    // 轉錄狀態
    transcriptionProgress: 0,
    transcriptionStage: 'idle',

    // 歷史記錄狀態
    historyList: [],
    currentPage: 1,
    totalItems: 0
});

// 預設匯出
export default StateManager;
