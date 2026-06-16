# Run Name 與 Project Rename 更新

本次更新包含兩項 UI / 命名修正：

1. Step 8 重新開始生成時，Run folder 命名改為連續無底線格式：`<run_name>1`, `<run_name>2`, `<run_name>3`, ...。若目前 Step 6 顯示上一輪生成後的 `run2`，下一次重新開始會正確產生 `run3`，不會變成 `run21`。
2. Homepage 專案卡右上角選單新增 `Rename`，可直接修改專案名稱。重新命名會同步更新 project folder id、project_state.json、project_index.json 與目前選取卡片狀態；生成中會阻擋 rename，避免資料夾移動造成執行中路徑失效。

`Rename` 只改專案名稱；`Class Name` 與既有輸入、runs、exports 不會被更名或刪除。
