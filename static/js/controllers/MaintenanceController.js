/**
 * 維護控制器
 * 處理系統維護相關的 UI 事件和邏輯
 */

import { apiService } from '../services/ApiService.js';
import { notificationSystem } from '../components/NotificationSystem.js';
import { formatFileSize, formatDate } from '../utils/formatters.js';

export class MaintenanceController {
    constructor() {
        this.elements = {
            // 容器
            maintenanceContainer: document.getElementById('maintenanceContainer'),

            // 按鈕
            refreshMaintenanceBtn: document.getElementById('refreshMaintenanceBtn'),
            forceCleanupBtn: document.getElementById('forceCleanupBtn'),
            optimizeDatabaseBtn: document.getElementById('optimizeDatabaseBtn'),
            startSchedulerBtn: document.getElementById('startSchedulerBtn'),
            stopSchedulerBtn: document.getElementById('stopSchedulerBtn'),
            applyRetentionBtn: document.getElementById('applyRetentionBtn'),
            refreshReportsBtn: document.getElementById('refreshReportsBtn'),

            // 磁碟空間資訊
            diskUsedPercent: document.getElementById('diskUsedPercent'),
            diskUsageBar: document.getElementById('diskUsageBar'),
            diskUsedSpace: document.getElementById('diskUsedSpace'),
            diskTotalSpace: document.getElementById('diskTotalSpace'),

            // 任務統計
            totalTasks: document.getElementById('totalTasks'),
            completedTasks: document.getElementById('completedTasks'),
            failedTasks: document.getElementById('failedTasks'),

            // 維護狀態
            schedulerStatus: document.getElementById('schedulerStatus'),
            lastCleanup: document.getElementById('lastCleanup'),
            historySize: document.getElementById('historySize'),

            // 清理設定
            retentionDays: document.getElementById('retentionDays'),

            // 報告
            reportsLoadingIndicator: document.getElementById('reportsLoadingIndicator'),
            reportsEmptyState: document.getElementById('reportsEmptyState'),
            reportsList: document.getElementById('reportsList')
        };
    }

    /**
     * 初始化控制器
     */
    init() {
        this.bindEvents();
        this.loadMaintenanceStatus();
        this.loadReports();
        console.log('✅ MaintenanceController 已初始化');
    }

    /**
     * 綁定所有事件
     */
    bindEvents() {
        // 重新整理按鈕
        if (this.elements.refreshMaintenanceBtn) {
            this.elements.refreshMaintenanceBtn.addEventListener('click', () => this.loadMaintenanceStatus());
        }

        // 維護操作按鈕
        if (this.elements.forceCleanupBtn) {
            this.elements.forceCleanupBtn.addEventListener('click', () => this.handleForceCleanup());
        }

        if (this.elements.optimizeDatabaseBtn) {
            this.elements.optimizeDatabaseBtn.addEventListener('click', () => this.handleOptimizeDatabase());
        }

        if (this.elements.startSchedulerBtn) {
            this.elements.startSchedulerBtn.addEventListener('click', () => this.handleStartScheduler());
        }

        if (this.elements.stopSchedulerBtn) {
            this.elements.stopSchedulerBtn.addEventListener('click', () => this.handleStopScheduler());
        }

        if (this.elements.applyRetentionBtn) {
            this.elements.applyRetentionBtn.addEventListener('click', () => this.handleApplyRetention());
        }

        if (this.elements.refreshReportsBtn) {
            this.elements.refreshReportsBtn.addEventListener('click', () => this.loadReports());
        }
    }

    /**
     * 載入維護狀態
     */
    async loadMaintenanceStatus() {
        try {
            const response = await apiService.maintenance.getStatus();
            const status = response.data || response;

            // 更新磁碟空間資訊
            if (status.disk_info) {
                this.updateDiskInfo(status.disk_info);
            }

            // 更新任務統計
            if (status.task_stats) {
                this.updateTaskStats(status.task_stats);
            }

            // 更新維護狀態
            if (status.scheduler_status !== undefined) {
                this.updateMaintenanceStatus(status);
            }

            notificationSystem.showSuccess('成功', '維護狀態已更新');

        } catch (error) {
            console.error('載入維護狀態失敗:', error);
            notificationSystem.showError('錯誤', '載入維護狀態失敗');
        }
    }

    /**
     * 更新磁碟資訊
     */
    updateDiskInfo(diskInfo) {
        const usedPercent = diskInfo.used_percent || 0;
        const usedGB = diskInfo.used_gb || 0;
        const totalGB = diskInfo.total_gb || 0;

        if (this.elements.diskUsedPercent) {
            this.elements.diskUsedPercent.textContent = `${usedPercent.toFixed(1)}%`;
        }

        if (this.elements.diskUsageBar) {
            this.elements.diskUsageBar.style.width = `${usedPercent}%`;

            // 根據使用率設定顏色
            this.elements.diskUsageBar.classList.remove('bg-blue-500', 'bg-yellow-500', 'bg-red-500');
            if (usedPercent >= 90) {
                this.elements.diskUsageBar.classList.add('bg-red-500');
            } else if (usedPercent >= 80) {
                this.elements.diskUsageBar.classList.add('bg-yellow-500');
            } else {
                this.elements.diskUsageBar.classList.add('bg-blue-500');
            }
        }

        if (this.elements.diskUsedSpace) {
            this.elements.diskUsedSpace.textContent = `${usedGB.toFixed(1)} GB`;
        }

        if (this.elements.diskTotalSpace) {
            this.elements.diskTotalSpace.textContent = `${totalGB.toFixed(1)} GB`;
        }
    }

    /**
     * 更新任務統計
     */
    updateTaskStats(taskStats) {
        if (this.elements.totalTasks) {
            this.elements.totalTasks.textContent = taskStats.total || 0;
        }

        if (this.elements.completedTasks) {
            this.elements.completedTasks.textContent = taskStats.completed || 0;
        }

        if (this.elements.failedTasks) {
            this.elements.failedTasks.textContent = taskStats.failed || 0;
        }
    }

    /**
     * 更新維護狀態
     */
    updateMaintenanceStatus(status) {
        if (this.elements.schedulerStatus) {
            const isRunning = status.scheduler_status === 'running';
            this.elements.schedulerStatus.textContent = isRunning ? '運行中' : '已停止';
            this.elements.schedulerStatus.className = `font-medium ${isRunning ? 'text-green-600' : 'text-gray-600'}`;
        }

        if (this.elements.lastCleanup) {
            this.elements.lastCleanup.textContent = status.last_cleanup ? formatDate(status.last_cleanup) : '從未執行';
        }

        if (this.elements.historySize) {
            const sizeInMB = status.history_size_mb || 0;
            this.elements.historySize.textContent = `${sizeInMB.toFixed(1)} MB`;
        }
    }

    /**
     * 處理強制清理
     */
    async handleForceCleanup() {
        const retentionDays = this.elements.retentionDays?.value || 30;

        if (!confirm(`確定要清理 ${retentionDays} 天前的任務嗎？此操作無法復原。`)) {
            return;
        }

        try {
            const response = await apiService.maintenance.cleanup({ retention_days: parseInt(retentionDays) });
            const data = response.data || response;

            notificationSystem.showSuccess(
                '清理完成',
                `清理了 ${data.files_cleaned || 0} 個檔案，釋放 ${(data.space_freed_mb || 0).toFixed(2)} MB 空間`
            );

            // 重新載入狀態和報告
            await this.loadMaintenanceStatus();
            await this.loadReports();

        } catch (error) {
            console.error('強制清理失敗:', error);
            notificationSystem.showError('錯誤', error.message || '強制清理失敗');
        }
    }

    /**
     * 處理資料庫最佳化
     */
    async handleOptimizeDatabase() {
        if (!confirm('確定要執行資料庫最佳化嗎？這可能需要一些時間。')) {
            return;
        }

        try {
            const response = await apiService.maintenance.optimizeDatabase();
            const data = response.data || response;

            notificationSystem.showSuccess(
                '最佳化完成',
                `執行了 ${data.actions_taken?.length || 0} 個操作，耗時 ${(data.duration_seconds || 0).toFixed(2)} 秒`
            );

            // 重新載入狀態和報告
            await this.loadMaintenanceStatus();
            await this.loadReports();

        } catch (error) {
            console.error('資料庫最佳化失敗:', error);
            notificationSystem.showError('錯誤', error.message || '資料庫最佳化失敗');
        }
    }

    /**
     * 處理啟動排程器
     */
    async handleStartScheduler() {
        try {
            const response = await apiService.maintenance.startScheduler();

            notificationSystem.showSuccess('成功', '維護排程器已啟動');

            // 重新載入狀態
            await this.loadMaintenanceStatus();

        } catch (error) {
            console.error('啟動排程器失敗:', error);
            notificationSystem.showError('錯誤', error.message || '啟動排程器失敗');
        }
    }

    /**
     * 處理停止排程器
     */
    async handleStopScheduler() {
        if (!confirm('確定要停止維護排程器嗎？')) {
            return;
        }

        try {
            const response = await apiService.maintenance.stopScheduler();

            notificationSystem.showSuccess('成功', '維護排程器已停止');

            // 重新載入狀態
            await this.loadMaintenanceStatus();

        } catch (error) {
            console.error('停止排程器失敗:', error);
            notificationSystem.showError('錯誤', error.message || '停止排程器失敗');
        }
    }

    /**
     * 處理套用保留天數
     */
    async handleApplyRetention() {
        const retentionDays = this.elements.retentionDays?.value;

        if (!retentionDays || retentionDays < 1 || retentionDays > 365) {
            notificationSystem.showError('錯誤', '保留天數必須在 1-365 天之間');
            return;
        }

        notificationSystem.showSuccess('成功', `保留天數已設定為 ${retentionDays} 天`);
    }

    /**
     * 載入維護報告
     */
    async loadReports() {
        try {
            // 顯示載入指示器
            this.showReportsLoading();

            const response = await apiService.maintenance.getReports({ limit: 10 });
            const data = response.data || response;
            const reports = data.reports || [];

            // 隱藏載入指示器
            this.hideReportsLoading();

            if (reports.length === 0) {
                this.showReportsEmptyState();
            } else {
                this.hideReportsEmptyState();
                this.renderReports(reports);
            }

        } catch (error) {
            console.error('載入維護報告失敗:', error);
            this.hideReportsLoading();
            notificationSystem.showError('錯誤', '載入維護報告失敗');
        }
    }

    /**
     * 顯示報告載入指示器
     */
    showReportsLoading() {
        if (this.elements.reportsLoadingIndicator) {
            this.elements.reportsLoadingIndicator.classList.remove('hidden');
        }
        if (this.elements.reportsList) {
            this.elements.reportsList.innerHTML = '';
        }
    }

    /**
     * 隱藏報告載入指示器
     */
    hideReportsLoading() {
        if (this.elements.reportsLoadingIndicator) {
            this.elements.reportsLoadingIndicator.classList.add('hidden');
        }
    }

    /**
     * 顯示報告空狀態
     */
    showReportsEmptyState() {
        if (this.elements.reportsEmptyState) {
            this.elements.reportsEmptyState.classList.remove('hidden');
        }
    }

    /**
     * 隱藏報告空狀態
     */
    hideReportsEmptyState() {
        if (this.elements.reportsEmptyState) {
            this.elements.reportsEmptyState.classList.add('hidden');
        }
    }

    /**
     * 渲染報告列表
     */
    renderReports(reports) {
        if (!this.elements.reportsList) return;

        this.elements.reportsList.innerHTML = '';

        reports.forEach(report => {
            const reportItem = this.createReportItem(report);
            this.elements.reportsList.appendChild(reportItem);
        });
    }

    /**
     * 創建報告項目
     */
    createReportItem(report) {
        const item = document.createElement('div');
        item.className = 'p-3 bg-gray-50 rounded-lg border border-gray-200';

        // 根據維護類型設定圖示和顏色
        let icon = 'fa-cog';
        let iconColor = 'text-gray-500';

        if (report.maintenance_type === 'cleanup') {
            icon = 'fa-broom';
            iconColor = 'text-orange-500';
        } else if (report.maintenance_type === 'database_optimization') {
            icon = 'fa-database';
            iconColor = 'text-blue-500';
        }

        // 根據等級設定徽章顏色
        let levelBadge = '';
        if (report.level === 'normal') {
            levelBadge = '<span class="px-2 py-1 text-xs font-semibold rounded bg-green-100 text-green-800">一般</span>';
        } else if (report.level === 'warning') {
            levelBadge = '<span class="px-2 py-1 text-xs font-semibold rounded bg-yellow-100 text-yellow-800">警告</span>';
        } else if (report.level === 'critical') {
            levelBadge = '<span class="px-2 py-1 text-xs font-semibold rounded bg-red-100 text-red-800">嚴重</span>';
        }

        const timestamp = formatDate(report.timestamp);
        const typeText = report.maintenance_type === 'cleanup' ? '清理' :
                        report.maintenance_type === 'database_optimization' ? '資料庫最佳化' :
                        report.maintenance_type;

        item.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center space-x-2">
                    <i class="fas ${icon} ${iconColor}"></i>
                    <span class="font-medium text-gray-800">${typeText}</span>
                    ${levelBadge}
                </div>
                <span class="text-xs text-gray-500">${timestamp}</span>
            </div>
            ${report.files_cleaned ? `
                <div class="text-sm text-gray-600">
                    清理了 <strong>${report.files_cleaned}</strong> 個檔案，
                    釋放 <strong>${report.space_freed_mb.toFixed(2)} MB</strong> 空間
                </div>
            ` : ''}
            ${report.actions_taken && report.actions_taken.length > 0 ? `
                <div class="text-sm text-gray-600 mt-1">
                    執行了 ${report.actions_taken.length} 個操作
                </div>
            ` : ''}
            ${report.errors && report.errors.length > 0 ? `
                <div class="text-sm text-red-600 mt-1">
                    <i class="fas fa-exclamation-triangle mr-1"></i>
                    ${report.errors.length} 個錯誤
                </div>
            ` : ''}
            <div class="text-xs text-gray-500 mt-2">
                耗時 ${report.duration_seconds.toFixed(2)} 秒
            </div>
        `;

        return item;
    }
}

// 創建全局實例
export const maintenanceController = new MaintenanceController();

// 預設匯出
export default MaintenanceController;
