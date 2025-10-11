# vidoe_manoger

這是一個基於 Faster Whisper 和 FastAPI 的企業級語音轉文字 (STT) 應用程式，提供 GPU 加速處理、完整的歷史紀錄管理、說話者辨識和現代化的 Web 界面。

## 🚀 核心功能

### 語音轉文字處理
- **GPU 加速處理**：使用 Faster Whisper 的 medium 模型，支援 CUDA 加速
- **多格式支援**：mp3、wav、m4a、flac、ogg 等主流音訊格式
- **YouTube 整合**：直接從 YouTube URL 下載並轉錄影片音訊
- **說話者辨識**：使用 WhisperX 進行多說話者分離和標記
- **語音活動檢測**：VAD 過濾功能，提升轉錄品質
- **多語言支援**：支援中文、英文、日文等多種語言

### 歷史紀錄管理
- **完整任務追蹤**：記錄每次轉換的詳細資訊和結果
- **檔案管理系統**：自動組織和保存音訊檔案、字幕檔案和文字檔案
- **搜尋和篩選**：支援按時間、狀態、來源類型等條件搜尋歷史紀錄
- **檔案下載**：支援下載原始音訊、SRT 字幕和純文字檔案
- **批次管理**：支援批次刪除和管理歷史任務

### 系統管理功能
- **自動維護**：定期清理過期檔案和最佳化資料庫
- **效能監控**：即時監控系統效能和資源使用情況
- **錯誤處理**：完整的錯誤追蹤和恢復機制
- **資料庫遷移**：支援資料庫版本管理和自動遷移

### 使用者體驗
- **即時進度顯示**：WebSocket 即時更新轉錄進度
- **響應式界面**：現代化的 Web UI，支援拖放上傳
- **回饋機制**：使用者評分和回饋系統
- **載入狀態管理**：智慧載入狀態和錯誤提示

## 📋 系統需求

### 硬體需求
- **CPU**：Intel i5 或 AMD Ryzen 5 以上
- **記憶體**：8GB RAM 以上（建議 16GB）
- **GPU**：NVIDIA GPU（支援 CUDA 11.8+）建議 6GB VRAM 以上
- **儲存空間**：至少 10GB 可用空間

### 軟體需求
- **作業系統**：Windows 10/11、Ubuntu 18.04+、macOS 10.15+
- **Python**：3.11 或更高版本
- **FFmpeg**：音訊處理必需
- **CUDA Toolkit**：11.8 或更高版本（GPU 加速）

## 🛠️ 安裝部署

### 1. 環境準備

#### 安裝 Python 3.11+
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv

# Windows (使用 Chocolatey)
choco install python --version=3.11.0

# macOS (使用 Homebrew)
brew install python@3.11
```

#### 安裝 FFmpeg
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg

# macOS (使用 Homebrew)
brew install ffmpeg
```

#### 安裝 CUDA Toolkit (GPU 加速)
```bash
# 下載並安裝 CUDA 11.8+
# 訪問：https://developer.nvidia.com/cuda-downloads
# 按照官方指南安裝對應版本
```

### 2. 專案設定

#### 克隆專案
```bash
git clone <repository-url>
cd faster-whisper-api
```

#### 建立虛擬環境
```bash
python3.11 -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

#### 安裝依賴套件
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 環境變數設定

建立 `.env` 檔案：
```bash
# Whisper 模型設定
WHISPER_DEVICE=cuda          # 或 cpu
WHISPER_COMPUTE_TYPE=float16 # 或 int8, float32

# 說話者辨識設定
DIARIZATION_DEVICE=cuda      # 或 cpu
HUGGINGFACE_TOKEN=your_token_here  # 可選，用於說話者辨識

# 資料庫設定
DATABASE_PATH=history/conversion_history.db

# 伺服器設定
HOST=0.0.0.0
PORT=8000
```

### 4. 資料庫初始化

#### 自動初始化（推薦）
```bash
python database_init.py --setup
```

#### 手動初始化
```bash
# 建立資料庫結構
python database_init.py --create

# 執行遷移（如果需要）
python database_init.py --migrate

# 檢查資料庫狀態
python database_init.py --status
```

### 5. 啟動服務

#### 開發模式
```bash
python main.py
```

#### 生產模式
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 使用 Docker（可選）
```bash
# 建立 Docker 映像
docker build -t faster-whisper-api .

# 執行容器
docker run -d -p 8000:8000 \
  -v $(pwd)/history:/app/history \
  -v $(pwd)/models:/app/models \
  --gpus all \
  faster-whisper-api
```

## 🔧 資料庫管理

### 基本操作

#### 檢查資料庫狀態
```bash
python database_init.py --status
```

#### 建立備份
```bash
python database_init.py --backup
```

#### 恢復備份
```bash
python database_init.py --restore backup_file.db
```

#### 資料庫遷移
```bash
# 檢查可用遷移
python database_init.py --list-migrations

# 執行遷移
python database_init.py --migrate

# 回滾遷移
python database_init.py --rollback 1.0.1
```

### 維護操作

#### 清理過期資料
```bash
python database_init.py --cleanup --days 30
```

#### 最佳化資料庫
```bash
python database_init.py --optimize
```

#### 檢查完整性
```bash
python database_init.py --check-integrity
```

## 📡 API 使用指南

### 語音轉文字 API

#### 基本轉錄
```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "file=@audio.mp3" \
  -F "model=whisper-1" \
  -F "response_format=json"
```

#### YouTube 轉錄
```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "youtube_url=https://www.youtube.com/watch?v=VIDEO_ID" \
  -F "model=whisper-1" \
  -F "with_diarization=true"
```

#### 說話者辨識
```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "file=@meeting.wav" \
  -F "model=whisper-1" \
  -F "with_diarization=true" \
  -F "language=zh"
```

### 歷史紀錄 API

#### 取得歷史紀錄
```bash
# 基本查詢
curl "http://localhost:8000/api/history?page=1&limit=20"

# 篩選查詢
curl "http://localhost:8000/api/history?status=completed&source_type=youtube"

# 搜尋
curl "http://localhost:8000/api/history/search?q=會議記錄"
```

#### 下載檔案
```bash
# 下載 SRT 字幕
curl "http://localhost:8000/api/history/TASK_ID/files/srt" -o subtitle.srt

# 下載原始音訊
curl "http://localhost:8000/api/history/TASK_ID/files/audio" -o audio.mp3
```

### 系統管理 API

#### 效能監控
```bash
curl "http://localhost:8000/api/performance/stats"
```

#### 維護狀態
```bash
curl "http://localhost:8000/api/maintenance/status"
```

## 🧪 測試

### 執行所有測試
```bash
python -m pytest tests/ -v
```

### 執行特定測試
```bash
# API 測試
python test_history_api.py

# 端到端測試
python test_end_to_end_conversion.py

# 資料庫測試
python test_database_migration.py

# 效能測試
python test_performance_optimization.py
```

### 整合測試
```bash
python run_integration_tests.py
```

## 📊 監控和維護

### 系統監控

#### 檢查系統狀態
```bash
curl "http://localhost:8000/api/health"
```

#### 效能報告
```bash
curl "http://localhost:8000/api/performance/report"
```

### 日誌管理

日誌檔案位置：
- 應用程式日誌：`app.log`
- 錯誤日誌：`error.log`
- 維護日誌：`maintenance.log`

### 自動維護

系統會自動執行以下維護任務：
- 每 24 小時清理過期檔案
- 每週最佳化資料庫
- 每 30 分鐘監控磁碟空間
- 每小時清理快取

## 🔧 配置選項

### 模型配置
```python
# main.py 中的模型設定
WHISPER_MODEL_SIZE = "medium"  # tiny, base, small, medium, large
WHISPER_DEVICE = "cuda"        # cuda, cpu
WHISPER_COMPUTE_TYPE = "float16"  # float16, int8, float32
```

### 效能調整
```python
# 並行處理設定
MAX_WORKERS = 4
BATCH_SIZE = 16

# 快取設定
CACHE_TTL = 3600  # 秒
MAX_CACHE_SIZE = 1000
```

## 🚨 故障排除

### 常見問題

#### CUDA 相關錯誤
```bash
# 檢查 CUDA 安裝
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"

# 重新安裝 PyTorch
pip uninstall torch torchaudio
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### 記憶體不足
```bash
# 調整模型大小
export WHISPER_MODEL_SIZE=small
export WHISPER_COMPUTE_TYPE=int8
```

#### 資料庫錯誤
```bash
# 檢查資料庫完整性
python database_init.py --check-integrity

# 重建資料庫
python database_init.py --recreate
```

### 效能最佳化

#### GPU 最佳化
- 使用 `float16` 精度以節省 VRAM
- 調整批次大小以平衡速度和記憶體使用
- 確保 CUDA 版本與 PyTorch 相容

#### 系統最佳化
- 定期清理臨時檔案
- 監控磁碟空間使用
- 調整工作程序數量

## 📚 技術架構

### 後端技術棧
- **FastAPI**：Web 框架和 API 服務
- **Faster Whisper**：語音轉文字核心引擎
- **WhisperX**：說話者辨識和對齊
- **SQLite**：資料庫（支援 PostgreSQL）
- **WebSocket**：即時通訊
- **Uvicorn**：ASGI 伺服器

### 前端技術棧
- **HTML5 + JavaScript**：原生前端實現
- **Tailwind CSS**：UI 樣式框架
- **Font Awesome**：圖標庫
- **WebSocket API**：即時更新

### 系統架構
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   FastAPI       │    │   Whisper       │
│   (HTML/JS)     │◄──►│   Backend       │◄──►│   Models        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   SQLite DB     │
                       │   File System   │
                       └─────────────────┘
```

## 📄 授權條款

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。

## 🤝 貢獻指南

歡迎提交 Issue 和 Pull Request！請確保：

1. 遵循現有的程式碼風格
2. 添加適當的測試
3. 更新相關文檔
4. 通過所有測試

## 📞 技術支援

如有問題或需要技術支援，請：

1. 查看 [故障排除](#-故障排除) 章節
2. 搜尋現有的 [Issues](../../issues)
3. 建立新的 Issue 並提供詳細資訊

---

**注意**：首次啟動時系統會自動下載 Whisper 模型，請確保網路連線穩定。模型檔案較大（約 1-5GB），下載時間取決於網路速度。 
