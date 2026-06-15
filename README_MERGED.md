# GenUI

此版本將 Defect 與 Food 兩套 UI 合併為單一入口。

## 執行

```bash
python launch_ui.py
```

啟動後會先進入 Step 0 模式選擇頁：

- `Gen Defect`：進入原 Defect 流程。
- `Gen Food`：進入原 Food 流程。

進入任一模式後，原本的 Step 0 Homepage 會顯示為 Step 1，其後流程依序往後位移。兩套模式各自保留自己的 `scripts/`、`tools/`、`docs/` 與專案狀態資料夾，避免互相覆蓋。
