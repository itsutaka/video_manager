/**
 * 通知系統組件
 * 顯示應用通知訊息
 */

export class NotificationSystem {
    constructor() {
        this.notifications = [];
        this.container = this.createNotificationContainer();
        this.maxNotifications = 5;
    }

    /**
     * 創建通知容器
     * @returns {HTMLElement} - 通知容器元素
     */
    createNotificationContainer() {
        let container = document.getElementById('notification-container');

        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'fixed top-4 right-4 z-50 space-y-2 max-w-sm';
            document.body.appendChild(container);
        }

        return container;
    }

    /**
     * 顯示通知
     * @param {string} type - 通知類型 (success, error, warning, info)
     * @param {string} title - 通知標題
     * @param {string} message - 通知訊息
     * @param {number} duration - 顯示時長（毫秒），0 表示不自動關閉
     * @returns {HTMLElement} - 通知元素
     */
    show(type, title, message, duration = 5000) {
        // 限制通知數量
        if (this.notifications.length >= this.maxNotifications) {
            this.remove(this.notifications[0]);
        }

        const notification = this.createNotification(type, title, message);
        this.container.appendChild(notification);
        this.notifications.push(notification);

        // 觸發進入動畫
        requestAnimationFrame(() => {
            notification.classList.remove('translate-x-full', 'opacity-0');
        });

        // 自動移除
        if (duration > 0) {
            setTimeout(() => {
                this.remove(notification);
            }, duration);
        }

        return notification;
    }

    /**
     * 創建通知元素
     * @param {string} type - 通知類型
     * @param {string} title - 標題
     * @param {string} message - 訊息
     * @returns {HTMLElement} - 通知元素
     */
    createNotification(type, title, message) {
        const notification = document.createElement('div');
        notification.className = 'notification-item transform transition-all duration-300 ease-in-out translate-x-full opacity-0';

        const typeStyles = {
            success: 'bg-green-500 border-green-600',
            error: 'bg-red-500 border-red-600',
            warning: 'bg-yellow-500 border-yellow-600',
            info: 'bg-blue-500 border-blue-600'
        };

        const iconClasses = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        notification.innerHTML = `
            <div class="flex items-start p-4 rounded-lg shadow-lg border-l-4 ${typeStyles[type] || typeStyles.info} text-white">
                <i class="${iconClasses[type] || iconClasses.info} text-xl mr-3 mt-0.5"></i>
                <div class="flex-1">
                    <h4 class="font-semibold text-sm">${this.escapeHtml(title)}</h4>
                    <p class="text-sm opacity-90 mt-1">${this.escapeHtml(message)}</p>
                </div>
                <button class="ml-2 text-white hover:text-gray-200 focus:outline-none notification-close" aria-label="關閉">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        // 綁定關閉按鈕事件
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.remove(notification);
        });

        return notification;
    }

    /**
     * 移除通知
     * @param {HTMLElement} notification - 通知元素
     */
    remove(notification) {
        if (!notification || !notification.parentNode) {
            return;
        }

        notification.classList.add('translate-x-full', 'opacity-0');

        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }

            const index = this.notifications.indexOf(notification);
            if (index > -1) {
                this.notifications.splice(index, 1);
            }
        }, 300);
    }

    /**
     * 顯示成功通知
     * @param {string} title - 標題
     * @param {string} message - 訊息
     * @param {number} duration - 顯示時長
     * @returns {HTMLElement} - 通知元素
     */
    showSuccess(title, message, duration = 3000) {
        return this.show('success', title, message, duration);
    }

    /**
     * 顯示錯誤通知
     * @param {string} title - 標題
     * @param {string} message - 訊息
     * @param {number} duration - 顯示時長
     * @returns {HTMLElement} - 通知元素
     */
    showError(title, message, duration = 8000) {
        return this.show('error', title, message, duration);
    }

    /**
     * 顯示警告通知
     * @param {string} title - 標題
     * @param {string} message - 訊息
     * @param {number} duration - 顯示時長
     * @returns {HTMLElement} - 通知元素
     */
    showWarning(title, message, duration = 5000) {
        return this.show('warning', title, message, duration);
    }

    /**
     * 顯示資訊通知
     * @param {string} title - 標題
     * @param {string} message - 訊息
     * @param {number} duration - 顯示時長
     * @returns {HTMLElement} - 通知元素
     */
    showInfo(title, message, duration = 5000) {
        return this.show('info', title, message, duration);
    }

    /**
     * 顯示載入通知
     * @param {string} message - 訊息
     * @returns {HTMLElement} - 通知元素
     */
    showLoading(message) {
        const notification = document.createElement('div');
        notification.className = 'notification-item transform transition-all duration-300 ease-in-out translate-x-full opacity-0';

        notification.innerHTML = `
            <div class="flex items-center p-4 rounded-lg shadow-lg border-l-4 bg-blue-500 border-blue-600 text-white">
                <div class="loading-spinner mr-3" style="width: 1rem; height: 1rem; border-width: 2px; border-color: rgba(255,255,255,0.3); border-top-color: white;"></div>
                <span class="text-sm">${this.escapeHtml(message)}</span>
            </div>
        `;

        this.container.appendChild(notification);
        this.notifications.push(notification);

        requestAnimationFrame(() => {
            notification.classList.remove('translate-x-full', 'opacity-0');
        });

        return notification;
    }

    /**
     * 清除所有通知
     */
    clearAll() {
        [...this.notifications].forEach(notification => {
            this.remove(notification);
        });
    }

    /**
     * HTML 轉義
     * @param {string} text - 原始文本
     * @returns {string} - 轉義後的文本
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 銷毀通知系統
     */
    destroy() {
        this.clearAll();

        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }

        this.notifications = [];
        this.container = null;
    }
}

// 創建全局通知系統實例
export const notificationSystem = new NotificationSystem();

// 預設匯出
export default NotificationSystem;
