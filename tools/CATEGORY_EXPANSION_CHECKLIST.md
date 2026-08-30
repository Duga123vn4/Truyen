# 📋 CHECKLIST BẮT BUỘC KHI MỞ RỘNG CATEGORY / ENTITY ID MỚI

> **Mục đích:** Đảm bảo tính toàn vẹn 100% của hệ sinh thái Lore, triệt tiêu hoàn toàn lỗi "sửa 1 chỗ quên nhiều chỗ" khi bổ sung một tiền tố thực thể mới (Ví dụ: `RACE-xxx` cho Chủng tộc, `TITLE-xxx` cho Danh hiệu, `CURSE-xxx` cho Lời nguyền).

---

## 🛠️ 6 BƯỚC KIỂM TRA BẮT BUỘC:

### 1. `[ ]` Cập nhật Bảng Ánh Xạ Enum (`VALID_LOAI_ENUM`)
* File: `canon_validator.py`, `3_Dich_Truyen_AI.bat`, `4_Quan_Ly_Novel.bat`.
* Bổ sung cặp từ khóa chuẩn hóa và tiền tố ID mới (Ví dụ: `"chủng tộc": ("RACE", "Chủng tộc", "races.md")`).

### 2. `[ ]` Cập nhật Hàm Nạp Core Canon Vào System Prompt
* File: `3_Dich_Truyen_AI.bat` (`get_glossary_content`) và `4_Quan_Ly_Novel.bat` (`get_full_canon_text`).
* Thêm file mới vào danh sách đọc ưu tiên nếu Category mới lưu ở file riêng (Ví dụ: `races.md`).

### 3. `[ ]` Cập nhật Thẩm Phán `canon_validator.py`
* File: `canon_validator.py`.
* Bổ sung quy tắc thẩm định, bóc tách và phân tầng bằng chứng cho loại thực thể mới.

### 4. `[ ]` Cập nhật Chức Năng Đổi Tên / Refactor Toàn Cục
* File: `4_Quan_Ly_Novel.bat` (`run_global_refactor`).
* Đảm bảo tính năng đổi tên quét qua cả file mới của Category đó.

### 5. `[ ]` Cập nhật Diff Studio & Báo Cáo Kiểm Toán
* File: `4_Quan_Ly_Novel.bat` (`generate_diff_data`, `DIFF_REPORT.md`).
* Đảm bảo các thay đổi của Category mới hiển thị trực quan trong báo cáo.

### 6. `[ ]` Chạy Kiểm Toán Toàn Vẹn Tham Chiếu (Referential Integrity Check)
* File: `test_suite_16.py` hoặc script audit.
* Xác nhận 100% mã ID mới được liên kết hợp lệ trong `ENTITY_INDEX.md` và không tạo ra tham chiếu mồ côi.
