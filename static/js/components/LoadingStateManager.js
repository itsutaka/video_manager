/**
 * 載入狀態管理器
 * 管理應用的載入狀態和進度顯示
 */

export class LoadingStateManager {
    constructor() {
        this.loadingStates = new Map();
        this.progressElements = this.getProgressElements();
    }

    /**
     * 獲取進度相關的 DOM 元素
     * @returns {Object} - DOM 元素對象
     */
    getProgressElements() {
        return {
            container: document.getElementById('loadingIndicator'),
            progressBar: document.getElementById('progressBar'),
            progressPercent: document.getElementById('progressPercent'),
            messageElement: null // 將在需要時創建
        };
    }

    /**
     * 開始載入
     * @param {string} taskId - 任務 ID
     * @param {string} message - 載入訊息
     */
    startLoading(taskId, message = '載入中...') {
        const state = {
            taskId,
            message,
            progress: 0,
            stage: 'initializing',
            startTime: Date.now(),
            estimatedTimeRemaining: null
        };

        this.loadingStates.set(taskId, state);
        this.updateUI(state);
        this.showLoadingContainer();
    }

    /**
     * 更新進度
     * @param {string} taskId - 任務 ID
     * @param {number} progress - 進度百分比 (0-100)
     * @param {string} message - 狀態訊息
     * @param {string} stage - 當前階段
     */
    updateProgress(taskId, progress, message = null, stage = 'processing') {
        const state = this.loadingStates.get(taskId);

        if (!state) {
            console.warn(`找不到任務 ${taskId} 的載入狀態`);
            return;
        }

        state.progress = Math.min(100, Math.max(0, progress));

        if (message) {
            state.message = message;
        }

        state.stage = stage;

        // 計算預估剩餘時間
        const elapsed = Date.now() - state.startTime;
        const rate = state.progress / elapsed;

        if (rate > 0 && state.progress < 100) {
            state.estimatedTimeRemaining = (100 - state.progress) / rate;
        }

        this.updateUI(state);
    }

    /**
     * 完成載入
     * @param {string} taskId - 任務 ID
     * @param {boolean} success - 是否成功
     * @param {string} message - 完成訊息
     */
    finishLoading(taskId, success = true, message = '完成') {
        const state = this.loadingStates.get(taskId);

        if (!state) {
            return;
        }

        state.progress = 100;
        state.message = message;
        state.stage = success ? 'completed' : 'error';
        state.finished = true;

        this.updateUI(state);

        // 延遲清理
        setTimeout(() => {
            this.loadingStates.delete(taskId);

            // 如果沒有其他載入任務，隱藏載入容器
            if (this.loadingStates.size === 0) {
                this.hideLoadingContainer();
            }
        }, success ? 1000 : 3000);
    }

    /**
     * 更新 UI
     * @param {Object} state - 載入狀態
     */
    updateUI(state) {
        const { progressBar, progressPercent, container } = this.progressElements;

        if (!progressBar || !progressPercent) {
            return;
        }

        // 更新進度條
        progressBar.style.width = `${state.progress}%`;
        progressPercent.textContent = `${Math.round(state.progress)}%`;

        // 更新載入訊息
        this.updateMessage(state);

        // 更新階段指示器
        this.updateStageIndicator(state.stage);
    }

    /**
     * 更新訊息
     * @param {Object} state - 載入狀態
     */
    updateMessage(state) {
        const { container } = this.progressElements;

        if (!container) {
            return;
        }

        let messageElement = container.querySelector('.loading-message');

        if (!messageElement) {
            messageElement = document.createElement('p');
            messageElement.className = 'loading-message text-gray-600 loading';
            container.appendChild(messageElement);
        }

        let messageText = state.message;

        // 添加預估時間
        if (state.estimatedTimeRemaining && state.progress < 100) {
            const seconds = Math.round(state.estimatedTimeRemaining / 1000);
            messageText += ` (預估剩餘 ${seconds} 秒)`;
        }

        messageElement.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>${messageText}`;
    }

    /**
     * 更新階段指示器
     * @param {string} stage - 當前階段
     */
    updateStageIndicator(stage) {
        const stages = {
            'initializing': '初始化',
            'file_processing': '檔案處理',
            'downloading': '下載中',
            'transcribing': '語音轉錄',
            'diarizing': '說話者識別',
            'post_processing': '後處理',
            'saving_files': '保存檔案',
            'completed': '完成',
            'error': '錯誤'
        };

        const stageName = stages[stage] || stage;
        console.log(`當前階段: ${stageName}`);

        // 可以在這裡添加視覺化的階段指示器
        this.emitStageEvent(stage, stageName);
    }

    /**
     * 發送階段事件
     * @param {string} stage - 階段代碼
     * @param {string} stageName - 階段名稱
     */
    emitStageEvent(stage, stageName) {
        const event = new CustomEvent('loading:stage', {
            detail: { stage, stageName }
        });
        window.dispatchEvent(event);
    }

    /**
     * 顯示載入容器
     */
    showLoadingContainer() {
        const { container } = this.progressElements;

        if (container) {
            container.classList.remove('hidden');
        }
    }

    /**
     * 隱藏載入容器
     */
    hideLoadingContainer() {
        const { container } = this.progressElements;

        if (container) {
            container.classList.add('hidden');
        }
    }

    /**
     * 重置進度
     */
    reset() {
        const { progressBar, progressPercent } = this.progressElements;

        if (progressBar) {
            progressBar.style.width = '0%';
        }

        if (progressPercent) {
            progressPercent.textContent = '0%';
        }

        this.loadingStates.clear();
        this.hideLoadingContainer();
    }

    /**
     * 獲取當前進度
     * @param {string} taskId - 任務 ID
     * @returns {number} - 進度百分比
     */
    getProgress(taskId) {
        const state = this.loadingStates.get(taskId);
        return state ? state.progress : 0;
    }

    /**
     * 獲取當前階段
     * @param {string} taskId - 任務 ID
     * @returns {string} - 當前階段
     */
    getStage(taskId) {
        const state = this.loadingStates.get(taskId);
        return state ? state.stage : null;
    }

    /**
     * 檢查是否正在載入
     * @param {string} taskId - 任務 ID（可選）
     * @returns {boolean} - 是否正在載入
     */
    isLoading(taskId = null) {
        if (taskId) {
            return this.loadingStates.has(taskId);
        }

        return this.loadingStates.size > 0;
    }

    /**
     * 獲取所有載入任務
     * @returns {Array} - 載入任務數組
     */
    getLoadingTasks() {
        return Array.from(this.loadingStates.values());
    }

    /**
     * 清除所有載入狀態
     */
    clearAll() {
        this.loadingStates.clear();
        this.reset();
    }

    /**
     * 銷毀管理器
     */
    destroy() {
        this.clearAll();
        this.progressElements = null;
    }
}

// 創建全局載入狀態管理器實例
export const loadingStateManager = new LoadingStateManager();

// 預設匯出
export default LoadingStateManager;
