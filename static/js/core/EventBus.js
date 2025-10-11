/**
 * 事件總線
 * 實現發布-訂閱模式，用於組件間通訊
 */

export class EventBus {
    constructor() {
        this.events = new Map();
        this.onceEvents = new Map();
    }

    /**
     * 訂閱事件
     * @param {string} eventName - 事件名稱
     * @param {Function} callback - 回調函數
     * @returns {Function} - 取消訂閱函數
     */
    on(eventName, callback) {
        if (!this.events.has(eventName)) {
            this.events.set(eventName, []);
        }

        this.events.get(eventName).push(callback);

        // 返回取消訂閱函數
        return () => this.off(eventName, callback);
    }

    /**
     * 訂閱一次性事件
     * @param {string} eventName - 事件名稱
     * @param {Function} callback - 回調函數
     * @returns {Function} - 取消訂閱函數
     */
    once(eventName, callback) {
        const wrapper = (...args) => {
            callback(...args);
            this.off(eventName, wrapper);
        };

        return this.on(eventName, wrapper);
    }

    /**
     * 取消訂閱事件
     * @param {string} eventName - 事件名稱
     * @param {Function} callback - 回調函數
     */
    off(eventName, callback) {
        if (!this.events.has(eventName)) {
            return;
        }

        if (!callback) {
            // 如果沒有指定回調，移除該事件的所有監聽器
            this.events.delete(eventName);
            return;
        }

        const callbacks = this.events.get(eventName);
        const index = callbacks.indexOf(callback);

        if (index > -1) {
            callbacks.splice(index, 1);
        }

        // 如果沒有監聽器了，刪除事件
        if (callbacks.length === 0) {
            this.events.delete(eventName);
        }
    }

    /**
     * 發布事件
     * @param {string} eventName - 事件名稱
     * @param {...any} args - 傳遞給回調的參數
     */
    emit(eventName, ...args) {
        if (!this.events.has(eventName)) {
            return;
        }

        const callbacks = this.events.get(eventName);

        // 使用副本以避免在回調中修改數組導致問題
        [...callbacks].forEach(callback => {
            try {
                callback(...args);
            } catch (error) {
                console.error(`事件 ${eventName} 的回調執行錯誤:`, error);
            }
        });
    }

    /**
     * 清除所有事件監聽器
     */
    clear() {
        this.events.clear();
        this.onceEvents.clear();
    }

    /**
     * 獲取事件監聽器數量
     * @param {string} eventName - 事件名稱
     * @returns {number} - 監聽器數量
     */
    listenerCount(eventName) {
        if (!this.events.has(eventName)) {
            return 0;
        }
        return this.events.get(eventName).length;
    }

    /**
     * 獲取所有事件名稱
     * @returns {Array<string>} - 事件名稱數組
     */
    eventNames() {
        return Array.from(this.events.keys());
    }
}

// 創建全局事件總線實例
export const globalEventBus = new EventBus();

// 預設匯出
export default EventBus;
