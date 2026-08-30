"""
🧪 TEST SUITE 16 - CANON ENGINE STRESS TESTS (ATOMIC CLAIMS V3)
16 bài test độc lập với các câu lệnh assert cố định theo kiến trúc Mệnh Đề Nguyên Tử.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canon_validator import (
    verify_raw_grounding,
    resolve_entity,
    validate_single_atomic_claim,
    validate_single_entity_extraction,
    EntityIndexEntry,
    TemporalRelationManager,
    ValidationResult,
    AtomicClaimResult
)

def run_all_tests():
    print("=" * 75)
    print("🧪 BẮT ĐẦU CHẠY BỘ 16 STRESS TESTS (ATOMIC CLAIMS V3 - THUẦN VIỆT)")
    print("=" * 75)

    # --------------------------------------------------------------------------
    # TEST 01: Entity mới -> Phải tạo Canon với các Claims được duyệt
    # --------------------------------------------------------------------------
    raw_01 = "そこに立っていたのは、グラン国の第三王女ベアトリスだった。彼女は銀の髪を持ち、鋭い眼差しを向けていた。"
    item_01 = {
        "ten_vi": "Beatrice",
        "ten_goc": "ベアトリス",
        "vai_tro": "Đệ tam Công chúa Vương quốc Gran",
        "khang_dinh": [
            {
                "noi_dung": "Là Đệ tam Công chúa Vương quốc Gran",
                "bang_chung": "グラン国の第三王女ベアトリスだった",
                "loai_bang_chung": "TRỰC TIẾP",
                "nguon_phat_ngon": "NGƯỜI_KỂ_CHUYỆN",
                "do_tin_cay": "XÁC NHẬN"
            },
            {
                "noi_dung": "Có mái tóc màu bạc",
                "bang_chung": "彼女は銀の髪を持ち",
                "loai_bang_chung": "TRỰC TIẾP",
                "nguon_phat_ngon": "NGƯỜI_KỂ_CHUYỆN",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_01 = validate_single_entity_extraction(item_01, raw_01, current_chapter=1, is_chapter_translated=True, existing_index=[])
    assert res_01.is_valid is True, "T01 Failed: Must be valid"
    assert res_01.action == "CREATE_CANON", f"T01 Failed: Expected CREATE_CANON, got {res_01.action}"
    assert res_01.written_to_canon is True, "T01 Failed: Must be written to Canon"
    assert len(res_01.canon_claims) == 2, f"T01 Failed: Expected 2 canon claims, got {len(res_01.canon_claims)}"
    assert res_01.standard_name == "Beatrice", "T01 Failed: Standard name mismatch"
    print("  ✅ [T01 PASSED] Entity mới -> Tạo Canon chuẩn xác với 2 Mệnh đề nguyên tử.")

    # --------------------------------------------------------------------------
    # TEST 02: Entity xuất hiện lần 2 -> Không tạo duplicate, thêm Claims mới
    # --------------------------------------------------------------------------
    index_02 = [EntityIndexEntry(entity_id="CHAR-001", standard_name="Aurelia", original_name="オレーリア", entity_type="Nhân vật", status="BÌNH THƯỜNG", first_chapter=1)]
    raw_02 = "オレーリアは微笑みながらお茶を飲んだ。"
    item_02 = {
        "ten_vi": "Aurelia",
        "ten_goc": "オレーリア",
        "khang_dinh": [
            {
                "noi_dung": "Uống trà và mỉm cười",
                "bang_chung": "オレーリアは微笑みながらお茶を飲んだ",
                "loai_bang_chung": "TRỰC TIẾP",
                "nguon_phat_ngon": "NGƯỜI_KỂ_CHUYỆN",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_02 = validate_single_entity_extraction(item_02, raw_02, current_chapter=2, is_chapter_translated=True, existing_index=index_02)
    assert res_02.is_valid is True, "T02 Failed: Must be valid"
    assert res_02.action == "SKIP_CANON", f"T02 Failed: Expected SKIP_CANON, got {res_02.action}"
    assert res_02.entity_id == "CHAR-001", "T02 Failed: Entity ID mismatch"
    assert res_02.written_to_canon is False, "T02 Failed: Must NOT write duplicate to Canon DB"
    assert len(res_02.canon_claims) == 1, "T02 Failed: Must capture new claim in evidence log"
    print("  ✅ [T02 PASSED] Entity xuất hiện lại -> Chặn duplicate, chỉ bổ sung Mệnh đề.")

    # --------------------------------------------------------------------------
    # TEST 03: Tên đầy đủ xuất hiện sau tên ngắn -> Merge & Upgrade vào Entity cũ
    # --------------------------------------------------------------------------
    index_03 = [EntityIndexEntry(entity_id="CHAR-004", standard_name="Dylan", original_name="ディラン", entity_type="Nhân vật", status="BÌNH THƯỜNG", first_chapter=1)]
    raw_03 = "ディラン・クロムウェルは剣を構えた。"
    item_03 = {
        "ten_vi": "Dylan Cromwell",
        "ten_goc": "ディラン・クロムウェル",
        "khang_dinh": [
            {
                "noi_dung": "Vào thế thủ kiếm",
                "bang_chung": "ディラン・クロムウェルは剣を構えた",
                "loai_bang_chung": "TRỰC TIẾP",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_03 = validate_single_entity_extraction(item_03, raw_03, current_chapter=4, is_chapter_translated=True, existing_index=index_03)
    assert res_03.is_valid is True, "T03 Failed: Must be valid"
    assert res_03.action == "UPGRADE_MERGE", f"T03 Failed: Expected UPGRADE_MERGE, got {res_03.action}"
    assert res_03.entity_id == "CHAR-004", "T03 Failed: Must keep original ID CHAR-004"
    assert res_03.standard_name == "Dylan Cromwell", "T03 Failed: Name must be upgraded to Dylan Cromwell"
    assert "Dylan" in res_03.aliases, "T03 Failed: Old short name must be kept as alias"
    print("  ✅ [T03 PASSED] Tên đầy đủ -> Merge & Nâng cấp tên chuẩn, giữ nguyên ID.")

    # --------------------------------------------------------------------------
    # TEST 04: Alias -> Nhận diện và liên kết vào Entity cũ
    # --------------------------------------------------------------------------
    index_04 = [EntityIndexEntry(entity_id="CHAR-003", standard_name="Felix", original_name="フェリクス", entity_type="Nhân vật", status="BÌNH THƯỜNG", first_chapter=1, aliases=[])]
    raw_04 = "学園で『氷の王子』と呼ばれるフェリクス殿下。"
    item_04 = {
        "ten_vi": "Hoàng tử Băng Giá",
        "ten_goc": "氷の王子",
        "khang_dinh": [
            {
                "noi_dung": "Được gọi là Hoàng tử Băng Giá tại học viện",
                "bang_chung": "学園で『氷の王子』と呼ばれるフェリクス殿下",
                "loai_bang_chung": "TRỰC TIẾP",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_04 = validate_single_entity_extraction(item_04, raw_04, current_chapter=2, is_chapter_translated=True, existing_index=index_04)
    assert res_04.is_valid is True, "T04 Failed: Must be valid"
    assert res_04.action == "ADD_ALIAS", f"T04 Failed: Expected ADD_ALIAS, got {res_04.action}"
    assert res_04.entity_id == "CHAR-003", "T04 Failed: Must point to Felix (CHAR-003)"
    print("  ✅ [T04 PASSED] Bí danh (Alias) -> Nhận diện và liên kết vào Entity gốc.")

    # --------------------------------------------------------------------------
    # TEST 05: Hồi tưởng -> Evidence Quá khứ, không biến thành trạng thái hiện tại
    # --------------------------------------------------------------------------
    raw_05 = "フェリクスは昔、エルザが聖剣を手にしていた姿を思い出した。"
    item_05 = {
        "ten_vi": "Elsa",
        "ten_goc": "エルザ",
        "khang_dinh": [
            {
                "noi_dung": "Từng cầm trên tay thanh thánh kiếm trong quá khứ",
                "bang_chung": "フェリクスは昔、エルザが聖剣を手にしていた姿を思い出した",
                "loai_bang_chung": "HỒI TƯỞNG",
                "pham_vi_thoi_gian": {"loai": "QUÁ_KHỨ", "tu_chuong": 1, "den_chuong": 10},
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_05 = validate_single_entity_extraction(item_05, raw_05, current_chapter=80, is_chapter_translated=True, existing_index=[])
    assert res_05.claims[0].pham_vi_thoi_gian["loai"] == "QUÁ_KHỨ", f"T05 Failed: Expected QUÁ_KHỨ, got {res_05.claims[0].pham_vi_thoi_gian}"
    assert res_05.claims[0].loai_bang_chung == "HỒI TƯỞNG", "T05 Failed: Evidence type mismatch"
    print("  ✅ [T05 PASSED] Hồi tưởng -> Định danh phạm vi QUÁ KHỨ, không nhầm thành hiện tại.")

    # --------------------------------------------------------------------------
    # TEST 06: Lời kể từ Nhân vật (Nói dối / Tin đồn) -> Lưu nguồn, hạ độ tin cậy
    # --------------------------------------------------------------------------
    raw_06 = "「オレーリア様が王家の証を盗んだのです！」とエルザは叫んだ。"
    claim_06 = {
        "noi_dung": "Aurelia đánh cắp tín vật Hoàng tộc",
        "bang_chung": "「オレーリア様が王家の証を盗んだのです！」とエルザは叫んだ",
        "loai_bang_chung": "LỜI KỂ",
        "nguon_phat_ngon": "CHAR-007 (Elsa)",
        "do_tin_cay": "XÁC NHẬN"
    }
    res_claim_06 = validate_single_atomic_claim(claim_06, raw_06, current_chapter=12)
    assert res_claim_06.do_tin_cay == "SUY ĐOÁN", f"T06 Failed: Hearsay must be downgraded, got {res_claim_06.do_tin_cay}"
    assert res_claim_06.action == "SEND_TO_REVIEW", "T06 Failed: Must send character claim to review/evidence"
    assert "Elsa" in res_claim_06.noi_dung, "T06 Failed: Speaker must be attributed in claim content"
    print("  ✅ [T06 PASSED] Lời kể nhân vật -> Gắn Nguồn phát ngôn, hạ độ tin cậy xuống SUY ĐOÁN.")

    # --------------------------------------------------------------------------
    # TEST 07: Tưởng tượng -> Lưu Sổ cái bằng chứng (Tâm lý), CẤM vào Canon DB
    # --------------------------------------------------------------------------
    raw_07 = "もしここでフェリクスを暗殺したらどうなるだろう、とオレーリアは空想した。"
    item_07 = {
        "ten_vi": "Aurelia",
        "ten_goc": "オレーリア",
        "khang_dinh": [
            {
                "noi_dung": "Tưởng tượng kịch bản ám sát Felix",
                "bang_chung": "もしここでフェリクスを暗殺したらどうなるだろう、とオレーリアは空想した",
                "loai_bang_chung": "TƯỞNG TƯỢNG",
                "nguon_phat_ngon": "CHAR-001 (Aurelia)",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    index_07 = [EntityIndexEntry(entity_id="CHAR-001", standard_name="Aurelia", original_name="オレーリア", entity_type="Nhân vật", status="BÌNH THƯỜNG", first_chapter=1)]
    res_07 = validate_single_entity_extraction(item_07, raw_07, current_chapter=3, is_chapter_translated=True, existing_index=index_07)
    assert res_07.claims[0].action == "EVIDENCE_LOG_ONLY", f"T07 Failed: Expected EVIDENCE_LOG_ONLY, got {res_07.claims[0].action}"
    assert res_07.written_to_canon is False, "T07 Failed: Must NOT be written to Canon DB"
    assert res_07.in_review_queue is False, "T07 Failed: Must NOT pollute Review Queue"
    print("  ✅ [T07 PASSED] Tưởng tượng -> Lưu Sổ cái bằng chứng tâm lý, cấm vào Canon, không rác Review.")

    # --------------------------------------------------------------------------
    # TEST 08: Suy luận yếu -> Đưa vào Hàng chờ duyệt, không tự động Canon hóa
    # --------------------------------------------------------------------------
    raw_08 = "彼は黒いマントを着ていた。おそらく秘密組織の幹部だろう。"
    item_08 = {
        "ten_vi": "Cán bộ Tổ chức Bí mật",
        "ten_goc": "秘密組織幹部",
        "khang_dinh": [
            {
                "noi_dung": "Là cán bộ cấp cao của tổ chức bí mật",
                "bang_chung": "おそらく秘密組織の幹部だろう",
                "loai_bang_chung": "SUY LUẬN",
                "do_tin_cay": "SUY ĐOÁN"
            }
        ]
    }
    res_08 = validate_single_entity_extraction(item_08, raw_08, current_chapter=15, is_chapter_translated=True, existing_index=[])
    assert res_08.action == "SEND_TO_REVIEW", f"T08 Failed: Expected SEND_TO_REVIEW, got {res_08.action}"
    assert res_08.in_review_queue is True, "T08 Failed: Must be placed in Review Queue"
    assert res_08.written_to_canon is False, "T08 Failed: Must NOT be written to Canon DB"
    print("  ✅ [T08 PASSED] Suy luận yếu -> Chuyển vào Hàng chờ duyệt chờ thẩm định.")

    # --------------------------------------------------------------------------
    # TEST 09: Canon cũ bị mâu thuẫn -> Đánh dấu XUNG ĐỘT và chuyển Hàng chờ duyệt
    # --------------------------------------------------------------------------
    raw_09 = "「フェリクス殿下とオレーリア様の婚約など、初めから存在しない」と告げられた。"
    item_09 = {
        "ten_vi": "Hôn ước Felix-Aurelia",
        "ten_goc": "婚約不存在",
        "khang_dinh": [
            {
                "noi_dung": "Hôn ước chưa từng tồn tại",
                "bang_chung": "フェリクス殿下とオレーリア様の婚約など、初めから存在しない",
                "loai_bang_chung": "TRỰC TIẾP",
                "do_tin_cay": "XÁC NHẬN",
                "trang_thai": "XUNG ĐỘT"
            }
        ]
    }
    res_09 = validate_single_entity_extraction(item_09, raw_09, current_chapter=20, is_chapter_translated=True, existing_index=[])
    assert res_09.action == "SEND_TO_REVIEW", f"T09 Failed: Expected SEND_TO_REVIEW, got {res_09.action}"
    assert res_09.claims[0].trang_thai == "XUNG ĐỘT", f"T09 Failed: Expected status XUNG ĐỘT, got {res_09.claims[0].trang_thai}"
    assert res_09.in_review_queue is True, "T09 Failed: Must be placed in Review Queue"
    print("  ✅ [T09 PASSED] Mâu thuẫn Canon -> Đánh dấu XUNG ĐỘT và chuyển Hàng chờ duyệt.")

    # --------------------------------------------------------------------------
    # TEST 10: Canon cũ thay đổi (Hủy hôn ở Ch.20) -> Cửa sổ thời gian (Temporal Windowing)
    # --------------------------------------------------------------------------
    tm_10 = TemporalRelationManager()
    tm_10.add_or_update_relation("REL-001", "CHAR-003", "HÔN PHU", "CHAR-001", current_chapter=1, evidence="婚約者")
    tm_10.add_or_update_relation("REL-002", "CHAR-003", "HỦY HÔN", "CHAR-001", current_chapter=20, evidence="婚約破棄", status="ĐÃ THAY ĐỔI")
    
    q_ch10 = tm_10.query_relation_at_chapter("CHAR-003", "CHAR-001", chapter_num=10)
    q_ch25 = tm_10.query_relation_at_chapter("CHAR-003", "CHAR-001", chapter_num=25)
    assert q_ch10 is not None and q_ch10.relation_type == "HÔN PHU", "T10 Failed: Ch.10 must be HÔN PHU"
    assert q_ch25 is not None and q_ch25.relation_type == "HỦY HÔN", "T10 Failed: Ch.25 must be HỦY HÔN"
    print("  ✅ [T10 PASSED] State transition -> Đóng Cửa sổ thời gian cũ (Ch.20), mở Cửa sổ mới.")

    # --------------------------------------------------------------------------
    # TEST 11: Nhân vật đổi trạng thái (Tử trận / Bị phế truất)
    # --------------------------------------------------------------------------
    tm_11 = TemporalRelationManager()
    rel_11 = tm_11.add_or_update_relation("REL-003", "CHAR-007", "TRẠNG_THÁI", "BỊ_PHẾ_TRUẤT", current_chapter=30, evidence="アイゼンベルク侯爵家取り潰し", status="ĐÃ THAY ĐỔI")
    assert rel_11.hieu_luc_tu_chuong == 30, "T11 Failed: Must take effect from Ch.30"
    assert rel_11.target_id == "BỊ_PHẾ_TRUẤT", "T11 Failed: Status target mismatch"
    print("  ✅ [T11 PASSED] Nhân vật đổi trạng thái -> Ghi nhận mốc hiệu lực chính xác.")

    # --------------------------------------------------------------------------
    # TEST 12: Tái xuất sau 100 chương -> Khớp đúng ID cũ không sinh rác
    # --------------------------------------------------------------------------
    index_12 = [
        EntityIndexEntry(entity_id="CHAR-005", standard_name="Nina", original_name="ニナ", entity_type="Nhân vật", status="BÌNH THƯỜNG", first_chapter=1)
    ]
    raw_12 = "100年ぶりにニナが姿を現した。"
    item_12 = {
        "ten_vi": "Nina",
        "ten_goc": "ニナ",
        "khang_dinh": [
            {
                "noi_dung": "Xuất hiện trở lại sau 100 năm",
                "bang_chung": "ニナが姿を現した",
                "loai_bang_chung": "TRỰC TIẾP",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_12 = validate_single_entity_extraction(item_12, raw_12, current_chapter=101, is_chapter_translated=True, existing_index=index_12)
    assert res_12.action == "SKIP_CANON", f"T12 Failed: Expected SKIP_CANON, got {res_12.action}"
    assert res_12.entity_id == "CHAR-005", "T12 Failed: Must match CHAR-005"
    assert res_12.written_to_canon is False, "T12 Failed: Must not duplicate"
    print("  ✅ [T12 PASSED] Tái xuất sau 100 chương -> Khớp đúng ID cũ, chống sinh rác.")

    # --------------------------------------------------------------------------
    # TEST 13: Chuyển quyền sở hữu vật phẩm theo thời gian
    # --------------------------------------------------------------------------
    tm_13 = TemporalRelationManager()
    tm_13.add_or_update_relation("REL-101", "ITEM-001", "SỞ_HỮU_BỞI", "Elsa", current_chapter=1, evidence="エルザの剣")
    tm_13.add_or_update_relation("REL-102", "ITEM-001", "SỞ_HỮU_BỞI", "Aurelia", current_chapter=50, evidence="オレーリアに譲渡された", status="ĐÃ THAY ĐỔI")
    
    owner_ch20 = tm_13.query_relation_at_chapter("ITEM-001", "Elsa", chapter_num=20)
    owner_ch60 = tm_13.query_relation_at_chapter("ITEM-001", "Aurelia", chapter_num=60)
    assert owner_ch20 is not None and owner_ch20.target_id == "Elsa", "T13 Failed: Ch.20 owner must be Elsa"
    assert owner_ch60 is not None and owner_ch60.target_id == "Aurelia", "T13 Failed: Ch.60 owner must be Aurelia"
    print("  ✅ [T13 PASSED] Chuyển giao vật phẩm -> Timeline sở hữu biến động chuẩn xác.")

    # --------------------------------------------------------------------------
    # TEST 14: RAW chưa dịch -> Phân tầng FUTURE EVIDENCE, không ghi Canon
    # --------------------------------------------------------------------------
    raw_14 = "未来の予言者カサンドラが登場する。"
    item_14 = {
        "ten_vi": "Cassandra",
        "ten_goc": "カサンドラ",
        "khang_dinh": [
            {
                "noi_dung": "Là nhà tiên tri của tương lai",
                "bang_chung": "未来の予言者カサンドラが登場する",
                "loai_bang_chung": "TRỰC TIẾP",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_14 = validate_single_entity_extraction(item_14, raw_14, current_chapter=150, is_chapter_translated=False, existing_index=[])
    assert res_14.stage == "FUTURE_EVIDENCE", f"T14 Failed: Expected FUTURE_EVIDENCE, got {res_14.stage}"
    assert res_14.written_to_canon is False, "T14 Failed: Future evidence must NOT write to active Canon"
    assert res_14.log_evidence is True, "T14 Failed: Must still log in future evidence"
    print("  ✅ [T14 PASSED] RAW chưa dịch -> Phân tầng FUTURE_EVIDENCE, bảo vệ Canon.")

    # --------------------------------------------------------------------------
    # TEST 15: AI bịa bằng chứng không có trong RAW -> REJECT HALLUCINATION
    # --------------------------------------------------------------------------
    raw_15 = "部屋の中には誰もいなかった。静寂だけが広がっていた。"
    item_15 = {
        "ten_vi": "Kẻ Ám Sát Thần Bí",
        "ten_goc": "謎の暗殺者",
        "khang_dinh": [
            {
                "noi_dung": "Sát thủ áo đen cầm dao xuất hiện",
                "bang_chung": "黒ずくめの暗殺者が短剣を握りしめて現れた",  # BẰNG CHỨNG GIẢ MẠO!
                "loai_bang_chung": "TRỰC TIẾP",
                "do_tin_cay": "XÁC NHẬN"
            }
        ]
    }
    res_15 = validate_single_entity_extraction(item_15, raw_15, current_chapter=5, is_chapter_translated=True, existing_index=[])
    assert res_15.is_valid is False, "T15 Failed: Must be invalid"
    assert res_15.action == "REJECT_HALLUCINATION", f"T15 Failed: Expected REJECT_HALLUCINATION, got {res_15.action}"
    assert res_15.written_to_canon is False, "T15 Failed: Must NOT write hallucination to Canon"
    print("  ✅ [T15 PASSED] Bằng chứng giả mạo -> REJECT HALLUCINATION thành công!")

    # --------------------------------------------------------------------------
    # TEST 16: Rollback / Audit History Integrity (Append-Only)
    # --------------------------------------------------------------------------
    tm_16 = TemporalRelationManager()
    tm_16.add_or_update_relation("REL-201", "Elsa", "HÔN_NHÂN", "ĐỘC_THÂN", current_chapter=1, evidence="独身")
    tm_16.add_or_update_relation("REL-202", "Elsa", "HÔN_NHÂN", "ĐÃ_KẾT_HÔN", current_chapter=20, evidence="結婚した", status="ĐÃ THAY ĐỔI")
    tm_16.add_or_update_relation("REL-203", "Elsa", "HÔN_NHÂN", "LY_HÔN", current_chapter=50, evidence="離婚した", status="ĐÃ THAY ĐỔI")
    
    assert len(tm_16.history_audit_trail) >= 3, "T16 Failed: Audit trail must preserve all events"
    assert len(tm_16.relations) == 3, "T16 Failed: All historical relation records must be retained"
    print("  ✅ [T16 PASSED] Sổ cái kiểm toán bất biến -> Lưu lịch sử Append-Only qua các mốc thời gian.")

    print("=" * 75)
    print("🎉 TẤT CẢ 16/16 STRESS TESTS ĐÃ VƯỢT QUA VỚI ASSERTION ATOMIC CLAIMS V3!")
    print("=" * 75)

if __name__ == "__main__":
    run_all_tests()
