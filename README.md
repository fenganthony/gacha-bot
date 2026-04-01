# 🎰 轉蛋機器人

Discord 轉蛋（扭蛋）機器人，包含精力、打工、代幣、扭蛋、冒險、兌換與活動模式系統，附帶 Web 後台管理介面。

## 功能

### 玩家指令

| 指令 | 說明 |
|------|------|
| `/簽到` | 每日簽到領取代幣 |
| `/打工` | 選擇打工地點，消耗精力賺取代幣 |
| `/領取` | 領取完成的打工報酬 |
| `/扭蛋` | 花費代幣抽獎 |
| `/冒險` | 投入資源挑戰冒險事件（機率成功/失敗） |
| `/兌換` | 兌換背包中的獎品，發送公開通知 |
| `/狀態` | 查看精力、代幣、打工進度 |
| `/背包` | 查看獎品收藏 |
| `/獎品池` | 查看所有獎品與機率 |

所有指令回應皆為 ephemeral（僅使用者本人可見）。

### 管理指令（需 Administrator 權限）

| 指令 | 說明 |
|------|------|
| `/設定 每日精力` | 設定每天獲得精力 |
| `/設定 精力上限` | 設定精力最大值 |
| `/設定 扭蛋費用` | 設定扭蛋消耗代幣 |
| `/設定 簽到獎勵` | 設定簽到代幣獎勵 |
| `/設定 簽到冷卻` | 設定簽到冷卻時間（小時） |
| `/設定 稀有度權重` | 調整 N/R/SR/SSR 權重 |
| `/設定 新增打工` | 新增打工地點 |
| `/設定 刪除打工` | 刪除打工地點 |
| `/設定 新增獎品` | 新增獎品（秘藏需設定權重） |
| `/設定 刪除獎品` | 刪除獎品 |
| `/設定 新增冒險` | 新增冒險事件（支援 custom_tokens 自選投入） |
| `/設定 刪除冒險` | 刪除冒險事件 |
| `/設定 管理角色` | 指定管理角色 |
| `/設定 查看` | 查看所有設定 |
| `/查看玩家 @成員` | 查看指定玩家狀態（需管理角色） |

### 扭蛋機率系統

- **N / R / SR / SSR** — 各有統一權重，同稀有度獎品均分機率
- **秘藏** — 每個獎品獨立設定權重，新增時指定

### 冒險系統

可設定的機率事件，每個冒險包含：
- **消耗類型** — 精力 (`energy`)、代幣 (`tokens`) 或自選代幣 (`custom_tokens`)
- **成功率** — 0-100%
- **成功/失敗獎勵** — 固定代幣 (`fixed`) 或投入代幣倍率 (`multiplier`)

**自選投入 (`custom_tokens`)**：
- 玩家自行決定投入多少代幣，管理端可設定最小值 (`min_bet`) 和最大值 (`max_bet`)
- 選擇後彈出輸入框讓玩家填寫金額
- 適合搭配 `multiplier` 獎勵類型（例如成功 ×3、失敗 ×0）

### 兌換系統

玩家可兌換背包中的獎品：
1. `/兌換` → 私密顯示背包獎品下拉選單
2. 選擇獎品 → 確認按鈕
3. 確認後獎品從背包移除，指定頻道發送公開通知

後台可自訂：
- 公告頻道（留空 = 使用者所在頻道）
- 標記身分組
- 訊息模板（支援 `{user}` `{item}` `{rarity}` `{role}` 變數）

### 活動模式

限時活動系統，從 Dashboard 啟動/結束：
- 啟動後所有代幣操作（簽到、打工、扭蛋、冒險）使用**限時代幣**
- 可設定每位玩家的初始限時代幣
- 結束活動時自動清除所有限時代幣，不影響普通代幣
- 指令顯示會自動切換為「限時代幣」

### Web Dashboard

內建後台管理介面，Bot 啟動時同時運行。

**設定頁** (`/`)：
- 精力、代幣、簽到設定
- 稀有度權重調整
- 兌換通知設定（頻道、身分組、訊息模板）
- 打工地點增刪
- 獎品池增刪（含機率顯示）
- 冒險事件增刪（支援自選投入類型）
- 活動模式啟動/結束
- 設定組合儲存/載入/刪除

**玩家管理頁** (`/users`)：
- 查看所有玩家列表
- 直接編輯個別玩家的精力、代幣、限時代幣
- 搜尋 User ID

## 安裝

### 前置需求

- Python 3.11+
- Discord Bot Token（[Discord Developer Portal](https://discord.com/developers/applications)）

### 步驟

```bash
# Clone
git clone https://github.com/fenganthony/gacha-bot.git
cd gacha-bot

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt

# 設定
cp config.example.json config.json
# 編輯 config.json，填入你的 bot token
```

### Discord Bot 設定

1. 到 [Discord Developer Portal](https://discord.com/developers/applications) 建立 Application
2. 進入 **Bot** 頁面，複製 Token 填入 `config.json`
3. 進入 **OAuth2 → URL Generator**，勾選 `bot` + `applications.commands`，權限選 `Administrator`
4. 用產生的連結邀請 Bot 到你的伺服器

### 啟動

```bash
python bot.py
```

Bot 和 Dashboard 會同時啟動：
- Discord Bot 上線
- Dashboard 預設在 `http://localhost:8080`（可透過環境變數 `PORT` 調整）

## 設定說明

`config.json` 欄位說明：

| 欄位 | 說明 |
|------|------|
| `bot_token` | Discord Bot Token |
| `energy.daily_amount` | 每日獲得精力 |
| `energy.max_amount` | 精力上限 |
| `work[]` | 打工地點列表（名稱、工時、精力消耗、代幣報酬） |
| `tokens.gacha_cost` | 扭蛋所需代幣 |
| `tokens.checkin_reward` | 簽到獎勵代幣 |
| `tokens.checkin_reset_hours` | 簽到冷卻小時數 |
| `activity.active` | 活動模式開關 |
| `activity.name` | 活動名稱 |
| `activity.initial_event_tokens` | 活動開始時每人初始限時代幣 |
| `redeem.channel_id` | 兌換公告頻道 ID（留空 = 當前頻道） |
| `redeem.role_id` | 兌換標記身分組 ID（留空 = 不標記） |
| `redeem.message_template` | 兌換公告訊息模板 |
| `admin_role` | 管理角色 ID |
| `rarity_weights` | N/R/SR/SSR 稀有度權重 |
| `gacha_pool[]` | 獎品列表（名稱、稀有度，秘藏需 weight） |
| `adventures[]` | 冒險事件列表（支援 custom_tokens 自選投入） |

## 技術架構

- **discord.py** — Discord Bot 框架
- **aiohttp** — Web Dashboard 伺服器
- **SQLite** — 玩家資料儲存
- **asyncio** — 非同步架構，DB 操作不阻塞事件循環
