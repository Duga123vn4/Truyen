VALID_CATEGORY_PATTERNS = [
    # (Category Key, ID Prefix, Standard Name, Target File, [Keywords])
    ("RACE", "RACE", "Chủng tộc / Tộc loài", "terms.md", ["chủng tộc", "tộc loài", "thú nhân", "tinh linh tộc", "long nhân", "dwarf", "elf", "tiểu tinh linh", "quỷ tộc", "ma tộc", "nhân tộc", "race", "beastman"]),
    ("ORG", "ORG", "Tổ chức / Phe phái", "factions_orgs.md", ["tổ chức", "học viện", "gia tộc", "hoàng tộc", "giáo hội", "quân đội", "hiệp hội", "bang hội", "đoàn kỵ sĩ", "công hội", "phái", "cục", "đoàn", "org", "faction"]),
    ("PLACE", "PLACE", "Địa danh", "locations.md", ["địa danh", "tầng tháp", "thành phố", "thị trấn", "di tích", "lâu đài", "vương quốc", "đế quốc", "hầm ngục", "núi", "rừng", "quảng trường", "pháo đài", "dungeon", "place", "location"]),
    ("ITEM", "ITEM", "Vật phẩm / Trang bị", "terms.md", ["vật phẩm", "trang bị", "vũ khí", "dược phẩm", "thuốc", "bảo vật", "thần khí", "kiếm", "rìu", "gậy", "áo giáp", "khiên", "lõi", "ma thạch", "item", "equipment", "weapon", "book", "tài liệu", "tác phẩm"]),
    ("SKILL", "SKILL", "Kỹ năng / Ma pháp", "terms.md", ["kỹ năng", "ma pháp", "chiêu thức", "phép thuật", "tuyệt kỹ", "chú thuật", "skill", "magic", "spell"]),
    ("JOB", "JOB", "Thiên chức", "terms.md", ["thiên chức", "nghề nghiệp", "chức nghiệp", "job", "class", "vocation"]),
    ("MONSTER", "MONSTER", "Sinh vật / Quái vật", "terms.md", ["sinh vật", "quái vật", "ma thú", "quái thú", "sinh linh", "yêu quái", "quái ma", "quái", "monster", "beast", "creature"]),
    ("EVENT", "EVENT", "Sự kiện", "events.md", ["sự kiện", "hội thảo", "chiến dịch", "khủng hoảng", "trận chiến", "đại hội", "event"]),
    ("TERM", "TERM", "Thuật ngữ thế giới", "terms.md", ["thuật ngữ", "khái niệm", "term"])
]

def classify_entity_type_robust(raw_loai: str):
    """Phân loại thực thể 3 Tầng (Exact Match + Token Split + Head-Noun Resolution)."""
    if not raw_loai:
        return None
    raw_clean = raw_loai.strip().lower()
    
    # Tầng 1: Exact Match hoàn toàn
    for cat_key, pfx, itype, tf, kws in VALID_CATEGORY_PATTERNS:
        for kw in kws:
            if raw_clean == kw:
                return (pfx, itype, tf)
                
    # Tầng 2: Token Split Match (ngăn cách bằng / hoặc dấu phẩy)
    tokens = [t.strip() for t in re.split(r'[/, -]+', raw_clean) if t.strip()]
    if tokens:
        first_token = tokens[0]
        for cat_key, pfx, itype, tf, kws in VALID_CATEGORY_PATTERNS:
            for kw in kws:
                if first_token == kw:
                    return (pfx, itype, tf)
                    
    # Tầng 3: Head-Noun Position Match (Từ khóa danh từ chính xuất hiện đầu tiên)
    best_match = None
    min_pos = 999999
    
    for cat_key, pfx, itype, tf, kws in VALID_CATEGORY_PATTERNS:
        for kw in kws:
            pos = raw_clean.find(kw)
            if pos != -1 and pos < min_pos:
                min_pos = pos
                best_match = (pfx, itype, tf)
                
    return best_match


    raw_clean = raw_loai.strip().lower()
    for kw, target_info in VALID_LOAI_ENUM.items():
        if kw in raw_clean:
            return target_info
    return None


"""
🏛️ CANON VALIDATOR & CONFLICT RESOLVER (CANON ENGINE V3 - ATOMIC CLAIMS)
Pure Python Module - Không phụ thuộc LLM.
Thực thi nguyên tắc Tam Quyền Phân Lập (Separation of Powers) và Atomic Claims.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import re
import json
import unicodedata
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict

# ==============================================================================
# 1. DATA STRUCTURES & PROTOCOLS
# ==============================================================================

@dataclass
class AtomicClaimResult:
    noi_dung: str
    bang_chung: str
    loai_bang_chung: str = "TRỰC TIẾP"
    nguon_phat_ngon: str = "NGƯỜI_KỂ_CHUYỆN"
    pham_vi_thoi_gian: Dict[str, Any] = field(default_factory=lambda: {"loai": "HIỆN_TẠI", "tu_chuong": None, "den_chuong": None})
    do_tin_cay: str = "XÁC NHẬN"
    trang_thai: str = "BÌNH THƯỜNG"
    is_grounded: bool = True
    action: str = "CREATE_CANON"  # CREATE_CANON, EVIDENCE_LOG_ONLY, SEND_TO_REVIEW, REJECT_HALLUCINATION
    details: str = ""

@dataclass
class ValidationResult:
    is_valid: bool
    action: str  # CREATE_CANON, SKIP_CANON, UPGRADE_MERGE, ADD_ALIAS, EVIDENCE_LOG_ONLY, SEND_TO_REVIEW, REJECT_HALLUCINATION
    entity_id: Optional[str] = None
    standard_name: str = ""
    original_name: str = ""
    entity_type: str = "NHÂN VẬT"
    status: str = "BÌNH THƯỜNG"
    confidence: str = "XÁC NHẬN"
    evidence_type: str = "TRỰC TIẾP"
    temporal_scope: str = "HIỆN TẠI"
    hieu_luc_tu_chuong: Optional[int] = None
    hieu_luc_den_chuong: Optional[int] = None
    stage: str = "CONFIRMED_CANON"  # CONFIRMED_CANON, FUTURE_EVIDENCE, UNCONFIRMED
    details: str = ""
    raw_evidence: str = ""
    written_to_canon: bool = False
    in_review_queue: bool = False
    log_evidence: bool = True
    aliases: List[str] = field(default_factory=list)
    claims: List[AtomicClaimResult] = field(default_factory=list)
    canon_claims: List[AtomicClaimResult] = field(default_factory=list)
    rejected_claims: List[AtomicClaimResult] = field(default_factory=list)
    review_claims: List[AtomicClaimResult] = field(default_factory=list)

@dataclass
class EntityIndexEntry:
    entity_id: str
    standard_name: str
    original_name: str
    entity_type: str
    status: str
    first_chapter: int
    aliases: List[str] = field(default_factory=list)

@dataclass
class TemporalRelation:
    relation_id: str
    source_id: str
    relation_type: str
    target_id: str
    noi_dung: str
    hieu_luc_tu_chuong: Optional[int]
    hieu_luc_den_chuong: Optional[int]
    evidence: str
    confidence: str
    status: str = "BÌNH THƯỜNG"
    speaker: str = "NGƯỜI_KỂ_CHUYỆN"

# ==============================================================================
# 2. RAW GROUNDING VERIFIER (CHỐNG BẰNG CHỨNG GIẢ MẠO / HALLUCINATION)
# ==============================================================================

def normalize_text_for_matching(text: str) -> str:
    """Loại bỏ khoảng trắng thừa, dấu câu, chuẩn hóa unicode để so khớp chuỗi bền bỉ."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\s\r\n\t「」『』"\'\.,…—\-\(\)（）]', '', text)
    return text.lower()

def verify_raw_grounding(raw_text: str, evidence: str, min_chars: int = 4) -> bool:
    """
    Kiểm tra xem câu bằng chứng (bang_chung) có thực sự xuất hiện trong RAW hay không.
    Trả về True nếu câu bằng chứng hợp lệ, False nếu là BẰNG CHỨNG GIẢ MẠO (Hallucination).
    """
    if not evidence or not evidence.strip():
        return False
    
    clean_raw = normalize_text_for_matching(raw_text)
    clean_evidence = normalize_text_for_matching(evidence)
    
    if len(clean_evidence) < min_chars:
        return clean_evidence in clean_raw
    
    # 1. So khớp trực tiếp toàn bộ chuỗi
    if clean_evidence in clean_raw:
        return True
    
    # 2. Nếu câu bằng chứng dài có dấu '...', thử tách các phân đoạn chính
    parts = [p.strip() for p in re.split(r'\.\.\.|…', evidence) if len(p.strip()) >= min_chars]
    if parts:
        all_parts_found = True
        for part in parts:
            clean_part = normalize_text_for_matching(part)
            if clean_part and clean_part not in clean_raw:
                all_parts_found = False
                break
        if all_parts_found:
            return True
            
    # 3. Trượt cửa sổ tìm kiếm nếu có sai lệch nhỏ dấu câu
    half_len = max(min_chars, int(len(clean_evidence) * 0.6))
    if clean_evidence[:half_len] in clean_raw or clean_evidence[-half_len:] in clean_raw:
        return True
        
    return False

# ==============================================================================
# 3. ENTITY RESOLVER & MERGING ENGINE
# ==============================================================================

def resolve_entity(
    new_entity: dict,
    existing_entities: List[EntityIndexEntry]
) -> Tuple[str, Optional[EntityIndexEntry], dict]:
    """
    Phân giải thực thể:
    - NEW: Thực thể hoàn toàn mới
    - EXISTING: Thực thể đã có, không thay đổi tên
    - UPGRADE_MERGE: Tên đầy đủ xuất hiện sau tên ngắn (Dylan -> Dylan Cromwell)
    - ADD_ALIAS: Bí danh / danh xưng mới của thực thể đã có
    """
    name_vi = (new_entity.get("ten_vi") or new_entity.get("name_vi") or "").strip()
    name_goc = (new_entity.get("ten_goc") or new_entity.get("name_orig") or "").strip()
    
    if not name_vi and not name_goc:
        return "REJECT", None, {}

    clean_orig = normalize_text_for_matching(name_goc)
    clean_vi = normalize_text_for_matching(name_vi)
    
    # 1. Quét tìm khớp chính xác (Exact Match)
    for ext in existing_entities:
        ext_clean_orig = normalize_text_for_matching(ext.original_name)
        ext_clean_vi = normalize_text_for_matching(ext.standard_name)
        
        if (clean_orig and clean_orig == ext_clean_orig) or (clean_vi and clean_vi == ext_clean_vi):
            return "EXISTING", ext, {"matched_id": ext.entity_id}
            
        for alias in ext.aliases:
            if normalize_text_for_matching(alias) in (clean_orig, clean_vi):
                return "EXISTING", ext, {"matched_id": ext.entity_id}

    # 2. Quét tìm Nâng cấp tên đầy đủ (Upgrade / Merge: Tên mới chứa tên cũ)
    for ext in existing_entities:
        ext_clean_orig = normalize_text_for_matching(ext.original_name)
        ext_clean_vi = normalize_text_for_matching(ext.standard_name)
        
        if ext_clean_orig and clean_orig and len(clean_orig) > len(ext_clean_orig) and ext_clean_orig in clean_orig:
            return "UPGRADE_MERGE", ext, {
                "target_id": ext.entity_id,
                "old_name_vi": ext.standard_name,
                "new_name_vi": name_vi,
                "old_name_orig": ext.original_name,
                "new_name_orig": name_goc
            }
            
        if ext_clean_vi and clean_vi and len(clean_vi) > len(ext_clean_vi) and ext_clean_vi in clean_vi:
            return "UPGRADE_MERGE", ext, {
                "target_id": ext.entity_id,
                "old_name_vi": ext.standard_name,
                "new_name_vi": name_vi,
                "old_name_orig": ext.original_name,
                "new_name_orig": name_goc
            }

    # 3. Quét nhận diện Bí danh (Alias)
    for ext in existing_entities:
        if name_vi in ["Hoàng tử Băng Giá", "Hoàng tử Băng", "Đệ Nhất Hoàng Tử"] and "Felix" in ext.standard_name:
            return "ADD_ALIAS", ext, {"target_id": ext.entity_id, "new_alias": name_vi}
        if name_vi in ["Ác nữ", "Tiểu thư Rosenberg"] and "Aurelia" in ext.standard_name:
            return "ADD_ALIAS", ext, {"target_id": ext.entity_id, "new_alias": name_vi}

    return "NEW", None, {}

# ==============================================================================
# 4. ATOMIC CLAIM VALIDATOR (THẨM ĐỊNH TỪNG MỆNH ĐỀ ĐỘC LẬP)
# ==============================================================================

def validate_single_atomic_claim(
    claim_dict: dict,
    raw_text: str,
    current_chapter: int
) -> AtomicClaimResult:
    """
    Thẩm định 1 Mệnh đề Nguyên tử (Atomic Claim).
    Trả về AtomicClaimResult với hành vi định tuyến cụ thể.
    """
    noi_dung = (claim_dict.get("noi_dung") or claim_dict.get("content") or claim_dict.get("claim") or "").strip()
    bang_chung = (claim_dict.get("bang_chung") or claim_dict.get("evidence") or "").strip()
    loai_bang_chung = (claim_dict.get("loai_bang_chung") or claim_dict.get("evidence_type") or "TRỰC TIẾP").upper().strip()
    nguon_phat_ngon = (claim_dict.get("nguon_phat_ngon") or claim_dict.get("speaker") or "NGƯỜI_KỂ_CHUYỆN").strip()
    do_tin_cay = (claim_dict.get("do_tin_cay") or claim_dict.get("confidence") or "CHƯA XÁC NHẬN").upper().strip()
    trang_thai = (claim_dict.get("trang_thai") or claim_dict.get("status") or "BÌNH THƯỜNG").upper().strip()
    
    # Chuẩn hóa pham_vi_thoi_gian
    pv_input = claim_dict.get("pham_vi_thoi_gian") or claim_dict.get("temporal_scope") or "HIỆN_TẠI"
    if isinstance(pv_input, dict):
        pham_vi_thoi_gian = {
            "loai": pv_input.get("loai", "HIỆN_TẠI").upper(),
            "tu_chuong": pv_input.get("tu_chuong", current_chapter),
            "den_chuong": pv_input.get("den_chuong", None)
        }
    else:
        pham_vi_thoi_gian = {
            "loai": str(pv_input).upper(),
            "tu_chuong": current_chapter if str(pv_input).upper() in ["HIỆN_TẠI", "HIỆN TẠI"] else None,
            "den_chuong": None
        }

    # BƯỚC 1: KIỂM TRA BÁM NGUỒN (Grounding Check)
    if not bang_chung or not verify_raw_grounding(raw_text, bang_chung):
        return AtomicClaimResult(
            noi_dung=noi_dung,
            bang_chung=bang_chung,
            loai_bang_chung=loai_bang_chung,
            nguon_phat_ngon=nguon_phat_ngon,
            pham_vi_thoi_gian=pham_vi_thoi_gian,
            do_tin_cay=do_tin_cay,
            trang_thai=trang_thai,
            is_grounded=False,
            action="REJECT_HALLUCINATION",
            details="Bằng chứng không tồn tại trong văn bản RAW (BẰNG CHỨNG GIẢ MẠO)."
        )

    # BƯỚC 2: XỬ LÝ TƯỞNG TƯỢNG / GIẤC MƠ
    if loai_bang_chung in ["TƯỞNG TƯỢNG", "GIẤC MƠ"]:
        return AtomicClaimResult(
            noi_dung=noi_dung,
            bang_chung=bang_chung,
            loai_bang_chung=loai_bang_chung,
            nguon_phat_ngon=nguon_phat_ngon,
            pham_vi_thoi_gian=pham_vi_thoi_gian,
            do_tin_cay=do_tin_cay,
            trang_thai=trang_thai,
            is_grounded=True,
            action="EVIDENCE_LOG_ONLY",
            details="Diễn biến tâm lý / Tưởng tượng -> Lưu Sổ cái bằng chứng, không tạo Fact/Event."
        )

    # BƯỚC 3: XỬ LÝ NHẮC ĐẾN
    if loai_bang_chung in ["NHẮC ĐẾN"]:
        return AtomicClaimResult(
            noi_dung=noi_dung,
            bang_chung=bang_chung,
            loai_bang_chung=loai_bang_chung,
            nguon_phat_ngon=nguon_phat_ngon,
            pham_vi_thoi_gian=pham_vi_thoi_gian,
            do_tin_cay="SUY ĐOÁN",
            trang_thai=trang_thai,
            is_grounded=True,
            action="EVIDENCE_LOG_ONLY",
            details="Chỉ được nhắc đến, không có hành động cụ thể -> Lưu Sổ cái bằng chứng."
        )

    # BƯỚC 4: XỬ LÝ LỜI KỂ / THƯ TỪ CỦA NHÂN VẬT (Nói dối, tin đồn)
    if loai_bang_chung in ["LỜI KỂ", "THƯ TỪ"]:
        if nguon_phat_ngon not in ["NGƯỜI_KỂ_CHUYỆN", "NGUOIKLECHUYEN", "NARRATOR"]:
            # Lời nói của nhân vật không mặc nhiên là sự thật khách quan
            return AtomicClaimResult(
                noi_dung=f"{nguon_phat_ngon} tuyên bố: {noi_dung}",
                bang_chung=bang_chung,
                loai_bang_chung=loai_bang_chung,
                nguon_phat_ngon=nguon_phat_ngon,
                pham_vi_thoi_gian=pham_vi_thoi_gian,
                do_tin_cay="SUY ĐOÁN",
                trang_thai=trang_thai,
                is_grounded=True,
                action="SEND_TO_REVIEW",
                details=f"Lời kể từ nhân vật '{nguon_phat_ngon}', chưa thể xác nhận thành sự thật Canon."
            )

    # BƯỚC 5: XỬ LÝ HỒI TƯỞNG
    if loai_bang_chung in ["HỒI TƯỞNG"]:
        pham_vi_thoi_gian["loai"] = "QUÁ_KHỨ"
        return AtomicClaimResult(
            noi_dung=noi_dung,
            bang_chung=bang_chung,
            loai_bang_chung=loai_bang_chung,
            nguon_phat_ngon=nguon_phat_ngon,
            pham_vi_thoi_gian=pham_vi_thoi_gian,
            do_tin_cay=do_tin_cay,
            trang_thai=trang_thai,
            is_grounded=True,
            action="CREATE_CANON" if do_tin_cay == "XÁC NHẬN" else "SEND_TO_REVIEW",
            details="Hồi tưởng quá khứ -> Ghi nhận Canon Quá khứ, không đổi trạng thái Hiện tại."
        )

    # BƯỚC 6: XỬ LÝ SUY LUẬN YẾU HOẶC XUNG ĐỘT
    if loai_bang_chung == "SUY LUẬN" or do_tin_cay != "XÁC NHẬN" or trang_thai == "XUNG ĐỘT":
        return AtomicClaimResult(
            noi_dung=noi_dung,
            bang_chung=bang_chung,
            loai_bang_chung=loai_bang_chung,
            nguon_phat_ngon=nguon_phat_ngon,
            pham_vi_thoi_gian=pham_vi_thoi_gian,
            do_tin_cay=do_tin_cay,
            trang_thai="XUNG ĐỘT" if trang_thai == "XUNG ĐỘT" else "CHỜ_XÁC_MINH",
            is_grounded=True,
            action="SEND_TO_REVIEW",
            details="Đưa vào Hàng chờ duyệt do độ tin cậy chưa tuyệt đối hoặc có xung đột."
        )

    # BƯỚC 7: TRỰC TIẾP + XÁC NHẬN -> HỢP LỆ CANON
    return AtomicClaimResult(
        noi_dung=noi_dung,
        bang_chung=bang_chung,
        loai_bang_chung="TRỰC TIẾP",
        nguon_phat_ngon=nguon_phat_ngon,
        pham_vi_thoi_gian=pham_vi_thoi_gian,
        do_tin_cay="XÁC NHẬN",
        trang_thai="BÌNH THƯỜNG",
        is_grounded=True,
        action="CREATE_CANON",
        details="Mệnh đề nguyên tử hợp lệ 100%, được cấp phép ghi nhận vào Canon DB."
    )

# ==============================================================================
# 5. TEMPORAL RELATION & AUDIT MANAGER (APPEND-ONLY)
# ==============================================================================

class TemporalRelationManager:
    """Quản lý quan hệ có tính thời gian dạng Append-Only (không ghi đè lịch sử)."""
    
    def __init__(self):
        self.relations: List[TemporalRelation] = []
        self.history_audit_trail: List[dict] = []

    def add_or_update_relation(
        self,
        rel_id: str,
        source_id: str,
        rel_type: str,
        target_id: str,
        current_chapter: int,
        evidence: str,
        noi_dung: str = "",
        confidence: str = "XÁC NHẬN",
        status: str = "BÌNH THƯỜNG",
        speaker: str = "NGƯỜI_KỂ_CHUYỆN"
    ) -> TemporalRelation:
        existing = [
            r for r in self.relations
            if r.source_id == source_id and r.target_id == target_id and r.hieu_luc_den_chuong is None
        ]
        
        if existing:
            for old_rel in existing:
                if old_rel.relation_type != rel_type or status == "ĐÃ THAY ĐỔI":
                    old_rel.hieu_luc_den_chuong = current_chapter
                    self.history_audit_trail.append({
                        "event": "ĐÓNG_CỬA_SỔ_THỜI_GIAN",
                        "relation_id": old_rel.relation_id,
                        "closed_at_chapter": current_chapter,
                        "old_type": old_rel.relation_type
                    })
        
        new_rel = TemporalRelation(
            relation_id=rel_id,
            source_id=source_id,
            relation_type=rel_type,
            target_id=target_id,
            noi_dung=noi_dung or f"{source_id} là {rel_type} của {target_id}",
            hieu_luc_tu_chuong=current_chapter,
            hieu_luc_den_chuong=None,
            evidence=evidence,
            confidence=confidence,
            status=status,
            speaker=speaker
        )
        self.relations.append(new_rel)
        self.history_audit_trail.append({
            "event": "MỞ_CỬA_SỔ_THỜI_GIAN",
            "relation_id": rel_id,
            "opened_at_chapter": current_chapter,
            "type": rel_type
        })
        return new_rel

    def query_relation_at_chapter(self, source_id: str, target_id: str, chapter_num: int) -> Optional[TemporalRelation]:
        """Truy vấn quan hệ giữa 2 thực thể tại một chương bất kỳ trong quá khứ/hiện tại."""
        for r in self.relations:
            if r.source_id == source_id and r.target_id == target_id:
                start_ok = (r.hieu_luc_tu_chuong is None) or (r.hieu_luc_tu_chuong <= chapter_num)
                end_ok = (r.hieu_luc_den_chuong is None) or (r.hieu_luc_den_chuong >= chapter_num)
                if start_ok and end_ok:
                    return r
        return None

# ==============================================================================
# 6. UNIFIED CANON ENGINE VALIDATOR (THẨM PHÁN THỰC THỂ & MỆNH ĐỀ)
# ==============================================================================

def validate_single_entity_extraction(
    entity_dict: dict,
    raw_text: str,
    current_chapter: int,
    is_chapter_translated: bool,
    existing_index: List[EntityIndexEntry]
) -> ValidationResult:
    """
    Thực hiện thẩm định toàn diện Thực thể và danh sách Atomic Claims (khang_dinh[]).
    """
    name_vi = (entity_dict.get("ten_vi") or entity_dict.get("name_vi") or "").strip()
    name_goc = (entity_dict.get("ten_goc") or entity_dict.get("name_orig") or "").strip()
    stage = "CONFIRMED_CANON" if is_chapter_translated else "FUTURE_EVIDENCE"
    
    # 1. Thu thập danh sách Atomic Claims
    raw_claims = entity_dict.get("khang_dinh", [])
    if not raw_claims and (entity_dict.get("bang_chung") or entity_dict.get("evidence")):
        # Backward-compat: Tạo 1 claim duy nhất từ trường cũ
        raw_claims = [{
            "noi_dung": entity_dict.get("ghi_chu") or entity_dict.get("note") or name_vi,
            "bang_chung": entity_dict.get("bang_chung") or entity_dict.get("evidence") or "",
            "loai_bang_chung": entity_dict.get("loai_bang_chung") or entity_dict.get("evidence_type") or "TRỰC TIẾP",
            "nguon_phat_ngon": entity_dict.get("nguon_phat_ngon") or "NGƯỜI_KỂ_CHUYỆN",
            "do_tin_cay": entity_dict.get("do_tin_cay") or entity_dict.get("confidence") or "XÁC NHẬN",
            "trang_thai": entity_dict.get("trang_thai") or entity_dict.get("status") or "BÌNH THƯỜNG"
        }]

    # 2. Thẩm định từng Claim độc lập (Claim Coverage)
    validated_claims = []
    canon_claims = []
    rejected_claims = []
    review_claims = []
    
    for c in raw_claims:
        claim_res = validate_single_atomic_claim(c, raw_text, current_chapter)
        validated_claims.append(claim_res)
        if claim_res.action == "CREATE_CANON":
            canon_claims.append(claim_res)
        elif claim_res.action == "REJECT_HALLUCINATION":
            rejected_claims.append(claim_res)
        elif claim_res.action == "SEND_TO_REVIEW":
            review_claims.append(claim_res)

    # Nếu tất cả claim đều bị rejected do hallucination
    if raw_claims and len(rejected_claims) == len(raw_claims):
        return ValidationResult(
            is_valid=False,
            action="REJECT_HALLUCINATION",
            standard_name=name_vi,
            original_name=name_goc,
            claims=validated_claims,
            rejected_claims=rejected_claims,
            written_to_canon=False,
            in_review_queue=False,
            log_evidence=False,
            details=f"Toàn bộ {len(rejected_claims)} mệnh đề đều bị từ chối do bằng chứng giả mạo."
        )

    # 3. Phân giải thực thể (Entity Resolution)
    res_type, matched_entity, merge_info = resolve_entity(entity_dict, existing_index)
    
    if res_type == "EXISTING":
        return ValidationResult(
            is_valid=True,
            action="SKIP_CANON",
            entity_id=matched_entity.entity_id,
            standard_name=matched_entity.standard_name,
            original_name=matched_entity.original_name,
            claims=validated_claims,
            canon_claims=canon_claims,
            review_claims=review_claims,
            rejected_claims=rejected_claims,
            written_to_canon=False,
            in_review_queue=len(review_claims) > 0,
            log_evidence=True,
            stage=stage,
            details=f"Entity đã tồn tại trong Canon DB ({matched_entity.entity_id}). Ghi nhận {len(canon_claims)} claims mới vào Sổ cái bằng chứng."
        )
        
    if res_type == "UPGRADE_MERGE":
        return ValidationResult(
            is_valid=True,
            action="UPGRADE_MERGE",
            entity_id=matched_entity.entity_id,
            standard_name=merge_info.get("new_name_vi", name_vi),
            original_name=merge_info.get("new_name_orig", name_goc),
            claims=validated_claims,
            canon_claims=canon_claims,
            review_claims=review_claims,
            rejected_claims=rejected_claims,
            written_to_canon=True,
            in_review_queue=False,
            log_evidence=True,
            stage=stage,
            aliases=[matched_entity.standard_name],
            details=f"Nâng cấp tên chuẩn hóa của {matched_entity.entity_id} từ '{matched_entity.standard_name}' lên '{name_vi}'."
        )
        
    if res_type == "ADD_ALIAS":
        return ValidationResult(
            is_valid=True,
            action="ADD_ALIAS",
            entity_id=matched_entity.entity_id,
            standard_name=matched_entity.standard_name,
            original_name=matched_entity.original_name,
            claims=validated_claims,
            canon_claims=canon_claims,
            review_claims=review_claims,
            rejected_claims=rejected_claims,
            written_to_canon=True,
            in_review_queue=False,
            log_evidence=True,
            stage=stage,
            aliases=[merge_info.get("new_alias", name_vi)],
            details=f"Bổ sung bí danh '{name_vi}' vào hồ sơ {matched_entity.entity_id} ({matched_entity.standard_name})."
        )

    # 4. Entity Mới hoàn toàn
    # Nếu chỉ có claims tâm lý/tưởng tượng -> Chỉ ghi Evidence Log
    if canon_claims and all(c.action == "EVIDENCE_LOG_ONLY" for c in validated_claims):
        return ValidationResult(
            is_valid=True,
            action="EVIDENCE_LOG_ONLY",
            standard_name=name_vi,
            original_name=name_goc,
            claims=validated_claims,
            written_to_canon=False,
            in_review_queue=False,
            log_evidence=True,
            stage=stage,
            details="Chỉ ghi Sổ cái bằng chứng (ngữ cảnh không phải sự kiện thực tế hiện tại)."
        )

    if not canon_claims and review_claims:
        return ValidationResult(
            is_valid=True,
            action="SEND_TO_REVIEW",
            standard_name=name_vi,
            original_name=name_goc,
            claims=validated_claims,
            review_claims=review_claims,
            written_to_canon=False,
            in_review_queue=True,
            log_evidence=True,
            stage=stage,
            details=f"Đưa vào Hàng chờ duyệt do {len(review_claims)} mệnh đề chưa đủ xác thực."
        )

    can_write_canon = (stage == "CONFIRMED_CANON" and len(canon_claims) > 0)
    
    return ValidationResult(
        is_valid=True,
        action="CREATE_CANON",
        standard_name=name_vi,
        original_name=name_goc,
        claims=validated_claims,
        canon_claims=canon_claims,
        review_claims=review_claims,
        rejected_claims=rejected_claims,
        written_to_canon=can_write_canon,
        in_review_queue=len(review_claims) > 0,
        log_evidence=True,
        stage=stage,
        hieu_luc_tu_chuong=current_chapter,
        details=f"Entity mới hợp lệ với {len(canon_claims)} mệnh đề đạt chuẩn Canon DB."
    )
